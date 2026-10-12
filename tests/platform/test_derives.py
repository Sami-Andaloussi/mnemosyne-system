"""THE BARRIER AGAINST A HAND-MAINTAINED DERIVATIVE (phase 2 · C4, then phase 3 · D1).

It judges a single population — the documents DECLARED in `DERIVES`, which speak in the source
document's name — and two classes of defect that share the same shape: **a derivative written by
hand ends up lying over time**. The range of the decision corpus (C4), and since D174 the
proclaimed EXECUTOR DEFAULT: neither `local-first`, nor `frontier-first` — the second would have
perished like the first.

Two families here, and the second matters as much as the first.

1. The judge over FABRICATED texts — it bites, it spares, it refuses silence.
2. **The regression against the REAL repository**: the declared derivatives, read from disk. This
 is the only witness that keeps the defect from coming back, and it is also the one that
 measures FALSE accusations: sub-decision labels (`D48-1`, `D54-2`, `D60-1`, ...) have the SHAPE
 of a range and are not one, and a looser pattern mistakes them for ranges. A capture rate
 without its false-accusation rate is a wall, not a gate.

 WHAT DOES NOT HOLD IN THIS DISTRIBUTION, AND IT MUST BE SAID: the false-accusation control of
family 2 needs a real population that actually CARRIES those sub-decision labels. Measured on the
documents this repository ships: **0 of the 7 labels in `INNOCENTS` occur in any declared
derivative**, so `test_les_INNOCENTS_du_depot_REEL_sont_bien_LA_...` is RED here by construction —
the discrimination it is meant to prove is untestable on this corpus. It is left RED and
explaining rather than deleted, weakened, or pointed at a file that does not exist.

What these tests do NOT cover, and that must be written down: the count of **27 invariants**,
copied into about twenty files. It is true today, and re-checking it is item D3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production import derives
from mnemosyne.production.derives import (
    COMPTE,
    DEFAUT,
    DERIVES,
    PLAGE,
    POIDS_GELE_CLAUDE_MD,
    PORTES_QUI_DECLARENT,
    SOURCE,
    ecart_adoption,
    message,
    message_adoption,
    message_ecart,
    poids_doctrine,
    verdict,
    verdict_adoption,
)

REPO = Path(__file__).resolve().parents[2]

#: The SUB-decision labels really present in the judged documents. They have the SHAPE of a range
#: and are not one — the permanent control against the too-loose pattern.
INNOCENTS = ("D48-1", "D54-2", "D60-1", "D60-2", "D119-a", "D121-A1", "invariants 6-8")


def _propre() -> dict[str, str]:
    return {nom: f"# {nom}\n\nnothing to see here, this file POINTS to `{SOURCE}`.\n" for nom in DERIVES}


# Throughout this file, fixture keys are literal document names paired 1:1 with the real
# `DERIVES`/`SOURCE` constants of `derives.py`: `verdict()` looks each of them up BY that exact
# name, and `_propre()` builds its dictionary FROM `DERIVES`. A key that is no longer in `DERIVES`
# is therefore never found at all -- the fixture line raises `KeyError`, which pytest reports as an
# ERROR and NOT as a failure (`-rf` does not even print it; `-rfE` does). So the two literal sets
# move TOGETHER, in the same commit, or the freeze below lies.


# ---------------------------------------------------------------- the judge, over fabricated text


def test_le_cas_PASSANT_un_derive_qui_POINTE_ne_declenche_rien() -> None:
    v = verdict(_propre())
    assert not v.refuse
    assert v.recopies == ()
    assert v.juges == DERIVES
    assert "none copies" in message(v)


def test_une_PLAGE_recopiee_est_nommee_avec_sa_LIGNE() -> None:
    textes = _propre()
    textes["README.md"] = "line one\nthe corpus D1→D124 is authoritative\n"
    v = verdict(textes)
    assert v.refuse
    assert len(v.recopies) == 1
    (r,) = v.recopies
    assert (r.document, r.ligne, r.texte, r.forme) == ("README.md", 2, "D1→D124", PLAGE)


def test_les_QUATRE_ecritures_de_plage_du_depot_sont_toutes_prises() -> None:
    """`→`, `->`, the French `à`, and the hyphen — the forms actually found in the corpus."""
    for ecriture in ("D1→D124", "D1->D124", "D1 à D143", "D113-D143"):
        textes = _propre()
        textes["docs/FORMAT_PLAN.md"] = f"corpus {ecriture} there we go\n"
        v = verdict(textes)
        assert v.refuse, f"{ecriture} was not caught"
        assert v.recopies[0].texte.strip() == ecriture


def test_un_COMPTE_de_decisions_est_la_MEME_dette_ecrite_autrement() -> None:
    textes = _propre()
    textes["README.md"] = "the corpus's 143 decisions\n"
    v = verdict(textes)
    assert v.refuse
    assert v.recopies[0].forme == COMPTE


def test_un_DEFAUT_D_EXECUTANT_proclame_est_refuse_dans_les_DEUX_sens() -> None:
    """D174: neither `local-first` nor `frontier-first`. Replacing one with the other is the
    DEFECT D149 COMMITTED — a proclaimed default perishes with the market."""
    for proclamation in (
        "a local-first system",
        "Mnemosyne is frontier-first",
        "assumed frontière-first posture",
        "we stay cloud first",
    ):
        textes = _propre()
        textes["docs/FORMAT_PLAN.md"] = f"{proclamation}\n"
        v = verdict(textes)
        assert v.refuse, f"« {proclamation} » was not refused"
        assert v.recopies[0].forme == DEFAUT
        assert "AGNOSTIC" in message(v) and "without replacing it" in message(v)


def test_le_refus_du_defaut_JURE_qu_il_ne_touche_aucune_barriere_de_DONNEES() -> None:
    """ The only way to turn D174 into a regression would be to read "remove local-first" as
 "remove sensible-local." The message says so, and this witness demands it."""
    textes = _propre()
    textes["README.md"] = "local-first\n"
    dit = message(verdict(textes))
    assert "sensible" in dit and "inv. 1" in dit and "intimate families" in dit


def test_l_INNOCENT_du_defaut_le_mot_local_SEUL_n_est_pas_une_proclamation() -> None:
    """`sensible` stays local, one surface is `stays_local`, a local model absorbs the volume —
    the word is only at fault in the shape `<word>-first`. Otherwise the gate would accuse
    invariant 1 itself."""
    textes = _propre()
    textes["README.md"] = (
        "`sensible` data never leaves local by an automated process\n"
        "`[read_only · stays_local]` · the local model absorbs the volume · first class\n"
    )
    assert not verdict(textes).refuse


def test_les_ETIQUETTES_de_sous_decision_ne_sont_JAMAIS_accusees() -> None:
    """The false accusation a too-loose pattern used to commit — frozen as a witness."""
    textes = _propre()
    textes["README.md"] = "\n".join(INNOCENTS) + "\n"
    v = verdict(textes)
    assert not v.refuse, f"innocents accused: {v.recopies}"


def test_la_SOURCE_n_est_pas_jugee_elle_ne_derive_de_RIEN() -> None:
    assert SOURCE not in DERIVES
    textes = _propre() | {SOURCE: "historical block settled D1→D97, and that is LEGITIMATE here\n"}
    assert not verdict(textes).refuse


def test_un_derive_INTROUVABLE_fait_ROUGIR_il_ne_sort_pas_du_jugement() -> None:
    """A rename must not turn a barrier into silence."""
    textes = _propre()
    del textes["docs/FORMAT_PLAN.md"]
    v = verdict(textes)
    assert v.refuse
    assert v.absents == ("docs/FORMAT_PLAN.md",)
    assert v.recopies == ()
    assert "NOT FOUND" in message(v) and "derives.py" in message(v)


def test_TOUS_les_derives_absents_REFUSE_ce_n_est_pas_un_depot_sain() -> None:
    v = verdict({})
    assert v.refuse
    assert v.juges == ()
    assert set(v.absents) == set(DERIVES)


def test_une_population_VIDE_REFUSE_au_lieu_de_rendre_un_vert_qui_ne_mesure_RIEN(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ THIS WITNESS HAD TO BE REWRITTEN: `verdict({})` did NOT reach it.

 It already refused through the `absents` clause — the `not self.juges` clause was therefore
 unreachable, and sabotaging it made nothing turn red. The only path that arms it is an EMPTIED
 `DERIVES`: nothing is declared any more, nothing is absent, nothing is judged. Without this
 clause, that repository would return a green that measures nothing.
 """
    monkeypatch.setattr(derives, "DERIVES", ())
    v = verdict({})
    assert v.juges == () and v.absents == () and v.recopies == ()
    assert v.refuse
    assert "EMPTY POPULATION" in message(v)


