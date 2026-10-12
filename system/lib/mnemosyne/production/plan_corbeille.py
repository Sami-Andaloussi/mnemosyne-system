"""H3 — move a RETIRED item's bytes out of a living arc, into a PERMANENT trash. Nothing is erased.

The operator's idea, countered by what is already law here: *"create a trash that stores
everything we delete, but permanently deletes it three months later."* Mnemosyne never erases
(inv. 2 — invalidate/archive), and ``make rangement`` is already a reversible quarantine. A
delayed erasure is an erasure with a clock on it — less safe, not more. So this corbeille has no
expiry: an item that leaves a living plan lands here, with its motif, its cost, and what replaces
it, and it STAYS.

**What H1 already does, and where it stops.** ``plan_retrait.applique_retrait`` (H1, closed) turns an
item's glyph to ```` and inserts a one-line HTML comment carrying ``motif``/``cout`` right after the
bullet — in place, invariant 2, nothing deleted. It never moves a byte out of the file. Measured on
this repo the day this module was written: a retired item's bullet, its H1 comment and its own
detail block all still sit in the arc that closed it, forever, growing the file that a plan is
supposed to shrink. This module is the SECOND half H1 names but does not build: the physical move.

**Why not ``plan/retires/``, the literal path the item names.** Measured against the reader this
module must never disagree with: :func:`~.plan_format.plan_entries` treats every ``.md`` file under
``plan/`` as an ARC, at any depth, unless it carries its own door. A retired item written to
``plan/retires/<x>.md`` would therefore be read back as an undeclared arc and refused
(``arc_hors_index``) by the very barrier this repo runs on every commit — the opposite of "``make
plans`` stops counting it". The corbeille sits BESIDE the arcs directory instead, exactly where
``docs/archive/`` already sits beside ``docs/plan/`` (:mod:`~.plan_archive`, same reasoning, same
:func:`~mnemosyne.runtime.plan_archiver_run.plan_site` a caller can reuse to find it).

**The SAME move as archiving, a third noun.** :mod:`~.plan_archive`'s own
:func:`~.plan_archive.verify_verbatim_roundtrip` says it explicitly: *"Archiving […] and converting
a plan into a folder […] are the SAME move over different nouns […] only the three nouns differ"*.
Here the noun is an ITEM rather than a closed SECTION or ARC, so this module supplies exactly those
three nouns and reuses that one proof — never a second, drifting copy of the guarantee that makes
the operator's rule 1 (*"write it as is, exactly as is"*) a barrier instead of a promise.

**One item per call, on purpose.** ``*Produit*`` asks for a NEW field H1 never collects — "what
replaces it" — and it cannot be derived, only stated. Auto-discovering every ```` item in a file
and moving them in one sweep would move some without that field ever being asked, and the arc's
own preamble warns against exactly this shape of mistake: *"an agent authorised to retire an item
can lower its own remaining-work count."* So the caller names ONE item; the module refuses
everything it cannot prove about THAT one.

**What this module does NOT do — rule 1, taken at its word.** The body that travels into the
corbeille is copied byte for byte, including any relative link it happens to carry. Rewriting a
link so it still resolves from the new location would be exactly the reformulation the operator's
rule 1 forbids — *measured on the real corpus, at write time*: two real relative links across the
whole ``docs/plan/`` tree, one in ``00-le-socle-du-plan.md``, one in
``ce-qui-n-est-pas-dans-ce-plan.md``, neither confirmed to sit inside an item's own detail block. A
body that carries one is UNCHANGED and the header says so, naming the limitation rather than
hiding it (the failure the orchestrator measured archiving two postes this same morning —
byte-exact, reachability broken).

Code & docstrings English (D117); this repo's own convention (D33) prints in French - this
public-mirror copy is translated into English throughout. Decisions: H1, H3, inv. 2.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

from .plan_archive import (
    VERBATIM_MARKER,
    VerbatimMove,
    verify_verbatim_roundtrip as _verify_verbatim_roundtrip,
)
from .plan_format import (
    PlanItem,
    ROLE_ARC,
    is_readable,
    read_plan,
    unreadable_reasons,
)

#: Re-exported so a caller of THIS module never needs to reach into `.plan_archive` for a name it
#: only knows because this module happens to reuse it internally.
verify_verbatim_roundtrip = _verify_verbatim_roundtrip

#: Beside the arcs directory, never inside it — see the module docstring for the measured reason a
#: literal `plan/retires/` would make every retired item an `arc_hors_index` refusal.
RETIRES_DIRNAME: Final = "retires"

#: The glyph H1 (`plan_retrait._GLYPHE_RETRAIT`) leaves on a retired item — not re-imported (that
#: constant is private to a module this one does not otherwise depend on), but PINNED to the same
#: value by `tests/orchestration/test_plan_corbeille.py`, which imports both and asserts equality:
#: two independent constants agreeing is a choice that can be checked, unlike one that is assumed.
GLYPHE_RETRAIT: Final = "\U000026D4"

#: H1's own comment, read back. Built from the EXACT string `applique_retrait` writes (verified
#: against its real output before this pattern was written — see the module's test), not guessed
#: at. Greedy `.*` for `motif` finds the LAST ` cout=` in the line, which is what a flattened,
#: `-->`-escaped field (`_sur_une_seule_ligne_de_commentaire`, plan_retrait.py) guarantees it can do
#: safely: motif itself can never contain a literal `-->`.
_RETRAIT_COMMENT_RE: Final = re.compile(
    r"<!-- RETRAIT \(H1\) id=(?P<id>\S+) le=(?P<le>\S+) motif=(?P<motif>.*) cout=(?P<cout>.*) -->\s*$"
)

_MAX_REMPLACE_CHARS: Final = 2000

REFUSAL_LABEL: Final = {
    "item_absent": "this identifier does not exist in the given text",
    "pas_retire_par_h1": "this item is not closed by the H1 mechanism — no retirement comment "
    "right after its bullet; this module only moves what H1 has actually retired",
    "commentaire_illisible": "the item carries a comment that LOOKS LIKE an H1 retirement but that "
    "the reader could not parse — refusal rather than guessing the reason or the cost",
    "remplace_vide": "\"what replaces it\" is missing — write the text, or literally AUCUN "
    "(a valid, free answer, just like AUCUN for Prérequis)",
    "remplace_illisible": "\"what replaces it\" contains a control character or exceeds "
    f"{_MAX_REMPLACE_CHARS} characters",
    "corbeille_existe": "a file with this name already exists in the trash — we never overwrite "
    "(inv. 2)",
}


class RetraitCorbeilleError(RuntimeError):
    """The move cannot be proven, or a required field is missing. Nothing is written."""


@dataclass(frozen=True, slots=True)
class RetraitTrouve:
    """One H1 retrait comment found on an item, already parsed — never re-derived twice."""

    id: str
    le: str
    motif: str
    cout: str


def retrait_trouve(item: PlanItem) -> RetraitTrouve | None:
    """Is ``item`` really retired BY H1 — and if so, what did H1 write? ``None`` when it is not.

    Asked of ``item.detail`` (the SAME indented block :func:`~.plan_format.read_plan` already
    folded for every other reader of this format) rather than a fresh line search: a second walk
    of "what sits under this bullet" is exactly the class of drift this repo has paid for once
    already (:func:`~.plan_format._item_block`, imported by nothing here on purpose — this function
    reads what the reader already read, not the raw file a second time).

    A ``clos`` item with NO such comment is not this module's business — a status can be closed for
    reasons that have nothing to do with H1, and moving one would delete a decision this module
    never made.
    """
    if item.status != "clos":
        return None
    for line in item.detail:
        found = _RETRAIT_COMMENT_RE.search(line)
        if found:
            return RetraitTrouve(**found.groupdict())
    return None


def _fold(text: str) -> str:
    """One string → one ASCII, lower-case, hyphen-joined fragment — same fold as `plan_archive._fold`,
    kept as its own tiny copy rather than imported: it is four lines with no state, and importing a
    leading-underscore helper for a fold this small would buy less than it costs to keep in step."""
    folded = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in folded if not unicodedata.combining(char))
    ascii_only = stripped.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-") or "item"


def retiree_filename(today: str, ident: str) -> str:
    """``retire-<AAAA-MM-JJ>-<ident>.md`` — the date first, so ``ls`` sorts the corbeille by when,
    the identifier rather than the title: an item's title can be edited, its identifier cannot
    (D166) — naming the file from the one thing that never changes is what makes ``ITEM=`` on the
    CLI and the file `ls` shows name the SAME retirement without a lookup."""
    return f"retire-{today}-{_fold(ident)}.md"


def _no_control_chars(text: str) -> bool:
    return all(ch == "\n" or ord(ch) >= 0x20 for ch in text)


@dataclass(frozen=True, slots=True)
class RetraitRefus:
    """One named reason this move will not happen."""

    reason: str
    detail: str

    @property
    def label(self) -> str:
        return REFUSAL_LABEL[self.reason]


@dataclass(frozen=True, slots=True)
class RetraitDeplacement:
    """One item that WOULD move — everything :func:`retiree_text` and the pointer need, computed
    once so the report the operator reads and the bytes actually written can never say two
    different things."""

    ident: str
    title: str
    #: Character offsets into the ARC text handed to :func:`plan_corbeille` — `text[start:end]` is
    #: the bullet line AND every indented line under it (H1's comment and the item's own detail
    #: included), exactly what `_item_block` already walks for every other reader of this format.
    start: int
    end: int
    body: str
    trouve: RetraitTrouve
    remplace: str
    filename: str
    link: str
    pointer: str


@dataclass(frozen=True, slots=True)
class CorbeillePlanning:
    """What one call WOULD do — computed whole, verified whole, written only after both pass."""

    source: str
    today: str
    original: str
    remaining: str
    move: RetraitDeplacement | None
    refusal: RetraitRefus | None

    @property
    def blocked(self) -> bool:
        return self.refusal is not None

    def corbeille_text(self) -> str:
        """The EXACT bytes that would land in the corbeille file — header, marker, then the body.

        The verifier reads the body back OUT of this string, not out of `move.body`: the thing
        proven must be the thing written (same discipline as `plan_archive.archive_text`).
        """
        assert self.move is not None  # noqa: S101 -- narrows for the type checker; callers check `blocked` first
        move = self.move
        header = "\n".join(
            [
                f"# Trash — {move.ident} · {move.title}",
                "",
                f"> Retired on {self.today} from `{self.source}`.",
                f"> H1 retirement: `{move.trouve.id}`, on {move.trouve.le}.",
                f"> **Reason** : {move.trouve.motif}",
                f"> **Cost** : {move.trouve.cout}",
                f"> **What replaces it** : {move.remplace}",
                ">",
                "> The body below is **the original text, byte for byte**: nothing has been",
                "> reworded, reordered or recompacted (the operator's rule 1). \U000026A0\U0000FE0F If this text carries a",
                "> RELATIVE LINK, it points at the ORIGINAL location — a link is never rewritten",
                "> here, so it may no longer resolve from this file.",
                "",
                "",
            ]
        )
        return header + VERBATIM_MARKER + move.body


def _pointer_line(ident: str, title: str, link: str, *, today: str) -> str:
    """The ONE line that stays in the arc where the item used to be — prose, never a bullet.

    Same shape as `plan_archive.pointer_line`, same reasoning (prose carries no key and no status,
    so it adds no item the reader could count), kept as a small local copy rather than a shared,
    parametrised call: `plan_archive.pointer_line` is not this module's file to widen for one verb.
    """
    return f"> **Retired on {today}** · {ident} · {title} → [{link}]({link})"


def plan_corbeille(
    text: str,
    *,
    source: str,
    ident: str,
    remplace: str,
    today: str,
    taken: frozenset[str] | set[str] = frozenset(),
    link_dir: str = RETIRES_DIRNAME,
) -> CorbeillePlanning:
    """Decide whether item ``ident`` can move to the corbeille, and what that would look like.

    Writes nothing. ``taken`` is the set of corbeille file names that already exist on disk, passed
    in rather than read, so the whole decision stays testable without a filesystem — same contract
    as `plan_archive.plan_archive`.

    Refuses, in order — the first to bite is the cause the operator reads, same discipline as
    `plan_archive.plan_archive`'s own ordering note: unknown item, then not really H1-retired
    (nothing to base a corbeille record on), then an unreadable H1 comment (refuse rather than
    guess at a motif or a cost), then the NEW field this module asks for, then the mechanical name
    collision last, because a name is fixable and the rest are not.
    """
    reading = read_plan(text)
    item = next((it for it in reading.items if it.ident == ident), None)
    if item is None:
        return CorbeillePlanning(
            source, today, text, text, None, RetraitRefus("item_absent", ident)
        )

    trouve = retrait_trouve(item)
    if trouve is None:
        has_comment_shape = any("<!-- RETRAIT" in line for line in item.detail)
        reason = "commentaire_illisible" if has_comment_shape else "pas_retire_par_h1"
        return CorbeillePlanning(source, today, text, text, None, RetraitRefus(reason, ident))

    if not remplace.strip():
        return CorbeillePlanning(source, today, text, text, None, RetraitRefus("remplace_vide", ident))
    if not _no_control_chars(remplace) or len(remplace) > _MAX_REMPLACE_CHARS:
        return CorbeillePlanning(
            source, today, text, text, None, RetraitRefus("remplace_illisible", ident)
        )

    filename = retiree_filename(today, ident)
    if filename in taken:
        return CorbeillePlanning(
            source, today, text, text, None, RetraitRefus("corbeille_existe", filename)
        )

    # The item's exact span: its bullet line (0-based index `item.line - 1`) plus every line under
    # it, walked with the SAME boundary `_item_block` uses (stop at the first line that is neither
    # blank nor indented) — not imported, because `item.line` already lets this walk the raw lines
    # directly without re-deriving the 1-based/0-based conversion `_item_block` hides internally.
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for raw in lines:
        offsets.append(offsets[-1] + len(raw))
    idx = item.line - 1
    start = offsets[idx]
    end = offsets[idx] + len(lines[idx])
    for raw in lines[item.line :]:
        if raw.strip() and not raw[:1].isspace():
            break
        end += len(raw)
    body = text[start:end]

    link = f"{link_dir}/{filename}" if link_dir else filename
    move = RetraitDeplacement(
        ident=item.ident,
        title=item.title,
        start=start,
        end=end,
        body=body,
        trouve=trouve,
        remplace=remplace.strip(),
        filename=filename,
        link=link,
        pointer=_pointer_line(item.ident, item.title, link, today=today),
    )
    remaining = text[:start] + move.pointer + "\n" + text[end:]
    return CorbeillePlanning(source, today, text, remaining, move, None)


def verify_roundtrip(planning: CorbeillePlanning) -> None:
    """Prove the move loses NOTHING, or raise — `plan_archive.verify_verbatim_roundtrip` on it.

    Fail-closed on a planning that has nothing to prove: called on a refused planning, that is a
    caller error (the runtime layer must check `blocked` first), and raising rather than silently
    passing is what makes that mistake loud instead of a false green.
    """
    if planning.move is None:
        raise RetraitCorbeilleError(
            "no move to prove — this planning was refused, verifying it is a caller error"
        )
    move = planning.move
    try:
        verify_verbatim_roundtrip(
            planning.remaining,
            (VerbatimMove(move.ident, move.pointer + "\n", planning.corbeille_text()),),
            planning.original,
            marker_name="the pointer",
            container_name="the remaining arc",
            written_name="the trash",
        )
    except Exception as mismatch:  # noqa: BLE001 -- re-raised under this module's own error type
        raise RetraitCorbeilleError(str(mismatch)) from mismatch


def verify_readability(planning: CorbeillePlanning, *, role: str = ROLE_ARC) -> None:
    """What is left behind must still be readable IN ITS ROLE, and gain no new refusal.

    Same rule `plan_archive.verify_readability` applies to a whole archived section, asked here of
    an arc that lost one item: `unreadable_reasons` is the ONE home for "what does readable mean",
    never re-derived. An arc that had exactly one item and loses it becomes unreadable AS AN ARC —
    that is not this function inventing a rule, it is the reader's own rule, surfaced before a
    write rather than after one at the pre-commit hook.
    """
    if planning.move is None:
        raise RetraitCorbeilleError(
            "no move to verify — this planning was refused"
        )
    after = read_plan(planning.remaining)
    if reasons := unreadable_reasons(after, role=role):
        raise RetraitCorbeilleError(
            f"after retirement to the trash, this file would no longer be readable as "
            f"{role} ({' · '.join(reasons)}) — nothing has been written."
        )
    if not is_readable(after, role=role):  # pragma: no cover - unreachable if unreadable_reasons is empty
        raise RetraitCorbeilleError(  # noqa: TRY003
            "after retirement to the trash, this file would no longer be readable — nothing has been written."
        )
