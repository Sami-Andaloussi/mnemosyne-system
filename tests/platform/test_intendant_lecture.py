"""Reading what a SMALL model returns - the Intendant's most exposed surface.

A 4-to-13 GB model does not obey "return ONLY a JSON object". It wraps it in ```json, it
prefaces it with a pleasantry, it comments afterward, it returns ``"null"`` as a string. All of
this is NORMAL, and a reader that demands it clean turns a correct answer into a failure - then
blames the model for the failure.

These tests are therefore written against DIRTY outputs, because those are the real ones. They
also defend the reverse gate: what is invalid must not enter the store, and an invented tool must
never reach an execution table.
"""

from __future__ import annotations

from mnemosyne.runtime import intendant as I  # noqa: N817 (readability of the cases below)


# -- Extracting an object from a chatty response -------------------------------------------------


def test_json_nu():
    assert I._extraire_json('{"a": 1}') == {"a": 1}


def test_json_dans_une_cloture_markdown():
    """By far the most frequent case."""
    assert I._extraire_json('Here:\n```json\n{"a": 1}\n```\nThere.') == {"a": 1}


def test_json_precede_et_suivi_de_prose():
    brut = 'Sure! Here\'s the sorting.\n{"genre": "tache"}\nI hope that helps.'
    assert I._extraire_json(brut) == {"genre": "tache"}


def test_un_objet_imbrique_est_rendu_ENTIER():
    """Cutting at the first `}` would produce an unreadable fragment - that is the trap of naive
    counting."""
    brut = 'blah blah {"outil": "x", "args": {"q": "cache"}} end'
    assert I._extraire_json(brut) == {"outil": "x", "args": {"q": "cache"}}


def test_une_accolade_dans_une_chaine_ne_compte_pas():
    brut = '{"texte": "he said } then {", "ok": true}'
    assert I._extraire_json(brut) == {"texte": "he said } then {", "ok": True}


def test_une_accolade_echappee_ne_compte_pas():
    brut = r'{"texte": "quote \" then }", "ok": true}'
    assert I._extraire_json(brut) == {"texte": 'quote " then }', "ok": True}


def test_un_premier_objet_casse_n_empeche_pas_de_trouver_le_second():
    """A model often scratches out its first attempt. Stopping at the first `{` would lose the
    right one."""
    brut = '{this isnt json} then the real one: {"genre": "pensee"}'
    assert I._extraire_json(brut) == {"genre": "pensee"}


def test_sans_json_rend_none():
    assert I._extraire_json("I'm not really sure what to answer you.") is None


def test_un_tableau_seul_n_est_pas_un_objet():
    assert I._extraire_json("[1, 2, 3]") is None


# -- Tool calls ------------------------------------------------------------------------------------


def test_appel_reconnu():
    assert I.lire_appel('{"outil": "rappel", "args": {"q": "embeddings cache"}}') == (
        "rappel",
        {"q": "embeddings cache"},
    )


def test_appel_sans_args_est_accepte():
    """`plans()` takes nothing: requiring an `args` would refuse a perfectly correct call."""
    assert I.lire_appel('{"outil": "plans"}') == ("plans", {})


def test_un_outil_hors_catalogue_est_REFUSE():
    """A model that invents `supprimer_tout` must not see its invention reach the server."""
    assert I.lire_appel('{"outil": "supprimer_tout", "args": {}}') is None
    assert I.lire_appel('{"outil": "rm", "args": {"path": "/"}}') is None


def test_une_reponse_normale_n_est_pas_un_appel():
    assert I.lire_appel("You'd told me to remind you to call the accountant before Friday.") is None


def test_un_json_qui_n_est_pas_un_appel_n_en_est_pas_un():
    assert I.lire_appel('{"genre": "tache", "horizon": "todo"}') is None


# -- Tidying --------------------------------------------------------------------------------------


def test_rangement_complet():
    brut = """```json
{"genre": "tache", "sujets": ["accountant", "administrative"], "horizon": "todo",
 "quand": null, "resume": "Call the accountant before Friday"}
```"""
    assert I.lire_rangement(brut) == {
        "genre": "tache",
        "sujets": ["accountant", "administrative"],
        "horizon": "todo",
        "resume": "Call the accountant before Friday",
    }


