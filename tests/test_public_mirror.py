"""Lock tests for the public-mirror skill (D109).

Pure unit tests only, on synthetic inputs — no dependency on the live repo's current file layout
(that would make the tests fragile against ordinary, unrelated repo changes). The scope constants
themselves were derived from a real diff at the time this skill was built; these tests pin the
*classification logic*, not today's exact file list.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from mnemosyne.production import public_mirror

from mnemosyne.production.public_mirror import (
    DOCS_ALLOWLIST,
    EXCLUDE_CLAUDE,
    EXCLUDE_SYSTEM_LIB,
    EXCLUDE_TESTS,
    PERSONAL_DENYLIST_PATTERNS,
    SANITIZE_CHECKLIST,
    SECRET_SHAPED_FIXTURE_PATHS,
    SELF_REFERENTIAL_DOC_PATHS,
    uncovered_codename_candidates,
    unpublishable_link_targets,
    untracked_publishable_files,
    SyncPlan,
    STATIC_EXPORT_ONLY_PATHS,
    UI_EXPORT_RELATIVE_PATH,
    classify_changed_paths,
    export_test_suite,
    is_in_scope,
    parse_git_status_paths,
    paths_not_yet_touched,
    partition_findings,
    paths_outside_scope,
    scan_for_leaks,
)


def test_engine_module_in_scope() -> None:
    assert is_in_scope("system/lib/mnemosyne/production/distillation.py") is True


def test_governance_module_excluded() -> None:
    """What stays out is what is genuinely PERSONAL, and nothing more. Both halves are asserted
    because either alone is a lie: an exclusion list that shrank to nothing would pass a
    "these are excluded" test only by having no witnesses left, and an inclusion test alone
    cannot see the list widen until it excludes nothing at all."""
    assert is_in_scope("system/lib/mnemosyne/production/cours.py") is False
    assert is_in_scope("system/lib/mnemosyne/production/harnais_de_sabotage.py") is False
    assert is_in_scope("tests/test_cours.py") is False
    assert is_in_scope("tests/platform/test_stop_hook.py") is False


def test_the_project_engineering_engine_IS_in_scope_since_D176() -> None:
    """The other direction of the same rule, and the one that would have gone silent if the
    2026-09-08 widening had been reverted by accident: the plan/orchestration engine is a generic
    OFFER to any project (D176), not the repo owner's private ritual, so it ships. Named
    modules, not a count -- a count stays true while the set underneath changes."""
    for path in (
        "system/lib/mnemosyne/production/plancher.py",
        "system/lib/mnemosyne/production/orchestration.py",
        "system/lib/mnemosyne/production/plan_mandat.py",
        "system/lib/mnemosyne/runtime/plan_mandat_run.py",
        "system/lib/mnemosyne/guard/egress_prefix.py",
        "tests/orchestration/test_plan_ordre.py",
        "tests/platform/test_egress_prefix.py",
    ):
        assert is_in_scope(path) is True, f"{path} should ship since the D176 widening"


def test_excluded_skill_folder_is_prefix_based() -> None:
    # Exact known file, and a HYPOTHETICAL new file never seen before -- the whole
    # folder is excluded by prefix, not just the files enumerated at scaffold time.
    assert is_in_scope("system/skills/cours/SKILL.md") is False
    assert is_in_scope("system/skills/cours/a_file_added_later.py") is False


def test_new_governance_file_defaults_to_in_scope() -> None:
    # A file that is neither on the denylist nor a known-excluded folder is INCLUDED
    # by default -- membership is never guessed from the name, only from the list.
    assert is_in_scope("system/lib/mnemosyne/production/a_brand_new_module.py") is True


def test_docs_is_allowlisted_not_denylisted() -> None:
    assert is_in_scope("docs/FORMAT_PLAN.md") is True
    assert is_in_scope("docs/governance/AME.md") is False
    assert is_in_scope("docs/anything_not_on_the_allowlist.md") is False


def test_private_decision_history_never_in_scope() -> None:
    for path in ("DISCUSSION.md", "CONSTITUTION.md", "START_HERE.md"):
        assert is_in_scope(path) is False


def test_knowledge_and_projects_never_in_scope() -> None:
    assert is_in_scope("knowledge/raw/some/book.md") is False
    assert is_in_scope("projects/saas/anything.py") is False


def test_scripts_denylist() -> None:
    assert is_in_scope("scripts/migrate_library_to_public.py") is False
    assert is_in_scope("scripts/posture_garde.py") is True


def test_classify_changed_paths_splits_and_sorts() -> None:
    plan = classify_changed_paths(
        [
            "system/lib/mnemosyne/production/distillation.py",
            "DISCUSSION.md",
            "system/lib/mnemosyne/production/cours.py",
            "tests/test_distillation.py",
        ]
    )
    assert isinstance(plan, SyncPlan)
    assert plan.in_scope == (
        "system/lib/mnemosyne/production/distillation.py",
        "tests/test_distillation.py",
    )
    assert plan.out_of_scope == (
        "DISCUSSION.md",
        "system/lib/mnemosyne/production/cours.py",
    )


def test_scan_for_leaks_clean_text_reports_nothing() -> None:
    assert scan_for_leaks("def hello():\n    return 'world'\n", rel_path="clean.py") == []


def test_scan_for_leaks_catches_a_secret_shaped_string() -> None:
    findings = scan_for_leaks(
        'API_KEY = "sk-proj-abcdefghij1234567890"\n', rel_path="leaky.py"
    )
    assert any("secret" in f for f in findings)


def test_scan_for_leaks_catches_personal_identity_terms() -> None:
    findings = scan_for_leaks(
        "contact Jordan at /Users/jordan-example/notes for details\n",
        rel_path="leaky.md",
    )
    assert any("jordan" in f.lower() for f in findings)
    assert any("/Users/jordan" in f for f in findings)


def test_sanitize_checklist_is_non_empty_and_mentions_the_hard_rules() -> None:
    assert len(SANITIZE_CHECKLIST) > 100
    lower = SANITIZE_CHECKLIST.lower()
    assert "english" in lower
    assert "secret" in lower


def test_sanitize_checklist_forbids_scanner_evasion() -> None:
    # Learned from the 2026-08-19 trial: an agent split a string literal purely to stop
    # guard.redact from matching it, with no behavior change -- must be explicitly forbidden.
    lower = SANITIZE_CHECKLIST.lower()
    assert "scanner" in lower
    assert "split" in lower


def test_sanitize_checklist_requires_paired_consistency() -> None:
    # Same trial: an edited docstring example left its paired expected output stale.
    assert "corresponds after your edit" in SANITIZE_CHECKLIST


def test_sanitize_checklist_forbids_blind_find_replace() -> None:
    # Retry #2 (2026-08-19): a blind substring replace of "colle" -> "adapter" also matched
    # inside "collections", producing "adapterctions" and breaking the whole export's import.
    lower = SANITIZE_CHECKLIST.lower()
    assert "find-and-replace" in lower
    assert "collections" in lower


def test_parse_git_status_paths_modified_and_untracked() -> None:
    porcelain = " M system/lib/mnemosyne/production/distillation.py\n?? tests/test_new_module.py\n"
    assert parse_git_status_paths(porcelain) == {
        "system/lib/mnemosyne/production/distillation.py",
        "tests/test_new_module.py",
    }


def test_parse_git_status_paths_handles_rename() -> None:
    assert parse_git_status_paths("R  old_name.py -> new_name.py\n") == {"new_name.py"}


def test_parse_git_status_paths_empty_input_is_empty_set() -> None:
    assert parse_git_status_paths("") == set()


def test_paths_not_yet_touched_reports_the_gap() -> None:
    assert paths_not_yet_touched(("a.py", "b.py", "c.py"), {"a.py", "c.py"}) == ["b.py"]


def test_paths_not_yet_touched_empty_when_everything_touched() -> None:
    assert paths_not_yet_touched(("a.py", "b.py"), {"a.py", "b.py", "unrelated.py"}) == []


def test_paths_outside_scope_catches_a_denylisted_sweep() -> None:
    # Learned from the 2026-08-19 retry #2 trial: a sanitization pass processed a whole
    # directory instead of the plan's exact list, writing 48 denylisted governance files
    # (system/lib/mnemosyne/production/cours.py among them) straight into the export --
    # zero content-scanner hits, since none of them named a secret or Jordan's identity.
    touched = {
        "system/lib/mnemosyne/production/distillation.py",  # legitimately in scope
        "system/lib/mnemosyne/production/cours.py",  # denylisted -- must be caught
        "DISCUSSION.md",  # never even reaches system/ or tests/ -- also out of scope
    }
    assert paths_outside_scope(touched) == [
        "DISCUSSION.md",
        "system/lib/mnemosyne/production/cours.py",
    ]


def test_paths_outside_scope_empty_when_everything_belongs() -> None:
    touched = {"system/lib/mnemosyne/production/distillation.py", "tests/test_distillation.py"}
    assert paths_outside_scope(touched) == []


# --- the fifth gate: the export's own test suite -------------------------------------------
def _fake_export(tmp_path: Path, *, test_body: str) -> Path:
    """A minimal export tree: a `system/lib` for PYTHONPATH and one test file carrying
    `test_body`. Deliberately NOT a copy of the real export -- this exercises the GATE, not the
    mirror's content."""
    root = tmp_path / "export"
    (root / "system" / "lib").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_witness.py").write_text(test_body, encoding="utf-8")
    return root


