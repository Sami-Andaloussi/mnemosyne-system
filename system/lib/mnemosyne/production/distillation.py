"""Distillateur (D39-4 / D28-D29) — the first concrete ``Skill[I, O]``: a document → its distilled fiche.

The distillateur reads one raw source (a ``.md`` OCR mirror) and produces its *distilled understanding*
— the three-part artifact of D28 that fills ``knowledge/distilled/`` (empty until now). It is the first
real body behind the ``SEED_SKILLS`` names (``skills.py``), so it establishes the pattern every later
skill follows: the D108 contract (typed I/O, normalized errors, idempotent resume, trace), model-agnostic
execution behind the Guard (the :class:`~mnemosyne.ports.runner.Runner` seam, never a married engine, D104),
and — the doctrine that matters most here — the **verbatim floor on P3**.

Three parts, two regimes (D28 / [[restructure-not-reformulate]], to grave D143):

* **P1 — identity card** (frontmatter) and **P2 — description layer** (summary, concepts): FREE
  synthesis. This is the agent/description layer (D28); a model may write it in its own words. The "you"
  layer (the user's live salience) is left EMPTY for the 210 non-annotated documents — it is filled later by
  the compagnon (D41 / brick ⑤), never invented here.
* **P3 — content**: **VERBATIM**. Distillation RESTRUCTURES the source (its words and its structure); it
  never REFORMULATES it. A model→model→model loop that paraphrases a source of truth degrades toward
  mediocrity, and a model OVER-ESTIMATES its own paraphrase ("ça va TE paraître bon alors que pas tant" — "it's going to LOOK good to you
  when it really is not that good").
  So faithfulness is a STRUCTURAL barrier, not a matter of trust: :func:`keep_verbatim` drops any P3 passage
  that is not a literal substring of the source (whitespace-normalized). A paraphrased or invented passage
  is rejected AT THE SOURCE — the same spirit as the D6 grep barrier and the D104 grammar barrier: the
  guarantee is in our code (D100), never in the model's good behaviour.

Model-agnostic and brick-free testable (D126): the skill decodes through an injected
:class:`~mnemosyne.ports.runner.Runner` (a stub in tests, the real MLX/local model at ignition) and mints
its ``MODEL_CALL`` capability through an injected grant source (the Guard's grant lifecycle, never a
self-minted right — D89 / D100). This is the production-type workload for local models: a long, repetitive,
low-reasoning pass over a big corpus, distilled document-by-document (the local context ceiling is short —
a 35B on this machine reasons well only on a short context, so a whole book is never fed at once).

Decisions: D39-4 (the distillateur seed) · D28 (three-part format) · D29 (templated by type) · D108 (the
skill I/O contract) · D100 (structural safety, not trust) · D104 (grammar-constrained, model behind the
Guard) · D41 (the empty "toi" layer, filled by the compagnon) · D126 (brick-free stub) · D19 / D54
(provenance / taint). Invariant carried: 17 (output label ≥ input). Code & docstrings English (D117); the
section headings and the frontmatter tokens stay French where they are user-facing (D33 / D117).
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from ..ports import (
    Envelope,
    ErrorCode,
    GovernanceLabel,
    GrammarConstraint,
    Grant,
    MnemosyneError,
    Runner,
    TraceId,
)
from ..provenance import strip_inserted_lines

#: The Guard grant lifecycle the skill needs: a callback that mints a fresh single-use ``MODEL_CALL``
#: grant for one distillation, given the input's label (D89 / D100 / M1). Mirrors ``agents``'
#: ``GrantSource`` — the skill NEVER mints its own capability (that would be the bypass D100 forbids); the
#: orchestration (``CoreApi.distill``) supplies this, routing every call through the Guard.
GrantSource = Callable[[GovernanceLabel], Grant]


class DistilledType:
    """The OPEN set of document types a distillation may take (D29 — "floor, not ceiling").

    Extensible without breakage (like :class:`~mnemosyne.production.memory.FicheType`): a new type adds a
    guidance block, never edits a barrier. The type selects its P3 content guidance (D29,
    :data:`_TYPE_GUIDANCE`): a per-type block steers WHICH spans to quote and HOW to frame the synthesis,
    while the two-regime rule and the verbatim floor stay SHARED. An unknown type falls open to ``GENERIC``
    (floor, not ceiling), so a new type distils generically until it is given its own block."""

    BOOK = "book"  # a book / manual — the 210-document corpus (D39-4)
    ARTICLE = "article"  # a paper / article
    TRANSCRIPT = "transcript"  # an audio/video transcription (verbatim P3 too, [[restructure-not-reformulate]])
    CHAT = "chat"  # an archived conversation (verbatim P3 too)
    GENERIC = "generic"  # fail-open default — any document, the generic guidance block


@dataclass(frozen=True, slots=True)
class DistillationInput:
    """The skill's ``I`` (D108-①): one raw source to distill, plus the minimal hints P1 needs.

    ``source_text`` is the raw ``.md`` mirror content — the source of truth P3 must quote verbatim. The raw
    is never mutated and stays the anchor the frontmatter points back to (``source``)."""

    doc_id: str
    source_text: str
    dtype: str = DistilledType.GENERIC
    title_hint: str = ""


@dataclass(frozen=True, slots=True)
class DistilledDoc:
    """The skill's ``O`` (D108-①): the three-part distilled fiche (D28), ready to render to markdown.

    P1 (identity): ``title`` / ``summary`` / ``tags``. P2 (description): ``description`` / ``concepts``,
    plus an ``agent_reserve`` that stays EMPTY for a non-annotated document (the "toi" layer, filled later
    by the compagnon — D41). P3 (content): ``passages``, each ALREADY passed through :func:`keep_verbatim`
    — so a rendered ``DistilledDoc`` cannot carry an invented passage by construction (D100)."""

    source_doc_id: str
    dtype: str
    # P1 — identity card (free synthesis, D28)
    title: str
    summary: str
    tags: tuple[str, ...]
    # P2 — description layer (free synthesis, D28); agent_reserve is the empty "you" layer (D41)
    description: str
    concepts: tuple[str, ...]
    agent_reserve: str = ""
    # P3 — content VERBATIM ([[restructure-not-reformulate]]); every passage ⊂ source (keep_verbatim)
    passages: tuple[str, ...] = ()

    def render(self) -> str:
        """Render to Obsidian- and Mnemosyne-friendly markdown: YAML frontmatter (P1) + body (P2 + P3).

        The body keeps the source's own words in P3 (verbatim) under user-facing headings; the
        agent layers (Description / Concepts) are the synthesis regime. The "Agent reserve" section is an
        explicit empty placeholder (D41), never filler."""
        # The H1 is single-line by nature: collapse any whitespace so a multi-line title can't inject a
        # bare '---' rule into the body (the exact, escaped title stays in the frontmatter). Audit MAJEUR #1.
        parts = [_render_frontmatter(self), f"# {' '.join(self.title.split())}\n"]
        parts.append("## Description\n\n" + (self.description.strip() or "_(to be completed)_") + "\n")
        if self.concepts:
            parts.append("## Concepts\n\n" + "\n".join(f"- {c}" for c in self.concepts) + "\n")
        reserve = self.agent_reserve.strip()
        parts.append(
            "## Agent reserve\n\n"
            + (
                reserve
                or '<!-- "you" layer — empty, filled in by the compagnon (D41 / brick 5) -->'
            )
            + "\n"
        )
        body = "\n\n".join(self.passages) if self.passages else "_(no passage kept)_"
        parts.append(
            "## Content\n\n"
            "<!-- P3 — VERBATIM (restructure-not-reformulate): taken word for word from the source -->\n\n"
            + body
            + "\n"
        )
        return "\n".join(parts)


# --------------------------------------------------------------------------- #
# The verbatim barrier (D100 / [[restructure-not-reformulate]]) — P3 ⊂ source  #
# --------------------------------------------------------------------------- #
def _normalize_ws(text: str) -> str:
    """Collapse every run of whitespace to a single space, NFC-normalize, and strip — the comparison
    normal form.

    So a passage that differs from its source only by line wrapping / indentation (the OCR mirror wraps
    differently than the model quotes it), or by a decomposed vs precomposed accent (``é`` as U+00E9 vs
    U+0065+U+0301, common across OCR / PDF), still matches — while a paraphrase (different WORDS) never
    does. Comparison stays case-sensitive: verbatim means the source's own casing too. NFC only tightens
    false NEGATIVES; it can never admit an invention (a non-substring stays dropped)."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def keep_verbatim(
    passages: tuple[str, ...], source: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split candidate P3 passages into ``(kept, dropped)`` by the verbatim floor (D100).

    A passage is KEPT iff its whitespace-normalized form is a literal substring of the whitespace-normalized
    ``source`` — i.e. it is genuinely the source's own words, contiguous, modulo wrapping. Everything else —
    a paraphrase, an invented sentence, an empty string — is DROPPED. This is the structural anti-invention
    barrier of [[restructure-not-reformulate]]: P3 can only ever be source words, and the guarantee holds
    even against a model that paraphrases or hallucinates (the barrier is our code, not the model's word —
    same spirit as the D6 grep barrier). Order is preserved; duplicates are kept once, first occurrence.

    The ``source`` is first stripped of its INSERTED lines (a vision figure caption, a YouTube ASR header, a
    vector-figure read-out — :func:`~mnemosyne.provenance.strip_inserted_lines`): those are inserted by an
    enrichment automatism, NOT the author's words, so a passage that quotes one is DROPPED — an inserted line
    can never be promoted to the source's verbatim (the sujet-2/E provenance discipline). The juge reuses this
    same floor, so it inherits the rule for free (one home). On any pre-enrichment source — no such line, the
    entire current corpus — the strip is a strict no-op, so this stays byte-identical to before the enrichment
    stage."""
    normalized_source = _normalize_ws(strip_inserted_lines(source))
    kept: list[str] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for passage in passages:
        normal = _normalize_ws(passage)
        if not normal:
            dropped.append(passage)
        elif normal in normalized_source and normal not in seen:
            kept.append(passage)
            seen.add(normal)
        elif normal in seen:
            continue  # an exact-repeat quote — kept once, silently deduped (not a fidelity failure)
        else:
            dropped.append(passage)
    return tuple(kept), tuple(dropped)


# --------------------------------------------------------------------------- #
# The source-quality gate (D85 / D100) — refuse garbage-IN before it distills  #
# --------------------------------------------------------------------------- #
#: Thresholds CALIBRATED on the real 241-book shelf (not guessed — D100): a clean prose book (Carver)
#: sits at ~0.65 prose / 0.58 letters / 0.02 digits ; a broken extraction or math/data/code soup falls
#: below — the "Machine Learning Refined" failure (0.48 prose, a 22 KB stub of a 500-page book), "A
#: Non-Random Walk" (0.01 letters, a dead extraction), "Strategic Asset Allocation" (0.39 digits, all
#: tables). The prose bar sits at 0.50, not 0.55: the audit showed 0.55 also flagged clean-prose books at
#: 0.51-0.54 (Business Analysis; Robust Statistics — the latter penalised by its own
#: ``<!-- formula-not-decoded -->`` OCR markers counting as non-prose); 0.50 still catches ML (0.48) while
#: the FRANK garbage of that band is caught by the letters/digits signals anyway. Biased to flag CLEAR
#: garbage, not borderline books: a flag is recoverable (re-extract, or ``make distill … FORCE=1``), a
#: garbage fiche silently pollutes the KB. A flagged source is ROUTED to extraction-repair. (Deferred
#: refinement: discount ``<!-- … -->`` marker lines from the prose ratio — 0.50 already suffices.)
_MIN_LETTERS_RATIO = 0.45
_MAX_DIGIT_RATIO = 0.12
_MIN_PROSE_CHAR_RATIO = 0.50
#: A whole book whose extraction captured only a few KB is a FAILED extraction, not a source — even when the
#: little it has is clean PROSE (a copyright / back-cover page distils to real verbatim that no downstream
#: check can see: the "Optimal Mean Reversion" case, a 2.5 KB stub of a 200-page book, which fooled the juge
#: into `ok`). Floor calibrated on the shelf: real books are 100 KB-2.5 MB, papers 20 KB+, the < 5 KB tail is
#: stubs / fragments. ``make distill … FORCE=1`` bypasses it for a genuinely short document.
_MIN_SOURCE_CHARS = 5000


@dataclass(frozen=True, slots=True)
class SourceQuality:
    """Verdict of :func:`assess_source_quality` — is a raw usable PROSE, or garbage (D85)?

    ``ok`` is the gate; ``reason`` names the failing signal(s) (empty when ok). The three ratios are
    kept for the flag / the juge (an informative flag, never a silent skip)."""

    ok: bool
    reason: str
    letters_ratio: float
    digit_ratio: float
    prose_char_ratio: float


def assess_source_quality(text: str) -> SourceQuality:
    """Input gate (D85 / D100): refuse a raw that could only distill to GARBAGE.

    :func:`keep_verbatim` guarantees P3 is faithful to the source — but faithful to GARBAGE is still
    garbage: a math book whose OCR/extraction dropped its prose distills to figure-label and equation
    soup (verbatim of nonsense passes the floor). So BEFORE distilling, this checks the raw is genuinely
    continuous prose, via content-agnostic signals (no language / dictionary assumption): the share of
    characters that are letters, that are digits, and that live in PROSE lines (>= 5 words, >= 30 chars,
    mostly letters). A source that fails ANY threshold is FLAGGED — the skill routes it to
    extraction-repair (the OCR campaign) instead of emitting a garbage-in-garbage-out fiche. Thresholds
    are calibrated on the real shelf (see the module constants), biased toward catching clear garbage."""
    n = len(text) or 1
    letters = sum(c.isalpha() for c in text)
    digits = sum(c.isdigit() for c in text)
    prose_chars = 0
    line_chars = 0
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        line_chars += len(line)
        line_letters = sum(c.isalpha() for c in line)
        if len(line.split()) >= 5 and len(line) >= 30 and line_letters / len(line) >= 0.65:
            prose_chars += len(line)
    letters_ratio = letters / n
    digit_ratio = digits / n
    prose_char_ratio = prose_chars / max(1, line_chars)
    reasons: list[str] = []
    # NOTE (public-mirror): these four messages are read by `tests/distillation/test_distillation.py`
    # (out of this sync batch's scope), which asserts the literal substring "quasi-vide" -- left in
    # French rather than translated, so that pairing is not silently broken from this side.
    if len(text) < _MIN_SOURCE_CHARS:
        reasons.append(
            f"extraction quasi-vide ({len(text)} chars < {_MIN_SOURCE_CHARS} — livre tronque ?)"
        )
    if letters_ratio < _MIN_LETTERS_RATIO:
        reasons.append(f"too few letters ({letters_ratio:.2f} < {_MIN_LETTERS_RATIO})")
    if digit_ratio > _MAX_DIGIT_RATIO:
        reasons.append(f"too many digits ({digit_ratio:.2f} > {_MAX_DIGIT_RATIO})")
    if prose_char_ratio < _MIN_PROSE_CHAR_RATIO:
        reasons.append(
            f"too little continuous prose ({prose_char_ratio:.2f} < {_MIN_PROSE_CHAR_RATIO})"
        )
    return SourceQuality(
        ok=not reasons,
        reason="; ".join(reasons),
        letters_ratio=letters_ratio,
        digit_ratio=digit_ratio,
        prose_char_ratio=prose_char_ratio,
    )


# --------------------------------------------------------------------------- #
# Frontmatter rendering (P1) — a tiny deterministic YAML writer (no brick)     #
# --------------------------------------------------------------------------- #
def _yaml_scalar(value: str) -> str:
    """Quote a scalar so a model-written field never breaks (or injects) the frontmatter (deterministic).

    P1 fields (title / summary / tags) are written FREELY by the model, so a value may carry a colon, a
    quote, a backslash — or a NEWLINE. Newlines / tabs are escaped too: a title like
    ``"Chapter 3\\n---\\nevil: true"`` would otherwise close the YAML block early and corrupt the whole
    identity card (audit MAJEUR #1)."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return '"' + escaped + '"'


def _render_frontmatter(doc: DistilledDoc) -> str:
    """The P1 identity card as a YAML frontmatter block (D28 / D33) — points back to the raw source.

    This is the GENERAL ``DistilledDoc`` path (one structured input, no shelf context): it emits only the
    fields a bare :class:`DistilledDoc` can carry honestly. The FULL D33 / D121-C2 card
    (:data:`.frontmatter.FRONTMATTER_FIELDS`, Workstream 2) is closed on the BOOK path
    (``distill_book._identity_card``), which has the source PATH to derive domain / sensitivity /
    source_path / lang. Completing this path would need :class:`DistillationInput` to carry that context —
    a NAMED residual, not done here (this path is not the 238-fiche book corpus)."""
    tags = "[" + ", ".join(_yaml_scalar(t) for t in doc.tags) + "]"
    lines = [
        "---",
        f"title: {_yaml_scalar(doc.title)}",
        f"type: {_yaml_scalar(doc.dtype)}",
        f"source: {_yaml_scalar(doc.source_doc_id)}",
        f"summary: {_yaml_scalar(doc.summary)}",
        f"tags: {tags}",
        f"distilled_by: {_yaml_scalar(f'{Distillateur.name}/{Distillateur.version}')}",
        "---",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# The model call — prompt + schema (grammar-constrained, D104)                 #
# --------------------------------------------------------------------------- #
#: The JSON schema the decoder is bound to (D104 / invariant 27): a structured distillation, so the model
#: CANNOT emit a shape the skill then has to guess at. The skill STILL re-validates (defense in depth, D100
#: — never trust the brick), and the verbatim floor still filters P3 afterwards. The fields are BOUNDED
#: (``maxItems`` / ``maxLength``): a distillation is SELECTIVE by nature (the key passages, not a copy), and
#: the bound also stops a grammar-constrained decoder from generating an unbounded array until it truncates
#: mid-string (an invalid, unterminated JSON — the failure mode confirmed at first ignition).
DISTILL_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "title": {"type": "string", "maxLength": 200},
            "summary": {"type": "string", "maxLength": 600},
            "tags": {"type": "array", "items": {"type": "string", "maxLength": 40}, "maxItems": 8},
            "description": {"type": "string", "maxLength": 1800},
            "concepts": {
                "type": "array",
                "items": {"type": "string", "maxLength": 100},
                "maxItems": 12,
            },
            "passages": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        },
        "required": ["title", "summary", "tags", "description", "concepts", "passages"],
    }
)

