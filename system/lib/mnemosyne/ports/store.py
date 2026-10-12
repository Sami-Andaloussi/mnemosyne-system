"""Store & IntentLog (D105) — three-store integrity, the truth as sole arbiter.

How the three stores (``.md``/git = THE versioned truth · Qdrant = vector index
· graph) stay consistent without ever corrupting or losing. Four standard
moves — nothing invented (D105):

1. **Write-ahead intent journal** — record "I will integrate / update /
 invalidate doc X" BEFORE touching the stores; a crash mid-way is finished or
 rolled back cleanly on restart. **Replay is IDEMPOTENT** (replaying an
 operation twice ⇒ same final state — invariant 24), which is what makes
 recovery safe even if a second crash hits during replay itself.
2. **Per-document consistency marker** — a fingerprint (content hash + "indexed
 in Qdrant / graph " flags). It is a reconstructible CACHE, **never a 4th
 source of truth** (D105-② / D56): the hash recomputes from the text, the
 flags re-verify by querying the indexes.
3. **Non-destructive reconciliation** — reindex the missing, purge orphans in
 the derived stores; never erase content (invariant 2).
4. **Arbiter = ``.md``/git** — on any disagreement the versioned text wins
 ALWAYS; the indexes rebuild from it (invariant 24 / D56).

Caveat (D82): the graph carries a HUMAN LAYER (your validations, links,
corrections) that is NOT a plain reconstructible derivative — reconciliation
repairs the derived indexes but NEVER touches it; it is protected separately by
the replayable journal + snapshots (D82).

Atomicity is **per document** (tout-ou-rien), never a global transaction — the
document grain avoids any global lock (D105 / D106). Updates **merge** into the
existing fiche rather than creating a duplicate (invariant 9 / D58). This is our
light glue over git, not a distributed-transaction manager (the from-scratch
trap to avoid — D98 / D105).

Decisions: D105 (integrity) · D56 / D44 (asymmetry, reconstructible derivatives)
· D82 (replayable journal, human layer) · D58 (merge, no duplicate). Invariants
carried: 2, 9, 24 (substrate of 12).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, NewType, Protocol, runtime_checkable

from .core import Envelope, GovernanceLabel

#: A document — the unit of atomicity across the three stores (D105 / D106).
DocId = NewType("DocId", str)
#: A recorded intent in the write-ahead journal (D105-①).
IntentId = NewType("IntentId", str)


# --------------------------------------------------------------------------- #
# Epistemic role (D137 — the 6th identity-card axis, D33)                     #
# --------------------------------------------------------------------------- #
class DocRole(Enum):
    """The epistemic ROLE a Moteur B document plays — the 6th identity-card axis (D137 / D33).

    Orthogonal to sensitivity (D101): sensitivity decides whether a datum may ever LEAVE the
    machine; role decides whether it may be CITED AS A SOURCE OF TRUTH inside an answer. This is a
    FACT about a document (like its ``statut de lecture``), never a subjective score — the "éviter
    le discrétionnaire" principle. It closes the gap D137 names: Moteur A (living) always had a
    validation gate (D59), Moteur B (documentary) never did, so every filed document read out as
    equal-rank truth — a raw, unverified working draft indistinguishable from an endorsed source.

    A document is the operator's own working material by default and becomes an endorsed source
    ONLY by an explicit human gesture (the D59 gate applied to documents — :meth:`TruthStore.set_role`,
    gated in :meth:`~mnemosyne.api.core_api.CoreApi.endorse_document`), never automatically.
    """

    MATIERE_DE_TRAVAIL = "matiere_de_travail"  # the operator's own production: unverified, bubble-local, NEVER a source of truth (fail-closed default)
    BASE_DE_CONNAISSANCES = (
        "base_de_connaissances"  # endorsed knowledge: authoritative, citable as a source of truth
    )


#: The fail-closed default role of every document (D137): nothing is a source of truth until an
#: explicit human gesture endorses it. A document whose role was never set is working material — so a
#: raw draft can never be presented as authority just because it was filed (mirrors DEFAULT_SENSITIVITY).
DEFAULT_ROLE: Final = DocRole.MATIERE_DE_TRAVAIL


class IntentKind(Enum):
    """What a journalled intent will do (D105-①). No hard delete (invariant 2)."""

    INTEGRATE = "integrate"
    UPDATE = "update"  # merges into the existing fiche, never duplicates (inv. 9)
    INVALIDATE = "invalidate"  # archives / closes validity, never erases (inv. 2)


@dataclass(frozen=True, slots=True)
class Intent:
    """A write-ahead record: the operation declared BEFORE the stores change."""

    kind: IntentKind
    doc: DocId
    label: GovernanceLabel


@dataclass(frozen=True, slots=True)
class ConsistencyMarker:
    """Per-document fingerprint — a reconstructible cache, never a 4th truth (D105-②)."""

    doc: DocId
    content_hash: str  # recomputed from the text (free)
    indexed_vector: bool  # re-verified by querying Qdrant
    indexed_graph: bool  # re-verified by querying the graph


@runtime_checkable
class IntentLog(Protocol):
    """The write-ahead journal that makes three-store integration crash-safe."""

    def record(self, intent: Intent) -> IntentId:
        """Append an intent BEFORE touching any store (D105-①)."""
        ...

    def replay(self) -> None:
        """Finish or roll back every uncommitted intent — IDEMPOTENTLY (invariant 24).

        Replaying twice must yield the same final state; this is what keeps the
        recovery safe under a second crash during replay (fail-safe, D100).
        """
        ...

    def mark_committed(self, doc: DocId, *, vector: bool, graph: bool) -> ConsistencyMarker:
        """Record that ``doc`` reached the derived stores (D105-②); returns the cache marker."""
        ...


@runtime_checkable
class TruthStore(Protocol):
    """``.md``/git — THE truth, the sole arbiter of every reconciliation (D56 / D105-④).

    Writes are atomic per document (D105 / D106), non-destructive (invariant 2):
    one invalidates or archives, one never hard-deletes. The derived stores
    (VectorIndex, GraphStore) rebuild from here; this never rebuilds from them.
    """

    def write(self, doc: DocId, content: Envelope[str]) -> ConsistencyMarker:
        """Write a document tout-ou-rien (atomic per doc); merge on update, never duplicate."""
        ...

    def read(self, doc: DocId) -> Envelope[str]:
        """Read the versioned truth; reads take no lock (read-during-write, D106 / inv. 25).

        CONTRACT (D136 / audit M-1c): the payload MUST round-trip byte-for-byte with what
        :meth:`write` stored — no normalisation, re-encoding, or whitespace fixup. Passage-aware
        recall re-chunks this text deterministically and selects by ordinal
        (:func:`~mnemosyne.ingest.chunk.select_passage`); any silent mutation here would shift every
        ordinal and pack the WRONG passage. A concrete adapter (e.g. a future git-backed store) that
        cannot guarantee byte-identity must instead store the chunker version alongside and invalidate
        stale ordinals — see the tracked D136 follow-up."""
        ...

    def invalidate(self, doc: DocId, *, reason: str) -> None:
        """Archive / close validity — never a hard delete (invariant 2 / D56 / D60)."""
        ...

    def is_valid(self, doc: DocId) -> bool:
        """Whether ``doc`` is present and still valid (not archived / invalidated, D60).

        The truth store is the arbiter (D56), so recall consults this to keep an ARCHIVED document out
        of an answer — least of all cited as a source once endorsed (D137 / audit finding 1): a derived
        index entry that outlived an archival is dropped fail-closed. An absent or closed document is
        not valid."""
        ...

    def role(self, doc: DocId) -> DocRole:
        """The document's epistemic role (D137) — read side of the endorsement gate.

        Fail-closed: every document is :data:`DEFAULT_ROLE` (matière-de-travail) until an explicit
        human gesture endorses it, so a matière-de-travail document is never presented as a source of
        truth at recall. An unknown id raises ``KeyError`` (never a guess)."""
        ...

    def set_role(self, doc: DocId, role: DocRole) -> None:
        """Set the document's epistemic role (D137) — the mechanism behind the endorsement gate.

        This is pure store mechanism; the HUMAN-GESTURE gate (endorsing to base-de-connaissances is
        never automatic — D59-5 / D100) lives above it in
        :meth:`~mnemosyne.api.core_api.CoreApi.endorse_document`. An unknown id raises ``KeyError``.
        Note (D137 / D58): a later :meth:`write` with CHANGED content reverts the role to
        :data:`DEFAULT_ROLE` — a new version is no longer an endorsed source until re-endorsed
        (fail-closed; mirrors living memory's update→PROPOSED on the CONTENT axis, role being orthogonal
        to sensitivity so a pure re-label at identical content keeps the endorsement)."""
        ...
