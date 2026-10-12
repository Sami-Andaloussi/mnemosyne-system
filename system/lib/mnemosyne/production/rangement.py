"""rangement (item 7 / D149 / D92 / D74) — deterministic detection of CLEAR repo cruft + a
non-destructive quarantine plan, and the frontier contract for the JUDGMENT pass on top.

Why this skill exists: the repo accumulates derived cruft (OS ``.DS_Store``, stale manifest backups,
old run logs, misplaced pilot outputs) that makes it un-navigable (``repo-navigability``). Tidying it is
exactly the kind of repetitive, automatable chore the autonomy nerve should PROPOSE (item 3), and its
frontier form is the operator's archetype for the multi-version doctrine (item 5): the code home holds
the DETERMINISTIC core, and the FRONTIER version is the emitted contract — a prompt, no bespoke ``.py``.

The split (anatomy: deterministic = CODE, judgment = agent):

  * CODE (here) finds only CLEARLY-classified cruft (``classify`` is deny-by-default: an unrecognized
    file is NOT a candidate, never guessed), plans a REVERSIBLE move into the quarantine
    (``knowledge/_quarantine/rangement-<stamp>/`` preserving each file's relative path, with a manifest),
    and refuses to touch a protected path (:func:`no_protected_path_touched`, a fail-closed guard
    exercised by a test — never a prompt asking a model to "be careful").
  * FRONTIER (via :func:`build_rangement_contract`, ``make rangement-emit``) does the judgment the code
    cannot: sanity-check the plan, and SCAN for the less-obvious mess a classifier can't know (a stale
    doc, a duplicate, an orphaned output) and PROPOSE it to the operator — never move it.

Two invariants the whole skill upholds, by construction not by trust (D100):

  * NON-DESTRUCTIVE (D74 / invariant 2): this skill only ever MOVES a file into the quarantine. It never
    deletes. Emptying the quarantine (a real deletion of the operator's bytes) is THEIR gesture, never
    this skill's.
  * PROPOSE, NEVER IMPOSE (D92): the deterministic pass acts only on cruft it can name with certainty;
    everything ambiguous is left for the frontier to PROPOSE and for the operator to decide.

Code & docstrings English (D117).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

#: The quarantine lives UNDER the (gitignored, personal) knowledge bubble — reusing the convention that
#: already exists on disk (``knowledge/_quarantine``). One dated sub-folder per pass keeps runs distinct
#: and every move trivially reversible (``mv`` back per the pass manifest). Never created by a dry run.
QUARANTINE_ROOT = "knowledge/_quarantine"

#: Directories the rangement pass NEVER descends into or touches — deny-by-default at the tree grain.
#: Live state (``system/state`` — the human-layer journal, gitignored D82; ``.snapshotstore`` — replay
#: history), nested SEPARATE git repos (``projects/*`` — each nested project owns its own history), the
#: sources of truth (``knowledge/raw`` + ``knowledge/distilled`` + ``knowledge/golden``) and derived
#: memory (``maps`` / ``proposals``), the quarantine itself, and toolchain/VCS/cache trees. A file under
#: any of these is out of scope, whatever its name — the classifier is never even consulted for it.
NEVER_TOUCH_PREFIXES: frozenset[str] = frozenset(
    {
        "system/state",
        "projects",
        "knowledge/raw",
        "knowledge/distilled",
        "knowledge/golden",
        "knowledge/maps",
        "knowledge/proposals",
        "knowledge/_quarantine",
    }
)

#: Directory NAMES that are never-touch wherever they appear as a path component (VCS, virtualenv,
#: dependency + tool caches, on-disk replay store).
NEVER_TOUCH_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".snapshotstore",
    }
)

#: The ONE live library manifest — protected explicitly so only its BACKUPS are ever quarantined.
_LIVE_MANIFEST = "library_manifest.json"


class CruftClass(str, Enum):
    """A file the deterministic pass can name as clear cruft with certainty (never a guess)."""

    OS_CRUFT = "os_cruft"  # .DS_Store and the like — OS metadata, always safe to quarantine
    STALE_MANIFEST_BACKUP = (
        "stale_manifest_backup"  # library_manifest.*.json / .bak (not the live one)
    )
    STALE_LOG = "stale_log"  # a *.log run artifact (live logs are protected by NEVER_TOUCH_*)
    MISPLACED_YOUTUBE = "misplaced_youtube"  # a *.youtube.md pilot output stranded at the repo root
    STALE_TODO = "stale_todo"  # a POST_RUN_TODO.md left behind by a past run


#: Human-readable reason per class — printed in the plan and the contract so the choice is legible.
_CLASS_REASON: dict[CruftClass, str] = {
    CruftClass.OS_CRUFT: "OS metadata file (Finder), never source",
    CruftClass.STALE_MANIFEST_BACKUP: "timestamped backup of the live library manifest — the store rebuilds from the live one",
    CruftClass.STALE_LOG: "a run-log artifact, not a source of truth",
    CruftClass.MISPLACED_YOUTUBE: "a youtube-pilot output stranded at the repo root (not ingested here)",
    CruftClass.STALE_TODO: "a post-run TODO left behind by a past run",
}


@dataclass(frozen=True, slots=True)
class Candidate:
    """One clearly-classified cruft file, by repo-relative path. ``reason`` echoes its class rationale."""

    path: str
    cls: CruftClass
    reason: str


@dataclass(frozen=True, slots=True)
class Move:
    """One planned quarantine move: ``src`` (repo-relative) → ``dst`` (under :data:`QUARANTINE_ROOT`)."""

    src: str
    dst: str
    cls: CruftClass


def _under_prefix(rel_path: str, prefix: str) -> bool:
    """Whether ``rel_path`` is ``prefix`` itself or lies under it (path-segment exact, not substring)."""
    return rel_path == prefix or rel_path.startswith(prefix + "/")


def in_scope(rel_path: str) -> bool:
    """Whether the rangement pass may consider ``rel_path`` at all (deny-by-default at the tree grain).

    Fail-closed: a path under any :data:`NEVER_TOUCH_PREFIXES`, or containing any
    :data:`NEVER_TOUCH_DIR_NAMES` component, is OUT of scope whatever its name."""
    parts = rel_path.split("/")
    if any(part in NEVER_TOUCH_DIR_NAMES for part in parts):
        return False
    return not any(_under_prefix(rel_path, prefix) for prefix in NEVER_TOUCH_PREFIXES)


def classify(rel_path: str) -> CruftClass | None:
    """Name ``rel_path`` as a :class:`CruftClass`, or ``None`` if it is not CLEAR cruft (deny-by-default).

    Only files this returns non-``None`` for are ever acted on; an unrecognized file is left untouched
    for the frontier to PROPOSE and the operator to judge — the classifier never guesses. Assumes
    ``rel_path`` is already :func:`in_scope` (the caller filters first)."""
    base = os.path.basename(rel_path)
    parent = os.path.dirname(rel_path)
    if base == ".DS_Store":
        return CruftClass.OS_CRUFT
    # A library-manifest BACKUP — any `library_manifest.*` that is not the ONE live file.
    if base.startswith("library_manifest.") and base != _LIVE_MANIFEST:
        return CruftClass.STALE_MANIFEST_BACKUP
    if base == "POST_RUN_TODO.md":
        return CruftClass.STALE_TODO
    # A youtube-pilot output stranded at the REPO ROOT (parent == "" for a top-level file); a *.youtube.md
    # nested somewhere intentional is left alone.
    if base.endswith(".youtube.md") and parent == "":
        return CruftClass.MISPLACED_YOUTUBE
    if base.endswith(".log"):
        return CruftClass.STALE_LOG
    return None


def scan(root: str) -> tuple[Candidate, ...]:
    """Walk ``root`` and return every CLEARLY-classified cruft :class:`Candidate`, sorted by path.

    Never descends into a :data:`NEVER_TOUCH_DIR_NAMES` directory (pruned from the walk) and skips any
    path not :func:`in_scope`; deterministic order (sorted) so the plan and its emitted contract are
    stable across runs."""
    found: list[Candidate] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune never-touch directories from the descent (both by-name and by-prefix), so a huge
        # ``.venv`` / ``knowledge/raw`` is never even walked.
        dirnames[:] = [
            d
            for d in dirnames
            if d not in NEVER_TOUCH_DIR_NAMES
            and in_scope(os.path.relpath(os.path.join(dirpath, d), root))
        ]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            if not in_scope(rel):
                continue
            cls = classify(rel)
            if cls is not None:
                found.append(Candidate(path=rel, cls=cls, reason=_CLASS_REASON[cls]))
    return tuple(sorted(found, key=lambda c: c.path))


def clear_cruft_count(root: str) -> int:
    """How many CLEARLY-classified cruft files the deterministic scan finds under ``root`` right now.

    The META count for the autonomy nerve (:class:`~mnemosyne.production.proposer.RepoTidyReview`, item 3):
    the DEPTH of clear cruft, never a path (invariant 22 / D66). A thin ``len(scan(...))`` — the SAME
    deny-by-default, ``NEVER_TOUCH``-guarded scan the plan itself uses (ONE code home, no second walk to
    drift, ``contract-single-source-emit``). Pure and robust: :func:`scan` never raises on a missing tree,
    so this returns 0 for an absent or already-tidy root (silence, never a false nudge)."""
    return len(scan(root))


def pass_stamp(now: datetime | None = None) -> str:
    """A UTC stamp naming one rangement pass's quarantine sub-folder (``rangement-<stamp>``)."""
    moment = now if now is not None else datetime.now(timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def plan_quarantine(candidates: tuple[Candidate, ...], stamp: str) -> tuple[Move, ...]:
    """Plan a REVERSIBLE move for each candidate into ``knowledge/_quarantine/rangement-<stamp>/`` with
    its repo-relative path PRESERVED (so two ``.DS_Store`` from different dirs never collide, and a
    restore is a plain ``mv`` back). Pure — plans, never touches disk."""
    dest_root = f"{QUARANTINE_ROOT}/rangement-{stamp}"
    return tuple(Move(src=c.path, dst=f"{dest_root}/{c.path}", cls=c.cls) for c in candidates)


def no_protected_path_touched(moves: tuple[Move, ...]) -> bool:
    """VERIFY-IN-CODE (fail-closed): every move's SOURCE is in scope, and every DESTINATION is inside the
    quarantine — so a plan can never move a protected/truth file, nor land anything outside the
    quarantine. Re-checked before any disk mutation, trusting no producer (the plan builder included)."""
    for mv in moves:
        if not in_scope(mv.src):
            return False
        if classify(mv.src) is None:  # a move whose source is not itself clear cruft — refuse
            return False
        if not _under_prefix(mv.dst, QUARANTINE_ROOT):
            return False
    return True


def plan_is_reversible(moves: tuple[Move, ...]) -> bool:
    """Whether the plan is losslessly reversible: every destination distinct (no move clobbers another),
    and no destination coincides with a source (no move feeds another). Empty plan is vacuously true."""
    dsts = [mv.dst for mv in moves]
    if len(set(dsts)) != len(dsts):
        return False
    srcs = {mv.src for mv in moves}
    return not (srcs & set(dsts))


#: The rangement rules, ONE code home — pinned by the emit lock-test and restated by no SKILL.md copy.
RANGEMENT_RULES: tuple[str, ...] = (
    "NON-DESTRUCTIVE (D74): only ever MOVE a file into the quarantine; NEVER delete. Emptying the "
    "quarantine is the operator's gesture, never yours.",
    "PROPOSE, NEVER IMPOSE (D92): act only on cruft named with certainty; PROPOSE everything ambiguous "
    "to the operator and let them decide.",
    "NEVER TOUCH live state, sources of truth, derived memory, nested project repos, or VCS/toolchain "
    "trees (the code's NEVER_TOUCH_* lists) — whatever a file is named.",
)


def build_rangement_contract(candidates: tuple[Candidate, ...], root: str, stamp: str) -> str:
    """EMIT the exact rangement contract a FRONTIER host applies (``make rangement-emit``) — the skill's
    frontier VERSION is this prompt, replayed from the code's real ``scan`` output, never hand-copied.

    It hands the frontier the deterministic plan (the clear-cruft worklist + where each file goes) and
    asks for the JUDGMENT the code cannot do: sanity-check the plan, then scan for the less-obvious mess
    and PROPOSE it — never move it. The hard rules come from :data:`RANGEMENT_RULES` (one source)."""
    moves = plan_quarantine(candidates, stamp)
    lines: list[str] = [
        "CONTRACT rangement (EMITTED from the code, mnemosyne.production.rangement — never hand-copied):",
        "=" * 78,
        "",
        f"Repo root: {root}",
        "",
        "YOU ARE the rangement pass of Mnemosyne, on the JUDGMENT side. The code has already detected",
        "the CLEAR cruft and planned a REVERSIBLE quarantine (below). Your job is what the code cannot",
        "do: (1) sanity-check this plan (nothing surprising), (2) SCAN for the less-obvious mess the",
        "classifier cannot know (a stale doc, a duplicate, an orphaned output) and",
        "PROPOSE it to the operator — never move it yourself.",
        "",
        "HARD RULES (single source: RANGEMENT_RULES):",
    ]
    lines += [f"  - {rule}" for rule in RANGEMENT_RULES]
    lines += ["", f"DETERMINISTIC PLAN — {len(moves)} clear file(s) to quarantine:"]
    if not moves:
        lines.append("  (no clear cruft detected — the repo is clean at the deterministic grain)")
    else:
        for mv in moves:
            lines.append(f"  [{mv.cls.value}] {mv.src}")
            lines.append(f"      -> {mv.dst}")
    lines += [
        "",
        "Apply this plan with `make rangement` (the code moves the files + writes a reversible",
        "manifest), THEN do your judgment pass and file your proposals for the operator (propose,",
        "never impose).",
    ]
    return "\n".join(lines) + "\n"
