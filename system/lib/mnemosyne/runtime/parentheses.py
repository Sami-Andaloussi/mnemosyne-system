"""CLI over the parenthesis protocol (C8-c) — open a detour, see what is running, bring it back.

    make parenthese-ouvrir TITRE="..." PLAN="<project>/PLAN.md" ITEM="C8" \\
        POURQUOI="..." RETOUR_ATTENDU="what the plan must receive back"
    make parentheses
    make parenthese-fermer FICHIER=docs/parentheses/....md RETOUR="..." DANS="<project>/PLAN.md"

Thin composition over :mod:`mnemosyne.production.parentheses` (the logic and every refusal live
there — ``runtime/`` is the machine room, ``production/`` the output layer). A pure read/append over
``docs/parentheses``: no model, no brick (D126).

**The asymmetry is inverted compared to signalements, on purpose.** There, FILING is trivial and
DRAINING is the careful half. Here, both ends are careful and the middle is trivial: opening must
declare what will come back, closing must prove it did, and the listing in between is a plain read.
That is what a parenthesis is — the two ends are the protocol, the middle is just work.

Every free-text argument arrives through the ENVIRONMENT (``MNEMO_P_*``), never interpolated into a
shell recipe: these are sentences a session composes, and backticks or ``$(...)`` in a Make recipe
would execute. Same reason as ``make signaler``.

Code, docstrings and what it prints are English (D117)."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ..production.parentheses import (
    DEFAULT_PARENTHESES_DIR,
    ParentheseRefusee,
    close_parenthese,
    closure_line,
    open_parenthese,
    open_parentheses,
    plan_points_at,
    pointer_line,
    read_parenthese,
)

#: Repo root from this module (``system/lib/mnemosyne/runtime/parentheses.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]

#: Where ``make parenthese-*`` passes each free-text field, out of reach of shell interpolation.
_ENV = {
    "titre": "MNEMO_P_TITRE",
    "plan": "MNEMO_P_PLAN",
    "item": "MNEMO_P_ITEM",
    "pourquoi": "MNEMO_P_POURQUOI",
    "retour_attendu": "MNEMO_P_RETOUR_ATTENDU",
    "fichier": "MNEMO_P_FICHIER",
    "retour": "MNEMO_P_RETOUR",
    "dans": "MNEMO_P_DANS",
}


def _arg(name: str) -> str:
    return os.environ.get(_ENV[name], "").strip()


def _shown(path: Path, *, repo_root: Path = _REPO_ROOT) -> Path:
    """``path`` relative to the repo when it is inside it — otherwise as-is (a temp tree in tests)."""
    try:
        return path.relative_to(repo_root)
    except ValueError:
        return path


def render_open(paths: Sequence[Path], *, repo_root: Path = _REPO_ROOT) -> str:
    """Render the running parentheses — with, for each, WHAT IT STILL OWES its plan.

    Pure, like its siblings ``render_open`` / ``render_proposals``: a faithful projection of what is
    on disk. Unlike them it does NOT stop at paths. A signalement's content is a defect report a
    session must read in full; a parenthesis's outstanding debt is one declared line, and hiding it
    behind "open the file" is how sixteen backlog bullets came to have no verifiable
    return at all. What is shown is the DECLARED debt, never the detour's working content.

    A parenthesis whose plan does not mention it is flagged: an open detour nothing points at is
    invisible from the plan, which is the waste this protocol exists to prevent. It is REPORTED,
    never blocked — the pointer is a human's paste, and a tool that refused work over a missing
    paste would be a door slower than the wall.
    """
    if not paths:
        return "# Mnémosyne · parentheses\n\nNo open parenthesis — nothing is lying around beside a plan.\n"
    noun = "open parenthesis" if len(paths) == 1 else "open parentheses"
    lines = [
        "# Mnémosyne · parentheses",
        "",
        f"{len(paths)} {noun} — each one still OWES something to its plan:",
        "",
    ]
    for path in paths:
        parenthese = read_parenthese(path)
        item = f" · item {parenthese.item}" if parenthese.item else ""
        lines.append(
            f"- **{parenthese.titre or path.stem}** — `{_shown(path, repo_root=repo_root)}`"
        )
        lines.append(f"  - starts from: `{parenthese.plan}`{item}")
        lines.append(f"  - must return: {parenthese.retour_attendu or '(not declared)'}")
        points = plan_points_at(parenthese, repo_root=repo_root)
        if points is False:
            lines.append(
                "  - **the plan does not point at it** : it is invisible from the plan. "
                "Paste its pointer line in there."
            )
        elif points is None:
            lines.append(
                "  - **plan unreadable or not found** : the pointer cannot be verified."
            )
    lines += [
        "",
        'To close one: `make parenthese-fermer FICHIER=<path> RETOUR="what came back" '
        'DANS="the file that carries it"`.',
        "Both are required — closing without naming what came back is refused.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _open(root: Path, repo_root: Path) -> int:
    """Open one parenthesis, then PRINT the single line to paste into the plan."""
    try:
        path = open_parenthese(
            _arg("titre"),
            plan=_arg("plan"),
            item=_arg("item"),
            pourquoi=_arg("pourquoi"),
            retour_attendu=_arg("retour_attendu"),
            root=root,
            repo_root=repo_root,
        )
    except ParentheseRefusee as refusal:
        print(str(refusal), file=sys.stderr)
        return 2
    parenthese = read_parenthese(path)
    plan_path = (
        repo_root / parenthese.plan
        if not Path(parenthese.plan).is_absolute()
        else Path(parenthese.plan)
    )
    try:
        line = pointer_line(
            parenthese, plan_text=plan_path.read_text(encoding="utf-8"), repo_root=repo_root
        )
    except OSError:  # pragma: no cover - open_parenthese already proved the plan is a file
        line = pointer_line(parenthese, plan_text="", repo_root=repo_root)
    print(f"Parenthesis opened: {_shown(path, repo_root=repo_root)}")
    print("")
    print(
        "Paste THIS line — and nothing else — into your plan (the identifier is free, and checked):"
    )
    print("")
    print(f"    {line}")
    print("")
    print("All of the parenthesis's work happens IN its file, never in the plan.")
    return 0


def _close(repo_root: Path) -> int:
    """Close one parenthesis — refused unless the return is named AND landed somewhere real."""
    raw = _arg("fichier")
    if not raw:
        print(
            "The parenthesis's file is required: make parenthese-fermer FICHIER=<path> "
            'RETOUR="..." DANS="..."\n(`make parentheses` lists them.)',
            file=sys.stderr,
        )
        return 2
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    if not path.is_file():
        print(f"Not found: {raw}", file=sys.stderr)
        return 2
    retour, dans = _arg("retour"), _arg("dans")
    try:
        parenthese = close_parenthese(path, retour=retour, dans=dans, repo_root=repo_root)
    except ParentheseRefusee as refusal:
        print(str(refusal), file=sys.stderr)
        return 2
    print(f"Parenthesis closed: {_shown(path, repo_root=repo_root)}")
    print("The file stays where it is — we never delete (inv. 2).")
    print("")
    print("In the plan, its pointer line becomes:")
    print("")
    print(f"    {closure_line(parenthese, retour=retour, dans=dans)}")
    return 0


def main(
    argv: Sequence[str] | None = None, *, root: Path | None = None, repo_root: Path | None = None
) -> int:
    """List the running parentheses, or open one (``--ouvrir``), or close one (``--fermer``)."""
    where = DEFAULT_PARENTHESES_DIR if root is None else root
    home = _REPO_ROOT if repo_root is None else repo_root
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--ouvrir":
        return _open(where, home)
    if args and args[0] == "--fermer":
        return _close(home)
    print(render_open(open_parentheses(where), repo_root=home), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
