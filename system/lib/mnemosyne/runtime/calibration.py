"""Calibration ((3)-7 / D69, re-amended on its extraction leg by D148) - the closure instrument.

Phase (3) ships bars over the two extraction legs, but only ONE of them still *gates* anything - both
trust flags nonetheless start ``False`` in ``real_runtime`` (fail-closed until measured):

* the GROUNDEDNESS anchor - entities-in-the-passage vs
  :data:`~mnemosyne.production.golden.MIN_GROUNDEDNESS` (0.95) and
  :data:`~mnemosyne.production.golden.MIN_YIELD` (1.0); below it no graph is auto-imposed and the
  content lands as a plan-B ``.md`` note (D58). This is what now DECIDES ``graph_extraction_trusted``
  (D148): the triple-F1 that used to hold that decision measured agreement with a hand-labelled
  golden's ONE frozen triple framing, not whether the extractor invents facts - see
  :mod:`mnemosyne.production.golden`'s module note for the measurement that forced the change.
* the FIDELITY gate - text-from-source token-F1 vs :data:`~mnemosyne.ingest.golden.MIN_INGEST_FIDELITY`
  (0.7); below it an extraction is still ingested (raw preserved, D85) but FLAGGED low-fidelity (F3).
  Unaffected by D148 - still a real F1-vs-bar gate.

The old EXTRACTION triple-F1 (vs :data:`~mnemosyne.production.golden.MIN_EXTRACTION_F1`) is still
measured every run and carried on :attr:`CalibrationReport.extraction_f1` - printed for the record -
but it no longer gates anything (D148).

The retrieval floor (``min_score``) is the THIRD provisional number. It began as a *declared constant*
(bge-m3 -> 0.55): a reasoned but DISCRETIONARY guess that can err in BOTH directions - too low invents,
too high silently drops a relevant passage (the (3)-2a symptom). :func:`calibrate_floor_runtime` now
EARNS it from a golden set too (:mod:`~mnemosyne.stores.golden`, D69): a ``(query, passage)`` cosine
sweep returns the floor that maximises retrieval F1. Unlike the fidelity gate and the groundedness
anchor above - each a FIXED bar an engine must CLEAR - the floor is a RECOMMENDED number: reported,
never auto-applied; adopting it over the embedder's declared ``recall_floor`` is an [OPERATOR] gesture
at ignition (D100). All these numbers' real values can only come from measuring the REAL bricks (the
MLX fact extractor, the Docling / WhisperKit reader, bge-m3) against a golden corpus.

**Honesty (F3 / D126).** The instrument is BRICK-FREE and PURE - :func:`run_calibration` takes the two
engines as callables, exactly like the golden scorers, so it measures a stub (abstains => below the bar
/ ungrounded => fail-closed) precisely as it will measure the real bricks. It does NOT fabricate
calibrated numbers: the actual measurement - expanding the hand-labelled seeds into a real (2) corpus and
reading off the F1 / groundedness to flip ``graph_extraction_trusted`` / ``source_extraction_trusted``,
is the machine-only :func:`main` run at ignition ([OPERATOR], at ignition), the same shape as the
1-click smoke's ``main()``.

Decisions: D69 (calibrate against a golden set) - D148 (extraction leg re-amended: groundedness, not
triple-F1, decides the trust flag) - D58 (plan B below the bar) - D125-B6 (fidelity golden) - D65 /
invariant 14 (retrieval floor, admit low recall) - D100 (fail-closed trust flags, never on an absent
measurement) - D126 (brick-free, callable seams). Code & docstrings English (D117); ``public`` /
``perso`` / ``sensible`` keep their French tokens (D33 / D66).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..ingest.golden import (
    FIDELITY_SEED,
    MIN_INGEST_FIDELITY,
    FidelityCase,
    load_fidelity_golden,
    score_fidelity,
)
from ..ports import Bubble, Envelope, GovernanceLabel, Sensitivity, Source, Vector
from ..production.golden import (
    GOLDEN_SEED,
    MIN_EXTRACTION_F1,
    MIN_GROUNDEDNESS,
    MIN_YIELD,
    ExtractionScore,
    GoldenCase,
    GroundednessScore,
    Triple,
    load_extraction_golden,
    score_extraction,
    score_groundedness,
)
from ..stores.golden import (
    RETRIEVAL_SEED,
    FloorScore,
    RetrievalCase,
    load_retrieval_golden,
    sweep_floor,
)
from .bootstrap import Runtime, bootstrap

#: The public bubble the calibration wraps its (public seed) content in. The extractor grants on its
#: OWN reduced-rights subject (D89), so this only labels the input; no ``sensible`` is calibrated (D66).
_CALIBRATION_LABEL = GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("calibration"))


@dataclass(frozen=True, slots=True)
class GateCalibration:
    """One golden gate measured against its provisional bar (D69) - the trust-flag decision."""

    name: str
    precision: float
    recall: float
    f1: float
    threshold: float
    cases: int

    @property
    def clears(self) -> bool:
        """Whether the measured F1 clears the bar - the trust flag the operator flips at ignition.
        The sole occupant of :attr:`CalibrationReport.gates` is now FIDELITY (else the fail-safe
        posture: low-fidelity flag, F3): the extraction leg moved OFF this F1-vs-bar shape onto
        groundedness entirely (D148), so this dataclass is no longer instantiated for it."""
        return self.f1 >= self.threshold


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """The (3)-7 calibration verdict (D69 / F3), re-amended on its extraction leg (D148).

    ``gates`` now holds ONLY the fidelity gate - a real F1-vs-bar decision. The extraction leg no
    longer gates: :attr:`extraction_f1` carries the OLD triple-F1 measurement (informative, printed,
    never read as a verdict - the golden it compares against froze one arbitrary triple framing,
    D148) and :attr:`groundedness` carries the measurement that actually DECIDES
    ``graph_extraction_trusted`` (entities-anchored-in-the-passage, D148)."""

    gates: tuple[GateCalibration, ...]
    groundedness: GroundednessScore | None = None
    extraction_f1: ExtractionScore | None = None

    @property
    def all_clear(self) -> bool:
        """Whether every remaining gate clears AND the groundedness anchor was measured and trusted.

        Four conjuncts, each fail-closed on its own (D100 / D69 / D148): an empty ``gates`` never
        clears (a missing gate cannot vacuously certify a bar); any gate below its bar blocks it;
        ``groundedness is None`` (never measured) blocks it - the point of this re-amendment: an
        absent measurement must never read as a pass; and a MEASURED-but-untrusted groundedness
        (below either of its own two bars) blocks it exactly like any other failing gate would. A
        caller that forgot to pass real ``passages`` to :func:`run_calibration` gets ``False`` here,
        never a silent vacuous ``True``."""
        return (
            bool(self.gates)
            and all(gate.clears for gate in self.gates)
            and self.groundedness is not None
            and self.groundedness.trusted
        )

    def gate(self, name: str) -> GateCalibration:
        """The named gate - only ``"fidelity"`` remains here (D148 moved ``"extraction"`` off ``gates``
        entirely, onto :attr:`extraction_f1`, informative-only). An unknown name is a clean
        ``KeyError`` (loud, never a silent wrong gate) - so ``gate("extraction")`` now raises too."""
        try:
            return next(gate for gate in self.gates if gate.name == name)
        except StopIteration:
            raise KeyError(name) from None


def _runtime_extractor(runtime: Runtime) -> Callable[[str], frozenset[Triple]]:
    """Adapt the runtime's Guard-routed fact extractor to the golden scorer's ``content -> triples``
    callable: wrap the text in a public envelope, extract, and normalize each ``Fact`` to a bare
    ``(subject, predicate, obj)`` string triple. The extractor grants on its own subject (D89), so a
    stub abstains => empty => recall 0 => fail-closed, exactly as the real MLX extractor is measured."""

    def extract(content: str) -> frozenset[Triple]:
        facts = runtime.fact_extractor.extract(Envelope(payload=content, label=_CALIBRATION_LABEL))
        return frozenset((str(f.subject), f.predicate, str(f.obj)) for f in facts)

    return extract


def run_calibration(
    *,
    extract: Callable[[str], frozenset[Triple]],
    read: Callable[[Source], str],
    extraction_cases: Sequence[GoldenCase] = GOLDEN_SEED,
    fidelity_cases: Sequence[FidelityCase] = FIDELITY_SEED,
    passages: Sequence[str] = (),
) -> CalibrationReport:
    """Measure the fidelity gate, the groundedness anchor, and the informative extraction F1 (D126 / D148).

    ONE actual gate remains in ``.gates``: fidelity (text-from-source token-F1 vs
    :data:`~mnemosyne.ingest.golden.MIN_INGEST_FIDELITY`). The extraction triple-F1 ((3)-3c's original
    design) is still measured and carried on :attr:`CalibrationReport.extraction_f1`, but it never
    gates - it compares against a hand-labelled golden that froze ONE valid triple decomposition per
    sentence, so exact match measured agreement with a labeller's arbitrary framing, not extraction
    quality (see :mod:`mnemosyne.production.golden`'s module note, D148). The
    ``graph_extraction_trusted`` decision now rests on ``score_groundedness(extract, passages)``
    instead - carried on :attr:`CalibrationReport.groundedness` - which asks a different, answerable
    question: did every entity the extractor named come FROM the passage it read? ``passages``
    defaults to empty, which :func:`~mnemosyne.production.golden.score_groundedness` scores as
    ungrounded (0.0, untrusted) - fail-closed, exactly like an absent golden (D100): a caller that
    forgets to pass real passages gets a report that can never be ``all_clear``, never a silent
    vacuous pass.

    Takes the two engines as CALLABLES (the real bricks behind the ports, or test doubles), so it
    never imports a brick and measures a stub exactly as the real thing (D126). An abstaining engine
    scores below the bar / ungrounded (fail-closed), never vacuously clears (D69)."""
    extraction = score_extraction(extract, extraction_cases)
    fidelity = score_fidelity(read, fidelity_cases)
    groundedness = score_groundedness(extract, passages)
    return CalibrationReport(
        gates=(
            GateCalibration(
                name="fidelity",
                precision=fidelity.precision,
                recall=fidelity.recall,
                f1=fidelity.f1,
                threshold=MIN_INGEST_FIDELITY,
                cases=fidelity.cases,
            ),
        ),
        groundedness=groundedness,
        extraction_f1=extraction,
    )


def calibrate_runtime(runtime: Runtime | None = None) -> CalibrationReport:
    """Run the calibration over a runtime's configured extractor + source reader (D69 / D148).

    Bootstraps a runtime (or uses the one given - e.g. ``real_runtime`` at ignition), adapts its
    Guard-routed fact extractor and its source reader to the scorer callables, and measures the
    fidelity gate, the groundedness anchor, and the (now informative-only) extraction F1 - all three
    against :data:`~mnemosyne.production.golden.GOLDEN_SEED` (:func:`run_calibration`'s own default
    for ``extraction_cases``), reusing its case content as the groundedness ``passages`` rather than
    inventing a second source. On the stub runtime the extractor abstains (ungrounded, and the
    informative extraction-F1 reads 0 too) while the utf-8 source reader recovers the seed text
    faithfully (fidelity clears) - the shape is identical once the real bricks slot in behind the
    same ports (D126); :func:`main` swaps in the real corpus-drawn golden at ignition."""
    rt = runtime if runtime is not None else bootstrap()
    return run_calibration(
        extract=_runtime_extractor(rt),
        read=rt.source_reader.read,
        passages=[case.content for case in GOLDEN_SEED],
    )


def _ocr_retry_reader(
    read: Callable[[Source], str], ocr_read: Callable[[Source], str]
) -> Callable[[Source], str]:
    """Compose the two prod read paths into ONE fidelity callable that mirrors the retry-OCR lifecycle.

    A fidelity golden mixes text-layer sources with genuinely SCANNED (image-only) ones. In PROD those
    two take DIFFERENT paths: the fast reader (``ocr=False``) handles text-layer documents, and a scan -
    which yields (near-)nothing under ``ocr=False`` - is flagged ``needs_ocr`` and RE-READ with the
    OCR-enabled reader (``connect_docling(ocr=True)`` -> OcrMac) on the ``--retry-ocr`` pass
    (:func:`~mnemosyne.runtime.library_run._ingest_runtime`, D69/D85). Measuring the scanned cases only
    on the ``ocr=False`` path would score them 0 - a BUG masquerading as a fidelity verdict (the (3)-7
    diagnostic: the two scans came back empty), not the quality the operator actually ships.

    So this reader reproduces that exact lifecycle: read with the fast reader first, and when it recovers
    NO usable text (empty after stripping - the image-only-scan signature), re-read with the OCR reader,
    exactly as prod's ``needs_ocr`` re-extract does. A text-layer case is untouched (fast path wins, no
    OCR tax); a scan is scored on its REAL OCR output. The empty-only trigger is deliberately narrow: a
    short-but-recovered text case never spuriously fires OCR, so the measurement stays honest (F3)."""

    def read_with_retry(source: Source) -> str:
        try:
            text = read(source)
        except Exception:  # noqa: BLE001 - a raise on the fast path is a FAILED read; fall through to OCR,
            text = ""  # exactly as prod nets the failure and re-extracts (never crashes the calibration, F3)
        if (
            text.strip()
        ):  # text-layer recovered => keep the fast result (no OCR tax), prod's common case
            return text
        return ocr_read(
            source
        )  # (near-)empty => the scan path: re-read OCR-enabled, as --retry-ocr does

    return read_with_retry


def _cosine(a: Vector, b: Vector) -> float:
    """Cosine similarity between two embedding vectors; 0 for a zero vector (no spurious match).

    The MEASUREMENT-side similarity the floor sweep scores on. It computes the SAME cosine metric the
    retrieval leg gates against ``min_score`` (D65), but deliberately with its OWN implementation rather
    than reaching into any index's internal cosine - the stub's private ``_cosine`` today, Qdrant's own
    (unexposed) at ignition. Same metric, independent code BY DESIGN: the floor is earned by measuring
    the embedder's vectors directly, so calibration never couples to a stub-only helper ((3)-2a). The two
    copies are verified equivalent; a future tune must keep the METRIC aligned, not the function object."""
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _runtime_similarity(runtime: Runtime) -> Callable[[str, str], float]:
    """Adapt the runtime's embedder to the sweep's ``(query, passage) -> cosine`` callable: embed both
    texts and cosine their vectors - exactly the score :class:`~mnemosyne.stores.retrieval.Retriever`
    gates against the floor (D65). Brick-free (D126): with the stub hashing encoder shared vocabulary
    separates, exactly as real bge-m3 will - the instrument is identical, only the numbers change."""

    def similarity(query: str, passage: str) -> float:
        vectors = runtime.embedder.embed([query, passage])
        return _cosine(vectors[0].vector, vectors[1].vector)

    return similarity


def calibrate_floor_runtime(
    runtime: Runtime | None = None, *, cases: Sequence[RetrievalCase] = RETRIEVAL_SEED
) -> FloorScore:
    """Earn the retrieval recall floor from a golden set over a runtime's embedder ((3)-2a / D69).

    Bootstraps a runtime (or uses the one given - e.g. ``real_runtime`` at ignition), adapts its
    embedder to the ``(query, passage) -> cosine`` callable, and sweeps the floor that maximises F1 over
    ``cases``. ``cases`` defaults to the hand-labelled :data:`~mnemosyne.stores.golden.RETRIEVAL_SEED`
    (so the brick-free suite proves the mechanism); at ignition :func:`main` passes the REAL golden drawn
    from the operator's corpus ((3)-2b, loaded from the gitignored ``knowledge/golden/``). On the stub the
    hashing encoder separates the seed (a clean floor at F1 1.0); the REAL number - bge-m3 over the corpus
    golden - is what the operator reads off, and ADOPTING it (overriding the embedder's declared
    ``recall_floor``) is an [OPERATOR] gesture, never auto-applied from a measurement (D100 / F3)."""
    rt = runtime if runtime is not None else bootstrap()
    return sweep_floor(_runtime_similarity(rt), cases)


def main() -> int:  # pragma: no cover - CLI over the REAL bricks ((3) ignition, machine-only)
    """Measure the REAL bricks against the golden sets and print the calibration verdict (``make
    calibrate``). Uses :func:`~mnemosyne.runtime.bootstrap.real_runtime`, so the MLX extractor, the
    Docling / WhisperKit reader and bge-m3 are measured behind the ports. Prints, in order: the
    fidelity gate, groundedness (the ACTUAL ``graph_extraction_trusted`` decision, D148 - with a
    couple of ``foreign``-triple examples when it fails, so a red result is diagnosable, not just
    red), the old triple-F1 explicitly labelled INFORMATIVE / NON-GATING with a one-line reason
    (D148: the golden it compares against froze one arbitrary triple framing), and the earned
    retrieval floor (a recommendation the operator adopts by gesture, never gating the exit). All
    goldens are the REAL corpus-drawn sets at ``knowledge/golden/{extraction,fidelity,retrieval}.json``
    (gitignored, perso) when in place, else the hand-labelled seed; an absent file is the D126
    default, a corrupt one RAISES (the loaders fail-close, never silently fall back to a laxer seed).
    A non-zero exit follows :attr:`CalibrationReport.all_clear` - fail-closed on every one of its
    conditions (D100 / D148): the fidelity gate AND a measured-and-trusted groundedness anchor,
    never a missing measurement."""
    # enforce_local_first FIRST (invariant 1 / D27): this loads Docling, and the posture is read once at
    # import. Added when widening the structural test's population from "opens Qdrant" to "loads weights"
    # showed this entry point had never been judged. real_runtime() below calls it again - it is idempotent.
    from .bootstrap import connect_docling, real_runtime
    from .local_first import enforce_local_first

    enforce_local_first()

    golden_dir = Path(__file__).resolve().parents[4] / "knowledge" / "golden"
    extraction_cases: Sequence[GoldenCase] = GOLDEN_SEED
    if (extraction_path := golden_dir / "extraction.json").exists():
        extraction_cases = load_extraction_golden(extraction_path)
    fidelity_cases: Sequence[FidelityCase] = FIDELITY_SEED
    if (fidelity_path := golden_dir / "fidelity.json").exists():
        fidelity_cases = load_fidelity_golden(fidelity_path)

    rt = real_runtime()
    # Fidelity is measured on the SAME two read paths prod ships (D69/D85): the runtime's fast reader
    # (``ocr=False``) for text-layer sources, and the OCR-enabled reader (``connect_docling(ocr=True)`` ->
    # OcrMac, prod's ``--retry-ocr`` brick) for the scans that come back empty under the fast path. Absent
    # this, the image-only scan cases would score 0 - a BUG, not the OCR quality the operator flips
    # ``source_extraction_trusted`` on. The composition reproduces the ``needs_ocr`` re-extract lifecycle.
    fidelity_read = _ocr_retry_reader(rt.source_reader.read, connect_docling(ocr=True).read)
    report = run_calibration(
        extract=_runtime_extractor(rt),
        read=fidelity_read,
        extraction_cases=extraction_cases,
        fidelity_cases=fidelity_cases,
        # The groundedness passages ARE the extraction golden's own case content (D148): the REAL
        # corpus-drawn text once extraction.json is in place, never a second invented source.
        passages=[case.content for case in extraction_cases],
    )
    print("CALIBRATION:", "ALL CLEAR" if report.all_clear else "BELOW BAR (fail-safe)")
    for gate in report.gates:
        verdict = "CLEARS -> trust" if gate.clears else "below -> fail-safe"
        print(
            f"  [{gate.name}] F1={gate.f1:.3f} vs bar {gate.threshold:.2f} "
            f"(P={gate.precision:.3f} R={gate.recall:.3f}, {gate.cases} case(s)) - {verdict}"
        )
    # Groundedness (D148) - the ACTUAL graph_extraction_trusted decision: no golden, no judge, just
    # whether every entity the extractor named came FROM the passage it read. Printed in full (not
    # just red/green) so a failure is diagnosable: both bars, the raw counts, and a few offenders.
    g = report.groundedness
    if g is None:  # pragma: no cover - run_calibration (called just above) always measures it
        print(
            "  [groundedness] NOT MEASURED - fail-closed, cannot certify graph_extraction_trusted"
        )
    else:
        verdict = "CLEARS -> trust" if g.trusted else "below -> fail-safe"
        print(
            f"  [groundedness] grounded={g.grounded:.3f} vs bar {MIN_GROUNDEDNESS:.2f}, "
            f"yield={g.yield_per_passage:.3f}/passage vs bar {MIN_YIELD:.2f} "
            f"({g.triples} triple(s) over {g.passages} passage(s)) - {verdict}"
        )
        if g.foreign:
            print(f"    {len(g.foreign)} foreign example(s) - why it failed, not just that it did:")
            for index, triple, words in g.foreign[:3]:
                print(f"      passage #{index} {triple} - foreign word(s): {', '.join(words)}")
    # The old triple-F1 ((3)-3c) - INFORMATIVE ONLY, never gating (D148). The hand-labelled golden froze
    # ONE valid triple decomposition per sentence, so exact match measured whether the extractor GUESSED
    # THE LABELLER'S FRAMING, not extraction quality (production/golden.py's module note has the full
    # measurement). Kept and printed for the record, same idiom as scaffold_only / anatomy_gaps elsewhere.
    ef1 = report.extraction_f1
    if ef1 is None:  # pragma: no cover - run_calibration (called just above) always measures it
        print("  [extraction F1] NOT MEASURED")
    else:
        print(
            f"  [extraction F1 - INFORMATIVE, NON-GATING] F1={ef1.f1:.3f} vs bar {MIN_EXTRACTION_F1:.2f} "
            f"(P={ef1.precision:.3f} R={ef1.recall:.3f}, {ef1.cases} case(s)) - "
            "not a verdict: the golden compares an arbitrary triple framing, see D148"
        )
    # The floor is swept over the REAL corpus golden ((3)-2b) when it is in place, else the seed. The golden
    # lives OUTSIDE git (verbatim corpus passages, perso) - an absent file is the D126 default, a corrupt
    # one RAISES (load_retrieval_golden fail-closes, never silently falls back to a laxer seed).
    retrieval_path = golden_dir / "retrieval.json"
    if retrieval_path.exists():
        retrieval_cases: Sequence[RetrievalCase] = load_retrieval_golden(retrieval_path)
        golden_src = f"real corpus golden ({retrieval_path.name})"
    else:
        retrieval_cases = RETRIEVAL_SEED
        golden_src = "hand-labelled SEED (no corpus golden in place yet)"
    floor = calibrate_floor_runtime(rt, cases=retrieval_cases)
    print(
        f"  [retrieval floor] earned {floor.floor:.3f} "
        f"(F1={floor.f1:.3f} P={floor.precision:.3f} R={floor.recall:.3f}, {floor.cases} case(s)) "
        f"over {golden_src} - recommendation, adopt via [OPERATOR] gesture (does not gate exit)"
    )
    return 0 if report.all_clear else 1


if __name__ == "__main__":  # pragma: no cover - machine-only entry
    import sys

    sys.exit(main())
