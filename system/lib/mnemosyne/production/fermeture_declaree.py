"""P9 -- "declared CLOSURE <-> flipped glyph in the SAME commit", the PURE judge.

Surfaced by the sibling project's harvest of 2026-09-08, item `P9`. The gap is **admitted on both sides**:
`docs/postes/README.md`, in its section on WHO closes an item, writes verbatim *"**No mechanism in
this repository today refuses a closure glyph placed without proof, on an ordinary day.**"*
(A LINE RANGE used to stand here instead of the section name. It was already off by four after one
edit of that document -- a citation by line number is a cache of a derivative, and it ages away from
its source with the first paragraph anyone adds above it. The section title moves only when the
section does.), and on the sibling project's side it was
recommendation #6 of its own lessons-for-Mnemosyne document -- *the only one that asked for a
BARRIER*, still nonexistent 19 days later.

 **WHAT THIS BARRIER HOLDS, AND WHAT IT DOES NOT HOLD.** It does **not** judge whether a closure
is DESERVED -- `fermeture_isolee.py` already measured that this is out of a gate's reach
(*"a `*Done when*` clause, drawn from history, is a fact of JUDGMENT, not of FORM"*). It holds the
**AGREEMENT** between two things the same commit already carries: what its message SAYS and what
its diff DOES. A closure written at only one of the two places is, literally, a closure nobody can
find again.

## The population, REPLAYED BY THIS JUDGE over the whole history (2026-09-08)

 **The first figure I had written here came from a `grep` of my own, and it was WRONG** (106
moves, 5 + 1 refusals). Re-derived by **the judge's own accessor** (`mesurer` + `ecarts`, replayed
on every commit):

```
commits judged : 2 196
 carrying at least one status MOVE : 111
 carrying at least one CLOSURE (//… -> or ) : 100
 REFUSED by this barrier : 5 (5% of closures)
```

The five are real and none is a false positive: `138d51ed` (`A1`,`A2`), `a1e17b98` (`F1`..`F4`),
`793e0a65` (`E5`), `0f155dbc` (`B7`) close an item without ever writing it in the message;
`8dd7505f` declares `cloture(H5)` while adding only 43 lines of prose -- **`H5` stayed ``**,
verified on the bytes of `8dd7505f^`. *A wall: 5 catches, zero false positive measured.*

## The two directions of the arrow, and why both count

- `fermeture_declaree_sans_bascule` -- the message announces, the plan does not move: **the
 closure exists only in a conversation**, and this is the class `docs/postes/README.md` calls
 *"17 commits announcing an item, ONE box checked"*.
- `bascule_sans_declaration` -- the plan moves, the message stays silent: **an item is closed and
 nothing searchable says so.** This is the more frequent direction (5 out of 6 real cases) and
 the one no human reader catches, because there is nothing to read.

 **The second direction requires the ident to be named in the FULL message (subject + body),
never in the subject alone** -- measured before deciding: the subject-only rule refused **10**
commits, the full-message one refuses **4**, and the spared ones all named their item, in the
body. *Measure the population before imposing the convention.*

## A PURE judge -- the population is injected into it

No disk access, no `git`, no `os.environ`: the edge
(:mod:`~mnemosyne.runtime.fermeture_declaree_run`) reads the diff and the message, this module
decides. It reuses the repo's **only** status reader (`plan_format._read_item`) rather than
writing a second one: a second glyph parser would drift from the first, and that is exactly the
fault D163 names.

Decisions: D75 (nobody closes on their own word) · inv. 2 (non-destructive) · D117 (French prose).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from .plan_format import _BULLET_RE, _read_item
from .routage_journal import STATUTS_FERMES

#: The verbs by which a commit message DECLARES a closure, in the form `verb(IDENT):`.
#: Drawn from this repo's real history (`close(H5)`, `cloture(H5)`), never guessed -- and frozen
#: as a SET: swapping two verbs would leave an identical, silent count.
VERBES_DE_FERMETURE: Final[frozenset[str]] = frozenset(
    {"close", "clos", "clot", "cloture", "clôture", "ferme", "fermeture"}
)

#: `verb(IDENT)` -- the ident is taken as-is (no space, no parenthesis) because the shape of
#: idents varies from one repo to another (`H5`, `E2-veto`, `B6-bis`, `A02-2`) and an ident
#: pattern written here would be a SECOND home facing `plan_format`. What is read is whatever
#: sits between the parentheses; it is the measured move, never this pattern, that says whether
#: the ident exists.
_DECLARATION_RE: Final = re.compile(r"\b([A-Za-zÀ-ÿ]+)\(([^()\s]+)\)")


@dataclass(frozen=True, slots=True)
class Bascule:
    """The glyph movement of ONE ident between the before and after of the same commit.

    ``avant`` / ``apres`` carry the **status** (the vocabulary of `plan_format.STATUS_BY_GLYPH`),
    never the glyph: a status is what the rest of the repo compares, and two glyphs that differ
    only by a variation selector are the same status."""

    ident: str
    avant: str
    apres: str

    @property
    def vers_ferme(self) -> bool:
        """Does this movement CLOSE? -- entering :data:`~.routage_journal.STATUTS_FERMES` while
        coming from elsewhere. An item already `fait` that stays `fait` is not a closure, and a
        `clos` that goes back to `en_cours` is a REOPENING, which this barrier does not judge."""
        return self.apres in STATUTS_FERMES and self.avant not in STATUTS_FERMES


@dataclass(frozen=True, slots=True)
class Ecart:
    """A named disagreement between the message and the diff. ``genre`` is one of the two
    directions of the arrow; ``ident`` is always the item's, so a refusal can be located."""

    genre: str
    ident: str

    @property
    def phrase(self) -> str:
        if self.genre == "fermeture_declaree_sans_bascule":
            return (
                f"{self.ident} : the message DECLARES the closure, the plan does not carry it — "
                "flip the glyph in THIS commit, or do not announce the closure"
            )
        return (
            f"{self.ident} : the glyph FLIPS to closed, the message does not name the item — "
            "name it in THIS commit's message"
        )


