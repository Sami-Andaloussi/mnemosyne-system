"""D79 / D75 - the generator<->critic loop on a rubric (the *plancher* nerve of the soul).

Biting tests for :mod:`mnemosyne.production.refinement`. The three assembly parts already existed
(the generator, the producer≠verifier gate, the human promotion portal); what was missing was the
GRADED LOOP that assembles them. These prove the mechanism, brick-free, against deterministic stubs
(D126): it refines on the critic's feedback UNTIL the rubric is met, is BOUNDED (a draft that never
clears cannot spin forever, D78), is NON-DESTRUCTIVE (the best attempt is kept, invariant 2), refuses
a self-audit (producer ≠ verifier, D75 / D100-6) and a cheating critic, and it PRODUCES - it never
promotes (that stays the human gesture, D79).
"""

from __future__ import annotations

from pytest import raises

from mnemosyne.production import RefinementRefused, Rubric, Score, refine


class _Gen:
    """A stub generator: its Nth draft is ``draft-N``; it records the feedback it was handed."""

    def __init__(self, identity: str = "gen") -> None:
        self.identity = identity
        self.feedbacks: list[str | None] = []

    def generate(self, brief: str, *, feedback: str | None = None) -> str:
        self.feedbacks.append(feedback)
        return f"draft-{len(self.feedbacks)}"


class _Critic:
    """A stub evaluator: returns pre-scripted :class:`Score` s, one per round."""

    def __init__(self, scores: list[Score], *, identity: str = "critic") -> None:
        self.identity = identity
        self._scores = scores
        self._i = 0

    def evaluate(self, draft: str, rubric: Rubric) -> Score:
        score = self._scores[self._i]
        self._i += 1
        return score


def test_the_loop_refines_on_feedback_until_the_rubric_is_met() -> None:
    """Each round improves; the loop stops the moment the bar is cleared and feeds feedback back."""
    rubric = Rubric(criteria=("a", "b", "c"), threshold=3)
    gen = _Gen()
    critic = _Critic(
        [
            Score(passed=frozenset({"a"}), feedback="fix b and c"),
            Score(passed=frozenset({"a", "b"}), feedback="fix c"),
            Score(passed=frozenset({"a", "b", "c"})),
        ]
    )

    result = refine(gen, critic, brief="produce", rubric=rubric, max_rounds=5)

    assert result.reached is True
    assert result.rounds == 3
    assert result.score.total == 3
    assert result.draft == "draft-3"
    assert gen.feedbacks == [None, "fix b and c", "fix c"]  # the critic's feedback was fed back


def test_the_loop_is_bounded_and_flags_when_the_bar_is_never_met() -> None:
    """A draft that never clears the bar stops at max_rounds (D78) and returns reached=False (a FLAG)."""
    rubric = Rubric(criteria=("a", "b"), threshold=2)
    gen = _Gen()
    critic = _Critic(
        [
            Score(passed=frozenset({"a"}), feedback="fix b"),
            Score(passed=frozenset({"a"}), feedback="fix b"),
        ]
    )

    result = refine(gen, critic, brief="produce", rubric=rubric, max_rounds=2)

    assert result.reached is False
    assert result.rounds == 2
    assert result.score.total == 1


def test_the_best_attempt_is_kept_even_if_a_later_round_is_worse() -> None:
    """Non-destructive (invariant 2): the peak draft is returned, not the last, worse one."""
    rubric = Rubric(criteria=("a", "b", "c"), threshold=3)  # never reached
    gen = _Gen()
    critic = _Critic(
        [
            Score(passed=frozenset({"a"}), feedback="more"),  # 1/3
            Score(passed=frozenset({"a", "b"}), feedback="more"),  # 2/3 <- the peak
            Score(passed=frozenset({"a"}), feedback="more"),  # 1/3 <- last, worse
        ]
    )

    result = refine(gen, critic, brief="produce", rubric=rubric, max_rounds=3)

    assert result.reached is False
    assert result.score.total == 2  # the BEST attempt, not the last
    assert result.draft == "draft-2"


def test_a_self_audit_is_refused_fail_closed() -> None:
    """Producer == verifier is refused before the loop even runs (D75 / D100-6, an isolated critic)."""
    gen = _Gen(identity="same")
    critic = _Critic([Score(passed=frozenset({"a"}))], identity="same")
    with raises(RefinementRefused):
        refine(gen, critic, brief="x", rubric=Rubric(criteria=("a",), threshold=1), max_rounds=1)


def test_a_critic_that_invents_a_criterion_is_refused() -> None:
    """A critic cannot pass a criterion OUTSIDE the rubric to cheat its way over the bar (D75/D100)."""
    gen = _Gen()
    critic = _Critic([Score(passed=frozenset({"not-in-rubric"}))])
    with raises(RefinementRefused):
        refine(
            gen, critic, brief="x", rubric=Rubric(criteria=("a", "b"), threshold=1), max_rounds=1
        )


def test_max_rounds_must_be_at_least_one() -> None:
    """A loop needs at least one round - a zero budget is a bug, refused fail-closed."""
    with raises(ValueError):
        refine(
            _Gen(),
            _Critic([]),
            brief="x",
            rubric=Rubric(criteria=("a",), threshold=1),
            max_rounds=0,
        )


def test_rubric_validates_its_shape() -> None:
    """A rubric guards its own shape: non-empty, distinct criteria, threshold in 1..N."""
    with raises(ValueError):
        Rubric(criteria=(), threshold=1)  # empty
    with raises(ValueError):
        Rubric(criteria=("a", "a"), threshold=1)  # duplicate criteria double-count
    with raises(ValueError):
        Rubric(criteria=("a", "b"), threshold=3)  # threshold above the criteria count
    with raises(ValueError):
        Rubric(criteria=("a", "b"), threshold=0)  # threshold below 1
