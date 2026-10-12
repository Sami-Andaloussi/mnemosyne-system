"""Health view + graceful degradation (D111) - the "is the system OK?" dashboard, fail-safe.

The JSONL logs trace *events* (D19) and :class:`~mnemosyne.runtime.observability.LocalObservability`
keeps them ``sensible``-clean; this module adds the health layer D111 asks for - user's
dashboard - and the one doctrine-touching conduct: what to do when a signal degrades.

**Health aggregation.** :class:`HealthMonitor` folds hardware probes (disk / RAM / thermal,
stubbed here, real at (3)) and functional signals (local runner up/down, stores reachable, work
queue depth, error rate) into a single :class:`~mnemosyne.ports.observability.HealthReport`.
The state is fail-safe: a full disk is ``CRITICAL`` (it breaks store AND backup writes); any
other degraded signal is ``DEGRADED``; otherwise ``OK``.

**Graceful degradation (the D111 rule, made structural).** When the local runner is down, the
``sensible`` becomes non-indexable (extraction / embedding must be LOCAL - D60 / D66). The
conduct is graceful degradation, fail-safe: ``sensible`` / ``perso`` work is **queued** for
deferred indexing, the ``public`` may continue (canal A), and NOTHING non-public is ever
switched to the cloud to cope. :func:`graceful_degradation` is that rule as code - a partition
into *carry-on* and *deferred* with no cloud path for non-public data, so a panic can never make
the cloisonnement give way (D111 / D27 / D66 / invariant 1).

Default OSS brick for the dashboard: **Langfuse** self-hosted LOCAL (``oss_registry.md``); the
traces may hold ``sensible`` so observability itself never exfiltrates (D111 / D66).

Decisions: D111 (health + graceful degradation)  -  D60 / D66 (sensible stays local)  -  D95 (RAM
juggling)  -  D19 / D108 (events -> error rate)  -  D78 (queue depth is a bounded resource).
Invariant carried: substrate of 1 (sensible-local holds even under failure) / 26 (queue depth).
Code & docstrings English (D117); ``public`` / ``perso`` / ``sensible`` stay French (D33 / D66).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..ports import (
    HealthReport,
    HealthState,
    Observability,
    WorkItem,
)


@runtime_checkable
class HardwareProbe(Protocol):
    """The three hardware signals D111 watches. Real probes (``psutil`` / IOKit) plug in at (3);
    the skeleton ships :class:`StubHardwareProbe` (all OK) so the aggregation is testable now."""

    def disk_ok(self) -> bool:
        """False when the disk is (near) full - CRITICAL: it breaks store AND backup writes."""
        ...

    def ram_ok(self) -> bool:
        """False under RAM pressure (model juggling, D95) - DEGRADED."""
        ...

    def thermal_ok(self) -> bool:
        """False when the M4 is thermally throttling - DEGRADED."""
        ...


class StubHardwareProbe:
    """Fail-safe stand-in reporting healthy hardware until real probes plug in at (3).

    Every signal is OK, so the skeleton's aggregate state is driven by the functional signals
    (runner / stores) a test injects; the real disk / RAM / thermal reads swap in behind this
    same protocol (D111 / D113)."""

    __slots__ = ()

    def disk_ok(self) -> bool:
        return True

    def ram_ok(self) -> bool:
        return True

    def thermal_ok(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class DegradationPlan:
    """How work is split when health degrades (D111) - fail-safe, no cloud path for non-public.

    ``carry_on`` may run now; ``deferred`` waits (queued for the local runner's return). The
    structural guarantee is what is ABSENT: there is no third "route to the cloud" bucket, so a
    ``perso`` / ``sensible`` item can only ever be deferred, never exfiltrated to cope (D111 /
    D27 / D66 / invariant 1)."""

    carry_on: tuple[WorkItem, ...]
    deferred: tuple[WorkItem, ...]
    reason: str


class HealthMonitor:
    """Folds hardware + functional signals into a :class:`HealthReport` (user's dashboard, D111).

    Construct with an optional :class:`HardwareProbe` (defaults to the healthy stub) and an
    optional :class:`~mnemosyne.ports.observability.Observability` to source the live error rate.
    :meth:`report` takes the functional signals (runner / stores / queue) a caller has just
    probed - the seam the real runtime fills at (3)."""

    __slots__ = ("_hardware", "_obs")

    def __init__(
        self,
        *,
        hardware: HardwareProbe | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._hardware: HardwareProbe = hardware if hardware is not None else StubHardwareProbe()
        self._obs = observability

    def report(
        self,
        *,
        runner_up: bool = True,
        stores_reachable: bool = True,
        queue_depth: int = 0,
    ) -> HealthReport:
        """Aggregate the current health, fail-safe (D111).

        State rule: a full disk is ``CRITICAL`` (breaks store AND backup writes); any other
        degraded signal - RAM, thermal, runner down, stores unreachable - is ``DEGRADED``;
        otherwise ``OK``. The error rate is read from the observability layer when present
        (D19 / D108), else 0.0."""
        disk_ok = self._hardware.disk_ok()
        ram_ok = self._hardware.ram_ok()
        thermal_ok = self._hardware.thermal_ok()
        error_rate = self._obs.health().error_rate if self._obs is not None else 0.0
        if not disk_ok:
            state = HealthState.CRITICAL
        elif not (ram_ok and thermal_ok and runner_up and stores_reachable):
            state = HealthState.DEGRADED
        else:
            state = HealthState.OK
        return HealthReport(
            state=state,
            disk_ok=disk_ok,
            ram_ok=ram_ok,
            thermal_ok=thermal_ok,
            runner_up=runner_up,
            stores_reachable=stores_reachable,
            queue_depth=queue_depth,
            error_rate=error_rate,
        )


def graceful_degradation(report: HealthReport, items: tuple[WorkItem, ...]) -> DegradationPlan:
    """Split ``items`` into carry-on vs deferred under ``report``, fail-safe (D111).

    The rule, keyed on the two signals that actually threaten cloisonnement:

    * **Disk full (CRITICAL).** Nothing carries on - a derived-store or backup write is unsafe,
      so all work defers (fail-safe, D100).
    * **Local runner down.** ``sensible`` / ``perso`` extraction / embedding cannot run
      (they must be LOCAL - D60 / D66), so those items DEFER (queued for the runner's return);
      only ``public`` items carry on (they may route canal A). **Never** the cloud for
      non-public data (invariant 1) - that is the whole point of degrading gracefully.
    * **Otherwise.** The local runner is available, so everything carries on - a thermal / RAM
      warning is surfaced on the dashboard, not a reason to defer ``sensible`` (it still runs
      locally); the circuit-breakers (EX5) throttle separately.

    The guarantee is structural: a non-public item is only ever placed in ``deferred``, never on
    a cloud path - there is no such path in the returned plan."""
    if report.state is HealthState.CRITICAL:
        return DegradationPlan(
            carry_on=(),
            deferred=items,
            reason="disk critical - all writes unsafe, every item deferred (fail-safe, D111)",
        )
    if not report.runner_up:
        carry_on = tuple(w for w in items if w.label.may_use_automatic_cloud())
        deferred = tuple(w for w in items if not w.label.may_use_automatic_cloud())
        return DegradationPlan(
            carry_on=carry_on,
            deferred=deferred,
            reason=(
                "local runner down - sensible/perso queued for deferred indexing, never cloud; "
                "public continues on canal A (D111 / D66 / invariant 1)"
            ),
        )
    return DegradationPlan(
        carry_on=items,
        deferred=(),
        reason="healthy or non-blocking degradation - all work runs locally (D111)",
    )


def may_start_heavy_run(report: HealthReport) -> tuple[bool, str]:
    """May a heavy CLI run (ingest / figures / youtube) START under ``report``? - the pre-flight rule (D111).

    The SAME disk-critical floor as :func:`graceful_degradation`, co-located here so all health CONDUCT
    lives in one module (consolidate-crosscutting-rules): a heavy run cold-starts multi-GB models and
    writes derived stores, so it is gated on the health state exactly as background work is deferred.

    * **Disk full (CRITICAL).** Refuse fail-closed: a store / backup write would be unsafe, so the run must
      not START - ``(False, <reason>)`` (mirrors ``graceful_degradation``'s "every item defers", D100).
    * **RAM / thermal / runner degraded (DEGRADED).** ALLOW, with a warning: the run stays LOCAL and the
      pressure is surfaced on the dashboard, never a reason to refuse (consistent with
      ``graceful_degradation``, which carries such work on and throttles separately) - ``(True, <warning>)``.
    * **Healthy (OK).** ``(True, "")`` - no notice.

    Returns ``(ok, reason)``: ``reason`` is empty only when fully healthy, a warning when DEGRADED (the run
    proceeds), and the refusal text when CRITICAL. The caller (``guarded_heavy_run``) enacts it: refuse on
    ``not ok``, surface the warning otherwise. English text (user-facing, D33)."""
    if report.state is HealthState.CRITICAL:
        return False, (
            "disk full (CRITICAL) - a heavy run would write into unsafe space; refusing fail-closed (D111)."
        )
    if report.state is HealthState.DEGRADED:
        return True, (
            "health degraded (RAM / thermal / runner) - the run continues LOCALLY; "
            "watch the dashboard (D111)."
        )
    return True, ""
