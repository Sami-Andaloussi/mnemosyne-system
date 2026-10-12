"""The Intendant's store - the notes journal and the threads' memory.

What these tests DEFEND, in the order their absence would hurt most:

1. **A thread survives the process restarting.** This is a core requirement: closing the process
   and reopening it seconds later must let the conversation resume as if it had never stopped -
   and the atelier was doing exactly the opposite (thread kept in memory only, docstring: "no
   history, no transcript"). If this test falls, v1 has no reason to exist.
2. **Nothing is ever erased** (invariant 2). Retiring a note takes it out of what the agent READS,
   without taking it out of the journal. Both halves are tested: gone from the read view AND still
   written.
3. **The operator's verbatim is untouchable.** Tidying adds, it never rewrites - otherwise what was
   said is lost in favor of what a model understood from it, which is the opposite of the goal.
4. **A model that goes off the rails does not corrupt the store.** An invented genre or horizon is
   ignored, not stored.
"""

from __future__ import annotations

import json

import pytest

from mnemosyne.runtime import intendant
from mnemosyne.runtime.intendant import EN_TETE_PORTRAIT


@pytest.fixture(autouse=True)
def magasin_neuf(tmp_path, monkeypatch):
    """Each test gets its own store - never the operator's real notes."""
    monkeypatch.setenv("MNEMO_INTENDANT_RACINE", str(tmp_path / "intendant"))
    return tmp_path / "intendant"


# -- Depositing -----------------------------------------------------------------------------------


def test_deposer_puis_lire_rend_la_note():
    note = intendant.deposer("call the accountant before friday")
    relues = intendant.lire()
    assert [n["id"] for n in relues] == [note["id"]]
    assert relues[0]["texte"] == "call the accountant before friday"
    assert relues[0]["etat"] == "vive"


def test_deposer_ne_demande_aucun_rangement():
    """Depositing must succeed BARE: that is what makes it independent of the model.

    If depositing required a genre or a horizon, a thought dictated while the model is
    off would be lost - precisely the case this v1 must make impossible."""
    note = intendant.deposer("a loose idea")
    assert note["genre"] == ""
    assert note["horizon"] == ""
    assert intendant.lire()[0]["texte"] == "a loose idea"


def test_deposer_refuse_le_vide():
    with pytest.raises(ValueError):
        intendant.deposer("   \n  ")


def test_les_sujets_sont_libres_aucune_liste_fermee():
    """Topics are open-ended: a subject outside the configured vocabulary must pass unchanged."""
    note = intendant.deposer("thing", sujets=["random-mess", "my-own-thing", "Coffee [break]"])
    assert intendant.lire()[0]["sujets"] == ["random-mess", "my-own-thing", "Coffee [break]"]
    assert note["sujets"] == ["random-mess", "my-own-thing", "Coffee [break]"]


# -- Tidying, second pass --------------------------------------------------------------------------


def test_ranger_complete_sans_toucher_au_verbatim():
    note = intendant.deposer("I need to call the accountant, it's urgent")
    intendant.ranger(
        note["id"],
        genre="tache",
        horizon="todo",
        sujets=["comptable"],
        resume="Call the accountant",
    )
    relue = intendant.lire()[0]
    assert relue["genre"] == "tache"
    assert relue["horizon"] == "todo"
    assert relue["resume"] == "Call the accountant"
    # THE point: the operator's text is the same byte for byte.
    assert relue["texte"] == "I need to call the accountant, it's urgent"


def test_ranger_ignore_un_genre_ou_un_horizon_invente():
    """A local model that hallucinates a label must not see it enter the store."""
    note = intendant.deposer("thing", genre="tache", horizon="todo")
    intendant.ranger(note["id"], genre="made-up-thing", horizon="immediate")
    relue = intendant.lire()[0]
    assert relue["genre"] == "tache"
    assert relue["horizon"] == "todo"


def test_deposer_ignore_aussi_un_genre_invente():
    note = intendant.deposer("thing", genre="whatever-nonsense", horizon="never")
    assert note["genre"] == ""
    assert note["horizon"] == ""


def test_ranger_sans_champ_valide_n_ecrit_rien():
    note = intendant.deposer("thing")
    avant = (intendant.racine() / "notes.jsonl").read_text(encoding="utf-8")
    assert intendant.ranger(note["id"], genre="not-a-genre") == {}
    apres = (intendant.racine() / "notes.jsonl").read_text(encoding="utf-8")
    assert avant == apres


# -- Non-destructive (invariant 2) -------------------------------------------------------------


