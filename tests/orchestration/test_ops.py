"""LOT 7 - health + graceful degradation (D111) and the Kopia backup (D110 / D118).

The doctrine-touching properties of the exploitation layer:

* **Graceful degradation is fail-safe (D111).** When the local runner is down, ``public`` work
  carries on (canal A) but ``perso`` / ``sensible`` work DEFERS - never a cloud path, so a panic
  cannot make the cloisonnement give way (invariant 1). Disk-full is CRITICAL: everything defers.
* **The backup is asymmetric and encrypted (D110 / D118).** Only the non-reconstructible truth is
  PRECIOUS; a non-public snapshot never lands on a non-zero-knowledge off-site target; and a
  backup is only trusted once restored + smoke-tested.

Decisions: D111 (health, graceful degradation)  -  D60 / D66 (sensible stays local)  -  D110 / D118
(asymmetric, zero-knowledge backup)  -  D109 (restore = smoke)  -  D121-E4 (human prerequisites).
Code & docstrings English (D117).
"""

from __future__ import annotations

import pytest

from mnemosyne.ports import (
    BackupClass,
    Bubble,
    GovernanceLabel,
    HealthState,
    Sensitivity,
    SnapshotId,
    TriggerKind,
    WorkId,
    WorkItem,
)
from mnemosyne.runtime import (
    BackupEngine,
    BackupRefused,
    HealthMonitor,
    KopiaBackup,
    OffSiteTarget,
    PRECIOUS_TARGETS,
    PrerequisiteState,
    StubHardwareProbe,
    bootstrap,
    check_human_prerequisites,
    graceful_degradation,
    run_smoke_test,
)


class _Probe:
    """A hardware probe with each signal forced, to drive the aggregate state."""

    def __init__(self, *, disk: bool = True, ram: bool = True, thermal: bool = True) -> None:
        self._disk, self._ram, self._thermal = disk, ram, thermal

    def disk_ok(self) -> bool:
        return self._disk

    def ram_ok(self) -> bool:
        return self._ram

    def thermal_ok(self) -> bool:
        return self._thermal


def _work(sid: str, sensitivity: Sensitivity) -> WorkItem:
    return WorkItem(
        id=WorkId(sid),
        trigger=TriggerKind.PERIODIC,
        descriptor=sid,
        label=GovernanceLabel(sensitivity=sensitivity, bubble=Bubble("b")),
    )


# --- health aggregation (D111) -----------------------------------------------------------
def test_healthy_when_all_signals_ok() -> None:
    assert HealthMonitor().report().state is HealthState.OK


def test_runner_down_or_pressure_is_degraded() -> None:
    assert HealthMonitor().report(runner_up=False).state is HealthState.DEGRADED
    assert HealthMonitor().report(stores_reachable=False).state is HealthState.DEGRADED
    assert HealthMonitor(hardware=_Probe(ram=False)).report().state is HealthState.DEGRADED


def test_disk_full_is_critical() -> None:
    report = HealthMonitor(hardware=_Probe(disk=False)).report()
    assert report.state is HealthState.CRITICAL
    assert not report.disk_ok


def test_stub_hardware_probe_reports_healthy() -> None:
    probe = StubHardwareProbe()
    assert probe.disk_ok() and probe.ram_ok() and probe.thermal_ok()


# --- graceful degradation, the fail-safe rule (D111) -------------------------------------
def test_runner_down_defers_non_public_and_never_clouds() -> None:
    items = (
        _work("pub", Sensitivity.PUBLIC),
        _work("perso", Sensitivity.PERSO),
        _work("sens", Sensitivity.SENSIBLE),
    )
    report = HealthMonitor().report(runner_up=False)
    plan = graceful_degradation(report, items)
    assert {w.id for w in plan.carry_on} == {WorkId("pub")}  # only public continues (canal A)
    assert {w.id for w in plan.deferred} == {WorkId("perso"), WorkId("sens")}
    # the guarantee: no non-public item is ever carried on (would be the cloud temptation)
    assert all(w.label.may_use_automatic_cloud() for w in plan.carry_on)


def test_disk_critical_defers_everything() -> None:
    items = (_work("pub", Sensitivity.PUBLIC), _work("sens", Sensitivity.SENSIBLE))
    report = HealthMonitor(hardware=_Probe(disk=False)).report()
    plan = graceful_degradation(report, items)
    assert plan.carry_on == ()
    assert {w.id for w in plan.deferred} == {WorkId("pub"), WorkId("sens")}


def test_healthy_carries_everything_locally() -> None:
    items = (_work("pub", Sensitivity.PUBLIC), _work("sens", Sensitivity.SENSIBLE))
    plan = graceful_degradation(HealthMonitor().report(), items)
    assert {w.id for w in plan.carry_on} == {WorkId("pub"), WorkId("sens")}
    assert plan.deferred == ()


# --- backup: asymmetry + zero-knowledge off-site (D110 / D118) ---------------------------
def test_precious_and_derived_are_distinct_classes() -> None:
    kb = KopiaBackup()
    precious = kb.snapshot(BackupClass.PRECIOUS)
    derived = kb.snapshot(BackupClass.DERIVED)
    assert "precious" in precious and "derived" in derived


def test_local_only_backup_allows_non_public() -> None:
    # local-only repo versions the sensible (D71) - no off-site barrier applies
    assert KopiaBackup(contains_non_public=True).snapshot()


def test_clear_offsite_refuses_non_public() -> None:
    kb = KopiaBackup(off_site=OffSiteTarget("s3-clear"), contains_non_public=True)
    with pytest.raises(BackupRefused):  # never sensible in clear off the machine (D118)
        kb.snapshot()


