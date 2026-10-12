"""(3)-7 - the calibration instrument (D69 / D148), the closure of phase (3).

Biting tests for :mod:`mnemosyne.runtime.calibration`, the 1-command driver that measures the
fidelity gate (ingestion token-F1), the groundedness anchor (entities-in-the-passage, D148), and
the now-informative-only extraction triple-F1 - reporting the ACTUAL trust verdict: ``all_clear``
requires the fidelity gate to clear AND the groundedness anchor to be MEASURED and trusted. The
point is honesty + fail-closed (F3 / D100): a perfect engine clears both; an abstaining one clears
neither (never a vacuous pass); an empty report never clears; and a groundedness that was simply
never MEASURED (the dataclass default, ``None``) never clears either - the single most important
property this file pins (D148: an absent measurement must never read as a pass). The bars stay
pinned to the real provisional constants so a future recalibration flows straight through. All
brick-free (D126): the pure core takes the engines as callables, and the runtime wrapper measures
the stub exactly as the real bricks - a stub extractor abstains (ungrounded, informative F1 reads 0)
while the utf-8 reader recovers the seed (fidelity clears). Code & docstrings English (D117).
"""

from __future__ import annotations

from dataclasses import fields

from mnemosyne.ingest.golden import FIDELITY_SEED, MIN_INGEST_FIDELITY
from mnemosyne.ports import Source
from mnemosyne.production.golden import (
    GOLDEN_SEED,
    MIN_EXTRACTION_F1,
    MIN_GROUNDEDNESS,
    MIN_YIELD,
    Triple,
)
from mnemosyne.runtime import (
    CalibrationReport,
    GateCalibration,
    Runtime,
    bootstrap,
    calibrate_floor_runtime,
    calibrate_runtime,
    run_calibration,
)
from mnemosyne.runtime.calibration import _ocr_retry_reader
from mnemosyne.stores.golden import RETRIEVAL_SEED


def _perfect_extract(content: str) -> frozenset[Triple]:
    """A flawless extractor: returns exactly each seed case's expected triples (precision = recall = 1)."""
    return next((case.expected for case in GOLDEN_SEED if case.content == content), frozenset())


def _perfect_read(source: Source) -> str:
    """A flawless reader: recovers exactly each seed case's expected text (token-F1 = 1)."""
    return next((case.expected_text for case in FIDELITY_SEED if case.source.ref == source.ref), "")


def _abstain_extract(_content: str) -> frozenset[Triple]:
    return frozenset()  # the stub posture: proposes nothing -> recall 0 -> below the bar


def _abstain_read(_source: Source) -> str:
    return ""  # a reader that recovers nothing -> recall 0 -> below the bar


def test_perfect_engines_clear_the_remaining_gate_and_the_groundedness_anchor() -> None:
    # RENAMED - was "...clear both bars": the extraction leg no longer GATES (D148), so "both" is now
    # the fidelity gate + the groundedness anchor. `passages` must be passed explicitly (the default
    # `()` is fail-closed, see test_abstaining_engines_are_fail_closed) - GOLDEN_SEED's own content is
    # fully grounded under a perfect extractor, so this is what "clears" looks like end-to-end.
    passages = [case.content for case in GOLDEN_SEED]
    report = run_calibration(extract=_perfect_extract, read=_perfect_read, passages=passages)
    assert report.all_clear  # both trust flags may be flipped True
    assert report.gate("fidelity").f1 == 1.0 and report.gate("fidelity").clears
    assert report.groundedness is not None
    assert report.groundedness.grounded == 1.0 and report.groundedness.trusted
    assert (
        report.extraction_f1 is not None and report.extraction_f1.f1 == 1.0
    )  # informative, still measured


def test_abstaining_engines_are_fail_closed() -> None:
    report = run_calibration(extract=_abstain_extract, read=_abstain_read)
    assert not report.all_clear
    assert report.gate("fidelity").f1 == 0.0 and not report.gate("fidelity").clears
    # D148: "extraction" is no longer a gate - the abstention still reads fail-closed on BOTH of its
    # replacements: the informative F1 (still 0, still printed) and the actual groundedness anchor
    # (no passages given here => score_groundedness's default-empty fail-closed shape, D100).
    assert report.extraction_f1 is not None and report.extraction_f1.f1 == 0.0
    assert report.groundedness is not None
    assert report.groundedness.grounded == 0.0 and not report.groundedness.trusted