def test_retirer_sort_du_chemin_de_lecture_mais_pas_du_journal():
    """Both halves of the doctrine, in a single test - because checking only one of the two
    would let through either a real erasure or a note that never disappears from the screen."""
    note = intendant.deposer("a thought to throw away")
    intendant.marquer(note["id"], "retiree")

    # 1. It has disappeared from what the agent and the screen READ.
    assert intendant.lire() == []
    # 2. It is still in the journal, intact.
    brut = (intendant.racine() / "notes.jsonl").read_text(encoding="utf-8")
    assert "a thought to throw away" in brut
    # 3. And an archive view can find it again.
    archive = intendant.lire(tous=True)
    assert [n["texte"] for n in archive] == ["a thought to throw away"]
    assert archive[0]["etat"] == "retiree"


def test_marquer_faite_la_sort_aussi_de_la_vue_vive():
    note = intendant.deposer("a thing to do")
    intendant.marquer(note["id"], "faite")
    assert intendant.lire() == []
    assert intendant.lire(tous=True)[0]["etat"] == "faite"


def test_marquer_refuse_un_etat_inconnu():
    note = intendant.deposer("thing")
    with pytest.raises(ValueError):
        intendant.marquer(note["id"], "deleted")


def test_aucun_geste_ne_reecrit_une_ligne_existante():
    """The journal is APPEND ONLY: after three actions, the first line is always the
    first, word for word."""
    note = intendant.deposer("the original verbatim")
    premiere = (intendant.racine() / "notes.jsonl").read_text(encoding="utf-8").splitlines()[0]
    intendant.ranger(note["id"], genre="pensee", resume="something else")
    intendant.marquer(note["id"], "faite")
    lignes = (intendant.racine() / "notes.jsonl").read_text(encoding="utf-8").splitlines()
    assert lignes[0] == premiere
    assert len(lignes) == 3


# -- Reading --------------------------------------------------------------------------------------


def test_une_ligne_corrompue_ne_tue_pas_le_journal():
    """An append-only journal can end on a truncated write. Losing the healthy notes because of
    the last one would be the worst of both worlds."""
    intendant.deposer("healthy note")
    with (intendant.racine() / "notes.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"v": 1, "geste": "depot", "note": {truncated\n')
    intendant.deposer("healthy note 2")
    textes = {n["texte"] for n in intendant.lire()}
    assert textes == {"healthy note", "healthy note 2"}


def test_par_horizon_expose_les_notes_non_rangees():
    """`sans` is not a fourth section: it is the queue of what has not been sorted yet. Hiding
    it would turn "I deposit first" into "I deposit and it gets lost"."""
    intendant.deposer("a", horizon="todo")
    intendant.deposer("b", horizon="routine")
    intendant.deposer("c")
    groupes = intendant.par_horizon()
    assert [n["texte"] for n in groupes["todo"]] == ["a"]
    assert [n["texte"] for n in groupes["routine"]] == ["b"]
    assert [n["texte"] for n in groupes["deadline"]] == []
    assert [n["texte"] for n in groupes["sans"]] == ["c"]


def test_par_horizon_normalise_les_ANCIENS_horizons_en_todo():
    """The 29 tasks filed before "court/moyen/long" became "todo/deadline/routine" must neither
    disappear nor stay stuck in a section that no longer exists.

    The journal is APPEND ONLY (inv. 2): it is impossible to write a test line with
    `deposer(horizon="court")`, since the function now rejects that value - exactly as it would
    reject any invented horizon. So the RAW journal line must be written, the way a real session
    from before this change would have."""
    intendant.racine().mkdir(parents=True, exist_ok=True)
    with (intendant.racine() / "notes.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "v": 1,
                    "geste": "depot",
                    "note": {
                        "id": "legacy1",
                        "texte": "a task from before",
                        "horizon": "court",
                        "parent": "",
                        "etat": "vive",
                        "depose_le": "2026-08-01T00:00:00Z",
                    },
                }
            )
            + "\n"
        )
    groupes = intendant.par_horizon()
    assert [n["texte"] for n in groupes["todo"]] == ["a task from before"]
    assert groupes["sans"] == []
    # Non-destructive: the stored field stays "court", only READING reclassifies it.
    assert intendant.lire()[0]["horizon"] == "court"


def test_par_horizon_ne_met_en_colonne_que_les_RACINES():
    """A sub-task lives under its parent, never in a column of its own.

    Requirement: a to-do list must support nested sub-lists per task, not just a single flat
    column. If a child ALSO took its own column slot, it would show up twice and the column's
    count would stop meaning "what I have to do by this deadline"."""
    mere = intendant.deposer("the parent", horizon="todo")
    intendant.deposer("the child", parent=mere["id"])
    # A child SORTED into todo by mistake must not surface anyway: it is the LINK that
    # decides, not the field - otherwise inconsistent data would reopen the defect.
    intendant.deposer("the sorted child", parent=mere["id"], horizon="todo")
    groupes = intendant.par_horizon()
    assert [n["texte"] for n in groupes["todo"]] == ["the parent"]
    assert groupes["sans"] == []


