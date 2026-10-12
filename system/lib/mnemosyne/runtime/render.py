"""GovernedRenderer (D66 / D89 / D100 / D108) — the governed document-output consumer.

Producing a shareable document is the **MIRROR of ingestion** and a NEW egress surface. This is the
consumer that stands in front of the :class:`~mnemosyne.ports.renderer.Renderer` brick so a ``sensible``
datum never becomes a portable artifact that LEAVES the machine without clearance:

* a **LOCAL** render (a file on the operator's own machine) is interior persistence — the local-only repo
  already versions the ``sensible`` (D71) — so any label renders, no egress grant, only traced; the
  Guard mediates FRONTIERS, not the interior (D89). Rendering locally first bypasses nothing: a later
  attempt to SHARE the artifact is itself egress-governed.
* a **SHAREABLE** render is EGRESS: it routes through the Guard as ``EXTERNAL_OUTPUT``, so the same
  barrier as any leak applies — the destination must be allow-listed (inv. 21) and the content must
  floor ``public`` by label AND by a deterministic re-read of the raw body (M2 — the label can lie, the
  content cannot). Non-public content escalates to a canal-B human gesture (D66 / D90), never an
  automatic leak; the single-use grant is redeemed here (M1, the non-local consumer).

**Redaction is STRUCTURAL, not trust (D100).** If a redactor is wired and asked for, the body is
redacted and then RE-CLASSIFIED — it is emitted as public only if the deterministic floor now agrees;
a redactor that under-cleans leaves the floor non-public, so the Guard still escalates. Absent a
redactor, non-public shareable content simply escalates (fail-closed). The concrete redactor (Presidio)
lands at ③-6b; this couture proves the barrier with the floor as the sole arbiter.

Decisions: D66 (routing) · D89 / D100 (mediation, non-derivation) · D101 (deterministic floor) · D108
(output contract) · D71 (local persistence) · M1 (single-use grant) · M2 (content re-floor). Invariants
carried: 21 (egress allow-list), 22 (payload never logged), 24. Code & docstrings English (D117).
"""

from __future__ import annotations

from ..ports import (
    Bubble,
    Classifier,
    Effect,
    Envelope,
    ErrorCode,
    GovernanceLabel,
    Guard,
    GuardRequest,
    MnemosyneError,
    Observability,
    Redactor,
    RenderDestination,
    RenderRequest,
    RenderResult,
)
from ..ports.renderer import Renderer


class RenderUnavailable(MnemosyneError):
    """No rendering engine is wired — output refused fail-closed (never a fabricated artifact, D111)."""

    code = ErrorCode.UNAVAILABLE


class MalformedRender(MnemosyneError):
    """A render was asked on a body that is not a source string (D108-① — caught at the source)."""

    code = ErrorCode.MALFORMED


class RefusingRenderer:
    """The fail-closed default :class:`~mnemosyne.ports.renderer.Renderer` (D99 / D111 / D126).

    With no engine wired, a render is REFUSED — never a fabricated or empty artifact passed off as a
    document. The real Typst engine is injected by :func:`~mnemosyne.runtime.bootstrap.real_runtime` at
    ③-6b; until then output degrades to a normalized :class:`RenderUnavailable`, exactly as
    :class:`~mnemosyne.tools.sandbox.RefusingSandbox` refuses an unconfined run."""

    def render(self, request: RenderRequest) -> RenderResult:
        raise RenderUnavailable(
            f"no rendering engine wired for {request.fmt!r} — output refused fail-closed "
            "(the Typst brick lands at ③-6b)"
        )


