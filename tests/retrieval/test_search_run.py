"""item 4 / D65 - the frontier RAG read surface renders passages faithfully, admits emptiness.

``render_recall`` is the pure (brick-free) half of ``make search``: a frontier host reads its stdout.
These pin the two things a frontier depends on - that real passages are printed, grouped by their
provenance ROLE (so a working-material draft is never mistaken for a citable source, D137); and that an
empty, low-recall read prints the explicit "no confident memory" admission (invariant 14) rather than a
blank that reads like "nothing exists". Brick-free: hand-built views, nothing installed (D126).
"""

from __future__ import annotations

from mnemosyne.api import RecallView
from mnemosyne.ports import Bubble, Envelope, GovernanceLabel, Sensitivity
from mnemosyne.runtime.search_run import render_recall

_LABEL = GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble("knowledge"))


def _view(*, facts=(), working=(), frame=(), low_recall=False, reason="ok") -> RecallView:
    return RecallView(
        frame=tuple(Envelope(t, _LABEL) for t in frame),
        facts=tuple(Envelope(t, _LABEL) for t in facts),
        working_material=tuple(Envelope(t, _LABEL) for t in working),
        sensitivity=Sensitivity.SENSIBLE,
        engines=("documentary",),
        admitted_low_recall=low_recall,
        reason=reason,
    )


def test_renders_passages_grouped_by_role() -> None:
    out = render_recall(
        _view(facts=("Kelly sizing caps risk of ruin.",), working=("my draft note",)),
        "kelly criterion",
    )
    # the query and both non-empty buckets, with their counts and payloads
    assert "kelly criterion" in out
    assert "ENDORSED SOURCES" in out and "(1)" in out
    assert "Kelly sizing caps risk of ruin." in out
    assert "WORKING MATERIAL" in out
    assert "my draft note" in out
    # an empty bucket is shown as such, never omitted (honest structure)
    assert "LIVING FRAME" in out and "(none)" in out
    # NOT the low-recall admission when content exists
    assert "no confident memory" not in out


def test_empty_low_recall_prints_admission_not_blank() -> None:
    out = render_recall(_view(low_recall=True, reason="below floor"), "obscure query")
    assert "no confident memory" in out
    assert "invariant 14" in out
    # the admission REPLACES the buckets - no misleading empty "ENDORSED SOURCES (0)" list
    assert "ENDORSED SOURCES" not in out


def test_low_recall_flag_does_not_suppress_present_content() -> None:
    # defense: if a caller marks low_recall yet still hands back readable facts, show them (the
    # admission is gated on ALL buckets empty, not the flag alone).
    out = render_recall(_view(facts=("a real passage",), low_recall=True), "q")
    assert "a real passage" in out
    assert "no confident memory" not in out
