"""The CLI edge of H6 — `make plan-mandat` finally publishes the derived mandate, never built
before today (measured 2026-08-16: nothing in the repo called `plan_mandat` outside its own
witnesses). Level 1: prints to stdout, writes nothing, refuses only an unreadable plan.

**12:5x — chat 1, judge: the first four witnesses all drew from ONE SINGLE population, the
toy fixture below, never this repo's real `docs/`.** Fixed by adding a fifth witness that
overwrites NOTHING of _REPO_ROOT -- same pattern as `test_plan_convert.py:56`
(`plan_files(_REPO_ROOT / "docs")` called as-is, with no monkeypatch).
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.runtime import plan_mandat_run

_DOOR = """\
# PLAN — Test H6

> **Cap** : verify the CLI edge of the derived mandate

## The arcs

- `plan/arc-a.md` — Arc A

## What this project declares

_Nothing declared._
"""

_ARC = """\
# Arc A

- **Z1** \U00002B1C An item with no dependency, therefore startable.
  *Dépend de* : AUCUNE
- **A9** \U00002B1C A second item with no dependency.
  *Dépend de* : AUCUNE
"""


def _projet(repo_root: Path) -> None:
    """A TOY plan, written as REAL files on disk (never a string fixture imitating one) -- under
    ``docs/``, the only `PLAN_ROOTS` `scan_plans` knows. **This is NOT this repo's REAL
    plan**: two items, zero dependencies -- see
    `test_le_mandat_derive_publie_reellement_sur_CE_depot` for the second population."""
    docs = repo_root / "docs"
    (docs / "plan").mkdir(parents=True)
    (docs / "PLAN.md").write_text(_DOOR, encoding="utf-8")
    (docs / "plan" / "arc-a.md").write_text(_ARC, encoding="utf-8")


def test_publie_le_mandat_derive_sur_un_plan_reel(tmp_path, monkeypatch, capsys) -> None:
    _projet(tmp_path)
    monkeypatch.setattr(plan_mandat_run, "_REPO_ROOT", tmp_path)
    rc = plan_mandat_run.main([])
    assert rc == 0
    sortie = capsys.readouterr().out
    assert "Z1" in sortie and "A9" in sortie
    assert "derived mandate" in sortie


def test_n_borne_le_nombre_de_tetes_publiees(tmp_path, monkeypatch, capsys) -> None:
    _projet(tmp_path)
    monkeypatch.setattr(plan_mandat_run, "_REPO_ROOT", tmp_path)
    rc = plan_mandat_run.main(["--n", "1"])
    assert rc == 0
    sortie = capsys.readouterr().out
    assert sortie.count("#1") == 1
    assert "#2" not in sortie


def test_refuse_sur_un_plan_illisible(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(plan_mandat_run, "_REPO_ROOT", tmp_path)
    rc = plan_mandat_run.main(["--plan", "docs-absent"])
    assert rc == 2
    assert "REFUSED" in capsys.readouterr().err


def test_n_ecrit_aucun_fichier(tmp_path, monkeypatch, capsys) -> None:
    """Level 1: this repo's *-emit pattern writes nothing, the mandate goes out on stdout alone."""
    _projet(tmp_path)
    monkeypatch.setattr(plan_mandat_run, "_REPO_ROOT", tmp_path)
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file())
    plan_mandat_run.main([])
    capsys.readouterr()
    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file())
    assert before == after


def test_le_mandat_derive_publie_reellement_sur_CE_depot(capsys) -> None:
    """A second population, genuinely different: `_REPO_ROOT` NOT monkeypatched --
    `plan_mandat_run` reads this repo's REAL `docs/`, exactly as `make plan-mandat` would for
    real. Does NOT assert a specific ident: the living plan closes items every round, a
    hard-coded ident would go red for a reason that is not a defect. Recomputes the expected
    value at test time, with the SAME accessor as the CLI -- if the two diverge, that is a real
    defect."""
    from mnemosyne.production.plan_mandat import mandat_derive, rendre_mandat
    from mnemosyne.production.plan_registry import scan_plans
    from mnemosyne.runtime.plan_mandat_run import _REPO_ROOT

    projet = next(
        p for p in scan_plans(_REPO_ROOT).projects if p.plan_path.parent.name == "docs"
    )
    attendu = rendre_mandat(mandat_derive(projet.reading, racine=_REPO_ROOT))

    rc = plan_mandat_run.main([])
    assert rc == 0
    sortie = capsys.readouterr().out
    assert sortie == "\n".join(attendu) + "\n"
