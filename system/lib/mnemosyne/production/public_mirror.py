"""Public mirror sync — the code home for the `public-mirror` skill.

Keeps `projects/mnemosyne/mnemosyne-github` (a separate git repo, already pushed public to
`github.com/Sami-Andaloussi/mnemosyne-system`) in sync with this repo's engine, cheaply and
incrementally, without ever depending on this conversation or on Jordan re-explaining anything —
D174 applied to a new kind of target: any capable LLM, given repo access and this module's
printed contract (`make public-mirror-emit`), must do the same job any other one would.

**Why the scope manifest lives here, in code, and not under `system/config/`.** That directory
is a walled zone (Guard policy, egress allow-list) that only Jordan's own live gesture can touch —
see CLAUDE.md, "trois murs". This manifest is not Guard policy: it is an ordinary, versioned
judgment call about what belongs in a public mirror, exactly the kind of thing a skill's own code
home already holds (compare `finisher.FINISH_PROMPT`, `distillation`'s chunking rules). It was
derived once from the live diff between `system/`/`tests/` here and the already-published export
(commit that introduced this file), not invented — see `_EXCLUDE_*` below.

**Two-phase design, both deterministic and model-free — the only model calls happen OUTSIDE this
module, one bounded call per changed file, driven by `SANITIZE_CHECKLIST` below:**
  1. `run()` — computes what changed in THIS repo since the last recorded sync (plain `git diff`,
     no model) and classifies it in/out of scope. Prints a plan; writes nothing.
  2. `verify_export()` — after sanitization has produced content in the export tree, scans it for
     a secret (`mnemosyne.guard.redact`) or this repo owner's own identifying strings, independent
     of whatever produced the content (a producer must not also be its own verifier). Fail-closed:
     any finding blocks the local commit the emitted recipe tells the caller to make.

Nothing in this module ever pushes to the public remote — see `SANITIZE_CHECKLIST` and the recipe
printed by `public_mirror_emit.py`: publish is always a separate, explicit, human-confirmed step.

Code & docstrings English (D117).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Container, Final, Iterable

from mnemosyne.guard.redact import redact_sensitive_text

# ---------------------------------------------------------------------------------------------
# Scope manifest — derived from the live diff on 2026-08-18, not guessed. Re-derive by diffing
# `git ls-files <root>` between this repo and the export whenever the boundary needs revisiting;
# don't hand-edit these sets from memory.
# ---------------------------------------------------------------------------------------------

EXPORT_RELATIVE_PATH = Path("projects/mnemosyne/mnemosyne-github")

#: Top-level roots considered at all. Anything else (DISCUSSION.md, CONSTITUTION.md, START_HERE.md,
#: knowledge/raw, knowledge/distilled, projects/ other than this mirror itself, ...) is simply
#: never reached by `is_in_scope` — no denylist needed for the rest of the repo.
INCLUDE_ROOTS = ("system/", "tests/", "scripts/", ".claude/", "pyproject.toml", "uv.lock", "Makefile")

#: docs/ is the OPPOSITE shape from everything else: excluded by default, only these exact paths
#: are in scope (generic methodology docs, not private decision history).
DOCS_ALLOWLIST = frozenset({
    "docs/FORMAT_PLAN.md",
    "docs/parentheses/README.md",
    "docs/signalements/README.md",
})

#: scripts/ denylists two personal-workflow scripts (one operates on Jordan's own knowledge library,
#: the other is a personal watch/monitoring script) — everything else under scripts/ is in scope.
EXCLUDE_SCRIPTS = frozenset({
    "scripts/migrate_library_to_public.py",
    "scripts/veille-chats.sh",
})

#: Whole system/skills/ subfolders excluded outright — a prefix match, so a NEW file added inside
#: one of these later is still caught without needing to re-derive the denylist.
EXCLUDE_SKILL_FOLDERS = ("cours", "enqueteur", "harnais-de-sabotage")

#: Exact files under system/lib/mnemosyne/{production,runtime}/ excluded by name. This list USED
#: to hold the whole plan/orchestration engine (plan_*, orchestration, gates, orphelins,
#: regle_candidate, rendement, ...) on the rationale that it was "specific to the repo owner's
#: internal process". D176 retired that rationale: project engineering is an OFFER made to every
#: project, not a private ritual — so 46 modules moved INTO scope on 2026-09-08, and with them the
#: most demonstrative engineering in the repo. What stays out is what is genuinely personal: a
#: learning/course tool and a sabotage harness. `guard/egress_prefix.py` left this list too — 105
#: lines, ZERO hosts or personal values measured, pure Guard capability, and a NEW in-scope module
#: (sites_de_sortie.py) names it, so excluding it would ship a dangling reference.
#: A NEW file added to production/ or runtime/ that is NOT on this list defaults to IN SCOPE —
#: `run()` prints it plainly in the plan so a human sees it before it is ever committed publicly;
#: this module does not try to guess membership from the name.
EXCLUDE_SYSTEM_LIB = frozenset({
    "system/lib/mnemosyne/production/cours.py",
    "system/lib/mnemosyne/production/harnais_de_sabotage.py",
})

EXCLUDE_SYSTEM_SKILLS = frozenset({
    "system/skills/cours/SKILL.md",
    "system/skills/cours/cours_emit.py",
    "system/skills/cours/cours_run.py",
    "system/skills/enqueteur/SKILL.md",
    "system/skills/enqueteur/completude.py",
    "system/skills/enqueteur/emit_completude.py",
    "system/skills/enqueteur/emit_enquete.py",
    "system/skills/enqueteur/enquete.py",
    "system/skills/harnais-de-sabotage/SKILL.md",
    "system/skills/harnais-de-sabotage/harnais-de-sabotage_run.py",
})

EXCLUDE_SYSTEM_OTHER = frozenset({
    "system/logs/README.md",
    "system/state/README.md",
})

#: tests/ mirrors the system/lib/ exclusion (one test suite per excluded module) plus a few tests
#: tied to other excluded things (the egress_prefix guard, the offre_aux_projets script, the stop
#: hook's Jordan-specific behaviour). Same non-derivable-by-pattern caveat as EXCLUDE_SYSTEM_LIB.
EXCLUDE_TESTS = frozenset({
    "tests/orchestration/test_completude.py",
    "tests/orchestration/test_enquete_gate.py",
    "tests/platform/test_stop_hook.py",
    "tests/test_cours.py",
    "tests/test_harnais_de_sabotage.py",
})

#: Makefile targets dropped from the export's copy — Jordan's own cross-session ritual, meaningless
#: without his private state files (system/state/*, docs/PLAN.md, ...).
MAKEFILE_DROPPED_TARGETS = ("bilan", "tick", "reprise", "signaler", "signalements", "signalement-traite")

#: `.claude/` paths dropped from the export: the editor wiring that routes THIS machine's private
#: projects. Not a name to translate -- their SUBSTANCE is a routing table naming a private
#: project, its directory layout (`projects/saas/projectalpha-chat-1..3`) and its state files. Sanitizing
#: them yields either a lie (a dispatcher routing to nothing) or an empty shell that teaches
#: nothing, so they leave the sync entirely. Measured 2026-09-09: none of the four is in the
#: mirror's published HEAD -- this sync would have published them for the FIRST time, and the
#: overreach gate now refuses the commit while they sit in the export's tree.
#: `settings.json` goes with them because it is what WIRES the private hooks: its published
#: version already points at `stop.sh` and is correct, while its source version can only ever
#: reintroduce the private routing. Fail-closed, and it completes a boundary this module had
#: half-drawn -- `EXCLUDE_TESTS` already drops `test_stop_hook.py` as Jordan-specific while shipping
#: the hook it tests. The IDEA worth showing (one blocking decision per turn-chain) survives as
#: prose in the export's own ARCHITECTURE.md, which needs no routing table to be true.
EXCLUDE_CLAUDE = frozenset({
    ".claude/hooks/projectalpha-stop.sh",
    ".claude/hooks/pre-compact.sh",
    ".claude/hooks/stop-dispatch.sh",
    ".claude/settings.json",
})

#: Paths hand-authored once in the export and NEVER touched by this sync (not a mirror of
#: anything in this repo) — listed so tooling can assert it never writes them, and so a human
#: reading this file sees the full boundary in one place.
STATIC_EXPORT_ONLY_PATHS = frozenset({
    "ARCHITECTURE.md", "CONTRIBUTING.md", "LICENSE", "README.md", "CLAUDE.md",
    ".gitattributes", ".gitignore", ".python-version",
    ".githooks/pre-commit", ".githooks/pre-push",
    "knowledge/README.md", "knowledge/raw/.gitkeep", "knowledge/distilled/.gitkeep",
    "projects/README.md",
})

#: ui/ syncs from a DIFFERENT source root — its own sibling git repo, not this repo's tree.
#: Out of scope for `run()`/`is_in_scope()` below; noted here so the boundary stays honest.
UI_SOURCE_PATH = Path("projects/mnemosyne/ui")
UI_EXPORT_RELATIVE_PATH = Path("ui")


def is_in_scope(rel_path: str) -> bool:
    """Pure membership test: is `rel_path` (POSIX, this-repo-root-relative) part of the public
    mirror sync AT ALL? Says nothing about whether it changed or is safe — only "considered"."""
    rel_path = rel_path.replace("\\", "/")

    if rel_path.startswith("docs/"):
        return rel_path in DOCS_ALLOWLIST
    if rel_path.startswith("scripts/"):
        return rel_path not in EXCLUDE_SCRIPTS
    if rel_path.startswith("system/"):
        if rel_path in EXCLUDE_SYSTEM_LIB or rel_path in EXCLUDE_SYSTEM_SKILLS or rel_path in EXCLUDE_SYSTEM_OTHER:
            return False
        # THIS TOOL'S OWN STATE FILE, excluded by DERIVATION from `_MARKER_PATH` and never by a
        # copied string -- a hardcoded path here would keep pointing at the old location the day
        # the marker moves, and the completion check would go quietly back to never reaching zero.
        # (`_MARKER_PATH` is defined further down; module-level names resolve at CALL time, so the
        # order is fine and the single source of truth stays single.)
        # WHY IT MUST BE OUT OF SCOPE AT ALL: it is gitignored in the export, so it can never be
        # "processed" by a sanitization pass -- `uncovered_in_scope_paths()` counted it as an
        # untouched in-scope path FOREVER. Measured 2026-09-09: exactly 1 path was reported, and it
        # was this one. A completion check that can never return zero is a check people learn to
        # ignore, which is worse than not having it.
        if rel_path == _MARKER_PATH.as_posix():
            return False
        if any(rel_path.startswith(f"system/skills/{folder}/") for folder in EXCLUDE_SKILL_FOLDERS):
            return False
        return True
    if rel_path.startswith("tests/"):
        return rel_path not in EXCLUDE_TESTS
    if rel_path == ".claude" or rel_path.startswith(".claude/"):
        return rel_path not in EXCLUDE_CLAUDE
    if rel_path in ("pyproject.toml", "uv.lock", "Makefile"):
        return True
    return False


@dataclass(frozen=True)
class SyncPlan:
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, ...]


def classify_changed_paths(changed_paths: Iterable[str]) -> SyncPlan:
    """Pure: split a raw changed-path list into in-scope (needs sanitizing into the export) and
    out-of-scope (informational only). Order-independent input, sorted-stable output."""
    in_scope: list[str] = []
    out_of_scope: list[str] = []
    for path in changed_paths:
        (in_scope if is_in_scope(path) else out_of_scope).append(path)
    return SyncPlan(in_scope=tuple(sorted(in_scope)), out_of_scope=tuple(sorted(out_of_scope)))


# ---------------------------------------------------------------------------------------------
# Sanitization contract — the ONE prompt a small bounded model call follows per changed file (or
# small batch of small files). Every token here is paid on EVERY call, so it stays terse on
# purpose. Single source: `public_mirror_emit.py` prints this constant verbatim, never a hand
# copy — the anti-drift lesson this repo already learned three times (contract-single-source-emit,
# commit 241e525) applied to a new host: any LLM, not just this session.
# ---------------------------------------------------------------------------------------------

SANITIZE_CHECKLIST = """\
You are producing ONE file for a public, English, open-source mirror of a private project. You
are given the exact original file content and its relative path. Output the complete replacement
content for that same relative path — nothing else, no preamble, no explanation.

