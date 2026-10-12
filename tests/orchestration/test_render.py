"""(3)-6a - the governed document-output couture (sorties : D66 / D89 / D100 / D108).

Biting tests for the output MIRROR of ingestion: a LOCAL render emits any label (interior persistence,
D71); a SHAREABLE render is egress-governed (allow-list inv. 21 + the M2 content re-floor - a `sensible`
body mislabeled `public` cannot slip out); redaction is STRUCTURAL (the deterministic floor is the
barrier, never the redactor's word); and the fail-closed default refuses rather than fabricate an
artifact. The single-use grant is redeemed exactly once on the shareable path (M1, the egress consumer).
"""

from __future__ import annotations

import re
from pathlib import Path

from pytest import raises

from mnemosyne.config import load_policy
from mnemosyne.guard import DeterministicGuard
from mnemosyne.ingest import DeterministicClassifier
from mnemosyne.ports import (
    Bubble,
    Envelope,
    EscalateToHuman,
    GovernanceLabel,
    GuardDenied,
    Grant,
    GuardRequest,
    RenderDestination,
    RenderRequest,
    RenderResult,
    Sensitivity,
)
from mnemosyne.runtime.render import (
    GovernedRenderer,
    MalformedRender,
    RefusingRenderer,
    RenderUnavailable,
)

_BUBBLE = Bubble("desk")
_HOST = "share.local"
# a body whose deterministic PII floor is `sensible` (the classifier's IBAN rule matches).
_IBAN_BODY = "Account balance FR7630006000011234567890189 to archive."
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Za-z0-9]){9,30}\b")


def _label(sensitivity: Sensitivity = Sensitivity.PUBLIC) -> GovernanceLabel:
    return GovernanceLabel(sensitivity=sensitivity, bubble=_BUBBLE)


def _egress_guard(
    tmp_path: Path, classifier: DeterministicClassifier, *, hosts: tuple[str, ...] = (_HOST,)
) -> DeterministicGuard:
    """A Guard whose protected policy allow-lists ``hosts`` for egress (SE5 / inv. 21)."""
    allow = ", ".join(f'"{h}"' for h in hosts)
    zone = tmp_path / "policy.toml"
    zone.write_text(f"[egress]\nallowlist = [{allow}]\n", encoding="utf-8")
    return DeterministicGuard(policy=load_policy(zone), classifier=classifier)


class _EchoRenderer:
    """A test :class:`Renderer` that echoes the body as bytes - proves the GOVERNED layer, not a real
    engine (the real Typst brick is (3)-6b). Records every request it is handed."""

    def __init__(self) -> None:
        self.requests: list[RenderRequest] = []

    def render(self, request: RenderRequest) -> RenderResult:
        self.requests.append(request)
        return RenderResult(fmt=request.fmt, artifact=request.body.encode("utf-8"))


class _StripRedactor:
    """A redactor that genuinely removes the IBAN span (so a re-floor lands PUBLIC)."""

    def redact(self, content: str) -> str:
        return _IBAN_RE.sub("[redacted]", content)


class _NoOpRedactor:
    """A redactor that UNDER-CLEANS - returns the body unchanged (the floor must still catch it)."""

    def redact(self, content: str) -> str:
        return content


class _BrokenRedactor:
    """A redactor that returns a NON-STRING (a broken brick) - must be treated like no redactor."""

    def redact(self, content: str) -> object:  # noqa: ARG002 - deliberately returns non-str
        return None


class _RedeemSpyGuard:
    """Wraps a Guard to count :meth:`redeem` calls - proves the single-use egress consumer (M1)."""

    def __init__(self, inner: DeterministicGuard) -> None:
        self._inner = inner
        self.grants = 0
        self.redeems = 0

    def grant(self, request: GuardRequest) -> Grant:
        self.grants += 1
        return self._inner.grant(request)

    def redeem(self, grant: Grant) -> None:
        self.redeems += 1
        self._inner.redeem(grant)


