"""Parentheses for Mnemosyne System."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from .frontmatter_status import (
    create_dated_entry,
    entries_with_status,
    field_of,
    set_status,
    status_of,
    today_stamp,
    yaml_quoted,
)
from .plan_format import DOOR_FILENAMES, read_plan
from .plan_registry import arc_tree

#: Repo root from here (``system/lib/mnemosyne/production/parentheses.py`` -> parents[4] = repo).
_REPO_ROOT: Final = Path(__file__).resolve().parents[4]

#: Where parentheses live. GITIGNORED except this directory's ``README.md``, for the reason D153
#: settled for signalements: the prose is composed from inside a project's context and can name a
#: personal source in its body AND in its title, which becomes a permanent filename. What is durable
#: is not the detour but its RETURN - and the return lands in the plan, which git does track.
DEFAULT_PARENTHESES_DIR: Final = _REPO_ROOT / "docs" / "parentheses"

#: A detour still running. Its debt is still outstanding.
OPEN: Final = "ouverte"
#: A detour whose return has been named AND located. Kept on disk forever (invariant 2).
CLOSED: Final = "fermee"

#: Files that are not parentheses (the contract doc lives in the same directory).
_NOT_A_PARENTHESE: Final = frozenset({"README.md"})

#: The pointer identity family. ``P`` + a number, which :data:`~mnemosyne.production.plan_format`'s
#: identity rule accepts (``[A-Za-z]{1,4}[0-9]+``) - so a pointer is a first-class plan item, not a
#: comment the reader would drop into prose.
_POINTER_IDENT_RE: Final = re.compile(r"\AP([0-9]+)\Z")

#: The glyph a pointer carries while the detour runs, and the one it carries once it is back. These
#: are KEYS of :data:`~mnemosyne.production.plan_format.STATUS_BY_GLYPH`, not decoration: the plan
#: format is written with them, and a line rendered here is read back by
#: :func:`~mnemosyne.production.plan_format.read_plan`. Put anything else in their place - an ASCII
#: label, a word - and the reader answers ``statut_inconnu`` on a line the protocol itself just
#: produced. ``\U0001f504`` is *en cours* (the detour is being worked), ```` is *fait*. A
#: parenthesis is never ```` - that is "reprise attendue", the state of the plan item it
#: departs FROM, never the state of the detour.
POINTER_GLYPH_OPEN: Final = "\U0001f504"
POINTER_GLYPH_CLOSED: Final = "\U00002705"


class ParentheseRefusee(ValueError):
    """Raised when a parenthesis operation cannot preserve its invariants."""


@dataclass(frozen=True, slots=True)
class Parenthese:
    """One detour, as read off its own file. The frontmatter IS the state - no side ledger.

    ``retour_attendu`` is the field the whole module exists for: declared at the opening, never
    empty, and carried here so the listing can show the outstanding debt beside every open detour
    instead of making someone open six files to find out what is owed.
    """

    path: Path
    titre: str
    plan: str
    item: str
    retour_attendu: str
    status: str

    @property
    def is_open(self) -> bool:
        return self.status == OPEN


def read_parenthese(path: Path) -> Parenthese:
    """Read one parenthesis off disk - fail-OPEN, like every reader in this family.

    An unreadable field yields ``""`` rather than raising: a queue that raises is a queue that stops
    the tick, and the tick must never be what stops a session.
    """
    return Parenthese(
        path=path,
        titre=field_of(path, "titre"),
        plan=field_of(path, "plan"),
        item=field_of(path, "item"),
        retour_attendu=field_of(path, "retour_attendu"),
        status=status_of(path) or "",
    )


def open_parentheses(root: Path = DEFAULT_PARENTHESES_DIR) -> tuple[Path, ...]:
    """Every parenthesis still running, sorted (filename order IS chronological - dated prefix)."""
    return entries_with_status(root, OPEN, skip_names=_NOT_A_PARENTHESE)


def open_parenthese_count(root: Path = DEFAULT_PARENTHESES_DIR) -> int:
    """HOW MANY detours are running - the meta-signal the tick surfaces, never a title (inv. 22)."""
    return len(open_parentheses(root))


def _resolve(raw: str, *, repo_root: Path) -> Path:
    """A path as a caller typed it - absolute, or relative to the repo root."""
    path = Path(raw)
    return path if path.is_absolute() else repo_root / path


def next_pointer_ident(*plan_texts: str) -> str:
    """The next free ``P<n>`` identity across EVERY file of a plan - computed, never guessed.

    Handing out a fixed ``P1`` would eventually duplicate an existing identity, and
    :func:`~mnemosyne.production.plan_format.read_plan` refuses a duplicate (``id_duplique``) - which
    the ``pre-commit`` barrier turns into a refused commit. So the one line we hand a human to paste
    must be one their plan can actually accept. Computed off the plan's OWN reader, so a change to
    what counts as an identity cannot leave this function behind.

    Variadic since D166, because an identity's scope is the whole PLAN and a plan is now a FOLDER:
    ``plan_registry.read_plan_tree`` threads ONE ``ident_seen`` through the door and every arc, so a
    ``P1`` free of the door and taken in ``plan/arc-c.md`` is still a duplicate. Each text is read on
    its own rather than glued into one string: a plan NESTED under ``plan/`` keeps its own identity
    scope, so concatenating would make a legal pair look like a duplicate and DROP one of the two -
    and an identity dropped from this set is a number handed out twice.
    """
    used = {
        int(found.group(1))
        for text in plan_texts
        for item in read_plan(text).items
        if (found := _POINTER_IDENT_RE.match(item.ident))
    }
    return f"P{max(used) + 1 if used else 1}"


def pointer_line(parenthese: Parenthese, *, plan_text: str, repo_root: Path = _REPO_ROOT) -> str:
    """THE one line the plan carries - a pointer, never the content (that is what keeps it clean).

    It says three things and stops: that a detour is running, what it is about, and where it lives.
    The expected return is deliberately NOT restated here: it is written in the parenthesis, and a
    hand-copied second copy of it is the exact defect ``plan_format`` was built against ("a computed
    number cannot rot; a copied number does within three days").

    ``plan_text`` is the DOOR as its caller read it; the ARCS are read here, because the caller holds
    one path and a plan is a folder (D166). That is not a refinement - it reopens the exact defect
    the computed identity exists against: every past parenthesis's ``P<n>`` sits in an arc, so an
    identity computed on the door alone is free of the door and free of nothing else, and the line we
    hand out makes the plan illisible on the very commit that pastes it.
    """
    shown = _shown(parenthese.path, repo_root=repo_root)
    plan_path = _resolve(parenthese.plan, repo_root=repo_root)
    return (
        f"- **{next_pointer_ident(plan_text, *_arc_texts(plan_path))}** {POINTER_GLYPH_OPEN} "
        f"Parenthesis - {parenthese.titre}  -  `{shown}`"
    )


def closure_line(parenthese: Parenthese, *, retour: str, dans: str) -> str:
    """What the pointer line BECOMES once the detour is back - the visible half of the return.

 Handed out at closing time for the same reason the pointer is handed out at opening time: a plan
 still showing ```` for a closed parenthesis lies at exactly the moment the protocol claims to
 have worked, and the person best placed to notice is the one who just closed it.
 """
    return (
        f"- **<the same identifier>** {POINTER_GLYPH_CLOSED} Parenthesis closed - "
        f"{parenthese.titre}  -  return: {retour} -> `{dans}`"
    )


def _shown(path: Path, *, repo_root: Path) -> Path:
    """``path`` relative to the repo when it sits inside it - otherwise as-is (a tmp tree in tests)."""
    try:
        return path.relative_to(repo_root)
    except ValueError:
        return path


def _plan_door(plan_path: Path) -> Path | None:
    """The DOOR of the plan ``plan_path`` designates - itself when it names a file, the folder's door
    when it names a folder, ``None`` when that folder carries no door at all.

    Since D166 a plan IS a folder, so ``plan: docs`` is a shape a hand-edited frontmatter now
    legitimately carries - and ``read_text`` on a directory raises ``IsADirectoryError``, which is an
    ``OSError``. The blanket catch downstream therefore switched the whole control off and answered
    "I don't know" about a plan sitting right there: the third outcome reached by falling into
    it, not by deciding it. ``None`` is now kept for what is genuinely unknowable.

    :func:`open_parenthese` still REFUSES a folder when a parenthesis is opened (its fourth refusal is
    untouched): the reader is deliberately more generous than the writer, because the writer's
    caller reads ``plan`` with ``read_text`` and falls back to an empty plan - which hands out ``P1``
    unconditionally. Widening there would open a hole; widening here closes one.
    """
    if plan_path.is_dir():
        doors = (plan_path / name for name in DOOR_FILENAMES)
        return next((door for door in doors if door.is_file()), None)
    return plan_path


def _plan_files(plan_path: Path) -> tuple[Path, ...]:
    """Every file the plan is made of - its door FIRST, then every arc under ``plan/``, at any depth.

    The arc list is DECLINED from :func:`~mnemosyne.production.plan_registry.arc_tree` rather than
    re-globbed here. "Where the arcs of a plan live" is one rule, and this repo has already measured
    what a second copy of a rule costs: four hand-copied numbers for one quantity, none of them read
    by any control. No cycle to fear - ``plan_registry`` imports ``plan_format`` and nothing else, so
    the day that stops being true this import fails LOUDLY, which a duplicated ``rglob`` would not.
    """
    door = _plan_door(plan_path)
    if door is None:
        return ()
    folder = door.parent
    return (door, *(folder / relative for relative in arc_tree(folder)))


def _plan_text(path: Path) -> str | None:
    """One plan file's bytes, or ``None`` - never an exception, on any hostile tree.

    ``UnicodeDecodeError`` is a ``ValueError``, not an ``OSError``: a single arc of invalid bytes
    under ``plan/`` escaped the old catch entirely and would have taken the tick down with it. The
    pair caught is the one ``plan_registry._read_text`` already catches - one vocabulary for "this
    file cannot be read", not two.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _arc_texts(plan_path: Path) -> tuple[str, ...]:
    """The bytes of every ARC of this plan. The door is skipped - its caller already holds it."""
    return tuple(
        text for path in _plan_files(plan_path)[1:] if (text := _plan_text(path)) is not None
    )


def plan_points_at(parenthese: Parenthese, *, repo_root: Path = _REPO_ROOT) -> bool | None:
    """Does the parenthesis's plan actually MENTION it? ``None`` when the plan cannot be read.

    Three outcomes, never two. A plan that cannot be read is not a plan that fails to point - saying
    ``False`` there would accuse a parenthesis for a missing file, and an accusation nobody can act on
    is worse than a silence somebody can measure.

    **The plan is a FOLDER, so the search is the folder** (D166): a door, plus one file per arc. The
    pointer of a parenthesis is pasted where the WORK sits, which is an arc and never the door - so
    reading the door alone answered "the plan does not point to it" about a plan that points at
    it perfectly. That false accusation is not an edge case: it is what the format's own shape
    produces on every plan that adopts it, and it lands on the one line a human already pasted.

    FOUND beats blind. ``None`` is reserved for "nothing was found AND something could not be read":
    a mention that IS there is not made less true by a file beside it that is not, and a plan whose
    arcs are half-unreadable must not be reported as a plan that fails to point.

    The match is on the FILENAME, not on a rendered line: the pointer is meant to be edited by a
    human (renumbered, reworded, moved under another section), and a check that demanded the exact
    bytes we emitted would go red on every legitimate edit - a control that punishes correct use is
    a control people delete.
    """
    files = _plan_files(_resolve(parenthese.plan, repo_root=repo_root))
    blind = not files
    for path in files:
        text = _plan_text(path)
        if text is None:
            blind = True
        elif parenthese.path.name in text:
            return True
    return None if blind else False


def open_parenthese(
    titre: str,
    *,
    plan: str,
    item: str,
    pourquoi: str,
    retour_attendu: str,
    root: Path = DEFAULT_PARENTHESES_DIR,
    repo_root: Path = _REPO_ROOT,
    today: date | None = None,
) -> Path:
    """Create a parenthesis only when its return path is explicit."""
    if not titre.strip():
        raise ParentheseRefusee(
            'A title is required: make parenthese-ouvrir TITRE="what we are about to look at" ...'
        )
    if not retour_attendu.strip():
        raise ParentheseRefusee(
            "REFUSED - a parenthesis must say WHAT MUST COME BACK to the plan once it closes.\n"
            "It is the one field that keeps a debt from being left behind: a parenthesis from an\n"
            "earlier project closed cleanly while leaving a decision that was never carried out, and\n"
            "nobody noticed.\n"
            'The fix: add RETOUR_ATTENDU="what the plan should receive" and try again.'
        )
    if not plan.strip():
        raise ParentheseRefusee(
            "REFUSED - a parenthesis must say WHICH PLAN it is departing from, otherwise it has\n"
            'nowhere to return to. The fix: add PLAN="path/to/your/PLAN.md" (or your project\'s own PLAN.md).'
        )
    plan_path = _resolve(plan, repo_root=repo_root)
    if not plan_path.is_file():
        raise ParentheseRefusee(
            f"REFUSED - this plan does not exist on disk: {plan}\n"
            "A parenthesis that points at a plan that cannot be found is orphaned from birth.\n"
            "The fix: check the plan's path and try again."
        )
    stamp = today_stamp(today)
    body = _TEMPLATE.format(
        status=OPEN,
        date=stamp,
        titre=yaml_quoted(titre),
        plan=yaml_quoted(plan.strip()),
        item=yaml_quoted(item.strip()),
        retour_attendu=yaml_quoted(retour_attendu),
        titre_nu=titre,
        pourquoi=pourquoi.strip() or "*(to fill in: why we are stepping away from the plan)*",
    )
    return create_dated_entry(root, stamp=stamp, title=titre, body=body)


def close_parenthese(
    path: Path,
    *,
    retour: str,
    dans: str,
    repo_root: Path = _REPO_ROOT,
    today: date | None = None,
) -> Parenthese:
    """Close one parenthesis - REFUSES unless the return is both NAMED and LOCATED. Never deletes.

    ``retour`` is what came back; ``dans`` is where it landed. Both are required, and ``dans`` must
    resolve to a file that exists. That second half is the one that closes an earlier project's
    defect: its parenthesis could have named its return truthfully ("the dependency field was
    decided") and the field still never reached ``chantiers.yaml``. A destination on disk is not
    proof the return is complete - nothing cheap is - but it is proof somebody had to go somewhere
    and write.

    Re-closing an already-closed parenthesis is REFUSED rather than silently ignored. Its siblings
    (``mark_handled``, ``mark_reviewed``) are idempotent, and here that would be a silent loss: a
    second closure carrying a DIFFERENT return would report success and record nothing, which is the
    exact shape of the defect this module exists to prevent.
    """
    if not retour.strip():
        raise ParentheseRefusee(
            "REFUSED - a parenthesis is not closed without saying WHAT CAME BACK to the plan.\n"
            "Closing it in silence is exactly the waste this is meant to prevent: the folder empties\n"
            "out and the debt remains.\n"
            'The fix: try again with RETOUR="what actually came back into the plan".'
        )
    if not dans.strip():
        raise ParentheseRefusee(
            "REFUSED - saying what came back is not enough: you must also say WHERE it came back to.\n"
            "Measured: a parenthesis from an earlier project named its decision, and the decision\n"
            "never reached the file meant to carry it. Naming it without placing it is closing on a\n"
            "promise.\n"
            'The fix: try again with DANS="the file that now carries this return".'
        )
    destination = _resolve(dans, repo_root=repo_root)
    if not destination.is_file():
        raise ParentheseRefusee(
            f"REFUSED - this destination file does not exist: {dans}\n"
            'A return "placed" in a file that does not exist is not placed.\n'
            "The fix: write the return into the plan (or the relevant file) first, then close it again."
        )
    if destination.resolve() == path.resolve():
        raise ParentheseRefusee(
            "REFUSED - a parenthesis cannot be its own destination.\n"
            "A return that stays inside the parenthesis never made it back to the plan: that is the\n"
            "debt, not its repayment.\n"
            "The fix: point DANS= at the plan or file that this return is meant to feed."
        )
    current = status_of(path)
    if current is None:
        raise ParentheseRefusee(
            f"REFUSED - this file does not carry a readable status: {path}\n"
            "The fix: check that this is indeed a parenthesis (make parentheses lists them)."
        )
    if current != OPEN:
        raise ParentheseRefusee(
            f"REFUSED - this parenthesis is already \"{current}\", it does not get closed twice.\n"
            "Otherwise the second return would be announced as recorded without actually being so.\n"
            "The fix: if it needs to reopen, put `status: ouverte` back in its header, then close it\n"
            "again."
        )
    stamp = today_stamp(today)
    set_status(
        path,
        CLOSED,
        extra_lines=(
            f"ferme_le: {yaml_quoted(stamp)}",
            f"retour: {yaml_quoted(retour)}",
            f"retour_dans: {yaml_quoted(dans.strip())}",
        ),
    )
    return read_parenthese(path)


#: The shell the opening session fills in. Written in English - the user reads these. The two machine-critical
#: fields (``retour_attendu`` at the top, ``retour``/``retour_dans`` written at closing) are in the
#: FRONTMATTER, not in the prose: what a control must read cannot live where a human is free to
#: rewrite it.
_TEMPLATE: Final = """---
status: {status}
date: "{date}"
titre: {titre}
plan: {plan}
item: {item}
retour_attendu: {retour_attendu}
---

# Parenthesis - {titre_nu}

**Where it departs from** - `{plan}`, item {item}

**Why we are stepping away** - {pourquoi}

**What must COME BACK to the plan once it closes** *(declared at opening, non-negotiable)* -
{retour_attendu}

---

## The work of the parenthesis

*(everything happens HERE, never in the plan: the plan carries only one line pointing back to this file)*

---

> **To close it**: `make parenthese-fermer FICHIER=<this file> RETOUR="what came back"
> DANS="the file that now carries it"`. Both are **required**: a parenthesis from an earlier project
> closed cleanly while leaving a decision that was never carried out - this is the exact hole being closed.
> This file is never deleted (invariant 2): its status changes to `fermee`, and it stays.
"""
