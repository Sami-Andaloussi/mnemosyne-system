"""Witnesses for ``P5`` — the watcher: a calm window WITH a ceiling, and ``HEAD`` proves the gesture.

The contract's **five** surfaces are here: the judge (``production/guetteur.py``), the **rc**
(:func:`~mnemosyne.runtime.guetteur_commit.juger` and :func:`~mnemosyne.runtime.guetteur_commit.main`),
the **published text**, the **production values** of the batch's three modules, and the **passing case**.

 No real repo, no real sleep, no real commit: everything is injected (D126).

Note for readers of this mirror: several strings asserted below come from
``production/guetteur.py`` / ``production/chrono.py`` / ``production/budget_porte.py``, which this
sync did not touch this round — the assertions match those modules' actual (French) output exactly,
rather than a translated guess.
"""

from __future__ import annotations

from mnemosyne.production.budget_porte import Unite, verdict as verdict_budget
from mnemosyne.production.chrono import verdict as verdict_chrono
from mnemosyne.production.guetteur import (
    HEAD_ILLISIBLE,
    HEAD_IMMOBILE,
    RC_MENTEUR,
    VERROUS_QUI_BLOQUENT,
    fenetre_calme,
    raison_dattente,
    resume_geste,
    verdict_du_geste,
    verrous_presents,
)
from mnemosyne.runtime import guetteur_commit as gc

A = "a" * 40
B = "b" * 40


class Horloge:
    """An injected monotonic clock: each read advances by ``pas`` second(s)."""

    def __init__(self, pas: float = 1.0) -> None:
        self.t = 0.0
        self.pas = pas

    def __call__(self) -> float:
        self.t += self.pas
        return self.t


def _git(head_successifs):
    """A fake git: returns the requested ``HEAD``s, one after another."""
    restants = list(head_successifs)

    def appel(args):
        if list(args[:2]) == ["rev-parse", "HEAD"]:
            valeur = restants.pop(0)
            return (0, valeur) if valeur else (128, "")
        return 0, ""

    return appel


# ── surface 1: THE JUDGE (calm window) ────────────────────────────────────────────────────────


def test_une_fenetre_est_calme_quand_AUCUN_bloqueur_n_est_present():
    assert fenetre_calme(()) is True
    assert fenetre_calme(("HEAD", "config", "objects")) is True


def test_chaque_bloqueur_gele_bloque_a_lui_seul():
    """The property over the WHOLE SET, not over a representative drawn at random."""
    for verrou in sorted(VERROUS_QUI_BLOQUENT):
        assert fenetre_calme((verrou,)) is False, f"{verrou} no longer blocks"
        assert verrous_presents(("config", verrou)) == (verrou,)


def test_le_juge_INTERSECTE_et_ne_croit_pas_le_bord_sur_parole():
    """An edge that dumped the whole of ``.git`` must not cause a permanent refusal."""
    tout = ("HEAD", "config", "objects", "refs", "logs", "hooks", "info", "packed-refs")
    assert verrous_presents(tout) == ()


# ── surface 1: THE JUDGE (has HEAD moved?) ────────────────────────────────────────────────────


def test_HEAD_IMMOBILE_est_refuse_MEME_avec_un_code_de_sortie_ZERO():
    """ THE line of P5: this is exactly what a ``| tee`` produces."""
    assert [r.genre for r in verdict_du_geste(A, A, 0)] == [HEAD_IMMOBILE]


def test_HEAD_qui_BOUGE_avec_un_code_NON_NUL_est_nomme_aussi():
    """The other direction of the lie: replaying it would create a duplicate."""
    assert [r.genre for r in verdict_du_geste(A, B, 1)] == [RC_MENTEUR]


def test_le_code_de_sortie_ne_JUGE_jamais_seul():
    """HEAD moved, rc == 0: green. HEAD unmoved, rc == 0: refused. The discriminant is HEAD."""
    assert verdict_du_geste(A, B, 0) == ()
    assert verdict_du_geste(A, A, 0) != ()


def test_un_HEAD_illisible_est_une_panne_d_instrument_pas_un_echec_du_geste():
    assert [r.genre for r in verdict_du_geste("", B, 0)] == [HEAD_ILLISIBLE]
    assert [r.genre for r in verdict_du_geste(A, "", 0)] == [HEAD_ILLISIBLE]


# ── surface 1: the capped wait ────────────────────────────────────────────────────────────────


def test_le_premier_sondage_a_lieu_AVANT_tout_sommeil():
    """The ordinary case (no peer) must not cost the repo a single second of sleep."""
    dormis = []
    demande, tour, _ = gc.attendre_le_tour(
        sonde=lambda: (), maintenant=Horloge(), dormir=dormis.append, plafond_attente_s=30.0
    )
    assert tour is not None and dormis == []


def test_l_attente_s_arrete_au_PLAFOND_et_rend_un_tour_NON_obtenu():
    dormis = []
    demande, tour, raison = gc.attendre_le_tour(
        sonde=lambda: ("index.lock",),
        maintenant=Horloge(pas=1.0),
        dormir=dormis.append,
        plafond_attente_s=5.0,
    )
    assert tour is None
    assert "index.lock" in raison
    assert dormis, "the watcher must have waited at least once before giving up"


