"""D93 - the orchestration engine loop that DRIVES the bounded scheduler.

Biting tests for :mod:`mnemosyne.runtime.engine`. The ``BoundedScheduler`` substrate was complete
but nothing in production ever moved work through it (``.dispatch()`` had no production caller,
RESTE_A_FAIRE §1). These prove the missing loop closes that gap: a submitted workflow is dispatched
under the bound and run, and the engine reacts by GRAVITY - a normal return COMPLETEs, an
``EscalateToHuman`` SUSPENDs and frees the slot (fail-safe, D96 / inv. 26), any other error FAILs
the job without crashing the drain (fail-closed, D80). The first REAL background workflow
(``verify_restore``, D110) is exercised end-to-end through the production ``CoreApi`` surface, and an
unknown descriptor is refused at admission (deny-by-default). Brick-free: nothing installed (D126).
"""

from __future__ import annotations

from dataclasses import replace

from pytest import raises

from mnemosyne.api.core_api import CoreApi
from mnemosyne.guard.bounds import BoundedScheduler
from mnemosyne.ports import (
    Bubble,
    EscalateToHuman,
    GovernanceLabel,
    HealthReport,
    ResourceBoundError,
    Sensitivity,
    TriggerKind,
    WorkId,
    WorkItem,
    WorkState,
)
from mnemosyne.ports.backup import RestoreReport, SnapshotId
from mnemosyne.runtime import DrainReport, OrchestrationEngine, bootstrap
from mnemosyne.runtime.health import HealthMonitor


def _label() -> GovernanceLabel:
    """A minimal governance label for a background work item (the data it touches)."""
    return GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("ops"))


def _item(wid: str, descriptor: str, *, trigger: TriggerKind = TriggerKind.PERIODIC) -> WorkItem:
    return WorkItem(id=WorkId(wid), trigger=trigger, descriptor=descriptor, label=_label())


def _item_s(wid: str, descriptor: str, sensitivity: Sensitivity) -> WorkItem:
    """A background item carrying a chosen sensitivity - to exercise the D111 fail-safe partition."""
    label = GovernanceLabel(sensitivity=sensitivity, bubble=Bubble("ops"))
    return WorkItem(
        id=WorkId(wid), trigger=TriggerKind.PERIODIC, descriptor=descriptor, label=label
    )


class _Disk:
    """A hardware probe with a toggleable disk signal (RAM / thermal healthy) - drives the D111 state:
    ``disk_ok=False`` folds to ``CRITICAL`` (every write unsafe), otherwise the monitor reports OK."""

    def __init__(self, *, ok: bool) -> None:
        self._ok = ok

    def disk_ok(self) -> bool:
        return self._ok

    def ram_ok(self) -> bool:
        return True

    def thermal_ok(self) -> bool:
        return True


class _Backup:
    """A duck-typed backup whose restore verification passes / fails on command (D110)."""

    def __init__(self, *, passed: bool) -> None:
        self._passed = passed

    def verify_restore(self) -> RestoreReport:
        return RestoreReport(
            snapshot=SnapshotId("snap"), restored_into="disposable", smoke_test_passed=self._passed
        )


# --------------------------------------------------------------------------- #
# The engine loop - graded reaction over the scheduler substrate (D93 / D80 / D96).           #
# --------------------------------------------------------------------------- #
def test_run_ready_runs_a_workflow_and_completes_it() -> None:
    """A submitted job is dispatched, run, and moved to DONE - the loop the scheduler lacked."""
    ran: list[str] = []
    scheduler = BoundedScheduler(capacity=4, concurrency=1)
    engine = OrchestrationEngine(scheduler, workflows={"w": lambda: ran.append("w")})
    wid = engine.submit(_item("j1", "w"))

    report = engine.run_ready()

    assert ran == ["w"]
    assert report == DrainReport(completed=(wid,))
    assert scheduler.state(wid) == WorkState.DONE


def test_escalate_to_human_suspends_the_job_and_frees_the_slot() -> None:
    """A workflow that needs a human SUSPENDs (fail-safe) and releases its slot (D96 / inv. 26)."""
    scheduler = BoundedScheduler(capacity=4, concurrency=1)

    def _needs_human() -> None:
        raise EscalateToHuman("awaiting user's canal-B gesture (D96)")

    engine = OrchestrationEngine(scheduler, workflows={"esc": _needs_human})
    wid = engine.submit(_item("j", "esc"))

    report = engine.run_ready()

    assert report == DrainReport(suspended=(wid,))
    assert scheduler.state(wid) == WorkState.SUSPENDED
    assert wid in scheduler.suspended_ids()  # the human-validation queue (D74 / D96)
    assert scheduler.slots_free() == 1  # the slot was released - another may run


