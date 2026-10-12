"""The veille-emit seam (anti-drift) -- the veille contract comes from the CODE, never a hand-copy.

Mirrors ``tests/distillation/test_emit_prompts.py``'s pattern for the sibling ``distill-emit`` seam: the
module under test (``system/skills/veilleur/veille.py``) is the ONE code home for the per-pass batch
bound, the extraction schema, and the printed contract; these lock that ``make veille``'s output is
always exactly what the code computes -- never a hand-typed schema or worklist that could silently
drift. Brick-free: a tmp distilled shelf + a tmp ledger stand in for a synthetic corpus (D126)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from _invariants import REPO_ROOT

_SCRIPT = REPO_ROOT / "system" / "skills" / "veilleur" / "veille.py"
_spec = importlib.util.spec_from_file_location("veille", _SCRIPT)
assert _spec is not None and _spec.loader is not None
veille = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(veille)

_DISTILLED_ROOT = Path(
    "knowledge/distilled"
)  # a plain relative root; never read from in these tests


def _fiche(distilled: Path, rel: str, text: str = "x") -> Path:
    path = distilled / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---- build_contract: empty worklist ---------------------------------------------------
def test_build_contract_is_honest_when_the_worklist_is_empty() -> None:
    out = veille.build_contract((), distilled_root=_DISTILLED_ROOT)
    assert "Nothing to survey" in out


def test_build_contract_empty_case_never_emits_a_worklist_or_schema() -> None:
    out = veille.build_contract((), distilled_root=_DISTILLED_ROOT)
    assert "WORKLIST" not in out
    assert "mark_surveyed" not in out


# ---- build_contract: non-empty worklist ------------------------------------------------
def test_build_contract_lists_every_worklist_fiche_with_its_resolved_path() -> None:
    worklist = ("finance/porter.md", "psycho/kahneman.md")
    out = veille.build_contract(worklist, distilled_root=_DISTILLED_ROOT)
    for fiche in worklist:
        assert fiche in out
        assert str(_DISTILLED_ROOT / fiche) in out


def test_build_contract_carries_the_three_finding_kinds() -> None:
    out = veille.build_contract(("finance/porter.md",), distilled_root=_DISTILLED_ROOT)
    for kind in ("principle", "skill", "hypothesis"):
        assert kind in out


def test_build_contract_names_the_staging_path_and_the_completion_call() -> None:
    from mnemosyne.production.veille_ledger import mark_surveyed

    out = veille.build_contract(("finance/porter.md",), distilled_root=_DISTILLED_ROOT)
    assert "knowledge/proposals/veille" in out
    # anti-drift: the completion call is DERIVED from the real symbol, so a rename can't ship a dead
    # reference that the test still blesses - assert the current qualified name IS what's emitted.
    assert f"{mark_surveyed.__module__}.{mark_surveyed.__qualname__}(" in out


def test_build_contract_carries_the_propose_never_impose_framing() -> None:
    out = veille.build_contract(("finance/porter.md",), distilled_root=_DISTILLED_ROOT)
    assert "NEVER impose" in out
    assert "INERT" in out


# ---- anti-drift: the schema block is the REAL constant, never a hand-copy -------------
def test_contract_schema_block_equals_the_real_veille_schema_dump() -> None:
    out = veille.build_contract(("finance/porter.md",), distilled_root=_DISTILLED_ROOT)
    expected = json.dumps(veille.VEILLE_SCHEMA, indent=2, ensure_ascii=False)
    assert expected in out


def test_veille_schema_has_exactly_the_five_required_keys() -> None:
    assert set(veille.VEILLE_SCHEMA["required"]) == {
        "kind",
        "statement",
        "rationale",
        "source",
        "proposed_test",
    }
    assert veille.VEILLE_SCHEMA["properties"]["kind"]["enum"] == [
        "principle",
        "skill",
        "hypothesis",
    ]


# ---- build_worklist: the per-pass batch cap -------------------------------------------
def test_build_worklist_respects_the_batch_cap_and_stays_sorted(tmp_path: Path) -> None:
    distilled = tmp_path / "distilled"
    n = veille.DEFAULT_BATCH + 5
    ids = [f"dom/book{i:03d}.md" for i in range(n)]
    for rel in ids:
        _fiche(distilled, rel)
    ledger = tmp_path / "veille.jsonl"

    worklist = veille.build_worklist(distilled, ledger_path=ledger, batch=3)
    assert worklist == tuple(sorted(ids)[:3])
    assert len(worklist) == 3


def test_build_worklist_defaults_to_default_batch(tmp_path: Path) -> None:
    distilled = tmp_path / "distilled"
    n = veille.DEFAULT_BATCH + 5
    for i in range(n):
        _fiche(distilled, f"dom/book{i:03d}.md")
    ledger = tmp_path / "veille.jsonl"

    worklist = veille.build_worklist(distilled, ledger_path=ledger)
    assert len(worklist) == veille.DEFAULT_BATCH


def test_build_worklist_excludes_already_surveyed_fiches(tmp_path: Path) -> None:
    distilled = tmp_path / "distilled"
    _fiche(distilled, "finance/porter.md")
    _fiche(distilled, "psycho/kahneman.md")
    ledger = tmp_path / "veille.jsonl"
    from mnemosyne.production.veille_ledger import mark_surveyed

    mark_surveyed("finance/porter.md", ledger_path=ledger)

    worklist = veille.build_worklist(distilled, ledger_path=ledger)
    assert worklist == ("psycho/kahneman.md",)


# ---- _slug: draft filename derivation --------------------------------------------------
def test_slug_lowercases_drops_the_extension_and_replaces_separators() -> None:
    assert veille._slug("finance/porter.md").startswith("finance-porter-")  # readable base + digest
    assert veille._slug("Psycho/Kahneman Thinking.md").startswith("psycho-kahneman-thinking-")


def test_slug_bounds_over_long_ids_and_stays_collision_free() -> None:
    """Real fiche ids run 200+ chars (long titles) - the slug must not overrun the APFS filename limit."""
    long_a = "finance/" + "a very long book title " * 20 + "alpha.md"
    long_b = "finance/" + "a very long book title " * 20 + "beta.md"  # same 80-char prefix as A
    slug_a, slug_b = veille._slug(long_a), veille._slug(long_b)
    assert len(slug_a) <= veille._SLUG_MAXLEN + 11  # cap + "-" + 10-hex digest
    assert slug_a != slug_b  # the digest of the FULL id keeps near-identical titles distinct


def test_slug_never_collides_for_short_ids_that_normalize_equal() -> None:
    """Distinct short ids that normalize to the same base ('a/b' vs 'a-b') must not share a draft path."""
    assert veille._slug("a/b.md") != veille._slug(
        "a-b.md"
    )  # the always-on digest disambiguates (D44)