1. Translate to English: every comment, docstring, user-facing string, and Markdown paragraph.
   Leave code syntax, identifiers, commands, and URLs unchanged.
2. Remove anything personally identifying: a real person's name (including the project's owner),
   a personal email, a personal filesystem path (e.g. anything under /Users/<name>/...), a phone
   number, or a reference to a private document that does not exist in this public mirror (e.g.
   DISCUSSION.md, CONSTITUTION.md, START_HERE.md, docs/PLAN.md). Replace a real name with a
   neutral term fitting the context ("the operator", "the user") — never invent a fake name.
3. Remove anything that could be a real secret: an API key, token, password, connection string,
   or private key — even if it looks like a placeholder already. If unsure whether a string is a
   real secret or a harmless example, replace it with an obvious placeholder rather than guessing
   it is safe.
4. Remove EMOJI used as prose decoration -- the doctrine markers this repo writes in comments
   and docstrings. Keep the leading bold text, drop the pictograph. Two things you must NOT
   remove: (a) a glyph the plan format PARSES as data, on a line that carries plan markup
   (an item bullet, an `## ARC` heading) -- there it is a value, not decoration, and stripping it
   breaks the parser and its tests; (b) emoji inside a Unicode FIXTURE -- skin-tone modifiers,
   zero-width joiners, family clusters -- they exist to exercise grapheme segmentation, and
   removing them silently voids the test. Measured 2026-09-09: the published mirror carried ZERO
   emoji, and this sync would have introduced 1,576 across 81 files, because the plan engine --
   by far the most emoji-dense code here -- enters the showcase for the first time. The rule was
   written into the PRESENTATION mandate only, never into this per-file contract: it held for the
   4 root documents and was invisible everywhere else.
5. This is translation + redaction, not a rewrite: preserve logic, structure, and behavior
   exactly. Do not refactor, "improve", reformat beyond what the language requires, or add/remove
   functionality. A line with nothing to translate or redact is copied unchanged.
6. Keep a comment's technical content (a warning, a constraint, a WHY) — translate its language,
   don't delete it for being in French.
7. If you cannot safely classify a passage (personal or not, secret-shaped or not), leave it
   marked `TODO(public-mirror): needs human review — <why>` rather than guessing either way.
