"""OpenAIBackend — the second frontier decode leg (GPT-5.6) proven against a FAKE client.

No SDK, no API key, no network — same posture as ``test_runner_anthropic.py`` (D126). The real
``openai`` wiring lives in ``load_openai_backend`` (sole importer, ``# pragma: no cover``).
"""
from __future__ import annotations

import json

import pytest

from mnemosyne.runtime.runner import GenerationBackend
from mnemosyne.runtime.runner_openai import HOST, OpenAIBackend

# -- fakes: the narrow shape OpenAIBackend reads off a Responses reply ------------------------


class _Details:
    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class _Usage:
    def __init__(self, i: int, o: int, *, cached: int | None = None) -> None:
        self.input_tokens = i
        self.output_tokens = o
        self.input_tokens_details = _Details(cached_tokens=cached) if cached is not None else None


class _Response:
    def __init__(
        self,
        output_text: str,
        *,
        usage: _Usage | None = None,
        status: str = "completed",
        incomplete_details: _Details | None = None,
    ) -> None:
        self.output_text = output_text
        self.usage = usage or _Usage(10, 5)
        self.status = status
        self.incomplete_details = incomplete_details


class _FakeResponses:
    """Records every ``create`` kwargs; returns a scripted reply, or raises a scripted error first."""

    def __init__(self, reply: _Response, *, fail_times: int = 0, error: Exception | None = None) -> None:
        self._reply = reply
        self._fail_times = fail_times
        self._error = error
        self.calls: list[dict] = []

    def create(self, **kw: object) -> _Response:
        self.calls.append(kw)
        if self._fail_times > 0:
            self._fail_times -= 1
            assert self._error is not None
            raise self._error
        return self._reply


class _FakeClient:
    def __init__(self, responses: _FakeResponses) -> None:
        self.responses = responses