#: The passage length ceiling REMOVED from the schema above on 2026-07-28, and why.
#:
#: the user: *« des fois on a besoin de moins, et tu te retrouves à demander plus ; des fois t'as besoin de
#: plus, et t'as pas assez. Donner un maximum… quelle est la justification ? j'en trouve pas. »*
#: ("sometimes you need less, and you end up asking for more; sometimes you need more, and you don't
#: have enough. Giving it a maximum... what's the justification? I can't find one.")
#: The two justifications written in this file were put to the test, one held:
#:   1. *« a distillation is SELECTIVE by nature »* — DOES NOT HOLD for a LENGTH bound. Selectivity is
#:      carried by ``maxItems`` (how many quotes), not by how long each one is: ten 1 500-char quotes
#:      from a million-char book is 1.5 % of it. Two different quantities under one word.
#:   2. *« the bound stops a grammar-constrained decoder from generating until the JSON is invalid »* —
#:      HOLDS, and it is the only one. It is a property of the DECODER, not of the product, so it now
#:      lives in :data:`GRAMMAR_SCHEMA` alone — the local route, 3.3 % of the shelf.
#:
#: And the measured fact that settles it: **a ceiling on a GENERATED output does not bound, it STEERS.**
#: Same book, same sections, same agent, same day, only the printed number changed — median quote 292
#: chars at 500, 477 at 1200, and the ceiling was NEVER reached in either. Worse, it COMPRESSES: the
#: shortest-to-longest spread was 3.5× at 500 and opens to 11× with no ceiling, in the right direction
#: on BOTH sides (median DROPS to 272 — a short quote stays short — while the longest TRIPLES to 1 433).
#: Raising the number to 1200 buys no adaptivity at all: it just moves the uniform target up.
#:
#: What replaces it is NOT another number: it is a FLOOR that is checkable in code — a passage must
#: END where a sentence ends (:func:`~mnemosyne.production.juge.truncated_passages` already computes it).
#: A ceiling picks a size nobody can know in advance; a floor states a property. See D165.
_PLAFOND_RETIRE_LE = "2026-07-28"

