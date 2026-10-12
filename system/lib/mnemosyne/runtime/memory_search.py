"""search_memory ((3)-5b / D114 / D65) - the agent's read tool over Mnémosyne's OWN memory.

The FIRST governed tool wired to the agent loop (D98): a ``local_function``, ``read_only``,
``stays_local`` tool that runs the SAME hybrid retrieval as the facade's ``search`` (D65) and the
SAME cloisonnement frontier + passage packer (:mod:`~mnemosyne.stores.governed_read`) - so the agent
can never see a hit a human search could not (invariant 4 / 3), never the whole document (D136), and
an insufficient retrieval ADMITS "no confident memory" (invariant 14) instead of inventing.

Deny-by-default holds structurally: the back-end is always wired, but the Guard refuses the call
until user sanctions the manifest in the protected catalog (``tools.toml``, D114-(5) / D102). The
untrusted return is re-floored by the invoker (D100-3), so this callable never labels its own output.

Code & docstrings English (D117).
"""

from __future__ import annotations

from ..ports import (
    Bubble,
    DataEgress,
    Envelope,
    Guard,
    SearchHit,
    Sensitivity,
    ToolBackend,
    ToolEffect,
    ToolManifest,
)
from ..stores import Retriever, is_raptor_summary
from ..stores.governed_read import (
    READ_POOL,
    GovernedTruth,
    SummarySource,
    may_read,
    pack_passage,
    pack_summary,
)
from ..tools import LocalFunctionTool

#: The tool's allow-list name - the key user sanctions in ``tools.toml`` and the agent calls (D114-(5)).
SEARCH_MEMORY = "search_memory"

#: How many passages a call returns - bounded context (invariant 16 / D136): enough to reason, never
#: the whole corpus. Tuned per model at (3) if a run shows it too tight or too broad.
_TOP_K = 6


def search_memory_manifest() -> ToolManifest:
    """The manifest describing :data:`SEARCH_MEMORY` - must MATCH the ``tools.toml`` entry user
    sanctions (D114-(5)). ``read_only`` + ``stays_local``: the Guard never escalates it to a human
    gesture (no life-action, no egress), yet it stays refused until the allow-list carries it."""
    return ToolManifest(
        name=SEARCH_MEMORY,
        backend=ToolBackend.LOCAL_FUNCTION,
        io_schema="query:str -> passages:str",
        permissions=("read",),
        egress=DataEgress.STAYS_LOCAL,
        effect=ToolEffect.READ_ONLY,
    )


