# SPDX-License-Identifier: MIT
"""`E2` — the edge (`runtime/orchestration_run.py`): the SAME three return codes as `make carte`,
the SAME door reader (`read_plan_tree`, never a second disk walk).
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_le_bord_REFUSE_de_calculer_sur_un_plan_ILLISIBLE(tmp_path, monkeypatch, capsys):
    """*A ceiling computed on a STALE source is an exact lie* — same discipline as `carte_run`."""
    from mnemosyne.runtime import orchestration_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PLAN.md").write_text("no plan title at all\n", encoding="utf-8")
    assert orchestration_run.main([]) == 1
    erreur = capsys.readouterr().err
    assert "UNREADABLE" in erreur


def test_le_bord_distingue_PAS_DE_PLAN_de_PLAN_CASSE(tmp_path, monkeypatch, capsys):
    """"No plan here" and "broken plan" are two different messages."""
    from mnemosyne.runtime import orchestration_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "docs").mkdir()
    assert orchestration_run.main([]) == 2, "no plan door -> rc 2, never rc 1"
    assert "no plan door" in capsys.readouterr().err


def test_C8_une_variable_VOISINE_MECONNUE_est_REFUSEE_au_lieu_de_retomber_en_silence(
    tmp_path, monkeypatch, capsys
) -> None:
    """C8: `make` silently ignores a variable it does not know — `PLAN=` instead of `POUR=` used
    to fall back in silence onto Mnémosyne's own plan and render an exact number on the WRONG
    population. Triggered, not deduced: the refusal names `PLAN=` precisely, never a generic
    heuristic."""
    from mnemosyne.runtime import orchestration_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("PLAN", "/some/arbitrary/path")
    monkeypatch.delenv("POUR", raising=False)
    assert orchestration_run.main([]) == 2
    erreur = capsys.readouterr().err
    assert "PLAN=" in erreur and "POUR=" in erreur, erreur


def test_C8_POUR_correct_prime_sur_un_voisin_present_par_accident(
    tmp_path, monkeypatch, capsys
) -> None:
    """A correctly-set `POUR=` is never blocked by a neighbor variable that happens to also be
    lying around in the environment — only the ABSENCE of `POUR` together with a present neighbor
    is a confusion signal."""
    from mnemosyne.runtime import orchestration_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "cible").mkdir()
    (tmp_path / "cible" / "PLAN.md").write_text(
        "# PLAN — neighbor\n\n> **Cap** : test.\n\n## Les etapes\n\n"
        "- **A1** \U00002B1C **Alone.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POUR", str(tmp_path / "cible"))
    monkeypatch.setenv("PLAN", "/some/arbitrary/path")
    assert orchestration_run.main([]) == 0
    assert "plan measured" in capsys.readouterr().out


def test_C8_la_sortie_NOMME_le_plan_mesure(tmp_path, monkeypatch, capsys) -> None:
    """The defect that bit: the number was correct, the POPULATION was never stated. The very
    first line of output must now name what was measured."""
    from mnemosyne.runtime import orchestration_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PLAN.md").write_text(
        "# PLAN — fixture\n\n> **Cap** : test.\n\n## Les etapes\n\n"
        "- **A1** \U00002B1C **Alone.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("POUR", raising=False)
    assert orchestration_run.main([]) == 0
    assert "plan measured: Mnémosyne" in capsys.readouterr().out


def test_le_bord_rend_la_borne_du_VRAI_depot(capsys):
    """**STRENGTHENED AFTER AUDIT (D75): this witness only checked the PRESENCE of substrings,
    never a VALUE** — a smoke witness, not a ceiling witness. `orchestration_run.main` could print
    any number at all and this witness would stay green. It now compares the edge's output
    against the SAME calculation, drawn from the pure functions (`largeur_vague_en_arcs`/
    `borne_chats`) on the same reading — not a frozen number that would go stale on the first
    closed item."""
    from mnemosyne.production.orchestration import borne_chats, largeur_vague_en_arcs
    from mnemosyne.production.plan_registry import read_plan_tree
    from mnemosyne.runtime import orchestration_run

    assert orchestration_run.main([]) == 0
    sortie = capsys.readouterr().out

    plans = read_plan_tree(REPO / "docs", "Mnémosyne")
    reading = plans[0].reading
    assert reading is not None
    largeur = largeur_vague_en_arcs(reading)
    borne = borne_chats(reading)
    assert f"wave width (startable arcs): {largeur}" in sortie, sortie
    assert f"chats to launch: {borne}" in sortie, sortie


def test_le_bord_calcule_sur_un_plan_MINIMAL_ecrit_a_la_main(tmp_path, monkeypatch, capsys):
    """A plan with two arcs, one free and one blocked — the ceiling must reflect EXACTLY what the
    file declares, not a default value."""
    from mnemosyne.runtime import orchestration_run

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PLAN.md").write_text(
        "# PLAN — fixture\n\n> **Cap** : test.\n\n## Les etapes\n\n"
        "- **A1** \U00002B1C **Free.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : AUCUNE\n  *Prérequis* : AUCUN\n"
        "- **B1** \U00002B1C **Blocked.**\n  *Produit* : x\n  *Fini quand* : c\n"
        "  *Dépend de* : A1\n  *Prérequis* : AUCUN\n",
        encoding="utf-8",
    )
    assert orchestration_run.main([]) == 0
    sortie = capsys.readouterr().out
    assert "wave width (startable arcs): 1" in sortie, sortie
    assert "chats to launch: 1" in sortie, sortie