# --- LOCAL render - interior persistence, any label, no egress grant (D71 / D89) --------------
def test_local_render_emits_any_label_without_a_grant(tmp_path: Path) -> None:
    cls = DeterministicClassifier()
    spy = _RedeemSpyGuard(_egress_guard(tmp_path, cls))
    renderer = _EchoRenderer()
    gov = GovernedRenderer(renderer=renderer, guard=spy, classifier=cls)

    out = gov.render(
        Envelope(payload=_IBAN_BODY, label=_label(Sensitivity.SENSIBLE)),
        fmt="pdf",
        subject=_BUBBLE,
        destination=RenderDestination.LOCAL,
    )
    assert out.payload == _IBAN_BODY.encode(
        "utf-8"
    )  # the artifact is the engine's bytes (fidelity)
    assert (
        out.label.sensitivity is Sensitivity.SENSIBLE
    )  # a local artifact keeps the content's label
    assert spy.grants == 0 and spy.redeems == 0  # interior - the Guard mediates frontiers, not this


# --- SHAREABLE render - egress-governed (allow-list + M2 content re-floor) --------------------
def test_shareable_public_render_allowed_to_allowlisted_target(tmp_path: Path) -> None:
    cls = DeterministicClassifier()
    spy = _RedeemSpyGuard(_egress_guard(tmp_path, cls))
    renderer = _EchoRenderer()
    gov = GovernedRenderer(renderer=renderer, guard=spy, classifier=cls)

    out = gov.render(
        Envelope(payload="Public agenda.", label=_label(Sensitivity.PUBLIC)),
        fmt="pdf",
        subject=_BUBBLE,
        destination=RenderDestination.SHAREABLE,
        target=_HOST,
    )
    assert out.payload == "Public agenda.".encode("utf-8")
    assert out.label.sensitivity is Sensitivity.PUBLIC
    assert spy.grants == 1 and spy.redeems == 1  # the single-use egress consumer (M1)


def test_shareable_render_to_unlisted_target_denied(tmp_path: Path) -> None:
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    gov = GovernedRenderer(renderer=_EchoRenderer(), guard=guard, classifier=cls)
    with raises(GuardDenied):  # deny-by-default egress allow-list (inv. 21 / SE5)
        gov.render(
            Envelope(payload="hello", label=_label(Sensitivity.PUBLIC)),
            fmt="pdf",
            subject=_BUBBLE,
            destination=RenderDestination.SHAREABLE,
            target="not.allow.listed",
        )


def test_shareable_sensible_content_mislabeled_public_escalates(tmp_path: Path) -> None:
    # THE M2 barrier: the LABEL lies (public) but the CONTENT floors sensible - the Guard re-reads the
    # raw body and refuses the auto-leak, routing to a canal-B human gesture (never a silent leak).
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    renderer = _EchoRenderer()
    gov = GovernedRenderer(renderer=renderer, guard=guard, classifier=cls)
    with raises(EscalateToHuman):
        gov.render(
            Envelope(payload=_IBAN_BODY, label=_label(Sensitivity.PUBLIC)),  # mislabeled public
            fmt="pdf",
            subject=_BUBBLE,
            destination=RenderDestination.SHAREABLE,
            target=_HOST,
        )
    assert renderer.requests == []  # the engine is NEVER reached - cleared before rendering


def test_shareable_sensible_label_escalates(tmp_path: Path) -> None:
    # non-public BY LABEL (benign content) also escalates - sensible-local holds by itself (D66).
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    gov = GovernedRenderer(renderer=_EchoRenderer(), guard=guard, classifier=cls)
    with raises(EscalateToHuman):
        gov.render(
            Envelope(payload="nothing special", label=_label(Sensitivity.SENSIBLE)),
            fmt="pdf",
            subject=_BUBBLE,
            destination=RenderDestination.SHAREABLE,
            target=_HOST,
        )


# --- Redaction is STRUCTURAL - the floor is the barrier, not the redactor (D100) --------------
def test_redaction_that_truly_cleans_allows_public_share(tmp_path: Path) -> None:
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    renderer = _EchoRenderer()
    gov = GovernedRenderer(
        renderer=renderer, guard=guard, classifier=cls, redactor=_StripRedactor()
    )
    out = gov.render(
        Envelope(payload=_IBAN_BODY, label=_label(Sensitivity.SENSIBLE)),
        fmt="pdf",
        subject=_BUBBLE,
        destination=RenderDestination.SHAREABLE,
        target=_HOST,
        redact=True,
    )
    assert (
        out.label.sensitivity is Sensitivity.PUBLIC
    )  # re-floored public after a genuine redaction
    assert b"FR7630006000011234567890189" not in out.payload  # the IBAN never reaches the artifact
    assert (
        _IBAN_RE.search(renderer.requests[0].body) is None
    )  # the engine only saw the cleaned body


