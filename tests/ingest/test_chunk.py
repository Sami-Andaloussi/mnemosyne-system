"""Chunker tests (D135) - deterministic, loss-less, bounded passages (brick-free, D126)."""

from __future__ import annotations

import pytest

from mnemosyne.ingest.chunk import Passage, chunk_text, select_passage


def test_empty_or_whitespace_yields_no_passage() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


def test_short_text_is_a_single_passage() -> None:
    assert chunk_text("a short note about trading") == [
        Passage(ordinal=0, text="a short note about trading")
    ]


def test_long_text_splits_into_bounded_ordered_passages() -> None:
    text = "\n\n".join(f"paragraph {i} " + "word " * 100 for i in range(20))
    passages = chunk_text(text, target=500, overlap=50)
    assert len(passages) > 1
    assert [p.ordinal for p in passages] == list(range(len(passages)))
    # each passage stays within ~target (+ carried overlap) => the encoder never truncates one.
    assert all(len(p.text) <= 500 + 50 for p in passages)


def test_is_deterministic() -> None:
    text = "\n\n".join(f"section {i}: " + "alpha beta gamma " * 40 for i in range(10))
    assert chunk_text(text, target=400, overlap=40) == chunk_text(text, target=400, overlap=40)


def test_covers_the_whole_content_no_token_dropped() -> None:
    text = "\n\n".join(f"unique_token_{i} " + "filler " * 50 for i in range(12))
    joined = "".join(p.text for p in chunk_text(text, target=300, overlap=30))
    assert all(f"unique_token_{i}" in joined for i in range(12))


def test_a_single_oversized_token_is_hard_split() -> None:
    passages = chunk_text("x" * 5000, target=1000, overlap=100)
    assert len(passages) >= 5
    assert all(len(p.text) <= 1000 + 100 for p in passages)


def test_overlap_must_be_below_target() -> None:
    with pytest.raises(ValueError):
        chunk_text("some text", target=100, overlap=100)


def test_select_passage_by_ordinal_returns_that_passage() -> None:
    # D136: the dense index's matched passage ordinal selects that exact passage (bounded), so recall
    # packs it, never the whole document.
    text = "\n\n".join(f"paragraph {i} " + "word " * 80 for i in range(10))
    passages = chunk_text(text)
    assert len(passages) > 2
    for ordinal in (0, 1, len(passages) - 1):
        assert select_passage(text, "ignored", ordinal=ordinal) == passages[ordinal].text


def test_select_passage_without_ordinal_picks_the_best_lexical_passage() -> None:
    # A keyword-only hit has no ordinal (chunk=None); the passage with the most query terms is chosen
    # - the same lexical signal the keyword leg used - never an arbitrary head.
    filler = "\n\n".join("neutral filler with no link at all here" for _ in range(80))
    marker = "the zones of price interest guide trading entries plan"
    text = filler + "\n\n" + marker + "\n\n" + filler
    assert len(chunk_text(text)) > 2  # several default-size passages
    chosen = select_passage(text, "price zones trading", ordinal=None)
    assert "price" in chosen and "trading" in chosen  # the on-topic passage, not a filler head


def test_select_passage_out_of_range_ordinal_falls_back_lexically() -> None:
    # A stale / out-of-range ordinal never indexes past the end - it degrades to the lexical pick,
    # not passage 0 (which here is pure filler).
    filler = "\n\n".join("neutral filler with no link" for _ in range(80))
    text = filler + "\n\nprice zones trading landmark\n\n" + filler
    assert len(chunk_text(text)) > 2
    chosen = select_passage(text, "price trading", ordinal=999)
    assert "price" in chosen and "trading" in chosen


def test_select_passage_on_empty_text_is_unchanged() -> None:
    assert select_passage("", "q", ordinal=0) == ""
    assert select_passage("   ", "q") == "   "


def test_select_passage_resists_boilerplate_term_repetition() -> None:
    # audit M-1b: distinct-term overlap, NOT raw frequency - a passage repeating one common query term
    # many times must not outrank the passage that covers MORE distinct query terms.
    boiler = "the " * 400  # one distinct query term ("the"), repeated 400×
    ontopic = "the price zones trading plan"  # four distinct query terms
    filler = "filler neutral with no link here " * 100
    text = boiler + "\n\n" + ontopic + "\n\n" + filler
    assert len(chunk_text(text)) > 2
    chosen = select_passage(text, "the price zones trading", ordinal=None)
    assert (
        "price" in chosen and "trading" in chosen
    )  # on-topic wins; boilerplate repetition doesn't
