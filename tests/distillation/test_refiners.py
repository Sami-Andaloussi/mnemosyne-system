"""Runner-backed generator & critic for the graded loop ((4) / D79 / D75 / D104).

Where :mod:`tests.test_refinement` proves the loop MECHANISM against pure stubs, this proves the
CONCRETE prises that incarnate its ports on a real model - brick-free (D126), against a weightless
Runner double: the generator builds its prompt and weaves the critic's feedback, the critic decodes a
grammar-bound verdict (bound to the rubric's own criteria, D104) and re-validates its shape
(:class:`CritiqueMalformed`, never a silent 0/N), and the ``CoreApi.produce`` surface runs the whole
loop with every model leg crossing the Guard (D89) - producing a graded DRAFT, never promoting it (D79).
"""

from __future__ import annotations

import json
from dataclasses import replace

from pytest import raises

from mnemosyne.api import CoreApi
from mnemosyne.ports import (
    Bubble,
    Effect,
    Envelope,
    GovernanceLabel,
    GrammarConstraint,
    Grant,
    GuardDenied,
    GuardRequest,
    Sensitivity,
)
from mnemosyne.production import (
    CritiqueMalformed,
    RefinementResult,
    Rubric,
    RunnerCritic,
    RunnerGenerator,
    Score,
)
from mnemosyne.production.refiners import _parse_score, _score_schema
from mnemosyne.runtime.bootstrap import bootstrap

_SUBJECT = Bubble("agent-test")


def _label(sensitivity: Sensitivity = Sensitivity.SENSIBLE) -> GovernanceLabel:
    return GovernanceLabel(sensitivity=sensitivity, bubble=_SUBJECT)


def _bare_grant(label: GovernanceLabel) -> Grant:
    """A test-double grant (a bare shape - no Guard token; the stub runner never redeems it)."""
    return Grant(
        request=GuardRequest(
            effect=Effect.MODEL_CALL,
            subject=label.bubble,
            inputs=(label,),
            descriptor="test refine",
        ),
        released_label=label,
    )


def _score_json(passed: list[str], feedback: str = "") -> str:
    return json.dumps({"passed": passed, "feedback": feedback})


class _StubRunner:
    """A weightless Runner double (D126): scripted drafts on ``complete``, scripted scores on
    ``complete_structured``; records the grants, prompts and constraints it was handed."""

    def __init__(self, *, drafts: list[str] | None = None, scores: list[str] | None = None) -> None:
        self._drafts = drafts
        self._scores = scores or []
        self._di = 0
        self._si = 0
        self.grants: list[Grant] = []
        self.gen_prompts: list[str] = []
        self.crit_prompts: list[str] = []
        self.constraints: list[GrammarConstraint] = []

    def complete(
        self, prompt: Envelope[str], *, grant: Grant, constraint: GrammarConstraint | None = None
    ) -> Envelope[str]:
        self.grants.append(grant)
        self.gen_prompts.append(prompt.payload)
        payload = self._drafts[self._di] if self._drafts is not None else f"draft-{self._di + 1}"
        self._di += 1
        return Envelope(payload=payload, label=prompt.label)

    def complete_structured(
        self, prompt: Envelope[str], *, grant: Grant, constraint: GrammarConstraint
    ) -> Envelope[str]:
        self.grants.append(grant)
        self.crit_prompts.append(prompt.payload)
        self.constraints.append(constraint)
        # repeat the last scripted score once the list is exhausted - lets a test run the loop to its
        # bound without scripting a score per round (the converging tests never reach past their list).
        payload = self._scores[self._si] if self._si < len(self._scores) else self._scores[-1]
        self._si += 1
        return Envelope(payload=payload, label=prompt.label)


# --------------------------------------------------------------------------- #
# The generator prise                                                          #
# --------------------------------------------------------------------------- #
def test_runner_generator_builds_the_prompt_and_weaves_feedback() -> None:
    """The brief lands in the prompt; the critic's feedback is woven into the next round (D79)."""
    runner = _StubRunner()
    gen = RunnerGenerator(runner, _bare_grant, identity="g", label=_label())

    first = gen.generate("write a risk note")
    second = gen.generate("write a risk note", feedback="cite a source")

    assert first == "draft-1" and second == "draft-2"
    assert "write a risk note" in runner.gen_prompts[0]
    assert "cite a source" not in runner.gen_prompts[0]  # no feedback on the first round
    assert "cite a source" in runner.gen_prompts[1]  # the feedback was fed back (refine on it)
    assert len(runner.grants) == 2  # one fresh MODEL_CALL grant per round (never self-granted)


