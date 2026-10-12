"""D154 - secret redaction at the boundaries, and what it deliberately does NOT catch.

Biting tests for the ported redactor (:mod:`mnemosyne.guard.redact`, MIT (c) 2025 Nous Research)
and its two wirings: the PUBLIC branch of the observability trail, and the untrusted return of a
governed tool call. Three things are proven here rather than asserted in a docstring:

* the redaction has **no off switch** - the upstream env opt-out was removed, so setting it
  changes nothing (a barrier that can be flipped is discipline, not a barrier - D100 / inv. 17);
* the ordering invariant at the tool seam - the PII floor is taken on the ORIGINAL payload, so
  masking a secret can never LOWER a return's sensitivity (inv. 17 / D100-2);
* the **limits**, stated as passing tests: an opaque secret with no vendor prefix and no
  ``key=value`` shape goes through untouched. This is regex defence-in-depth behind the real
  barriers (Guard routing, sandbox, sensible-local), never a security frontier of its own.
"""

from __future__ import annotations

import os

from mnemosyne.guard import DeterministicGuard, redact
from mnemosyne.guard.redact import redact_sensitive_text
from mnemosyne.ingest import DeterministicClassifier
from mnemosyne.ports import (
    Bubble,
    DataEgress,
    Envelope,
    GovernanceLabel,
    Sensitivity,
    ToolBackend,
    ToolEffect,
    ToolManifest,
)
from mnemosyne.runtime.observability import LocalObservability
from mnemosyne.tools import ConfigToolCatalog, GovernedToolInvoker, LocalFunctionTool

_BUBBLE = Bubble("research")

_GITHUB_PAT = "ghp_AbCdEfGhIjKlMnOpQrStUv0123456789"
_ANTHROPIC_KEY = "sk-ant-api03-AbCdEfGh1234567890IjKlMnOpQrSt"


def _label(sensitivity: Sensitivity = Sensitivity.PUBLIC) -> GovernanceLabel:
    return GovernanceLabel(sensitivity=sensitivity, bubble=_BUBBLE)


def _armed_invoker(fn) -> GovernedToolInvoker:
    """An invoker whose Guard allow-lists one read-only local tool running ``fn``."""
    manifest = ToolManifest(
        name="reader",
        backend=ToolBackend.LOCAL_FUNCTION,
        io_schema="q:str -> out:str",
        permissions=("read",),
        egress=DataEgress.STAYS_LOCAL,
        effect=ToolEffect.READ_ONLY,
    )
    classifier = DeterministicClassifier()
    guard = DeterministicGuard(catalog=ConfigToolCatalog([manifest]), classifier=classifier)
    return GovernedToolInvoker(
        guard=guard,
        plugins={manifest.name: LocalFunctionTool(manifest, fn)},
        classifier=classifier,
    )


# --- the corpus itself: what it catches ---------------------------------------------------
def test_vendor_prefixes_and_credential_shapes_are_masked() -> None:
    assert _ANTHROPIC_KEY not in redact_sensitive_text(f"ANTHROPIC_API_KEY={_ANTHROPIC_KEY}")
    assert _GITHUB_PAT not in redact_sensitive_text(f"Authorization: Bearer {_GITHUB_PAT}")
    assert "AKIAIOSFODNN7EXAMPLE" not in redact_sensitive_text("id AKIAIOSFODNN7EXAMPLE")
    # a DB connection string keeps its host (operationally useful) but loses the password
    masked = redact_sensitive_text("postgres://user:hunter2@db.internal:5432/research")
    assert "hunter2" not in masked
    assert "db.internal" in masked


def test_ordinary_prose_is_not_mangled() -> None:
    """A redactor that eats normal text would be turned off within a week."""
    for benign in (
        "the Q4 report = a draft, nothing more",
        "SELECT * FROM prices WHERE country = 'ZW'",
        "https://example.com/docs?page=2&sort=asc",
    ):
        assert redact_sensitive_text(benign) == benign


