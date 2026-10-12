# SPDX-License-Identifier: MIT
"""`E2` -- the DERIVED bound on the number of chats. The PURE part (`orchestration.py`); the edge
has its own test (`test_orchestration_run.py`, to be written in the same gesture as
`runtime/orchestration_run.py`).
"""

from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path

from mnemosyne.production.orchestration import (
    CAPACITE_ARBITRAGE_PAR_TOUR,
    borne_chats,
    largeur_vague_en_arcs,
)
from mnemosyne.production.plan_format import fold_plan
from mnemosyne.production.plan_registry import read_plan_tree

REPO = Path(__file__).resolve().parents[2]


def _lecture(texte: str):
    return fold_plan(texte, (), lambda _m: (None, "absent"), folder_form=False)


def _plan_a_N_arcs(n_libres: int, n_bloques: int) -> str:
    """``n_libres`` arcs of one free item each, ``n_bloques`` arcs of one blocked item each."""
    from string import ascii_uppercase

    texte = "# PLAN - fixture\n\n## The steps\n\n"
    corps = "  *Produit* : x\n  *Fini quand* : c\n  *Prérequis* : AUCUN\n"
    lettres = iter(ascii_uppercase)
    bloqueur = next(lettres)
    texte += f"- **{bloqueur}1** \U00002B1C **The blocker, never counted.**\n{corps}  *Dépend de* : AUCUNE\n"
    for _ in range(n_libres):
        lettre = next(lettres)
        texte += f"- **{lettre}1** \U00002B1C **Free.**\n{corps}  *Dépend de* : AUCUNE\n"
    for _ in range(n_bloques):
        lettre = next(lettres)
        texte += f"- **{lettre}1** \U00002B1C **Blocked.**\n{corps}  *Dépend de* : {bloqueur}1\n"
    return texte


def test_largeur_vague_en_arcs_compte_les_arcs_DEMARRABLES_pas_les_items():
    """Three free arcs (one item each) + two blocked arcs (one item each, same blocker) + the
    blocker itself (its own arc, free) -- the width counts ARCS, never items."""
    reading = _lecture(_plan_a_N_arcs(n_libres=3, n_bloques=2))
    # the blocker is itself a full-fledged arc, free -- 3 + 1 = 4
    assert largeur_vague_en_arcs(reading) == 4, (
        "3 free arcs + the blocker's arc (also free) = 4; the 2 blocked arcs do not count"
    )


def test_largeur_vague_en_arcs_est_ZERO_sur_un_plan_ENTIEREMENT_bloque_ou_fini():
    """No startable item -- the width is honestly 0, never an exception or an optimistic
    default."""
    texte = (
        "# PLAN - fixture\n\n## The steps\n\n"
        "- **A1** \U00002705 **Done.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
    )
    assert largeur_vague_en_arcs(_lecture(texte)) == 0, "a single item, already DONE: nothing to start"


def test_borne_chats_est_le_MINIMUM_des_deux_termes():
    """`E2`'s `*Fini quand*`, word for word: `min(wave width, arbitration capacity)`.
    Both edges of the `min` are tested separately -- the wave that dominates, then the capacity."""
    # NARROW wave (2 arcs) < capacity (3) -- the wave must win
    etroit = _lecture(_plan_a_N_arcs(n_libres=1, n_bloques=0))  # blocker + 1 free = 2 free arcs
    assert largeur_vague_en_arcs(etroit) == 2
    assert borne_chats(etroit) == 2, "the wave (2) is UNDER the capacity (3): it must win"

    # WIDE wave (6 arcs) > capacity (3) -- the capacity must win
    large = _lecture(_plan_a_N_arcs(n_libres=5, n_bloques=0))  # blocker + 5 free = 6 free arcs
    assert largeur_vague_en_arcs(large) == 6
    assert borne_chats(large) == CAPACITE_ARBITRAGE_PAR_TOUR == 3, (
        "the wave (6) exceeds the capacity (3): the capacity must cap it, never the wave"
    )


