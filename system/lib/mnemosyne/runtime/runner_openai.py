"""OpenAIBackend (D104 / D103) — a second FRONTIER decode leg behind the Runner's GenerationBackend
seam, for a sibling project's "structured production" task class.

**Why this exists.** The user, 2026-08-21: that sibling project's production tasks (`governed_bench.py` and
whatever else the routing table sends to the "Sonnet/local" tier) should stop running against the
local MLX backend — not for cost (the local decode is free), but for LATENCY (~29 min for a single
real bench run, serial on one machine) and because the local model is not what that project will actually
ship with. They explicitly chose the safety posture: a HARD spend limit set on their own OpenAI
account (``platform.openai.com`` → Organization limits → "Enforce a hard limit") is the real backstop,
so no per-call ``[OPERATOR]`` gesture gates an individual run the way :mod:`.runner_anthropic`'s
campaign does today — *"I'm authorizing every run to be a go [...] I have a barrier over there, not on
your end."* The data itself is that sibling project's own explicit, dated call: current production data (macro
reports built from already-public sources — BLS, World Bank, OECD, central banks) is ``public``, not
``sensible`` — see ``state/decisions/`` in that sibling project and the memory this session wrote
(recorded in a memory entry the session wrote). That is what makes the automatic canal-A path legal at all
(D66); this backend does not change that rule, it only gives canal A a second provider to reach.

**A drop-in GenerationBackend, NOT an autonomous agent** — same contract as
:class:`~mnemosyne.runtime.runner_anthropic.AnthropicBackend`, same reason: the caller (e.g.
``governed_bench.py``) drives one bounded task per call and takes back a filled schema; the model
fills a form, it never decides the work.

**The barrier is the Garde, not this code (D100).**

* **PUBLIC-only by ROUTING (invariant 1 / D66)**, exactly like the Anthropic leg. A caller reaches
 this backend only after ``route_model`` returns canal A, which only happens when every input is
 ``public``. This module does not — and structurally cannot — loosen that; it is a second decode
 engine behind the same gate, not a new gate.
* **Allow-listed host (invariant 21 / SE5).** ``api.openai.com`` sits on the protected egress
 allow-list (D159 request ``a1c65f3fce92``, examined by an isolated agent — verdict ``allow`` —
 and approved live by the user on 2026-08-21). **Measured while wiring this**: for a MODEL_CALL
 effect the egress allow-list is not actually consulted (``_rule_model_call`` reads only
 ``route_model()``, never ``request.target`` — confirmed against ``guard/monitor.py`` and true
 already for the never-applied ``api.anthropic.com`` entry). Declaring the host here is still done,
 for the same audit-trail reason the Anthropic leg does it, but the real gate a caller depends on is
 the canal-A routing check above, not this list.
* **Sole-importer + lazy (D103 / invariant 20 / D126).** ``openai`` is imported inside
 :func:`load_openai_backend` ONLY, so this module (and its stub-tested core) import with no SDK
 installed. :class:`OpenAIBackend` talks to an injected client, so the retry / parsing logic is
 proven against a fake with NO key and NO network.
* **The key belongs to the user (invariant 22).** Read from the environment BY THE SDK ([OPERATOR]
 gesture); Mnemosyne code never touches the value. That sibling project's own ``secrets/openai.env`` (same
 convention as its other API keys — ``scripts/acquisition_secrets.py``) is loaded into the process
 environment by whatever entry point runs the campaign, before this factory is called; this module
 only ever reads ``os.environ``.

**Structured output = the Responses API's native ``text.format`` (json_schema), not tool-use.** The
passed JSON schema becomes ``text.format.schema``; the reply's ``output_text`` is a JSON string that
:func:`~mnemosyne.runtime.runner.enforce_grammar` (+ ``close_json`` repair) then RE-VALIDATES in the
runner (belt and braces: the model is never trusted, invariant 27). ``strict`` is left ``False`` —
the schemas this seam receives are not pre-massaged to OpenAI's stricter subset (every field
``required``, ``additionalProperties: false`` everywhere), and the runner's own re-validation is the
actual guarantee; ``strict`` here would only be an optimisation, and a schema it rejects would fail
LOUD before ever reaching that re-validation instead of degrading to it.

Decisions: D104 (runner seam, mirrors runner_anthropic) · D103 / inv 20 (sole importer) · D66
(public-only egress routing, unchanged by this module) · D85 (per-call resilience) · D117 (English
code). Model pricing/name are placeholders pending the model choice the user and this session still
owe each other — see :data:`_DEFAULT_MODEL`.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable

from ..ports.core import ResourceBoundError
from ..production.spend import CanonicalUsage, SpendLedger


def refuser_si_tronque(response: object, plafond: int) -> None:
    """ Mirrors :func:`~mnemosyne.runtime.runner_anthropic.refuser_si_tronque` (D165 / A4): a
 response cut off mid-thought by the output ceiling must be REFUSED, never consumed as if it were
 complete. The Responses API signals this as ``status == "incomplete"`` with
 ``incomplete_details.reason == "max_output_tokens"`` — the shape differs from Anthropic's
 ``stop_reason``, the rule does not."""
    if getattr(response, "status", None) != "incomplete":
        return
    details = getattr(response, "incomplete_details", None)
    if getattr(details, "reason", None) != "max_output_tokens":
        return
    raise ResourceBoundError(
        f"response TRUNCATED by the output ceiling (max_output_tokens={plafond}): the model was "
        f"cut off before finishing. This is not a short response, it is an INCOMPLETE response — "
        f"consuming it as if it were whole is the real fault. Remedy: raise "
        f"`max_output_tokens` at the call site, or split the request. Tokens already spent are "
        f"still counted."
    )


#: Tiered by the user on 2026-08-21, A TWO-TIER SCALE ONLY (`gpt-5-mini` DROPPED after
#: benchmark verification -- stays in `spend.py`'s price table for history, no longer
#: in this scale): `gpt-5-nano` by default, `gpt-5.6-luna` as a fallback IF AND ONLY IF
#: Nano genuinely fails the task. THIS IS NOT A cost/quality OPTIMIZATION -- the user
#: explicitly REJECTS that trade-off, verbatim: *"even if it's worse and the quality-to-price
#: ratio is worse, I'd rather have paid 40 cents [...] than pay [...] 1.20 where the
#: quality is maybe 10% better [...] we don't discuss it, we test Nano."* A future chat that
#: saw Nano "rated lower" and wanted to swap it for Luna by default would be GOING AGAINST
#: this direct word -- Luna stays the ESCALATION, never the starting point, even if
#: public benchmarks (noisy on models this recent, cross-cutting and sometimes contradicting
#: each other that day) suggest Luna would be "objectively" a better quality-to-price ratio. On
#: the relative input/output weight, verbatim: *"what we're building is almost
#: entirely OUT tokens"* -- the OUTPUT price dominates the real cost. `gpt-5-nano`: $0.05/Mtok in,
#: $0.40/Mtok out (verified at developers.openai.com/api/docs/pricing). A product argument from
#: the user beyond price: local (already judged sufficient for "production_structuree",
#: `state/decisions/routage-par-capacite.md`) is in their words "a hundred times dumber" than a GPT-5
#: Nano -- if local is enough, Nano clears the bar with room to spare.
_DEFAULT_MODEL = "gpt-5-nano"

#: The one host this backend reaches. On the egress allow-list since 2026-08-21 (D159, request
#: a1c65f3fce92) — see the caveat in the module docstring: this is not what gates MODEL_CALL,
#: it is [routing] canal_a_auto (D66) that does, unchanged by this module.
HOST = "api.openai.com"

#: Output ceiling per call — margin above the largest schema this task class
#: produces today (same proportions as `distill_book`'s local threshold).
_DEFAULT_MAX_TOKENS = 4096

#: HTTP statuses worth retrying on a long batch (rate-limit / overload / transient server error).
#: Duck-typed on the exception (`.status_code`) — same classes as `runner_anthropic`, the OpenAI SDK
#: carries the same error shape (`openai.APIStatusError` and its subclasses expose `.status_code`).
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 529})

#: Fallback when no status is present — SDK error class-name fragments (lower-cased). Same
#: fragments as `runner_anthropic`: both SDKs (Anthropic, OpenAI) name their exceptions from the
#: same family (`RateLimitError`, `APIConnectionError`, `APITimeoutError`, `InternalServerError`).
_RETRYABLE_NAMES = ("ratelimit", "overloaded", "apiconnection", "apitimeout", "internalserver")


def _is_retryable(exc: BaseException) -> bool:
    """Identical to `runner_anthropic._is_retryable` — a quota refusal (OpenAI ceiling reached,
    `insufficient_quota`) carries neither a retryable status nor a retryable name fragment, so it
    never loops against a ceiling already reached (the provider-side brake the user chose must
    stop, not get hammered again by a blind retry loop)."""
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        status = getattr(exc, "status", None)
    if isinstance(status, int) and status in _RETRYABLE_STATUS:
        return True
    name = type(exc).__name__.lower()
    return any(tag in name for tag in _RETRYABLE_NAMES)


class OpenAIBackend:
    """A :class:`~mnemosyne.runtime.runner.GenerationBackend` backed by the OpenAI Responses API.

    Mirrors :class:`~mnemosyne.runtime.runner_anthropic.AnthropicBackend` structurally: a TESTABLE
    core (retry + parsing + usage accounting) holding an INJECTED client (any object exposing
    ``responses.create(...)``), proven with NO SDK and NO key. :func:`load_openai_backend` is the
    sole importer of ``openai`` (D103) and supplies the real client.

    Every security barrier stays OUTSIDE this class (grant redemption M1, grammar enforcement
    invariant 27, replay snapshot) — this is a plain decode primitive, same posture as the Anthropic
    leg."""

    __slots__ = (
        "_client",
        "_model",
        "_max_tokens",
        "_max_retries",
        "_base_delay",
        "_sleep",
        "_usage",
        "_ledger",
        "_cost_ceiling_eur",
        "_token_ceiling",
    )

    def __init__(
        self,
        client: object,
        *,
        model: str = _DEFAULT_MODEL,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        max_retries: int = 6,
        base_delay: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        ledger: SpendLedger | None = None,
        cost_ceiling_eur: float = 0.0,
        token_ceiling: int = 0,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._sleep = sleep  # injectable so tests never actually wait
        self._usage = {"input_tokens": 0, "output_tokens": 0, "requests": 0}
        self._ledger = ledger
        self._cost_ceiling_eur = cost_ceiling_eur
        self._token_ceiling = token_ceiling

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def usage(self) -> dict[str, int]:
        """Cumulative token usage — a COPY, so a caller cannot mutate the running tally."""
        return dict(self._usage)

    def generate(self, prompt: str) -> str:
        """Free-form completion. Structured distillation uses :meth:`generate_structured`."""
        response = self._create(input=[{"role": "user", "content": prompt}])
        return getattr(response, "output_text", "") or ""

    def generate_structured(self, prompt: str, schema: str, kind: str) -> str:
        """Fill ``schema`` FROM the ``prompt`` content via the Responses API's native structured
        output; the runner re-validates. Only ``kind == "json_schema"`` takes the schema path (the
        sole kind distillation uses); anything else, or an unparseable schema, falls back to
        free-form — matching :meth:`~mnemosyne.runtime.runner_anthropic.AnthropicBackend.generate_structured`."""
        if kind != "json_schema":
            return self.generate(prompt)
        try:
            input_schema = json.loads(schema)
        except json.JSONDecodeError:
            return self.generate(prompt)
        text_format = {
            "format": {
                "type": "json_schema",
                "name": "structured_output",
                "schema": input_schema,
                "strict": False,  # see module docstring: the runner's own re-validation is the guarantee
            }
        }
        response = self._create(
            input=[{"role": "user", "content": prompt}],
            text=text_format,
        )
        return getattr(response, "output_text", "") or ""

    def _create(self, **kwargs: object) -> object:
        """``responses.create`` with capped exponential backoff on TRANSIENT errors. A non-retryable
        error, or exhausted retries, RAISES. Usage is tallied on every success.

        Ceiling checked ONCE before the first attempt (D155/D86, same ordering rule as the Anthropic
        leg): a retry storm is one logical call, and the tokens a failed-then-retried attempt spends
        are still real spend once it succeeds."""
        if self._ledger is not None:
            self._ledger.check_ceilings(
                cost_ceiling_eur=self._cost_ceiling_eur, token_ceiling=self._token_ceiling
            )
        attempt = 0
        while True:
            try:
                response = self._client.responses.create(  # type: ignore[attr-defined]
                    model=self._model, max_output_tokens=self._max_tokens, **kwargs
                )
            except Exception as exc:  # noqa: BLE001 - classify then retry-or-raise, SDK-free (D103)
                attempt += 1
                if attempt > self._max_retries or not _is_retryable(exc):
                    raise
                self._sleep(self._backoff(attempt))
                continue
            self._record(response)
            refuser_si_tronque(response, self._max_tokens)
            return response

    def _backoff(self, attempt: int) -> float:
        return min(self._base_delay * (2 ** (attempt - 1)), 30.0) + random.uniform(
            0, self._base_delay
        )

    def _record(self, response: object) -> None:
        """Tally one success — in RAM for the campaign, and on DISK when a ledger is wired. Mirrors
        `AnthropicBackend._record`'s two-way/four-way split."""
        usage = getattr(response, "usage", None)
        self._usage["requests"] += 1
        self._usage["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
        self._usage["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
        if self._ledger is not None:
            self._ledger.record(self._model, CanonicalUsage.from_openai(usage))


def load_openai_backend(  # pragma: no cover - needs the brick + the user's key (③ ignition, smoke-tested)
    *,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    max_retries: int = 6,
    api_key_env: str = "OPENAI_API_KEY",
) -> OpenAIBackend:
    """Wire the real OpenAI backend (③ ignition, D126 ``[OPERATOR]``). Mirrors
    :func:`~mnemosyne.runtime.runner_anthropic.load_anthropic_backend` exactly.

    SOLE importer of ``openai`` (D103 / invariant 20), imported LAZILY. Reads the user's key from
    ``api_key_env`` and fails LOUD if absent — the key is an [OPERATOR] gesture (their own
    ``secrets/openai.env``, loaded into the environment by the caller before this runs), never a repo
    secret, never touched by Mnemosyne code beyond this read. The caller MUST have cleared the egress
    first (``route_model`` → public) — the Guard is the barrier, not this factory (D100)."""
    import os

    from openai import OpenAI  # the SOLE import of the brick (D103 / invariant 20)

    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"{api_key_env} not set — the OpenAI backend needs the user's API key ([OPERATOR] "
            "gesture, never a repo secret). Load secrets/openai.env before running."
        )
    client = OpenAI(api_key=api_key, max_retries=max_retries)
    return wire_backend(client, model=model, max_tokens=max_tokens, max_retries=max_retries)


def wire_backend(
    client: object,
    *,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    max_retries: int = 6,
) -> OpenAIBackend:
    """Build a fully-wired backend around an already-built client — ledger included, ceilings left at
    zero. Identical posture to :func:`~mnemosyne.runtime.runner_anthropic.wire_backend`, and for the
    same reason: it MEASURES (``make depense`` must never under-count what actually ran) but it does
    NOT refuse — the user's chosen brake for this backend is their own OpenAI account spend limit
    (platform.openai.com → Organization limits → "Enforce a hard limit"), not a Mnemosyne-side
    ceiling nobody asked for. A caller that wants the Mnemosyne-side ceiling too passes
    ``cost_ceiling_eur``/``token_ceiling`` explicitly, or this function starts reading
    :func:`~mnemosyne.production.spend.policy_ceilings` the day the user asks for that — one line,
    added on their word rather than guessed here."""
    return OpenAIBackend(
        client,
        model=model,
        max_tokens=max_tokens,
        max_retries=max_retries,
        ledger=SpendLedger(),
    )
