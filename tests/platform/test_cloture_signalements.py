"""Witnesses of the signalement closure judge (P1).

The FIVE surfaces, separately: the pure judge · the rc · the published text · the PRODUCTION
value (the ratchet and the `RACINE`, judged on the REAL corpus) · the passing case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.cloture import (
    ACCEPTE,
    HERITAGE_SANS_AUTEUR,
    Defaut,
    message,
    verdict,
)
from mnemosyne.production.signalements import HANDLED, OPEN
from mnemosyne.runtime import cloture_run

_RIEN: frozenset[str] = frozenset()


# --------------------------------------------------------------------------------------------
# 1. THE JUDGE — pure verdicts, on an injected population.
# --------------------------------------------------------------------------------------------


def test_le_CAS_PASSANT_une_cloture_ATTRIBUEE_et_un_ouvert_ne_refusent_RIEN() -> None:
    """Without this witness, we would only be measuring its ability to refuse everything."""
    v = verdict(
        [
            Defaut("a", HANDLED, auteur="chat-2"),
            Defaut("b", OPEN),
        ],
        heritage=_RIEN,
    )
    assert v.refuse is False and v.non_mesure is False
    assert v.attribues == ("a",) and v.juges == 2


def test_une_cloture_SANS_AUTEUR_hors_cliquet_est_REFUSEE() -> None:
    """*A closure nobody can verify is not a closure.*"""
    v = verdict([Defaut("a", HANDLED)], heritage=_RIEN)
    assert v.clos_sans_auteur == ("a",) and v.refuse is True


def test_une_cloture_SANS_AUTEUR_DANS_le_cliquet_est_publiee_jamais_refusee() -> None:
    v = verdict([Defaut("a", HANDLED)], heritage=frozenset({"a"}))
    assert v.heritees == ("a",) and v.clos_sans_auteur == () and v.refuse is False


def test_le_cliquet_refuse_AUSSI_dans_l_autre_sens_quand_le_gain_est_encaisse() -> None:
    """*A loosened ratchet no longer ratchets.* An entry that gains an author must LEAVE the
    freeze, or the gain quietly reverts with no red flag to say so."""
    v = verdict([Defaut("a", HANDLED, auteur="chat-2")], heritage=frozenset({"a"}))
    assert v.attribues == ("a",)
    assert v.heritage_perime == ("a",) and v.refuse is True


def test_une_entree_de_cliquet_qui_DISPARAIT_du_corpus_refuse_aussi() -> None:
    """A freeze that names a report which has disappeared is protecting a past state — and never
    turns red on its own."""
    v = verdict([Defaut("b", OPEN)], heritage=frozenset({"a"}))
    assert v.heritage_perime == ("a",) and v.refuse is True


def test_un_ECHANGE_dans_le_cliquet_laisse_le_COMPTE_identique_et_le_juge_le_NOMME() -> None:
    """1 = 1, silent — if the ratchet were keyed on a COUNT. It is keyed on the SET."""
    v = verdict([Defaut("neuf", HANDLED)], heritage=frozenset({"vieux"}))
    assert v.clos_sans_auteur == ("neuf",) and v.heritage_perime == ("vieux",)


def test_un_statut_HORS_VOCABULAIRE_est_NOMME_jamais_perdu_en_silence() -> None:
    """The fault that `signalements.drain` spells out in full: *"already drained, or a status
    we do not recognise"* — two opposite causes inside a single silent branch."""
    v = verdict([Defaut("a", "Ouvert"), Defaut("b", "")], heritage=_RIEN)
    assert v.inconnus == (("a", "Ouvert"), ("b", ""))
    assert v.refuse is True


def test_un_defaut_ACCEPTE_sans_son_PRIX_est_refuse_et_avec_son_prix_passe() -> None:
    """Population NULL today (the `accepte` status doesn't exist yet in the repository): this
    witness arms the clause, it does not claim it bites on anything real."""
    assert verdict([Defaut("a", ACCEPTE)], heritage=_RIEN).acceptes_sans_cout == ("a",)
    v = verdict([Defaut("a", ACCEPTE, cout="we live with it")], heritage=_RIEN)
    assert v.acceptes_sans_cout == () and v.refuse is False


def test_une_population_VIDE_est_une_NON_MESURE_jamais_un_vert() -> None:
    v = verdict([], heritage=_RIEN)
    assert v.non_mesure is True and v.refuse is False