def test_une_sous_tache_ORPHELINE_redevient_racine_plutot_que_de_disparaitre():
    """With its parent retired, the child drops out of its parent's read path - but not out of
    view.

    The reverse would be the worst of both errors: the operator would retire ONE line and lose
    three, with no screen ever saying so. A visible orphan gets noticed and moved; a hidden
    orphan never gets recovered."""
    mere = intendant.deposer("the parent", horizon="todo")
    intendant.deposer("the child", parent=mere["id"])
    intendant.marquer(mere["id"], "retiree")
    groupes = intendant.par_horizon()
    assert [n["texte"] for n in groupes["sans"]] == ["the child"]


# -- reordonner - manual ordering by drag-and-drop -------------------------------------------------


def test_reordonner_impose_l_ordre_choisi():
    """Manual reordering is preserved: `par_horizon` returns the chosen order exactly."""
    a = intendant.deposer("a", horizon="todo")
    b = intendant.deposer("b", horizon="todo")
    c = intendant.deposer("c", horizon="todo")
    intendant.reordonner([c["id"], a["id"], b["id"]])
    groupes = intendant.par_horizon()
    assert [n["texte"] for n in groupes["todo"]] == ["c", "a", "b"]


def test_une_tache_jamais_glissee_reste_devant_les_tachees_rangees():
    """A section never touched by drag-and-drop keeps its deposit-order sort - here, a
    FOURTH task filed afterward must stay AT THE TOP, as it would before any manual ordering:
    that is what lets `+ add` keep appearing at the top of the list."""
    a = intendant.deposer("a", horizon="todo")
    b = intendant.deposer("b", horizon="todo")
    intendant.reordonner([b["id"], a["id"]])
    intendant.deposer("new", horizon="todo")
    groupes = intendant.par_horizon()
    assert [n["texte"] for n in groupes["todo"]] == ["new", "b", "a"]


def test_reordonner_est_non_destructif_une_ligne_de_plus_par_note():
    """Same family of actions as `ranger` (inv. 2): one `modif` line per note touched,
    never a rewrite of the deposit line."""
    a = intendant.deposer("a", horizon="todo")
    b = intendant.deposer("b", horizon="todo")
    n_avant = len(intendant._journal().read_text(encoding="utf-8").splitlines())
    intendant.reordonner([b["id"], a["id"]])
    lignes_apres = intendant._journal().read_text(encoding="utf-8").splitlines()
    assert len(lignes_apres) == n_avant + 2
    assert intendant.lire()[1]["texte"] == "a"  # the verbatim hasn't moved


def test_reordonner_ignore_un_id_vide():
    a = intendant.deposer("a", horizon="todo")
    intendant.reordonner([a["id"], "", "   "])
    groupes = intendant.par_horizon()
    assert [n["texte"] for n in groupes["todo"]] == ["a"]


# -- Deadline and description ------------------------------------------------------------------


def test_echeance_valide_est_gardee_sur_une_deadline():
    note = intendant.deposer("pay the rent", horizon="deadline", echeance="2026-09-01T18:00:00")
    assert intendant.lire()[0]["echeance"] == "2026-09-01T18:00:00"
    assert note["echeance"] == "2026-09-01T18:00:00"


def test_echeance_illisible_est_ignoree_pas_stockee_telle_quelle():
    """Text that is clearly not a date must not be able to break a sort or a
    count later, on screen."""
    note = intendant.deposer("a thing", horizon="deadline", echeance="whatever")
    assert note["echeance"] == ""
    assert intendant.lire()[0]["echeance"] == ""


def test_ranger_pose_une_echeance_sans_toucher_au_reste():
    note = intendant.deposer("a project", horizon="deadline")
    intendant.ranger(note["id"], echeance="2026-10-05T09:00:00")
    assert intendant.lire()[0]["echeance"] == "2026-10-05T09:00:00"


def test_description_vit_a_cote_du_texte_sans_le_remplacer():
    note = intendant.deposer("prepare the file", description="detail the title doesn't carry")
    relue = intendant.lire()[0]
    assert relue["description"] == "detail the title doesn't carry"
    assert relue["texte"] == "prepare the file"
    assert note["description"] == "detail the title doesn't carry"


def test_ranger_peut_ajouter_une_description_apres_coup():
    note = intendant.deposer("a thing")
    intendant.ranger(note["id"], description="added later")
    assert intendant.lire()[0]["description"] == "added later"


# -- Re-parenting a note already there -------------------------------------------------------------
#
# Re-parenting preserves a note's creation metadata and history, unlike re-submitting it.


