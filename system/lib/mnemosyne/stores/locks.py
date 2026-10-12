"""DocumentLocks (D106) - document-grain locking without deadlock.

Concurrency for the three stores, grained at the DOCUMENT (D105 / D106): never a
global lock. Three rules are structural, not left to discipline:

* **Reads never block** - a read takes NO lock, so a concurrent write can never block
  it (read-during-write, invariant 25). :meth:`~DocumentLocks.read_blocked` is
  therefore always ``False``.
* **Document grain** - a write locks ONLY its document; a write to a *different*
  document proceeds freely. Re-taking a held document is REFUSED
  (:class:`LockContended`) rather than silently blocking, so a would-be deadlock
  surfaces as a normalized, recoverable error (D108-(2)) instead of a hang.
* **No lock across an external wait** - a lock may NEVER be held across a network /
  model wait: :meth:`~DocumentLocks.external_wait` refuses
  (:class:`LockHeldAcrossWaitError`) while any lock is held. This forbids the classic
  deadlock of holding a lock during slow I/O (D106); the pattern is release -> wait ->
  re-acquire.

A single-writer, in-memory model of the discipline the real store adapters inherit -
what LOT 4b fixes is the CONTRACT, not a threading engine. Both errors subclass
:class:`~mnemosyne.ports.core.ResourceBoundError`, so the orchestrator (D93) reads the
normalized ``RESOURCE_BOUND`` code and backs off. Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from ..ports import DocId, ResourceBoundError


class LockContended(ResourceBoundError):
    """A document's write lock is already held - re-taking it would deadlock (D106).

    Raised, not blocked, so a would-be deadlock is a normalized, recoverable event."""


class LockHeldAcrossWaitError(ResourceBoundError):
    """An external (network / model) wait was attempted while holding a lock (D106):
    forbidden, because a lock held across I/O is the classic deadlock / starvation."""


class DocumentLocks:
    """Document-grain locks: reads never block, no lock across an external wait (D106)."""

    __slots__ = ("_held",)

    def __init__(self) -> None:
        self._held: set[DocId] = set()

    @contextmanager
    def write(self, doc: DocId) -> Iterator[None]:
        """Hold ``doc``'s write lock for the block (document grain, D106).

        A DIFFERENT document stays free (no global lock); re-taking ``doc`` while it is
        held raises :class:`LockContended` instead of blocking (invariant 25)."""
        if doc in self._held:
            raise LockContended(f"document {doc!r} is already write-locked (D106, invariant 25)")
        self._held.add(doc)
        try:
            yield
        finally:
            self._held.discard(doc)

    def read_blocked(self, doc: DocId) -> bool:  # noqa: ARG002 - reads take no lock, ever
        """Whether a read of ``doc`` is blocked - ALWAYS ``False`` (read-during-write,
        invariant 25): reads take no lock, so a concurrent write never blocks a reader."""
        return False

    def external_wait(self) -> None:
        """Cross a network / model wait boundary - REFUSED while any lock is held (D106).

        A lock must never span an external wait (invariant 25): release before waiting,
        then re-acquire. Raises :class:`LockHeldAcrossWaitError` if a lock is held."""
        if self._held:
            raise LockHeldAcrossWaitError(
                f"cannot perform an external wait while holding locks {self._held!r} "
                "(release before waiting - D106, invariant 25)"
            )
