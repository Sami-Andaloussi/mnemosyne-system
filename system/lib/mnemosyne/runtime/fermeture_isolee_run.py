"""H5 (line 5) - the edge: reads THIS repo's plan and its git history, publishes the closures
that no second identity has ever touched.

Same split as the rest of the repo: `production/fermeture_isolee.py` stays pure, this module opens
the disk and shells out to `git` - via `commits_par_ident` (`routage_journal_run.py`), never a
second `git log`: *a single home, never recopied* (D163), the same lesson `commits_dates_par_ident`
already paid for once - no need to pay it again here.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..production.fermeture_isolee import fermetures_solitaires
from ..production.plan_registry import scan_plans
from .routage_journal_run import commits_par_ident


def resume(racine: Path) -> str:
    """The text for `make fermeture-isolee` - fail-open, LEVEL 1: this check never refuses,
    it publishes what it was able to measure (same discipline as `orphelins_run.resume`)."""
    dossier = racine / "docs"
    projet = next((p for p in scan_plans(racine).projects if p.plan_path.parent == dossier), None)
    if projet is None or projet.reading is None:
        return "\U000026A0\U0000FE0F isolated closures (H5) NOT MEASURED - this repo's plan is not readable.\n"

    commits = commits_par_ident(racine)
    if commits is None:
        return "\U000026A0\U0000FE0F isolated closures (H5) NOT MEASURED - the git history could not be read.\n"

    solitaires = fermetures_solitaires(projet.reading.items, commits)
    total_fermes = sum(1 for i in projet.reading.items if i.status in ("fait", "clos"))
    if not solitaires:
        return (
            f"isolated closures (H5, line 5): 0 out of {total_fermes} closed item(s) - "
            "each one carries at least a SECOND identity named in its history.\n"
        )

    lignes = [
        f"isolated closures (H5, line 5): {len(solitaires)} out of {total_fermes} closed item(s) "
        "- no SECOND identity named in their known history:",
        "",
    ]
    for s in solitaires:
        qui = s.modele if s.modele else "no identity (no known commit carries a trailer)"
        lignes.append(f"  {s.ident} - {qui}")
    lignes += [
        "",
        "\U000026A0\U0000FE0F This is a FLOOR, not proof that no audit happened (D75): the chats in this repo share",
        "one model, so a legitimate cross-chat audit can carry the SAME identity as the producer.",
        "Named, not refused - see the docstring of production/fermeture_isolee.py.",
    ]
    return "\n".join(lignes) + "\n"


def _racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    return Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]


def main() -> int:  # pragma: no cover - [OPERATOR] surface
    print(resume(_racine()), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