def test_the_suite_gate_BITES_on_a_red_export(tmp_path: Path) -> None:
    """The whole point of A2: a mechanism that never bites proves nothing. A red export must
    produce a finding, and the finding must carry pytest's own words -- not a generic string."""
    root = _fake_export(tmp_path, test_body="def test_witness() -> None:\n    assert False\n")

    findings = export_test_suite(export_root=root, expected_failures=frozenset())

    assert findings, "a RED export test suite produced no finding -- the gate does not bite"
    assert "DIVERGED" in findings[0] and "NOT declared" in findings[0]
    assert "test_witness" in findings[0], "the finding must name what failed, not just that it did"


def test_the_suite_gate_stays_silent_on_a_green_export(tmp_path: Path) -> None:
    """The other half, which a gate that only ever refuses would fail: a green export must
    produce NO finding. Without this, a gate hard-wired to `return ["RED"]` would pass the test
    above and block every sync forever."""
    root = _fake_export(tmp_path, test_body="def test_witness() -> None:\n    assert True\n")

    assert export_test_suite(export_root=root, expected_failures=frozenset()) == []


def test_the_suite_gate_refuses_a_missing_tests_directory(tmp_path: Path) -> None:
    """Fail-closed on absence: an export with no `tests/` must be a finding, never a silent
    green -- an absent suite and a passing suite must not compare equal."""
    root = tmp_path / "export"
    (root / "system" / "lib").mkdir(parents=True)

    findings = export_test_suite(export_root=root, expected_failures=frozenset())

    assert findings and "not found" in findings[0]


# --- export-only documents: the mirror's own public face -----------------------------------
def test_the_mirrors_own_public_documents_do_not_count_as_overreach() -> None:
    """Arc C's mandate is to rewrite the mirror's README/ARCHITECTURE/CONTRIBUTING/CLAUDE. They
    exist ONLY in the export, so `is_in_scope` says False -- and before this exemption the
    overreach check refused them, which would have blocked the final commit after every fleet
    had already finished. Measured live on arc C's first delivery, 2026-09-08."""
    assert paths_outside_scope(sorted(STATIC_EXPORT_ONLY_PATHS)) == []


