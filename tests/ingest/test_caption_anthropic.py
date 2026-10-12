"""Frontier vision captioner (sujet G / niveau 3) - the Guard is the barrier, not the adapter's manners.

The niveau-3 captioner sends a book figure to a cloud VLM - an EGRESS invariant 1 forbids AUTOMATICALLY. The
whole safety of :class:`AnthropicVisionCaptioner` is that it asks the Guard FIRST and sends NOTHING if the
Guard refuses. These tests pin exactly that, against a REAL :class:`DeterministicGuard` and a recording stub
backend (no SDK, D126): a figure leaves ONLY with a canal-B human gesture to an allow-listed host, and any
refusal - or API error - fails to ``""`` (D85), never a leak and never a lost book. Producer ≠ verifier
(D75): an isolated audit re-checks the egress security independently.
"""

from __future__ import annotations

from mnemosyne.config import Policy
from mnemosyne.guard.monitor import DeterministicGuard
from mnemosyne.ingest import AnthropicVisionCaptioner
from mnemosyne.ingest.caption_anthropic import _PROMPT, _clean_caption
from mnemosyne.ports import Bubble, HumanTier, Sensitivity

_FIGURE = b"\x89PNG\r\n\x1a\n a raw abstract chart the 7B fizzled on"


class _RecordingBackend:
    """A stub frontier backend that RECORDS every call, so a test can assert whether a figure actually left
    (the backend is reached) or not (the Guard refused before any egress)."""

    def __init__(
        self,
        reply: str = "A bar chart, increasing from left to right.",
        *,
        boom: bool = False,
    ) -> None:
        self.calls: list[tuple[bytes, str]] = []
        self._reply = reply
        self._boom = boom

    def describe(self, image: bytes, prompt: str) -> str:
        self.calls.append((image, prompt))
        if self._boom:
            raise RuntimeError("frontier API unreachable")
        return self._reply


def _guard(*, allow_anthropic: bool = True) -> DeterministicGuard:
    """A real Guard whose egress allow-list holds api.anthropic.com (or not). No classifier wired - a figure
    is raster BYTES, so the content floor fail-closes to SENSIBLE without one (M2)."""
    hosts = frozenset({"api.anthropic.com"}) if allow_anthropic else frozenset()
    policy = Policy(
        profile="test",
        canal_a_auto=frozenset({Sensitivity.PUBLIC}),
        egress_allowlist=hosts,
        contracts=(),
        declared_domains={},
        bounds={"queue_capacity": 256},
        quotas={},
    )
    return DeterministicGuard(policy=policy)


def _captioner(
    guard: DeterministicGuard, backend: _RecordingBackend, gesture: HumanTier | None
) -> AnthropicVisionCaptioner:
    return AnthropicVisionCaptioner(
        guard=guard, subject=Bubble("library"), backend=backend, human_gesture=gesture
    )


# --- the gesture opens the door (the positive path) -------------------------------------------------


def test_a_canal_b_gesture_lets_a_figure_reach_the_frontier() -> None:
    backend = _RecordingBackend()
    cap = _captioner(_guard(), backend, HumanTier.FLAG_ROUTINE)
    out = cap.caption(_FIGURE)
    assert out == "A bar chart, increasing from left to right."
    assert len(backend.calls) == 1  # the egress was authorized -> the frontier was actually reached
    sent_image, sent_prompt = backend.calls[0]
    assert (
        sent_image == _FIGURE and sent_prompt == _PROMPT
    )  # exactly the figure + the fixed public prompt


# --- the Guard is the barrier: no gesture / no host => NOTHING leaves (the point) --------------------


def test_without_a_gesture_the_guard_refuses_and_nothing_is_sent() -> None:
    # a captioner built with NO gesture (no confirmed batch) is structurally inert: the Guard escalates the
    # non-public egress, so caption fails CLOSED to "" and the backend is NEVER reached (no figure leaves).
    backend = _RecordingBackend()
    cap = _captioner(_guard(), backend, None)
    assert cap.caption(_FIGURE) == ""
    assert backend.calls == []  # the figure never reached the network - the Guard blocked it first


def test_an_un_allow_listed_host_is_denied_even_with_a_gesture() -> None:
    # the allow-list barrier is ABSOLUTE and independent of the gesture (D90): with the host OFF the policy
    # allow-list, even a FLAG_ROUTINE gesture cannot send the figure - the grant is DENIED, fail-closed to "".
    backend = _RecordingBackend()
    cap = _captioner(_guard(allow_anthropic=False), backend, HumanTier.FLAG_ROUTINE)
    assert cap.caption(_FIGURE) == ""
    assert backend.calls == []


def test_a_benign_or_life_decision_gesture_does_not_clear_a_leak() -> None:
    # only FLAG_ROUTINE (an explicit pre-effect validation) clears canal B; BENIGN (notify-after) and
    # LIFE_DECISION (never full-auto) do not - both fail closed, nothing leaves (fail-safe, no accidental widening).
    for tier in (HumanTier.BENIGN, HumanTier.LIFE_DECISION):
        backend = _RecordingBackend()
        assert _captioner(_guard(), backend, tier).caption(_FIGURE) == ""
        assert backend.calls == []


# --- fail-open on the API, minimisation of what leaves ----------------------------------------------


def test_an_authorized_call_that_errors_fails_open() -> None:
    # egress authorized (gesture + host) but the API blows up -> per-figure FAIL-OPEN (D85): "" so the book is
    # never lost, and the backend WAS reached (the failure is downstream of the cleared egress).
    backend = _RecordingBackend(boom=True)
    cap = _captioner(_guard(), backend, HumanTier.FLAG_ROUTINE)
    assert cap.caption(_FIGURE) == ""
    assert len(backend.calls) == 1


def test_surrounding_book_context_is_not_sent_to_the_frontier() -> None:
    # minimisation: the ImageCaptioner contract accepts `context`, but the frontier adapter deliberately sends
    # ONLY the figure + the fixed public prompt - never surrounding book text (which could be `perso`).
    backend = _RecordingBackend()
    cap = _captioner(_guard(), backend, HumanTier.FLAG_ROUTINE)
    cap.caption(_FIGURE, context="a personal and sensitive passage from the operator's book")
    _sent_image, sent_prompt = backend.calls[0]
    assert sent_prompt == _PROMPT  # the fixed prompt, unchanged
    assert (
        "personal" not in sent_prompt and "operator" not in sent_prompt
    )  # the context did not leak


# --- small surface guarantees -----------------------------------------------------------------------


def test_the_caption_is_collapsed_to_one_tidy_line() -> None:
    backend = _RecordingBackend(reply="  A   bell\n  shaped  curve.  \n")
    cap = _captioner(_guard(), backend, HumanTier.FLAG_ROUTINE)
    assert cap.caption(_FIGURE) == "A bell shaped curve."


def test_clean_caption_is_content_agnostic() -> None:
    assert _clean_caption("  a\n  b   c ") == "a b c"
    assert _clean_caption("") == ""


def test_model_id_is_exposed_for_provenance() -> None:
    cap = _captioner(_guard(), _RecordingBackend(), HumanTier.FLAG_ROUTINE)
    assert cap.model_id == "claude-haiku-4-5"
