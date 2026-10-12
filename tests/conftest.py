"""Suite-wide barrier: **no test may write into the protected configuration zone** (SE4).

The policy pipeline can write during approval, so every test must use an injected target rather than
the canonical ``system/config/policy.toml``. A test that reaches the protected zone would corrupt
versioned configuration without an intentional change.

So the guarantee is structural instead of remembered: every test is fingerprinted against the zone
before and after it runs, and the one that mutates it FAILS, by name. This catches the whole class
(any test, any verb, any future writer), not the one case that was found.

``stat`` rather than a content hash on purpose: every writer in this repo replaces atomically
(``tmp.replace``), which always yields a fresh inode and mtime - so identical-content rewrites are
caught too, while keeping the fixture inexpensive.

Decisions: SE4 / D102 (the zone is privileged and read-only to agents)  -  D159 (the human gesture is
the only legitimate writer)  -  invariant 2 (nothing here deletes; it only refuses).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
PROTECTED_ZONE = _REPO_ROOT / "system" / "config"

# A whole FILE is the wrong unit when the fixture gap is a SINGLE witness, and the file-grained
# list that used to sit above proved it: lifting its skip showed 644 tests hidden, of which only a
# handful could not run. Measured again at 05:00, on the seven files it still covered:
#
#     495 passing checks hidden  +  80 failing  +  8 skipped
#
# That `80` is INHERITED from that 05:00 pass and was NOT re-measured here; what WAS re-measured
# is the exemption list itself (below). The failures it does not cover are ordinary breakage the
# file-grained skip was hiding from everyone - they are red now, on purpose, because a red
# nobody can see is worse than a red somebody must fix.
#
# ==============================================================================================
# 2026-09-09, RE-MEASURED IN FULL - AND THE LIST WAS LYING ABOUT ITSELF IN TWO WAYS.
# ==============================================================================================
# The header here used to read "only the 15 named below". Counted by parsing this file instead of
# by reading its prose: there were **16**. A number written by hand beside a list it does not
# compute drifts from it silently - so the count is no longer written here at all. It is FROZEN in
# `tests/orchestration/test_plan_format.py`
# (`test_the_suites_own_EXEMPTION_lists_are_FROZEN_and_every_name_still_EXISTS`), in a DIFFERENT
# file, so editing one side without the other reddens instead of rotting.
#
# Second lie, the one that changes the remedy: the block below used to claim that every entry
# "cites a governance document this distribution does not carry (CONSTITUTION.md, docs/governance/,
# the repo's own living plan)" and that "each was confirmed by its failure message naming the absent
# document". Each of the 16 was then RUN with the skip stripped, and its real failure READ. Result:
#
#     7 really do name an absent governance / living-plan document  -> _ABSENT_GOVERNANCE_DOCUMENT
#     7 fail for another reason entirely                            -> _DOCS_TREE_SUBSET
#     1 needed no exemption at all: it PASSES                       -> removed
#     1 is required BY ITS OWN DOCSTRING to stay red                -> removed
#
# Five of those seven were inside the block that claimed each failure "names the absent document":
# three name NO document at all (they fail on a FLOOR - `4 >= 8`, `0 >= 4`), and two name
# `docs/FIN-DE-SESSION.md`, which is an operating document, not governance. The distinction is not
# cosmetic: a governance exemption dies the day the document ships, a subset exemption dies the day
# the shipped `docs/` tree grows. They are re-measured on different triggers, so they are two lists.
#
# A list of exemptions rots exactly like any register: re-measure it whenever the other arc says it
# repaired something, and never trust that only the entry they NAMED has moved - of the four found
# in the previous pass, they had named ONE; of the two found in this one, nobody had named either.
#
# ONE entry exempts ONE check, and it says why - the TRUE why, read off its own failure, never
# inferred from the fact that it failed. Regenerate both lists with a trylast plugin that strips the
# marker (never `touch CONSTITUTION.md`: that changes collection for every other process while it
# exists):
#
#     PYTHONPATH=<dir> pytest <files> -q -p no:cacheprovider -p degel


#: Their failure message NAMES a document this distribution does not ship, and that document is
#: `CONSTITUTION.md`, something under `docs/governance/`, or the repo's own living plan
#: (`docs/PLAN.md` and its `docs/plan/` arcs). This exemption dies the day the document ships.
_ABSENT_GOVERNANCE_DOCUMENT = frozenset(
    {
        # FileNotFoundError on `docs/governance/DERIVE.md`.
        "tests/orchestration/test_plan_format.py"
        "::test_DERIVE_md_rend_la_main_vers_les_VRAIES_commandes_de_derive_projet",
        # `versioned witnesses absent from disk: ['docs/governance/PLAN_INCARNATION.md']`.
        "tests/orchestration/test_plan_format.py"
        "::test_the_CONTROL_corpus_cannot_be_EMPTIED_in_silence",
        # `docs/PLAN.md` is absent, so the living plan reads back as state='absent', reading=None.
        "tests/orchestration/test_plan_format.py"
        "::test_on_the_real_plan_a_PARKED_item_carries_the_reason_it_is_parked",
        # Same absent `docs/PLAN.md`, same unreadable reading.
        "tests/orchestration/test_plan_format.py"
        "::test_the_repos_own_living_plan_is_read_and_is_MOSTLY_PROSE",
        # FileNotFoundError on `docs/plan/00-le-socle-du-plan.md`, an arc of that living plan.
        "tests/orchestration/test_plan_format.py"
        "::test_the_six_fields_are_read_off_THIS_repos_own_arc_and_not_only_off_a_fixture",
        # `docs no longer carries any plan door (PLAN.md, PLAN_COURANT.md)` - the same absent plan.
        "tests/orchestration/test_plan_registry.py"
        "::test_scan_plans_SEES_the_repos_own_plan_which_can_never_live_under_projects",
        # FileNotFoundError on `CONSTITUTION.md`, which this distribution does not ship.
        "tests/test_invariants.py::test_constitution_section_5_matches_the_registered_invariants",
    }
)

#: A DIFFERENT cause, and therefore a different remedy: these do NOT hang on one absent governance
#: document. They walk the `docs/` tree, or carry a FLOOR over it, and this distribution ships a
#: 4-document subset of it (`git ls-files docs/` -> FORMAT_PLAN.md, parentheses/, postes/,
#: signalements/). So they measure an incomplete corpus rather than a defect, and no single file
#: would clear them - only a larger shipped `docs/` would. RE-MEASURE THIS LIST WHENEVER THE SHIPPED
#: `docs/` TREE GROWS, which is a different trigger from the list above.
_DOCS_TREE_SUBSET = frozenset(
    {
        # NOT governance: the 16 frozen VERSIONED_WITNESSES are all absent here, and 11 of the 16 are
        # ordinary `docs/` files (README, BANC_MODELES, veille/, moissons/, besoins/, archive/, ...).
        "tests/orchestration/test_plan_format.py"
        "::test_the_VERSIONED_half_of_the_population_is_walked_and_it_is_named_not_counted",
        # NOT governance, and it names NO document: a FLOOR, `only 4 real judgeable document(s)`,
        # `assert 4 >= 8`. The shipped `docs/` tree is simply half the size the floor expects.
        "tests/orchestration/test_plan_format.py"
        "::test_the_index_check_really_FIRES_on_this_repo_and_fires_ONLY_inside_a_DOOR",
        # NOT governance, names NO document: the same `assert 4 >= 8` floor, one function over.
        "tests/orchestration/test_plan_format.py"
        "::test_the_two_numbers_are_stated_TOGETHER_and_neither_can_be_read_alone",
        # Its fixture IS the repo: it globs `docs/postes/chat-*.md` and needs at least 3 seats.
        # MEASURED, not assumed - and measured through GIT, because `ls` answers about the author's
        # disk while a clone only ever receives what git carries. RE-MEASURED 2026-09-09: the folder
        # `docs/postes/README.md` is now TRACKED here (the previous note recorded `-> 0` and asked
        # for exactly this re-measurement), but the seats it needs are `chat-*.md` files, of which
        # git carries **0** - so `assert 0 >= 3` still fails, and now for a reason stated correctly.
        # A red that can never go green in a clone teaches a reader nothing.
        "tests/orchestration/test_ui_contract.py"
        "::test_qui_le_tient_survit_a_la_PROSE_REELLE_des_VRAIS_postes",
        # NOT governance: FileNotFoundError on `docs/FIN-DE-SESSION.md`, an operating document of
        # the private repo, outside `docs/governance/` and outside the living plan.
        "tests/platform/test_bilan.py::test_le_vrai_bilan_existe_et_porte_ses_deux_bornes",
        # NOT governance: the same absent `docs/FIN-DE-SESSION.md`.
        "tests/platform/test_bilan.py::test_verifier_ne_touche_a_rien",
        # It needs at least 10 FROZEN dead links under `docs/archive/` to prove the judge resolves
        # anything; this distribution ships no `docs/archive/` at all, so it finds 0. Its passing
        # sibling (`..._ne_porte_AUCUN_lien_mort_hors_archive`) needs no exemption and has none.
        "tests/platform/test_documents.py"
        "::test_liens_le_juge_MORD_sur_le_depot_REEL_sinon_le_vert_ne_prouve_rien",
    }
)

# ----------------------------------------------------------------------------------------------
# REMOVED 2026-09-09, and named here rather than deleted in silence - what covers them instead:
#
#   tests/platform/test_documents.py::test_liens_le_DEPOT_REEL_ne_porte_AUCUN_lien_mort_hors_archive
#       It PASSES in this distribution (run with the skip stripped: `1 passed`). It was exempted as
#       a pair with its sibling above, on the sibling's evidence. An exemption that shelters a green
#       test removes it from judgment for nothing, and hides the day it starts failing. Nothing
#       needs to cover it: it is simply judged again, like every other check.
#
#   tests/platform/test_derives.py::test_les_INNOCENTS_du_depot_REEL_sont_bien_LA_sinon_le_vert_...
#       Its own docstring decides this, in writing: "RED IN THIS DISTRIBUTION, AND DELIBERATELY LEFT
#       RED [...] The floor of 4 is NOT lowered and the witness is NOT skipped, because both would
#       turn a real gap into a green." The exemption silently overruled a decision written into the
#       code it was exempting. What covers it instead is what that docstring already names: the
#       fabricated-text control `test_les_ETIQUETTES_de_sous_decision_ne_sont_JAMAIS_accusees` still
#       proves the judge DISCRIMINATES, while this red keeps saying, out loud, that the shipped
#       corpus no longer exercises it. THIS IS A DELIBERATE RED, and it is the only one this pass
#       adds. Full suite, MEASURED before and after by SET DIFF of the failing node ids, not by
#       their count: 137 -> 135 failing. This entry is the single arrival; the three departures
#       are the PROJECT_WITNESSES checks repaired in `tests/orchestration/test_plan_format.py`.
# ----------------------------------------------------------------------------------------------

#: Kept for the file-grained case, and deliberately EMPTY: a whole file is almost never the right
#: unit (see the 495 hidden passing checks above). The public repository is a runnable template;
#: optional governance fixtures are deliberately not distributed, and their checks stay VISIBLE
#: rather than being presented as a product failure.
_OPTIONAL_GOVERNANCE_TESTS: frozenset[str] = frozenset()

#: The witnesses that measure THIS repository's own living corpus -- its plan (docs/PLAN.md,
#: docs/plan/), its arcs, its posts, its needs channel, its reports ledger, its commit journal.
#: The public distribution deliberately ships none of it: the corpus is the operator's working
#: material, not the engine. These checks therefore have nothing to read here, and several of them
#: SAY SO in their own refusal ("zero arcs would be an instrument failure, never a green") -- they
#: are right to refuse, and that is why they are skipped rather than deleted or weakened.
#:
#: HOW THIS LIST WAS BUILT, and it is the only thing that makes it defensible. Every entry was
#: RE-RUN, by node id, in the repository that DOES ship the corpus. Measured 2026-09-09:
#:     120 ids common to both repositories       ->  118 pass there, 2 fail there
#:       7 ids exist only here (sanitisation renames) ->  6 pass there, 1 fails there
#: Only the 124 that pass with the corpus present are listed below. The 3 that fail on BOTH sides
#: are deliberately NOT here -- a failure that survives the corpus is a defect, and burying it is
#: exactly what a long exemption list is good at:
#:     tests/orchestration/test_plan_gate_emit.py::test_FAIL_CLOSED_gagne_quand_racine_CASSEE_ET_aucun_plan_a_la_fois
#:     tests/orchestration/test_plan_gate_emit.py::test_FAIL_CLOSED_un_PYTHONPATH_casse_BLOQUE_le_commit
#:     tests/orchestration/test_plan_format.py::test_NO_real_item_declares_a_field_BEFORE_its_canonical_declaration
#:
#: The whole list is inert the moment the corpus IS shipped: pytest_collection_modifyitems returns
#: before applying any skip when CONSTITUTION.md exists. The predicate is a FACT about the
#: repository, never a property of the failure -- an exemption justified by the defect's own
#: symptom certifies the escape it is meant to prevent.
_LIVING_CORPUS_WITNESSES = frozenset(
    {
        "tests/identity/test_self_model.py"
        "::test_choix_du_modele_card_addresses_a_doc_that_REALLY_EXISTS",
        "tests/orchestration/test_a_lire.py"
        "::test_le_REEL_du_plan_est_gele",
        "tests/orchestration/test_a_lire.py"
        "::test_le_bare_filename_C4_lui_meme_est_NON_resolu_sans_deviner",
        "tests/orchestration/test_a_lire.py"
        "::test_le_gabarit_reel_isole_le_SEUL_bare_vraiment_introuvable_du_plan",
        "tests/orchestration/test_attribution.py"
        "::test_le_VRAI_plan_rend_des_arcs_et_des_arcs_FINIS",
        "tests/orchestration/test_attribution.py"
        "::test_les_VRAIS_postes_se_lisent_SANS_degradation",
        "tests/orchestration/test_avancement.py"
        "::test_le_CAS_PASSANT_le_plan_reel_rend_rc_0_et_imprime_la_louche",
        "tests/orchestration/test_avancement.py"
        "::test_le_plan_REEL_de_ce_depot_se_lit_et_declare_une_MAJORITE_d_items_sans_poids",
        "tests/orchestration/test_avancement.py"
        "::test_un_dossier_INEXISTANT_rend_rc_2_et_dit_que_ce_n_est_PAS_zero_pourcent",
        "tests/orchestration/test_besoins.py"
        "::test_le_canal_REEL_de_ce_depot_existe_et_porte_son_contrat",
        "tests/orchestration/test_besoins.py"
        "::test_le_canal_REEL_porte_au_moins_UN_besoin_et_il_est_LISIBLE",
        "tests/orchestration/test_besoins.py"
        "::test_le_compteur_pour_le_tick_voit_le_canal_REEL",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_le_VRAI_plan_du_projet_voisin_168_etapes_contre_10000_a_10_pourcent",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.23-14]",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.23-4]",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.23-8]",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.55-14]",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.55-4]",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.55-8]",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.86-14]",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.86-4]",
        "tests/orchestration/test_carte.py"
        "::test_LA_CLAUSE_sur_TOUT_le_DOMAINE_le_pire_cas_decide[0.86-8]",
        "tests/orchestration/test_carte.py"
        "::test_POUR_UN_AUTRE_PROJET_derive_et_routage_se_TAISENT_pas_les_chiffres_de_MNEMOSYNE",
        "tests/orchestration/test_carte.py"
        "::test_SANS_POUR_derive_et_routage_continuent_de_rendre_MNEMOSYNE_cas_passant",
        "tests/orchestration/test_carte.py"
        "::test_la_LIGNE_des_arcs_tient_sur_UNE_ligne_sur_les_deux_plans_REELS",
        "tests/orchestration/test_carte.py"
        "::test_le_BORD_dessine_l_arbre_ENTIER_et_le_DIT",
        "tests/orchestration/test_carte.py"
        "::test_le_BORD_lit_la_declaration_et_NOMME_une_peremption_PERIMEE",
        "tests/orchestration/test_carte.py"
        "::test_le_NIVEAU_ARC_est_JUSTE_sur_les_DEUX_formes_de_plan",
        "tests/orchestration/test_carte.py"
        "::test_le_REEL_confirme_la_clause_reparee_un_seul_item_hors_du_courant",
        "tests/orchestration/test_carte.py"
        "::test_le_VRAI_plan_ne_GROSSIT_pas_au_dela_de_la_fixture_de_10000",
        "tests/orchestration/test_carte.py"
        "::test_le_bord_rend_la_carte_du_VRAI_depot",
        "tests/orchestration/test_carte.py"
        "::test_le_depot_porte_sa_SURFACE_de_declaration",
        "tests/orchestration/test_carte.py"
        "::test_le_fichier_LIVRE_ne_declare_AUCUNE_peremption",
        "tests/orchestration/test_carte.py"
        "::test_un_SOUS_PLAN_illisible_est_NOMME_et_le_compte_dit_qu_il_l_exclut",
        "tests/orchestration/test_disjoncteur.py"
        "::test_items_du_plan_descend_dans_les_SOUS_PLANS",
        "tests/orchestration/test_disjoncteur.py"
        "::test_le_VRAI_plan_de_ce_depot_est_lisible_et_NON_VIDE",
        "tests/orchestration/test_disjoncteur.py"
        "::test_le_disjoncteur_MORD_sur_le_VRAI_depot",
        "tests/orchestration/test_fermeture_declaree.py"
        "::test_mesurer_lit_un_VRAI_commit_du_depot",
        "tests/orchestration/test_fermeture_declaree.py"
        "::test_rc_0_sur_le_VRAI_commit_ou_les_deux_moities_s_ACCORDENT",
        "tests/orchestration/test_fermeture_declaree.py"
        "::test_rc_1_sur_le_VRAI_commit_qui_BASCULE_sans_declarer",
        "tests/orchestration/test_fermeture_declaree.py"
        "::test_rc_1_sur_le_VRAI_commit_qui_DECLARE_sans_basculer",
        "tests/orchestration/test_fermeture_isolee.py"
        "::test_fermetures_solitaires_sur_le_REEL_B2_est_NOMME",
        "tests/orchestration/test_livrables.py"
        "::test_la_PREVISUALISATION_montre_la_commande",
        "tests/orchestration/test_livrables.py"
        "::test_le_CABLAGE_ne_LEVE_pas_sur_un_fichier_illisible",
        "tests/orchestration/test_livrables.py"
        "::test_le_REEL_du_plan_de_MNEMOSYNE_n_orpheline_AUCUN_item",
        "tests/orchestration/test_livrables.py"
        "::test_le_SEUL_precedent_du_depot_se_lit",
        "tests/orchestration/test_livrables.py"
        "::test_le_gabarit_porte_la_MESURE_qui_le_justifie",
        "tests/orchestration/test_lot_emit.py"
        "::test_la_borne_traverse_REELLEMENT_la_CLI_pas_seulement_la_fonction",
        "tests/orchestration/test_lot_emit.py"
        "::test_le_REEL_du_plan_est_gele_ZERO_recouvrement",
        "tests/orchestration/test_lot_emit.py"
        "::test_le_bord_ASSEMBLE_et_REUSSIT_quand_TOUS_les_OUT_existent",
        "tests/orchestration/test_lot_emit.py"
        "::test_le_bord_EMET_un_mandat_reel_rc_0",
        "tests/orchestration/test_lot_emit.py"
        "::test_le_bord_NOMME_le_lot_manquant_pas_juste_un_compte",
        "tests/orchestration/test_lot_emit.py"
        "::test_le_bord_REFUSE_un_arc_inexistant_rc_2",
        "tests/orchestration/test_lot_emit.py"
        "::test_le_bord_emet_puis_REFUSE_tant_qu_un_OUT_manque",
        "tests/orchestration/test_obligation.py"
        "::test_le_VRAI_registre_est_coherent_avec_le_VRAI_Makefile",
        "tests/orchestration/test_obligation_run.py"
        "::test_la_population_REELLE_distingue_les_QUATRE_etats_et_C1_est_HORS_SCOPE",
        "tests/orchestration/test_obligation_run.py"
        "::test_le_JUGE_lui_meme_tourne_sur_la_population_REELLE_pas_seulement_le_lecteur",
        "tests/orchestration/test_orchestration.py"
        "::test_borne_chats_REJOUE_sur_le_VRAI_plan_de_Mnemosyne_colle_a_l_usage_REEL",
        "tests/orchestration/test_orchestration_run.py"
        "::test_le_bord_rend_la_borne_du_VRAI_depot",
        "tests/orchestration/test_orphelins_run.py"
        "::test_POSTE_PAR_PARTIE_porte_les_QUATRE_fichiers_REELS",
        "tests/orchestration/test_orphelins_run.py"
        "::test_sur_le_REEL_delegations_py_est_DESORMAIS_declare_par_ORCHESTRATEUR",
        "tests/orchestration/test_passation.py"
        "::test_la_mesure_se_PREND_vraiment_sur_le_depot_REEL",
        "tests/orchestration/test_passation.py"
        "::test_le_filtre_des_PARQUES_est_celui_du_hook_Stop_sur_une_population_FABRIQUEE",
        "tests/orchestration/test_passation.py"
        "::test_rc_1_SUR_PAROLE_sur_le_depot_REEL",
        "tests/orchestration/test_perimetre.py"
        "::test_le_COMPTE_du_depot_est_gele_A_PART",
        "tests/orchestration/test_perimetre.py"
        "::test_le_REEL_du_depot_est_gele",
        "tests/orchestration/test_plan_archive.py"
        "::test_les_bornes_de_section_sont_celles_du_lecteur_de_plans",
        "tests/orchestration/test_plan_convert.py"
        "::test_le_VRAI_plan_du_depot_se_reconstruit_octet_pour_octet",
        "tests/orchestration/test_plan_format.py"
        "::test_THIS_plans_own_arc_passes_the_level_2_barrier_it_invents",
        "tests/orchestration/test_plan_format.py"
        "::test_how_many_DECLARATIONS_the_corpus_REALLY_carries_and_each_sits_in_a_DOOR",
        "tests/orchestration/test_plan_format.py"
        "::test_the_REAL_door_of_this_repo_DECLARES_every_arc_it_owns_and_never_merely_MENTIONS_them",
        "tests/orchestration/test_plan_format.py"
        "::test_the_arc_floor_is_the_REAL_population_and_LOWERING_the_literal_reddens",
        "tests/orchestration/test_plan_format.py"
        "::test_the_gate_calls_the_PREDICATE_and_this_witness_confesses_its_limit",
        "tests/orchestration/test_plan_format.py"
        "::test_the_index_check_accuses_ZERO_of_the_repos_REAL_documents",
        "tests/orchestration/test_plan_format.py"
        "::test_the_index_check_answers_the_SAME_at_EVERY_SCALE[0 arcs]",
        "tests/orchestration/test_plan_format.py"
        "::test_the_level_2_barrier_is_ARMED_and_the_gate_really_READS_it",
        "tests/orchestration/test_plan_format.py"
        "::test_the_living_plan_keeps_NO_bullet_that_declares_a_glyph_and_ends_in_SILENCE",
        "tests/orchestration/test_plan_format.py"
        "::test_the_two_halves_agree_on_the_REAL_lines_of_this_repo_and_BOTH_SIDES_are_stated",
        "tests/orchestration/test_plan_format.py"
        "::test_the_versioned_corpus_ALSO_pins_the_ceiling_so_the_guarantee_is_not_owner_only",
        "tests/orchestration/test_plan_mandat_run.py"
        "::test_le_mandat_derive_publie_reellement_sur_CE_depot",
        "tests/orchestration/test_plan_ordre.py"
        "::test_RIEN_ne_sort_de_la_file_sans_etre_NOMME",
        "tests/orchestration/test_plan_ordre.py"
        "::test_router_sur_MNEMOSYNE_les_items_a_barriere_LOURDE_atterrissent_chez_le_chat_d_arc",
        "tests/orchestration/test_plan_recul_run.py"
        "::test_depot_absent_rend_None_jamais_une_liste_devinee",
        "tests/orchestration/test_plan_test_a_trois.py"
        "::test_chaque_item_repond_au_test_a_trois",
        "tests/orchestration/test_plan_test_a_trois.py"
        "::test_chaque_reponse_est_un_verdict_valide",
        "tests/orchestration/test_plan_test_a_trois.py"
        "::test_le_plan_porte_encore_ses_items",
        "tests/orchestration/test_plans_run.py"
        "::test_ecart_NOMME_une_porte_qui_DECLARE_MAIS_N_EST_PAS_gelee_et_NE_REFUSE_PAS",
        "tests/orchestration/test_plans_run.py"
        "::test_ecart_est_VIDE_quand_toute_porte_declarante_est_DEJA_gelee",
        "tests/orchestration/test_plans_run.py"
        "::test_sabotage_UNE_PORTE_QUI_QUITTE_LE_GEL_fait_APPARAITRE_l_ecart",
        "tests/orchestration/test_routage_journal_run.py"
        "::test_sur_le_REEL_le_correctif_du_TIRET_recupere_des_commits_MNEMOSYNE_aussi",
        "tests/orchestration/test_routage_journal_run.py"
        "::test_sur_le_REEL_le_journal_rend_AU_MOINS_10_items_mesures",
        "tests/orchestration/test_routage_journal_run.py"
        "::test_sur_le_REEL_les_quatre_cases_sont_publiees_par_make_carte",
        "tests/orchestration/test_tick.py"
        "::test_run_tick_surfaces_les_candidats_retenus_sans_epreuve",
        "tests/platform/test_accord_chiffre.py"
        "::test_la_population_reelle_porte_des_enregistrements_DATES_qu_on_epargne",
        "tests/platform/test_arsenal.py"
        "::test_la_surface_sur_le_vrai_depot_sort_zero",
        "tests/platform/test_arsenal.py"
        "::test_le_vrai_makefile_et_la_vraie_table_se_recouvrent",
        "tests/platform/test_arsenal.py"
        "::test_les_regles_dures_restent_dans_claude_md_et_pas_dans_l_arsenal",
        "tests/platform/test_batterie.py"
        "::test_le_CAS_PASSANT_de_PRODUCTION_les_DEUX_gels_tiennent_sur_le_depot_REEL",
        "tests/platform/test_bilan.py"
        "::test_les_compteurs_prennent_les_MEMES_chemins_que_le_tick",
        "tests/platform/test_bilan.py"
        "::test_verifier_refuse_une_date_qui_n_est_pas_celle_du_fichier",
        "tests/platform/test_cloture_signalements.py"
        "::test_chaque_entree_du_cliquet_designe_un_RAPPORT_qui_existe",
        "tests/platform/test_cloture_signalements.py"
        "::test_la_RACINE_de_production_designe_le_DEPOT_et_ses_signalements",
        "tests/platform/test_cloture_signalements.py"
        "::test_le_CAS_PASSANT_de_PRODUCTION_le_corpus_REEL_ne_rougit_pas",
        "tests/platform/test_derives.py"
        "::test_CLAUDE_md_du_depot_REEL_tient_son_gel",
        "tests/platform/test_derives.py"
        "::test_le_gel_du_poids_est_bien_CELUI_du_fichier_pas_un_nombre_decoratif",
        "tests/platform/test_derives.py"
        "::test_les_INNOCENTS_du_depot_REEL_sont_bien_LA_sinon_le_vert_ne_prouve_rien",
        "tests/platform/test_garde_shell.py"
        "::test_eprouve_sur_de_VRAIS_messages_de_commit_de_CE_depot",
        "tests/platform/test_garde_shell.py"
        "::test_le_MEME_backtick_MORD_quand_le_delimiteur_n_est_PAS_quote",
        "tests/platform/test_offre_aux_projets.py"
        "::test_le_DEPOT_REEL_adresse_chaque_capacite_offerte_AUJOURD_HUI",
        "tests/platform/test_offre_aux_projets.py"
        "::test_le_DEPOT_REEL_montre_la_forme_ATTEIGNABLE_dans_chaque_document",
        "tests/platform/test_plafond_rotation.py"
        "::test_le_perimetre_REEL_attrape_les_fichiers_REELLEMENT_suivis_par_git",
        "tests/platform/test_plafond_rotation.py"
        "::test_le_plafond_REEL_REFUSE_les_journaux_REELS_d_aujourd_hui",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_end_to_end_CYCLE_un_plan_sain_REEL_du_depot_n_est_jamais_refuse",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_end_to_end_CYCLE_une_dependance_circulaire_est_REFUSEE_puis_ACCEPTEE",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_end_to_end_D176_le_VRAI_plan_de_Mnemosyne_est_INCHANGE_par_la_declaration",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_end_to_end_D176_un_projet_HORS_Mnemosyne_peut_ADOPTER_un_sous_ensemble",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_end_to_end_H4_un_predecesseur_ILLISIBLE_refuse_plutot_que_de_se_taire",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_end_to_end_H4_une_promotion_qui_perd_un_item_est_REFUSEE_puis_ACCEPTEE",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_end_to_end_la_barriere_REFUSE_toujours_un_plan_ECRIT_A_LA_MAIN_qui_ment",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_end_to_end_un_plan_ECHAFAUDE_passe_la_barriere_du_PREMIER_coup",
        "tests/platform/test_pre_commit_plan_gate.py"
        "::test_the_refusal_REPORT_is_EXACTLY_these_lines",
        "tests/platform/test_recensement_des_passes.py"
        "::test_la_porte_REELLE_amputee_d_une_passe_est_REFUSEE",
        "tests/platform/test_recensement_des_passes.py"
        "::test_le_CAS_PASSANT_de_PRODUCTION_la_porte_REELLE_ne_rougit_pas",
        "tests/platform/test_recensement_des_passes.py"
        "::test_les_CINQ_marqueurs_geles_sont_ECRITS_dans_la_porte_REELLE",
    }
)


#: The two witness sets and the skip each one earns. Separate reasons, because `pytest -rs` is where
#: a reader learns which population left the judgment and why - a shared reason would put both
#: causes behind one sentence, which is the exact defect this pass repaired.
_WITNESS_EXEMPTIONS: tuple[tuple[frozenset[str], str], ...] = (
    (
        _ABSENT_GOVERNANCE_DOCUMENT,
        "requires a governance document this distribution does not ship "
        "(CONSTITUTION.md, docs/governance/, or the repo's own living plan docs/PLAN.md)",
    ),
    (
        _DOCS_TREE_SUBSET,
        "this distribution ships a 4-document subset of docs/; this check walks that tree or "
        "carries a floor over it, so it measures an incomplete corpus, not a defect",
    ),
    (
        _LIVING_CORPUS_WITNESSES,
        "measures this repository's OWN living corpus (plan, arcs, posts, needs, reports, commit "
        "journal), which this distribution deliberately does not ship -- each of these was re-run "
        "by node id in the repository that DOES ship it and passes there",
    ),
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip only checks whose fixture this distribution genuinely does not carry.

    Each set brings its OWN reason, so the skip NAMES the cause instead of hiding two different
    causes behind one sentence. A skip that does not say what is missing is a silent skip.
    """
    if (_REPO_ROOT / "CONSTITUTION.md").is_file():
        return
    file_skip = pytest.mark.skip(reason="requires optional governance fixtures")
    marks = {
        nodeid: pytest.mark.skip(reason=reason)
        for witnesses, reason in _WITNESS_EXEMPTIONS
        for nodeid in witnesses
    }
    for item in items:
        if item.nodeid.split("::", 1)[0] in _OPTIONAL_GOVERNANCE_TESTS:
            item.add_marker(file_skip)
        elif item.nodeid in marks:
            item.add_marker(marks[item.nodeid])


