"""Chapter grammar + self-delimited verbatim fence — the ONE home of how a fiche's structure is read (D143 / D100).

A fiche is a book distilled into ``## N. title`` chapters, each ending in a ``### Contenu (verbatim)`` block of P3
passages copied byte-for-byte from the source. THREE readers must agree on where a chapter starts — and where a
heading QUOTED from the source does NOT: the distiller that WRITES a fiche (``distill_book._section_md``), the
finisher that re-titles it (``finisher.parse_fiche`` / ``chapter_numbers_ok``), and the juge that verifies it
(``juge._chapters``). Two private copies of that grammar would drift and split a fiche one host rewrote from the
one another host flags (consolidate-crosscutting-rules) — so the grammar lives HERE, imported by all three.

**The trap it closes (D143).** OCR sources quote their own numbering: a verbatim line ``## 2. Foo`` sits INSIDE a
passage (63 % of the corpus has such lines). A naive ``^## \\d+\\.`` scan mistakes it for a chapter boundary and
TRUNCATES the verbatim there — its tail demoted to P2, the numbers rewritten. The structural fix is to make the
verbatim block SELF-DELIMITED: the writer wraps it in :data:`VERBATIM_BEGIN` / :data:`VERBATIM_END` sentinels, and
every chapter-boundary scan runs on :func:`mask_fenced_verbatim` first — which blanks the fenced span (offsets
preserved 1:1) so a heading quoted inside it can never be read as a boundary. The P3 bytes are UNTOUCHED (the
sentinels are separate lines around the passages, never inside them); only the PARSE changes.

**Backward-compatible by construction.** A fiche with no fence (every pre-fix corpus fiche) contains no sentinel,
so :func:`mask_fenced_verbatim` returns it unchanged and it is scanned exactly as before — the guard that flags a
false heading fail-closed still bites (chapters non-sequential / count != frontmatter). Only a NEW, fenced fiche
gains the protection. Code & docstrings English (D117)."""

from __future__ import annotations

import re

#: A chapter heading — ``## N. Title`` at line start. Group 1 = the number (sequencing / count check), group 2 =
#: the title. The ONE definition (it was duplicated in finisher + juge, a silent-drift hazard): both import it here.
SECTION_RE = re.compile(r"^## (\d+)\.[ \t]*(.+)$", re.MULTILINE)

#: The self-delimiting sentinels around a chapter's verbatim passages. HTML comments: invisible in a rendered
#: fiche, and (unlike a ``` code fence) they cannot collide with a passage's own backticks. Same ``mnemosyne:``
#: convention as the ``source-unusable`` / ``distill-failed`` markers the juge already skips when counting passages.
VERBATIM_BEGIN = "<!-- mnemosyne:verbatim-begin -->"
VERBATIM_END = "<!-- mnemosyne:verbatim-end -->"

#: The two placeholders ``distill_book._section_md`` writes when a field is empty. EXACT strings, and the ONE home
#: for them: the juge SKIPS these paragraphs when counting P3, so anything it skips is a paragraph THE VERBATIM
#: FLOOR NEVER SEES. They must therefore be pinned here and matched EXACTLY, never by prefix.
PLACEHOLDER_DESCRIPTION = "_(no description)_"
PLACEHOLDER_NO_PASSAGE = "_(no verbatim passage kept)_"

#: Namespaced machine markers a Mnemosyne writer may emit inside a fiche (``source-unusable``, ``distill-failed``,
#: the two sentinels above). Variable payload, hence a prefix — but they are HTML comments, i.e. INVISIBLE in a
#: rendered fiche: forging one can HIDE text, never DISPLAY unverified text as a quotation.
_MARKER_PREFIX = "<!-- mnemosyne:"


def is_structural_marker(paragraph: str) -> bool:
    """True if this paragraph is Mnemosyne's own scaffolding, not claimed content — hence exempt from the P3 floor.

    **Anything this returns True for enters a fiche WITHOUT ever being checked against the source.** So the rule
    is an EXACT allow-list, never a prefix over VISIBLE text. It used to be ``startswith("_(")`` — and an isolated
    audit (2026-07-28) walked straight through it: a fiche carrying paragraphs like ``_(The market will collapse in
    March 2027.)_`` inside its verbatim fence printed ``6/6 passages verbatim (rendement 100%) · VERDICT: PASSE``
    while DISPLAYING three fabricated quotations under ``### Contenu (verbatim)``. ``_(…)_`` renders as visible
    italics: a prefix rule over it is a hole the producer opens by typing two characters.

    The symmetric error was live too: ``startswith("<!--")`` exempted ``<!-- formula-not-decoded -->`` and
    ``<!-- image -->``, markers that come from the OCR **sources** — so they are text genuinely quoted from the
    author's file. Measured on the real shelf: **48 paragraphs** escaped judgement that way (34 + 13 + 1).

    **What that measurement does NOT say.** Judging them moves ``n_passages`` by +48 but ``n_verbatim`` by only
    +9, and the honest reading of that gap is **duplication, not fabrication**: all 48 ARE present in their source
    (checked directly, 0 absent), and ``keep_verbatim`` collapses repeats to their first occurrence. Reading +48/+9
    as "39 paragraphs are not in their source" was wrong, and it was published for a few minutes — the exact trap
    already recorded about this function's silent dedup. On today's shelf the hole was real but **unexploited**:
    nothing fabricated was found. Only OUR namespace is scaffolding; everything else is a claim, and a claim faces
    the floor."""
    p = paragraph.strip()
    return p in (PLACEHOLDER_DESCRIPTION, PLACEHOLDER_NO_PASSAGE) or p.startswith(_MARKER_PREFIX)


def mask_fenced_verbatim(text: str) -> str:
    """Return ``text`` with every character inside a verbatim fence replaced by a space (newlines kept), so a
    ``## N.`` heading QUOTED from a source can never be mistaken for a chapter boundary (D143).

    Offsets are preserved 1:1 — a match found in the masked text indexes the ORIGINAL ``text`` unchanged, so a
    caller scans the mask for boundaries yet slices the real text for content. No fence present (a pre-fix fiche)
    → ``text`` is returned as-is (fully backward-compatible). An UNTERMINATED fence (a truncated / corrupt write,
    e.g. an interrupted distillation) is masked to end-of-text — fail-closed: the chapters it swallows then fail
    the sequential / count check and the fiche is FLAGGED, never silently mis-parsed."""
    if VERBATIM_BEGIN not in text:
        return text
    out: list[str] = []
    i = 0
    while True:
        begin = text.find(VERBATIM_BEGIN, i)
        if begin == -1:
            out.append(text[i:])
            break
        out.append(text[i:begin])  # text before the fence: kept as-is
        end = text.find(VERBATIM_END, begin + len(VERBATIM_BEGIN))
        stop = len(text) if end == -1 else end + len(VERBATIM_END)
        span = text[
            begin:stop
        ]  # the fence + its contents: blanked, newlines kept so offsets/line starts survive
        out.append("".join(c if c == "\n" else " " for c in span))
        if end == -1:  # unterminated -> everything after BEGIN is masked; nothing left to scan
            break
        i = stop
    return "".join(out)
