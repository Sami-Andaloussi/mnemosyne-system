"""Scheduler (D93 / D96) - the orchestrator: bounded queue, slot release on pause.

The central piece that assembles and runs everything else (the kinetic core).
It receives the four trigger modes (D67), queues work, and runs a limited number
at a time (concurrency cap D95 / D80) with interactive work (user live)
preempting background passes (D106). Each step runs under the Guard (D89); each
life-action candidate goes through the agent-juge (D91); writes are atomic per
document (D105). After a crash it resumes from the replayable journal (D82).

Three invariants are structural here:

* **Bounded queues** (invariant 16 / D78) - every growing resource, the work
  queue included, has an active configured bound.
* **No lock during an external wait** (invariant 25 / D106) - a network / canal-B
  call happens OUTSIDE any lock; the lock is taken only for the short final
  write.
* **Pause -> slot release** (invariant 26 / D96 / D74 / D111) - a work item that
  SUSPENDS (awaiting a human gesture, deferred indexing, or a life-decision
  blocked by the agent-juge) **releases its concurrency slot** and resumes when
  the FLAG is resolved; the queue stays bounded and non-destructive.

This port is OUR glue (like the Guard), not an OSS engine. The runtime
(concurrency policy, triggers, bootstrap, graceful degradation) is wired at
LOT 5; this contract fixes the surface.

Decisions: D93 (orchestrator)  -  D96 (pause for human gesture)  -  D67 (triggers)  -
D95 / D80 (concurrency, kill-switch)  -  D78 (bounds)  -  D82 (replay). Invariants
carried: 16, 25, 26 (substrate of 6, 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType, Protocol, runtime_checkable

from .core import GovernanceLabel

#: A unit of scheduled work.
WorkId = NewType("WorkId", str)


class TriggerKind(Enum):
    """The four ways work enters the queue (D67)."""

    MANUAL = "manual"  # user via the UI (interactive, prioritized)
    PERIODIC = "periodic"
    EVENT = "event"
    CASCADE = "cascade"  # a workflow spawning follow-up work (bounded fan-out, D80)


class WorkState(Enum):
    """Lifecycle of a work item. Only ``RUNNING`` holds a concurrency slot."""

    QUEUED = "queued"  # waiting, holds NO slot
    RUNNING = "running"  # executing, holds a slot
    SUSPENDED = "suspended"  # awaiting human / deferred index / blocked life-decision ->
    #     RELEASES its slot (invariant 26)
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class WorkItem:
    """A job to schedule, carrying the governance label of the data it touches."""

    id: WorkId
    trigger: TriggerKind
    descriptor: str
    label: GovernanceLabel


@runtime_checkable
class Scheduler(Protocol):
    """Queues, runs, suspends and resumes work under bounded concurrency (D93)."""

    def submit(self, work: WorkItem) -> WorkId:
        """Enqueue ``work``. Raises :class:`~mnemosyne.ports.core.ResourceBoundError`
        if the bounded queue is full (invariant 16); interactive triggers preempt
        background passes (D106)."""
        ...

    def state(self, work: WorkId) -> WorkState:
        """Current lifecycle state of a work item."""
        ...

    def suspend(self, work: WorkId, *, awaiting: str) -> None:
        """Suspend ``work`` pending ``awaiting`` (a human gesture / deferred index /
        blocked life-decision) and RELEASE its concurrency slot (invariant 26)."""
        ...

    def resume(self, work: WorkId) -> None:
        """Resume a suspended item once its FLAG is resolved (invariant 26)."""
        ...

    def pause_all(self) -> None:
        """Global pause / kill-switch (D80); in-flight work suspends non-destructively."""
        ...