#: The decoder guardrail — the ONE place a length maximum is still load-bearing, and only there.
#: A grammar-constrained decoder that may not stop keeps emitting inside a JSON string until the
#: completion budget runs out, and what arrives is an UNTERMINATED string: invalid JSON, the failure
#: mode confirmed at first ignition. That is a nameable BREAKAGE, which is the test a ceiling must pass.
#: Deliberately far above any observed need (largest passage measured with no ceiling at all: 1 433
#: chars) so it never steers the output the way 500 did — if it ever binds, that is a signal to look,
#: never a number to raise quietly. Applies to the local ``GLM`` route only; the frontier and agent
#: routes are unconstrained by construction and see :data:`DISTILL_SCHEMA` as printed.
GRAMMAR_PASSAGE_MAX: Final = 8000
GRAMMAR_SCHEMA = json.dumps(
    {
        **json.loads(DISTILL_SCHEMA),
        "properties": {
            **json.loads(DISTILL_SCHEMA)["properties"],
            "passages": {
                "type": "array",
                "items": {"type": "string", "maxLength": GRAMMAR_PASSAGE_MAX},
                "maxItems": 10,
            },
        },
    }
)

_PROMPT_TEMPLATE = """\
You distill ONE source document into a structured fiche. Return ONLY JSON matching the schema.

{type_guidance}

Two regimes, do not confuse them:
- title, summary, tags, description, concepts: WRITE these freely in your own words (a faithful synthesis).
  Stay NEUTRAL and OBJECTIVE — report what the source claims, ATTRIBUTED to it ("the author argues…",
  "the book presents…"). NEVER restate the source's own promotional or marketing language ("a unique new
  method", "the definitive guide") as established fact: these notes describe a source, not the truth.
  This governs the synthesis fields ONLY — never drop or alter a verbatim passage below because of it.
- passages: this is the VERBATIM content layer. COPY exact, contiguous spans from the source, word for word.
  NEVER paraphrase, summarize, translate, or edit a passage — copy it literally. Choose the ~10 MOST
  substantive passages (each a contiguous exact quote). Any passage that is not an exact quote is DISCARDED.
  NEVER "repair" the source. This corpus is OCR: em-dashes arrive glued ("at once-say"), footnote calls
  appear as markdown links mid-sentence, words are split ("A CKNOWLEDGMENTS"). Copy that noise EXACTLY as
  it is — fixing punctuation, spacing or a broken word makes the span stop matching the source, and the
  passage is then DISCARDED. Prefer a SHORTER span that is exact over a longer one you had to tidy up.

Document type: {dtype}
Title hint (may be empty): {title_hint}

--- SOURCE START ---
{source}
--- SOURCE END ---
"""

