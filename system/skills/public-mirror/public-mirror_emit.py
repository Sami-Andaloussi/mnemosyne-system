#!/usr/bin/env python3
"""Couture `public-mirror-emit` — EMITS the complete, self-sufficient public-mirror contract from
the single source of truth: system/lib/mnemosyne/production/public_mirror.py. Same anti-drift
lesson as the distillateur/finisseur/skill-creator seams (contract-single-source-emit, commit
241e525), applied to a new requirement: this contract must be followable by ANY capable LLM, not
just this session, given nothing but repo read/write access and this printed text (D174) — no
extra instructions from the human, no extra context from this conversation.

Print-only, no model/brick required (like the other -emit seams).

Usage: make public-mirror-emit
"""

from __future__ import annotations

import sys

_RULE = "=" * 92


def build_emission() -> str:
    """Assemble the emission from the ONE code home — returned as text; `main` prints it. Pure and
    offline: every fact below is read straight from `mnemosyne.production.public_mirror`, so this
    cannot drift from what the code actually enforces."""
    from mnemosyne.production import (
        DOCS_ALLOWLIST,
        EXCLUDE_SCRIPTS,
        EXCLUDE_SKILL_FOLDERS,
        EXPORT_RELATIVE_PATH,
        INCLUDE_ROOTS,
        MAKEFILE_DROPPED_TARGETS,
        SANITIZE_CHECKLIST,
        EXCLUDE_CLAUDE,
        STATIC_EXPORT_ONLY_PATHS,
    )

    lines: list[str] = [
        "PUBLIC-MIRROR CONTRACT (emitted from code — system/lib/mnemosyne/production/public_mirror.py — never hand-copied)",
        _RULE,
        "",
        "WHAT THIS IS",
        "You are bringing a public, sanitized, English mirror of this private repository up to "
        f"date. The mirror lives at {EXPORT_RELATIVE_PATH} (its own git repo, already pushed "
        "public to github.com/Sami-Andaloussi/mnemosyne-system). You need nothing beyond this text plus "
        "read/write access to this repository and that folder — follow it exactly and you will do "
        "the same job any other capable model would, with zero extra input from a human.",
        "",
        "HARD RULES — never relaxed, regardless of who or what is executing this",
        "  1. NEVER push or publish anything. Prepare and commit LOCALLY inside the export repo "
        "only — a human approves every `git push` explicitly; that decision is never yours.",
        "  2. NEVER read source content from the raw working tree. Use `git show HEAD:<path>` (or "
        "`git archive`) from THIS repo — some of its config files carry local, personal, "
        "uncommitted edits that a raw filesystem copy would leak into the public export.",
        "  3. Every file you produce must pass `make public-mirror-verify` before you commit it — "
        "it checks FOUR independent things: content (no secret or personal-identity leak), "
        "coverage (every in-scope path from step 1's plan was actually touched), scope (nothing "
        "OUTSIDE the plan was touched — e.g. a whole directory swept up instead of the plan's "
        "exact path list), and that `import mnemosyne` still succeeds against the export (catches "
        "code-breaking corruption — see checklist rule 9). On any finding: fix and re-run — never "
        "commit past one.",
        "  4. Keep each sanitization call SMALL and BOUNDED. If you dispatch this work to a "
        "cheaper/smaller model (recommended — this is mechanical translation + redaction, not "
        "judgment), give it ONE file — or a few small files together, well under ~40,000 tokens of "
        "combined input — per call, with the checklist below inlined IN FULL. Do not assume it can "
        "look anything up beyond what you give it in that one call. A 200,000-token-context model "
        "with a 64,000-token output cap (e.g. Claude Haiku) cannot safely take a large batch at "
        "once — its OUTPUT for a translate-and-clean pass runs close to the size of its input.",
        "  5. Process EVERY path listed in step 1's IN SCOPE plan — not a sample, not \"the "
        "important ones,\" not a subset because a batch ran long. If a specific path is genuinely "
        "impossible to process, stop and name that exact path and why to the human instead of "
        "omitting it from your summary. Rule 3's mechanical check is a backstop, not a substitute "
        "for actually finishing the plan — a report that is technically true about what you "
        "touched is still a failure if it does not say what you skipped.",
        "  6. Never restructure code, split a string literal, or rewrite a pattern for the sole "
        "purpose of changing what `make public-mirror-verify` matches, without any real change in "
        "meaning or behavior — including this sync tool's own code. Full rule and why: checklist "
        "rule 7 below.",
        "",
        "STEPS",
        "  1. Run `make public-mirror`. Deterministic, no model: it prints every path that changed "
        "in this repo since the last recorded sync, split into IN SCOPE (needs sanitizing) and "
        "out-of-scope (ignored, informational). First run: everything in scope counts as new.",
        "  2. For each in-scope path — ONLY the exact paths step 1 printed, never a directory "
        "swept wholesale — read it with `git show HEAD:<path>` from this repo, produce the "
        f"sanitized replacement per the checklist below, and write it to "
        f"{EXPORT_RELATIVE_PATH}/<same path>. One model call per file or small batch — rule 4. "
        "Every single in-scope path gets this treatment — rule 5 — and NO path outside it does, "
        "even if it lives in the same directory as one that does.",
        "  3. Run `make public-mirror-verify`. It reports four independent things: content "
        "findings (secret or personal-identity leaks), coverage findings (in-scope paths from "
        "step 1 that were never touched), scope findings (touched paths that were never in the "
        "plan at all), and an import-smoke-test failure (the export no longer imports cleanly). "
        "Fix and re-run until ALL FOUR are empty.",
        f"  4. Commit LOCALLY inside {EXPORT_RELATIVE_PATH} (`git add` + `git commit`, no push).",
        "  5. Run `make public-mirror-mark-synced` so the next plan starts from this point.",
        "  6. Report to the human: how many in-scope paths you processed out of the plan's total, "
        "confirm step 3 reported both checks clean, and stop. Do not push.",
        "",
        "SCOPE — read live from the code below, never hand-maintained prose that could drift from it",
        f"  Included roots at all             : {', '.join(INCLUDE_ROOTS)}",
        f"  docs/ is allow-listed to just     : {', '.join(sorted(DOCS_ALLOWLIST)) or '(none)'}",
        f"  scripts/ excludes                 : {', '.join(sorted(EXCLUDE_SCRIPTS)) or '(none)'}",
        f"  system/skills/ folders excluded   : {', '.join(EXCLUDE_SKILL_FOLDERS)}",
        "  system/lib/mnemosyne/{production,runtime}/ and the folders above ALSO denylist specific "
        "files by exact name (Mnemosyne's own internal plan/governance machinery — private, "
        "coupled to docs this mirror doesn't carry). `make public-mirror` already applies the full "
        "list; you do not need to reproduce it by hand, and should not try to guess membership "
        "from a file's name — a new file in one of these two directories that isn't already "
        "denylisted defaults to IN SCOPE and is printed plainly in the plan for a human to notice.",
        f"  Makefile targets dropped in the export : {', '.join(MAKEFILE_DROPPED_TARGETS)}",
        "  Never touched by this sync (hand-authored once in the export, independent of this "
        f"repo's content): {', '.join(sorted(STATIC_EXPORT_ONLY_PATHS))}",
        f"  .claude/ is in scope EXCEPT these, dropped 2026-09-09 : "
        f"{', '.join(sorted(EXCLUDE_CLAUDE))}",
        "  Those four are NOT a naming problem you can translate away: their SUBSTANCE is a "
        "routing table naming a private project, its directory layout and its state files, plus "
        "the settings file that wires them. A sanitized dispatcher routes to nothing. Do not "
        "recreate them, do not translate them, and if you find them in the export's working tree, "
        "they must LEAVE it -- the overreach check refuses the commit while they are there.",
        "  ui/ in the export syncs from a DIFFERENT source — projects/mnemosyne/ui/, its own "
        "sibling git repo — never from this tree. Out of scope for the steps above.",
        "",
        "PER-FILE SANITIZATION CHECKLIST — inline this verbatim in every model call you dispatch",
        _RULE,
        SANITIZE_CHECKLIST.rstrip("\n"),
        _RULE,
        "",
        "This text is generated fresh from the code every time — if anything here ever looks stale "
        "against system/lib/mnemosyne/production/public_mirror.py, the code wins: re-run "
        "`make public-mirror-emit` and use that output, never a memory of a previous run.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    _ = sys.argv[1:] if argv is None else argv  # no arguments used — the contract is not per-file
    print(build_emission(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
