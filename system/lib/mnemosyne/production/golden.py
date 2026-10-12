"""Extraction golden-set (③-3c) — a chiffered exit criterion + the plan-B trigger (D69).

The living-memory lot does NOT claim a perfect extractor. It poses a *measurable* bar: score the
configured fact extractor against a labelled golden-set (precision / recall / F1 of the triples it
proposes) and, below a threshold, fall back to plan B — hand the operator a readable ``.md`` note
instead of auto-imposing a doubtful graph (:func:`~mnemosyne.production.memory.note_fiche`; "no
auto-imposed graph", D58). The scorer is pure — it takes the extractor as a callable — so it measures
the stub (abstains ⇒ recall 0 ⇒ below bar ⇒ plan B, correctly) exactly as it will measure the real
MLX extractor once installed.

**Honesty (F3).** :data:`GOLDEN_SEED` is a hand-labelled SEED, not étage ②'s corpus — it proves the
mechanism (a perfect extractor scores 1.0, an abstaining one 0.0) and pins the wiring; expanding it
against a real ② corpus, and measuring the real extractor to SET the runtime trust flag
(``Runtime.graph_extraction_trusted``), is traced debt at ignition. :data:`MIN_EXTRACTION_F1` is
provisional, to be calibrated like the retrieval ``min_score`` was (D68 / D69).

Decisions: D69 (calibrate against a golden set) · D120 (aggregator quality) · D100 (extraction in
the loop, under the net) · D58 (plan B, ``.md`` fiches). Code & docstrings English (D117).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

#: A bare extracted claim — ``(subject, predicate, obj)``, engine-agnostic.
Triple = tuple[str, str, str]

#: Runs of separators — whitespace, underscores, hyphens, and any non-alphanumeric punctuation —
#: that :func:`_canon` collapses so surface-only spelling never scores as a miss (see below).
_SEPARATORS = re.compile(r"[\W_]+", re.UNICODE)


def _canon(element: str) -> str:
    """Canonicalise ONE triple element (subject / predicate / obj) for a sense-level match (D69).

    The real MLX extractor writes a claim in prose surface — ``"Low price"``, ``"high rate of
    return"`` — while the hand-labelled golden writes the SAME claim snake-cased — ``"low_price"``,
    ``"high_rate_of_return"``. Scoring those as different triples measured a SPELLING mismatch, not an
    extraction miss (the ③-7 diagnostic: F1 collapsed on surfaces, not on content). This folds both
    sides to a common form BEFORE the set arithmetic: lowercase, then collapse every run of separators
    (whitespace / ``_`` / ``-`` / punctuation) to a single ``_`` and strip the ends. So ``"Low price"``,
    ``"low_price"`` and ``"low-price"`` all become ``low_price``.

    Deliberately CONSERVATIVE — a normalisation, not a fuzzy or semantic match (no stemming, no
    synonyms, no edit-distance): it only erases separator/case noise, so two genuinely different words
    still score as a miss and the bar keeps biting. Applied per-element (never to the joined triple), so
    a boundary shift like ``("a b", "c")`` vs ``("a", "b c")`` cannot silently collide across fields."""
    return _SEPARATORS.sub("_", element).strip("_").lower()


def _canon_triple(triple: Triple) -> Triple:
    """Canonicalise each element of a triple (:func:`_canon`) for the sense-level overlap (D69)."""
    return (_canon(triple[0]), _canon(triple[1]), _canon(triple[2]))


#: Provisional F1 bar an extractor must clear to be trusted with the graph (else plan B). Calibrate
#: against a real ② corpus, like the retrieval ``min_score`` (0.55) was recalibrated at ③-2a (D69).
MIN_EXTRACTION_F1 = 0.6


@dataclass(frozen=True, slots=True)
class GoldenCase:
    """One labelled example: the ``content`` and the exact set of triples it SHOULD yield."""

    content: str
    expected: frozenset[Triple]


@dataclass(frozen=True, slots=True)
class ExtractionScore:
    """The measured quality of an extractor over a golden-set — precision / recall / F1 (D69)."""

    precision: float
    recall: float
    f1: float
    cases: int

    @property
    def trusted(self) -> bool:
        """Whether the extractor clears :data:`MIN_EXTRACTION_F1` — the plan-B decision (D58)."""
        return self.f1 >= MIN_EXTRACTION_F1


def score_extraction(
    extract: Callable[[str], frozenset[Triple]], cases: Sequence[GoldenCase]
) -> ExtractionScore:
    """Score ``extract`` against ``cases`` — micro-averaged precision / recall / F1 over triples.

    ``extract`` is any content→triples callable (the real model behind the Guard, or a test
    double), so the scorer never imports a brick (D126). A true positive is a proposed triple that
    is expected; precision guards against invention (a doubtful extractor that hallucinates triples
    scores low), recall against silence (an abstaining stub scores 0). An extractor that abstains on
    a non-empty golden-set scores recall 0 → F1 0 → plan B, the fail-safe posture. A golden-set with
    NOTHING to find (empty, or every case expecting no triple) is fail-CLOSED (F1 0, untrusted): a
    missing or mis-configured golden can never vacuously certify an extractor into the graph (D69).

    Both sides are canonicalised (:func:`_canon`) before the overlap, so a match is at the level of
    SENSE — ``("Low price", "implies", "high rate of return")`` scores as the golden's snake-cased
    ``("low_price", "implies", "high_rate_of_return")`` — not the raw surface an extractor happens to
    print. The fold is separator/case only (conservative, D69): it never lets two different words pass."""
    if not any(case.expected for case in cases):
        return ExtractionScore(precision=0.0, recall=0.0, f1=0.0, cases=len(cases))
    true_positive = false_positive = false_negative = 0
    for case in cases:
        try:
            got = extract(case.content)
        except Exception:  # noqa: BLE001 - a raising extractor is a FAILED extraction (recall loss), not
            got = (
                frozenset()
            )  # an aborted run: it scores as untrusted, never crashes the calibration (F3)
        got_canon = {_canon_triple(triple) for triple in got}
        want_canon = {_canon_triple(triple) for triple in case.expected}
        true_positive += len(got_canon & want_canon)
        false_positive += len(got_canon - want_canon)
        false_negative += len(want_canon - got_canon)
    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive)
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative)
        else 1.0
    )
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return ExtractionScore(precision=precision, recall=recall, f1=f1, cases=len(cases))


# ── GROUNDEDNESS (D148) — the gate that REPLACED the F1 above for the trust flag ────────────────
#
# Why this exists: `score_extraction` cannot measure a generative extractor. Measured 2026-07-17 on the
# REAL 30-case corpus golden — F1 0.058, and the number is UNINTERPRETABLE, not a verdict:
#   - the golden holds 29 DISTINCT predicates for 47 triples (`known_as` / `is_known_as` /
#     `also_known_as` are three spellings of ONE relation) — no extractor can guess which the labeller
#     picked, because the labeller had no convention either;
#   - it is not exhaustive, so a TRUE unlabelled fact scores as a false positive (92 emitted vs 47
#     labelled ⇒ precision structurally capped ~0.51 even if every triple were right);
#   - deepest: ONE sentence admits MANY valid triple decompositions. The golden froze one framing;
#     exact match therefore demands the extractor GUESS THE LABELLER'S FRAMING. That is not measurable
#     (even a perfectly-scored predicate caps F1 ~0.21).
# So the F1 gate was not a bar, it was a WALL — and it dead-locked the living graph (INVENTAIRE #1).
#
# What the gate is actually FOR: deciding whether the extractor can be trusted to feed the graph. The
# risk it must hold is that THE GRAPH FILLS WITH LIES. Agreement with a labeller's framing does not
# measure that. Groundedness does: an entity absent from the passage is an entity the model brought
# from somewhere else — which is exactly the observed failure (a passage stating only that
# dependencies are inverted yielded SIX triples recited from training data).
#
# ENTITIES only, predicate deliberately FREE: naming a relation is an inherently linguistic act (a
# passage reading "Jegadeesh and Titman's paper" legitimately yields the predicate `wrote`, a word the
# passage never contains). Measured: scoring the predicate too flagged 13/58 — every one a false alarm
# on an honest verb (`wrote`, `outlines`, `equals`). Freeing it buys that back, but it is a genuine
# GIVE-UP, not a free win — see residue #4.
#
# HONEST RESIDUES — what this does NOT catch, stated up front (order = written before the guarantee):
#   1. A SCRAMBLE stays grounded: re-order a passage's own ENTITY words into a false claim and every
#      one is still "from the passage". Groundedness bounds where the ENTITY material came from (never
#      the predicate, #4), and never whether the assembly is true. NECESSARY, not sufficient.
#   2. It is partly CIRCULAR: `_EXTRACT_PROMPT` now TELLS the model to use the passage's vocabulary, and
#      this measures whether it did. So the gate tests CONTRACT-COMPLIANCE on the entities, not intrinsic
#      skill. Defensible for a graph — compliance is what makes the ENTITIES safe to store — but it is
#      not a claim about how good the model is, nor (see #4) about the predicate, and must not read as one.
#   3. Recall/usefulness is NOT measured. Deliberate: a poorer graph is recoverable by re-extracting; a
#      lying graph is not. `MIN_YIELD` below is the anti-vacuity floor, not a quality measure.
#   4. The PREDICATE is unanchored — an INVENTION CHANNEL this gate does not watch. An extractor pairing
#      two real passage entities with a WHOLLY fabricated relation ("(inflation, was secretly caused by,
#      deflation)" — every entity grounded, the claim invented) scores grounded 1.0, trusted, foreign ().
#      A fabricated predicate IS a lie in the graph, the very thing the gate exists to keep out, and it
#      is the price of dodging the 13/58 false alarms above. Mitigated, NOT closed, elsewhere: the
#      prompt asks for "the relation the passage asserts, as a short verb phrase", and the REAL extractor
#      was measured faithful on its predicates — but THIS gate does not prove it, and must not be read as
#      proving the extractor cannot invent a relation.
#
#: Content words carry the claim; function words carry none, so their absence proves nothing. Kept
#: SMALL and closed on purpose: every word added here is a word the extractor may invent for free.
_FUNCTION_WORDS: frozenset[str] = frozenset(
    """the a an of to its it is in and s that this by for as are be was were on with or at from
    which when""".split()
)

#: Share of emitted triples whose ENTITIES are all built from the passage. PROVISIONAL, and honest about
#: its basis: HAND-SET, with margin below a measurement — not swept like the retrieval floor (which is a
#: real argmax-F1 over labels, `sweep_floor`). Measured: the prompted extractor scored **1.000** (58/58
#: triples over 30 corpus passages), its un-prompted self 0/6 on the recital case. 0.95 sits below the
#: 1.000 with room, yet is not vacuous — it would still FAIL a run that came back at, say, 3 foreign
#: entities in 58 (0.948). One model, one corpus slice: re-measure when either changes (D69's discipline).
MIN_GROUNDEDNESS = 0.95

#: Triples per passage, floor (HAND-SET with margin, like MIN_GROUNDEDNESS). WHY it must exist:
#: groundedness alone is trivially gamed by SILENCE — an extractor that emits one safe triple, or nothing,
#: scores 1.000. That is the same vacuity `_scoreless` golden sets are fail-closed against (D100): a gate
#: an abstaining extractor passes is not a gate. Measured on FACT-DENSE passages: the real extractor
#: yields 1.9/passage where the hand labeller wrote 1.6, so 1.0 has headroom and still catches an
#: extractor that has started skipping passages. NB this floor ASSUMES the passages are fact-dense like
#: the golden's; over a fact-sparse slice a competent extractor would fail it — so feed it dense text
#: (`main()` uses the golden's own cases), never arbitrary prose.
MIN_YIELD = 1.0


@dataclass(frozen=True, slots=True)
class GroundednessScore:
    """How much of what an extractor SAYS was actually IN what it read (D148)."""

    grounded: float
    yield_per_passage: float
    triples: int
    passages: int
    #: The offenders, for diagnosis — ``(passage_index, triple, foreign_words)``. A number says the
    #: gate failed; this says WHY, so a failure is actionable instead of merely red.
    foreign: tuple[tuple[int, Triple, tuple[str, ...]], ...] = ()

    @property
    def trusted(self) -> bool:
        """Whether BOTH bars clear — grounded enough to not lie, productive enough to not be vacuous."""
        return self.grounded >= MIN_GROUNDEDNESS and self.yield_per_passage >= MIN_YIELD


def _content_words(element: str) -> frozenset[str]:
    """The claim-bearing words of a triple element (canonicalised, function words dropped)."""
    return frozenset(w for w in _canon(element).split("_") if w and w not in _FUNCTION_WORDS)


def score_groundedness(
    extract: Callable[[str], frozenset[Triple]], passages: Sequence[str]
) -> GroundednessScore:
    """Measure how far an extractor stays INSIDE what it read — no golden, no judge (D148 / D100).

    Needs no labelled expectation at all, so it runs over ANY passage of the real corpus rather than a
    hand-labelled 30. Each emitted triple is GROUNDED iff every content word of its subject and obj
    appears in the passage; the predicate is free (see the module note). A raising extractor yields
    nothing for that passage — a recall loss, never a crashed calibration (symmetric with
    :func:`score_extraction`).

    Fail-closed on vacuity (D100), on THREE fronts — each was a way to score a hollow 1.0:
    NO passage, or an extractor that emits NOTHING, returns ``grounded=0.0``; and a triple that names
    no entity at all (subject and obj empty or function-words-only) counts as UNGROUNDED, never as a
    free pass. That last clause is load-bearing: without it a one-line extractor emitting one
    ``("", "", "")`` per passage — reading nothing — scored grounded 1.0 / yield 1.0 and cleared both
    bars (the D148 audit found it). "It never lied because it never said anything" must not certify
    an extractor, exactly as a missing golden may not."""
    if not passages:
        return GroundednessScore(grounded=0.0, yield_per_passage=0.0, triples=0, passages=0)
    grounded = 0
    total = 0
    foreign: list[tuple[int, Triple, tuple[str, ...]]] = []
    for index, passage in enumerate(passages, 1):
        try:
            got = extract(passage)
        except Exception:  # noqa: BLE001 - a raising extractor is a FAILED extraction, not a crashed run
            continue
        available = _content_words(passage)
        for triple in got:
            total += 1
            entity_words = _content_words(triple[0]) | _content_words(triple[2])
            outside = entity_words - available
            # A triple is grounded iff it NAMES an entity (has content words) AND every one is from
            # the passage. The `entity_words` non-emptiness clause is the anti-vacuity teeth: without
            # it, a triple whose subject/obj are only function words or empty strings — ("", "", "")
            # / ("the", "is", "a") — yields `outside == set()` and would count as grounded, so a
            # one-line extractor that emits ONE such triple per passage and NEVER READS scores
            # grounded 1.0, yield 1.0, and passes both bars (found by the D148 audit). It names
            # nothing, so it is NOT grounded — it is vacuous, reported with an explicit marker so the
            # diagnosis reads "named no entity" rather than a misleading empty foreign-word list.
            if not entity_words:
                foreign.append((index, triple, ("<no entity named>",)))
            elif outside:
                foreign.append((index, triple, tuple(sorted(outside))))
            else:
                grounded += 1
    if total == 0:
        return GroundednessScore(
            grounded=0.0, yield_per_passage=0.0, triples=0, passages=len(passages)
        )
    return GroundednessScore(
        grounded=grounded / total,
        yield_per_passage=total / len(passages),
        triples=total,
        passages=len(passages),
        foreign=tuple(foreign),
    )


#: A hand-labelled SEED (F3: not étage ②'s corpus) — enough to prove the bar bites and pin the
#: wiring. Expand against a real ② corpus at ignition (traced debt).
GOLDEN_SEED: tuple[GoldenCase, ...] = (
    GoldenCase(
        "A researcher lives in Riverton.", frozenset({("researcher", "lives_in", "Riverton")})
    ),
    GoldenCase(
        "Mnémosyne is written in Python.", frozenset({("Mnémosyne", "written_in", "Python")})
    ),
    GoldenCase(
        "The service runs local backups.", frozenset({("service", "runs", "local_backups")})
    ),
)


def load_extraction_golden(path: Path | str) -> tuple[GoldenCase, ...]:
    """Load an extraction golden set from a JSON file (③ ignition) — the REAL corpus-drawn cases that
    expand the hand-labelled :data:`GOLDEN_SEED` to read off the extraction F1 over the real MLX model.

    Symmetric to :func:`~mnemosyne.stores.golden.load_retrieval_golden`. The file lives OUTSIDE git
    (``knowledge/golden/``, gitignored): its passages are verbatim excerpts of the operator's corpus
    (perso / copyrighted), so they must never enter the tracked history — the same garde-fou as the raw
    shelf and the bubbles (D71 / D137). Shape: a non-empty JSON list of objects
    ``{"content": str, "expected": [[subject, predicate, obj], ...]}`` — each ``expected`` entry a
    3-element ``[s, p, o]`` list of strings (the exact triples the passage SHOULD yield). Unknown keys
    (e.g. an inline ``_note`` / ``_domain`` / ``_source``) are ignored, never a parse failure.

    Fail-closed (F3 / D100): a malformed file RAISES (a :class:`ValueError`, or a ``JSONDecodeError`` /
    ``OSError`` from the read) rather than silently yielding a laxer or empty golden that could vacuously
    certify an extractor — a broken golden must STOP the calibration, never quietly weaken the bar. (An
    all-``expected``-empty golden is still handled by :func:`score_extraction`'s own fail-safe: nothing
    to find ⇒ F1 0, untrusted.) An ABSENT file is the caller's concern: the ignition run falls back to
    :data:`GOLDEN_SEED` only when no real golden is in place yet (the D126 default), never on a
    present-but-corrupt one."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"extraction golden {path}: expected a non-empty JSON list of cases")
    cases: list[GoldenCase] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"extraction golden {path}: case {i} is not a JSON object")
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"extraction golden {path}: case {i} has an empty or non-string content"
            )
        expected = item.get("expected", [])
        if not isinstance(expected, list):
            raise ValueError(f"extraction golden {path}: case {i} field 'expected' must be a list")
        triples: set[Triple] = set()
        for triple in expected:
            if (
                not isinstance(triple, (list, tuple))
                or len(triple) != 3
                or not all(isinstance(part, str) and part.strip() for part in triple)
            ):
                raise ValueError(
                    f"extraction golden {path}: case {i} has a triple that is not "
                    "[subject, predicate, obj] of non-empty strings"
                )
            triples.add((triple[0], triple[1], triple[2]))
        cases.append(GoldenCase(content=content, expected=frozenset(triples)))
    return tuple(cases)
