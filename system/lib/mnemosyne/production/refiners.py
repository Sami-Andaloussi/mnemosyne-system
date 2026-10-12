"""Runner-backed generator & adversarial critic for the graded loop ((4) / D79 / D75 / D104).

The mechanism of the *plancher* loop lives, brick-free, in :mod:`.refinement` - it knows only the
:class:`~mnemosyne.production.refinement.Generator` / :class:`~mnemosyne.production.refinement.Evaluator`
PORTS, never a model. This module supplies the CONCRETE prises that incarnate those ports on a real
model, exactly as :mod:`.distillation` incarnates the distillation skill: each decodes through an
injected :class:`~mnemosyne.ports.runner.Runner` (model-agnostic, D104) and mints its ``MODEL_CALL``
capability through an injected :data:`GrantSource` - never a self-granted call (the bypass D100
forbids); the orchestration (:meth:`~mnemosyne.api.core_api.CoreApi.produce`) supplies the grant
lifecycle, so every model leg crosses the frontier through the Guard (D89).

Two prises, two ROLES, kept structurally apart (D75 / D100-6):

* :class:`RunnerGenerator` - produces a draft from the brief with a FREE-FORM completion, refining on
  the critic's feedback. Its ``identity`` names the producer.
* :class:`RunnerCritic` - grades a draft against the rubric with a STRUCTURED completion
  (grammar-bound, D104 / invariant 27): the decoder is bound to a schema whose ``passed`` items are an
  ENUM of the rubric's own criteria, so the model CANNOT emit a criterion outside the rubric - a
  *structural incapacity*, not a trusted model. The critic still re-validates the shape
  (:func:`_parse_score`, defense in depth, D100) and carries a DISTINCT ``identity`` (≠ the
  generator's), so :func:`~mnemosyne.production.refinement.refine` refuses a self-audit fail-closed.

Both prises run on the SAME injected Runner today - the Guard routes a ``MODEL_CALL`` by label, not by
the grant descriptor - so the substantive producer≠verifier separation is the DISTINCT identity + PROMPT
isolation (the critic is handed only the draft and the criteria, never the generator's reasoning); the
distinct-role descriptors leave an audit trail a future provider aiguilleur could route a separate critic
model on.

The generator's real brain COULD be the multi-turn agent (:func:`~mnemosyne.agents.loop.run_agent`,
with tools) rather than a single completion - the :class:`~mnemosyne.production.refinement.Generator`
port accepts either. The first wiring is the single-completion producer: symmetric with the critic,
Guard-mediated the same way, and provable brick-free here against a stub runner (D126). A richer
agent-generator is a later impl of the SAME port, not a change to the loop. Code & docstrings English
(D117).

Decisions: D79 (production loop)  -  D75 / D100-6 (producer ≠ verifier, distinct roles)  -  D104 /
invariant 27 (grammar-bound structured output)  -  D89 / D100 (behind the Guard, never self-granted)  -
D126 (brick-free proof)  -  D108-(2) (normalized malformed error).
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..ports import (
    Envelope,
    ErrorCode,
    GovernanceLabel,
    GrammarConstraint,
    Grant,
    MnemosyneError,
    Runner,
)
from .refinement import Rubric, Score

#: The Guard grant lifecycle a prise needs: a callback that mints a fresh single-use ``MODEL_CALL``
#: grant for one model leg, given the data's label (D89 / D100 / M1). Mirrors the distillateur's and
#: the agent loop's - the prise NEVER mints its own capability; the orchestration supplies this.
GrantSource = Callable[[GovernanceLabel], Grant]

#: A bound on the critic's free-text feedback - it is guidance for the next round, not a payload; the
#: cap keeps a grammar-constrained decoder from running an unbounded string (mirrors the distillateur's
#: bounded schema, the failure mode confirmed at first ignition).
_FEEDBACK_MAX = 2000

_GENERATE_TEMPLATE = """\
You produce ONE deliverable from the brief below. Return ONLY the deliverable text, nothing else.

BRIEF:
{brief}
"""

_REFINE_SUFFIX = """
A critic reviewed your previous attempt and it did NOT clear the bar. Address this feedback directly,
keeping what already worked:
{feedback}
"""

_CRITIQUE_TEMPLATE = """\
You are an ADVERSARIAL critic grading a draft against a rubric. For EACH criterion, decide whether the
draft genuinely MEETS it - judge strictly, and pass a criterion ONLY when it is truly satisfied. Return
ONLY JSON matching the schema: the criteria met, and concrete feedback the producer can act on to clear
the ones it missed.

RUBRIC CRITERIA (pass a subset of exactly these):
{criteria}