def test_le_refus_NOMME_la_sortie() -> None:
    textes = _propre()
    textes["docs/FORMAT_PLAN.md"] = "corpus D1→D124\n"
    dit = message(verdict(textes))
    assert "REMOVE the bound" in dit
    assert SOURCE in dit
    assert "cite it elsewhere" in dit


def test_TOUTES_les_recopies_sont_rendues_pas_seulement_la_PREMIERE() -> None:
    textes = _propre()
    textes["README.md"] = "D1→D124\n\nD1→D153\n"
    textes["docs/FORMAT_PLAN.md"] = "the 143 decisions\n"
    v = verdict(textes)
    assert len(v.recopies) == 3
    assert {r.document for r in v.recopies} == {"README.md", "docs/FORMAT_PLAN.md"}


# ------------------------------------------------- the regression against the REAL repository
# The witnesses below read the DECLARED derivatives straight off `REPO`, so they regression-test
# this repository's actual state rather than a fixture shaped to fit. Their population is derived
# from `DERIVES` and never copied by hand -- except the frozen SET just above, which is copied ON
# PURPOSE (a set that follows the mutation cannot denounce it).
# `tests/conftest.py` currently exempts four of them by NODE ID while the governance corpus is
# absent from this distribution; renaming any of them here silently lifts that exemption.