def test_zero_knowledge_offsite_accepts_non_public() -> None:
    zk = OffSiteTarget("b2", encrypted=True, zero_knowledge=True, keys_stored_separately=True)
    assert zk.may_receive_non_public()
    assert KopiaBackup(off_site=zk, contains_non_public=True).snapshot()


def test_public_only_treasure_allows_clear_offsite() -> None:
    kb = KopiaBackup(off_site=OffSiteTarget("s3-clear"), contains_non_public=False)
    assert kb.snapshot()  # nothing non-public to protect => the barrier does not trip


def test_verify_restore_runs_the_smoke_test() -> None:
    report = KopiaBackup().verify_restore()
    assert report.smoke_test_passed
    assert "disposable" in report.restored_into  # restored into a throwaway bubble (D99)


class _SpyBackupEngine:
    """A backup engine that records what it was asked to snapshot / restore (the (3)-6b brick's seam)."""

    def __init__(self) -> None:
        self.snapshots: list[tuple[BackupClass, tuple[str, ...]]] = []
        self.restores: list[tuple[SnapshotId, str]] = []

    def create_snapshot(self, klass: BackupClass, targets: tuple[str, ...]) -> SnapshotId:
        self.snapshots.append((klass, targets))
        return SnapshotId(f"real-{klass.value}-{len(self.snapshots)}")

    def restore_snapshot(self, snapshot: SnapshotId, *, into: str) -> None:
        self.restores.append((snapshot, into))


def test_snapshot_delegates_to_the_injected_engine() -> None:
    # the real Kopia CLI plugs in behind the SAME couture (barrier stays ours): the engine does the I/O.
    engine = _SpyBackupEngine()
    assert isinstance(engine, BackupEngine)  # structural conformance to the seam
    sid = KopiaBackup(engine=engine).snapshot(BackupClass.PRECIOUS)
    assert sid == "real-precious-1"  # the engine minted it, not the stub
    assert engine.snapshots == [
        (BackupClass.PRECIOUS, PRECIOUS_TARGETS)
    ]  # the named treasure (D110)


def test_offsite_barrier_runs_BEFORE_the_engine() -> None:
    # the security barrier is couture, applied before the brick - a refused snapshot never reaches the
    # engine, so a swapped engine can never leak sensible off a clear target (D118 / D100).
    engine = _SpyBackupEngine()
    kb = KopiaBackup(off_site=OffSiteTarget("s3-clear"), contains_non_public=True, engine=engine)
    with pytest.raises(BackupRefused):
        kb.snapshot()
    assert engine.snapshots == []  # the engine was NEVER reached


def test_restore_delegates_to_engine_then_smokes() -> None:
    engine = _SpyBackupEngine()
    report = KopiaBackup(engine=engine).restore(SnapshotId("s1"), into="/tmp/bubble")
    assert engine.restores == [(SnapshotId("s1"), "/tmp/bubble")]  # real restore I/O ran
    assert report.smoke_test_passed  # then the smoke validated the rebuilt system (D109)


def test_verify_restore_smokes_the_restored_runtime_not_a_fresh_stub() -> None:
    # audit (3)-7 M1: the restore proof must exercise the RESTORED tree - the smoke runs against the
    # runtime the injected factory builds FROM `into`, not an unrelated fresh stub (else "proven" is
    # hollow: the smoke would green even if the restore produced garbage). This wires the affordance
    # run_smoke_test(runtime=...) was designed for (D110 / D109).
    seen: list[str] = []

    def factory(into: str):
        seen.append(into)  # at ignition: build a runtime ROOTED at the restored `into`
        return bootstrap()

    report = KopiaBackup(restore_runtime=factory).verify_restore()
    assert report.smoke_test_passed
    assert seen == [
        report.restored_into
    ]  # the smoke's runtime was built FROM the restored location


def test_restore_is_fail_closed_when_the_restored_runtime_cannot_be_built() -> None:
    # a restore whose runtime cannot be rebuilt from the restored tree is NOT proven - never a false ok.
    def broken(_into: str):
        raise RuntimeError("restored tree unreadable")

    report = KopiaBackup(restore_runtime=broken).restore(SnapshotId("s1"), into="/tmp/x")
    assert (
        not report.smoke_test_passed
    )  # fail-closed: a restore we cannot read is not a backup (D110)


# --- human prerequisites: FLAG, never fail (D121-E4) ------------------------------------
def test_prerequisites_flag_unknown_by_default() -> None:
    prereqs = check_human_prerequisites()
    assert {p.name for p in prereqs} == {"icloud_adp", "kopia_offsite_key", "api_cost_ceiling"}
    assert all(p.state is PrerequisiteState.UNKNOWN and p.flagged for p in prereqs)


def test_prerequisites_confirmed_do_not_flag() -> None:
    prereqs = check_human_prerequisites(
        adp_confirmed=True, kopia_key_confirmed=True, api_ceiling_confirmed=True
    )
    assert all(p.state is PrerequisiteState.CONFIRMED and not p.flagged for p in prereqs)


def test_missing_prerequisite_flags_loudly() -> None:
    prereqs = check_human_prerequisites(adp_confirmed=False)
    adp = next(p for p in prereqs if p.name == "icloud_adp")
    assert adp.state is PrerequisiteState.MISSING and adp.flagged


def test_smoke_report_carries_prerequisites() -> None:
    report = run_smoke_test()
    assert report.passed
    assert len(report.prerequisites) == 3