def test_ranger_peut_reparenter_une_note_deja_deposee():
    mere = intendant.deposer("Example Lab", horizon="todo")
    fille = intendant.deposer("set up a GitHub for Example Lab", horizon="todo")
    # Before: both are ROOTS, each takes its own column line.
    avant = intendant.par_horizon()
    assert {n["id"] for n in avant["todo"]} == {mere["id"], fille["id"]}

    intendant.ranger(fille["id"], parent=mere["id"])

    relue = next(n for n in intendant.lire() if n["id"] == fille["id"])
    assert relue["parent"] == mere["id"]
    # After: the child no longer takes its own line - it lives under its parent.
    apres = intendant.par_horizon()
    assert {n["id"] for n in apres["todo"]} == {mere["id"]}


def test_ranger_refuse_qu_une_note_devienne_sa_propre_mere():
    note = intendant.deposer("thing")
    assert intendant.ranger(note["id"], parent=note["id"]) == {}
    assert intendant.lire()[0]["parent"] == ""


# -- Search ---------------------------------------------------------------------------------------


def test_chercher_ignore_les_accents_dans_les_DEUX_sens():
    """The operator dictates by voice: accents fall wherever chance has it in the transcription.
    A search that requires them would find nothing half the time - and it must work whether the
    accent is missing from the NOTE or from the QUERY.

    NOTE: the accented/unaccented word pair below is the
    property under test (accent folding), not decorative prose, so it is intentionally left
    untranslated per the mandate's unicode-subject exception."""
    intendant.deposer("préférence for MoE models")
    intendant.deposer("preference for coffee")
    assert len(intendant.chercher("preference")) == 2
    assert len(intendant.chercher("préférence")) == 2


def test_chercher_pese_le_verbatim_plus_que_le_resume():
    """What the OPERATOR said must rank above what a model summarized from it."""
    intendant.deposer("the embeddings cache")
    intendant.deposer("something else", resume="cache")
    resultats = intendant.chercher("cache")
    assert resultats[0]["texte"] == "the embeddings cache"


def test_chercher_sans_question_rend_les_recentes_pas_le_vide():
    intendant.deposer("a")
    intendant.deposer("b")
    assert len(intendant.chercher("")) == 2


def test_chercher_ne_rend_pas_les_notes_retirees():
    note = intendant.deposer("a secret")
    intendant.marquer(note["id"], "retiree")
    assert intendant.chercher("secret") == []


# -- The SITUATION-based deferral -------------------------------------------------------------------


def test_rappeler_situation_ne_regarde_que_le_quand():
    """The deferral mechanism: a note held back until a specific later moment, not until any
    related word resurfaces.

    A note whose TEXT talks about perf but that wasn't waiting for anything must not resurface -
    otherwise "what I set aside for this moment" turns back into "anything containing this
    word"."""
    attend = intendant.deposer(
        "put a cache on the embeddings", quand="when I'm working on Acme Research's perf"
    )
    intendant.deposer("Acme Research's perf is bad")  # no `quand`
    trouvees = intendant.rappeler_situation("I'm working on Acme Research's perf")
    assert [n["id"] for n in trouvees] == [attend["id"]]


def test_rappeler_situation_vide_ne_rend_rien():
    intendant.deposer("thing", quand="later")
    assert intendant.rappeler_situation("") == []


# -- THE THREADS - instant memory --------------------------------------------------------------


def test_un_fil_survit_a_la_mort_du_processus():
    """THE test of v1. We simulate the shutdown by discarding all in-memory state: only disk
    remains. If this test falls, the operator's central requirement is not met."""
    fil = intendant.fil_neuf(modele="un-modele")
    intendant.fil_ajouter(fil["id"], "I'm working on the workshop", "sounds good, tell me more")
    intendant.fil_ajouter(fil["id"], "it loses everything when I close it", "that's the unpersisted thread")

    # reopening moments later: nothing but the id needs to survive the round trip.
    rouvert = intendant.fil_lire(fil["id"])
    assert rouvert is not None
    assert [t["texte"] for t in rouvert["tours"]] == [
        "I'm working on the workshop",
        "sounds good, tell me more",
        "it loses everything when I close it",
        "that's the unpersisted thread",
    ]
    assert [t["role"] for t in rouvert["tours"]] == [
        "operator",
        "intendant",
        "operator",
        "intendant",
    ]


def test_le_fil_est_ecrit_a_CHAQUE_tour_pas_a_la_fermeture():
    """End-of-session persistence does not survive an abrupt shutdown - which is the NORMAL
    case the operator described, not the accident."""
    fil = intendant.fil_neuf()
    intendant.fil_ajouter(fil["id"], "first", "response")
    sur_disque = json.loads((intendant.racine() / "fils" / f"{fil['id']}.json").read_text("utf-8"))
    assert len(sur_disque["tours"]) == 2


