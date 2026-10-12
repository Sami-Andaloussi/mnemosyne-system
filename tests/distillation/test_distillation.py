"""Distillateur - the first concrete Skill[I,O], and its verbatim floor.

The property that makes this skill worth its weight, in the operator's own words:
**P3 is the source's own words, never a model paraphrase.** The structural proof is
:func:`test_p3_is_the_fidelity_floor_even_against_an_inventing_model` - under a runner that returns invented
passages, NONE survive; if one did, the model would have written the content layer (the mediocrity the
operator refuses). The barrier is our code (:func:`keep_verbatim`), not the model's good behaviour - the same
spirit as a grep-based barrier elsewhere in this codebase. The rest exercises the typed I/O contract
(normalized errors, idempotent resume, label monotonicity), the three-part render, and the Guard-mediated
``distill`` surface: a distillation is a MODEL_CALL that only ever crosses the frontier through the Guard.

Brick-free: the model leg is a stub runner, so the barriers are real and testable before any model
is installed.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import replace

from pytest import raises

from mnemosyne.api import CoreApi
from mnemosyne.ports import (
    Bubble,
    Effect,
    Envelope,
    ErrorCode,
    GovernanceLabel,
    Grant,
    GrammarConstraint,
    GuardDenied,
    GuardRequest,
    Sensitivity,
    TraceId,
)
from mnemosyne.production import (
    Distillateur,
    DistillationInput,
    DistillationMalformed,
    DistilledDoc,
    DistilledType,
    build_prompt,
    keep_verbatim,
)
from mnemosyne.production.distillation import _normalize_ws, assess_source_quality, close_json
from mnemosyne.runtime.bootstrap import bootstrap

# A realistic source of truth (a finance mirror, the corpus register) - one logical string so the tests
# are deterministic regardless of wrapping; keep_verbatim normalizes whitespace anyway.
_SOURCE = (
    "Risk management is the core of quantitative finance. "
    "A prudent investor diversifies across uncorrelated assets, measures volatility, "
    "and sizes each position so a single loss never threatens the whole portfolio. "
    "Value investing rests on a simple idea: buy a dollar for fifty cents. "
    "The margin of safety is the distance between price and intrinsic value."
)
_IN_SOURCE = "The margin of safety is the distance between price and intrinsic value."
_ALSO_IN_SOURCE = "A prudent investor diversifies across uncorrelated assets, measures volatility"
_INVENTED = "Buy low and sell high - a timeless maxim of the trade."

_SUBJECT = Bubble("agent-test")


def _label(sensitivity: Sensitivity = Sensitivity.SENSIBLE) -> GovernanceLabel:
    return GovernanceLabel(sensitivity=sensitivity, bubble=_SUBJECT)


def _bare_grant(label: GovernanceLabel) -> Grant:
    """A test-double grant (a bare shape - no Guard token; the stub runner never redeems it)."""
    return Grant(
        request=GuardRequest(
            effect=Effect.MODEL_CALL,
            subject=label.bubble,
            inputs=(label,),
            descriptor="test distill",
        ),
        released_label=label,
    )


class _StubRunner:
    """A weightless Runner double: returns a canned JSON completion, records what it was asked."""

    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.last_grant: Grant | None = None
        self.last_prompt: Envelope[str] | None = None
        self.last_constraint: GrammarConstraint | None = None

    def complete_structured(
        self, prompt: Envelope[str], *, grant: Grant, constraint: GrammarConstraint
    ) -> Envelope[str]:
        self.last_grant, self.last_prompt, self.last_constraint = grant, prompt, constraint
        return Envelope(payload=self._payload, label=prompt.label)

    def complete(
        self, prompt: Envelope[str], *, grant: Grant, constraint: GrammarConstraint | None = None
    ) -> Envelope[str]:
        return self.complete_structured(
            prompt, grant=grant, constraint=constraint or GrammarConstraint("{}")
        )


def _distillation_json(passages: list[str], **overrides: object) -> str:
    """A well-shaped distillation payload, with the passages the test wants to feed the barrier."""
    data: dict[str, object] = {
        "title": "Risk and Value",
        "summary": "Position sizing meets the margin of safety.",
        "tags": ["risk", "value-investing"],
        "description": "The document connects position sizing to the margin of safety.",
        "concepts": ["margin of safety", "position sizing"],
        "passages": passages,
    }
    data.update(overrides)
    return json.dumps(data)


def _skill(payload: str) -> tuple[Distillateur, _StubRunner]:
    runner = _StubRunner(payload)
    return Distillateur(runner, _bare_grant), runner


def _run(payload: str, *, dtype: str = DistilledType.GENERIC) -> DistilledDoc:
    skill, _ = _skill(payload)
    inp = DistillationInput(doc_id="library/deadbeef", source_text=_SOURCE, dtype=dtype)
    out = skill.run(Envelope(inp, _label()), trace=TraceId("t-distill"))
    return out.payload


# --------------------------------------------------------------------------- #
# The verbatim floor - the heart                                              #
# --------------------------------------------------------------------------- #
def test_keep_verbatim_keeps_source_substrings_and_drops_a_paraphrase() -> None:
    kept, dropped = keep_verbatim((_IN_SOURCE, _INVENTED, _ALSO_IN_SOURCE), _SOURCE)
    assert kept == (_IN_SOURCE, _ALSO_IN_SOURCE)  # order preserved
    assert dropped == (_INVENTED,)


def test_keep_verbatim_matches_across_whitespace_differences() -> None:
    # a quote re-wrapped with newlines / double spaces is still the SAME words -> kept (OCR wraps differ).
    rewrapped = "The margin of\nsafety  is the   distance between price and intrinsic value."
    kept, dropped = keep_verbatim((rewrapped,), _SOURCE)
    assert kept == (rewrapped,) and dropped == ()


def test_keep_verbatim_is_case_sensitive_and_drops_the_empty_string() -> None:
    lowered = (
        "the margin of safety is the distance between price and intrinsic value."  # 'the' vs 'The'
    )
    kept, dropped = keep_verbatim((lowered, "", "   "), _SOURCE)
    assert kept == ()  # verbatim means the source's own casing too
    assert dropped == (lowered, "", "   ")


def test_keep_verbatim_dedupes_a_repeated_quote() -> None:
    kept, _ = keep_verbatim((_IN_SOURCE, _IN_SOURCE), _SOURCE)
    assert kept == (_IN_SOURCE,)  # kept once, first occurrence


def test_keep_verbatim_matches_across_unicode_nfc_nfd() -> None:
    # audit MINEUR #2: a decomposed accent (e + combining acute) must still match a precomposed source
    # (OCR/PDF mix the two) - NFC tightens the false negative WITHOUT ever admitting an invention.
    source = "La theorie du portefeuille optimise le risque au fil du temps."
    source = source.replace("theorie", "théorie")  # precomposed e-acute (NFC)
    decomposed = unicodedata.normalize("NFD", source)  # e + U+0301
    assert decomposed != source  # genuinely different bytes
    kept, dropped = keep_verbatim((decomposed,), source)
    assert kept == (decomposed,) and dropped == ()


def test_p3_is_the_fidelity_floor_even_against_an_inventing_model() -> None:
    # THE doctrine test (= the bench "verbatim fidelity test"): a model that paraphrases everything
    # produces an EMPTY content layer - its invented prose can never become P3 (not trust).
    doc = _run(_distillation_json([_INVENTED, "Another fabricated sentence entirely."]))
    assert doc.passages == ()


def test_p3_passages_are_all_substrings_of_the_source() -> None:
    # structural invariant, checked on the assembled fiche: every surviving P3 passage is source words.
    doc = _run(_distillation_json([_IN_SOURCE, _INVENTED, _ALSO_IN_SOURCE]))
    assert doc.passages == (_IN_SOURCE, _ALSO_IN_SOURCE)
    normalized_source = _normalize_ws(_SOURCE)
    assert all(_normalize_ws(p) in normalized_source for p in doc.passages)


# --------------------------------------------------------------------------- #
# The decoder repair - close_json recovers a near-miss, floor stays unmoved      #
# --------------------------------------------------------------------------- #
def test_close_json_is_a_noop_on_already_valid_json() -> None:
    assert json.loads(close_json('{"a": "b", "c": [1, 2]}')) == {"a": "b", "c": [1, 2]}


def test_close_json_never_crashes_on_degenerate_input() -> None:
    # close_json must ALWAYS return a str - a total function: any leftover invalidity is caught downstream
    # by enforce_grammar (fail-closed), never by close_json raising. Covers the audit's pathological set.
    for bad in ("", '"', "{", "[", "\\", '"\\', "[[[", '{"a":', '{"a": "b",', "}]"):
        assert isinstance(close_json(bad), str)


def test_close_json_recovers_an_unterminated_verbatim_passage() -> None:
    # THE real corpus failure (chunk-7 shape): a verbatim passage carrying quotes leaves the decoder's
    # JSON string unterminated - its closing " got escaped as \", so the array/object closers that follow
    # are swallowed as string content. The barrier repairs it deterministically; the mangled passage is
    # then DROPPED by the verbatim floor, so recovery never fabricates a passage.
    mangled = (
        '{"title": "T", "summary": "s", "tags": [], "description": "d", "concepts": [], '
        '"passages": ["'
        + _IN_SOURCE
        + '", "As Einstein said, \\"leave elegance to the tailor.\\"] }'
    )
    with raises(json.JSONDecodeError):
        json.loads(mangled)  # genuinely broken (unterminated string)
    data = json.loads(close_json(mangled))  # now parses - the barrier's guarantee
    kept, dropped = keep_verbatim(tuple(data["passages"]), _SOURCE)
    assert _IN_SOURCE in kept  # the clean earlier passage survives
    assert len(dropped) == 1  # the repair-mangled tail passage cannot pass keep_verbatim


def test_distillateur_opts_into_json_repair() -> None:
    # The distillateur supplies repair=close_json: its verbatim floor is what makes recovery safe,
    # so it opts in where a floorless caller (e.g. a classifier) would keep the strict refusal.
    skill, runner = _skill(_distillation_json([_IN_SOURCE]))
    skill.run(
        Envelope(DistillationInput(doc_id="d", source_text=_SOURCE), _label()), trace=TraceId("t")
    )
    assert runner.last_constraint is not None
    assert runner.last_constraint.repair is close_json


# --------------------------------------------------------------------------- #
# The source-quality gate - refuse garbage-IN before it distills                #
# --------------------------------------------------------------------------- #
def test_assess_source_quality_passes_real_prose() -> None:
    q = assess_source_quality(
        _SOURCE * 15
    )  # a book-sized run of clean prose (above the size floor)
    assert q.ok and q.reason == ""


def test_assess_source_quality_flags_math_extraction_soup() -> None:
    # THE real failure (ML-Refined): a math book whose extraction is figure/equation soup - few letters,
    # many digits, no continuous prose. keep_verbatim would pass verbatim-OF-garbage; the gate refuses it.
    garbage = "\n".join(
        ["0/2 3Y56 7 8 9", "xTw =0", "-2 -2 -4 -4 8(20) 05 10 4.0 40", "run 3"] * 80
    )
    q = assess_source_quality(garbage)
    assert not q.ok and q.reason


def test_assess_source_quality_flags_a_dead_extraction() -> None:
    # almost no letters (symbols / whitespace) - a broken extraction, flagged on the letters signal.
    q = assess_source_quality("|||  ... === ---  ::: 12 34 56\n" * 200)
    assert not q.ok


def test_assess_source_quality_flags_a_tiny_extraction() -> None:
    # a whole book reduced to a few KB (front-matter only) is a FAILED extraction - the SIZE floor catches it
    # even when the little it has is clean prose (the "Optimal Mean Reversion" false-OK the juge cannot see).
    tiny = (
        "This book delves into the realm of financial engineering and mean reversion strategies. " * 25
    )
    q = assess_source_quality(tiny)  # ~2 KB of genuine prose, but far too little for a book
    assert not q.ok and "quasi-vide" in q.reason


# --------------------------------------------------------------------------- #
# The typed I/O contract - normalized errors, resume, monotonic label          #
# --------------------------------------------------------------------------- #
def test_distillateur_produces_the_three_part_fiche() -> None:
    doc = _run(_distillation_json([_IN_SOURCE]))
    # P1 identity (free synthesis)
    assert doc.title == "Risk and Value"
    assert doc.tags == ("risk", "value-investing")
    assert doc.source_doc_id == "library/deadbeef"
    # P2 description (free synthesis) - the "toi" layer stays empty, never invented
    assert doc.concepts == ("margin of safety", "position sizing")
    assert doc.agent_reserve == ""
    # P3 content (verbatim)
    assert doc.passages == (_IN_SOURCE,)


def test_distillateur_carries_the_input_label_forward() -> None:
    # The derived fiche inherits the source's governance - never lowered, never cross-bubble.
    skill, _ = _skill(_distillation_json([_IN_SOURCE]))
    inp = DistillationInput(doc_id="library/x", source_text=_SOURCE)
    out = skill.run(Envelope(inp, _label(Sensitivity.SENSIBLE)), trace=TraceId("t"))
    assert out.label.sensitivity is Sensitivity.SENSIBLE
    assert out.label.bubble == _SUBJECT


def test_distillateur_mints_a_model_call_grant_for_the_input_label() -> None:
    skill, runner = _skill(_distillation_json([_IN_SOURCE]))
    skill.run(
        Envelope(DistillationInput(doc_id="d", source_text=_SOURCE), _label()), trace=TraceId("t")
    )
    assert runner.last_grant is not None
    assert runner.last_grant.request.effect is Effect.MODEL_CALL
    assert runner.last_constraint is not None  # a structured call is grammar-bound


def test_distillateur_rejects_malformed_model_output() -> None:
    skill, _ = _skill("this is not json at all")
    with raises(DistillationMalformed) as exc:
        skill.run(
            Envelope(DistillationInput(doc_id="d", source_text=_SOURCE), _label()),
            trace=TraceId("t"),
        )
    assert exc.value.code is ErrorCode.MALFORMED


def test_distillateur_rejects_a_wrong_shape() -> None:
    # a JSON object whose 'passages' is not a list of strings is caught at the source, never propagated.
    wrong = json.dumps(
        {
            "title": "t",
            "summary": "s",
            "tags": [],
            "description": "d",
            "concepts": [],
            "passages": "not-a-list",
        }
    )
    skill, _ = _skill(wrong)
    with raises(DistillationMalformed):
        skill.run(
            Envelope(DistillationInput(doc_id="d", source_text=_SOURCE), _label()),
            trace=TraceId("t"),
        )


def test_distillateur_is_idempotent() -> None:
    payload = _distillation_json([_IN_SOURCE, _ALSO_IN_SOURCE])
    a = _run(payload)
    b = _run(payload)
    assert (
        a == b
    )  # a single atomic call -> same input yields the same fiche, no duplication


def test_build_prompt_carries_the_source_and_the_verbatim_instruction() -> None:
    inp = DistillationInput(doc_id="d", source_text=_SOURCE, dtype=DistilledType.BOOK)
    prompt = build_prompt(inp)
    assert _SOURCE in prompt
    assert "VERBATIM" in prompt and "paraphrase" in prompt.lower()
    assert DistilledType.BOOK in prompt


def test_build_prompt_steers_by_type_but_keeps_the_shared_verbatim_floor() -> None:
    # Each type gets its OWN P3 guidance (a distinct signature phrase), while the shared
    # verbatim-floor instruction stays in every one (the fidelity barrier is one, never per-type).
    signatures = {
        DistilledType.BOOK: "BOOK or manual",
        DistilledType.ARTICLE: "ARTICLE or paper",
        DistilledType.TRANSCRIPT: "TRANSCRIPT of spoken",
        DistilledType.CHAT: "archived CONVERSATION",
        DistilledType.GENERIC: "general document",
    }
    for dtype, signature in signatures.items():
        prompt = build_prompt(DistillationInput(doc_id="d", source_text=_SOURCE, dtype=dtype))
        assert signature in prompt  # this type's own steering block is present
        assert "COPY exact, contiguous spans" in prompt  # the shared verbatim floor rides along
        # a type never leaks ANOTHER type's steering block into its prompt
        others = [s for d, s in signatures.items() if d != dtype]
        assert not any(o in prompt for o in others)


def test_build_prompt_unknown_type_falls_open_to_generic() -> None:
    # "a floor, not a ceiling": an unknown type must not break - it distils with the GENERIC block.
    prompt = build_prompt(
        DistillationInput(doc_id="d", source_text=_SOURCE, dtype="not-a-real-type")
    )
    assert "general document" in prompt  # fell open to GENERIC guidance
    assert "BOOK or manual" not in prompt  # never a wrong-type block
    assert "COPY exact, contiguous spans" in prompt  # the verbatim floor still present


# --------------------------------------------------------------------------- #
# The three-part render - Obsidian- and Mnemosyne-friendly markdown            #
# --------------------------------------------------------------------------- #
def test_render_has_frontmatter_body_and_the_empty_agent_layer() -> None:
    doc = _run(_distillation_json([_IN_SOURCE]))
    md = doc.render()
    assert md.startswith("---\n")
    assert 'title: "Risk and Value"' in md
    assert 'source: "library/deadbeef"' in md
    assert "## Description" in md and "## Content" in md
    assert _IN_SOURCE in md  # the verbatim passage is present, unaltered
    # the "you" layer is an explicit empty placeholder, never filler
    assert "Agent reserve" in md and "compagnon" in md


def test_render_frontmatter_escapes_a_colon_in_the_title() -> None:
    # a title with a colon must not break the YAML frontmatter (deterministic quoting, no yaml brick).
    doc = _run(_distillation_json([_IN_SOURCE], title="Chapter 3: Risk"))
    md = doc.render()
    assert 'title: "Chapter 3: Risk"' in md


def test_render_frontmatter_escapes_newlines_and_never_breaks_the_block() -> None:
    # audit MAJEUR #1 regression: a model-written title carrying a newline + '---' must NOT close the YAML
    # block early. The newline is escaped, so the whole document has exactly ONE real frontmatter close.
    doc = _run(_distillation_json([_IN_SOURCE], title="Chapter 3\n---\nevil: true"))
    md = doc.render()
    assert (
        'title: "Chapter 3\\n---\\nevil: true"' in md
    )  # escaped onto ONE line, not a premature close
    assert (
        len(md.split("\n---\n")) == 2
    )  # only the frontmatter's own close delimiter (the bug -> 3 parts)


# --------------------------------------------------------------------------- #
# The Guard-mediated surface - distill only ever crosses via the Guard
# --------------------------------------------------------------------------- #
def test_coreapi_distill_routes_through_the_guard_and_returns_a_fiche() -> None:
    rt = bootstrap()
    stub = _StubRunner(_distillation_json([_IN_SOURCE, _INVENTED]))
    api = CoreApi(replace(rt, runner=stub))
    doc = api.distill(
        DistillationInput(doc_id="library/deadbeef", source_text=_SOURCE), subject=_SUBJECT
    )
    assert isinstance(doc, DistilledDoc)
    assert doc.passages == (_IN_SOURCE,)  # the invented passage was floored out
    # the model leg went through the Guard: the stub saw a real, sealed MODEL_CALL grant (M1).
    assert stub.last_grant is not None
    assert stub.last_grant.request.effect is Effect.MODEL_CALL
    assert stub.last_grant.token is not None  # a genuine Guard-minted seal, not a bare shape


def test_coreapi_distill_fails_closed_when_the_guard_denies() -> None:
    class _DenyAllGuard:
        def grant(self, request: object) -> Grant:
            raise GuardDenied("deny-all: distillation")

    rt = bootstrap()
    stub = _StubRunner(_distillation_json([_IN_SOURCE]))
    api = CoreApi(replace(rt, runner=stub, guard=_DenyAllGuard()))
    with raises(GuardDenied):
        api.distill(DistillationInput(doc_id="d", source_text=_SOURCE), subject=_SUBJECT)
    assert stub.last_grant is None  # no grant => the model was never called (fail-closed)
