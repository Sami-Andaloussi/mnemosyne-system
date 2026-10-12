"""Frontier vision caption adapter (sujet G / niveau 3) — a CLOUD VLM behind the ImageCaptioner port,
reachable ONLY through a canal-B human gesture (D90).

The local vector extraction (sujet E) and the local 7B VLM (:mod:`.caption_mlx`) fill most figure holes,
but both FAIL on abstract charts (a line/scatter the 7B captions as "La" — the degenerate fizzle
:func:`~mnemosyne.ingest.caption.is_degenerate_caption` catches). Niveau 3 sends exactly those figures to a
frontier model (Claude Haiku vision). Sending a book figure to a third-party cloud is an EGRESS — the very
thing invariant 1 forbids AUTOMATICALLY — so this adapter is the opposite of :mod:`.caption_mlx` in one
respect and identical in every other:

* **Guard-mediated, never automatic (the whole point).** :meth:`AnthropicVisionCaptioner.caption` asks the
  Guard for an ``EXTERNAL_OUTPUT`` grant BEFORE a single byte leaves. A figure is raster bytes → the Guard's
  content floor cannot read it → fail-closed ``SENSIBLE`` (M2): the flow leaves ONLY on the canal-B human
  gesture this captioner was constructed with (the workstream-G extension of ``_rule_egress``). No gesture, or
  a host not on the allow-list ⇒ ``grant`` fails closed and NOTHING is sent — the barrier is the Guard, not
  this adapter's good behaviour (D100). The gesture itself is posed by trusted runtime code after the
  operator confirms the batch, never derived from the (untrusted) figure.
* **Sole-importer + brick-free (invariant 20 / D103 / D126).** The ``anthropic`` SDK is imported LAZILY, in
  :func:`connect_anthropic_vision` only, so the module (and its testable core) import with no SDK installed.
  The core talks to a narrow :class:`_VisionBackend`, so the mediation logic is proven against a stub with a
  REAL Guard; the SDK translation is ``# pragma: no cover`` (confronted at the ③ smoke, like the MLX seam).
* **Model-generated, marked, fail-open (D85 / D100).** The caption is an INTERPRETATION — woven in with
  :data:`~mnemosyne.provenance.FIGURE_CLOUD_MARK` (sujet G2), stripped from the verbatim floor like any
  inserted line. ANY failure (a refused grant, an API error) returns ``""`` so the placeholder simply stays
  and no book is ever lost to a caption failure.

We deliberately send ONLY the figure bytes + a FIXED public prompt — never the surrounding book ``context``
(that text could be ``perso``): minimising what leaves is cheaper than re-flooring it (M2). The API key
belongs to the operator, read from the environment by the SDK adapter (an [OPERATOR] gesture), never handled
by Mnemosyne code.

Decisions: D90 (canal-B human gesture) · invariant 1 / D66 (no AUTOMATIC cloud for non-public) · D100 (Guard
is the barrier, zero-trust) · D103 / invariant 20 (sole importer) · D126 (brick-free suite) · D85 (per-figure
fail-open) · D117 (English code, French caption). Code & docstrings English; the prompt asks for French.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ports import (
    Bubble,
    Effect,
    EscalateToHuman,
    GovernanceLabel,
    Guard,
    GuardDenied,
    GuardRequest,
    HumanTier,
    ImageCaptioner,
    Sensitivity,
)

#: Frozen default frontier VLM — Claude Haiku vision (fast + cheap, enough for a figure read-out). A one-line
#: swap; carried into the caption's provenance so a model change is traceable (mirrors :attr:`ImageCaptioner.model_id`).
_DEFAULT_MODEL = "claude-haiku-4-5"

#: The one egress host this captioner may reach. It must ALSO be on the protected policy allow-list
#: ([OPERATOR] POLICY_WRITE) — declaring it here is not enough, the Guard denies an un-listed host (the two
#: barriers, D90).
_HOST = "api.anthropic.com"

#: The captioning instruction — the SINGLE source of the frontier prompt (anti-drift). Unlike the 4-bit local
#: VLM (:mod:`.caption_mlx`, which regurgitates a listy prompt), a frontier model follows a richer, conditional
#: ask — so this one may name what to report AND carry an "illegible ⇒ empty" clause. Strictly factual,
#: anti-hallucination. French output — the caption lands in the operator's French .md files (D117 product).
_PROMPT = (
    "Décris cette figure de livre en 1 à 3 phrases, en français. Reste strictement factuel : rapporte ce "
    "qui est réellement visible (type de graphique, axes, courbes/barres, tendance, légendes lisibles) et "
    "n'invente aucune donnée. Si la figure est illisible ou vide, réponds par une chaîne vide."
)


def _clean_caption(text: str) -> str:
    """Collapse a frontier caption to one tidy line (a marked caption is a single blockquote line downstream).

    No chat-token stripping (a frontier model does not dribble ``<|im_end|>`` like the 4-bit local VLM); just a
    whitespace collapse + strip so the woven line stays clean. Content-agnostic — never edits the wording."""
    return " ".join(text.split()).strip()


@runtime_checkable
class _VisionBackend(Protocol):
    """The narrow seam to the frontier model — ``describe(figure bytes, prompt) -> caption`` — so the
    Guard-mediation core is testable against a stub with NO SDK (D126). The real adapter is the sole importer
    of ``anthropic`` (:class:`_AnthropicVisionBackend`); a stub returns a canned string."""

    def describe(self, image: bytes, prompt: str) -> str:
        """Return the model's raw description of ONE figure. May raise — the caller fails open (D85)."""
        ...