def test_le_titre_naît_des_mots_de_operator_pas_du_modele():
    """It is they who must recognize their thread in a list, and they recognize their own
    words."""
    fil = intendant.fil_neuf()
    intendant.fil_ajouter(fil["id"], "the embeddings cache", "I'll answer you with something different")
    assert intendant.fil_lire(fil["id"])["titre"] == "the embeddings cache"


def test_fil_dernier_rend_celui_qu_on_venait_de_quitter():
    a = intendant.fil_neuf(titre="old")
    b = intendant.fil_neuf(titre="recent")
    intendant.fil_ajouter(a["id"], "I'm coming back to the old one", "ok")
    # `a` was just touched: it is THAT one we reopen, not the most recently created.
    assert intendant.fil_dernier()["id"] == a["id"]
    intendant.fil_ajouter(b["id"], "no, this one", "ok")
    assert intendant.fil_dernier()["id"] == b["id"]


def test_fils_lister_ne_charge_pas_les_tours():
    fil = intendant.fil_neuf()
    intendant.fil_ajouter(fil["id"], "a very long message " * 50, "response")
    liste = intendant.fils_lister()
    assert liste[0]["tours"] == 1  # the COUNT of exchanges, not their content
    assert "texte" not in liste[0]


def test_un_identifiant_de_fil_ne_peut_pas_sortir_du_dossier():
    """An id travels through an HTTP request. Letting it carry `../` would let a page write
    anywhere on disk. The barrier sits at the filesystem boundary."""
    for mechant in ("../evasion", "a/b", "..", "", "x" * 65, "name with space"):
        with pytest.raises(ValueError):
            intendant._chemin_fil(mechant)


def test_lire_un_fil_inexistant_ou_mechant_rend_none_sans_lever():
    """A missing thread must cost ONE thread, never the whole screen."""
    assert intendant.fil_lire("doesnotexist123") is None
    assert intendant.fil_lire("../evasion") is None


def test_un_fil_corrompu_ne_tue_pas_la_liste():
    bon = intendant.fil_neuf(titre="good")
    (intendant.racine() / "fils" / "casse.json").write_text("{truncated", encoding="utf-8")
    liste = intendant.fils_lister()
    assert [f["id"] for f in liste] == [bon["id"]]


def test_fil_ajouter_sur_un_fil_absent_rend_none():
    assert intendant.fil_ajouter("absent123456", "a", "b") is None


# -- What the screen reads -------------------------------------------------------------------------


def test_etat_rend_tout_en_une_lecture():
    intendant.deposer("a", horizon="todo")
    intendant.deposer("b")
    fil = intendant.fil_neuf(titre="a conversation")
    vue = intendant.etat()
    assert vue["total"] == 2
    assert vue["comptes"] == {"deadline": 0, "todo": 1, "routine": 0, "sans": 1}
    assert [f["id"] for f in vue["fils"]] == [fil["id"]]
    assert set(vue["par_horizon"]) == {"deadline", "todo", "routine", "sans"}


def test_etat_sur_un_magasin_vierge_ne_leve_pas():
    """The very first launch at the operator's: no file exists yet."""
    vue = intendant.etat()
    assert vue["total"] == 0
    assert vue["fils"] == []
    assert vue["comptes"]["sans"] == 0


# -- What surfaces ON ITS OWN -----------------------------------------------------------------------
#
# The deferral (`quand`) and `pertinentes` are two forms of recall the base offers, with no extra
# gesture from the user.


def test_pertinentes_remonte_le_deja_dit_sur_le_sujet():
    intendant.deposer("Acme Research's embeddings cache is bothering me")
    intendant.deposer("I need to call an accountant")
    trouvees = intendant.pertinentes("I'm working on embeddings")
    assert [n["texte"] for n in trouvees] == ["Acme Research's embeddings cache is bothering me"]


def test_pertinentes_exclut_la_note_qu_on_VIENT_d_ecrire():
    """The trap: the current turn's note matches itself perfectly.

    Without exclusion, it would grab the base's whole budget just to hand the model back the
    sentence it is already reading - and the real related notes would get pushed out."""
    ancienne = intendant.deposer("the embeddings cache, an idea from three weeks ago")
    courante = intendant.deposer("I'm working on the embeddings cache")
    trouvees = intendant.pertinentes("I'm working on the embeddings cache", sauf=courante["id"])
    assert [n["id"] for n in trouvees] == [ancienne["id"]]