def test_le_null_EN_CHAINE_est_traite_comme_un_null():
    """Small models often return `"null"` instead of `null`.

    Taking it for a real value would surface EVERY note at the slightest situation - the
    deferral would become permanent noise, and the mechanism would be unusable."""
    assert "quand" not in I.lire_rangement('{"quand": "null"}')
    assert "quand" not in I.lire_rangement('{"quand": "NULL"}')
    assert "quand" not in I.lire_rangement('{"quand": "  "}')


def test_un_quand_reel_est_garde():
    range_ = I.lire_rangement('{"quand": "when I\'m working on Acme Research\'s perf"}')
    assert range_["quand"] == "when I'm working on Acme Research's perf"


def test_un_genre_ou_un_horizon_invente_est_laisse_de_cote():
    range_ = I.lire_rangement('{"genre": "urgent", "horizon": "immediate", "resume": "ok"}')
    assert range_ == {"resume": "ok"}


def test_les_sujets_restent_LIBRES_mais_bornes_en_nombre():
    """Free in content (the operator's call), bounded in number: a model that loops out of
    control can return forty labels, and they would be paid for on every display."""
    brut = '{"sujets": ' + str([f"s{i}" for i in range(40)]).replace("'", '"') + "}"
    assert len(I.lire_rangement(brut)["sujets"]) == 8


def test_des_sujets_vides_sont_jetes():
    assert "sujets" not in I.lire_rangement('{"sujets": ["", "  "]}')


def test_une_reponse_sans_rien_de_valide_rend_un_dict_vide():
    assert I.lire_rangement("I didn't understand your request.") == {}
    assert I.lire_rangement('{"whatever": "nonsense"}') == {}


# -- The base ---------------------------------------------------------------------------------------


def test_le_socle_nomme_TOUS_les_outils_du_catalogue():
    """The catalog has a single home. If a tool is added without the base saying so, the model
    will never call it - and the tool would be a capability that nothing reaches."""
    texte = I.socle()
    for nom in I.OUTILS:
        assert nom in texte


def test_un_mode_ajoute_son_amorce_sans_rien_interdire():
    technique = I.socle("technique")
    assert I.MODES["technique"]["amorce"] in technique
    # The ORIENTED mode: nothing in the base forbids talking about something else (the operator's
    # call). Both languages are checked on purpose - this module's user-facing strings are French
    # today and translating them must not quietly turn this check into one that can never fail.
    assert not any(m in technique.lower() for m in ("interdit", "forbid", "never talk"))


def test_le_mode_libre_n_ajoute_aucune_amorce():
    assert I.socle("libre") == I.socle()


def test_un_mode_inconnu_retombe_sur_libre_sans_lever():
    assert I.socle("mode-that-does-not-exist") == I.socle("libre")


def test_les_notes_en_attente_arrivent_PAR_LE_SOCLE():
    """The deferral must arrive without being asked for: that is its whole point.

    The operator will not think to ask for what they forgot - if it took a tool to surface it, the
    mechanism would never trigger at the moment it matters."""
    texte = I.socle("technique", en_attente=[{"resume": "put a cache on the embeddings"}])
    assert "put a cache on the embeddings" in texte


def test_le_socle_borne_le_nombre_de_rappels():
    """What enters the base is paid for on EVERY turn, on a window of about 16,000 tokens
    for the small models in the lineup."""
    beaucoup = [{"resume": f"note {i}"} for i in range(20)]
    texte = I.socle(en_attente=beaucoup)
    assert texte.count("note ") == 5


# -- The reasoning envelope -------------------------------------------------------------------------
#
# Each case below is a REAL extract from the 2026-08-04 bench, not an invented string. A fixture
# written from memory would have the shape I BELIEVE these models produce; these have the shape
# they actually produce.
#
# NOTE: the raw `brut` fixtures and their expected outputs in
# this section are verbatim recorded model output (per the paragraph above), not authored prose;
# translating the French portions would misrepresent what was actually recorded, so they are left
# untouched.