def test_l_ENSEMBLE_des_derives_est_GELE_pas_seulement_son_compte() -> None:
    """Removing a document from `DERIVES` takes it out of judgment without any green moving.

    The other witnesses compare `v.juges` to `DERIVES` — so they follow the mutation instead of
    denouncing it. Only a SET written out here makes it visible. Widening it is a deliberate
    gesture: you edit this line, and you know why.
    """
    assert set(DERIVES) == {
        "README.md",
        "docs/FORMAT_PLAN.md",
    }


def test_les_CINQ_derives_declares_EXISTENT_vraiment() -> None:
    """Freeze the SET, never the count: a name that no longer resolves must turn red HERE.

 The `CINQ` in this function's name is a leftover from a five-document population and is NOT
 a count this test checks — it checks the SET, whatever its size. The name is kept because
 `tests/conftest.py` exempts this witness BY NODE ID; renaming it here would silently change
 another file's behaviour from this one.
 """
    manquants = [nom for nom in DERIVES if not (REPO / nom).is_file()]
    assert not manquants, f"declared in DERIVES but absent from the repository: {manquants}"
    assert (REPO / SOURCE).is_file()


def test_AUCUN_derive_du_depot_REEL_ne_recopie_l_etendue_du_corpus() -> None:
    v = verdict({nom: (REPO / nom).read_text(encoding="utf-8") for nom in DERIVES})
    assert not v.refuse, message(v)
    assert v.juges == DERIVES


def test_la_barriere_MORD_sur_le_depot_REEL_quand_on_y_remet_la_faute() -> None:
    """Without this witness, the green above could come from a judge that reads nothing.

 The fault is put back into the REAL bytes, and the injection is ASSERTED before the barrier
 is asked anything. The previous version anchored on a phrase (`str.replace(..., 1)`): an anchor
 that has since moved returns the text UNCHANGED, in silence, and the witness then measures its
 own no-op instead of the judge. The victim is DERIVED from `DERIVES`, never copied by hand.
 """
    victime = DERIVES[0]
    textes = {nom: (REPO / nom).read_text(encoding="utf-8") for nom in DERIVES}
    sain = textes[victime]
    textes[victime] = sain + "\nthe decision corpus D1→D124 is authoritative\n"
    assert textes[victime] != sain, f"nothing was injected into {victime}: this measures nothing"

    v = verdict(textes)
    assert v.refuse
    assert [r.document for r in v.recopies] == [victime]


