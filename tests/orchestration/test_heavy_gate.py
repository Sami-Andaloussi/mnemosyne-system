"""guarded_heavy_run + may_start_heavy_run (Q1 / D111) - the ONE seam the heavy CLIs wrap their work in.

Proves the two composed bounds: the HEALTH pre-flight (:func:`may_start_heavy_run`) refuses fail-closed
on a CRITICAL disk BEFORE the lock is even touched (cheap-before-expensive, fail-fast), only WARNS on a
DEGRADED signal (the run still proceeds), and is silent when fully healthy; and that
:func:`guarded_heavy_run` composes health + the cross-process ``HeavyRunLock`` correctly - releasing the
lock on exit even when the body raises, coordinating two gates on the same lock path, and staying
backward-compatible when ``health=None`` (lock-only, the pre-Q1 skeleton path). Brick-free (D126)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.guard.heavy_lock import HeavyRunBusy
from mnemosyne.ports import HealthReport, HealthState
from mnemosyne.runtime.health import may_start_heavy_run
from mnemosyne.runtime.heavy import HeavyRunRefused, guarded_heavy_run


def _report(state: HealthState, **overrides: object) -> HealthReport:
    """A fully-healthy ``HealthReport`` by default; override just the signal(s) under test."""
    fields: dict[str, object] = dict(
        state=state,
        disk_ok=True,
        ram_ok=True,
        thermal_ok=True,
        runner_up=True,
        stores_reachable=True,
        queue_depth=0,
        error_rate=0.0,
    )
    fields.update(overrides)
    return HealthReport(**fields)


# ---- may_start_heavy_run: the pre-flight rule in isolation ------------------------------
def test_may_start_heavy_run_refuses_fail_closed_on_critical_disk() -> None:
    ok, reason = may_start_heavy_run(_report(HealthState.CRITICAL, disk_ok=False))
    assert ok is False
    assert reason and "CRITICAL" in reason


def test_may_start_heavy_run_warns_but_allows_on_degraded() -> None:
    ok, reason = may_start_heavy_run(_report(HealthState.DEGRADED, ram_ok=False))
    assert ok is True
    assert reason  # a non-empty warning - the run still proceeds


def test_may_start_heavy_run_is_silent_when_fully_healthy() -> None:
    assert may_start_heavy_run(_report(HealthState.OK)) == (True, "")


# ---- guarded_heavy_run: health pre-flight composed with the lock ------------------------
def test_guarded_heavy_run_refuses_before_the_lockfile_is_ever_created(tmp_path: Path) -> None:
    lock_path = tmp_path / "heavy_run.lock"
    with pytest.raises(HeavyRunRefused):
        with guarded_heavy_run(
            "library-ingestion",
            health=lambda: _report(HealthState.CRITICAL, disk_ok=False),
            lock_path=lock_path,
        ):
            raise AssertionError("the body must never run once the health pre-flight refuses")
    assert not lock_path.exists()  # fail-fast: health is checked BEFORE the lock is touched


def test_guarded_heavy_run_surfaces_a_degraded_warning_and_still_runs_the_body(
    tmp_path: Path,
) -> None:
    notes: list[str] = []
    ran = False
    with guarded_heavy_run(
        "library-ingestion",
        health=lambda: _report(HealthState.DEGRADED, thermal_ok=False),
        lock_path=tmp_path / "heavy_run.lock",
        on_notice=notes.append,
    ):
        ran = True
    assert ran
    assert (
        len(notes) == 1 and notes[0]
    )  # the DEGRADED warning reached on_notice; the run was NOT refused


def test_guarded_heavy_run_is_silent_and_runs_the_body_when_healthy(tmp_path: Path) -> None:
    notes: list[str] = []
    ran = False
    with guarded_heavy_run(
        "library-ingestion",
        health=lambda: _report(HealthState.OK),
        lock_path=tmp_path / "heavy_run.lock",
        on_notice=notes.append,
    ):
        ran = True
    assert ran
    assert notes == []  # nothing to surface when fully healthy


def test_two_gates_on_the_same_lock_path_the_second_is_busy(tmp_path: Path) -> None:
    # real default locker (genuine flock), no health arg - proves the lock itself coordinates the gates.
    lock_path = tmp_path / "heavy_run.lock"
    first = guarded_heavy_run("library-ingestion", lock_path=lock_path)
    first.__enter__()  # kept open, mirroring "enter the first, then try the second"
    try:
        with pytest.raises(HeavyRunBusy):
            with guarded_heavy_run("figures-enrich", lock_path=lock_path):
                raise AssertionError(
                    "the second body must never run while the first holds the lock"
                )
    finally:
        first.__exit__(None, None, None)


def test_lock_is_released_even_when_the_body_raises(tmp_path: Path) -> None:
    lock_path = tmp_path / "heavy_run.lock"
    with pytest.raises(ValueError, match="boom"):
        with guarded_heavy_run("library-ingestion", lock_path=lock_path):
            raise ValueError("boom")
    # released on the way out despite the exception: a fresh gate on the same path acquires fine
    with guarded_heavy_run("figures-enrich", lock_path=lock_path):
        pass


def test_health_none_skips_the_health_gate_only_the_lock_applies(tmp_path: Path) -> None:
    lock_path = tmp_path / "heavy_run.lock"
    ran = False
    with guarded_heavy_run("library-ingestion", health=None, lock_path=lock_path):
        ran = True
        assert (
            lock_path.exists()
        )  # the lock IS still taken even with no health gate (backward-compat)
    assert ran
