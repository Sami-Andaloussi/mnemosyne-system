"""AnthropicBackend - the frontier decode leg (Claude Haiku) proven against a FAKE client.

No SDK, no API key, no network: the retry / tool-use-parsing / usage-accounting CORE is exercised
here (D126), exactly like caption_anthropic's stub-tested core. The real ``anthropic`` wiring lives
in ``load_anthropic_backend`` (sole importer, ``# pragma: no cover``, confronted at the (3) smoke).
"""

from __future__ import annotations

import json

import pytest

from mnemosyne.runtime.runner import GenerationBackend
from mnemosyne.runtime.runner_anthropic import (
    HOST,
    _STRUCTURED_TOOL,
    AnthropicBackend,
)

# -- fakes: the narrow shape AnthropicBackend reads off a Messages reply ----------------------


class _Block:
    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class _Usage:
    def __init__(self, i: int, o: int) -> None:
        self.input_tokens = i
        self.output_tokens = o


class _Msg:
    def __init__(self, content: list[_Block], *, usage: _Usage | None = None) -> None:
        self.content = content
        self.usage = usage or _Usage(10, 5)


class _FakeMessages:
    """Records every ``create`` kwargs; returns a scripted reply, or raises a scripted error first."""

    def __init__(self, reply: _Msg, *, fail_times: int = 0, error: Exception | None = None) -> None:
        self._reply = reply
        self._fail_times = fail_times
        self._error = error
        self.calls: list[dict] = []

    def create(self, **kw: object) -> _Msg:
        self.calls.append(kw)
        if self._fail_times > 0:
            self._fail_times -= 1
            assert self._error is not None
            raise self._error
        return self._reply


class _FakeClient:
    def __init__(self, messages: _FakeMessages) -> None:
        self.messages = messages