def test_les_INNOCENTS_du_depot_REEL_sont_bien_LA_sinon_le_vert_ne_prouve_rien() -> None:
    """The anti-false-accusation control only means something if the population still holds it.

 RED IN THIS DISTRIBUTION, AND DELIBERATELY LEFT RED. Measured on the documents this
 repository ships: **0 of the 7 labels occur in any declared derivative**. The floor of 4 is NOT
 lowered and the witness is NOT skipped, because both would turn a real gap into a green: the
 fabricated-text control (`test_les_ETIQUETTES_de_sous_decision_ne_sont_JAMAIS_accusees`) still
 proves the judge DISCRIMINATES, but nothing here proves the REAL corpus still exercises it.
 It reads the judged population (`DERIVES`) rather than a file that does not exist, so it fails
 with a message that names the gap instead of an opaque `FileNotFoundError`.
 """
    corpus = {nom: (REPO / nom).read_text(encoding="utf-8") for nom in DERIVES}
    presents = sorted({e for e in INNOCENTS for texte in corpus.values() if e in texte})
    assert len(presents) >= 4, (
        f"only {presents} across the declared derivatives {list(DERIVES)} — below this floor, "
        "'0 false accusations' no longer measures a discrimination"
    )


# ------------------------------------------- THE RATCHET ON `CLAUDE.md`'S WEIGHT (phase 3 · D4)


def test_le_cliquet_du_poids_REFUSE_DANS_LES_DEUX_SENS() -> None:
    """A ratchet that only bites upward loosens with every unbanked gain."""
    assert poids_doctrine(POIDS_GELE_CLAUDE_MD) == ""
    trop = poids_doctrine(POIDS_GELE_CLAUDE_MD + 1)
    assert "REMOVE" in trop and "MOVE" in trop and "SAME\nCOMMIT" in trop.replace(" ", "\n")
    mou = poids_doctrine(POIDS_GELE_CLAUDE_MD - 1)
    assert "slack" in mou and "lower" in mou


def test_le_refus_du_poids_NOMME_l_ecart_pas_seulement_le_fait() -> None:
    """"too big" without the number leaves the reader guessing what to cut."""
    assert "+500 B" in poids_doctrine(1_500, gel=1_000)
    assert "300 B of slack" in poids_doctrine(700, gel=1_000)


def test_CLAUDE_md_du_depot_REEL_tient_son_gel() -> None:
    octets = (REPO / "CLAUDE.md").stat().st_size
    assert poids_doctrine(octets) == "", poids_doctrine(octets)


def test_le_gel_du_poids_est_bien_CELUI_du_fichier_pas_un_nombre_decoratif() -> None:
    """ A freeze that corresponds to nothing real would pass green while measuring nothing.

 Same defect as a count with no command behind it: the number must BE the measurement.
 """
    assert (REPO / "CLAUDE.md").stat().st_size == POIDS_GELE_CLAUDE_MD


# ------------------------- THE FREEZE OVER THE SET OF DECLARING GATES (the first adopter's pattern, D163)


def test_une_porte_gelee_qui_declare_encore_TIENT() -> None:
    v = verdict_adoption(courant={"epreuve/plan/PLAN.md": "produced"}, geles=("epreuve/plan/PLAN.md",))
    assert v.refuse is False
    assert v.tenues == ("epreuve/plan/PLAN.md",)
    assert v.effacees == ()


def test_VINGT_CARACTERES_EFFACES_ANNULENT_L_ADOPTION__LE_GEL_LE_REFUSE() -> None:
    """The scene measured by the auditor, reproduced literally: `**Format**: produced` (20
    characters) disappears, same items, and the freeze must refuse instead of turning green again."""
    porte = "epreuve/plan/PLAN.md"
    avant = verdict_adoption(courant={porte: "produced"}, geles=(porte,))
    assert avant.refuse is False

    apres = verdict_adoption(courant={porte: ""}, geles=(porte,))
    assert apres.refuse is True
    assert apres.effacees == (derives.Effacee(porte=porte),)