def test_a_hard_error_fails_the_job_but_the_drain_continues() -> None:
    """A failing job is marked FAILED and surfaced (fail-closed, D80); it never crashes the drain."""
    ran: list[str] = []
    scheduler = BoundedScheduler(capacity=8, concurrency=1)

    def _boom() -> None:
        raise RuntimeError("boom")

    engine = OrchestrationEngine(
        scheduler, workflows={"boom": _boom, "ok": lambda: ran.append("ok")}
    )
    bad = engine.submit(_item("bad", "boom"))
    good = engine.submit(_item("good", "ok"))

    report = engine.run_ready()

    assert report.failed == (bad,)
    assert report.completed == (good,)  # the other, independent job still ran
    assert ran == ["ok"]
    assert scheduler.state(bad) == WorkState.FAILED
    assert scheduler.state(good) == WorkState.DONE


def test_manual_interactive_work_is_run_before_background() -> None:
    """Interactive MANUAL work preempts a queued background pass (D106) - proven by run order."""
    order: list[str] = []
    scheduler = BoundedScheduler(capacity=8, concurrency=1)
    engine = OrchestrationEngine(
        scheduler,
        workflows={"bg": lambda: order.append("bg"), "ui": lambda: order.append("ui")},
    )
    engine.submit(_item("bg", "bg", trigger=TriggerKind.PERIODIC))
    engine.submit(_item("ui", "ui", trigger=TriggerKind.MANUAL))

    report = engine.run_ready()

    assert order == ["ui", "bg"]  # MANUAL first (D106)
    assert report.completed == (WorkId("ui"), WorkId("bg"))


def test_run_ready_drains_every_ready_job_in_one_pass() -> None:
    """One tick advances all work that CAN run now, re-dispatching as slots free (concurrency 2)."""
    ran: list[int] = []
    scheduler = BoundedScheduler(capacity=8, concurrency=2)
    engine = OrchestrationEngine(scheduler, workflows={"w": lambda: ran.append(1)})
    ids = [engine.submit(_item(f"j{i}", "w")) for i in range(3)]

    report = engine.run_ready()

    assert len(ran) == 3
    assert set(report.completed) == set(ids)


def test_submit_refuses_an_unknown_descriptor_fail_closed() -> None:
    """An unknown workflow is refused at admission - never queued as work the engine cannot run."""
    scheduler = BoundedScheduler(capacity=4)
    engine = OrchestrationEngine(scheduler, workflows={"known": lambda: None})

    with raises(KeyError):
        engine.submit(_item("j", "unknown"))
    with raises(KeyError):
        scheduler.state(WorkId("j"))  # it was never admitted to the scheduler


def test_run_ready_on_an_empty_queue_is_a_noop() -> None:
    """Nothing ready => an empty report, no dispatch - idempotent, safe to tick repeatedly."""
    engine = OrchestrationEngine(BoundedScheduler(capacity=4), workflows={})
    assert engine.run_ready() == DrainReport()


def test_scheduler_item_is_a_read_only_lookup() -> None:
    """The scheduler exposes a work item read-only (the engine reads it back); unknown ids raise."""
    scheduler = BoundedScheduler(capacity=4)
    work = _item("j", "w")
    scheduler.submit(work)
    assert scheduler.item(WorkId("j")) is work
    with raises(KeyError):
        scheduler.item(WorkId("nope"))


def test_a_suspended_job_re_runs_through_the_engine_after_resume() -> None:
    """After resume + another tick the engine re-runs the workflow - the suspend/resume round trip
    the ``scheduler.item()`` lookup rests on (it finds the job's workflow back the second time too)."""
    runs: list[int] = []
    scheduler = BoundedScheduler(capacity=4, concurrency=1)

    def _once_then_ok() -> None:
        runs.append(1)
        if len(runs) == 1:
            raise EscalateToHuman("needs a human the first time (D96)")

    engine = OrchestrationEngine(scheduler, workflows={"flaky": _once_then_ok})
    wid = engine.submit(_item("j", "flaky"))
    assert engine.run_ready().suspended == (wid,)  # first tick: suspended, slot freed

    scheduler.resume(wid)  # the FLAG cleared (a human acted)
    report = engine.run_ready()  # second tick: it runs to completion
    assert report.completed == (wid,)
    assert runs == [1, 1]
    assert scheduler.state(wid) == WorkState.DONE