def test_the_exemption_covers_the_WHOLE_measured_class_not_the_four_documents() -> None:
    """The first fix closed a CASE (four root .md files) and left the CLASS open: 21 paths are
    tracked in the export while `is_in_scope` says False, so a legitimate sterilization edit on
    any of the other 17 still read as overreach. Caught live at 2026-09-08 23:50 -- arc C was
    editing `ui/serve.py` and the gate flagged it. This freezes the SET (never the count) of
    boundaries that carry the exemption, so widening it stays a deliberate act."""
    assert paths_outside_scope(["ui/serve.py", "ui/web/app.js", ".githooks/pre-commit"]) == []
    assert sorted(STATIC_EXPORT_ONLY_PATHS) == [
        ".gitattributes", ".githooks/pre-commit", ".githooks/pre-push", ".gitignore",
        ".python-version", "ARCHITECTURE.md", "CLAUDE.md", "CONTRIBUTING.md", "LICENSE",
        "README.md", "knowledge/README.md", "knowledge/distilled/.gitkeep",
        "knowledge/raw/.gitkeep", "projects/README.md",
    ]


def test_no_denylisted_path_can_hide_behind_either_exemption() -> None:
    """The exemptions are safe only because no denylisted path sits inside them -- measured, not
    assumed (2026-09-08: 0 of 21 denylisted paths tracked in the export). If a future edit ever
    moves a denylisted file under `ui/` or into the static list, the gate that caught 48 files
    and ~7,850 lines of French prose on 2026-08-19 goes quiet, and THIS is what says so."""
    denylisted = sorted(EXCLUDE_SYSTEM_LIB | EXCLUDE_TESTS)
    assert denylisted, "empty denylist would make this witness vacuous"
    ui_prefix = f"{UI_EXPORT_RELATIVE_PATH.as_posix()}/"
    for path in denylisted:
        assert path not in STATIC_EXPORT_ONLY_PATHS, f"{path} sheltered by the static exemption"
        assert not path.startswith(ui_prefix), f"{path} sheltered by the ui/ exemption"


def test_a_brand_new_file_at_an_undeclared_path_is_still_overreach() -> None:
    """The bite that must survive both exemptions: writing something NEW where nothing is
    declared. Sterilizing an already-published file cannot leak (it is already public); inventing
    a path can, and that is the 2026-08-19 failure mode."""
    for invented in ("notes/journal.md", "ui_backup/serve.py", "knowledge/raw/carnet.md"):
        assert paths_outside_scope([invented]) == [invented], f"{invented} must be refused"


def test_the_exemption_stays_a_LIST_and_never_widens_to_the_repo_root() -> None:
    """The other half, and the one that matters: exempting the four named documents must not
    exempt every root-level file. A blanket 'root .md is fine' rule would let this repo's own
    private DISCUSSION.md / CONSTITUTION.md / START_HERE.md through the only check that would
    have caught them."""
    for private in ("DISCUSSION.md", "CONSTITUTION.md", "START_HERE.md", "MISE_A_JOUR.md"):
        assert paths_outside_scope([private]) == [private], f"{private} must still be refused"


def test_the_exempted_documents_are_still_NOT_in_the_sync_plan() -> None:
    """The exemption lives in the overreach check and NOT in `is_in_scope`, on purpose: were it
    in `is_in_scope`, THIS repo's private README.md and CLAUDE.md would enter the sync plan and be
    copied into the public mirror -- the exact leak this module exists to prevent."""
    for path in sorted(STATIC_EXPORT_ONLY_PATHS):
        assert is_in_scope(path) is False


# --- the editor wiring that routes a PRIVATE project ---------------------------------------
def test_the_private_project_routing_hooks_leave_the_sync() -> None:
    """`stop-dispatch.sh` does not merely NAME a private project -- its body is a routing table
    carrying the project's directory layout (`projects/saas/<name>-chat-1..3`), and
    `pre-compact.sh` carries the same plus its state-file paths. Sanitizing them yields a
    dispatcher routing to nothing. Measured 2026-09-09: NONE of the four is in the mirror's
    published HEAD, so this sync would have published them for the FIRST time. Freeze the SET,
    never the count."""
    assert sorted(EXCLUDE_CLAUDE) == [
        ".claude/hooks/pre-compact.sh",
        ".claude/hooks/projectalpha-stop.sh",
        ".claude/hooks/stop-dispatch.sh",
        ".claude/settings.json",
    ]
    for dropped in EXCLUDE_CLAUDE:
        assert is_in_scope(dropped) is False, f"{dropped} must not enter the sync"


def test_dropping_the_private_hooks_does_not_drop_the_public_ones() -> None:
    """The other half: `.claude/` stays in scope. A blanket 'drop .claude' would silently remove
    five hooks the mirror already publishes -- exactly the over-wide remedy this module keeps
    catching elsewhere."""
    for kept in (
        ".claude/hooks/stop.sh",
        ".claude/hooks/README.md",
        ".claude/hooks/pre-tool-use.sh",
        ".claude/hooks/session-start.sh",
        ".claude/hooks/user-prompt-submit.sh",
    ):
        assert is_in_scope(kept) is True, f"{kept} must stay in the sync"


def test_the_dropped_wiring_is_REFUSED_by_the_overreach_gate_not_merely_unplanned() -> None:
    """Being out of scope is not enough: the files are already sitting in the export's working
    tree, written before this exclusion existed. What actually stops the leak is the overreach
    gate refusing the commit while they are there -- an exclusion alone would have let a
    fail-open commit ship them."""
    assert paths_outside_scope(sorted(EXCLUDE_CLAUDE)) == sorted(EXCLUDE_CLAUDE)


