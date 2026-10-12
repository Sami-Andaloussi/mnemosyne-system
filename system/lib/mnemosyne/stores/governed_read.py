"""Governed reading (D119 / D65 / D136) - the shared read frontier + passage packing.

Extracted from :class:`~mnemosyne.api.core_api.CoreApi` so the SAME governed-read rule serves
BOTH the facade's ``search`` / ``recall`` and the agent's ``search_memory`` tool ((3)-5b): one
definition of the cloisonnement frontier and the passage packer, never two copies that could
drift into a leak (consolidate-crosscutting-rules - a governance rule lives in ONE place).

* :func:`may_read` - the DOMAIN then BUBBLE frontier a hit must pass to be shown to a subject,
  both Guard-mediated and deny-by-default (D89 / D72 / D54).
* :func:`pack_passage` - the RELEVANT passage of a hit (never the whole document, D136), keeping
  the document's own governance label so cloisonnement travels with it (D108-(5)).

Code & docstrings English (D117).
"""

from __future__ import annotations

from typing import Protocol

from ..ingest.chunk import select_passage
from ..ports import (
    Bubble,
    Decision,
    DocId,
    Effect,
    Envelope,
    GovernanceLabel,
    Guard,
    GuardRequest,
    SearchHit,
)
from .raptor import RaptorNode, is_raptor_summary

#: Over-fetch width for a governed read (MAJEUR-2). A read surface retrieves a WIDE pool, applies the
#: cloisonnement frontier (:func:`may_read`), THEN truncates to the caller's ``top_k`` - so a
#: to-be-withheld hit (foreign bubble / undeclared domain), or one a cross-encoder ranks high, can no
#: longer take a ``top_k`` slot and EVICT a readable one, silently reducing READABLE recall. Never a
#: leak (the foreigner still fails ``may_read``), only a recall repair. Shared by BOTH read surfaces -
#: the facade (``CoreApi.search`` / ``recall``) and the agent's ``search_memory`` tool - so the two
#: never drift (consolidate-crosscutting-rules). Kept ``>=`` the rerank pool
#: (``reranked_retriever._RERANK_POOL`` = 40) so a wired reranker reranks the FULL pool and the surface
#: takes the ``top_k`` readable of that reranked order. A bounded over-fetch (invariant 16): at most
#: ``READ_POOL`` Guard checks + one wide retrieve, only ``top_k`` ever packed.
READ_POOL = 40


class TruthReader(Protocol):
    """The minimal read surface :func:`pack_passage` needs: a doc id -> its truth envelope."""

    def read(self, doc: DocId) -> Envelope[str]: ...


class TruthValidity(Protocol):
    """The ``is_valid`` arbiter :func:`summary_is_current` needs - a doc id -> still-valid truth (D56)."""

    def is_valid(self, doc: DocId) -> bool: ...


class GovernedTruth(TruthReader, TruthValidity, Protocol):
    """read (leaf packing) + is_valid (summary staleness) - the truth surface a governed read needs
    to serve BOTH leaf documents and RAPTOR summaries from one call site (search_memory)."""


class SummarySource(Protocol):
    """The RaptorStore read surface :func:`pack_summary` needs - a summary doc id -> its node (D56).

    ``get`` raises ``KeyError`` for an unknown / swept id, exactly like
    :class:`~mnemosyne.stores.raptor.RaptorStore`."""

    def get(self, doc: DocId) -> RaptorNode: ...


def may_read(guard: Guard, subject: Bubble, label: GovernanceLabel) -> bool:
    """Whether ``subject`` may read a hit labelled ``label`` - DOMAIN then BUBBLE frontiers.

    Two Guard-mediated frontiers, deny-by-default (D89), both centralized in the Guard (D119):
    (1) DOMAIN cloisonnement - a hit carrying a domain ``subject`` does not declare is withheld
    (invariant 4 / D72), enforced EVEN intra-bubble (a bubble sees only its declared domains), so a
    validated cross-bubble contract can never widen the domain grain it is meant to restrict;
    (2) BUBBLE cloisonnement - a foreign-bubble hit passes only through a validated cross-bubble
    contract (invariant 3 / D54). A same-bubble hit whose domains are all declared is an intra-bubble
    read (not a frontier, D89); a domain-less hit skips gate (1). Any non-ALLOW ruling never surfaces
    the hit (fail-closed)."""
    # (1) domain frontier (invariant 4 / D72) - checked even for a same-bubble hit.
    if label.domains:
        domain_ruling = guard.authorize(
            GuardRequest(
                effect=Effect.DOMAIN_ACCESS,
                subject=subject,
                inputs=(label,),
                target=None,
                descriptor="domain read",
            )
        )
        if domain_ruling.decision is not Decision.ALLOW:
            return False
    # (2) bubble frontier (invariant 3 / D54) - a same-bubble hit is intra-bubble (allowed).
    if label.bubble == subject:
        return True
    ruling = guard.authorize(
        GuardRequest(
            effect=Effect.CROSS_BUBBLE,
            subject=subject,
            inputs=(label,),
            target=str(label.bubble),
            descriptor="cross-bubble read",
        )
    )
    return ruling.decision is Decision.ALLOW