# --- the hardening over upstream: there is no off switch ----------------------------------
def test_no_environment_variable_can_disable_redaction() -> None:
    """Upstream honours ``HERMES_REDACT_SECRETS``; we deleted the switch.

    Asserted two ways, because the behavioural half alone cannot fail (nothing reads the
    variable, so it tests the absence of absent code - audit NIT). The load-bearing half is
    structural: the module does not import ``os`` at all, so it CANNOT consult the
    environment. That assertion fails the day someone reintroduces an opt-out.
    """
    assert not hasattr(redact, "os")

    previous = os.environ.get("HERMES_REDACT_SECRETS")
    os.environ["HERMES_REDACT_SECRETS"] = "false"
    try:
        assert _GITHUB_PAT not in redact_sensitive_text(f"token {_GITHUB_PAT}")
    finally:
        if previous is None:
            os.environ.pop("HERMES_REDACT_SECRETS", None)
        else:
            os.environ["HERMES_REDACT_SECRETS"] = previous


# --- the honest limits, as passing tests --------------------------------------------------
def test_an_opaque_secret_with_no_prefix_and_no_key_shape_passes_through() -> None:
    """The documented blind spot. Stated as a test so it can never be quietly believed away.

    A high-entropy string that matches no vendor prefix and sits outside any ``key=value``
    shape is indistinguishable from a hash, an id, or a base64 blob. This is why the redactor
    is defence in depth and never the reason a secret is allowed near a boundary.
    """
    opaque = "Zx9Qw3Lm7Tk2Rv8Np4Hs6Yd1Bg5Fj0Ce"
    assert redact_sensitive_text(f"the value is {opaque}") == f"the value is {opaque}"


# --- wiring 1: the PUBLIC branch of the trace trail ---------------------------------------
def test_a_public_trace_masks_a_secret_but_keeps_operational_values() -> None:
    """Sensitivity redaction never covered this branch: ``public`` records values verbatim."""
    obs = LocalObservability()
    trace = obs.start_trace("research.fetch", _label(Sensitivity.PUBLIC))
    obs.event(trace, "model.call", cmd=f"curl -H 'Authorization: Bearer {_GITHUB_PAT}'", ok=True)

    line = obs.records()[-1]
    assert _GITHUB_PAT not in line
    assert "true" in line  # the operational field still travels - the log stays useful


def test_a_non_public_trace_is_unaffected_by_the_new_layer() -> None:
    """The pre-existing structural redaction still wins: keys travel, values do not."""
    obs = LocalObservability()
    trace = obs.start_trace("journal", _label(Sensitivity.SENSIBLE))
    obs.event(trace, "note", body="nothing secret, just intimate")

    line = obs.records()[-1]
    assert "intimate" not in line
    assert "body" in line


# --- wiring 2: the untrusted tool return --------------------------------------------------
def test_a_tool_return_is_masked_with_a_non_reusable_sentinel() -> None:
    """A head/tail mask still looks like a key; an agent could write it back and destroy it."""
    invoker = _armed_invoker(lambda call: f"config: api_key = {_GITHUB_PAT}")
    out = invoker.call("reader", Envelope(payload="cat config", label=_label()), subject=_BUBBLE)

    assert _GITHUB_PAT not in str(out.payload)
    assert "redacted" in str(out.payload)
    # the mask must not be a head/tail slice of the REAL token (that is the reusable-looking
    # shape); assert against this token's own prefix, not upstream's issue example.
    assert _GITHUB_PAT[:8] not in str(out.payload)


def test_masking_the_return_never_lowers_its_sensitivity() -> None:
    """The ordering invariant: floor on the ORIGINAL, redact after (inv. 17 / D100-2).

    This is not hypothetical - the two filters genuinely overlap on ONE shape, the E.164 phone
    number, which the redactor masks (``+336****5678``) and the PII floor reads as ``perso``.
    Measured on the wired classifier: ``floor("+33612345678") == PERSO`` but
    ``floor("+336****5678") == PUBLIC``. So redacting first would silently DECLASSIFY a tool
    return carrying a phone number, from ``perso`` to ``public`` - and in a bubble open to the
    internet, ``public`` is exactly what may leave. Hence: floor first, mask after.
    """
    invoker = _armed_invoker(lambda call: f"contact +33612345678, token {_GITHUB_PAT}")
    out = invoker.call("reader", Envelope(payload="cat", label=_label()), subject=_BUBBLE)

    assert out.label.sensitivity is Sensitivity.PERSO  # would be PUBLIC if masked before flooring
    assert "+33612345678" not in str(out.payload)
    assert _GITHUB_PAT not in str(out.payload)
