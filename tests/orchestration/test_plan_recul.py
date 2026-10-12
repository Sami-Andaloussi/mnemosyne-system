"""D5's PURE JUDGE (`plan_recul.py`) — `rejoue_plancher` REPLAYS D3's judge, it does not rewrite
it; `mandat_de_recul` PUBLISHES, it never refuses anything (level 1)."""

from __future__ import annotations

from mnemosyne.production.plan_derive import Jour
from mnemosyne.production.plan_recul import (
    Signal,
    balayage_reecriture,
    compte_temoins_fichiers,
    mandat_de_recul,
    refus_le_plus_repete,
    rejoue_plancher,
    rejoue_reecriture,
)
from mnemosyne.production.plan_retrait import RetraitEtat


def _jour(date: str, part_pct: float) -> Jour:
    """A synthetic `Jour` whose `.part * 100 == part_pct`, built on a fixed total of 100."""
    return Jour(date=date, produit=round(part_pct), total=100)


# --------------------------------------------------------------------------------------------
# rejoue_plancher
# --------------------------------------------------------------------------------------------


def test_rejoue_plancher_ne_declenche_QUE_les_jours_sous_le_seuil() -> None:
    jours = [
        _jour("d1", 80.0),  # above: never
        _jour("d2", 32.0),  # above, just barely: never
        _jour("d3", 5.0),  # under: triggers
        _jour("d4", 20.0),  # under: triggers
        _jour("d5", 50.0),  # back above: never
    ]
    resultats = rejoue_plancher(jours, x=30.0, n=1)
    assert tuple(d.date for d in resultats) == ("d3", "d4")
    assert all(d.plancher.franchi for d in resultats)


def test_rejoue_plancher_rend_vide_quand_rien_ne_franchit_jamais() -> None:
    jours = [_jour("d1", 80.0), _jour("d2", 90.0), _jour("d3", 60.0)]
    assert rejoue_plancher(jours, x=30.0, n=1) == ()


def test_rejoue_plancher_rend_vide_sur_une_serie_vide() -> None:
    assert rejoue_plancher([], x=30.0, n=1) == ()


def test_rejoue_plancher_EXCLUT_un_jour_total_ZERO_jamais_lu_comme_franchi() -> None:
    """ Session-3 audit (2026-08-16), proven by execution: `Jour(total=0)` was not filtered out
 -- `Jour.part` returns `0.0`, read as "under the floor" instead of "no data." Same class that
 `plan_derive.plus_grande_chute` already paid for and fixed. This test must go red if the filter
 `pleins = [j for j in jours if j.total]` disappears."""
    jours = [_jour("d1", 80.0), Jour(date="d2", produit=0, total=0), _jour("d3", 90.0)]
    resultats = rejoue_plancher(jours, x=30.0, n=1)
    assert resultats == (), f"a day with no data (total=0) must NEVER trigger: {resultats}"


def test_rejoue_plancher_le_jour_ZERO_ne_casse_pas_LA_FENETRE_des_jours_reels_voisins() -> None:
    """A `total=0` day inserted between two real days must also not DISTURB the trailing-N window
    of measured days: it is removed from the series BEFORE the sweep, not merely ignored partway
    through the sweep (which would shift the window by N for nothing)."""
    jours = [
        _jour("d1", 5.0),
        Jour(date="d1-5", produit=0, total=0),  # day with no data, slipped in between d1 and d2
        _jour("d2", 5.0),
    ]
    resultats = rejoue_plancher(jours, x=30.0, n=2)
    # without the total=0 day: d1 (5%) then d2 (5%) -- at n=2, d2 must trigger (the last 2 are < 30)
    assert tuple(d.date for d in resultats) == ("d2",)


def test_rejoue_plancher_respecte_la_FENETRE_TRAILING_de_n_jours_consecutifs() -> None:
    """N=2: a SINGLE day under the threshold is not enough -- the last TWO are needed, together.

    `d2` (32%, above) breaks the window for `d3` (jours[-2:] = [d2, d3], NOT all < 30); only `d4`
    has its last two days (`d3`, `d4`) both < 30 -- it's the ONLY day that triggers. A replay that
    ignored N and tested each day in isolation would also wrongly trigger on `d3`."""
    jours = [
        _jour("d1", 80.0),
        _jour("d2", 32.0),
        _jour("d3", 5.0),  # only one under the threshold here -- n=2 excludes it (d2 breaks the window)
        _jour("d4", 20.0),  # d3+d4 both < 30: triggers
    ]
    resultats = rejoue_plancher(jours, x=30.0, n=2)
    assert tuple(d.date for d in resultats) == ("d4",)


