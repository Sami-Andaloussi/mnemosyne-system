"""Models in the loop (D100 / D89) - the local sensors the 4a / 4b seams left for LOT 5.

LOT 4a shipped the classifier's semantic pass as an abstaining ``NullSemanticSensor``, and
LOT 4b integrated graph facts "as given"; both left a seam explicitly for LOT 5 to plug a
REAL local model into - behind the Guard. This module fills them. Every model here obeys
D100 (non-derivation) structurally:

* **Behind the Guard (D89).** A sensor never calls a backend directly - it obtains a
  ``MODEL_CALL`` :class:`Grant` from the Guard, which routes ``sensible`` content LOCAL
  (never canal A). No grant, no call.
* **Content-as-data (D100-3 / D81).** The content is the PROMPT payload, treated as
  untrusted (zero-trust, ``sensible`` until proven); an injection in it is data, never an
  instruction that could steer the label.
* **Raise-only (D100-2).** A sensor can only ADD prudence. The semantic pass feeds the
  classifier through a ``max`` (invariant 18), so it can never lower a label; the fact
  extractor emits facts that the journal envelopes with the CONTENT's label, so extraction
  can never declassify.

The backend is the grammar-bound :class:`~mnemosyne.runtime.runner.LocalRunner` (a stub until
(3)): structured output is decoded under a grammar (invariant 27), so a sensor's model output
is well-formed by construction. With the stub the sensors ABSTAIN (no verdict, no facts) -
the seam is wired, the model is not yet installed - exactly the fail-safe posture of the
``Null`` stand-ins they replace. Code & docstrings English (D117).

Decisions: D89 (behind the Guard)  -  D100 (non-derivation: content-as-data, raise-only)  -
D101 / D72 (sensitivity signal)  -  D103 / D84 (fact extraction)  -  D104 (grammar-bound).
Invariants carried: substrate of 18 (semantic pass), 20 / 24 (enveloped facts), 27 (grammar).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..ports import (
    DEFAULT_SENSITIVITY,
    Bubble,
    Effect,
    Envelope,
    Fact,
    GovernanceLabel,
    GrammarConstraint,
    Guard,
    GuardRequest,
    MnemosyneError,
    NodeId,
    RoutingClass,
    Runner,
    Sensitivity,
)

if TYPE_CHECKING:
    from .model_router import ModelRouter

#: Grammar for the sensitivity pass - a single token the classifier feeds through ``max``.
_SENSITIVITY_GRAMMAR = GrammarConstraint(
    schema=json.dumps(
        {"type": "object", "required": ["level"], "properties": {"level": {"type": "string"}}}
    )
)
#: Grammar for fact extraction - a list of ``(subject, predicate, obj)`` triples (D103). The ``items``
#: shape is REQUIRED, not decorative: it is the CONTRACT :func:`_parse_facts` reads (each item must carry
#: ``subject`` / ``predicate`` / ``obj``) AND it is what the grammar-bound decoder constrains the model to
#: - Outlines' ``json_schema`` on a bare ``{"type": "array"}`` permits (and the under-steered model emits)
#: an array of PROSE STRINGS, which every ``item["subject"]`` then drops => recall 0 (calibration (3)-7). A
#: fully-described item makes emitting a non-triple structurally impossible and tells the model the exact
#: shape to produce (the schema rides in the prompt, ``_STRUCTURED_INSTRUCTION``).
_TRIPLE_SCHEMA = {
    "type": "object",
    "required": ["subject", "predicate", "obj"],
    "properties": {
        "subject": {"type": "string"},
        "predicate": {"type": "string"},
        "obj": {"type": "string"},
    },
    "additionalProperties": False,
}
_FACT_GRAMMAR = GrammarConstraint(
    schema=json.dumps(
        {
            "type": "object",
            "required": ["facts"],
            "properties": {"facts": {"type": "array", "items": _TRIPLE_SCHEMA}},
        }
    )
)
#: The extraction CONTRACT - the ONE home of what a "fact" MEANS here (contract-single-source-emit).
#: The runner's generic wrapper (``runner_mlx._STRUCTURED_INSTRUCTION``) only says "conform to this
#: schema", so until YYYY-MM-DD the word ``"facts"`` in the schema was the ENTIRE task specification the
# Deployment-specific measurement omitted; the behavior is covered by tests.
#: day (`make calibrate`): (a) INVENTION - on a passage stating only that dependencies are inverted
#: against the flow of control, the model returned SIX triples recited from its training data
#: ("promotes loose coupling and high cohesion"...) and missed the one fact actually stated; (b) entities
#: named in prose surface ("the ratio of a bank's capital to its assets") - a node that can never merge
#: with another, which is precisely what a graph is FOR. Neither is expressible as a grammar (both are
#: about MEANING, not shape), so they are stated here, in words. The grammar still binds the SHAPE
#: (invariant 27); this binds the intent. It steers, it cannot guarantee - the honest split.
#:
#: NOT a scoring trick: (a) is a correctness requirement for a memory that must not lie to itself, and
#: (b) is a design requirement of the graph. Both would be right with no golden set at all.
_EXTRACT_PROMPT = """Extract the factual claims STATED IN the passage below, as (subject, predicate, obj) triples.

