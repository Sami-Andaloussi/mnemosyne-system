"""Heavy-run lock (Q1 / D95 / invariants 16 / 26) - "one heavy task at a time" made real ACROSS processes.

The :class:`~mnemosyne.guard.bounds.BoundedScheduler`'s concurrency bound (``[bounds] concurrency = 1``:
one big model at a time, D95 / invariant 26) is IN-PROCESS - it coordinates work items inside one engine.
But the heavy CLI entrypoints (``make ingest`` / ``figures-enrich`` / ``youtube-ingest``) are SEPARATE OS
processes, each cold-starting multi-GB models; two launched at once both load and thrash the machine's RAM
/ GPU - the exact "two commands run in parallel are not coordinated" gap. This lock realizes the SAME
``concurrency = 1`` invariant ACROSS processes: a heavy run acquires it before loading anything heavy; a
second heavy run finds it held and is refused fail-closed (the invariant-16 / D78 posture - a bound is
active when a breach REFUSES, not when it is merely written down).

**Mechanism.** An advisory ``fcntl.flock(LOCK_EX | LOCK_NB)`` on a lockfile under ``system/state`` (gitignored).
``flock`` is tied to the OPEN FILE DESCRIPTION, so if a holder CRASHES the kernel releases it automatically -
no stale-lock wedge (the frequent pidfile failure mode). The lockfile also carries a one-line owner STAMP
(``name`` / ``pid`` / ``since``) purely so a refusal can name WHO holds it and SINCE WHEN; correctness rests
on ``flock``, never on the stamp (a stale stamp left by a crashed holder cannot wedge a new acquire, because
the ``flock`` is already gone). Deny-by-default, fail-closed, non-destructive - this touches none of user's
data, only a coordination lockfile.

The lock MECHANISM is injectable (:class:`Locker`), so the suite drives both the free and the busy paths
deterministically without spawning a second real process, brick-free (D126). Code & docstrings are English
(D117); in the original system the user-facing refusal text is shown to the user in French (D33) - it has
been translated to English below for this public mirror.

Decisions: D95 (one big model at a time)  -  D78 / invariant 16 (a bound REFUSES, fail-closed)  -  D80
(fail-closed)  -  D96 (non-destructive). Invariants carried: 16 / 26 (concurrency, made cross-process).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

#: Repo root from this module (``system/lib/mnemosyne/guard/heavy_lock.py`` -> parents[4] = repo).
_REPO_ROOT = Path(__file__).resolve().parents[4]
#: The coordination lockfile - one heavy run holds it at a time. Under ``system/state`` (gitignored,
#: reconstructible: a coordination lock is pure runtime state, never user's data - portability floor, Q3).
DEFAULT_LOCK_PATH = _REPO_ROOT / "system" / "state" / "heavy_run.lock"

#: Bytes read back from the lockfile for the owner stamp - a single short JSON line, capped defensively.
_STAMP_READ_BYTES = 4096


class HeavyRunBusy(RuntimeError):
    """Raised fail-closed when another heavy run already holds the lock (invariant 16 / D95).

    Carries the current :class:`HeavyRunHolder` (when the stamp is readable) so the CLI can tell user
    exactly what is running and since when - a legible refusal, never a silent block nor the current
    uncoordinated collision."""

    def __init__(self, message: str, *, holder: HeavyRunHolder | None = None) -> None:
        super().__init__(message)
        self.holder = holder


@dataclass(frozen=True, slots=True)
class HeavyRunHolder:
    """Who holds the heavy-run lock, read from the lockfile stamp - for the refusal MESSAGE only.

    Never trusted for the "is it held?" decision (that rests on ``flock``): a stamp left by a crashed
    holder is stale, but the ``flock`` it wrote is already released, so a new acquire still succeeds."""

    name: str
    pid: int
    since: str  # iso-8601

    @classmethod
    def from_stamp(cls, raw: str) -> HeavyRunHolder | None:
        """Parse the one-line JSON stamp, fail-open: any malformed / partial line yields ``None``.

        The stamp is best-effort UX (who holds the lock), so a garbled or half-written line degrades to
        a generic refusal message rather than crashing the refusal path (D100)."""
        try:
            data = json.loads(raw)
            return cls(name=str(data["name"]), pid=int(data["pid"]), since=str(data["since"]))
        except (ValueError, TypeError, KeyError):
            return None


class Locker(Protocol):
    """The advisory-lock mechanism behind :class:`HeavyRunLock` - injectable so the suite is brick-free.

    :meth:`try_acquire` is NON-BLOCKING: it returns ``True`` if the exclusive lock was taken, ``False`` if
    another holder has it (never blocks, so a second heavy run refuses fast). :meth:`release` drops it."""

    def try_acquire(self, fd: int) -> bool: ...

    def release(self, fd: int) -> None: ...


class FlockLocker:  # pragma: no cover - the real fcntl path (machine-only; the suite injects a fake)
    """Default :class:`Locker`: a non-blocking exclusive ``fcntl.flock`` (BSD/macOS, D103-adjacent).

    ``LOCK_EX | LOCK_NB`` takes the lock or raises ``BlockingIOError`` when held -> ``try_acquire`` returns
    ``False`` (refuse fast). The lock rides the fd, so a crashed holder is auto-released by the kernel."""

    __slots__ = ()

    def try_acquire(self, fd: int) -> bool:
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def release(self, fd: int) -> None:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


class HeavyRunLock:
    """A cross-process "one heavy run at a time" lock (realizes ``[bounds] concurrency = 1``, D95).

    Use it as a context manager around a heavy section::

        with HeavyRunLock(path, "library-ingestion"):
            ...  # cold-start the big model + run the batch

    :meth:`acquire` takes the advisory lock or raises :class:`HeavyRunBusy` fail-closed (naming the current
    holder); :meth:`release` drops it and is idempotent. Non-destructive: it writes only its own stamp to
    the coordination lockfile, never touches user's data. ``pid`` / ``now`` / ``locker`` are injectable so
    the suite proves both the free and busy paths deterministically (D126)."""

    __slots__ = ("_path", "_name", "_pid", "_now", "_locker", "_fd")

    def __init__(
        self,
        path: Path | str,
        name: str,
        *,
        pid: int | None = None,
        now: Callable[[], datetime] | None = None,
        locker: Locker | None = None,
    ) -> None:
        self._path = Path(path)
        self._name = name
        self._pid = pid if pid is not None else os.getpid()
        # ``now`` is a clock CALLABLE returning an aware datetime; default = real UTC now. Injectable so the
        # stamp's timestamp is deterministic under test.
        self._now = now if now is not None else (lambda: datetime.now(timezone.utc))
        self._locker: Locker = locker if locker is not None else FlockLocker()
        self._fd: int | None = None

    def acquire(self) -> None:
        """Take the lock, or raise :class:`HeavyRunBusy` fail-closed if another heavy run holds it.

        Opens (creating) the lockfile, tries the non-blocking exclusive lock, and on success stamps it with
        ``{name, pid, since}`` (truncating any stale stamp) and ``fsync``\\ s so a concurrent refusal can read
        who holds it. On failure it reads the current holder's stamp for the message, closes its fd (dropping
        no lock - it never held one), and refuses. Double-acquire in one process is a misuse (``RuntimeError``)."""
        if self._fd is not None:
            raise RuntimeError(f"heavy-run lock {self._name!r} already acquired in this process")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        if not self._locker.try_acquire(fd):
            holder = self._read_holder(fd)
            os.close(fd)
            raise HeavyRunBusy(self._busy_message(holder), holder=holder)
        try:
            os.ftruncate(fd, 0)
            stamp = json.dumps(
                {"name": self._name, "pid": self._pid, "since": self._now().isoformat()}
            )
            os.write(fd, stamp.encode("utf-8"))
            os.fsync(fd)
        except OSError:  # stamping is best-effort UX; a write hiccup must not drop a lock we hold
            pass
        self._fd = fd

    def release(self) -> None:
        """Release the lock and close the fd - idempotent (a no-op if not held), so ``finally`` is safe."""
        if self._fd is None:
            return
        try:
            self._locker.release(self._fd)
        finally:
            os.close(self._fd)
            self._fd = None

    def holder(self) -> HeavyRunHolder | None:
        """The current owner stamp, or ``None`` - read-only, NEVER a liveness check (see the class note).

        A missing lockfile yields ``None``; a present one yields its parsed stamp (or ``None`` if garbled).
        This is the stamp, not proof the lock is held - a crashed holder leaves a stale stamp whose ``flock``
        is already gone. For "is a heavy run actually running?", attempt an :meth:`acquire` (it is the only
        honest liveness signal)."""
        if not self._path.is_file():
            return None
        fd = os.open(self._path, os.O_RDONLY)
        try:
            return self._read_holder(fd)
        finally:
            os.close(fd)

    def _read_holder(self, fd: int) -> HeavyRunHolder | None:
        """Read + parse the owner stamp from an open fd (seek to 0 first), fail-open to ``None``."""
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            raw = os.read(fd, _STAMP_READ_BYTES).decode("utf-8", "replace").strip()
        except OSError:
            return None
        return HeavyRunHolder.from_stamp(raw) if raw else None

    def _busy_message(self, holder: HeavyRunHolder | None) -> str:
        """The refusal message shown to the user - names the holder when its stamp is readable (D33).

        Shown to the user in French in the original system; translated to English here for this
        public mirror."""
        if holder is None:
            return (
                "a heavy run is already in progress (lock held) - only one heavy run at a time (D95). "
                "Retry once it has finished."
            )
        return (
            f"a heavy run is already in progress: {holder.name!r} (PID {holder.pid}) since {holder.since} "
            "- only one heavy run at a time (D95). Retry once it has finished."
        )

    def __enter__(self) -> HeavyRunLock:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> bool:
        self.release()
        return False