def _fingerprint() -> dict[str, tuple[int, int]]:
    """(size, mtime_ns) per file in the zone.

    A missing zone RAISES rather than returning ``{}``. That branch is where this barrier would go
    silently dead - move this file one directory and ``parents[1]`` stops naming the repo root, the
    fingerprints become two empty dicts, they compare equal, and every test passes while nothing is
    watched. `system/config/` is versioned, so in any real checkout it is there; its absence means
    the barrier lost its target, and a control that cannot see must fail, never shrug."""
    if not PROTECTED_ZONE.is_dir():
        raise AssertionError(
            f"the protected zone cannot be found at {PROTECTED_ZONE} - this barrier is no longer "
            "watching anything. Fix the path (tests/conftest.py) before running the suite."
        )
    marks: dict[str, tuple[int, int]] = {}
    for path in sorted(PROTECTED_ZONE.rglob("*")):
        if path.is_file():
            info = os.stat(path)
            marks[str(path.relative_to(_REPO_ROOT))] = (info.st_size, info.st_mtime_ns)
    return marks


@pytest.fixture(autouse=True)
def protected_zone_is_read_only() -> None:  # type: ignore[misc]
    """Fail the test that touched ``system/config/`` - naming the file, not just the fact."""
    before = _fingerprint()
    yield
    after = _fingerprint()
    if before == after:
        return
    touched = sorted(
        set(before) ^ set(after)
        | {name for name in set(before) & set(after) if before[name] != after[name]}
    )
    raise AssertionError(
        "this test wrote into the PROTECTED ZONE (SE4) - it belongs only to the human gesture "
        f"(D102/D159): {', '.join(touched)}. Inject a tmp_path instead of the "
        "canonical path (e.g. --policy-path)."
    )