def test_un_plafond_a_ZERO_ne_fait_AUCUN_tour_de_boucle():
    """The condition is ``>=``: with ``>`` a ceiling of zero would still sleep once."""
    dormis = []
    _, tour, _ = gc.attendre_le_tour(
        sonde=lambda: ("index.lock",),
        maintenant=Horloge(),
        dormir=dormis.append,
        plafond_attente_s=0.0,
    )
    assert tour is None and dormis == []


def test_le_guetteur_REPART_des_que_le_verrou_disparait():
    etats = [("index.lock",), ("index.lock",), ()]
    dormis = []
    _, tour, _ = gc.attendre_le_tour(
        sonde=lambda: etats.pop(0),
        maintenant=Horloge(),
        dormir=dormis.append,
        plafond_attente_s=100.0,
    )
    assert tour is not None and len(dormis) == 2


# ── surface 2: THE RC / THE DECISION ──────────────────────────────────────────────────────────


def test_rc_0_quand_la_fenetre_est_obtenue_le_geste_fait_et_HEAD_bouge():
    passage = gc.sous_garde(
        lambda: 0,
        git=_git([A, B]),
        sonde=lambda: (),
        maintenant=Horloge(pas=0.1),
        dormir=lambda _: None,
        cpu=iter([0.0, 0.4]).__next__,
    )
    code, _ = gc.juger(passage)
    assert code == 0


def test_rc_1_quand_HEAD_est_IMMOBILE_malgre_un_geste_qui_dit_avoir_reussi():
    passage = gc.sous_garde(
        lambda: 0,
        git=_git([A, A]),
        sonde=lambda: (),
        maintenant=Horloge(pas=0.1),
        dormir=lambda _: None,
        cpu=iter([0.0, 0.4]).__next__,
    )
    code, _ = gc.juger(passage)
    assert code == 1


def test_rc_1_quand_l_attente_est_PLAFONNEE_et_le_geste_n_est_PAS_lance():
    lance = []
    passage = gc.sous_garde(
        lambda: lance.append("!") or 0,
        git=_git([]),
        sonde=lambda: ("index.lock",),
        maintenant=Horloge(pas=10.0),
        dormir=lambda _: None,
        cpu=lambda: 0.0,
        plafond_attente_s=5.0,
    )
    code, _ = gc.juger(passage)
    assert code == 1
    assert lance == [], "a turn never obtained must launch NOTHING"


def test_rc_1_quand_le_BUDGET_CPU_est_depasse():
    passage = gc.sous_garde(
        lambda: 0,
        git=_git([A, B]),
        sonde=lambda: (),
        maintenant=Horloge(pas=0.1),
        dormir=lambda _: None,
        cpu=iter([0.0, 99.0]).__next__,
    )
    code, _ = gc.juger(passage, budget_cpu_s=10.0)
    assert code == 1


def test_rc_2_quand_HEAD_est_ILLISIBLE_le_2_ne_s_ECRASE_PAS_sur_le_1():
    """An instrument failure is not a failure of the gesture — collapsing the two destroys the
    distinction."""
    passage = gc.sous_garde(
        lambda: 0,
        git=_git(["", ""]),
        sonde=lambda: (),
        maintenant=Horloge(pas=0.1),
        dormir=lambda _: None,
        cpu=iter([0.0, 0.4]).__next__,
    )
    code, _ = gc.juger(passage)
    assert code == 2


def test_main_rend_2_sans_commande_et_ne_lance_RIEN():
    lance = []
    assert gc.main([], git=_git([]), sonde=lambda: (), lanceur=lambda c: lance.append(c) or 0) == 2
    assert (
        gc.main(["--"], git=_git([]), sonde=lambda: (), lanceur=lambda c: lance.append(c) or 0) == 2
    )
    assert lance == []


def test_main_passe_la_commande_TELLE_QUELLE_en_LISTE_et_rend_0_au_vert():
    recue = []
    code = gc.main(
        ["--", "git", "commit", "-m", "x"],
        git=_git([A, B]),
        sonde=lambda: (),
        lanceur=lambda c: recue.append(list(c)) or 0,
    )
    assert code == 0
    assert recue == [["git", "commit", "-m", "x"]]


def test_main_rend_1_quand_le_geste_ment_par_un_pipe():
    code = gc.main(
        ["--", "sh", "-c", "false | true"],
        git=_git([A, A]),
        sonde=lambda: (),
        lanceur=lambda c: 0,
    )
    assert code == 1


# ── surface 3: THE PUBLISHED TEXT ─────────────────────────────────────────────────────────────


def test_le_texte_du_HEAD_immobile_ACCUSE_le_pipe_et_pas_le_commit():
    texte = resume_geste(verdict_du_geste(A, A, 0))
    assert "RIEN n'a ete commite" in texte
    assert "relis HEAD" in texte


def test_le_texte_du_rc_menteur_INTERDIT_de_rejouer():
    texte = resume_geste(verdict_du_geste(A, B, 1))
    assert "NE LE REJOUE PAS" in texte