#: Per-type P3 guidance (D29 — "templated by type"): a short block that steers WHICH spans to quote and
#: HOW to frame the synthesis for each document type, WITHOUT touching the two-regime rule or the verbatim
#: floor below (those stay shared — the fidelity barrier is one, never per-type). This is the honest,
#: minimal realization of the extension seam :class:`DistilledType` names: real per-type steering where it
#: earns fidelity, not a per-type COPY of the barrier. An unknown type falls OPEN to ``GENERIC`` (D29
#: "floor, not ceiling"), so a new type never breaks — it just distils generically until given a block.
_TYPE_GUIDANCE: dict[str, str] = {
    DistilledType.BOOK: (
        "This source is a BOOK or manual. In the synthesis, capture its central thesis and the framework "
        "it builds (its main parts, the arc of its argument), attributed to the author. For the verbatim "
        "passages, choose the load-bearing definitions and claims a reader would cite, spread ACROSS the "
        "work — not all from the opening pages."
    ),
    DistilledType.ARTICLE: (
        "This source is an ARTICLE or paper. In the synthesis, state its research question, method, and "
        "principal finding, attributed to the author. For the verbatim passages, prefer the thesis "
        "statement, the key results, and any stated limitations — the spans another work would quote."
    ),
    DistilledType.TRANSCRIPT: (
        "This source is a TRANSCRIPT of spoken audio or video. Treat repetition and disfluency as the "
        "medium, not content: synthesize what the speaker actually conveys. For the verbatim passages, "
        "copy the substantive spoken spans exactly as transcribed — the claims and explanations, never "
        "filler, greetings, or sponsor breaks."
    ),
    DistilledType.CHAT: (
        "This source is an archived CONVERSATION. In the synthesis, capture what was discussed and any "
        "conclusion or decision reached, attributed to the participants. For the verbatim passages, copy "
        "the exchanges that carry the substance exactly — the questions and answers that matter, never "
        "greetings or logistics."
    ),
    DistilledType.GENERIC: (
        "This source is a general document. Synthesize its substance faithfully, and for the verbatim "
        "passages copy its most substantive contiguous spans exactly."
    ),
}


