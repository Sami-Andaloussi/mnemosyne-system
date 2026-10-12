"""``make plans`` gains a REFUSAL — ``VERIFIER=1``, never the default path.

Two axes, both named in :func:`~mnemosyne.runtime.plans_run.verifier_problems`: a plan that exists
and cannot be read (ILLISIBLE, already computed by the scan) and a frozen door
(:data:`~mnemosyne.production.derives.PORTES_QUI_DECLARENT`) that stopped declaring its
``**Format**``. This is the CALLER the adoption gel measured it lacked — the default (read) path
stays untouched, ``rc 0`` always, exactly as before this file existed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production import derives
from mnemosyne.production.plan_registry import PLAN_FILENAME, scan_plans, scan_projects
from mnemosyne.runtime import plans_run
from mnemosyne.runtime.plans_run import render_registry, verifier_problems

REPO = Path(__file__).resolve().parents[2]

GOOD = "# PLAN — x\n\n> **Cap** : make progress\n\n- **A1** \U00002B1C do it\n"
#: Missing ``**Cap**`` — the exact shape `test_plan_registry.py` uses to reach ILLISIBLE.
BROKEN = "# PLAN — x\n\n- **A1** \U00002B1C do it\n"


def tree(root: Path, layout: dict[str, str | None]) -> Path:
    projects = root / "projects"
    for name, body in layout.items():
        home = projects / name
        home.mkdir(parents=True, exist_ok=True)
        if body is not None:
            (home / PLAN_FILENAME).write_text(body, encoding="utf-8")
    return projects


# --- D177 (a89b368): the "The gesture, per project" skeleton points to the GATE, never a phrase -
#
# Autonomy probe (2026-08-17): an agent that faithfully follows this block declares a Format,
# pulls `VERIFIER=1`, gets green, stops — without ever learning that a declaration alone HOLDS
# nothing (D177). The block must point to `make plan-gate-emit`, never hand-copy the six tokens
# (D163: it is the copy that manufactured the spelling trap measured elsewhere).


def test_le_bloc_absent_pointe_plan_gate_emit_SANS_recopier_les_jetons(tmp_path: Path) -> None:
    from mnemosyne.production.plan_format import FIELD_NAMES

    (tmp_path / "projects" / "saas" / "alpha").mkdir(parents=True)
    printed = render_registry(
        scan_projects(tmp_path / "projects"), projects_root=tmp_path / "projects"
    )
    assert "make plan-gate-emit" in printed
    # D163: a hand-copied token (even a single one) recreates the trap — the pointer is enough.
    for token in FIELD_NAMES:
        assert token not in printed, f"hand-copied token: {token!r} (D163)"


# --- verifier_problems: axis 1, ILLISIBLE --------------------------------------------------------


def test_aucun_probleme_sur_un_registre_propre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())
    registry = scan_projects(tree(tmp_path, {"saas/alpha": GOOD}))
    assert verifier_problems(registry, repo_root=tmp_path) == ()


def test_un_plan_ILLISIBLE_est_NOMME(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())
    registry = scan_projects(tree(tmp_path, {"saas/alpha": BROKEN}))
    problems = verifier_problems(registry, repo_root=tmp_path)
    assert len(problems) == 1
    assert "saas/alpha" in problems[0]
    assert "UNREADABLE" in problems[0]


def test_plusieurs_ILLISIBLES_sont_TOUS_NOMMES_pas_seulement_comptes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())
    registry = scan_projects(tree(tmp_path, {"saas/alpha": BROKEN, "saas/beta": BROKEN}))
    (problem,) = verifier_problems(registry, repo_root=tmp_path)
    assert "saas/alpha" in problem and "saas/beta" in problem


# --- verifier_problems: axis 2, the adoption freeze (derives.verdict_adoption) -------------------


def test_une_porte_gelee_qui_declare_encore_NE_REFUSE_PAS(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    porte = "projects/saas/alpha/PLAN.md"
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", (porte,))
    body = "# PLAN — x\n\n> **Format** : produit\n\n> **Cap** : make progress\n\n- **A1** \U00002B1C do it\n"
    registry = scan_projects(tree(tmp_path, {"saas/alpha": body}))
    assert verifier_problems(registry, repo_root=tmp_path) == ()


def test_une_porte_gelee_dont_le_FORMAT_a_disparu_REFUSE_et_NOMME_la_porte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scene measured by the auditor, reproduced here with this module as the REAL CALLER:
    twenty characters disappear, same items, and `make plans VERIFIER=1` must refuse."""
    porte = "projects/saas/alpha/PLAN.md"
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", (porte,))
    registry = scan_projects(tree(tmp_path, {"saas/alpha": GOOD}))  # no **Format** at all
    (problem,) = verifier_problems(registry, repo_root=tmp_path)
    assert porte in problem
    assert "PORTES_QUI_DECLARENT" in problem