8. Never restructure code or split a string literal for the sole purpose of changing what an
   automated scanner matches (e.g. breaking "secret-looking-text" into adjacent literals so a
   regex stops matching it, or rewriting a pattern's own denylist so it stops matching real
   content). If verify flags a real, behavior-relevant match, fix it per rules 2-3 above. If you
   believe it is a false positive on an already-harmless example, make that example more
   obviously fake — never change code so it merely LOOKS different to a scanner while behaving
   identically. This applies to this sync tool's own code exactly as much as to any other file.
9. If you change one half of a matched pair — an example value and the output shown for it, a
   test's input and its expected assertion, a fixture value and the code path that reads it —
   re-check the other half still corresponds after your edit. A translation or rename applied to
   only one side of a pair silently breaks it.
10. Never translate by a blind find-and-replace of a word or phrase across a file's raw text.
   Read each occurrence in its own context and rewrite that sentence. A substring match does not
   know the difference between a French word inside a comment and the same letters forming part
   of an unrelated identifier, import, or URL — e.g. replacing "colle" with "adapter" as a bare
   substring would also land inside "collections", silently producing "adapterctions" and
   breaking the import. If a word appears identically many times, that is not license to pattern
   match it — check what actually surrounds each occurrence.
11. If the file is a MANIFEST — a catalogue, registry, or index that names other files, folders,
   or capabilities — filter its entries by the same exclusion the mirror applies to the things
   they name, and add an entry for anything that DOES ship and is missing. A manifest copied
   verbatim is the one file where a correct per-line translation still leaves the result wrong:
   every line is fine, the SET is not. Measured 2026-09-09 on `system/config/skills.toml`, which
   this sync copied unfiltered: it advertised 3 skills whose folders `EXCLUDE_SKILL_FOLDERS`
   deliberately keeps out of the mirror, and stayed silent about 1 that had just entered it.
   A declared-but-absent entry is a promise nothing can keep; an undeclared-but-present one is
   invisible to every fresh agent — and the published mirror had neither defect before this sync.
