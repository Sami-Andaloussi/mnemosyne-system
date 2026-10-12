"""OrchestrationEngine (D93) — the engine loop that DRIVES the bounded scheduler.

:class:`~mnemosyne.guard.bounds.BoundedScheduler` is the orchestrator's kinetic SUBSTRATE (a
bounded queue + a concurrency bound + suspend / resume / kill-switch, invariants 16 / 26). It is
complete and tested, but nothing in production ever moved work through it: ``.dispatch()`` had no
production caller and only ``TriggerKind.MANUAL`` was wired (RESTE_A_FAIRE §1, D93). This module is
the missing loop the scheduler's own docstring names ("the broader D93 engine loop … is wired at
③"): it receives submitted work, dispatches it under the concurrency bound, runs each workflow, and
reacts by gravity — the piece that turns Mnémosyne from "an assistant you query" into "a system
that does things in the background" (the *autonomous* trait of the soul).

**Graded reaction (D93 / D80 / D96).** A workflow is a bounded callable. When the engine runs it:

* it returns normally → :meth:`~mnemosyne.guard.bounds.BoundedScheduler.complete` (slot freed,
  terminal);
* it raises :class:`~mnemosyne.ports.EscalateToHuman` → :meth:`suspend` awaiting the human gesture —
  the slot is freed (invariant 26 / D96), the work is RETAINED and resumes when the FLAG clears
  (fail-SAFE: a run that needs a human never proceeds on its own, and is not counted a failure);
* it raises anything else → :meth:`fail` (fail-CLOSED, D80): the job stops in a terminal FAILED
  state rather than continue in an incoherent one; the drain moves on to the other, independent
  jobs and the failure is surfaced in the :class:`DrainReport` (never swallowed in silence). A
  ``GuardDenied`` is exactly such a hard failure — only an explicit ``EscalateToHuman`` suspends.

**Graceful degradation BEFORE the run (D111 / invariant 1).** When a health probe is wired, the
engine reads it once per tick and applies the fail-safe partition
(:func:`~mnemosyne.runtime.health.graceful_degradation`, the single home of the rule) to each
dispatched batch: a full disk defers every item (no derived-store or backup write is safe); a downed
local runner defers the non-``public`` (extraction / embedding must stay LOCAL — D60 / D66); nothing
non-public is EVER switched to the cloud to cope. A deferred item is :meth:`suspend`\\ ed — its slot
released (invariant 26), retained non-destructively — so a panic can never make the cloisonnement
give way. No probe wired (a skeleton / interactive build) → nothing degrades, every ready item
carries on exactly as before (backward-compatible).

**Deliberately lean (lookahead vs simplicity).** The engine is SYNCHRONOUS and TICK-based: a
trigger calls :meth:`run_ready` to advance ready work, and it returns. That is enough to prove the
loop end-to-end through the production path with the first real background workflow, without a
daemon. The parts D93 also envisions are built JUST-IN-TIME when a real need arrives (the first
being the autonomous proposer, soul ⑤):

* the automatic triggers beyond ``MANUAL`` — a real cron for ``PERIODIC``, a watcher for ``EVENT``,
  bounded ``CASCADE`` fan-out (D67); today a caller (a CLI tick) submits and drives ``run_ready``;
* a pre-emptive wall-clock time-out / cost budget per job (D80 / D86) — today the scheduler's queue
  and concurrency bounds hold (invariants 16 / 26), the failure path is fail-closed;
* crash-recovery of in-flight workflows from a replayable journal (D82 protects the HUMAN layer of
  the graph, not the work queue yet) and the live supervision surface that AUTOMATICALLY RESUMES
  health-deferred work when the signal clears, and shows it (D93-④ / D111 / Backlog UI) — the
  degradation PARTITION is enacted at dispatch now (above); only its automatic resume rides here.

The interactive canary (:func:`~mnemosyne.agents.loop.run_agent`) is untouched: it stays a direct
single-shot run behind the Guard; the engine COEXISTS to manage BACKGROUND work, it does not
replace it. Code & docstrings English (D117).

Decisions: D93 (orchestrator loop) · D80 (graded reaction, fail-closed / fail-safe, kill-switch) ·
D96 (suspend for a human gesture) · D67 (triggers) · D106 (interactive preempts) · D78 (bounds, via
the scheduler). Invariants leaned on: 16, 26 (both live in the scheduler this loop drives).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..ports import EscalateToHuman
from .health import graceful_degradation

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..guard.bounds import BoundedScheduler
    from ..ports import HealthReport, WorkId, WorkItem

#: A unit of background work: a bounded callable the engine runs. It raises
#: :class:`~mnemosyne.ports.EscalateToHuman` to SUSPEND (await a human gesture, D96) or any other
#: exception to FAIL (fail-closed, D80); a normal return COMPLETEs it. It takes no argument — a
#: workflow closes over whatever runtime component it drives (wired where the components live, e.g.
#: :class:`~mnemosyne.api.core_api.CoreApi`). Its return value is not used by the engine.
WorkflowFn = Callable[[], object]


@dataclass(frozen=True, slots=True)
class DrainReport:
    """What one :meth:`OrchestrationEngine.run_ready` pass did — the observable, testable result.

    Each id lands in exactly one bucket (the terminal / suspended outcome of the run the pass
    started for it). The trigger (a CLI tick today, a cron / watcher later) reads it to know what
    ran, what now waits on a human (``suspended``), what was DEFERRED under a degraded health signal
    (``deferred`` — suspended too, but awaiting a SYSTEM condition, not a human; D111), and what
    failed (surfaced, never swallowed)."""

    completed: tuple[WorkId, ...] = ()
    suspended: tuple[WorkId, ...] = ()
    failed: tuple[WorkId, ...] = ()
    deferred: tuple[
        WorkId, ...
    ] = ()  # health-deferred (D111): slot released, retained, never clouded


class OrchestrationEngine:
    """Drives the :class:`~mnemosyne.guard.bounds.BoundedScheduler`: submit → dispatch → run → react.

    Holds the workflow registry (a work item's ``descriptor`` names the workflow to run). It reads a
    job's :class:`~mnemosyne.ports.WorkItem` BACK from the scheduler at dispatch time, so the
    scheduler stays the single source of truth for queue / slot / lifecycle state (invariants 16 /
    26) and the engine duplicates none of it — it only orchestrates the cadence and the graded
    reaction (D93). The registry is fixed at wiring (a private copy); an unknown descriptor is
    refused at :meth:`submit`, never queued."""

    __slots__ = ("_scheduler", "_workflows", "_health")

    def __init__(
        self,
        scheduler: BoundedScheduler,
        *,
        workflows: Mapping[str, WorkflowFn],
        health: Callable[[], HealthReport] | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._workflows = dict(workflows)  # a private copy — the registry is fixed at wiring
        # D111: an optional health probe read once per :meth:`run_ready` tick to defer work fail-safe.
        # None (a skeleton / interactive build) → no degradation, every ready item carries on as before.
        self._health = health

    def submit(self, item: WorkItem) -> WorkId:
        """Enqueue ``item`` for its named workflow, or refuse fail-closed.

        The ``descriptor`` MUST name a registered workflow: an unknown descriptor is refused HERE,
        at admission (``KeyError``) — never queued as work the engine could not run (deny-by-default,
        the same posture as the tool catalog, D114-⑤ / D100). A full queue is refused by the
        scheduler (:class:`~mnemosyne.ports.ResourceBoundError`, invariant 16)."""
        if item.descriptor not in self._workflows:
            raise KeyError(
                f"no workflow registered for descriptor {item.descriptor!r} — refusing to queue "
                "work the engine cannot run (deny-by-default, D100)"
            )
        return self._scheduler.submit(item)

    def run_ready(self) -> DrainReport:
        """Advance ready work to a terminal / suspended outcome — one synchronous tick (D93).

        Dispatches under the concurrency bound (interactive ``MANUAL`` work first, D106); a batch
        deferred by a degraded health signal is SUSPENDED fail-safe before running (D111, never
        clouded), and the rest run and react by gravity (``complete`` / ``suspend`` / ``fail`` — see
        the module docstring). A no-op returning an empty report when nothing is ready (idempotent).

        **Structurally terminating (D78 / D80).** The drain runs at most one full queue's worth of
        work (the scheduler's ``capacity``): the ready backlog is always ≤ capacity (invariant 16),
        so this never truncates real work — but it makes the loop TERMINATE even if a workflow
        self-submits. A future CASCADE would otherwise keep the queue non-empty forever, and the queue
        bound would NOT fire to save it (the depth stays low). This is the coarse anti-runaway floor
        (D93-② "plafond global d'auto-déclenchements"); the FINE cascade fan-out budget lands WITH the
        first self-scheduling workflow (soul ⑤), not before it (lean).

        **Two deferred debts, tracked here.** (1) There is no pre-emptive wall-clock time-out yet: a
        hung workflow blocks this synchronous tick — tolerable while a CLI / test drives it, but the
        per-job timeout / cost budget (D80 / D86) MUST land with the unattended daemon. (2) The
        scheduler retains every terminal job (``_items`` / ``_state``); a long-running engine needs
        terminal-state eviction (D78) — both land with the daemon, together."""
        completed: list[WorkId] = []
        suspended: list[WorkId] = []
        failed: list[WorkId] = []
        deferred: list[WorkId] = []
        # D111: sense health ONCE for this synchronous tick; the fail-safe partition is then applied to
        # each dispatched batch below (a mid-tick change cannot race a running decision). A probe that
        # RAISES is doubt → the tick defers every item rather than run blind or crash (fail-safe).
        report, probe_failed = self._sense_health()
        budget = (
            self._scheduler.capacity
        )  # one queue's worth per tick — the anti-runaway floor (D78)
        while budget > 0:
            started = self._scheduler.dispatch()
            if not started:
                break
            defer_ids, why = self._degradation_plan(report, started, probe_failed=probe_failed)
            for wid in started:
                budget -= 1
                if wid in defer_ids:
                    # fail-SAFE (D111 / invariant 1): health degraded → DEFER this item instead of
                    # running it — release the slot (invariant 26), RETAIN it (never dropped), and
                    # never route non-public to the cloud to cope. Automatic resume when the signal
                    # clears rides with the supervision surface (D93-④); a manual resume works today.
                    self._scheduler.suspend(wid, awaiting=why)
                    deferred.append(wid)
                    continue
                try:
                    # the lookup is INSIDE the try: a descriptor with no registered workflow — only
                    # reachable via a submit that bypassed ours, since the scheduler is shared — FAILS
                    # the job fail-closed rather than crash the drain and leak its RUNNING slot (D80).
                    workflow = self._workflows[self._scheduler.item(wid).descriptor]
                    workflow()
                except EscalateToHuman as escalation:
                    # fail-SAFE: a run that needs a human releases its slot and waits (D96 / inv. 26)
                    self._scheduler.suspend(wid, awaiting=str(escalation))
                    suspended.append(wid)
                except Exception:  # noqa: BLE001 - a failing job is marked FAILED + surfaced, never crashes the drain (D80)
                    self._scheduler.fail(wid)
                    failed.append(wid)
                else:
                    self._scheduler.complete(wid)
                    completed.append(wid)
        return DrainReport(
            completed=tuple(completed),
            suspended=tuple(suspended),
            failed=tuple(failed),
            deferred=tuple(deferred),
        )

    def _sense_health(self) -> tuple[HealthReport | None, bool]:
        """Read the health probe once, fail-safe — returns ``(report, probe_failed)``.

        No probe wired → ``(None, False)`` (proceed exactly as before). A probe that RAISES (a
        contract violation — the real probe is fail-safe by construction, it should not) is DOUBT:
        ``(None, True)``, and the tick then DEFERS every dispatched item rather than run blind on an
        unknown health or crash the drain (fail-safe, D111 / D100)."""
        if self._health is None:
            return None, False
        try:
            return self._health(), False
        except Exception:  # noqa: BLE001 - an unreadable health signal is doubt → defer fail-safe
            return None, True

    def _degradation_plan(
        self,
        report: HealthReport | None,
        started: tuple[WorkId, ...],
        *,
        probe_failed: bool = False,
    ) -> tuple[frozenset[WorkId], str]:
        """Which of ``started`` to DEFER, and the awaiting reason (D111 — the fail-safe rule).

        The rule itself lives in ONE place — :func:`~mnemosyne.runtime.health.graceful_degradation`
        (a full disk defers everything; a downed local runner defers the non-``public`` so it is
        never clouded; otherwise nothing). The engine only ENACTS the plan (suspends the deferred),
        so the fail-safe conduct is not duplicated here. An unreadable probe (``probe_failed``) defers
        the WHOLE batch (doubt → don't run); no probe / no report → nothing deferred."""
        if probe_failed:
            return frozenset(started), "health probe unreadable — deferring fail-safe (D111 / D100)"
        if report is None:
            return frozenset(), ""
        items = tuple(self._scheduler.item(wid) for wid in started)
        plan = graceful_degradation(report, items)
        return frozenset(w.id for w in plan.deferred), plan.reason
