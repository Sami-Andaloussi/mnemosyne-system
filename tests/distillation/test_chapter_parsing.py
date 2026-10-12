"""chapter_parsing (D143 / D100) - the shared chapter grammar + the self-delimited verbatim fence.

THE property proven here: a ``## N.`` heading QUOTED inside a verbatim fence is blanked by
``mask_fenced_verbatim`` (never read as a chapter boundary) while every REAL heading - and every character
offset - is preserved 1:1, so a caller scans the mask for boundaries yet slices the real text for content.
Brick-free."""

from __future__ import annotations

from mnemosyne.production.chapter_parsing import (
    SECTION_RE,
    VERBATIM_BEGIN,
    VERBATIM_END,
    mask_fenced_verbatim,
)


def _fenced(passages: str) -> str:
    return VERBATIM_BEGIN + "\n\n" + passages + "\n\n" + VERBATIM_END


def _nums(text: str) -> list[str]:
    return [m.group(1) for m in SECTION_RE.finditer(mask_fenced_verbatim(text))]


def test_no_fence_is_returned_unchanged() -> None:
    # every pre-fix corpus fiche has no sentinel -> identical bytes -> scanned exactly as before (backward-compat).
    text = "## 1. A\n\nbody\n\n## 2. B\n\nmore\n"
    assert mask_fenced_verbatim(text) == text
    assert _nums(text) == ["1", "2"]


def test_mask_preserves_length_and_newline_positions() -> None:
    # offsets 1:1: same length, newlines at the same indices -> a match in the mask indexes the ORIGINAL text.
    text = (
        "## 1. A\n\n### Contenu (verbatim)\n\n" + _fenced("quote ## 2. Foo end") + "\n\n## 2. B\n"
    )
    masked = mask_fenced_verbatim(text)
    assert len(masked) == len(text)
    assert [i for i, c in enumerate(text) if c == "\n"] == [
        i for i, c in enumerate(masked) if c == "\n"
    ]


def test_a_heading_quoted_inside_the_fence_is_not_a_boundary() -> None:
    # THE trap (D143): "## 2." sits inside a verbatim passage. Masked, only the REAL headings remain, and the
    # matched offsets recover them verbatim from the ORIGINAL text.
    quoted = "A precious line.\n\n## 2. This is quoted from the OCR source.\n\nmore."
    text = (
        "## 1. Real One\n\n### Contenu (verbatim)\n\n"
        + _fenced(quoted)
        + "\n\n## 2. Real Two\n\n### Contenu (verbatim)\n\n"
        + _fenced("another line.")
        + "\n"
    )
    matches = list(SECTION_RE.finditer(mask_fenced_verbatim(text)))
    assert [m.group(1) for m in matches] == [
        "1",
        "2",
    ]  # the quoted "## 2." inside chapter 1's fence is skipped
    assert text[matches[0].start() :].startswith("## 1. Real One")
    assert text[matches[1].start() :].startswith("## 2. Real Two")


def test_unterminated_fence_is_masked_to_end_fail_closed() -> None:
    # a truncated / corrupt write (BEGIN, no END): mask to EOF -> the swallowed headings fail the count check
    # upstream (chapter_numbers_ok) and the fiche is FLAGGED, never silently mis-parsed.
    text = (
        "## 1. A\n\n### Contenu (verbatim)\n\n" + VERBATIM_BEGIN + "\n\nbody\n\n## 2. B\n\nmore\n"
    )
    assert _nums(text) == ["1"]


def test_multiple_fences_keep_the_text_between_them_visible() -> None:
    text = (
        "## 1. A\n\n### Contenu (verbatim)\n\n" + _fenced("x ## 9. q") + "\n\n"
        "## 2. B\n\n### Contenu (verbatim)\n\n" + _fenced("y ## 8. r") + "\n\n"
        "## 3. C\n"
    )
    assert _nums(text) == [
        "1",
        "2",
        "3",
    ]  # quoted ## 9. / ## 8. blanked; the 3 real headings survive


def test_section_re_captures_number_then_title() -> None:
    # the ONE grammar the 3 readers share: group 1 = number (sequencing), group 2 = title.
    m = SECTION_RE.search("## 7. Risk Management")
    assert m is not None and m.group(1) == "7" and m.group(2) == "Risk Management"