def test_la_BIJECTION_chaque_defaut_tombe_dans_EXACTEMENT_une_case() -> None:
    """No catch-all bucket: the total across the buckets must equal the total judged."""
    population = [
        Defaut("attribue", HANDLED, auteur="x"),
        Defaut("herite", HANDLED),
        Defaut("nu", HANDLED),
        Defaut("ouvert", OPEN),
        Defaut("accepte_nu", ACCEPTE),
        Defaut("bizarre", "zzz"),
    ]
    v = verdict(population, heritage=frozenset({"herite"}))
    classes = (
        len(v.attribues)
        + len(v.heritees)
        + len(v.clos_sans_auteur)
        + len(v.acceptes_sans_cout)
        + len(v.inconnus)
    )
    assert v.juges == len(population)
    assert classes == len(population) - 1, "only the conforming `open` one falls into no bucket"


# --------------------------------------------------------------------------------------------
# 2. THE PUBLISHED TEXT.
# --------------------------------------------------------------------------------------------


def test_le_texte_publie_TOUJOURS_le_cardinal_juge() -> None:
    """*A green result doesn't say by how much* — except here."""
    texte = message(verdict([Defaut("a", HANDLED, auteur="x")], heritage=_RIEN))
    assert "sur 1 defaut(s) juge(s)" in texte


def test_le_texte_de_NON_MESURE_ne_se_lit_pas_comme_un_vert() -> None:
    texte = message(verdict([], heritage=_RIEN))
    assert "NON MESUREES" in texte and "panne d'instrument" in texte


def test_le_message_de_refus_nomme_LE_RAPPORT_et_LES_DEUX_gestes() -> None:
    """*The refusal message names the way out.* Two gestures here: attribute it, or enter it in
    the ratchet."""
    texte = message(verdict([Defaut("my-report", HANDLED)], heritage=_RIEN))
    assert "my-report" in texte
    assert "par: <qui>" in texte and "HERITAGE_SANS_AUTEUR" in texte


def test_le_texte_nomme_TOUTES_les_causes_jamais_la_premiere_seule() -> None:
    texte = message(
        verdict(
            [Defaut("nu", HANDLED), Defaut("bizarre", "zzz"), Defaut("cher", ACCEPTE)],
            heritage=frozenset({"parti"}),
        )
    )
    for attendu in ("SANS AUTEUR", "cliquet", "HORS VOCABULAIRE", "sans leur prix"):
        assert attendu in texte, attendu


# --------------------------------------------------------------------------------------------
# 3. THE RC.
# --------------------------------------------------------------------------------------------


def _rapport(dossier: Path, nom: str, corps: str) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"{nom}.md").write_text(f"---\n{corps}\n---\n\nsome text\n", encoding="utf-8")


def test_le_rc_vaut_0_sur_un_corpus_conforme(tmp_path: Path) -> None:
    _rapport(tmp_path / "docs" / "signalements", "a", 'status: traite\npar: "chat-2"')
    assert cloture_run.main(racine=tmp_path, heritage=_RIEN) == 0


def test_le_rc_vaut_1_sur_une_cloture_sans_auteur(tmp_path: Path) -> None:
    _rapport(tmp_path / "docs" / "signalements", "a", "status: traite")
    assert cloture_run.main(racine=tmp_path, heritage=_RIEN) == 1


def test_le_rc_vaut_2_quand_le_DOSSIER_est_absent_pas_0(tmp_path: Path) -> None:
    """*Two absences of measurement never compare equal to a green result.*"""
    assert cloture_run.main(racine=tmp_path, heritage=_RIEN) == 2


def test_le_README_n_est_pas_un_signalement_et_le_dossier_vide_rend_2(tmp_path: Path) -> None:
    dossier = tmp_path / "docs" / "signalements"
    dossier.mkdir(parents=True)
    (dossier / "README.md").write_text("---\nstatus: traite\n---\n", encoding="utf-8")
    assert cloture_run.main(racine=tmp_path, heritage=_RIEN) == 2


def test_le_bord_lit_les_QUATRE_noms_de_champ_d_auteur(tmp_path: Path) -> None:
    """**SABOTAGE FIX: THE FOUR NAMES ARE WRITTEN HERE, NOT READ FROM THE CONSTANT.**
    The first version looped over `cloture_run.CHAMPS_AUTEUR` — so shrinking that constant to
    `("par",)` ALSO shrank the fixture, and the saboteur turned green. *A witness that draws its
    population from the very value it is testing cannot contradict it.*"""
    attendus = ("par", "traite_par", "clos_par", "by")
    dossier = tmp_path / "docs" / "signalements"
    for index, champ in enumerate(attendus):
        _rapport(dossier, f"r{index}", f'status: traite\n{champ}: "someone"')
    assert cloture_run.main(racine=tmp_path, heritage=_RIEN) == 0
    assert set(attendus) <= set(cloture_run.CHAMPS_AUTEUR)


