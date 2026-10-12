"""Resource bounds + the scheduler (D78 / D112 / D93, invariants 16 / 26) — bounds made active.

Every growing resource (work queue, concurrency, agent fan-out, retrieval breadth, logs)
carries an active bound read from the protected zone (``system/config``); crossing it is a
fail-closed refusal (:class:`~mnemosyne.ports.core.ResourceBoundError`), never a silent
overrun (D78). :func:`check_bound` is the reusable circuit-breaker pattern (D112).

:class:`BoundedScheduler` is the orchestrator's kinetic core (D93): a work queue and a
CONCURRENCY bound, both active. Two invariants live in it:

* **Bounded queues (invariant 16 / D78).** A saturated queue rejects fail-closed.
* **Pause → slot release (invariant 26 / D96 / D74).** Only ``RUNNING`` holds a concurrency
  slot; a work item that SUSPENDS (awaiting a human gesture, deferred index, or a
  life-decision blocked by the agent-juge) RELEASES its slot so another may run, and resumes
  non-destructively when its FLAG is resolved. ``pause_all`` is the kill-switch (D80).

Concurrency is a bound (one big model at a time, D95 / D80), so it lives here with the
others. The broader D93 engine loop — trigger cadence, execute-each-step-under-the-Guard,
crash recovery from the replayable journal (D82) — has no invariant of its own and is wired
at ③; this class delivers the scheduling substance those loops drive. Code & docstrings
English (D117).

Decisions: D78 / D112 (bounds, circuit-breaker) · D93 (orchestrator) · D96 (pause for a
human gesture) · D95 / D80 (concurrency, kill-switch) · D106 (interactive preempts
background). Invariants carried: 16, 26.
"""

from __future__ import annotations

from ..config import Policy
from ..ports import ResourceBoundError, TriggerKind, WorkId, WorkItem, WorkState


def check_bound(current: int, ceiling: int, *, resource: str) -> None:
    """Circuit-breaker (D112): refuse fail-closed when ``current`` reaches ``ceiling``.

    The reusable shape every growing resource guards itself with (D78, invariant 16):
    a bound is active when a breach *raises*, not when it is merely written down."""
    if current >= ceiling:
        raise ResourceBoundError(
            f"resource {resource!r} at its configured bound {ceiling} (invariant 16, D78)"
        )


