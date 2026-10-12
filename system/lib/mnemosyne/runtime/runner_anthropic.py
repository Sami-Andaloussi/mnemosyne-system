"""AnthropicBackend (D104 / D103) — the FRONTIER decode leg behind the Runner's GenerationBackend
seam, for the PUBLIC-book distillation campaign (Claude Haiku).

**Why this exists.** The local MLX backend (:mod:`.runner_mlx`, GLM-4-9B) distils faithfully but
SERIALLY — one big model resident at a time (D95, 32 GB budget), ~2 h per book. A 20-book batch is
~40 h, which stalls the user's work for days. A PUBLISHED book is ``public`` by provenance (D144), so its
text MAY leave to an allow-listed cloud host (``route_model`` → canal A, D66) — and the Anthropic API
parallelises across books/sections (network-bound, not RAM-bound), turning ~40 h into well under an
hour. Same seam, same barriers, a faster engine.

**A drop-in GenerationBackend, NOT an autonomous agent.** :class:`~mnemosyne.runtime.runner.LocalRunner`
decodes through the primitive :class:`~mnemosyne.runtime.runner.GenerationBackend` surface (str in, str
out, a ``model_id`` tag); the whole faithful pipeline of ``distill_book.py`` (section chunking, verbatim
P3 floor D143, JSON repair, sub-chunk recovery, atomic assembly) is REUSED byte-for-byte — only the
decode engine changes. This is the exact opposite of the failed Haiku-*agent* path (an agent told to
"distil this book" skimps and self-reports success falsely, verified 2026-07-16): here the CODE drives,
handing the model ONE section + a STRICT tool schema and taking back the filled object. The model fills
a form, it never decides the work — faithful by construction (contract-single-source, D28 / D143).

**The barrier is the Garde, not this code (D100).**

* **PUBLIC-only by ROUTING (invariant 1 / D66).** This backend reaches the cloud, so a caller MUST use
  it ONLY after ``route_model`` returns canal A — which it does *only* when every input is ``public``;
  any ``perso`` / ``sensible`` / unlabeled input forces ``LOCAL``. A non-public doc can therefore never
  reach Haiku. The routing decision lives in the Guard, not here (see the campaign runner).
* **Allow-listed host (invariant 21 / SE5).** ``api.anthropic.com`` must ALSO sit on the protected
  egress allow-list (an [OPERATOR] POLICY_WRITE) — an independent second barrier; declaring :data:`HOST`
  here is not enough.
* **Sole-importer + lazy (D103 / invariant 20 / D126).** ``anthropic`` is imported inside
  :func:`load_anthropic_backend` ONLY, so this module (and its stub-tested core) import with no SDK
  installed. :class:`AnthropicBackend` talks to an injected client, so the retry / tool-parsing logic
  is proven against a fake with NO key and NO network; the SDK wiring is ``# pragma: no cover`` (the (3)
  smoke confronts it, like the MLX seam).
* **The key belongs to the user (invariant 22).** Read from the environment BY THE SDK ([OPERATOR]
  gesture); Mnémosyne code never touches the value (mirrors :mod:`.caption_anthropic`).

**Structured output = tool-use.** The passed JSON schema becomes a single tool's ``input_schema``, the
call FORCES that tool (``tool_choice``), and the tool's ``input`` is returned as a JSON string — which
:func:`~mnemosyne.runtime.runner.enforce_grammar` (+ ``close_json`` repair) then RE-VALIDATES in the
runner (belt and braces: the model is never trusted, invariant 27).

Decisions: D104 (runner seam) · D103 / inv 20 (sole importer) · D95 (why frontier for the batch) ·
D144 / D66 (public-only egress routing) · D85 (per-call resilience → the section net) · D117 (English code).
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable

from ..ports.core import ResourceBoundError
from ..production.spend import CanonicalUsage, SpendLedger


def refuser_si_tronque(message: object, plafond: int) -> None:
    """ AN OUTPUT CEILING THAT TRUNCATES SILENTLY PRODUCES A FALSE RESPONSE (A4 / D165).

 Measured on 2026-08-09: this runner called `messages.create(max_tokens=4096)` and **never
 read `stop_reason`**. When the model hit the ceiling, the caller received a response
 **truncated mid-word** that looks exactly like a complete response — and nothing, anywhere,
 said so. This is the defect this repo's memory had already named for the local runner without
 anyone closing it, and it was ALSO alive on the frontier path.

 THE ASYMMETRY WAS THE DEFECT. The INPUT ceiling (D136) **refuses**; the OUTPUT one
 **truncated silently**. Both are configured bounds (inv. 16): both must speak up. So this
 raises `ResourceBoundError` — *between a silent false green and a loud false red, pick the one
 that shouts* — and a response cut off mid-sentence is not a response.

 CALLED **AFTER** ACCOUNTING, AND THE ORDER IS THE POINT: the tokens really were spent, so
 they are logged before the refusal. Refusing first would erase real spend from the books
 (D155/D86).
 """
    if getattr(message, "stop_reason", None) != "max_tokens":
        return
    raise ResourceBoundError(
        f"reponse TRONQUEE par le plafond de sortie (max_tokens={plafond}) : le modele a ete coupe "
        f"avant d'avoir fini. Ce n'est pas une reponse courte, c'est une reponse INCOMPLETE — la "
        f"consommer comme si elle etait entiere est la vraie faute. Remede : relever `max_tokens` "
        f"au site d'appel, ou decouper la demande. Les jetons deja depenses sont comptes."
    )


#: Frozen default frontier model — Claude Haiku 4.5 (fast + cheap, enough to FILL a section's
#: structured form). Matches :data:`mnemosyne.ingest.caption_anthropic._DEFAULT_MODEL`; a one-line
#: swap, carried into the fiche's ``distilled_by`` provenance so a model change stays traceable.
_DEFAULT_MODEL = "claude-haiku-4-5"

#: The one egress host this backend reaches. Public — named so a caller can pre-check the routing /
#: allow-list before constructing the backend. It must ALSO be on the protected egress allow-list
#: ([OPERATOR] POLICY_WRITE, invariant 21); declaring it here is not enough (the two barriers, D90).
HOST = "api.anthropic.com"

#: Output ceiling per section call — matches ``distill_book``'s local backend (margin > the schema's
#: max output so a section's JSON is never truncated).
_DEFAULT_MAX_TOKENS = 4096

#: The single forced tool that carries the schema — structured output = tool-use (the Anthropic-native
#: way to get schema-valid JSON). Its ``input`` is the object the runner then re-validates (invariant 27).
_STRUCTURED_TOOL = "emit_structured"

#: HTTP statuses worth retrying on a long batch (rate-limit / overloaded / transient server). Matched
#: DUCK-TYPED on the exception (a ``.status_code`` / ``.status``) so this module imports no SDK error
#: types (D103): a fake client can raise a plain error carrying one of these in tests.
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 529})

#: Fallback classification when no status is present — SDK error class-name fragments (lower-cased).
_RETRYABLE_NAMES = ("ratelimit", "overloaded", "apiconnection", "apitimeout", "internalserver")


def _text_of(message: object) -> str:
    """Join the text blocks of a Messages reply (free-form path). Duck-typed like caption_anthropic —
    a tool_use block carries no ``.text`` and contributes nothing."""
    blocks = getattr(message, "content", []) or []
    return "".join(getattr(block, "text", "") or "" for block in blocks).strip()


def _tool_input_of(message: object, tool_name: str) -> str:
    """Return ``json.dumps`` of the forced tool's ``input`` (structured path).

    With ``tool_choice`` forcing :data:`_STRUCTURED_TOOL`, a well-formed reply carries exactly one
    ``tool_use`` block for it. A missing block (a refusal, a malformed reply) RAISES — the distill D85
    net then sub-chunks or flags the section (never a silent hole)."""
    blocks = getattr(message, "content", []) or []
    for block in blocks:
        if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == tool_name:
            return json.dumps(getattr(block, "input", {}) or {}, ensure_ascii=False)
    raise RuntimeError(
        f"no tool_use block {tool_name!r} in the frontier reply (forced tool_choice)"
    )


def _is_retryable(exc: BaseException) -> bool:
    """Whether a failed ``messages.create`` is a TRANSIENT error worth retrying — classified SDK-free.

    A resource-bound breach (invariant 7) or a schema/auth error is NOT transient: it carries no
    retryable status and no matching class name, so it propagates (never hammered past a blown quota)."""
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        status = getattr(exc, "status", None)
    if isinstance(status, int) and status in _RETRYABLE_STATUS:
        return True
    name = type(exc).__name__.lower()
    return any(tag in name for tag in _RETRYABLE_NAMES)


class AnthropicBackend:
    """A :class:`~mnemosyne.runtime.runner.GenerationBackend` backed by the Anthropic Messages API.

    The TESTABLE core (retry + tool-use parsing + usage accounting), holding an INJECTED client (any
    object exposing ``messages.create(...)``) so the whole thing is unit-proven against a fake with NO
    SDK and NO key (D126) — the caption_anthropic split. :func:`load_anthropic_backend` is the sole
    importer of ``anthropic`` (D103) and supplies the real client.

    A plain primitive: EVERY security barrier stays in :class:`LocalRunner` (grant redemption M1,
    grammar enforcement invariant 27, replay snapshot, label monotonicity). Structured output is a
    FORCED tool call whose ``input_schema`` is the passed schema; the returned JSON is re-validated by
    the runner (D100 — the model is never trusted)."""

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
        # D155 — the durable half of the accounting. Optional so every existing construction (and the
        # whole brick-free suite) keeps working unchanged; a ceiling of 0 means "not configured" and
        # never blocks, so wiring the ledger without ceilings gives measurement with no new refusal.
        self._ledger = ledger
        self._cost_ceiling_eur = cost_ceiling_eur
        self._token_ceiling = token_ceiling

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def usage(self) -> dict[str, int]:
        """Cumulative token usage (input/output/requests) — read by the campaign to PRICE the run (a
        copy, so a caller cannot mutate the running tally)."""
        return dict(self._usage)

    def generate(self, prompt: str) -> str:
        """Free-form completion (the answer path). Structured distillation uses
        :meth:`generate_structured`."""
        message = self._create(messages=[{"role": "user", "content": prompt}])
        return _text_of(message)

    def generate_structured(self, prompt: str, schema: str, kind: str) -> str:
        """Fill ``schema`` FROM the ``prompt`` content via a FORCED tool call; the runner re-validates.

        Only ``kind == "json_schema"`` takes the tool path (the sole kind distillation uses); anything
        else falls back to free-form. The schema is ours (always valid JSON) — a defensive parse
        failure also falls back rather than raising blind."""
        if kind != "json_schema":
            return self.generate(prompt)
        try:
            input_schema = json.loads(schema)
        except json.JSONDecodeError:
            return self.generate(prompt)
        tool = {
            "name": _STRUCTURED_TOOL,
            "description": "Return the distilled result as a single structured object.",
            "input_schema": input_schema,
        }
        message = self._create(
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": _STRUCTURED_TOOL},
        )
        return _tool_input_of(message, _STRUCTURED_TOOL)

    def _create(self, **kwargs: object) -> object:
        """``messages.create`` with capped exponential backoff on TRANSIENT errors (long-batch
        resilience). A non-retryable error, or exhausted retries, RAISES — the distill D85 net records
        the section for re-processing. Usage is tallied on every success (cost accounting).

        The ceiling is checked ONCE, before the first attempt (D155 / D86): a retry storm is the same
        logical call, and re-checking between attempts would abandon work mid-flight over a ceiling
        that the call itself is not what crossed. ``ResourceBoundError`` propagates like any other
        non-retryable failure — it is a refusal, not a transient."""
        if self._ledger is not None:
            self._ledger.check_ceilings(
                cost_ceiling_eur=self._cost_ceiling_eur, token_ceiling=self._token_ceiling
            )
        attempt = 0
        while True:
            try:
                message = self._client.messages.create(  # type: ignore[attr-defined]
                    model=self._model, max_tokens=self._max_tokens, **kwargs
                )
            except Exception as exc:  # noqa: BLE001 - classify then retry-or-raise, SDK-free (D103)
                attempt += 1
                if attempt > self._max_retries or not _is_retryable(exc):
                    raise
                self._sleep(self._backoff(attempt))
                continue
            self._record(message)
            refuser_si_tronque(message, self._max_tokens)
            return message

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff capped at 30 s, plus jitter (avoid a synchronised retry storm)."""
        return min(self._base_delay * (2 ** (attempt - 1)), 30.0) + random.uniform(
            0, self._base_delay
        )

    def _record(self, message: object) -> None:
        """Tally one success — in RAM for the campaign, and on DISK when a ledger is wired.

        The RAM tally keeps its original two-way shape (existing readers depend on it); the ledger
        gets the four-way split, cache reads and writes included, because those are what a long
        cached run actually spends (D155)."""
        usage = getattr(message, "usage", None)
        self._usage["requests"] += 1
        self._usage["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
        self._usage["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
        if self._ledger is not None:
            self._ledger.record(self._model, CanonicalUsage.from_anthropic(usage))


def load_anthropic_backend(  # pragma: no cover - needs the brick + the user's key ((3) ignition, smoke-tested)
    *,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    max_retries: int = 6,
    api_key_env: str = "ANTHROPIC_API_KEY",
) -> AnthropicBackend:
    """Wire the real Anthropic backend ((3) ignition, D126 ``[OPERATOR]``).

    SOLE importer of ``anthropic`` (D103 / invariant 20), imported LAZILY so the module and its
    stub-tested core load with no SDK. Reads the user's key from ``api_key_env`` and fails LOUD if
    absent (a silent no-key would look like a systemic distill failure, F3): the key is an
    [OPERATOR] gesture, held by the SDK, never touched by Mnémosyne code. The caller MUST have
    cleared the egress first (``route_model`` → public + host allow-listed) — the Guard is the
    barrier, not this factory (D100)."""
    import os

    from anthropic import Anthropic  # the SOLE import of the brick (D103 / invariant 20)

    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"{api_key_env} not set — the frontier distillation backend needs the user's API key "
            "([OPERATOR] gesture, never a repo secret). Export it before running the Haiku campaign."
        )
    # The SDK's own retry is a floor; AnthropicBackend layers batch-aware backoff on top.
    client = Anthropic(api_key=api_key, max_retries=max_retries)
    # D155 — the ledger and the ceilings are wired HERE, not left to the caller. The first audit of
    # this lot found them optional in the only construction that has a real key and a real network:
    # `spend.py` existed, `make depense` worked, and the campaign spent with `ledger=None` — so the
    # ceiling was never checked and not one line was ever journaled. A counter that must be opted
    # into at every call site is the decorative ceiling it was written to replace.
    return wire_backend(client, model=model, max_tokens=max_tokens, max_retries=max_retries)


def wire_backend(
    client: object,
    *,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    max_retries: int = 6,
) -> AnthropicBackend:
    """Build a fully-wired backend around an already-built client — ledger and ceilings included.

    Split out of :func:`load_anthropic_backend` so the WIRING is testable without the SDK or a key.
    The factory above is ``# pragma: no cover`` by necessity (it imports the brick and reads the
    user's key), and the audit's blocker lived exactly there: the ledger was optional, production
    passed ``None``, and no test could see it because nothing covers that line. Splitting the one
    decision that matters into a plain function is what makes it provable.

    **It MEASURES; it does not refuse.** The ceilings are deliberately NOT passed, so both stay 0 —
    "not configured" — and no call is ever blocked here. The first version did pass them, and the
    user was right to call it out: turning a comment that had sat inert in ``policy.toml`` into an
    active refusal is a change in KIND, not a fix. It puts a limit on the user's own work, which is
    a policy act and therefore THEIR gesture (D92 / D74) — the system proposes, it never imposes,
    least of all on the person it serves. Worse, it was handed to them as a feature ("your sibling
    project's mandate becomes applicable") when what it actually did was throttle them: ~11 distillation
    calls, €0.25 of real spend, then a refusal.

    Measuring is the harmless half and the useful one: ``make depense`` can tell the truth about what
    was spent without anything being stopped. A caller that genuinely wants the brake passes
    ``cost_ceiling_eur`` / ``token_ceiling`` explicitly — and the day the user wants it on by
    default, that is one line here, added on their word rather than on mine.
    """
    return AnthropicBackend(
        client,
        model=model,
        max_tokens=max_tokens,
        max_retries=max_retries,
        ledger=SpendLedger(),
    )