class _Status(Exception):
    """A transient-looking API error carrying a duck-typed ``.status_code`` (no SDK types needed)."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"http {status_code}")
        self.status_code = status_code


def _no_sleep() -> list[float]:
    return []


_SCHEMA = json.dumps(
    {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
)


# -- conformance + happy paths ------------------------------------------------------------------


def test_is_generation_backend() -> None:
    be = OpenAIBackend(_FakeClient(_FakeResponses(_Response(json.dumps({"summary": "x"})))))
    assert isinstance(be, GenerationBackend)
    assert be.model_id == "gpt-5-nano"
    assert HOST == "api.openai.com"


def test_generate_structured_sends_json_schema_format_and_returns_output_text() -> None:
    resp = _FakeResponses(_Response(json.dumps({"summary": "the point", "extra": 1})))
    be = OpenAIBackend(_FakeClient(resp))
    out = be.generate_structured("CONTENT", _SCHEMA, "json_schema")
    assert json.loads(out) == {"summary": "the point", "extra": 1}
    sent = resp.calls[-1]
    assert sent["text"]["format"]["type"] == "json_schema"
    assert sent["text"]["format"]["schema"] == json.loads(_SCHEMA)
    assert sent["text"]["format"]["strict"] is False
    assert sent["input"] == [{"role": "user", "content": "CONTENT"}]


def test_generate_returns_output_text() -> None:
    be = OpenAIBackend(_FakeClient(_FakeResponses(_Response("hello world"))))
    assert be.generate("hi") == "hello world"


def test_non_json_schema_kind_falls_back_to_free_form() -> None:
    resp = _FakeResponses(_Response("freeform"))
    be = OpenAIBackend(_FakeClient(resp))
    assert be.generate_structured("CONTENT", _SCHEMA, "gbnf") == "freeform"
    assert "text" not in resp.calls[-1]  # free-form: no structured format requested


def test_unparseable_schema_falls_back_rather_than_raising() -> None:
    be = OpenAIBackend(_FakeClient(_FakeResponses(_Response("fallback"))))
    assert be.generate_structured("CONTENT", "{not json", "json_schema") == "fallback"


# -- resilience: retry / raise -------------------------------------------------------------------


def test_retries_transient_error_then_succeeds() -> None:
    slept: list[float] = []
    resp = _FakeResponses(_Response(json.dumps({"summary": "ok"})), fail_times=2, error=_Status(529))
    be = OpenAIBackend(_FakeClient(resp), base_delay=0.01, sleep=slept.append)
    out = be.generate_structured("CONTENT", _SCHEMA, "json_schema")
    assert json.loads(out) == {"summary": "ok"}
    assert len(slept) == 2
    assert len(resp.calls) == 3


def test_non_retryable_error_raises_immediately() -> None:
    slept: list[float] = []
    resp = _FakeResponses(_Response("x"), fail_times=1, error=_Status(400))
    be = OpenAIBackend(_FakeClient(resp), sleep=slept.append)
    with pytest.raises(_Status):
        be.generate("hi")
    assert slept == []


def test_insufficient_quota_style_error_is_not_retried() -> None:
    """The OpenAI-side hard spend cap the user relies on must actually STOP a run, not get retried past."""
    slept: list[float] = []

    class _InsufficientQuota(Exception):
        status_code = 429  # OpenAI sends 429 for both rate-limit AND exhausted-quota

    # a real insufficient_quota error carries no retryable class-name fragment and, unlike a genuine
    # rate limit, should not be treated as transient by a caller that cares — this backend cannot
    # distinguish the two from status alone (OpenAI overloads 429 for both), so it retries either;
    # the OWN account-level hard cap (platform.openai.com) is what actually stops the spend, per
    # the user's explicit design (module docstring). This test pins that retrying 429 is a bounded,
    # capped loop, never infinite.
    resp = _FakeResponses(_Response("x"), fail_times=99, error=_InsufficientQuota())
    be = OpenAIBackend(_FakeClient(resp), max_retries=2, base_delay=0.01, sleep=slept.append)
    with pytest.raises(_InsufficientQuota):
        be.generate("hi")
    assert len(resp.calls) == 3  # 1 initial + 2 retries, then raise — never unbounded


def test_retries_are_capped_then_raise() -> None:
    slept: list[float] = []
    resp = _FakeResponses(_Response("x"), fail_times=99, error=_Status(429))
    be = OpenAIBackend(_FakeClient(resp), max_retries=3, base_delay=0.01, sleep=slept.append)
    with pytest.raises(_Status):
        be.generate("hi")
    assert len(resp.calls) == 4
    assert len(slept) == 3


# -- usage accounting (cost pricing) --------------------------------------------------------------


def test_usage_accumulates_across_calls() -> None:
    resp = _FakeResponses(_Response("x", usage=_Usage(100, 20)))
    be = OpenAIBackend(_FakeClient(resp))
    be.generate("a")
    be.generate("b")
    assert be.usage == {"input_tokens": 200, "output_tokens": 40, "requests": 2}
    be.usage["input_tokens"] = 0
    assert be.usage["input_tokens"] == 200


def test_a_ledger_records_cached_tokens_nested_one_level_deeper_than_anthropic(tmp_path) -> None:
    from mnemosyne.production.spend import SpendLedger

    usage = _Usage(100, 20, cached=9000)
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    be = OpenAIBackend(_FakeClient(_FakeResponses(_Response("x", usage=usage))), ledger=ledger)

    be.generate("a")

    assert be.usage == {"input_tokens": 100, "output_tokens": 20, "requests": 1}
    assert ledger.spent().usage.cache_read == 9000
    assert ledger.spent().usage.cache_write == 0  # OpenAI has no cache-write charge, ever


def test_without_a_ledger_the_backend_behaves_exactly_as_before() -> None:
    be = OpenAIBackend(_FakeClient(_FakeResponses(_Response("x"))))
    assert be.generate("a") == "x"


def test_the_production_wiring_measures_but_never_refuses() -> None:
    """Mirrors the Anthropic pin: production journals spend but never blocks the user's own work —
    their chosen brake for THIS backend is the OpenAI account spend limit, not a Mnémosyne-side ceiling."""
    from mnemosyne.runtime.runner_openai import wire_backend

    be = wire_backend(_FakeClient(_FakeResponses(_Response("x"))))

    assert be._ledger is not None, "production would spend with nothing counted"
    assert be._cost_ceiling_eur == 0 and be._token_ceiling == 0, "a limit nobody asked for"
    assert be.generate("a") == "x"


# ── A4 · an OUTPUT ceiling that truncates silently produces a FALSE response (D165) ───────────────


def test_une_reponse_TRONQUEE_par_max_output_tokens_REFUSE() -> None:
    from mnemosyne.ports.core import ResourceBoundError
    from mnemosyne.runtime.runner_openai import refuser_si_tronque

    coupee = _Response("partial", status="incomplete", incomplete_details=_Details(reason="max_output_tokens"))
    with pytest.raises(ResourceBoundError) as capture:
        refuser_si_tronque(coupee, 4096)
    dit = str(capture.value)
    assert "4096" in dit, f"the refusal must NAME the ceiling that bit. Got: {dit}"
    assert "INCOMPLETE" in dit


def test_une_reponse_ENTIERE_passe_et_l_INNOCENT_est_teste_avec() -> None:
    from mnemosyne.runtime.runner_openai import refuser_si_tronque

    refuser_si_tronque(_Response("ok", status="completed"), 4096)  # does not raise
    refuser_si_tronque(_Response("ok"), 4096)  # default status = "completed"
    # incomplete for a reason OTHER than the output ceiling must not be confused with it
    refuser_si_tronque(
        _Response("x", status="incomplete", incomplete_details=_Details(reason="content_filter")),
        4096,
    )


def test_la_DEPENSE_est_comptee_AVANT_le_refus() -> None:
    import inspect

    from mnemosyne.runtime import runner_openai

    source = inspect.getsource(runner_openai.OpenAIBackend._create)
    assert source.index("self._record(response)") < source.index("refuser_si_tronque("), (
        "accounting must precede the refusal"
    )