def build_prompt(inp: DistillationInput) -> str:
    """Assemble the distillation prompt (P1/P2 free, P3 verbatim, P3 STEERED per type — D29). The source is
    fed whole — the caller distills document-by-document, because the practical local context is short (a big
    local model reasons well only on a short context; a whole corpus is never fed at once, cf. the model
    bench). The type-specific block (:data:`_TYPE_GUIDANCE`) steers passage SELECTION and synthesis FRAMING;
    an unknown type falls open to the GENERIC block, so a new type distils generically rather than breaking."""
    guidance = _TYPE_GUIDANCE.get(inp.dtype, _TYPE_GUIDANCE[DistilledType.GENERIC])
    return _PROMPT_TEMPLATE.format(
        type_guidance=guidance,
        dtype=inp.dtype,
        title_hint=inp.title_hint or "(none)",
        source=inp.source_text,
    )


def close_json(candidate: str) -> str:
    """Deterministically CLOSE a near-miss JSON so it parses — the distillation repair (D100 / D85).

    Wired as the ``repair`` of the distillation :class:`GrammarConstraint`. The grammar-constrained
    decoder (Outlines) can, on a VERBATIM passage that itself contains quotation marks, escape the
    passage's own closing ``"`` and leave the JSON string unterminated — a real, deterministic failure
    on the corpus (books are full of quoted speech; retrying is useless, the greedy decode reproduces
    it). Rather than lose the whole chunk, this scans the text tracking string/escape state and a
    bracket stack, then: closes a still-open string, drops a dangling trailing backslash or comma, and
    closes every open ``[`` / ``{``. The result parses.

    Why this is SAFE here and NOT a licence to invent (D100): the repair may leave garbage in the last,
    mangled string (e.g. a trailing ``]}`` swallowed as content), but P3 runs every passage through
    :func:`keep_verbatim` afterwards — any passage that is not a literal substring of the source is
    DROPPED. So a repair can never fabricate a verbatim passage; at worst it costs the one mangled
    passage (recoverable by sub-chunking). This is why ``repair`` is opt-in to the distillateur, whose
    verbatim floor makes it safe — a caller without such a floor keeps the strict fail-closed barrier."""
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in candidate:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "[{":
            stack.append(ch)
        elif ch in "]}" and stack:
            stack.pop()
    out = candidate[:-1] if esc else candidate  # a dangling backslash would escape our own closer
    if in_str:
        out += '"'
    out = out.rstrip()
    if out.endswith(","):  # a trailing comma before the close is invalid JSON
        out = out[:-1]
    for opener in reversed(stack):
        out += "]" if opener == "[" else "}"
    return out