def test_gates_carry_the_real_provisional_bars() -> None:
    # the report pins the bars to the live constants, so a recalibration of MIN_INGEST_FIDELITY /
    # MIN_GROUNDEDNESS / MIN_YIELD flows straight through the instrument (D69) - no drifting duplicate.
    # RENAMED premise (D148): MIN_EXTRACTION_F1 no longer backs a *gate* threshold - `gates` holds only
    # fidelity now. It still backs ExtractionScore.trusted on the informative `extraction_f1`, checked
    # here too so the constant's live wiring is pinned on BOTH remaining consumers.
    passages = [case.content for case in GOLDEN_SEED]
    report = run_calibration(extract=_perfect_extract, read=_perfect_read, passages=passages)
    assert report.gate("fidelity").threshold == MIN_INGEST_FIDELITY
    assert {g.name for g in report.gates} == {"fidelity"}
    assert report.extraction_f1 is not None
    assert report.extraction_f1.trusted == (report.extraction_f1.f1 >= MIN_EXTRACTION_F1)
    assert report.groundedness is not None
    assert report.groundedness.trusted == (
        report.groundedness.grounded >= MIN_GROUNDEDNESS
        and report.groundedness.yield_per_passage >= MIN_YIELD
    )


def test_empty_report_never_clears() -> None:
    # D100 / D69: a report with no gate can never vacuously certify a bar - fail-closed by construction.
    # (D148: this is one of TWO independent fail-closed axes now on `all_clear` - see
    # test_all_clear_is_false_when_groundedness_was_never_measured for the other.)
    assert not CalibrationReport(gates=()).all_clear


def test_all_clear_is_false_when_groundedness_was_never_measured() -> None:
    # THE property this re-amendment exists to pin (D148 / D100): an ABSENT measurement must never
    # certify. A report with a CLEARING gate and no groundedness (the dataclass default, `None`) must
    # NOT read as all-clear - else a caller that forgot to pass real `passages` to run_calibration
    # would get a silent, vacuous pass instead of the fail-safe posture.
    clearing_fidelity = GateCalibration(
        name="fidelity", precision=1.0, recall=1.0, f1=1.0, threshold=MIN_INGEST_FIDELITY, cases=1
    )
    report = CalibrationReport(gates=(clearing_fidelity,))  # groundedness left at its None default
    assert report.groundedness is None
    assert not report.all_clear


def test_one_gate_below_bar_blocks_all_clear() -> None:
    # a mixed run (grounded extractor, fidelity abstains) must NOT report all-clear. Passing real
    # passages so groundedness clears ISOLATES the failure to fidelity alone - proving fidelity still
    # gates on its own, exactly as before D148 (only the OTHER gate's identity changed).
    passages = [case.content for case in GOLDEN_SEED]
    report = run_calibration(extract=_perfect_extract, read=_abstain_read, passages=passages)
    assert report.groundedness is not None and report.groundedness.trusted
    assert not report.gate("fidelity").clears
    assert not report.all_clear


def test_calibrate_runtime_on_stub_is_groundedness_fail_closed_fidelity_faithful() -> None:
    # RENAMED (was "...extraction_fail_closed..."): the stub fact extractor still abstains, but D148
    # means that now reads as groundedness=0.0 (vacuous silence, fail-closed) and extraction_f1=0.0
    # (informative only) rather than a gating "extraction" bar. Fidelity is unaffected: the utf-8
    # PlainTextSourceReader still recovers the seed text faithfully. The shape is identical once the
    # real MLX / Docling bricks slot in behind the same ports (D126).
    report = calibrate_runtime(bootstrap())
    assert isinstance(report, CalibrationReport)
    assert (
        report.groundedness is not None and not report.groundedness.trusted
    )  # abstains => ungrounded
    assert (
        report.extraction_f1 is not None and report.extraction_f1.f1 == 0.0
    )  # informative, still 0
    assert report.gate("fidelity").clears  # the seed decodes perfectly under the utf-8 stub
    assert not report.all_clear  # groundedness untrusted => trust flags stay False at ignition


def test_runtime_trust_flags_are_fail_closed_by_type() -> None:
    # audit (3)-7 M2 / D100: the SAFE state (untrusted) is the dataclass DEFAULT, so a raw Runtime never
    # inherits trust - only an explicit measurement raises it. bootstrap() opts the vacuously-safe stub
    # into True (the stub abstains, so no false trust is possible); real_runtime now passes True for
    # graph too (the operator's gesture 2026-07-17, after the groundedness bar cleared - D148), but that is a
    # measured call-site posture, NOT this type default, which stays False (the property pinned here).
    defaults = {f.name: f.default for f in fields(Runtime)}
    assert defaults["graph_extraction_trusted"] is False
    assert defaults["source_extraction_trusted"] is False
    stub = (
        bootstrap()
    )  # the stub assembly stays True (vacuous - abstaining extractor / faithful utf-8)
    assert stub.graph_extraction_trusted is True and stub.source_extraction_trusted is True