def test_le_bloc_think_de_glm_z1_est_retire():
    brut = "<think>\nOkay, let's tackle this. The operator wants me to...\n</think>\n\nJe place la tâche le mercredi."
    assert I.nettoyer_reponse(brut) == "Je place la tâche le mercredi."


def test_le_canal_analyse_de_gpt_oss_est_retire():
    brut = (
        "<|channel|>analysis<|message|>We need to respond in 3 lines, in French. The operator is..."
        "<|start|>assistant<|channel|>final<|message|>Il parle du worker qui garde le modèle chaud."
    )
    assert I.nettoyer_reponse(brut) == "Il parle du worker qui garde le modèle chaud."


def test_les_marqueurs_orphelins_partent_aussi():
    """A response truncated mid-harmony-format leaves isolated tags."""
    assert I.nettoyer_reponse("<|start|>assistant<|message|>Bonjour.") == "Bonjour."


def test_une_reponse_NORMALE_traverse_intacte():
    """The large majority of models wrap nothing: cleaning must not cost them anything."""
    for brut in ("Je place la tâche le mercredi de 18h à 20h.", '{"genre": "tache"}', "a < b > c"):
        assert I.nettoyer_reponse(brut) == brut


def test_une_reponse_ENTIEREMENT_enveloppee_rend_le_BRUT_pas_du_VIDE():
    """The trap. `GLM-Z1` overran its output limit on two bench tasks: it had written
    ONLY reasoning. Returning "" would turn "it answered badly" into "it didn't answer at all" -
    a silence looks like a system failure, and is much harder to diagnose than a shaky answer."""
    brut = "<think>Okay, let's see. operator needs to schedule a 2-hour task and</think>"
    assert I.nettoyer_reponse(brut) == brut


def test_le_nettoyage_laisse_le_JSON_lisible():
    """The tool call must survive cleaning: it is the same string that serves both."""
    brut = '<think>he wants his notes</think>\n{"outil": "chercher_notes", "args": {"q": "cache"}}'
    assert I.lire_appel(I.nettoyer_reponse(brut)) == ("chercher_notes", {"q": "cache"})


# -- The code FLOOR under the deferral -------------------------------------------------------------
#
# The deferred-task extractor recognizes a stable phrase pattern; it does not ask a model to perform
# arithmetic that a deterministic parser can handle.
#
# NOTE: the French sentences fed into `situation_differee`
# below are matched against a hardcoded French-language regex in the (out-of-scope) production
# module (`_DIFFERE`/`_PLUS_TARD` in intendant.py, keyed on "quand"/"une fois que"/"dès que"/
# "apres que"/"pas maintenant"/"plus tard"); translating them would make the pattern stop
# matching, so the trigger phrases are left in French throughout this section.


def test_le_plancher_lit_la_situation_dans_la_phrase():
    """Representative deferred-task phrasings."""
    assert (
        I.situation_differee(
            "faudrait un cache sur les embeddings mais pas maintenant, c'est quand je serai sur les perfs"
        )
        == "quand je serai sur les perfs"
    )
    assert "une fois que" in I.situation_differee(
        "une fois que j'aurai fini les cours il faudra que je rappelle le comptable"
    )
    assert I.situation_differee("on verra ça dès que la captation sera finie").startswith("dès que")


def test_le_plancher_se_TAIT_quand_il_n_y_a_pas_de_situation():
    """The real risk is not missing a deferral, it's inventing one.

    A note with a fake `quand` would resurface at the slightest sentence and drown out the real
    reminders - the mechanism would become permanent noise, therefore unusable. No `quand` at all
    is better."""
    assert I.situation_differee("faut que je rappelle le comptable avant vendredi") == ""
    assert I.situation_differee("il fait beau aujourd'hui") == ""
    assert I.situation_differee("pas maintenant") == ""  # says there is one, not which one
    assert I.situation_differee("") == ""


def test_le_plancher_garde_les_MOTS_DE_OPERATOR():
    """These are their own words, which will have to match later, when they redescribe the same
    situation. A rewording would lose the vocabulary by which they will recognize it."""
    assert I.situation_differee("c'est quand je serai sur l'optimisation des perfs") == (
        "quand je serai sur l'optimisation des perfs"
    )