class AnthropicVisionCaptioner:
    """Guard-mediated frontier :class:`ImageCaptioner` (niveau 3): describe ONE figure via a cloud VLM, but
    ONLY through a canal-B human gesture (D90). This is NOT an automatic-local captioner — its exception to
    invariant 1 rests entirely on the Guard: :meth:`caption` obtains an ``EXTERNAL_OUTPUT`` grant (which the
    workstream-G ``_rule_egress`` clears only for a gesture, to an allow-listed host) BEFORE any byte leaves,
    and returns ``""`` fail-CLOSED if the Guard refuses — so a mis-wired call (no gesture) sends nothing.

    Constructed with the gesture the run holds after the operator confirmed the batch; per-figure FAIL-OPEN
    (D85)."""

    __slots__ = ("_guard", "_subject", "_backend", "_gesture", "_model_id", "_host", "_label")

    def __init__(
        self,
        *,
        guard: Guard,
        subject: Bubble,
        backend: _VisionBackend,
        human_gesture: HumanTier | None = None,
        model_id: str = _DEFAULT_MODEL,
        host: str = _HOST,
        label: GovernanceLabel | None = None,
    ) -> None:
        self._guard = guard
        self._subject = subject
        self._backend = backend
        # the canal-B gesture that authorises THIS run's egress (D90). None (the default) ⇒ no gesture ⇒ the
        # Guard escalates every figure and nothing leaves — a captioner built without a confirmed batch is
        # structurally inert, not a silent leak.
        self._gesture = human_gesture
        self._model_id = model_id
        self._host = host
        # the label the outbound flow wears. Fail-safe SENSIBLE (invariant 23): a book figure is non-public,
        # and the content floor forces SENSIBLE anyway (bytes are unreadable, M2) — so the gesture is always
        # required, whatever the caller passes.
        self._label = (
            label
            if label is not None
            else GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=subject)
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    def caption(self, image: bytes, *, context: str = "") -> str:
        """Describe ONE figure via the frontier — Guard-mediated, fail-open (D85 / D100).

        ``context`` is accepted for the :class:`ImageCaptioner` contract but DELIBERATELY NOT sent: only the
        figure bytes + the fixed public :data:`_PROMPT` leave, minimising the flow (surrounding book text
        could be ``perso``). Returns ``""`` when the Guard refuses the egress (no gesture / host not
        allow-listed) OR the API call fails — so a figure that cannot be described just stays a placeholder."""
        request = GuardRequest(
            effect=Effect.EXTERNAL_OUTPUT,
            subject=self._subject,
            inputs=(self._label,),
            target=self._host,
            descriptor=f"describe a book figure via {self._model_id}",
            # bytes ⇒ unreadable content ⇒ fail-closed SENSIBLE at the floor (M2); gesture-gated. The port's
            # payload type is `str | bytes | None`, so the image's binary type ITSELF carries "non-public"
            # (no type: ignore, no way to mislabel it public). repr-hidden, so it never surfaces in a log (inv22).
            payload=image,
            human_gesture=self._gesture,
        )
        try:
            grant = self._guard.grant(
                request
            )  # deny (host) → GuardDenied; no gesture → EscalateToHuman
            self._guard.redeem(grant)  # M1 — authenticate + spend the single-use egress seal
        except (GuardDenied, EscalateToHuman):
            return (
                ""  # the Guard refused the egress → NOTHING leaves; the figure stays a placeholder
            )
        # NB: a ResourceBoundError (a quota/cycle BREACH, invariant 7) is deliberately NOT caught here — it
        # must PROPAGATE (a bound breach is a systemic stop, not a per-figure failure: swallowing it would
        # keep hammering the API past a blown quota). The campaign's per-book net isolates it (D140).
        try:
            raw = self._backend.describe(image, _PROMPT)
        except Exception:  # noqa: BLE001 - fail-open per figure (D85): an API error never aborts the book
            return ""
        return _clean_caption(raw)


