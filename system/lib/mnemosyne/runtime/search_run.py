"""search_run (item 4 / D149 / D65) — the thin RAG READ surface for a FRONTIER host.

``make agent`` runs the whole governed loop: retrieve, then REASON and GENERATE with the local MLX
brain, returning a synthesized answer. A frontier host (Claude Code / Codex) does its OWN reasoning —
it wants the raw RETRIEVED PASSAGES, not a small local model's answer laid on top. This entry is that
surface: it runs Mnémosyne's governed hybrid read (:meth:`~mnemosyne.api.core_api.CoreApi.recall`,
D65 — reranked dense ⊕ BM25, cloisonnement-gated) and PRINTS the passages, so a frontier can query the
library from a shell and reason frontier-side::

    make search Q="Kelly criterion and risk of ruin"
    python -m mnemosyne.runtime.search_run "<query>" [--within sensible] [--top-k 8]

Retrieval-only, so NO generative brain is loaded (:func:`~mnemosyne.runtime.bootstrap.real_runtime`
with ``load_brain=False``): bge-m3 + Qdrant + BM25 + reranker only — the ~GB MLX LLM weights are never
touched. It reads AS the knowledge bubble, defaulting to the PUBLIC partition — where the reference library now
lives after the 2026-07-16 "books = public by provenance" migration (~235k chunks in
``mnemosyne_public``; ``--within`` selects another partition). It reads through the SAME Guard: a
frontier host never sees a passage a human search could not (invariant 4 / 3 / D72 / D54), and an
insufficient retrieval ADMITS "no confident memory" (invariant 14) rather than inventing.

Honest limit (D136): the governed passage packer keeps only the passage TEXT, so this surface groups
passages by their provenance ROLE — ENDORSED source (citable) / WORKING material (never a source) /
validated LIVING fiche — but does not yet print a per-passage doc id to cite. Add that (via the packer)
only if citation-by-id proves needed. Code & docstrings English (D117). NOT run in CI (needs the bricks).
"""

from __future__ import annotations

import argparse
import sys

from ..api import CoreApi, RecallView
from ..guard.fencing import fence_recalled, sanitize_recalled
from ..ingest.library import KNOWLEDGE_BUBBLE
from ..ports import Sensitivity
from .bootstrap import real_runtime

#: The partition the reference library lives in — PUBLIC since the 2026-07-16 "books = public by
#: provenance" migration (``mnemosyne_public`` holds the ~235k library chunks). The default `within`.
#: NOTE: ``make agent`` runs under a conservative SENSIBLE safety floor (D101, "sensible until proven"),
#: which ALSO scopes its search to the near-empty sensible partition — so the agent does not currently
#: reach this public library. Decoupling the answer-label posture from the search partition is a separate
#: design question (flagged). ``make search`` is a direct, explicit read, so it targets where the corpus is.
_DEFAULT_WITHIN = Sensitivity.PUBLIC

#: Human token ("public" / "perso" / "sensible") → member — ``Sensitivity`` is an IntEnum whose ``.token``
#: is the french label (D33), so ``--within sensible`` resolves cleanly (never the int ``.value``).
_SENSITIVITY_BY_TOKEN = {s.token: s for s in Sensitivity}


def render_recall(view: RecallView, query: str) -> str:
    """Render a :class:`~mnemosyne.api.core_api.RecallView` as plain text for a frontier host to read.

    Pure (no bricks) so it is unit-tested directly. Prints the read routing then the three provenance
    buckets kept SEPARATE by :meth:`~mnemosyne.api.core_api.CoreApi.recall` (D137) — endorsed sources,
    working material, living frame — each passage numbered. An all-empty low-recall view prints the
    explicit admission (invariant 14), never a blank that reads like "nothing exists".

    Every passage is FENCED (D154): what comes back is third-party text — a book, a report, a
    transcript — landing straight in a frontier's prompt, where a sentence buried mid-document
    is otherwise indistinguishable from an instruction. Each payload is sanitised individually
    (so no single passage can close the fence and promote its tail to top-level), and the whole
    recall travels inside ONE annotated block, so the reader sees one boundary, not twenty."""
    header = [
        f"query: {query!r}",
        f"engines: {', '.join(view.engines) or '(none)'}",
        f"reason: {view.reason}",
        "",
    ]
    if view.admitted_low_recall and not (view.facts or view.working_material or view.frame):
        header.append(
            "[no confident memory] — nothing readable cleared the recall floor (invariant 14). "
            "Say what you could not find rather than inventing."
        )
        return "\n".join(header)

    def _bucket(title: str, envs: tuple) -> list[str]:
        out = [f"== {title} ({len(envs)}) =="]
        if not envs:
            out.append("  (none)")
        for i, env in enumerate(envs, start=1):
            # per-passage sanitising: one poisoned passage must not un-fence the ones after it
            out.append(f"[{i}]\n{sanitize_recalled(str(env.payload))}")
        return out

    body = list(_bucket("ENDORSED SOURCES — citable (base-de-connaissances)", view.facts))
    body.append("")
    body += _bucket(
        "WORKING MATERIAL — unverified, NEVER a source (matiere-de-travail)", view.working_material
    )
    body.append("")
    body += _bucket("LIVING FRAME — validated fiches (Moteur A)", view.frame)
    return "\n".join([*header, fence_recalled("\n".join(body))])


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - [OPERATOR] ignition (bricks, no MLX brain)
    parser = argparse.ArgumentParser(
        prog="make search",
        description="Query Mnémosyne's library and PRINT the retrieved passages (frontier read surface).",
    )
    parser.add_argument("query", help="the natural-language query to retrieve passages for")
    parser.add_argument(
        "--within",
        default=_DEFAULT_WITHIN.token,
        choices=sorted(_SENSITIVITY_BY_TOKEN),
        help="sensitivity partition to search (default: public — where the reference library lives)",
    )
    parser.add_argument("--top-k", type=int, default=8, help="max passages per bucket (default 8)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    within = _SENSITIVITY_BY_TOKEN[args.within]

    print(
        "[search_run] building real_runtime (bge-m3 + Qdrant + BM25 + reranker; NO MLX brain)…",
        flush=True,
    )
    runtime = real_runtime(load_brain=False)
    api = CoreApi(runtime)
    print(
        f"[search_run] subject={KNOWLEDGE_BUBBLE!r} within={within.token} top_k={args.top_k}\n",
        flush=True,
    )
    view = api.recall(args.query, within=within, subject=KNOWLEDGE_BUBBLE, top_k=args.top_k)
    print(render_recall(view, args.query))
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] ignition
    raise SystemExit(main())