def test_une_porte_gelee_ABSENTE_du_courant_compte_comme_EFFACEE() -> None:
    """Same rule as `absents` for `DERIVES`: a rename does not remove a gate from judgment in
    silence."""
    v = verdict_adoption(courant={}, geles=("epreuve/plan/PLAN.md",))
    assert v.refuse is True
    assert v.effacees == (derives.Effacee(porte="epreuve/plan/PLAN.md"),)


def test_le_gel_JUGE_L_ENSEMBLE_une_porte_saine_n_epargne_pas_une_porte_effacee() -> None:
    v = verdict_adoption(
        courant={"a/PLAN.md": "produced", "b/PLAN.md": ""},
        geles=("a/PLAN.md", "b/PLAN.md"),
    )
    assert v.tenues == ("a/PLAN.md",)
    assert v.effacees == (derives.Effacee(porte="b/PLAN.md"),)
    assert v.refuse is True


def test_le_message_d_adoption_NOMME_la_porte_effacee() -> None:
    v = verdict_adoption(courant={}, geles=("epreuve/plan/PLAN.md",))
    msg = message_adoption(v)
    assert "epreuve/plan/PLAN.md" in msg
    assert "PORTES_QUI_DECLARENT" in msg


def test_le_message_d_adoption_est_VIDE_quand_rien_ne_refuse() -> None:
    v = verdict_adoption(courant={"a/PLAN.md": "produced"}, geles=("a/PLAN.md",))
    assert message_adoption(v) != ""
    assert "all of them still declare" in message_adoption(v)


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/saas/example-project").is_dir(),
    reason="projects/ is gitignored by design",
)
def test_PORTES_QUI_DECLARENT_est_bien_L_ENSEMBLE_mesure_pas_seulement_son_compte() -> None:
    """ A count (`len == 14`) would let a silent swap through (one gate leaving, another
 entering) — the same defect as `freeze-the-set-not-the-count` elsewhere in this repository.
 We compare the SET.

 **2026-08-17, FIXED AFTER A FINAL AUDIT**: the first version copied the 14 paths BY HAND —
 a literal list doubling another literal list, the copy D163 forbids. It used to bite on EVERY
 new adopter (a 15th project, outside the first adopter, joining the freeze should NOT touch
 this list — but growing `PORTES_QUI_DECLARENT` to register it broke this witness anyway,
 demanding a SECOND hand edit on top of the first).
 The reference is now DERIVED — from a source INDEPENDENT of `PORTES_QUI_DECLARENT` (so not
 tautological) but which no longer copies anything by hand: the first adopter's REAL gates,
 read from disk. **Only that adopter's PART of the freeze is compared** (never the whole
 tuple): a new adopter outside it grows `PORTES_QUI_DECLARENT` without touching this witness —
 only a REAL change in the first adopter's gates should move it.
 """
    from mnemosyne.production.plan_registry import read_plan_tree

    prefixe = "projects/saas/example-project/"
    reel = {
        p.plan_path.relative_to(REPO).as_posix()
        for p in read_plan_tree(REPO / "projects/saas/example-project", "example-project")
        if p.reading is not None and p.reading.format_declare.strip()
    }
    gele = {porte for porte in PORTES_QUI_DECLARENT if porte.startswith(prefixe)}
    assert gele == reel, (
        "the first adopter's PART of the freeze must match its real gates EXACTLY -- a new "
        "adopter outside it must never make this witness turn red"
    )
    assert len(PORTES_QUI_DECLARENT) == len(set(PORTES_QUI_DECLARENT)), "no duplicate in the freeze"


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/saas/example-project").is_dir(),
    reason="projects/ is gitignored by design",
)
def test_le_gel_LIT_LE_DISQUE_et_TIENT_sur_les_14_portes_REELLES_du_PREMIER_ADOPTANT_AUJOURD_HUI() -> None:
    """The REAL caller of this freeze, today: this test, on every `pytest` run — not a frozen text.

    LEVEL 1 measured before arming it (chat 3's precedent on the gate, 168 items/0 refusals): the
    14 gates ALWAYS declare, so this witness refuses nothing for now — that is expected, not a
    defect. The day one of them loses its declaration, THIS test turns red and names it.
    """
    from mnemosyne.production.plan_format import read_plan

    courant: dict[str, str] = {}
    for porte in PORTES_QUI_DECLARENT:
        chemin = REPO / porte
        assert chemin.is_file(), f"frozen gate not found on disk: {porte}"
        texte = chemin.read_text(encoding="utf-8", errors="replace")
        courant[porte] = read_plan(texte, origin=porte).format_declare

    v = verdict_adoption(courant=courant)
    assert v.refuse is False, message_adoption(v)
    assert set(v.tenues) == set(PORTES_QUI_DECLARENT)