def test_calibrate_floor_runtime_on_stub_earns_a_clean_separating_floor() -> None:
    # the third provisional number ((3)-2a / D69), brick-free: the stub hashing embedder scores each
    # query's shared-vocabulary passages ABOVE its distractors, so the sweep earns a clean floor (F1 1.0)
    # at a positive, sub-1 value - exactly the shape real bge-m3 yields at ignition, only the number
    # changes ((3)-2b). The floor is a RECOMMENDATION, never auto-applied over recall_floor (D100 / F3).
    floor = calibrate_floor_runtime(bootstrap())
    assert floor.f1 == 1.0  # the stub cleanly separates the trading-flavoured seed
    assert (
        0.0 < floor.floor < 1.0
    )  # a real earned floor, not the fail-safe 1.0 nor a degenerate 0.0
    assert floor.cases == len(RETRIEVAL_SEED)


def test_report_gate_unknown_name_is_a_clean_keyerror() -> None:
    from pytest import raises

    report = run_calibration(extract=_abstain_extract, read=_abstain_read)
    with raises(KeyError):
        report.gate("nonexistent")  # loud, never a silent wrong gate
    with raises(KeyError):
        # D148: "extraction" moved OFF `.gates` entirely (onto `.extraction_f1`, informative-only) -
        # pinned so a regression that silently re-added it as a no-op gate name would be caught here.
        report.gate("extraction")


def _scan() -> Source:
    return Source(ref="scan.pdf", data=b"%PDF image-only", mime="application/pdf")


def test_ocr_retry_reader_keeps_the_fast_result_on_a_text_layer_source() -> None:
    # (3)-7 fix C: a text-layer source is recovered by the fast (ocr=False) reader, so the OCR reader is
    # NOT called - no OCR tax on the common case, exactly as prod skips the needs_ocr re-extract when the
    # fast pass already yielded text (D69/D85).
    ocr_calls: list[Source] = []

    def fast(_source: Source) -> str:
        return "clean text-layer content"

    def ocr(source: Source) -> str:
        ocr_calls.append(source)
        return "OCR OUTPUT"

    read = _ocr_retry_reader(fast, ocr)
    assert read(_scan()) == "clean text-layer content"
    assert ocr_calls == []  # the OCR path was never taken


def test_ocr_retry_reader_falls_through_to_ocr_on_an_empty_scan() -> None:
    # an image-only scan yields (near-)nothing under ocr=False => the reader re-reads OCR-enabled, exactly
    # the prod --retry-ocr lifecycle. Without this the scan would score fidelity 0 (a BUG, not a verdict).
    def fast_empty(_source: Source) -> str:
        return "   \n  "  # whitespace-only => no usable text recovered (the scan signature)

    def ocr(_source: Source) -> str:
        return "recovered by OcrMac"

    read = _ocr_retry_reader(fast_empty, ocr)
    assert (
        read(_scan()) == "recovered by OcrMac"
    )  # scored on the REAL OCR output, not on the empty pass


def test_ocr_retry_reader_falls_through_to_ocr_when_the_fast_path_raises() -> None:
    # a raise on the fast path is a FAILED read, not an aborted run: it falls through to OCR (prod nets the
    # failure and re-extracts), so one Docling hiccup on a scan never crashes the calibration (F3).
    def fast_boom(_source: Source) -> str:
        raise RuntimeError("docling drift")

    def ocr(_source: Source) -> str:
        return "recovered after the fast path failed"

    read = _ocr_retry_reader(fast_boom, ocr)
    assert read(_scan()) == "recovered after the fast path failed"


def test_gate_calibration_clears_is_a_ge_comparison() -> None:
    # exactly AT the bar clears (>=), a hair below does not - the boundary is the promotion decision.
    # Uses MIN_INGEST_FIDELITY, not MIN_EXTRACTION_F1 (D148 moved extraction off this dataclass shape
    # entirely, onto groundedness): fidelity is the only bar GateCalibration backs now.
    at_bar = GateCalibration(
        name="x",
        precision=1.0,
        recall=1.0,
        f1=MIN_INGEST_FIDELITY,
        threshold=MIN_INGEST_FIDELITY,
        cases=1,
    )
    below = GateCalibration(
        name="x",
        precision=1.0,
        recall=1.0,
        f1=MIN_INGEST_FIDELITY - 0.01,
        threshold=MIN_INGEST_FIDELITY,
        cases=1,
    )
    assert at_bar.clears and not below.clears
