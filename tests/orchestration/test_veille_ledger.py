"""The veille ledger (Q5) - the append-only memory of which distilled fiches a veille pass surveyed.

These prove the non-repetition floor of the veille nerve: the worklist is exactly {fiches on disk} −
{surveyed}, navigation/index stubs never inflate it (the tick-README false-nudge lesson), the read is
fail-open over a missing / garbled ledger, and marking is strictly append-only + idempotent (D44).
Brick-free over a temp shelf (D126)."""

from __future__ import annotations

from pathlib import Path

from mnemosyne.production.veille_ledger import (
    fiche_id,
    mark_surveyed,
    surveyed_ids,
    unsurveyed_fiche_count,
    unsurveyed_fiches,
)


def _fiche(distilled: Path, rel: str, text: str = "x") -> Path:
    path = distilled / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---- surveyed_ids (fail-open read) ---------------------------------------------------
def test_surveyed_ids_is_empty_when_the_ledger_is_absent(tmp_path: Path) -> None:
    assert surveyed_ids(tmp_path / "nope.jsonl") == frozenset()


def test_surveyed_ids_skips_blank_and_garbled_lines(tmp_path: Path) -> None:
    """A best-effort memory: one corrupt byte re-surveys a fiche (idempotent), it never crashes the pass."""
    ledger = tmp_path / "veille.jsonl"
    ledger.write_text(
        '{"fiche": "a/one.md"}\n\n{not json}\n{"fiche": ""}\n{"other": 1}\n{"fiche": "b/two.md"}\n',
        encoding="utf-8",
    )
    assert surveyed_ids(ledger) == frozenset({"a/one.md", "b/two.md"})


# ---- mark_surveyed (append-only, idempotent, non-destructive) -------------------------
def test_mark_surveyed_appends_and_reads_back(tmp_path: Path) -> None:
    ledger = tmp_path / "state" / "veille.jsonl"  # parent created on first mark
    mark_surveyed("a/one.md", ledger_path=ledger)
    mark_surveyed("b/two.md", ledger_path=ledger)
    assert surveyed_ids(ledger) == frozenset({"a/one.md", "b/two.md"})


def test_mark_surveyed_is_idempotent_and_never_rewrites_history(tmp_path: Path) -> None:
    """Re-marking the same fiche adds no second line - strictly append-only, no duplicate growth (D44)."""
    ledger = tmp_path / "veille.jsonl"
    mark_surveyed("a/one.md", ledger_path=ledger)
    mark_surveyed("a/one.md", ledger_path=ledger)
    assert ledger.read_text(encoding="utf-8").count("a/one.md") == 1


# ---- unsurveyed_fiches / count (the worklist = on-disk − surveyed) --------------------
def test_unsurveyed_lists_fiches_not_yet_in_the_ledger_sorted(tmp_path: Path) -> None:
    distilled = tmp_path / "distilled"
    _fiche(distilled, "finance/porter.md")
    _fiche(distilled, "psycho/kahneman.md")
    ledger = tmp_path / "veille.jsonl"
    mark_surveyed("finance/porter.md", ledger_path=ledger)

    assert unsurveyed_fiches(distilled, ledger_path=ledger) == ("psycho/kahneman.md",)
    assert unsurveyed_fiche_count(distilled, ledger_path=ledger) == 1


def test_unsurveyed_skips_readme_moc_index_and_dotfiles(tmp_path: Path) -> None:
    """Navigation / index stubs are not fiches - counting them would manufacture a false nudge."""
    distilled = tmp_path / "distilled"
    _fiche(distilled, "finance/porter.md")
    _fiche(distilled, "finance/README.md")
    _fiche(distilled, "MOC.md")
    _fiche(distilled, "finance/index.md")
    _fiche(distilled, "finance/.hidden.md")
    ledger = tmp_path / "veille.jsonl"

    assert unsurveyed_fiches(distilled, ledger_path=ledger) == ("finance/porter.md",)


def test_unsurveyed_is_empty_when_no_distilled_root(tmp_path: Path) -> None:
    assert unsurveyed_fiches(tmp_path / "absent", ledger_path=tmp_path / "l.jsonl") == ()
    assert unsurveyed_fiche_count(tmp_path / "absent", ledger_path=tmp_path / "l.jsonl") == 0


def test_fiche_id_is_the_posix_path_relative_to_the_distilled_root(tmp_path: Path) -> None:
    distilled = tmp_path / "distilled"
    path = _fiche(distilled, "finance/porter.md")
    assert fiche_id(distilled, path) == "finance/porter.md"