def test_rejoue_plancher_chaque_declenchement_porte_SES_PROPRES_jours_recents() -> None:
    """Each `Declenchement` must carry the `Plancher` AS IT WAS on that day, not the series' last
    one -- otherwise two triggers on different dates would be indistinguishable."""
    jours = [_jour("d1", 5.0), _jour("d2", 8.0)]
    resultats = rejoue_plancher(jours, x=30.0, n=1)
    assert len(resultats) == 2
    assert resultats[0].plancher.recentes == (5.0,)
    assert resultats[1].plancher.recentes == (8.0,)


# --------------------------------------------------------------------------------------------
# mandat_de_recul
# --------------------------------------------------------------------------------------------


def test_mandat_NOMME_un_signal_qui_declenche_avec_ses_dates() -> None:
    signal = Signal(nom="plancher", declenche=True, preuve="franchi 3 jours", dates=("d3", "d4", "d5"))
    page = mandat_de_recul([signal])
    assert "DÉCLENCHE" in page
    assert "plancher" in page
    assert "d3, d4, d5" in page
    assert "arc H" in page  # the mandate doesn't undo anything itself


def test_mandat_dit_AUCUN_declenchement_quand_tous_les_signaux_sont_calmes() -> None:
    signal = Signal(nom="plancher", declenche=False, preuve="jamais franchi")
    page = mandat_de_recul([signal])
    assert "aucun signal mesuré ne déclenche" in page
    assert "CALME" in page
    assert "DÉCLENCHE" not in page.split("CALME")[0].replace("ne déclenche", "")


def test_mandat_NOMME_un_signal_NON_MESURABLE_plutot_que_de_le_taire() -> None:
    signal = Signal(nom="immobilite", declenche=None, preuve="faits non construits (257 revisions)")
    page = mandat_de_recul([signal])
    assert "NON MESURABLE" in page
    assert "immobilite" in page
    assert "257 revisions" in page


def test_mandat_NE_CONFOND_JAMAIS_les_trois_classes_sur_un_lot_mixte() -> None:
    """Three signals, three distinct classes: each appears in ITS OWN section and in NEITHER of
 the other two -- this is the central guarantee of `Signal.declenche`'s three values.

 **THE FIRST VERSION OF THIS TEST DIDN'T BITE**: it only checked each name's absence in the
 PRECEDING section, never in the OTHER TWO. Real sabotage (`calmes = [s for s in signaux if
 s.declenche is False]` → `if not s.declenche`, merging `None` into the quiet ones): 10/10 tests
 STAYED GREEN, including this one. *A ONE-DIRECTION exclusion check proves nothing about the
 other two directions* — fixed here by testing all nine pairs (3 signals × 3 sections), not just
 three."""
    signaux = [
        Signal(nom="SIG-DECLENCHE", declenche=True, preuve="preuve-A", dates=("d1",)),
        Signal(nom="SIG-CALME", declenche=False, preuve="preuve-B"),
        Signal(nom="SIG-INCONNU", declenche=None, preuve="preuve-C"),
    ]
    page = mandat_de_recul(signaux)
    assert "1/3" in page  # 1 trigger out of 3 signals

    # `find`, never `index`: a heading that DISAPPEARS (a rename, a translation pass) makes
    # `str.index` RAISE `ValueError` -- the witness then leaves the FAILED list entirely and lands
    # in ERRORS, changing CATEGORY at the same time as colour. `find` returns -1, and the `0 <=`
    # below turns that into a plain, loud FAILURE. The three headings are inline f-string literals
    # in `plan_recul.mandat_de_recul` (no named constant to aim at), so they are spelled out here.
    i_declenche = page.find("DÉCLENCHE(NT)")
    i_calme = page.find("CALME(S)")
    i_inconnu = page.find("NON MESURABLE(S)")
    assert 0 <= i_declenche < i_calme < i_inconnu, (
        "the three section headings must ALL be present, in this order -- one of them is missing "
        f"or reordered (DÉCLENCHE(NT)={i_declenche}, CALME(S)={i_calme}, "
        f"NON MESURABLE(S)={i_inconnu}); this test must be revisited"
    )

    section_declenche = page[i_declenche:i_calme]
    section_calme = page[i_calme:i_inconnu]
    section_inconnue = page[i_inconnu:]

    assert "SIG-DECLENCHE" in section_declenche
    assert "SIG-CALME" not in section_declenche
    assert "SIG-INCONNU" not in section_declenche

    assert "SIG-CALME" in section_calme
    assert "SIG-DECLENCHE" not in section_calme
    assert "SIG-INCONNU" not in section_calme

    assert "SIG-INCONNU" in section_inconnue
    assert "SIG-DECLENCHE" not in section_inconnue
    assert "SIG-CALME" not in section_inconnue


