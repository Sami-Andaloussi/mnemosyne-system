"""Behavior tests for the domain lifecycle (D46) - create a new library domain, governed.

Pins the pure planner + the two SAFE writes (shelf tree, taxonomy line) + the honest hand-off of the
governed third (the POLICY_WRITE gesture, EMITTED for a human, never written here). Code & docstrings
English (D117); the shelf / domain / family tokens stay as graven in the toml (D33)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from mnemosyne.ingest.domain_lifecycle import (
    DomainLifecycleError,
    create_domain,
    insert_taxonomy_line,
    plan_new_domain,
)

# A minimal but representative taxonomy: [domains] with two family blocks, then [types].
_TAXO = """# Taxonomie - source de verite.
[domains]
# --- Famille Finance ---
asset-pricing = ["Finance", "Investing"]
crypto        = ["Finance", "Assets"]
# --- Famille General ---
misc          = ["General", "Misc"]

[types]
allowed = ["books", "web"]
default = "books"
"""


def _plan(
    domain="macro", family="Economics", group="Macro", *, mapped=frozenset(), declared=frozenset()
):
    return plan_new_domain(domain, family, group, mapped_domains=mapped, declared_domains=declared)


# ---- pure planner --------------------------------------------------------------------
def test_plan_computes_shelf_taxonomy_line_and_policy_hint() -> None:
    plan = _plan()
    assert plan.raw_shelf == Path("Economics/Macro/macro/books")
    assert plan.distilled_shelf == plan.raw_shelf
    assert plan.taxonomy_line == 'macro = ["Economics", "Macro"]'
    assert "POLICY_WRITE" in plan.policy_hint and '"macro"' in plan.policy_hint
    assert plan.already_mapped is False and plan.already_declared is False


def test_plan_reflects_already_mapped_and_declared() -> None:
    plan = _plan(mapped=frozenset({"macro"}), declared=frozenset({"macro"}))
    assert plan.already_mapped is True and plan.already_declared is True


def test_plan_refuses_a_malformed_domain_or_family() -> None:
    with pytest.raises(DomainLifecycleError):
        _plan(domain="Macro Econ")  # uppercase + space
    with pytest.raises(DomainLifecycleError):
        _plan(domain="../evil")  # path separator
    with pytest.raises(DomainLifecycleError):
        _plan(
            domain="macro\n"
        )  # trailing newline (\Z-anchored, not $ - M1) - never a junk shelf name
    with pytest.raises(DomainLifecycleError):
        _plan(family="Bad/Family")


# ---- pure taxonomy inserter ----------------------------------------------------------
def test_insert_under_an_existing_family_lands_in_that_block() -> None:
    out = insert_taxonomy_line(_TAXO, "value-investing", "Finance", "Investing")
    data = tomllib.loads(out)  # round-trips
    assert data["domains"]["value-investing"] == ["Finance", "Investing"]
    # grouped: the new line sits inside the Finance block (after crypto, before the General comment).
    assert out.index("value-investing") < out.index("# --- Famille General ---")
    assert out.count("# --- Famille Finance ---") == 1  # no duplicate family block


def test_insert_a_new_family_creates_a_block_before_types() -> None:
    out = insert_taxonomy_line(_TAXO, "macro", "Economics", "Macro")
    data = tomllib.loads(out)
    assert data["domains"]["macro"] == ["Economics", "Macro"]
    assert out.count("# --- Famille Economics ---") == 1
    assert out.index("# --- Famille Economics ---") < out.index("[types]")
    assert out.index("misc") < out.index(
        "# --- Famille Economics ---"
    )  # appended after existing domains


def test_insert_raises_without_a_domains_table() -> None:
    with pytest.raises(DomainLifecycleError):
        insert_taxonomy_line('[types]\ndefault = "books"\n', "macro", "Economics", "Macro")


# ---- create_domain (I/O on tmp_path) -------------------------------------------------
def test_create_domain_makes_the_tree_writes_taxonomy_and_never_touches_policy(
    tmp_path: Path,
) -> None:
    raw, distilled = tmp_path / "raw", tmp_path / "distilled"
    taxo = tmp_path / "taxonomy.toml"
    taxo.write_text(_TAXO, encoding="utf-8")
    plan = _plan()  # macro / Economics / Macro, not yet mapped

    create_domain(plan, raw_root=raw, distilled_root=distilled, taxonomy_path=taxo)

    assert (raw / "Economics/Macro/macro/books").is_dir()
    assert (distilled / "Economics/Macro/macro/books").is_dir()
    data = tomllib.loads(taxo.read_text(encoding="utf-8"))
    assert data["domains"]["macro"] == ["Economics", "Macro"]
    assert (tmp_path / "taxonomy.toml.bak").exists()  # backed up once (non-destructive)
    assert not (tmp_path / "policy.toml").exists()  # policy is a human gesture - never written here


def test_create_domain_is_idempotent_for_an_already_mapped_domain(tmp_path: Path) -> None:
    raw, distilled = tmp_path / "raw", tmp_path / "distilled"
    taxo = tmp_path / "taxonomy.toml"
    taxo.write_text(_TAXO, encoding="utf-8")
    plan = _plan(domain="crypto", family="Finance", group="Assets", mapped=frozenset({"crypto"}))

    create_domain(plan, raw_root=raw, distilled_root=distilled, taxonomy_path=taxo)

    assert (raw / "Finance/Assets/crypto/books").is_dir()  # tree still (idempotently) ensured
    assert taxo.read_text(encoding="utf-8") == _TAXO  # taxonomy untouched (already mapped)
    assert not (tmp_path / "taxonomy.toml.bak").exists()  # no write => no backup


# ---- door render (honest hand-off) ---------------------------------------------------
def test_render_flags_the_policy_gesture_when_undeclared() -> None:
    from mnemosyne.runtime.domain_new import render_domain_result

    out = render_domain_result(_plan())
    assert "POLICY_WRITE" in out and "[OPERATOR]" in out
    assert "withheld from recall" in out


def test_render_says_ready_when_already_declared() -> None:
    from mnemosyne.runtime.domain_new import render_domain_result

    out = render_domain_result(_plan(mapped=frozenset({"macro"}), declared=frozenset({"macro"})))
    assert "ready" in out.lower()
    assert "already mapped" in out  # taxonomy-untouched line