def test_pertinentes_ne_rend_rien_sur_un_sujet_inconnu():
    intendant.deposer("the embeddings cache")
    assert intendant.pertinentes("a recipe for banana bread") == []


# -- The portrait -------------------------------------------------------------------------------


def test_sans_portrait_le_socle_n_en_parle_pas():
    """A fabricated portrait would make the agent reason about a life that is not the
    operator's - and it would have no way to know it's false. Absent, it stays silent."""
    assert intendant.portrait() == ""
    assert EN_TETE_PORTRAIT not in intendant.socle()


def test_l_EN_TETE_est_REELLEMENT_EMIS_sinon_la_garde_est_inerte():
    """THE WITNESS THAT WAS MISSING -- and its absence cost a PRIVACY guard.

    Pointing both assertions at `EN_TETE_PORTRAIT` is not enough on its own: if the constant stops
    being the string `socle()` actually emits, `EN_TETE_PORTRAIT not in socle()` becomes true BY
    CONSTRUCTION again and the guard is inert -- the original defect, moved one notch. Measured on
    this mirror, 2026-09-09: translation changed the emitted heading without touching the two
    assertions, which still looked for the French text; they were green forever, including if the
    portrait had leaked.

    This is the only test that ties the constant to the EMISSION. It asserts BOTH directions --
    present when a portrait exists, absent when there is none -- because either one alone would
    accept an empty constant, and an empty string is inside every string."""
    intendant.racine().mkdir(parents=True, exist_ok=True)
    (intendant.racine() / "portrait.md").write_text("- teaches 9am-5pm\n", encoding="utf-8")
    avec = intendant.socle(portrait=intendant.portrait())
    assert EN_TETE_PORTRAIT and EN_TETE_PORTRAIT.strip(), "an EMPTY heading is inside every string"
    assert EN_TETE_PORTRAIT in avec, (
        "the constant has drifted away from what socle() emits: the two privacy guards that check "
        "for its ABSENCE are true by construction again"
    )
    assert EN_TETE_PORTRAIT not in intendant.socle(portrait="")


def test_le_portrait_entre_dans_le_socle_quand_il_existe():
    (intendant.racine()).mkdir(parents=True, exist_ok=True)
    (intendant.racine() / "portrait.md").write_text("- class 9am-5pm\n", encoding="utf-8")
    assert "class 9am-5pm" in intendant.socle(portrait=intendant.portrait())


def test_les_connexes_entrent_dans_le_socle_et_sont_bornees():
    """What enters the base is paid for on EVERY turn: the bound is the same as for the
    deferral."""
    beaucoup = [{"resume": f"related {i}", "depose_le": "2026-08-04"} for i in range(20)]
    texte = intendant.socle(connexes=beaucoup)
    assert texte.count("related ") == 5


def test_le_socle_dit_que_TOUT_est_deja_garde():
    """The operator removed the "Keep" button: the agent must never ask whether to keep
    something, nor promise to do so - it is already written before it even sees the sentence."""
    assert "ALREADY recorded" in intendant.socle()


def test_le_socle_interdit_le_recap_complet_apres_une_ecriture():
    """A confirmation after `ajouter_sous_tache` must remain a short acknowledgement, not a full recap."""
    assert "ONE SHORT SENTENCE" in intendant.socle()
    assert "generic closing formula" in intendant.socle()


# -- The portrait: ONE file, TWO views -----------------------------------------------------------
#
# The operator's real portrait weighs 15,191 characters, about ~4,900 tokens - 30% of a
# `phi-4` window (16,384), paid on EVERY turn. So the base only takes the sections that change the
# answer to ANY question at all. A "short version" stored separately would drift from the
# original with nothing to flag it: it is the SAME file, read two different ways.

_PORTRAIT = """# PORTRAIT - operator

## 1. Rhythm
- sport tuesday and thursday 6-7:30pm

## 3. Projects
### Acme Research
- some macro-level report thing

## 6. Health and body
- 23 years old, 1.83 m

## 7. How to talk to them
- don't over-engineer

## 9. To remember, and WHEN
- when wednesday 5pm approaches
"""


def _poser_portrait(texte=_PORTRAIT):
    intendant.racine().mkdir(parents=True, exist_ok=True)
    (intendant.racine() / "portrait.md").write_text(texte, encoding="utf-8")


def test_le_socle_ne_prend_que_les_sections_declarees():
    _poser_portrait()
    court = intendant.portrait()
    assert "sport tuesday and thursday" in court  # 1. Rhythm
    assert "don't over-engineer" in court  # 7. How to talk to them
    assert "wednesday 5pm" in court  # 9. To remember
    # What would cost a lot without serving every turn stays in the file.
    assert "macro-level" not in court  # 3. Projects - the `plans` tool says it better
    assert "1.83 m" not in court  # 6. Health


