"""plan-corbeille — move ONE H1-retired item out of a living arc, into the permanent trash beside it.

The input/output half of :mod:`mnemosyne.production.plan_corbeille`, which holds every decision as a
pure function. Same four side effects as its sibling :mod:`plan_archiver_run`, and nothing else: read
the arc, print, and — only under ``--apply`` — write.

**Dry-run by default** (D92 — propose, never impose). **Nothing is written until the round-trip is
proven**, exactly like ``plan-archiver``: if corbeille-text + remaining arc do not give the original
file back character for character, the command exits non-zero and no file is touched.

**Order of writes under ``--apply``: corbeille FIRST, arc LAST** — same reasoning as
``plan_archiver_run.apply_planning``: a failure between the two must duplicate the item, never lose
it (invariant 2).

Run::

    make plan-corbeille PLAN="projects/example-project/plan/07-example-arc.md" ITEM=H3 REMPLACE="nothing for now"
    make plan-corbeille PLAN="..." ITEM=H3 REMPLACE="..." APPLY=1        # writes

Brick-free, no model, no network. Code & docstrings English (D117); this repo's own convention
(D33) prints in French — this public-mirror copy is translated into English throughout."""

from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from ..production.plan_corbeille import (
    RETIRES_DIRNAME,
    CorbeillePlanning,
    RetraitCorbeilleError,
    plan_corbeille,
    verify_readability,
    verify_roundtrip,
)
from .plan_archiver_run import plan_site

#: Repo root from this module (``system/lib/mnemosyne/runtime/plan_corbeille_run.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]

#: What to DO about each refusal — attached to the reason, same discipline as
#: ``plan_archiver_run._GESTE``: a refusal that names a problem without naming a gesture turns a
#: tool into an obstacle.
_GESTE: dict[str, str] = {
    "item_absent": (
        "The move: check the identifier. The plan may have changed since the H1 approval — "
        "re-read `make item-retirer queue` to see what was actually applied."
    ),
    "pas_retire_par_h1": (
        "The move: go through `make item-retirer` first (H1) — ask, get it reviewed, get the "
        "operator's GO LIVE, then apply. This command does not retire anything itself, it only "
        "moves what H1 has already retired."
    ),
    "commentaire_illisible": (
        "The move: look at the line by hand. A comment that starts like an H1 retirement but does "
        "not parse is more likely a manual edit than a real retirement — fix or remove that "
        "comment before running again."
    ),
    "remplace_vide": (
        "The move: give REMPLACE=\"...\" — even « NONE » is a valid, free answer, but the field "
        "must be written, never guessed."
    ),
    "remplace_illisible": (
        "The move: shorten or clean up the REMPLACE text (a control character, or too long)."
    ),
    "corbeille_existe": (
        "The move: none. A file with this name is already in the trash — we never overwrite "
        "(inv. 2). If this really is a second retirement of the same identifier, it is a "
        "duplicate to review by hand."
    ),
}


def _bytes_of(path: Path) -> str:
    """A file's EXACT bytes — ``newline=""``, same reason as ``plan_archiver_run._bytes_of``: the
    byte-for-byte guarantee must not become a claim about Python's newline translation layer."""
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def retires_root_of(plan_path: Path) -> tuple[Path, str]:
    """Where this arc's corbeille lives, and the relative link the pointer left in it should use.

    Reuses :func:`~.plan_archiver_run.plan_site` WHOLE rather than re-deriving "which door owns
    this file" a second time — the exact class of drift this repo has already paid for once
    (D170). ``archive_root`` and the corbeille sit BESIDE the same door, so the corbeille's root is
    archive_root's own parent with :data:`~.plan_corbeille.RETIRES_DIRNAME` appended, and the two
    directories' relative links from the arc differ only in that last component.
    """
    site = plan_site(plan_path)
    base = site.archive_root.parent
    retires_root = base / RETIRES_DIRNAME
    link_dir = Path(os.path.relpath(retires_root, plan_path.parent)).as_posix()
    return retires_root, link_dir


