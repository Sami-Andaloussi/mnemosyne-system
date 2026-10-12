"""Tests for D7 model routing - the task-class -> model router, model-agnostic (D7 / D70).

Locks the doctrine `system/lib/mnemosyne/ports/routing.py` / `runtime/model_router.py` /
`runtime/models.py` state in their docstrings:

* **Frontier-default** - an unmapped :class:`RoutingClass` resolves to ``None``, the wired
  capable default runner ("frontier suffices for the majority", D66); an EMPTY routing table
  therefore sends every class to the default, never an error.
* **Model-agnostic / config-driven** - the class -> model mapping lives in policy CONFIG
  (``[model_routing]``), never hard-coded; the bench (D69) fills it empirically.
* **Zero-regression** - a consumer built with no router (``router=None``) builds the exact
  pre-D7 ``GuardRequest`` shape: ``target`` ``None``, ``descriptor`` ``""``.
* **Orthogonality (the governance invariant)** - this router picks the MODEL only. The
  Guard's ``route_model`` picks the CHANNEL by SENSITIVITY (invariant 1, sensible-local) and
  always wins: populating ``[model_routing]`` must never move a ``sensible`` / ``perso`` call
  off LOCAL.

Code & docstrings English (D117); ``public`` / ``perso`` / ``sensible`` keep their French
tokens (D33 / D66).
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.config import Policy, load_policy
from mnemosyne.guard import DeterministicGuard
from mnemosyne.ports import (
    Bubble,
    Channel,
    Effect,
    Envelope,
    GrammarConstraint,
    Grant,
    GovernanceLabel,
    GuardRequest,
    RoutingClass,
    Sensitivity,
)
from mnemosyne.runtime import (
    LocalObservability,
    LocalRunner,
    ModelFactExtractor,
    ModelRouter,
    ModelSemanticSensor,
    SnapshotStore,
)
from mnemosyne.runtime.backend_registry import BackendRegistry
from mnemosyne.runtime.models import _model_call_request

PUB, PERSO, SENS = Sensitivity.PUBLIC, Sensitivity.PERSO, Sensitivity.SENSIBLE

# --- builders -------------------------------------------------------------------------


def _label(level: Sensitivity, bubble: str = "b") -> GovernanceLabel:
    return GovernanceLabel(sensitivity=level, bubble=Bubble(bubble))


def _policy(**over: object) -> Policy:
    """A minimal, deny-by-default test policy (mirrors test_invariants.py / test_stores.py):
    only the field(s) a case cares about vary via ``over``. ``canal_a_auto`` defaults to
    ``{PUBLIC}`` - the production default (``policy.toml``'s ``canal_a_auto = ["public"]``)
    - so the orthogonality tests exercise both branches of ``route_model`` unchanged."""
    base: dict[str, object] = {
        "profile": "test",
        "canal_a_auto": frozenset({Sensitivity.PUBLIC}),
        "egress_allowlist": frozenset(),
        "contracts": (),
        "declared_domains": {},
        "bounds": {},
        "quotas": {},
    }
    base.update(over)
    return Policy(**base)  # type: ignore[arg-type]


def _runner() -> LocalRunner:
    """A stub-backed runner with NO guard wired - mirrors ``test_runtime.py``'s helper: the
    runner then only shape-checks a grant's effect (never redeems its token), so any Grant
    shaped for MODEL_CALL is accepted regardless of which Guard minted it."""
    return LocalRunner(snapshots=SnapshotStore(), observability=LocalObservability())


class _CapturingGuard:
    """A minimal Guard double that records every request it is asked to grant.

    Stands in for :class:`DeterministicGuard` so a consumer's D7-routed ``GuardRequest`` can
    be inspected directly (the real Guard mints a ``Grant`` but never exposes the request it
    was given, and the snapshot store only records the BACKEND's model id, never the D7-routed
    ``target`` - D98, the physical swap is a later seam). Paired with the no-guard-wired
    runner above, so the returned ``Grant`` needs no valid token (D89 / M1 shape-only path):
    the request SHAPE is what these tests assert, not authorization semantics (already covered
    by invariants 1 / 5 in test_invariants.py)."""

    def __init__(self) -> None:
        self.requests: list[GuardRequest] = []

    def grant(self, request: GuardRequest) -> Grant:
        self.requests.append(request)
        return Grant(request=request, released_label=request.inputs[0])


# ====================================================================================== #
# RoutingClass (D7 / D26) - the capability taxonomy, model-agnostic                       #
# ====================================================================================== #


def test_routing_class_has_exactly_micro_and_reasoning_members() -> None:
    assert {member.name for member in RoutingClass} == {"MICRO", "REASONING"}


def test_routing_class_value_tokens_are_the_lowercase_config_keys() -> None:
    assert RoutingClass.MICRO.value == "micro"
    assert RoutingClass.REASONING.value == "reasoning"


# ====================================================================================== #
# Policy.model_for (D7 / D70) - config-driven, frontier-default                          #
# ====================================================================================== #


def test_model_for_empty_table_resolves_every_class_to_none() -> None:
    # D126 default (no bench measurement yet): an empty [model_routing] sends EVERY class to
    # the capable default, never an error - "frontier suffices for the majority" out of the box.
    policy = _policy()
    assert policy.model_for(RoutingClass.MICRO) is None
    assert policy.model_for(RoutingClass.REASONING) is None


def test_model_for_returns_the_mapped_model_for_its_class() -> None:
    policy = _policy(model_routing={"micro": "tiny-local"})
    assert policy.model_for(RoutingClass.MICRO) == "tiny-local"


def test_model_for_honors_an_explicit_default_when_unmapped() -> None:
    policy = _policy()  # empty table
    assert policy.model_for(RoutingClass.REASONING, default="fallback-id") == "fallback-id"


def test_model_for_mapped_class_wins_over_a_passed_default() -> None:
    # the CONFIGURED mapping always wins over a caller-supplied default - `default` is only
    # ever consulted for a class the policy has not mapped.
    policy = _policy(model_routing={"micro": "tiny-local"})
    assert policy.model_for(RoutingClass.MICRO, default="ignored") == "tiny-local"


# ====================================================================================== #
# load_policy (D7 / D70) - [model_routing] is CONFIG, the section is optional             #
# ====================================================================================== #


def test_load_policy_parses_the_model_routing_section(tmp_path: Path) -> None:
    zone = tmp_path / "policy.toml"
    zone.write_text('profile = "test"\n\n[model_routing]\nmicro = "tiny-local"\n', encoding="utf-8")
    policy = load_policy(zone)
    assert policy.model_routing.get("micro") == "tiny-local"
    assert policy.model_for(RoutingClass.MICRO) == "tiny-local"
    assert policy.model_for(RoutingClass.REASONING) is None  # unmapped => still the default


def test_load_policy_without_the_section_defaults_to_the_frontier_for_every_class(
    tmp_path: Path,
) -> None:
    zone = tmp_path / "policy.toml"
    zone.write_text('profile = "test"\n', encoding="utf-8")  # no [model_routing] at all
    policy = load_policy(zone)
    assert dict(policy.model_routing) == {}
    assert policy.model_for(RoutingClass.MICRO) is None
    assert policy.model_for(RoutingClass.REASONING) is None


# ====================================================================================== #
# ModelRouter.route (D7) - delegates to Policy.model_for, never raises                    #
# ====================================================================================== #


def test_router_route_resolves_to_none_over_an_empty_table() -> None:
    router = ModelRouter(_policy())
    assert router.route(RoutingClass.MICRO) is None
    assert router.route(RoutingClass.REASONING) is None


def test_router_route_resolves_to_the_mapped_model_id() -> None:
    router = ModelRouter(_policy(model_routing={"reasoning": "big-local"}))
    assert router.route(RoutingClass.REASONING) == "big-local"
    assert router.route(RoutingClass.MICRO) is None  # the other class stays untouched


def test_router_never_raises_on_an_unmapped_class() -> None:
    router = ModelRouter(_policy())  # nothing mapped
    for routing_class in RoutingClass:
        assert router.route(routing_class) is None  # fail-safe toward the capable default


# ====================================================================================== #
# _model_call_request (D7) - the GuardRequest builder, zero-regression when unrouted      #
# ====================================================================================== #


def test_model_call_request_router_none_is_byte_identical_to_pre_d7() -> None:
    subject = Bubble("ingest")
    inputs = (_label(PUB),)
    request = _model_call_request(
        subject=subject,
        inputs=inputs,
        router=None,
        routing_class=RoutingClass.MICRO,
        action="classify",
    )
    # byte-identical to the pre-D7 shape: no target, no descriptor.
    assert request == GuardRequest(effect=Effect.MODEL_CALL, subject=subject, inputs=inputs)
    assert request.target is None
    assert request.descriptor == ""
    assert request.effect is Effect.MODEL_CALL


def test_model_call_request_with_router_over_an_empty_table_names_the_default() -> None:
    router = ModelRouter(_policy())
    request = _model_call_request(
        subject=Bubble("ingest"),
        inputs=(_label(PUB),),
        router=router,
        routing_class=RoutingClass.MICRO,
        action="classify",
    )
    assert request.target is None
    assert "default" in request.descriptor
    assert "micro" in request.descriptor


def test_model_call_request_with_router_over_a_mapped_table_names_the_model() -> None:
    router = ModelRouter(_policy(model_routing={"micro": "tiny-local"}))
    request = _model_call_request(
        subject=Bubble("ingest"),
        inputs=(_label(PUB),),
        router=router,
        routing_class=RoutingClass.MICRO,
        action="classify",
    )
    assert request.target == "tiny-local"
    assert "tiny-local" in request.descriptor


# ====================================================================================== #
# Consumer wiring (D7) - ModelSemanticSensor / ModelFactExtractor declare their class      #
# ====================================================================================== #


def test_semantic_sensor_request_target_is_none_without_a_router() -> None:
    guard = _CapturingGuard()
    sensor = ModelSemanticSensor(guard, _runner(), subject=Bubble("ingest"))  # router=None
    assert sensor.assess("a normal note") is None  # stub => abstain (verdict is NOT under test)
    assert len(guard.requests) == 1
    assert guard.requests[0].target is None
    assert guard.requests[0].descriptor == ""


def test_semantic_sensor_request_target_reflects_a_mapped_router() -> None:
    guard = _CapturingGuard()
    router = ModelRouter(_policy(model_routing={"micro": "tiny-local"}))
    sensor = ModelSemanticSensor(guard, _runner(), subject=Bubble("ingest"), router=router)
    assert sensor.assess("a normal note") is None  # still abstains - only the REQUEST differs
    assert guard.requests[0].target == "tiny-local"
    assert "tiny-local" in guard.requests[0].descriptor


def test_fact_extractor_request_target_is_none_without_a_router() -> None:
    guard = _CapturingGuard()
    extractor = ModelFactExtractor(guard, _runner(), subject=Bubble("ingest"))  # router=None
    facts = extractor.extract(Envelope("Paris is the capital of France", _label(PUB)))
    assert facts == ()  # stub => no fact (the verdict is NOT under test)
    assert guard.requests[0].target is None
    assert guard.requests[0].descriptor == ""


def test_fact_extractor_request_target_reflects_a_mapped_router() -> None:
    guard = _CapturingGuard()
    router = ModelRouter(_policy(model_routing={"micro": "tiny-local"}))
    extractor = ModelFactExtractor(guard, _runner(), subject=Bubble("ingest"), router=router)
    facts = extractor.extract(Envelope("Paris is the capital of France", _label(PUB)))
    assert facts == ()
    assert guard.requests[0].target == "tiny-local"
    assert "tiny-local" in guard.requests[0].descriptor


# ====================================================================================== #
# Orthogonality (D7 / invariant 1) - route_model picks the CHANNEL, unaffected by MODEL   #
# routing; a sensible / perso call NEVER moves off LOCAL because [model_routing] is set   #
# ====================================================================================== #


def test_route_model_is_unaffected_by_a_populated_model_routing_table() -> None:
    # A richly populated model_routing table - the router genuinely resolves both classes to
    # concrete local models, so this is not an accidentally-empty / vacuous table.
    policy = _policy(model_routing={"micro": "tiny-local", "reasoning": "big-local"})
    router = ModelRouter(policy)
    assert router.route(RoutingClass.MICRO) == "tiny-local"
    assert router.route(RoutingClass.REASONING) == "big-local"
    # ... yet the Guard's CHANNEL decision (D66, invariant 1) is untouched: sensible / perso /
    # unlabeled-fail-safe still force LOCAL - the model router can never move them off-machine.
    guard = DeterministicGuard(policy=policy)
    assert guard.route_model((_label(SENS),)) is Channel.LOCAL
    assert guard.route_model((_label(PERSO),)) is Channel.LOCAL
    assert guard.route_model(()) is Channel.LOCAL  # empty => most-restrictive, unchanged
    # ... and public still clears canal A automatically - the populated table did not
    # ACCIDENTALLY tighten the channel gate either (orthogonal in BOTH directions).
    assert guard.route_model((_label(PUB),)) is Channel.CANAL_A_PUBLIC_AUTO


def test_route_model_gives_identical_verdicts_with_and_without_model_routing_configured() -> None:
    # The strongest form of the orthogonality claim: the SAME inputs, against a Guard built
    # over an EMPTY vs. a richly-populated model_routing table, must yield the IDENTICAL
    # channel every time - model routing is provably not one of route_model's inputs.
    empty_guard = DeterministicGuard(policy=_policy())
    populated_guard = DeterministicGuard(
        policy=_policy(model_routing={"micro": "tiny-local", "reasoning": "big-local"})
    )
    cases = (
        (_label(SENS),),
        (_label(PERSO),),
        (),
        (_label(PUB),),
        (_label(PUB), _label(SENS)),
    )
    for inputs in cases:
        assert empty_guard.route_model(inputs) is populated_guard.route_model(inputs)


# ====================================================================================== #
# Runner dispatch (γ / D98) - the routed model-id SELECTS the backend (not just names it); #
# unmapped / default-id / no-registry all fall back to the single wired default backend.   #
# ====================================================================================== #


class _MarkBackend:
    """A weightless ``GenerationBackend`` double whose free-form output is just its OWN id - so a
    test reads WHICH backend actually decoded a call (the proof γ dispatched, not merely named)."""

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def generate(self, prompt: str) -> str:
        return f"[{self._model_id}]"

    def generate_structured(self, prompt: str, schema: str, kind: str) -> str:
        return "{}"


def _model_grant(target: str | None) -> Grant:
    """A shape-only ``MODEL_CALL`` grant carrying a routed ``target``. The dispatch runner wires no
    Guard, so the token is never redeemed (only the effect SHAPE is checked) - the backend SELECTION
    is under test here, not authorization (covered by invariants 1 / 5 in test_invariants.py)."""
    label = _label(PUB)
    request = GuardRequest(
        effect=Effect.MODEL_CALL, subject=Bubble("ingest"), inputs=(label,), target=target
    )
    return Grant(request=request, released_label=label)


def _dispatch_runner(
    registry: BackendRegistry | None, *, snapshots: SnapshotStore | None = None
) -> LocalRunner:
    """A runner whose DEFAULT backend is ``default-model`` (a MarkBackend), optionally over a bench
    ``registry`` - so a test reads WHICH backend served a call off the payload AND (via an injected
    ``snapshots``) off the provenance tag the snapshot records (inv. 12)."""
    return LocalRunner(
        snapshots=snapshots if snapshots is not None else SnapshotStore(),
        observability=LocalObservability(),
        backend=_MarkBackend("default-model"),
        backends=registry,
    )


def test_runner_dispatches_a_completion_to_the_routed_backend() -> None:
    # γ: a call whose grant routes to a mapped, non-default model decodes through THAT backend - the
    # router's choice finally takes EFFECT (D98), no longer merely riding along as provenance.
    reg = BackendRegistry({"big-local": lambda: _MarkBackend("big-local")})
    store = SnapshotStore()
    out = _dispatch_runner(reg, snapshots=store).complete(
        Envelope("hi", _label(PUB)), grant=_model_grant("big-local")
    )
    assert out.payload == "[big-local]"  # the routed backend decoded
    # inv. 12 - the snapshot tags the model that ACTUALLY ran, never the stale default (provenance)
    assert store.get(store.all_ids()[0]).model_id == "big-local"


def test_runner_falls_back_to_the_default_for_none_or_unmapped_target() -> None:
    # None (unrouted) or an id the registry does not know => the wired default backend (the router's
    # capable default, D70) - never a crash, never a wrong backend.
    reg = BackendRegistry({"big-local": lambda: _MarkBackend("big-local")})
    runner = _dispatch_runner(reg)
    none_out = runner.complete(Envelope("hi", _label(PUB)), grant=_model_grant(None))
    unmapped_out = runner.complete(Envelope("hi", _label(PUB)), grant=_model_grant("nope"))
    assert none_out.payload == "[default-model]" and unmapped_out.payload == "[default-model]"


def test_runner_reuses_the_wired_default_for_its_own_id_without_a_second_load() -> None:
    # A call routed to the DEFAULT model's own id reuses the already-wired backend - the registry is
    # never consulted, so a second copy of the same weights is never loaded (memory, D95).
    loads: list[str] = []

    def factory() -> _MarkBackend:
        loads.append("default-model")
        return _MarkBackend("default-model")

    reg = BackendRegistry({"default-model": factory})
    out = _dispatch_runner(reg).complete(
        Envelope("hi", _label(PUB)), grant=_model_grant("default-model")
    )
    assert out.payload == "[default-model]" and loads == []


def test_runner_without_a_registry_ignores_the_routed_id_zero_regression() -> None:
    # No registry wired => the routed target is inert and every call uses the single default backend:
    # byte-identical to pre-γ behaviour (D126).
    out = _dispatch_runner(None).complete(
        Envelope("hi", _label(PUB)), grant=_model_grant("big-local")
    )
    assert out.payload == "[default-model]"


def test_runner_dispatches_a_structured_completion_and_tags_the_real_model() -> None:
    # The PRODUCTION model consumers (ModelSemanticSensor.assess / ModelFactExtractor.extract) decode
    # ONLY through complete_structured - so dispatch + honest tagging must hold on THAT path too. The
    # grammar barrier rejects a non-JSON marker, so which backend ran is read off the snapshot tag
    # (inv. 12) - the exact provenance guarantee γ adds on the path production actually uses.
    reg = BackendRegistry({"big-local": lambda: _MarkBackend("big-local")})
    store = SnapshotStore()
    constraint = GrammarConstraint(schema='{"type": "object"}')
    _dispatch_runner(reg, snapshots=store).complete_structured(
        Envelope("hi", _label(PUB)), grant=_model_grant("big-local"), constraint=constraint
    )
    assert store.get(store.all_ids()[0]).model_id == "big-local"