def test_tout_rend_le_fichier_ENTIER():
    """For a search or a display - never for the base."""
    _poser_portrait()
    assert "macro-level" in intendant.portrait(tout=True)
    assert "1.83 m" in intendant.portrait(tout=True)


def test_un_portrait_AUX_TITRES_INCONNUS_rend_tout_plutot_que_RIEN():
    """The trap: the operator renames their sections by hand during a later edit.

    Returning "" would turn "the titles changed" into "there is no portrait" - and
    the agent would reason about an empty life with nothing to say so. A whole portrait costs
    tokens; an absent portrait costs wrong answers."""
    _poser_portrait("# PORTRAIT\n\n## My own rhythm\n- early riser\n")
    assert "early riser" in intendant.portrait()


def test_sans_fichier_le_portrait_est_VIDE_et_le_socle_se_tait():
    assert intendant.portrait() == ""
    assert EN_TETE_PORTRAIT not in intendant.socle(portrait=intendant.portrait())


def test_les_sections_voulues_sont_choisissables():
    _poser_portrait()
    sante = intendant.portrait(sections=("6.",))
    assert "1.83 m" in sante
    assert "sport tuesday" not in sante


# -- racine_par_titre - the check `poser_tache` never used to make -------------------------------
#
# NOTE: this header's history was already partly redacted
# before this pass (a generic placeholder line sat mid-paragraph in the source). Reconstructed
# from the surviving fragments: adding something as a sub-task must first check whether a
# matching root task already exists, rather than blindly creating a new one - a real request to
# add a UI Mnemosyne sub-task, with no existing-root check, produced TWO distinct "UI Mnemosyne"
# roots with identical sub-tasks.


def test_racine_par_titre_trouve_une_correspondance_exacte():
    note = intendant.deposer("UI Mnémosyne", genre="tache", horizon="todo")
    assert intendant.racine_par_titre("UI Mnémosyne")["id"] == note["id"]


def test_racine_par_titre_ignore_accents_et_casse():
    note = intendant.deposer("UI Mnémosyne", genre="tache", horizon="todo")
    assert intendant.racine_par_titre("ui mnemosyne")["id"] == note["id"]
    assert intendant.racine_par_titre("UI MNÉMOSYNE")["id"] == note["id"]


def test_racine_par_titre_absente_rend_none():
    assert intendant.racine_par_titre("Does not exist") is None


def test_racine_par_titre_ignore_une_sous_tache_du_meme_texte():
    """A SUB-task is not a root - same title, wrong level, never a false
    match that would hang new sub-tasks in the wrong place."""
    parent = intendant.deposer("Theme", genre="tache", horizon="todo")
    intendant.deposer("UI Mnémosyne", genre="tache", parent=parent["id"])
    assert intendant.racine_par_titre("UI Mnémosyne") is None


def test_racine_par_titre_ignore_une_note_retiree():
    note = intendant.deposer("UI Mnémosyne", genre="tache", horizon="todo")
    intendant.marquer(note["id"], "retiree")
    assert intendant.racine_par_titre("UI Mnémosyne") is None


# -- notes_par_titre - the resolver behind rename/delete/describe from chat -----------------------
#
# Requirement: the model never has access to a note's internal id - only to what the user typed.
# Without a title resolver, a request to rename or delete a task could not be carried out at all;
# the system would file a new task describing the request instead of acting on it.


def test_notes_par_titre_trouve_une_racine():
    note = intendant.deposer("UI Mnémosyne", genre="tache", horizon="todo")
    trouvees = intendant.notes_par_titre("UI Mnémosyne")
    assert [n["id"] for n in trouvees] == [note["id"]]


def test_notes_par_titre_trouve_aussi_une_sous_tache():
    """Unlike `racine_par_titre`: rename/delete must also work on a SUB-task -
    the operator doesn't make that distinction when talking about it in chat."""
    parent = intendant.deposer("Theme", genre="tache", horizon="todo")
    fille = intendant.deposer("Work on the RAG", genre="tache", parent=parent["id"])
    trouvees = intendant.notes_par_titre("Work on the RAG")
    assert [n["id"] for n in trouvees] == [fille["id"]]


def test_notes_par_titre_correspond_aussi_au_resume_affiche():
    """The operator names a task by what they SEE on screen (the `resume`, once set), not
    necessarily by the original verbatim."""
    note = intendant.deposer("poorly transcribed voice note", genre="tache", horizon="todo")
    intendant.ranger(note["id"], resume="Build the recurrence feature")
    trouvees = intendant.notes_par_titre("Build the recurrence feature")
    assert [n["id"] for n in trouvees] == [note["id"]]


