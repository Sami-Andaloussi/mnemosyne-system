#!/usr/bin/env python3
"""Couture `plan-emit` — EMIT the LITERAL shape of a conformant plan, replayed from the code homes.

The other emit seams of this repo hand a MODEL its contract. This one hands a HOST the bytes of a
plan: the door, the arcs, the index entry, the statuses, the separators — admitted AND refused — and
every refusal the reader can name. Nothing here is written by hand. Every slot of
:data:`~mnemosyne.production.plan_scaffold.PLAN_CONTRACT_TEMPLATE` is filled by CALLING the real
code (``door_skeleton``, ``arc_skeleton``, ``index_entry``, ``slugify``, ``arc_ident``,
``STATUS_LABEL``, ``REFUSAL_KINDS``, ``REFUSAL_LABEL``, the separator sets), so this file cannot
say something the reader would refuse — the way a hand-copied contract silently does after the next
edit to its source (contract-single-source-emit; measured on the separator set itself, D170: a rule
DERIVED from what the tool writes scored twelve on twelve against the tool and two on ten against
the shapes a human types).

**THE FENCES ARE PART OF THE CONTRACT, not decoration.** Each handed-out artefact sits inside a
fenced block whose info string is ``markdown <clef>``, where ``<clef>`` is the FILE the block must be
written to (``PLAN.md``, ``plan/socle.md``, …) or ``entree`` for the standalone index line. That
delimitation is what lets ``tests/orchestration/test_plan_emit.py`` pull the exact bytes back out and
put them through the READER itself (``read_plan`` + ``merge_plan`` + ``index_problems`` +
``is_readable``) — the one proof that matters here: a skeleton this seam emits and the reader would
refuse is a contract that teaches the mistake at the exact moment a plan is being born.
:func:`emitted_blocks` is the ONE expression of that delimitation, read by the suite rather than
re-written there — two statements of one shape is how an emitter and its test start disagreeing.

**A6 ADDS A SECTION THIS FILE DOES NOT TREAT THE SAME WAY.** Everything above is the FORM
(level 2): fenced, replayed from code that a reader judges. The METHOD section
(:func:`~mnemosyne.production.plan_scaffold.method_skeleton`) is NOT fenced and carries no file to
write — it is level 1 (this project's own obligation framework), seven questions an author may answer
"not applicable" for free. It travels through this SAME seam (the operator: *"it travels through make
plan-emit, and that's the whole point"* — one home, emitted to every host, never hand-copied into a
project's own doc) precisely so a host that reads only the form still meets the thinking.

Print-only: no model, no brick, no network, and it opens no file.

Code & docstrings English (D117); everything printed is English in this public mirror (translated
per D33's mirror rule), accent-free in the glue text to match the voice of the contract it fills.

Usage : make plan-emit [NOM="my project"]
"""

from __future__ import annotations

import re
import sys
from typing import Final

#: The name a bare ``make plan-emit`` speaks about. Written as an obvious placeholder rather than a
#: plausible name: an agent that copies the door verbatim must SEE that this one word is its own.
DEFAULT_PROJECT: Final = "<the project's name>"

#: The second arc's title. The first is the code's own :data:`plan_scaffold.DEFAULT_ARC_TITLE`; this
#: one exists so the index shape is seen REPEATED (one line per arc) and so the identity rule shows
#: what it really is — one LETTER per arc, ``A1`` then ``B1``, never ``A1`` then ``A2``.
SECOND_ARC_TITLE: Final = "Measurements"

#: The key of the block carrying the standalone index line — the only block that is not a file.
ENTRY_KEY: Final = "entree"

_FENCE: Final = "```"
_BLOCK_LANG: Final = "markdown"
_RULE: Final = "=" * 88

#: The delimitation, as a reader of the emission: an opening fence carrying ``markdown <clef>``, the
#: bytes, and a closing fence alone on its line. Declared ONCE, used by :func:`_block` to write and
#: by :func:`emitted_blocks` to read, so the emitter and the suite cannot hold two ideas of where a
#: block starts. No artefact handed out here contains a line that is nothing but three backticks.
_BLOCK_RE: Final = re.compile(
    rf"^{_FENCE}{_BLOCK_LANG} (?P<key>\S+)\n(?P<text>.*?)^{_FENCE}$",
    re.DOTALL | re.MULTILINE,
)

#: Said once, right under the first block: the fence is the envelope, never the letter.
_FENCE_NOTE: Final = (
    "   (the two lines of three backticks are the block's DELIMITATION — they name the\n"
    "    file to write, and are NEVER part of its content)\n"
)


def _block(key: str, text: str) -> str:
    """One fenced block: its key (the file to write, or ``entree``) and its exact bytes."""
    tail = "" if text.endswith("\n") else "\n"
    return f"{_FENCE}{_BLOCK_LANG} {key}\n{text}{tail}{_FENCE}\n"


def emitted_blocks(emission: str) -> dict[str, str]:
    """Every block of an emission, ``key -> the exact bytes handed out``.

    Published for the suite: the test that proves this seam cannot drift from the reader has to get
    the bytes back, and it must not re-state the delimitation to do it. Fail-closed by construction —
    a delimitation this function cannot read yields nothing, and a reader handed nothing refuses.
    """
    return {found.group("key"): found.group("text") for found in _BLOCK_RE.finditer(emission)}