def render(planning: CorbeillePlanning, *, corbeille_dir: str, applied: bool) -> str:
    """The report the operator reads — what would move (or why it is refused), and whether it
    happened."""
    lines = [
        "# Mnémosyne · retirement to trash (H3)",
        "",
        f"`{planning.source}` — item `{planning.move.ident if planning.move else '?'}`.",
        "",
    ]
    if planning.blocked:
        refus = planning.refusal
        assert refus is not None  # noqa: S101 -- narrows for the type checker; `blocked` already confirmed it
        lines += [
            f"## REFUSED — {refus.detail}",
            "",
            f"      {refus.label}",
            f"      {_GESTE[refus.reason]}",
            "",
        ]
        return "\n".join(lines).rstrip() + "\n"

    move = planning.move
    assert move is not None  # noqa: S101 -- `not planning.blocked` guarantees this
    verbe = "MOVED" if applied else "What would move"
    lines += [
        f"## {verbe} — {move.ident} · {move.title}",
        "",
        f"      reason: {move.trouve.motif}",
        f"      cost  : {move.trouve.cout}",
        f"      replaces: {move.remplace}",
        f"      → `{corbeille_dir}/{move.filename}`",
        f"      the plan keeps: `{move.pointer}`",
        "",
    ]
    if applied:
        lines += [
            "**APPLIED** — file written to the trash, arc rewritten.",
            "",
            "Reconstruction verified **before** any write: trash copy + remaining arc give back "
            "the original arc, character for character.",
            "",
        ]
    else:
        lines += [
            "**DRY RUN — nothing was written.** The byte-for-byte reconstruction has already been "
            "verified against what precedes.",
            "",
            "To apply: `make plan-corbeille ... APPLY=1`",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def apply_planning(planning: CorbeillePlanning, *, plan_path: Path, retires_root: Path) -> None:
    """Write the corbeille file, then the arc. Only after BOTH verifiers have already passed.

    Same ordering as ``plan_archiver_run.apply_planning``, same reason: the corbeille copy is
    proven byte-identical to the item BEFORE the first write, so releasing the arc's own copy is
    the second half of a move, never a deletion of anything — every crash between the two writes
    duplicates the item, and none loses it (invariant 2).

    AUDIT DELEGATED ON 2026-08-16 (D75): this function verifies NOTHING itself — neither that
    ``planning`` really comes from :func:`~.plan_corbeille.plan_corbeille`, nor that
    :func:`~.plan_corbeille.verify_roundtrip`/:func:`~.plan_corbeille.verify_readability` actually
    ran, nor that ``move.trouve`` carries a non-empty reason and cost. The auditor built a
    ``CorbeillePlanning`` by hand (reason="", cost="") and had it written directly, completely
    bypassing ``plan_corbeille()`` — a GHOST item, never seen by H1, written without raising.
    **This is NOT reachable through ANY `make` target nor through :func:`main` below** — both
    verifiers run BEFORE any call to this function, without exception — but this function itself
    is not the proof of that: ``main()`` is. *A module that only writes through this function is
    structurally level-2 only by the will of its one caller, never by a guarantee this function
    carries itself* — the same finding ``plan_archiver_run.apply_planning`` already carries,
    identically, and not specific to H3.
    **Never call this function directly outside this module.** It is a writing detail of
    :func:`main`, not a safe entry point.
    """
    assert planning.move is not None  # noqa: S101 -- caller already checked `blocked`
    move = planning.move
    retires_root.mkdir(parents=True, exist_ok=True)
    with (retires_root / move.filename).open("x", encoding="utf-8", newline="") as handle:
        handle.write(planning.corbeille_text())
    tmp = plan_path.with_name(f"{plan_path.name}.tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(planning.remaining)
    tmp.replace(plan_path)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI side effect
    """Plan, prove, report — and write only under ``--apply``. Non-zero on refusal or a failed proof."""
    parser = argparse.ArgumentParser(
        description="Move ONE item already retired by H1 into the permanent trash (H3)."
    )
    parser.add_argument("plan", help="path to the arc containing the item")
    parser.add_argument("--item", required=True, help="the item's identifier, e.g. H3")
    parser.add_argument(
        "--remplace", required=True, help='what replaces this item — "NONE" is a valid answer'
    )
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args(argv)

    plan_path = Path(args.plan).expanduser()
    if not plan_path.is_file():
        print(f"No file at `{plan_path}` — nothing to retire.")
        return 1

    text = _bytes_of(plan_path)
    retires_root, link_dir = retires_root_of(plan_path)
    taken = {entry.name for entry in retires_root.glob("*.md")} if retires_root.is_dir() else set()

    try:
        source = str(plan_path.relative_to(_REPO_ROOT))
    except ValueError:
        source = str(plan_path)

    planning = plan_corbeille(
        text,
        source=source,
        ident=args.item,
        remplace=args.remplace,
        today=args.today,
        taken=frozenset(taken),
        link_dir=link_dir,
    )
    if not planning.blocked:
        try:
            verify_roundtrip(planning)
            verify_readability(planning)
        except RetraitCorbeilleError as refus:
            print(f"Trash retirement REFUSED — {refus}")
            return 1

    written = args.apply and not planning.blocked
    if written:
        try:
            apply_planning(planning, plan_path=plan_path, retires_root=retires_root)
        except FileExistsError as squatter:
            print(
                f"Retirement INTERRUPTED — `{Path(squatter.filename).name}` appeared between "
                "the check and the write. Nothing was overwritten, the arc was not rewritten."
            )
            return 1

    try:
        where = str(retires_root.relative_to(_REPO_ROOT))
    except ValueError:
        where = str(retires_root)
    print(render(planning, corbeille_dir=where, applied=written), end="")
    return 1 if planning.blocked else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
