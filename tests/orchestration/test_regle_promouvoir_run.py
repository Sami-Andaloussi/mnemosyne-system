"""I3(b) -- the connector GETS ITSELF JUDGED: does `exiger_panne_declaree` really have a caller?

 **WHAT THIS FILE PROVES, AND IT IS THE WHOLE POINT OF `I3`**: an isolated audit measured that
`production/regle_candidate.py::exiger_panne_declaree` had NO real caller -- no `make` target, no
hook, no production site. The project's governance documentation is explicit: *"the level is that of its
CALLER, never that of its code."* These witnesses therefore never invoke the judge's function
directly: they ALL go through `main()`, the real caller, exactly as it would be exercised from the
command line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.runtime.regle_promouvoir_run import main, nom_de_skill


# ── nom_de_skill: a PROPOSED name, never a guarantee ────────────────────────────────


def test_nom_de_skill_retire_la_date_et_le_mot_proposition() -> None:
    assert nom_de_skill(Path("2026-08-09-proposition-harnais-de-sabotage.md")) == "harnais-de-sabotage"


def test_nom_de_skill_sans_prefixe_reconnu_garde_le_nom() -> None:
    assert nom_de_skill(Path("methode-divergence.md")) == "methode-divergence"


def test_nom_de_skill_ne_rend_jamais_une_chaine_vide() -> None:
    """If both prefixes strip EVERYTHING (a name that was ONLY the date), the original name
    comes back instead of an empty string -- a nameless skill is not a usable proposal."""
    assert nom_de_skill(Path("2026-08-09-.md")) != ""


# ── main(): the REAL caller, refuses or names -- never promotes on its own ───────────────────


def _ecrire(tmp_path: Path, nom: str, texte: str) -> Path:
    chemin = tmp_path / nom
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def test_refuse_une_fiche_sans_panne_declaree(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fiche = _ecrire(tmp_path, "sans-panne.md", "# Une proposition\n\nAucune declaration ici.\n")
    rc = main([str(fiche)])
    assert rc == 1
    sortie = capsys.readouterr()
    assert "REFUSED" in sortie.err
    assert "sans-panne.md" in sortie.err


def test_refuse_une_panne_declaree_sans_chiffre(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fiche = _ecrire(tmp_path, "panne-vague.md", "# X\n\n**Panne :** ca casse parfois.\n")
    rc = main([str(fiche)])
    assert rc == 1
    assert "NO FIGURE" in capsys.readouterr().err


def test_promouvable_avec_un_chiffre_reel(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fiche = _ecrire(
        tmp_path,
        "2026-08-09-proposition-harnais-de-sabotage.md",
        "# X\n\n**Panne :** 4 sur 7 tentatives ont trouve un defaut invisible a la relecture.\n",
    )
    rc = main([str(fiche)])
    assert rc == 0
    sortie = capsys.readouterr().out
    assert "PROMOTABLE" in sortie
    assert "skill-new" in sortie and "NAME=harnais-de-sabotage" in sortie
    assert "skill-eprouver SKILL=harnais-de-sabotage" in sortie
    assert "skill-juger" in sortie and "skill-verdict" in sortie


def test_promouvable_avec_un_aveu_sans_chiffre(tmp_path: Path) -> None:
    """The admission is a valid, free response (A2) -- it must pass, not only the figure."""
    fiche = _ecrire(tmp_path, "aveu.md", "# X\n\n**Panne :** aucune mesuree.\n")
    assert main([str(fiche)]) == 0


def test_ne_lance_JAMAIS_le_skill_eprouver_lui_meme(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The module NAMES the next chain, it never EXECUTES it -- that is the boundary its own
    module explicitly writes (`make skill-eprouver` requires an already-built skill, which this
    module does not build)."""
    fiche = _ecrire(tmp_path, "x.md", "# X\n\n**Panne :** x8 plus lent.\n")
    main([str(fiche)])
    sortie = capsys.readouterr().out
    assert "nothing below is launched by this module" in sortie


def test_fiche_absente_refuse_au_lieu_de_lever(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`lire_fiche` renders an undeclared candidacy on an unreadable file -- the gate refuses
    with its normal message, it never crashes."""
    rc = main([str(tmp_path / "n-existe-pas.md")])
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().err


def test_usage_sur_un_mauvais_nombre_d_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert main(["a", "b"]) == 2
    assert "usage" in capsys.readouterr().err
