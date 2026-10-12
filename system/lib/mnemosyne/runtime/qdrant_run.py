"""qdrant_run — the missing GESTURE: see the vector index, and bring it back up.

The 2026-07-27 ergonomics measurement found ``make search`` failing after 11,6 s on
``Connection refused``. The diagnosis it produced ("no command starts Qdrant") was half
right, and the half that was wrong matters more: the server was not missing, it was **stopped** —
a Docker container named ``mnemo-qdrant``, created 2026-07-02, holding **240 498 indexed passages**,
named in exactly one place in the repo (an internal ignition log nobody
reads while searching). Every entry point needs it; nothing brought it back; the failure said
nothing. Two commands close that:

* ``make qdrant``     — is it listening, and WHAT DOES IT HOLD (point counts, per collection);
* ``make qdrant-up``  — start the existing container. Brick-free (stdlib only), so the door is
  fast: a door slower than the wall around it is never used (measured, 20:1).

**Why there is no local-file fallback here, though the plan called for one.** ``qdrant-client``
does offer an embedded mode (``QdrantClient(path=…)``), and it would have been a few lines. It was
refused on a measurement, not a preference: the 240 498 points live inside the container's own
writable layer (``docker inspect`` reports ZERO mounts), in the server's storage format, which the
python-side embedded mode cannot read — and embedded mode caps out around 20k points anyway (D68 /
D121-B2, why server mode was chosen). A file fallback would therefore start EMPTY and answer
"no trusted memory" (invariant 14) over a corpus that exists — a working-looking door
onto nothing. That is worse than a refusal: a refusal is read, a silent emptiness is believed.
Hence the opposite posture everywhere below: **the status always prints the point counts**, so an
empty index can never pass for the library, and ``qdrant-up`` never CREATES a container (a fresh
empty one would look identical to the real one from the outside).

Code & docstrings English (D117); operator lines French, like every surface the operator reads.
"""

from __future__ import annotations

import argparse
import http.client
import json
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TextIO
from urllib.parse import urlsplit

from ..stores import QDRANT_URL
from .local_first import ServiceDependency, answers

#: The container that holds the index on this machine (ALLUMAGE Phase 0, 2026-07-02). The SINGLE
#: source of that name: the status, the start gesture and the refusal message all read it here.
QDRANT_CONTAINER = "mnemo-qdrant"

#: What to run on a machine that has no container at all. Printed, NEVER executed (see ``start``):
#: creating one is a human act. Two differences from the container that exists on the operator's
#: Mac today, both deliberate — ``--restart`` so it survives a reboot, and a named volume so
#: ``docker rm`` stops being a data-destroying command.
CREATE_COMMAND = (
    f"docker run -d --name {QDRANT_CONTAINER} --restart unless-stopped "
    f"-p 6333:6333 -p 6334:6334 -v {QDRANT_CONTAINER}-storage:/qdrant/storage qdrant/qdrant"
)

_HTTP_TIMEOUT = 3.0


@dataclass(frozen=True, slots=True)
class Collection:
    """One Qdrant collection and how much it actually holds (``points < 0`` = count unreadable)."""

    name: str
    points: int


@dataclass(frozen=True, slots=True)
class Inventory:
    """What the server holds — or that we could not find out.

    The ``known`` flag is the whole point, and an isolated audit is what put it here. The first
    version returned a bare tuple, so "the API answered 500" and "there are no collections" arrived
    as the same empty tuple — and the status then printed a CONFIDENT ABSENCE over 240 498 live
    passages, with exit code 0. That is precisely the silent lie this module was written to prevent,
    reproduced by the module itself. ``ContainerFacts`` had the distinction from the start; the
    inventory did not, and no test noticed because the test PINNED the conflation."""

    known: bool
    collections: tuple[Collection, ...] = ()

    @property
    def readable_total(self) -> int:
        """Sum of the counts we could actually read — unreadable ones are NOT counted as zero."""
        return sum(c.points for c in self.collections if c.points >= 0)

    @property
    def unreadable(self) -> int:
        return sum(1 for c in self.collections if c.points < 0)


