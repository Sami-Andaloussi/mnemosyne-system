"""Provenance marks - an INSERTED line is never promoted to the source's verbatim.

The vision stage, YouTube auto-captions, and vector-figure extraction all INSERT
lines into a raw source that are not the author's words. These tests pin the barrier that keeps them out of P3:
:func:`strip_inserted_lines`
removes such lines, so :func:`keep_verbatim` (and the juge that reuses it) drops any passage quoting one -
even though the line really is a substring of the enriched raw. Producer != verifier: an isolated audit
checks this independently. Brick-free - no VLM, no network.

The coupling tests are the anti-drift guard: what the PRODUCERS write (weave_captions, transcript_to_markdown)
is exactly what the VERIFIER strips. If a mark changes on one side only, these break.
"""

from __future__ import annotations

from mnemosyne.ingest import transcript_to_markdown, weave_captions, weave_enrichments
from mnemosyne.ports import FetchedTranscript, TranscriptCue
from mnemosyne.production import JudgeStatus, judge_fiche, keep_verbatim
from mnemosyne.provenance import (
    AUTO_CAPTION_MARK,
    FIGURE_CAPTION_MARK,
    FIGURE_CLOUD_MARK,
    FIGURE_DATA_MARK,
    FIGURE_IMAGE_MARK,
    INSERTED_MARKS,
    strip_inserted_lines,
)

_BOOK = (
    "Risk management is the core of quantitative finance.\n"
    "A prudent investor diversifies across uncorrelated assets.\n"
    "Position sizing ensures a single loss never threatens the whole portfolio."
)


# --- the mask itself: strict no-op off, surgical on -------------------------------------------------


def test_strip_is_a_strict_noop_without_any_mark() -> None:
    # zero regression: a pre-enrichment source (the entire current corpus) is returned UNCHANGED, same object
    assert strip_inserted_lines(_BOOK) is _BOOK


def test_strip_removes_a_vision_caption_line_keeping_the_text_around_it() -> None:
    enriched = (
        "Before the figure.\n"
        f"> {FIGURE_CAPTION_MARK} A curve the model invented.\n"
        "After the figure."
    )
    out = strip_inserted_lines(enriched)
    assert FIGURE_CAPTION_MARK not in out
    assert "A curve the model invented." not in out
    assert "Before the figure." in out and "After the figure." in out


def test_strip_removes_a_youtube_header_but_keeps_the_transcript_body() -> None:
    # the YouTube mark is a HEADER: the transcript body below it is the legitimate source and must survive
    enriched = f"> {AUTO_CAPTION_MARK}\n\nHello this is the spoken transcript body."
    out = strip_inserted_lines(enriched)
    assert AUTO_CAPTION_MARK not in out
    assert "Hello this is the spoken transcript body." in out


def test_all_marks_are_registered_in_one_list() -> None:
    assert INSERTED_MARKS == (
        FIGURE_CAPTION_MARK,
        AUTO_CAPTION_MARK,
        FIGURE_DATA_MARK,
        FIGURE_CLOUD_MARK,
        FIGURE_IMAGE_MARK,
    )


def test_strip_removes_an_extracted_image_line_but_keeps_the_prose_around_it() -> None:
    # arc D: the line carries the figure ITSELF (a link to the PNG), not a description - but the LINE is
    # still ours, so the verbatim floor must refuse it exactly like a caption. Without this, our markdown
    # syntax and our "Figure N" alt could be promoted as the author's words.
    enriched = (
        "Before the figure.\n\n"
        f"> {FIGURE_IMAGE_MARK} ![Figure 4](book.figures/fig-003.png)  -  Curve(s)\n\n"
        "After the figure."
    )
    out = strip_inserted_lines(enriched)
    assert FIGURE_IMAGE_MARK not in out
    assert "fig-003.png" not in out
    assert "Before the figure." in out and "After the figure." in out


def test_strip_removes_a_frontier_cloud_caption_line() -> None:
    # the level-3 frontier caption is model-generated (an interpretation) -> masked from the verbatim floor
    enriched = f"Before.\n> {FIGURE_CLOUD_MARK} A curve described by the frontier model.\nAfter."
    out = strip_inserted_lines(enriched)
    assert FIGURE_CLOUD_MARK not in out
    assert "A curve described by the frontier model." not in out
    assert "Before." in out and "After." in out


def test_strip_is_normalization_proof_on_a_decomposed_source() -> None:
    # audit M1: an OCR/PDF source can arrive DECOMPOSED (NFD). The mark's accents (décrite/générée) must still
    # be caught - else the line survives the strip, then keep_verbatim's own NFC-fold makes the caption match
    # and it slips through. This is defense in depth: the barrier must not depend on the source's normal form.
    import unicodedata

    desc = "A hallucinated curve with no basis."
    nfd = unicodedata.normalize("NFD", f"Before.\n> {FIGURE_CAPTION_MARK} {desc}\nAfter.")
    out = strip_inserted_lines(nfd)
    assert desc not in out  # the marked line is gone despite the decomposed accents
    assert (
        keep_verbatim((desc,), nfd)[0] == ()
    )  # end to end: the caption is refused against the NFD source


