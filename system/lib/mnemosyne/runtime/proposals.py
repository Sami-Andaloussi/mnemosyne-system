"""CLI over the inert-proposal queue - read what awaits review, or mark one reviewed.

    make proposals                              # what did the system deposit for me?
    make proposal-reviewed FICHIER=knowledge/proposals/veille/xxx.md

Thin composition over :mod:`mnemosyne.production.proposals` (the logic lives there; ``runtime/``
is the machine room, ``production/`` the output layer). A pure read/rewrite over
``knowledge/proposals``: no model, no brick (D126).

It lists PATHS and never a digest. That is not laziness: a proposal is a hypothesis or a candidate
skill mined FROM operator-managed library, and the point of the review is that HE reads the reasoning and
the quoted source, not a summary of it. A digest would quietly become the thing being judged.

Marking one ``revu`` means "seen and decided about" - NOT promoted. Turning a draft into a real
skill or a living fact stays a separate, deliberate act (D92 / D100: propose, never impose, and no
auto-promotion). Nothing here deletes anything (invariant 2).

Code & docstrings English (D117); this CLI's output is English too."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ..production.proposals import DEFAULT_PROPOSALS_DIR, mark_reviewed, open_proposals

#: Repo root from this module (``system/lib/mnemosyne/runtime/proposals.py`` -> parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]
#: Where ``make proposal-reviewed`` passes the path, out of reach of shell interpolation.
_FILE_ENV = "MNEMO_FICHIER"


def _shown(path: Path) -> Path:
    """``path`` relative to the repo when it is inside it - otherwise as-is (a temp tree in tests)."""
    try:
        return path.relative_to(_REPO_ROOT)
    except ValueError:
        return path


def render_open(paths: Sequence[Path]) -> str:
    """Render the pending proposals as readable markdown - or an honest 'nothing' line.

    Pure, like :func:`mnemosyne.runtime.tick.render_proposals`: a faithful projection of what is on
    disk. Groups by sub-queue (``veille/``...) so a long list stays legible."""
    if not paths:
        return "# Mnemosyne  -  proposals\n\nNo proposal is awaiting review.\n"
    noun = "inert proposal" if len(paths) == 1 else "inert proposals"
    lines = [
        "# Mnemosyne  -  proposals",
        "",
        f"{len(paths)} {noun} awaiting your review - the system deposited them, it promotes none of them:",
        "",
    ]
    seen_group = ""
    for path in paths:
        group = path.parent.name
        if group != seen_group:
            lines.append(f"**{group}/**")
            seen_group = group
        lines.append(f"- `{_shown(path)}`")
    lines += [
        "",
        "Read them yourself (they cite your own sources). Then, to classify one:",
        "`make proposal-reviewed FICHIER=<path>` - 'seen and decided', NEVER 'promoted'.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None, *, root: Path | None = None) -> int:
    """List the pending proposals, or mark one reviewed with ``--revu``.

    The path comes from ``argv`` when given, else from ``MNEMO_FICHIER``. A missing file is refused
    with a message rather than silently doing nothing."""
    where = DEFAULT_PROPOSALS_DIR if root is None else root
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--revu":
        raw = (" ".join(args[1:]) or os.environ.get(_FILE_ENV, "")).strip()
        if not raw:
            print("A file is required: make proposal-reviewed FICHIER=<path>", file=sys.stderr)
            return 2
        path = Path(raw)
        if not path.is_absolute():
            path = _REPO_ROOT / path
        if not path.is_file():
            print(f"Not found: {raw}", file=sys.stderr)
            return 2
        mark_reviewed(path)
        print(f"Proposal marked reviewed: {_shown(path)}")
        print("Nothing was promoted or deleted - the draft stays in place (invariant 2).")
        return 0
    print(render_open(open_proposals(where)), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