# ------------------------------- THE ADOPTION GAP: who declares but is NOT frozen (option c)


def test_ecart_adoption_est_VIDE_quand_toute_porte_declarante_est_gelee() -> None:
    ecart = ecart_adoption(declare={"a/PLAN.md": "produced"}, geles=("a/PLAN.md",))
    assert ecart == ()
    assert message_ecart(ecart) == "0 gates declare outside the freeze: nothing to register."


def test_ecart_adoption_NOMME_une_porte_qui_declare_HORS_du_gel() -> None:
    ecart = ecart_adoption(
        declare={"a/PLAN.md": "produced", "b/PLAN.md": "produced"}, geles=("a/PLAN.md",)
    )
    assert ecart == ("b/PLAN.md",)
    msg = message_ecart(ecart)
    assert "b/PLAN.md" in msg
    # CONTRACT CHANGED ON 2026-08-18, AND THIS WITNESS CAUGHT IT (it used to require
    # `PORTES_QUI_DECLARENT`, the CONSTANT's name). The message named a file to EDIT BY HAND; it
    # now names a COMMAND. *This is not a weakening: naming the gesture a reader can actually pose
    # is strictly stronger than naming the symbol they would have had to go edit.*
    # The second adopter had read the old version and answered "I report, I do not repair" -- they
    # were right, and it was the symptom of a message addressed to the wrong reader.
    assert "make gel-inscrire PORTE=b/PLAN.md APPLY=1" in msg


def test_ecart_adoption_IGNORE_une_porte_qui_ne_declare_rien() -> None:
    """A non-declaring gate is not an "oversight" -- D176: no adoption, no obligation."""
    ecart = ecart_adoption(declare={"a/PLAN.md": "", "b/PLAN.md": "   "}, geles=())
    assert ecart == ()


def test_ecart_adoption_est_TRIE_deux_tours_nomment_dans_le_meme_ordre() -> None:
    ecart = ecart_adoption(declare={"z/PLAN.md": "produced", "a/PLAN.md": "produced"}, geles=())
    assert ecart == ("a/PLAN.md", "z/PLAN.md")


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects").is_dir(),
    reason="projects/ is gitignored by design",
)
def test_ecart_adoption_le_DEPOT_REEL_n_a_AUCUNE_porte_declarante_hors_du_gel_AUJOURD_HUI() -> (
    None
):
    """The REAL caller of the gap, today: this test, on every `pytest` run.

 LEVEL 1 measured before choosing between (a)/(b)/(c) (ticket, round 18:3x): as of 2026-08-17,
 the first adopter is the ONLY project declaring anywhere under `projects/` — measured by this very test,
 not assumed. If a second project adopts one day and this test turns red, that is PROOF the gap
 works: it names the new adopter, and that is the signal that triggers the registration gesture
 (b).

 **2026-08-17, FOUND BY A FINAL AUDIT — THIS DELIBERATE RED DID NOT CARRY ITS OWN REMEDY.**
 `make plan-nouveau ... FORMAT="produced" APPLY=1` on a new project makes THIS test turn red —
 intentionally. But the operator cannot edit Python, and the session that knows what to do gets
 archived. Decision made (ticket, option (a), recommended): **keep the bite, remove the wall**
 — the failure message (`message_ecart`) ALREADY names the gate and the file to edit
 (`PORTES_QUI_DECLARENT`, `derives.py`), so NO further edit is needed HERE beyond reading it.
 **The second edit an adopter used to require — the literal list copied into
 `test_PORTES_QUI_DECLARENT_est_bien_L_ENSEMBLE_mesure_pas_seulement_son_compte`
 — has been removed**: that witness now derives from the first adopter's REAL gates on disk,
 scoped to that adopter alone, so a new adopter outside it no longer touches it. **A single edit now
 suffices**: add the path named below to `PORTES_QUI_DECLARENT`
 (`system/lib/mnemosyne/production/derives.py`). Verified by REPLAYING it: a disposable project
 created under `projects/_essai/...`, added to `PORTES_QUI_DECLARENT` alone (no other edit),
 yields 36/36 green tests.
 """
    from mnemosyne.production.plan_registry import scan_projects

    registre = scan_projects(REPO / "projects")
    declare: dict[str, str] = {}
    for projet in registre.projects:
        if projet.reading is None:
            continue
        declare[projet.plan_path.relative_to(REPO).as_posix()] = projet.reading.format_declare

    ecart = ecart_adoption(declare=declare)
    assert ecart == (), message_ecart(ecart)


