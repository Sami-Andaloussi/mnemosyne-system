"""distillateur skill (body `system/skills/distillateur/distill_book.py`) - distilled<->raw mirror + safety net.

The GOVERNED distillateur (the Skill + its verbatim barrier) is tested in ``test_distillation.py``;
here we cover the invariants specific to the SCRIPT orchestrator that the operator relies on for the campaign:

* **MIRROR structure (campaign imperative)** - a fiche's path is DERIVED from the raw's path
  (``raw/`` -> ``distilled/``, same subtree + same name), never hand-typed: whatever the operator changes
  in ``raw``, ``distilled`` moves identically.
* **Level-2 safety net (sub-chunk)** - ``_split_half`` cuts losslessly; ``_merge_docs`` glues the
  sub-distillates back into ONE doc (passages concatenated, tags/concepts deduped while keeping order).

The script is imported by path (importlib): its module body has no side effects (constants +
defs, lazy mnemosyne imports), so running it is safe and needs no brick."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from _invariants import REPO_ROOT
from mnemosyne.production import DistilledDoc

_SCRIPT = REPO_ROOT / "system" / "skills" / "distillateur" / "distill_book.py"
_spec = importlib.util.spec_from_file_location("distill_book", _SCRIPT)
assert _spec is not None and _spec.loader is not None
distill_book = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(distill_book)


# --------------------------------------------------------------------------- #
# The mirror distilled<->raw - the path is DERIVED from the raw, never hand-typed #
# --------------------------------------------------------------------------- #
def test_distilled_path_mirrors_the_raw_subtree_and_filename() -> None:
    out = distill_book._distilled_path_for(Path("knowledge/raw/quant-finance/Foo - Bar.md"))
    # raw/ -> distilled/, SAME domain subdir + SAME filename (not a slug)
    assert out.parts[-3:] == ("distilled", "quant-finance", "Foo - Bar.md")
    assert "raw" not in out.parts  # it moved to distilled, it is not left under raw


def test_distilled_path_mirrors_a_deeper_raw_subtree() -> None:
    # a nested rayon (user reshelves into a subfolder) mirrors identically - the whole relative subtree.
    out = distill_book._distilled_path_for(
        Path("knowledge/raw/information-retrieval/Machine_Learning/Foo.md")
    )
    assert out.parts[-4:] == ("distilled", "information-retrieval", "Machine_Learning", "Foo.md")


def test_distilled_path_falls_back_to_flat_slug_off_the_shelf() -> None:
    # an input NOT under knowledge/raw/ (e.g. a scratchpad test .md) -> a flat slug fiche, no crash.
    out = distill_book._distilled_path_for(
        Path("/tmp/x/Systematic Strategy -- Robert Carver -- 2015 -- .md")
    )
    assert out.parent == distill_book._DISTILLED  # flat under distilled/
    assert out.suffix == ".md" and out.name  # a real filename, slugified


# --------------------------------------------------------------------------- #
# The net level 2 - sub-chunk split (lossless) + merge (one section, deduped)   #
# --------------------------------------------------------------------------- #
def test_split_half_is_lossless_and_splits_both_sides() -> None:
    text = "line one\nline two\nline three\nline four\nline five\n"
    left, right = distill_book._split_half(text)
    assert left + right == text  # a split never loses a character
    assert left and right  # both halves carry content


def _doc(
    title: str,
    *,
    tags: tuple[str, ...],
    concepts: tuple[str, ...],
    passages: tuple[str, ...],
    description: str,
    summary: str,
) -> DistilledDoc:
    return DistilledDoc(
        source_doc_id="d",
        dtype="book",
        title=title,
        summary=summary,
        tags=tags,
        description=description,
        concepts=concepts,
        passages=passages,
    )


def test_merge_docs_concatenates_passages_and_dedupes_in_order() -> None:
    a = _doc(
        "A",
        tags=("x", "y"),
        concepts=("c1", "c2"),
        passages=("p1", "p2"),
        description="desc A",
        summary="sa",
    )
    b = _doc(
        "B",
        tags=("y", "z"),
        concepts=("c2", "c3"),
        passages=("p3",),
        description="desc B",
        summary="",
    )
    merged = distill_book._merge_docs([a, b], "Section 7")
    assert merged.passages == ("p1", "p2", "p3")  # verbatim content concatenated in order
    assert merged.tags == ("x", "y", "z")  # deduped, order preserved
    assert merged.concepts == ("c1", "c2", "c3")
    assert "desc A" in merged.description and "desc B" in merged.description
    assert merged.summary == "sa"  # first non-empty summary
    assert merged.title == "Section 7"  # the section keeps its single title


class _FailBigApi:
    """A stub CoreApi: decode fails on a big section, succeeds once it is small enough."""

    def __init__(self, *, ceiling: int) -> None:
        self._ceiling = ceiling
        self.sizes: list[int] = []

    def distill(self, inp: object, *, subject: object) -> object:
        text = inp.source_text  # type: ignore[attr-defined]
        self.sizes.append(len(text))
        if len(text) > self._ceiling:
            raise RuntimeError("too big to decode")
        return _doc(
            inp.title_hint,
            tags=("t",),
            concepts=("c",),  # type: ignore[attr-defined]
            passages=(text.strip()[:20] or "p",),
            description="d",
            summary="s",
        )


def test_distill_section_recovers_by_subchunking_then_merges() -> None:
    # L2: a section that fails whole is split until each half decodes, then merged into ONE doc.
    api = _FailBigApi(ceiling=5000)
    doc = distill_book._distill_section(api, "doc", "Title", "x\n" * 4000)  # ~8000 chars
    assert doc is not None
    assert len(doc.passages) == 2  # the two recovered halves, merged into one section
    assert any(n > 5000 for n in api.sizes) and any(n <= 5000 for n in api.sizes)  # it really split


def test_distill_section_returns_none_when_unrecoverable() -> None:
    # Exhausted (every attempt fails) -> None, so the caller writes the L3 flag (never silent).
    api = _FailBigApi(ceiling=0)  # nothing is ever small enough -> always raises
    assert distill_book._distill_section(api, "doc", "Title", "y\n" * 4000) is None


# --------------------------------------------------------------------------- #
# The self-delimited verbatim fence - _section_md wraps P3 so a "## N."          #
# quoted from an OCR source never reads as a chapter boundary                    #
# --------------------------------------------------------------------------- #
def test_section_md_wraps_verbatim_in_a_self_delimiting_fence() -> None:
    from mnemosyne.production.chapter_parsing import (
        SECTION_RE,
        VERBATIM_BEGIN,
        VERBATIM_END,
        mask_fenced_verbatim,
    )

    doc = _doc(
        "Ch",
        tags=("t",),
        concepts=("c",),
        passages=("A precious line.", "## 2. A heading quoted from the OCR source.", "tail."),
        description="d",
        summary="s",
    )
    md = distill_book._section_md(3, "Real Title", doc)
    assert VERBATIM_BEGIN in md and VERBATIM_END in md  # the verbatim block is fenced by the writer
    # the real chapter heading "## 3." is a boundary; the quoted "## 2." inside the fence is NOT.
    assert [m.group(1) for m in SECTION_RE.finditer(mask_fenced_verbatim(md))] == ["3"]
    assert (
        "## 2. A heading quoted from the OCR source." in md
    )  # the quoted heading is preserved verbatim