class BoundedScheduler:
    """The orchestrator's scheduler (D93): a bounded queue + a concurrency bound, both active.

    :meth:`submit` enforces the queue ceiling fail-closed (invariant 16); the lifecycle
    (:meth:`dispatch` / :meth:`suspend` / :meth:`resume` / :meth:`pause_all`) tracks
    concurrency slots so a suspended item releases its slot (invariant 26). Interactive
    (``MANUAL``) work preempts background passes (D106). Non-destructive: a suspended item is
    retained and resumable — nothing is dropped."""

    __slots__ = (
        "_capacity",
        "_concurrency",
        "_queue",
        "_running",
        "_suspended",
        "_state",
        "_items",
    )

    def __init__(self, capacity: int, *, concurrency: int = 1) -> None:
        if capacity < 0:
            raise ValueError(f"capacity must be >= 0, got {capacity}")
        if concurrency < 1:
            raise ValueError(f"concurrency must be >= 1, got {concurrency}")
        self._capacity = capacity
        self._concurrency = concurrency
        self._queue: list[WorkId] = []  # QUEUED, awaiting a slot (holds none)
        self._running: set[WorkId] = set()  # RUNNING, each holding one slot
        self._suspended: dict[WorkId, str] = {}  # SUSPENDED → its awaiting reason (D96)
        self._state: dict[WorkId, WorkState] = {}
        self._items: dict[WorkId, WorkItem] = {}  # kept for priority + non-destructive resume

    @classmethod
    def from_policy(cls, policy: Policy) -> BoundedScheduler:
        """Build a scheduler whose bounds are read from the protected zone (SE4) — the queue
        depth and the concurrency cap are *configured*, not hard-coded (invariants 16 / 26)."""
        return cls(
            capacity=policy.bound("queue_capacity"),
            concurrency=policy.bound("concurrency"),
        )

    # -- admission (invariant 16) -----------------------------------------------------
    def submit(self, work: WorkItem) -> WorkId:
        """Enqueue ``work`` (QUEUED, holds no slot), or refuse fail-closed if the queue is
        full (invariant 16). Interactive triggers preempt background passes at dispatch."""
        check_bound(len(self._queue), self._capacity, resource="work_queue")
        self._queue.append(work.id)
        self._items[work.id] = work
        self._state[work.id] = WorkState.QUEUED
        return work.id

    def state(self, work: WorkId) -> WorkState:
        """Current lifecycle state; unknown ids raise ``KeyError`` (never a guess)."""
        return self._state[work]

    def item(self, work: WorkId) -> WorkItem:
        """The submitted :class:`WorkItem` for ``work`` (read-only); unknown ids raise ``KeyError``.

        The orchestration engine (:mod:`~mnemosyne.runtime.engine`) reads it back at dispatch to find
        a job's workflow — across a suspend / resume round trip — so the scheduler stays the single
        source of truth for a work item and the engine duplicates none of its state. Read-only like
        :meth:`running_ids`: it holds no slot and changes no bound (never a guess on an unknown id)."""
        return self._items[work]

    # -- concurrency lifecycle (invariant 26) -----------------------------------------
    def dispatch(self) -> tuple[WorkId, ...]:
        """Start QUEUED items up to the concurrency bound; ``MANUAL`` first (D93 / D106).

        Moves items QUEUED → RUNNING while a slot is free (concurrency cap, D95). Returns the
        ids started. The runtime calls this; the bound is active — never over-subscribed."""
        started: list[WorkId] = []
        while self._queue and len(self._running) < self._concurrency:
            wid = self._pick_next()
            self._queue.remove(wid)
            self._running.add(wid)
            self._state[wid] = WorkState.RUNNING
            started.append(wid)
        return tuple(started)

    def suspend(self, work: WorkId, *, awaiting: str) -> None:
        """Suspend ``work`` and RELEASE its concurrency slot (invariant 26 / D96).

        A running or queued item awaiting a human gesture / deferred index / blocked
        life-decision moves to SUSPENDED and frees its slot so another may run. Non-destructive
        — the item is retained with its ``awaiting`` reason and can :meth:`resume`. Fail-closed:
        a terminal (DONE / FAILED) item is refused, so it can never be resurrected into a slot
        via a later resume + dispatch (terminal states stay terminal, consistent with
        :meth:`complete` / :meth:`fail`)."""
        if work not in self._state:
            raise KeyError(f"cannot suspend unknown work {work!r}")
        if self._state[work] in (WorkState.DONE, WorkState.FAILED):
            raise KeyError(
                f"cannot suspend terminal work {work!r} ({self._state[work].value}) — a terminal "
                "item stays terminal (no resurrection)"
            )
        self._running.discard(work)  # release the slot (the heart of invariant 26)
        if work in self._queue:
            self._queue.remove(work)
        self._suspended[work] = awaiting
        self._state[work] = WorkState.SUSPENDED

    def resume(self, work: WorkId) -> None:
        """Resume a suspended item once its FLAG is resolved (invariant 26).

        It re-enters the queue (QUEUED) and takes a slot at the next :meth:`dispatch` — a
        non-destructive round trip, the queue still bounded (invariant 16)."""
        if work not in self._suspended:
            raise KeyError(f"cannot resume work {work!r} that is not suspended")
        del self._suspended[work]
        self._queue.append(work)
        self._state[work] = WorkState.QUEUED

    def pause_all(self) -> None:
        """Global pause / kill-switch (D80): every in-flight item suspends non-destructively.

        All RUNNING and QUEUED items move to SUSPENDED and release their slots; terminal items
        (DONE / FAILED) are untouched. Resume each individually once cleared."""
        for wid in list(self._running) + list(self._queue):
            self._running.discard(wid)
            if wid in self._queue:
                self._queue.remove(wid)
            self._suspended[wid] = "paused (kill-switch, D80)"
            self._state[wid] = WorkState.SUSPENDED

    def complete(self, work: WorkId) -> None:
        """Mark a RUNNING item DONE and release its slot (terminal). Fail-closed: a non-running
        item is a misuse → ``KeyError``, so a terminal item can never be resurrected into a slot
        by a later dispatch / resume (slot accounting stays consistent with state)."""
        if work not in self._running:
            raise KeyError(f"cannot complete work {work!r} that is not running")
        self._running.discard(work)
        self._state[work] = WorkState.DONE

    def fail(self, work: WorkId) -> None:
        """Mark a RUNNING item FAILED and release its slot (terminal). Fail-closed like
        :meth:`complete`: a non-running item raises ``KeyError`` (no resurrection); the error is
        normalized upstream (D108-②) and the queue stays bounded."""
        if work not in self._running:
            raise KeyError(f"cannot fail work {work!r} that is not running")
        self._running.discard(work)
        self._state[work] = WorkState.FAILED

    # -- introspection (the slot accounting invariant 26 rests on) --------------------
    def running_count(self) -> int:
        """How many slots are currently held (== items RUNNING)."""
        return len(self._running)

    def running_ids(self) -> tuple[WorkId, ...]:
        """The ids currently holding a slot."""
        return tuple(self._running)

    def suspended_ids(self) -> tuple[WorkId, ...]:
        """The ids currently SUSPENDED — the human-validation / deferred-index queue (D96 / D74).

        Read-only introspection (like :meth:`running_ids`): the UI's supervision surface (D119-c)
        reads it to show the validation queue; it holds no slot and changes no bound."""
        return tuple(self._suspended)

    def slots_free(self) -> int:
        """Concurrency slots available to :meth:`dispatch` right now (D95)."""
        return self._concurrency - len(self._running)

    @property
    def capacity(self) -> int:
        """The configured queue bound (invariant 16 / D78) — read-only introspection.

        The orchestration engine (:mod:`~mnemosyne.runtime.engine`) reads it to cap ONE drain at a
        full queue's worth of work, so a self-submitting workflow cannot make the drain loop forever
        — a coarse anti-runaway floor until the fine cascade fan-out budget lands with the first such
        workflow (D93-② / D80)."""
        return self._capacity

    def _pick_next(self) -> WorkId:
        """Next item to run: interactive (``MANUAL``) preempts background, else FIFO (D106)."""
        for wid in self._queue:
            if self._items[wid].trigger is TriggerKind.MANUAL:
                return wid
        return self._queue[0]
