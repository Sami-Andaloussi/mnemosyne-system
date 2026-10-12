"""G9 -- witnesses for PRECEDENCE (a repository procedure takes priority over the prompt of a mandate).

The FIVE surfaces: 1. the JUDGE · 2. the RC (`main`) · 3. the published TEXT · 4. the PRODUCTION
VALUE (the real root, the real addresses, **and the mandate `lot_emit.rendre()` REALLY emits**) ·
5. the PASSING CASE.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production import lot_emit
from mnemosyne.production.precedence import (
    ADRESSE_ABSENTE,
    ADRESSE_MORTE,
    ADRESSES_QUI_PRIMENT,
    CLAUSE,
    CLAUSE_ABSENTE,
    GENRES,
    adresses_manquantes,
    resume,
    verdicts,
)
from mnemosyne.runtime import precedence_run as bord

_TOUTES = frozenset(ADRESSES_QUI_PRIMENT)


# ─────────────────────────────  1. THE JUDGE  ─────────────────────────────


def test_adresses_manquantes_rend_l_ORDRE_GELE_jamais_un_tri():
    """A refusal must read in the same order as the constant it is faulting."""
    assert adresses_manquantes("") == ADRESSES_QUI_PRIMENT
    assert adresses_manquantes(CLAUSE) == ()
    partiel = "we cite docs/signalements/README.md and CLAUDE.md, nothing else"
    assert adresses_manquantes(partiel) == (
        "ARCHITECTURE.md",
        "CONTRIBUTING.md",
        "docs/FORMAT_PLAN.md",
    )


def test_une_CLAUSE_ABSENTE_est_nommee_AVANT_les_adresses():
    """A mandate with no clause does not have an address problem: it has no precedence at all."""
    trouves = verdicts("# MANDATE -- arc A\n", adresses_vivantes=_TOUTES)
    assert trouves[0][0] == CLAUSE_ABSENTE
    assert {g for g, _ in trouves[1:]} == {ADRESSE_ABSENTE}


def test_une_ADRESSE_MORTE_est_un_ecart_MEME_quand_le_mandat_la_CITE():
    """*A pointer to nothing is worse than no pointer: it looks like a pointer.*"""
    vivantes = _TOUTES - {"docs/FORMAT_PLAN.md"}
    trouves = verdicts(CLAUSE, adresses_vivantes=vivantes)
    assert trouves == ((ADRESSE_MORTE, "docs/FORMAT_PLAN.md"),)


def test_les_ADRESSES_sont_gelees_en_ENSEMBLE_jamais_en_COMPTE():
    assert ADRESSES_QUI_PRIMENT == (
        "CLAUDE.md",
        "ARCHITECTURE.md",
        "CONTRIBUTING.md",
        "docs/FORMAT_PLAN.md",
        "docs/signalements/README.md",
    ), "swapping two addresses would leave the count identical and silent"
    assert GENRES == frozenset({"clause_absente", "adresse_absente", "adresse_morte"})


def test_la_CLAUSE_dit_les_TROIS_choses_qu_elle_doit_dire():
    """A single source: if the clause loses one of its three halves, the rule changes meaning."""
    assert "takes priority over THIS MANDATE" in CLAUSE, "the precedence itself"
    assert "you do not negotiate" in CLAUSE, "the recourse WITHOUT negotiation -- the heart of G9"
    assert "Nothing DETECTS a contradiction" in CLAUSE, "the admission: no semantic barrier"
    assert all(a in CLAUSE for a in ADRESSES_QUI_PRIMENT), "and the addresses, derived"


# ─────────────────────────  5. THE PASSING CASE  ─────────────────────────


def test_un_mandat_CONFORME_ne_rougit_PAS():
    """Without it, we only measure its ability to refuse everything."""
    assert verdicts(f"# MANDATE\n{CLAUSE}\n", adresses_vivantes=_TOUTES) == ()
    assert resume((), adresses=5).startswith("\U00002705")


# ─────────────────────────  3. THE PUBLISHED TEXT  ─────────────────────────


def test_le_texte_porte_TOUJOURS_le_nombre_d_adresses_verifiees():
    """"precedence carried" on zero addresses would read like "precedence carried" on five."""
    assert "5 address(es) that take priority, verified" in resume((), adresses=5)
    assert "0 address(es) that take priority, verified" in resume((), adresses=0)


def test_les_TROIS_phrases_de_refus_sont_DISTINCTES():
    texte = resume(
        (
            (CLAUSE_ABSENTE, ""),
            (ADRESSE_ABSENTE, "CLAUDE.md"),
            (ADRESSE_MORTE, "docs/FORMAT_PLAN.md"),
        ),
        adresses=5,
    )
    assert "3 gap(s)" in texte
    assert "CLAUSE ABSENT" in texte and "no recourse against its principal's error" in texte
    assert "ADDRESS NOT CITED — CLAUDE.md" in texte
    assert "DEAD ADDRESS — docs/FORMAT_PLAN.md" in texte
    assert "looks like a pointer" in texte


# ────────────────  4. THE PRODUCTION VALUE  ────────────────


def test_la_RACINE_de_production_designe_le_DEPOT_pas_system():
    assert (bord.RACINE / ".git").exists(), bord.RACINE
    assert (bord.RACINE / "CLAUDE.md").is_file(), bord.RACINE


def test_les_CINQ_adresses_EXISTENT_reellement_dans_ce_depot():
    """A dead address is not a hypothesis: it is what happens at the first `git mv`."""
    vivantes = bord.adresses_vivantes(bord.RACINE)
    assert vivantes == frozenset(ADRESSES_QUI_PRIMENT), sorted(set(ADRESSES_QUI_PRIMENT) - vivantes)


def test_LE_MANDAT_REELLEMENT_EMIS_PAR_CE_DEPOT_PORTE_LA_CLAUSE():
    """ **THE WIRING WITNESS, and it is the one that is always missing.** The witnesses above
 judge fabricated text; this one calls `lot_emit.rendre()`, this repository's only mandate
 emitter. Unwiring the clause from `rendre()` would leave them ALL green — the class *the
 barrier nothing calls*, measured twice elsewhere in this repository."""
    rendu = lot_emit.rendre(lot_emit.Mandat(arc="A", porte="PLAN.md", items=()), bord.RACINE)
    assert CLAUSE in rendu, "the clause no longer travels with the mandate"
    assert verdicts(rendu, adresses_vivantes=bord.adresses_vivantes(bord.RACINE)) == ()


def test_la_clause_voyage_MEME_sur_un_mandat_VIDE():
    """*A guarantee that depends on content is not a guarantee.*"""
    assert CLAUSE in bord.mandat_emis_ici(bord.RACINE)


# ─────────────────────────  2. THE RC / THE DECISION  ─────────────────────────


def test_rc_0_sur_le_mandat_REEL_de_ce_depot(capsys: pytest.CaptureFixture[str]):
    assert bord.main([], racine=bord.RACINE) == 0
    assert capsys.readouterr().out.startswith("\U00002705")


def test_rc_1_sur_un_mandat_SANS_clause(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    faux = tmp_path / "mandat.md"
    # The wording is free: `precedence_run.main()` READS this file and hands the whole text to
    # `verdicts()` — it parses nothing out of it. Any mandate that does not carry the clause is
    # judged the same way, which is exactly what this witness pins down.
    faux.write_text("# MANDATE — arc A\ngate: PLAN.md\n", encoding="utf-8")
    assert bord.main(["--mandat", str(faux)], racine=bord.RACINE) == 1, (
        "a hardcoded `return 0` would pass here"
    )
    assert "CLAUSE ABSENT" in capsys.readouterr().out


def test_rc_1_quand_une_ADRESSE_est_MORTE(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(bord, "adresses_vivantes", lambda _r: frozenset())
    assert bord.main([], racine=bord.RACINE) == 1
    assert "DEAD ADDRESS" in capsys.readouterr().out


def test_rc_2_quand_le_mandat_designe_est_ILLISIBLE(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Zero mandate read is NOT a compliant mandate."""
    assert bord.main(["--mandat", str(tmp_path / "absent.md")], racine=bord.RACINE) == 2
    # The exact phrase `precedence_run.main()` prints on an unreadable mandate. It is what
    # separates "NOT MEASURED" from "REFUSED": the rc alone cannot tell an instrument failure
    # from a non-conforming mandate, only the sentence can.
    assert "NOT MEASURED" in capsys.readouterr().err


def test_adresses_vivantes_LIT_VRAIMENT_LE_DISQUE(tmp_path: Path):
    """ **This witness closes a SURVIVING sabotage.** Replacing the body with
 `frozenset(ADRESSES_QUI_PRIMENT)` left 16 witnesses green: the production one compares the
 output to the complete set, so a liar that returns everything passes. It takes a root where
 the addresses are MISSING for the disk read to actually be exercised."""
    assert bord.adresses_vivantes(tmp_path) == frozenset(), "no address here"
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs" / "signalements").mkdir(parents=True)
    (tmp_path / "docs" / "signalements" / "README.md").write_text("x", encoding="utf-8")
    assert bord.adresses_vivantes(tmp_path) == frozenset(
        {"CLAUDE.md", "docs/signalements/README.md"}
    )


def test_une_adresse_qui_devient_un_DOSSIER_est_MORTE(tmp_path: Path):
    """`is_file`, not `exists`: a `git mv` that turns a document into a folder of the same name
    would leave `exists()` true and the address would point at nothing readable."""
    (tmp_path / "CLAUDE.md").mkdir()
    assert bord.adresses_vivantes(tmp_path) == frozenset()