# --------------------------------------------------------------------------- #
# The critic prise (grammar-bound + re-validated)                              #
# --------------------------------------------------------------------------- #
def test_runner_critic_parses_a_grammar_bound_score() -> None:
    """The critic decodes a structured verdict and re-validates it into a Score (D104 / D100)."""
    runner = _StubRunner(scores=[_score_json(["a", "b"], feedback="tighten c")])
    critic = RunnerCritic(runner, _bare_grant, identity="c", label=_label())

    score = critic.evaluate("a draft", Rubric(criteria=("a", "b", "c"), threshold=3))

    assert score.passed == frozenset({"a", "b"})
    assert score.total == 2
    assert score.feedback == "tighten c"
    assert len(runner.grants) == 1  # the critic mints its OWN grant (Guard-mediated, D89)


def test_runner_critic_binds_the_decoder_to_the_rubric_criteria() -> None:
    """A structured call is grammar-bound (invariant 27), and ``passed`` is an ENUM of the criteria."""
    runner = _StubRunner(scores=[_score_json(["a"])])
    critic = RunnerCritic(runner, _bare_grant, identity="c", label=_label())

    critic.evaluate("a draft", Rubric(criteria=("a", "b"), threshold=1))

    schema = json.loads(runner.constraints[0].schema)
    assert schema["properties"]["passed"]["items"]["enum"] == [
        "a",
        "b",
    ]  # cannot name a non-criterion
    assert schema["properties"]["passed"]["maxItems"] == 2


def test_runner_critic_rejects_a_malformed_verdict() -> None:
    """A verdict that is not the agreed shape is refused fail-closed, never a silent 0/N (D108-(2))."""
    rubric = Rubric(criteria=("a",), threshold=1)
    critic_bad_json = RunnerCritic(
        _StubRunner(scores=["not json"]), _bare_grant, identity="c", label=_label()
    )
    with raises(CritiqueMalformed):
        critic_bad_json.evaluate("d", rubric)

    critic_bad_shape = RunnerCritic(
        _StubRunner(scores=[json.dumps({"passed": "a", "feedback": ""})]),  # passed must be a LIST
        _bare_grant,
        identity="c",
        label=_label(),
    )
    with raises(CritiqueMalformed):
        critic_bad_shape.evaluate("d", rubric)


def test_parse_score_shape_checks_the_payload() -> None:
    """`_parse_score` re-validates the brick's output; the rubric-membership gate is refine's, not its."""
    rubric = Rubric(criteria=("a", "b"), threshold=1)
    assert _parse_score(_score_json(["a"], "note"), rubric) == Score(
        passed=frozenset({"a"}), feedback="note"
    )
    with raises(CritiqueMalformed):
        _parse_score("[]", rubric)  # a JSON array, not an object
    with raises(CritiqueMalformed):
        _parse_score(json.dumps({"passed": [1], "feedback": ""}), rubric)  # non-string criterion
    with raises(CritiqueMalformed):
        _parse_score(json.dumps({"passed": ["a"], "feedback": 3}), rubric)  # non-string feedback
    # a criterion outside the rubric is NOT rejected here - refine owns that gate (D75), proven below
    outside = _parse_score(_score_json(["z"]), rubric)
    assert outside.passed == frozenset({"z"})


def test_score_schema_is_empty_safe_and_bounded() -> None:
    """The schema always names the criteria as the enum and bounds the array to their count."""
    schema = json.loads(_score_schema(Rubric(criteria=("x", "y", "z"), threshold=2)))
    assert schema["properties"]["passed"]["items"]["enum"] == ["x", "y", "z"]
    assert schema["properties"]["passed"]["uniqueItems"] is True
    assert schema["required"] == ["passed", "feedback"]


# --------------------------------------------------------------------------- #
# The Guard-mediated surface (D89 / D119) - produce runs the loop, never promotes
# --------------------------------------------------------------------------- #
def _converging_runner() -> _StubRunner:
    """Three rounds climbing 1/3 -> 2/3 -> 3/3 - the loop should stop the moment the bar is cleared."""
    return _StubRunner(
        scores=[
            _score_json(["a"], feedback="add b and c"),
            _score_json(["a", "b"], feedback="add c"),
            _score_json(["a", "b", "c"]),
        ]
    )


def test_coreapi_produce_runs_the_graded_loop_through_the_guard() -> None:
    rt = bootstrap()
    runner = _converging_runner()
    api = CoreApi(replace(rt, runner=runner))

    result = api.produce(
        "write a risk note",
        rubric=Rubric(criteria=("a", "b", "c"), threshold=3),
        subject=_SUBJECT,
        max_rounds=5,
    )

    assert isinstance(result, RefinementResult)
    assert result.reached is True
    assert result.rounds == 3  # stopped the moment the bar was cleared, not max_rounds
    assert result.draft == "draft-3"
    # every model leg crossed the Guard: 3 generate + 3 critique = 6 real, sealed MODEL_CALL grants (M1)
    assert len(runner.grants) == 6
    assert all(g.token is not None for g in runner.grants)  # genuine Guard seals, not bare shapes
    assert all(g.request.effect is Effect.MODEL_CALL for g in runner.grants)