def test_la_cle_du_courant_est_LE_CHEMIN_RELATIF_AU_DEPOT_en_POSIX(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The flagship project's freeze is written with `/`, never `\\` — a caller that built its keys
    differently would read EVERY door as erased, on any platform where `os.sep` differs."""
    porte = "projects/saas/alpha/PLAN.md"
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", (porte,))
    body = "# PLAN — x\n\n> **Format** : produit\n\n> **Cap** : make progress\n\n- **A1** \U00002B1C do it\n"
    registry = scan_projects(tree(tmp_path, {"saas/alpha": body}))
    courant = plans_run._courant_format_declare(registry, repo_root=tmp_path)
    assert courant[porte] == "produit"


def test_une_porte_gelee_ABSENTE_du_disque_compte_comme_EFFACEE(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same rule as `derives.verdict_adoption`: a rename/deletion does not silently take a door
    out of judgment — `courant` simply no longer contains the key."""
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ("projects/saas/alpha/PLAN.md",))
    registry = scan_projects(tree(tmp_path, {}))  # nothing on disk
    (problem,) = verifier_problems(registry, repo_root=tmp_path)
    assert "projects/saas/alpha/PLAN.md" in problem


# --- R1 (isolated audit, 0718e26): the JUDGE'S OWN accessor, on the REAL corpus, not a
# population built FROM the freeze itself ---------------------------------------------------------
#
# None of the witnesses above can see a gap between the keys `_courant_format_declare`
# produces and the REAL population that `PORTES_QUI_DECLARENT` freezes: `test_derives.py` builds
# `courant` by ITERATING the frozen tuple itself (the keys equal the freeze BY CONSTRUCTION), and
# the `tree()` fixtures above only ever lay down a FLAT tree — 13 of the flagship project's 14 real doors are
# NESTED (`projects/saas/<project>/plan/<arc>/PLAN.md`). A witness that manufactures its own
# population from the freeze measures its own construction, never the judge's accessor — and the
# failure mode of a real gap is a total FALSE REFUSAL on intact doors, the worst class: a door
# that cries false gets disarmed within the hour (measured elsewhere in this repository).


@pytest.mark.skipif(
    not (REPO / "projects/saas/reference-project").is_dir(),
    reason="projects/ is gitignored by design",
)
def test_l_accesseur_du_juge_COUVRE_les_14_portes_REELLES_dont_13_NICHEES() -> None:
    """Reads the DISK through `_courant_format_declare` (the judge's own accessor, not an ad hoc
    reconstruction) and checks that its keys cover AT LEAST the frozen population — a superset,
    never a strict equality: a future, not-yet-frozen adopter may legitimately appear in
    `courant` without being in the freeze."""
    courant = plans_run._courant_format_declare(scan_plans(REPO), repo_root=REPO)
    manquantes = set(derives.PORTES_QUI_DECLARENT) - set(courant)
    assert not manquantes, f"frozen door(s) missing from the judge's accessor: {manquantes}"
    assert any("/plan/" in porte for porte in courant), (
        "no NESTED door seen — this witness tests nothing"
    )


