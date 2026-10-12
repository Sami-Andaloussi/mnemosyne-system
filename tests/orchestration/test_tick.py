"""The autonomy driver — ``tick`` runs one coordinated engine drain and surfaces proposals (Q1/Q3).

The "wake-up": the seam the SessionStart hook (and a later daemon/cron) calls so the proactive nerve
(soul ⑤) fires without a manual call. These prove it drives the engine end-to-end, surfaces the
meta-only intake signal from the REAL shelf, and stays silent when there is nothing to say. Brick-free
(D126); the drain touches no pipeline and every proposal is inert (propose, never impose, D92).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mnemosyne.production.veille_ledger import mark_surveyed
from mnemosyne.runtime.tick import render_proposals, run_tick


# ---- render (pure) -------------------------------------------------------------------
def test_render_is_honest_when_there_is_nothing_to_propose() -> None:
    assert "Rien à proposer" in render_proposals(())


def test_render_lists_each_proposal_summary() -> None:
    out = render_proposals(
        (SimpleNamespace(summary="3 sources sit un-homed …"), SimpleNamespace(summary="2 fiches await …"))
    )
    assert "2 propositions" in out  # plural agreement, human-facing
    assert "3 sources sit un-homed" in out and "2 fiches await" in out


def test_render_uses_the_singular_for_one() -> None:
    out = render_proposals((SimpleNamespace(summary="1 source sits un-homed …"),))
    assert "1 proposition " in out and "propositions" not in out


# ---- run_tick (brick-free integration over a temp shelf) -----------------------------
def test_run_tick_surfaces_the_intake_backlog_from_the_real_shelf(tmp_path: Path) -> None:
    """The driver drives the engine, and the meta-only intake signal reaches the receptacle (Q2 via tick)."""
    sas = tmp_path / "raw" / "_intake"
    sas.mkdir(parents=True)
    (sas / "an-unmapped-book.pdf").write_text("x", encoding="utf-8")
    (sas / "a-novel-theme.epub").write_text("y", encoding="utf-8")

    proposals = run_tick(knowledge_root=tmp_path)
    assert any("2 sources" in p.summary and "domain-new" in p.summary for p in proposals)
    assert all(p.reviewed is False for p in proposals)  # inert until the operator's review (propose, never impose)


def test_run_tick_raises_no_intake_nudge_when_the_sas_is_empty(tmp_path: Path) -> None:
    """No un-homed sources ⇒ the intake source is silent (no noise); robust to the queue's default state."""
    proposals = run_tick(knowledge_root=tmp_path)  # tmp_path has no raw/_intake
    assert not any("un-homed" in p.summary for p in proposals)


def test_run_tick_surfaces_the_veille_backlog_from_the_real_shelf(tmp_path: Path) -> None:
    """The driver surfaces the meta-only veille signal — N distilled fiches await mining (Q5 via tick)."""
    distilled = tmp_path / "distilled"
    (distilled / "finance").mkdir(parents=True)
    (distilled / "finance" / "porter.md").write_text("x", encoding="utf-8")
    (distilled / "psycho").mkdir(parents=True)
    (distilled / "psycho" / "kahneman.md").write_text("y", encoding="utf-8")
    ledger = tmp_path / "veille.jsonl"

    proposals = run_tick(knowledge_root=tmp_path, ledger_path=ledger)
    assert any("2 distilled fiches" in p.summary and "make veille" in p.summary for p in proposals)
    assert all(p.reviewed is False for p in proposals)  # inert until the operator's review (propose, never impose)


def test_run_tick_raises_no_veille_nudge_when_the_corpus_is_surveyed(tmp_path: Path) -> None:
    """Every fiche recorded in the ledger ⇒ the veille source is silent (no noise, non-repeating)."""
    distilled = tmp_path / "distilled"
    (distilled / "finance").mkdir(parents=True)
    (distilled / "finance" / "porter.md").write_text("x", encoding="utf-8")
    ledger = tmp_path / "veille.jsonl"
    mark_surveyed("finance/porter.md", ledger_path=ledger)

    proposals = run_tick(knowledge_root=tmp_path, ledger_path=ledger)
    assert not any("veille" in p.summary for p in proposals)


# ---- THE WIRING, not just the judge -------------------------------------------------------------
# CLASS MEASURED ON 2026-09-08, AND IT WAS OPEN FOR EVERY SOURCE IN THIS FILE.
# An isolated auditor cut the wiring of `moissons_en_attente_resume` inside `run_tick`: **76/76
# witnesses stayed GREEN**. Re-measured by the requester: identical. The suites exercised the
# JUDGES (`moisson_due`, `proposer`) and never the LINE that wires them in — a perfect, unplugged
# judge has exactly the appearance of a working judge. This is the "the barrier nothing calls"
# class applied to wiring, reproduced ONE HOUR after closing it elsewhere.
# None of the sibling sources has a wiring witness either (`grep moisson_due_resume` on this
# file -> 0). This one witness closes ONE; the others stay open, and it is written down rather
# than left to imply the class is closed.


def test_run_tick_surfaces_les_candidats_retenus_sans_epreuve(tmp_path: Path) -> None:
    """`I2-bis` REALLY travels through the tick — cutting its line inside `run_tick` must turn
    this RED."""
    moissons = tmp_path / "docs" / "moissons"
    moissons.mkdir(parents=True)
    (moissons / "m.md").write_text(
        'arc: "P/plan/01"\nretenus: 3\neprouves: 0\n\n**Panne :** mesuree.\n', encoding="utf-8"
    )
    proposals = run_tick(knowledge_root=tmp_path, repo_root=tmp_path)
    assert any("candidats RETENUS" in p.summary for p in proposals), (
        "the I2-bis source does not travel through run_tick — the wiring is cut"
    )
    assert all(p.reviewed is False for p in proposals)  # inert (propose, never impose, D92)


def test_run_tick_reste_silencieux_quand_tout_est_eprouve(tmp_path: Path) -> None:
    """THE PASSING CASE of the wiring — without it, a source that ALWAYS spoke would pass the
    witness above, and the tick would publish noise on every startup."""
    moissons = tmp_path / "docs" / "moissons"
    moissons.mkdir(parents=True)
    (moissons / "m.md").write_text(
        'arc: "P/plan/01"\nretenus: 3\neprouves: 3\n\n**Panne :** mesuree.\n', encoding="utf-8"
    )
    proposals = run_tick(knowledge_root=tmp_path, repo_root=tmp_path)
    assert not any("candidats RETENUS" in p.summary for p in proposals)