#: The commit REPLAYED by the test below -- not the LIVE plan. Chosen, not invented: it is the
#: closing commit of `C2` ("THE PLAN'S LAST BOTTLENECK FALLS"), that night's last plan bottleneck,
#: measured directly in an isolated checkout (`git worktree`) on 2026-08-16: `largeur=8`, far
#: above `CAPACITE_ARBITRAGE_PAR_TOUR=3`.
#:
#: TODO(public-mirror): needs human review - this hash is a commit of the PRIVATE repo's own git
#: history. This public mirror is a separate repository with its own, independent history (see
#: the sync contract: "already pushed public to github.com/Sami-Andaloussi/mnemosyne-system"), so
#: `git archive e8151ad -- docs` in `_plan_reel_au_commit` below will not resolve here, and
#: `test_borne_chats_REJOUE_sur_le_VRAI_plan_de_Mnemosyne_colle_a_l_usage_REEL` is expected to
#: fail against this export for that reason. Left unchanged rather than guessed at: only a human
#: can decide whether to pick an equivalent commit from the mirror's own history, or accept this
#: test as private-repo-only.
_COMMIT_VAGUE_LARGE = "e8151ad"


def _plan_reel_au_commit(commit: str, tmp_path: Path):
    """Reconstructs `docs/` EXACTLY AS IT WAS at `commit` -- never the live plan.

 **FIXED on 2026-08-16 (the orchestrator's own arbitration, verified before being followed)**:
 this test used to read from `REPO / "docs"`, the LIVE plan -- true when it was written, and even
 more true since (this repo's own plan closed out over the course of the night down to just 1
 startable arc, under `CAPACITE_ARBITRAGE_PAR_TOUR`, which empties the test of meaning BY ITS OWN
 docstring). A test drawn from PRODUCTION must never stop production from FINISHING -- it must
 read from a REAL, DATED state of the repo, never from its state today. `git archive`
 reconstructs the exact bytes of `docs/` at that commit, never a rewrite: the property being
 proved stays "the formula fits a real use", not "... fits today's use"."""
    archive = subprocess.run(  # noqa: S603, S607
        ["git", "archive", commit, "--", "docs"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    # `git archive` already carries the `docs/` prefix in every entry name -- extract straight
    # into `tmp_path` (not `tmp_path / "docs"`) or the result becomes `docs/docs/...`.
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(tmp_path, filter="data")  # noqa: S202 -- content of THIS repo, not external
    return tmp_path / "docs"


def test_borne_chats_REJOUE_sur_le_VRAI_plan_de_Mnemosyne_colle_a_l_usage_REEL(tmp_path: Path):
    """ Replayed against a REAL, DATED state of the repo (not a fixture, and no longer the live
 plan since 2026-08-16 -- see :func:`_plan_reel_au_commit`): that night ran at 3 chats
 (three concurrent chat-session logs from that night), and the formula must land on that same
 figure for `E2`'s `*Fini quand*` to be more than a formula that merely sounds right.

 **NAMED BY THE AUDIT (D75): this test does NOT bite if `borne_chats` is sabotaged to always
 return `CAPACITE_ARBITRAGE_PAR_TOUR`** -- over the real population (9 arcs), that sabotage still
 returns `3`, the right answer by coincidence. *This is not the test that guards that class*:
 `test_borne_chats_est_le_MINIMUM_des_deux_termes` (a NARROW synthetic population) guards it,
 and an isolated audit verified that by actually sabotaging the code. This one proves something
 else -- that the formula FITS real usage -- not that the mechanism reacts to every input."""
    dossier = _plan_reel_au_commit(_COMMIT_VAGUE_LARGE, tmp_path)
    plans = read_plan_tree(dossier, "Mnemosyne")
    reading = plans[0].reading
    assert reading is not None, "the real plan must be readable for this test to mean anything"

    largeur = largeur_vague_en_arcs(reading)
    assert largeur > CAPACITE_ARBITRAGE_PAR_TOUR, (
        f"measured {largeur} startable arc(s) at commit {_COMMIT_VAGUE_LARGE} -- if this number "
        "falls back UNDER the capacity, the bound stops demonstrating that it is the capacity that "
        "caps it, and this test becomes meaningless (pick a commit with a wider wave instead)"
    )
    assert borne_chats(reading) == CAPACITE_ARBITRAGE_PAR_TOUR == 3, (
        f"wave={largeur} arcs, capacity={CAPACITE_ARBITRAGE_PAR_TOUR} -- the bound must land "
        "on 3, this session's real chat count"
    )
