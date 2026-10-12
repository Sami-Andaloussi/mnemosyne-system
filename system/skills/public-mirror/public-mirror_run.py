#!/usr/bin/env python3
"""Thin adapter for the public-mirror skill (D174 applied to any LLM host) - orchestration ONLY:
dispatches a CLI subcommand to the code home in
system/lib/mnemosyne/production/public_mirror.py. Never reimplements logic that belongs there
(see system/skills/skill-creator/references/architecture.md).

Usage:
  make public-mirror              # print the deterministic sync plan (default action)
  make public-mirror-verify       # scan the export tree for secret / personal-identity leaks
  make public-mirror-mark-synced  # record the export as caught up to source HEAD
"""

from __future__ import annotations

import sys


def main() -> int:
    from mnemosyne.production.public_mirror import (
        export_import_smoke_test,
        export_test_suite,
        mark_synced,
        run,
        uncovered_in_scope_paths,
        unexpected_touched_paths,
        partition_findings,
        verify_export,
        SyncMarkerUnknownHere,
    )

    args = sys.argv[1:]
    action = args[0] if args else "plan"

    if action == "plan":
        run()
        return 0

    if action == "verify":
        findings = verify_export()
        try:
            missing = uncovered_in_scope_paths()
            unexpected = unexpected_touched_paths()
        except SyncMarkerUnknownHere as refus:
            # A REFUSAL, not a traceback. This is the first thing that happens to anyone
            # who clones this repository and runs the tool: the recorded marker names a
            # commit of the PRIVATE source repo, which this checkout does not have.
            print(f"public-mirror verify: REFUSED -- {refus}", file=sys.stderr)
            return 2
        import_errors = export_import_smoke_test()
        suite_errors = export_test_suite() if not import_errors else []
        if not findings and not missing and not unexpected and not import_errors and not suite_errors:
            print(
                "public-mirror verify: clean -- no secret/personal-identity leak, every in-scope "
                "path from the plan was touched, nothing outside the plan's scope was touched, "
                "`import mnemosyne` succeeds against the export, and the export's OWN test "
                "suite passes."
            )
            return 0
        findings, expected = partition_findings(findings)
        if expected:
            print(
                f"public-mirror verify: {len(expected)} expected finding(s) -- the redaction guard "
                "firing on its OWN fixtures. NOT blocking (a redaction module with no "
                "secret-shaped string tests nothing), printed so a human still sees them:"
            )
            for finding in expected:
                print(f"  ~ {finding}")
        if findings:
            print(f"public-mirror verify: {len(findings)} finding(s) -- DO NOT commit until resolved:")
            for finding in findings:
                print(f"  ! {finding}")
        if missing:
            print(
                f"public-mirror verify: {len(missing)} in-scope path(s) from the plan were never "
                "touched in the export -- DO NOT commit until every one is processed, or explicitly "
                "justified to the human:"
            )
            for path in missing:
                print(f"  ? {path}")
        if unexpected:
            print(
                f"public-mirror verify: {len(unexpected)} touched path(s) are OUTSIDE the plan's "
                "scope entirely (is_in_scope() is False) -- this usually means a denylisted "
                "directory got swept up wholesale instead of the plan's exact path list. DO NOT "
                "commit until these are reverted or you can justify each one to the human:"
            )
            for path in unexpected:
                print(f"  * {path}")
        if import_errors:
            print(
                "public-mirror verify: `import mnemosyne` FAILS against the export's current "
                "working tree -- this usually means a translation pass corrupted code syntax or "
                "an identifier (e.g. a blind find-replace matching inside an unrelated name). DO "
                "NOT commit until it imports cleanly:"
            )
            for err in import_errors:
                print(f"  X {err}")
        if suite_errors:
            print(
                "public-mirror verify: the export's OWN test suite FAILS -- a leak scan, a path "
                "check and an import all say nothing about BEHAVIOUR. Retry #1 silently voided two "
                "security assertions by rewriting their example values, and retry #2 broke all 78 "
                "test files with one corrupted line. DO NOT commit until it is green:"
            )
            for err in suite_errors:
                print(f"  T {err}")
        return 1

    if action == "mark-synced":
        commit = args[1] if len(args) > 1 else None
        mark_synced(commit)
        return 0

    print(f"unknown action {action!r} -- expected 'plan', 'verify', or 'mark-synced'")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
