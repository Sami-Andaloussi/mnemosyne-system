"""The finisher (D42 / operator's point 4 / D143) — makes a fiche READABLE without EVER touching the
verbatim P3.

The distiller guarantees FIDELITY (P3 = the source's own words) but not beauty: chapter titles come
from the raw OCR titles of the source (often bad — an author's name, "Published by", gibberish, the
"(section)" placeholder), and the table of contents inherits them. The finisher POLISHES the
synthesis layer — chapter titles + P2 descriptions + table of contents — so the fiche is pleasant to
read and to navigate.

**P3 is SACRED, guaranteed by CONSTRUCTION (D143 / D100).** The finisher never re-renders the
verbatim content: :func:`parse_fiche` captures the ``### Contenu (verbatim)`` block of each chapter
as RAW TEXT, and :func:`render_fiche` copies it through unchanged. Only ``title`` and ``description``
(P2 layer, free synthesis) go through the model/heuristic. A model that goes off the rails therefore
CANNOT corrupt the verbatim — it is not on its path. The ONLY angle from which PARSING itself could
get it wrong — a false ``## N.`` header INSIDE a verbatim passage (a source line like ``## 2.1 Foo``)
— is closed TWICE: (1) STRUCTURALLY, the verbatim block is SELF-DELIMITED
(:mod:`~mnemosyne.production.chapter_parsing`, ``verbatim-begin/end`` sentinels laid down by the
distiller) and every chapter scan ignores it, so a fenced fiche is parsed cleanly; (2) FAIL-CLOSED as
a fallback, for any non-fenced fiche (the pre-fix corpus): :func:`chapter_numbers_ok` detects the
ambiguity and the finisher then REFUSES to touch the fiche (better unfinished than a truncated
verbatim). The judge (:func:`~mnemosyne.production.judge_fiche`) re-validates P3 afterwards AND
flags such a fiche: belt and suspenders (no model is trusted, finisher included).

Model-agnostic (D126): the retitling is an INJECTED ``retitle`` (a deterministic stub based on the
default concepts; the real local or frontier model at stage ③). Code & docstrings in English (D117);
operator-facing labels stay in French in the source (D33)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, replace

from .chapter_parsing import (
    PLACEHOLDER_DESCRIPTION,
    PLACEHOLDER_NO_PASSAGE,
    SECTION_RE,
    mask_fenced_verbatim,
)

_CHAPTERS_RE = re.compile(
    r"^chapters:[ \t]*(\d+)", re.MULTILINE
)  # the count declared in the frontmatter
_CONTENU_MARK = "### Contenu (verbatim)"


def chapter_numbers_ok(text: str) -> bool:
    """True iff the split into chapters is NOT ambiguous — the invariant of a fiche fit to finish
    (D143).

    A false header INSIDE a passage (a source line like ``## 2.1 Foo`` or ``## 2. Foo``, common in
    OCR: 63% of the corpus's books have one) would become a false chapter boundary -> the verbatim
    would be TRUNCATED there, its tail demoted to P2, the numbers rewritten. TWO barriers overlap:
    (1) IN FORM — :func:`~mnemosyne.production.chapter_parsing.mask_fenced_verbatim` neutralises
    any header quoted INSIDE a self-delimited verbatim block (a fenced fiche), so the scan only
    sees the REAL headers; (2) IN SUBSTANCE, for any fiche (fenced or not, including the whole
    pre-fix corpus) — the numbers seen must be 1, 2, …, N sequential AND their count must equal the
    frontmatter's ``chapters: N``. A non-fenced fiche where a passage carries ``## N.`` therefore
    still fails (2) -> the finisher REFUSES to touch it (fail-closed, D85) and the judge FLAGS it;
    a fenced fiche is parsed cleanly."""
    nums = [int(m.group(1)) for m in SECTION_RE.finditer(mask_fenced_verbatim(text))]
    if nums != list(range(1, len(nums) + 1)):
        return False
    declared = _CHAPTERS_RE.search(text)
    return declared is None or int(declared.group(1)) == len(nums)


_CONCEPTS_MARK = "**Concepts** :"
_PLACEHOLDER_TITLE = "(section)"


@dataclass(frozen=True, slots=True)
class Chapter:
    """One chapter of a fiche. ``contenu`` is the RAW ``### Contenu (verbatim)`` block — P3, SACRED: it is
    copied through byte-for-byte, never re-rendered from parts (so a retitle can never corrupt it)."""

    title: str
    description: str
    concepts: tuple[str, ...]
    contenu: str  # verbatim P3 block, raw — copied through unchanged


#: What a chapter title looks like when it should be rewritten: the ``(section)`` placeholder, OCR/garbage
#: (mostly non-letters), or a bare number/one char. Kept CONSERVATIVE — a decent-but-imperfect title (an
#: author name, a generic heading) is left to the model path; the deterministic floor only fixes the CLEAR
#: cases, never mangles a real title.
def is_bad_title(title: str) -> bool:
    t = title.strip()
    if not t or t == _PLACEHOLDER_TITLE or len(t) < 3:
        return True
    letters = sum(c.isalpha() for c in t)
    return letters / len(t) < 0.5  # mostly digits/symbols -> OCR garbage, not a title


#: Known OPENERS of a MECHANICAL P2 description — a placeholder, not a synthesis. A bulk host (the Codex
#: polish) fills a FIXED sentence with the chapter title + its first concepts ("L'auteur traite ici de «…» et
#: aborde également …", or an index/references/bio/TOC boilerplate) — it says nothing true about the content.
#: :func:`is_templated_description` lets the juge SURFACE this (verify-in-code, D75: no host can silently claim
#: "synthèse" while shipping a gabarit) and a future finisher know what to rewrite. Accent/apostrophe-folded.
_TEMPLATE_MARKERS = (
    "l'auteur traite ici de",
    "l'auteur presente les elements",
    "l'auteur consigne ici ses remerciements",
    "le chapitre fournit l'index",
    "le chapitre rassemble les references",
    "le chapitre presente des elements biographiques",
    "le chapitre reproduit",
)  # openers OBSERVED in the corpus; anchored at the start (startswith) — never a generic opener (e.g.
#    "l'auteur examine …" would flag a real synthesis): a false positive would label real work.


def _fold(text: str) -> str:
    """Lowercase, strip, straighten apostrophes and drop accents — the comparison form for template matching."""
    folded = unicodedata.normalize("NFKD", text.strip().lower().replace("’", "'"))
    return "".join(c for c in folded if not unicodedata.combining(c))


def is_templated_description(description: str) -> bool:
    """True iff a chapter's P2 description is a MECHANICAL template, not a real synthesis (D75, verify-in-code).

    A templated description fills a FIXED sentence with the chapter's title + its first concepts — it conveys
    nothing about the actual content. Detection is CONSERVATIVE (anchored on known template openers, accent- and
    apostrophe-insensitive) so a genuine synthesis is never mislabeled. Used by the juge to REPORT P2-templating
    as a SEPARATE axis — it never fails P3 fidelity (the verbatim is judged on its own)."""
    folded = _fold(description)
    return any(folded.startswith(marker) for marker in _TEMPLATE_MARKERS)


def _title_from_concepts(concepts: tuple[str, ...], idx: int) -> str:
    """Deterministic fallback title from the chapter's own concepts (no model) — the floor for a bad title."""
    gloss = ", ".join(concepts[:2])
    return f"Chapitre {idx}" + (f" — {gloss}" if gloss else "")


#: The literal placeholder a chapter's concept list inherits when the distiller could not decode a formula
#: from the source (observed in ~1700 chapters corpus-wide) -- never a real concept, always dropped.
_PLACEHOLDER_CONCEPT = "formula-not-decoded"

#: A SMALL, UNDENIABLE stopword set for :func:`curate_concepts` -- articles / coordinating conjunctions /
#: common prepositions ONLY, in English and French (the two languages observed around the corpus), matched
#: case-insensitively. Deliberately narrow: no verbs, pronouns, adverbs or short content words -- a book's own
#: vocabulary ("null", "four", "size", "non", "out"...) must never be mistaken for a function word, so only
#: the closed, undeniable classes are listed. Single-letter articles ("a") are already caught by the
#: length < 2 rule in curate_concepts, so are not repeated here.
_STOPWORDS = frozenset(
    {
        # English: articles, coordinating conjunctions, common prepositions
        "an",
        "the",
        "and",
        "or",
        "but",
        "nor",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "from",
        "by",
        "as",
        "into",
        "onto",
        # French: articles, coordinating conjunctions ("mais ou et donc or ni car"), common prepositions
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "et",
        "ou",
        "mais",
        "donc",
        "car",
        "ni",
        "dans",
        "sur",
        "avec",
        "pour",
        "par",
        "sans",
        "sous",
        "chez",
        "entre",
    }
)

_PURE_NUMBER_RE = re.compile(
    r"^\d+(?:[.,]\d+)?$"
)  # a bare number ("42", "3.14") -- never a real concept


#: Trailing symbols that are part of a real concept token, not edge noise: the "++"/"#" of C++, C#, F#, A#.
#: A concept must never be mangled (D42), so a trailing run of these survives the edge-strip (and the len<2 drop).
_KEEP_TRAILING = frozenset("+#")


def _strip_edge_punct(token: str) -> str:
    """Strip leading/trailing non-alphanumeric characters from ONE token (interior punctuation -- the hyphen
    in "mean-variance" -- is kept). A bare concept's edge punctuation is normally OCR/extraction noise
    ("Testing'", "func-"), never meaningful -- EXCEPT a trailing run of ``+``/``#``, which is load-bearing in
    language names (C++, C#, F#, A#) and is preserved so a real concept is never mangled into oblivion (D42)."""
    start, end = 0, len(token)
    while start < end and not token[start].isalnum():
        start += 1
    while end > start and not token[end - 1].isalnum() and token[end - 1] not in _KEEP_TRAILING:
        end -= 1
    return token[start:end]


def curate_concepts(concepts: list[str]) -> list[str]:
    """Deterministically clean a chapter's concept list (D42) -- drop leaked-extraction noise, keep everything
    that MIGHT be a real concept. CONSERVATIVE by construction (a real concept must never be dropped or
    mangled; when unsure, keep it -- under-cleaning beats over-cleaning):

    1. Drop the literal ``formula-not-decoded`` placeholder (case-insensitive) -- a formula the distiller
       could not decode, leaked in as a fake "concept".
    2. Strip stray leading/trailing punctuation from each token (:func:`_strip_edge_punct`) -- extraction
       fragments like "Testing'" or "func-" become "Testing" / "func"; interior characters are untouched.
    3. Drop a token that, after stripping, is empty (this also covers pure-punctuation tokens -- they strip
       down to nothing), is a bare number, has length < 2, or is a pure stopword (:data:`_STOPWORDS`).
    4. Dedupe case-insensitively, keeping the FIRST occurrence's original casing and position -- surviving
       tokens are never lowercased or otherwise normalized ("Bayes" stays "Bayes").

    If curation would empty the list, the ORIGINAL list is returned unchanged instead: an empty concept list
    would starve the deterministic title fallback (:func:`_title_from_concepts`) and the Sommaire gloss --
    a chapter keeping a few noisy concepts is better than losing its only content markers entirely."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in concepts:
        token = _strip_edge_punct(raw.strip())
        if not token:
            continue
        low = token.lower()
        if low == _PLACEHOLDER_CONCEPT or _PURE_NUMBER_RE.fullmatch(token) or len(token) < 2:
            continue
        if low in _STOPWORDS or low in seen:
            continue
        seen.add(low)
        cleaned.append(token)
    return cleaned or list(concepts)


#: Separators that may sit between a title's real text and a leaked "formula-not-decoded" suffix -- plain
#: ASCII whitespace/punctuation plus the em dash (u2014) used elsewhere in this file's own gloss separators
#: (D117: written as an escape, not a literal, so the source stays ASCII-only).
_TITLE_JUNK_RE = re.compile(
    r"[\s,;:_\-\u2014]*" + re.escape(_PLACEHOLDER_CONCEPT) + r"[\s.,;:]*$", re.IGNORECASE
)


def _clean_title_junk(title: str) -> str:
    """Strip the SAME leaked-extraction junk from a title, but only in UNAMBIGUOUS cases: a trailing
    "formula-not-decoded" placeholder (with its separator), or trailing footnote asterisks. A title is a full
    phrase where trailing punctuation is often part of the real title (a question mark, a closing
    parenthesis) -- unlike a bare concept token, edge punctuation is NOT stripped wholesale here: that would
    mangle legitimate titles like "Does It Matter Empirically?" or "Modern Studies (1988-2007)". Never
    returns an empty string (falls back to the original title)."""
    cleaned = _TITLE_JUNK_RE.sub("", title.strip())
    cleaned = cleaned.rstrip("*").rstrip()
    return cleaned or title.strip()


def parse_fiche(text: str) -> tuple[str, list[Chapter]]:
    """Split a fiche into its ``header`` (frontmatter + H1 + banner, sommaire dropped — it is rebuilt) and
    its chapters. Boundaries are found on :func:`~mnemosyne.production.chapter_parsing.mask_fenced_verbatim`
    (a ``## N.`` quoted inside a verbatim fence is not a boundary, D143) but every slice indexes the ORIGINAL
    text — the ``### Contenu (verbatim)`` block of each chapter is kept RAW, fence markers and all (P3 preserved,
    carried through verbatim by :func:`render_fiche`)."""
    masked = mask_fenced_verbatim(
        text
    )  # offsets preserved 1:1 -> matches index the original `text`
    first = SECTION_RE.search(masked)
    if first is None:
        return text, []
    header = text[: first.start()]
    som = header.find("\n## Sommaire")
    if som != -1:  # drop the old sommaire — render_fiche rebuilds it from the (possibly new) titles
        header = header[:som].rstrip() + "\n"
    chapters: list[Chapter] = []
    matches = list(SECTION_RE.finditer(masked))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end() : end]
        contenu = ""
        pre = block
        if _CONTENU_MARK in block:
            pre, contenu = block.split(_CONTENU_MARK, 1)
        concepts: tuple[str, ...] = ()
        desc = pre
        if _CONCEPTS_MARK in pre:
            desc, conc = pre.split(_CONCEPTS_MARK, 1)
            concepts = tuple(
                ln.strip()[1:].strip() for ln in conc.splitlines() if ln.strip().startswith("-")
            )
        chapters.append(Chapter(m.group(2).strip(), desc.strip(), concepts, contenu.strip("\n")))
    return header, chapters


def render_fiche(header: str, chapters: list[Chapter]) -> str:
    """Re-render a fiche: header + a rebuilt ``## Sommaire`` + each chapter. The verbatim ``contenu`` block
    is emitted UNCHANGED (P3 sacred)."""
    parts = [header.rstrip(), "", "## Sommaire", ""]
    for i, ch in enumerate(chapters, 1):
        gloss = ", ".join(ch.concepts[:3])
        parts.append(f"- [[#{i}. {ch.title}]]" + (f" — {gloss}" if gloss else ""))
    for i, ch in enumerate(chapters, 1):
        parts += ["", f"## {i}. {ch.title}", "", ch.description or PLACEHOLDER_DESCRIPTION]
        if ch.concepts:
            parts += ["", _CONCEPTS_MARK, *(f"- {c}" for c in ch.concepts)]
        parts += ["", _CONTENU_MARK, "", ch.contenu or PLACEHOLDER_NO_PASSAGE]
    return "\n".join(parts) + "\n"


#: A retitle strategy: given a chapter, return its (new title, new description). The model path (local /
#: frontier) supplies a real one; ``None`` uses the deterministic floor (fix a bad title from the concepts).
Retitle = Callable[[Chapter], tuple[str, str]]


#: The polish contract for a FRONTIER host (Codex) — the ONE code home of the finisseur's model-facing
#: instruction, emitted by ``finish_emit.py`` (``make finish-emit``), NEVER hand-copied into the SKILL.md
#: (a copy drifts — the distillateur lesson, contract-single-source-emit / commit 241e525). The deterministic
#: floor uses ``retitle`` / :func:`_title_from_concepts`; a frontier host applies THIS. P3 stays sacred either
#: way (the verbatim block is copied through by the agent, then re-checked by the juge).
FINISH_PROMPT = """\
You polish ONE already-distilled fiche for READABILITY. You improve only the synthesis layer (chapter titles
and their P2 descriptions) and the table of contents. You NEVER touch the verbatim content (P3).

Two régimes, do not confuse them:
- title and description (P2): REWRITE for clarity. The title must be a SHORT, DESCRIPTIVE title of the
  chapter's real content — never an author name, "Published by", "(section)", a bare number, or OCR garbage.
  The description stays NEUTRAL and ATTRIBUTED to the author ("the author shows…", "the chapter presents…");
  you may improve the wording, never invent a claim or restate the book's marketing as established fact.
- the "### Contenu (verbatim)" block of each chapter is P3 — SACRED. COPY it byte-for-byte, unchanged: never
  rephrase, reformat, re-wrap, translate, or truncate it. A fiche whose verbatim moved is a FAILURE (the juge
  re-checks it).

Keep the chapter numbering (## 1., ## 2., …) and their count exactly as-is. Rebuild the "## Sommaire" from the
new titles (one Obsidian link per chapter + up to 3 of its concepts). Write valid markdown (real newlines).
"""


def finish_fiche(text: str, retitle: Retitle | None = None) -> str:
    """Polish a fiche's readability WITHOUT touching P3 (D143). Only ``title`` / ``description`` / ``concepts``
    change; the verbatim ``contenu`` block of every chapter is carried through unchanged (structural
    guarantee, D100).

    ``retitle`` supplies the new (title, description) per chapter (the model path); ``None`` = the
    deterministic floor: a CLEARLY bad title (:func:`is_bad_title`) is rebuilt from the (curated) concepts, a
    decent title is lightly de-noised (:func:`_clean_title_junk`) and kept, descriptions are untouched. Every
    chapter's concept list is run through :func:`curate_concepts` regardless of which title path was taken --
    it feeds BOTH the chapter's own ``**Concepts**`` block and the rebuilt sommaire's trailing gloss (same
    ``Chapter.concepts`` field, :func:`render_fiche` uses it for both), so the two never drift apart.

    Fail-closed (D143 / D85): if the ``## N.`` headers are not sequential (a false header inside a verbatim
    passage, cf. :func:`chapter_numbers_ok`), the text is returned UNCHANGED — better an unfinished fiche
    than a truncated verbatim."""
    if not chapter_numbers_ok(text):
        return text
    header, chapters = parse_fiche(text)
    finished: list[Chapter] = []
    for i, ch in enumerate(chapters, 1):
        curated_concepts = curate_concepts(list(ch.concepts))
        if retitle is not None:
            new_title, new_desc = retitle(ch)
        else:
            cleaned_title = _clean_title_junk(ch.title)
            new_title = (
                _title_from_concepts(curated_concepts, i)
                if is_bad_title(cleaned_title)
                else cleaned_title
            )
            new_desc = ch.description
        finished.append(
            replace(
                ch,
                title=new_title.strip(),
                description=new_desc.strip(),
                concepts=tuple(curated_concepts),
            )
        )
    return render_fiche(header, finished)
