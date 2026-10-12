"""Reconciler (D65 / D60) - surface A<->B contradictions as a non-destructive FLAG.

The reconciliation pass between Moteur A (living memory / graph, volatile facts) and
Moteur B (documentary truth / ``.md``, stable content). Invariant 10: a disagreement
between the two engines is SURFACED as a flag - never silently kept, never silently
overwritten. The human arbitrates (D82). The pass is READ-ONLY: it touches neither
store (non-destructive, invariant 2), so reconciliation can never itself corrupt a
memory.

The real reconciliation aligns facts semantically (LOT 5+); what LOT 4b fixes is the
CONTRACT - contradiction => FLAG, non-destructive. Here a claim is compared by value:
the graph's current object for ``(entity, predicate)`` against the truth fiche's
payload for that entity. Code & docstrings English (D117).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ports import DocId, GraphStore, NodeId, TruthStore


@dataclass(frozen=True, slots=True)
class ReconciliationFlag:
    """A surfaced A<->B contradiction (invariant 10): the living (graph) value and the
    documentary (truth) value disagree.

    Non-destructive - both are kept and a human arbitrates (D82); never a silent
    overwrite (D60)."""

    entity: NodeId
    predicate: str
    living_value: str
    documentary_value: str


class Reconciler:
    """Compares Moteur A (graph) and Moteur B (truth) and FLAGS contradictions (inv. 10)."""

    __slots__ = ("_truth", "_graph")

    def __init__(self, truth: TruthStore, graph: GraphStore) -> None:
        self._truth = truth
        self._graph = graph

    def reconcile(self, entity: NodeId, predicate: str) -> ReconciliationFlag | None:
        """FLAG a contradiction between the graph's current fact for ``(entity,
        predicate)`` and the truth fiche's value; ``None`` on agreement or absence.

        Read-only: neither store is mutated (non-destructive, invariant 2 / D82). A
        surfaced disagreement is returned for the human to arbitrate - it is never
        resolved by overwriting one side (D60)."""
        facts = self._graph.query(subject=entity, predicate=predicate)
        if not facts:
            return None
        living_value = str(facts[0].obj)
        try:
            documentary_value = self._truth.read(DocId(str(entity))).payload
        except KeyError:
            return None
        if living_value == documentary_value:
            return None
        return ReconciliationFlag(
            entity=entity,
            predicate=predicate,
            living_value=living_value,
            documentary_value=documentary_value,
        )