def test_notes_par_titre_rend_TOUTES_les_correspondances_ambigues():
    """An identical title can occur as both a root task and sub-task. Return both, never guess."""
    racine = intendant.deposer("Work on the RAG", genre="tache", horizon="todo")
    parent = intendant.deposer("To do, to test", genre="tache", horizon="todo")
    fille = intendant.deposer("Work on the RAG", genre="tache", parent=parent["id"])
    trouvees = {n["id"] for n in intendant.notes_par_titre("Work on the RAG")}
    assert trouvees == {racine["id"], fille["id"]}


def test_notes_par_titre_absente_rend_liste_vide():
    assert intendant.notes_par_titre("Does not exist") == []


def test_notes_par_titre_ignore_une_note_retiree():
    note = intendant.deposer("UI Mnémosyne", genre="tache", horizon="todo")
    intendant.marquer(note["id"], "retiree")
    assert intendant.notes_par_titre("UI Mnémosyne") == []


# -- The .md backup copy - accessible even if the UI breaks -----------------------------------------
#
# Requirement: a continuously updated backup of the task metadata must exist, so that if the UI
# ever breaks, the current state of the list is still reachable somewhere at all times.


def test_deposer_ecrit_la_copie_md():
    intendant.deposer("call the accountant", genre="tache", horizon="todo")
    chemin = intendant.racine() / "liste.md"
    assert chemin.is_file()
    assert "call the accountant" in chemin.read_text(encoding="utf-8")


def test_la_copie_md_reflete_les_trois_sections():
    intendant.deposer("a routine task", genre="tache", horizon="routine")
    intendant.deposer("a deadline task", genre="tache", horizon="deadline", echeance="2026-09-01")
    intendant.deposer("a todo task", genre="tache", horizon="todo")
    texte = (intendant.racine() / "liste.md").read_text(encoding="utf-8")
    assert "## Routine" in texte and "a routine task" in texte
    assert "## Deadlines" in texte and "a deadline task" in texte and "2026-09-01" in texte
    assert "## To-do" in texte and "a todo task" in texte


def test_la_copie_md_imbrique_les_sous_taches():
    parent = intendant.deposer("Work on the RAG", genre="tache", horizon="deadline")
    intendant.deposer("Decide the OCR runs", genre="tache", parent=parent["id"])
    texte = (intendant.racine() / "liste.md").read_text(encoding="utf-8")
    ligne_parent = texte.index("Work on the RAG")
    ligne_fille = texte.index("Decide the OCR runs")
    assert ligne_fille > ligne_parent  # the child is written AFTER its parent, so below it
    assert texte.count("  - Decide the OCR runs") == 1  # indented one notch


def test_la_copie_md_utilise_le_resume_quand_il_existe():
    note = intendant.deposer("prepare the meeting", genre="tache", horizon="todo")
    intendant.ranger(note["id"], resume="Prepare the client check-in")
    texte = (intendant.racine() / "liste.md").read_text(encoding="utf-8")
    assert "Prepare the client check-in" in texte
    assert "prepare the meeting" not in texte


def test_retirer_une_note_la_sort_de_la_copie_md():
    note = intendant.deposer("to remove", genre="tache", horizon="todo")
    intendant.marquer(note["id"], "retiree")
    texte = (intendant.racine() / "liste.md").read_text(encoding="utf-8")
    assert "to remove" not in texte


def test_reordonner_reecrit_la_copie_md_une_seule_fois(monkeypatch):
    """`reordonner` loops over several notes: the copy must only be rewritten at THE END, not
    once per note touched -- otherwise sorting ten tasks would write the file ten times."""
    a = intendant.deposer("a", genre="tache", horizon="todo")
    b = intendant.deposer("b", genre="tache", horizon="todo")
    compteur = {"n": 0}
    original = intendant._ecrire_liste_md

    def compte_et_ecrit():
        compteur["n"] += 1
        original()

    monkeypatch.setattr(intendant, "_ecrire_liste_md", compte_et_ecrit)
    intendant.reordonner([b["id"], a["id"]])
    assert compteur["n"] == 1


def test_la_copie_md_est_absente_avant_tout_depot():
    assert not (intendant.racine() / "liste.md").is_file()


def test_ecrire_liste_md_ne_leve_jamais_meme_si_l_ecriture_echoue(monkeypatch):
    """Best effort: a WRITE failure on the copy must never bubble an
    exception up to the caller (the real deposit, in the journal, already succeeded)."""

    def casse(*_a, **_k):
        raise OSError("disk full, for example")

    monkeypatch.setattr(intendant.os, "replace", casse)
    intendant.deposer("it must succeed anyway", genre="tache", horizon="todo")
    assert intendant.lire()[0]["texte"] == "it must succeed anyway"
