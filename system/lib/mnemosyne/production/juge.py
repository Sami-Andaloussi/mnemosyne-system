"""The judge (D42 / D75 / D100 / D85) — verifies a distilled fiche WITHOUT trusting the model that produced it.

A fiche can be produced by the LOCAL model (through the governed stack, already floor-filtered) OR by
a FRONTIER agent (Codex/ChatGPT) following the skill's contract. The second has NO structural barrier on
production: it can return an empty template (every chapter "(section)", generic descriptions, zero
verbatim), paraphrase P3 while believing it did well, or reduce an entire book to a STUB (its cover page). The
judge is producer != verifier (D75) applied to distillation: it runs each fiche back through the repo's
SAME barriers — the verbatim floor (:func:`keep_verbatim`) and the source-quality gate
(:func:`assess_source_quality`) — plus a COVERAGE floor, and returns a normalized verdict. No trust
in the model, Codex included: the guarantee lives in the code (D100), never in its good faith.

**``ok`` = P3 FAITHFUL, not "a nice distillation."** The judge guarantees FIDELITY (the passages are the
source's real words) and a minimal COVERAGE (the book is not reduced to a stub) — it judges NEITHER the P2
synthesis prose NOR how finely the chapters are cut (that is the finisher's job). An ``ok`` means "the
substance can be trusted," not "it is perfect."

The judge REWRITES nothing (neither raw nor fiche): it OBSERVES and FLAGS (D85). The orchestrator (the
``juge`` skill) acts on its verdicts. Code & docstrings in English (D117); labels facing the user stay in
French in the source repository (D33) — translated to English in this public mirror."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .chapter_parsing import SECTION_RE, is_structural_marker, mask_fenced_verbatim
from .distillation import assess_source_quality, keep_verbatim
from .finisher import chapter_numbers_ok, is_templated_description


class JudgeStatus:
    """The normalized verdict of :func:`judge_fiche` — what the orchestrator dispatches on (D108-2)."""

    OK = "ok"  # P3 FAITHFUL + covered: real verbatim spread across chapters (fidelity, NOT a judge of P2 prose)
    HOLLOW = (
        "hollow"  # a template/placeholder shell — no content produced (the model did NOT distil)
    )
    THIN = "thin"  # distilled to almost nothing / mostly-empty chapters — a stub (e.g. only the cover page)
    PARAPHRASED = (
        "paraphrased"  # claims passages, but too few survive the floor (paraphrased / invented P3)
    )
    FLAGGED = (
        "flagged"  # the fiche IS a source-unusable flag (expected when the source is truly garbage)
    )
    MALFORMED = "malformed"  # escaped \n / no frontmatter / no chapters — not valid fiche markdown
    RAW_MISSING = "raw_missing"  # no mirror raw to check the verbatim against
    CUT = (
        "cut"  # a passage stops MID-WORD in the source — the completude FLOOR (D165), and it bites
    )


@dataclass(frozen=True, slots=True)
class FicheVerdict:
    """One fiche's normalized verdict + the numbers behind it (an INFORMATIVE flag, never a silent skip)."""

    status: str
    n_chapters: int
    n_passages: int  # P3 passages the fiche CLAIMS
    n_verbatim: int  # of those, how many are genuinely the source's words (survive keep_verbatim)
    reason: str
    #: chapters whose P2 description is a MECHANICAL template, not a synthesis — a SEPARATE axis from P3
    #: fidelity: it NEVER changes ``ok``; it SURFACES an un-synthesized "polish" so no host claims it silently.
    n_templated: int = 0
    #: claimed passages CUT by the schema's ``maxLength`` — a THIRD separate axis, and the one the verbatim
    #: floor is structurally blind to: a truncated prefix of a literal span is still a literal span, so
    #: :func:`keep_verbatim` blesses it. Like ``n_templated`` it NEVER changes ``ok`` (the passage IS the
    #: source's words — just not all of them); it only refuses to let the loss stay silent.
    n_truncated: int = 0
    #: passages that stop MID-WORD in the source — the completeness FLOOR (D165), and the only one of
    #: the four axes that BITES: it replaces the removed ceiling. Unlike ``n_truncated`` (the
    #: archaeology of a dead regime) and ``n_templated`` (the P2 prose), a mid-word cut is a fault of
    #: TODAY's producer, immediately fixable, and exclusive: 0 out of 2,664 control passages. See
    #: :func:`cut_mid_word` for why this criterion and not the other.
    n_cut_midword: int = 0

    @property
    def ok(self) -> bool:
        """Whether the fiche is trustworthy — P3-faithful & covered, OR a legitimate source-unusable flag."""
        return self.status in (JudgeStatus.OK, JudgeStatus.FLAGGED)


