"""The CLI half of H3 — dry-run by default, writes only under `--apply`, and never before the
byte-level proof has already passed. Real files, a real `tmp_path`, never a mock of the filesystem.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production.plan_corbeille import RETIRES_DIRNAME
from mnemosyne.production.plan_format import read_plan
from mnemosyne.production.plan_retrait import applique_retrait
from mnemosyne.runtime import plan_corbeille_run

_DOOR = """\
# PLAN — Test H3

> **Cap** : verify the trash module

## The arcs

- `plan/arc-a.md` — Arc A

## What this project declares

_Nothing declared._
"""

_ARC = """\
# Arc A

- **A1** \U00002B1C A normal item, never touched.
- **A2** \U00002B1C An item H1 will retire, then H3 will move.
  *Produit* : something concrete
  *Fini quand* : condition verified
- **A3** \U00002B1C A third item, never touched either.
"""


def _projet(tmp_path: Path, *, retirer_a2: bool = True) -> Path:
    """A REAL door + `plan/` folder, on disk — never a fixture of strings pretending to be one."""
    (tmp_path / "plan").mkdir()
    (tmp_path / "PLAN.md").write_text(_DOOR, encoding="utf-8")
    arc_text = _ARC
    if retirer_a2:
        arc_text = applique_retrait(
            arc_text,
            ("A2",),
            motif="test reason",
            cout="none",
            id_retrait="deadbeef0001",
            quand="2026-08-16T00:00:00+00:00",
        )
    (tmp_path / "plan" / "arc-a.md").write_text(arc_text, encoding="utf-8")
    return tmp_path / "plan" / "arc-a.md"


def _run(*args: str) -> int:
    return plan_corbeille_run.main(list(args))


# --- 1. the trash sits BESIDE `plan/`, never inside it -------------------------------------------


def test_retires_root_of_est_A_COTE_de_plan_JAMAIS_DEDANS(tmp_path: Path) -> None:
    """Measured: a literal `.md` under `plan/` is read as an ARC at any depth
    (plan_format.plan_entries). A `plan/retires/x.md` would therefore be an `arc_hors_index` — this
    function must render a path BESIDE `plan/`, never inside it."""
    arc_path = _projet(tmp_path, retirer_a2=False)
    retires_root, link_dir = plan_corbeille_run.retires_root_of(arc_path)

    assert retires_root == tmp_path / RETIRES_DIRNAME
    assert not str(retires_root).startswith(str(tmp_path / "plan") + "/")
    assert link_dir == f"../{RETIRES_DIRNAME}"


# --- 2. dry run by default: nothing is written -----------------------------------------------------


def test_SEC_PAR_DEFAUT_n_ecrit_RIEN(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    arc_path = _projet(tmp_path)
    avant = arc_path.read_text(encoding="utf-8")

    rc = _run(str(arc_path), "--item", "A2", "--remplace", "see H4", "--today", "2026-08-16")

    assert rc == 0
    assert arc_path.read_text(encoding="utf-8") == avant, "the dry run wrote into the arc"
    assert not (tmp_path / RETIRES_DIRNAME).exists(), "the dry run created the trash folder"
    assert "DRY RUN" in capsys.readouterr().out


# --- 3. --apply writes BOTH files, trash copy FIRST ------------------------------------------------


def test_APPLY_ecrit_la_corbeille_ET_reecrit_l_arc(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arc_path = _projet(tmp_path)

    rc = _run(
        str(arc_path), "--item", "A2", "--remplace", "see H4", "--today", "2026-08-16", "--apply"
    )

    assert rc == 0
    corbeille = tmp_path / RETIRES_DIRNAME / "retire-2026-08-16-a2.md"
    assert corbeille.is_file()
    assert "A2" in corbeille.read_text(encoding="utf-8")
    assert "see H4" in corbeille.read_text(encoding="utf-8")

    reading = read_plan(arc_path.read_text(encoding="utf-8"))
    assert [it.ident for it in reading.items] == ["A1", "A3"], "A2 must have vanished from the live arc"
    assert "APPLIED" in capsys.readouterr().out


def test_APPLY_ne_touche_PAS_aux_items_voisins(tmp_path: Path) -> None:
    arc_path = _projet(tmp_path)
    _run(str(arc_path), "--item", "A2", "--remplace", "x", "--today", "2026-08-16", "--apply")

    texte = arc_path.read_text(encoding="utf-8")
    assert "A normal item, never touched." in texte
    assert "A third item, never touched either." in texte


# --- 4. refusals rendered cleanly, nothing is written ------------------------------------------------


def test_refuse_un_item_jamais_retire_et_n_ecrit_rien(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arc_path = _projet(tmp_path, retirer_a2=False)
    avant = arc_path.read_text(encoding="utf-8")

    rc = _run(str(arc_path), "--item", "A1", "--remplace", "x", "--apply")

    assert rc == 1
    assert arc_path.read_text(encoding="utf-8") == avant
    assert not (tmp_path / RETIRES_DIRNAME).exists()
    assert "REFUSED" in capsys.readouterr().out


def test_refuse_REMPLACE_manquant_au_niveau_argparse() -> None:
    with pytest.raises(SystemExit):
        _run("a/path.md", "--item", "A2")


def test_fichier_absent_est_signale_proprement(tmp_path: Path) -> None:
    rc = _run(str(tmp_path / "does-not-exist.md"), "--item", "A2", "--remplace", "x")
    assert rc == 1


# --- 5. never overwrite (inv. 2) — a second attempt on the same day is refused ---------------------


def test_UN_SECOND_RETRAIT_LE_MEME_JOUR_SUR_LE_MEME_IDENT_REFUSE_JAMAIS_N_ECRASE(
    tmp_path: Path,
) -> None:
    """Measuring inv. 2: replaying the same command afterwards must never silently
    replace a trash file that was already written."""
    arc_path = _projet(tmp_path)
    _run(
        str(arc_path), "--item", "A2", "--remplace", "premiere fois", "--today", "2026-08-16",
        "--apply",
    )
    corbeille = tmp_path / RETIRES_DIRNAME / "retire-2026-08-16-a2.md"
    contenu_original = corbeille.read_text(encoding="utf-8")

    # A2 is no longer in the arc, so a second call on A2 hits "item_absent" -- refused
    # before it even reaches the question of the filename. Checked here to make sure it stays a
    # refusal, never a write.
    rc = _run(
        str(arc_path), "--item", "A2", "--remplace", "seconde fois", "--today", "2026-08-16",
        "--apply",
    )
    assert rc == 1
    assert corbeille.read_text(encoding="utf-8") == contenu_original


# --- 6. the TOCTOU race — found by the isolated audit of 2026-08-16, ZERO coverage before this -----
#
# The auditor's measurement: `apply_planning`'s `"x"` mode is the SECOND line of defense (on top of
# the plain `corbeille_existe` refusal) against a trash file appearing BETWEEN the `taken` snapshot
# and the write. Sabotaged into `"w"`, the ENTIRE suite (30 witnesses) stayed green — nothing bit.
# This test exercises precisely THAT window: the file appears AFTER `plan_corbeille()` has already
# decided it did not exist yet, never before (otherwise it is the plain refusal, already tested
# elsewhere).


def test_LA_COURSE_TOCTOU_est_refusee_MEME_QUAND_LE_FICHIER_APPARAIT_APRES_l_examen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Simulates a second process that writes the same trash file in the exact window
    between the `taken` snapshot (in `main`) and the write (`apply_planning`) — by wrapping
    `plan_corbeille()` so it creates the competing file just AFTER computing a plan that did
    not see it yet. If `apply_planning` falls back to `open("w", ...)` instead of `"x"`, this
    test must turn red — that is the proof that the guard matters, not just a re-reading of
    the code."""
    arc_path = _projet(tmp_path)
    from mnemosyne.production import plan_corbeille as module

    reel = module.plan_corbeille
    sentinelle = "CONTENT OF THE REAL CONCURRENT PROCESS -- MUST NEVER BE OVERWRITTEN\n"

    def avec_course(*args, **kwargs):
        planning = reel(*args, **kwargs)
        if not planning.blocked:
            cible = tmp_path / RETIRES_DIRNAME / planning.move.filename
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(sentinelle, encoding="utf-8")
        return planning

    monkeypatch.setattr(plan_corbeille_run, "plan_corbeille", avec_course)

    rc = _run(
        str(arc_path), "--item", "A2", "--remplace", "x", "--today", "2026-08-16", "--apply"
    )

    cible = tmp_path / RETIRES_DIRNAME / "retire-2026-08-16-a2.md"
    assert cible.read_text(encoding="utf-8") == sentinelle, (
        "the race OVERWROTE the concurrent process's file -- invariant 2 broken"
    )
    assert rc == 1
    assert "INTERRUPTED" in capsys.readouterr().out
    # And the arc was NOT rewritten: the trash write fails BEFORE the arc's
    # (the same ordering apply_planning's docstring claims).
    reading = read_plan(arc_path.read_text(encoding="utf-8"))
    assert [it.ident for it in reading.items] == ["A1", "A2", "A3"], (
        "the arc was rewritten despite the trash write failing"
    )