@dataclass(frozen=True, slots=True)
class ContainerFacts:
    """What Docker says about the container — or that Docker could not be asked.

    ``known=False`` means "we do not know", which is NOT "it does not exist": a machine without the
    ``docker`` CLI, or a daemon that is down, must not print a confident absence."""

    known: bool
    exists: bool = False
    running: bool = False
    restart_policy: str = ""
    mounts: int = 0
    why_unknown: str = ""

    @property
    def survives_reboot(self) -> bool:
        """A restart policy of ``no`` is why the index is down after every reboot of the Mac."""
        return self.restart_policy not in ("", "no")


@dataclass(frozen=True, slots=True)
class QdrantState:
    """Everything the status needs, gathered once so rendering stays pure and testable."""

    url: str
    listening: bool
    inventory: Inventory
    container: ContainerFacts


def _http_get_json(url: str) -> dict:  # pragma: no cover - real socket (the [OPERATOR] side)
    """One GET, decoded as JSON. ``HTTPConnection``, never ``urlopen``: same reason as
    :func:`~mnemosyne.runtime.local_first.speaks_http` — ``urlopen`` honours ``http_proxy`` even for
    localhost and FOLLOWS redirects, so a status command could leave the machine (measured). Here
    the socket is the one we name, which makes the local-first property an incapacity, not a claim."""
    parsed = urlsplit(url)
    connection = http.client.HTTPConnection(
        parsed.hostname or "localhost", parsed.port or 80, timeout=_HTTP_TIMEOUT
    )
    try:
        connection.request("GET", parsed.path or "/")
        response = connection.getresponse()
        if response.status >= 400:
            raise OSError(f"HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))
    finally:
        connection.close()


def read_collections(url: str, *, get: Callable[[str], dict] = _http_get_json) -> Inventory:
    """Collections and their point counts, via Qdrant's HTTP API. Brick-free (stdlib urllib).

    Two kinds of tolerance, and they are NOT the same:

    * the LISTING fails (server down, HTTP 500, an API key required, a reverse proxy, a payload that
      is not the shape we expect) ⇒ ``known=False``. We do not know what it holds, and saying "it
      holds nothing" would be a lie. ``HTTPError`` subclasses ``URLError``, so a 500 used to land in
      the same branch as a refused connection and produce a confident empty — the defect an audit
      found here. The catch is deliberately BROAD (``Exception``) because the failure modes of a
      remote JSON API are not enumerable, and a traceback out of this door would reproduce the very
      thing the door replaces.
    * ONE collection's detail fails ⇒ that collection is kept with ``-1`` points. Dropping the line
      would read like "there is no such collection"; an unknown count is not zero and not absence."""
    try:
        listing = get(f"{url.rstrip('/')}/collections")
        names = sorted(entry["name"] for entry in listing["result"]["collections"])
    except Exception:  # noqa: BLE001 - see docstring: unknown must never render as empty
        return Inventory(known=False)
    found = []
    for name in names:
        try:
            detail = get(f"{url.rstrip('/')}/collections/{name}")
            found.append(Collection(name=name, points=int(detail["result"]["points_count"])))
        except Exception:  # noqa: BLE001 - a single unreadable count, kept and marked
            found.append(Collection(name=name, points=-1))
    return Inventory(known=True, collections=tuple(found))


#: The one docker message that PROVES a container is absent. Anything else — a dead daemon, a
#: permission error, a context that does not exist — means "we could not ask", which leads to the
#: opposite gesture. Enumerating what PROVES absence, rather than blacklisting known failures.
_NO_SUCH_OBJECT = "no such object"


def _docker(args: Sequence[str]) -> tuple[int, str, str]:  # pragma: no cover - real subprocess
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["docker", *args], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return 127, "", "docker not found or unreachable"
    return done.returncode, (done.stdout or "").strip(), (done.stderr or "").strip()


def read_container(
    name: str = QDRANT_CONTAINER, *, run: Callable[[Sequence[str]], tuple[int, str, str]] = _docker
) -> ContainerFacts:
    """Ask Docker about the container. Best-effort, and CAREFUL about the difference between "it is
    not there" and "I could not ask".

    Only the literal ``No such object`` proves absence. A stopped Docker daemon also exits 1, and the
    first version read that as absence — handing the operator a ``docker run`` command to create a
    second, EMPTY container while their 240 498 passages sat intact in the one Docker could not be
    asked about. The stderr was being thrown away; it is the evidence."""
    code, out, err = run(
        [
            "inspect",
            "-f",
            "{{.State.Running}}|{{.HostConfig.RestartPolicy.Name}}|{{len .Mounts}}",
            name,
        ]
    )
    if code == 127:
        return ContainerFacts(known=False, why_unknown=err or "docker not found")
    if code == 0 and "|" in out:
        running, policy, mounts = (out.split("|") + ["", "", ""])[:3]
        return ContainerFacts(
            known=True,
            exists=True,
            running=running.strip().lower() == "true",
            restart_policy=policy.strip(),
            mounts=int(mounts) if mounts.strip().isdigit() else 0,
        )
    if _NO_SUCH_OBJECT in err.casefold():
        return ContainerFacts(known=True, exists=False)
    return ContainerFacts(known=False, why_unknown=err or f"docker returned code {code}")


def render_state(state: QdrantState) -> str:
    """The status a human reads. Pure, so every branch of it is asserted in the suite."""
    lines = [f"# Qdrant — Mnémosyne's vector index ({state.url})", ""]
    if not state.listening:
        lines += [
            "\U0000274C NOTHING ANSWERS. Every search, every recall, every ingest fails as long as this holds.",
            "",
            "   the fix: make qdrant-up",
        ]
    elif not state.inventory.known:
        # The dangerous middle case: it answers, but not with an inventory we can read. Saying
        # "0 passages" here would be a confident lie about a library that may be entirely intact.
        lines += [
            "\U000026A0\U0000FE0F IT ANSWERS, BUT I COULD NOT READ ITS INVENTORY.",
            '   So I do NOT know what it holds — this is **not** "it is empty".',
            "   (an HTTP error, an API key required, a proxy in front: all of these produce this case)",
        ]
    else:
        inventory = state.inventory
        lines.append(f"\U00002705 answers — {len(inventory.collections)} collection(s)")
        caveat = (
            f" (+ {inventory.unreadable} collection(s) with an UNREADABLE count, not counted)"
            if inventory.unreadable
            else ""
        )
        lines.append(f"   total read: {inventory.readable_total} passages{caveat}")
        lines.append("")
        for collection in inventory.collections:
            count = "unreadable count" if collection.points < 0 else f"{collection.points} passages"
            empty = "   \U000026A0\U0000FE0F EMPTY" if collection.points == 0 else ""
            lines.append(f"   · {collection.name} — {count}{empty}")
        if not inventory.collections:
            lines.append("   \U000026A0\U0000FE0F NO COLLECTION AT ALL: the server answers, but holds NOTHING.")
            lines.append("      An empty server answers just like a full one — hence this count.")
    lines.append("")
    lines += _render_container(state.container)
    return "\n".join(lines)


def _render_container(facts: ContainerFacts) -> list[str]:
    """The two facts that explain WHY it keeps dying, and what would destroy the index."""
    if not facts.known:
        why = f" ({facts.why_unknown})" if facts.why_unknown else ""
        return [
            f"container `{QDRANT_CONTAINER}`: I could NOT ask Docker{why}.",
            '   This is not "it does not exist": start Docker Desktop, then re-run `make qdrant`.',
        ]
    if not facts.exists:
        return [
            f"container `{QDRANT_CONTAINER}`: ABSENT from this machine.",
            "   to create it (a human act, never automatic):",
            f"   {CREATE_COMMAND}",
        ]
    lines = [
        f"container `{QDRANT_CONTAINER}`: {'running' if facts.running else 'STOPPED'}"
        f" · auto-restart: {facts.restart_policy or 'not declared'} · mounted volumes: {facts.mounts}"
    ]
    if not facts.survives_reboot:
        lines += [
            "   \U000026A0\U0000FE0F it does NOT come back after a Mac reboot — that is the cause of the 07/27 outage.",
            f"      to make it durable: docker update --restart unless-stopped {QDRANT_CONTAINER}",
        ]
    if facts.mounts == 0:
        lines += [
            "   \U000026A0\U0000FE0F NO VOLUME AT ALL: the index lives inside the container's own layer.",
            f"      `docker rm {QDRANT_CONTAINER}` would destroy the ~240,000 passages. Rebuildable",
            "      (D56: a derivative, the truth stays the .md files), but that is hours of re-indexing.",
        ]
    return lines


def wait_until_ready(
    url: str,
    *,
    deadline: float = 20.0,
    step: float = 0.25,
    ready: Callable[[str], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> bool:
    """Poll until the service actually ANSWERS, or give up at ``deadline``. Bounded, always.

 ``docker start`` returns 0 the moment the order is accepted, and ``docker-proxy`` binds the port
 immediately — so " it is back" was being printed several seconds before Qdrant could answer
 anything, and a ``make qdrant-up && make search`` chained right after could still be refused. An
 audit flagged it as a suspicion it could not execute (restarting the container was outside its
 mandate); it costs a bounded poll to remove, so it is removed rather than declared.

 **The deadline is read off a CLOCK, never summed from the sleeps.** A second audit measured the
 first version overshooting its announced bound by 5 to 6× (~100 s for a declared 20 s) against a
 held-but-mute port — precisely the state ``docker-proxy`` is in, and the only state this function
 exists for: each probe blocks for up to its own timeout, and none of that was being counted. The
 test that "proved" the bound injected a cost-free probe, so it only ever measured the sleeps it
 had itself supplied."""
    answered = ready if ready is not None else (lambda u: answers(_dependency(u)))
    started = now()
    while True:
        if answered(url):
            return True
        if now() - started >= deadline:
            return False
        sleep(step)


def render_start(facts: ContainerFacts, *, started: bool, ready: bool | None = None) -> str:
    """What ``make qdrant-up`` prints. Never creates: see the module docstring.

    ``ready`` is tri-state on purpose: ``None`` means nothing was started so readiness was never
    asked, ``True``/``False`` are an answer. Reporting "not ready" for a question nobody asked would
    be the same conflation this module fights everywhere else."""
    if not facts.known:
        return (
            "\U0000274C Docker is unreachable — cannot start the index.\n"
            "   Start Docker Desktop, then re-run `make qdrant-up`."
        )
    if not facts.exists:
        return (
            f"\U0000274C Container `{QDRANT_CONTAINER}` does not exist on this machine.\n"
            "   I do NOT create it: a fresh container is EMPTY and answers exactly like a\n"
            '   full one — search would say "no trusted memory" over a library\n'
            "   that exists. Creating one is your call, knowingly:\n"
            f"   {CREATE_COMMAND}"
        )
    if (started or facts.running) and ready is False:
        state = "restarted fine" if started else "was already running"
        return (
            f"\U000026A0\U0000FE0F `{QDRANT_CONTAINER}` {state}, but it is NOT ANSWERING.\n"
            "   The container is up and the port is taken; the service itself is not talking.\n"
            "   Wait a few seconds and check: make qdrant\n"
            f"   If it still does not answer: docker logs --tail 40 {QDRANT_CONTAINER}"
        )
    if facts.running and not started:
        return (
            f"\U00002705 `{QDRANT_CONTAINER}` was already running AND it answers. What it holds: make qdrant"
        )
    if started:
        return f"\U00002705 `{QDRANT_CONTAINER}` is back up AND it answers. What it holds: make qdrant"
    return (
        f"\U0000274C `{QDRANT_CONTAINER}` exists but refused to start.\n"
        f"   Check why: docker start {QDRANT_CONTAINER}"
    )


def read_state(
    url: str, *, run: Callable[[Sequence[str]], tuple[int, str, str]] = _docker
) -> QdrantState:
    """Gather everything the status needs. The only I/O; rendering stays pure."""
    listening = answers(_dependency(url))
    return QdrantState(
        url=url,
        listening=listening,
        inventory=read_collections(url) if listening else Inventory(known=False),
        container=read_container(run=run),
    )


def start_container(
    *, run: Callable[[Sequence[str]], tuple[int, str, str]] = _docker
) -> tuple[ContainerFacts, bool]:
    """Start the EXISTING container, or do nothing. **Never creates one** — and that abstention is
    the behaviour under test, not merely the wording of the refusal it prints.

    An audit found the guarantee untested: every assertion was on ``render_start``'s text, so a
    version that happily created a container passed the whole suite. ``run`` is injectable for that
    reason alone, and the test asserts the argv Docker actually receives contains no ``run`` and no
    ``create``. Why it matters: a fresh container is EMPTY and, from the outside, indistinguishable
    from the one holding the library."""
    facts = read_container(run=run)
    if facts.known and facts.exists and not facts.running:
        return facts, run(["start", QDRANT_CONTAINER])[0] == 0
    return facts, False


def cmd_etat(url: str, *, state: QdrantState | None = None, out: TextIO | None = None) -> int:
    """``make qdrant``. Exit code non-zero on "I could not read it" as well as on "it is down": a
    status that exits 0 while unable to see the library reads as success to every script and reader.

    Injectable, and NOT ``pragma: no cover``, because an audit sabotaged this exit code — and the
    whole readiness wiring of ``cmd_demarrer`` — with the entire suite staying green. The pure
    renderers were tested; the fact that anything CALLED them was held by nothing."""
    resolved = state if state is not None else read_state(url)
    print(render_state(resolved), file=out if out is not None else sys.stdout)
    return 0 if (resolved.listening and resolved.inventory.known) else 1


def cmd_demarrer(
    url: str,
    *,
    run: Callable[[Sequence[str]], tuple[int, str, str]] = _docker,
    ready: Callable[[str], bool] | None = None,
    deadline: float = 20.0,
    out: TextIO | None = None,
) -> int:
    """``make qdrant-up``. Readiness is asked whenever a container IS running — started just now or
    already up — because "it was already running" says nothing about whether it ANSWERS, and that
    branch is the likeliest one (a second `make qdrant-up`, or Docker Desktop restarting it).

    ``deadline`` is a parameter and not a constant so a test can bound the wait: without it, checking
    the mute branch cost the suite a real 20 seconds — a test that is expensive to run is a test that
    gets deleted."""
    facts, started = start_container(run=run)
    answered: bool | None = None
    if started or (facts.known and facts.running):
        answered = wait_until_ready(url, deadline=deadline, ready=ready)
    print(
        render_start(facts, started=started, ready=answered),
        file=out if out is not None else sys.stdout,
    )
    return 0 if answered else 1


def _dependency(url: str) -> ServiceDependency:
    """The same ServiceDependency the START uses, so this door and the preflight judge identically.
    An audit found them diverged: the preflight required an HTTP answer while this door was content
    with a held port, so `make qdrant` printed "IT ANSWERS" about `docker-proxy`."""
    return ServiceDependency.at(url, label="Qdrant", remedy="make qdrant-up", without_it="")


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - [OPERATOR] ignition
    parser = argparse.ArgumentParser(
        prog="make qdrant",
        description="See the vector index (and what it holds), or restart it.",
    )
    parser.add_argument("commande", choices=("etat", "demarrer"), nargs="?", default="etat")
    parser.add_argument(
        "--url", default=QDRANT_URL, help=f"server address (default {QDRANT_URL})"
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return cmd_etat(args.url) if args.commande == "etat" else cmd_demarrer(args.url)


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] ignition
    raise SystemExit(main())
