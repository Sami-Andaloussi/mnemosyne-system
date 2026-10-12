"""Runtime compactor (D77, invariant 15) - persist BEFORE compacting, or refuse.

Mnémosyne's internal ``/compact`` (D77): a long session / workflow is kept in the LOW zone
of the context window (context rot is real - quality drops well before the limit). Compaction
happens at LOGICAL frontiers decided by the orchestrator (D77-h), never mid high-stakes task
(D77-g). The one rule that guarantees ZERO quality loss is the golden rule:

* **Persist before compacting (D77-e, invariant 15).** Nothing is compacted until the
  DURABLE content - decisions, productions, lessons - is written OUTSIDE, retrievable from
  external memory (a direct application of D76 corollary 4). A durable item not yet
  persisted makes :meth:`Compactor.compact` REFUSE fail-closed (:class:`PersistBeforeCompact`)
  rather than drop something unrecoverable. Only the TRANSITORY fil jetable is summarized;
  the durable is never lost (D77-f).

The compactor reads external memory (the ``.md``/git truth store, the arbiter D56) to VERIFY
retrievability - it never writes it; persisting is the caller's prior step (write-ahead via
the journal, D105). This is the runtime compactor the #9 mechanics deferred (D77); the
per-frontier cadence is driven by the scheduler (D77-h). Code & docstrings English (D117).

Decisions: D77-e/f/g/h (persist-before-compact, durable vs transitory, frontiers)  -  D76-(4)
(lessons written outside immediately)  -  D56 (truth as arbiter). Invariant carried: 15.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ports import DocId, ErrorCode, MnemosyneError, TruthStore


class PersistBeforeCompact(MnemosyneError):
    """A compaction was refused because durable content was not yet persisted (inv. 15).

    Fail-closed like a Guard denial (``DENIED``): rather than lose an unrecoverable durable
    item, the compactor stops - the context stays fresh until the durable is written outside
    (D77-e / D76-(4))."""

    code = ErrorCode.DENIED


@dataclass(frozen=True, slots=True)
class CompactionResult:
    """Outcome of a compaction at a logical frontier (D77)."""

    compacted: bool
    persisted: tuple[DocId, ...]  # the durable items confirmed retrievable in external memory
    dropped_transient: bool  # whether a transitory fil jetable was summarized away


class Compactor:
    """Compacts a session at a frontier only once its durable content is externally durable.

    Holds a reference to external memory (the truth store, D56) to VERIFY persistence; it
    never writes it. A durable item absent from external memory blocks the compaction
    (invariant 15)."""

    __slots__ = ("_external",)

    def __init__(self, external_memory: TruthStore) -> None:
        self._external = external_memory

    def compact(
        self,
        *,
        durable: tuple[DocId, ...] = (),
        transient: str = "",
    ) -> CompactionResult:
        """Compact at a frontier - but only if every durable item is retrievable (D77-e).

        Verifies each ``durable`` id is readable from external memory; a missing one raises
        :class:`PersistBeforeCompact` and NOTHING is compacted (fail-closed). When all are
        durable, the transitory ``transient`` is summarized away and the durable is kept
        (non-destructive - the durable is never lost, D77-f)."""
        for doc in durable:
            if not self._is_persisted(doc):
                raise PersistBeforeCompact(
                    f"durable item {doc!r} is not retrievable in external memory; nothing "
                    "compacts until it is written outside (invariant 15 / D77-e / D76-(4))"
                )
        return CompactionResult(
            compacted=True,
            persisted=durable,
            dropped_transient=bool(transient),
        )

    def _is_persisted(self, doc: DocId) -> bool:
        """Whether ``doc`` is retrievable from external memory (the arbiter, D56)."""
        try:
            self._external.read(doc)
        except KeyError:
            return False
        return True