def test_le_plancher_RELEVE_mais_n_ECRASE_jamais_le_modele():
    """A floor picks up what is missing; it does not replace what is already there."""
    phrase = "un cache, mais pas maintenant, c'est quand je serai sur les perfs"
    # The model managed to return the `quand`: it is ITS OWN that stays.
    du_modele = I.lire_rangement('{"quand": "à la phase de performance"}', texte=phrase)
    assert du_modele["quand"] == "à la phase de performance"
    # The model missed it: the code sets it.
    sans = I.lire_rangement('{"genre": "tache"}', texte=phrase)
    assert sans["quand"] == "quand je serai sur les perfs"


def test_sans_le_texte_le_plancher_ne_peut_pas_jouer():
    """A caller that does not pass the sentence only gets what the model returned - and this is
    stated, rather than letting it seem like the floor always protects."""
    assert "quand" not in I.lire_rangement('{"genre": "tache"}')


def test_le_socle_ORDONNE_d_utiliser_les_connexes():
    """This block used to say "only repeat it if it's useful", and the model concluded it
    was never useful: asked "is there something I said about this?" it would answer "sure, let me
    look it up", even though the answer was right in front of it. An instruction that leaves a
    small model to ARBITRATE, it arbitrates badly."""
    texte = I.socle(connexes=[{"resume": "le cache des embeddings", "depose_le": "2026-08-04"}])
    assert "never offer to go and look it up" in texte


# -- Splitting a message into several notes ----------------------------------------------------
#
# Requirement: a large message covering many distinct subjects must not collapse into a single
# task - each distinct subject deserves its own note, filed properly by the system rather than
# left for the operator to untangle later.


def test_un_message_a_TROIS_sujets_rend_TROIS_notes():
    brut = """```json
{"items": [
 {"texte": "faut que je rappelle le comptable", "resume": "Rappeler le comptable",
  "genre": "tache", "horizon": "todo", "sujets": ["comptable"], "quand": null},
 {"texte": "le cache des embeddings d'Acme Research", "resume": "Mettre un cache sur les embeddings",
  "genre": "projet", "horizon": "deadline", "sujets": ["research"], "quand": "quand je serai sur les perfs"},
 {"texte": "un LLM c'est un enhancer pas un outil magique", "resume": "Un LLM est un enhancer",
  "genre": "regle", "horizon": "routine", "sujets": ["llm"], "quand": null}
]}
```"""
    notes = I.lire_extraction(brut)
    assert len(notes) == 3
    assert [n["genre"] for n in notes] == ["tache", "projet", "regle"]
    assert notes[1]["quand"] == "quand je serai sur les perfs"


def test_le_texte_reste_SES_mots_le_resume_est_celui_de_l_intendant():
    """The two live side by side: it must always be possible to get back to what they said.

    NOTE: the French example content below (`texte`/`resume`
    values) recurs across this and several following tests and, in a few of them, must line up
    with the French-only `situation_differee` trigger phrases exercised later in the same section;
    left untranslated for internal consistency rather than translating some occurrences and not
    others."""
    brut = '{"items": [{"texte": "faut que je rappelle le comptable", "resume": "Rappeler le comptable"}]}'
    note = I.lire_extraction(brut)[0]
    assert note["texte"] == "faut que je rappelle le comptable"
    assert note["resume"] == "Rappeler le comptable"


def test_un_message_a_UN_sujet_rend_UNE_note():
    """No artificial splitting: the goal is to reflect the message, not to chop it up."""
    assert len(I.lire_extraction('{"items": [{"texte": "un seul truc"}]}')) == 1


def test_rien_a_retenir_rend_une_liste_VIDE():
    """A question or a greeting must not manufacture a task."""
    assert I.lire_extraction('{"items": []}') == []


def test_une_reponse_ILLISIBLE_rend_une_liste_vide_sans_lever():
    """And the caller MUST treat this emptiness as "lose nothing": the original dump
    then stays visible, rather than disappearing in favor of nothing."""
    for brut in ("le modèle a raconté n'importe quoi", '{"items": "pas une liste"}', "{}", ""):
        assert I.lire_extraction(brut) == []