def test_coreapi_produce_returns_a_flagged_draft_when_the_bar_is_never_met() -> None:
    """A draft that never clears is returned with reached=False (a FLAG for user), never promoted."""
    rt = bootstrap()
    runner = _StubRunner(scores=[_score_json(["a"], "more"), _score_json(["a"], "more")])
    api = CoreApi(replace(rt, runner=runner))

    result = api.produce(
        "brief", rubric=Rubric(criteria=("a", "b"), threshold=2), subject=_SUBJECT, max_rounds=2
    )

    assert (
        result.reached is False
    )  # a DRAFT, never auto-promoted - promotion stays api.promote (D79)
    assert result.rounds == 2  # bounded (D78)


def test_coreapi_produce_routes_the_two_roles_with_distinct_descriptors() -> None:
    """Producer and critic carry DISTINCT grant descriptors - the Guard MAY route them to distinct
    models, and the loop refuses a self-audit by construction (distinct identities, D75)."""
    rt = bootstrap()
    runner = _converging_runner()
    api = CoreApi(replace(rt, runner=runner))

    api.produce(
        "brief",
        rubric=Rubric(criteria=("a", "b", "c"), threshold=3),
        subject=_SUBJECT,
        max_rounds=5,
    )

    descriptors = {g.request.descriptor for g in runner.grants}
    assert descriptors == {"refine: generate (D79)", "refine: critique (D75)"}


def test_coreapi_produce_fails_closed_when_the_guard_denies() -> None:
    class _DenyAllGuard:
        def grant(self, request: object) -> Grant:
            raise GuardDenied("deny-all: produce")

    rt = bootstrap()
    runner = _converging_runner()
    api = CoreApi(replace(rt, runner=runner, guard=_DenyAllGuard()))
    with raises(GuardDenied):
        api.produce(
            "brief", rubric=Rubric(criteria=("a",), threshold=1), subject=_SUBJECT, max_rounds=3
        )
    assert runner.grants == []  # no grant => the model was never called (fail-closed, D100)


def test_coreapi_produce_fails_closed_on_a_mid_loop_denial() -> None:
    """A Guard denial in a LATER round propagates - no best-effort past a refused model call (D100)."""

    class _DenyAfterGuard:
        def __init__(self, inner: object, *, deny_at: int) -> None:
            self._inner = inner
            self._deny_at = deny_at
            self._n = 0

        def grant(self, request: object) -> Grant:
            self._n += 1
            if self._n >= self._deny_at:
                raise GuardDenied("deny after N: produce mid-loop")
            return self._inner.grant(request)  # type: ignore[attr-defined]

    rt = bootstrap()
    runner = _StubRunner(scores=[_score_json(["a"], feedback="more")])  # never clears 2/2
    api = CoreApi(replace(rt, runner=runner, guard=_DenyAfterGuard(rt.guard, deny_at=3)))
    with raises(GuardDenied):
        api.produce(
            "brief", rubric=Rubric(criteria=("a", "b"), threshold=2), subject=_SUBJECT, max_rounds=5
        )
    # round 1 ran fully (generate + critique = 2 sealed grants); round 2's generate grant was refused
    # BEFORE reaching the runner, so no third model leg happened.
    assert len(runner.grants) == 2


def test_coreapi_produce_propagates_a_malformed_critique() -> None:
    """A critic verdict that is not the agreed shape surfaces as CritiqueMalformed, never a silent grade."""
    rt = bootstrap()
    runner = _StubRunner(scores=["not-json-at-all"])
    api = CoreApi(replace(rt, runner=runner))
    with raises(CritiqueMalformed):
        api.produce(
            "brief", rubric=Rubric(criteria=("a",), threshold=1), subject=_SUBJECT, max_rounds=3
        )


def test_coreapi_produce_clamps_max_rounds_to_the_protected_depth_bound() -> None:
    """A caller cannot buy more rounds than SE4's protected depth ceiling - max_rounds is clamped (D100)."""
    rt = bootstrap()
    ceiling = rt.policy.bound("agent_max_turns")
    runner = _StubRunner(
        scores=[_score_json(["a"], feedback="more")]
    )  # never clears 2/2 -> runs to the cap
    api = CoreApi(replace(rt, runner=runner))

    result = api.produce(
        "brief",
        rubric=Rubric(criteria=("a", "b"), threshold=2),
        subject=_SUBJECT,
        max_rounds=10_000,
    )

    assert result.reached is False
    assert (
        result.rounds == ceiling
    )  # clamped to agent_max_turns, not the 10_000 the caller asked for
