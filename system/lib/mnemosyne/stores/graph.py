"""InMemoryGraphStore (D103 / D84) - bi-temporal fact graph behind the GraphStore seam.

A light in-memory stand-in for the living-memory engine (default brick:
**LadybugDB**, D103), implementing :class:`~mnemosyne.ports.graphstore.GraphStore`.
No module imports the engine directly (invariant 20): the rest of Mnémosyne speaks
ONLY to this port, and the encapsulation is a build-failing barrier - an import scan
(``tests._invariants.direct_imports_of``) fails if any module reaches a graph engine
outside this seam. Three properties are structural, not optional:

* **Encapsulation** (invariant 20 / D103) - the only door to the graph; a fact enters
  solely as an :class:`~mnemosyne.ports.core.Envelope`, whose label proves its
  extraction passed the Guard (D89). A naked (un-enveloped) fact is refused.
* **Non-destructive** (invariant 2 / D84) - :meth:`~InMemoryGraphStore.invalidate`
  CLOSES a fact's valid-time (archival); it never erases. The engine's mass-deletes
  are neutralised into invalidation ("invalidé ≠ effacé", D60-2), so a past-instant
  query still sees an invalidated fact.
* **Bi-temporal** (D84) - a fact carries valid-time; :meth:`~InMemoryGraphStore.query`
  may travel ``as_of`` a past instant.

Fact identity is the ``(subject, predicate, obj, valid_from)`` tuple, so re-recording
an identical fact is idempotent - no duplicate. That idempotence is the substrate of
the journal's idempotent replay (invariant 24). Code & docstrings English (D117).
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime

from ..ports import Envelope, Fact, FactId, NodeId


def _fact_id(fact: Fact) -> FactId:
    """Content-addressed id: identical facts collapse to one (idempotent add, inv. 24)."""
    key = "\x1f".join(
        (str(fact.subject), fact.predicate, str(fact.obj), fact.valid_from.isoformat())
    )
    return FactId(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16])


class InMemoryGraphStore:
    """In-memory LadybugDB stand-in - the sole door to the living-memory graph (inv. 20).

    Bi-temporal and non-destructive: :meth:`invalidate` closes valid-time, and an
    identical fact never duplicates (content-addressed ids)."""

    __slots__ = ("_facts",)

    def __init__(self) -> None:
        self._facts: dict[FactId, Fact] = {}

    def add_fact(self, fact: Envelope[Fact]) -> FactId:
        """Record a fact carried in a governance :class:`Envelope` (Guard passage, D89).

        A naked :class:`Fact` (not enveloped) is refused: engine output enters the
        graph only bearing its label (invariant 20 / D103). Re-adding an identical
        fact returns its existing id - idempotent, no duplicate (invariant 24)."""
        if not isinstance(fact, Envelope):
            raise TypeError(
                "add_fact requires an Envelope[Fact]: a fact enters the graph only "
                "carrying its governance label (Guard passage - D89 / D103 / invariant 20)"
            )
        payload = fact.payload
        fid = _fact_id(payload)
        self._facts.setdefault(fid, payload)
        return fid

    def invalidate(self, fact: FactId, *, at: datetime) -> None:
        """Close a fact's validity at ``at`` - archival, NOT a hard delete (inv. 2 / D84).

        The fact stays recorded with a closed valid-time, so a query ``as_of`` an
        instant before ``at`` still sees it (bi-temporal, non-destructive, D60-2).
        An UNKNOWN id is a NO-OP (idempotent close), matching the real LadybugDB
        backend - the stub and the brick now agree on the whole port ((3)-3c, 3a debt)."""
        existing = self._facts.get(fact)
        if existing is not None:
            self._facts[fact] = replace(existing, valid_to=at)

    def query(
        self,
        *,
        subject: NodeId | None = None,
        predicate: str | None = None,
        as_of: datetime | None = None,
    ) -> list[Fact]:
        """Query facts, optionally *as of* a past instant (bi-temporal travel, D84).

        Without ``as_of`` the query is "now": an invalidated (closed) fact is archived
        and NOT returned. With ``as_of`` a fact is visible when it was valid then -
        ``valid_from <= as_of`` and it was not yet closed (``valid_to`` open or later)."""
        out: list[Fact] = []
        for fact in self._facts.values():
            if subject is not None and fact.subject != subject:
                continue
            if predicate is not None and fact.predicate != predicate:
                continue
            if as_of is None:
                if fact.valid_to is not None:  # closed => not currently valid
                    continue
            else:
                if fact.valid_from > as_of:
                    continue
                if fact.valid_to is not None and fact.valid_to <= as_of:
                    continue
            out.append(fact)
        return out