def test_the_emitted_contract_actually_BUILDS_and_carries_the_dropped_wiring() -> None:
    """The gap this closes, found the hard way 2026-09-09: adding `EXCLUDE_CLAUDE` to
    `public_mirror.py` and citing it from the emit script left 36 tests GREEN -- they all import
    from `mnemosyne.production.public_mirror` directly, while the emit script imports from the
    PACKAGE, whose `__init__` did not re-export it. `make public-mirror-emit` died with an
    ImportError that no test could see: green by the path least taken.

    It also guards the contract's own honesty. The emitted text is what a dispatched model reads
    INSTEAD of this repo; a model that never learns these four paths are dropped will happily
    recreate the private routing table this module just removed."""
    import importlib.util
    import mnemosyne.production as package

    assert hasattr(package, "EXCLUDE_CLAUDE"), "the package must re-export what the emit imports"

    emit_path = (
        Path(__file__).resolve().parents[1] / "system/skills/public-mirror/public-mirror_emit.py"
    )
    spec = importlib.util.spec_from_file_location("_pm_emit", emit_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    text = module.build_emission()
    for dropped in EXCLUDE_CLAUDE:
        assert dropped in text, f"the contract never tells a dispatched model about {dropped}"


# --- dangling references to private documents: DERIVED, never hand-listed ------------------
def test_a_private_doc_reference_is_caught_by_DERIVING_from_is_in_scope() -> None:
    """The hand-list of three root documents was measured on 2026-09-09 to catch 33 of 105
    references in the export: it missed 72 references to 23 private documents across 15 shipped
    files -- including `docs/miroir-public/MANDATS.md`, which this chantier's own orchestrator
    introduced the same evening. Deriving from `is_in_scope` gives one source of truth."""
    for private in ("docs/PLAN.md", "docs/CONTRAT_UI.md", "docs/governance/AME.md",
                    "docs/postes/chat-1.md", "docs/miroir-public/MANDATS.md"):
        findings = scan_for_leaks(f"see {private} for details", rel_path="x.py")
        assert findings, f"{private} is not shipped and must be flagged"
        assert private in findings[0]


def test_the_derived_pass_REPORTS_but_does_not_BLOCK_while_the_root_docs_do() -> None:
    """Measured 2026-09-09: of 244 private-path occurrences in the export, ~5 are references that
    DIRECT a reader and ~239 are paths merely exhibited as pattern examples (`.githooks/pre-commit`
    explains a glob with `docs/plan/arc-c.md`, a path that exists nowhere by design). At ~2%
    precision this pass is a wall if it blocks -- people bypass a wall, or they mutilate good
    comments to satisfy it. It still REPORTS everything, so the discovery survives; a human does
    the triage. The three ROOT documents keep blocking: they are never plausible examples."""
    blocking, info = partition_findings(scan_for_leaks("docs/plan/arc-c.md", rel_path="x.py"))
    assert blocking == [] and len(info) == 1, "an exhibited doc path must report, never block"

    blocking, _ = partition_findings(scan_for_leaks("see CONSTITUTION.md", rel_path="x.py"))
    assert blocking, "the root governance documents must still BLOCK"


def test_a_doc_the_mirror_DOES_ship_is_never_flagged() -> None:
    """The differentiating half. A rule that flags every `docs/*.md` would fire on the mirror's
    own shipped documentation and drown the real findings -- and `is_in_scope` is precisely what
    tells the two apart, which is why the check reads it instead of a second list."""
    for shipped in sorted(DOCS_ALLOWLIST)[:5]:
        assert scan_for_leaks(f"see {shipped}", rel_path="x.py") == [], f"{shipped} ships"


def test_a_bare_basename_never_counts_as_a_private_doc_reference() -> None:
    """The phantom this replaces: a first attempt matched basenames too and reported 130
    references to `docs/postes/README.md` in files that merely said `README.md` -- a text
    detector counting citations as instances. Full paths only."""
    for innocent in ("see README.md", "the PLAN.md format", "AME.md is a name"):
        assert scan_for_leaks(innocent, rel_path="x.py") == [], innocent


def test_the_derived_pass_is_actually_REACHED() -> None:
    """Written because the first version of this block landed AFTER `return findings` -- dead
    code that the 36 existing tests happily reported green. A check that cannot run proves
    nothing, and nothing else in this file would have noticed."""
    text = "docs/PLAN.md and docs/CONTRAT_UI.md and DISCUSSION.md"
    findings = scan_for_leaks(text, rel_path="x.py")
    assert len(findings) >= 3, f"expected the hand-list AND the derived pass, got {findings}"


# --- blocking vs expected: a gate that can never go green gets bypassed --------------------
def test_the_guards_own_fixtures_do_not_block_the_commit() -> None:
    """Without this split `verify` can never return 0: `guard.redact` always fires on the module
    that does the redacting and on the tests proving it does. A gate that is permanently red is a
    gate people learn to step around -- worse than no gate at all."""
    fixtures = [
        f"{path}: guard.redact caught a secret-shaped string in this file"
        for path in sorted(SECRET_SHAPED_FIXTURE_PATHS)
    ]
    blocking, expected = partition_findings(fixtures)
    assert blocking == [], f"the guard's own fixtures must not block: {blocking}"
    assert len(expected) == len(fixtures), "and they must still be REPORTED, never hidden"


def test_being_allowed_a_fake_key_is_not_being_allowed_ANYTHING() -> None:
    """The half that carries the whole design. The exemption is per-FINDING-KIND, not per-file: an
    identity leak or a private-doc reference inside those same seven files still blocks. Otherwise
    'this file may contain a fake token' would silently become 'this file is unchecked'."""
    path = sorted(SECRET_SHAPED_FIXTURE_PATHS)[0]
    for other in ("personal-identity term matched '\\bjordan\\b' -> 'JORDAN'",
                  "references a private-only document not shipped in this mirror -> 'docs/PLAN.md'"):
        blocking, _ = partition_findings([f"{path}: {other}"])
        assert blocking, f"{other} must still block even in {path}"


def test_a_secret_shaped_string_ANYWHERE_ELSE_still_blocks() -> None:
    """The other half: the exemption is a frozen SET of seven paths, never a rule about redaction
    files in general. A new module that starts carrying key-shaped strings blocks until a human
    deliberately adds it here."""
    for elsewhere in ("system/lib/mnemosyne/production/plan_format.py",
                      "tests/orchestration/test_plan_format.py", "scripts/whatever.py"):
        blocking, _ = partition_findings(
            [f"{elsewhere}: guard.redact caught a secret-shaped string in this file"]
        )
        assert blocking, f"{elsewhere} is not a declared fixture path and must block"


def test_the_fixture_path_set_is_FROZEN_and_includes_this_very_file() -> None:
    """Freeze the SET, never the count. The eighth entry is this file: its own fixtures carry
    `sk-...` to prove `scan_for_leaks` catches a key, so the leak scanner catches the test that
    tests the leak scanner. It was missed on the first freeze because the set was measured
    against the export's tracked files while these very tests were still being written -- a set
    measured on a population you are concurrently changing is stale before it is frozen."""
    assert sorted(SECRET_SHAPED_FIXTURE_PATHS) == [
        "system/lib/mnemosyne/guard/fencing.py",
        "system/lib/mnemosyne/guard/redact.py",
        "system/lib/mnemosyne/tools/invoke.py",
        "tests/platform/test_fencing.py",
        "tests/platform/test_redact.py",
        "tests/retrieval/test_memory_search.py",
        "tests/test_invariants.py",
        "tests/test_public_mirror.py",
    ]


def test_a_private_project_CODENAME_blocks_like_a_personal_name() -> None:
    """The mandate is literal: "zero reference to my other projects, nothing is transferred".
    Measured 2026-09-09: the export still carried 195 occurrences across 35 files -- in shipped
    prose (`docs/parentheses/README.md` uses the project as its worked example), in production
    comments (`arsenal.py`: "measured (X harvest, 2026-08-17)"), in test fixtures. No gate saw any
    of them: every other denylist pattern is a NAME, this one is a CODENAME, so no rule derived
    it, and a sibling chat found exactly ONE by eye -- in a filename. Eyes do not scale to 195.

    It BLOCKS rather than reports: unlike a doc path, a codename has no innocent illustrative
    form -- naming the project IS referencing it."""
    for text in ("# measured (Projectalpha harvest, 2026-08-17)",
                 "projects/saas/Projectalpha Research",
                 "the PROJECTALPHA parenthesis was a file",
                 "projects/personal/projectbeta/PLAN.md",
                 "Projectbeta was born while the rule was being written"):
        blocking, _ = partition_findings(scan_for_leaks(text, rel_path="x.py"))
        assert blocking, f"a private project codename must block: {text!r}"


def test_a_common_word_is_NEVER_added_to_the_denylist_on_suspicion() -> None:
    """The other half of the sweep, and the one that keeps the gate usable. Two candidates were
    checked and REJECTED: "course" is the English word behind the `cours` skill (7 hits, all
    innocent) and "trading" is a domain in the committed, public-safe taxonomy (196 hits, all
    innocent). A pattern that fires on a common word trains people to ignore every finding --
    the same 2%-precision wall the derived doc-path pass had to be pulled back from."""
    for innocent in ("a source-backed course about one named project",
                     'group = "finance/trading"',
                     "quant-trading strategies"):
        blocking, _ = partition_findings(scan_for_leaks(innocent, rel_path="x.py"))
        assert blocking == [], f"a common word must not block: {innocent!r}"


def test_the_denylist_itself_must_ship_with_PLACEHOLDERS_not_the_real_strings() -> None:
    """The paradox this file lives with: `public_mirror.py` is itself shipped, so a denylist of
    private strings would publish the very strings it hides. The export's copy carries substituted
    placeholder names instead. This witness states the invariant so the next person adding a
    pattern knows the sanitization pass owes it the same treatment -- otherwise the denylist
    becomes the leak."""
    assert len(PERSONAL_DENYLIST_PATTERNS) == 9, (
        "a pattern was added or removed -- the export's copy needs its placeholder updated in the "
        "same pass, or this module publishes what it exists to redact"
    )
    # ADMITTED WEAKNESS, because this file grave the opposite rule elsewhere: a COUNT is satisfied
    # by an EXCHANGE -- remove one pattern, add another, and 9 stays 9 in silence. It is kept as a
    # COUNT on purpose: freezing the SET here would mean writing the private strings into a second
    # shipped file, which is the leak this witness exists to prevent. So this is a SIGNPOST, not
    # the barrier. The barrier is `test_the_exported_copy_is_scanned_with_its_own_denylist`, which
    # reads the EXPORT and fires on a real string whatever the count says -- and it is what caught
    # the author of this very line, minutes after two patterns were added upstream.


def test_the_per_file_contract_names_the_emoji_rule_AND_its_two_exceptions() -> None:
    """The clause "no emoji" reached the PRESENTATION mandate and never this per-file contract --
    so it held for the 4 root documents and was invisible for the other 331 files. Measured
    2026-09-09: the published mirror carried ZERO emoji and this sync would have introduced 1,576
    across 81 files, because the plan engine (by far the most emoji-dense code) enters the showcase
    for the first time. A rule that lives in one mandate is not a rule of the sync."""
    checklist = SANITIZE_CHECKLIST.lower()
    assert "emoji" in checklist, "the per-file contract must carry the rule, not just one mandate"
    assert "parses as data" in checklist or "parses" in checklist, (
        "without the format-glyph exception the pass breaks the plan parser"
    )
    assert "fixture" in checklist, (
        "without the Unicode-fixture exception the pass silently voids grapheme tests"
    )


def test_the_EXPORTED_copy_of_this_module_carries_no_denylisted_string() -> None:
    """The self-check that was missing, and it cost a real leak on 2026-09-09.

 A comment in this module warns, in so many words, that the file SHIPS and that its denylist
 patterns must therefore be published under placeholder names "or the denylist becomes the leak
 it exists to prevent". Three hours later the same author added `EXCLUDE_CLAUDE` a few lines
 below, naming a private path IN CLEAR. **Writing the guard is not applying it.**

 The check belongs on the EXPORTED copy, never on this one: here the constant MUST name the
 real path or it excludes nothing. The leak exists only where the file is published. That
 asymmetry is the whole point, and stating it wrong is how the first version of this test
 failed on a file that was perfectly correct.

 Skips when the export is absent -- a witness that cannot see its subject must say so rather
 than pass in silence."""
    export = Path(__file__).resolve().parents[1] / "projects/mnemosyne/mnemosyne-github"
    shipped = export / "system/lib/mnemosyne/production/public_mirror.py"
    if not shipped.exists():
        pytest.skip("export tree not present -- nothing to judge")

    source = shipped.read_text(encoding="utf-8")
    start = source.index("PERSONAL_DENYLIST_PATTERNS")
    end = source.index("PRIVATE_DOC_REFERENCE_PATTERNS")
    ailleurs = source[:start] + source[end:]

    coupables = [p.pattern for p in PERSONAL_DENYLIST_PATTERNS if p.search(ailleurs)]
    assert coupables == [], (
        f"the SHIPPED copy names {coupables} outside its own denylist definition. Use a "
        "placeholder, exactly as the five original patterns already do in the export."
    )


def test_the_denylist_boundary_treats_UNDERSCORE_as_a_separator() -> None:
    """`\b` is the wrong boundary and it cost a real miss. `_` is a word character in `re`, so
    `\bprojectalpha\b` does NOT match `_PROJECTALPHA_HOSTS`, `projectalpha_pos` or `test_the_real_projectalpha_block` --
    exactly the shapes a half-finished rename leaves behind: the strings already say "research",
    the identifiers still say the codename. Found 2026-09-09 by a sibling chat auditing from a
    disjoint scope, on a gate written hours earlier and believed sound.

    Neither of us would have found it alone -- and the fix belongs to every pattern here, not just
    the one that was caught, which is why the boundary is defined ONCE."""
    for cache in ("_PROJECTALPHA_HOSTS = 1", "projectalpha_pos = 3", "def test_the_real_projectalpha_block():",
                  "JORDAN_ROOT = Path()", "x = projectbeta_id", "EXAMPLEPROJECT_KEY"):
        assert scan_for_leaks(cache, rel_path="x.py"), f"underscore-glued: {cache!r} must be caught"

    for innocent in ("projectalphaing the terrain", "projectbetaation of light", "jordanesque"):
        assert scan_for_leaks(innocent, rel_path="x.py") == [], (
            f"{innocent!r} embeds the word in a LONGER one -- widening the boundary must not "
            "widen it to substrings, or the gate starts firing on English"
        )


# --- the detector may NAME what it detects; it may not hide anything else -------------------
def test_the_dangling_ref_detector_may_name_the_documents_it_hunts() -> None:
    """`PRIVATE_DOC_REFERENCE_PATTERNS` spells CONSTITUTION.md/DISCUSSION.md/START_HERE.md in clear,
    and this file asserts on those same literals. The pass therefore fires on both BY CONSTRUCTION
    -- the same shape as `guard.redact` firing on the redaction fixtures. Six findings, measured on
    the export 2026-09-09: two files x three documents."""
    findings = [
        f"{path}: references a private-only document not shipped in this mirror -> {doc!r}"
        for path in sorted(SELF_REFERENTIAL_DOC_PATHS)
        for doc in ("CONSTITUTION.md", "DISCUSSION.md", "START_HERE.md")
    ]
    blocking, expected = partition_findings(findings)
    assert blocking == [], f"the detector's own literals must not block: {blocking}"
    assert len(expected) == 6, "and all six must still be REPORTED, never hidden"


def test_naming_the_docs_you_hunt_is_not_being_allowed_ANYTHING() -> None:
    """The half that carries the design, and the one attempt #1 of this chantier failed: it died for
    DISARMING the exported copy's denylist. An identity leak or a secret-shaped string inside these
    two files still BLOCKS -- the exemption is per-finding-KIND, never per-file."""
    identity = "personal-identity term matched '(?<![A-Za-z0-9])(jordan)(?![A-Za-z0-9])' -> 'jordan'"
    for path in sorted(SELF_REFERENTIAL_DOC_PATHS):
        blocking, _ = partition_findings([f"{path}: {identity}"])
        assert blocking, f"an identity leak must still block in {path}"

    # And the sets are INDEPENDENT, never a shared 'trusted files' list. This assertion was written
    # over-broad first and the test caught it: `tests/test_public_mirror.py` legitimately sits in
    # SECRET_SHAPED_FIXTURE_PATHS (its fixtures carry `sk-...` to prove the scanner catches a key),
    # so a redact finding there is expected -- while the very same finding BLOCKS in the production
    # module, which is in neither redaction set. One exemption never grants another.
    redact = "guard.redact caught a secret-shaped string in this file"
    blocking, _ = partition_findings(
        [f"system/lib/mnemosyne/production/public_mirror.py: {redact}"]
    )
    assert blocking, "naming private docs does not buy a redaction exemption"
    blocking, expected = partition_findings([f"tests/test_public_mirror.py: {redact}"])
    assert blocking == [] and expected, "and the redaction exemption is granted by ITS OWN set"


def test_a_private_doc_reference_ANYWHERE_ELSE_still_blocks() -> None:
    """The other half: a frozen SET of two paths, never a rule about 'files that mention documents'.
    Measured by SET DIFF against the published HEAD ad755e3 -- 15 pairs (file, document) online,
    20 in the export, 16 of them NEW and 11 published ones cleaned away. `15 -> 20` reads as '+5'
    and is a near-total substitution with 4 survivors; every published pair is a TEST file while 9
    newcomers are PRODUCTION. Freezing the published baseline would have exempted exactly the
    production sites this must catch."""
    for elsewhere in ("system/lib/mnemosyne/production/derives.py",
                      "system/lib/mnemosyne/runtime/accord_chiffre_run.py",
                      "tests/conftest.py"):
        blocking, _ = partition_findings(
            [f"{elsewhere}: references a private-only document not shipped in this mirror -> 'CONSTITUTION.md'"]
        )
        assert blocking, f"{elsewhere} is not the detector and must block"


def test_the_self_referential_path_set_is_FROZEN() -> None:
    """Freeze the SET, never the count -- and keep it at two. Any third entry is a file that stopped
    being checked for dangling references, which is a deliberate, reviewed act."""
    assert sorted(SELF_REFERENTIAL_DOC_PATHS) == [
        "system/lib/mnemosyne/production/public_mirror.py",
        "tests/test_public_mirror.py",
    ]


# --- the third and fourth codename: the sweep that closed the second had the same blind spot ---
def test_the_third_codename_and_its_glued_forms_are_caught() -> None:
    """Measured 2026-09-09: 29 occurrences in 8 files of the export -- three PRODUCTION modules and
    three in `docs/FORMAT_PLAN.md`, the showcase's own front door -- and the gate saw NONE. The
    previous sweep is described in this module as "listing every real project directory on disk";
    it listed ONE level, where the folders are generic (`saas`, `trading`, `personal`). The
    codenames live one level DOWN. The sweep that closed the gap carried the same blind spot."""
    for form in ("veskin_forge", "veskin-forge", "veskin forge", "Veskinforge", "VESKIN_FORGE",
                 "pelmar-tessil", "pelmar tessil"):
        assert scan_for_leaks(f"see {form} here", rel_path="x.py"), f"{form} must be caught"


def test_the_new_patterns_do_not_eat_innocent_neighbours() -> None:
    """The other half, without which a denylist becomes a wall: a pattern that fires on ordinary
    words teaches people to ignore the gate. None of these is a reference to a private project."""
    for innocent in ("alphabet", "the lab", "alpha channel", "usine", "conception of a plan",
                     "alphanumeric", "labour"):
        assert scan_for_leaks(f"see {innocent} here", rel_path="x.py") == [], (
            f"{innocent!r} is an ordinary word and must pass"
        )


def test_the_candidate_probe_proposes_what_no_pattern_covers() -> None:
    """The DISCOVERY half. Three codenames in a row were found by an eye and not by this gate, so
    the population is derived from disk instead of enumerated. It REPORTS -- a bare directory name
    still collides with English, and a gate that is wrong most of the time is a wall."""
    # The candidate name here is INVENTED. The first version of this witness used a real project
    # folder of this machine, and the probe it tests reported it -- from the shipped copy of this
    # very file -- within minutes. A fixture that needs "a private codename" must never borrow a
    # real one: the test file ships, so the fixture becomes the leak.
    text = "we mention zelbrac-tissane, veskin_forge, config and data in the mirror"
    got = uncovered_codename_candidates(
        ["zelbrac-tissane", "veskin_forge", "config", "data", "ab"], text, own_dir_names=["config"]
    )
    assert got == ["zelbrac-tissane"], got
    #   veskin_forge -> already covered by a denylist pattern (it BLOCKS, no need to propose it)
    #   config    -> a directory the mirror itself uses: an ordinary word of this codebase
    #   data      -> CODENAME_STOPWORDS
    #   ab        -> shorter than 4 characters


def test_the_probe_reports_and_never_blocks() -> None:
    """A candidate is a question for a human, not a refusal. Measured on the real export: narrowing
    the population to depth<=2 under `projects/` and dropping names the mirror uses as directories
    took this pass from 250 candidates to 4 -- the difference between a signal and a wall."""
    finding = "(export): a project directory on this machine is named in the mirror and no denylist pattern covers it -> 'whatever'"
    blocking, informational = partition_findings([finding])
    assert blocking == [] and informational == [finding]


# --- what git will not publish is, for the reader, what does not exist ----------------------
def test_a_document_pointing_at_an_UNTRACKED_file_blocks() -> None:
    """Found by a sibling chat: `README.md` and `ARCHITECTURE.md` linked to two production modules
    written during the sync and never `git add`-ed. On a public clone those links are 404s, in the
    two documents a reader opens first. The remedy is `git add`, NEVER cutting the link -- the link
    is correct, it is the staging that is missing."""
    got = unpublishable_link_targets(
        "see [the engine](system/lib/x.py) and `system/lib/y.py`",
        rel_path="README.md", tracked={"system/lib/y.py"}, on_disk={"system/lib/x.py", "system/lib/y.py"},
    )
    assert len(got) == 1 and "system/lib/x.py" in got[0], got
    assert "git add" in got[0], "the finding must name the remedy, not just the defect"


def test_an_ABSENT_target_is_NOT_reported_and_that_is_the_whole_precision() -> None:
    """The half that keeps this pass usable. Measured on the export: 139 named paths are absent
    from disk and nearly all are illustrative (`docs/plan/arc-c.md` explaining a glob), while 6 are
    present-but-untracked and every one is real. Blocking on the 139 would rebuild the 2%-precision
    wall this module refuses elsewhere -- a gate wrong most of the time is one people walk around."""
    assert unpublishable_link_targets(
        "see [an example](docs/plan/arc-c.md) and https://example.com/x.py",
        rel_path="README.md", tracked=set(), on_disk=set(),
    ) == []
    assert unpublishable_link_targets(
        "see `system/lib/x.py`", rel_path="notes.txt", tracked=set(), on_disk={"system/lib/x.py"}
    ) == [], "only documents are scanned"


def test_untracked_files_block_even_when_NOTHING_points_at_them() -> None:
    """The wider form, and the one the coverage gate is blind to by construction: it counts a path
    as PROCESSED when it appears in `git status`, and an untracked file appears there. So
    `uncovered = 0` and `publishable = 0` hold at the same time. Measured 2026-09-09: 155 untracked
    files in the export, including the whole public-mirror skill and the plan engine that a human
    arbitration had just brought INTO the showcase."""
    got = untracked_publishable_files(tracked={"a.py"}, on_disk={"a.py", "b.py", "c.py"})
    assert len(got) == 1, "one aggregate finding, never one line per file: an unreadable refusal is overridden"
    assert "2 file" in got[0] and "b.py" in got[0] and "git add" in got[0], got
    blocking, _ = partition_findings(got)
    assert blocking == got, "this BLOCKS -- publishing without it ships a mirror missing files"


def test_nothing_untracked_is_silence_not_a_finding() -> None:
    """A gate that fires when there is nothing to fix teaches people to ignore it."""
    assert untracked_publishable_files(tracked={"a.py", "b.py"}, on_disk={"a.py", "b.py"}) == []


def test_the_two_populations_must_NOT_be_the_SAME_set() -> None:
    """The asymmetry IS the gate, and this witness exists because a well-argued slogan would erase
    it: "a publication gate iterates on the TARGET state, never the current state" is right for the
    files to READ and fatal for the paths to JUDGE. Measured on the real export by collapsing the
    two into one set: 8 dangling links -> 0, untracked finding -> 0, every other test still green.
    A present-but-untracked file belongs to the FUTURE population and not to the PRESENT one."""
    both = {"README.md", "system/lib/x.py"}
    assert unpublishable_link_targets(
        "see `system/lib/x.py`", rel_path="README.md", tracked=both, on_disk=both
    ) == [], "collapsed populations report nothing -- this is the SABOTAGE, not the design"
    assert untracked_publishable_files(tracked=both, on_disk=both) == []

    assert unpublishable_link_targets(
        "see `system/lib/x.py`", rel_path="README.md",
        tracked={"README.md"}, on_disk=both,
    ), "judged against what a commit would carry NOW, the dangling link is visible"
    assert untracked_publishable_files(tracked={"README.md"}, on_disk=both)


# ---------------------------------------------------------------------------------------------
# EXPECTED_EXPORT_FAILURES -- the gate stopped requiring ZERO on 2026-09-09 and now compares SETS.
# Requiring zero was unreachable: 124 of the export's checks read a corpus this mirror does not
# ship. These four witnesses hold the widening in BOTH directions, because a gate that only
# forbids NEW failures would let a renamed or silently-weakened test leave without a word.
# ---------------------------------------------------------------------------------------------


def _suite_qui_rend(
    sortie: str, monkeypatch, tmp_path: Path, attendues: frozenset[str] | None = None
) -> list[str]:
    """Runs `export_test_suite` against a stubbed pytest, so the diff logic is measured on its own."""
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "system" / "lib").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(public_mirror, "purge_bytecode_caches", lambda _root: 0)

    class _Fini:
        returncode = 1
        stdout = sortie
        stderr = ""

    monkeypatch.setattr(public_mirror.subprocess, "run", lambda *a, **k: _Fini())
    return public_mirror.export_test_suite(export_root=tmp_path, expected_failures=attendues)


