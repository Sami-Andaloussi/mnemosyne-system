"""Retrieval golden-set ((3)-2a / D69) — the recall floor EARNED from a golden set, not hand-set.

The retrieval leg (D65) admits "I don't know" when the best dense score is below a floor
(``min_score``, invariant 14) — the barrier against inventing a confident answer where there is none
(D100). That floor was a *declared constant* (bge-m3 → 0.55): a reasoned but DISCRETIONARY guess about
the score distribution, and a discretionary guess can err in BOTH directions — too low invents, too
HIGH silently drops a genuinely relevant passage (the symptom that opened (3)-2a — a "price zones"
passage scoring 0.526 rejected under a 0.55 floor). D69 says a number like this is not hand-set: it is
MEASURED against a labelled golden set. This module is that measurement.

**The sweep.** :func:`sweep_floor` takes a ``(query, passage) → similarity`` callable and a set of
labelled cases (each query with its RELEVANT passages and its DISTRACTORS), and evaluates every
observed similarity as a candidate floor, returning the one whose ``>= floor`` return-decision
MAXIMISES F1 over the golden set. F1 (not raw recall) is the objective on purpose: raw recall is
trivially maximised by a floor of 0 — return everything, i.e. invent (invariant 14); F1 balances
recovering the relevant against admitting the distractors, so the floor is lowered ONLY as far as the
golden set proves it earns. On an F1 tie the HIGHER floor wins — the prudent, fail-closed lean (admit
"I don't know" more readily than admit a distractor, invariant 14 / D100).

**Fail-closed (F3 / D69 / D100).** A golden set with no relevant passage to recover (empty, or every
case all-distractor) proves NOTHING — so it may never RELAX the floor: it returns the maximal floor
:data:`_FAIL_SAFE_FLOOR` (1.0, admit almost everything as "I don't know") at F1 0, the same fail-safe
posture as an empty extraction / fidelity golden scoring 0 (untrusted). A missing golden can never talk
Mnémosyne into a laxer floor.

**Honesty (F3 / D126).** The scorer is PURE — it never imports an embedder; it measures the stub
hashing encoder (shared vocabulary ⇒ separable) exactly as it will measure real bge-m3. The SEED below
is a hand-labelled seed, NOT a deployment corpus: it proves the mechanism (a separating embedder earns a
clean floor at F1 1.0, a blind one earns only a poor F1) and pins the wiring. The real floor NUMBER —
real bge-m3 over a golden set drawn from the user's corpus — is read off at ignition ((3)-2b), and
ADOPTING it (overriding the embedder's declared ``recall_floor``) is an [OPERATOR] gesture, never
auto-applied from this stub measurement: this module RECOMMENDS a floor, it does not silently
re-floor (D100).

Decisions: D69 (calibrate against a golden set) · D65 (retrieval fusion / the floor) · D68 (min_score
origin, embedder-carried floor) · D100 / invariant 14 (admit low recall, never invent) · D126
(brick-free, callable seam). Code & docstrings English (D117); ``public`` / ``perso`` / ``sensible``
keep their French tokens (D33 / D66).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

#: The maximal, fail-safe floor (invariant 14): only a ~identical passage clears it, so almost
#: everything is admitted as "I don't know". The posture a golden set that proves nothing falls back to
#: (it may never RELAX the floor, D100).
_FAIL_SAFE_FLOOR = 1.0


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    """One labelled retrieval example: a ``query``, the passages that SHOULD clear the floor
    (``relevant``), and near-topic ``distractors`` that should NOT — the two classes the floor must
    separate (D69). A case with no relevant passage contributes only distractors (it can never justify
    lowering the floor)."""

    query: str
    relevant: frozenset[str]
    distractors: frozenset[str]


@dataclass(frozen=True, slots=True)
class FloorScore:
    """The recall floor EARNED from the golden set ((3)-2a / D69): the floor that maximised F1, plus the
    return-decision quality (precision / recall / F1) AT that floor. ``floor`` is the number the user
    reads off at ignition to (optionally) override the embedder's declared ``recall_floor`` — a
    RECOMMENDATION, never auto-applied (D100). A poor ``f1`` is the honest signal that the embedder
    cannot cleanly separate on this golden (the recommendation should not be adopted)."""

    floor: float
    precision: float
    recall: float
    f1: float
    cases: int


def _score(similarity: Callable[[str, str], float], query: str, passage: str) -> float:
    """Score one ``(query, passage)`` pair, netting an UNSCORABLE result — a raising similarity, OR a
    non-finite output (NaN / ±inf) — as a FAILED match: the sentinel ``-inf``, below every finite floor
    (recall loss). So a non-finite score never reaches a ``>=`` comparison (where ``nan >= x`` would be a
    silent, always-False non-match) — the netting is DELIBERATE, not incidental. Never crashes the
    calibration (F3), exactly as the extraction / fidelity scorers net a raising engine."""
    try:
        score = similarity(query, passage)
    except Exception:  # noqa: BLE001 - a raising similarity is a failed match, not an aborted run (F3)
        return float("-inf")
    return (
        score if math.isfinite(score) else float("-inf")
    )  # NaN / ±inf ⇒ unscorable ⇒ non-match sentinel


def _prf(
    true_positive: int, false_positive: int, false_negative: int
) -> tuple[float, float, float]:
    """Precision / recall / F1 for a return-decision at one floor. NB the divergence from the
    extraction / fidelity scorers: an empty numerator here is 0.0, NOT the vacuous 1.0 — a floor that
    returns nothing (tp+fp == 0) is a useless floor, never vacuously perfect, so the sweep never
    prefers a floor above every relevant score. F1 is 0 whenever there is no true positive."""
    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive)
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative)
        else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def sweep_floor(
    similarity: Callable[[str, str], float], cases: Sequence[RetrievalCase]
) -> FloorScore:
    """Sweep the recall floor over a golden set, returning the F1-maximising floor (D69 / invariant 14).

    ``similarity`` is any ``(query, passage) → score`` callable (real bge-m3 cosine behind the port, or
    a test double) so the sweep never imports a brick (D126). Every relevant and distractor passage is
    scored against its query; the candidate floors are the DISTINCT observed (finite) scores — the only
    values at which the ``>= floor`` decision changes — each evaluated micro-averaged over ALL cases.
    The floor with the highest F1 wins; scanning high → low, a strict-improvement update means an F1
    tie KEEPS the higher (more prudent) floor — admit "I don't know" more readily than admit a
    distractor (invariant 14 / D100).

    A golden set with no relevant passage anywhere (or nothing scorable) proves nothing and may not
    RELAX the floor: it returns the fail-safe :data:`_FAIL_SAFE_FLOOR` (1.0) at F1 0 — the same
    fail-closed posture as an empty extraction / fidelity golden (D69 / D100)."""
    labelled: list[tuple[float, bool]] = []  # (similarity, is_relevant) over every labelled pair
    for case in cases:
        labelled.extend(
            (_score(similarity, case.query, passage), True) for passage in case.relevant
        )
        labelled.extend(
            (_score(similarity, case.query, passage), False) for passage in case.distractors
        )
    # A golden may only LOWER the floor on the strength of a relevant passage it actually recovered, so
    # the fail-safe keys on a FINITE relevant score — not a mere relevant LABEL (a relevant pair that
    # raised / scored non-finite recovered nothing, audit (3)-2a finding 1). This one check subsumes both
    # "no relevant label" and "nothing scorable at all" (either ⇒ no finite relevant), so a golden that
    # proves nothing can never RELAX the floor (invariant 14 / D69 / D100) — the maximal fail-safe floor,
    # the same posture an empty extraction / fidelity golden takes.
    if not any(math.isfinite(s) for s, relevant in labelled if relevant):
        return FloorScore(
            floor=_FAIL_SAFE_FLOOR, precision=0.0, recall=0.0, f1=0.0, cases=len(cases)
        )
    total_relevant = sum(
        relevant for _, relevant in labelled
    )  # LABEL count: an unscorable relevant is a FN
    candidates = sorted({s for s, _ in labelled if math.isfinite(s)}, reverse=True)  # high → low
    best: FloorScore | None = None
    for (
        floor
    ) in candidates:  # high → low, so a strict-improvement update keeps the HIGHER floor on a tie
        cleared_relevant = sum(1 for s, relevant in labelled if relevant and s >= floor)
        cleared_distractor = sum(1 for s, relevant in labelled if not relevant and s >= floor)
        precision, recall, f1 = _prf(
            cleared_relevant, cleared_distractor, total_relevant - cleared_relevant
        )
        if best is None or f1 > best.f1:
            best = FloorScore(
                floor=floor, precision=precision, recall=recall, f1=f1, cases=len(cases)
            )
    assert best is not None  # candidates non-empty ⇒ the loop ran at least once
    return best


#: A hand-labelled SEED (F3: not a deployment corpus) — enough to prove the floor earns and pin the
#: wiring. Each query's relevant passages SHARE its vocabulary while the distractors do not, so the
#: stub hashing embedder separates them (a clean floor at F1 1.0) exactly as real bge-m3 will on real
#: content. Expand against a local calibration set at ignition to read the real floor
#: ((3)-2b, traced debt).
RETRIEVAL_SEED: tuple[RetrievalCase, ...] = (
    RetrievalCase(
        query="price zones support resistance",
        relevant=frozenset(
            {
                "The strategy marks price zones as support and resistance.",
                "Entries trigger at the support and resistance price zones.",
            }
        ),
        distractors=frozenset(
            {
                "The service runs scheduled backups every night.",
                "The embedder bge-m3 is multilingual.",
            }
        ),
    ),
    RetrievalCase(
        query="position sizing risk per trade",
        relevant=frozenset(
            {
                "Position sizing caps the risk per trade at one percent.",
                "The risk per trade drives the position sizing rule.",
            }
        ),
        distractors=frozenset(
            {
                "A researcher lives in Riverton.",
                "The renderer produces a Typst PDF.",
            }
        ),
    ),
)


def load_retrieval_golden(path: Path | str) -> tuple[RetrievalCase, ...]:
    """Load a retrieval golden set from a JSON file ((3)-2b) — the REAL corpus-drawn cases that expand
    the hand-labelled :data:`RETRIEVAL_SEED` at ignition to read off the real floor over bge-m3.

    The file lives OUTSIDE git (``knowledge/golden/``, gitignored): its passages are verbatim excerpts
    of the user's corpus (perso / copyrighted), so they must never enter the tracked history — the same
    garde-fou as the raw shelf and the bubbles (D71 / D137). Shape: a non-empty JSON list of objects
    ``{"query": str, "relevant": [str, ...], "distractors": [str, ...]}`` (``distractors`` optional; a
    case with no ``relevant`` contributes only distractors, exactly as :class:`RetrievalCase` allows).

    Fail-closed (F3 / D100): a malformed file RAISES (a :class:`ValueError`, or a ``JSONDecodeError`` /
    ``OSError`` from the read) rather than silently yielding a laxer or empty golden that could talk the
    floor down — a broken golden must STOP the calibration, never quietly weaken the barrier. (A
    well-formed but all-distractor golden is still handled by :func:`sweep_floor`'s own fail-safe: it
    proves nothing, so it can never RELAX the floor below the maximal :data:`_FAIL_SAFE_FLOOR`.) An
    ABSENT file is the caller's concern: the ignition run falls back to :data:`RETRIEVAL_SEED` only when
    no real golden is in place yet (the D126 default), never on a present-but-corrupt one."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"retrieval golden {path}: expected a non-empty JSON list of cases")
    cases: list[RetrievalCase] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"retrieval golden {path}: case {i} is not a JSON object")
        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"retrieval golden {path}: case {i} has an empty or non-string query")
        relevant = item.get("relevant", [])
        distractors = item.get("distractors", [])
        for name, value in (("relevant", relevant), ("distractors", distractors)):
            if not isinstance(value, list) or not all(
                isinstance(p, str) and p.strip() for p in value
            ):
                raise ValueError(
                    f"retrieval golden {path}: case {i} field {name!r} must be a list of non-empty strings"
                )
        overlap = frozenset(relevant) & frozenset(distractors)
        if overlap:  # a passage cannot be both the answer and a distractor for the same query (F3)
            raise ValueError(
                f"retrieval golden {path}: case {i} lists {len(overlap)} passage(s) as both relevant and distractor"
            )
        cases.append(
            RetrievalCase(
                query=query, relevant=frozenset(relevant), distractors=frozenset(distractors)
            )
        )
    return tuple(cases)
