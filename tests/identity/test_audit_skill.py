"""The skill-creator's verify-in-code audit (D75 / D100-6) - the judge-analog for a skill's
ANATOMY rather than its distilled content.

Two layers, tested separately (like judge_fiche vs judge_library.run_judge): the PURE verdict
`mnemosyne.production.audit_skill(...)` (given already-read texts/facts - no filesystem), and the
orchestration in `system/skills/skill-creator/audit_skill.py` (globbing, the Makefile, the `ast`
scan of `production/*.py` for `*_PROMPT`/`*_TEMPLATE` constants). The property that matters most
(the arc's central lesson, made runnable): a SKILL.md that hand-copies even a SLICE of a code-home
prompt constant is CAUGHT - not just in theory, but against the REAL constants this repo ships
(FINISH_PROMPT et al), and the `scaffold_only` axis is proven to never fold into `ok` either way."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from _invariants import REPO_ROOT
from mnemosyne.production import SCAFFOLD_MARKERS, SkillAudit, audit_skill
from mnemosyne.production import skills

_SCRIPT = (
    REPO_ROOT / "system" / "skills" / "skill-creator" / "audit_skill.py"
)
_spec = importlib.util.spec_from_file_location("audit_skill_script", _SCRIPT)
assert _spec is not None and _spec.loader is not None
audit_skill_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit_skill_script)

_PROD_ROOT = REPO_ROOT / "system" / "lib" / "mnemosyne" / "production"

# NOTE (public-mirror): the French prose inside `_GOOD_MD` / `_D36_CONFORMANT_MD` below is left
# UNTRANSLATED on purpose. Several tests further down build their fixtures by `.replace()`-ing an
# EXACT substring of this text (e.g. the angle-bracket test, the scaffold_only test), and the six
# D36 body-section headers are matched by a French, accent-folding-only regex in
# `mnemosyne.production.skills._D36_BODY_SECTIONS` (checked against the real source before writing
# this note) - translating "Methode"/"Entrees -> Sorties"/"Quand FLAG" would silently stop them
# from being recognized. Only the one personal name inside the fixture body is redacted (rule 2).
_GOOD_MD = (
    "---\n"
    "name: exemple-skill\n"
    "description: >\n"
    "  Un skill d'exemple bien forme, avec une description suffisamment longue et honnete pour\n"
    "  passer la lint de frontmatter sans faire semblant d'etre autre chose qu'un test.\n"
    "---\n\n"
    "# Skill : exemple-skill\n\n"
    "## Quand l'utiliser\n"
    "Un vrai corps, assez long pour ne pas ressembler a un scaffold vide - plusieurs phrases qui "
    "decrivent honnetement le skill, exactement comme le ferait un skill reel de ce repo, pour "
    "depasser le plancher de longueur du corps sans tricher avec un remplissage absurde.\n\n"
    "## Sous le capot\nRien de plus a verifier ici pour ce test.\n"
)


# ============================ audit_skill (pure verdict) ==============================
def test_a_well_formed_skill_with_an_emit_seam_passes() -> None:
    verdict = audit_skill(name="exemple-skill", skill_md=_GOOD_MD, n_skill_md_files=1, has_emit_seam=True)
    assert isinstance(verdict, SkillAudit)
    assert verdict.ok and not verdict.reasons
    assert verdict.scaffold_only is False


def test_a_missing_skill_md_fails_with_a_named_reason() -> None:
    verdict = audit_skill(name="x", skill_md=None, n_skill_md_files=0, has_emit_seam=True)
    assert not verdict.ok
    assert any("no SKILL.md" in r for r in verdict.reasons)


def test_more_than_one_skill_md_fails() -> None:
    verdict = audit_skill(name="x", skill_md=_GOOD_MD, n_skill_md_files=2, has_emit_seam=True)
    assert not verdict.ok
    assert any("2 SKILL.md" in r for r in verdict.reasons)


def test_a_skill_with_a_model_contract_but_no_emit_seam_fails() -> None:
    # a skill that HAS a model-facing contract (requires_emit_seam=True) yet ships no seam is a
    # real gap - the frontier host can never receive the contract, so this MUST fail.
    verdict = audit_skill(
        name="x", skill_md=_GOOD_MD, n_skill_md_files=1, has_emit_seam=False, requires_emit_seam=True
    )
    assert not verdict.ok and verdict.has_emit_seam is False and verdict.requires_emit_seam is True
    assert any("emit seam" in r for r in verdict.reasons)


def test_a_model_free_skill_without_an_emit_seam_passes() -> None:
    # the BLOCKER the audit flagged: juge is a valid model-LESS skill (nothing to emit), so an
    # absent seam is INFORMATIONAL - surfaced on the field, NEVER appended to reasons, never ok=False.
    verdict = audit_skill(
        name="juge", skill_md=_GOOD_MD, n_skill_md_files=1, has_emit_seam=False, requires_emit_seam=False
    )
    assert verdict.ok is True
    assert verdict.has_emit_seam is False and verdict.requires_emit_seam is False
    assert not any("emit seam" in r for r in verdict.reasons)  # never a reason when not required


def test_frontmatter_lint_catches_a_non_kebab_name() -> None:
    bad = _GOOD_MD.replace("name: exemple-skill", "name: Exemple_Skill")
    verdict = audit_skill(name="x", skill_md=bad, n_skill_md_files=1, has_emit_seam=True)
    assert not verdict.ok and any("kebab-case" in r for r in verdict.reasons)


def test_frontmatter_lint_catches_a_missing_description() -> None:
    bad = "---\nname: exemple-skill\n---\n\n# body\n" + ("x" * 400)
    verdict = audit_skill(name="x", skill_md=bad, n_skill_md_files=1, has_emit_seam=True)
    assert not verdict.ok and any("description" in r for r in verdict.reasons)


def test_frontmatter_lint_catches_angle_brackets_in_the_description() -> None:
    bad = _GOOD_MD.replace(
        "Un skill d'exemple bien forme",
        "Un skill <script>alert(1)</script> d'exemple bien forme",
    )
    verdict = audit_skill(name="x", skill_md=bad, n_skill_md_files=1, has_emit_seam=True)
    assert not verdict.ok and any("angle bracket" in r for r in verdict.reasons)


def test_frontmatter_lint_catches_an_over_long_description() -> None:
    bad = "---\nname: x\ndescription: >\n  " + ("d " * 600) + "\n---\n\n# b\n" + ("x" * 400)
    verdict = audit_skill(name="x", skill_md=bad, n_skill_md_files=1, has_emit_seam=True)
    assert not verdict.ok and any("over the" in r and "cap" in r for r in verdict.reasons)


def test_scaffold_only_is_a_separate_axis_never_folded_into_ok() -> None:
    # a skill can be structurally PASSING (ok=True) yet still be an unfilled scaffold - lesson 6 -
    # and the reverse never happens either: a scaffold marker alone must not flip ok to False.
    marker = SCAFFOLD_MARKERS[0]
    scaffolded = _GOOD_MD.replace("Rien de plus a verifier ici pour ce test.", marker)
    verdict = audit_skill(name="x", skill_md=scaffolded, n_skill_md_files=1, has_emit_seam=True)
    assert verdict.ok is True  # NOT demoted by scaffold_only
    assert verdict.scaffold_only is True and marker in verdict.scaffold_reason


def test_scaffold_only_also_fires_on_a_too_short_body_without_any_marker() -> None:
    short = "---\nname: x\ndescription: >\n  une description valide et bornee\n---\n\nrien.\n"
    verdict = audit_skill(name="x", skill_md=short, n_skill_md_files=1, has_emit_seam=True)
    assert verdict.scaffold_only is True and "chars" in verdict.scaffold_reason


def test_a_real_skill_length_body_is_not_mistaken_for_a_scaffold() -> None:
    # the length floor must never mislabel a genuinely full, real skill (no false positive here).
    assert audit_skill(
        name="x", skill_md=_GOOD_MD, n_skill_md_files=1, has_emit_seam=True
    ).scaffold_only is False


def test_scaffold_only_fires_when_the_code_home_is_a_stub_but_the_skill_md_is_filled() -> None:
    # the FINDING: a nicely-written SKILL.md over a code home still containing a SCAFFOLD_MARKER
    # (an un-filled stub) must report scaffold_only=True - the axis is honest WHEREVER the scaffold
    # still is. ok stays unaffected (a separate axis), the reason names the code-home file.
    stub_home = f'def run():\n    raise NotImplementedError("{SCAFFOLD_MARKERS[2]} implement me")\n'
    verdict = audit_skill(
        name="x",
        skill_md=_GOOD_MD,  # filled, marker-free, long body
        n_skill_md_files=1,
        has_emit_seam=True,
        impl_texts={"production/x.py": stub_home},
    )
    assert verdict.scaffold_only is True and verdict.ok is True  # honest, but NOT a failure
    assert "production/x.py" in verdict.scaffold_reason and SCAFFOLD_MARKERS[2] in verdict.scaffold_reason


def test_a_filled_code_home_does_not_trip_scaffold_only() -> None:
    # the guard against over-detection: a real, filled code home (no marker) leaves a filled skill
    # scaffold_only=False - this is what keeps the four real skills clean.
    verdict = audit_skill(
        name="x",
        skill_md=_GOOD_MD,
        n_skill_md_files=1,
        has_emit_seam=True,
        impl_texts={"production/x.py": "def run():\n    return compute()\n"},
    )
    assert verdict.scaffold_only is False and verdict.ok is True


def test_an_unparseable_skill_file_is_surfaced_as_a_hard_failure() -> None:
    # FIX 2: a broken skill .py must not audit as clean - it is a reason (ok=False), not swallowed.
    verdict = audit_skill(
        name="x",
        skill_md=_GOOD_MD,
        n_skill_md_files=1,
        has_emit_seam=True,
        unparseable_files=("system/skills/x/x_run.py",),
    )
    assert verdict.ok is False
    assert any("does not parse" in r and "x_run.py" in r for r in verdict.reasons)


# ============================ anti-drift (the arc's central lesson) ===================
def test_anti_drift_lint_fires_on_a_planted_excerpt_of_a_code_home_constant() -> None:
    constant_text = (
        "This is the exact contract text a model must follow, word for word, no drift allowed here."
    )
    constants = {"finisher.FINISH_PROMPT": constant_text}
    planted = _GOOD_MD + "\n" + constant_text[:70]  # a literal PREFIX slice - always the i=0 window
    verdict = audit_skill(
        name="x", skill_md=planted, n_skill_md_files=1, has_emit_seam=True, prompt_constants=constants
    )
    assert not verdict.ok
    assert verdict.anti_drift_hits == ("finisher.FINISH_PROMPT",)
    assert any("anti-drift" in r for r in verdict.reasons)


def test_anti_drift_catches_a_65_char_run_at_a_stride_unaligned_offset() -> None:
    # HARDENING: with _DRIFT_STRIDE=1 the guaranteed floor equals the 60-char window, so even a
    # 65-char verbatim run pasted from the MIDDLE of a constant (offset 23 - not aligned to any
    # large stride, the exact case the old stride=40 would have MISSED) is caught.
    const = (
        "Zephyr quokka vex nimbus fjord glyph waltz brixton qophs a deliberately distinctive "
        "contract line here for the anti-drift floor test."
    )
    constants = {"mod.FOO_PROMPT": const}
    planted = _GOOD_MD + "\n" + const[23:88]  # a 65-char mid-constant slice
    assert len(const[23:88]) == 65
    verdict = audit_skill(
        name="x", skill_md=planted, n_skill_md_files=1, has_emit_seam=True, prompt_constants=constants
    )
    assert verdict.anti_drift_hits == ("mod.FOO_PROMPT",) and not verdict.ok


def test_anti_drift_ignores_a_run_shorter_than_the_window() -> None:
    # the floor is the WINDOW (60): a 59-char run is below it and must NOT fire - a short shared
    # phrase is not evidence of a hand-copied contract (keeps the lint from false-positiving prose).
    const = "A short but distinctive phrase that is quite under sixty chars ok here too long now."
    constants = {"mod.FOO_PROMPT": const}
    planted = _GOOD_MD + "\n" + const[:59]  # 59 chars - one below the window
    verdict = audit_skill(
        name="x", skill_md=planted, n_skill_md_files=1, has_emit_seam=True, prompt_constants=constants
    )
    assert verdict.anti_drift_hits == ()


def test_anti_drift_lint_does_not_fire_on_an_honest_paraphrase() -> None:
    # SKILL.md is EXPECTED to describe the contract in its own words (this repo's own SKILL.md
    # files do exactly that) - the lint must not punish description, only literal copying.
    constants = {"finisher.FINISH_PROMPT": "You polish ONE already-distilled fiche for READABILITY."}
    paraphrase = _GOOD_MD + "\nCe skill ameliore la lisibilite d'une fiche deja distillee.\n"
    verdict = audit_skill(
        name="x", skill_md=paraphrase, n_skill_md_files=1, has_emit_seam=True, prompt_constants=constants
    )
    assert verdict.anti_drift_hits == () and verdict.ok


def test_anti_drift_lint_fires_against_the_real_shipped_finish_prompt() -> None:
    # end-to-end against the REAL code (not a synthetic stand-in): the exact scenario the task's
    # own manual check exercises - a SKILL.md that pastes a slice of a real *_PROMPT constant.
    from mnemosyne.production import FINISH_PROMPT

    constants = audit_skill_script.prompt_like_constants(_PROD_ROOT)
    assert any(name.endswith("FINISH_PROMPT") for name in constants)  # the real constant was found
    planted = _GOOD_MD + "\n" + FINISH_PROMPT[20:120]  # a mid-constant slice, not the whole thing
    verdict = audit_skill(
        name="x", skill_md=planted, n_skill_md_files=1, has_emit_seam=True, prompt_constants=constants
    )
    assert not verdict.ok
    assert any(hit.endswith("FINISH_PROMPT") for hit in verdict.anti_drift_hits)


# ============================ scaffold-in-code-home + unparseable surfacing (this task) ========
def test_scaffold_impl_texts_reads_code_home_and_run_adapter_only_not_the_whole_dir(
    tmp_path: Path, monkeypatch
) -> None:
    # NARROW by design: it reads the derived code home + *_run.py adapter, NOT every *.py - so the
    # skill-creator's own new_skill.py / skills.py (which hold the marker strings as CONSTANTS) can
    # never false-positive the scaffold scan. Here: a marker-bearing helper.py is IGNORED; the code
    # home and the *_run.py adapter ARE read.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "system" / "lib" / "mnemosyne" / "production").mkdir(parents=True)
    skill = tmp_path / "system" / "skills" / "demo"
    skill.mkdir(parents=True)
    (tmp_path / "system" / "lib" / "mnemosyne" / "production" / "demo.py").write_text(
        f'# {SCAFFOLD_MARKERS[0]}\n', encoding="utf-8"
    )
    (skill / "demo_run.py").write_text("x = 1\n", encoding="utf-8")
    (skill / "helper.py").write_text(f'MARK = "{SCAFFOLD_MARKERS[0]}"\n', encoding="utf-8")  # a CONSTANT
    texts = audit_skill_script.scaffold_impl_texts(skill, "demo")
    labels = " ".join(texts)
    assert "production/demo.py" in labels and "demo_run.py" in labels
    assert "helper.py" not in labels  # the constant-holding file is NOT scanned (no false positive)


def test_code_home_path_maps_name_with_hyphens_to_underscores() -> None:
    assert audit_skill_script.code_home_path("my-new-skill").name == "my_new_skill.py"


def test_unparseable_skill_py_surfaces_a_broken_file_scoped_to_the_skill(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "system" / "lib" / "mnemosyne" / "production").mkdir(parents=True)
    skill = tmp_path / "system" / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "good.py").write_text("x = 1\n", encoding="utf-8")
    (skill / "bad.py").write_text("def f(:\n    pass\n", encoding="utf-8")  # syntax error
    broken = audit_skill_script.unparseable_skill_py(skill, "demo")
    assert any(b.endswith("bad.py") for b in broken)
    assert not any(b.endswith("good.py") for b in broken)


def test_the_four_real_skills_have_no_unparseable_files_and_no_code_home_scaffold_marker(monkeypatch) -> None:
    # regression guard for THIS task: the real skills must stay clean on both new axes - none has a
    # broken .py, and none has a scaffold marker in its (derived) code home / *_run.py adapter.
    repo = REPO_ROOT
    monkeypatch.chdir(repo)  # the helpers resolve the code home relative to cwd (repo root, like make)
    root = repo / "system" / "skills"
    for name in ("distillateur", "finisseur", "juge", "skill-creator"):
        assert audit_skill_script.unparseable_skill_py(root / name, name) == []
        texts = audit_skill_script.scaffold_impl_texts(root / name, name)
        for text in texts.values():
            assert not any(marker in text for marker in SCAFFOLD_MARKERS)


# ============================ orchestration (system/skills/skill-creator/audit_skill.py) ======
def test_prompt_like_constants_scans_the_real_production_lib() -> None:
    constants = audit_skill_script.prompt_like_constants(_PROD_ROOT)
    names = set(constants)
    assert any(n.endswith("FINISH_PROMPT") for n in names)
    assert any(n.endswith("_PROMPT_TEMPLATE") for n in names)  # distillation.py's private constant
    assert any(n.endswith("SKILL_ANATOMY_TEMPLATE") for n in names)  # this skill's own contract


def test_prompt_like_constants_ignores_a_syntactically_broken_stub(tmp_path: Path) -> None:
    # a DRAFT skill's code-home stub can be mid-edit / syntactically broken; the scan must never
    # crash the whole audit over one bad file (D100 - a candidate's own defect stays local to it).
    (tmp_path / "broken.py").write_text("def f(:\n    pass", encoding="utf-8")
    (tmp_path / "fine.py").write_text('A_PROMPT = "hello, this is a fine literal string constant"\n', encoding="utf-8")
    constants = audit_skill_script.prompt_like_constants(tmp_path)
    assert "fine.A_PROMPT" in constants and "broken" not in " ".join(constants)


def test_prompt_like_constants_also_collects_a_schema_string_constant(tmp_path: Path) -> None:
    # HARDENING 3: the scan family now includes *_SCHEMA, so a future `FOO_SCHEMA = \"\"\"...\"\"\"`
    # a model must follow cannot drift into a SKILL.md undetected (a _PROMPT and a _TEMPLATE too).
    (tmp_path / "m.py").write_text(
        'FOO_SCHEMA = "a literal schema string a model must follow"\n'
        'BAR_TEMPLATE = "a template"\n'
        'BAZ_PROMPT = "a prompt"\n'
        'NOT_A_CONTRACT = "ignored"\n',
        encoding="utf-8",
    )
    constants = audit_skill_script.prompt_like_constants(tmp_path)
    assert "m.FOO_SCHEMA" in constants and "m.BAR_TEMPLATE" in constants and "m.BAZ_PROMPT" in constants
    assert "m.NOT_A_CONTRACT" not in constants


# ============================ has_model_contract -> requires_emit_seam (the BLOCKER fix) =======
def test_has_model_contract_true_for_the_real_model_skills_false_for_juge() -> None:
    # the exact required outcomes: distillateur/finisseur/skill-creator reference a model contract
    # (a *_SCHEMA / *_PROMPT / *_TEMPLATE, imported from their code home) -> True; juge references
    # none (pure verification, nothing to emit) -> False. This is what makes juge's seam optional.
    root = REPO_ROOT / "system" / "skills"
    assert audit_skill_script.has_model_contract(root / "distillateur") is True
    assert audit_skill_script.has_model_contract(root / "finisseur") is True
    assert audit_skill_script.has_model_contract(root / "skill-creator") is True
    assert audit_skill_script.has_model_contract(root / "juge") is False


def test_has_model_contract_detects_a_locally_defined_contract_constant(tmp_path: Path) -> None:
    # a skill whose own *.py DEFINES a module-level contract constant (not just imports one) also
    # counts - so a self-contained skill with a prompt but no seam still gets flagged as needing one.
    skill_dir = tmp_path / "s"
    skill_dir.mkdir()
    (skill_dir / "body.py").write_text('MY_PROMPT = "a contract a model follows"\n', encoding="utf-8")
    assert audit_skill_script.has_model_contract(skill_dir) is True


def test_has_model_contract_detects_a_contract_only_in_the_derived_code_home(
    tmp_path: Path, monkeypatch
) -> None:
    production = tmp_path / "production"
    production.mkdir()
    skill_dir = tmp_path / "cours"
    skill_dir.mkdir()
    (production / "cours.py").write_text(
        'COURSE_PROMPT_TEMPLATE = "a contract a model follows"\n', encoding="utf-8"
    )
    monkeypatch.setattr(audit_skill_script, "_PROD_ROOT", production)

    assert audit_skill_script.has_model_contract(skill_dir) is True


def test_has_model_contract_ignores_a_contract_token_only_in_a_comment_or_docstring(tmp_path: Path) -> None:
    # AST-based, so a token appearing ONLY inside a comment or a string literal is NOT a reference
    # (avoids a false 'has a contract' from prose mentioning FINISH_PROMPT).
    skill_dir = tmp_path / "s"
    skill_dir.mkdir()
    (skill_dir / "doc.py").write_text('"""mentions FINISH_PROMPT in prose."""\n# and MY_SCHEMA here\nx = 1\n', encoding="utf-8")
    assert audit_skill_script.has_model_contract(skill_dir) is False


def test_has_emit_seam_true_for_a_prefixed_emit_file_like_the_real_distillateur(tmp_path: Path) -> None:
    # distillateur's real seam is named emit_prompts.py - prefixed, not suffixed - this must match.
    skill_dir = tmp_path / "un-skill"
    skill_dir.mkdir()
    (skill_dir / "emit_prompts.py").write_text("", encoding="utf-8")
    assert audit_skill_script.has_emit_seam(skill_dir, makefile_text="") is True


def test_has_emit_seam_true_via_an_abbreviated_makefile_target(tmp_path: Path) -> None:
    # the Makefile target need not spell out the folder name (distill-emit, not distillateur-emit)
    # - has_emit_seam ties it back to the skill by the RECIPE referencing the skill's own path.
    skill_dir = tmp_path / "distillateur"
    skill_dir.mkdir()
    makefile = "distill-emit: ## comment\n\tuv run python system/skills/distillateur/emit_prompts.py\n"
    assert audit_skill_script.has_emit_seam(skill_dir, makefile_text=makefile) is True


def test_has_emit_seam_false_when_neither_signal_is_present(tmp_path: Path) -> None:
    skill_dir = tmp_path / "juge"
    skill_dir.mkdir()
    (skill_dir / "judge_library.py").write_text("", encoding="utf-8")  # no "emit" in the name
    assert audit_skill_script.has_emit_seam(skill_dir, makefile_text="judge:\n\techo hi\n") is False


def test_main_exits_zero_on_a_passing_skill_and_nonzero_on_a_failing_one(tmp_path: Path, monkeypatch) -> None:
    skill_dir = tmp_path / "ok-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(_GOOD_MD, encoding="utf-8")
    (skill_dir / "ok_skill_emit.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Makefile").write_text("help:\n\techo hi\n", encoding="utf-8")
    (tmp_path / "system" / "lib" / "mnemosyne" / "production").mkdir(parents=True)
    assert audit_skill_script.main([str(skill_dir)]) == 0

    empty_dir = tmp_path / "empty-skill"
    empty_dir.mkdir()
    assert audit_skill_script.main([str(empty_dir)]) != 0


def test_main_passes_a_model_free_skill_that_has_no_emit_seam(tmp_path: Path, monkeypatch) -> None:
    # end-to-end BLOCKER regression (the juge shape): a well-formed skill with NO model contract and
    # NO emit seam must exit 0 - the gate must not hard-fail a known-good model-free skill.
    skill_dir = tmp_path / "verifier-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(_GOOD_MD, encoding="utf-8")
    (skill_dir / "verify_lib.py").write_text("def run():\n    return 0\n", encoding="utf-8")  # no contract
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Makefile").write_text("help:\n\techo hi\n", encoding="utf-8")
    (tmp_path / "system" / "lib" / "mnemosyne" / "production").mkdir(parents=True)
    assert audit_skill_script.main([str(skill_dir)]) == 0


def test_main_reports_usage_with_no_arguments() -> None:
    assert audit_skill_script.main([]) == 1


# ============================ D36 SKILL.md anatomy gaps (this task - Ch.3) =====================
# D36 fixes the SKILL.md-level anatomy: a normed frontmatter HEADER (name / description /
# task_class / sensitivity_max / version / id / date) plus a FLOOR of six mandatory BODY sections
# (Role / Method / Inputs -> Outputs / When-to-FLAG / Validation / Logs). `anatomy_gaps` is a THIRD
# axis on SkillAudit, mirroring scaffold_only: informational, NEVER folded into `ok` - so a skill
# built before this axis existed (all four real skills, at the time of the triage) is surfaced
# honestly rather than retroactively failed.
#
# NOTE (public-mirror): the six body-section headers below ("Role", "Methode", "Entrees -> Sorties",
# "Quand FLAG", "Validation", "Logs") are left UNTRANSLATED on purpose - they are matched verbatim
# (accents optional, wording is not) by `mnemosyne.production.skills._D36_BODY_SECTIONS`, so writing
# the English gloss from the comment above ("Method", "Inputs -> Outputs", "When-to-FLAG") in their
# place would make this fixture stop being D36-conformant.
_D36_CONFORMANT_MD = (
    "---\n"
    "name: exemple-skill\n"
    "description: >\n"
    "  Un skill d'exemple bien forme, avec une description suffisamment longue et honnete pour\n"
    "  passer la lint de frontmatter sans faire semblant d'etre autre chose qu'un test.\n"
    "task_class: atomic\n"
    "sensitivity_max: perso\n"
    'version: "1.0"\n'
    "id: exemple-skill\n"
    "date: 2026-07-15\n"
    "---\n\n"
    "# Skill : exemple-skill\n\n"
    "## Role\nL'agent devient un exemple, pour le test, jamais autre chose.\n\n"
    "## Methode\nEtapes fictives mais assez longues pour ne pas ressembler a un scaffold vide, "
    "decrivant honnetement un skill complet de bout en bout pour ce test unitaire precis.\n\n"
    "## Entrees -> Sorties\nEntree : un fichier bidon. Sortie : un autre fichier bidon, ecrit "
    "quelque part de raisonnable pour ce test.\n\n"
    "## Quand FLAG\nSi l'entree est absente ou ambigue, le skill s'arrete et escalade vers l'operateur.\n\n"
    "## Validation\nUn validateur adversarial fictif relit et verifie le resultat produit.\n\n"
    "## Logs\nChaque passage ecrit un evenement JSONL, sans secret ni contenu sensible.\n"
)


def test_anatomy_gaps_is_empty_for_a_fully_d36_conformant_skill_md() -> None:
    verdict = audit_skill(
        name="exemple-skill", skill_md=_D36_CONFORMANT_MD, n_skill_md_files=1, has_emit_seam=True
    )
    assert verdict.anatomy_gaps == ()
    assert verdict.ok is True  # a clean D36 axis does not by itself make or break the others


def test_anatomy_gaps_reports_every_missing_d36_element_without_ever_flipping_ok() -> None:
    # _GOOD_MD is the pre-D36 shape (name/description only, no D36 sections): every D36-specific
    # frontmatter field and every mandatory body section must be reported as a gap, yet the skill
    # still passes overall - the whole point: never retroactively fail a skill built before D36.
    verdict = audit_skill(name="exemple-skill", skill_md=_GOOD_MD, n_skill_md_files=1, has_emit_seam=True)
    assert verdict.ok is True
    for field in ("task_class", "sensitivity_max", "version", "id", "date"):
        assert any(f"missing '{field}'" in gap for gap in verdict.anatomy_gaps)
    for label in ("Role", "Methode", "Entrees -> Sorties", "Quand FLAG", "Validation", "Logs"):
        assert any(f"'{label}' section" in gap for gap in verdict.anatomy_gaps)


def test_anatomy_gaps_frontmatter_half_closes_independently_of_the_body_half() -> None:
    # adding ONLY the frontmatter fields (no body sections yet) closes exactly the frontmatter
    # gaps and leaves the six body-section gaps untouched - the two halves are independent checks.
    md = _GOOD_MD.replace(
        "---\n\n# Skill",
        'task_class: atomic\nsensitivity_max: perso\nversion: "1.0"\nid: x\ndate: 2026-07-15\n'
        "---\n\n# Skill",
    )
    verdict = audit_skill(name="x", skill_md=md, n_skill_md_files=1, has_emit_seam=True)
    assert not any("frontmatter missing" in gap for gap in verdict.anatomy_gaps)
    assert len(verdict.anatomy_gaps) == 6  # the six body sections are still all missing


def test_anatomy_gaps_body_check_accepts_the_accented_french_spelling_too() -> None:
    # a human or a frontier agent may naturally write the accented spelling ("Rôle", "Méthode") -
    # the detector must not force the accent-free house style this repo's real files happen to use.
    accented = _D36_CONFORMANT_MD.replace("## Role", "## Rôle").replace("## Methode", "## Méthode")
    verdict = audit_skill(name="x", skill_md=accented, n_skill_md_files=1, has_emit_seam=True)
    assert verdict.anatomy_gaps == ()


def test_anatomy_gaps_never_appears_in_reasons_and_never_affects_ok() -> None:
    # SEPARATE axis, same guarantee as scaffold_only: a candidate riddled with D36 gaps (11 here:
    # 5 frontmatter fields + 6 body sections, all missing from _GOOD_MD) is still `ok` as long as
    # the OTHER, pre-existing checks pass.
    verdict = audit_skill(name="x", skill_md=_GOOD_MD, n_skill_md_files=1, has_emit_seam=True)
    assert verdict.ok is True and not verdict.reasons
    assert len(verdict.anatomy_gaps) == 11
    assert not any(gap in verdict.reasons for gap in verdict.anatomy_gaps)


def test_the_four_real_skills_are_now_fully_d36_anatomy_conformant() -> None:
    # regression guard for THIS task: distillateur/finisseur/juge/skill-creator now carry the D36
    # frontmatter header + the six mandatory body sections - the gap the triage started from
    # (0/4 real SKILL.md carried the D36 frontmatter) is closed, and `ok` stays green throughout.
    root = REPO_ROOT / "system" / "skills"
    for name in ("distillateur", "finisseur", "juge", "skill-creator"):
        text = (root / name / "SKILL.md").read_text(encoding="utf-8")
        verdict = audit_skill(name=name, skill_md=text, n_skill_md_files=1, has_emit_seam=True)
        assert verdict.anatomy_gaps == (), f"{name}: {verdict.anatomy_gaps}"
        assert verdict.ok is True, f"{name}: {verdict.reasons}"


def test_le_motif_D36_accepte_les_DEUX_langues_et_REFUSE_une_troisieme() -> None:
    """On 2026-09-09, three of the six D36 patterns accepted ONLY French: the accent was optional,
    the WORD was not. The public mirror must be entirely in English, so translating `### Methode`
    made the section DISAPPEAR TO THE JUDGE's eyes -- in silence, the judge living in a different
    file than the document. Three SKILL.md files out of eight were downgraded, two of them for days.

    This witness holds the broadening IN BOTH DIRECTIONS. Without it, broadening would be a blank
    check: a pattern that accepted any heading would no longer measure the form at all.
    """
    for francais, anglais, refuse in (
        ("## Methode", "## Method", "## Procedure"),
        ("## Entrees -> Sorties", "## Inputs -> Outputs", "## Data -> Results"),
        ("## Quand FLAG", "## When to FLAG", "## If unsure"),
    ):
        motifs = {nom: rx for nom, rx in skills._D36_BODY_SECTIONS}
        rx = next(rx for nom, rx in skills._D36_BODY_SECTIONS if rx.search(francais))
        assert rx.search(francais), f"le motif ne voit plus le francais : {francais}"
        assert rx.search(anglais), f"le motif ne voit pas l'anglais : {anglais}"
        assert not rx.search(refuse), (
            f"ELARGISSEMENT TROP LARGE : le motif accepte {refuse!r}, une troisieme orthographe "
            "que personne n'a declaree -- il ne mesure plus la forme, il l'ignore"
        )
        assert motifs, "table vide : un ensemble vide rendrait ce temoin vrai par construction"
