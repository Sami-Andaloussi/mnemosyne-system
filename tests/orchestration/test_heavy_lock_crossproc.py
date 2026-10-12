"""The heavy-run lock across REAL OS processes (Q1) - the guarantee the single-process suite cannot prove.

``test_heavy_lock.py`` exercises the flock MECHANISM with two ``HeavyRunLock`` instances in one interpreter
(two open-file-descriptions). But Q1's entire reason to exist is coordinating two SEPARATE processes (two
``make`` in two terminals), and the "a crashed holder is auto-released by the kernel - no permanent wedge"
claim is a property of ``flock`` being tied to the open-file-description, not the object. These two tests
pin BOTH with genuine subprocesses, so a future refactor that silently breaks cross-process behaviour - e.g.
switching ``flock`` (per-OFD) to ``lockf`` (per-process), or closing the fd before the run ends - fails here
instead of shipping. Slower than the rest (spawns Python), but this is the headline invariant. Brick-free."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
from _invariants import REPO_ROOT

from mnemosyne.guard.heavy_lock import HeavyRunBusy, HeavyRunLock

#: A child that acquires the heavy-run lock in its OWN process, signals ready (writes its pid), and then
#: holds it by sleeping - until the parent kills it. ``sys.argv`` = [lock_path, ready_path, libdir].
_CHILD_HOLDER = """
import sys, time
from pathlib import Path

sys.path.insert(0, sys.argv[3])
from mnemosyne.guard.heavy_lock import HeavyRunLock

lock_path, ready_path = sys.argv[1], sys.argv[2]
lock = HeavyRunLock(lock_path, "child-holder")
lock.acquire()
Path(ready_path).write_text(str(__import__("os").getpid()), encoding="utf-8")
time.sleep(30)  # hold the lock until the parent tears us down
"""

_LIBDIR = str(REPO_ROOT / "system" / "lib")


def _spawn_holder(tmp_path: Path, lock_path: Path) -> tuple[subprocess.Popen[bytes], int]:
    """Start a real child process holding ``lock_path``; return ``(process, its_pid)`` once it has acquired.

    Blocks (briefly) until the child signals ready by writing its pid, so the parent never races the child's
    acquire. Raises if the child dies before acquiring or never becomes ready."""
    script = tmp_path / "holder.py"
    script.write_text(_CHILD_HOLDER, encoding="utf-8")
    ready = tmp_path / "ready"
    proc = subprocess.Popen([sys.executable, str(script), str(lock_path), str(ready), _LIBDIR])
    for _ in range(200):  # up to ~10 s, polling every 50 ms
        if ready.is_file():
            return proc, int(ready.read_text(encoding="utf-8"))
        if proc.poll() is not None:
            raise RuntimeError(f"holder child exited early with {proc.returncode}")
        time.sleep(0.05)
    proc.kill()
    raise RuntimeError("holder child never signalled ready")


def test_a_second_os_process_is_refused_while_the_first_holds(tmp_path: Path) -> None:
    """The headline guarantee: while a real process holds the lock, a second one is refused fail-closed."""
    lock_path = tmp_path / "heavy.lock"
    proc, child_pid = _spawn_holder(tmp_path, lock_path)
    try:
        with pytest.raises(HeavyRunBusy) as exc_info:
            HeavyRunLock(lock_path, "parent").acquire()
        # the refusal names the REAL other-process holder (its pid), not a same-interpreter stand-in
        assert exc_info.value.holder is not None
        assert exc_info.value.holder.pid == child_pid
        assert exc_info.value.holder.name == "child-holder"
    finally:
        proc.kill()
        proc.wait(timeout=5)


def test_a_killed_holder_auto_releases_the_lock_no_wedge(tmp_path: Path) -> None:
    """No permanent wedge: SIGKILL the holder (no ``finally``, no ``release``) - the next run still acquires."""
    lock_path = tmp_path / "heavy.lock"
    proc, _ = _spawn_holder(tmp_path, lock_path)
    proc.kill()  # SIGKILL - the child never runs release(); only the kernel drops the flock on process death
    proc.wait(timeout=5)

    lock = HeavyRunLock(lock_path, "parent")
    lock.acquire()  # must NOT raise - a stale stamp remains, but the flock is gone, so the acquire succeeds
    try:
        holder = lock.holder()
        assert (
            holder is not None and holder.name == "parent"
        )  # the new run overwrote the stale stamp
    finally:
        lock.release()
