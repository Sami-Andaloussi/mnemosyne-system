"""HeavyRunLock (Q1 / D95) - the cross-process "one heavy run at a time" advisory lock.

Proves acquire / release / holder against BOTH the REAL ``fcntl.flock`` (genuine same-process
contention across two ``HeavyRunLock`` instances on the same lockfile - exactly the shape of two
``make ingest`` / ``make figures-enrich`` invocations colliding) and an injected fake :class:`Locker`
(deterministic free / busy paths, no real file locking needed). Also pins the owner stamp
(name / pid / since, clock-injected), :meth:`HeavyRunHolder.from_stamp`'s fail-open parsing, the
context-manager form, double-acquire misuse, and that :data:`DEFAULT_LOCK_PATH` resolves under
``system/state`` (gitignored coordination state). Brick-free, deterministic (D126)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mnemosyne.guard.heavy_lock import (
    DEFAULT_LOCK_PATH,
    HeavyRunBusy,
    HeavyRunHolder,
    HeavyRunLock,
)

_CLOCK = lambda: datetime(2026, 7, 15, 14, 2, tzinfo=timezone.utc)  # noqa: E731 - a deterministic clock
_PID = 1234


class _FakeLocker:
    """A deterministic ``Locker`` stub (D126): ``try_acquire`` returns a preset bool, never touches fcntl."""

    def __init__(self, acquires: bool) -> None:
        self._acquires = acquires
        self.released: list[int] = []

    def try_acquire(self, fd: int) -> bool:
        return self._acquires

    def release(self, fd: int) -> None:
        self.released.append(fd)


# ---- acquire / holder: the owner stamp -------------------------------------------------
def test_acquire_writes_a_stamp_that_holder_reads_back_with_the_injected_clock(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "heavy_run.lock"
    lk = HeavyRunLock(lock_path, "library-ingestion", pid=_PID, now=_CLOCK)
    lk.acquire()
    try:
        assert lk.holder() == HeavyRunHolder("library-ingestion", _PID, _CLOCK().isoformat())
    finally:
        lk.release()


# ---- real flock contention (no fake - genuine same-process fcntl contention) ------------
def test_real_flock_contention_refuses_the_second_acquire_naming_the_first_holder(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "heavy_run.lock"
    lk1 = HeavyRunLock(lock_path, "library-ingestion", pid=_PID, now=_CLOCK)
    lk2 = HeavyRunLock(lock_path, "figures-enrich", pid=_PID + 1, now=_CLOCK)
    lk1.acquire()
    try:
        with pytest.raises(HeavyRunBusy) as excinfo:
            lk2.acquire()
        # the refusal names the FIRST holder (name + pid), read back from the real lockfile stamp
        assert excinfo.value.holder == HeavyRunHolder(
            "library-ingestion", _PID, _CLOCK().isoformat()
        )
    finally:
        lk1.release()


def test_release_frees_the_lock_for_a_new_acquire_and_is_idempotent(tmp_path: Path) -> None:
    lock_path = tmp_path / "heavy_run.lock"
    lk1 = HeavyRunLock(lock_path, "library-ingestion", now=_CLOCK)
    lk1.acquire()
    lk1.release()
    lk1.release()  # calling it twice never raises (idempotent)
    lk2 = HeavyRunLock(lock_path, "figures-enrich", now=_CLOCK)
    lk2.acquire()  # the lock is genuinely free now
    lk2.release()


def test_release_before_any_acquire_is_a_noop(tmp_path: Path) -> None:
    lock_path = tmp_path / "never.lock"
    HeavyRunLock(lock_path, "never-acquired").release()  # no raise
    assert not lock_path.exists()  # never even opened - a true no-op, not a lazy-create + release


# ---- injected fake Locker: deterministic free / busy paths ------------------------------
def test_fake_locker_refusing_raises_busy_with_the_generic_message(tmp_path: Path) -> None:
    lk = HeavyRunLock(tmp_path / "heavy_run.lock", "library-ingestion", locker=_FakeLocker(False))
    with pytest.raises(HeavyRunBusy) as excinfo:
        lk.acquire()
    assert excinfo.value.holder is None  # a freshly-created lockfile carries no stamp yet
    msg = str(excinfo.value)
    assert "only one heavy run at a time" in msg
    assert "PID" not in msg  # the GENERIC message (no holder to name), not the named variant


def test_fake_locker_granting_lets_acquire_succeed(tmp_path: Path) -> None:
    lk = HeavyRunLock(tmp_path / "heavy_run.lock", "library-ingestion", locker=_FakeLocker(True))
    lk.acquire()
    assert lk.holder() is not None
    lk.release()


# ---- context-manager form ----------------------------------------------------------------
def test_context_manager_form_acquires_then_releases_on_exit(tmp_path: Path) -> None:
    lock_path = tmp_path / "heavy_run.lock"
    with HeavyRunLock(lock_path, "library-ingestion") as lk:
        assert lk.holder() is not None  # held during the block
    # released on exit: a fresh lock on the same path acquires fine
    lk2 = HeavyRunLock(lock_path, "figures-enrich")
    lk2.acquire()
    lk2.release()


# ---- misuse: double-acquire in one process -----------------------------------------------
def test_double_acquire_same_instance_without_release_is_a_misuse_error(tmp_path: Path) -> None:
    lk = HeavyRunLock(tmp_path / "heavy_run.lock", "library-ingestion")
    lk.acquire()
    try:
        with pytest.raises(RuntimeError, match="already acquired"):
            lk.acquire()
    finally:
        lk.release()


# ---- HeavyRunHolder.from_stamp: fail-open parsing -----------------------------------------
def test_from_stamp_parses_a_valid_json_line() -> None:
    raw = json.dumps(
        {"name": "library-ingestion", "pid": 999, "since": "2026-07-15T14:02:00+00:00"}
    )
    assert HeavyRunHolder.from_stamp(raw) == HeavyRunHolder(
        "library-ingestion", 999, "2026-07-15T14:02:00+00:00"
    )


def test_from_stamp_fails_open_to_none_on_garbled_partial_or_empty() -> None:
    assert HeavyRunHolder.from_stamp("{not json") is None  # garbled
    assert (
        HeavyRunHolder.from_stamp(json.dumps({"name": "x"})) is None
    )  # partial: missing pid/since
    assert HeavyRunHolder.from_stamp("") is None  # empty


# ---- holder() with no lockfile -------------------------------------------------------------
def test_holder_on_a_path_with_no_lockfile_is_none(tmp_path: Path) -> None:
    lk = HeavyRunLock(tmp_path / "absent.lock", "library-ingestion")
    assert lk.holder() is None


# ---- DEFAULT_LOCK_PATH + parent-dir creation ------------------------------------------------
def test_default_lock_path_is_under_system_state() -> None:
    assert DEFAULT_LOCK_PATH.parts[-3:] == ("system", "state", "heavy_run.lock")


def test_acquire_creates_the_parent_directory_when_missing(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "heavy_run.lock"
    assert not nested.parent.exists()
    lk = HeavyRunLock(nested, "library-ingestion")
    lk.acquire()
    try:
        assert nested.parent.is_dir() and nested.is_file()
    finally:
        lk.release()