def test_les_items_vides_sont_jetes_pas_transformes_en_notes_creuses():
    brut = '{"items": [{"texte": "", "resume": ""}, {"texte": "  "}, {"texte": "du vrai"}]}'
    assert [n["texte"] for n in I.lire_extraction(brut)] == ["du vrai"]


def test_un_item_sans_texte_mais_avec_resume_survit():
    """The model sometimes forgets to copy the excerpt back. The reworded note is better than
    nothing."""
    assert I.lire_extraction('{"items": [{"resume": "Rappeler le comptable"}]}')[0]["texte"] == (
        "Rappeler le comptable"
    )


def test_le_nombre_de_notes_tirees_est_BORNE():
    """A large message can legitimately carry ten things; beyond that it is the model looping
    out of control, and twelve bogus notes would drown out the real ones."""
    items = ",".join(f'{{"texte": "chose {i}"}}' for i in range(30))
    assert len(I.lire_extraction('{"items": [' + items + "]}")) == 10


def test_le_PLANCHER_du_differe_joue_sur_chaque_extrait():
    """The code re-reads the situation in the operator's own words when the model missed it for
    this item."""
    brut = '{"items": [{"texte": "un cache, mais pas maintenant, c\'est quand je serai sur les perfs"}]}'
    assert I.lire_extraction(brut)[0]["quand"] == "quand je serai sur les perfs"


def test_l_invite_demande_bien_UNE_ENTREE_PAR_CHOSE():
    """The instruction that carries the whole behavior: if it disappears, the splitting dies in
    silence and things fall back to one note per message with no test turning red."""
    texte = I.invite_extraction("bla")
    assert "ONE entry per distinct thing" in texte
    assert "If he talks about five subjects, return five entries" in texte
    assert "actionable" in texte


# -- Splitting a LARGE message into tasks to handle ONE AT A TIME -----------------------------------
#
# Requirement: a large message asking for many different things must be split into
# separate conversational turns, since a small model struggles to reliably handle many tasks at
# once. Different from the splitting above: this one writes NOTHING to the store, it builds
# conversation TURNS, handled one by one.


def test_un_message_a_deux_demandes_rend_deux_taches_dans_l_ordre():
    brut = """```json
{"taches": [
  "faut que je rappelle le comptable avant vendredi",
  "aussi, est-ce que tu peux checker où en est Acme Research ?"
]}
```"""
    assert I.lire_decoupage(brut) == [
        "faut que je rappelle le comptable avant vendredi",
        "aussi, est-ce que tu peux checker où en est Acme Research ?",
    ]


def test_une_demande_repartie_dans_le_message_reste_une_SEULE_tache():
    """Requirement: a single request that the operator brings up at the start, then again in the
    middle and at the end of a message, must be copy-pasted back verbatim as ONE task, not
    re-fragmented into several. The model already assembles the passages in ITS OWN extract - it
    is the reader that must not re-split them."""
    brut = '{"taches": ["passage du début + passage du milieu + passage de la fin, assemblés"]}'
    assert I.lire_decoupage(brut) == [
        "passage du début + passage du milieu + passage de la fin, assemblés"
    ]


def test_une_seule_demande_dans_tout_le_message_rend_une_seule_tache():
    brut = '{"taches": ["le message entier, une seule chose à faire"]}'
    assert I.lire_decoupage(brut) == ["le message entier, une seule chose à faire"]


def test_un_decoupage_rate_retombe_sur_le_message_ENTIER_jamais_sur_rien():
    """A failed split must cost "one turn instead of N", never "the message disappears": the
    same guarantee as the model-free deposit, applied here to splitting."""
    assert I.lire_decoupage(
        "Je n'ai pas compris.", source="le message original de l'operateur"
    ) == ["le message original de l'operateur"]
    assert I.lire_decoupage('{"n_importe": "quoi"}', source="son message") == ["son message"]
    assert I.lire_decoupage("", source="") == []