Rules:
- ONLY what the passage itself states. If the passage does not state it, do not emit it - even if you
  know it to be true. You are READING, not recalling.
- subject and obj NAME AN ENTITY: the shortest phrase that names the thing. No articles (the/a/an), no
  possessives, no trailing qualifiers. The same concept must always get the same name, so that two
  passages about it meet on one node.
- predicate is the relation the passage asserts, as a short lowercase verb phrase.
- A passage that states no fact yields an empty list. An empty list is a correct answer.

Passage:
{passage}"""

#: French sensitivity token -> level (raise-only; an unknown token abstains).
_LEVEL_BY_TOKEN = {s.token: s for s in Sensitivity}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


#: The model sees only this many characters of a document (D135): a whole document overflows the
#: model window. The sample is spread
#: (head+middle+tail, ``_bounded_sample``) so a contextual signal past the head is still seen; the
#: deterministic PII floor scans the FULL content separately (Classifier.floor), so a tail marker
#: is never missed even here.
_ASSESS_CHAR_BUDGET = 8000


def _bounded_sample(content: str, budget: int) -> str:
    """A length-bounded, position-spread sample of ``content`` for the semantic pass (D135 / audit
    A-3): head + middle + tail rather than a bare prefix, so a contextual sensitivity signal past
    the head is still seen. A recall heuristic only - the deterministic PII floor is the guarantee
    and scans the full content, never this sample."""
    if len(content) <= budget:
        return content
    third = budget // 3
    mid = len(content) // 2
    return content[:third] + content[mid - third // 2 : mid + third // 2] + content[-third:]


def _model_call_request(
    *,
    subject: Bubble,
    inputs: tuple[GovernanceLabel, ...],
    router: ModelRouter | None,
    routing_class: RoutingClass,
    action: str,
) -> GuardRequest:
    """Build the ``MODEL_CALL`` request, routing the MODEL by task class (D7) when a router is wired.

    The routed model id - or ``None``, the capable default - is recorded as ``target`` ("destination:
    model backend") and named in the ``descriptor`` for provenance. Router absent => ``target`` None
    and empty descriptor: byte-identical to the pre-D7 request (zero-regression). The CHANNEL stays
    the Guard's own ``route_model`` decision (sensitivity, invariant 1); this only names the model -
    the two compose and the channel always wins (a ``sensible`` call never leaves local)."""
    if router is None:
        return GuardRequest(effect=Effect.MODEL_CALL, subject=subject, inputs=inputs)
    target = router.route(routing_class)
    return GuardRequest(
        effect=Effect.MODEL_CALL,
        subject=subject,
        inputs=inputs,
        target=target,
        descriptor=f"{action} [{routing_class.value}] via {target or 'default'}",
    )


class ModelSemanticSensor:
    """The classifier's contextual semantic pass, backed by a local model (D101 / D100).

    Realizes the ``SemanticSensor`` seam of LOT 4a: :meth:`assess` classifies content through
    a Guard-routed local model, RAISE-only (the classifier feeds it through ``max``). Content
    is zero-trust data; the call never leaves local (``sensible``). With the stub runner it
    abstains - the model is not yet installed."""

    __slots__ = ("_guard", "_runner", "_subject", "_router")

    #: This sensor's D7 capability class - a bounded sensitivity classification is a mechanical
    #: micro-task, so a small local model suffices once the bench maps MICRO (D7 / D69).
    _ROUTING_CLASS = RoutingClass.MICRO

    def __init__(
        self,
        guard: Guard,
        runner: Runner,
        *,
        subject: Bubble,
        router: ModelRouter | None = None,
    ) -> None:
        self._guard = guard
        self._runner = runner
        self._subject = subject
        # D7 - optional (zero-regression): absent => no routing (target None, today's behaviour);
        # wired (bootstrap) => declares this call's task class so the routed model is recorded.
        self._router = router

    def assess(self, content: str) -> Sensitivity | None:
        """Assess the contextual sensitivity of ``content`` - RAISE-only, LOCAL (D100 / D101).

        Content is treated as ``sensible`` until proven (zero-trust), so the Guard routes the
        model call LOCAL; the model's opinion enters the classifier only through ``max`` and
        can never lower a label. Returns ``None`` (abstain) when the model has no verdict. The
        model sees only a BOUNDED, position-spread sample (``_bounded_sample`` over
        ``_ASSESS_CHAR_BUDGET``, D135 / audit A-3): a whole document overflows the model window;
        the deterministic PII floor scans the FULL content separately, so a tail marker is never
        missed."""
        sample = _bounded_sample(content, _ASSESS_CHAR_BUDGET)
        label = GovernanceLabel(sensitivity=DEFAULT_SENSITIVITY, bubble=self._subject)
        grant = self._guard.grant(
            _model_call_request(
                subject=self._subject,
                inputs=(label,),
                router=self._router,
                routing_class=self._ROUTING_CLASS,
                action="classify",
            )
        )
        out = self._runner.complete_structured(
            Envelope(sample, label), grant=grant, constraint=_SENSITIVITY_GRAMMAR
        )
        return _parse_level(out.payload)


class ModelFactExtractor:
    """The living-memory fact extractor, backed by a local model (D103 / D100).

    Realizes the seam LOT 4b left ("facts integrated as given"): :meth:`extract` proposes
    facts from content through a Guard-routed, grammar-bound local model (invariant 27), so
    the triples are well-formed by construction. The facts are NAKED - the journal envelopes
    them with the content's label (raise-only: extraction can never declassify)."""

    __slots__ = ("_guard", "_runner", "_subject", "_router")

    #: This extractor's D7 capability class - grammar-bound triple extraction is a mechanical
    #: micro-task, so a small local model suffices once the bench maps MICRO (D7 / D69).
    _ROUTING_CLASS = RoutingClass.MICRO

    def __init__(
        self,
        guard: Guard,
        runner: Runner,
        *,
        subject: Bubble,
        router: ModelRouter | None = None,
    ) -> None:
        self._guard = guard
        self._runner = runner
        self._subject = subject
        # D7 - optional (zero-regression), wired by bootstrap; absent => today's behaviour.
        self._router = router

    def extract(self, content: Envelope[str]) -> tuple[Fact, ...]:
        """Propose facts from ``content`` via a Guard-routed, grammar-bound model (D103).

        The model call is routed by the Guard (LOCAL for ``sensible``); its structured output
        is grammar-constrained so every triple is well-formed (invariant 27). Facts are
        returned naked and carry the content's governance downstream (the journal envelopes
        them, raise-only). With the stub runner no fact is produced - the seam awaits (3).

        The content is wrapped in :data:`_EXTRACT_PROMPT` (which says what a fact IS here, and above
        all "only what the passage states") before the runner's generic schema wrapper. The wrapper's
        text rides INSIDE the envelope's payload, so it is bounded by the same ``_require_bounded``
        ceiling as the content - a passage near the ceiling now RAISES slightly sooner (fail-closed,
        never truncated, D136). The LABEL is carried over untouched: wrapping is not declassification."""
        grant = self._guard.grant(
            _model_call_request(
                subject=self._subject,
                inputs=(content.label,),
                router=self._router,
                routing_class=self._ROUTING_CLASS,
                action="extract-facts",
            )
        )
        prompt = Envelope(_EXTRACT_PROMPT.format(passage=content.payload), content.label)
        out = self._runner.complete_structured(prompt, grant=grant, constraint=_FACT_GRAMMAR)
        return _parse_facts(out.payload)


def _parse_level(payload: str) -> Sensitivity | None:
    """Read the model's sensitivity token; unknown / empty => abstain (raise-only via max)."""
    try:
        token = json.loads(payload).get("level", "")
    except (json.JSONDecodeError, AttributeError):
        return None
    return _LEVEL_BY_TOKEN.get(str(token))


def _parse_facts(payload: str) -> tuple[Fact, ...]:
    """Read the model's ``(subject, predicate, obj)`` triples; malformed items are dropped."""
    try:
        raw = json.loads(payload).get("facts", [])
    except (json.JSONDecodeError, AttributeError):
        return ()
    facts: list[Fact] = []
    at = _utcnow()
    for item in raw:
        try:
            facts.append(
                Fact(
                    subject=NodeId(str(item["subject"])),
                    predicate=str(item["predicate"]),
                    obj=NodeId(str(item["obj"])),
                    valid_from=at,
                )
            )
        except (TypeError, KeyError, MnemosyneError):
            continue  # a malformed triple is dropped, never a crash (D108-(2))
    return tuple(facts)