def _ligne(nodeid: str) -> str:
    return f"FAILED {nodeid} - AssertionError: whatever"


def test_the_gate_is_SILENT_when_the_failing_set_is_EXACTLY_the_declared_one(
    monkeypatch, tmp_path
) -> None:
    """The passing case, and it must exist: without it the gate could be blocking on everything."""
    sortie = "\n".join(
        [_ligne(n) for n in sorted(public_mirror.EXPECTED_EXPORT_FAILURES)] + ["3 failed, 10 passed"]
    )
    assert _suite_qui_rend(sortie, monkeypatch, tmp_path) == []


def test_the_gate_BLOCKS_on_a_failure_that_was_never_declared(monkeypatch, tmp_path) -> None:
    sortie = "\n".join(
        [_ligne(n) for n in sorted(public_mirror.EXPECTED_EXPORT_FAILURES)]
        + [_ligne("tests/whatever.py::test_a_brand_new_break"), "4 failed, 9 passed"]
    )
    findings = _suite_qui_rend(sortie, monkeypatch, tmp_path)
    assert findings and "test_a_brand_new_break" in findings[0]
    assert "NOT declared" in findings[0]


def test_the_gate_BLOCKS_when_a_DECLARED_failure_stops_failing(monkeypatch, tmp_path) -> None:
    """A rename makes an id vanish and another appear with no change in substance -- measured on
    2026-09-09, four ids at once. If the gate only watched for NEW failures, the rename would erase
    a declared defect in silence."""
    garde, *reste = sorted(public_mirror.EXPECTED_EXPORT_FAILURES)
    sortie = "\n".join([_ligne(n) for n in reste] + ["2 failed, 11 passed"])
    findings = _suite_qui_rend(sortie, monkeypatch, tmp_path)
    assert findings and garde in findings[0]
    assert "no longer fail" in findings[0]


def test_a_COLLECTION_ERROR_blocks_and_is_never_read_as_an_empty_failing_set(
    monkeypatch, tmp_path
) -> None:
    """A run that collected nothing prints the same `0 failed` as a clean run. Measured twice in one
    day on this very repository. The gate must refuse to compare a set it never measured."""
    sortie = "ERROR tests/x.py - ImportError: boom\n\nno tests ran in 0.01s"
    findings = _suite_qui_rend(sortie, monkeypatch, tmp_path)
    assert findings and "COLLECTION ERROR" in findings[0]
    assert "never measured" in findings[0]