def statuts(lignes: tuple[str, ...]) -> dict[str, str]:
    """``ident -> status`` for the top-level bullets of a set of markdown lines.

 The lines arrive **without** the diff's `+`/`-` prefix: stripping it is the edge's job,
 because it is the edge that knows which diff they come from. An empty ident (notation
 `- [x] …`, no key) is ignored: the barrier compares identities, and an anonymous checkbox
 carries none -- ignoring it is a refusal to guess, not an oversight."""
    trouves: dict[str, str] = {}
    for numero, ligne in enumerate(lignes, start=1):
        puce = _BULLET_RE.match(ligne)
        if puce is None or puce.group(1):
            continue
        item, _, _ = _read_item(puce.group(2), line_no=numero)
        if item is not None and item.ident:
            trouves[item.ident] = item.status
    return trouves


def bascules(avant: dict[str, str], apres: dict[str, str]) -> tuple[Bascule, ...]:
    """The status movements between two states -- an ident present on both sides whose status
 changed. Sorted by ident so a refusal is reproducible.

 An ident that **appeared** (absent from ``avant``) is not a move: an item written as `` on
 the first pass closed no prior work, and requiring it to be named would turn the barrier into
 a drafting rule. A **disappeared** ident is not one either -- that is a removal, judged
 elsewhere (`plan_retrait.py`), and sticking a refusal on it here would judge the same class
 twice."""
    return tuple(
        Bascule(ident=ident, avant=avant[ident], apres=apres[ident])
        for ident in sorted(apres)
        if ident in avant and avant[ident] != apres[ident]
    )


def idents_declares(message: str) -> frozenset[str]:
    """The idents whose closure the message ANNOUNCES, in the form `verb(IDENT)`.

    Case-insensitive on the verb only: `Close(H5)` announces, `CLOSE(h5)` announces the closure
    of `h5` -- the ident is never normalized, because it is a plan's key and folding it here would
    make it diverge from `plan_format`."""
    return frozenset(
        trouve.group(2)
        for trouve in _DECLARATION_RE.finditer(message)
        if trouve.group(1).lower() in VERBES_DE_FERMETURE
    )


def nomme(message: str, ident: str) -> bool:
    """Is ``ident`` cited in ``message`` as a whole word?

 The boundaries are `[\\w-]`, not `\\b`: with `\\b`, `B6` would match inside `B6-bis`
 and a move of `B6` would pass on the mere mention of its neighbor. *Checking a value does not
 protect the site that uses another.*"""
    return re.search(rf"(?<![\w-]){re.escape(ident)}(?![\w-])", message) is not None


def ecarts(message: str, mouvements: tuple[Bascule, ...]) -> tuple[Ecart, ...]:
    """The verdict: the two directions of the arrow, in order (declared first, flipped next).

 **The ORDER of the two loops is deliberate**: a closure declared and never carried is the
 most expensive fault (it leaves a plan that lies); publishing it first keeps a reader from
 stopping at the first gap and believing the only problem is a poorly worded message."""
    fermes = frozenset(b.ident for b in mouvements if b.vers_ferme)
    trouves = [
        Ecart("fermeture_declaree_sans_bascule", ident)
        for ident in sorted(idents_declares(message))
        if ident not in fermes
    ]
    trouves += [
        Ecart("bascule_sans_declaration", ident)
        for ident in sorted(fermes)
        if not nomme(message, ident)
    ]
    return tuple(trouves)


def resume(mouvements: tuple[Bascule, ...], trouves: tuple[Ecart, ...]) -> str:
    """The published text. It ALWAYS names the compared population -- *an equality over zero pairs
    is true by construction*, and a "no gap" without its cardinal would be exactly that green."""
    fermes = sum(1 for b in mouvements if b.vers_ferme)
    entete = (
        f"declared closure ↔ flipped glyph : {len(mouvements)} status movement(s), "
        f"{fermes} of them to a CLOSED status"
    )
    if not trouves:
        return f"\U00002705 {entete} — full agreement.\n"
    lignes = [f"\U000026D4 {entete} — {len(trouves)} gap(s):"]
    lignes += [f"   · {e.phrase}" for e in trouves]
    return "\n".join(lignes) + "\n"