def test_submit_propagates_the_queue_bound_fail_closed() -> None:
    """A full queue is refused fail-closed at submit (invariant 16) - the bound is never swallowed."""
    scheduler = BoundedScheduler(capacity=1)
    engine = OrchestrationEngine(scheduler, workflows={"w": lambda: None})
    engine.submit(_item("a", "w"))
    with raises(ResourceBoundError):
        engine.submit(_item("b", "w"))


def test_run_ready_terminates_even_if_a_workflow_self_submits() -> None:
    """A workflow that submits follow-up work cannot make the drain loop forever: one tick runs at
    most a full queue's worth (the anti-runaway floor, D78) and RETURNS - the fine cascade fan-out
    budget is a later, deliberate addition (soul (5)), not a silent infinite loop today."""
    scheduler = BoundedScheduler(capacity=4, concurrency=1)
    seen: list[int] = []

    def _cascade() -> None:
        seen.append(1)
        try:
            engine.submit(_item(f"more#{len(seen)}", "w"))
        except ResourceBoundError:
            pass  # queue full - the follow-up simply waits (bounded, non-destructive)

    engine = OrchestrationEngine(scheduler, workflows={"w": _cascade})
    engine.submit(_item("start", "w"))

    report = engine.run_ready()  # must RETURN, not hang
    assert 0 < len(seen) <= scheduler.capacity  # bounded by one queue's worth
    assert len(report.completed) <= scheduler.capacity


# --------------------------------------------------------------------------- #
# Graceful degradation before the run - the D111 fail-safe partition, wired into the loop.     #
# --------------------------------------------------------------------------- #
def test_health_critical_defers_every_job_without_running_it() -> None:
    """A full disk (CRITICAL) defers ALL work fail-safe: nothing runs, every job is retained and its
    slot released - no derived-store / backup write is attempted on an unsafe disk (D111 / D100)."""
    ran: list[str] = []
    scheduler = BoundedScheduler(capacity=8, concurrency=2)
    engine = OrchestrationEngine(
        scheduler,
        workflows={"w": lambda: ran.append("w")},
        health=lambda: HealthMonitor(hardware=_Disk(ok=False)).report(),
    )
    ids = [engine.submit(_item(f"j{i}", "w")) for i in range(3)]

    report = engine.run_ready()

    assert ran == []  # not a single workflow body ran - the disk is unsafe to write
    assert set(report.deferred) == set(ids)
    assert report.completed == () and report.failed == ()
    for wid in ids:
        assert scheduler.state(wid) == WorkState.SUSPENDED  # retained, non-destructive
    assert scheduler.slots_free() == 2  # every slot was released (invariant 26)


def test_health_runner_down_defers_non_public_and_never_clouds_it() -> None:
    """The headline D111 guarantee: a downed local runner runs the ``public`` (canal A) but DEFERS the
    ``perso`` / ``sensible`` - they are queued, never switched to the cloud to cope (invariant 1)."""
    ran: list[str] = []
    scheduler = BoundedScheduler(capacity=8, concurrency=1)
    engine = OrchestrationEngine(
        scheduler,
        workflows={"w": lambda: ran.append("w")},
        health=lambda: HealthMonitor().report(runner_up=False),
    )
    pub = engine.submit(_item_s("pub", "w", Sensitivity.PUBLIC))
    perso = engine.submit(_item_s("perso", "w", Sensitivity.PERSO))
    sens = engine.submit(_item_s("sens", "w", Sensitivity.SENSIBLE))

    report = engine.run_ready()

    assert report.completed == (pub,)  # only public continued
    assert set(report.deferred) == {perso, sens}  # non-public deferred, never clouded
    assert ran == ["w"]  # exactly one body ran (the public one)
    assert scheduler.state(pub) == WorkState.DONE
    assert scheduler.state(perso) == WorkState.SUSPENDED
    assert scheduler.state(sens) == WorkState.SUSPENDED


def test_health_ok_carries_every_job_including_sensible_locally() -> None:
    """A wired-but-healthy probe defers NOTHING - even ``sensible`` runs (it runs LOCALLY); the
    fail-safe never over-defers, so a healthy system behaves exactly as with no probe at all."""
    ran: list[str] = []
    scheduler = BoundedScheduler(capacity=8, concurrency=2)
    engine = OrchestrationEngine(
        scheduler,
        workflows={"w": lambda: ran.append("w")},
        health=lambda: HealthMonitor().report(),  # all-healthy
    )
    ids = [engine.submit(_item_s(f"j{i}", "w", Sensitivity.SENSIBLE)) for i in range(3)]

    report = engine.run_ready()

    assert len(ran) == 3
    assert set(report.completed) == set(ids)
    assert report.deferred == ()