def test_redaction_that_undercleans_still_escalates(tmp_path: Path) -> None:
    # THE D100 test: a redactor that fails to remove the IBAN cannot lower the verdict - the
    # deterministic re-floor still lands sensible, so the Guard escalates (structural, not trust).
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    gov = GovernedRenderer(
        renderer=_EchoRenderer(), guard=guard, classifier=cls, redactor=_NoOpRedactor()
    )
    with raises(EscalateToHuman):
        gov.render(
            Envelope(payload=_IBAN_BODY, label=_label(Sensitivity.SENSIBLE)),
            fmt="pdf",
            subject=_BUBBLE,
            destination=RenderDestination.SHAREABLE,
            target=_HOST,
            redact=True,
        )


def test_no_redactor_wired_non_public_still_escalates(tmp_path: Path) -> None:
    # redact=True but no redactor wired => body unchanged => non-public stays non-public => escalate.
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    gov = GovernedRenderer(renderer=_EchoRenderer(), guard=guard, classifier=cls)  # no redactor
    with raises(EscalateToHuman):
        gov.render(
            Envelope(payload=_IBAN_BODY, label=_label(Sensitivity.SENSIBLE)),
            fmt="pdf",
            subject=_BUBBLE,
            destination=RenderDestination.SHAREABLE,
            target=_HOST,
            redact=True,
        )


def test_redactor_returning_non_string_still_escalates(tmp_path: Path) -> None:
    # audit (3)-6 M1 / D100: a BROKEN redactor (returns non-str) cannot be re-classified -> it is treated
    # exactly like no redactor (the original non-public label stands), so the Guard escalates and the
    # engine is never reached - the barrier never trusts the brick's output SHAPE.
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    renderer = _EchoRenderer()
    gov = GovernedRenderer(
        renderer=renderer, guard=guard, classifier=cls, redactor=_BrokenRedactor()
    )
    with raises(EscalateToHuman):
        gov.render(
            Envelope(payload=_IBAN_BODY, label=_label(Sensitivity.SENSIBLE)),
            fmt="pdf",
            subject=_BUBBLE,
            destination=RenderDestination.SHAREABLE,
            target=_HOST,
            redact=True,
        )
    assert renderer.requests == []  # cleared before rendering - the engine is never reached


# --- Fail-closed default + malformed input ---------------------------------------------------
def test_refusing_renderer_refuses_never_fabricates(tmp_path: Path) -> None:
    # no rendering engine wired => output refused fail-closed, never an empty/fake artifact (D111).
    with raises(RenderUnavailable):
        RefusingRenderer().render(RenderRequest(body="x", fmt="pdf"))


def test_non_string_body_is_malformed(tmp_path: Path) -> None:
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    gov = GovernedRenderer(renderer=_EchoRenderer(), guard=guard, classifier=cls)
    with raises(MalformedRender):
        gov.render(
            Envelope(payload=object(), label=_label(Sensitivity.PUBLIC)),  # not a source string
            fmt="pdf",
            subject=_BUBBLE,
            destination=RenderDestination.LOCAL,
        )


def test_default_destination_is_the_stricter_shareable_path(tmp_path: Path) -> None:
    # a caller who FORGETS to say LOCAL is governed as egress (fail-safe stricter), never the reverse:
    # a sensible body with no destination given must escalate, not silently render.
    cls = DeterministicClassifier()
    guard = _egress_guard(tmp_path, cls)
    gov = GovernedRenderer(renderer=_EchoRenderer(), guard=guard, classifier=cls)
    with raises(EscalateToHuman):
        gov.render(
            Envelope(payload=_IBAN_BODY, label=_label(Sensitivity.SENSIBLE)),
            fmt="pdf",
            subject=_BUBBLE,
            target=_HOST,  # no destination -> defaults to SHAREABLE
        )
