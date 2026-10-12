"""THE LESSONS INDEX GETS JUDGED (project 0  -  A1) - the PULL path that doubles the PUSH channel.

WHY THIS FILE EXISTS. The memory surface must remain bounded and independently tested.
This module opens the pull path; these witnesses verify that it remains truthful and never writes
the operator's local memory.

THE FIRST WITNESS IS THE INNOCENT: without it, an index that would NEVER find anything
would pass every witness for abstention - *a gate already red discriminates against no one*.

AND THE MOST IMPORTANT WITNESS IS `test_le_dossier_de_memoire_n_est_JAMAIS_ecrit`. Erasing or
rewriting a local memory is a human gesture (D74, inv. 2). A regression that made this module write
must turn red, not read fine.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from mnemosyne.production.lecons import IndexDesLecons, lire_titre


def _fiche(dossier: Path, nom: str, description: str, corps: str) -> Path:
    chemin = dossier / nom
    chemin.write_text(
        f"---\nname: {nom.removesuffix('.md')}\ndescription: {description}\n"
        f"metadata:\n  type: feedback\n---\n\n{corps}\n",
        encoding="utf-8",
    )
    return chemin


def _memoire(tmp_path: Path) -> Path:
    dossier = tmp_path / "memory"
    dossier.mkdir(parents=True, exist_ok=True)
    _fiche(
        dossier,
        "a-floor-never-a-ceiling.md",
        "A FLOOR, never a CEILING",
        "A ceiling on a generated output does not bound it, it steers the generation.",
    )
    _fiche(
        dossier,
        "prove-the-test-bites.md",
        "Sabotage a green test on the first try",
        "A mechanism that never bites proves nothing at all.",
    )
    _fiche(
        dossier,
        "tidy-the-repo.md",
        "Tidying is a permanent principle",
        "An unreadable repo costs more than an incomplete repo.",
    )
    # The TWO indexes live in the same folder and are NOT fiches.
    (dossier / "MEMORY.md").write_text(
        "# Memory Index\n- [A floor](a-floor-never-a-ceiling.md) - ceiling generated\n",
        encoding="utf-8",
    )
    (dossier / "MEMORY-2.md").write_text(
        "- [Prove](prove-the-test-bites.md) - sabotage ceiling\n", encoding="utf-8"
    )
    return dossier


def _index(tmp_path: Path) -> IndexDesLecons:
    """Always a database OUTSIDE the memory folder - that is also what the real default does."""
    index = IndexDesLecons(_memoire(tmp_path), db_path=tmp_path / "lecons.db")
    index.refresh()
    return index


def test_une_question_TROUVE_sa_fiche(tmp_path: Path) -> None:
    """THE INNOCENT, first: the passing path must pass, or nothing measured afterward means anything."""
    index = _index(tmp_path)
    rappel = index.search("ceiling generated output")
    assert rappel.mode == "and", rappel
    assert [t.nom for t in rappel.trouvailles] == ["a-floor-never-a-ceiling.md"]
    assert rappel.trouvailles[0].titre == "A FLOOR, never a CEILING"
    index.close()


def test_les_DEUX_index_ne_sont_pas_des_fiches(tmp_path: Path) -> None:
    """`MEMORY.md` and `MEMORY-2.md` POINT AT the fiches - indexing them would match the PUSH
    artifact first, which is exactly what the PULL path exists to work around.

    NOTE: `MEMORY.md`/`MEMORY-2.md` are not decorative test
    strings here: they must match `INDEX_FILENAMES` in the (out-of-scope) production module
    `system/lib/mnemosyne/production/lecons.py`. Renaming them in this file alone would silently
    break this test against the real, unrenamed constant, so they are left untouched (checked
    against the whole mirror, not only this lot)."""
    index = _index(tmp_path)
    assert index.compte() == 3, "3 fiches, not 5 - the two indexes are excluded"
    noms = {t.nom for t in index.search("ceiling", limit=10).trouvailles}
    assert "MEMORY.md" not in noms and "MEMORY-2.md" not in noms
    index.close()


def test_le_dossier_de_memoire_n_est_JAMAIS_ecrit(tmp_path: Path) -> None:
    """THE CARDINAL WITNESS. This module READS the operator's memory; it does not write it, does
    not merge it, does not delete it (D74, inv. 2). We freeze the fingerprint of EACH file and the
    LIST of names - identical content with one file more or fewer would pass a simple count."""
    dossier = _memoire(tmp_path)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dossier.iterdir())}
    index = IndexDesLecons(dossier, db_path=tmp_path / "lecons.db")
    index.refresh()
    index.search("ceiling sabotage repo", limit=10)
    index.refresh()
    index.close()
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dossier.iterdir())}
    assert after == before, (
        "the memory folder has CHANGED - content, or one file more/fewer"
    )


def test_une_question_SANS_MOT_CHERCHABLE_s_abstient_et_le_DIT(tmp_path: Path) -> None:
    """"I couldn't search" and "there is nothing" are two different answers (inv. 14).
    Conflating them makes a silence indistinguishable from a real emptiness."""
    index = _index(tmp_path)
    rappel = index.search("the of to in is")
    assert rappel.mode == "none" and rappel.trouvailles == () and rappel.termes == ()
    index.close()


def test_un_VRAI_rien_se_distingue_de_l_abstention(tmp_path: Path) -> None:
    """The corpus WAS queried and carries nothing: `mode='and'`, but with TERMS retained."""
    index = _index(tmp_path)
    rappel = index.search("xyzzy quuxfrobnicator")
    assert rappel.trouvailles == ()
    assert rappel.mode == "and", "a real nothing is not an abstention"
    assert rappel.termes, (
        "the searched terms must come back, otherwise there is no way to tell the operator"
    )
    index.close()


def test_le_repli_OR_ne_s_active_QU_APRES_l_echec_du_strict(tmp_path: Path) -> None:
    """A loose fallback playing FIRST would bury an exact match under approximations."""
    index = _index(tmp_path)
    strict = index.search("ceiling generated")
    assert strict.mode == "and"
    # `ceiling` lives in one fiche, `sabotage` in ANOTHER, and never in the same one: a working
    # fallback must therefore bring back TWO. This witness's first version used a word that NO
    # fiche carried - the fallback returned only 1 result and the assertion wrongly
    # blamed the code, when the bug was in the witness itself.
    lache = index.search("ceiling sabotage", limit=10)
    assert lache.mode == "or", "these two words do not coexist in any fiche"
    assert {t.nom for t in lache.trouvailles} == {
        "a-floor-never-a-ceiling.md",
        "prove-the-test-bites.md",
    }, "the fallback must bring back BOTH fiches, one per word"
    index.close()


def test_une_limite_NEGATIVE_ne_deverse_pas_le_corpus(tmp_path: Path) -> None:
    """WARNING: reachable from the command line (`TOPK=-1`). In SQL, a negative limit means
    "no limit" and returns EVERYTHING - the exact opposite of the bounded-read promise (inv. 16)."""
    index = _index(tmp_path)
    assert index.search("ceiling", limit=-1).trouvailles == ()
    index.close()


def test_le_refresh_est_INCREMENTAL_et_DIT_ce_qu_il_a_fait(tmp_path: Path) -> None:
    """A silent refresh that indexed nothing is indistinguishable from a refresh that indexed
    everything - and that is how an EMPTY index passes for a library."""
    dossier = _memoire(tmp_path)
    index = IndexDesLecons(dossier, db_path=tmp_path / "lecons.db")
    premier = index.refresh()
    assert premier == {"ajoutees": 3, "majes": 0, "retirees": 0, "inchangees": 0}
    assert index.refresh()["inchangees"] == 3, "nothing has moved on disk"

    _fiche(
        dossier,
        "tidy-the-repo.md",
        "Tidying is a permanent principle",
        "An unreadable repo costs more, and the new word is cryptocurrency.",
    )
    troisieme = index.refresh()
    assert troisieme["majes"] == 1 and troisieme["inchangees"] == 2
    assert [t.nom for t in index.search("cryptocurrency").trouvailles] == ["tidy-the-repo.md"]
    index.close()


def test_une_fiche_DISPARUE_sort_de_l_index(tmp_path: Path) -> None:
    """It is not deleted HERE - it has already left the disk. Keeping its row would make the
    index return a file nobody can open: *an unreadable result is worse than none*."""
    dossier = _memoire(tmp_path)
    index = IndexDesLecons(dossier, db_path=tmp_path / "lecons.db")
    index.refresh()
    (dossier / "tidy-the-repo.md").unlink()
    assert index.refresh()["retirees"] == 1
    assert index.compte() == 2
    assert index.search("unreadable").trouvailles == ()
    index.close()


def test_une_description_ABSENTE_reste_vide_et_n_est_jamais_INVENTEE(tmp_path: Path) -> None:
    """A fabricated description here would read exactly like one the operator wrote."""
    assert lire_titre("no frontmatter at all") == ""
    assert lire_titre("---\nname: x\n---\n\nbody\n") == ""
    assert (
        lire_titre('---\ndescription: "with quotes"\n---\n\nbody\n')
        == "with quotes"
    )


def test_une_borne_a_ZERO_ne_se_lit_PAS_comme_un_corpus_muet(tmp_path: Path) -> None:
    """FOUND BY PULLING ON THE SURFACE, NOT BY RE-READING IT. `make lecons TOPK=-1` was
    rendering 'this is a true "nothing", not a closed door' on a corpus that carries the answer:
    the read bound (inv. 16) had returned zero BEFORE any search ran. *A refusal that names the
    wrong cause closes the question instead of reopening it* - and this one was telling the
    operator their memory is empty."""
    from mnemosyne.runtime.lecons_run import rendre

    index = _index(tmp_path)
    empty = index.search("ceiling", limit=0)
    texte = rendre(empty, "ceiling", compte=index.compte(), limite=0)
    # WARNING: we are targeting the WHOLE AFFIRMATION, not the fragment `real "nothing"`: the
    # correct message ALSO contains it, in its NEGATION ("this is NEITHER ... NOR a real
    # "nothing""). This witness's first version used a `not in` on the fragment, which turned
    # red on the CORRECT message.
    # *A text detector counts citations as instances.*
    AFFIRMATION = 'this is a true "nothing", not a closed door'
    assert "was never consulted" in texte
    assert AFFIRMATION not in texte, "the bound must NEVER read like a silent corpus"

    # And a real nothing still reads as a real nothing - otherwise we've just moved the lie.
    reel = index.search("xyzzy", limit=6)
    assert AFFIRMATION in rendre(reel, "xyzzy", compte=index.compte(), limite=6)
    index.close()


def test_un_dossier_ABSENT_ne_leve_pas_et_ne_ment_pas(tmp_path: Path) -> None:
    """A path that does not resolve must return ZERO fiches - and the count SAYS so. Concluding
    "the memory is empty" from a wrong path is the mistake `make search`'s refusal paid for."""
    index = IndexDesLecons(tmp_path / "nowhere", db_path=tmp_path / "lecons.db")
    assert index.fiches() == []
    assert index.refresh() == {"ajoutees": 0, "majes": 0, "retirees": 0, "inchangees": 0}
    assert index.compte() == 0
    index.close()
