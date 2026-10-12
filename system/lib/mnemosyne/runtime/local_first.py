"""Local-first start (invariant 1 / D27) — the weights are on the disk, so nothing dials out.

A field report from a downstream project's bench (2026-07-21) measured a cold start sitting **30 minutes**
inside ``real_runtime()``: 39 s of CPU over 29:55 (it was asleep), one socket in ``CLOSE_WAIT``
to the Hugging Face CDN, no timeout ever firing — while every weight it needed was already in
``~/.cache/huggingface/hub``. Re-run with the HF stack forced offline, the same weights loaded in
**under a second**. Two distinct defects, and the report judged the second the worse:

1. **Robustness.** A system whose whole premise is *local-first* let an OUTBOUND dependency decide
   whether it starts at all. That is structural, not bad luck: it recurs on any network where a
   connection half-closes instead of failing cleanly (captive portal, slow DNS, a CDN dropping the
   peer). The close is a POSTURE, not a retry: the model cache is read offline by default, so there
   is no socket to hang on. Note what this is NOT: ``HF_HUB_ETAG_TIMEOUT`` already defaulted to 10 s
   on the machine that hung for 30 minutes — a timeout is a hope, not a guarantee, so the bounded
   waits below are only a belt for the branch a human OPENS on purpose.
2. **Visibility.** Nothing was printed for 30 minutes. Nothing distinguished "loading a big model"
   from "dead on a socket"; it took ``ps`` + ``lsof`` to tell. A blocked step that NAMES itself
   turns 30 minutes into 30 seconds — so every heavy step announces itself BEFORE it runs, and
   every line is FLUSHED (an announcement buffered behind the hang would be just as invisible).

Why the env vars are not enough on their own, measured: ``huggingface_hub`` reads
``HF_HUB_OFFLINE`` **at import** into ``huggingface_hub.constants``, so an ``os.environ`` write
after the package is imported changes nothing. :func:`enforce_local_first` therefore does both —
sets the environment (correct for anything not yet imported, and inherited by subprocesses) AND
forces the flag on every already-imported ``huggingface_hub`` module that still holds ``False``.
That single choke point is what ``transformers``, ``FlagEmbedding`` and ``mlx_lm`` all download
through, so forcing it there covers the stack (verified: ``transformers.utils.hub.is_offline_mode()``
flips with it, and a cached resolve then opens ZERO sockets).

Code & docstrings English (D117). In the source repository, operator-facing lines are French, for
the operator who reads them directly; this public mirror translates them to English throughout.
Decisions: D27 / invariant 1 (local-first) · D100 (refuse / degrade, never hang) · D126.
"""

from __future__ import annotations

import http.client
import os
import socket
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from types import ModuleType
from typing import TextIO
from urllib.parse import urlsplit

#: The env switch a HUMAN sets to let a start reach the network — a first install, or a deliberate
#: model refresh. Local-first is the DEFAULT (invariant 1), so going out is an explicit act, and the
#: posture line PRINTS which branch is live: an opened door nobody can see is the same trap again.
ALLOW_DOWNLOAD_ENV = "MNEMOSYNE_ALLOW_MODEL_DOWNLOAD"

#: The offline posture: read the model cache, never the CDN. ``TRANSFORMERS_OFFLINE`` is redundant on
#: recent ``transformers`` (which re-exports the hub flag) and harmless on older ones — kept because
#: the field workaround used it and a copied command should keep working.
_OFFLINE_ENV: Mapping[str, str] = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}

#: The belt for the branch a human OPENED (``ALLOW_DOWNLOAD_ENV``): if the start is allowed out, its
#: waits are at least BOUNDED, so the worst case is a refusal instead of an indefinite sleep. Set only
#: on that branch, and never over a value the caller chose (their number always wins).
_BOUNDED_WAIT_ENV: Mapping[str, str] = {
    "HF_HUB_ETAG_TIMEOUT": "5",
    "HF_HUB_DOWNLOAD_TIMEOUT": "30",
}

#: The flag every download in the HF stack is gated on, wherever a stale copy of it is bound.
_FLAG = "HF_HUB_OFFLINE"

_HF_PACKAGE = "huggingface_hub"


_TRUTHY = ("1", "true", "yes", "on")
_FALSY = ("0", "false", "no", "off")


def _is_true(raw: str | None) -> bool:
    return raw is not None and raw.strip().lower() in _TRUTHY


