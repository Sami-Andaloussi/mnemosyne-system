"""The generator↔critic loop on a rubric (D79 / D75 / D39-⑥) — the *plancher* nerve of the soul.

Producing is a first-order finality (D79), and the way Mnemosyne "graves what works" is a loop:
**produce → a DISTINCT critic grades the draft on a rubric → refine on the feedback → until the bar
is met** (graded until it clears the bar, 6/6). The three parts it rests on already
exist — a governed model (the Runner D104, or :func:`~mnemosyne.agents.loop.run_agent`), the
producer≠verifier gate (:func:`~mnemosyne.production.verifier.require_distinct`, D75 / D100-6), and the
human promotion portal
(:class:`~mnemosyne.production.workflow.ProductionWorkflow.promote`, D79) — but nothing assembled them
into a graded loop. This module is that assembly, and only that.

Four properties are structural, not optional:

* **Producer ≠ verifier, intrinsically (D75 / D100-6 / D39-⑥).** The generator and the evaluator carry
  their own ``identity``; :func:`refine` refuses fail-closed (:class:`RefinementRefused`) unless the
  two are DISTINCT — an adversarial critic in a separate instance, never a self-audit.
* **Bounded (D78).** The loop runs at most ``max_rounds`` times — a draft that never clears the bar
  cannot spin forever (anti-runaway, the same floor the scheduler and the orchestration engine carry).
* **Non-destructive (invariant 2).** The BEST attempt seen is always kept, so a later, worse revision
  never loses the best draft the loop produced; the result reports whether the bar was actually
  ``reached`` (a FLAG for the user when it was not).
* **It produces, it does not publish (D79 / D96).** The loop returns a draft that PASSED the rubric;
  it never promotes it. Promotion to a validated deliverable stays the human gesture through
  :meth:`ProductionWorkflow.promote` (a distinct verifier + the user's sign-off) — the automation
  produces, it does not publish (nothing sensible leaves in auto, D66).

The generator and the evaluator are PORTS (:class:`Generator` / :class:`Evaluator`), injected at
wiring: the concrete Runner-backed prises (:class:`~mnemosyne.production.refiners.RunnerGenerator` /
:class:`~mnemosyne.production.refiners.RunnerCritic`, assembled by
:meth:`~mnemosyne.api.core_api.CoreApi.produce`) decode through a governed Runner (D104) whose real
model lands at ③ ignition, so the loop's MECHANISM is proven brick-free here against deterministic
stubs (D126). A richer agent-generator (:func:`~mnemosyne.agents.loop.run_agent`, with tools) is a
later impl of the SAME generator port, not a change to this loop. The concrete per-task rubrics (a
trading deliverable's criteria) are *contenu*, passed in — not baked here. Code & docstrings English
(D117).

Decisions: D79 (production = 1st-order finality; the free internal iteration; auto = draft-only) ·
D75 / D100-6 / D39-⑥ (producer ≠ verifier, an adversarial critic isolated) · D78 (bounded, anti-runaway)
· invariant 2 (non-destructive) · D96 / D66 (produce, never auto-publish).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..ports import ErrorCode, MnemosyneError
from .verifier import require_distinct


class RefinementRefused(MnemosyneError):
    """The loop refused fail-closed — a self-audit (generator == evaluator) or a cheating critic.

    Like a Guard denial (``DENIED``): the plancher loop never trusts a draft graded by its own
    producer, and never a critic that passes a criterion outside the rubric (D75 / D100-6)."""

    code = ErrorCode.DENIED


@dataclass(frozen=True, slots=True)
class Rubric:
    """A grading rubric: named criteria + the passing threshold (the "N out of M" bar, D79).

    Criteria are named and DISTINCT (a duplicate would double-count); the threshold is how many must
    be met to clear the bar (``1..len(criteria)``). The rubric is *contenu* — a concrete task passes
    its own criteria in; this class only holds and validates the shape."""

    criteria: tuple[str, ...]
    threshold: int

    def __post_init__(self) -> None:
        if not self.criteria:
            raise ValueError("a rubric needs at least one criterion")
        if len(set(self.criteria)) != len(self.criteria):
            raise ValueError(f"rubric criteria must be distinct, got {self.criteria!r}")
        if not 1 <= self.threshold <= len(self.criteria):
            raise ValueError(f"threshold must be in 1..{len(self.criteria)}, got {self.threshold}")


@dataclass(frozen=True, slots=True)
class Score:
    """A critic's verdict on one draft: which criteria it MET, plus refine-me feedback (D79).

    ``passed`` is the set of criteria the evaluator judged met (a subset of the rubric's — the loop
    refuses a critic that invents a criterion). ``feedback`` is what the next round feeds back to the
    generator so it can improve where it fell short."""

    passed: frozenset[str]
    feedback: str = ""

    @property
    def total(self) -> int:
        """How many criteria were met — compared to the rubric's threshold to clear the bar."""
        return len(self.passed)


