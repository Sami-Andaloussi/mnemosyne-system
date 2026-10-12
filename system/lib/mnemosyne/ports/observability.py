"""Observability (D111) - health view + tracing, self-hosted LOCAL, never exfiltrates.

The JSONL logs trace *events* (D19); this port adds the "is the system OK?" view
(user's dashboard) and the tracing layer:

* **Hardware health** - disk full (critical: breaks store AND backup writes),
  RAM pressure (model juggling, D95), M4 thermals.
* **Functional health** - local runner up/down, stores reachable, agent queue
  length / blockages, error rate (normalized codes, D108), API cost (-> bornes).

Self-hosted **LOCAL**: traces can contain ``sensible``, so observability itself
**must never exfiltrate** (sensible-local). On a doctrine-touching failure -
the **local runner down** - the conduct is GRACEFUL degradation, fail-safe:
``sensible`` items are **queued** for deferred indexing (and a clear "sensible
indexing paused" signal is raised), NEVER switched to the cloud to cope; the
``public`` path may continue (canal A). A failure degrades; it never makes the
cloisonnement give way (D111).

Default OSS bricks: **Langfuse** (tracing, local) + **DeepEval** (golden-set
eval) - see ``system/config/oss_registry.md`` (D111).

Decisions: D111 (health observability)  -  D19 (event logs)  -  D108 (normalized
errors)  -  D95 (RAM juggling)  -  D66 / D60 (never exfiltrate `sensible`).
Invariants carried: substrate of 16, 22 (no `sensible` content in traces), 26
(queue depth -> slot release).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from .core import GovernanceLabel, TraceId


class HealthState(Enum):
    """Overall system health (D111). Drives circuit-breakers / FLAGs (EX5)."""

    OK = "ok"
    DEGRADED = "degraded"  # e.g. runner down -> `sensible` indexing queued (fail-safe)
    CRITICAL = "critical"  # e.g. disk full -> store/backup writes at risk


@dataclass(frozen=True, slots=True)
class HealthReport:
    """A snapshot of hardware + functional health (D111)."""

    state: HealthState
    disk_ok: bool
    ram_ok: bool
    thermal_ok: bool
    runner_up: bool
    stores_reachable: bool
    queue_depth: int
    error_rate: float


@runtime_checkable
class Observability(Protocol):
    """Local tracing + health; never exfiltrates ``sensible`` (D111)."""

    def start_trace(self, name: str, label: GovernanceLabel) -> TraceId:
        """Open a trace for one operation; ``label`` lets the layer keep
        ``sensible`` traces local-only (never exfiltrated, D111)."""
        ...

    def event(self, trace: TraceId, name: str, **fields: object) -> None:
        """Record a structured event under ``trace``. Implementations MUST NOT
        write ``sensible`` content into a greppable trace (invariant 22 / 12)."""
        ...

    def health(self) -> HealthReport:
        """Current hardware + functional health (user's dashboard, D111)."""
        ...
