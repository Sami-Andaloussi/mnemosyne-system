"""GraphStore (D103) - bi-temporal fact graph behind a swap-able seam.

The living memory (Moteur A - a bi-temporal fact graph, D55) is NOT rebuilt
from scratch: we adopt an OSS graph engine and reverse it under our rules (D98).
The rest of Mnémosyne speaks ONLY to this interface, never to the engine
directly (invariant 20): no module imports LadybugDB / Graphiti / FalkorDB.

Three rules are structural here, not optional:

* **Engine encapsulated** (invariant 20 / D103) - the only door to the graph;
  every engine output (LLM fact-extraction, embedding) passes through the Guard
  (D89); a direct call outside this interface fails the build.
* **Non-destructive** (invariant 2 / D84) - the OSS engine's mass deletes
  (``delete_by_group_id`` / hard-delete) are neutralized into *invalidation*:
  closing a fact's valid-time, never erasing it ("invalidé ≠ effacé", D60-2).
* **Bi-temporal** (D84) - each fact carries valid-time (when it was true) and
  transaction-time (when it was recorded); queries may ask "as of" a past
  instant.

Default OSS brick: **LadybugDB** (embedded graph, MIT / arm64, in-process,
available today); swap alternative: **Graphiti-local** in its embedded
FalkorDB-Lite mode, if merged / mature at the bench ((2)) - see
``system/config/oss_registry.md`` (D103 / D121-B1). The bi-temporal semantics
live ONLY here (no double logic); embedding stays the single D68 decision,
plugged in through the Guard.

Decisions: D103 (adoption)  -  D55 / D84 (bi-temporal living memory)  -  D56 / D60
(non-destructive)  -  D68 (embedding plugged in)  -  D100 (extraction in the loop).
Invariants carried: 20, 2 (substrate of 10, 13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NewType, Protocol, runtime_checkable

from .core import Envelope

#: A node (entity) in the fact graph.
NodeId = NewType("NodeId", str)
#: A recorded bi-temporal fact.
FactId = NewType("FactId", str)


@dataclass(frozen=True, slots=True)
class Fact:
    """A bi-temporal fact (D55 / D84).

    ``valid_from`` / ``valid_to`` express *when the fact was true in the world*;
    ``valid_to is None`` means still valid. Closing ``valid_to`` is an
    invalidation (archival), never a deletion (invariant 2). The
    transaction-time (when Mnémosyne recorded it) is kept by the engine.
    """

    subject: NodeId
    predicate: str
    obj: NodeId
    valid_from: datetime
    valid_to: datetime | None = None


@runtime_checkable
class GraphStore(Protocol):
    """The sole interface to the living-memory graph (invariant 20)."""

    def add_fact(self, fact: Envelope[Fact]) -> FactId:
        """Record a fact. The envelope's label proves its extraction passed the
        Guard (D89 / D103); the engine choice stays hidden behind this seam."""
        ...

    def invalidate(self, fact: FactId, *, at: datetime) -> None:
        """Close a fact's validity at ``at`` - archival, NOT a hard delete (inv. 2 / D84)."""
        ...

    def query(
        self,
        *,
        subject: NodeId | None = None,
        predicate: str | None = None,
        as_of: datetime | None = None,
    ) -> list[Fact]:
        """Query facts, optionally *as of* a past instant (bi-temporal travel, D84)."""
        ...
