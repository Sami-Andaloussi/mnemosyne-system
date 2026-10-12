"""LocalRunner (D104, invariants 27 / 12) — grammar-bound local execution behind the Guard.

Runs a local model only on a Guard-minted :class:`~mnemosyne.ports.guard.Grant` (D89): no
grant, no call; a grant for another effect — or a forged one, when a Guard is wired to verify
its token (M1) — is refused. Realizes the
:class:`~mnemosyne.ports.runner.Runner` port with two structural barriers:

* **Grammar-constrained output is STANDARD (invariant 27 / D104 / D100).** A structured /
  tool-calling completion is decoded UNDER a grammar, so emitting a malformed tool call or
  JSON is *structurally impossible*: :func:`enforce_grammar` is the decoder barrier — every
  structured output passes through it and a non-conforming candidate RAISES
  :class:`MalformedOutput` (code ``MALFORMED``) instead of being emitted. The safety is in
  the decoder, not in trusting the model.
* **Replayable + clean (invariant 12 / D76-①).** Every call captures a replay snapshot into
  the protected store (the full ``sensible`` input/output) and emits a redacted trace event
  to observability (no ``sensible`` in the greppable log).

Output monotonicity (invariant 17): the result envelope is at least as restrictive as the
prompt — ``prompt.label.raised_to(grant.released_label.sensitivity)``, never lower.

Decoding is a SEAM (③-2c): :class:`LocalRunner` hosts the barriers and decodes through an
injected :class:`GenerationBackend`, defaulting to the weightless :class:`_StubDecoder` (like
``StubEmbedder``) and swapping in the real MLX brick behind the SAME seam at ③ (D104 / D126) —
so the *barriers* are real and testable before any model is installed. Code & docstrings English
(D117); ``public`` / ``perso`` / ``sensible`` keep their French tokens (D33 / D66).

Decisions: D104 (runner, grammar standard, tool-calling gate) · D89 (behind the Guard) ·
D100 (structural safety) · D76-① (replay snapshot) · D111 (clean trace). Invariants
carried: 27, 12 (substrate of 5, 16, 11).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..ports import (
    Effect,
    Envelope,
    ErrorCode,
    GrammarConstraint,
    Grant,
    Guard,
    GuardDenied,
    MnemosyneError,
    ResourceBoundError,
)
from .observability import LocalObservability
from .snapshots import SnapshotStore

if TYPE_CHECKING:
    from .backend_registry import BackendRegistry

#: Model id of the stub decoder (real MLX / llama.cpp backends plug in behind this at ③).
_STUB_MODEL_ID = "stub-runner-v0"

#: The largest prompt (content + schema, in characters) the runner will feed a model — a fail-CLOSED
#: ceiling, the structural close of the "unbounded content → model" class (D136). A whole document
#: overflows the model's context window (the Étape-3 pilot hit 208k tokens > the model's ~131k, hours
#: per doc): a single call must NEVER exceed what the model can read. The runner RAISES
#: ``ResourceBoundError`` (invariant 16 / D78) rather than TRUNCATING, because the salient part — a
#: question, the newest turn, an instruction — usually sits at the END, so a silent head-truncation
#: would answer confidently from the WRONG half (D100: refuse, never silently degrade). Legitimate
#: callers stay under it by construction (the bounded classifier sample, packed recall passages, a
#: compacted history). Characters, not tokens, to stay tokenizer-free (as the chunker, D135) — but the
#: chars↔tokens ratio is LANGUAGE-bound (~4:1 Latin, down to ~1:1 for CJK), so this default is
#: Latin-calibrated (~12-16k tokens, ~6× the 8k classifier sample) and NOT universally safe: ③ sets
#: the real ceiling per installed model + corpus via ``policy.bounds['max_prompt_chars']`` — the D78
#: named place read by bootstrap (no code change). The fixed chat-template overhead the backend adds
#: is small and absorbed by this conservative margin.
_MAX_PROMPT_CHARS = 48_000


class MalformedOutput(MnemosyneError):
    """A candidate violated its grammar / schema (invariant 27, D104 / D108-①).

    Raised by :func:`enforce_grammar` when output does not conform — so a malformed tool
    call is never *emitted*, only refused (the decoder is the barrier, D100-1)."""

    code = ErrorCode.MALFORMED


def enforce_grammar(candidate: str, constraint: GrammarConstraint) -> str:
    """The decoder barrier (invariant 27): return a grammar-valid output, or raise
    :class:`MalformedOutput` — and NOTHING ELSE, whatever the schema contains.

    A grammar-constrained decoder (Outlines / XGrammar, D104) cannot *emit* a token that
    breaks the grammar; this function models that guarantee for the stub — a non-conforming
    candidate raises :class:`MalformedOutput` rather than passing through. For
    ``kind="json_schema"`` it checks the output parses as a JSON object and carries every
    ``required`` property at its declared type; for ``kind="gbnf"`` it checks the output is
    non-empty (a full grammar engine lands with the real runner at ③).

    If ``constraint`` carries a ``repair`` (opt-in — see :class:`GrammarConstraint`), a
    candidate that fails to PARSE is repaired then RE-VALIDATED against the same schema before
    being accepted: the "valid or raise" guarantee is untouched (a repaired-but-still-
    nonconforming candidate raises), only a near-miss is recovered (D100 / D85).

    **The outer net is the barrier's own contract, structurally (D100 / invariant 17).** A
    barrier that escapes by an exception of ANOTHER family does not fail closed — it
    *disappears*: the caller catches ``MalformedOutput`` (the documented contract), so a
    ``TypeError`` from inside the validator sails straight past it and what the barrier
    protected falls through to code never written for that case. That is not a limitation, it
    is a hole where a wall was drawn. This happened for real: a standard JSON-Schema union
    (``{"type": ["integer", "null"]}``) made the type lookup raise ``TypeError: unhashable
    type: 'list'`` on a PERFECTLY VALID output — and it was one representative of a class
    (schema not an object, ``properties`` not a dict, ``required`` not a list, an unreadable
    ``type``). So the class is closed by an INCAPACITY, not by patching its members: any
    non-``MalformedOutput`` exception raised while judging is translated into a fail-closed
    refusal, chained (``from exc``) and naming the original type + message so nothing is
    masked. The specific shapes are ALSO handled below, so a legitimate schema gets a
    legitimate verdict rather than a blanket refusal — the net catches what nobody foresaw."""
    try:
        if constraint.kind == "json_schema":
            return _enforce_json_schema(candidate, constraint.schema, constraint.repair)
        if not candidate:
            raise MalformedOutput("empty output under a grammar constraint (invariant 27)")
        return candidate
    except MalformedOutput:
        raise  # already the contract's refusal — pass it through untouched
    except Exception as exc:  # noqa: BLE001 - deliberate: the barrier may NEVER escape its contract
        raise MalformedOutput(
            "the grammar barrier could not certify this output — refusing fail-closed "
            f"({type(exc).__name__}: {exc}) (invariant 27 / D100)"
        ) from exc


def _enforce_json_schema(
    candidate: str, schema_text: str, repair: Callable[[str], str] | None = None
) -> str:
    # The schema is NOT always ours: it arrives from a caller (``make local-run SCHEMA=…``, a
    # project's bench), so "a constant, always valid JSON" was an assumption, not a fact. An
    # unusable schema means the barrier cannot CERTIFY the output ⇒ it refuses (fail-closed),
    # rather than crashing outside its contract or waving the output through unjudged.
    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError as exc:
        raise MalformedOutput(
            f"the grammar constraint's schema is not valid JSON, nothing can be certified against "
            f"it: {exc} (invariant 27 / D100)"
        ) from exc
    if not isinstance(schema, dict):
        raise MalformedOutput(
            f"the grammar constraint's schema must be a JSON object, got "
            f"{type(schema).__name__} (invariant 27)"
        )
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        if repair is None:
            raise MalformedOutput(f"output is not valid JSON under its schema: {exc}") from exc
        # A near-miss (e.g. an unterminated string on a quoted verbatim passage): repair
        # DETERMINISTICALLY, then fall through to the SAME shape checks — the repaired candidate
        # earns no exemption (D100). If it still does not parse, refuse fail-closed.
        try:
            candidate = repair(candidate)
            value = json.loads(candidate)
        except Exception as exc2:  # noqa: BLE001 - a repair is arbitrary caller code: any failure fails closed
            raise MalformedOutput(
                f"output is not valid JSON under its schema even after repair: {exc2}"
            ) from exc2
    if not isinstance(value, dict):
        raise MalformedOutput("schema output must be a JSON object (invariant 27)")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise MalformedOutput(
            f"schema 'properties' must be an object, got {type(properties).__name__} (invariant 27)"
        )
    required = schema.get("required", [])
    # A non-list ``required`` is worse than a crash: iterating the STRING "pick" checks four
    # properties 'p','i','c','k', so a valid output is refused with a nonsense reason. The
    # barrier must not deliver a verdict it did not actually compute (D100).
    if not isinstance(required, (list, tuple)):
        raise MalformedOutput(
            f"schema 'required' must be a list of property names, got {type(required).__name__} "
            "(invariant 27)"
        )
    for key in required:
        if not isinstance(key, str):
            raise MalformedOutput(
                f"schema 'required' holds a non-string property name {key!r} (invariant 27)"
            )
        if key not in value:
            raise MalformedOutput(f"required property {key!r} missing (invariant 27)")
        declared = properties.get(key, {})
        if not isinstance(declared, dict):
            raise MalformedOutput(
                f"schema declares property {key!r} as {type(declared).__name__}, not an object "
                "(invariant 27)"
            )
        expected = declared.get("type")
        if expected is not None and not _json_type_ok(value[key], expected):
            raise MalformedOutput(f"property {key!r} is not of type {expected!r} (invariant 27)")
    return candidate


#: JSON-schema primitive types → the Python types a value may take. ``"null"`` is one of them (a
#: first-class JSON-Schema type): without it, ``{"type": "null"}`` was silently NOT enforced, and
#: the very common nullable union ``["integer", "null"]`` had no member the barrier could judge.
_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


def _single_type_ok(value: object, expected: str) -> bool:
    """Does ``value`` satisfy ONE declared JSON-Schema type name? Unknown keyword ⇒ not enforced."""
    py = _JSON_TYPES.get(expected)
    if py is None:
        return True  # unknown type keyword — not enforced by the stub (real engine at ③)
    if expected in ("number", "integer") and isinstance(value, bool):
        return False  # a bool is neither a number nor an integer (JSON distinguishes true/false)
    return isinstance(value, py)


def _json_type_ok(value: object, expected: object) -> bool:
    """Does ``value`` satisfy the declared ``type`` — a single name OR a UNION list?

    JSON-Schema lets ``type`` be a list: ``{"type": ["integer", "null"]}`` is the ordinary way to
    write "an integer, or nothing" — exactly what an abstention needs ("pick a candidate OR
    abstain"). It is satisfied when ANY declared member is (with ``"null"`` mapping to ``NoneType``,
    see ``_JSON_TYPES``), so refusing a valid nullable output is not on the table.

    Two failure shapes are deliberately answered DIFFERENTLY, because they are different
    situations. An unknown type *keyword* (``"whatever"``) is the documented non-enforcement seam —
    the stub judges what it knows and leaves the full spec to the real engine at ③ — so it is not
    enforced, single or inside a union. A ``type`` that is not a string nor a list of strings is not
    JSON-Schema at all: the barrier cannot read the declaration, so it cannot certify the output,
    so it REFUSES (raised here, caught by the caller's ``MalformedOutput`` contract). Guessing
    would be the one unacceptable answer (D100: refuse, never silently degrade)."""
    if isinstance(expected, str):
        return _single_type_ok(value, expected)
    if isinstance(expected, list) and expected and all(isinstance(m, str) for m in expected):
        return any(_single_type_ok(value, member) for member in expected)
    raise MalformedOutput(
        f"schema declares an unreadable 'type' {expected!r} (expected a type name or a non-empty "
        "list of type names) — the barrier cannot certify against it (invariant 27 / D100)"
    )


@runtime_checkable
class GenerationBackend(Protocol):
    """The primitive decode surface :class:`LocalRunner` runs a completion through (③-2c).

    Deliberately expressed in primitives (str in, str out, a ``model_id`` tag) with no domain
    types, so a light double stands in for the real model in tests (D126) while EVERY barrier
    (grant redemption M1, grammar enforcement invariant 27, replay snapshot, label monotonicity)
    stays in :class:`LocalRunner`. BOTH decode calls receive the prompt CONTENT (the text to
    complete / to extract structure from); ``generate_structured`` also carries the schema and its
    kind — decoding a schema blind to the content would only hallucinate (③-2 closure / F2). The
    default is the weightless :class:`_StubDecoder`;
    :func:`~mnemosyne.runtime.runner_mlx.load_mlx_backend` supplies the real MLX one (D104 / D103)."""

    @property
    def model_id(self) -> str: ...
    def generate(self, prompt: str) -> str: ...
    def generate_structured(self, prompt: str, schema: str, kind: str) -> str: ...


#: JSON-schema type → the minimal value the stub decoder emits for it.
_DEFAULTS: dict[str, object] = {
    "string": "",
    "number": 0,
    "integer": 0,
    "boolean": False,
    "object": {},
    "array": [],
    "null": None,
}


def _default_for(json_type: object) -> object:
    """The minimal value the stub emits for a declared type — union-tolerant, NEVER raises.

    A UNION (``["integer", "null"]``) takes the first member the stub knows, so a nullable field
    gets a usable value: ``_DEFAULTS.get(["integer", "null"])`` used to raise ``TypeError:
    unhashable type: 'list'`` — the SAME defect as in the barrier, in a second place. Anything
    unreadable falls back to ``""`` and is judged downstream by :func:`enforce_grammar`; a stub
    backend is not a barrier, so its job is to hand the barrier something to judge, never to
    decide."""
    if isinstance(json_type, str):
        return _DEFAULTS.get(json_type, "")
    if isinstance(json_type, list):
        for member in json_type:
            if isinstance(member, str) and member in _DEFAULTS:
                return _DEFAULTS[member]
    return ""


def _stub_instance(schema_text: str) -> dict[str, object]:
    """The minimal instance the stub emits for a schema — ``{}`` for anything it cannot walk.

    Every shape check is a "can I read this?", never a verdict on the output: the empty object it
    returns instead is what :func:`enforce_grammar` judges (and refuses)."""
    parsed = json.loads(schema_text)
    if not isinstance(parsed, dict):
        return {}
    properties = parsed.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}
    required = parsed.get("required", [])
    if not isinstance(required, (list, tuple)):
        return {}
    instance: dict[str, object] = {}
    for key in required:
        if not isinstance(key, str):
            return {}
        declared = properties.get(key, {})
        instance[key] = _default_for(declared.get("type") if isinstance(declared, dict) else None)
    return instance


class _StubDecoder:
    """The default in-repo decode backend: deterministic, weightless — real barriers, stub tokens.

    Stands in for the MLX / llama.cpp backend until ③ ignition (like ``StubEmbedder``): its only
    job is to let :class:`LocalRunner`'s barriers be real and testable before any model is
    installed. Replaced behind the SAME :class:`GenerationBackend` seam by
    :class:`~mnemosyne.runtime.runner_mlx._MlxBackend` at ③-2c (D126)."""

    @property
    def model_id(self) -> str:
        return _STUB_MODEL_ID

    def generate(self, prompt: str) -> str:
        """Deterministic stub free-form output (a real backend replaces this at ③)."""
        return f"[stub-runner] {prompt.strip()}"

    def generate_structured(self, prompt: str, schema: str, kind: str) -> str:
        """Produce a minimal instance the grammar accepts (the constrained decoder, stub).

        The ``prompt`` (content) is ignored ON PURPOSE: the stub decodes deterministically from the
        schema alone, so the semantic pass / fact extractor ABSTAIN (empty verdict / no fact) until
        a real model is installed at ③ — the fail-safe posture the ``Null`` sensors had. The seam
        still HANDS it the content, so the real backend (which needs it) is not decoding blind (F2).

        **A schema shape the stub cannot walk yields ``"{}"``, never an exception.** The schema comes
        from a caller and can be anything; a *backend* that crashes on it robs the barrier of the
        chance to refuse (and a backend crash is NOT ``MalformedOutput`` — swallowing a real
        backend's OOM as "malformed" would be a lie). So the stub degrades to the empty object,
        which :func:`enforce_grammar` then refuses for its missing required properties: the verdict
        stays with the barrier, where it belongs."""
        if kind != "json_schema":
            return "ok"
        try:
            return json.dumps(_stub_instance(schema), ensure_ascii=False)
        except Exception:  # noqa: BLE001 - a stub must never crash a call on the caller's schema
            return "{}"


class LocalRunner:
    """A grammar-bound local runner behind the Guard (D104): pluggable decoder, real barriers.

    Every call requires a ``MODEL_CALL`` :class:`Grant`, captures a replay snapshot, and
    emits a redacted trace event. Structured output is decoded under a grammar so it can
    never be malformed (invariant 27). Decoding runs through an injected
    :class:`GenerationBackend` (stub by default, the real MLX brick at ③-2c) — the barriers
    are the runner's, the tokens are the backend's (D126)."""

    __slots__ = (
        "_backend",
        "_backends",
        "_snapshots",
        "_obs",
        "_model_id",
        "_guard",
        "_max_prompt_chars",
    )

    def __init__(
        self,
        *,
        snapshots: SnapshotStore,
        observability: LocalObservability,
        backend: GenerationBackend | None = None,
        backends: BackendRegistry | None = None,
        guard: Guard | None = None,
        max_prompt_chars: int | None = None,
    ) -> None:
        # the decode seam (③-2c): the injected backend does the token work; default = the stub
        # decoder, so the brick-free suite runs unchanged (D126). Its id tags snapshots + traces.
        self._backend = backend if backend is not None else _StubDecoder()
        # D7 / D98 (γ) — optional bench registry: a call ROUTED to a mapped model-id
        # (grant.request.target) decodes through THAT model's backend, loaded just-in-time and one
        # big model at a time (D95); absent ⇒ every call uses the single default (zero-regression).
        self._backends = backends
        self._snapshots = snapshots
        self._obs = observability
        self._model_id = self._backend.model_id
        # M1 (D89 / D100) — when wired (the bootstrap production path) the runner AUTHENTICATES
        # each grant's token before acting; a unit-test double may omit it and check shape only.
        self._guard = guard
        # D136 — the fail-closed input ceiling (invariant 16 / D78): no single call may exceed what the
        # model can read. Default = the module constant; bootstrap passes policy.bounds['max_prompt_chars']
        # when ③ sets it (the D78 named place), so tuning to the installed model needs no code change.
        ceiling = max_prompt_chars if max_prompt_chars is not None else _MAX_PROMPT_CHARS
        if ceiling <= 0:
            raise ValueError(f"max_prompt_chars must be positive, got {ceiling}")
        self._max_prompt_chars = ceiling

    @property
    def model_id(self) -> str:
        """The id of the wired decode backend — what tags this runner's snapshots + traces."""
        return self._model_id

    @property
    def max_prompt_chars(self) -> int:
        """The resolved input ceiling this runner enforces (D136). Exposed so a caller that must
        map-reduce UNDER it (the RAPTOR summarizer, Ch.5) derives its per-call budget from the SAME
        number — never an independent constant that could drift above this bound."""
        return self._max_prompt_chars

    def _backend_for(self, grant: Grant) -> tuple[GenerationBackend, str]:
        """The decode backend serving this call's ROUTED model, and the model-id to tag it (D7 / γ).

        The router named a model per task class and it rides the grant as ``grant.request.target``
        (D7). When a bench registry is wired AND the target is a mapped, NON-default model, this call
        decodes through THAT model's backend (loaded just-in-time, one big model at a time, D95). A
        ``None`` target, the DEFAULT model's own id, or an unmapped one all resolve to the wired
        default backend — the router's capable fallback (D70). No registry wired ⇒ always the default
        (byte-identical to pre-γ). The returned model-id tags the snapshot + trace with the model that
        ACTUALLY ran, never a stale default (honest provenance, invariant 12)."""
        target = grant.request.target
        if self._backends is not None and target is not None and target != self._model_id:
            resolved = self._backends.resolve(target)
            if resolved is not None:
                return resolved, resolved.model_id
        return self._backend, self._model_id

    def complete(
        self,
        prompt: Envelope[str],
        *,
        grant: Grant,
        constraint: GrammarConstraint | None = None,
    ) -> Envelope[str]:
        """Free-form local completion (D104). ``grant`` proves the Guard routed the call;
        an optional ``constraint`` still bounds the output. Result label ≥ prompt (inv. 17)."""
        self._require_bounded(prompt, constraint)
        self._require_model_call(grant)
        backend, model_id = self._backend_for(grant)
        text = backend.generate(prompt.payload)
        if constraint is not None:
            text = enforce_grammar(text, constraint)
        return self._emit(prompt, text, grant, constraint, model_id=model_id)

    def complete_structured(
        self,
        prompt: Envelope[str],
        *,
        grant: Grant,
        constraint: GrammarConstraint,
    ) -> Envelope[str]:
        """Structured / tool-calling completion (invariant 27): the grammar is REQUIRED and
        the decoder is bound to it, so the output cannot be a malformed tool call or JSON."""
        self._require_bounded(prompt, constraint)
        self._require_model_call(grant)
        backend, model_id = self._backend_for(grant)
        candidate = backend.generate_structured(prompt.payload, constraint.schema, constraint.kind)
        text = enforce_grammar(candidate, constraint)  # the barrier: conform or raise
        return self._emit(prompt, text, grant, constraint, model_id=model_id)

    # -- structural checks + stub decoding --------------------------------------------
    def _require_bounded(self, prompt: Envelope[str], constraint: GrammarConstraint | None) -> None:
        """Refuse a prompt larger than the model can read — fail-CLOSED, never truncated (D136).

        The structural close of the "unbounded content → model" class: a whole document overflows
        the context window, so a single call is capped at ``_max_prompt_chars`` and an oversized one
        RAISES :class:`ResourceBoundError` (invariant 16 / D78). BOTH variable terms count — the
        content payload AND the grammar schema the backend also decodes against (audit m-1) — so a
        big tool schema cannot slip a call over the ceiling; the fixed chat-template overhead is small
        and absorbed by the conservative margin. Raising, not truncating, is deliberate — the salient
        part often sits at the END (a question, the newest turn), so a silent head-cut would answer
        confidently from the wrong half (D100). The caller degrades (capture keeps the datum
        truth-first, plan-B) or map-reduces; it never gets a quietly-wrong completion. Checked FIRST,
        before the grant is redeemed, so an oversized call is refused without burning its one-time
        grant (M1)."""
        size = len(prompt.payload) + (len(constraint.schema) if constraint is not None else 0)
        if size > self._max_prompt_chars:
            raise ResourceBoundError(
                f"prompt+schema of {size} chars exceeds the runner bound of {self._max_prompt_chars} "
                "(invariant 16 / D78 / D136) — reduce or map-reduce before the call, never truncate"
            )

    def _require_model_call(self, grant: Grant) -> None:
        """A runner acts only on an AUTHENTIC Guard grant FOR a model call (D89 / M1).

        Checks the effect shape, then — when a Guard is wired (the production path via bootstrap)
        — authenticates AND consumes the grant's token: a forged or replayed grant is refused
        fail-closed (M1 / D100). Without a wired Guard (a unit-test double) only the shape is
        checked. The effect is verified first so a valid grant merely mis-routed here is not
        burned before the shape refusal."""
        if grant.request.effect is not Effect.MODEL_CALL:
            raise GuardDenied(
                f"runner requires a MODEL_CALL grant, got {grant.request.effect.value!r} (D89)"
            )
        if self._guard is not None:
            self._guard.redeem(grant)  # M1 — authentic + unspent, or GuardDenied (D100)

    def _emit(
        self,
        prompt: Envelope[str],
        text: str,
        grant: Grant,
        constraint: GrammarConstraint | None,
        *,
        model_id: str,
    ) -> Envelope[str]:
        """Wrap the output (label ≥ prompt), snapshot it, and trace it redacted (inv. 12).

        ``model_id`` is the backend that ACTUALLY decoded this call — the routed bench model when γ
        dispatched, else the default — so the snapshot + trace name the real model, never a stale
        default (honest replay / provenance, invariant 12)."""
        out_label = prompt.label.raised_to(grant.released_label.sensitivity)
        output = Envelope(text, out_label)
        self._snapshots.capture(
            model_id=model_id,
            prompt=prompt,
            output=output,
            constraint=constraint.schema if constraint is not None else None,
        )
        trace = self._obs.start_trace("model.call", out_label)
        self._obs.event(trace, "model.complete", model=model_id, output=text)
        return output