# --- keep_verbatim inherits the barrier (the point: the guarantee is one home) ----------------------


def test_keep_verbatim_drops_a_passage_quoting_a_vision_caption() -> None:
    # the caption text IS a substring of the enriched raw, yet it must NOT survive the verbatim floor
    desc = "A curve the model invented out of thin air."
    enriched = _BOOK + f"\n\n> {FIGURE_CAPTION_MARK} {desc}\n"
    real = (
        "A prudent investor diversifies across uncorrelated assets."  # a genuine line of the book
    )
    kept, dropped = keep_verbatim((real, desc), enriched)
    assert kept == (real,)  # the author's words survive
    assert dropped == (desc,)  # the model's caption is refused, though it sits in the raw


def test_the_mark_not_the_text_is_what_disqualifies() -> None:
    # control isolating the cause: the SAME text, present as ordinary source prose (no mark), IS verbatim
    desc = "A curve the model invented out of thin air."
    plain = _BOOK + f"\n\n{desc}\n"  # same bytes, but not on a marked line
    kept, _dropped = keep_verbatim((desc,), plain)
    assert kept == (
        desc,
    )  # so the barrier keys on the MARK, never on the text - no collateral drop


# --- coupling producer <-> verifier (anti-drift): what is written is what is stripped ----------------


def test_a_woven_vision_caption_is_refused_by_the_floor() -> None:
    invented = "A totally invented description of a figure."
    woven = weave_captions("<!-- image -->", [invented])
    assert woven.startswith(f"> {FIGURE_CAPTION_MARK}")  # the producer wrote the marked line
    assert strip_inserted_lines(woven).strip() == ""  # the verifier strips it whole
    kept, dropped = keep_verbatim((invented,), woven)
    assert kept == () and dropped == (invented,)  # end to end: a VLM caption never becomes verbatim


def test_a_woven_figure_data_readout_is_refused_by_the_floor() -> None:
    # a vector-figure read-out is deterministic, but its characterization is OUR prose - the floor
    # must refuse it as verbatim exactly like a VLM caption (fail-closed)
    readout = "Histogram / bar chart - X axis in [0, 1] - height profile (0-100): 10, 50, 100"
    woven = weave_enrichments("<!-- image -->", [(FIGURE_DATA_MARK, readout)])
    assert woven.startswith(f"> {FIGURE_DATA_MARK}")  # the producer wrote the marked line
    assert strip_inserted_lines(woven).strip() == ""  # the verifier strips it whole
    kept, dropped = keep_verbatim((readout,), woven)
    assert kept == () and dropped == (
        readout,
    )  # end to end: a vector read-out never becomes verbatim


def test_a_youtube_auto_caption_header_is_stripped_by_the_floor() -> None:
    transcript = FetchedTranscript(
        video_id="abcdefghijk",
        title="A talk",
        uploader="A channel",
        webpage_url="https://youtu.be/abcdefghijk",
        language="en",
        auto_generated=True,
        cues=(TranscriptCue(start_s=0.0, text="Hello, this is the body of the transcript."),),
    )
    md = transcript_to_markdown(transcript)
    assert AUTO_CAPTION_MARK in md  # the producer wrote the header
    stripped = strip_inserted_lines(md)
    assert AUTO_CAPTION_MARK not in stripped  # the verifier removed the header line
    assert (
        "Hello, this is the body of the transcript." in stripped
    )  # the body (the source) stays


# --- the juge, verified end to end, inherits the rule for free --------------------------------------


def _fiche(title: str, passages: list[str]) -> str:
    body = "\n\n".join(passages)
    return (
        '---\ntitle: "T"\ntype: "book"\n---\n\n# T\n\n'
        f"## 1. {title}\n\nDesc.\n\n**Concepts** :\n- x\n\n### Contenu (verbatim)\n\n{body}\n"
    )


def test_juge_does_not_bless_a_vision_caption_as_verbatim() -> None:
    desc = "A curve the model hallucinated for this chart."
    enriched = _BOOK + f"\n\n> {FIGURE_CAPTION_MARK} {desc}\n"
    real = [
        "Risk management is the core of quantitative finance.",
        "A prudent investor diversifies across uncorrelated assets.",
        "Position sizing ensures a single loss never threatens the whole portfolio.",
    ]
    verdict = judge_fiche(_fiche("Chapter", [*real, desc]), enriched)
    assert verdict.n_passages == 4 and verdict.n_verbatim == 3  # the caption is not counted
    assert (
        verdict.status == JudgeStatus.PARAPHRASED and not verdict.ok
    )  # contaminated fiche is flagged
