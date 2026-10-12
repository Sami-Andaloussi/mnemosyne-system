"""item 7 / D74 / D92 - the rangement pass names ONLY clear cruft, guards protected paths fail-closed,
plans reversibly, and emits a contract that restates the code's rules verbatim (anti-drift).

Brick-free: pure detection/plan over hand-built paths and a tmp tree, nothing installed (D126).
"""

from __future__ import annotations

from mnemosyne.production.rangement import (
    QUARANTINE_ROOT,
    RANGEMENT_RULES,
    CruftClass,
    Move,
    build_rangement_contract,
    classify,
    clear_cruft_count,
    in_scope,
    no_protected_path_touched,
    plan_is_reversible,
    plan_quarantine,
    scan,
)


class TestClassifyIsDenyByDefault:
    def test_recognized_cruft_gets_its_class(self) -> None:
        assert classify(".DS_Store") is CruftClass.OS_CRUFT
        assert classify("tests/.DS_Store") is CruftClass.OS_CRUFT
        assert classify("knowledge/library_manifest.json.bak") is CruftClass.STALE_MANIFEST_BACKUP
        assert (
            classify("knowledge/library_manifest.pre-realign.20260714T200144Z.json")
            is CruftClass.STALE_MANIFEST_BACKUP
        )
        assert classify("knowledge/ingest.log") is CruftClass.STALE_LOG
        assert classify("arj7oStGLkU.youtube.md") is CruftClass.MISPLACED_YOUTUBE
        assert classify("knowledge/POST_RUN_TODO.md") is CruftClass.STALE_TODO

    def test_unrecognized_is_never_guessed(self) -> None:
        # source / truth / config are NOT cruft - the classifier returns None, they are left untouched
        assert classify("system/lib/mnemosyne/production/rangement.py") is None
        assert classify("README.md") is None
        assert classify("system/config/policy.toml") is None
        # the LIVE manifest is protected - only its backups are cruft
        assert classify("knowledge/library_manifest.json") is None
        # a youtube fiche nested somewhere intentional (not the repo root) is NOT misplaced
        assert classify("knowledge/raw/talks/x.youtube.md") is None


class TestInScopeGuard:
    def test_protected_trees_are_out_of_scope(self) -> None:
        assert in_scope("system/state/daemon.log") is False  # the LIVE daemon log is safe
        assert in_scope("projects/saas/.DS_Store") is False  # a nested separate git repo
        assert in_scope(".venv/lib/x.orig") is False
        assert in_scope("knowledge/raw/book.md") is False
        assert in_scope("knowledge/distilled/x.md") is False
        assert (
            in_scope("knowledge/_quarantine/rangement-old/.DS_Store") is False
        )  # never re-quarantine
        assert in_scope("system/lib/mnemosyne/__pycache__/x.pyc") is False

    def test_in_scope_cruft_passes(self) -> None:
        assert in_scope(".DS_Store") is True
        assert in_scope("knowledge/ingest.log") is True
        assert in_scope("tests/.DS_Store") is True


class TestVerifyInCodeFailClosed:
    def test_refuses_a_move_off_a_protected_or_non_cruft_source(self) -> None:
        # a source in a protected tree (even named like a log) is refused
        bad = (
            Move(
                src="system/state/daemon.log",
                dst=f"{QUARANTINE_ROOT}/r/x",
                cls=CruftClass.STALE_LOG,
            ),
        )
        assert no_protected_path_touched(bad) is False
        # a source that is not itself clear cruft is refused (defense against a mis-built plan)
        not_cruft = (
            Move(
                src="README.md",
                dst=f"{QUARANTINE_ROOT}/r/README.md",
                cls=CruftClass.OS_CRUFT,
            ),
        )
        assert no_protected_path_touched(not_cruft) is False

    def test_refuses_a_destination_outside_the_quarantine(self) -> None:
        escaping = (Move(src=".DS_Store", dst="somewhere/else/.DS_Store", cls=CruftClass.OS_CRUFT),)
        assert no_protected_path_touched(escaping) is False

    def test_accepts_a_clean_plan(self) -> None:
        good = (
            Move(
                src=".DS_Store",
                dst=f"{QUARANTINE_ROOT}/rangement-x/.DS_Store",
                cls=CruftClass.OS_CRUFT,
            ),
        )
        assert no_protected_path_touched(good) is True

    def test_reversibility_rejects_colliding_destinations(self) -> None:
        clash = (
            Move(src="a/.DS_Store", dst=f"{QUARANTINE_ROOT}/r/x", cls=CruftClass.OS_CRUFT),
            Move(src="b/.DS_Store", dst=f"{QUARANTINE_ROOT}/r/x", cls=CruftClass.OS_CRUFT),
        )
        assert plan_is_reversible(clash) is False


def test_scan_finds_only_cruft_skipping_protected_trees(tmp_path) -> None:
    # a faithful mini-repo: some clear cruft, some protected/truth files that must NOT be picked up
    (tmp_path / ".DS_Store").write_text("x", "utf-8")
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge/ingest.log").write_text("x", "utf-8")
    (tmp_path / "knowledge/library_manifest.json").write_text("{}", "utf-8")  # LIVE - keep
    (tmp_path / "knowledge/library_manifest.json.bak").write_text("{}", "utf-8")  # backup - cruft
    (tmp_path / "knowledge/raw").mkdir()
    (tmp_path / "knowledge/raw/book.md").write_text("truth", "utf-8")  # source - never
    (tmp_path / "system").mkdir()
    (tmp_path / "system/state").mkdir()
    (tmp_path / "system/state/daemon.log").write_text("live", "utf-8")  # live state - never
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv/x.orig").write_text("dep", "utf-8")  # toolchain - never

    found = {c.path: c.cls for c in scan(str(tmp_path))}
    assert found == {
        ".DS_Store": CruftClass.OS_CRUFT,
        "knowledge/ingest.log": CruftClass.STALE_LOG,
        "knowledge/library_manifest.json.bak": CruftClass.STALE_MANIFEST_BACKUP,
    }
    # the plan is clean and reversible over the real scan
    moves = plan_quarantine(tuple(scan(str(tmp_path))), "stamp")
    assert no_protected_path_touched(moves) and plan_is_reversible(moves)
    # the propose-to-automate COUNT (item 3) is exactly the length of that scan - the same code home,
    # never a second walk to drift ([[contract-single-source-emit]]).
    assert clear_cruft_count(str(tmp_path)) == 3


def test_clear_cruft_count_is_zero_on_a_clean_or_absent_tree(tmp_path) -> None:
    """The item-3 nerve stays SILENT on a clean tree - no false nudge (and never raises on a missing root)."""
    (tmp_path / "system").mkdir()
    (tmp_path / "system/lib.py").write_text("code", "utf-8")  # not cruft
    assert clear_cruft_count(str(tmp_path)) == 0
    assert clear_cruft_count(str(tmp_path / "does_not_exist")) == 0


class TestEmitRestatesRulesVerbatim:
    def test_contract_carries_the_code_rules_not_a_paraphrase(self) -> None:
        contract = build_rangement_contract((), "/repo", "stamp")
        # a REAL fragment of each rule constant appears - a future edit to RANGEMENT_RULES that forgets
        # the contract (or vice-versa) turns this red (contract-single-source-emit lock).
        for rule in RANGEMENT_RULES:
            assert rule in contract
        assert "D74" in contract and "D92" in contract

    def test_empty_scan_reads_as_clean_not_blank(self) -> None:
        contract = build_rangement_contract((), "/repo", "stamp")
        assert "no clear cruft" in contract
