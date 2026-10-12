"""The benne - raw-intake realities (D85): lifecycle, non-destructive dedup FLAG, bound.

*The benne* (``knowledge/raw``, D16) is the raw entry point. D85 grades its three
concrete realities:

* an explicit, traceable document **lifecycle** - ``raw -> indexed -> distilled ->
  validated`` (D85 / D33), a forward-only progression;
* **near-duplicates FLAGGED non-destructively** - "resembles X", never auto-dropped;
  the human arbitrates (D54-3 / D59 ; non-destructive, invariant 2);
* a **bounded** intake so a flood of sources cannot exhaust the QUEUE DEPTH (D78 /
  invariant 16) - the ceiling (a COUNT of held items) comes from the protected zone
  (SE4). Since (3)-6 (resource limits) a SECOND, orthogonal ceiling bounds the BYTES one
  held source costs in RAM: a per-source byte cap (``intake_source_bytes``, SE4) refuses
  a single huge media before it is buffered, so one over-size file cannot exhaust memory
  even when the queue is nearly empty (closes the (3)-4-audit byte-cap debt).

Document integration into the three stores lands in LOT 4b; the benne holds and grades
sources up to that boundary. Code & docstrings English (D117); governance tokens stay
French (D33 / D66).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from enum import IntEnum

from ..config import Policy
from ..guard import check_bound
from ..ports import DocId, Envelope, Source

#: Policy bound name for the intake queue DEPTH - a COUNT of held items (D85 queue, D78 / SE4).
INTAKE_BOUND = "intake_capacity"
#: Policy bound name for the per-source RAW-BYTE ceiling ((3)-6 resource limits, D78 / SE4) - orthogonal
#: to the count bound: it caps the memory ONE held source may cost, so a single huge media is refused
#: before it is buffered (closes the (3)-4-audit debt where the count bound let one over-size file in).
INTAKE_SOURCE_BYTES_BOUND = "intake_source_bytes"


class LifecycleState(IntEnum):
    """A benne document's traceable lifecycle (D85 / D33).

    Ordered so advancement is monotonic - a document moves FORWARD only (a re-do is a
    fresh intake, not a rewind); the ordering itself is what makes :meth:`BenneItem.advance`
    refuse a backward move."""

    RAW = 0  # raw - landed, not yet indexed
    INDEXED = 1  # indexed - present in the derived stores (LOT 4b)
    DISTILLED = 2  # distilled - summarised / fact-extracted
    VALIDATED = 3  # validated - human-approved (D74 grid)


@dataclass(frozen=True, slots=True)
class BenneItem:
    """A raw source held in the benne: its content envelope (extracted text + governance label,
    D108-(5)), its lifecycle state, a content fingerprint for dedup, and - for a binary source - the
    raw :class:`~mnemosyne.ports.source.Source` itself, PRESERVED non-destructively (D85).

    Holding the raw ``source`` is the truth-first guarantee for binary ingestion ((3)-4): if the OCR /
    ASR extraction was poor (below the fidelity golden-set) or failed, the original bytes are still
    here, re-extractable later by a better engine - exactly as Moteur B preserves the datum for the
    LLM extractor. A plain-text intake carries ``source=None`` (there is nothing raw to keep)."""

    doc: DocId
    envelope: Envelope[str]
    state: LifecycleState
    fingerprint: str
    source: Source | None = None

    def advance(self, to: LifecycleState) -> BenneItem:
        """Move the document forward in its lifecycle (D85), returning the moved item.

        A backward move is refused - progress is non-destructive; re-doing work is a
        fresh intake, not a rewind (invariant 2 / D85)."""
        if to < self.state:
            raise ValueError(
                f"lifecycle cannot move backward from {self.state.name} to {to.name} (D85)"
            )
        return replace(self, state=to)


@dataclass(frozen=True, slots=True)
class DuplicateFlag:
    """A NON-DESTRUCTIVE near-duplicate signal (D85): ``doc`` resembles ``similar_to``
    with ``similarity``. The human arbitrates (D54-3 / D59) - the benne never auto-drops
    either copy."""

    doc: DocId
    similar_to: DocId
    similarity: float


_WORD = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> tuple[str, ...]:
    """Lowercased word tokens - the shingling substrate for near-duplicate detection."""
    return tuple(m.group(0).lower() for m in _WORD.finditer(text))


def _fingerprint(text: str) -> str:
    """Stable normalised content fingerprint - the exact-duplicate key (D85)."""
    return hashlib.sha256(" ".join(_tokens(text)).encode("utf-8")).hexdigest()


def _similarity(a: str, b: str) -> float:
    """Jaccard similarity over word sets - a cheap, deterministic near-dup measure.

    The heavier detector (MinHash / embedding) swaps in at LOT 4b; what LOT 4a fixes is
    the FLAG *contract* (non-destructive, human-arbitrated), not the metric."""
    sa, sb = set(_tokens(a)), set(_tokens(b))
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class Benne:
    """The raw intake zone (D85): bounded, dedup-flagging, lifecycle-tracking.

    Intake enforces the configured bound fail-closed (invariant 16), FLAGS a near
    duplicate non-destructively (never dropping it), and lands the document in the RAW
    state. Integration into the three stores is LOT 4b."""

    __slots__ = ("_capacity", "_max_source_bytes", "_near_threshold", "_items")

    def __init__(
        self,
        *,
        capacity: int,
        max_source_bytes: int | None = None,
        near_threshold: float = 0.8,
    ) -> None:
        if capacity < 0:
            raise ValueError(f"capacity must be >= 0, got {capacity}")
        if max_source_bytes is not None and max_source_bytes < 0:
            raise ValueError(f"max_source_bytes must be >= 0, got {max_source_bytes}")
        if not 0.0 < near_threshold <= 1.0:
            raise ValueError(f"near_threshold must be in (0, 1], got {near_threshold}")
        self._capacity = capacity
        # (3)-6: the per-source raw-byte ceiling. ``None`` => uncapped (a direct construction with no
        # binary sources, e.g. a text-only test); ``from_policy`` always sets it from the protected zone.
        self._max_source_bytes = max_source_bytes
        self._near_threshold = near_threshold
        self._items: dict[DocId, BenneItem] = {}

    @classmethod
    def from_policy(cls, policy: Policy, *, near_threshold: float = 0.8) -> Benne:
        """Build a benne whose intake ceilings come from the protected zone (SE4, D85/D78).

        BOTH bounds are read fail-closed: the queue DEPTH (``intake_capacity``) and the per-source
        BYTE ceiling (``intake_source_bytes``, (3)-6) - a missing bound raises, never a silent unbounded
        resource (D78 / invariant 16)."""
        return cls(
            capacity=policy.bound(INTAKE_BOUND),
            max_source_bytes=policy.bound(INTAKE_SOURCE_BYTES_BOUND),
            near_threshold=near_threshold,
        )

    def intake(
        self, doc: DocId, content: Envelope[str], *, source: Source | None = None
    ) -> tuple[BenneItem, DuplicateFlag | None]:
        """Land a source in the benne (state RAW), bounded and dedup-flagged.

        Refuses fail-closed if the bounded queue is full (invariant 16). Returns the
        landed item plus a non-destructive :class:`DuplicateFlag` when it resembles one
        already held - NEVER dropping either copy (the human arbitrates, D85). ``source`` is the raw
        binary original ((3)-4): when given it is PRESERVED on the item, so a poor / failed extraction
        is re-doable, never a lost datum; dedup keys on the EXTRACTED text (``content.payload``), so
        two scans of the same document are flagged as near-duplicates.

        NON-DESTRUCTIVE ((3)-4a audit, D85 / invariant 2): the benne is an append-only intake zone - a
        re-intake of an already-held ``doc`` is REFUSED fail-closed (a document is advanced through its
        lifecycle via :meth:`advance`, never silently overwritten). This closes the collision where a
        reused ``DocId`` would clobber a preserved raw source (losing the datum) and reset its state."""
        if doc in self._items:
            raise ValueError(
                f"benne is non-destructive: {doc!r} is already held - re-intake is refused (advance "
                "its lifecycle, or use a fresh id); overwriting would drop the preserved source (D85)"
            )
        check_bound(len(self._items), self._capacity, resource="benne_intake")
        # (3)-6 per-source byte ceiling (orthogonal to the queue-depth count): refuse a single over-size
        # raw source BEFORE it is retained, so one huge media cannot exhaust RAM (D78 / invariant 16). A
        # source whose byte count is at or above the ceiling is refused fail-closed (check_bound: `>=`).
        if source is not None and self._max_source_bytes is not None:
            check_bound(len(source.data), self._max_source_bytes, resource="benne_source_bytes")
        flag = self._nearest_duplicate(doc, content)
        item = BenneItem(
            doc=doc,
            envelope=content,
            state=LifecycleState.RAW,
            fingerprint=_fingerprint(content.payload),
            source=source,
        )
        self._items[doc] = item
        return item, flag

    def item(self, doc: DocId) -> BenneItem:
        """The held item; an unknown id raises ``KeyError`` (never a guess)."""
        return self._items[doc]

    def advance(self, doc: DocId, to: LifecycleState) -> BenneItem:
        """Advance a held document's lifecycle (D85), storing the moved item."""
        moved = self._items[doc].advance(to)
        self._items[doc] = moved
        return moved

    def _nearest_duplicate(self, doc: DocId, content: Envelope[str]) -> DuplicateFlag | None:
        """The nearest near-duplicate, CLOISONNEMENT-scoped ((3)-4a audit).

        A near-duplicate is only ever flagged against a source in the SAME partition AND bubble
        (invariant 1 / 3), so a capture receipt never names a document from another sensitivity /
        bubble (no cross-partition metadata leak - the DocId of a ``sensible`` scan must not surface in
        a ``perso`` receipt). A token-less extraction (a blank / failed OCR) is not compared at all:
        two empty extractions are not "duplicates" (an honest receipt, F3), only two coincidental
        blanks."""
        tokens = _tokens(content.payload)
        if not tokens:
            return None
        label = content.label
        best: DuplicateFlag | None = None
        for other_id, other in self._items.items():
            if other_id == doc:
                continue
            if (
                other.envelope.label.bubble != label.bubble
                or other.envelope.label.sensitivity != label.sensitivity
            ):
                continue  # a different cloisonnement is never compared (no leak, invariant 1 / 3)
            score = _similarity(content.payload, other.envelope.payload)
            if score >= self._near_threshold and (best is None or score > best.similarity):
                best = DuplicateFlag(doc=doc, similar_to=other_id, similarity=score)
        return best