"""

# ---------------------------------------------------------------------------------------------
# Verification — deterministic, no model. Runs on whatever the sanitization step produced, right
# before any local commit in the export repo. Independent of the step it checks by construction
# (producer != verifier, D75) — it does not know or care which model or which prompt wrote the
# text it is scanning.
# ---------------------------------------------------------------------------------------------

#: This repo owner's own identifying strings — an exact, literal denylist, not a name-shaped
#: heuristic. Extend if a new identifying string is ever adopted (a new email, a renamed home
#: directory, ...); do not try to generalize this into a pattern that guesses names.
#: `\b` is the WRONG boundary here, and it cost a real miss: `_` is a word character in `re`, so
#: `\bprojectalpha\b` does not match `_PROJECTALPHA_HOSTS`, `projectalpha_pos`, or `test_the_real_projectalpha_block` -- exactly
#: the shapes a half-finished rename leaves behind (strings already say "research", identifiers
#: still say the codename). Found 2026-09-09 by a sibling chat auditing from a disjoint scope, on
#: a gate I had written hours earlier and believed sound.
#: `_MOT` treats `_` and digits as separators, so `foo_projectalpha_bar` matches while `projectalphaing` does not.
_MOT = r"(?<![A-Za-z0-9])({})(?![A-Za-z0-9])"

PERSONAL_DENYLIST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(_MOT.format("jordan"), re.IGNORECASE),
    re.compile("examplesurname", re.IGNORECASE),
    re.compile(_MOT.format("examplehandle"), re.IGNORECASE),
    re.compile(_MOT.format("exampleproject"), re.IGNORECASE),
    re.compile(r"/Users/jordan\w*"),
    # The repo owner's OTHER projects. Not personally identifying, and that is exactly why it was
    # missed for three weeks: every other pattern here is a name, this one is a codename, so no
    # rule derived it. The mandate is literal -- "zero reference to my other projects, nothing is
    # transferred" -- and measured 2026-09-09 the export still carried 195 occurrences across 35
    # files, none of which any gate could see. A sibling chat found ONE of them by eye, in a
    # filename; eyes do not scale to 195.
    # Unlike a doc path, this class has no innocent form: a codename in prose IS a reference to a
    # private project, so it BLOCKS rather than merely reporting.
    # NOTE for the sanitization pass: this file ships. The patterns here are published with
    # substituted placeholder names (`jordan`, `examplehandle`, ...), never the real strings -- give any
    # new one the same treatment, or the denylist becomes the leak it exists to prevent.
    re.compile(_MOT.format("projectalpha"), re.IGNORECASE),
    # Found by SWEEPING the class instead of waiting to trip over it: listing every real
    # project/bubble directory on disk and grepping each against the export surfaced a second
    # codename in 5 places. Two other candidates were checked and REJECTED on evidence, which is
    # why they are absent: "course" is the English word behind the `cours` skill, and "trading" is
    # a domain in the committed (public-safe) taxonomy, not a project reference. A denylist grows
    # by measurement, never by suspicion -- a pattern that fires on a common word teaches people
    # to ignore the gate.
    re.compile(_MOT.format("projectbeta"), re.IGNORECASE),
    # A THIRD and a FOURTH codename, 2026-09-09, found by a sibling chat -- and the way they were
    # missed is the lesson, not the names. The sweep that added the second one is described above
    # as "listing every real project/bubble directory on disk": it listed ONE level (`projects/*`),
    # where the folders are generic words (`saas`, `trading`, `personal`). The codenames live one
    # level DOWN (`projects/*/<codename>`), so the very sweep that closed the previous gap had the
    # same blind spot as the fault it closed, one directory deeper. Measured on the export:
    # 29 occurrences in 8 files -- three of them PRODUCTION modules, and three in the showcase's
    # own front door (`docs/FORMAT_PLAN.md`) -- plus 1 for the fourth name. The gate saw none.
    # `uncovered_codename_candidates` below now DERIVES this population recursively so a fifth
    # project cannot depend on someone's eye.
    re.compile(_MOT.format("veskin[_ -]?forge"), re.IGNORECASE),
    re.compile(_MOT.format("pelmar[- ]?tessil"), re.IGNORECASE),
)

#: Directory names under `projects/**` that are ordinary words, never codenames. A denylist that
#: fires on `docs` or `data` teaches people to ignore the gate -- the same reasoning that kept
#: `course` and `trading` out of the patterns above. Kept SHORT and literal on purpose: an entry
#: here is a name the gate will never propose again, so it is a small, reviewable act.
CODENAME_STOPWORDS = frozenset({
    "data", "docs", "scripts", "signaux", "src", "tests", "tmp", "ui", "web",
    "course", "cours", "notes", "archive", "assets", "build", "dist", "logs",
})


def uncovered_codename_candidates(
    dir_names: Iterable[str], text: str, *, own_dir_names: Iterable[str] = ()
) -> list[str]:
    """Pure: which directory names appear in `text` but are matched by NO denylist pattern?

    The discovery half of the identity check, and it exists because the hand-list failed three
    times in a row -- each new codename was found by an eye, never by the gate. The population is
    DERIVED (every directory under `projects/**`, recursively) instead of enumerated, so a project
    created tomorrow is a candidate the day it exists (D163: one source of truth).

    REPORTS, never blocks: at 4+ characters a bare directory name still collides with ordinary
    English, and a gate that is wrong most of the time is a wall people walk around. What blocks is
    the denylist, once a human has read a candidate and added it. Names shorter than 4 characters,
    purely numeric names, and `CODENAME_STOPWORDS` are dropped -- they produce noise, not signal.
    """
    own = {n.lower() for n in own_dir_names}
    out: list[str] = []
    for name in sorted({n for n in dir_names if n}):
        low = name.lower()
        if len(low) < 4 or low.isdigit() or low in CODENAME_STOPWORDS or low.startswith((".", "_")):
            continue
        # The filter that beats any hand-written stopword list: a name the MIRROR ITSELF uses as a
        # directory is an ordinary word of this codebase (`config`, `runtime`, `skills`, `tests`),
        # never a private codename. Derived from the thing being judged, so it cannot go stale --
        # and it is what took this pass from 250 candidates to a readable handful.
        if low in own:
            continue
        if not re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", text, re.IGNORECASE):
            continue
        if any(p.search(name) for p in PERSONAL_DENYLIST_PATTERNS):
            continue
        out.append(name)
    return out

#: References to documents that exist ONLY in the private repo — not personally identifying, but
#: a dangling reference for anyone reading the public mirror (e.g. a test asserting against
#: "CONSTITUTION.md §5", which this mirror never ships). Flagged separately so the finding
#: names the actual problem instead of being lumped in with a name/path leak.
PRIVATE_DOC_REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bDISCUSSION\.md\b"),
    re.compile(r"\bCONSTITUTION\.md\b"),
    re.compile(r"\bSTART_HERE\.md\b"),
)

#: Any `docs/.../*.md` path mentioned in shipped text. The three patterns above name the private
#: ROOT documents (no `docs/` prefix, so no rule derives them); everything under `docs/` is
#: decided by `is_in_scope` instead of by a hand-list, because a hand-list of 3 was measured on
#: 2026-09-09 to catch 33 of 105 references -- it missed 72 references to 23 private documents
#: across 15 shipped files (`docs/PLAN.md` x33, `docs/CONTRAT_UI.md`, `docs/postes/chat-1.md`,
#: `docs/governance/AME.md`, ... and `docs/miroir-public/MANDATS.md`, which THIS chantier's own
#: orchestrator introduced the same evening without noticing). Deriving from `is_in_scope` gives
#: one source of truth (D163): a doc that enters the mirror is never flagged, a doc that does not
#: always is, and neither list can drift from the other because there is only one.
#: FULL PATHS ONLY, never a bare basename: a first attempt matched `README.md` too and reported
#: 130 phantom references to `docs/postes/README.md` -- a text detector counting citations as
#: instances, the failure this module keeps meeting.
_DOC_PATH_MENTION = re.compile(r"(?<![\w/.-])docs/[\w./-]+\.md\b")


#: Files whose JOB is to carry secret-shaped strings: the redaction guard itself and the tests
#: that prove it redacts. A redaction module containing no API-key-shaped string tests nothing, so
#: `guard.redact` will always fire on them and `verify` could never return 0 -- and a gate that can
#: never go green is a gate people learn to bypass, which is worse than no gate.
#:
#: Measured 2026-09-09 before freezing this set: 31 triggering lines across these 7 files, every
#: one a fixture or a docstring quoting one. The only finding that deserved a real investigation
#: was the phone number, because a fixture built on the author's REAL number WOULD be a leak: it
#: ends in `12345678` (8 distinct digits, strictly increasing pairs -- the canonical fake), and a
#: full-repo search INCLUDING the gitignored personal corpus finds it in these test files only.
#:
#: These findings are still PRINTED, never hidden -- they move from blocking to informational.
#: A secret-shaped string in any OTHER file still blocks, which is the whole point: the exemption
#: is per-path and frozen by a witness, so widening it is a deliberate, reviewed act.
SECRET_SHAPED_FIXTURE_PATHS = frozenset({
    "system/lib/mnemosyne/guard/fencing.py",
    "system/lib/mnemosyne/guard/redact.py",
    "system/lib/mnemosyne/tools/invoke.py",
    "tests/platform/test_fencing.py",
    "tests/platform/test_redact.py",
    "tests/retrieval/test_memory_search.py",
    "tests/test_invariants.py",
    # THIS module's own test file: its fixtures carry `API_KEY = "sk-..."` precisely to prove
    # `scan_for_leaks` catches a key. Added a few minutes after the seven above, and the delay is
    # the lesson: the set was frozen against the export's tracked files at a moment when this file
    # had not yet been synced with the very tests being written. A set measured on a population
    # you are concurrently changing is already stale when you freeze it.
    "tests/test_public_mirror.py",
})

#: The derived doc-path pass is REPORTED but does not block, and the measurement says why: of 244
#: private-path occurrences in the export, only about 5 are references that DIRECT a reader
#: somewhere (`voir X`, `cf. X`, a markdown link). The other ~239 are paths merely EXHIBITED as
#: examples -- `.githooks/pre-commit` explains a glob with `docs/plan/arc-c.md`, a path that exists
#: nowhere and is not supposed to. Removing those would make the comments unreadable, which is the
#: opposite of what this mirror is for. As a BLOCKING signal the pass runs at roughly 2% precision,
#: and a gate that is wrong 98% of the time is a wall: people bypass it, or they damage good code
#: to satisfy it. Informational keeps every discovery (this pass is what caught the orchestrator's
#: own `docs/miroir-public/MANDATS.md` leak) while a human does the triage the regex cannot.
#: The three ROOT documents above keep blocking: `CONSTITUTION.md`/`DISCUSSION.md`/`START_HERE.md`
#: are never plausible pattern examples, so their precision is not in question.
_DERIVED_DOC_MARKER = "mentions a doc path this mirror does not ship (may be an illustrative example)"

_PRIVATE_DOC_MARKER = "references a private-only document not shipped in this mirror"

#: The two files that ARE the dangling-reference detector. `PRIVATE_DOC_REFERENCE_PATTERNS` names
#: `CONSTITUTION.md`/`DISCUSSION.md`/`START_HERE.md` in clear, and the test file asserts on those
#: same literals -- so this pass fires on them BY CONSTRUCTION, exactly as `guard.redact` fires on
#: the redaction fixtures above. Same remedy, same shape, same limit.
#:
#: Measured 2026-09-09 by SET DIFF against the published HEAD `ad755e3`, never by count: 15 pairs
#: (file, document) already online, 20 in the export, of which 16 are NEW and 11 published ones
#: have been cleaned away. `15 -> 20` looks like "+5"; it is a near-total substitution with only 4
#: survivors. That diff is why this exemption is TWO paths and not the published baseline: every
#: one of the 15 published pairs is a TEST file, no production file of the online mirror cites
#: these documents, and 9 of the newcomers are production. Freezing the published set would have
#: exempted precisely what must be caught.
#:
#: ONLY for the private-doc class. A `jordan`/codename identity match or a secret-shaped string in
#: these files still BLOCKS -- being allowed to name the documents you exist to detect is not being
#: allowed to contain anything. Attempt #1 of this chantier died for DISARMING the exported copy's
#: denylist; classifying a printed finding is not that, and the exported copy keeps its patterns
#: armed under a self-scan witness.
SELF_REFERENTIAL_DOC_PATHS = frozenset({
    "system/lib/mnemosyne/production/public_mirror.py",
    "tests/test_public_mirror.py",
})

_UNPUBLISHABLE_LINK_MARKER = "a shipped document points at a file that EXISTS here but git will not publish"

_UNTRACKED_MARKER = "file(s) exist in the export but git will NOT publish them -- `git add` them before committing"


def untracked_publishable_files(tracked: Iterable[str], on_disk: Iterable[str]) -> list[str]:
    """Pure: which files are present in the export and NOT yet known to git?

 The widest form of the defect the link pass finds one instance of, and the more dangerous one
 because nothing has to point at a file for its absence to matter. `git push` carries commits,
 and a commit carries only what was `git add`-ed: a file written by a sanitization pass and never
 staged is, from the public reader's side, a file that does not exist.

 The coverage gate cannot see this. It counts a path as PROCESSED when it appears in
 `git status`, and an untracked file appears there -- so `uncovered = 0` and `publishable = 0`
 can hold at the same time. Measured 2026-09-09 on this export: 153 untracked files, among them
 the whole `system/skills/public-mirror/` skill, `production/orchestration.py` and
 `production/lot_emit.py` -- the last two linked from `README.md` and `ARCHITECTURE.md`, the two
 documents a reader opens first. A previous attempt shipped the mirror image of this fault: 48
 files written into the export that no tracked-file check could see.

 Reported as ONE aggregate finding, never 153 lines: a refusal a human cannot read is a refusal
 a human overrides.
 """
    missing = sorted(set(on_disk) - set(tracked))
    if not missing:
        return []
    head = ", ".join(missing[:5])
    more = f", ... (+{len(missing) - 5} more)" if len(missing) > 5 else ""
    return [f"(export): {len(missing)} {_UNTRACKED_MARKER} -> {head}{more}"]

#: Markdown links and backticked paths, the two ways this repo's documents name a file.
_DOC_LINK = re.compile(r"\[[^\]]*\]\(([^)\s#]+)")
_DOC_BACKTICK = re.compile(r"`([\w./-]+\.(?:py|md|toml|sh|json|js|html))`")


def unpublishable_link_targets(
    text: str, *, rel_path: str, tracked: Container[str], on_disk: Container[str]
) -> list[str]:
    """Pure: which paths does this document name that exist HERE but that `git push` will not carry?

 The narrowest useful predicate, and the narrowness is the point. Three states a named path can
 be in, measured 2026-09-09 across the export's tracked markdown:

 * tracked ............................... 0 findings, it publishes
 * ABSENT from disk ...................... 139 -- almost all illustrative examples
 (`docs/plan/arc-c.md` explaining a glob); blocking on these is the 2%-precision wall the
 derived-doc pass already refuses to be
 * present on disk, NOT tracked .......... 6, in `README.md` and `ARCHITECTURE.md`, and every
 one of them is REAL: two production modules written during the sync and never `git add`-ed

 Only the third state blocks. It cannot be a false positive by construction -- the file is right
 there, so the author meant it -- and it is precisely the failure a previous attempt shipped:
 48 new files written into the export, invisible to every tracked-file check, and a reader who
 clones gets a 404 in the two documents opened first.
 The remedy is always `git add <path>`, never editing the link: the link is CORRECT.
 """
    if not rel_path.endswith(".md"):
        return []
    base = PurePosixPath(rel_path).parent
    found: list[str] = []
    for match in list(_DOC_LINK.finditer(text)) + list(_DOC_BACKTICK.finditer(text)):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        cand = target if "/" in target and not target.startswith(".") else str((base / target).as_posix())
        cand = str(PurePosixPath(cand))
        if cand in tracked or cand not in on_disk or cand in found:
            continue
        found.append(cand)
    return [f"{rel_path}: {_UNPUBLISHABLE_LINK_MARKER} -> {c!r} (the fix is `git add`, never cutting the link)"
            for c in found]


_CODENAME_CANDIDATE_MARKER = "a project directory on this machine is named in the mirror and no denylist pattern covers it"

_REDACT_FINDING_MARKER = "guard.redact caught a secret-shaped string"


def is_expected_fixture_finding(finding: str) -> bool:
    """Pure: is this finding a detector firing on its OWN fixtures? Each class carries its own
    frozen path set and NEVER borrows another's: a `guard.redact` hit is expected only under
    `SECRET_SHAPED_FIXTURE_PATHS`, a private-doc reference only under `SELF_REFERENTIAL_DOC_PATHS`.
    The identity denylist has NO exempt set at all, so a `jordan` or codename match always blocks,
    in every file, including these. Being allowed to contain a fake API key -- or to name the
    document you exist to detect -- is not being allowed to contain anything."""
    if _DERIVED_DOC_MARKER in finding or _CODENAME_CANDIDATE_MARKER in finding:
        return True
    path = finding.split(":", 1)[0].strip()
    if _PRIVATE_DOC_MARKER in finding:
        return path in SELF_REFERENTIAL_DOC_PATHS
    if _REDACT_FINDING_MARKER not in finding:
        return False
    return path in SECRET_SHAPED_FIXTURE_PATHS


def partition_findings(findings: Iterable[str]) -> tuple[list[str], list[str]]:
    """Pure: split `scan_for_leaks` output into (blocking, informational), preserving order.
    Informational findings are printed to the human and do NOT prevent the commit."""
    blocking, informational = [], []
    for finding in findings:
        (informational if is_expected_fixture_finding(finding) else blocking).append(finding)
    return blocking, informational


def scan_for_leaks(text: str, *, rel_path: str = "") -> list[str]:
    """Pure, no I/O. Three independent passes: `guard.redact` for secret-SHAPED strings (API keys,
    tokens, private keys, connection strings, ...), a literal denylist for this repo owner's
    identifying strings, and a check for dangling references to private-only documents. None
    substitutes for another — a real secret is not personally identifying, a name is not
    secret-shaped, and a dangling doc reference is neither. Returns human-readable findings; empty
    list = clean."""
    findings: list[str] = []
    redacted = redact_sensitive_text(text, file_read=True)
    if redacted != text:
        findings.append(f"{rel_path}: guard.redact caught a secret-shaped string in this file")
    for pattern in PERSONAL_DENYLIST_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(f"{rel_path}: personal-identity term matched {pattern.pattern!r} -> {match.group(0)!r}")
    for pattern in PRIVATE_DOC_REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(f"{rel_path}: {_PRIVATE_DOC_MARKER} -> {match.group(0)!r}")
    for mention in dict.fromkeys(_DOC_PATH_MENTION.findall(text)):
        if not is_in_scope(mention):
            findings.append(
                f"{rel_path}: {_DERIVED_DOC_MARKER} -> {mention!r}"
            )
    return findings

def verify_export(*, export_root: Path | None = None) -> list[str]:
    """Impure orchestrator: scan every TRACKED-OR-UNTRACKED-BUT-NOT-GITIGNORED text file under
    `export_root` (default: EXPORT_RELATIVE_PATH) with `scan_for_leaks`. `git ls-files --cached
    --others --exclude-standard`, not a raw filesystem walk and not tracked-only: a working tree
    also holds `.venv/`, `.pytest_cache/`, and similar local build junk that embeds this machine's
    own paths (a `.venv/bin/activate` script, for instance) and is never part of what a `git push`
    would actually publish, so a raw walk produces pure noise -- but a BRAND NEW file a
    sanitization pass just wrote is untracked until `git add`, and `git ls-files` alone (no
    `--others`) silently skips it, so content in a file that was never `git add`-ed would sail
    through unscanned. (Found this the hard way: the 2026-08-19 retry's own uncommitted new files
    were never even opened by this function before the fix -- see
    `mnemosyne-public-release-in-progress.md`.) Returns the aggregated findings — empty means the
    export tree is clean."""
    root = export_root or EXPORT_RELATIVE_PATH
    if not root.exists():
        return [f"export root not found: {root}"]
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return [f"{root} is not a git repository (or `git ls-files` failed): {result.stderr.strip()}"]
    # THE TWO POPULATIONS ARE DELIBERATELY DIFFERENT, AND THE ASYMMETRY *IS* THE GATE.
    #   READ  -> `--cached --others --exclude-standard`: everything that will ship after `git add`,
    #            so a brand-new file written by a sanitization pass is opened and scanned.
    #   JUDGE -> `ls-files` alone: what a commit made RIGHT NOW would actually carry.
    # A sibling chat proposed the slogan "a publication gate iterates on the TARGET state, never the
    # current state" -- true for the READ side, and applied to BOTH sides it silences this gate
    # completely. Measured 2026-09-09 by making them one set: 8 dangling links -> 0, and the
    # untracked-files finding -> 0, with every test still green. A file that is present-but-
    # untracked belongs to the future population and NOT to the present one; collapse the two and
    # nothing can ever be reported as missing.
    tracked = set(
        subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True).stdout.split()
    )
    on_disk = set(result.stdout.split())
    findings: list[str] = []
    corpus: list[str] = []
    for rel in sorted(line for line in result.stdout.splitlines() if line):
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_for_leaks(text, rel_path=rel))
        findings.extend(
            unpublishable_link_targets(text, rel_path=rel, tracked=tracked, on_disk=on_disk)
        )
        corpus.append(text)
    # The DISCOVERY pass, run once over the whole export rather than per file: which project
    # directory names on this machine appear in the mirror without any denylist pattern covering
    # them? Three codenames in a row were found by an eye and not by this gate; the population is
    # derived recursively from `projects/**` so the fourth is not.
    own_dirs = [d.name for d in root.rglob("*") if d.is_dir()]
    findings.extend(untracked_publishable_files(tracked, on_disk))
    for name in uncovered_codename_candidates(
        _project_dir_names(), "\n".join(corpus), own_dir_names=own_dirs
    ):
        findings.append(f"(export): {_CODENAME_CANDIDATE_MARKER} -> {name!r}")
    return findings


def _project_dir_names() -> list[str]:
    """Impure: every directory name under `projects/**`, recursively. Empty when the folder is
    absent -- the mirror's own checkout has no `projects/` content (gitignored by design), so this
    discovery pass is a SOURCE-side capability and degrades to silence elsewhere rather than
    pretending it measured something."""
    root = Path("projects")
    if not root.is_dir():
        return []
    names: list[str] = []
    for depth in ("*", "*/*"):
        for path in root.glob(depth):
            if path.is_dir() and str(EXPORT_RELATIVE_PATH) not in str(path):
                names.append(path.name)
    return names


# ---------------------------------------------------------------------------------------------
# Sync-state marker — where's "last synced" recorded. Lives in system/state/ (gitignored runtime
# state, same as this repo's other cross-session state), never in the export. Missing marker means
# first run: every in-scope file is treated as new.
# ---------------------------------------------------------------------------------------------

_MARKER_PATH = Path("system/state/public_mirror_sync.json")


def read_last_synced_commit() -> str | None:
    if not _MARKER_PATH.exists():
        return None
    try:
        data = json.loads(_MARKER_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    sha = data.get("last_synced_source_commit")
    return sha if isinstance(sha, str) and sha else None


def write_last_synced_commit(sha: str) -> None:
    _MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MARKER_PATH.write_text(json.dumps({"last_synced_source_commit": sha}, indent=2) + "\n", encoding="utf-8")


def _run_git(args: list[str]) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


class SyncMarkerUnknownHere(RuntimeError):
    """The recorded sync marker names a commit THIS repository does not have.

    Its own class, not a bare RuntimeError, because the caller must be able to turn it into a
    readable refusal instead of a traceback -- and because it is the FIRST thing that happens to
    anyone who clones the public mirror and runs `make public-mirror-verify`."""


def changed_paths_since(commit: str | None) -> list[str]:
    """Deterministic, no model. `commit=None` (first run) means every tracked path is 'new'.

 REFUSES, READABLY, when `commit` is not a commit of the repository this runs in.
 Measured 2026-09-09 by running the SHIPPED tool inside the SHIPPED mirror, which is the only
 way this class of defect shows itself: the sync marker records a commit of the PRIVATE source
 repo, so `git diff <sha>..HEAD` exits 128 and `subprocess.run(check=True)` raised a raw
 `CalledProcessError` -- a ten-line traceback ending in `returned non-zero exit status 128`,
 naming neither the cause nor the gesture. The flagship tool of the showcase crashed on its
 first run for every reader who cloned it.
 A crash is not fail-closed: fail-closed REFUSES and says WHY. This does both."""
    if commit is None:
        return [line for line in _run_git(["ls-files"]).splitlines() if line]
    connu = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True, text=True
    )
    if connu.returncode != 0:
        raise SyncMarkerUnknownHere(
            f"the recorded sync marker names commit {commit!r}, which this repository does not "
            f"have. That marker belongs to the PRIVATE source repo: this comparison is meaningless "
            f"here and is refused rather than guessed. Delete "
            f"`{_MARKER_PATH}` to treat every tracked path as new, or run this from the source "
            f"repository the marker was written in."
        )
    diff = _run_git(["diff", "--name-only", "--diff-filter=ACMR", f"{commit}..HEAD"])
    return [line for line in diff.splitlines() if line]


# ---------------------------------------------------------------------------------------------
# Completion check — deterministic, no model. Catches SILENT partial coverage: an agent that
# processes only some of the plan's in-scope paths without saying so. Learned the hard way (the
# 2026-08-19 trial: 35 of 413 planned paths touched, self-reported as "clean" because the only
# check at the time was content-quality on whatever WAS touched — see the memory entry
# `mnemosyne-public-release-in-progress.md`). Meant to run at the same point as `verify_export`,
# on the export's working tree BEFORE any commit — the plan is meaningless to compare against an
# already-committed, clean export.
# ---------------------------------------------------------------------------------------------


def parse_git_status_paths(porcelain_output: str) -> set[str]:
    """Pure: extract touched relative paths from `git status --porcelain` (v1 format) output.
    Handles the common `XY path` and rename `XY orig -> new` shapes; does not unescape exotic
    quoted filenames (same simplification level as the rest of this module)."""
    touched: set[str] = set()
    for line in porcelain_output.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        touched.add(path.strip())
    return touched


def paths_not_yet_touched(in_scope: Iterable[str], touched: set[str]) -> list[str]:
    """Pure: which of `in_scope` are absent from `touched`? Order-preserving over `in_scope`."""
    return [path for path in in_scope if path not in touched]


#: Files that live ONLY in the export and have no counterpart in this repo: the mirror's own
#: public-facing documents, written fresh for it and never synced from here (this repo's README /
#: CLAUDE.md are private and must NEVER be copied over). `is_in_scope` correctly says False for
#: them -- they are not part of a source->mirror sync -- but that made the overreach check refuse
#: the very work the plan's arc C mandates: updating them. Measured 2026-09-08, live, on arc C's
#: first delivery: `unexpected_touched_paths()` returned exactly these four and would have blocked
#: the final commit after every fleet had finished. Kept as an explicit, tiny allow-list rather
#: than a loosening of `is_in_scope`: adding a path here must stay a deliberate, reviewable act.
def paths_outside_scope(touched: Iterable[str]) -> list[str]:
    """Pure: which of `touched` are neither `is_in_scope` nor a path this module already declares
    as living OUTSIDE the main sync? Sorted output (unlike `paths_not_yet_touched`, `touched` has
    no meaningful pre-existing order to preserve).

    Two exemptions, both DECLARED ABOVE rather than invented here -- the boundary is stated once
    (D163) and this function reads it:

    * `STATIC_EXPORT_ONLY_PATHS` -- hand-authored in the export, mirroring nothing in this repo;
    * everything under `UI_EXPORT_RELATIVE_PATH` -- synced from a DIFFERENT source root
      (`UI_SOURCE_PATH`, its own sibling repo), so the main sync's scope has no opinion on it.

    Both apply HERE and not in `is_in_scope`, deliberately: making these paths "in scope" would
    put this repo's own private README/CLAUDE.md into the sync plan and copy them into the public
    mirror -- the exact leak this whole module exists to prevent.

    Measured 2026-09-08 against the export's tracked tree: 21 tracked paths are outside
    `is_in_scope`, and 14 + 7 = 21 of them are covered by exactly these two exemptions, with zero
    orphans and zero stale entries. In the same measurement, ZERO denylisted path
    (EXCLUDE_SYSTEM_LIB / EXCLUDE_SYSTEM_SKILLS / EXCLUDE_TESTS / ...) is tracked in the export --
    so neither exemption can shelter one today, and `test_public_mirror.py` freezes that.

    Sterilizing an already-published file cannot leak anything (it is already public); what this
    gate exists to catch is a pass that writes something NEW where nothing belongs, and both
    exemptions leave that bite intact."""
    ui_prefix = f"{UI_EXPORT_RELATIVE_PATH.as_posix()}/"
    return sorted(
        path
        for path in touched
        if not is_in_scope(path)
        and path not in STATIC_EXPORT_ONLY_PATHS
        and not path.startswith(ui_prefix)
    )


def uncovered_in_scope_paths(*, export_root: Path | None = None) -> list[str]:
    """Impure orchestrator (one subprocess call): re-derives the CURRENT plan the same way
    `run()` does, then reports which in-scope paths have no corresponding change in the export's
    working tree. Empty list says nothing about the QUALITY of what was touched (see
    `scan_for_leaks` for content, and D39-6 for the human review quality still requires) — only
    that every in-scope path was touched at all."""
    plan = classify_changed_paths(changed_paths_since(read_last_synced_commit()))
    root = export_root or EXPORT_RELATIVE_PATH
    if not root.exists():
        return list(plan.in_scope)
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return list(plan.in_scope)
    touched = parse_git_status_paths(result.stdout)
    return paths_not_yet_touched(plan.in_scope, touched)


def unexpected_touched_paths(*, export_root: Path | None = None) -> list[str]:
    """Impure orchestrator (one subprocess call): the MIRROR IMAGE of
    `uncovered_in_scope_paths` -- which touched paths in the export's working tree are OUTSIDE
    the sync's scope entirely (`is_in_scope` is False)? Catches a sanitization pass that swept up
    denylisted files -- e.g. by processing a whole directory instead of the plan's exact path
    list -- which `verify_export` alone cannot: a private governance module naming no secret and
    no personal string is still a real privacy defect, and content scanning has nothing to match
    on. Found the hard way (2026-08-19 retry #2): 48 denylisted files, ~7,850 lines of untouched
    French internal-governance prose, written straight into the export -- zero content-scanner
    hits, completely absent from the executing agent's own final report, caught only by comparing
    the touched-path set against `is_in_scope` directly. Empty list = every touched path belongs
    in the sync at all (says nothing about whether its CONTENT is safe -- see `scan_for_leaks`)."""
    root = export_root or EXPORT_RELATIVE_PATH
    if not root.exists():
        return []
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    touched = parse_git_status_paths(result.stdout)
    return paths_outside_scope(touched)


def export_import_smoke_test(*, export_root: Path | None = None, timeout: int = 120) -> list[str]:
    """Impure orchestrator: does `import mnemosyne` succeed against the export's CURRENT working
    tree? Catches code-breaking corruption that neither `scan_for_leaks` (content-shape only) nor
    the coverage/scope checks (path bookkeeping only) can see. Found the hard way (2026-08-19
    retry #2): a translation pass did what looks like a blind substring replace of the French word
    "colle" (glue) -> "adapter" and it silently also matched inside the unrelated stdlib import
    `collections.abc`, producing `adapterctions.abc` -- syntactically valid Python (so nothing
    catches it at parse time), but it broke `import mnemosyne` outright and, with it, ALL 78 of
    the export's own test files at collection. Not a substitute for actually running the test
    suite (still an open TODO -- this only proves the package imports, not that it behaves
    correctly) but it is nearly free and would have caught this exact defect deterministically.
    Reuses THIS repo's already-resolved environment, pointed at the export's own `system/lib` via
    PYTHONPATH, rather than resolving a separate venv inside the export. Returns a one-item
    finding on failure (its last stderr line), empty list on success."""
    root = export_root or EXPORT_RELATIVE_PATH
    lib_dir = root / "system" / "lib"
    if not lib_dir.exists():
        return [f"{lib_dir} not found -- cannot run the import smoke test"]
    env = {**os.environ, "PYTHONPATH": str(lib_dir)}
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-c", "import mnemosyne"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [f"`import mnemosyne` against the export timed out after {timeout}s"]
    if result.returncode != 0:
        stderr_lines = [line for line in result.stderr.strip().splitlines() if line]
        last_line = stderr_lines[-1] if stderr_lines else "(no stderr)"
        return [f"`import mnemosyne` fails against the export's current working tree: {last_line}"]
    return []



def purge_bytecode_caches(root: Path) -> int:
    """Impure: delete every `__pycache__` under `root`, skipping `.venv`. Returns how many were
    removed -- a COUNT and not None, so a caller can tell "purged nothing" from "did not run".

    WHY THIS GATE PURGES AND THE ORDINARY DEVELOPER DOES NOT: this export is imported under two
    different `PYTHONPATH` roots in the same working tree -- the private library when the suite is
    run from the source repo, the export's own library when it is run the way a stranger would.
    Bytecode written under one arrangement is what the next process finds. `-p no:cacheprovider`
    already handles pytest's OWN cache; it does nothing about CPython's. Measured in this project
    more than once: a suite that had to be re-run after a cache purge to give its real verdict.
    The cost is milliseconds; the thing it protects is the LAST gate before a publication, whose
    only job is to answer "does this behave". A false green there is paid for in public.
    `.venv` is skipped deliberately: it is thousands of directories of third-party bytecode that
    no arrangement of this repo can poison, and walking it would turn milliseconds into seconds."""
    retires = 0
    for cache in root.rglob("__pycache__"):
        if ".venv" in cache.parts or not cache.is_dir():
            continue
        shutil.rmtree(cache, ignore_errors=True)
        retires += 1
    return retires


#: The failures this export is EXPECTED to carry, and the reason each one SURVIVES the corpus.
#: Frozen as a SET, never as a count: a NEW failure and a DISAPPEARED one must both block, because
#: a test that stops failing may simply have been renamed -- which is exactly what happened on
#: 2026-09-09, when a rename pass made four ids vanish and four appear with no change in substance.
#:
#: WHY THIS IS NOT "requiring zero". Requiring a green suite was UNREACHABLE here: 124 of the
#: export's checks measure the operator's own living corpus, which this mirror deliberately does
#: not ship, and they are skipped by name in the export's `tests/conftest.py`. The three below
#: fail on BOTH sides -- they survive the corpus, so they are defects, and they are declared here
#: rather than skipped. An unreachable stop condition is a check people learn to ignore.
EXPECTED_EXPORT_FAILURES: Final[frozenset[str]] = frozenset(
    {
        # Filed as a report on 2026-09-09: the local `.venv` carries an editable install, so
        # `import mnemosyne` succeeds whatever PYTHONPATH says, and these two fail-closed witnesses
        # no longer bite. The defect is in the harness, not in the export -- and it reproduces in
        # the source repository, which is why it is declared instead of hidden.
        "tests/orchestration/test_plan_gate_emit.py"
        "::test_FAIL_CLOSED_gagne_quand_racine_CASSEE_ET_aucun_plan_a_la_fois",
        "tests/orchestration/test_plan_gate_emit.py"
        "::test_FAIL_CLOSED_un_PYTHONPATH_casse_BLOQUE_le_commit",
        # Pre-existing in the source too, verified back to back on the isolated test: a field is
        # declared before its canonical declaration in 27 occurrences over 17 paths, but only ONE
        # distinct filename -- the rest are clones. Real defect, open, not this export's doing.
        "tests/orchestration/test_plan_format.py"
        "::test_NO_real_item_declares_a_field_BEFORE_its_canonical_declaration",
    }
)


def export_test_suite(
    *,
    export_root: Path | None = None,
    timeout: int = 900,
    expected_failures: frozenset[str] | None = None,
) -> list[str]:
    """Impure orchestrator: does the export's OWN test suite pass against its current working
    tree? The fifth and last gate, and the one deliberately deferred through both hardening
    rounds of 2026-08-19 -- reinstated here because the evidence for it is no longer
    speculative. `export_import_smoke_test` proves the package IMPORTS; it says nothing about
    whether it BEHAVES. Retry #2 broke all 78 of the export's test files with a single corrupted
    line, and retry #1 silently voided two security assertions in `test_redact.py` by rewriting
    their example values -- neither is visible to a leak scan, a path-bookkeeping check, or an
    import. The cost objection is measured and dead: the export's suite runs in 75s
    (2429 passed, 2026-09-08), against a 120s import smoke test that was already accepted.

    Reuses THIS repo's already-resolved environment with PYTHONPATH pointed at the export's own
    `system/lib`, exactly like the import smoke test -- no separate venv resolution inside the
    export. `-p no:cacheprovider` keeps the export's working tree free of a `.pytest_cache` that
    `unexpected_touched_paths` would then (correctly) flag as an out-of-scope touched path.
    Returns a one-item finding carrying pytest's own summary line on failure, empty on success."""
    root = export_root or EXPORT_RELATIVE_PATH
    # A PARAMETER, defaulted -- not a module constant read straight from the body. A fixture export
    # carries none of the real export's declared failures, so a body-read constant would make every
    # synthetic witness report them as "disappeared" and there would be no way to test the passing
    # case at all. The default is what production uses; the parameter is what makes it measurable.
    attendues = EXPECTED_EXPORT_FAILURES if expected_failures is None else expected_failures
    tests_dir = root / "tests"
    lib_dir = root / "system" / "lib"
    if not tests_dir.exists():
        return [f"{tests_dir} not found -- cannot run the export's own test suite"]
    purge_bytecode_caches(root)
    env = {**os.environ, "PYTHONPATH": str(lib_dir)}
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", "pytest", str(tests_dir), "-q", "-p", "no:cacheprovider"],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [f"the export's own test suite timed out after {timeout}s"]
    lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    summary = lines[-1] if lines else "(no pytest output)"
    if any(line.startswith("ERROR") for line in lines):
        erreurs = [line for line in lines if line.startswith("ERROR")][:5]
        return [
            "the export's own test suite raised a COLLECTION ERROR, so its failing set was never "
            f"measured: {summary} | " + " ; ".join(erreurs)
        ]
    observees = {
        line.removeprefix("FAILED ").split(" - ", 1)[0].removeprefix(f"{root.as_posix()}/")
        for line in lines
        if line.startswith("FAILED ")
    }
    neufs = sorted(observees - attendues)
    disparues = sorted(attendues - observees)
    if not neufs and not disparues:
        return []
    finding = f"the export's own test suite DIVERGED from its declared failing set: {summary}"
    if neufs:
        finding += " | NEW failure(s), NOT declared: " + " ; ".join(neufs[:5])
    if disparues:
        finding += (
            " | declared failure(s) that no longer fail -- a test that stops failing may have been "
            "renamed or silently weakened, so say which and why: " + " ; ".join(disparues[:5])
        )
    return [finding]

def run() -> None:
    """`make public-mirror` — print the deterministic sync plan. Writes nothing: the marker only
    advances via `mark_synced()`, which the emitted recipe calls only after sanitizing, verifying,
    and committing locally in the export repo."""
    last = read_last_synced_commit()
    changed = changed_paths_since(last)
    plan = classify_changed_paths(changed)
    head = _run_git(["rev-parse", "HEAD"]).strip()

    print(f"public-mirror plan — source HEAD {head}")
    print(f"last synced commit : {last or '(none — first run, full scope)'}")
    print(f"changed paths seen : {len(changed)}")
    print()
    print(f"IN SCOPE ({len(plan.in_scope)}) — sanitize each into {EXPORT_RELATIVE_PATH}/<same path>:")
    for path in plan.in_scope:
        print(f"  + {path}")
    if plan.out_of_scope:
        print()
        print(f"out of scope, ignored ({len(plan.out_of_scope)}):")
        for path in plan.out_of_scope:
            print(f"  . {path}")
    print()
    print("Nothing written. After sanitizing (SANITIZE_CHECKLIST) + `make public-mirror-verify` +")
    print(f"a local commit in {EXPORT_RELATIVE_PATH}, record the sync:")
    print('  PYTHONPATH=system/lib uv run python -c "from mnemosyne.production.public_mirror import mark_synced; mark_synced()"')


def mark_synced(commit: str | None = None) -> None:
    """Record that the export is caught up to `commit` (default: current source HEAD). Call this
    ONLY after the sanitized content is verified clean and committed locally in the export repo —
    never before, or the next plan will silently skip files that were never actually synced."""
    sha = commit or _run_git(["rev-parse", "HEAD"]).strip()
    write_last_synced_commit(sha)
    print(f"recorded: last_synced_source_commit = {sha}")
