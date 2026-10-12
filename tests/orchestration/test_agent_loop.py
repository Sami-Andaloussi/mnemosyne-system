"""D98 - the governed agent loop's core, proven brick-free (the modele-doublure = the stub decoder).

Biting tests for :mod:`mnemosyne.agents.loop`. The couture the Pydantic AI bridge left open is the
per-turn grant lifecycle (:func:`build_grant_source`): each agent turn must mint a FRESH single-use
``MODEL_CALL`` grant the Runner redeems (M1), routed LOCAL for ``sensible`` (never canal A), and a
denied turn must fail closed (no grant, no model). These prove exactly that - driving the REAL
:class:`~mnemosyne.runtime.runner.LocalRunner` (stub decoder) as Pydantic AI's engine would, with
NO brick installed (D126). The turn ceiling is read from the protected zone and an override may only
LOWER it (D100 / SE4). What NEEDS the brick - that the real ``RunnerModel.request`` actually fires -
is the ignition check :func:`smoke_agent_invokes_runner` (``# pragma: no cover``). Code English (D117).
"""

from __future__ import annotations

from pytest import raises

from mnemosyne.agents import build_grant_source
from mnemosyne.agents.loop import _resolve_turn_ceiling
from mnemosyne.ports import (
    Bubble,
    Channel,
    Effect,
    Envelope,
    GovernanceLabel,
    Grant,
    GuardDenied,
    GuardRequest,
    Sensitivity,
)
from mnemosyne.runtime.bootstrap import bootstrap

_SUBJECT = Bubble("agent-test")


def _label() -> GovernanceLabel:
    return GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=_SUBJECT)


def test_grant_source_mints_a_single_use_model_call_grant() -> None:
    # the couture: a turn's grant is a MODEL_CALL capability the Runner redeems exactly once (M1).
    rt = bootstrap()
    source = build_grant_source(rt.guard, _SUBJECT)
    grant = source(_label())
    assert grant.request.effect is Effect.MODEL_CALL
    rt.runner.complete(Envelope("turn one", _label()), grant=grant)  # authentic + unspent -> runs
    with raises(GuardDenied):
        rt.guard.redeem(grant)  # the runner already consumed it -> single-use refusal (M1 / D100)


def test_each_turn_mints_a_fresh_grant() -> None:
    # a grant is single-use, so the loop cannot reuse one across turns - each mint is distinct.
    rt = bootstrap()
    source = build_grant_source(rt.guard, _SUBJECT)
    g1, g2 = source(_label()), source(_label())
    assert g1.token is not None and g2.token is not None
    assert g1.token.nonce != g2.token.nonce


def test_sensible_turn_routes_local_never_canal_a() -> None:
    # sensible-local holds structurally: a bridged turn (floored sensible) never routes canal A.
    rt = bootstrap()
    grant = build_grant_source(rt.guard, _SUBJECT)(_label())
    assert grant.channel is Channel.LOCAL
    assert not grant.may_leave_machine  # invariant 1 / D66


def test_loop_drives_the_stub_runner_over_many_turns() -> None:
    # simulate Pydantic AI's engine: N turns, each minting a fresh grant via the source and driving
    # the REAL grammar-bound Runner (stub decoder = the modele-doublure). Every turn gets a reply and
    # burns its OWN grant (M1 single-use) - the governed loop, end to end, with no brick (D126).
    rt = bootstrap()
    source = build_grant_source(rt.guard, _SUBJECT)
    grants: list[Grant] = []
    for i in range(4):
        grant = source(_label())
        grants.append(grant)
        reply = rt.runner.complete(Envelope(f"turn {i}", _label()), grant=grant)
        assert reply.payload.strip()  # the stub answered this turn
    nonces = {g.token.nonce for g in grants if g.token is not None}
    assert len(nonces) == 4  # four distinct single-use capabilities, one per turn
    for spent in grants:
        with raises(GuardDenied):
            rt.guard.redeem(spent)  # each turn's grant was already consumed (single-use)


def test_grant_source_fails_closed_when_the_guard_denies() -> None:
    # no grant => no model: a denied turn PROPAGATES, never a silent pass (D100). A Guard whose
    # grant refuses stands in for any deny/escalate path; build_grant_source never swallows it.
    class _DenyingGuard:
        def grant(self, request: GuardRequest) -> Grant:
            raise GuardDenied("denied for the test (fail-closed)")

    source = build_grant_source(_DenyingGuard(), _SUBJECT)  # type: ignore[arg-type]
    with raises(GuardDenied):
        source(_label())


def test_turn_ceiling_reads_the_zone_and_override_only_lowers() -> None:
    # the anti-runaway depth is configured (SE4), not hard-coded; an override may only LOWER it.
    rt = bootstrap()
    ceiling = rt.policy.bound("agent_max_turns")
    assert _resolve_turn_ceiling(rt, None) == ceiling  # the configured cap by default
    assert _resolve_turn_ceiling(rt, 2) == 2  # an override below the cap lowers it
    assert _resolve_turn_ceiling(rt, ceiling + 100) == ceiling  # cannot exceed the zone (D100)
    assert _resolve_turn_ceiling(rt, 0) == 1  # clamped to at least one turn