# ---- `inscrire_porte`: the gesture that replaces the hand edit (2026-08-18) --------------------
# The defect closed: `make plans` used to publish "as long as no gesture registers it in
# PORTES_QUI_DECLARENT (…/derives.py)" -- which describes a HAND EDIT OF CODE, i.e. a Mnemosyne
# session and an editor. The second adopter read it and rightly answered, "from a
# project session, I report, I do not repair."

_SOURCE_REELLE = (
    REPO / "system" / "lib" / "mnemosyne" / "production" / "derives.py"
).read_text(encoding="utf-8")


def test_l_ancre_du_gel_matche_EXACTEMENT_une_fois_sur_le_fichier_REEL() -> None:
    """ An anchor that matches 0 times writes nothing; 2 times writes in the wrong place of a
 PRODUCTION module. Measured on the real bytes, never on a fixture shaped to fit."""
    assert len(derives._ANCRE_GEL.findall(_SOURCE_REELLE)) == 1


def test_inscrire_ajoute_UNE_entree_et_UNE_SEULE_au_fichier_reel() -> None:
    avant = _SOURCE_REELLE.count('    "')
    apres = derives.inscrire_porte(_SOURCE_REELLE, "projects/z/ztest/PLAN.md")
    assert '    "projects/z/ztest/PLAN.md",\n' in apres
    assert apres.count('    "') == avant + 1
    # the entry falls INSIDE the tuple, not after: the following line is its closing parenthesis
    lignes = apres.splitlines()
    i = lignes.index('    "projects/z/ztest/PLAN.md",')
    assert lignes[i + 1] == ")", lignes[i : i + 2]


def test_inscrire_REFUSE_une_porte_DEJA_gelee() -> None:
    """A duplicate would make `ecart_adoption` inconsistent with itself."""
    deja = derives.PORTES_QUI_DECLARENT[0]
    with pytest.raises(derives.GelError, match="already frozen"):
        derives.inscrire_porte(_SOURCE_REELLE, deja)


def test_inscrire_REFUSE_un_chemin_qui_casserait_le_litteral_python() -> None:
    """ The freeze is CODE: a quote or a backslash in the path would write an invalid Python
 module -- and the refusal must land BEFORE the write, never at the next import."""
    for mauvais in ('projects/a"b/PLAN.md', "projects/a\\b/PLAN.md", "projects/a\nb/PLAN.md"):
        with pytest.raises(derives.GelError, match="not representable"):
            derives.inscrire_porte(_SOURCE_REELLE, mauvais)


def test_inscrire_REFUSE_quand_l_ancre_a_disparu() -> None:
    """The tuple changed shape: a named refusal beats a guessed insertion."""
    with pytest.raises(derives.GelError, match="insertion anchor found 0 times"):
        derives.inscrire_porte("# a module without the tuple\n", "projects/z/ztest/PLAN.md")


def test_le_message_d_ecart_nomme_la_COMMANDE_et_pas_un_fichier_a_editer() -> None:
    """ THE POINT THAT MATTERS: a message that names a file to edit names a gesture its reader
 (a PROJECT session) cannot pose; one that names a command names one they can -- and `make -C`
 makes it reachable from a project folder (J4)."""
    msg = message_ecart(("projects/perso/x/PLAN.md",))
    assert "make gel-inscrire PORTE=projects/perso/x/PLAN.md APPLY=1" in msg
    assert "make -C ~/mnemosyne gel-inscrire" in msg
