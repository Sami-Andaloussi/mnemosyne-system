"""Structural / contract smoke test for LOT 1 (the ports).

This is NOT the 27-invariant suite - that is LOT 2, which binds failing tests to
these contracts at the system boundary. Here we only check that the contract
layer holds together: every port imports and is an abstract Protocol, and the
governed-data algebra of ``core`` behaves exactly as the contract states
(most-restrictive merge, fail-safe default, upward-only relabel - the type-level
form of invariants 17 / 18 / 23).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import mnemosyne.ports as ports
from mnemosyne.ports import (
    PORTS,
    Bubble,
    Classification,
    CloisonnementError,
    Domain,
    Envelope,
    ErrorCode,
    GovernanceLabel,
    GuardDenied,
    MonotonicityError,
    Sensitivity,
)

# --- the contract layer holds together ------------------------------------------------


def test_all_public_names_resolve() -> None:
    for name in ports.__all__:
        assert hasattr(ports, name), f"mnemosyne.ports.__all__ exports missing name: {name}"


def test_prises_present_as_protocols() -> None:
    # 13 prises at LOT 1 (D123) + KeywordIndex ((3)-2b) + Renderer ((3)-6, the document-output prise)
    # + Reranker (LOT 5, the cross-encoder rerank leg, D68 stage 6); 18 Protocol objects because
    # Store = IntentLog + TruthStore and Tools = ToolPlugin + ToolCatalog.
    assert len(PORTS) == 18
    for port in PORTS:
        assert getattr(port, "_is_protocol", False), f"{port.__name__} is not a Protocol"


def test_ports_are_not_instantiable() -> None:
    # A Protocol cannot be constructed - adapters (LOT 4b/5/6) implement it instead.
    for port in (ports.Guard, ports.GraphStore, ports.Runner):
        with pytest.raises(TypeError):
            port()  # type: ignore[abstract,call-arg]


# --- Sensitivity (D101 / D66 / invariant 1) -------------------------------------------


def test_sensitivity_is_ordered_public_perso_sensible() -> None:
    assert Sensitivity.PUBLIC < Sensitivity.PERSO < Sensitivity.SENSIBLE
    assert max(Sensitivity.PUBLIC, Sensitivity.SENSIBLE) is Sensitivity.SENSIBLE
    assert Sensitivity.SENSIBLE.token == "sensible"


def test_only_public_may_use_automatic_cloud() -> None:
    assert Sensitivity.PUBLIC.may_use_automatic_cloud() is True
    assert Sensitivity.PERSO.may_use_automatic_cloud() is False
    assert Sensitivity.SENSIBLE.may_use_automatic_cloud() is False


def test_default_sensitivity_is_sensible() -> None:
    assert ports.DEFAULT_SENSITIVITY is Sensitivity.SENSIBLE


# --- GovernanceLabel (D108-(5) / invariants 17 / 23) ------------------------------------


def _label(level: Sensitivity, bubble: str = "b", domains: tuple[str, ...] = ()) -> GovernanceLabel:
    return GovernanceLabel(
        sensitivity=level,
        bubble=Bubble(bubble),
        domains=frozenset(Domain(d) for d in domains),
    )


def test_unlabeled_data_is_fail_safe_sensible() -> None:
    label = GovernanceLabel.unlabeled()
    assert label.sensitivity is Sensitivity.SENSIBLE
    assert label.bubble == ports.UNLABELED_BUBBLE


def test_merge_takes_the_maximum_and_unions_domains() -> None:
    merged = _label(Sensitivity.PUBLIC, "b", ("x",)).merge(_label(Sensitivity.PERSO, "b", ("y",)))
    assert merged.sensitivity is Sensitivity.PERSO
    assert merged.domains == {Domain("x"), Domain("y")}


def test_merge_across_bubbles_is_refused() -> None:
    with pytest.raises(CloisonnementError):
        _label(Sensitivity.PERSO, "finances").merge(_label(Sensitivity.PERSO, "santé"))


def test_label_cannot_be_lowered_automatically() -> None:
    sensitive = _label(Sensitivity.SENSIBLE)
    assert sensitive.raised_to(Sensitivity.SENSIBLE) is sensitive  # no-op allowed
    with pytest.raises(MonotonicityError):
        sensitive.raised_to(Sensitivity.PUBLIC)
    raised = _label(Sensitivity.PUBLIC).raised_to(Sensitivity.SENSIBLE)
    assert raised.sensitivity is Sensitivity.SENSIBLE


# --- Envelope (D108-(5)) ----------------------------------------------------------------


def test_envelope_relabel_is_upward_only() -> None:
    env = Envelope(payload="x", label=_label(Sensitivity.PERSO))
    assert env.relabel(_label(Sensitivity.SENSIBLE)).label.sensitivity is Sensitivity.SENSIBLE
    with pytest.raises(MonotonicityError):
        env.relabel(_label(Sensitivity.PUBLIC))


def test_envelope_relabel_refuses_cross_bubble() -> None:
    # m1 (rebullage silencieux): relabel may not move an envelope to another bubble - a
    # cross-bubble move needs a validated Guard contract, not a quiet label swap (inv 3).
    env = Envelope(payload="x", label=_label(Sensitivity.PERSO, "finances"))
    assert env.relabel(_label(Sensitivity.SENSIBLE, "finances")).label.bubble == Bubble("finances")
    with pytest.raises(CloisonnementError):
        env.relabel(_label(Sensitivity.SENSIBLE, "santé"))


def test_envelope_map_keeps_the_label() -> None:
    env = Envelope(payload="hello", label=_label(Sensitivity.SENSIBLE))
    mapped = env.map(len)
    assert mapped.payload == 5
    assert mapped.label is env.label


# --- normalized errors (D108 volet (2)) -------------------------------------------------


def test_errors_carry_normalized_codes() -> None:
    assert GuardDenied.code is ErrorCode.DENIED
    assert MonotonicityError.code is ErrorCode.MONOTONICITY
    assert isinstance(GuardDenied("x"), ports.MnemosyneError)


def test_provenance_derivation_keeps_the_chain() -> None:
    root = ports.Provenance(origin="doc:1", produced_by="ingest", at=datetime.now(timezone.utc))
    child = root.derive("distill")
    assert child.parents == (root,)
    assert child.origin == "doc:1"


def test_classification_cannot_sit_below_its_floor() -> None:
    # invariant 18 (D101): an illegal verdict - below the deterministic floor -
    # is unrepresentable, mirroring the self-enforcing types in `core`.
    Classification(
        sensitivity=Sensitivity.SENSIBLE,
        floor=Sensitivity.SENSIBLE,
        domain_signal=Sensitivity.SENSIBLE,
    )
    with pytest.raises(MonotonicityError):
        Classification(
            sensitivity=Sensitivity.PUBLIC,
            floor=Sensitivity.SENSIBLE,
            domain_signal=Sensitivity.PUBLIC,
        )