class GovernedRenderer:
    """Governs a document render so a ``sensible`` datum never becomes a portable artifact that LEAVES
    the machine without clearance — the output mirror of the ingestion floor (D66 / D89 / D100).

    Holds the rendering engine (the brick), the Guard (to grant + redeem a SHAREABLE render), a
    classifier (the deterministic re-read behind redaction, M2 / D101), an optional redactor (③-6b), and
    an optional observability sink. It reaches the engine NO other way — the single door (D55) through
    which content is cleared, redacted if asked, rendered, and returned governed."""

    __slots__ = ("_renderer", "_guard", "_classifier", "_redactor", "_obs")

    def __init__(
        self,
        *,
        renderer: Renderer,
        guard: Guard,
        classifier: Classifier | None = None,
        redactor: Redactor | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._renderer = renderer
        self._guard = guard
        self._classifier = classifier
        self._redactor = redactor
        self._obs = observability

    def render(
        self,
        content: Envelope[object],
        *,
        fmt: str,
        subject: Bubble,
        destination: RenderDestination = RenderDestination.SHAREABLE,
        target: str | None = None,
        title: str = "",
        redact: bool = False,
    ) -> Envelope[bytes]:
        """Clear, (optionally) redact, render, and return the governed artifact.

        ``destination`` defaults to ``SHAREABLE`` — the fail-safe stricter path: a caller who forgets to
        say LOCAL is governed as egress, never the reverse. A LOCAL render emits any label (interior,
        D71). A SHAREABLE render raises :class:`~mnemosyne.ports.core.GuardDenied` for an unlisted target
        and :class:`~mnemosyne.ports.core.EscalateToHuman` when non-public content needs a canal-B
        gesture (D66 / D90). Raises :class:`MalformedRender` if the body is not a source string."""
        body = content.payload
        if not isinstance(body, str):
            raise MalformedRender(
                "render body is not a source string — malformed output caught at the source (D108-①)"
            )

        if destination is RenderDestination.LOCAL:
            # interior persistence (D71): any label renders on the operator's own machine, no egress grant. A
            # later attempt to SHARE the artifact is itself egress-governed, so nothing is bypassed here.
            self._trace("render.local", content.label, fmt=fmt)
            result = self._renderer.render(RenderRequest(body=body, fmt=fmt, title=title))
            return Envelope(payload=result.artifact, label=content.label)

        # SHAREABLE → egress. Optionally redact to a public-safe body first (structural, re-classified).
        emit_body, emit_label = body, content.label
        if redact:
            emit_body, emit_label = self._redact_to_public(body, content.label)

        request = GuardRequest(
            effect=Effect.EXTERNAL_OUTPUT,
            subject=subject,
            inputs=(emit_label,),
            target=target,
            descriptor=f"render {fmt!r} document to {target!r}",
            # M2 — hand the Guard the RAW body that would leave so it re-floors the content, not just the
            # label (the label can under-state what leaves). Repr-hidden on GuardRequest → never logged.
            payload=emit_body,
        )
        grant = self._guard.grant(request)  # deny → GuardDenied; non-public → EscalateToHuman
        self._guard.redeem(
            grant
        )  # M1 — the non-local consumer: authenticate + spend the single-use seal
        self._trace("render.share", grant.released_label, fmt=fmt, target=target or "")
        result = self._renderer.render(RenderRequest(body=emit_body, fmt=fmt, title=title))
        # the artifact wears the Guard's released label (public once cleared, never the caller's word).
        return Envelope(payload=result.artifact, label=grant.released_label)

    def _redact_to_public(self, body: str, label: GovernanceLabel) -> tuple[str, GovernanceLabel]:
        """Redact ``body`` then RE-CLASSIFY — the barrier is the deterministic floor, not the redactor
        (D100). No redactor / no classifier wired ⇒ the body is unchanged and keeps its (non-public)
        label, so the Guard escalates (fail-closed). A redactor that under-cleans — or one that returns a
        non-string at all (a broken brick, D100 — never trust its output SHAPE) — leaves the original
        non-public label → still escalates; only a genuinely public-floored result may leave as public.
        Taint persists (the domains are carried forward); only the sensitivity is re-derived."""
        if self._redactor is None or self._classifier is None:
            return body, label
        redacted = self._redactor.redact(body)
        if not isinstance(redacted, str):
            # a redactor that did not return a string cannot be re-classified — treat it exactly like no
            # redactor: keep the non-public label so the Guard escalates (audit ③-6 M1 / D100 / D108-②).
            return body, label
        floor = self._classifier.floor(
            redacted
        )  # did redaction actually clean it? pure code, no model
        return redacted, GovernanceLabel(
            sensitivity=floor, bubble=label.bubble, domains=label.domains
        )

    def _trace(self, name: str, label: GovernanceLabel, **fields: object) -> None:
        """Record one output event (metadata only — the obs sink redacts values under a non-public
        trace, so no ``sensible`` content reaches the greppable log, inv. 12 / 22)."""
        if self._obs is None:
            return
        trace = self._obs.start_trace(name, label)
        self._obs.event(trace, name, **fields)