class _Status(Exception):
    """A transient-looking API error carrying a duck-typed ``.status_code`` (no SDK types needed)."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"http {status_code}")
        self.status_code = status_code


def _tool_reply(payload: dict) -> _Msg:
    return _Msg([_Block(type="tool_use", name=_STRUCTURED_TOOL, input=payload)])


def _no_sleep() -> list[float]:
    """Return a list capturing every backoff sleep, so tests never actually wait."""
    return []


_SCHEMA = json.dumps(
    {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
)


# -- conformance + happy paths ----------------------------------------------------------------


def test_is_generation_backend() -> None:
    be = AnthropicBackend(_FakeClient(_FakeMessages(_tool_reply({"summary": "x"}))))
    assert isinstance(be, GenerationBackend)
    assert be.model_id == "claude-haiku-4-5"
    assert HOST == "api.anthropic.com"


def test_generate_structured_forces_the_tool_and_returns_its_input() -> None:
    msgs = _FakeMessages(_tool_reply({"summary": "the point", "extra": 1}))
    be = AnthropicBackend(_FakeClient(msgs))
    out = be.generate_structured("CONTENT", _SCHEMA, "json_schema")
    # returns the tool input as JSON (which LocalRunner.enforce_grammar re-validates)
    assert json.loads(out) == {"summary": "the point", "extra": 1}
    # the call FORCED our single tool with the passed schema as its input_schema
    sent = msgs.calls[-1]
    assert sent["tool_choice"] == {"type": "tool", "name": _STRUCTURED_TOOL}
    assert sent["tools"][0]["name"] == _STRUCTURED_TOOL
    assert sent["tools"][0]["input_schema"] == json.loads(_SCHEMA)
    assert sent["messages"] == [{"role": "user", "content": "CONTENT"}]


def test_generate_joins_text_blocks() -> None:
    msg = _Msg([_Block(type="text", text="hello "), _Block(type="text", text="world")])
    be = AnthropicBackend(_FakeClient(_FakeMessages(msg)))
    assert be.generate("hi") == "hello world"


def test_non_json_schema_kind_falls_back_to_free_form() -> None:
    msg = _Msg([_Block(type="text", text="freeform")])
    msgs = _FakeMessages(msg)
    be = AnthropicBackend(_FakeClient(msgs))
    assert be.generate_structured("CONTENT", _SCHEMA, "gbnf") == "freeform"
    # free-form: no tool forced
    assert "tools" not in msgs.calls[-1]


def test_unparseable_schema_falls_back_rather_than_raising() -> None:
    msg = _Msg([_Block(type="text", text="fallback")])
    be = AnthropicBackend(_FakeClient(_FakeMessages(msg)))
    assert be.generate_structured("CONTENT", "{not json", "json_schema") == "fallback"


# -- resilience: retry / raise ----------------------------------------------------------------


def test_retries_transient_error_then_succeeds() -> None:
    slept: list[float] = []
    msgs = _FakeMessages(_tool_reply({"summary": "ok"}), fail_times=2, error=_Status(529))
    be = AnthropicBackend(_FakeClient(msgs), base_delay=0.01, sleep=slept.append)
    out = be.generate_structured("CONTENT", _SCHEMA, "json_schema")
    assert json.loads(out) == {"summary": "ok"}
    assert len(slept) == 2  # slept once per transient failure
    assert len(msgs.calls) == 3  # 2 failed + 1 success


def test_non_retryable_error_raises_immediately() -> None:
    slept: list[float] = []
    msgs = _FakeMessages(_tool_reply({"summary": "x"}), fail_times=1, error=_Status(400))
    be = AnthropicBackend(_FakeClient(msgs), sleep=slept.append)
    with pytest.raises(_Status):
        be.generate("hi")
    assert slept == []  # a 400 is not transient - no backoff, no retry


def test_retries_are_capped_then_raise() -> None:
    slept: list[float] = []
    # always fails transiently; max_retries=3 -> 1 initial + 3 retries = 4 attempts, then raise
    msgs = _FakeMessages(_tool_reply({"summary": "x"}), fail_times=99, error=_Status(429))
    be = AnthropicBackend(_FakeClient(msgs), max_retries=3, base_delay=0.01, sleep=slept.append)
    with pytest.raises(_Status):
        be.generate("hi")
    assert len(msgs.calls) == 4
    assert len(slept) == 3


def test_missing_tool_block_raises_for_the_section_net() -> None:
    # a reply with no tool_use block (e.g. a refusal) -> RuntimeError, caught upstream by the D85 net
    msg = _Msg([_Block(type="text", text="I cannot")])
    be = AnthropicBackend(_FakeClient(_FakeMessages(msg)))
    with pytest.raises(RuntimeError, match="tool_use"):
        be.generate_structured("CONTENT", _SCHEMA, "json_schema")


# -- usage accounting (cost pricing) ----------------------------------------------------------


def test_usage_accumulates_across_calls() -> None:
    msgs = _FakeMessages(_Msg([_Block(type="text", text="x")], usage=_Usage(100, 20)))
    be = AnthropicBackend(_FakeClient(msgs))
    be.generate("a")
    be.generate("b")
    assert be.usage == {"input_tokens": 200, "output_tokens": 40, "requests": 2}
    # the returned dict is a COPY - mutating it does not corrupt the running tally
    be.usage["input_tokens"] = 0
    assert be.usage["input_tokens"] == 200


# -- D155: the durable ledger + the ceilings that policy.toml declared and nobody read ----------


def test_a_ledger_records_the_four_token_classes_where_the_ram_tally_only_sees_two(
    tmp_path,
) -> None:
    """The RAM tally keeps its old shape for existing readers; the ledger gets the real split."""
    from mnemosyne.production.spend import SpendLedger

    usage = _Usage(100, 20)
    usage.cache_read_input_tokens = 9000
    usage.cache_creation_input_tokens = 400
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    be = AnthropicBackend(
        _FakeClient(_FakeMessages(_Msg([_Block(type="text", text="x")], usage=usage))),
        ledger=ledger,
    )

    be.generate("a")

    assert be.usage == {"input_tokens": 100, "output_tokens": 20, "requests": 1}
    assert (
        ledger.spent().usage.cache_read == 9000
    )  # invisible to the RAM tally, priced by the ledger


def test_the_ceiling_refuses_the_NEXT_call_and_never_reaches_the_api(tmp_path) -> None:
    """Enforcement must sit before the request. A ceiling checked afterwards is a report."""
    from mnemosyne.production.spend import CanonicalUsage, SpendLedger
    from mnemosyne.guard.bounds import ResourceBoundError

    ledger = SpendLedger(tmp_path / "spend.jsonl")
    ledger.record(
        "claude-opus-4-8", CanonicalUsage(input=2_000_000)
    )  # ~ 9,20 EUR, over a 5 EUR cap
    msgs = _FakeMessages(_Msg([_Block(type="text", text="x")]))
    be = AnthropicBackend(_FakeClient(msgs), ledger=ledger, cost_ceiling_eur=5.0)

    with pytest.raises(ResourceBoundError):
        be.generate("a")
    assert msgs.calls == []  # the money was never spent


def test_without_a_ledger_the_backend_behaves_exactly_as_before() -> None:
    """Zero regression: every existing construction site keeps working, and never blocks."""
    msgs = _FakeMessages(_Msg([_Block(type="text", text="x")]))
    be = AnthropicBackend(_FakeClient(msgs))

    assert be.generate("a") == "x"
    assert len(msgs.calls) == 1


def test_the_production_wiring_measures_but_never_refuses() -> None:
    """Both halves of a lesson, pinned where they can be seen.

    `load_anthropic_backend` is `# pragma: no cover` - it imports the SDK and reads operator's key - so
    the line that decides what production does was invisible to every test. `wire_backend` is that
    line, extracted.

    It MUST journal (the audit's blocker: production used to pass `ledger=None`, so nothing was
    counted). It MUST NOT block: shipping an active ceiling on operator-managed work was a limit imposed
    without asking - "propose, never impose" applies to him first of all. Measuring is harmless and
    useful; refusing is his gesture to make.
    """
    from mnemosyne.runtime.runner_anthropic import wire_backend

    be = wire_backend(_FakeClient(_FakeMessages(_Msg([_Block(type="text", text="x")]))))

    assert be._ledger is not None, "production would spend with nothing counted"
    assert be._cost_ceiling_eur == 0 and be._token_ceiling == 0, "a limit nobody asked for"
    assert be.generate("a") == "x"  # and it actually runs


# -- A4  -  an OUTPUT ceiling that cuts off in silence produces a FALSE response (D165) ------------


def test_une_reponse_TRONQUEE_par_le_plafond_de_sortie_REFUSE(_unused: None = None) -> None:
    """THE DEFECT MEASURED ON 2026-08-09: this runner called `messages.create(max_tokens=4096)`
    and NEVER read `stop_reason`. A response cut off mid-word arrived at the caller with
    the exact appearance of a complete response. *A refusal is read, an emptiness is believed* - and an
    incomplete response consumed as whole is worse than an empty one."""
    from mnemosyne.ports.core import ResourceBoundError
    from mnemosyne.runtime.runner_anthropic import refuser_si_tronque

    coupee = _Block(stop_reason="max_tokens")
    with pytest.raises(ResourceBoundError) as capture:
        refuser_si_tronque(coupee, 4096)
    dit = str(capture.value)
    assert "4096" in dit, f"the refusal must NAME the ceiling that bit. Saw: {dit}"
    assert "INCOMPLETE" in dit, "the refusal must say it is incomplete, not merely short"


def test_une_reponse_ENTIERE_passe_et_l_INNOCENT_est_teste_avec(_unused: None = None) -> None:
    """Without this witness, a refusal that ALWAYS raised would also pass the test above."""
    from mnemosyne.runtime.runner_anthropic import refuser_si_tronque

    for fin in ("end_turn", "tool_use", "stop_sequence", None):
        refuser_si_tronque(_Block(stop_reason=fin), 4096)  # does not raise
    refuser_si_tronque(_Block(), 4096)  # an object with no stop_reason at all


def test_la_DEPENSE_est_comptee_AVANT_le_refus(_unused: None = None) -> None:
    """THE ORDER IS THE CONTROL. The tokens really were spent: refusing before recording
    them in the ledger would erase real spend from the books (D155/D86)."""
    import inspect

    from mnemosyne.runtime import runner_anthropic

    source = inspect.getsource(runner_anthropic.AnthropicBackend._create)
    assert source.index("self._record(message)") < source.index("refuser_si_tronque("), (
        "the accounting must precede the refusal"
    )
