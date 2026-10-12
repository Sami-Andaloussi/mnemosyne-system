"""THE END-OF-SESSION SUMMARY GETS JUDGED (workstream 1 · B5).

 WHAT THESE WITNESSES HOLD, AND WHAT THEY DO NOT — read before trusting a green.

They hold **the figures**: the block is generated, it carries its date and the command for each
measurement, and `VERIFIER=1` refuses when it has drifted. They hold **nothing of the
narrative**: a summary whose figures are fresh and whose prose lies would still pass green here.
This is an ADMISSION, not an oversight — which is why the rule about the gesture (*re-pulling the
summary RIGHT BEFORE compacting*) is written in the file itself and in the repo's own orientation
guide, where a human reads it.

 THE FIRST WITNESS IS THE INNOCENT CASE: without it, a judge that refused EVERYTHING would pass
every accusing witness that follows.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from mnemosyne.production.bilan import (
    CHEMIN,
    MARQUEUR_DEBUT,
    MARQUEUR_FIN,
    BilanRefus,
    Mesure,
    a_derive,
    etat_courant,
    premiere_ligne_qui_differe,
    remplacer_l_etat,
    rendre_l_etat,
)

_RACINE = Path(__file__).resolve().parents[2]
_UNE = (Mesure("some stuff", "3", "make stuff"),)
_PROSE = f"# BILAN\n\nsome prose WRITTEN BY HAND\n\n{MARQUEUR_DEBUT}\n{MARQUEUR_FIN}\n"


def test_un_bloc_sain_se_grave_et_porte_sa_date_et_sa_commande() -> None:
    bloc = rendre_l_etat(_UNE, mesure_le="2026-01-02")
    assert bloc.startswith(MARQUEUR_DEBUT) and bloc.endswith(MARQUEUR_FIN)
    assert "2026-01-02" in bloc
    assert "`make stuff`" in bloc and "| 3 |" in bloc


def test_un_bloc_vide_est_refuse() -> None:
    """ An EMPTY state block reads exactly like a SOUND block — two absences compare equal."""
    with pytest.raises(BilanRefus, match="no measurement to engrave"):
        rendre_l_etat((), mesure_le="2026-01-02")


def test_une_mesure_sans_sa_commande_est_refusee() -> None:
    """*A count without its command is a memory*: the reader must be able to redo it."""
    with pytest.raises(BilanRefus, match="with no command"):
        rendre_l_etat((Mesure("some stuff", "3", "  "),), mesure_le="2026-01-02")


def test_la_prose_ecrite_a_la_main_n_est_jamais_touchee() -> None:
    """ *A rewrite loses what it does not recopy.* The code writes ONLY between the bounds."""
    apres = remplacer_l_etat(_PROSE, rendre_l_etat(_UNE, mesure_le="2026-01-02"))
    assert "some prose WRITTEN BY HAND" in apres
    assert apres.startswith("# BILAN")


def test_une_borne_absente_refuse_au_lieu_de_deviner() -> None:
    with pytest.raises(BilanRefus, match="bound `end`"):
        remplacer_l_etat(f"# BILAN\n{MARQUEUR_DEBUT}\n", "peu importe")


def test_une_borne_en_double_refuse() -> None:
    with pytest.raises(BilanRefus, match="bound `start` present 2 times"):
        remplacer_l_etat(f"{MARQUEUR_DEBUT}\n{MARQUEUR_DEBUT}\n{MARQUEUR_FIN}\n", "peu importe")


def test_des_bornes_inversees_refusent() -> None:
    with pytest.raises(BilanRefus, match="inverted"):
        remplacer_l_etat(f"{MARQUEUR_FIN}\ndu texte\n{MARQUEUR_DEBUT}\n", "peu importe")


def test_un_bloc_grave_ne_derive_pas_de_lui_meme() -> None:
    bloc = rendre_l_etat(_UNE, mesure_le="2026-01-02")
    assert not a_derive(remplacer_l_etat(_PROSE, bloc), bloc)
    assert etat_courant(remplacer_l_etat(_PROSE, bloc)) == bloc


def test_un_chiffre_qui_bouge_est_une_derive() -> None:
    grave = remplacer_l_etat(_PROSE, rendre_l_etat(_UNE, mesure_le="2026-01-02"))
    frais = rendre_l_etat((Mesure("some stuff", "4", "make stuff"),), mesure_le="2026-01-02")
    assert a_derive(grave, frais)


def test_la_DATE_seule_suffit_a_faire_une_derive() -> None:
    """ INTENTIONAL: a summary measured yesterday can carry the SAME figures and still be wrong.
 What we want to know is WHEN it was pulled — not just what it said."""
    grave = remplacer_l_etat(_PROSE, rendre_l_etat(_UNE, mesure_le="2026-01-02"))
    assert a_derive(grave, rendre_l_etat(_UNE, mesure_le="2026-01-03"))


# ── The surface, on the REAL file in the repo ─────────────────────────────────────────────────

# TODO(public-mirror): needs human review — the tests below exercise this repo's REAL
# end-of-session summary file and top-level orientation document, plus docs/signalements content
# (subprocess calls and file reads against `_RACINE`, the actual checkout root). The public
# mirror's docs/ only carries the allow-listed subset (FORMAT_PLAN.md, parentheses/README.md,
# signalements/README.md), so several of these tests may not pass unmodified once this file runs
# inside the mirror repo itself.


def _lancer(**env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mnemosyne.runtime.bilan_run"],
        capture_output=True,
        text=True,
        cwd=_RACINE,
        env={**os.environ, "PYTHONPATH": str(_RACINE / "system" / "lib"), **env},
    )


def test_le_vrai_bilan_existe_et_porte_ses_deux_bornes() -> None:
    """ THE ADDRESS IS STABLE: if this file moves or loses its bounds, resumption has nowhere to live."""
    texte = (_RACINE / CHEMIN).read_text(encoding="utf-8")
    assert texte.count(MARQUEUR_DEBUT) == 1 and texte.count(MARQUEUR_FIN) == 1


def test_start_here_pointe_le_bilan() -> None:
    """*A document nothing points to does not exist* — applied to the repo's own door.

    TODO(public-mirror): needs human review — the private checkout's top-level orientation
    document is expected to point readers at the bilan file; this public mirror does not ship
    that document, so there is nothing here to read the assertion against."""
    pytest.skip("the private repo's top-level orientation document is not part of this public mirror")


def test_verifier_ne_touche_a_rien() -> None:
    avant = (_RACINE / CHEMIN).read_bytes()
    _lancer(VERIFIER="1", DATE="1999-01-01")
    assert (_RACINE / CHEMIN).read_bytes() == avant


def test_verifier_refuse_une_date_qui_n_est_pas_celle_du_fichier() -> None:
    """The probe BITES: without this witness, `VERIFIER=1` could go on refusing nothing at all."""
    fait = _lancer(VERIFIER="1", DATE="1999-01-01")
    assert fait.returncode == 1
    assert "DRIFTED" in fait.stdout


def test_un_bilan_absent_refuse_au_lieu_de_se_taire(tmp_path: Path) -> None:
    fait = _lancer(CLAUDE_PROJECT_DIR=str(tmp_path), VERIFIER="1")
    assert fait.returncode == 2
    assert "unreadable" in fait.stderr


def test_les_compteurs_prennent_les_MEMES_chemins_que_le_tick() -> None:
    """ THE FIRST-PULL BUG, FROZEN HERE. The four counters do NOT take the same shape of
 argument; passing the root to all four produced **0 open items** where the tick saw **5**. A
 counter that returns a plausible number for the wrong path never turns red on its own — so the
 two pulls are compared side by side."""
    from mnemosyne.production.signalements import open_signalement_count
    from mnemosyne.runtime.bilan_run import mesures

    par_le_bilan = next(m for m in mesures(_RACINE) if "field reports" in m.quoi)
    comme_le_tick = open_signalement_count(_RACINE / "docs" / "signalements")
    assert par_le_bilan.valeur == str(comme_le_tick)
    assert par_le_bilan.valeur != str(open_signalement_count(_RACINE)), (
        "the fixture no longer distinguishes the right path from the wrong one: this witness "
        "measures nothing anymore"
    )


def test_la_derive_NOMME_sa_premiere_ligne_avec_le_numero_du_DOCUMENT() -> None:
    """`B5`: *"refuse the commit by NAMING the first line that differs"*.

 **A refusal that does not say WHERE gets bypassed**: faced with a 16-line block, the reader
 re-runs the command without looking. The number is the DOCUMENT's — the one the editor
 displays — not the block's, or it would have to be converted by hand to be of any use.
 """
    document = "entete\n\n" + MARQUEUR_DEBUT + "\nalpha\nZULU\n" + MARQUEUR_FIN + "\n"
    frais = MARQUEUR_DEBUT + "\nalpha\nbravo\n" + MARQUEUR_FIN

    ou = premiere_ligne_qui_differe(document, frais)

    assert ou is not None
    assert "line 5" in ou, ou           # 3 header lines + the marker + alpha -> ZULU is the 5th
    assert "ZULU" in ou and "bravo" in ou, ou


def test_un_accord_parfait_ne_NOMME_rien() -> None:
    """The gate must stay silent when nothing has moved — otherwise it refuses every commit."""
    bloc = MARQUEUR_DEBUT + "\nalpha\nbravo\n" + MARQUEUR_FIN
    assert premiere_ligne_qui_differe("entete\n\n" + bloc + "\n", bloc) is None


def test_une_DERIVE_ne_rend_JAMAIS_None_meme_par_la_LONGUEUR() -> None:
    """ **Silence is the worst refusal**: returning `None` on a real drift says "up to date".

 Both blocks carry their markers, so a length that differs always makes a different pair
 appear — but that guarantee rests on a PROPERTY OF ANOTHER FUNCTION (`rendre_l_etat` keeps its
 markers). This witness holds it by the RESULT: whatever happens, a drift is NAMED. It also
 exercises the case where the fresh block has lost its marker — the guard branch.
 """
    document = "entete\n\n" + MARQUEUR_DEBUT + "\nalpha\nbravo\n" + MARQUEUR_FIN + "\n"

    assert premiere_ligne_qui_differe(document, MARQUEUR_DEBUT + "\nalpha\n" + MARQUEUR_FIN) is not None
    assert premiere_ligne_qui_differe(document, MARQUEUR_DEBUT + "\nalpha") is not None
    assert premiere_ligne_qui_differe(document, MARQUEUR_DEBUT + "\nalpha\nbravo\ncharlie\n" + MARQUEUR_FIN) is not None