# --- 7. sabotage — the command really BITES on a real H1 replayed ----------------------------------


def test_SABOTAGE_deux_retraits_H1_du_MEME_jour_sur_des_items_differents_ne_collisionnent_pas(
    tmp_path: Path,
) -> None:
    """Proof that `retiree_filename` (named by IDENTIFIER, never by title) holds even when
    two items on the same day have titles that look alike — named after the ident, never
    guessed from the text."""
    arc_path = _projet(tmp_path)
    _run(str(arc_path), "--item", "A2", "--remplace", "x", "--today", "2026-08-16", "--apply")

    # Retire A1 too, same day.
    texte = arc_path.read_text(encoding="utf-8")
    apres = applique_retrait(
        texte, ("A1",), motif="m2", cout="none", id_retrait="feedface0002",
        quand="2026-08-16T01:00:00+00:00",
    )
    arc_path.write_text(apres, encoding="utf-8")
    rc = _run(str(arc_path), "--item", "A1", "--remplace", "y", "--today", "2026-08-16", "--apply")

    assert rc == 0
    fichiers = sorted(p.name for p in (tmp_path / RETIRES_DIRNAME).glob("*.md"))
    assert fichiers == ["retire-2026-08-16-a1.md", "retire-2026-08-16-a2.md"]
