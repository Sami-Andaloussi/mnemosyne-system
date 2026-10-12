"""MarkdownTruthStore (D105 / D56) - the ``.md``/git truth: merge-on-update, non-destructive.

Moteur B's arbiter. On any disagreement the versioned text wins ALWAYS, and the
derived stores (VectorIndex, GraphStore) rebuild from HERE - never the reverse
(D56). This lot ships a light in-memory stand-in for the ``.md``/git layer; the
real git-backed adapter (our "light glue over git", D105 / D98) swaps in behind
the :class:`~mnemosyne.ports.store.TruthStore` port without touching a caller.
What LOT 4b fixes is the *contract*:

* **merge-on-update** - writing an existing document updates its fiche in place; it
  never creates a second fiche (invariant 9 / D58). History is kept, so the merge
  is non-destructive (invariant 2): each write appends a version, the latest wins.
* **atomic per document** - a write is all-or-nothing at the document grain, never a
  global transaction (D105 / D106).
* **non-destructive invalidation** - :meth:`~MarkdownTruthStore.invalidate` closes a
  fiche's validity (archival); it never hard-deletes (invariant 2 / D56 / D60).
* **reads take no lock** - a read never blocks on a concurrent write
  (read-during-write, D106 / invariant 25).

Code & docstrings English (D117); governance tokens stay French (D33 / D66).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from ..ports import DEFAULT_ROLE, ConsistencyMarker, DocId, DocRole, Envelope


def content_hash(payload: str) -> str:
    """The reconstructible content key of a :class:`ConsistencyMarker` (D105-(2)).

    A pure function of the text, so the marker is a rebuildable cache and never a
    fourth source of truth; the journal reuses it so its markers agree with the
    store's (invariant 24)."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Fiche:
    """A document's versioned truth: its ordered history plus validity (D105 / D56).

    ``versions`` keeps every written envelope (non-destructive, invariant 2); the
    LAST is the current truth. ``invalid_reason`` closes validity without erasing
    (archival, D60). ``role`` is the epistemic axis (D137): matière-de-travail until
    an explicit human gesture endorses it as a base-de-connaissances source."""

    doc: DocId
    versions: tuple[Envelope[str], ...]
    invalid_reason: str | None = None
    role: DocRole = DEFAULT_ROLE  # D137 - fail-closed: working material until endorsed

    @property
    def current(self) -> Envelope[str]:
        """The current truth - the most recent version (D56)."""
        return self.versions[-1]


class MarkdownTruthStore:
    """In-memory stand-in for the ``.md``/git truth (D105), implementing
    :class:`~mnemosyne.ports.store.TruthStore`: merge-on-update, atomic per document,
    non-destructive, lock-free reads."""

    __slots__ = ("_fiches",)

    def __init__(self) -> None:
        self._fiches: dict[DocId, Fiche] = {}

    def write(self, doc: DocId, content: Envelope[str]) -> ConsistencyMarker:
        """Write ``doc`` all-or-nothing; MERGE on update, never a duplicate (invariant 9).

        A first write creates the fiche; a subsequent write appends a version to the
        SAME fiche (merge-on-update, D58) and keeps the prior versions (non-destructive,
        invariant 2). Re-writing also re-opens validity (a fresh assertion supersedes a
        prior archival). Returns the per-document consistency marker (derived flags
        start false; the journal sets them once the derived stores catch up)."""
        existing = self._fiches.get(doc)
        if existing is None:
            self._fiches[doc] = Fiche(doc=doc, versions=(content,))
        else:
            # merge-on-update (D58): append the version, re-open validity. A CHANGED content ALSO
            # re-opens the ROLE gesture (D137, fail-closed): a new version of an endorsed source is no
            # longer trusted as authority until re-endorsed. This mirrors living memory's update->PROPOSED
            # on the CONTENT axis ONLY - role tracks whether the CONTENT is an authoritative source, so a
            # pure sensitivity re-label at identical content keeps the endorsement (the new sensitivity
            # rides on this version's label separately; role is orthogonal to sensitivity, D137). An
            # identical re-write (same content hash) keeps the endorsement - idempotent, so a duplicate
            # capture never silently demotes a source (like :meth:`LivingMemory.propose`).
            changed = content_hash(content.payload) != content_hash(existing.current.payload)
            self._fiches[doc] = replace(
                existing,
                versions=(*existing.versions, content),
                invalid_reason=None,
                role=DEFAULT_ROLE if changed else existing.role,
            )
        return ConsistencyMarker(
            doc=doc,
            content_hash=content_hash(content.payload),
            indexed_vector=False,
            indexed_graph=False,
        )

    def read(self, doc: DocId) -> Envelope[str]:
        """Read the current versioned truth; an unknown id raises ``KeyError``.

        Reads take NO lock (read-during-write, D106 / invariant 25): a concurrent
        write never blocks a reader."""
        return self._fiches[doc].current

    def invalidate(self, doc: DocId, *, reason: str) -> None:
        """Archive / close a fiche's validity - never a hard delete (invariant 2 / D60).

        The fiche and its whole version history remain; only validity is closed, so
        the truth is recoverable and a past reader still sees it."""
        self._fiches[doc] = replace(self._fiches[doc], invalid_reason=reason)

    def role(self, doc: DocId) -> DocRole:
        """The document's epistemic role (D137); an unknown id raises ``KeyError`` (never a guess)."""
        return self._fiches[doc].role

    def set_role(self, doc: DocId, role: DocRole) -> None:
        """Set the document's epistemic role (D137) - pure mechanism; the human-gesture endorsement
        gate lives in :meth:`~mnemosyne.api.core_api.CoreApi.endorse_document`. An unknown id raises
        ``KeyError``. A later :meth:`write` with changed content reverts an endorsement (D137 / D58)."""
        self._fiches[doc] = replace(self._fiches[doc], role=role)

    # --- non-destructive introspection (no destructive verb - invariant 2) ---
    def count(self) -> int:
        """The number of distinct fiches - the anti-duplicate witness (invariant 9)."""
        return len(self._fiches)

    def versions(self, doc: DocId) -> tuple[Envelope[str], ...]:
        """A fiche's full, non-destructive version history (invariant 2)."""
        return self._fiches[doc].versions

    def is_valid(self, doc: DocId) -> bool:
        """Whether a fiche is present and still valid (not archived)."""
        fiche = self._fiches.get(doc)
        return fiche is not None and fiche.invalid_reason is None
