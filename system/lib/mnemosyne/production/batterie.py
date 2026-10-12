"""THE TEST BATTERY THAT CANNOT MELT AWAY (G4 candidate from the flagship project's harvest).

> *"An `OK` on an empty battery is the falsest green there is."*

## THE CONTEXT, MEASURED HERE (2026-09-08) — and it is worse than at the flagship project

```
/usr/bin/grep -cE "pytest|ruff|make test" .githooks/pre-commit   ->  0
git remote -v | wc -l                                            ->  0   (so `pre-push` NEVER
      fires; the hook admits it itself: "this hook normally never fires")
uv run pytest --collect-only -q | tail -1                        ->  (moves with every witness
      added: the number is not written here, it is PULLED — `make batterie` publishes it)
```

***Our test battery sits on NO automatic path.*** Nothing, nowhere, notices when it has melted
away. A test that turns red, gets skipped, or falls silent makes no one blush — because no one
pulls it, and because nothing judges its SHAPE.

## The four conditions, and what is settled here

* **failure / error** — refused. Judged on an INJECTED report (the edge can pull it from a real run).
* **skip** — a skip site **outside the freeze** is refused, and a frozen site that has **lost**
  its skip is refused too (the ratchet refuses in both directions). *No blanket refusal*:
  :func:`sites_de_saut` finds **42** of them in `tests/`, all legitimate (the flagship project's
  population gitignored, missing brick, platform) — a clause that refused every skip would refuse **every**
  run, and so would be disarmed the same day. A wider sweep (any `pytest.skip` call, including
  outside a `test_` function) counts **74**: the built-in reader is narrower than that sweep, and
  that is written here rather than discovered later.
* **silent test** — a test with **zero assertions** outside the freeze is refused. Measured by the
  built-in reader: **14 silent out of 4,232** test functions, all shaped like "the INNOCENT passes"
  / "DOES NOT RAISE" — they assert by *not raising*. A legitimate shape, so frozen, never forbidden.
* **empty battery** — zero tests collected is not a green: it is :attr:`Verdict.non_mesure`.

## WHAT IS **NOT** BUILT HERE, AND WHY (the register says so itself)

The flagship project's **fingerprint-frozen floor** (`PLANCHER_DE_TEMOINS`) **duplicates `make memoire`**, already
bidirectional (`Makefile:175`). *"So the net contribution is the THREE OTHER conditions and the
pure extraction of the verdict, never the ratchet."* So it is not rewritten here — that is a
measured refusal, not an oversight.

## The PURE extraction of the verdict

:func:`verdict` launches nothing, reads nothing, prints nothing: *it was deliberately extracted
from `main()` because a saboteur had survived inside it*. The edge (:mod:`mnemosyne.runtime.batterie_run`)
is the only thing that touches disk and the subprocess.

English prose in this public mirror (the private original follows D117: French prose, for its
operator).
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final

#: The grain of a witness: ``<relative path>::<function>`` — the shape of a pytest nodeid, the one
#: that survives a line move where a line number would turn red at every reformat.
SEPARATEUR: Final = "::"


@dataclass(frozen=True, slots=True)
class Rapport:
    """What one battery run produced — **injected**, never discovered here.

    ``collectes`` is the cardinal: *an empty battery yields `OK`*. ``echecs`` and ``erreurs`` carry
    the nodeids, never their count — *a count cannot be fixed, a line can*."""

    collectes: int = 0
    echecs: tuple[str, ...] = ()
    erreurs: tuple[str, ...] = ()
    #: The skip sites READ FROM SOURCE (static), not the skips observed at runtime: the freeze must
    #: hold without requiring a full battery run before every commit.
    sites_de_saut: tuple[str, ...] = ()
    muets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Verdict:
    """Everything is NAMED. Each cause has its own slot; no catch-all slot."""

    echecs: tuple[str, ...] = ()
    erreurs: tuple[str, ...] = ()
    sauts_neufs: tuple[str, ...] = ()
    sauts_disparus: tuple[str, ...] = ()
    muets_neufs: tuple[str, ...] = ()
    muets_disparus: tuple[str, ...] = ()
    collectes: int = 0
    tenus: tuple[str, ...] = field(default=())

    @property
    def non_mesure(self) -> bool:
        """Zero tests collected. *An `OK` on an empty battery is the falsest green there is*:
        it is distinct from a refusal AND distinct from a green."""
        return self.collectes == 0

    @property
    def refuse(self) -> bool:
        return bool(
            self.echecs
            or self.erreurs
            or self.sauts_neufs
            or self.sauts_disparus
            or self.muets_neufs
            or self.muets_disparus
        )


def verdict(
    rapport: Rapport,
    *,
    sauts_geles: frozenset[str],
    muets_geles: frozenset[str],
) -> Verdict:
    """The PURE judge — a report goes in, a verdict comes out. No disk, no subprocess.

    **BOTH RATCHETS REFUSE IN BOTH DIRECTIONS.** A site that stops being skipped, or a witness
    that gains an assertion, must LEAVE the freeze in the same gesture: *a loosened ratchet no
    longer clicks*, and the gain would be lost again with no red to say so."""
    sites = frozenset(rapport.sites_de_saut)
    muets = frozenset(rapport.muets)
    return Verdict(
        echecs=tuple(sorted(rapport.echecs)),
        erreurs=tuple(sorted(rapport.erreurs)),
        sauts_neufs=tuple(sorted(sites - sauts_geles)),
        sauts_disparus=tuple(sorted(sauts_geles - sites)),
        muets_neufs=tuple(sorted(muets - muets_geles)),
        muets_disparus=tuple(sorted(muets_geles - muets)),
        collectes=rapport.collectes,
        tenus=tuple(sorted((sites & sauts_geles) | (muets & muets_geles))),
    )


def message(v: Verdict) -> str:
    """The page — it **always** says how many it judged, and it names ALL the causes.

    Never the first alone: *a battery with two faults where only one is named sends someone to
    fix it, come back, and find another red.*"""
    if v.non_mesure:
        return (
            "\U000026A0\U0000FE0F BATTERY NOT MEASURED: zero tests collected. “no failures” and “nothing ran” "
            "do not read the same way — an `OK` on an empty battery is the falsest green there "
            "is."
        )
    lignes = [
        f"battery: {v.collectes} test(s) collected, {len(v.tenus)} frozen shape(s) held"
    ]
    causes = (
        (v.echecs, "test(s) FAILING", "fix them, or the battery has already melted"),
        (v.erreurs, "test(s) in ERROR", "a collection error hides an entire file"),
        (
            v.sauts_neufs,
            "SKIP site(s) outside the freeze",
            "a test that starts being skipped is a test that stopped biting: add it to "
            "`SAUTS_GELES` (`system/lib/mnemosyne/production/batterie.py`) with its reason, "
            "or remove the skip",
        ),
        (
            v.sauts_disparus,
            "frozen SKIP site(s) that no longer are",
            "REMOVE them from the freeze to bank the gain",
        ),
        (
            v.muets_neufs,
            "SILENT witness(es) outside the freeze",
            "a test with no assertion measures its own ability not to raise: add an "
            "assertion, or add it to `MUETS_GELES` "
            "(`system/lib/mnemosyne/production/batterie.py`) stating what it guarantees",
        ),
        (
            v.muets_disparus,
            "witness(es) frozen as silent that now assert",
            "REMOVE them from the freeze",
        ),
    )
    for noms, quoi, remede in causes:
        if noms:
            apercu = ", ".join(noms[:5]) + (
                f" (and {len(noms) - 5} more)" if len(noms) > 5 else ""
            )
            lignes.append(f"\U000026D4 {len(noms)} {quoi}: {apercu}. {remede}.")
    return "\n".join(lignes)


# --------------------------------------------------------------------------------------------
# THE TWO STATIC READERS — pure: they take text in, they return names.
# --------------------------------------------------------------------------------------------
#
# They live here, with the judge, not at the edge: they are RULES ("what is a silent test?"),
# and *a rule inside a module gets tested, a table inside a script only gets re-read*. The edge
# just hands them the text of each file.

_MOTS_D_ASSERTION: Final = ("raises", "warns", "approx", "fail", "assert")


def _asserte(fonction: ast.AST) -> bool:
    """Does this test body assert anything at all?

    **DELIBERATELY GENEROUS**: a bare `assert`, but also `pytest.raises`, `pytest.warns`,
    `pytest.fail`, `unittest.assertX`. Being strict here would cost false accusations against
    perfectly valid witnesses, and *a check that convicts innocents gets disarmed within the
    hour*. The trade-off is named: a test that calls a function named `assert_something` without
    checking anything would pass — that is the real limit of any static detector."""
    for n in ast.walk(fonction):
        if isinstance(n, ast.Assert):
            return True
        if isinstance(n, ast.Call):
            rendu = ast.dump(n.func).lower()
            if any(mot in rendu for mot in _MOTS_D_ASSERTION):
                return True
        if isinstance(n, ast.With | ast.AsyncWith):
            for item in n.items:
                rendu = ast.dump(item.context_expr).lower()
                if any(mot in rendu for mot in _MOTS_D_ASSERTION):
                    return True
    return False


def _fonctions_de_test(source: str) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name.startswith("test_"):
            yield n


def temoins_muets(source: str, chemin: str) -> tuple[str, ...]:
    """The tests in ``source`` that assert NOTHING, shaped as ``path::function``."""
    return tuple(
        f"{chemin}{SEPARATEUR}{n.name}" for n in _fonctions_de_test(source) if not _asserte(n)
    )


def sites_de_saut(source: str, chemin: str) -> tuple[str, ...]:
    """The tests in ``source`` that **can** be skipped — marker or call, without telling them apart.

    **STATIC, AND THAT IS A MEASURED CHOICE.** Reading the skips ACTUALLY observed would need a
    full battery run — measured at over 40 minutes on this repo, so *a gate slower than the wall
    it guards, which would never be used*. The site itself reads in half a second and answers the
    question that matters: *did someone add a reason not to run this test?*

    A `pytest.skip` written inside a helper function (outside `test_`) is not seen: that is the
    limit, it is real, and it is written here rather than discovered later."""
    trouves: list[str] = []
    for n in _fonctions_de_test(source):
        saute = any(
            "skip" in ast.dump(deco).lower() or "xfail" in ast.dump(deco).lower()
            for deco in n.decorator_list
        )
        if not saute:
            for interne in ast.walk(n):
                if isinstance(interne, ast.Call):
                    rendu = ast.dump(interne.func).lower()
                    if "skip" in rendu or "xfail" in rendu:
                        saute = True
                        break
        if saute:
            trouves.append(f"{chemin}{SEPARATEUR}{n.name}")
    return tuple(trouves)


# --------------------------------------------------------------------------------------------
# THE TWO FREEZES — written here, never derived on the fly from what they guard.
# --------------------------------------------------------------------------------------------
#
# A freeze recomputed on every run from the population it watches ALWAYS yields "nothing
# moved". These two sets were produced ONCE by the two readers above, run against `tests/` on
# 2026-09-08, then PASTED here: it is that paste that makes them falsifiable.
#
# The SET, never the count: *a swap would leave the count identical, and silent.*

#: The 14 witnesses with zero assertions as of 2026-09-08. All shaped like "the INNOCENT passes" /
#: "DOES NOT RAISE": they assert by **not raising**, which is a real assertion no static reader
#: can see. Frozen, therefore — never forbidden.
MUETS_GELES: Final[frozenset[str]] = frozenset(
    {
        "tests/orchestration/test_heavy_lock.py::test_release_frees_the_lock_for_a_new_acquire_and_is_idempotent",
        "tests/orchestration/test_perimetre.py::test_le_CABLAGE_ne_LEVE_pas_sur_un_fichier_illisible",
        "tests/orchestration/test_plan_corbeille.py::test_verify_readability_ACCEPTE_un_arc_qui_garde_au_moins_un_item",
        "tests/orchestration/test_plan_corbeille.py::test_verify_roundtrip_PASSE_sur_un_mouvement_reel",
        "tests/orchestration/test_regle_candidate.py::test_une_candidature_promouvable_NE_LEVE_PAS",
        "tests/orchestration/test_runner_anthropic.py::test_une_reponse_ENTIERE_passe_et_l_INNOCENT_est_teste_avec",
        "tests/orchestration/test_runner_mlx_troncature.py::test_l_INNOCENT_une_generation_SOUS_le_plafond_passe",
        "tests/orchestration/test_runner_mlx_troncature.py::test_un_plafond_NUL_ou_NEGATIF_ne_declenche_rien",
        "tests/orchestration/test_runner_mlx_troncature.py::test_un_tokenizer_MUET_n_invente_JAMAIS_une_troncature",
        "tests/orchestration/test_runner_openai.py::test_une_reponse_ENTIERE_passe_et_l_INNOCENT_est_teste_avec",
        "tests/orchestration/test_spend.py::test_a_negative_ceiling_is_not_configured_not_a_veto",
        "tests/orchestration/test_spend.py::test_an_unconfigured_ceiling_never_becomes_an_accidental_kill_switch",
        "tests/platform/test_mur_de_tours.py::test_l_INNOCENT_une_panne_ORDINAIRE_passe_INTACTE",
        "tests/platform/test_walls.py::test_record_never_raises_even_when_the_parent_cannot_be_created",
        # --- 2026-09-09, public-mirror sync. Both are ALSO frozen skips above: in this
        # distribution they are skipped, so their body never runs and carries no assertion
        # the collector can see. What they guarantee lives in the repository that ships the
        # fixture; here they guarantee nothing, and saying so is the point.
        "tests/orchestration/test_routage_journal_run.py::test_sur_un_AUTRE_DEPOT_le_correctif_recupere_AU_MOINS_LA_MOITIE_des_commits_type",
        "tests/platform/test_bilan.py::test_start_here_pointe_le_bilan",
    }
)

#: The skip sites as of 2026-09-08. A skip is legitimate here (the flagship project's population gitignored,
#: missing brick, platform); what is not legitimate is a NEW skip appearing without a word said.
SAUTS_GELES: Final[frozenset[str]] = frozenset(
    {
        "tests/orchestration/test_derive_run.py::test_DB_la_population_REELLE_est_INCHANGEE_par_first_parent",
        "tests/orchestration/test_derive_run.py::test_la_fenetre_RECENTE_PARLE_des_qu_elle_porte_une_chute",
        "tests/orchestration/test_derive_run.py::test_population_disparue_VRAI_pour_le_sibling_FAUX_pour_un_projet_encore_PRESENT",
        "tests/orchestration/test_derive_run.py::test_sur_la_POPULATION_REELLE_la_bascule_du_21_juillet_SORT",
        "tests/orchestration/test_model_catalog.py::test_the_REAL_declaration_and_the_REAL_disk_agree_on_THIS_machine",
        "tests/orchestration/test_parc.py::test_assembler_REFUSE_et_NOMME_sur_le_MEME_lot_REEL_externe_arc_F",
        "tests/orchestration/test_plan_archive.py::test_les_bornes_de_section_tiennent_HORS_POPULATION_sur_le_plan_REEL_externe",
        "tests/orchestration/test_plan_format.py::test_a_plan_written_in_plain_checkboxes_elsewhere_in_the_repo_is_readable_as_is",
        "tests/orchestration/test_plan_format.py::test_no_value_of_the_REAL_corpus_runs_away_again",
        "tests/orchestration/test_plan_format.py::test_the_control_plans_raise_ZERO_false_accusations",
        "tests/orchestration/test_plan_format.py::test_the_reader_finds_the_FOUR_sibling_fields_and_names_the_TWO_that_are_missing_everywhere",
        "tests/orchestration/test_plan_ordre.py::test_duree_REJOUE_sur_LE_PROJET_date_ou_NOMME_chacune_des_18_etapes_fermees",
        "tests/orchestration/test_plan_ordre.py::test_lots_sur_LE_PROJET_AUCUNE_paire_A_L_INTERIEUR_D_UN_LOT_ne_collisionne",
        "tests/orchestration/test_plan_ordre.py::test_rejoue_sur_LE_PROJET_le_graphe_declare_tient_et_ne_porte_AUCUN_cycle",
        "tests/orchestration/test_plan_ordre.py::test_router_REJOUE_sur_LE_PROJET_publie_les_quatre_cases_ET_les_abstentions",
        "tests/orchestration/test_plan_ordre.py::test_sur_LE_PROJET_la_tete_de_file_CHANGE_face_au_tri_topologique_nu",
        "tests/orchestration/test_plan_recul_run.py::test_balayage_reecriture_sibling_SEPARE_P6_du_RESTE_sur_la_POPULATION_REELLE",
        "tests/orchestration/test_plan_recul_run.py::test_balayage_reecriture_git_sibling_SEPARE_le_PLUS_REECRIT_du_RESTE_sur_la_POPULATION_REELLE",
        "tests/orchestration/test_plan_recul_run.py::test_reecriture_sur_P6_REEL_confirme_ZERO_commits_et_25_temoins_JAMAIS_25_tout_court",
        "tests/orchestration/test_plan_recul_run.py::test_refus_repete_retrait_sur_la_POPULATION_REELLE_reproduit_le_denied_count_4",
        "tests/orchestration/test_plan_recul_run.py::test_signal_plancher_sur_la_POPULATION_REELLE_est_un_Signal_qui_declenche",
        "tests/orchestration/test_plan_recul_run.py::test_sur_la_POPULATION_REELLE_le_rejeu_declenche_AU_MOINS_au_22_juillet",
        "tests/orchestration/test_plan_recul_run.py::test_temoins_fichiers_sur_la_POPULATION_REELLE_rend_25_pour_P6",
        "tests/orchestration/test_plan_recul_signal1.py::test_sibling_faits_sur_la_POPULATION_REELLE_reproduit_le_chiffre_mesure_a_la_main",
        "tests/orchestration/test_plan_recul_signal1.py::test_immobilite_sibling_sur_la_POPULATION_REELLE_se_mesure_pas_se_tait",
        "tests/orchestration/test_plan_retrait.py::test_all_states_HORS_POPULATION_sur_le_ledger_REEL_jamais_vu_par_ce_module",
        "tests/orchestration/test_plancher_run.py::test_le_DENOMINATEUR_BORNE_reproduit_le_79_8_pourcent_publie_du_15_juillet",
        "tests/orchestration/test_plancher_run.py::test_le_REJEU_HISTORIQUE_n_est_PAS_bloque_par_l_etat_courant",
        "tests/orchestration/test_plancher_run.py::test_le_cas_PASSANT_une_population_PRESENTE_se_mesure",
        "tests/orchestration/test_plancher_run.py::test_le_resume_NOMME_la_population_DISPARUE_plutot_que_deviner_un_checkbox",
        "tests/orchestration/test_plancher_run.py::test_le_resume_sur_LE_PROJET_dit_NON_MESURE_MEME_avec_le_predicat_historique_INJECTE",
        "tests/orchestration/test_plancher_run.py::test_sur_la_POPULATION_REELLE_le_plancher_EST_franchi",
        "tests/orchestration/test_plans_run.py::test_l_accesseur_du_juge_COUVRE_les_14_portes_REELLES_dont_13_NICHEES",
        "tests/orchestration/test_regle_candidate.py::test_eprouve_sur_les_declarations_SOEURS_reelles_de_la_memoire",
        "tests/orchestration/test_regle_candidate.py::test_le_REEL_du_depot_est_gele",
        "tests/orchestration/test_ui_contract.py::test_an_unreadable_ARC_is_NAMED_instead_of_silently_shrinking_the_queue",
        "tests/orchestration/test_ui_contract.py::test_an_unreadable_projects_directory_degrades_ONE_card_not_the_whole_page",
        "tests/orchestration/test_ui_contract.py::test_an_unreadable_signalement_FILE_is_indisponible_never_a_confident_zero",
        "tests/orchestration/test_ui_contract.py::test_qui_le_tient_dit_INCONNU_plutot_que_de_SE_TAIRE_quand_un_poste_est_ILLISIBLE",
        "tests/platform/test_derives.py::test_PORTES_QUI_DECLARENT_est_bien_L_ENSEMBLE_mesure_pas_seulement_son_compte",
        "tests/platform/test_derives.py::test_ecart_adoption_le_DEPOT_REEL_n_a_AUCUNE_porte_declarante_hors_du_gel_AUJOURD_HUI",
        "tests/platform/test_derives.py::test_le_gel_LIT_LE_DISQUE_et_TIENT_sur_les_14_portes_REELLES_du_PREMIER_ADOPTANT_AUJOURD_HUI",
        # --- 2026-09-09, public-mirror sync. Four skip sites that appeared in THIS
        # distribution and had never been declared. Each names the fixture this repository
        # genuinely does not ship -- none of them covers a broken check.
        "tests/orchestration/test_routage_journal_run.py::test_sur_un_AUTRE_DEPOT_le_correctif_recupere_AU_MOINS_LA_MOITIE_des_commits_type",
        "tests/platform/test_bilan.py::test_start_here_pointe_le_bilan",
        "tests/platform/test_comparaison_cardinale.py::test_sur_les_PORTES_REELLES_du_depot_la_comparaison_n_est_pas_VACANTE",
        "tests/test_public_mirror.py::test_the_EXPORTED_copy_of_this_module_carries_no_denylisted_string",
    }
)