# --- R1, HERMETIC TWIN (isolated audit, a7f39461545ae7931): the same guard, without depending on
# the flagship project ---------------------------------------------------------------------------
#
# **LOW-CONFIDENCE CAVEAT found by the audit**: the witness above measures ONLY on a machine
# that carries `projects/saas/reference-project` — elsewhere (any fresh clone, `projects/` being
# gitignored by design), its `skipif` makes it GREEN by measuring NOTHING, silently. The guard
# against an accessor that would exclude NESTED doors therefore exists, in practice, only on that
# one machine. This twin closes the CLASS with a constructed tree (`tmp_path`), never just the
# CASE: it bites everywhere, without confusing "the flagship project absent" with "nothing to protect."


def test_l_accesseur_du_juge_COUVRE_une_porte_NICHEE_construite_JAMAIS_SKIP(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    porte_racine = "projects/saas/beta/PLAN.md"
    porte_nichee = "projects/saas/beta/plan/01-arc/PLAN.md"
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", (porte_racine, porte_nichee))

    racine = tree(
        tmp_path,
        {
            "saas/beta": (
                "# PLAN — beta\n\n> **Cap** : make progress\n\n## The arcs\n\n"
                "- `plan/01-arc/PLAN.md` — arc 1\n\n- **R1** \U00002B1C root\n"
            )
        },
    )
    sous_plan = racine / "saas" / "beta" / "plan" / "01-arc"
    sous_plan.mkdir(parents=True)
    (sous_plan / PLAN_FILENAME).write_text(
        "# PLAN — beta/01-arc\n\n> **Format** : produit\n\n> **Cap** : sub-cap\n\n- **A1** \U00002B1C do it\n",
        encoding="utf-8",
    )

    registry = scan_projects(racine)
    courant = plans_run._courant_format_declare(registry, repo_root=tmp_path)
    manquantes = {porte_racine, porte_nichee} - set(courant)
    assert not manquantes, f"nested door(s) missing from the judge's accessor: {manquantes}"
    assert courant[porte_nichee] == "produit"


# --- sabotage: the gate must REALLY bite, not just look armed -----------------------------------


def test_sabotage_EFFACER_LE_FORMAT_fait_ROUGIR_exactement_ce_temoin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    porte = "projects/saas/alpha/PLAN.md"
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", (porte,))
    with_format = (
        "# PLAN — x\n\n> **Format** : produit\n\n> **Cap** : make progress\n\n- **A1** \U00002B1C do it\n"
    )
    tenue = scan_projects(tree(tmp_path, {"saas/alpha": with_format}))
    assert verifier_problems(tenue, repo_root=tmp_path) == (), "before sabotage: it holds"

    sabotee = scan_projects(tree(tmp_path, {"saas/alpha": GOOD}))  # the sabotage: **Format** removed
    (problem,) = verifier_problems(sabotee, repo_root=tmp_path)
    assert porte in problem, "after sabotage: refuses and NAMES the door"


# --- main(): VERIFIER=1 is the ONLY path that changes the rc ------------------------------------
#
# In-process (no subprocess): a subprocess would inherit the REAL POPULATION of
# `derives.PORTES_QUI_DECLARENT` (the flagship project's real doors, frozen by a different batch) and would
# refuse on a `tmp_path` that doesn't carry them — a fault of the WITNESS, not of the gate under
# test here.


def test_sans_VERIFIER_rc_reste_0_MEME_sur_un_plan_ILLISIBLE(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())
    monkeypatch.delenv("VERIFIER", raising=False)
    tree(tmp_path, {"saas/alpha": BROKEN})
    rc = plans_run.main(["--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "UNREADABLE" in out, "the read view hasn't changed, it already named it"
    assert "VERIFIER=1 REFUSE" not in out


def test_avec_VERIFIER_env_rc_1_sur_un_plan_ILLISIBLE_et_le_REFUS_est_IMPRIME(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())
    monkeypatch.setenv("VERIFIER", "1")
    tree(tmp_path, {"saas/alpha": BROKEN})
    rc = plans_run.main(["--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "VERIFIER=1 REFUSE" in out
    assert "saas/alpha" in out


def test_avec_flag_verifier_meme_effet_que_la_variable_environnement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())
    monkeypatch.delenv("VERIFIER", raising=False)
    tree(tmp_path, {"saas/alpha": BROKEN})
    rc = plans_run.main(["--repo-root", str(tmp_path), "--verifier"])
    assert rc == 1, capsys.readouterr().out


def test_avec_VERIFIER_rc_0_quand_tout_est_propre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())
    monkeypatch.setenv("VERIFIER", "1")
    tree(tmp_path, {"saas/alpha": GOOD})
    rc = plans_run.main(["--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "no refusal" in out


# --- THE ADOPTION GAP (derives.ecart_adoption), WIRED HERE BECAUSE NOTHING CALLED IT (20:0x) ----
#
# Built and sabotage-proven at turn 18:3x, zero callers in production — the SAME class as
# `verdict_adoption` three hours earlier, in the same file (`derives.py`). Level 1 DELIBERATELY:
# publishes, NEVER refuses here (the refusal stays under `VERIFIER=1`, on the ONLY doors already
# frozen) — a fresh adopter that declares but is not yet in `PORTES_QUI_DECLARENT` is not at
# fault, it is waiting for a gesture.


def test_ecart_est_VIDE_quand_toute_porte_declarante_est_DEJA_gelee(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    porte = "projects/saas/alpha/PLAN.md"
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", (porte,))
    body = "# PLAN — x\n\n> **Format** : produit\n\n> **Cap** : make progress\n\n- **A1** \U00002B1C do it\n"
    tree(tmp_path, {"saas/alpha": body})
    rc = plans_run.main(["--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "0 porte déclare hors du gel : rien à inscrire." in out


def test_ecart_NOMME_une_porte_qui_DECLARE_MAIS_N_EST_PAS_gelee_et_NE_REFUSE_PAS(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exact scene from the task: a new project declares, nobody has entered it into the
    freeze yet — `make plans` must NAME it, and `VERIFIER=1` must NOT refuse on it (it is not at
    fault toward any promise: it made none)."""
    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())  # nothing frozen yet
    body = "# PLAN — x\n\n> **Format** : produit\n\n> **Cap** : make progress\n\n- **A1** \U00002B1C do it\n"
    tree(tmp_path, {"saas/gamma": body})
    rc = plans_run.main(["--repo-root", str(tmp_path), "--verifier"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "1 PORTE(S) DÉCLARENT UN FORMAT ET NE SONT PAS GELÉES" in out
    assert "projects/saas/gamma/PLAN.md" in out
    assert "VERIFIER=1 REFUSE" not in out, (
        "a fresh adopter is not at fault, it is waiting for a gesture"
    )


def test_sabotage_UNE_PORTE_QUI_QUITTE_LE_GEL_fait_APPARAITRE_l_ecart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Real sabotage of the caller itself (not of the judge, already sabotaged elsewhere): a
    frozen door leaves the freeze (rename/unfreeze), and the gap must catch it on the next pass."""
    porte = "projects/saas/alpha/PLAN.md"
    body = "# PLAN — x\n\n> **Format** : produit\n\n> **Cap** : make progress\n\n- **A1** \U00002B1C do it\n"
    tree(tmp_path, {"saas/alpha": body})

    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", (porte,))
    avant = plans_run.main(["--repo-root", str(tmp_path)])
    assert "rien à inscrire" in capsys.readouterr().out
    assert avant == 0

    monkeypatch.setattr(derives, "PORTES_QUI_DECLARENT", ())  # the door leaves the freeze
    apres = plans_run.main(["--repo-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert apres == 0
    assert porte in out and "NE SONT PAS GELÉES" in out