def test_mandat_sur_une_liste_vide_ne_leve_pas() -> None:
    page = mandat_de_recul([])
    assert "aucun signal mesuré ne déclenche" in page


# --------------------------------------------------------------------------------------------
# compte_temoins_fichiers -- signal 3, witness-FILES HALF only
# --------------------------------------------------------------------------------------------


def test_compte_temoins_fichiers_compte_EXACTEMENT_les_revisions_de_l_ident() -> None:
    noms = ["P6--t5.md", "P6--t6.md", "P6--t13-pistes-6-a-13.md", "autre.md"]
    assert compte_temoins_fichiers(noms, "P6") == 3


def test_compte_temoins_fichiers_NE_CONFOND_PAS_un_ident_PREFIXE_avec_un_AUTRE() -> None:
    """`P6` must NOT count revisions of `P60` or `P6X` -- only its own. Sabotage-relevant: an
    unanchored pattern (`ident + "--t"` searched anywhere) would wrongly match all three."""
    noms = ["P6--t1.md", "P60--t1.md", "P6X--t1.md", "XP6--t1.md"]
    assert compte_temoins_fichiers(noms, "P6") == 1


def test_compte_temoins_fichiers_ignore_les_fichiers_SANS_le_suffixe_t_N() -> None:
    noms = ["P6.md", "P6-notes.md", "P6--resume.md"]
    assert compte_temoins_fichiers(noms, "P6") == 0


def test_compte_temoins_fichiers_sur_une_liste_vide_rend_zero() -> None:
    assert compte_temoins_fichiers([], "P6") == 0


def test_compte_temoins_fichiers_reproduit_le_chiffre_REEL_mesure_a_la_main_pour_P6() -> None:
    """Fixture reproducing EXACTLY the names found by `ls` on the real repo (2026-08-16) -- 25
    files, `t1`-`t4` (conditions/) then `t5`-`t24` and one `t13` variant (faits/). Anchors the
    figure published in the internal planning notes (D5, state of play) and in
    `production/plan_recul.py` (module docstring) to something executable."""
    conditions = [f"P6--t{n}.md" for n in range(1, 5)]
    faits = [f"P6--t{n}.md" for n in range(5, 25)] + ["P6--t13-pistes-6-a-13.md"]
    assert compte_temoins_fichiers(conditions + faits, "P6") == 25


# --------------------------------------------------------------------------------------------
# refus_le_plus_repete -- signal 4, SCOPE = the withdrawal door (H1) only, TWO proofs
# --------------------------------------------------------------------------------------------


def _etat(id_: str, denied_count: int = 0) -> RetraitEtat:
    return RetraitEtat(
        id=id_,
        items=("Z1",),
        motif="test",
        cout="aucun",
        requested_by="test",
        filed_at="2026-01-01T00:00:00+00:00",
        denied_count=denied_count,
    )


def test_refus_le_plus_repete_trouve_le_PIRE_denied_count() -> None:
    etats = [_etat("a", denied_count=1), _etat("b", denied_count=4), _etat("c", denied_count=2)]
    r = refus_le_plus_repete(etats, {})
    assert r.porte == "retrait (H1)"
    assert r.cible_bypass == "b"
    assert r.tentatives_bypass == 4


def test_refus_le_plus_repete_trouve_le_PIRE_refus_geste_INDEPENDAMMENT_du_bypass() -> None:
    """ The test that proves the session-3 audit's fix: an id with `denied_count=0` (never a
 bypass attempt) can still have been refused K times by the normal GESTURE (`.refuse()`) -- the
 two measurements must stay INDEPENDENT, never one masked by the other."""
    etats = [_etat("a", denied_count=0)]
    r = refus_le_plus_repete(etats, {"a": 6, "b": 1})
    assert r.tentatives_bypass == 0
    assert r.cible_bypass == ""
    assert r.refus_geste == 6
    assert r.cible_refus == "a"


def test_refus_le_plus_repete_sur_des_entrees_vides_rend_UNE_MESURE_ZERO_pas_None() -> None:
    """The ledger EXISTS (the edge read it) but no request lives in it yet -- `0` on BOTH
    measurements is a legitimate measurement, never confused with "not yet measurable" (that's the
    edge's job via `None`, not this pure function's)."""
    r = refus_le_plus_repete([], {})
    assert r.tentatives_bypass == 0
    assert r.cible_bypass == ""
    assert r.refus_geste == 0
    assert r.cible_refus == ""