def _media_type(
    image: bytes,
) -> str:  # pragma: no cover - trivial sniffing, exercised at the ③ smoke
    """Best-effort media type from the figure's magic bytes (the SDK needs it for a base64 image block)."""
    if image.startswith(b"\x89PNG"):
        return "image/png"
    if image.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"  # a Docling figure is a PNG by default; a safe fallback


class _AnthropicVisionBackend:  # pragma: no cover - real Anthropic SDK translation (③ ignition, smoke-tested)
    """Thin translation from :class:`_VisionBackend` to the Anthropic Messages API (sole importer, D103).

    Holds an injected client (so this class never imports ``anthropic`` at module scope). ``describe`` sends
    ONE base64 image block + the prompt and joins the text blocks of the reply. Best-guess call shape until
    the ③ smoke confronts it ([OPERATOR]) — F3 honesty, not invented certainty."""

    __slots__ = ("_client", "_model", "_max_tokens")

    def __init__(self, client: object, model: str, max_tokens: int = 300) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def describe(self, image: bytes, prompt: str) -> str:
        import base64

        b64 = base64.standard_b64encode(image).decode("ascii")
        message = self._client.messages.create(  # type: ignore[attr-defined]
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": _media_type(image),
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        blocks = getattr(message, "content", []) or []
        return "".join(getattr(block, "text", "") for block in blocks)


def connect_anthropic_vision(
    *,
    guard: Guard,
    subject: Bubble,
    human_gesture: HumanTier | None = None,
    model: str = _DEFAULT_MODEL,
    api_key_env: str = "ANTHROPIC_API_KEY",
    label: GovernanceLabel | None = None,
) -> ImageCaptioner:  # pragma: no cover - needs the brick + the operator's key (③ ignition)
    """Wire a frontier :class:`ImageCaptioner` (the niveau-3 seam, sujet G).

    Imports ``anthropic`` LAZILY — the SOLE import of the brick (D103 / invariant 20) — so the module stays
    import-safe without it (D126). Reads the operator's key from ``api_key_env`` and fails LOUD if it is
    absent (a silent no-key would look like a systemic caption failure, F3): the key is an [OPERATOR]
    gesture, never a repo secret, and the SDK holds it — Mnemosyne code never touches the value. The returned
    captioner mediates every figure through ``guard`` under ``human_gesture`` (D90); pass the gesture ONLY
    after the operator confirms the batch."""
    import os

    from anthropic import Anthropic  # the SOLE import of the brick (D103 / invariant 20)

    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"{api_key_env} not set — the frontier vision seam needs the operator's API key ([OPERATOR] "
            "gesture, never a repo secret). Export it before enabling niveau 3."
        )
    backend = _AnthropicVisionBackend(Anthropic(api_key=api_key), model)
    return AnthropicVisionCaptioner(
        guard=guard,
        subject=subject,
        backend=backend,
        human_gesture=human_gesture,
        model_id=model,
        label=label,
    )