def test_health_deferred_job_resumes_and_runs_when_the_signal_clears() -> None:
    """A deferred job is non-destructive and recoverable: once the disk clears and it is resumed, a
    later tick runs it to completion - deferral is a pause, never a drop (D111 / invariant 26)."""
    ran: list[str] = []
    state = {"disk_ok": False}
    scheduler = BoundedScheduler(capacity=4, concurrency=1)
    engine = OrchestrationEngine(
        scheduler,
        workflows={"w": lambda: ran.append("w")},
        health=lambda: HealthMonitor(hardware=_Disk(ok=state["disk_ok"])).report(),
    )
    wid = engine.submit(_item("j", "w"))

    assert engine.run_ready().deferred == (wid,)  # disk full -> deferred, retained
    assert ran == []
    assert scheduler.state(wid) == WorkState.SUSPENDED

    state["disk_ok"] = True  # the signal cleared
    scheduler.resume(wid)  # supervision resumes it (manual today, automatic with the daemon)
    report = engine.run_ready()  # a healthy tick runs it

    assert report.completed == (wid,)
    assert ran == ["w"]
    assert scheduler.state(wid) == WorkState.DONE


def test_health_runner_down_splits_a_multi_item_batch_by_item() -> None:
    """The fail-safe partition is PER-ITEM inside a single dispatched batch, not per-tick: at
    concurrency 2 a ``public`` and a ``perso`` start together, and only the ``perso`` is deferred."""
    ran: list[str] = []
    scheduler = BoundedScheduler(capacity=8, concurrency=2)
    engine = OrchestrationEngine(
        scheduler,
        workflows={"w": lambda: ran.append("w")},
        health=lambda: HealthMonitor().report(runner_up=False),
    )
    pub = engine.submit(_item_s("pub", "w", Sensitivity.PUBLIC))
    perso = engine.submit(_item_s("perso", "w", Sensitivity.PERSO))

    report = (
        engine.run_ready()
    )  # concurrency 2 -> both start in ONE batch, then the filter splits them

    assert report.completed == (pub,)
    assert report.deferred == (perso,)
    assert ran == ["w"]  # only the public body ran
    assert scheduler.state(pub) == WorkState.DONE
    assert scheduler.state(perso) == WorkState.SUSPENDED


def test_a_raising_health_probe_defers_the_whole_batch_fail_safe() -> None:
    """A probe that RAISES is doubt: the tick defers EVERY dispatched item (fail-safe) rather than run
    blind on an unknown health or crash the drain - the safety net cannot be voided by its own probe."""
    ran: list[str] = []
    scheduler = BoundedScheduler(capacity=4, concurrency=2)

    def _broken_probe() -> HealthReport:
        raise RuntimeError("probe contract violation")

    engine = OrchestrationEngine(
        scheduler, workflows={"w": lambda: ran.append("w")}, health=_broken_probe
    )
    ids = [engine.submit(_item(f"j{i}", "w")) for i in range(2)]

    report = engine.run_ready()  # must NOT raise - the probe failure is caught and defers fail-safe

    assert ran == []
    assert set(report.deferred) == set(ids)
    for wid in ids:
        assert scheduler.state(wid) == WorkState.SUSPENDED


# --------------------------------------------------------------------------- #
# The production path - the first real background workflow through CoreApi (D93 / D110).       #
# --------------------------------------------------------------------------- #
def test_prod_path_verify_restore_completes_when_the_backup_restores() -> None:
    """schedule_work + run_background run verify_restore as MANAGED work - the real production path."""
    api = CoreApi(replace(bootstrap(), backup=_Backup(passed=True)))
    wid = api.schedule_work("verify_restore", label=_label())
    assert wid in api.run_background().completed


def test_prod_path_verify_restore_fails_when_the_backup_does_not_restore() -> None:
    """A backup that does not restore is surfaced as a FAILED job, never a silent 'all good' (D110)."""
    api = CoreApi(replace(bootstrap(), backup=_Backup(passed=False)))
    wid = api.schedule_work("verify_restore", label=_label())
    assert wid in api.run_background().failed


def test_prod_path_refuses_an_unknown_workflow_fail_closed() -> None:
    """The facade refuses to schedule a workflow the engine does not know (deny-by-default, D100)."""
    api = CoreApi(bootstrap())
    with raises(KeyError):
        api.schedule_work("does_not_exist", label=_label())