def _is_false(raw: str | None) -> bool:
    """Explicitly false — NOT merely absent. Absent means "nobody decided", which is not consent."""
    return raw is not None and raw.strip().lower() in _FALSY


#: How long one loopback connect may take before the service counts as down. A local port either
#: answers in microseconds or refuses instantly; this is a belt against a half-open socket, the same
#: failure shape as the CDN hang above — bounded, so the preflight can never become the new stall.
_PROBE_TIMEOUT = 1.0


class StartupDependencyError(RuntimeError):
    """A LOCAL service the start cannot work without is not answering.

    Raised BEFORE any weight is read, carrying the operator message: what is down, at which address,
    what breaks without it, and the exact gesture that brings it back.

    **It is an ordinary ``Exception``, and an isolated audit is why.** The first version derived from
    ``SystemExit``, to print the message alone instead of a twelve-frame traceback — right problem,
    wrong instrument. A ``BaseException`` walks straight through every ``except Exception`` in the
    repo, and two of those are FAIL-CLOSED barriers, measured: the orchestration drain
    (:mod:`~mnemosyne.runtime.engine`, which marks a job FAILED *rather than crash the drain and leak
    its RUNNING slot*, D80 / invariant 26) and ``backup.restore`` (a runtime that cannot be rebuilt is
    a FAILED restore, *never a false ok*, D109). Both were traversed — the drain left a job RUNNING
    forever and never ran the next one. **A refusal must never be more privileged than the barriers
    it passes through.** The readability is bought instead by :func:`install_refusal_hook`, which acts
    only when NOTHING caught the refusal — exactly the case where a human is the last reader."""


@dataclass(frozen=True, slots=True)
class ServiceDependency:
    """A local service a real start depends on — and the gesture that revives it.

    Built with :meth:`at` from the SAME url constant the connection uses, so the check and the
    connection cannot drift apart. ``remedy`` is a command the operator can actually type (a repair
    that requires writing code never happens, measured); ``without_it`` says what stops working,
    because "Qdrant is down" means nothing to a reader who does not know what Qdrant carries."""

    label: str
    url: str
    remedy: str
    without_it: str

    @classmethod
    def at(cls, url: str, *, label: str, remedy: str, without_it: str) -> ServiceDependency:
        dep = cls(label=label, url=url, remedy=remedy, without_it=without_it)
        dep.address()  # fail at import, not at the first start, if the url carries no port
        return dep

    def address(self) -> tuple[str, int]:
        """``(host, port)`` parsed from :attr:`url` — never a second, hand-written copy."""
        parsed = urlsplit(self.url)
        if not parsed.hostname or parsed.port is None:
            raise ValueError(
                f"dependency {self.label!r}: url without host or without port ({self.url!r})"
            )
        return parsed.hostname, parsed.port