def test_le_texte_vert_dit_que_le_code_de_sortie_n_a_PAS_juge():
    assert "le code de sortie n'a pas juge" in resume_geste(())


def test_la_raison_d_attente_NOMME_ce_qui_bloque():
    assert raison_dattente(("index.lock",)) == "occupe par : index.lock"
    assert raison_dattente(()) == "fenetre calme"


def test_le_texte_du_tour_perdu_DIT_que_le_travail_n_est_PAS_en_cause():
    passage = gc.sous_garde(
        lambda: 0,
        git=_git([]),
        sonde=lambda: ("index.lock",),
        maintenant=Horloge(pas=10.0),
        dormir=lambda _: None,
        cpu=lambda: 0.0,
        plafond_attente_s=5.0,
    )
    _, texte = gc.juger(passage)
    assert "Turn NEVER obtained" in texte
    assert "this is contention, not the commit" in texte


def test_le_texte_vert_complet_porte_les_TROIS_juges():
    passage = gc.sous_garde(
        lambda: 0,
        git=_git([A, B]),
        sonde=lambda: (),
        maintenant=Horloge(pas=0.1),
        dormir=lambda _: None,
        cpu=iter([0.0, 0.4]).__next__,
    )
    _, texte = gc.juger(passage)
    assert "stay" in texte  # chrono (G7)
    assert "PER UNIT" in texte  # budget_porte (G12)
    assert "HEAD a bouge" in texte  # guetteur (P5)


# ── surface 4: THE PRODUCTION VALUES ──────────────────────────────────────────────────────────


def test_l_ENSEMBLE_des_bloqueurs_de_production_est_GELE_par_EGALITE():
    """A freeze covers the WHOLE SET: a SWAP would leave ``5 == 5`` and the gate would stay silent."""
    assert VERROUS_QUI_BLOQUENT == frozenset(
        {"index.lock", "MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply"}
    )


def test_les_TROIS_bornes_de_production_ont_les_valeurs_derivees_et_le_bon_ORDRE_de_grandeur():
    """Injecting everywhere would leave the real values naked. They are judged here, in the open."""
    assert gc.PLAFOND_ATTENTE_S == 30.0
    assert gc.GARDE_FOU_SERVICE_S == 300.0
    assert gc.BUDGET_CPU_GESTE_S == 10.0
    assert gc.INTERVALLE_SONDE_S == 0.2


def test_la_borne_MURALE_de_production_est_un_garde_fou_JAMAIS_un_budget():
    """It must stay TWO orders of magnitude above the measured work (0.37 s wall).

    If someone one day tightens it toward the real cost, it becomes a wall-clock budget — which
    G12 forbids — and this witness turns red before it ever reaches a commit.
    """
    mural_mesure_s = 0.37
    assert gc.GARDE_FOU_SERVICE_S / mural_mesure_s > 100


def test_le_budget_CPU_de_production_ACCEPTE_le_pire_coût_mesure_et_REFUSE_la_regression():
    """0.77 s CPU = the worst recorded under 20 burners. 150 s = another project's order of magnitude."""
    assert verdict_budget((Unite("gate", cpu_s=0.77, mural_s=1.32),), gc.BUDGET_CPU_GESTE_S) == ()
    assert (
        verdict_budget((Unite("gate", cpu_s=150.0, mural_s=300.0),), gc.BUDGET_CPU_GESTE_S) != ()
    )


def test_le_plafond_d_attente_de_production_reste_SOUS_l_intervalle_median_entre_commits():
    """90 s is the median interval measured over 1,715 intervals. Beyond that, you are no longer
    queuing."""
    intervalle_median_mesure_s = 90.0
    assert gc.PLAFOND_ATTENTE_S < intervalle_median_mesure_s / 2


# ── surface 5: THE PASSING CASE ───────────────────────────────────────────────────────────────


def test_LE_CAS_LEGITIME_NE_ROUGIT_PAS_de_bout_en_bout():
    """A free window, a commit that moves HEAD, 0.4 s CPU — with the module's REAL bounds."""
    passage = gc.sous_garde(
        lambda: 0,
        git=_git([A, B]),
        sonde=lambda: (),
        maintenant=Horloge(pas=0.1),
        dormir=lambda _: None,
        cpu=iter([0.0, 0.4]).__next__,
    )
    code, texte = gc.juger(passage)
    assert code == 0
    assert "REFUS" not in texte
    assert verdict_chrono(passage.chrono) == ()


def test_une_attente_LONGUE_suivie_d_un_travail_COURT_passe_avec_les_bornes_REELLES():
    """G7 end to end: 29 s of waiting, 0.2 s of work — GREEN under the production bounds."""
    instants = iter([0.0, 29.0, 29.2])  # request · turn obtained · gesture end
    passage = gc.sous_garde(
        lambda: 0,
        git=_git([A, B]),
        sonde=lambda: (),
        maintenant=lambda: next(instants),
        dormir=lambda _: None,
        cpu=iter([0.0, 0.2]).__next__,
    )
    code, _ = gc.juger(passage)
    assert passage.chrono.tour_obtenu == 29.0
    assert code == 0
