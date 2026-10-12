"""D159 - WallLedger: "buter sur un mur cesse d'être silencieux".

The load-bearing claim is structural: :meth:`DeterministicGuard.authorize` is the ONE choke point
every mediated effect passes through (D89), so wiring the deposit there - rather than asking every
caller to remember to log its own refusal - means a refusal cannot leave without a matching entry.
``test_a_deny_is_logged`` / ``test_an_escalate_is_logged`` ARE the control that turns red: comment
out the `self._log_wall(request, floor)` line in ``guard/monitor.py`` and either one fails
immediately. (That sabotage-and-restore was run by hand while D159 was being built; these tests
are what caught it.)
"""

from __future__ import annotations

from pathlib import Path

from pytest import raises

from mnemosyne.config import Policy
from mnemosyne.guard import DeterministicGuard, WallLedger
from mnemosyne.ports import (
    Bubble,
    Decision,
    Effect,
    GovernanceLabel,
    GuardDenied,
    GuardRequest,
    HumanTier,
    Ruling,
    Sensitivity,
)


def _policy(**over: object) -> Policy:
    """Minimal deny-by-default test policy - mirrors test_model_routing.py's builder."""
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


def _label(bubble: str = "b", sensitivity: Sensitivity = Sensitivity.PUBLIC) -> GovernanceLabel:
    return GovernanceLabel(sensitivity=sensitivity, bubble=Bubble(bubble))


# --- WallLedger, in isolation: fail-open on every axis ----------------------------------------
def test_record_and_read_all_round_trip(tmp_path: Path) -> None:
    ledger = WallLedger(tmp_path / "w.jsonl")
    req = GuardRequest(
        effect=Effect.POLICY_WRITE, subject=Bubble("research"), inputs=(), descriptor="widen egress"
    )
    ledger.record(req, Ruling(Decision.ESCALATE, "reason text", HumanTier.LIFE_DECISION))

    entries = ledger.read_all()
    assert len(entries) == 1
    assert entries[0]["effect"] == "policy_write"
    assert entries[0]["subject"] == "research"
    assert entries[0]["decision"] == "escalate"
    assert entries[0]["reason"] == "reason text"
    assert entries[0]["tier"] == "life_decision"


def test_read_all_on_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert WallLedger(tmp_path / "never.jsonl").read_all() == ()


def test_a_corrupt_line_is_skipped_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "w.jsonl"
    path.write_text("this is not json\n", encoding="utf-8")
    assert WallLedger(path).read_all() == ()


def test_record_never_raises_even_when_the_parent_cannot_be_created(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")  # a FILE, so mkdir(parents=True) below it must fail
    ledger = WallLedger(blocker / "sub" / "walls.jsonl")
    req = GuardRequest(effect=Effect.POLICY_WRITE, subject=Bubble("b"), inputs=())
    ledger.record(req, Ruling(Decision.DENY, "x"))  # must not raise (D111 fail-open)


# --- wired into the Guard: the actual control ---------------------------------------------------
def test_a_deny_is_logged(tmp_path: Path) -> None:
    walls = WallLedger(tmp_path / "walls.jsonl")
    guard = DeterministicGuard(_policy(), walls=walls)
    request = GuardRequest(
        effect=Effect.CROSS_BUBBLE,
        subject=Bubble("b"),
        inputs=(_label(bubble="other"),),
        target="elsewhere",
    )
    ruling = guard.authorize(request)
    assert ruling.decision is Decision.DENY
    entries = walls.read_all()
    assert len(entries) == 1
    assert entries[0]["effect"] == "cross_bubble"
    assert entries[0]["decision"] == "deny"


def test_an_escalate_is_logged(tmp_path: Path) -> None:
    walls = WallLedger(tmp_path / "walls.jsonl")
    guard = DeterministicGuard(_policy(), walls=walls)
    ruling = guard.authorize(
        GuardRequest(effect=Effect.POLICY_WRITE, subject=Bubble("b"), inputs=())
    )
    assert ruling.decision is Decision.ESCALATE
    entries = walls.read_all()
    assert len(entries) == 1
    assert entries[0]["decision"] == "escalate"
    assert entries[0]["tier"] == "life_decision"


def test_an_allow_is_never_logged(tmp_path: Path) -> None:
    walls = WallLedger(tmp_path / "walls.jsonl")
    guard = DeterministicGuard(_policy(), walls=walls)
    ruling = guard.authorize(
        GuardRequest(effect=Effect.MODEL_CALL, subject=Bubble("b"), inputs=(_label(),))
    )
    assert ruling.decision is Decision.ALLOW
    assert walls.read_all() == ()


def test_without_a_ledger_authorize_is_unaffected() -> None:
    """Zero regression: `walls` defaults to None, so every pre-D159 caller is byte-identical."""
    guard = DeterministicGuard(_policy())
    ruling = guard.authorize(
        GuardRequest(effect=Effect.POLICY_WRITE, subject=Bubble("b"), inputs=())
    )
    assert ruling.decision is Decision.ESCALATE  # unaffected by the absent ledger


def test_grant_deposits_the_refusal_before_raising(tmp_path: Path) -> None:
    """`grant()` calls `authorize()` first - the SAME choke point, so refusals raised from
    `grant()` (not just plain `authorize()` calls) are deposited too."""
    walls = WallLedger(tmp_path / "walls.jsonl")
    guard = DeterministicGuard(_policy(), walls=walls)
    request = GuardRequest(
        effect=Effect.CROSS_BUBBLE,
        subject=Bubble("b"),
        inputs=(_label(bubble="other"),),
        target="elsewhere",
    )
    with raises(GuardDenied):
        guard.grant(request)
    assert len(walls.read_all()) == 1


def test_a_broken_wall_ledger_never_changes_the_verdict() -> None:
    """The Guard's core correctness must never depend on the logging side-channel succeeding -
    even a ledger that raises on `record` (not just a real WallLedger, which already swallows its
    own errors) must not change what `authorize` returns."""

    class _ExplodingLedger:
        def record(self, request: GuardRequest, ruling: Ruling) -> None:
            raise RuntimeError("disk full")

    guard = DeterministicGuard(_policy(), walls=_ExplodingLedger())  # type: ignore[arg-type]
    ruling = guard.authorize(
        GuardRequest(effect=Effect.POLICY_WRITE, subject=Bubble("b"), inputs=())
    )
    assert ruling.decision is Decision.ESCALATE  # unaffected - no exception propagated either


# --- `make murs`: the visibility side --------------------------------------------------------
def test_render_walls_is_honest_when_empty() -> None:
    from mnemosyne.runtime.murs_run import render_walls

    assert "Aucun refus" in render_walls(())


def test_render_walls_groups_by_effect_and_lists_the_most_recent() -> None:
    from mnemosyne.runtime.murs_run import render_walls

    entries = (
        {
            "at": "2026-07-26T10:00:00",
            "effect": "egress",
            "decision": "deny",
            "reason": "hote absent",
        },
        {
            "at": "2026-07-26T11:00:00",
            "effect": "policy_write",
            "decision": "escalate",
            "reason": "acte privilegie",
        },
        {
            "at": "2026-07-26T12:00:00",
            "effect": "egress",
            "decision": "deny",
            "reason": "hote absent (2)",
        },
    )
    out = render_walls(entries)
    assert "egress: 2" in out
    assert "policy_write: 1" in out
    assert "acte privilegie" in out
    assert "make policy-demander" in out