@runtime_checkable
class Generator(Protocol):
    """Produces a draft from a brief, optionally refining on the critic's feedback (D79).

    Carries its own ``identity`` so the loop can prove it is DISTINCT from the evaluator (D75). The
    first real impl is :class:`~mnemosyne.production.refiners.RunnerGenerator` (a governed Runner
    completion); a multi-turn agent (:func:`~mnemosyne.agents.loop.run_agent`) is an equally valid
    impl of this same port."""

    identity: str

    def generate(self, brief: str, *, feedback: str | None = None) -> str: ...


@runtime_checkable
class Evaluator(Protocol):
    """Grades a draft against a rubric — the adversarial critic in a DISTINCT instance (D39-⑥ / D75).

    Carries its own ``identity`` (≠ the generator's). The real impl is
    :class:`~mnemosyne.production.refiners.RunnerCritic`, a structured-output completion (grammar-bound,
    D104) wired at ignition; the mechanism is proven here against a stub."""

    identity: str

    def evaluate(self, draft: str, rubric: Rubric) -> Score: ...


@dataclass(frozen=True, slots=True)
class RefinementResult:
    """The outcome of a loop: the best draft, its score, how many rounds ran, and whether it cleared.

    ``reached`` is the FLAG: True ⇒ the draft met the rubric's threshold; False ⇒ the loop hit
    ``max_rounds`` without clearing the bar and returns its BEST attempt (non-destructive, invariant
    2) for the user to judge — never a silent "good enough"."""

    draft: str
    score: Score
    rounds: int
    reached: bool


def refine(
    generator: Generator,
    evaluator: Evaluator,
    *,
    brief: str,
    rubric: Rubric,
    max_rounds: int,
) -> RefinementResult:
    """Run the generator↔critic loop until the rubric is met or ``max_rounds`` is spent (D79 / D78).

    Each round: the generator produces (refining on the previous round's feedback), the DISTINCT
    evaluator grades against the rubric, and if the score meets the threshold the loop returns that
    draft. Otherwise the feedback feeds the next round, up to ``max_rounds`` (bounded, D78) — then the
    BEST attempt is returned with ``reached=False`` (non-destructive, invariant 2; a FLAG for the user).

    Fail-closed: the generator and evaluator must be DISTINCT identities (:class:`RefinementRefused`,
    D75 / D100-6 — an adversarial critic, never a self-audit), and a critic that passes a criterion
    OUTSIDE the rubric is refused (it cannot invent its way over the bar). The loop PRODUCES a draft
    that passed the bar; it never promotes it — promotion stays the human gesture through
    :meth:`~mnemosyne.production.workflow.ProductionWorkflow.promote` (D79)."""
    require_distinct(
        generator.identity, evaluator.identity, RefinementRefused, what="generator-critic loop"
    )
    if max_rounds < 1:
        raise ValueError(f"max_rounds must be >= 1, got {max_rounds}")

    criteria = set(rubric.criteria)
    best_draft: str | None = None
    best_score: Score | None = None
    feedback: str | None = None
    rounds_run = 0
    for round_index in range(1, max_rounds + 1):
        rounds_run = round_index  # rounds = the total effort spent, not the round of the best draft
        draft = generator.generate(brief, feedback=feedback)
        score = evaluator.evaluate(draft, rubric)
        invented = score.passed - criteria
        if invented:
            raise RefinementRefused(
                f"generator-critic loop: the evaluator passed criteria outside the rubric "
                f"{sorted(invented)} — a critic cannot invent its way over the bar (D75 / D100)"
            )
        if best_score is None or score.total > best_score.total:
            best_draft, best_score = draft, score  # keep the BEST attempt (non-destructive, inv. 2)
        if score.total >= rubric.threshold:
            # first draft to clear the bar — it is the best possible, so stop here (D78 bound honored)
            return RefinementResult(draft=draft, score=score, rounds=rounds_run, reached=True)
        feedback = score.feedback  # refine on the critic's feedback next round
    assert best_draft is not None and best_score is not None  # max_rounds >= 1 ⇒ a round ran
    return RefinementResult(draft=best_draft, score=best_score, rounds=rounds_run, reached=False)