DRAFT:
{draft}
"""


def _score_schema(rubric: Rubric) -> str:
    """The JSON schema the critic's decoder is bound to (D104 / invariant 27).

    ``passed`` is an array whose items are an ENUM of the rubric's OWN criteria - so a grammar-bound
    decoder is *structurally incapable* of naming a criterion outside the rubric (the barrier is the
    decoder, not the model's honesty, D100-1); ``uniqueItems`` stops a double-count, ``maxItems`` bounds
    it to the criteria count. ``feedback`` is a bounded free-text string. The critic re-validates the
    parsed shape anyway (:func:`_parse_score`), so even an un-constrained runner is caught."""
    return json.dumps(
        {
            "type": "object",
            "properties": {
                "passed": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(rubric.criteria)},
                    "maxItems": len(rubric.criteria),
                    "uniqueItems": True,
                },
                "feedback": {"type": "string", "maxLength": _FEEDBACK_MAX},
            },
            "required": ["passed", "feedback"],
        }
    )


class CritiqueMalformed(MnemosyneError):
    """The critic's structured output was not the agreed shape (D108-(2) / invariant 27).

    Normalized (never a bare crash), carried as ``MALFORMED`` so the loop / orchestrator knows to retry
    or FLAG. The grammar constraint makes this rare, but the critic re-validates anyway (defense in
    depth, D100 - a malformed verdict is caught at the source, never propagated as a silent 0/N)."""

    code = ErrorCode.MALFORMED


def _parse_score(text: str, rubric: Rubric) -> Score:
    """Parse + shape-check the critic's JSON verdict into a :class:`Score` (D108-(1) / D100).

    Re-validates the brick's output rather than trusting it: the payload must be a JSON object with a
    ``passed`` list of strings and a ``feedback`` string, else :class:`CritiqueMalformed`. The criteria
    are NOT filtered against the rubric here - :func:`~mnemosyne.production.refinement.refine` owns that
    gate (it REFUSES an invented criterion, D75), so this stays a pure shape check and never silently
    swallows a cheat. Duplicates collapse in the ``frozenset`` (a criterion is met or not, once)."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CritiqueMalformed(f"critic output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CritiqueMalformed(f"critic output must be a JSON object, got {type(data).__name__}")
    passed = data.get("passed")
    if not isinstance(passed, list) or not all(isinstance(item, str) for item in passed):
        raise CritiqueMalformed("critic field 'passed' must be a list of criterion strings")
    feedback = data.get("feedback", "")
    if not isinstance(feedback, str):
        raise CritiqueMalformed("critic field 'feedback' must be a string")
    return Score(passed=frozenset(passed), feedback=feedback)


class RunnerGenerator:
    """A :class:`~mnemosyne.production.refinement.Generator` on a governed Runner (D79 / D104).

    Produces a draft from the brief with a free-form completion, weaving the critic's feedback into the
    next round's prompt. Mints a fresh ``MODEL_CALL`` grant per round through the injected
    :data:`GrantSource` (never self-granted, D100); the resulting draft is the payload of the runner's
    output envelope (label monotone ≥ the input, invariant 17 - the Guard may raise it, never lower it)."""

    __slots__ = ("identity", "_runner", "_grant_source", "_label")

    def __init__(
        self, runner: Runner, grant_source: GrantSource, *, identity: str, label: GovernanceLabel
    ) -> None:
        self.identity = identity
        self._runner = runner
        self._grant_source = grant_source
        self._label = label

    def generate(self, brief: str, *, feedback: str | None = None) -> str:
        """Produce a draft for ``brief``, refining on the previous round's ``feedback`` if any."""
        prompt = _GENERATE_TEMPLATE.format(brief=brief)
        if feedback:
            prompt += _REFINE_SUFFIX.format(feedback=feedback)
        grant = self._grant_source(self._label)
        completion = self._runner.complete(Envelope(payload=prompt, label=self._label), grant=grant)
        return completion.payload


class RunnerCritic:
    """An :class:`~mnemosyne.production.refinement.Evaluator` on a governed Runner (D75 / D104).

    Grades a draft against the rubric with a STRUCTURED completion bound to :func:`_score_schema` (the
    decoder cannot name a criterion outside the rubric, D104 / invariant 27), then re-validates the
    shape into a :class:`Score` (:func:`_parse_score`, defense in depth). Mints its OWN ``MODEL_CALL``
    grant through the injected :data:`GrantSource` and carries a ``identity`` DISTINCT from the
    generator's, so the loop refuses a self-audit fail-closed (D75 / D100-6)."""

    __slots__ = ("identity", "_runner", "_grant_source", "_label")

    def __init__(
        self, runner: Runner, grant_source: GrantSource, *, identity: str, label: GovernanceLabel
    ) -> None:
        self.identity = identity
        self._runner = runner
        self._grant_source = grant_source
        self._label = label

    def evaluate(self, draft: str, rubric: Rubric) -> Score:
        """Grade ``draft`` against ``rubric`` - a grammar-bound verdict, re-validated to a Score.

        No ``repair`` is supplied to the constraint (unlike the distillateur's ``close_json``): the critic
        has no verbatim floor that would make a repair safe (the opt-in-repair rule,
        :class:`~mnemosyne.ports.runner.GrammarConstraint`), and its ``feedback`` is short prose a
        grammar-bound decoder escapes anyway. A malformed verdict is therefore rare, and when it happens it
        raises :class:`CritiqueMalformed` (normalized MALFORMED, D108-(2)) so the orchestrator retries or
        FLAGS - never a silent 0/N slipped past as a real grade."""
        criteria = "\n".join(f"- {c}" for c in rubric.criteria)
        prompt = _CRITIQUE_TEMPLATE.format(criteria=criteria, draft=draft)
        grant = self._grant_source(self._label)
        completion = self._runner.complete_structured(
            Envelope(payload=prompt, label=self._label),
            grant=grant,
            constraint=GrammarConstraint(_score_schema(rubric)),
        )
        return _parse_score(completion.payload, rubric)