def test_refus_le_plus_repete_sur_des_etats_JAMAIS_refuses_rend_fois_zero_cible_vide() -> None:
    """All requests exist but none has `denied_count > 0` -- a real zero, not an absence of
    measurement, and NO target named (naming a target at fois=0 would invent a culprit)."""
    r = refus_le_plus_repete([_etat("a", denied_count=0), _etat("b", denied_count=0)], {})
    assert r.tentatives_bypass == 0
    assert r.cible_bypass == ""


def test_refus_le_plus_repete_reproduit_le_chiffre_REEL_mesure_a_la_main() -> None:
    """Fixture reproducing the one request refused 4 times found on the real ledger
    (`system/state/retraits_requests.jsonl`, id `da18c1b22975`, H1 audit of 2026-08-15) -- anchors
    the figure cited in the module docstring to something executable."""
    r = refus_le_plus_repete(
        [_etat("da18c1b22975", denied_count=4), _etat("autre", denied_count=1)], {}
    )
    assert r.tentatives_bypass == 4
    assert r.cible_bypass == "da18c1b22975"


# --------------------------------------------------------------------------------------------
# rejoue_reecriture / balayage_reecriture -- the sweep over K, ruled on by the orchestrator
# --------------------------------------------------------------------------------------------


def test_rejoue_reecriture_ne_declenche_que_les_idents_qui_ATTEIGNENT_k() -> None:
    temoins = {"A": ("2026-01-01", "2026-01-02"), "B": ("2026-01-01",)}
    resultats = rejoue_reecriture(temoins, k=2)
    assert {d.ident for d in resultats} == {"A"}


def test_rejoue_reecriture_rend_la_date_DU_K_IEME_temoin_pas_le_plus_recent() -> None:
    """With three witnesses: at k=2, the date returned is that of the SECOND one (sorted), not the
    last -- the day the threshold was crossed, not the day of the last known witness."""
    temoins = {"A": ("2026-01-03", "2026-01-01", "2026-01-05")}  # deliberately unsorted on input
    resultats = rejoue_reecriture(temoins, k=2)
    assert len(resultats) == 1
    assert resultats[0].date == "2026-01-03"  # the 2nd after sorting: 01-01, 01-03, 01-05
    assert resultats[0].total == 3


def test_rejoue_reecriture_rend_vide_quand_personne_n_atteint_k() -> None:
    temoins = {"A": ("2026-01-01",), "B": ("2026-01-01", "2026-01-02")}
    assert rejoue_reecriture(temoins, k=5) == ()


def test_balayage_reecriture_publie_CHAQUE_k_meme_ceux_a_zero_declenchement() -> None:
    temoins = {"A": ("2026-01-01", "2026-01-02", "2026-01-03")}
    balayage = balayage_reecriture(temoins, k_min=1, k_max=5)
    assert [b.k for b in balayage] == [1, 2, 3, 4, 5]
    assert len(balayage[2].declenchements) == 1  # k=3: A triggers (index 2 = k=3)
    assert len(balayage[3].declenchements) == 0  # k=4: nobody
    assert len(balayage[4].declenchements) == 0  # k=5: nobody


def test_balayage_reecriture_SEPARE_un_outlier_du_bruit_a_un_k_intermediaire() -> None:
    """Reproduces the EXACT shape of a real project's population (measured by hand before writing this
    module): one item with 25 witnesses, another with 5, the rest at 1-3 -- at k=6, ONLY the
    outlier triggers, exactly the separation the orchestrator asked to look for."""
    temoins = {
        "P6": tuple(f"2026-08-{d:02d}" for d in range(1, 26)),
        "P13": tuple(f"2026-08-{d:02d}" for d in range(1, 6)),
        "P4": ("2026-08-01", "2026-08-02", "2026-08-03"),
        "F2": ("2026-08-01",),
    }
    balayage = {b.k: b for b in balayage_reecriture(temoins, k_min=1, k_max=30)}
    assert {d.ident for d in balayage[6].declenchements} == {"P6"}
    assert {d.ident for d in balayage[25].declenchements} == {"P6"}
    assert balayage[26].declenchements == ()  # nobody reaches 26, not even P6 (25 exactly)


def test_balayage_reecriture_leve_si_k_min_depasse_k_max() -> None:
    import pytest

    with pytest.raises(ValueError):
        balayage_reecriture({}, k_min=5, k_max=1)
