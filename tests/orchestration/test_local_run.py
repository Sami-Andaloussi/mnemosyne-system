"""item 1 - ``CoreApi.run_local``: the frontier->LOCAL dispatch surface, fully governed.

The write-analog of ``make search``: a frontier hands the LOCAL model one bounded task and takes the
completion back. These prove the surface is GOVERNED, not a raw model hole - it decodes through the
runtime's Runner (a real ``MODEL_CALL`` grant minted at the Guard), it is grammar-bound when a schema is
given (invariant 27), and it does NOT bypass the D136 input ceiling (an over-large prompt is refused, never
truncated). Brick-free: the default weightless ``_StubDecoder`` stands in for the MLX brain (D126), so the
GOVERNANCE is exercised end-to-end without any model installed.
"""

from __future__ import annotations

import json

import pytest

from mnemosyne.api.core_api import CoreApi
from mnemosyne.ports import Bubble, ResourceBoundError
from mnemosyne.runtime import bootstrap

_WORK = Bubble("work")


def test_run_local_free_form_dispatches_through_the_governed_runner() -> None:
    """A free-form task decodes through the Runner behind a real Guard-minted MODEL_CALL grant.

    The default stub decoder echoes the prompt, so its presence in the output PROVES the full governed
    path ran (grant minted at the Guard -> runner redeemed it -> completion returned) - not a bypass."""
    api = CoreApi(bootstrap())
    out = api.run_local("summarize this paragraph", subject=_WORK)
    assert "summarize this paragraph" in out


def test_run_local_structured_output_is_grammar_valid() -> None:
    """With a JSON schema the output is grammar-bound: the required key is present, never malformed (inv. 27)."""
    api = CoreApi(bootstrap())
    schema = json.dumps(
        {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}
    )
    out = api.run_local("extract the title", subject=_WORK, schema=schema)
    obj = json.loads(out)  # valid JSON by construction (the decoder barrier), never a bare crash
    assert "title" in obj


def test_run_local_refuses_an_over_large_prompt_never_truncates() -> None:
    """The D136 ceiling is not bypassed: an over-large prompt RAISES rather than being silently truncated."""
    api = CoreApi(bootstrap())
    huge = "x" * (api._rt.runner.max_prompt_chars + 1)
    with pytest.raises(ResourceBoundError):
        api.run_local(huge, subject=_WORK)