def build_search_memory_tool(
    *,
    retriever: Retriever,
    guard: Guard,
    truth: GovernedTruth,
    summaries: SummarySource | None = None,
    top_k: int = _TOP_K,
    search_within: Sensitivity | None = None,
) -> LocalFunctionTool:
    """Build the governed ``search_memory`` tool over the assembled stores ((3)-5b / D65).

    The callable retrieves within ONE sensitivity partition (invariant 1, never crossed) and the call's
    domains, keeps only hits the caller :func:`~mnemosyne.stores.governed_read.may_read` (domain +
    bubble frontier), packs each to its relevant passage (:func:`~mnemosyne.stores.governed_read.
    pack_passage`, D136), and returns them as text. A low-recall retrieval returns an explicit "no
    confident memory" admission (invariant 14); hits all withheld by cloisonnement say so - never a
    silent empty that reads like "nothing exists".

    ``search_within`` is the tool's READ CLEARANCE - the ONE partition it searches - DECOUPLED from the
    calling agent's answer-floor label (item 12). ``None`` (default) => it searches the CALL's own
    partition (``call.label.sensitivity``), the zero-regression behaviour any generic caller keeps. Set
    (the bootstrap wiring) => it searches THAT partition regardless of the call's floor: the library agent
    runs under a conservative ``sensible`` ANSWER floor (D101) yet must read its ``public`` reference
    library, so it is wired ``search_within=PUBLIC`` - the shelf where the books live, exactly where
    ``make search`` reads. This never widens exposure: it selects a SINGLE, EXPLICIT, user-wired partition
    (still invariant 1 - one partition, never crossed), the ``may_read`` bubble/domain frontier is
    unchanged, and the untrusted return is re-floored UP to the call's floor by the invoker (D100-3), so a
    ``public`` passage comes back labelled at least ``sensible`` - over-protective, never a declassification.

    A RAPTOR summary hit (``library/summary/*``, Ch.5) holds NO truth fiche - its text lives in the
    injected ``summaries`` RaptorStore - so it is packed through the SAME governed summary read the
    facade's ``recall`` uses (:func:`~mnemosyne.stores.governed_read.pack_summary`: staleness +
    stored-label re-gate), never the truth packer that would ``KeyError`` on it. Left ``None`` (a
    hand-built runtime, D126), a summary hit is dropped silently rather than crashing.

    Deliberately SEARCH-grade, exactly like the facade's ``search`` ((3)-5b live): it does NOT filter by
    ``is_valid`` (a FICHE concept - every raw DOCUMENT fails it, so the whole working-material library
    would vanish, D137) nor split by epistemic role. The library stays fully searchable to the agent."""
    # MINOR-1 (audit ebf0846): make the one-partition-DOWN guarantee STRUCTURAL, not a convention. The return
    # re-floor keys off the CALL's own floor + content PII (see the invoker), NOT the partition read - so a
    # wiring that read a HIGHER partition than the caller's floor would silently declassify. PUBLIC is the
    # global-minimum partition (the shared reference shelf), so it is the ONLY safe down-read; None = the
    # call's own partition. Any other value is refused fail-closed at BUILD time (a miswire fails LOUD).
    if search_within is not None and search_within is not Sensitivity.PUBLIC:
        raise ValueError(
            f"search_within must be None (the call's own partition) or PUBLIC (the shared shelf), got "
            f"{search_within.token!r}: a tool may only DOWN-read to the global-minimum partition, never UP "
            "to a more-sensitive one (invariant 1 / D100 - the return re-floor would not catch it)"
        )

    def _run(call: Envelope[object]) -> str:
        query = call.payload if isinstance(call.payload, str) else str(call.payload)
        subject: Bubble = call.label.bubble
        # The READ CLEARANCE (item 12): the wired partition when set, else the call's own - DECOUPLED from
        # the answer floor so the library agent reads `public` (its books) under a `sensible` answer label.
        within: Sensitivity = search_within if search_within is not None else call.label.sensitivity
        # MAJEUR-2: over-fetch a WIDE pool, clear the cloisonnement frontier, THEN truncate to top_k -
        # the SAME readable-recall repair the facade applies (READ_POOL, governed_read), so a
        # to-be-withheld hit ranked high no longer evicts a readable one from the returned top_k.
        result = retriever.retrieve(
            query, within=within, domains=call.label.domains, top_k=max(top_k, READ_POOL)
        )
        if result.admitted_low_recall:
            return f"[search_memory] no confident memory for {query!r} - {result.reason}"
        readable = tuple(hit for hit in result.hits if may_read(guard, subject, hit.label))[:top_k]
        if not readable:
            return (
                f"[search_memory] {len(result.hits)} hit(s) found but none readable from here "
                "- withheld by cloisonnement (domain / bubble)"
            )
        # Leaf hits stay the untouched truth packer (D136); a RAPTOR summary hit is read from the
        # RaptorStore through the shared governed summary read - which may drop it (stale / swept /
        # unwired), so pack THEN filter rather than assume every readable hit yields a passage.
        packed: list[tuple[SearchHit, Envelope[str]]] = []
        for hit in readable:
            if is_raptor_summary(hit.doc):
                env = (
                    pack_summary(summaries, truth, guard, subject, hit)
                    if summaries is not None
                    else None
                )
            else:
                env = pack_passage(truth, hit, query)
            if env is not None:
                packed.append((hit, env))
        if not packed:
            return (
                f"[search_memory] {len(readable)} summary hit(s) matched but none current "
                "- stale or swept (nothing to show)"
            )
        # RAW on purpose (D154). The fence used to be applied here - but this runs UPSTREAM of
        # the invoker's PII floor, so a document could splice its own PII across a forged tag
        # and have the sanitising hide it before the floor looked. The invoker now fences every
        # tool return, after flooring and redacting it. Do not re-add fencing here.
        blocks = [
            f"[{i}] doc={hit.doc} score={hit.score:.3f}\n{env.payload}"
            for i, (hit, env) in enumerate(packed, start=1)
        ]
        return "\n\n".join(blocks)

    return LocalFunctionTool(search_memory_manifest(), _run)