def pack_passage(truth: TruthReader, hit: SearchHit, query: str) -> Envelope[str]:
    """Pack the RELEVANT passage of a recall hit, never the whole document (D136).

    A whole-document read would overflow the model at generation (the fail-closed runner bound
    refuses it, D136 / invariant 16); instead the truth is re-chunked deterministically and the
    matched passage selected - ``hit.chunk`` from the dense index, or the best lexical passage for a
    keyword-only hit (:func:`~mnemosyne.ingest.chunk.select_passage`). The passage keeps the
    document's OWN governance label (the truth envelope's), so cloisonnement travels with it
    unchanged (D108-(5)); only the payload shrinks to what an answer actually needs."""
    whole = truth.read(hit.doc)
    passage = select_passage(whole.payload, query, ordinal=hit.chunk)
    return Envelope(passage, whole.label)


def summary_is_current(
    summaries: SummarySource,
    truth: TruthValidity,
    node: RaptorNode,
    _seen: frozenset[DocId] = frozenset(),
) -> bool:
    """Whether every LEAF book a RAPTOR synopsis rolls up is still valid truth (audit M2, D137).

    Symmetric with the leaf read path's ``truth.is_valid`` gate: recurse a **domain** synopsis (whose
    members are book synopses) down to the leaf book ids and check
    :meth:`~mnemosyne.ports.store.TruthStore.is_valid` on each - the SAME arbiter (D56). A member
    synopsis already swept from the store, or a leaf archived at the truth level, makes the whole
    synopsis stale: dropped fail-closed, never surfaced (D100 / D74). Between an archival and the next
    ``make raptor-build`` sweep, this read-time check is what upholds 'archived => never surfaced as
    answer content' for the derived summary layer too. A cyclic member graph - only reachable from a
    corrupted / tampered on-disk store - is treated as stale (a revisited node returns ``False``),
    fail-closed, never a ``RecursionError`` out of a recall (audit NIT-2)."""
    if node.doc in _seen:
        return False  # a cycle (corrupted store) => stale, fail-closed - never a RecursionError
    seen = _seen | {node.doc}
    for member in node.member_ids:
        if is_raptor_summary(member):
            try:
                child = summaries.get(member)
            except KeyError:
                return False  # a member synopsis vanished (swept) => this rollup is stale
            if not summary_is_current(summaries, truth, child, seen):
                return False
        elif not truth.is_valid(member):
            return False  # a leaf book archived at the truth level => stale
    return True


def pack_summary(
    summaries: SummarySource,
    truth: TruthValidity,
    guard: Guard,
    subject: Bubble,
    hit: SearchHit,
) -> Envelope[str] | None:
    """Resolve a RAPTOR summary hit's synopsis text from the RaptorStore (Ch.5), never truth.

    A ``library/summary/`` doc is DERIVED (D56): it holds no truth-store fiche, so reading it through
    :func:`pack_passage` would ``KeyError`` on ``truth.read``. This is the ONE governed summary read,
    shared by the facade's ``recall`` and the agent's ``search_memory`` tool so neither grows a second
    copy that could drift into a leak (consolidate-crosscutting-rules). Two gates keep a synopsis
    honest, symmetric with the leaf path: (M2) it is dropped when it rolls up an ARCHIVED book
    (:func:`summary_is_current`, the same ``truth.is_valid`` arbiter); (m1) its OWN stored
    ``node.label`` is re-gated against ``subject`` (same-bubble + :func:`may_read`), so a store/index
    label divergence drops fail-closed rather than leaking. Returns ``None`` when the node was swept
    meanwhile - the caller drops it silently, never a crash (D100)."""
    try:
        node = summaries.get(hit.doc)
    except KeyError:
        return None
    if not summary_is_current(summaries, truth, node):
        return None  # M2 - a synopsis of an archived book is stale content, never surfaced
    if node.label.bubble != subject or not may_read(guard, subject, node.label):
        return None  # m1 - re-gate the STORED label, not merely the vector hit's
    return Envelope(node.text, node.label)