_PLACEHOLDER_TITLE = (
    "(section)"  # distill_book's fallback title — a whole fiche of these = no real headings
)
_CONTENU_MARK = "### Contenu (verbatim)"
_CONCEPTS_MARK = "**Concepts**"

#: Fidelity + COVERAGE floors (D75 / D100), calibrated on the real shelf: a real BOOK distils to many
#: verbatim passages spread across its chapters (Carver ~200 / 27 ch, Clean Architecture ~220 / 26). An
#: ``ok`` needs (a) high verbatim YIELD — most claimed passages are truly the source's words; (b) enough
#: TOTAL verbatim — else it is a STUB (a whole book reduced to its copyright page passes (a) alone, the live
#: "Optimal Mean Reversion" false-OK the audit caught); (c) enough chapters actually CARRYING content — else
#: it is mostly-empty (the failed-chunk case, latent until the OCR campaign). A wrongly-THIN book is
#: recoverable (re-distil / force); a rubber-stamped stub silently pollutes the KB (D75: never bless the unfaithful).
_MIN_VERBATIM_YIELD = 0.8
_MIN_VERBATIM_TOTAL = 3
_MIN_COVERAGE = 0.4


def _chapters(fiche_text: str) -> list[tuple[str, str, list[str]]]:
    """``(title, P2 description, claimed P3 passages)`` per chapter — split at each ``## N. title`` heading.

    The description is the prose BEFORE the chapter's ``**Concepts**`` / ``### Contenu (verbatim)`` marks (the
    P2 layer, checked for TEMPLATING). A passage = a paragraph under the ``### Contenu (verbatim)`` block; the
    empty-content placeholder ``_(...)_`` and the ``<!-- ... -->`` markers (fence sentinels included) are NOT
    passages (so an empty/failed chapter contributes zero — it must not inflate the coverage). Boundaries are
    found on the fence-masked text (a ``## N.`` quoted inside a verbatim block is not a chapter, D143); each
    slice indexes the ORIGINAL ``fiche_text`` so the passages stay intact for :func:`keep_verbatim`."""
    matches = list(SECTION_RE.finditer(mask_fenced_verbatim(fiche_text)))
    chapters: list[tuple[str, str, list[str]]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(fiche_text)
        block = fiche_text[m.end() : end]
        description = block
        for mark in (_CONCEPTS_MARK, _CONTENU_MARK):
            if mark in description:
                description = description.split(mark, 1)[0]
        passages: list[str] = []
        if _CONTENU_MARK in block:
            for para in block.split(_CONTENU_MARK, 1)[1].split("\n\n"):
                p = para.strip()
                if p and not is_structural_marker(p):
                    # We filter on the CLEANED form but KEEP the trailing whitespace: a cut at the
                    # schema's ceiling lands at N characters *whitespace included*, and a `.strip()`
                    # upstream made it invisible to the detector — 1,967 truncations missed out of
                    # 6,087, i.e. 32%, found by an isolated audit. `keep_verbatim` normalizes
                    # whitespace, so no verdict moves (verified on the shelf's 248 fiches).
                    # (This comment used to read "1,931 out of ~6,051": two approximate figures that
                    # contradicted `truncated_passages`'s docstring IN THIS SAME FILE. A 4th isolated
                    # audit caught it. The exact pair is 4,120 + 1,967 = 6,087.)
                    passages.append(para.strip("\n"))
        chapters.append(
            (m.group(2).strip(), description.strip(), passages)
        )  # group(2)=title (group(1)=number)
    return chapters


#: What a KEPT sentence ends on. Deliberately broad (closing quotes and parentheses included): the
#: goal is to accuse ONLY what visibly stops mid-way.
_FINALES: frozenset[str] = frozenset('.!?"»)…:;')


#: The length ceiling that RULED the shelf from 2026-05 to 2026-07-28, then was REMOVED
#: (`distillation.DISTILL_SCHEMA`, D165 — a ceiling on a generated output does not bound it, it STEERS it).
#:
#: **This is no longer a rule: it is ARCHAEOLOGY.** It no longer bounds anything and must never
#: become a directive again. Its sole function is to let :func:`truncated_passages` keep
#: recognizing the **6,087 amputations already on the shelf** — passages cut clean at 500 by a
#: regime that no longer exists. Erasing them from the count would make them invisible; reattributing
#: them to today's producer would accuse it of a fault it did not commit.
#:
#: It used to be READ from the schema, precisely so a copied number would not survive a schema
#: change. The schema changed — which is why it is written here, DATED, with the reason for its
#: death: reading a vanished ceiling would have crashed the judge across the whole shelf.
PLAFOND_HISTORIQUE: int = 500


def passage_cap() -> int:
    """The ceiling under which the CURRENT shelf was produced — see :data:`PLAFOND_HISTORIQUE`."""
    return PLAFOND_HISTORIQUE


def truncated_passages(passages: Sequence[str], cap: int | None = None) -> tuple[str, ...]:
    """The passages CUT CLEAN by the schema's ceiling — the loss the verbatim floor cannot see.

    A truncated passage remains a **literal, contiguous** excerpt of the source: it is a prefix. It
    therefore passes :func:`keep_verbatim` without a hitch, and the fiche is blessed `ok`. Measured on
    2026-07-28 against the real shelf (77,155 passages): **6,351 passages are EXACTLY 500 characters
    long**, and **95.8% of them (6,087, across 210 fiches) end with no closing punctuation at all** —
    versus **4.3%** on a control population of 50,768 passages between 300 and 480 characters. A ratio
    of **22**.

    The criterion is the CONJUNCTION: length exactly at the ceiling AND visibly stopping mid-way.
    No accusation is possible outside the ceiling.

    **The ceiling is measured trailing whitespace INCLUDED.** An early version received passages
    already `.strip()`-ed and missed **1,967 truncations out of 6,087 (32%)**: the cut lands at N
    characters *space or tab included*, so cleaning upstream makes it invisible. This is why
    :func:`_chapters` now keeps the trailing whitespace (no verdict moves:
    `keep_verbatim` normalizes whitespace — verified on the 248 fiches).

    **This counter names NO cause.** Measured breakdown: the `frontier` path **6,045 / 71,778 =
    8.4%** (99.3% of the loss), the local `GLM` path **42 / 2,582 = 1.6%**, the `haiku` path **0 / 2,795**.
    The constrained-grammar decoder is wired only into the LOCAL path (`distillation.py`), the one
    that truncates the least: blaming the grammar was wrong, and that mistake was published.

    This axis makes nothing unreadable and changes no verdict: it only refuses to let the loss stay
    silent. Fixing it requires re-distilling, which is the user's move, not ours.

    **The length criterion holds TWO requirements at once, and only one of the two is obvious.**

    1. *Above the ceiling, the cut did NOT happen* — a passage longer than `limit` has crossed the
       boundary, so it was not truncated by it. **22 real passages** on the shelf exceed it, and
       accusing them would be a pure false accusation.
    2. *But strict equality was STEERABLE BY THE VERY THING BEING MEASURED.* An isolated audit
       (2026-07-28) added **one space** to the tail of every passage in a real fiche: length 501, no
       more accusation, the count dropping from **182 to 1** — and no other figure moved, since
       `keep_verbatim` normalizes whitespace and the floor therefore sees nothing there.

    The conjunction that satisfies both: the passage **reaches** the ceiling, and its excess is
    ONLY whitespace (``len(p.rstrip()) <= limit``). A real cut lands at `limit` characters
    *whitespace included* — so `rstrip` always brings it back under the boundary — while a genuinely
    longer passage stays above it. Neither `==` (gameable) nor `>=` (which accuses the 22) does it
    alone. Cost measured on the shelf: **0** — the count stays at 6,087, which is expected since
    nobody padded anything; what changes is that nobody CAN anymore.

    The symmetric loophole closes on its own: padding with PUNCTUATION instead of whitespace changes
    a non-whitespace character, so the passage stops being a literal substring of the source and the
    floor DROPS it. The two barriers compose.
    """
    limit = passage_cap() if cap is None else cap
    return tuple(
        p
        for p in passages
        if len(p) >= limit and len(p.rstrip()) <= limit and (p.rstrip()[-1:] or " ") not in _FINALES
    )


def cut_mid_word(passages: Sequence[str], raw_text: str) -> tuple[str, ...]:
    """The passages that stop MID-WORD — the completeness FLOOR, and it BITES.

    It is the replacement for the ceiling removed on 2026-07-28 (D165): size is no longer bounded, a
    property is required instead. And the property is not guessed — it is READ FROM THE SOURCE. A
    passage is a literal prefix; we look at the character that FOLLOWS it in the raw text. If the
    passage ends on an alphanumeric character and the next one is also alphanumeric, a word was cut
    in two.

    **WHY NOT "does not end on punctuation," which seemed like the natural criterion.** Measured
    on the shelf, excluding historical amputations (71,116 passages):

    | criterion | flagged | fiches | would flip |
    |---|---|---|---|
    | no closing punctuation | **4,248** (6.0%) | 221 / 248 | **22 books** |
    | cut mid-word | **13** (0.02%) | 10 / 248 | — |

    **330x fewer**, and above all: the 22 books the first criterion rejected were *Asset Pricing*,
    *Time Series Analysis*, *High-Dimensional Statistics*, *Machine Learning*… — all MATH books.
    The accusation was following the **book's discipline**, not the producer's care: a sentence
    ending on an equation mangled by OCR has no closing punctuation, and that is nobody's fault. A
    floor that accuses a POPULATION instead of a FAULT is not a floor, it is a wall — and it would
    have flooded the refusal queue the very day it was created.

    A mid-word cut, by contrast, is **exclusive**: an isolated audit measured it at **0 out of 2,664**
    control passages (at the ceiling but ending on punctuation; final witness; non-final witness). No
    healthy population cuts a word. That is what authorizes this floor to BITE where the other could
    only count.

    Returns the tuple of faulty passages, in order — not a count: what is actionable is the
    passage itself, and the gate NAMES it.
    """
    coupes: list[str] = []
    for p in passages:
        i = raw_text.find(p)
        if i < 0:  # not in the source: that is the VERBATIM FLOOR's business, not this one's
            continue
        suivant = raw_text[i + len(p) : i + len(p) + 1]
        if p[-1:].isalnum() and suivant.isalnum():
            coupes.append(p)
    return tuple(coupes)


def _flatten(chapters: list[tuple[str, str, list[str]]]) -> tuple[str, ...]:
    """Every CLAIMED P3 passage, chapter order preserved — the exact input the verbatim floor scores."""
    return tuple(p for _, _, passages in chapters for p in passages)


def verbatim_split(fiche_text: str, raw_text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``(kept, dropped)`` for one fiche's claimed P3 — the SAME split :func:`judge_fiche` scores.

    :func:`judge_fiche` runs this split, keeps the two COUNTS and throws the dropped half away (it
    only ever renders a verdict). Yet that half is the only actionable thing a producer holds: the
    passages it must repair before its fiche enters the base. A calculation nothing prints does not
    exist for whoever is working — hence the targeted door `make verbatim-check`, which calls THIS
    hearth. A second extraction, however faithful the day it is written, drifts
    ([[contract-single-source-emit]]); the door additionally REFUSES if its split and the verdict's
    counts disagree, so a fork announces itself instead of quietly blessing.
    """
    return keep_verbatim(_flatten(_chapters(fiche_text)), raw_text)


def judge_fiche(fiche_text: str, raw_text: str | None) -> FicheVerdict:
    """Verify ONE fiche against its raw source — the structural, no-trust verdict (D100 / D75).

    Order matters: a deliberate source-unusable FLAG is not a failure; escaped ``\\n`` / a missing frontmatter
    / no chapters is MALFORMED before we try to score; then the heart — run the CLAIMED P3 passages through
    :func:`keep_verbatim` against the raw. A distillation with placeholder chapters or no passages is HOLLOW;
    one whose passages are mostly not the source's words is PARAPHRASED (yield < 0.8); one that IS faithful
    but distilled the book to almost nothing (a stub: too few verbatim, or mostly-empty chapters) is THIN.
    Only a faithful AND covered fiche is OK. ``raw_text`` None → RAW_MISSING (we refuse to bless what we
    cannot check)."""
    if "status: source-unusable" in fiche_text or "mnemosyne:source-unusable" in fiche_text:
        note = ""
        if raw_text is not None and assess_source_quality(raw_text).ok:
            note = " ; but the source re-tests OK -> false positive? (make distill FORCE=1)"
        return FicheVerdict(JudgeStatus.FLAGGED, 0, 0, 0, "fiche = source-unusable flag" + note)
    if fiche_text.count("\\n") > 5 and fiche_text.count("\n") < 5:
        return FicheVerdict(
            JudgeStatus.MALFORMED, 0, 0, 0, "escaped newlines (\\n) — invalid markdown"
        )
    if not fiche_text.lstrip().startswith("---"):
        return FicheVerdict(JudgeStatus.MALFORMED, 0, 0, 0, "no frontmatter")
    if not chapter_numbers_ok(
        fiche_text
    ):  # a fake ## N. heading inside a passage -> ambiguous parsing (D143)
        return FicheVerdict(
            JudgeStatus.MALFORMED,
            0,
            0,
            0,
            "non-sequential chapters (a ## N. line inside a verbatim passage?) — ambiguous parsing, needs hardening",
        )
    chapters = _chapters(fiche_text)
    n_chapters = len(chapters)
    if n_chapters == 0:
        return FicheVerdict(JudgeStatus.MALFORMED, 0, 0, 0, "no chapters (## N. ...)")
    n_templated = sum(1 for _, desc, _ in chapters if is_templated_description(desc))
    all_passages = _flatten(
        chapters
    )  # same flattening as verbatim_split — one single hearth, zero copy
    # A SEPARATE axis, computed BEFORE the raw gate: a truncation is read off the passage itself (its
    # length, its ending), not against the source — a fiche with no mirror raw has no reason to be
    # exempted from the finding. It NEVER changes the verdict.
    n_cut = len(truncated_passages(all_passages))
    if raw_text is None:
        return FicheVerdict(
            JudgeStatus.RAW_MISSING,
            n_chapters,
            0,
            0,
            "no mirror raw to verify the verbatim against",
            n_templated=n_templated,
            n_truncated=n_cut,
        )
    kept, _dropped = keep_verbatim(all_passages, raw_text)
    n_passages, n_verbatim = len(all_passages), len(kept)
    # The FLOOR, and it requires the raw: completeness is READ from the source, it is not guessed
    # from the passage. That is why it is computed HERE and not with the axes that precede the raw
    # gate.
    # EXCLUDE the historical amputations, or the floor punishes the fault of a DEAD ceiling.
    # Measured the error by arming it: the 6,087 amputated passages cut mid-word 38% of the time; when
    # they were included, this floor rejected 201 fiches out of 248 instead of 10. Measurement was done
    # on one population (excluding amputations) and the gate was armed on another (all of them) — the
    # exact fault this repository names "an EXCLUDED population is UNJUDGED," taken the other way round.
    amputes = set(map(id, truncated_passages(all_passages)))
    coupes_mot = cut_mid_word(tuple(p for p in all_passages if id(p) not in amputes), raw_text)
    n_mot = len(coupes_mot)
    n_filled = sum(1 for _, _, passages in chapters if passages)
    coverage = n_filled / n_chapters
    if all(title == _PLACEHOLDER_TITLE for title, _, _ in chapters) or n_passages == 0:
        return FicheVerdict(
            JudgeStatus.HOLLOW,
            n_chapters,
            n_passages,
            n_verbatim,
            "empty template: placeholder titles/content, no passage produced (the form, not the substance)",
            n_templated=n_templated,
            n_truncated=n_cut,
            n_cut_midword=n_mot,
        )
    if n_verbatim / n_passages < _MIN_VERBATIM_YIELD:
        return FicheVerdict(
            JudgeStatus.PARAPHRASED,
            n_chapters,
            n_passages,
            n_verbatim,
            f"only {n_verbatim}/{n_passages} passages are genuine verbatim — the rest is paraphrased/invented",
            n_templated=n_templated,
            n_truncated=n_cut,
            n_cut_midword=n_mot,
        )
    if n_verbatim < _MIN_VERBATIM_TOTAL or coverage < _MIN_COVERAGE:
        return FicheVerdict(
            JudgeStatus.THIN,
            n_chapters,
            n_passages,
            n_verbatim,
            f"under-distilled (stub): {n_verbatim} verbatim passages, {n_filled}/{n_chapters} chapters filled "
            f"(coverage {coverage:.0%})",
            n_templated=n_templated,
            n_truncated=n_cut,
            n_cut_midword=n_mot,
        )
    if n_mot:
        # THE FLOOR BITES. Measured before arming it: 13 passages in 10 fiches across the whole
        # shelf — actionable, not a flood. The natural criterion ("does not end on punctuation")
        # would have flagged 4,248 in 221 fiches and flipped 22 books, ALL math books: it was
        # accusing the book's discipline, not a fault. Cf. `cut_mid_word`.
        return FicheVerdict(
            JudgeStatus.CUT,
            n_chapters,
            n_passages,
            n_verbatim,
            f"{n_mot} passage(s) stop MID-WORD in the source — the quote is truncated in the "
            "middle of a word, these are not the author's complete words",
            n_templated=n_templated,
            n_truncated=n_cut,
            n_cut_midword=n_mot,
        )
    p2 = f" ; P2 template {n_templated}/{n_chapters} (not synthesized)" if n_templated else ""
    return FicheVerdict(
        JudgeStatus.OK,
        n_chapters,
        n_passages,
        n_verbatim,
        f"P3 faithful: {n_verbatim}/{n_passages} verbatim, {n_filled}/{n_chapters} chapters filled"
        + p2,
        n_templated=n_templated,
        n_truncated=n_cut,
        n_cut_midword=n_mot,
    )