def test_un_rapport_SANS_frontmatter_entre_en_INCONNU_il_n_est_pas_SAUTE(tmp_path: Path) -> None:
    """Skipping it would be exactly the silent loss this pair exists to close."""
    dossier = tmp_path / "docs" / "signalements"
    dossier.mkdir(parents=True)
    (dossier / "casse.md").write_text("no frontmatter at all\n", encoding="utf-8")
    assert cloture_run.main(racine=tmp_path, heritage=_RIEN) == 1


# --------------------------------------------------------------------------------------------
# 4. THE PRODUCTION VALUE — judged on the REAL corpus, never injected.
# --------------------------------------------------------------------------------------------


def test_la_RACINE_de_production_designe_le_DEPOT_et_ses_signalements() -> None:
    dossier = cloture_run.RACINE / cloture_run.DOSSIER
    assert dossier.is_dir(), f"{dossier} — the production RACINE does not point at the repository"
    assert len(cloture_run.recenser(dossier)) > 10


def test_le_CAS_PASSANT_de_PRODUCTION_le_corpus_REEL_ne_rougit_pas(
    capsys: pytest.CaptureFixture,
) -> None:
    """No injection: the real corpus, the real ratchet. This is the witness that will turn red
    the day a report is drained with no author — or attributed without the ratchet shrinking."""
    assert cloture_run.main() == 0, capsys.readouterr().out


def test_le_cliquet_de_production_n_est_PAS_VIDE_et_couvre_le_corpus_MESURE() -> None:
    """An empty ratchet is doubly inert. Measured on 2026-09-08: 22 closures, 0 authors."""
    assert len(HERITAGE_SANS_AUTEUR) == 22


def test_chaque_entree_du_cliquet_designe_un_RAPPORT_qui_existe() -> None:
    dossier = cloture_run.RACINE / cloture_run.DOSSIER
    for entree in sorted(HERITAGE_SANS_AUTEUR):
        assert (dossier / f"{entree}.md").is_file(), entree


def test_le_vocabulaire_est_IMPORTE_de_son_foyer_jamais_retape() -> None:
    """A third home for the vocabulary is exactly what `signalements.py` refuses to open."""
    from mnemosyne.production import cloture, signalements

    assert cloture.OPEN is signalements.OPEN and cloture.HANDLED is signalements.HANDLED


# --------------------------------------------------------------------------------------------
# THE PUBLISHED TEXT — after an isolated audit: the `heritage_perime` branch was SILENT.
# --------------------------------------------------------------------------------------------
#
# And the witness that claimed to cover the message WAS LYING BY SUBSTRING: it looked for the
# token `"cliquet"`, which appears on THREE lines of the message — including the header and
# another cause. Its clause was satisfied without the targeted cause ever being true. *A token
# shared by several branches distinguishes none of them.*
def test_la_branche_HERITAGE_PERIME_a_sa_PROPRE_phrase() -> None:
    """Mutation `if v.heritage_perime:` -> `if False:`: SURVIVED before this witness."""
    from mnemosyne.production.cloture import Verdict, message

    texte = message(
        Verdict(
            clos_sans_auteur=(),
            heritage_perime=("rapport-x.md",),
            acceptes_sans_cout=(),
            inconnus=(),
            attribues=(),
            heritees=(),
            juges=1,
        )
    )
    assert "rapport-x.md" in texte, "the stale entry is not named"
    assert "HERITAGE_SANS_AUTEUR" in texte  # the gesture, not just the reproach


def test_les_causes_ont_des_phrases_DISTINCTES_jamais_un_jeton_commun() -> None:
    """The shape that would have caught the substring lie: two verdicts, two sentences, and we
    require them to DIFFER. A token present everywhere cannot satisfy this assertion."""
    from mnemosyne.production.cloture import Verdict, message

    def _v(**kw: object) -> Verdict:
        base: dict[str, object] = {
            "clos_sans_auteur": (),
            "heritage_perime": (),
            "acceptes_sans_cout": (),
            "inconnus": (),
            "attribues": (),
            "heritees": (),
            "juges": 1,
        }
        base.update(kw)
        return Verdict(**base)  # type: ignore[arg-type]

    sans_auteur = message(_v(clos_sans_auteur=("a.md",)))
    perime = message(_v(heritage_perime=("b.md",)))
    assert sans_auteur != perime
    assert "a.md" in sans_auteur and "a.md" not in perime
    assert "b.md" in perime and "b.md" not in sans_auteur