def probe_tcp(host: str, port: int, *, timeout: float = _PROBE_TIMEOUT) -> bool:
    """Whether ``host:port`` accepts a connection. One bounded loopback connect, no protocol talk."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def speaks_http(host: str, port: int, *, timeout: float = _PROBE_TIMEOUT, path: str = "/") -> bool:
    """Whether SOMETHING at ``host:port`` answers an HTTP request — ANY status code counts.

    An accepted TCP connection proves a port is HELD, not that the service is there: an audit walked
    the preflight past a socket that never spoke a word, and past ``docker-proxy``, which binds the
    port the instant a container starts and well before Qdrant answers. The start would then have
    paid the eleven seconds anyway — the exact failure the check exists to prevent.

    Deliberately status-BLIND: a 404, a 403 "API key required", a 500 all prove a server is on the
    other end, which is the whole question here. Pinning a specific endpoint or a 200 would make a
    version bump, or an auth setting, refuse a perfectly working index — a false kill is as bad as a
    miss (measured on this very arc).

    **``HTTPConnection`` and not ``urlopen``, and this is a local-first barrier, not a style choice.**
    The first version used ``urlopen`` with a ``# noqa: S310 - loopback only`` comment asserting what
    it could not enforce, and a second audit measured the comment false in two directions: with
    ``http_proxy`` set, CPython routes even a ``localhost`` URL through the proxy (there is no
    implicit loopback bypass without ``no_proxy``), and ``urlopen`` FOLLOWS redirects, so whatever
    holds port 6333 could answer ``302`` and send the start off to any host on earth. Both were
    observed leaving the machine — inside the module whose entire purpose is that nothing does.
    ``HTTPConnection`` talks to the socket it is given: no proxy lookup, no redirect. The invariant
    becomes an INCAPACITY instead of a claim in a comment (D100)."""
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        connection.request("GET", path)
        connection.getresponse()  # a 4xx/5xx is an ANSWER: something is alive on the other end
        return True
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def answers(dependency: ServiceDependency, *, timeout: float = _PROBE_TIMEOUT) -> bool:
    """The real probe: the port is held AND something behind it speaks HTTP.

    TCP first because it fails in microseconds on the common case (nothing listening), so a dead
    dependency stays instant; the HTTP round-trip only runs on a port that is actually held."""
    host, port = dependency.address()
    return probe_tcp(host, port, timeout=timeout) and speaks_http(host, port, timeout=timeout)


def unreachable(
    dependencies: Sequence[ServiceDependency],
    *,
    probe: Callable[[ServiceDependency], bool] = answers,
) -> tuple[ServiceDependency, ...]:
    """The subset of ``dependencies`` that does not answer. Pure given ``probe``, so it is tested
    both ways — a down service refuses, and a live one passes (a check that refuses everything is
    as broken as one that refuses nothing)."""
    return tuple(dep for dep in dependencies if not probe(dep))


def dependency_refusal(down: Sequence[ServiceDependency]) -> str:
    """The operator message for a start that cannot proceed. English in this mirror (French in the
    source, for the operator who reads it directly)."""
    lines = [
        f"UNREACHABLE LOCAL DEPENDENCY — {len(down)} service(s) not responding.",
        "Startup stops HERE, before loading a single weight.",
        "",
    ]
    for dep in down:
        host, port = dep.address()
        lines += [
            f"  · {dep.label}",
            f"    address   : {host}:{port} (nobody answers)",
            f"    without it: {dep.without_it}",
            f"    the fix   : {dep.remedy}",
        ]
    return "\n".join(lines)


#: Whether the refusal hook is already in place. A module-level flag, not a re-read of
#: ``sys.excepthook``, because the point is to install AT MOST ONCE per process — see below.
_HOOK_INSTALLED = False


def install_refusal_hook(*, out: TextIO | None = None) -> None:
    """Make an UNCAUGHT :class:`StartupDependencyError` print its message alone, without a traceback.

    Placed here rather than in the exception's base class, and that distinction is the whole lesson:
    a ``SystemExit`` would have bought the same readability by walking through every ``except
    Exception`` in the repo, including two fail-closed barriers. A hook fires ONLY when the exception
    reached the top of the interpreter — so a barrier that catches the refusal behaves exactly as
    before, and only the case where a HUMAN is the last reader changes.

    Three properties an audit had to measure into existence, each closing a real failure:

    * **IDEMPOTENT.** The first version chained a new hook on every call. A process refusing in a
      loop grew the chain without bound — 400 links measured at 401 refusals, and a ``RecursionError``
      at 1200, on an ORDINARY unrelated exception whose report was then lost entirely. A readability
      aid that can destroy the reporting of every other failure is a bad trade.
    * **THE STREAM IS READ WHEN WRITING**, never captured at install time. Captured, it froze onto a
      file that could since be closed (measured: the test suite left the hook bound to a closed
      handle), and a refusal inside ``contextlib.redirect_stderr`` printed NOTHING AT ALL — the
      1970s-grade defect of the original field report ("nothing was printed for 30 minutes"),
      faithfully recreated by the fix for readability.
    * **THREADS TOO.** Python consults ``threading.excepthook`` for an exception escaping a thread,
      so ``sys.excepthook`` alone never fired there."""
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED and out is None:
        return
    previous_sys, previous_thread = sys.excepthook, threading.excepthook

    def write(value: BaseException) -> None:
        # `out` when a caller supplied one (tests), else the CURRENT sys.stderr — resolved now, so a
        # redirect installed after this hook still receives the message.
        print(str(value), file=out if out is not None else sys.stderr, flush=True)

    def hook(kind: type[BaseException], value: BaseException, trace: object) -> None:
        if isinstance(value, StartupDependencyError):
            write(value)
            return
        previous_sys(kind, value, trace)  # type: ignore[arg-type]

    def thread_hook(args: object) -> None:
        value = getattr(args, "exc_value", None)
        if isinstance(value, StartupDependencyError):
            write(value)
            return
        previous_thread(args)  # type: ignore[arg-type]

    sys.excepthook = hook
    threading.excepthook = thread_hook  # type: ignore[assignment]
    _HOOK_INSTALLED = True


def require_services(
    dependencies: Sequence[ServiceDependency],
    *,
    reporter: StartupReporter | None = None,
    probe: Callable[[ServiceDependency], bool] = answers,
) -> None:
    """Refuse to start when a local service is down — EARLY, and saying the gesture.

    The same defect as the CDN hang above, one layer out and measured on 2026-07-27: ``make search``
    spent **11.6 s** loading bge-m3 and the reranker, then died on ``Connection refused`` because a
    container was stopped. Nothing was wrong with the weights; nothing in the message said so. The
    dependency is one round-trip away, so it is read FIRST.

    This tightens nothing: every function that assembles a real Runtime wires ``connect_qdrant()``,
    so a start that fails here would have failed anyway — only later, and worse. The readability hook
    is installed at the moment of refusal, which is the single point every entry passes through: no
    ``except`` clause to add per entry point, and nothing installed on the path that succeeds."""
    down = unreachable(dependencies, probe=probe)
    if not down:
        if reporter is not None:
            reporter.say(
                "reachable local dependencies: "
                + ", ".join(f"{d.address()[1]}" for d in dependencies)
            )
        return
    install_refusal_hook()
    raise StartupDependencyError(dependency_refusal(down))


@dataclass(frozen=True, slots=True)
class ModelCachePosture:
    """What the start actually did about the network — printable, and assertable in a test.

    Returned rather than merely applied: a posture nobody can read is a claim, and this repo
    prints margins instead of verdicts. ``forced`` names the already-imported modules whose stale
    ``HF_HUB_OFFLINE`` had to be overwritten — the failure mode env vars alone cannot fix."""

    offline: bool
    applied: Mapping[str, str]
    forced: tuple[str, ...]

    def line(self) -> str:
        """The one line the operator reads to know which branch is live."""
        if self.offline:
            forced = f", {len(self.forced)} binding(s) forced" if self.forced else ""
            return (
                "local-first: model cache OFFLINE, no network egress at startup "
                f"(HF_HUB_OFFLINE=1{forced}) — to allow a download: "
                f"{ALLOW_DOWNLOAD_ENV}=1"
            )
        return (
            f"NETWORK ALLOWED at startup ({ALLOW_DOWNLOAD_ENV}=1 or HF_HUB_OFFLINE=0): a model "
            "absent from the cache will be downloaded, and the wait is bounded (etag 5 s, download 30 s) — "
            "without this setting, startup is offline"
        )


def enforce_local_first(
    env: MutableMapping[str, str] | None = None,
    modules: Mapping[str, ModuleType | None] | None = None,
) -> ModelCachePosture:
    """Make the model cache local-first BEFORE any brick is imported, and report what it did.

    Call this FIRST in a cold start: the environment is only read once by the HF stack, so a write
    that lands after ``import huggingface_hub`` is a write into the void. Both halves are needed and
    each covers what the other cannot — the env for what is not yet imported (and for subprocesses),
    the forced bindings for what already is.

    Idempotent, and it never fights the caller. EITHER human signal opens the door — Mnémosyne's own
    ``MNEMOSYNE_ALLOW_MODEL_DOWNLOAD=1`` or an explicit ``HF_HUB_OFFLINE=0`` — and both are honoured
    the same way, in the environment AND in the forced bindings. Half-honouring one (leaving the env
    var alone while forcing the in-memory flag to the opposite) would be worse than ignoring it: it
    would look respected and behave overridden. Absent is not consent: a variable nobody set means
    nobody decided, and the default is local (invariant 1)."""
    env = os.environ if env is None else env
    modules = sys.modules if modules is None else modules
    offline = not (_is_true(env.get(ALLOW_DOWNLOAD_ENV)) or _is_false(env.get("HF_HUB_OFFLINE")))
    wanted = _OFFLINE_ENV if offline else _BOUNDED_WAIT_ENV
    applied = {key: value for key, value in wanted.items() if key not in env}
    env.update(applied)
    forced: tuple[str, ...] = ()
    if offline:
        forced = _force_offline_bindings(modules)
    return ModelCachePosture(offline=offline, applied=applied, forced=forced)


def _force_offline_bindings(modules: Mapping[str, ModuleType | None]) -> tuple[str, ...]:
    """Overwrite every stale ``HF_HUB_OFFLINE`` an already-imported ``huggingface_hub`` module holds.

    Scoped to that package on purpose. It is the choke point the whole stack downloads through, and
    probing attributes on ``transformers`` submodules instead trips its lazy-alias shim into hundreds
    of deprecation warnings — noise is a cost, and covering the choke point is what changes behaviour.
    A module that does not carry the flag, or already has it ``True``, is left untouched."""
    forced: list[str] = []
    for name, module in list(modules.items()):
        if module is None or not (name == _HF_PACKAGE or name.startswith(f"{_HF_PACKAGE}.")):
            continue
        if getattr(module, _FLAG, None) is False:
            setattr(module, _FLAG, True)
            forced.append(name)
    return tuple(forced)


#: Addresses that never leave the machine. Local-first does not mean "no sockets" — Qdrant, tantivy's
#: sidecars and the WhisperKit server all live on loopback, and a start MUST reach them. The line that
#: matters is the machine's edge, so the instrument below counts only what crosses it.
_LOOPBACK_HOSTS = frozenset({"", "localhost", "localhost.", "127.0.0.1", "::1", "0.0.0.0", "::"})


def _is_local_address(address: object) -> bool:
    """Is this connect target on this machine? A non-tuple address is a UNIX socket (local)."""
    if not isinstance(address, tuple) or not address:
        return True
    host = address[0]
    if not isinstance(host, str):
        return True
    return host in _LOOPBACK_HOSTS or host.startswith("127.")


@contextmanager
def watch_outbound_network(*, refuse: bool = False) -> Iterator[list[str]]:
    """Record every attempt to leave the MACHINE inside this block; loopback passes untouched.

    The instrument the field report asked for: "cut the network, start, and check it never tries to
    go out". Reporting the count beats asserting a posture flag — a flag says what we *set*, this
    says what actually happened at the edge. Both legs are watched because the failed start reached
    for DNS first (``getaddrinfo`` for ``huggingface.co:443``) and never got as far as ``connect``.

    ``refuse=False`` (default) observes and delegates, so a start that is LEGITIMATELY online still
    works and merely gets counted — that is the shape a smoke check wants. ``refuse=True`` makes any
    exit impossible, which is how a test proves the offline posture rather than trusting it. The
    patches are always undone, including through an exception."""
    import socket

    attempts: list[str] = []
    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect

    def _note(what: str) -> None:
        attempts.append(what)
        if refuse:
            raise OSError(f"outbound network is refused inside this block: {what}")

    def guarded_getaddrinfo(host, port, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not _is_local_address((host, port)):
            _note(f"dns {host}:{port}")
        return real_getaddrinfo(host, port, *args, **kwargs)

    def guarded_connect(self, address):  # type: ignore[no-untyped-def]
        if not _is_local_address(address):
            _note(f"connect {address}")
        return real_connect(self, address)

    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]
    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    try:
        yield attempts
    finally:
        socket.getaddrinfo = real_getaddrinfo  # type: ignore[assignment]
        socket.socket.connect = real_connect  # type: ignore[method-assign]


class StartupReporter:
    """Says which start step is running, so a blocked one NAMES itself instead of going silent.

    The field defect was not slowness, it was indistinguishability: a 30-minute sleep on a socket
    looked exactly like loading a big model. Each step prints BEFORE it runs (an "after" line cannot
    be reached by a step that never returns), FLUSHED at once (an announcement stuck in a buffer is
    invisible too), and reports its own elapsed time — including on the way out through an
    exception, so a failure says how long it took to fail."""

    __slots__ = ("_out", "_tag", "_index", "_total")

    def __init__(self, *, total: int, out: TextIO | None = None, tag: str = "runtime") -> None:
        self._out = out if out is not None else sys.stderr
        self._tag = tag
        self._index = 0
        self._total = total

    def say(self, message: str) -> None:
        print(f"[{self._tag}] {message}", file=self._out, flush=True)

    def posture(self, posture: ModelCachePosture) -> None:
        self.say(posture.line())

    @contextmanager
    def step(self, label: str) -> Iterator[None]:
        """Announce one start step, then time it — whichever way it leaves."""
        self._index += 1
        marker = f"{self._index}/{self._total}"
        self.say(f"{marker} {label}…")
        started = time.monotonic()
        try:
            yield
        except BaseException:
            self.say(f"{marker} {label} — FAILED after {time.monotonic() - started:.1f} s")
            raise
        else:
            self.say(f"{marker} {label} — ok ({time.monotonic() - started:.1f} s)")