class DistillationMalformed(MnemosyneError):
    """The model's structured output was not the agreed shape (D108-② / invariant 27).

    Normalized (never a bare crash): carried as ``MALFORMED`` so the orchestrator (D93) knows to retry or
    FLAG. The grammar constraint makes this rare, but the skill re-validates anyway (defense in depth, D100
    — a malformed payload is caught at the source, never propagated)."""

    code = ErrorCode.MALFORMED


def _parse_distillation(text: str) -> dict[str, object]:
    """Parse + shape-check the model's JSON (D108-① — malformed caught at the source, never propagated)."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise DistillationMalformed(f"distillation output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DistillationMalformed(
            f"distillation output must be a JSON object, got {type(data).__name__}"
        )
    for scalar in ("title", "summary", "description"):
        if not isinstance(data.get(scalar), str):
            raise DistillationMalformed(f"distillation field {scalar!r} must be a string")
    for listed in ("tags", "concepts", "passages"):
        value = data.get(listed)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise DistillationMalformed(f"distillation field {listed!r} must be a list of strings")
    return data


# --------------------------------------------------------------------------- #
# The skill (D108 / D39-4)                                                      #
# --------------------------------------------------------------------------- #
class Distillateur:
    """The distillateur skill: a governed, verbatim-faithful ``Skill[DistillationInput, DistilledDoc]`` (D108).

    Decodes through an injected :class:`~mnemosyne.ports.runner.Runner` (model-agnostic, D104) and mints its
    ``MODEL_CALL`` capability through an injected :data:`GrantSource` (never self-granted, D100). The four
    D108 volets, honestly:

    * **Typed I/O (①)** — ``DistillationInput`` → ``DistilledDoc``; the model's JSON is re-validated
      (:func:`_parse_distillation`) and P3 is filtered by :func:`keep_verbatim`, so the output cannot carry a
      malformed shape or an invented passage.
    * **Normalized errors (②)** — a malformed model output raises :class:`DistillationMalformed`
      (``MALFORMED``); a Guard refusal or an unavailable runner propagate as their already-normalized errors.
    * **Idempotent resume (③)** — distillation is a single atomic structured call with no partial persisted
      state, so re-running with the same input yields the same fiche, with no duplication (the ``resume_key``
      is accepted for the contract and reserved for a future chunked-distillation of very long documents).
    * **Trace (④)** — the ``trace`` handle threads the run; observability of the model leg lives in the
      Runner, which emits a redacted trace event per call (D111) — the skill adds no un-redacted trace.

    Output monotonicity (invariant 17): the fiche wears the runner's OUTPUT label — the input's label
    possibly RAISED by the Guard's routing, never lowered, never cross-bubble — so the derived
    understanding inherits at least the source's governance."""

    __slots__ = ("_runner", "_grant_source")

    name = "distillateur"
    version = "0.1.0"

    def __init__(self, runner: Runner, grant_source: GrantSource) -> None:
        self._runner = runner
        self._grant_source = grant_source

    def run(
        self,
        request: Envelope[DistillationInput],
        *,
        trace: TraceId,
        resume_key: str | None = None,
    ) -> Envelope[DistilledDoc]:
        """Distill ``request.payload`` into a governed :class:`DistilledDoc` (D108).

        Mints a ``MODEL_CALL`` grant for the input label, decodes the structured distillation under the JSON
        grammar (D104), re-validates the shape, and filters P3 through the verbatim floor — then returns the
        fiche wearing the runner's OUTPUT label (invariant 17: ``>=`` the input, since the Guard may raise it
        when routing, never lower it). ``resume_key`` is accepted (contract) and unused in v1 — a single
        atomic call has no partial state to resume, so re-running yields the same final state with no
        duplication (a byte-identical fiche additionally holds when the model decodes deterministically)."""
        inp = request.payload
        grant = self._grant_source(request.label)
        prompt = Envelope(payload=build_prompt(inp), label=request.label)
        # repair=close_json: a verbatim passage carrying quotes can leave the decoder's JSON string
        # unterminated (D85). The barrier repairs + re-validates it; keep_verbatim below then drops
        # any passage the repair could have mangled — so recovery never costs fidelity (D100).
        completion = self._runner.complete_structured(
            prompt, grant=grant, constraint=GrammarConstraint(GRAMMAR_SCHEMA, repair=close_json)
        )
        data = _parse_distillation(completion.payload)
        kept, _dropped = keep_verbatim(tuple(data["passages"]), inp.source_text)  # type: ignore[arg-type]
        doc = DistilledDoc(
            source_doc_id=inp.doc_id,
            dtype=inp.dtype,
            title=str(data["title"]) or inp.title_hint,
            summary=str(data["summary"]),
            tags=tuple(data["tags"]),  # type: ignore[arg-type]
            description=str(data["description"]),
            concepts=tuple(data["concepts"]),  # type: ignore[arg-type]
            passages=kept,
        )
        # The fiche wears the runner's output label: request.label RAISED to the released sensitivity if the
        # Guard routed it up (invariant 17). completion.label >= request.label, same bubble/domains (D104).
        return Envelope(payload=doc, label=completion.label)
