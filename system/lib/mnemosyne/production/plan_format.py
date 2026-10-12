"""The imposed project plan format - one FOLDER, one reader, no second source (the user, 2026-07-28).

**A plan is a folder, not a file** - the user reversed his own choice of the previous day on
2026-07-29 (D166): *"folder, folder, folder for plans. I am changing my mind. This is fundamental,
folder."* His reason is scale, and the measure agreed with him before he said it: no mature project
of this repo has ever kept its plan in a single file, and this repo's own plan went from 191 to 1310
lines in two days - a session working ONE arc paid for the whole project to read it. A door
(``PLAN.md``) carries the cap and the index; ``plan/`` beside it carries one file per arc; any folder
with a door is a plan, at every level. Recursion is PERMITTED and never imposed: a single-file plan
is the floor, not a degraded case.

Nothing of the reader below changed shape for that. :func:`read_plan` is still PURE over bytes, which
is exactly what made the move possible - the folder lives in the callers, and what they hand back
here (:func:`merge_plan`) is the same :class:`PlanReading` every consumer already knew.


The user asked for it in his own words: *"I would like it to be imposed on every project we build
[...] so we can see, continuously, even when the project is done by a frontier, where things
visually stand. A way of writing things in a folder needs to be imposed on frontiers so it can be
carried over to the UI easily."* This module is the reader that makes that possible: it turns
a project's ``PLAN.md`` into items a machine can display, WITHOUT the project keeping a second,
machine-only copy of its own state.

**Why markdown and not YAML/JSON - measured, not preferred.** Another project kept exactly that second
copy (``state/registres/chantiers.yaml``). Its own ``meta.role`` field records what happened: *"this
field announced 'the 17 still-blocking defects' and 'FIVE bodies of work' when the file listed SEVEN
workstreams and the counter found TWENTY-ONE"* - four hand-copied numbers for one quantity, none of
them read by any control. The repair that project landed is the rule this module enforces:
**a computed number cannot rot, a copied one does it in three days.** So the human prose and the
machine's input are the SAME BYTES, and no total is ever written by hand.

**Three outcomes per line, never two.** A line is read as an item, REFUSED with a named reason, or
counted as prose. The third one is why :class:`PlanReading` carries ``prose_lines``: "8 items" printed
about a 500-line file looks like success while 98 % of it was invisible. A control that only sees what
IS cannot see what is MISSING, so the residual is published, never swallowed.

**What is imposed is deliberately small** (a door slower than the wall is never used): the file's
NAME and place, one ``**Cap** :`` line, and a status carried BY each item. Everything else - prose,
tables, quotes, sub-bullets, sections - stays free and is simply not read. Two notations are accepted
for an item, because two are what frontier agents already write in this repo (measured on five
pre-existing plans): plain markdown checkboxes, and a glyph form. The checkbox form is the FLOOR, not
the ceiling.

**The vocabulary grows from USE, never from imagination.** The glyph form started with four statuses
and now carries six, and the two additions were not designed: they were READ OFF the living plan,
which had already written them where this reader is blind (an H2 heading, two table cells, one bullet
behind a token the reader could not parse). A format whose writers keep expressing a state it refuses
does not keep them disciplined - it pushes the state out of the machine's reach, silently.

Code, docstrings and everything the operator reads are English (D117). What stays French is DATA and
only data: the status TOKENS, the field NAMES (``Produit``, ``Fini quand``, ``Dépend de``,
``Prérequis``, ``À lire``, ``Taille``…) and the prerequisite vocabulary (``AUCUN``, ``OWNER``,
``MONDE``, ``AUTRE-PROJET``) are what the reader looks for LITERALLY in a plan — translating one
would make the writer emit a line the reader refuses.
Decisions: D100 (structural over discipline) - D92 (propose, never impose - this reads, it never
writes) - invariant 2 (non-destructive: a pure reader).
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Callable, Iterator
from itertools import takewhile
from dataclasses import dataclass
from typing import Final

#: The imposed file name, at the root of a project folder. Fixed so the UI finds it without being
#: configured per project — a location that must be declared somewhere is a location nobody declares.
PLAN_FILENAME: Final = "PLAN.md"

#: Where the arcs of a plan live: a directory NEXT TO the door, one file per arc (D166, clause 2).
#: The shape was measured, not invented — another project carries ``STATE.md`` + ``state/plans/`` and
#: is the only healthy planning corpus in this repo (1 orphan out of 28, against 25 out of 25 in the
#: trading chantier, which has no door at all).
ARCS_DIRNAME: Final = "plan"

#: The door names a plan root may carry, in order of preference. Two, and the second is the legacy
#: name Mnemosyne's own plan carried until C20-12 renamed it to its own top-level ``PLAN.md``; it stays declared
#: because another plan may still carry it. Declaring the
#: legacy name HERE is what lets there be one reader instead of two — the alternative, which this
#: repo lived with, was a whole second barrier written specially for the one plan that did not sit
#: under ``projects/``. A declaration ages loudly; a special case ages in silence.
DOOR_FILENAMES: Final = (PLAN_FILENAME, "PLAN_COURANT.md")

#: The three ROLES a markdown file can play, and the reason ``readable`` had to split (D166,
#: clause 6). One text used to have to carry a cap AND items to be readable, which made a door
#: (cap, no item) and an arc (items, no cap) BOTH unreadable — the mono-file assumption, sitting in
#: a single boolean read by three consumers. The rule now depends on what the file IS.
ROLE_PORTE: Final = "porte"
ROLE_ARC: Final = "arc"
ROLE_PLAN: Final = "plan"

#: The statuses, glyph -> token. ``pret`` is the user's own distinction ("a thing to set up, not yet
#: under way") and it is the one plain markdown cannot express: a heavy run that is BUILT and TESTED
#: but waits for his gesture is neither done nor to-do, and showing it as to-do hides that it is ready.
#:
#: ``clos`` and ``en_pause`` were added the same way the first four were: by MEASURING what the
#: writers already do. On this repository's own top-level plan document the closure glyph ```` appears nine times and the
#: suspension glyph ```` once - and every single one of those ten sits where this reader is blind:
#: an H2 heading (``## ARC G - EN PAUSE``), two cells of a table, one bullet behind a token the
#: identity rule cannot parse, six indented prose blocks. Refusing a state does not stop it being
#: expressed; it only moves it out of reach. The two are a PAIR and the labels must not blur them:
#: ``clos`` means nothing will come back, ``en_pause`` means something will.
#:
#: ```` also lives in this repo as a PROSE marker ("my figure was wrong "), six times in
#: that same file. That costs nothing here - a glyph is only read as a status when it FOLLOWS a bold
#: token opening a top-level bullet - but it is why ```` in a table now flags that table as a
#: possible second source. A flag, never a refusal.
STATUS_BY_GLYPH: Final = {
    "\U00002B1C": "a_faire",
    "\U0001F504": "en_cours",
    "\U00002705": "fait",
    "\U0001F17F": "pret",
    "\U000026D4": "clos",
    "\U000023F8": "en_pause",
}
#: The labels - the only place a status becomes words. The operator reads these, never the tokens.
#: The KEYS are data (every consumer indexes on them); the VALUES are prose and are translated.
STATUS_LABEL: Final = {
    "a_faire": "to do",
    "en_cours": "in progress",
    "fait": "done",
    "pret": "ready — awaiting your gesture",
    "clos": "closed — will not be done, and that is decided",
    "en_pause": "paused — resumption expected",
}

#: **Delegated audit D75 (2026-08-17, `derives.py`/`PORTES_QUI_DECLARENT`) — RESERVATION R1,
#: VERIFIED AND DOCUMENTED HERE rather than "fixed": these four DOOR fields (`_TITLE_RE`, `_CAP_RE`,
#: `_SUCCEDE_A_RE`, `_FORMAT_RE`) do NOT call `_hors_citation`/`_hors_code` the way
#: `_field_declares` does for ITEM fields. Measured before writing this note rather than asserted:
#: their ANCHOR (`^\s*(?:>\s*)?`) already makes `_hors_citation`/`_hors_code` REDUNDANT for the two
#: cases they guard against in `_field_declares` — a marker between backticks or between quotation
#: marks CANNOT match these anchored regexes (the first non-blank character must be `*`, never
#: `` ` `` nor `«`/`"`), so quoting a door field in prose is ALREADY safe, with no dedicated guard
#: code. Locked down by
#: `test_un_champ_de_PORTE_cite_entre_backticks_ou_guillemets_ne_matche_JAMAIS` (`test_plan_format.py`).
#: **What STAYS open, and no syntax closes it** (the same admission as `_hors_citation`'s "BOLD
#: at the head"): a BARE prose sentence, with no backtick and no quotation mark, that opens ITS OWN
#: line with exactly `**Format** : …` — structurally identical to a real declaration. Not manifested
#: today (verified: that project's 14 real doors each return exactly 1 occurrence,
#: `/usr/bin/grep -c '\*\*Format\*\*'`); the remedy is the same one `_hors_citation` already wrote:
#: quote the field between backticks or quotation marks when TALKING about it.
_TITLE_RE: Final = re.compile(r"^#\s+PLAN\s*[—–-]\s*(.+?)\s*$")
_CAP_RE: Final = re.compile(r"^\s*(?:>\s*)?\*\*Cap\*\*\s*:\s*(.+?)\s*$")
#: H4 — a door's lineage: which frozen plan this one CONTINUES. Same pattern as `_CAP_RE` —
#: a DOOR field, optional (a plan with no predecessor does not carry it, `AUCUN` is not even
#: required), read ONCE, never looked up anywhere but the top of the document.
_SUCCEDE_A_RE: Final = re.compile(r"^\s*(?:>\s*)?\*\*Succède à\*\*\s*:\s*(.+?)\s*$")
#: D176 — a plan that is NOT Mnemosyne's own declares here EXACTLY the tokens of
#: :data:`FIELD_NAMES` it adopts (``produit, fini_quand``…), comma-separated. Same
#: pattern as `_SUCCEDE_A_RE` — a DOOR field, optional, read ONCE. See
#: :func:`champs_requis_pour`: it is the only thing this module reads to know "who adopted it".
_FORMAT_RE: Final = re.compile(r"^\s*(?:>\s*)?\*\*Format\*\*\s*:\s*(.+?)\s*$")
_SECTION_RE: Final = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_RE: Final = re.compile(r"^([ \t]*)[-*]\s+(.*)$")
_CHECKBOX_RE: Final = re.compile(r"^\[([ xX])\]\s*(.*)$")
#: A bold token opening a bullet. Matching it is NOT enough to call the line an item — see
#: :func:`_read_item`. Measured why: ``PLAN_INCARNATION.md`` opens 14 prose bullets with
#: ``- **Embodies** :`` / ``- **Deliverables** :``, and a reader that claimed those as malformed items
#: accused a perfectly good document 14 times. A catch rate without its false-kill rate is a wall.
_IDENT_RE: Final = re.compile(r"^\*\*([A-Za-z][A-Za-z0-9-]{0,11})\*\*\s*(.*)$")
#: What an IDENTITY looks like, as opposed to a word: letters then at least one digit (``A1``, ``D8``,
#: ``B6-bis``). Only an identity-shaped token may be REFUSED for lacking a status; a plain word is
#: simply prose. A bullet that carries a real status glyph is an item whatever its token looks like,
#: so naming an item ``**Foundation** `` still works — the digit rule closes a false accusation, it never
#: silences a line that declared a status.
_IDENTITY_RE: Final = re.compile(r"^[A-Za-z]{1,4}[0-9]+(?:-[A-Za-z]+)?$")
#: ANY bold token opening a bullet — deliberately permissive, and used ONLY to refuse-by-name a line
#: that carries a status glyph behind a token :data:`_IDENT_RE` cannot read. Never to build an item.
_BOLD_TOKEN_RE: Final = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$")
_TABLE_RE: Final = re.compile(r"^\s*\|.*\|\s*$")
#: An INDEX ENTRY in a door: a mention of ``plan/<something>.md``. Deliberately not a markdown link —
#: measured on that project, 75 of the 81 edges of its plan graph are bare filename mentions and only SIX
#: are real links, all inside one closed cluster. A rule demanding hand-written links would score
#: 6/81 on the best-kept project in the repo, so the form is free and only the COMPLETENESS is
#: checked. The character class stops at markdown delimiters, ``,``, ``;`` and newline but NOT at a
#: space or a ``:`` — 1775 of the 8165 paths under ``projects/`` carry a space and 9 carry a ``:``
#: (``Vpilot-S:S``), so a class excluding them would never SEE those entries, and a door pointing at
#: nothing would read as a door pointing at nothing wrong.
#:
#: The first captured character may not be whitespace, and that guard is what stops the space
#: tolerance from becoming a FALSE accusation. Without it an ordinary sentence — "the arcs live in
#: plan/ and the form is FORMAT_PLAN.md" — captures " and the form is FORMAT_PLAN.md" and the
#: door is refused for an index entry nobody wrote. A control that punishes correct use is a control
#: people delete. Residual limit, named rather than hidden: ``plan/x et ceci.md`` (no space right
#: after the slash) still matches. Measured on the six real plans of this repo: ZERO occurrences of
#: the whole pattern today — which is why the guard goes in BEFORE the first plan adopts the form.
#:
#: THE LEFT BOUNDARY IS THE WHOLE FIRST HALF OF THE RULE, and it was missing. ``plan`` must be a
#: COMPLETE path segment: without the lookbehind, every directory whose name merely ENDS in "plan"
#: was read as the arcs directory. That is not hypothetical — ``state/audits/fin-de-plan/`` exists
#: in that project, the very one D166 names as the model, and it took two of the ten false
#: accusations measured over the repo. ``ancien-plan/x.md`` and ``monplan/x.md`` fell the same way.
#: A path separator is NOT a word character, so ``some/plan/arc-c.md`` still matches: the boundary
#: rejects a longer SEGMENT, never a longer PATH.
_ARC_REF_RE: Final = re.compile(
    rf"(?<![A-Za-z0-9_.\-]){ARCS_DIRNAME}/"
    rf"([^\s`()\[\]|\"'<>\n,;][^`()\[\]|\"'<>\n,;]*?\.md)"
)

#: A fenced code block delimiter, with its RUN and its INFO STRING captured. Everything between an
#: opening fence and its matching close is an EXAMPLE, by definition: the page is showing what an
#: index looks like, not declaring one. ``docs/FORMAT_PLAN.md`` — the page that SPECIFIES this very
#: check — took two of its five false accusations from the ```markdown block it hands out for
#: frontiers to copy.
#:
#: THE CHARACTER AND THE LENGTH ARE PART OF THE RULE, and reading them is what separates this from
#: a parity toggle. A naive "every fence flips a boolean" mis-reads a page that wraps a ``` example
#: inside a ``~~~`` block — which is EXACTLY what a page documenting this format has to do to show
#: what a fenced example looks like: the inner ``` flipped the boolean back to "outside", every line
#: of the example became live text, and the page that specifies the check collected an
#: ``index_sans_fichier``. The symmetric silences came from the same toggle: one unclosed fence
#: turned the whole rest of the file into "inside a block" and switched the staleness check off
#: without a word. See :func:`_outside_code`, which closes both directions at once.
_FENCE_RE: Final = re.compile(r"^([ \t]{0,3})(`{3,}|~{3,})[ \t]*(.*?)[ \t]*$")

#: DELEGATED AUDIT OF 2026-08-15, OUTSIDE THE SCOPE OF A7 (G4, 5th round) — fixed anyway, cost
#: measured at ZERO across 1733 real documents. Opening a document-level comment used to require
#: STRICT column 0 when the fence, one layer up, tolerates `[ \t]{0,3}` per CommonMark. A draft
#: whose OPENER is indented (with its CONTENT staying at column 0) therefore escaped both
#: mechanisms at once — neither the document's (strict column 0) nor the item's (which only sees a
#: bullet's block) — and a column-0 bullet inside it could STEAL THE ID of a real item, causing
#: that item to be refused by an `id_duplique` accusing the innocent line. Same tolerance as the
#: fence, for the same reason: CommonMark, not a convention of its own.
_COMMENT_OUVRE_RE: Final = re.compile(r"^[ \t]{0,3}<!--")

#: A structural CONTAINER: the markers that open something a line can hold an entry IN — a list item
#: (quoted or not, numbered or not), an ATX heading, a link-reference definition, and the three HTML
#: tags that are the same three things written in HTML. Table cells are handled beside this, because
#: a pipe only opens a cell on a line that really is a table row.
#:
#: **Measured before it was written, over the 320 real markdown documents of this repo** (every
#: ``.md`` under ``docs/`` and under ``projects/``): the FIRST shipped pattern called every
#: ``plan/…md`` occurrence an index entry — **18 accusations, 18 false, 0 true**. The repair that
#: followed dug the symmetric hole: requiring a bare list marker plus a fixed decoration set made the
#: check see **0 declarations in the whole repo**, and blind to **20 of the 25 shapes a human writes**
#: — including the three shapes :func:`_read_item` reads as ITEMS. A control that condemns nobody
#: because it sees nothing is the same wall, turned around.
#:
#: NAMED alternatives rather than one opaque union, and the reason is a measured hole in the
#: SUITE rather than in this rule: the corpus of guilty shapes that defends this pattern could lose
#: a shape AND its frozen name in one two-line edit without a single test going red (60 witnesses out
#: of 60 left that way). A name here is a reference the suite can read and that lives OUTSIDE the
#: test file — so a shape that is the SOLE witness of one alternative can no longer be deleted in
#: silence. It is not a full freeze and the residual is stated where it is measured, in the suite.
_CONTAINER_PATTERNS: Final = (
    # a list item — bullet or numbered, quoted or not
    ("bullet", r"^[ \t]*(?:>[ \t]*)*(?:[-*+]|\d+[.)])[ \t]+"),
    ("heading", r"^[ \t]{0,3}\#{1,6}[ \t]+"),  # an ATX heading: `## plan/arc-c.md`
    ("reference link", r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*"),  # `[arc-c]: plan/arc-c.md`
    # The same three, written in HTML — but only where the line OPENS on tags. Left unanchored, the
    # ``<li>`` alternative made a SENTENCE quoting the tag ("the `<li>plan/x.md</li>` tags are
    # accepted") a declaration, which is the exact class this whole repair exists to close: a page
    # explaining the format would have been accused by the format. Other tags may precede it, so
    # ``<ul><li>plan/arc-c.md</li></ul>`` on one line is still an entry.
    ("HTML tag", r"^[ \t]*(?:<[A-Za-z/][^>\n]*>[ \t]*)*<(?:li|td|th)\b[^>\n]*>"),
)
_CONTAINER_RE: Final = re.compile("|".join(pattern for _, pattern in _CONTAINER_PATTERNS))

#: An HTML tag, opening or closing — used ONLY to read what FOLLOWS a path, never to find one.
#: ``<li>plan/arc-c.md</li>`` ends on a closing tag and is an entry; a tag is notation, not a word.
_HTML_TAG_RE: Final = re.compile(r"</?[A-Za-z][^>\n]*>")

#: An HTML ATTRIBUTE that holds a path — ``<a href="plan/arc-c.md">``. Anchored at the start of the
#: line for exactly the reason the ``<li>`` alternative had to be: unanchored, a sentence QUOTING the
#: tag ("you write `<a href='plan/x.md'>`") becomes a declaration, and the page explaining the
#: format gets accused by the format. The quote is what makes this need no tail rule at all: an
#: attribute value has a closing delimiter, so the path either fills it exactly or it does not.
_ATTR_ENTRY_RE: Final = re.compile(
    r"^[ \t]*(?:>[ \t]*)*(?:[-*+]|\d+[.)])?[ \t]*"
    r"(?:<[A-Za-z/][^>\n]*>[ \t]*)*<[A-Za-z][^>\n]*?\b(?:href|src)=(\"|')"
)

#: A table CELL boundary — but only on a line that really is a table row. The pipe alternative is
#: read only when the line OPENS with a pipe, which is how every table in this repo is written, and
#: the restriction is not cosmetic: a shell pipeline quoted in a sentence (``ls | plan/x.md``) would
#: otherwise present itself as a second cell. The reader already has a table predicate
#: (:data:`_TABLE_RE`); this one is deliberately looser at the end (a row being typed is still a row)
#: and stricter at the start.
_CELL_RE: Final = re.compile(r"\|[ \t]*")

#: A markdown link LABEL, up to the parenthesis that opens its target: ``[Arc C](``.
_LINK_LABEL_RE: Final = re.compile(r"\[[^\]\n]*\]\(")

#: Single characters that are NOTATION rather than content — the decorations, delimiters and
#: separators this repo really writes around a path. **Not one letter and not one digit is in this
#: set, and that is the whole boundary**: one word of prose in front of the path and the line is a
#: sentence, not an index. ``- the command `ls | plan/x.md` fails`` stops on the ``t`` of ``the``.
_NOTATION_CHARS: Final = frozenset("`*_\"'“”‘’«»()[]{}<>|,;:.!?/\\+=~#&-–—−·•…→⇒⟶ ")


def _is_notation(char: str) -> bool:
    """Is this single character NOTATION — a decoration, a separator, or a status glyph?

    ONE predicate, read by everything that walks characters around a path: :func:`_skip_notation`,
    :func:`_notation_run_before`, :func:`_notation_run_after`, :func:`_skip_tail`. It was written
    out four times before, and the fourth copy is exactly where a rule stops being enforced.
    """
    return char in _NOTATION_CHARS or char in _VARIATION_SELECTORS or _is_glyph_shaped(char)


def _skip_notation(text: str) -> int:
    """How many leading characters of ``text`` are NOTATION — never content, never a word.

 ONE vocabulary, read by BOTH halves of this module. :func:`_read_item` splits a bullet into its
 notation (a checkbox, a bold identity token, a status glyph) and its title with exactly these
 objects — :data:`_CHECKBOX_RE`, :data:`_BOLD_TOKEN_RE`, :func:`_is_glyph_shaped`,
 :data:`_VARIATION_SELECTORS` — and so does this. That is the point, not a coincidence: the two
 halves used to hold two different ideas of what a line is, and the three shapes the reader
 accepts as ITEMS (``- **ARC-C** `plan/arc-c.md```, ``- [ ] plan/arc-c.md``, ``- [x] …``) were
 MUTE to the index check. **138 of the 246 bullets of the repo's own living plan sat in that blind
 shape**, while the spec page told frontiers *"write your index as bullets if you want to never
 think about it again"*. Two definitions of "a line" inside one module is a guarantee of drift, so
 there is one.
 """
    pos = 0
    while pos < len(text):
        rest = text[pos:]
        if (link := _LINK_LABEL_RE.match(rest)) is not None:
            pos += link.end()  # `[Arc C](` — the label of a markdown link, never its target
            continue
        if (box := _CHECKBOX_RE.match(rest)) is not None:
            pos += box.start(2)  # `[ ]` / `[x]` — the same regex the reader builds an item from
            continue
        if (bold := _BOLD_TOKEN_RE.match(rest)) is not None:
            pos += bold.start(2)  # `**ARC-C**` — an identity, or a label; the reader reads both
            continue
        if _is_notation(rest[0]):
            pos += 1  # a decoration, a separator, or a status glyph — the reader's own predicate
            continue
        return pos
    return pos


#: Every refusal this module can name. Declared so the spec page and the reader cannot drift apart,
#: and — the part that matters — so each one can be shown to be PRODUCIBLE: a name is not a test, and
#: a refusal kind no input can trigger is a promise nobody keeps.
REFUSAL_KINDS: Final = (
    "statut_inconnu",
    "statut_manquant",
    "double_notation",
    "id_duplique",
    "identite_illisible",
    "arc_hors_index",
    "index_sans_fichier",
    "bloc_non_ferme",
    "arc_vide",
    "bloc_document_non_ferme",
    "commentaire_document_non_ferme",
    "succede_a_hors_porte",
)

#: The refusals the level-2 PREREQUISITE judge raises — :func:`prerequisite_problems`, and nothing
#: else. **Declared apart because merging them cost a lie that TRAVELS.**
#:
#: ``make plan-emit`` prints the whole of :data:`REFUSAL_KINDS` under the heading "The READER, on
#: the bytes" — so the two prerequisite refusals were emitted to every project as if
#: :func:`read_plan` raised them, which ``docs/FORMAT_PLAN.md`` denies in so many words. The emitted
#: contract also carries **zero** occurrences of the vocabulary that lifts them, so a frontier told
#: to apply it to the letter could not satisfy a refusal it was promised. *A wrong page is bad; a
#: wrong page that is EMITTED is the copy that outlives its original.*
#:
#: The split is the anchor, not the repair: the emitter belongs to another chat's lot, and one
#: line there (``READER_REFUSALS`` instead of ``REFUSAL_KINDS``) now makes its heading true.
PREREQUISITE_REFUSALS: Final = (
    "prerequis_manquant",
    "prerequis_inconnu",
)

#: The refusal the level-2 REQUIRED-FIELD judge raises — :func:`required_field_problems`.
#:
#: **ARMED as of 2026-08-15** — ``.githooks/pre-commit`` calls :func:`required_field_problems`,
#: with :func:`champs_requis_pour` as its scope. Cost measured before arming: **49 items, 0
#: refusals**; and the gate **BITES** — a real commit carrying an item stripped of four fields was
#: REFUSED, all four named.
#:
#: **This block said "PREPARED, NOT ARMED" for the entire time the gate was already refusing.**
#: The witness that guarded the deferral was indeed removed when arming; these lines here were not,
#: and an audit found that a reader of the code home would have concluded the exact opposite of the
#: truth. *A false comment is worse than no comment: it closes the question.*
REQUIRED_FIELD_REFUSALS: Final = ("champ_requis_manquant",)

#: What :func:`read_plan`, :func:`index_problems` and :func:`fold_plan` can raise — the refusals a
#: reader really produces from bytes.
READER_REFUSALS: Final = REFUSAL_KINDS

#: Every refusal any judge of this module can name. The union stays under the old name because the
#: spec page and three suites read it, and splitting a constant without keeping its union is how a
#: check quietly stops covering half of what it covered.
#: The refusals the ORDER judge raises. Imported by name rather than by module, because
#: :mod:`~mnemosyne.production.plan_ordre` imports THIS module and the reverse would be a cycle.
#: Declared here because an audit measured that a producer left OUT of the union escapes BOTH
#: gates at once — "every declared kind is producible" and "the spec page names them all".
ORDER_REFUSALS: Final = (
    "dependance_inconnue",
    "dependance_sur_soi",
    "liste_illisible",
    "cycle_de_dependances",
)

#: The refusal the REGISTRY raises when an arc exists and does not open. Declared here like the
#: others - it slipped past both gates, and for a reason worth writing down: it is built from a
#: CONSTANT (`ARC_ILLISIBLE`), not from a literal, so the control I had written to find missing
#: producers - a scan of the literals passed to `PlanProblem` - could not see it. *My own measuring
#: instrument carried the same blind spot as the defect it was looking for.*
REGISTRY_REFUSALS: Final = ("arc_illisible",)

#: The refusal the PRODUCT judge raises - :func:`produit_problems` (C2), split off like
#: :data:`PREREQUISITE_REFUSALS`: measured BEFORE writing it (55 real items, 2 name only a
#: folder, 30 cite no path at all - a wall demanding a path everywhere would refuse more than
#: half the plan). Deliberately NOT wired into `.githooks/pre-commit`: the clause exists, its
#: scope stays with the CALLER, exactly the doctrine :func:`prerequisite_problems` already set.
PRODUIT_REFUSALS: Final = ("produit_est_un_dossier",)

#: The refusal the FILIATION clause raises - :func:`~mnemosyne.production.plan_archive.
#: filiation_problems` (H4). Declared here like :data:`ORDER_REFUSALS`, for the same cycle
#: reason: `plan_archive` imports `plan_format`, never the other way around.
FILIATION_REFUSALS: Final = ("item_perdu_a_la_promotion",)

ALL_REFUSAL_KINDS: Final = (
    READER_REFUSALS
    + PREREQUISITE_REFUSALS
    + REQUIRED_FIELD_REFUSALS
    + ORDER_REFUSALS
    + REGISTRY_REFUSALS
    + PRODUIT_REFUSALS
    + FILIATION_REFUSALS
)


#: The two variation selectors, and NOTHING else. This used to drop every combining mark
#: (``unicodedata.category(ch) != "Mn"``), which is a far bigger net than the name promised — and it
#: reached the TITLE, not just the glyph: a plan written in NFD ("Économies" as ``E`` + U+0301) came
#: back "Economies", accents stripped, while the indented detail block below kept them. Four
#: non-NFC markdown files already live under ``projects/``. A filter whose name says "variation
#: selectors" must filter variation selectors.
_VARIATION_SELECTORS: Final = frozenset({"︎", "\U0000FE0F"})


def _despecify(text: str) -> str:
    """Drop variation selectors so ```` and ```` are the same glyph.

 Writers — human and model — emit U+FE0F inconsistently, and a status silently unread because of an
 invisible codepoint is the worst kind of hole: the plan looks written and the UI shows nothing.
 """
    return "".join(ch for ch in text if ch not in _VARIATION_SELECTORS)


def _is_glyph_shaped(char: str) -> bool:
    """Does this character SIT where a status glyph sits — a pictograph, not punctuation?

 This is what closes the reader's last silence. Being IN :data:`STATUS_BY_GLYPH` was the old test,
 so an unknown glyph behind an unreadable token matched nothing at all and the bullet vanished
 into prose with no item and no refusal — ``- **E2-vetoed** …`` on the living plan, absent from
 the items, absent from the refusals, on a plan the reader called readable.

 The net is Unicode's own class of pictographic symbols (``So``) — which is exactly what all six
 status glyphs are, asserted in the suite so the vocabulary can never outgrow the net. Its width
 was MEASURED before it was written, not after: over every markdown of this repo, among the
 bold-token bullets the reader treats as prose, the character following the token is ``So``
 exactly ONCE — the line above. One category wider (``Sm``) would have accused 194 more, 33 of
 them the ordinary ``- **X** → y`` sentence this repo writes everywhere; ``Sk`` would have added
 74 backticks. A catch rate without its false-kill rate is a wall, so both were measured.
 """
    return bool(char) and unicodedata.category(char) == "So"


#: THE SIX FIELDS an item may DECLARE — token → the name a human writes. **These names are DATA,
#: not prose: they stay French because the reader looks for them LITERALLY in a plan.** Translating
#: one here without translating every plan in existence would make this module refuse the very
#: documents it is meant to read. Four of them were
#: not designed here: another project invented ``Produit``, ``Fini quand``, ``Taille`` and
#: ``Dépend de`` while writing 168 items, and never brought them home. Two — ``Prérequis`` and
#: ``À lire`` — are missing everywhere and are the reason this reader exists rather than a convention.
#:
#: **The vocabulary grows from USE, never from imagination** — the rule this module already applied
#: to statuses, applied to fields.
#:
#: **THE POPULATION IS NAMED BECAUSE THE FIRST VERSION OF THIS BLOCK MIXED TWO.** The counts below
#: come from **the 2 389 markdown files of the repo** (everything outside ``.venv``); the numbers
#: first written here were measured over ``projects/`` and this repository's own ``plan/`` folder alone while the paragraph
#: beside them quoted a repo-wide total — 600 against 971, two populations under one label, caught by
#: an isolated audit. *A rate on the wrong population kills a good design*, and a count without its
#: command is a memory. The command:
#:
#: .. code-block:: bash
#:
#:     find . -name '*.md' -not -path './.venv/*' -print0 | xargs -0 /usr/bin/grep -hoE '\*Taille\*[ \t]*:' | wc -l
#:
#: ``*Taille* :`` 228 · ``*Produit* :`` 227 · ``*Fini quand* :`` 204 · ``*Depend de* :`` 173 ·
#: ``*Dépend de* :`` 47 · ``*Prérequis* :`` 46 · ``*À lire* :`` 46 — **971 in total**.
#:
#: ``Depend de`` outnumbers ``Dépend de`` **173 to 47**, which is why the NAME is matched with its
#: accents folded. That folding reaches the name and NOTHING else: this module already paid for a
#: filter whose net was wider than its promise (a plan written in NFD came back with its title
#: stripped of accents), so a VALUE is never normalised — it is kept as the author wrote it.
FIELD_NAMES: Final = {
    "produit": "Produit",
    "fini_quand": "Fini quand",
    "depend_de": "Dépend de",
    "prerequis": "Prérequis",
    "a_lire": "À lire",
    "taille": "Taille",
}

#: Fields the reader KNOWS how to read and does **not** oblige — the second half of a distinction
#: that has to be explicit, or the two collapse.
#:
#: :data:`FIELD_NAMES` is what item ``A1`` obliges, and it is what :attr:`PlanItem.missing_fields`
#: measures. THIS one is the grammar without the obligation: a plan may write these, the reader will
#: hand them over, and no item is ever short of one. Merging the two lists would have made every
#: capability that ever adds a field silently widen what every OTHER item must answer.
#:
#: **``Test à trois`` is here because a sibling chat had written a SECOND GRAMMAR for it** — its
#: own ``re.compile(r"^\s*\*Test à trois\*\s*:\s*(.*)$")``, plus a hand-rolled walk over
#: ``title`` + ``detail`` that skipped code fences by hand. That copy was already narrower than this
#: reader on the day it was written (it cannot see ``**Test à trois**``, nor a marker sharing a line,
#: nor the paragraph boundary), and *a contract with two homes is a contract whose copies drift*.
#: Measured: **48 of the 48 items** of this plan carry the field, so the grammar is not a curiosity.
#:
#: ``*Obligation*`` sits on the same 48 items and is NOT here — it belongs to another item, whose
#: owner has not asked. Nothing in this repo reads it in code today (measured: 0 sites). Naming the
#: gap rather than filling it: adding a field nobody asked for is how a vocabulary stops being read
#: by the people who own it.
#: **`obligation` WAS ADDED HERE ON 2026-08-15, AND SILENCE WAS THE DEFAULT.** `*Obligation*`
#: is declared by **45 of the plan's 50 items** and was known to no one: not being a
#: marker, it did not open a field — **its value was CONCATENATED onto the previous field's**,
#: and `missing_fields` stayed empty. *A field the grammar ignores does not disappear: it
#: moves in with its neighbor.* Measured: 45 values of `*Fini quand*` carried the obligation's
#: text, and the level-2 gate returned **0 refusals** — it could not see it.
#: **KNOWN, NOT OBLIGED** — this is the exact precedent for `test_a_trois`: the reader hands it
#: over, and no item is refused for not declaring it. *Making something readable is not making it
#: mandatory; conflating the two would have refused 5 items at once.*
#: And that is what makes `A2` verifiable: the three-level scale was **carved in but
#: illegible**, so nothing could check that an item declaring "level 2" really carried a
#: gate.
#: **``État du terrain`` added on 2026-08-15 (C2)** — KNOWN, NOT OBLIGED, the exact precedent for
#: ``test_a_trois``/``obligation``: the reader hands it over, no item is refused for not
#: declaring it. "Nothing occupies this role" is a VALID and REQUIRED answer (the same principle as
#: ``AUCUN`` for ``*Prérequis*``) — the field exists so that answer gets WRITTEN rather than left
#: silent: that project measures `P9` invisible to its own scheduling precisely because nothing
#: declares who, today, already occupies (or does not occupy) the role an item promises to fill.
#: **``Sert`` added on 2026-08-16 (G2)** — KNOWN, NOT OBLIGED, the same precedent as the three
#: above: *"a plan item that matches no citation is an idea of my own — legitimate,
#: but to be announced as such"*, never a refusal on its absence. `production/livrables.py` already
#: carries `juger_rattachements`/`rendre_rattachements` (commit `7efcf10`), built WITHOUT this
#: field — `item.field("sert")` was the only entry point they were missing, now added.
EXTRA_FIELD_NAMES: Final = {
    "test_a_trois": "Test à trois",
    "obligation": "Obligation",
    "etat_du_terrain": "État du terrain",
    "sert": "Sert",
}

#: Every field this reader can hand over — the six obliged plus the known. ONE dict, because the
#: parser and :meth:`PlanItem.field` must accept exactly the same set or a field would be readable
#: in one half and rejected in the other.
KNOWN_FIELDS: Final = {**FIELD_NAMES, **EXTRA_FIELD_NAMES}

#: THE CLOSED VOCABULARY of a ``*Prérequis*`` — token → **who can lift it**. The KEYS are data:
#: a plan writes them literally and :attr:`PlanItem.prerequisite` compares against them, so they are
#: never translated. Only the sentences beside them are prose.
#:
#: **A prerequisite is NOT a dependency, and the whole field exists to stop the two blurring.** A
#: ``*Dépend de*`` is a STEP of the plan and frees itself the day that step turns ````; a
#: ``*Prérequis*`` sits OUTSIDE the plan and **never frees itself** — someone has to go and do
#: something in the world. The user asked for it in his own words: *"when there is no prerequisite,
#: you just don't have one"*.
#:
#: **``OWNER`` IS A ROLE, NOT A NAME, and that is the whole answer to the three-form test.** Written
#: as a person, the field would be unreadable in the two other entrances this format must serve —
#: the extraction factory and Example Research have no such person. The token stays, the LABEL says what it means:
#: the human guardian of *this* project, whoever that is. And the distribution is not the same
#: everywhere: here the dominant prerequisite is ``OWNER``; at Example Research's ~1 500 plans it will be
#: ``AUTRE-PROJET`` — *the value that almost never fires here is the one that will carry the traffic
#: there*, which is exactly why the vocabulary is closed rather than sampled from this repo.
#:
#: ``AUCUN`` maps to the empty sentence because nobody has to lift it: **it is a valid and FREE
#: answer**, the same design as the lesson gate — one obliges the QUESTION, never the ANSWER.
PREREQUISITE_HOLDERS: Final = {
    "AUCUN": "",
    "OWNER": "this project's human guardian — they alone can lift it",
    "MONDE": "a state of the world — nobody here can lift it",
    "AUTRE-PROJET": "another project — it will lift there, never here",
}

#: The decorations a prerequisite may open with — quotes, emphasis, and the two invisible spaces.
_PREREQUISITE_DECORATIONS: Final = "*_`«\"'‘’“” \t\u00a0\u200b"

#: Unicode categories that are NOT content: format controls, combining and enclosing marks, modifier
#: and other symbols. **A CLASS, because enumerating the cases has now failed three times on this
#: one line.** First `` alone worked and `` did not (U+FE0F). Then `_despecify` closed those two
#: codepoints — and an audit walked in with EIGHT more: the zero-width joiner of ``‍‍``, a skin
#: tone (````), the keycap ``U+20E3``, the soft hyphen, the word joiner, ``U+FEFF``, ``U+034F``.
#: Two of them are not hypothetical — measured over the `.md` files git tracks, U+00AD sits in 34
#: and U+20E3 in 33. *Close the class, not the case*, owed for the third time here.
_NOT_CONTENT: Final = frozenset({"Cf", "Mn", "Me", "Sk", "So"})

#: Code points whose CATEGORY says "letter" (`Lo`) and that print **no glyph at all**.
#:
#: **FOURTH TIME I HAVE CLOSED THIS HOLE, AND THE FOURTH IS STILL A LIST.** A third party proved
#: `rc=0` on the real hook with `*Produit* : ㅤ` (`U+3164`): `isspace()` is **false**, the category
#: is `Lo`, so :data:`_NOT_CONTENT` — an enumeration of CATEGORIES — does not bite. The human, for
#: their part, sees `*Produit* :` followed by nothing.
#:
#: **AND I AM NOT CLAIMING THIS IS A CLASS.** The Unicode property that really describes them is
#: `Default_Ignorable_Code_Point` — **`unicodedata` does not expose it**. So there is no predicate,
#: in the standard library, for "does this character print a glyph". What follows is a **LIST**,
#: closed as of Unicode 15 for the known *fillers* only, and a code point added tomorrow will get
#: through. *The admission is worth more than a false barrier*: the command that re-derives it is
#: `grep 'Default_Ignorable_Code_Point' DerivedCoreProperties.txt` against the targeted Unicode
#: version.
#:
#: I had written in item `A1`: *"the judge now reads the same unicode category everywhere"*.
#: **That was FALSE**, and it took a third party to measure it — an unverified closing sentence
#: becomes the proof that nobody ever re-checks.
_SANS_GLYPHE: Final = frozenset("\u115f\u1160\u3164\uffa0")


def _opens_with_decoration(char: str) -> bool:
    """Is this character notation rather than the start of a token? Category, never a list."""
    return char in _PREREQUISITE_DECORATIONS or unicodedata.category(char) in _NOT_CONTENT


#: Characters that BELONG to a prerequisite token — letters of any script, digits, ``_`` and the
#: hyphen of ``AUTRE-PROJET``. Everything else ENDS the word.
#:
#: **THIS REPLACES A REGEX THAT CLOSED THE CASE AND LEFT THE CLASS OPEN — twice in a row.** The
#: first version was a bare prefix (``AUCUN2`` read as ``AUCUN``). The repair added a lookahead
#: ``(?![A-Za-z0-9_])`` and a second isolated audit walked straight through it two ways:
#:
#: * **backtracking on the hyphen** — ``[A-Za-z-]+`` can stop just before a ``-``, and ``-`` is not
#:   in the lookahead's class, so ``AUCUN-SAUF_SI``, ``AUCUN-BLOQUANT2`` and ``AUCUN-2026-08-13``
#:   all came back ``AUCUN``, **startable, zero refusals**;
#: * **an accent at the END** — the class was ASCII, so ``É`` did not close the word either:
#:   ``AUCUNÉ`` → ``AUCUN``, startable. The commit claimed a mis-accented ``AUCUN`` was refused; it
#:   was true for an accent in the MIDDLE and false for one at the end.
#:
#: So there is no prefix and no lookahead any more: the WHOLE word is taken and compared as it
#: stands. A rule that cannot express "prefix" cannot leak one. *Close the class, not the case* —
#: and this is the second time that lesson was owed on this very line.
#: **NO ACCENT FOLDING, and this is the OPPOSITE choice from the field NAME one screen above.**
#: A name is prose a human writes and ``Depend de`` really means ``Dépend de`` (173 against 47). A
#: token is a KEY: ``AUCÙN`` is a typo, not a spelling, and folding it silently repaired it into a
#: green ``startable``. Two questions, two answers — do not "harmonise" the two while tidying.
#:
#: **Residual, named: what FOLLOWS a correct token is free prose and is never parsed**, so
#: ``AUCUN, but actually OWNER must validate`` reads ``AUCUN``. That is the item's own decision (the
#: tail is for the human), and it is the author contradicting themselves rather than the reader
#: guessing — structurally the same shape as ``AUCUN — LIFTED on 2026-08-13.``, which must pass.
#: A value opening on a DIGIT is read as that digit (``1 **AUCUN**`` → ``'1'``, refused): the same
#: rule that catches ``AUCUN2`` cannot also decide that a leading digit was decoration.
_PREREQUISITE_WORD_CHARS: Final = frozenset("_-")

#: An emphasised token followed by a colon — ``*Produit* :``, ``**Fini quand** :``, ``_Taille_:``.
#:
#: **THE COLON IS THE WHOLE RULE, and it is a measurement rather than a taste.** Over the 2 389
#: markdown files of this repo the six names appear **971** times behind a colon, **172** times
#: inside backticks (``the `*Fini quand*` field``, a MENTION), and **110** times followed directly by
#: a word ("if the *Fini quand* is a command" — prose).
#:
#: A dash form exists — `` *Fini quand* — the command …`` — and it was measured before being
#: refused: **15 occurrences, 6 real declarations and 9 mentions**, a **60 %** false-accusation rate
#: on the increment ("the very heart of the *Produit* — has no…", "Look for a clause of the
#: *Fini quand*"). Admitting it buys 6 lines and fabricates 9 declarations nobody wrote. *A catch
#: rate without its false-kill rate is a wall* — so those 6 lines read as fields ABSENT, which is the
#: honest outcome: an absent field is NAMED, never guessed.
#:
#: **PUBLIC, and that is an arbitration rather than a style choice.** A sibling chat's already-CLOSED
#: clause reads this pattern to find a field on a line; it was reaching a PRIVATE name of this
#: module, which moved **three times** in one evening. *A closed item that depends on a private under
#: rewrite is a closure that can REOPEN without anyone deciding it* — and a closure silently undone
#: is worse than an item never closed, because the plan goes on claiming it is done.
#:
#: Being public makes it a CONTRACT: its two groups (the emphasis run, the name) are what callers
#: read, and narrowing them is a breaking change even though nothing outside this file says so.
#:
#: **The 9 mentions all carry a bare word in front, so :func:`_field_declares` would refuse them
#: anyway — which means the witness for this clause had to be built on one of the 6 TRUE lines**, a
#: pictograph in front and nothing else to catch it. Without that, an isolated audit showed the whole
#: suite staying green while the dash became a legal separator: the test passed for its neighbour's
#: reason, and the rule it claimed to freeze was loose.
FIELD_MARKER_RE: Final = re.compile(r"(\*{1,2}|_{1,2})([^*_\n]{1,16}?)\1[ \t]*:")


def _field_key(name: str) -> str:
    """Fold a written field name to its lookup key — accents dropped, case dropped, spaces collapsed.

    Applied to the NAME only, never to a value. ``Depend de`` and ``Dépend de`` are the same field
    (**173** occurrences against **47** in this repo); ``prevision`` and ``prévision`` inside a value
    are two different words and stay that way.
    """
    decomposed = unicodedata.normalize("NFD", name).lower()
    return " ".join("".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").split())


#: Every accepted spelling of every field, folded → token. Built from :data:`KNOWN_FIELDS` so a name
#: added there is readable immediately and cannot be admitted in one place and refused in the other.
_FIELD_BY_KEY: Final = {_field_key(name): token for token, name in KNOWN_FIELDS.items()}


def _ouvre_sa_ligne(line: str, position: int) -> bool:
    """Does the marker at ``position`` sit at the HEAD of its line, outside any indentation?

    That is the canonical form ``docs/FORMAT_PLAN.md`` imposes — and prose, for its part, never
    opens its line with a field marker. Used as the tie-breaker when a field is declared TWICE.
    """
    return not line[:position].strip()


def _regions_commentees(line: str, deja_ouvert: bool) -> tuple[tuple[tuple[int, int], ...], bool]:
    """The commented-out intervals of THIS line, and whether a region stays OPEN at the end.

 **MY FIRST VERSION ONLY LOOKED AT THE FIRST ``<!--`` OF THE LINE**, and gave up as soon as a
 ``-->`` appeared after it. Three routes reopened the hole because of that, two of them proven by
 REAL commits a third party got accepted:

 * ``<!-- note --> <!-- the six fields live here`` — the region was never opened;
 * a ``<!--`` sitting on the **bullet's own line** — the guard lived under ``if offset:``;
 * a ``\u0060<!--\u0060`` QUOTED ahead of the real one — ``find`` returned the quoted one, and the test collapsed.

 In all three cases the item showed **no field at all** and the gate accepted it.
 And the same fault produced a **FALSE REFUSAL** too: an item correctly declaring `AUCUN` whose
 block carried a comment of the 1st shape came out refused (`champ_duplique`), because the
 commented-out text became a second candidate. *Paying a refusal for having answered `AUCUN`
 contradicts "accepted and free" — and a false refusal in this gate stops three chats at once.*

 So the WHOLE line is swept, ignoring any opening or closing quoted inside a code span, and
 carrying the state from one line to the next.
 """
    regions: list[tuple[int, int]] = []
    ouvert = 0 if deja_ouvert else None
    index = 0
    while index < len(line):
        if line.startswith("<!--", index) and ouvert is None and _hors_code(line, index):
            ouvert = index
            index += 4
            continue
        if line.startswith("-->", index) and ouvert is not None and _hors_code(line, index):
            regions.append((ouvert, index + 3))
            ouvert = None
            index += 3
            continue
        index += 1
    if ouvert is not None:
        regions.append((ouvert, len(line)))
    return tuple(regions), ouvert is not None


def _hors_commentaire(line: str, position: int) -> bool:
    """Is the marker at ``position`` OUTSIDE an HTML comment closed ON THIS LINE?

 **I HAD CLOSED THE CLASS ON THE VALUE AND LEFT THE DECLARATION SIDE OPEN.** The walk already
 skips a comment that is **never closed** (it opens an ignored region); a complete ``<!-- … -->``
 sitting on one line was never skipped. The exact same asymmetry, **the same characters just
 moved**: ``*Prérequis* : <!-- AUCUN -->`` → **empty, REFUSED** · ``<!-- *Prérequis* : AUCUN -->``
 → **declared, 0 problem**.
 Consequence proven by a third party, **a REAL commit accepted**: an item whose **six** fields
 all live inside six one-line comments — so an item that shows **NO field at all** — clears the
 level-2 barrier without a word.
 Cost measured before arming it: **0 real declarations lost** across the whole corpus.
 """
    ouvert = None
    for index in range(position):
        if line.startswith("<!--", index):
            ouvert = index
        elif line.startswith("-->", index) and ouvert is not None:
            ouvert = None
    return ouvert is None


def _hors_citation(line: str, position: int) -> bool:
    """Is the marker at ``position`` OUTSIDE a quotation in French guillemets?

 Sibling of :func:`_hors_code`, same question, different punctuation: a ``«`` opened and not
 closed before the marker means a plan is being QUOTED, not written.

 **My backtick parity had closed THE CASE, not the class.** A third party, then the
 orchestrator, measured that ``"*Prérequis* : OWNER"`` in plain prose was still read as a
 declaration, and that the captured value came back as ``OWNER" was published startable…"``.
 Cost measured before arming it: **1007 real declarations intact · 9 quotations** stop being
 read as declarations — the 9 are audit reports quoting a plan.

 **WHAT STAYS OPEN, AND NO SYNTAX CLOSES IT: BOLD AT THE HEAD.**
 ``**Defect.** *Prérequis* : OWNER was read wrongly`` (a quotation) and
 ``**failure.** *Produit* : p`` (a real declaration, **61 real bullets** of this repo) are
 **structurally identical**. Telling them apart would take understanding the MEANING, not the
 form. *That half is not closed: it is written down.* The practicable remedy is to quote a field
 **between backticks or between quotation marks** when talking about it — both are now safe.
 """
    if line.count("«", 0, position) > line.count("»", 0, position):
        return False
    if line.count("“", 0, position) > line.count("”", 0, position):
        return False
    # The RIGHT double quote has no opening/closing form: its parity is the only signal.
    # The apostrophe `'` is deliberately ABSENT — the plans this reads are written in French, whose
    # elisions ("l'item", "qu'il") would flip half the corpus into "quoted". *A separator that lives
    # inside the language itself cannot double as a delimiter.*
    return line.count('"', 0, position) % 2 == 0


def _hors_code(line: str, position: int) -> bool:
    """Is the marker at ``position`` OUTSIDE a markdown code span?

 **SIMPLE PARITY WAS WRONG, and a third party proved it: a marker
 inside DOUBLE backticks**
 (double backtick, standard markdown, **589 files of this repo** carry that pattern) leaves an
 EVEN count and so passed for plain text. This now follows RUNS of backticks the way markdown
 does: a span opens on a run of N and closes on the next run of exactly N. It is the same
 *declaration vs. mention* distinction :func:`_field_declares` makes for fields — measured at its
 own expense: a DOCUMENTATION line quoting ``<!--`` opened a real comment and made the fields of
 the item carrying it disappear.
 """
    ouvert = None
    index = 0
    while index < position:
        if line[index] != "`":
            index += 1
            continue
        depart = index
        while index < len(line) and line[index] == "`":
            index += 1
        longueur = index - depart
        if ouvert is None:
            ouvert = longueur
        elif ouvert == longueur:
            ouvert = None
    return ouvert is None


def _ferme_reellement_un_commentaire(text: str) -> bool:
    """Does ``text`` carry the `-->` that really closes a document-level comment?

 **DELEGATED AUDIT OF 2026-08-15, IN `A7`'S CLAUSE — THIRD ROUND, NOT HELD (C2): THE SECOND
 ROUND'S FIX (C1) HAD MOVED AWAY FROM THE REFERENCE RIGHT WHERE `D1` HAD MOVED CLOSER TO IT.**
 Version C1 applied :func:`_hors_code`/:func:`_hors_citation` — the predicates that judge a FIELD
 MARKER quoted in French prose — to the closing of an HTML comment. But in HTML/CommonMark, a
 backtick or a quotation mark has **no special meaning INSIDE a comment that is already open**:
 it is the **FIRST** `-->`, full stop, that closes it — no exception. So the C1 fix manufactured
 FALSE NEGATIVES (a real `-->`, preceded on the same line by an unpaired backtick or quotation
 mark, stopped being recognised): the gate refused a legitimate commented-out draft (the very
 grievance that opened `A7`), and worse — a clean `-->` further down the document closed the
 comment TOO LATE, swallowing a real item in between, WITHOUT RAISING A SINGLE REFUSAL. The exact
 shape of `D2`'s damage, resurrected by `C1`'s own remedy.

 Back to the real rule: NO notion of quotation applies to CLOSING. Writing a literal `-->`
 inside a comment — even between backticks, just to talk about it — is a PROSE trap, not a
 READER defect: this repo knows that now (see the history of item `A7`, which had to rewrite its
 own prose to stop doing it).
 """
    return "-->" in text


def _field_declares(line: str, start: int) -> bool:
    """Is this marker a DECLARATION, rather than a field name quoted inside a sentence?

 **A MARKER BETWEEN BACKTICKS IS A QUOTATION — AND THIS MODULE KNEW THAT WITHOUT APPLYING IT.**
 `_hors_code` was written two hours earlier, to stop a quoted ``<!--`` from opening a real
 comment; it was never wired onto FIELD markers. Found by a third party, living in the repo: item
 `A3` declares ``*Prérequis* : AUCUN`` and the judge read **`OWNER`** — because a NARRATIVE line
 seven lines above quoted ``*Prérequis* : OWNER`` between backticks, and `field()` returns the
 FIRST one. **`A3` was published NOT STARTABLE and dropped from the queue by its own
 documentation.** The reverse direction is worse: prose quoting ``*Prérequis* : AUCUN`` above a
 real `OWNER` made the item startable **with the pre-commit green**.
 *Second time in the same session that a mechanism triggers on the very text describing it.*
 Cost measured before arming it, across the whole corpus: **1016 real declarations intact**, **36
 quotations** stop being read as declarations — and the 36 are audit reports and tables quoting a
 field.
 Decoration at the head (``…failure.** *Produit* : …``) remains PROOF of a declaration: 61 real
 bullets of this repo use it. It is not that which gets removed, it is the code span.


 The same question :func:`_declares` asks of a path, asked of a field, and answered with the same
 vocabulary — :func:`_notation_run_before`, this module's own idea of what a decoration is.

 Two ways to be one, and a space is NOT one of them:

 * **the marker opens its line** — `` *Produit* : …``, how a plan writes a field;
 * **a non-space decoration stands in front of it** — ``…failure.** *Produit* : …``, how that
 other project writes one mid-paragraph, which is the shape 61 top-level bullets of this repo really use.

 **A WORD AND A SINGLE SPACE IN FRONT MAKES IT A SENTENCE.** Measured over the 2 389 markdown
 files: the colon rule alone scores **971**, and exactly **14** of those carry a bare word in
 front — ``"`F3` says *Fini quand* :"``, ``"carries no token in its *Fini quand* :"``, and two
 tally rows of a report (``126 *Taille* :``). **All fourteen are mentions, none is a
 declaration**, so this guard costs nothing on the corpus and stops the reader publishing
 fourteen fields nobody wrote.
 """
    if not line[:start].strip():
        return True
    if not _hors_code(line, start) or not _hors_citation(line, start):
        return False
    if not _hors_commentaire(line, start):
        return False
    return any(not char.isspace() for char in _notation_run_before(line, start))


def _opens_a_new_block(line: str) -> bool:
    """Does this line START a new rhetorical block, rather than continue the sentence above it?

 **THE BOUNDARY IS A PICTOGRAPH AT THE HEAD OF THE LINE, and the narrowing to "pictograph" is a
 MEASUREMENT, not a taste.** This repo opens a new block with a glyph and a bold run — `` **…**``,
 `` **…**``, `` **…**``, `` **…**`` — and that is what has to close a field's value.

 Admitting a BARE ``**`` as well would cut deeper (98 over-long values down to 2, against 7) and
 it was refused on evidence: of five cuts sampled, **two were false** — an ordinary sentence
 wrapped by the editor onto a line that happens to begin with a bold run (``… counting the term
 across the repo yields`` / ``**one single meaning** (the rule of arc 00 F2) …``). Cutting there
 truncates a clause the author wrote as one. With the pictograph alone, **six sampled cuts out of
 six are correct** and every value kept ends on a closed sentence.

 The glyph must OPEN the line. Mid-line it is ordinary emphasis — ``third party. **The verdict…``
 sits inside the ``*Fini quand*`` of this very plan's ``A6`` and must NOT end it.
 """
    head = line.strip()[:1]
    return bool(head) and _is_glyph_shaped(head)


def read_item_fields(
    body: str,
    block: tuple[str, ...] = (),
    *,
    dupliques: list[str] | None = None,
) -> tuple[tuple[str, str], ...]:
    """The fields an item DECLARES, in declaration order — ``((token, value), …)``.

 ``body`` is the bullet's own text and ``block`` the RAW lines under it — blanks and fences
 included, exactly as :func:`_item_block` hands them over. A field is written in BOTH places and
 reading only one loses the other: **47 top-level bullets of this repo carry a field marker on
 the bullet line itself** (``- **A07-3** **…** *Produit* : …``), while this plan writes them
 underneath.

 **A VALUE IS A PARAGRAPH, NOT "EVERYTHING UNTIL THE NEXT FIELD" — and that mistake shipped
 here before an isolated audit measured it.** Closing a value only on the next marker read
 correctly for the marker and catastrophically for the prose: on the real corpus **235 values of
 665 ran past 400 characters and one reached 15 015**, an ``A03-20`` whose ``*Produit*`` is one
 sentence and whose published value swallowed four paragraphs and three code blocks. The
 docstring claimed to close exactly that defect while leaving it wide open — *a guarantee wearing
 a live name over a dead branch.* A value therefore ends at the FIRST of:

 * **the next accepted field marker** — 70 lines of this repo carry two or more;
 * **a blank line** — the author closed the paragraph;
 * **a fenced block** — and the fence's CONTENT is not scanned at all, which is the second half
 of the same repair: an item SHOWING the form to write (the pedagogical example ``make
 plan-emit`` hands to frontiers) had its example published as a real declaration, closing
 backtick included;
 * **a line opening on a pictograph** — :func:`_opens_a_new_block`, the measured boundary;
 * the end of the item's block.

 Measured after the repair, same corpus: over 2 000 characters, **98 values → 7**; the longest is
 **3 812** and is a genuinely long clause, not a swallowed one. Residual stated rather than
 hidden: a value written as several paragraphs with no glyph and no blank line between them is
 still read as one.

 Wrapping inside a paragraph is the editor's, not the author's, so newlines and indentation
 collapse to single spaces — the only normalisation, and what makes a value re-read identical to
 what was written on one line.

 **A field declared twice keeps the FIRST**, and the second's text is dropped rather than
 appended: an item that says ``*Produit*`` twice has two answers, and gluing them would invent a
 third. Measured on this corpus, repetitions are **0** — so the rule is pinned by a witness of
 its own rather than by the corpus, which cannot exercise it.
 """
    collected: dict[str, list[str]] = {}
    order: list[str] = []
    dupliques = [] if dupliques is None else dupliques
    open_token: str | None = None
    fence: tuple[str, int] | None = None
    in_comment = False
    for offset, line in enumerate((body, *block)):
        # The bullet's own line can carry neither a fence nor a paragraph break — it IS the head of
        # the block. Only the lines UNDER it can close a value.
        # **A REGION'S STATE MUST ADVANCE ON **EVERY** LINE.** This scan used to live further
        # down, AFTER the `continue`s that discard blank lines, tables and block openings — so it
        # never saw them, and a `-->` sitting on one of them was never read: the region stayed open
        # **until the end of the item**. Measured on a real arc: `B2` — whose comment contains a
        # table — lost **ALL** of its fields.
        # And I had concluded "it's not the scanner" by testing it OUTSIDE the walk, where these
        # `continue`s do not exist. *A component cleared by an isolated test can still be guilty
        # inside the loop that calls it: what changes it is not the component, it is what precedes
        # it.*
        regions, in_comment = _regions_commentees(line, in_comment)
        if regions and open_token is not None and regions[0][0] == 0:
            open_token = None
        if offset:
            # **CLOSURE IS JUDGED AFTER THE SCAN, NOT BEFORE.** These two `continue`s used to live
            # ABOVE it: a `-->` sitting on a closing line, or inside a closing, was never read, and
            # the region stayed open until the end of the item — **6 fields out of 6 lost**. This is
            # the very fault I had just fixed, **moved down two lines**. *A state that carries across
            # lines must advance BEFORE any `continue`, with no exception — where a scan sits is a
            # property of the LOOP, not of the scan.*
            # **A8, 2026-08-15: A NAIVE TOGGLE STOLE A FIELD IN SILENCE, ZERO REFUSAL.** This line
            # used to do `in_fence = not in_fence` on ANYTHING that looks like a fence, regardless of
            # character or length — so a ``` nested inside a ~~~ (the pedagogical example this format
            # must be able to show) closed at the wrong spot, reopened the example line as LIVE, and
            # *Produit* took its value. Same predicate as the document level
            # (:func:`_fence_ferme`, A7) — a SINGLE home, never a third version: same character, a
            # run at least as long, no info string.
            found_fence = _FENCE_RE.match(line)
            if found_fence:
                if fence is None:
                    fence = (found_fence.group(2)[0], len(found_fence.group(2)))
                elif _fence_ferme(found_fence, fence):
                    fence = None
                # else: a different character, a shorter run, or an info string — CONTENT of the
                # open block, not its closer (same branch as _scan_fences).
                open_token = None
                continue
            if fence is not None:
                continue
            # **A MULTI-LINE HTML COMMENT HID SIX FIELDS OUT OF SIX.** The reader saw an item
            # declaring NONE of them; the gate counted **6/6** and accepted the commit (`rc=0`,
            # proven on the real hook by a third party). I had removed the comment at the VALUE
            # level — the same `<!--` token, moved up by A SINGLE LINE, reopened everything.
            # The right place was right in front of me: this walk already skips ``` closures via
            # `in_fence`. **A comment is the SAME THING — a region markdown does not render** — and
            # it is skipped by the same gesture. *Closing a class at the value level when it lives
            # at the BLOCK level is closing the case once again.*
            # **AND A `<!--` BETWEEN BACKTICKS IS A MENTION, NOT AN OPENING.** First version
            # without this test: the very line where I DOCUMENT this fix in item `A1` opened a
            # comment and swallowed the item's fields — **four witnesses of this repo's arc turned
            # red at once.** *My own documentation was triggering my own fix.* This module already
            # asked the question for fields (`_field_declares`); here it is asked of the token, and
            # answered by the parity of the backticks that precede it.
            if not line.strip() or _TABLE_RE.match(line) or _opens_a_new_block(line):
                open_token = None
                if not FIELD_MARKER_RE.search(line):
                    continue
        cut = 0
        for match in FIELD_MARKER_RE.finditer(line):
            if any(debut <= match.start() < fin for debut, fin in regions):
                continue
            token = _FIELD_BY_KEY.get(_field_key(match.group(2)))
            if token is None or not _field_declares(line, match.start()):
                continue
            if open_token is not None:
                collected[open_token].append(line[cut : match.start()])
            cut = match.end()
            if token in collected:
                # **"FIRST ONE WINS" LET A QUOTATION STEAL A DECLARATION'S PLACE.** A third party
                # disproved my own admission — I had said no syntax distinguishes
                # `**Defect.** *Prérequis* : X` (a quotation) from a real, decorated declaration.
                # That is true AT THE LINE LEVEL, and false at the ITEM level: when the same field
                # is declared twice, the one that **OPENS its line** is the canonical form
                # `FORMAT_PLAN.md` imposes, and prose never opens its own line with a marker.
                # Cost measured by the third party over **2395 files · 1172 items: 0 items change
                # reading** — the 332 decorated declarations survive, because none of them coexists
                # with a canonical declaration of the same field. Gain: **8 of the 9 attack shapes**
                # fall, the BOLD shape included, as soon as the item carries its canonical
                # declaration.
                # **THE `champ_duplique` REFUSAL IS REMOVED, AND THAT IS AN ADMISSION.** It was
                # meant to punish prose that steals a declaration. Measured by a third party, it did
                # four wrong things and not one right one:
                # · it **refused the very remedy `FORMAT_PLAN.md` ORDERS people to write** — an item
                #   whose field is decorated and that ALSO adds the canonical declaration, exactly as
                #   the format requires, was REFUSED. **224 decorated declarations across 149 items**
                #   were one line away from this refusal;
                # · it was **not bounded**, when the whole of level 2 is: an item declaring NOTHING
                #   passed, an item **answering `AUCUN`** paid a hard refusal;
                # · its message was **wrong** — "declared twice at the head of a line" where neither
                #   of the two was: it sent people looking for two lines that did not exist;
                # · and it **did not protect the output**: `make plans`, the queue and `ui-json`
                #   publish at level 1, so the stolen value still circulated there regardless.
                # *A gate that refuses the correct gesture is removed, not patched.*
                # **WHAT IT LEAVES OPEN, WRITTEN DOWN RATHER THAN PROMISED CLOSED**: a **decorated**
                # quotation sitting above a real declaration still steals its value, because
                # `field()` returns the FIRST one. Closing that needs a signal that does not exist at
                # the line level; the arbiter I had tried was stillborn.
                open_token = None  # already answered — the repeat says nothing new
                continue
            collected[token], open_token = [], token
            order.append(token)
        if open_token is not None:
            collected[open_token].append(line[cut:])
    # **DO NOT STRIP HTML COMMENTS HERE.** I had done that, so the judge and the accessor would
    # read the same value — but `fold_plan` rewrites the document STARTING FROM HERE: the
    # byte-for-byte reconstruction witness turned red on the spot. Stripping at the assembly home
    # would have **DESTROYED 61 comments** in the user's files on the very first rewrite, without a
    # word. *The STORED value belongs to reconstruction; it is the JUDGE that must ignore the
    # invisible — cf. `PlanItem._sans_contenu`.*
    return tuple((token, " ".join(" ".join(collected[token]).split())) for token in order)


def _is_summary_table(raw: str) -> bool:
    """A markdown table row carrying a status glyph — a SECOND source of truth about state.

    One predicate, two readers: :func:`read_plan` subtracts these lines from the prose residual, and
    :func:`_detail_after` must skip the very same lines. When the two disagreed, an indented status
    table under an item landed in BOTH buckets and ``attached_prose <= prose_lines`` — documented as
    "a SUBSET, never a second bucket" and pinned by two tests — silently inverted.
    """
    return bool(_TABLE_RE.match(raw)) and any(g in _despecify(raw) for g in STATUS_BY_GLYPH)


@dataclass(frozen=True)
class PlanItem:
    """One readable item: its identity, its status, what it says, where it sits, and its detail.

 ``detail`` is what an interface needs to be worth opening. The user's own reason for imposing a
 format is *"so that it is easier to translate into something graphically nice"* — and a
 view that renders only titles is a list, not a view: ``D8 LE RUN COMPLET`` alone hides the nine
 lines saying it takes 9 to 18 hours and must not be chained with a preview. Those lines are the
 indented block under the item, kept verbatim; they stay counted in ``prose_lines`` because
 attaching a line does not make it an item.
 """

    ident: str
    status: str
    title: str
    section: str
    line: int
    detail: tuple[str, ...] = ()
    #: Which FILE of the plan this came from — ``""`` for the door, ``"plan/arc-c.md"`` for an arc.
    #: A plan is now a folder, so ``line`` alone stopped being a location: five arcs all have a
    #: line 12. Empty by default so every existing construction and every existing test still holds.
    source: str = ""
    #: What the item DECLARES, in declaration order — ``(("produit", "…"), ("taille", "…"))``. Added
    #: at the END of the field list on purpose: the **5** sites of this repo that build a ``PlanItem``
    #: do it positionally, and a field inserted anywhere else would have re-numbered them. (The "61"
    #: this comment first carried was the plan's count of sites READING ``PLAN_FILENAME``/``PlanItem``
    #: — a different quantity, borrowed for a claim it did not measure.) An
    #: item that declares nothing carries an empty tuple, exactly as it did before this existed.
    fields: tuple[tuple[str, str], ...] = ()

    @property
    def label(self) -> str:
        """The status in words — for anything a human reads."""
        return STATUS_LABEL[self.status]

    def field(self, token: str) -> str | None:
        """What this item declared for ``token`` — ``None`` when it declared NOTHING.

 **``None`` and ``""`` are not the same answer, and collapsing them is the defect this
 whole item exists to close.** ``None`` means the field is ABSENT; ``""`` means the author
 wrote ``*Produit* :`` and then wrote nothing. A reader that returned ``""`` for both would
 make an unasked question indistinguishable from an unanswered one — *two absences of
 measurement compare equal*, and the plan would look complete.

 Raises on an unknown token rather than returning ``None``: a typo'd field name silently
 meaning "absent" would let a caller check a field that does not exist and see green.
 """
        if token not in KNOWN_FIELDS:
            raise ValueError(f"unknown field: {token!r} (expected: {', '.join(KNOWN_FIELDS)})")
        return next((value for name, value in self.fields if name == token), None)

    @property
    def declared_fields(self) -> tuple[str, ...]:
        """The tokens this item declared, in declaration order."""
        return tuple(token for token, _ in self.fields)

    @property
    def missing_fields(self) -> tuple[str, ...]:
        """The fields this item NEVER declared, by their written name, in :data:`FIELD_NAMES` order.

 **This is the "named, never guessed" half of the format, and it is an ACCESSOR rather than
 a refusal.** The arc that asks for it rules that one obliges the QUESTION and never the
 ANSWER — a control demanding a quantity per record fabricates the content it demands, paid
 for in this repo at five invented clauses, two of them false. So an item short of a field is
 NAMED here, and what refuses is a barrier that reads this list, declares which fields it
 requires, and answers for its own false-kill rate.
 """
        return tuple(name for token, name in FIELD_NAMES.items() if self.field(token) is None)

    @property
    def prerequisite(self) -> str | None:
        """The ``*Prérequis*`` token, uppercased — ``None`` when the field was never declared.

        THREE outcomes, never two, and the third is the one an audit found unguarded:

        * ``None`` — the field was never declared;
        * a token — read as written, uppercased, **even when it is outside the vocabulary**, so
          :func:`prerequisite_problems` can NAME it. Collapsing "unknown" into "absent" would make a
          typo indistinguishable from a silence, and the two need different repairs;
        * ``""`` — the field is there and nothing readable opens it (declared empty, or opening on a
          pictograph). Distinct from ``None`` on purpose, and the refusal below QUOTES the raw value
          so the message accuses something rather than ``''``.

        The decorations stripped in front include the typographic quotes and the two invisible
        spaces (U+00A0, U+200B): each of them turned a perfectly legitimate ``AUCUN`` into a false
        refusal, and an invisible codepoint is the worst kind of hole — the plan looks written and
        the reader says the vocabulary was broken.
        """
        value = self.field("prerequis")
        if value is None:
            return None
        # ONE walk, over a CATEGORY — every decoration, every invisible, every pictograph, whatever
        # its codepoint. Three enumerations died here before this predicate existed.
        head = value
        while head and _opens_with_decoration(head[0]):
            head = head[1:]
        # **NO `rstrip("-")`.** It was added here with a justification that is measurably FALSE:
        # `AUCUN -- LIFTED` reads `AUCUN` with OR without it, because the walk stops on the SPACE. What
        # it really bought was `AUCUN-`, `AUCUN--` and `AUCUN- (unless OWNER validates)` becoming
        # STARTABLE — refused by the commit before it. A repair that reopens the permissive side is
        # worse than the defect it closes, and this line has now leaked that way four times running.
        return "".join(
            takewhile(lambda ch: ch.isalnum() or ch in _PREREQUISITE_WORD_CHARS, head)
        ).upper()

    @property
    def startable(self) -> bool:
        """Can work on this item BEGIN? Only ``AUCUN`` says yes.

 **An item that declares nothing is NOT startable**, and that asymmetry is the point. The
 alternative — silence meaning "go ahead" — is precisely *validating on a hypothesis*, which
 is the sentence this field exists to make impossible. An unasked question is not a lifted
 prerequisite.
 """
        return self.prerequisite == "AUCUN"

    @property
    def blocked_by(self) -> str:
        """WHO can lift what blocks this item — empty when nothing does.

        The sentence, not the token: a surface that prints ``OWNER`` tells a reader nothing about
        what to do, and *the refusal message must name the way out*. An undeclared prerequisite says
        so in full rather than borrowing one of the four answers.
        """
        token = self.prerequisite
        if token is None:
            return "prerequisite not declared — nothing says what blocks, so nothing starts"
        return PREREQUISITE_HOLDERS.get(token, f"unreadable prerequisite: {token!r}")

    @staticmethod
    def _visible(valeur: str) -> str:
        """The PRIVATE value of what markdown does not render — the only home of this question.

        The empty-value judge depends on it, and so do the witnesses that bound what a human reads:
        two ideas of "visible" in one repo, and the barrier would pick the weaker one.
        """
        # `html.unescape` BEFORE the judgement: `&nbsp;` and `&#8203;` are written as visible ASCII
        # and RENDER invisible — the gate was counting an answer where the reader sees nothing
        # (`rc=0` proven by a third party). Decoding brings them back to what the human will see,
        # and the empty-value predicate does the rest. **The other half — `<span style=
        # "display:none">todo</span>` — stays OPEN, and I am stating it**: stripping `<…>` tags
        # would eat a legitimate `<path>`, which would manufacture a FALSE REFUSAL — and a false
        # refusal in this gate stops all three chats at once. Between letting an invisible value
        # through and refusing a true one, this gate chooses to let it through, and says so.
        return html.unescape(_COMMENTAIRE_HTML.sub("", valeur))

    @staticmethod
    def _sans_contenu(valeur: str) -> bool:
        """Does the value carry NO content at all — including one made only of invisibles?

 **A THIRD SHAPE OF "PRESENT WITHOUT AN ANSWER", proven by two REAL commits accepted.**
 `blank_fields` used to compare against `""` after `" ".join(v.split())`, but `str.split()`
 does **not** cut on the `Cf`/`Mn` categories: a field holding a single `U+200B` (or
 `U+00AD`, `U+2060`, `U+FEFF`, `U+200D`, `U+034F`) was "filled in" for the gate and **EMPTY
 for the human**, who sees `*Produit* :` followed by nothing. Measured: 13 files of this repo
 carry U+00AD, 2 carry U+200B.

 **And the module already held the remedy, applied to a SINGLE field**:
 :data:`_NOT_CONTENT` makes the prerequisite judge refuse these same code points. *Two ideas
 of "does this field have an answer" in one module, and the barrier took the weaker one.*
 Now there is only one.
 """
        return not any(
            ch
            for ch in PlanItem._visible(valeur)
            if (
                not ch.isspace()
                and ch not in _SANS_GLYPHE
                and unicodedata.category(ch) not in _NOT_CONTENT
            )
        )

    @property
    def blank_fields(self) -> tuple[str, ...]:
        """The fields declared and left EMPTY — ``*Produit* :`` with nothing behind it.

        The third outcome this reader owes, beside declared and absent: a question asked and not
        answered is not the same as a question never asked, and only naming both keeps a plan from
        looking complete because every heading is present.
        """
        return tuple(
            name
            for token, name in FIELD_NAMES.items()
            if (value := self.field(token)) is not None and self._sans_contenu(value)
        )


@dataclass(frozen=True)
class PlanProblem:
    """One line that TRIED to be an item and was refused, with the reason named.

    A refusal is not a crash: the rest of the plan is still read. But it is never silent — an item
    whose status cannot be read is an item the UI would quietly drop, and a plan that quietly drops
    items is worse than no plan, because nobody can tell.
    """

    line: int
    kind: str
    detail: str
    #: The file the refused line sits in — ``""`` for the door. Same reason as :attr:`PlanItem.source`:
    #: "line 12 : statut_inconnu" is not a location once a plan spans five files.
    source: str = ""

    @property
    def where(self) -> str:
        """Where to go and look, in one string — the file when there is one, the line when there is.

        ``line == 0`` means the refusal is about the FOLDER, not about a line: an arc that exists and
        is named nowhere has no line to point at. Printing "line 0" was the shape of a refusal
        nobody can act on — it reads like a location and is not one. Seen in the hook's real output
        before it was fixed: ``line 0 : arc_hors_index -- plan/forgotten arc.md``.
        """
        if not self.line:
            return f"{self.source} (the folder)" if self.source else "(the plan folder)"
        return f"{self.source} line {self.line}" if self.source else f"line {self.line}"


@dataclass(frozen=True)
class PlanReading:
    """What one ``PLAN.md`` yielded — including everything that was NOT read.

    ``prose_lines`` and ``total_lines`` are here so no caller can print a count of items without being
    able to print what it ignored to get there.
    """

    project: str
    cap: str
    items: tuple[PlanItem, ...]
    problems: tuple[PlanProblem, ...]
    prose_lines: int
    total_lines: int
    #: ``(source, line)`` pairs -- the SAME shape as :attr:`PlanItem.source`/:attr:`PlanProblem.
    #: source`, for the SAME reason. **UNTIL 2026-08-16 THIS WAS ``tuple[int, ...]``, BARE LINE
    #: NUMBERS (BR3, measured before fixing).** ``items`` and ``problems`` are already qualified by
    #: file; this neighbour was not — three siblings merged by :func:`merge_plan`, two carrying their
    #: origin, one not. On a folder-form plan two files can each hold a table at their own line 12,
    #: and a caller reading the merged tuple could not tell which. Measured on the real corpus before
    #: fixing: **186 real entries** across four projects (Mnemosyne's own door included) — not a
    #: theoretical population. This repository's own UI-contract document already states the general rule for the two
    #: siblings this one had drifted from: *"the pair (file, line) is the location; the line alone
    #: is not, any more"*.
    summary_tables: tuple[tuple[str, int], ...] = ()
    #: The arc files merged into this reading, relative to the DOOR's folder (``plan/arc-c.md``) —
    #: the same namespace as :attr:`PlanItem.source`, and :func:`merge_plan` refuses any pair where
    #: the two disagree. Empty for a plan that is a single file. Published rather than counted so a
    #: report can NAME what it read: "4 arcs" cannot tell the user which one is missing.
    parts: tuple[str, ...] = ()
    #: H4 — the (verbatim, unresolved) reference of the frozen plan this one EXTENDS, from
    #: ``**Succède à** :`` at the head of the door. Empty for a plan with no predecessor — never
    #: required, the same as ``cap`` is: a first plan has nobody to file under.
    succede_a: str = ""
    #: D176 — the (verbatim, unresolved) adoption declaration from ``**Format** :`` at the head of
    #: the door. Empty for a plan that declared nothing — the default case, which must keep
    #: obliging NOTHING. See :func:`champs_requis_pour`, the sole reader of this field.
    format_declare: str = ""

    @property
    def readable(self) -> bool:
        """Readable AS A WHOLE PLAN: it names its cap and carries at least one item.

 Unchanged on purpose — for a plan that is one file this is exactly the old rule, and for a
 plan that is a folder this object IS the union (door + arcs), so "cap in the door, at least
 one item across the arcs" falls out with nothing to restate. What SPLIT off are the two
 rules below, for judging one file that is only PART of a plan.

 **`bool(self.cap)` WOULD HAVE CAUGHT ONLY HALF OF IT (BR1, 2026-08-16).** `_CAP_RE`
 captures ``(.+?)``, so ``**Cap** : `` returns ``' '`` — a space, TRUE for ``bool()``. This
 exact same defect was already closed for :func:`unreadable_reasons`/:func:`is_readable` (see
 their comment), which remain the REAL judgement path of this repo (``plan_registry.py``, the
 pre-commit hook) — but this property gave a SECOND, different, answer to the same question.
 *A contract with two homes drifts*, even when only one of the two is called in production:
 the second one stays readable, testable, and ready to mislead the next caller.
 """
        return not PlanItem._sans_contenu(self.cap) and bool(self.items)

    @property
    def readable_as_door(self) -> bool:
        """A door is readable when it names its cap. Its items are optional — they live in the arcs.

        See the warning on :attr:`readable` (BR1): same fix, same reason."""
        return not PlanItem._sans_contenu(self.cap)

    @property
    def readable_as_arc(self) -> bool:
        """An arc is readable when it carries at least one item. It has no cap — the door holds it."""
        return bool(self.items)

    @property
    def untracked(self) -> int:
        """Items with no identity — displayable, but impossible to follow across an edit.

        Surfaced rather than tolerated in silence: the plain-checkbox floor allows them (a frontier
        writing ``- [ ] do X`` is still writing a readable plan), but a UI cannot say "this one
        moved to done" about a line whose only key is its own wording.
        """
        return sum(1 for item in self.items if not item.ident)

    @property
    def attached_prose(self) -> int:
        """Prose lines that hang under an item, and are therefore renderable with it.

        A SUBSET of ``prose_lines``, never a second bucket — attaching a line does not claim it. The
        pair matters: it says how much of the reasoning an interface could show (attached) versus how
        much would stay invisible unless someone opens the file (the rest).
        """
        return sum(len(item.detail) for item in self.items)

    def by_status(self) -> dict[str, int]:
        """Item counts per status — COMPUTED here, so a plan never has to write a total by hand."""
        counts = dict.fromkeys(STATUS_LABEL, 0)
        for item in self.items:
            counts[item.status] += 1
        return counts


#: What each role REQUIRES, and the sentence said when it is missing. A mapping rather than
#: three ``if``s because the three consumers of the old boolean (``plan_registry``, the pre-commit
#: hook, ``plan_archive.verify_readability``) each carried their OWN hand-copied version of these two
#: sentences, in three slightly different wordings — a vocabulary copied three times is a vocabulary
#: that ages three ways. Splitting the rule without merging the copies would have made four.
#: **`titre` WAS MISSING HERE FOR 17 DAYS** — a field report from 2026-07-29 said so, and
#: clause 2 of `A4` requires it: *"every DOOR of this repo carries a non-empty `# PLAN — …` title"*.
#: The reader already READ it (`reading.project`); **nobody REQUIRED it**. Measured before arming
#: it: `# PLAN — ` (empty) · `# PLAN` (bare) · title made only of spaces · invisible title →
#: **readable=True** all four times. *An empty title reads as a valid plan.*
#: An ARC does not carry one: the requirement only holds for roles that have a DOOR.
_REQUIRED_BY_ROLE: Final = {
    ROLE_PORTE: ("titre", "cap"),
    ROLE_ARC: ("items",),
    ROLE_PLAN: ("titre", "cap", "items"),
}
_MISSING_SENTENCE: Final = {
    "titre": "no non-empty `# PLAN — …` title",
    "cap": "no `**Cap** :` line found",
    "items": "no readable item (a checkbox, or `- **ID** <glyph> …`)",
}


def unreadable_reasons(reading: PlanReading, *, role: str = ROLE_PLAN) -> tuple[str, ...]:
    """Why this text is not readable IN ITS ROLE — empty when it is. One rule, every consumer.

    ``role`` is the whole point: the same bytes are a fine DOOR and a hopeless ARC. Passing an
    unknown role raises rather than defaulting to something permissive — a typo'd role silently
    meaning "requires nothing" would turn this into a rubber stamp, and it would look green.
    """
    if role not in _REQUIRED_BY_ROLE:
        raise ValueError(f"unknown role: {role!r} (expected: {', '.join(_REQUIRED_BY_ROLE)})")
    # **`bool(reading.project)` WOULD HAVE CLOSED ONLY HALF OF IT.** `_TITLE_RE` captures `(.+?)`,
    # so `# PLAN — ` returns **`' '`** — a space, so TRUE. Measured: 2 of the 4 empty shapes would
    # have passed. The FIELD empty-value judge already handles spaces, invisibles and comments:
    # *two ideas of "empty" in one module, and the barrier takes the weaker one.*
    have = {
        "titre": not PlanItem._sans_contenu(reading.project),
        # **I CLOSED THE TITLE AND LEFT ITS NEIGHBOUR OPEN — the case, not the class, once more.**
        # `_CAP_RE` captures `(.+?)` exactly like `_TITLE_RE`: `**Cap** :   ` returns `' '`, so
        # TRUE. Measured: cap made only of spaces · invisible cap · cap made of a comment → **all
        # three passed**. And that is the very name of the field report that stayed open for 17
        # days: *"the plan reader accepts a blank cap"*. One single empty-value judge for both.
        "cap": not PlanItem._sans_contenu(reading.cap),
        "items": bool(reading.items),
    }
    return tuple(_MISSING_SENTENCE[need] for need in _REQUIRED_BY_ROLE[role] if not have[need])


def is_readable(reading: PlanReading, *, role: str = ROLE_PLAN) -> bool:
    """The verdict the three consumers share: readable in its role AND carrying no named refusal."""
    return not unreadable_reasons(reading, role=role) and not reading.problems


def _read_item(body: str, *, line_no: int) -> tuple[PlanItem | None, PlanProblem | None, bool]:
    """Read one top-level bullet. Returns ``(item, problem, claimed)``.

    ``claimed`` says whether the bullet even tried to be an item; a plain prose bullet is neither an
    item nor a problem — it is prose, and saying so is the third outcome this reader owes its caller.
    """
    checkbox = _CHECKBOX_RE.match(body)
    ident_match = _IDENT_RE.match(body)

    if checkbox:
        status = "fait" if checkbox.group(1).lower() == "x" else "a_faire"
        rest = checkbox.group(2).strip()
        inner = _IDENT_RE.match(rest)
        # A glyph BEHIND a checkbox is two statuses on one line. Guessing which one wins would make
        # the reader the author of a state nobody wrote — so the line is refused and named instead.
        #
        # ``inner and`` — the glyph must sit where a glyph is READ as a status, i.e. right after a
        # bold token. Without a checkbox, `- do X` is prose (the glyph notation needs its bold
        # token), so a glyph opening free text can never be "the other notation" and refusing it was
        # an asymmetry, not a rule. It cost a real item the moment the vocabulary grew: `- [ ] Read
        # **Ernie Chan "Quantitative Trading"**` in `example_research/ROADMAP.md`, written by another agent
        # months before this format, where `` means exactly the suspension now in the vocabulary —
        # phase 4 of a numbered list, put on hold. Adding the status would have DELETED the line.
        # The narrowing is named, not hidden: `- [x] done` is now the checkbox's `fait` with ``
        # left verbatim in the title. Population measured before the cut — repo-wide, exactly one
        # checkbox line opens on a status glyph, and it is that one.
        if inner and _despecify(inner.group(2).strip())[:1] in STATUS_BY_GLYPH:
            return None, PlanProblem(line_no, "double_notation", body[:60]), True
        named = inner is not None and _IDENTITY_RE.match(inner.group(1)) is not None
        ident, title = (inner.group(1), inner.group(2).strip()) if named else ("", rest)
        return PlanItem(ident, status, title, "", line_no), None, True
    if not ident_match:
        # A bullet whose bold token is not identity-shaped is prose — UNLESS it declares a status.
        # `_IDENT_RE` is ASCII-only, space-free and capped at 12 characters, so every one of
        # `**Étape 1** `, `**Infrastructure** `, `**Arc C** `, `**1A** `, `**A1_bis** `
        # fell through to prose and VANISHED — from a reader whose own docstring promises it "never
        # silences a line that declared a status", on a format being imposed on French plans. The
        # glyph is what separates an accusation from a false one: `- **Embodies** : …` still reads
        # as prose, because it declares nothing.
        #
        # `_is_glyph_shaped`, not `in STATUS_BY_GLYPH`: the membership test made this branch blind to
        # exactly the lines that need it most — a token the reader cannot parse AND a glyph it does
        # not know produced NO item and NO refusal, the only combination that was silent.
        loose = _BOLD_TOKEN_RE.match(body)
        if loose and _is_glyph_shaped(_despecify(loose.group(2).strip())[:1]):
            return None, PlanProblem(line_no, "identite_illisible", f"**{loose.group(1)}**"), True
        return None, None, False

    ident, rest = ident_match.group(1), ident_match.group(2).strip()
    identity = _IDENTITY_RE.match(ident) is not None
    if not rest:
        return (
            (None, PlanProblem(line_no, "statut_manquant", ident), True)
            if identity
            else (None, None, False)
        )
    # Clean ONCE and read both the glyph and the title off the same string: two independent calls to
    # _despecify made the one on the glyph an equivalent mutant (the variation selector trails the
    # base codepoint, so ``[:1]`` dropped it anyway) — dead guarantee wearing a live name.
    clean = _despecify(rest)
    glyph = clean[:1]
    if glyph not in STATUS_BY_GLYPH:
        # The second half of the same silence. `**Foundation** …` is READABLE as a key and DECLARES
        # something — it just declares a status nobody defined; before, only an identity-SHAPED token
        # (`A1`, `D8`) could be refused here, so a named-but-digitless token took an unknown glyph
        # straight to prose. Which of the two refusals is named depends on the ORDER of these checks,
        # and the order is deliberate: identity first, because a line whose token cannot be read
        # cannot be NAMED in a refusal, and a refusal nobody can locate is barely better than silence.
        if not identity and not _is_glyph_shaped(glyph):
            return None, None, False
        return None, PlanProblem(line_no, "statut_inconnu", f"{ident} → {rest[:12]!r}"), True
    title = clean[1:].strip()
    return PlanItem(ident, STATUS_BY_GLYPH[glyph], title, "", line_no), None, True


def plan_skeleton(project: str) -> str:
    """The smallest ``PLAN.md`` that is already readable — what a project starts from.

    Handed out rather than described, for the reason the whole format exists: an agent told to "write
    a plan in the imposed format" writes something slightly different every time, and the user cannot see
    a divergence until an interface shows him nothing. The suite parses this exact string, so the
    skeleton can never drift away from the reader that must accept it.

    It also carries the ADDRESSES of what Mnemosyne holds for a project agent (D163). This is the one
    place where that pointer is structural rather than disciplinary: the skeleton is what actually
    LANDS in a project folder, so the map arrives in the file the agent must open first. A project
    agent is right not to read Mnemosyne's directories — that would burn its context for nothing — so
    a document nobody points at is a document nobody reads.

    It stays a SINGLE FILE, and that is a decision rather than an omission. A plan of one file is the
    FLOOR of the format, never a degraded case: another project keeps 26 planning files flat and is the
    healthiest planning corpus measured in this repo (one orphan in 28), while the folder form exists
    for the day a plan stops fitting in one screen. Handing every brand-new project a ``plan/``
    directory and an arc would impose the recursion D166 deliberately left PERMITTED — so the birth of
    a project hands the floor, plus the ADDRESS of the two gestures that grow it (``make plan-emit``
    for the literal structure, ``make plan-nouveau`` for the code writing it).
    """
    return "\n".join(
        [
            f"# PLAN — {project}",
            "",
            "> **Cap** : (what we are trying to obtain right now, in one line)",
            "",
            "## To do",
            "",
            "- **A1** \U00002B1C (the first item)",
            "",
            "<!-- Statuses: \U00002B1C to do · \U0001F504 in progress · \U00002705 done · \U0001F17F\U0000FE0F ready, awaiting a human gesture",
            "               \U000026D4 closed, will not be done · \U000023F8\U0000FE0F paused, resumption expected.",
            "     The indented block under an item belongs to it. Form: docs/FORMAT_PLAN.md",
            "",
            "     What Mnemosyne holds FOR YOU, outside this folder (D163 — the address, not the copy):",
            "       make describe                what you have access to, before building anything",
            "       make plan-emit               the LITERAL structure of a plan — to apply, not to interpret",
            "       make plan-nouveau            this plan is growing? it becomes a FOLDER, and the code writes it",
            "       docs/FORMAT_PLAN.md          the form of THIS file",
            "       docs/signalements/README.md  Mnemosyne breaks? you REPORT it, you do not repair it (D153)",
            "       docs/parentheses/README.md   a detour opens? it lives BESIDE the plan, and it COMES BACK (C8-c) -->",
            "",
        ]
    )


def _detail_after(lines: list[str], item_line: int) -> tuple[str, ...]:
    """The indented block that belongs to the item declared at ``item_line`` (1-based), verbatim.

    Stops at the first line that is neither blank nor indented — the next top-level bullet, a heading,
    a table or a fresh paragraph. Kept verbatim rather than flattened so a renderer still has the
    links, the bold and the nesting the author wrote; a plan view is meant to be READ.
    """
    return tuple(
        raw
        for raw in _item_block(lines, item_line)
        # already counted as a summary table — collecting it too breaks the subset
        if raw.strip() and not _is_summary_table(raw)
    )


def _item_block(lines: list[str], item_line: int) -> tuple[str, ...]:
    """Every RAW line belonging to the item declared at ``item_line`` (1-based) — blanks included.

 **THE SINGLE ENUMERATION of what sits under an item**, and it exists because two halves of this
 module needed the same walk with two different filters. :func:`_detail_after` wants the prose a
 renderer can show, so it drops blanks and summary tables; :func:`read_item_fields` needs the
 blanks and the fences precisely BECAUSE they are where a value ends. Written twice, the two
 would have drifted — the defect this module already names about ``_is_summary_table`` and about
 ``parts``/``source``, both of which drifted the moment they existed in two places.

 **A10, 2026-08-17 — DECIDED BY THE USER (`(a)`): THE BOUNDARY WAS BLIND TO FENCES, NOT
 ONLY TO INDENTATION.** The old version broke on the first non-blank, non-indented line, EVEN
 when that line opened a fence — so a code block written at column 0 (legal: `docs/FORMAT_PLAN.md`
 forbids it nowhere) ended the item AT THE FENCE'S FIRST CHARACTER, and everything that followed
 — often `*Dépend de*`, written at the end of an item — silently disappeared. Measured before
 fixing: 1 item out of 66 at Mnemosyne (our fences are indented by habit), 108 out of 168 at
 that project (which does not indent them and yet violates no written rule).
 **The fix REUSES :func:`_scan_fences` — a single home, never a third version** of the
 CommonMark rule it already applies elsewhere in this module (:func:`_outside_code`,
 :func:`live_lines`, :func:`unclosed_fence_line`): a fence line, and anything living BETWEEN a
 correctly matched pair of fences, is never "live" — so it is never a candidate to close the
 block. The boundary does not change nature (still "the first non-blank, non-indented line"), it
 now only applies to LIVE lines: ``read_item_fields`` already matched fences correctly on what
 this block handed it — the inconsistency was not in its matching, it was that ``_item_block``
 never handed it anything to match in the first place.
 **A block that is never closed stays covered elsewhere, not here**: `_scan_fences` never
 closes an orphan fence, so this block then extends to the end of the file — exactly what
 `bloc_non_ferme` (a separate refusal, in `read_plan`) already does for this same class. Not
 restating it here avoids a third opinion on the same question.

 The boundary is now the whole contract with the ~113 sites reading ``detail`` (measured on this
 corpus, `system/lib/` + `tests/`, C9/A10 — a different count than the ~61 first cited, base
 published rather than reconciled): the block stops at the first LIVE line that is neither blank
 nor indented — the next top-level bullet, a heading, a fresh paragraph at column 0. A line inside
 a fenced block, open or closing it, is never live and never stops the block.
 """
    remaining = lines[item_line:]
    live, _ = _scan_fences(remaining)
    collected: list[str] = []
    for raw, est_live in zip(remaining, live):
        if est_live and raw.strip() and not raw[:1].isspace():
            break
        collected.append(raw)
    return tuple(collected)


def _sans_bom(text: str) -> str:
    """Drop a leading BOM. ONE function, because three judges must read the SAME bytes.

    ``\ufeff`` is not whitespace to Python, so ``text.strip()`` keeps it: an arc holding nothing but
    a BOM escaped ``arc_vide`` — the exact silence that refusal exists to close — and a BOM in front
    of a fence produced a false ``bloc_non_ferme``. The first fix landed in :func:`read_plan` alone,
    which made the reader and its sibling judges stop reading the same bytes. *A single home is only
    single if everybody goes through it.*
    """
    return text.lstrip("\ufeff")


def read_plan(
    text: str, *, origin: str = "", ident_seen: dict[str, str] | None = None
) -> PlanReading:
    """Parse a ``PLAN.md`` into items, refusals and residual — a PURE function over its bytes.

    Nothing here writes, and nothing here guesses: a line that does not match is prose, and prose is
    counted rather than dropped.

    ``ident_seen`` is the one thing that is not per-file, and it is passed IN rather than owned here
    (D166, clause 5). It used to be created inside this function, so ``id_duplique`` could only ever
    see one text — and cutting a plan into one file per arc would have made every cross-arc collision
    invisible, in silence, on the very edit that created the arcs. The caller that reads a whole
    folder threads ONE dict through every file, so the scope of a key is the PLAN. It stops there and
    goes no further: two different plans each carrying an ``S02`` is normal and must stay legal — at
    the scale this format is being built for, a hundred theories will each name a strategy ``S02``.

    ``origin`` names the file for the items and refusals produced here; it is what makes ``ligne 12``
    a location again once five arcs each have one. Both default to the single-file behaviour, so a
    caller that reads one file gets exactly what it got before.
    """
    # **THE BOM IS STRIPPED HERE, AND NOWHERE ELSE.** A leading `\ufeff` — which a Windows editor
    # or an export can plant ALL BY ITSELF — sticks to the title's `#`, so `_TITLE_RE` stops
    # matching and the plan silently loses its NAME: `readable` stays true (it only asks for the cap
    # and one item), `make plans` shows a nameless project, and nothing turns red. *"Nobody will
    # write that" is a property of the moment, not of the code.*
    #
    # Fixing it here rather than at the caller closes the CLASS: the two paths that turn plan
    # bytes into text — `plan_registry._read_text` (the disk) and `.githooks/pre-commit` (the git
    # index) — both decode as plain `utf-8`, and BOTH go through this function. A `utf-8-sig` in one
    # of them would have left the other open, and the next one born open too.
    lines = _sans_bom(text).splitlines()
    project, cap, succede_a, format_declare, section = "", "", "", "", ""
    items: list[PlanItem] = []
    problems: list[PlanProblem] = []
    ident_seen = {} if ident_seen is None else ident_seen
    tables: list[tuple[str, int]] = []
    claimed_lines = 0

    # **`A7` — THE READER HAD NO NOTION OF QUOTATION AT THE DOCUMENT LEVEL.** `A1` closed this
    # class at the ITEM level (a field marker quoted between backticks or inside a comment is no
    # longer read as a declaration); it stayed WIDE OPEN one floor above — here, where the question
    # is not "is this marker a declaration?" but "is this WHOLE LINE a plan, or the quotation of a
    # plan?". Measured, and reproduced by the orchestrator before this fix existed: a pedagogical
    # ```markdown block became a real item, and so did a draft parked inside a `<!-- -->` at column
    # 0 — and the commit gate refused the very document that EXPLAINS the format, citing the same
    # missing field names as a real, incomplete item. *A class closed at one floor stays open at the
    # floor above.*
    # And the SAME class bit a second, independent module two hours later (chat 2's obligation
    # registry): *"a pedagogical example is not an order, but nothing tells the two apart when they
    # share the same shape"* — the shape, precisely, is what this guard adds.
    #
    # **FIRST VERSION OF THIS GUARD: AUDITED, AND NOT HELD (2026-08-15).** An isolated third
    # party (D75) found two defects INSIDE the clause, both born of the same design mistake:
    # (D1) the toggle was a simple boolean, regardless of character or length — so a
    # ``` ```markdown ``` nested inside a ``` ~~~ ```, the shape `docs/FORMAT_PLAN.md` MUST use to
    # document itself, closed at the wrong spot and gave birth to a spurious item.
    # *That is exactly the class `_scan_fences` had already closed elsewhere — this guard carried a
    # SECOND, weaker, copy of it.*
    # (D2) the fence was tested BEFORE the comment state: an UNMATCHED fence inside a commented-out
    # draft (an ordinary pasted output excerpt) flipped `en_bloc_de_code` while still staying
    # "inside" the comment — the real `-->` then fell into `if en_bloc_de_code: continue` and was
    # never seen. **Both regions stayed open until the end of the file**, swallowing every real item
    # that followed, WITHOUT RAISING A SINGLE REFUSAL.
    # **Remedy: a single state, strict priority to whichever block is already open.** As long as a
    # comment is open, no line may open or close a fence inside it (and vice versa) — exactly what a
    # real Markdown parser does, where the block opened FIRST governs until ITS OWN closing. Closing
    # a fence reuses `_fence_ferme`, the same predicate `_scan_fences` uses — a single home for the
    # rule, two call sites.
    en_bloc_de_code: tuple[str, int] | None = None
    en_commentaire_colonne_0 = False
    ligne_ouverture_region = 0
    for offset, raw in enumerate(lines):
        line_no = offset + 1
        if en_commentaire_colonne_0:
            if _ferme_reellement_un_commentaire(raw):
                en_commentaire_colonne_0 = False
            continue
        if en_bloc_de_code is not None:
            found_fence = _FENCE_RE.match(raw)
            if found_fence is not None and _fence_ferme(found_fence, en_bloc_de_code):
                en_bloc_de_code = None
            continue
        found_fence = _FENCE_RE.match(raw)
        if found_fence is not None:
            en_bloc_de_code = (found_fence.group(2)[0], len(found_fence.group(2)))
            ligne_ouverture_region = line_no
            continue
        if _COMMENT_OUVRE_RE.match(raw):
            # DELEGATED AUDIT OF 2026-08-15, IN A7'S CLAUSE — FOURTH ROUND (F1). This site was
            # asking the question on `raw[4:]` (after `<!--`) while the continuation asks it on the
            # WHOLE `raw` — TWO strings for the SAME question. They only diverge on `<!-->` and
            # `<!--->` (an EMPTY HTML comment): their `-->` overlaps indices 0-3, and cutting at
            # index 4 splits it in two. `<!-->` therefore stayed open, swallowing every real item
            # that followed — WITHOUT RAISING A SINGLE REFUSAL. Two sites, one single question: `raw`.
            if not _ferme_reellement_un_commentaire(raw):
                en_commentaire_colonne_0 = True
                ligne_ouverture_region = line_no
            continue
        if not project and (found := _TITLE_RE.match(raw)):
            project, claimed_lines = found.group(1), claimed_lines + 1
            continue
        if not cap and (found := _CAP_RE.match(raw)):
            cap, claimed_lines = found.group(1), claimed_lines + 1
            continue
        if not succede_a and (found := _SUCCEDE_A_RE.match(raw)):
            succede_a, claimed_lines = found.group(1), claimed_lines + 1
            continue
        if not format_declare and (found := _FORMAT_RE.match(raw)):
            format_declare, claimed_lines = found.group(1), claimed_lines + 1
            continue
        if found := _SECTION_RE.match(raw):
            section, claimed_lines = found.group(1), claimed_lines + 1
            continue
        if _is_summary_table(raw):
            tables.append((origin, line_no))
            continue
        bullet = _BULLET_RE.match(raw)
        if bullet is None or bullet.group(1):
            continue
        item, problem, claimed = _read_item(bullet.group(2), line_no=line_no)
        claimed_lines += 1 if claimed else 0
        if problem is not None:
            problem = PlanProblem(problem.line, problem.kind, problem.detail, origin)
        if item is not None and item.ident and item.ident in ident_seen:
            # The unique-key check lives HERE, not in `_read_item`, because `_read_item` only ever
            # reached it down the GLYPH branch: `- [x] **C1** …` twice was read as two items with the
            # same identity and nothing said so. The ident is what an interface keys its list on, so a
            # collision silently renders ONE card. One notation caught, one not, is a closed case, not
            # a closed class.
            problems.append(
                PlanProblem(
                    line_no, "id_duplique", f"{item.ident} (already {ident_seen[item.ident]})", origin
                )
            )
            item = None
        if item is not None:
            block = _item_block(lines, item.line)
            detail = _detail_after(lines, item.line)
            items.append(
                PlanItem(
                    item.ident,
                    item.status,
                    item.title,
                    section,
                    item.line,
                    detail,
                    origin,
                    # The BULLET's own text, and the RAW block — not `detail`, which has already
                    # dropped the blank lines and the tables that are exactly where a value ends.
                    #
                    # Passing the body rather than `title` is a choice that CANNOT be measured
                    # from the outside, and saying so is the honest form: since `title` is never
                    # shortened, it still carries the marker, and reading either gives the same
                    # fields on all 1 106 items of this repo — 0 difference. The body is passed
                    # because it is what the line really said; the claim that the title "would have
                    # lost them" was false and is withdrawn.
                    read_item_fields(bullet.group(2), block),
                )
            )
            if item.ident:
                ident_seen[item.ident] = (
                    f"{origin} line {line_no}" if origin else f"line {line_no}"
                )
        if problem is not None:
            problems.append(problem)

    # DELEGATED AUDIT OF 2026-08-15, OUTSIDE A7'S CLAUSE (H-a) — fixed anyway: a document-level
    # region that was never closed swallowed the rest of the file IN SILENCE, without raising a
    # single refusal. Its twin — a fence that is never closed — already says "a mechanism that goes
    # quiet must be able to SAY it went quiet" (see `_scan_fences`); this guard was the exception to
    # it. An anchor that costs 0 today: measured, no document of the real corpus carries an open
    # document-level region at the end of the file.
    if en_bloc_de_code is not None:
        problems.append(
            PlanProblem(
                ligne_ouverture_region,
                "bloc_document_non_ferme",
                "code block never closed — everything after it stops being read",
                origin,
            )
        )
    if en_commentaire_colonne_0:
        problems.append(
            PlanProblem(
                ligne_ouverture_region,
                "commentaire_document_non_ferme",
                "comment never closed — everything after it stops being read",
                origin,
            )
        )

    return PlanReading(
        project=project,
        cap=cap,
        items=tuple(items),
        problems=tuple(problems),
        prose_lines=len(lines) - claimed_lines - len(tables),
        total_lines=len(lines),
        summary_tables=tuple(tables),
        succede_a=succede_a,
        format_declare=format_declare,
    )


def _same_name(left: str, right: str) -> bool:
    """Are these two the SAME file name? Compared in NFC, because macOS answers NFD.

    Not a nicety: 80 paths of this repo are stored decomposed, so a door written ``plan/économie.md``
    (NFC, what an editor emits) and the file ``plan/économie.md`` (NFD, what the filesystem returns)
    are different strings for ``==`` and the same file for everyone else. Without this, the index
    check would accuse every accented arc of being unindexed AND its own entry of pointing nowhere —
    two false refusals from one invisible codepoint.
    """
    return unicodedata.normalize("NFC", left) == unicodedata.normalize("NFC", right)


#: Four spaces is an INDENTED CODE BLOCK in markdown — an example, and the detail block under an item
#: besides. It is the one place the "the whole line is just this path" rule below must not reach.
_CODE_INDENT: Final = 4

#: The typographic separators — the marks a TOOL emits. ``plan_convert.py`` writes an em dash, and
#: for a while these nine characters plus the three below WERE the whole rule.
_TYPOGRAPHIC_SEPARATORS: Final = "—–−→⇒⟶·•»"

#: The keys a HUMAN presses. **THE DEFECT THIS LINE CLOSES IS A CLASS, NOT A CHARACTER.** The
#: separator set used to be exactly the marks ``make plan-convertir`` writes — a reference DERIVED
#: from the thing it verifies, so it scored a perfect twelve on twelve against the tool and **two on
#: ten against the shapes a human really types**. The ASCII hyphen ``-`` was the one that mattered:
#: a person retyping an index line with the key on their keyboard DISARMED the staleness check on
#: that line, and nothing anywhere said so. Measured before it was added, on the 320 real documents:
#: **12 declarations and 54 mentions before, 12 and 54 after** — the widening costs nothing on the
#: corpus, and what it buys is that the most edited line of the system survives being retyped.
_ASCII_SEPARATORS: Final = "-:=|"

#: A SEPARATOR — what a human puts between a label and the path it points at. The subset of
#: :data:`_NOTATION_CHARS` that carries the "and here it is" meaning, and it is the entire difference
#: between an entry whose path merely ENDS the bullet and a sentence whose path happens to fall last:
#: ``- Arc C — plan/arc-c.md`` is an index line, ``- a duplicate between plan/arc-c.md and
#: plan/arc-d.md`` is a sentence, and only the dash tells them apart. A space is NOT one.
_SEPARATOR_CHARS: Final = frozenset(_TYPOGRAPHIC_SEPARATORS + _ASCII_SEPARATORS)

#: For every typographic separator, the key a keyboard produces for it. Written out rather than
#: derived, because "``·`` is typed as ``*``" is a JUDGEMENT and a judgement must be visible — the
#: same reason :data:`~mnemosyne.production.plan_archive.CLOSED_STATUSES` is written out. What the
#: judgement BUYS is that the class can be closed by a test: every value here is either a separator
#: or named in :data:`SEPARATOR_KEYS_REFUSED`, so a mark admitted in its printed form and refused
#: under the fingers is no longer possible to ship by omission.
SEPARATOR_ASCII_KEY: Final = {
    "—": "-",
    "–": "-",
    "−": "-",
    "→": "-",
    "⟶": "-",
    "⇒": "=",
    "·": "*",
    "•": "*",
    "»": ">",
}

#: The ASCII keys this rule REFUSES, and why — the symmetric hole of the widening above, named and
#: measured rather than discovered later. Each reason is a real cost, not a fear: adding ``*``
#: accuses ``docs/FORMAT_PLAN.md`` on the real corpus (measured: 1 accusation, line 220), and adding
#: ``>`` accuses two shapes this suite pins as innocent. Both numbers are re-measured by the suite,
#: so a reason that stops being true reddens instead of ageing into folklore.
SEPARATOR_KEYS_REFUSED: Final = {
    "*": "markdown emphasis: `- **plan/x.md** has been archived` would become an entry again",
    ">": "the closing of any HTML tag: `<li>plan/x.md</li> a sentence` would become an entry again",
    ",": "the comma of a sentence: `- plan/x.md, it no longer exists` would become an entry again",
    "(": "the bracket of an aside: `- plan/x.md (it no longer exists)` would become an entry again",
}


def _notation_run_before(raw: str, start: int) -> str:
    """The uninterrupted run of NOTATION characters immediately in front of ``start``.

    Read backwards on single characters only — a checkbox or a bold token cannot be recognised from
    its right edge, and it does not need to be: this run exists solely to ask whether a SEPARATOR
    stands between a label and the path.
    """
    pos = start
    while pos > 0 and _is_notation(raw[pos - 1]):
        pos -= 1
    return raw[pos:start]


def _skip_tail(text: str) -> int:
    """How many leading characters of ``text`` are NOTATION or a complete HTML TAG — never a word.

    :func:`_skip_notation` cannot be reused as-is on the right of a path: ``<li>plan/arc-c.md</li>``
    closes on ``</li>``, whose ``l`` and ``i`` are letters, so a notation-only walk stops on the tag
    and calls the tag prose. A tag is punctuation with a name; a word is content.
    """
    pos = 0
    while pos < len(text):
        rest = text[pos:]
        if (tag := _HTML_TAG_RE.match(rest)) is not None:
            pos += tag.end()
            continue
        if _is_notation(rest[0]):
            pos += 1
            continue
        return pos
    return pos


def _tail_notation(raw: str, end: int) -> str:
    """The run of NOTATION (and complete HTML tags) that immediately FOLLOWS the path.

    The mirror of :func:`_notation_run_before`, and the pair is the whole of the entry rule: a path
    is an entry when a SEPARATOR stands between it and its label, on EITHER side.
    ``- Arc C — plan/arc-c.md`` and ``- plan/arc-c.md — Arc C`` are the same index line written in
    the two orders this repo really writes, and a rule reading only one side blesses every sentence
    written in the other.

    It reads THROUGH closing tags, which is not cosmetic: ``<li>plan/arc-c.md</li> — l'arc C`` puts
    its separator behind ``</li>``, and a character-only walk would stop on the ``l`` of the tag and
    call the whole HTML form a sentence.
    """
    tail = raw[end:]
    return tail[: _skip_tail(tail)]


def _tail_declares(raw: str, end: int, *, separators: frozenset[str] | None = None) -> bool:
    """Is what FOLLOWS the path still compatible with an INDEX ENTRY, rather than a sentence?

 THE THIRD SYMMETRIC HOLE OF THIS RULE, and it was open until it was measured. The
 "inside a container, at its content" way home never looked at the tail AT ALL, while the way
 beside it (behind a separator, at the end) demanded a clear one. So EVERY bullet, cell or
 heading where only NOTATION precedes the path was a declaration whatever the sentence behind it
 said, and ``- plan/arc-archive.md has been archived, it no longer exists`` — an ordinary line of prose
 about a file that is gone — REFUSED a real commit (``index_sans_fichier``, reproduced). That is
 exactly the shape a converted door writes about its own history, so the mechanism would have
 blocked the first commit after the gesture it exists to permit.

 Two ways to pass, and they mirror the two ways a path may be REACHED:

 * **nothing but notation to the end of the line** — including closing HTML tags, which are
 punctuation with a name (``<li>plan/arc-c.md</li>``);
 * **a SEPARATOR in the notation that follows it** — ``- plan/arc-c.md — the reader``, and
 ``- `plan/arc-i.md` — ARC I — …``, the exact line ``make plan-convertir`` writes into a door.

 A space is not a separator, and that is the entire boundary: one word behind the path with
 nothing but a space in between and the line is a sentence. The tail is NECESSARY and never
 sufficient — ``- see plan/arc-c.md : for the detail`` passes here and is still a mention,
 because nothing in front of it opens an entry.

 ``separators`` narrows which marks count, and it exists for exactly ONE caller: way 4 of
 :func:`_declares`, the way home with no container marker in front of it. See there for the
 measurement — the same shape is an index entry with an em dash and re-wrapped prose with ``--``,
 and at column 0 there is no marker to tell them apart.
 """
    tail = raw[end:]
    if _skip_tail(tail) == len(tail):
        return True
    return bool(
        set(_tail_notation(raw, end)) & (_SEPARATOR_CHARS if separators is None else separators)
    )


def _declares(raw: str, start: int, end: int) -> bool:
    """Is the reference at ``raw[start:end]`` a DECLARATION, rather than a mention of a path?

 Four ways to be one, and every one of them is structural — no guess about intent:

 0. **the tail** — :func:`_tail_declares`, asked FIRST and asked of every way below. Whatever
 stands in front of a path, a sentence behind it makes the line a sentence.
 1. **column 0, bare** — a door listing its arcs one per line with no bullet at all, which is the
 form the pre-commit suite's own fixture is written in. Nothing may sit in front, and the
 reason is a measurement rather than taste: over the 320 documents of this repo **0 lines of
 prose open on a bare ``dir/file.md`` and 40 open on a BACKTICKED one** (what an editor
 produces when it re-wraps a paragraph), so decoration at column 0 is what separates the index
 from the forty.
 2. **inside a container, at its content** — a list item, a table cell, a heading, a link
 reference, an ``<li>`` — with only NOTATION between the marker and the path. The notation is
 :func:`_skip_notation`, i.e. the reader's own vocabulary, which is what finally lets
 ``- **ARC-C** `plan/arc-c.md``` and ``- [ ] plan/arc-c.md`` be seen: they are items, and the
 half of this module that reads items has always said so.
 3. **inside a container, behind a SEPARATOR** — ``- Arc C — plan/arc-c.md``. A label, a dash,
 the path: that is an index line whatever the label says. The separator is what keeps the
 sentence out — ``- a duplicate between plan/arc-c.md and plan/arc-d.md`` also ends on a path, and
 a rule asking only "does it end the line" would have accused it. So does
 ``- the command `ls | plan/x.md` fails``, on the other side.
 4. **the line IS the path**, notation on both sides and nothing else — ```plan/arc-c.md``` alone,
 and ```plan/arc-c.md` — the line that is ONLY the path``, which ``docs/FORMAT_PLAN.md``
 hands out as an entry shape. **THIS WAY HOME TAKES ONLY THE TYPOGRAPHIC SEPARATORS, and
 that is where the ASCII widening stops.** It has no container marker in front of it to vouch
 for the line, and D167 counted **40 real lines of prose in this repo that open on a BACKTICKED
 path at column 0** — what an editor produces when it re-wraps a paragraph. One of them is
 ``slot-universe-audit-2.md:332``: ```…-suite.md`` -- cut at the 600-line limit``, whose
 ``--`` is exactly the key being admitted everywhere else. Structurally that line and the spec's
 own entry are the SAME shape; only the character tells them apart, so at column 0 only the
 character a person had to reach for counts. Inside a bullet, a cell or a heading the marker is
 the deliberate act and the hyphen is safe — which is why the narrowing lives HERE and not in
 :data:`_SEPARATOR_CHARS`.
 5. **an HTML attribute** — ``- <a href="plan/arc-c.md">Arc C</a>``. Its closing quote is its
 tail, which is why this one answers before the tail rule rather than through it.

 **Four spaces of indentation stop ALL of them**, and that is a repair rather than a detail: the
 guard used to sit on way 4 alone, so `` plan/arc-c.md`` was correctly read as an indented code
 block while `` - plan/arc-c.md``, the same code block showing a bullet, was ACCUSED. One rule
 cannot hold in one of its ways and not in the others. Measured before it was widened: over the
 320 real documents of this repo, **0 lines sit at four spaces or more carrying both a container
 and a ``plan/…md``**, so this costs no real entry and closes a class of false accusation on
 exactly the pages that must show examples.

 What is NOT here is the missing half of a symmetric pair: prose gets no container and no
 separator, so a sentence still declares nothing, and that is checked against a pinned corpus of
 mentions — the boundary is a test, not a claim.
 """
    if len(raw) - len(raw.lstrip(" ")) >= _CODE_INDENT:
        return False
    if (attr := _ATTR_ENTRY_RE.match(raw)) is not None and attr.end() == start:
        return raw[end : end + 1] == attr.group(1)
    if not _tail_declares(raw, end):
        return False
    if start == 0:
        return True
    starts = [m.end() for m in _CONTAINER_RE.finditer(raw)]
    if raw.lstrip().startswith("|"):
        starts += [m.end() for m in _CELL_RE.finditer(raw)]
    behind_separator = bool(set(_notation_run_before(raw, start)) & _SEPARATOR_CHARS)
    for opened in starts:
        if opened > start:
            continue
        if _skip_notation(raw[opened:start]) == start - opened or behind_separator:
            return True
    return _skip_notation(raw[:start]) == start and _tail_declares(
        raw, end, separators=frozenset(_TYPOGRAPHIC_SEPARATORS)
    )


def _names_alone(name: str, text: str) -> bool:
    """Does ``text`` mention ``name`` as a path of its OWN, rather than as the tail of another one?

    The hole this closes was the exact one clause 4 of D166 exists to prevent. The fallback used to be
    ``base in door`` — a raw substring test — so a door that never indexed ``plan/notes.md`` but
    mentioned ``mesures/notes.md`` anywhere in its prose returned ``refus: []`` and the arc was
    certified by a sentence about something else. ANY prose containing the file name vouched for the
    file.

    The boundary is a path boundary, not a word boundary: ``/`` is excluded on the LEFT precisely so
    ``mesures/notes.md`` stops vouching for ``notes.md``, while ``plan/notes.md`` — which does vouch —
    is already carried by the explicit references and needs no fallback.
    """
    escaped = re.escape(unicodedata.normalize("NFC", name))
    return re.search(rf"(?<![A-Za-z0-9_.\-/]){escaped}(?![A-Za-z0-9_.\-])", text) is not None


def _fence_ferme(found: re.Match[str], ouvrante: tuple[str, int]) -> bool:
    """Does the fence line ``found`` close a block opened by ``ouvrante`` (char, run)?

 SAME character, a run AT LEAST as long, NO info string after it (nothing but whitespace) — the
 CommonMark rule a closer must satisfy.
 **DELEGATED AUDIT OF 2026-08-15 (G3, A7's 5th round): the old phrase "NOTHING but an info
 string after it" was AMBIGUOUS** — read quickly, it reads as the opposite of what the code does
 (`not found.group(3)`, which demands the ABSENCE of an info string). Reworded without ambiguity;
 its English sibling in :func:`_outside_code` ("nothing but whitespace after it") was not
 ambiguous.
 Extracted here so there is only ONE home: :func:`_scan_fences`
 and the document-level guard of :func:`read_plan` (A7) both call it. Letting them diverge has
 already cost a whole class of defect — see the history of :func:`_scan_fences` — and the A7
 guard, before this fix, carried a SECOND, weaker copy of it (a plain toggle, regardless of
 character or length), which reopened exactly the same class one floor up: a
 ``` ```markdown ``` nested inside a ``` ~~~ ``` — the shape ``docs/FORMAT_PLAN.md`` must use to
 document itself — closed at the wrong spot (audit of 2026-08-15).
 """
    char, run = found.group(2)[0], len(found.group(2))
    return char == ouvrante[0] and run >= ouvrante[1] and not found.group(3)


def _scan_fences(lines: list[str]) -> tuple[list[bool], int]:
    """Read the fences ONCE: ``(is this line live?, line of a fence never closed)``.

 ONE FOYER, and the silence lived exactly where the two copies of this predicate diverged.
 The same rule — *same character, at least as long, nothing but whitespace after it* — used to be
 written out twice, in :func:`_outside_code` and in :func:`unclosed_fence_line`. Weakening one
 copy (``run >= fence[1]`` → ``run == fence[1]``, i.e. refusing to let a LONGER closing fence
 close a block, which CommonMark allows) switched the staleness check off for every line after
 that block **and the other copy still answered "every fence is closed"**, so no
 ``bloc_non_ferme`` was raised and nothing said a word. A mechanism that goes quiet must be able
 to SAY it went quiet, and it cannot when two statements of one rule can disagree.
 """
    live: list[bool] = []
    fence: tuple[str, int] | None = None
    open_at = 0
    for offset, raw in enumerate(lines):
        found = _FENCE_RE.match(raw)
        if found is None:
            live.append(fence is None)
            continue
        live.append(False)  # a fence line is never live text, whatever it turns out to be
        if fence is None:
            fence, open_at = (found.group(2)[0], len(found.group(2))), offset + 1
        elif _fence_ferme(found, fence):
            fence, open_at = None, 0
        # else: a shorter run, a different character, or a run carrying an info string — this is
        # CONTENT of the open block, not its closer. Falling through here is the ``~~~``/``` fix.
    return live, open_at


def _outside_code(lines: list[str]) -> Iterator[tuple[int, str, bool]]:
    """Walk the lines, saying for each whether it is LIVE text or the inside of a fenced example.

    Yields ``(offset, raw, live)``. A fence line is never live, and neither is anything between an
    opening fence and the fence that really closes it — *same character, at least as long*, nothing
    but whitespace after it. That is CommonMark's rule, and reading it rather than counting fences is
    what closes a pair of opposite defects that a parity toggle carries by construction:

    * the FALSE ACCUSATION — a page that wraps a ``` example inside a ``~~~`` block, which is exactly
      what a page documenting this format must do to show a fenced example: the inner ``` flipped the
      toggle to "outside", the example became live text, and ``docs/FORMAT_PLAN.md`` — the page that
      SPECIFIES this check — collected an ``index_sans_fichier`` from its own illustration;
    * the SILENCE — one unclosed fence (or one indented by three spaces and never closed) turned
      every remaining line of the door into "inside a block" and switched the staleness check off
      without a word. Here an unclosed fence still swallows the rest of ITS OWN file, which is what
      markdown itself does; what it can no longer do is be opened by a delimiter that was only ever
      example text.

    The tail of an unclosed fence is reported by :func:`unclosed_fence_line` rather than guessed at,
    so a door that turns its own check off says so instead of passing quietly. Both read
    :func:`_scan_fences` — the ONE statement of the rule; see its docstring for what two said.
    """
    live, _ = _scan_fences(lines)
    for offset, raw in enumerate(lines):
        yield offset, raw, live[offset]


def unclosed_fence_line(text: str) -> int:
    """The 1-based line of a code fence this text never closes — ``0`` when every fence is closed.

    Published rather than kept private because it is the one thing that can still turn the staleness
    check off wholesale, and a mechanism that goes quiet must be able to SAY it went quiet. Measured
    over the 320 real markdown documents of this repo before it was written: **0 carry an unclosed
    fence**, so a door that carries one is not a shape this repo writes — it is a door being edited.

    It answers from the SAME walk as :func:`_outside_code`, so "the check went silent here" and
    "a fence is open here" can no longer be two different opinions.
    """
    return _scan_fences(text.splitlines())[1]


def live_lines(text: str) -> tuple[bool, ...]:
    """For each line of ``text``, in order: is it LIVE, or the inside of a fenced example?

    Published for the same reason :func:`unclosed_fence_line` is: anything that EDITS a door has to
    ask the same question this module asks when it JUDGES one, and it must ask it of the same walk.
    Measured, and the reason this exists: the code that posts a sub-plan's index entry on its parent
    looked for "the last line naming a ``plan/…md``" with a bare regex, so a door carrying a
    ```` ```markdown ```` example of an index got the entry planted INSIDE the example — birth exit
    0, commit exit 0, and the sub-plan invisible in the rendered index, because completeness
    (``arc_hors_index``) counts a mention anywhere INCLUDING inside a fence, by design (D167).
    A generosity that is right for the JUDGE is a trap for the WRITER; one walk, asked twice.

    Indexed like ``text.splitlines()`` — the same enumeration ``_outside_code`` yields, so a caller
    may zip it against ``splitlines(keepends=True)`` without a second opinion about what a line is.
    """
    return tuple(_scan_fences(text.splitlines())[0])


def declared_paths(text: str) -> tuple[str, ...]:
    """Every ``plan/….md`` this text DECLARES, in order — the JUDGE's question, not the regex's.

    A bare :data:`_ARC_REF_RE` search answers *"does this text contain a path?"*; this one answers
    *"would the reader read this path as an INDEX ENTRY?"*, which is the question
    :func:`index_problems` really asks before it can raise ``index_sans_fichier``. The two are not
    the same question and the gap is measurable: a title mentioning ``plan/arc-c.md`` mid-line
    carries a reference and declares nothing, so a refusal written on the first predicate accuses an
    input the judge would wave through — and prints a justification that is FALSE for that class.

    Same walk as the judge — the fence scan of :func:`_outside_code`, then :data:`_ARC_REF_RE`, then
    :func:`_declares`. Written as a second rule it would be a second opinion, which is the class D171
    was paid for.

    ALL of them, never the first: a line that legitimately declares one path (an index entry does,
    that is its job) and smuggles a second one behind it would answer "yes, and it is the legitimate
    one" to a caller that can only ask once.
    """
    found: list[str] = []
    for _, raw, live in _outside_code(text.splitlines()):
        if not live:
            continue
        found.extend(
            f"{ARCS_DIRNAME}/{match.group(1).strip()}"
            for match in _ARC_REF_RE.finditer(raw)
            if _declares(raw, match.start(), match.end())
        )
    return tuple(found)


def _dirname(path: str) -> str:
    """The directory part of a ``/``-joined path — ``""`` at the root, never the file's own name."""
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _door_dirs(paths: tuple[str, ...]) -> set[str]:
    """Every directory of ``paths`` that carries a door. Clause 3: a folder with a door IS a plan."""
    return {_dirname(p) for p in paths if p.rsplit("/", 1)[-1] in DOOR_FILENAMES}


def owning_plan(path: str, paths: tuple[str, ...]) -> str | None:
    """Which plan does ``path`` belong to, given every path of the tree? ``None`` when none does.

    Pure over strings so the SAME rule answers on the disk (``rglob``) and in the git index
    (``git ls-files``). The barrier and the reader disagreeing about what belongs to what is the one
    failure this cannot afford: a file judged by neither is a file that ships unread.

    The LONGEST match wins, and that is the whole of clause 3: with a door at ``root/PLAN.md`` and
    another at ``root/plan/c/PLAN.md``, the file ``root/plan/c/plan/detail.md`` belongs to the inner
    plan, not the outer one. Recursion needs no extra rule — only a tie-break.
    """
    here = _dirname(path)
    base = path.rsplit("/", 1)[-1]
    owners = [
        door_dir
        for door_dir in _door_dirs(paths)
        if (base in DOOR_FILENAMES and here == door_dir)
        or path.startswith(f"{door_dir}/{ARCS_DIRNAME}/" if door_dir else f"{ARCS_DIRNAME}/")
    ]
    return max(owners, key=len) if owners else None


def plan_entries(folder: str, paths: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What lies in ``<folder>/plan/`` — ``(arcs, nested doors)``, each relative to that directory.

    Arcs are what gets MERGED into this plan; nested doors are plans of their own (own cap, own
    identity scope) and are only required to be named in the index. A nested door OWNS its own file
    and its own ``plan/`` subtree, and those are excluded here — counting them twice would double
    every item at every level of a recursive plan.

    Everything else under ``plan/`` is an arc **at any depth**, named by its path relative to
    ``plan/`` (``c/arc-1.md``). That is deliberate rather than incidental: a plan with forty arcs
    will group them in sub-directories long before it makes each group a sub-plan, and a file that
    belongs to no level at all is a file that vanishes — the exact silence this format exists to
    close. Recursion stays PERMITTED and never imposed: that project keeps 26 plan files flat and healthy.

    Sorted, so a report and a refusal list are stable from one run to the next.
    """
    prefix = f"{folder}/{ARCS_DIRNAME}/" if folder else f"{ARCS_DIRNAME}/"
    inside = sorted(p for p in paths if p.startswith(prefix) and p.endswith(".md"))
    # ONLY the outermost doors are this plan's business. Without this filter the call returned every
    # DESCENDANT door, at every depth — the exclusion the docstring promises held for a nested plan's
    # arcs and not for its doors, because ``owning_plan`` answers "its own directory" for a door
    # wherever it sits. ``read_plan_tree`` then recursed into a grandchild once directly and once
    # through each ancestor: measured on a four-level tree, FOUR real plans came back as EIGHT
    # verdicts, the deepest one four times. Two levels of nesting show nothing (a child has no
    # descendant), which is why the shape only appears at three — and why it would have shipped.
    doors = {_dirname(p) for p in inside if p.rsplit("/", 1)[-1] in DOOR_FILENAMES}
    outermost = {d for d in doors if not any(d.startswith(f"{other}/") for other in doors - {d})}
    arcs: list[str] = []
    nested: list[str] = []
    for path in inside:
        owner = owning_plan(path, tuple(inside))
        if owner is None or not owner.startswith(prefix.rstrip("/") + "/"):
            arcs.append(path[len(prefix) :])
        elif (
            owner == _dirname(path)
            and owner in outermost
            and path.rsplit("/", 1)[-1] in DOOR_FILENAMES
        ):
            nested.append(path[len(prefix) :])
    return tuple(arcs), tuple(nested)


def index_problems(
    door_text: str, arcs: tuple[str, ...], *, folder_form: bool = True
) -> tuple[PlanProblem, ...]:
    """Does the door's index MATCH what lies in ``plan/``? Two refusals, both named — D166 clause 4.

    ``arcs`` are the arc paths as found on the disk (or in the git index), relative to ``plan/``.
    Returns ``arc_hors_index`` for an arc nothing in the door mentions, and ``index_sans_fichier``
    for a ``plan/…md`` the door names and that does not exist.

    **Why this is the central clause, and it is measured, not feared.** The best-kept project of this
    repo (another project: one orphan in 28 planning files, against 25 in 25 in the trading chantier)
    had ALREADY drifted when it was measured: its most recent plan file declares ``lire_en_premier:
    true`` in its own frontmatter and the door, written three hours earlier, does not know it exists.
    A hand-held index rots on the time scale of the work itself, so the index is checked by code or
    the folder form reproduces at scale the exact defect arc C8 just closed.

    **THE TWO DIRECTIONS ARE NOT THE SAME QUESTION, and reading them off one list of references is
    what made this a wall instead of a floor.** Measured over the 320 real markdown documents of this
    repo: **18 accusations, 18 false, 0 true** — a 100 % false-accusation rate, landing on
    ``docs/FORMAT_PLAN.md`` (the page that SPECIFIES this check), on the living plan (including the
    paragraph documenting the defect) and on that other project, the one D166 names as the model. So
    the two directions now read two different things off the door:

    * **completeness** (``arc_hors_index``, "is this arc named anywhere?") stays GENEROUS — any
      mention, in any form, in any context, including inside backticks and inside a fenced example.
      Being wrong here costs a missed orphan; being strict here would refuse doors that are correct,
      and demanding real markdown links would have scored 6 out of 81 on that project, the best-kept
      planning corpus measured in this repo. The form is free; only the completeness bites.
    * **staleness** (``index_sans_fichier``, "does this named file exist?") is now STRUCTURAL: only a
      reference sitting in a CONTAINER — a list item, a table cell, a heading, a link reference, an
      ``<li>``, or a line that is nothing but the path — with only NOTATION between the marker and the
      path, outside any fenced block, is a DECLARATION (:func:`_declares`). A path quoted mid-sentence
      is a MENTION, and a page may mention any path it likes. This is what a document can be judged on
      without the check having to guess intent.

    That structural half was FIRST WRITTEN TOO NARROW, and the symmetry is the lesson: demanding a
    bare list marker plus a fixed decoration set left the check seeing **0 declarations across the
    whole repo** and blind to the three shapes :func:`read_plan` itself reads as items. A control
    that condemns nobody because it sees nothing is the same wall, turned around; both numbers —
    what it catches and what it accuses — are pinned in the suite, never in a report.

    That asymmetry is not a compromise between the two, it is the recognition that they carry
    opposite risks — and it is exactly what ``docs/FORMAT_PLAN.md`` already promised in words:
    *"the form is free, only completeness is verified"*.

    ``folder_form`` is False when the plan has no ``plan/`` directory at all, and it then suppresses
    ``index_sans_fichier`` — there is no index to verify on a plan that is one file. Kept as a second
    line even though the entry rule now makes prose structurally incapable of triggering the refusal:
    a guard that has stopped being the only thing standing is not a guard to remove. ``arc_hors_index``
    is never suppressed: it needs a file that really exists, so it cannot be triggered by prose.
    """
    door = unicodedata.normalize("NFC", door_text)
    found: list[PlanProblem] = []
    #: Base names carried by exactly ONE entry. The bare-name fallback below is only allowed for
    #: these, and the exception is not hypothetical: every nested door is called ``PLAN.md``, so
    #: naming ONE of them used to index them ALL — measured, two forgotten sub-plans and zero
    #: refusals. Two arcs called ``notes.md`` in different sub-directories collide the same way. A
    #: fallback that cannot tell two files apart is a fallback that certifies the one nobody wrote.
    unique = {
        base
        for base in {arc.rsplit("/", 1)[-1] for arc in arcs}
        if sum(1 for arc in arcs if _same_name(arc.rsplit("/", 1)[-1], base)) == 1
    }

    def cited(arc: str) -> bool:
        base = arc.rsplit("/", 1)[-1]
        if any(_same_name(ref, arc) for ref in refs):
            return True
        if base not in unique:
            return False
        return any(_same_name(ref, base) for ref in refs) or _names_alone(base, door)

    refs: list[str] = []
    # A door that never closes a fence turns its OWN staleness check off for every line after it —
    # the silence named as an open residual when the entry rule shipped. It is named here instead:
    # measured over the 320 real markdown documents of this repo, ZERO carry an unclosed fence, so
    # this refuses a door being edited and no door anybody wrote. A mechanism that goes quiet must
    # say so; a silence nobody can see is the one defect no later audit can find.
    if folder_form and (open_at := unclosed_fence_line(door)):
        found.append(
            PlanProblem(
                open_at,
                "bloc_non_ferme",
                "code block never closed — everything after it stops being verified",
            )
        )
    for offset, raw, live in _outside_code(door.splitlines()):
        for match in _ARC_REF_RE.finditer(raw):
            ref = match.group(1).strip()
            # A reference ALWAYS counts as a citation, wherever it sits — completeness is generous.
            refs.append(ref)
            if not folder_form or not live or not _declares(raw, match.start(), match.end()):
                continue
            if not any(
                _same_name(ref, arc) or _same_name(ref, arc.rsplit("/", 1)[-1]) for arc in arcs
            ):
                found.append(PlanProblem(offset + 1, "index_sans_fichier", f"{ARCS_DIRNAME}/{ref}"))
    found.extend(
        PlanProblem(0, "arc_hors_index", f"{ARCS_DIRNAME}/{arc}") for arc in arcs if not cited(arc)
    )
    return tuple(found)


#: The vocabulary as a REFUSAL says it — each token followed by the role it means. ``OWNER`` is the
#: reason this exists: printed bare, a refusal orders a reader at the extraction factory or at
#: Example Research to write a first name that means nothing to them, and the three-form answer this field
#: gave ("OWNER is a ROLE, never a name") lived only in a label nobody prints. *A guarantee that only
#: the docstring holds is a wish.*
_VOCABULARY_GLOSSED: Final = tuple(
    token if not role else f"{token} ({role.split(' — ')[0]})"
    for token, role in PREREQUISITE_HOLDERS.items()
)


#: The ROOT folder of Mnemosyne's plan. Doors are DERIVED from :data:`DOOR_FILENAMES`, they are
#: not retyped.
#:
#: **THIS WAS STILL A LIST — OF TWO — AND IT FORGOT THE SECOND DECLARED DOOR NAME.** It used to
#: be a two-item list naming this repository's own top-level plan document and its plan folder
#: directly, while :data:`DOOR_FILENAMES` declares **two** and the hook matches both of them.
#: Proven by a REAL commit accepted: renaming that document to its legacy door name + an item at
#: **0/6 fields** → **the entire obligation disappears without a word**. And the name is not
#: hypothetical: it is the one this very plan carried until C20-12, and this module still declares
#: *"because another plan may still carry it"*.
#: **Second time this scope leaked through an enumeration.** It is now derived instead.
_DOSSIER_DU_PLAN: Final = "docs"

#: An HTML comment — closed, or open until the end of the value. **Markdown does NOT render it; so
#: it cannot answer a field.** Stripped at the SINGLE home where values are assembled, so that
#: `field()`, `blank_fields` and the witnesses all read the SAME value — an accessor that saw a
#: different one would reopen the hole through its own door.
#:
#: **MY FIRST FIX WAS A CASE, NOT THE CLASS.** I had closed the invisible code points; the same
#: hole was open here too: a field holding `<!-- todo -->` was *filled in* for the barrier
#: (**refusals=0**) and **EMPTY for the human**, who sees `*Produit* :` followed by nothing. The
#: class is not "unicode invisibles" — it is **EVERYTHING THE GATE COUNTS THAT THE READER CANNOT
#: SEE**.
#:
#: **Neither hypothetical nor far-fetched: 61 HTML comments live inside `docs/`,** including ones
#: `make plan-nouveau` itself writes. Found because a comment **stuck** to a value inflated it to
#: **1416 characters** and turned the length-cap witness red: the rendered value was no longer the
#: one the human reads — its tail carried a narrative, not a stopping rule.
_COMMENTAIRE_HTML: Final = re.compile(r"<!--.*?(?:-->|$)", re.DOTALL)


def champs_requis_pour(door_path: str, declare: str = "") -> tuple[str, ...]:
    """Which fields THIS plan obliges — the six for Mnemosyne's own plan, EXACTLY what is
 declared elsewhere, nothing for a plan that declares nothing.

 **THIS USED TO BE A LIST OF LOCATIONS INSIDE THE DOOR, AND AN AUDIT WALKED THROUGH IT IN
 SILENCE.** The hook carried a table keyed by this repository's own top-level door path alone.
 But ``owning_plan`` applies *"the longest match wins"* (D166 clause 3: **any folder carrying a
 door is a plan, AT EVERY LEVEL**) — so the moment a sub-plan is born under this repository's own
 plan folder, its door becomes a nested ``<x>/PLAN.md``, the table returns ``()``, and **the
 obligation disappears without a word**. Triggered with this repo's own sanctioned command:
 ``make plan-nouveau CHEMIN="plan/zz" APPLY=1`` writes an item carrying **0 of the 6 fields**, and
 the commit is **ACCEPTED**. *A list of locations always forgets one more location* — the hook's
 own header accuses itself of already having paid for this mistake once, and I made it again
 inside it.

 **So this is a PREDICATE, and it lives HERE** rather than in the hook: a rule inside a module
 gets tested; a table inside a shell script gets re-read. The scope stays narrow — Mnemosyne's
 own plan **and its sub-plans**, nothing else: a floor laid on another project's plan would be a
 ceiling in disguise (the precedent set by ``A5``), and that project declares ``*Prérequis*`` on 0 of
 its 168 items.

 **D176 (2026-08-16) — SAME HOLE, ONE STEP HIGHER.** The half above is a PREDICATE closed
 over a single path: it decides WHO is bound, never HOW a project that is NOT Mnemosyne could
 become one. No line of this repo could make it say "yes" to a project — the scope was right,
 the MEANS to enter it did not exist. The user, verbatim: *"once you adopt the standard, you
 never drift away from it"* — a standard nobody can ADOPT cannot be honoured either.

 **The remedy: ``declare``, the verbatim content of ``**Format** :`` at the head of the door**
 (:data:`PlanReading.format_declare`, the same pattern as ``succede_a`` — a DOOR field, read
 once). Every recognised token of :data:`FIELD_NAMES`, comma-separated, BECOMES required; an
 unknown token (a typo, a token from another vocabulary) is silently ignored — it obliges
 nothing, and it refuses nothing either. **Two hard boundaries, measured by the neighbouring
 witnesses**: (1) a door outside Mnemosyne WITHOUT ``**Format**`` gets ``declare=""`` by default
 → ``()``, exactly today's behaviour, unchanged; (2) a door declaring ``produit, fini_quand`` is
 held to THOSE TWO ONLY, never the other four — ``required_field_
 problems`` claims ONLY what ``required`` names, so there is no line to write here to keep that
 boundary holding.

 **Mnemosyne's own plan does NOT need to declare itself**: the path-based branch below stays
 the unconditional floor — ``declare`` is not even read for those doors. That is deliberate: it
 is the only branch this repo's NEGATIVE CONTROL exercises (0 refusals on its 49 items, and it
 DOES bite on a mutilated item); making it depend on a line of prose would add a new way to lose
 it without changing a single observable behaviour today.
 """
    portes = {f"{_DOSSIER_DU_PLAN}/{nom}" for nom in DOOR_FILENAMES}
    if door_path in portes or door_path.startswith(f"{_DOSSIER_DU_PLAN}/{ARCS_DIRNAME}/"):
        return tuple(FIELD_NAMES)
    return tuple(
        token
        for token in (jeton.strip().lower() for jeton in declare.split(","))
        if token in FIELD_NAMES
    )


def required_field_problems(
    reading: PlanReading, *, required: tuple[str, ...] = tuple(FIELD_NAMES)
) -> tuple[PlanProblem, ...]:
    """Judge which items are short of a REQUIRED field — the level-2 half of item ``A1``.

 ``required`` is the CALLER's decision, and that is the whole scoping mechanism: level 2 on this
 plan, level 1 everywhere else, exactly the precedent item ``A5`` set. Passing ``()`` obliges
 nothing, which is what a project that has not adopted the format should get.

 **The barrier is ARMED** (2026-08-15) — see :data:`REQUIRED_FIELD_REFUSALS`. It refuses
 **0 of the 49 items** of Mnemosyne's own plan and **does bite** on a mutilated item, both
 measured with a real commit before and after arming it.

 One refusal per ITEM rather than per missing field, and the sentence NAMES every field short:
 six lines about one item is a wall of text, and a refusal a reader cannot act on in one read is
 a refusal they learn to skip. ``AUCUN``/``AUCUNE`` remain valid, free answers everywhere — this
 obliges the QUESTION, never the answer, which is the rule the whole arc rests on.
 """
    wanted = [name for token, name in FIELD_NAMES.items() if token in required]
    found: list[PlanProblem] = []
    for item in reading.items:
        # `blank_fields` TOO, and its absence here was "the barrier nothing calls": this judge
        # used to read only `missing_fields`, so **six fields declared EMPTY passed the commit** —
        # measured. Yet `blank_fields`'s own docstring says it exists to stop "a plan looking
        # complete because every heading is present". A question asked and left unanswered is not a
        # question that got answered.
        short = [
            name for name in wanted if name in item.missing_fields or name in item.blank_fields
        ]
        if not short:
            continue
        found.append(
            PlanProblem(
                item.line,
                "champ_requis_manquant",
                f"{item.ident or item.title[:24]} — {len(short)} field(s) not filled in: "
                f"{' · '.join(short)} ; an answer such as `AUCUN` is valid and free",
                item.source,
            )
        )
    return tuple(found)


def prerequisite_problems(reading: PlanReading) -> tuple[PlanProblem, ...]:
    """Judge the ``*Prérequis*`` of every item of ``reading`` — the LEVEL-2 half of the field.

 **THIS IS A SEPARATE CALL, AND THAT IS THE WHOLE DESIGN.** :func:`read_plan` stays what it has
 always been — a pure reader that never demands. The obligation lives HERE so its CALLER decides
 the scope, and the reason is a measurement rather than a preference: ``*Prérequis*`` is declared
 by **0 of that project's 168 items**, so a refusal wired into the reader would have refused
 168 items out of 168 on the day it shipped, and the same for the extraction factory and
 Example Research. *A control that condemns everybody is the same wall as one that condemns nobody* — and
 this arc's governing rule is explicit that one publishes rather than punishing the existing.

 The plan that INVENTS a rule is the one that submits to it: the level-2 barrier is meant for
 Mnemosyne's own plan, and the same field reaches other projects at level 1 — an invitation
 carried by ``make plan-emit``. A floor laid on somebody else's plan is a ceiling in disguise.

 Two refusals, and they are two different repairs:

 * ``prerequis_manquant`` — the item never declared the field. The silence is what this closes:
 an item whose prerequisite nobody asked about gets started on a hypothesis.
 * ``prerequis_inconnu`` — a token outside :data:`PREREQUISITE_HOLDERS`. Naming it is what makes
 the vocabulary closed rather than decorative; an open vocabulary is a free-text field wearing
 a schema's name.

 ``AUCUN`` raises nothing and costs nothing: the question is obliged, the answer never is.
 """
    found: list[PlanProblem] = []
    for item in reading.items:
        token = item.prerequisite
        if token is None:
            found.append(
                PlanProblem(
                    item.line,
                    "prerequis_manquant",
                    f"{item.ident or item.title[:24]} — write `*Prérequis* :` followed by "
                    f"{' · '.join(_VOCABULARY_GLOSSED)} ; `AUCUN` is a valid and free answer",
                    item.source,
                )
            )
        elif token not in PREREQUISITE_HOLDERS:
            found.append(
                PlanProblem(
                    item.line,
                    "prerequis_inconnu",
                    f"{item.ident or item.title[:24]} → "
                    + (
                        f"{token[:24]!r} outside the vocabulary"
                        if token
                        else f"nothing readable in \"{item.field('prerequis')}\""
                    )
                    + f" ({' · '.join(_VOCABULARY_GLOSSED)})",
                    item.source,
                )
            )
    return tuple(found)


#: A backtick-quoted token from the ``*Produit*`` field that LOOKS like a path — contains a `/`, or
#: ends in a short extension. Same heuristic as the one measured for ``*À lire*`` elsewhere in this
#: repo, rewritten here rather than imported: ``*Produit*`` is a different field, over its own
#: population, and the two modules do not belong to the same home (D162) — a private function
#: shared across that seam would have made this module depend on the other one.
_PRODUIT_TOKEN_RE: Final = re.compile(r"`([^`]+)`")
_EXTENSION_COURTE_RE: Final = re.compile(r"\.[A-Za-z]{1,5}$")

#: A LINE suffix on a cited path — ``:143``, ``:57-60``. Stripped before comparison: the SAME file
#: cited at two different lines is the SAME product, not two.
#: **DELEGATED AUDIT OF 2026-08-15 (E1, a reservation on a HELD clause)** — the first version
#: returned the WHOLE token, line suffix included: on that project's real plan, the auditor measured
#: **15 pairs of items writing the SAME file** (``scripts/extraire_lignes.py:143``
#: against ``scripts/extraire_lignes.py:57-60``) sorted into the SAME batch by `plan_ordre.lots()`,
#: because equality was STRING equality, not file equality. *A path cited twice with two different
#: anchors is not two paths — it is the same piece of writing seen from two angles.*
_SUFFIXE_LIGNE_RE: Final = re.compile(r":\d+(?:-\d+)?$")


def chemins_cites_par_produit(produit: str) -> tuple[str, ...]:
    """The ``*Produit*`` tokens that look like a path — neither resolved nor checked on disk,
 only recognised by their FORM. Same principle :func:`index_problems` already applies to an
 arc citation higher up in this module: the form is free, but a cited path has a recognisable
 form, a `/` or an extension.

 Only the FIRST word of a token counts (``` `validate_output.py --write-artifacts` ``` cites a
 file, not its arguments), and its line suffix is stripped (:data:`_SUFFIXE_LIGNE_RE`) BEFORE
 judging its form AND before it is returned — otherwise the same file cited in two spots of the
 plan with two different anchors reads as two distinct files.

 **PUBLIC (E1): the same question, a second caller, never a second answer.**
 ``plan_ordre.lots()`` needs it to judge whether two ``*Produit*`` overlap — that is the SAME
 population this already judges (folder-vs-file); a module that answered "which paths does this
 *Produit* cite?" twice would drift sooner or later, like the two-home fence `A7`/`A8` closed.
 Different from the neighbouring choice (``*À lire*`` stays rewritten, never imported): here
 BOTH callers ask the question of the SAME field, not of two fields that merely share a
 heuristic.
 """
    trouves: list[str] = []
    for tok in _PRODUIT_TOKEN_RE.findall(produit):
        premier = _SUFFIXE_LIGNE_RE.sub("", tok.split()[0] if tok.split() else tok)
        if "/" in premier or _EXTENSION_COURTE_RE.search(premier):
            trouves.append(premier)
    return tuple(trouves)


def produit_problems(reading: PlanReading) -> tuple[PlanProblem, ...]:
    """Judge the ``*Produit*`` of every item of ``reading`` — C2: *"the product names a FILE,
 never a folder"*.

 **MEASURED BEFORE WRITING IT, like :func:`prerequisite_problems` before it.** Over the 55
 real items of this repo: **30 (55%) cite NO path at all** in their ``*Produit*`` — conceptual
 prose ("the command that transforms…", "the transcript reader…"), never at fault on its own,
 and **out of scope for this clause**: it does NOT judge "does it cite a path", it judges "WHEN
 a path is cited, is it a real one". A clause refusing the absence of a path would condemn more
 than half the plan on the day it is armed — the same wall :func:`prerequisite_problems`
 measured and refused to build. **2 (4%) cite ONLY folders** (``plan/retires/``,
 ``projects/mnemosyne/ui/``): that population, and only that one, is what :data:`PRODUIT_REFUSALS`
 names.

 An item where NO cited token looks like a path passes silently: this clause does not claim to
 know whether a purely conceptual product SHOULD cite one — only that a product that DOES cite
 one must not limit itself to a folder.
 """
    found: list[PlanProblem] = []
    for item in reading.items:
        chemins = chemins_cites_par_produit(item.field("produit") or "")
        if not chemins:
            continue
        fichiers = [c for c in chemins if not c.rstrip().endswith("/")]
        if fichiers:
            continue
        found.append(
            PlanProblem(
                item.line,
                "produit_est_un_dossier",
                f"{item.ident or item.title[:24]} — *Produit* cites only "
                f"{' · '.join(f'`{c}`' for c in chemins)}, never a specific file inside",
                item.source,
            )
        )
    return tuple(found)


def produit_resolu_rapport(reading: PlanReading) -> str:
    """``produits_resolus=N/N terrain_declare=N/N`` over ``reading`` — C2's *Fini quand*, word for
    word: a JUDGED population, the output PRINTS both ratios together, never one without the other
    (a lesson already paid for twice in this repo: two numbers published separately read as one
    where they actually measure two different things).

    ``produits_resolus`` counts an item whose ``*Produit*`` cites AT LEAST one path that is NOT
    ONLY a folder (:func:`produit_problems` does not accuse it) **and** that cited something
    path-shaped to begin with — a purely conceptual product (30 of the 55 real items) is neither
    resolved nor at fault, it is OUTSIDE what this clause judges, see :func:`produit_problems`.

    ``terrain_declare`` counts an item whose ``*État du terrain*`` is present and NOT EMPTY —
    "nothing occupies this role" written out in plain words counts; a field that was never opened
    does not. The same distinction :attr:`PlanItem.blank_fields` makes for the six obliged fields,
    rebuilt here because this field is KNOWN (:data:`EXTRA_FIELD_NAMES`) and not obliged, hence
    outside the population `blank_fields` walks.
    """
    total = len(reading.items)
    en_defaut = {p.line for p in produit_problems(reading)}
    produits_resolus = sum(
        1
        for item in reading.items
        if item.line not in en_defaut and chemins_cites_par_produit(item.field("produit") or "")
    )
    terrain_declare = sum(
        1
        for item in reading.items
        if (valeur := item.field("etat_du_terrain")) is not None
        and not PlanItem._sans_contenu(valeur)
    )
    return f"produits_resolus={produits_resolus}/{total} terrain_declare={terrain_declare}/{total}"


def merge_plan(
    door: PlanReading,
    arcs: tuple[tuple[str, PlanReading], ...],
    *,
    extra: tuple[PlanProblem, ...] = (),
) -> PlanReading:
    """Fold a door and its arcs into ONE reading — the object every consumer already knows how to use.

    ``arcs`` are ``(path relative to the door's folder, reading)`` pairs — ``plan/arc-c.md``, the
    SAME string the arc's items carry in :attr:`PlanItem.source`. The path travels here rather than
    being recovered from the items, because an arc with zero items and zero refusals would otherwise
    leave no trace at all — and a file that vanishes from the report is exactly the failure mode this
    whole format exists to close.

    That equality is CHECKED, not documented: the two namespaces drifted the moment they existed
    (``parts`` relative to ``plan/``, ``source`` relative to the door), both docstrings claimed the
    same thing, and a consumer had to re-glue the prefix by hand with a comment begging nobody to
    tidy it away. A convention two callers must remember is a convention that has already broken.

    This merge is what keeps the folder form from rippling through the repo: ``readable``,
    ``by_status()``, ``untracked``, ``prose_lines`` all keep their exact meaning, applied to the
    union. The alternative — a second, folder-shaped result type — would have meant every caller
    growing a branch, and a caller that forgets the branch reports only the door, in silence.

    The door comes FIRST and its cap and title win: a plan has one cap, and naming it is the door's
    whole job. ``succede_a`` follows the exact same rule for the exact same reason — but unlike a
    stray ``**Cap**`` on an arc, which loses nothing a reader relied on, a stray ``**Succède à**``
    on an arc is silently worth NOTHING: H4 exists specifically to refuse a promotion that drops
    work without a word, so the one field built to prevent silent loss cannot itself be lost in
    silence. An arc that declares one is therefore named as a problem, not merely outvoted.
    """
    for path, arc in arcs:
        carried = {entry.source for entry in arc.items} | {
            problem.source for problem in arc.problems
        }
        if carried - {path}:
            raise ValueError(
                f"the arc \"{path}\" carries lines attributed to {sorted(carried - {path})} — "
                "the arc's path and the `origin` passed to `read_plan` must be the SAME string."
            )
    misplaced_succede_a = tuple(
        PlanProblem(
            0,
            "succede_a_hors_porte",
            "**Succède à** only counts on the door -- declared here, it protects nothing",
            path,
        )
        for path, arc in arcs
        if arc.succede_a
    )
    return PlanReading(
        project=door.project,
        cap=door.cap,
        items=door.items + tuple(item for _, arc in arcs for item in arc.items),
        problems=door.problems
        + tuple(p for _, arc in arcs for p in arc.problems)
        + misplaced_succede_a
        + extra,
        prose_lines=door.prose_lines + sum(arc.prose_lines for _, arc in arcs),
        total_lines=door.total_lines + sum(arc.total_lines for _, arc in arcs),
        summary_tables=door.summary_tables
        + tuple(n for _, arc in arcs for n in arc.summary_tables),
        parts=tuple(path for path, _ in arcs),
        succede_a=door.succede_a,
        format_declare=door.format_declare,
    )


def fold_plan(
    door_text: str,
    tree: tuple[str, ...],
    read: Callable[[str], tuple[str | None, str]],
    *,
    folder_form: bool | None = None,
    on_loss: Callable[[str, str], PlanProblem] | None = None,
) -> PlanReading:
    """Fold a door and its ``plan/`` into ONE reading. **The single enumeration of a plan's arcs.**

 ``tree`` is every path under ``plan/``, relative to the DOOR (``plan/foundation.md``,
 ``plan/t1/PLAN.md``, ``plan/t1/plan/foundation.md``) — the raw contents of the directory, nested plans
 included. Which of those are THIS plan's arcs is :func:`plan_entries`' answer and **nobody
 else's**: ``read`` is called for those and for nothing else.

 **THAT IS THE WHOLE POINT OF THIS FUNCTION EXISTING, and it was measured, not feared.** The
 pre-commit judge folded a plan this way; the birth command (``plan-nouveau``) walked the parent's
 ``plan/`` with its own ``rglob`` and handed EVERY file it found to the fold — a second
 enumeration, one directory deeper. So a plan's SECOND sibling sub-plan was refused: the first
 sub-plan's own arc came back as an arc of the PARENT, its ``A1`` collided with the parent's
 ``A1``, and the refusal blamed Mnemosyne (``id_duplique``) for a birth that was correct. Proof
 the two verdicts really were opposite: with the internal check disabled the second sub-plan was
 born AND the commit passed. A capability whose whole promise is *"it is the same code as the
 gate"* cannot own a second walk of the disk.

 ``read`` returns ``(text, why)`` — ``(None, why)`` for an arc that is on the disk and cannot be
 opened. ``on_loss`` turns that into the problem the caller wants to publish; without it a loss
 raises, because a plan silently short of an arc is the silence this format exists to close.

 ``folder_form`` defaults to "there is something under ``plan/``". Callers that know the directory
 exists but is empty pass it explicitly, exactly as :func:`index_problems` documents.

 **THE ARC ITSELF IS ASKED TWO QUESTIONS HERE, and they lived nowhere.** ``index_problems``
 interrogates the DOOR; ``read_plan`` reads whatever a file happens to say. Nothing asked whether
 an arc that exists still holds anything, so emptying ``plan/collecte.md`` by hand took a plan
 from *" 3 items"* to *" 2 items"* — no refusal, no file name, state ``readable``. **The
 reader sees what IS, never what is MISSING**, and this is the fold every surface goes through, so
 it is the one place where saying it once covers ``make plans``, ``make ui-json``,
 ``verify_readability`` and the pre-commit barrier at the same time.

 * ``bloc_non_ferme`` — a fence an arc never closes swallows every item behind it, exactly as it
 switches the staleness check off in a door. Measured before it was written: **0 of the 12 real
 arcs of this repo carry one**, and 0 of the 320 documents D168 walked.
 * ``arc_vide`` — a BLANK arc, and the word is the whole boundary. *"An arc with no item"* was
 the remedy an audit named; measuring it first is what saved it from being a wall, because
 **7 of those same 12 real arcs carry no item at all** (``contexte-en-une-ligne.md``,
 ``ce-qui-n-est-pas-dans-ce-plan…md``, …) — prose sections that became arc files at conversion
 and are perfectly correct. A refusal there would have made Mnemosyne's own plan UNREADABLE and
 blocked every commit. So the refusal takes only what no writing of this repo occupies (0 of
 12 blank), and the item-free arc is a FLAG on the surface instead — ``PlanReading.parts`` and
 the per-arc count name it there. *A catch rate without its false-kill rate is a wall.*

 The two are DISJOINT by construction — a file carrying an unclosed fence is not a blank file —
 so neither one shelters the other and their order decides nothing. Said here rather than dressed
 up as an ordering rule: a guarantee no input can exercise is a sentence, not a check.
 """
    arc_paths, nested = plan_entries("", tree)
    seen: dict[str, str] = {}
    door = read_plan(door_text, ident_seen=seen)
    arcs: list[tuple[str, PlanReading]] = []
    losses: list[PlanProblem] = []
    for relative in arc_paths:
        # ONE string for the arc's path, built once: it is both the key `merge_plan` publishes in
        # `parts` and the `origin` every line of that arc carries. Two expressions for one path is
        # how the two drifted apart in the first place, and `merge_plan` now refuses the pair.
        member = f"{ARCS_DIRNAME}/{relative}"
        text, why = read(member)
        if text is None:
            if on_loss is None:
                raise ValueError(f"the arc \"{member}\" is unreadable and no `on_loss` answers for it")
            losses.append(on_loss(member, why))
            continue
        if open_at := unclosed_fence_line(_sans_bom(text)):
            losses.append(
                PlanProblem(
                    open_at,
                    "bloc_non_ferme",
                    "code block never closed — the items that follow are no longer read",
                    member,
                )
            )
        # `_sans_bom` and not `text.strip()`: a `\ufeff` is NOT whitespace to Python, so an
        # arc reduced to a BOM used to escape `arc_vide` — the exact silence this refusal exists to
        # close. The BOM fix had been placed in `read_plan` alone, so the reader and
        # its sibling judges were no longer reading the same bytes. *A single home is only single if
        # everyone goes through it.*
        if not _sans_bom(text).strip():
            # `line=0` and NO `source`, the path travelling in the detail: the exact shape
            # `arc_hors_index` and `arc_illisible` already use for a refusal about a FILE rather
            # than a line. One wording for one question.
            losses.append(
                PlanProblem(
                    0,
                    "arc_vide",
                    f"{member} : the file is EMPTY — its items have vanished from the printed count ;"
                    " write at least one item in it, or remove the file and its index entry",
                )
            )
        arcs.append((member, read_plan(text, origin=member, ident_seen=seen)))
    return merge_plan(
        door,
        tuple(arcs),
        # The unreadable arcs stay in `arc_paths` handed to `index_problems`: they are still ON THE
        # DISK, so the door must still name them. Dropping them here would have made a broken arc
        # ALSO an arc the index is no longer allowed to miss — one defect quietly excusing another.
        extra=index_problems(
            door_text,
            arc_paths + nested,
            folder_form=bool(tree) if folder_form is None else folder_form,
        )
        + tuple(losses),
    )
