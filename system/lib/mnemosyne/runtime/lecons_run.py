"""`make lecons` — QUERY the lessons instead of always receiving all of them (workstream 0, A1).

The pull surface that complements the push channel. It replaces nothing and erases nothing:
`MEMORY.md` stays frozen and loaded by the built-in, `MEMORY-2.md` stays injected by the hook. What
it adds is the ability to ASK — and so, later, to pull down what should be pushed.

No model, no network, no cost. `sqlite3` is in the standard library.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..production.lecons import IndexDesLecons, Rappel
from .memoire import dossier_de_memoire


def rendre(rappel: Rappel, question: str, *, compte: int, limite: int = 6) -> str:
    """What the user (or an agent) reads. The count of indexed fiches is ALWAYS printed.

    Printing the corpus size on every answer is not decoration: an index that answers "nothing"
    because it is EMPTY reads exactly like one that answers "nothing" because the corpus holds nothing.
    *A refusal reads as one, an empty result is taken on faith* — the same failure the search door was
    hardened against on 2026-07-28, reproduced here would be the same bug in a new place.
    """
    lignes = [f"# Lessons · {compte} fiche(s) indexed"]
    if not question.strip():
        lignes.append("")
        lignes.append('Ask a question: make lecons Q="what you are about to do"')
        return "\n".join(lignes)

    if rappel.mode == "none":
        lignes.append("")
        lignes.append(
            "\U000026A0\U0000FE0F No searchable word in this question (only stop-words). This is NOT "
            "\"there is nothing\" — it is \"I was not able to search\"."
        )
        return "\n".join(lignes)

    if not rappel.trouvailles:
        lignes.append("")
        if limite <= 0:
            # MEASURED ON 2026-08-09, ON THIS VERY SURFACE: with `TOPK=-1` the read bound
            # (inv. 16) returns zero results, and this block used to announce "a true nothing" on a
            # corpus that carries the answer. *A refusal that names the WRONG cause is worse than a
            # silent refusal*: it closes the question instead of reopening it. The cause is named here.
            lignes.append(
                f"\U000026A0\U0000FE0F You asked for {limite} result(s): the read bound returns zero BEFORE "
                f"any search runs. This is NEITHER an abstention NOR a true \"nothing\" — the corpus "
                f"({compte} fiches) was never consulted. Rerun with TOPK >= 1."
            )
            return "\n".join(lignes)
        lignes.append(
            f"No lesson carries {' + '.join(rappel.termes)}. The corpus WAS "
            f"queried ({compte} fiches) — this is a true \"nothing\", not a closed door."
        )
        return "\n".join(lignes)

    precision = "all words" if rappel.mode == "and" else "at least one word (fallback)"
    lignes.append(
        f"_{len(rappel.trouvailles)} lesson(s) · {precision} · {' + '.join(rappel.termes)}_"
    )
    lignes.append("")
    for t in rappel.trouvailles:
        titre = t.titre or "(this fiche carries no description)"
        lignes.append(f"- **{t.nom}** — {titre}")
        if t.extrait:
            lignes.append(f"  > {t.extrait}")
    lignes.append("")
    lignes.append("Read one BEFORE acting: a cited lesson is not an applied lesson.")
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - [OPERATOR] surface (host tree)
    parser = argparse.ArgumentParser(
        description="Query the memory's lessons (full-text, no model, no cost)."
    )
    parser.add_argument("question", nargs="?", default="", help="what you are looking for")
    parser.add_argument("--top-k", type=int, default=6, help="number of lessons returned")
    parser.add_argument(
        "--dossier", type=Path, default=None, help="memory folder (default: derived)"
    )
    args = parser.parse_args(argv)

    dossier = args.dossier or dossier_de_memoire()
    if not dossier.is_dir():
        # NOT "the memory is empty" — a path that does not resolve. The distinction is the whole
        # point: concluding "empty" from an unresolved path is how a full corpus gets declared absent.
        print(
            f"\U000026D4 memory folder NOT FOUND: {dossier}\n"
            f"This is not \"the memory is empty\", it is a path that does not resolve. "
            f"Do not conclude anything about the lessons from this refusal.",
            file=sys.stderr,
        )
        return 2

    index = IndexDesLecons(dossier)
    try:
        index.refresh()
        rappel = index.search(args.question, limit=args.top_k)
        print(rendre(rappel, args.question, compte=index.compte(), limite=args.top_k))
    finally:
        index.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
