"""E3 - what was written and that nobody committed, and the PARKED paths that are NEVER proposed.

 **The witness that matters is the one for parked paths**, and it CANNOT be exercised on a real
file: the only two parked paths visible to `git status` live under `system/config/`, one of
`CLAUDE.md`'s three walls - changing them to test the gate would mean crossing the wall the gate
protects. That is exactly why the judge is PURE and its population is injected: the `porcelain`
output is hand-built right here, without touching anything.
"""

from __future__ import annotations

from mnemosyne.production.non_committe import (
    AUTRES_CITES as PLAFOND_ATTENDU,
    PARQUES,
    Depot,
    attentes,
    est_parque,
    lire,
    rendre,
)

# A REAL `git status --porcelain` output, in its actual shape: two status columns, a space, the
# path. One tracked modified file, one untracked, one renamed, and the two parked paths TRACKED
# BY GIT.
PORCELAIN = """\
 M docs/example.md
?? docs/brouillon.md
R  docs/vieux.md -> docs/neuf.md
 M system/config/policy.toml
 M system/config/domains.toml
"""


def test_les_parques_ne_sont_JAMAIS_proposes():
    """The exact clause of E3's end-of-task condition: "a parked file is never proposed"."""
    (a,) = attentes([lire("this repo", PORCELAIN)])
    assert "system/config/policy.toml" not in a.a_committer
    assert "system/config/domains.toml" not in a.a_committer
    assert set(a.parques) == {"system/config/policy.toml", "system/config/domains.toml"}


def test_ce_qui_reste_est_NOMME_fichier_par_fichier():
    """"There are still things to commit" is the generic reminder that gets skipped; a name can
    be checked."""
    (a,) = attentes([lire("this repo", PORCELAIN)])
    assert a.a_committer == ("docs/example.md", "docs/brouillon.md", "docs/neuf.md")


def test_un_renommage_rend_le_NOUVEAU_chemin():
    """It is the only one that will exist after the commit - proposing the old one would be
    proposing a ghost."""
    assert lire("x", "R  a.md -> b.md\n").chemins == ("b.md",)


def test_la_classe_est_fermee_pas_le_cas():
    """A THIRD config file, added tomorrow, is parked without anyone having to think about it."""
    assert est_parque("system/config/a-file-that-does-not-exist-yet.toml")
    assert est_parque("scripts/perso/my-script.sh")
    assert not est_parque("system/lib/mnemosyne/production/obligation.py")


def test_la_classe_n_avale_PAS_les_voisins_SUIVIS_de_ce_qu_elle_parque():
    """ The symmetric defect, found by the isolated audit: a class too WIDE swallows innocents.

 `CLAUDE.md` parks `system/state/*.jsonl` - files that are **gitignored**, hence absent from
 any `git status`. The `system/state/` prefix therefore bought NOTHING, and cost it its
 tracked neighbours (`README.md`, `.gitkeep`): a file written there was not named at the end
 of the task, E3's clause 1 failing on a real class.
 """
    assert not est_parque("system/state/README.md")
    assert not est_parque("system/state/.gitkeep")


def test_un_depot_dont_TOUT_est_parque_DISPARAIT():
    """Announcing "2 parked" with nothing to do is noise - and noise teaches people to skip the
    block."""
    assert attentes([lire("this repo", " M system/config/policy.toml\n")]) == ()


def test_un_depot_propre_DISPARAIT_et_le_bloc_est_VIDE():
    """Silence is a result: a detector that always talks says nothing."""
    assert attentes([lire("this repo", "")]) == ()
    assert rendre(()) == ""


def test_le_bloc_NOMME_le_depot_ET_le_nombre_de_parques_ecartes():
    """What is set aside is SAID - a silent truncation reads as "I covered everything"."""
    rendu = rendre(attentes([lire("the memory (outside the repo)", PORCELAIN)]))
    assert "the memory (outside the repo)" in rendu
    assert "2 PARKED path(s) set aside" in rendu
    assert all(prefixe in rendu for prefixe in PARQUES)
    assert "policy.toml" not in rendu, (
        "a parked file is not proposed, not even in the set-aside list"
    )


def test_plusieurs_depots_sont_rendus_separement():
    """E3 says "across the three repos"; the set is DERIVED at the edge, never counted here."""
    rendu = rendre(
        attentes(
            [
                Depot("this repo", ("docs/example.md",)),
                Depot("the memory (outside the repo)", ("MEMORY.md",)),
                Depot("The Research Project", ("plan/03-captation/PLAN.md",)),
            ]
        )
    )
    assert rendu.count("\U000025B8") == 3


def test_la_liste_des_AUTRES_est_BORNEE_et_DIT_ce_qu_elle_laisse():
    """ Born from real use: a `ruff format` run across the whole repo left 125 modified files
 (identical AST on 125/125), and the block started rendering 127 lines at the end of every
 task, for all three chats. A wall of 127 names IS how you learn to ignore a block."""
    porcelain = "".join(f" M file{n:03d}.py\n" for n in range(40))
    rendu = rendre(attentes([lire("this repo", porcelain)]))
    # We count the PATHS listed, not the word "file" - it also lives in the block's prose, and
    # a first version of this witness counted 11 for 8 cited. *A probe that counts the wrong
    # thing accuses the code of a fault it does not have.*
    cites = [ligne for ligne in rendu.splitlines() if ligne.strip().startswith("file")]
    assert len(cites) == PLAFOND_ATTENDU, "8 paths cited, not one more"
    assert "…and 32 more" in rendu
    assert "git status --porcelain" in rendu, "the command that shows EVERYTHING is named"


def test_ce_que_LA_TACHE_a_ecrit_n_est_JAMAIS_borne():
    """The counterpart, and it's the one that matters: what the task wrote is what gets LOST."""
    porcelain = "".join(f" M mine{n:03d}.py\n" for n in range(40))
    rendu = rendre(attentes([lire("this repo", porcelain)], [f"mine{n:03d}.py" for n in range(40)]))
    assert rendu.count("mine") == 40, "no truncation on the task's own work"
    assert "more —" not in rendu


def test_une_ligne_porcelain_tronquee_ne_LEVE_pas():
    """A `git` that stutters must not silence the whole reminder - it loses one line, not
    everything."""
    assert lire("x", "M\n M docs/example.md\n").chemins == ("docs/example.md",)