def test_les_taches_acceptent_aussi_la_forme_objet():
    """A small model sometimes returns `{"texte": "..."}` instead of a bare string - the same
    tolerance as `lire_extraction` for the same reason: demanding a single shape punishes an
    answer that is correct in substance."""
    brut = '{"taches": [{"texte": "un objet plutôt qu\'une chaîne"}, "une chaîne normale"]}'
    assert I.lire_decoupage(brut) == ["un objet plutôt qu'une chaîne", "une chaîne normale"]


def test_le_nombre_de_taches_est_BORNE():
    items = ",".join(f'"tâche {i}"' for i in range(30))
    assert len(I.lire_decoupage('{"taches": [' + items + "]}")) == 12


def test_l_invite_de_decoupage_demande_le_copier_coller_mot_pour_mot():
    texte = I.invite_decoupage("bla")
    assert "copy-pasted word for word" in texte or "COPY-PASTE" in texte
    assert "Identify each DISTINCT" in texte


# -- Grouping - structuring directly into fields ready to file --------------------------------
#
# Requirement: turning a big request into conversation turns risks falling back into full
# conversation, where the model can choose to NARRATE instead of calling the tool. Grouping
# structures each task directly into a single call, for a deposit in CODE afterward
# (`_deposer_groupes`, serve.py) - these tests defend the READER of this structure, not the
# deposit itself (which lives outside this repo, § serve.py).


def test_lire_groupement_rend_les_champs_structures():
    brut = (
        '{"groupes": [{"titre": "UI Mnemosyne", "sous_taches": ["a", "b"], '
        '"section": "todo", "echeance": "", "description": "some context", '
        '"parent_titre": "Mnemosyne"}]}'
    )
    assert I.lire_groupement(brut) == [
        {
            "titre": "UI Mnemosyne",
            "sous_taches": ["a", "b"],
            "section": "todo",
            "echeance": "",
            "description": "some context",
            "parent_titre": "Mnemosyne",
        }
    ]


def test_lire_groupement_un_groupe_qui_se_cite_lui_meme_comme_parent_est_ignore():
    """A model that attaches to its OWN title would create a loop -- refused at the source,
    before `_deposer_groupes` even has to detect it."""
    brut = '{"groupes": [{"titre": "X", "parent_titre": "x"}]}'  # different case, same title
    assert I.lire_groupement(brut)[0]["parent_titre"] == ""


def test_lire_groupement_sans_taches_rend_une_liste_VIDE_jamais_le_message_entier():
    """Unlike `lire_decoupage`, no fallback to the source message: a failed grouping must let
    the caller fall back to the classic split, not produce a phantom task."""
    assert I.lire_groupement("Je n'ai pas compris.") == []
    assert I.lire_groupement('{"groupes": []}') == []
    assert I.lire_groupement('{"n_importe": "quoi"}') == []


def test_lire_groupement_ecarte_un_groupe_sans_titre():
    brut = '{"groupes": [{"titre": "", "sous_taches": ["x"]}, {"titre": "valide"}]}'
    assert I.lire_groupement(brut) == [
        {
            "titre": "valide",
            "sous_taches": [],
            "section": "todo",
            "echeance": "",
            "description": "",
            "parent_titre": "",
        }
    ]


def test_lire_groupement_une_echeance_hors_deadline_est_ecartee():
    brut = '{"groupes": [{"titre": "x", "section": "todo", "echeance": "2026-08-15"}]}'
    assert I.lire_groupement(brut)[0]["echeance"] == ""


def test_lire_groupement_une_section_inventee_retombe_sur_todo():
    brut = '{"groupes": [{"titre": "x", "section": "n_importe_quoi"}]}'
    assert I.lire_groupement(brut)[0]["section"] == "todo"


def test_le_nombre_de_groupes_est_BORNE():
    items = ",".join(f'{{"titre": "groupe {i}"}}' for i in range(30))
    assert len(I.lire_groupement('{"groupes": [' + items + "]}")) == 12


def test_l_invite_de_groupement_demande_les_champs_de_poser_tache():
    texte = I.invite_groupement("bla")
    assert "sous_taches" in texte
    assert "section" in texte
    assert "Identify each DISTINCT" in texte
