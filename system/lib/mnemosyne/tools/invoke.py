"""GovernedToolInvoker (D114-③ / D99 / D100) — the governed tool-call executor.

This is the CONSUMER the Guard's ``TOOL_CALL`` grant was waiting for. ③-1 minted a grant sealing the
routed channel + ``may_leave_machine`` (M1) but posed **no non-local consumer** to redeem it — the
egress-enforcement debt deferred to ③-5. The invoker closes that loop:

1. **Authorize + mint** — asks the Guard to ``grant`` the call. The Guard rules from the PROTECTED
   catalog (``_rule_tool_call``), never the caller's word (D100): an unlisted tool is denied, a
   life-action tool and a tool leaving the machine with non-public data escalate to a human gesture.
2. **Redeem** — ``guard.redeem(grant)`` authenticates + consumes the single-use token (M1). THIS is the
   non-local consumer: a forged / replayed grant is refused fail-closed, and a call the Guard did not
   clear never reaches the tool. Egress enforcement is now structural, not a dangling seal.
3. **Invoke** — the allow-listed plugin runs (whatever its back-end: local function, API, MCP server).
   A tool allow-listed but not wired is fail-closed — a missing plugin is a refusal, never a guess.
4. **Re-label the untrusted RETURN** — a tool result is UNTRUSTED data (D81 / D100-3): its own label is
   DISCARDED and a fresh one is minted in the caller's bubble at the MAXIMUM of (the inputs' floor, the
   raw content's PII floor) — like egress M2, the label can lie but the content cannot. The return can
   only RAISE prudence, never lower a barrier nor trigger an action alone (D101 / D100-2).

The Guard, catalog, and sandbox stay OUR glue; the plugins are the swap-able back-ends (③-5b). Code &
docstrings English (D117). Decisions: D114 (tool prise, Guard both-ends) · D89 / D100 (mediation,
non-derivation) · D101 (re-label by max) · D66 (sensible-local egress) · M1 (single-use grant).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ..guard.fencing import fence_recalled
from ..guard.redact import redact_sensitive_text
from ..ports import (
    Bubble,
    Classifier,
    Effect,
    Envelope,
    GovernanceLabel,
    Grant,
    Guard,
    GuardDenied,
    GuardRequest,
    Sensitivity,
    ToolManifest,
    ToolPlugin,
)


class GovernedToolInvoker:
    """Runs an allow-listed tool through the Guard at BOTH ends (D114-③) — the missing grant consumer.

    Holds the Guard (to grant + redeem), the wired plugins (name → :class:`ToolPlugin`), and an optional
    classifier to floor an untrusted string return. It reaches a tool NO other way — the single door
    (D55) through which a tool call is authorised, consumed, executed, and its result re-labelled."""

    __slots__ = ("_guard", "_plugins", "_classifier")

    def __init__(
        self,
        *,
        guard: Guard,
        plugins: Mapping[str, ToolPlugin] | None = None,
        classifier: Classifier | None = None,
    ) -> None:
        self._guard = guard
        # a private copy: the wired set cannot be mutated from outside after construction (D100).
        self._plugins: dict[str, ToolPlugin] = dict(plugins) if plugins is not None else {}
        self._classifier = classifier

    def call(
        self,
        tool: str,
        arguments: Envelope[object],
        *,
        subject: Bubble,
        inputs: tuple[GovernanceLabel, ...] = (),
    ) -> Envelope[object]:
        """Authorise, redeem, invoke, and re-label the return — the whole governed round-trip.

        ``inputs`` are the labels of every datum the call involves (what the Guard rules on); it
        defaults to the arguments' own label. Raises :class:`~mnemosyne.ports.core.GuardDenied` for an
        unlisted / unwired tool or a forged grant, and :class:`~mnemosyne.ports.core.EscalateToHuman`
        when a human gesture is required first (a life-action, or non-public data leaving the machine —
        canal B). The returned envelope is UNTRUSTED, re-floored by the maximum (D101 / D100)."""
        effective_inputs = inputs if inputs else (arguments.label,)
        request = GuardRequest(
            effect=Effect.TOOL_CALL,
            subject=subject,
            inputs=effective_inputs,
            target=tool,
            descriptor=f"tool call {tool!r}",
            # M2 (audit ③-5a): the raw arguments are what a LEAVES_EXTERNAL tool sends out, so hand the
            # Guard the string content to re-floor — the label can lie, the content cannot. A non-str
            # payload is left None → the Guard floors it fail-safe SENSIBLE (unreadable content that
            # leaves the machine needs a canal-B gesture, never a silent auto-leak). Never logged (inv.22).
            payload=arguments.payload if isinstance(arguments.payload, str) else None,
        )
        grant = self._guard.grant(request)  # deny → GuardDenied; human gesture → EscalateToHuman
        self._guard.redeem(
            grant
        )  # M1 — the non-local consumer: authenticate + spend the single-use seal
        plugin = self._plugins.get(tool)
        if plugin is None:
            # the Guard allow-listed it, but no back-end is wired — fail-closed, never a guess (D73 / D126).
            raise GuardDenied(
                f"tool {tool!r} is allow-listed but not wired to a plugin — refused fail-closed "
                "(the real back-ends land in ③-5b)"
            )
        result = plugin.invoke(arguments, grant=grant)
        return self._relabel_untrusted(result.payload, subject=subject, inputs=effective_inputs)

    def _relabel_untrusted(
        self, payload: object, *, subject: Bubble, inputs: tuple[GovernanceLabel, ...]
    ) -> Envelope[object]:
        """Wrap an untrusted tool return in a FRESH label minted in ``subject`` (D100-3 / D101).

        The plugin's own returned label is never trusted: the sensitivity is the MAX of the inputs'
        floor and the raw content's deterministic PII floor (M2 — content cannot lie down), so a tool
        can neither launder ``sensible`` output as ``public`` nor act by relabelling. The domains carry
        forward from the inputs (taint kept). The label is minted in the CALLER's bubble (``subject``),
        exactly like the Guard's released label (``_released_label``): the return belongs to the bubble
        that made the call — this is not a cross-bubble read (the tool computed on caller-supplied
        arguments, never reading another bubble's store; a back-end that WOULD read a store stays
        Guard-mediated at that read, ③-5b).

        The returned STRING is additionally secret-redacted (D154) before it travels: a tool that
        cats a config, echoes its environment or dumps an HTTP request hands the agent whatever
        credentials the machine had lying around, and from here that text flows into prompts,
        traces and memory. Secrets reach a back-end through the broker's grant, never through a
        tool's return value, so no ACCESS is lost by masking. Fidelity, however, is: the vendor
        prefixes are greedy, so a benign token that merely starts like one is eaten with the rest
        of its word — measured, ``"reference sk-2024-quarterly-report"`` comes back as
        ``"reference «redacted:sk-…»"``, and a phone number in a passage is masked too. Accepted:
        no consumer parses this text (``search_memory`` is the only sanctioned tool, and every
        caller hands the payload to a model), so the cost is a rare mangled word rather than a
        broken flow. The mask is the NON-REUSABLE sentinel (``file_read=True``): a head/tail mask
        still looks like a real key, and an agent that reads one and writes it back silently
        destroys the stored credential.

        Finally the text is FENCED (D154): a tool return is untrusted data by definition, and
        it lands verbatim in a model's context, so it is wrapped and annotated as material to
        reason about rather than instructions to follow. It applies to every tool, not just
        recall — a fetcher bringing back a web page needs it at least as much.

        ORDER MATTERS, and this exact sequence is what two audits converged on —
        **floor(raw) → redact(raw) → fence**:

        * *Floor before redact.* Flooring cleaned text could only LOWER sensitivity, the
          downgrade monotonic prudence forbids (invariant 17 / D100-2). Real case: the phone
          pattern reads ``+33612345678`` as ``perso`` but its masked form as ``public``.
        * *Floor before sanitise.* Sanitising used to happen inside the recall tool, i.e.
          UPSTREAM of this floor — so a document could splice its own PII across a forged tag
          and have it slip past (``+336123456</recalled>78ABCDEF``). **Honest status of this
          one: it is a belt, and the braces are elsewhere.** Since the sanitiser now swaps a
          tag for a SPACE instead of deleting it, the same payloads floor correctly even with
          the old ordering — an auditor moved the fence back above the floor and no test fell,
          and hunted for a payload where the order still decides the verdict without finding
          one (``<``, ``>`` and space are all non-word characters, so ``\\b`` behaves the same).
          So the ordering is currently REDUNDANT with the substitution rather than load-bearing.
          Both are kept because they fail differently: the substitution protects against
          adjacency tricks, the ordering protects against any future transformation that goes
          back to removing things. Neither is trusted to be the only one.
        * *Fence LAST.* When the tool fenced its own output, this redaction then ran over the
          finished block — and ``Authorization:`` followed by ``</recalled>`` made the
          redactor mask the CLOSING TAG as if it were a credential. The fence never closed,
          which silently declares everything after it in the prompt (including the operator's
          own turn) to be untrusted recalled data. The redactor must never see a structured block.

        Two residues this ordering CREATES, named rather than discovered later:

        * **A secret split by a forged tag escapes the redactor.** Redaction now runs on the raw
          text, so ``ghp_AbCdEfGh</recalled>IjKlMnOpQrStUv0123456789`` presents two halves too
          short to match; the sanitiser then rejoins them with a space, and the model reads the
          key one space away from usable. It WAS masked under the old ordering. Accepted: the
          alternative reopens BLOQUANT-B, which needs no attacker at all — and a secret is only
          ever meant to reach a back-end through the broker's grant, never through tool text.
        * **Non-string returns bypass both layers.** The ``isinstance`` guard below means a
          ``dict`` or ``list`` is neither redacted nor fenced. The floor still treats it
          fail-safe ``sensible`` (unreadable content cannot be cleared), so nothing leaks past
          the Guard — but the content reaches the model unfenced once stringified downstream.
          Fine while ``search_memory`` is the only sanctioned tool; revisit when a fetcher that
          returns structured JSON is wired.
        """
        input_floor = max((label.sensitivity for label in inputs), default=Sensitivity.SENSIBLE)
        content_floor = self._content_floor(payload)
        sensitivity = max(input_floor, content_floor)
        domains = frozenset().union(*(label.domains for label in inputs)) if inputs else frozenset()
        label = GovernanceLabel(sensitivity=sensitivity, bubble=subject, domains=domains)
        if isinstance(payload, str):
            payload = fence_recalled(redact_sensitive_text(payload, file_read=True))
        return Envelope(payload=payload, label=label)

    def _content_floor(self, payload: object) -> Sensitivity:
        """Deterministic PII floor of an untrusted return (M2). A non-string payload or no classifier
        wired is fail-safe ``SENSIBLE`` — the Guard never lets out content it could not read (D100)."""
        if self._classifier is None or not isinstance(payload, str):
            return Sensitivity.SENSIBLE
        return self._classifier.floor(payload)


class LocalFunctionTool:
    """A minimal in-process :class:`ToolPlugin` (the ``LOCAL_FUNCTION`` back-end, D114-①).

    Wraps a pure Python callable ``fn(arguments) -> object``; the invoker re-labels whatever it returns
    as untrusted (D100), so ``fn`` need not (and must not be trusted to) label its own output. This is
    the couture's exercised stub — the real code-executing local tool (which runs under the
    :class:`~mnemosyne.ports.sandbox.Sandbox`, D99) and the API / MCP back-ends land in ③-5b. It acts
    only on a grant the invoker already redeemed (deny-by-default)."""

    __slots__ = ("manifest", "_fn")

    def __init__(self, manifest: ToolManifest, fn: Callable[[Envelope[object]], object]) -> None:
        self.manifest = manifest
        self._fn = fn

    def invoke(self, call: Envelope[object], *, grant: Grant) -> Envelope[object]:
        """Run the wrapped callable. The returned envelope's label is provisional — the invoker
        discards it and re-floors the payload (D100-3), so it carries only the raw result."""
        return Envelope(payload=self._fn(call), label=call.label)