def build_emission(project: str = DEFAULT_PROJECT) -> str:
    """Fill the contract FRAME by replaying the real code — never by retyping what it produces.

    Lazy imports, like every other emit seam of this repo: the seam stays importable (and testable)
    without ``PYTHONPATH`` gymnastics at module load, and the cost of the code home is paid only when
    an emission is really built.
    """
    from mnemosyne.production.plan_archive import slugify
    from mnemosyne.production.plan_convert import index_entry
    from mnemosyne.production.plan_format import (
        ARCS_DIRNAME,
        PLAN_FILENAME,
        REFUSAL_KINDS,
        SEPARATOR_ASCII_KEY,
        SEPARATOR_KEYS_REFUSED,
        STATUS_BY_GLYPH,
        STATUS_LABEL,
        _ASCII_SEPARATORS,
        _TYPOGRAPHIC_SEPARATORS,
    )
    from mnemosyne.production.plan_scaffold import (
        DEFAULT_ARC_TITLE,
        DEFAULT_CAP,
        PLAN_CONTRACT_TEMPLATE,
        REFUSAL_LABEL,
        arc_ident,
        arc_skeleton,
        door_skeleton,
        method_skeleton,
    )

    # The two arcs, and their file names through the SAME `slugify` `plan_scaffold` uses — so what
    # this contract shows and what `make plan-nouveau` writes are the same string, not two guesses.
    titles = (DEFAULT_ARC_TITLE, SECOND_ARC_TITLE)
    members = tuple(f"{ARCS_DIRNAME}/{slugify(title)}.md" for title in titles)
    entries = tuple(zip(members, titles, strict=True))

    door = door_skeleton(project, DEFAULT_CAP, entries)
    arcs = tuple(arc_skeleton(title, arc_ident(rank)) for rank, title in enumerate(titles))

    tree = "\n".join(
        [
            f"       {project}/",
            f"       ├── {PLAN_FILENAME}".ljust(37) + "the DOOR: the goal and the index, no items",
            f"       └── {ARCS_DIRNAME}/".ljust(37) + "the ARCS: one file per arc",
            f"           ├── {members[0].split('/')[-1]}",
            f"           └── {members[1].split('/')[-1]}",
        ]
    )

    door_slot = _block(PLAN_FILENAME, door) + _FENCE_NOTE
    arc_slot = "\n".join(
        [
            _block(members[0], arcs[0]),
            "   And the SECOND arc — one LETTER per arc, never a number: identities are unique",
            "   across the WHOLE folder, so B2, B3, B4 stay yours without ever colliding with A2.",
            "",
            _block(members[1], arcs[1]),
        ]
    )
    entry_slot = _block(ENTRY_KEY, index_entry(members[0], titles[0])).rstrip("\n")

    statuses = "\n".join(
        f"     {glyph}  {STATUS_LABEL[token]}" for glyph, token in STATUS_BY_GLYPH.items()
    )

    # Two families, and the emission must not blur them: the marks a TOOL emits, and the keys a
    # HUMAN presses. Both come from the reader's own sets — there is no public name for either, and
    # re-deriving "which characters are separators" here is exactly the second home D170 paid for.
    # The two families on SEPARATE lines, and not a single one-letter word in the surrounding prose:
    # that's what lets the suite re-read the emitted set without re-typing it.
    separators = (
        " ".join(_TYPOGRAPHIC_SEPARATORS)
        + "\n   ... and the ASCII keys, under your fingers, admitted too\n   "
        + " ".join(_ASCII_SEPARATORS)
    )
    replaces: dict[str, list[str]] = {}
    for mark, key in SEPARATOR_ASCII_KEY.items():
        replaces.setdefault(key, []).append(mark)
    refused = "\n".join(
        f"     {key}  "
        + (f"(the key for {' '.join(replaces[key])})" if key in replaces else "").ljust(22)
        + reason
        for key, reason in SEPARATOR_KEYS_REFUSED.items()
    )

    refusals = "\n".join(
        [
            "   The READER, on the bytes (mnemosyne.production.plan_format):",
            *(f"     {kind}" for kind in REFUSAL_KINDS),
            "",
            "   BIRTH, before writing anything at all (make plan-nouveau):",
            *(f"     {token.ljust(26)}{label}" for token, label in REFUSAL_LABEL.items()),
        ]
    )

    return PLAN_CONTRACT_TEMPLATE.format(
        rule=_RULE,
        tree=tree,
        door_name=PLAN_FILENAME,
        door=door_slot,
        arcs_dirname=ARCS_DIRNAME,
        arc=arc_slot,
        entry=entry_slot,
        separators=separators,
        refused=refused,
        statuses=statuses,
        refusals=refusals,
        method=method_skeleton(),
    )


def main(argv: list[str] | None = None) -> int:
    """``make plan-emit [NOM="..."]`` — one optional positional argument: the project's name."""
    args = sys.argv[1:] if argv is None else argv
    project = args[0].strip() if args and args[0].strip() else DEFAULT_PROJECT
    print(build_emission(project), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
