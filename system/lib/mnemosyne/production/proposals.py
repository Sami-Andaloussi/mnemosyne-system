"""The inert-proposal queue (D155) - what the system deposited, awaiting operator's review.

``make describe`` advertises a surface: *"proposals - receive non-solicited proposals and review
them - propose, never impose (D119-f / D92)"*. The DEPOSIT half was real - the veilleur writes
inert drafts under ``knowledge/proposals/veille/``, and an agent can drop a candidate skill there
- but the RETURN half was missing: nothing ever told operator they existed. Eight drafts had been
sitting there, correctly filed and permanently invisible, until a project session filed a
signalement about it. A queue nobody drains is a queue nobody filled.

This module is that return path. It answers two questions and performs one gesture:

* HOW MANY drafts await (the meta-signal the tick surfaces - a count, never the content, inv. 22);
* WHICH files they are (for a session that will actually read them);
* flip one to ``revu`` once it has been looked at - **never delete it** (invariant 2).

**The status is the file's own frontmatter**, not a side ledger: a proposal is OUR artefact, so
one file is one truth and nothing can drift out of sync. (The veille LEDGER exists for the
opposite reason - it tracks fiches we do NOT own, to avoid re-surveying them.) The parsing and
the atomic rewrite come from :mod:`~mnemosyne.production.frontmatter_status`, shared with the
signalements queue.

**Why a review gesture had to ship with the counter.** ``veille_ledger`` records the lesson in its
own docstring: a nudge with no way to clear it becomes a perpetual false alarm, and an alarm that
is always on is an alarm nobody reads. Counting drafts without offering ``revu`` would have
guaranteed that outcome. Reviewing is NOT promoting: a reviewed proposal is one operator has seen and
decided about; turning one into a real skill or a living fact stays a separate, deliberate act
(D92 / D100 - propose, never impose, and no auto-promotion).

Decisions: D92 / D119-f (propose, never impose)  -  D155 (the return path)  -  invariant 22 (the tick
sees counts, never matter)  -  invariant 2 (a status flips, a proposal is never deleted).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from .frontmatter_status import entries_with_status, set_status, status_of

#: Repo root from here (``system/lib/mnemosyne/production/proposals.py`` -> parents[4] = repo).
_REPO_ROOT: Final = Path(__file__).resolve().parents[4]

#: Where inert proposals live. Covers every sub-queue (``veille/`` today, more later) because the
#: scan recurses - a new depositor gets surfaced without touching this module.
DEFAULT_PROPOSALS_DIR: Final = _REPO_ROOT / "knowledge" / "proposals"

#: Awaiting review. This is the veilleur's own wording (``system/skills/veilleur/veille.py``
#: writes ``status: draft``) - we read what the depositor writes rather than asking it to change.
DRAFT: Final = "draft"
#: Seen and decided about by operator. NOT "promoted": promotion is a separate, deliberate act.
REVIEWED: Final = "revu"

#: Navigation files that are not proposals, should a queue ever grow one.
_NOT_A_PROPOSAL: Final = frozenset({"README.md", "MOC.md", "INDEX.md"})


def open_proposals(root: Path = DEFAULT_PROPOSALS_DIR) -> tuple[Path, ...]:
    """Every proposal still awaiting review, sorted by path (so sub-queues group together).

    A missing directory yields ``()`` - nothing has ever been deposited, which is not an error.
    """
    return entries_with_status(root, DRAFT, skip_names=_NOT_A_PROPOSAL)


def open_proposal_count(root: Path = DEFAULT_PROPOSALS_DIR) -> int:
    """HOW MANY proposals await - the meta-signal the tick surfaces, never their content (inv. 22).

    This one matters more than its siblings: a proposal's body is mined FROM operator-managed library and
    can name a personal source, so the count is the only thing allowed to cross into the tick.
    """
    return len(open_proposals(root))


def mark_reviewed(path: Path) -> Path:
    """Flip one proposal to ``revu``. Idempotent, non-destructive, body untouched.

    Re-running on an already-reviewed proposal (or one whose frontmatter block is destroyed) leaves
    it exactly as it is, rather than raising: draining a queue must never be the thing that breaks.
    """
    if status_of(path) != DRAFT:
        return path
    return set_status(path, REVIEWED)
