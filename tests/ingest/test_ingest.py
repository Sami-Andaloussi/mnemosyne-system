"""Structural tests for LOT 4a - ingestion + classification + aiguilleur + benne.

This is NOT the 27-invariant ledger (that is ``test_invariants.py``, which promotes
invariant 18 against the classifier). Here we exercise the LOT 4a components directly:
the classifier's MAX-of-signals / fail-safe / raise-only behaviour (D101 / D100), the
deterministic aiguilleur routing rules (D57 write / D65 read), and the benne's raw-intake
realities (D85 - lifecycle, non-destructive dedup FLAG, bounded queue). Producer ≠
verifier (D75): an isolated audit checks this independently.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from mnemosyne.config import load_policy
from mnemosyne.ingest import (
    FIDELITY_SEED,
    Benne,
    CompositeSemanticSensor,
    ContentNature,
    DeterministicClassifier,
    DuplicateFlag,
    Engine,
    FidelityCase,
    FusedAnswer,
    LifecycleState,
    NullSemanticSensor,
    PlainTextSourceReader,
    QueryKind,
    SemanticSensor,
    fuse,
    load_fidelity_golden,
    route_ingest,
    route_read,
    score_fidelity,
)
from mnemosyne.ports import (
    Bubble,
    Classification,
    Classifier,
    CloisonnementError,
    DocId,
    Domain,
    Envelope,
    GovernanceLabel,
    ResourceBoundError,
    Sensitivity,
    Source,
    SourceReader,
)

# --- builders -------------------------------------------------------------------------


def _label(level: Sensitivity, bubble: str = "b", domains: tuple[str, ...] = ()) -> GovernanceLabel:
    return GovernanceLabel(
        sensitivity=level,
        bubble=Bubble(bubble),
        domains=frozenset(Domain(d) for d in domains),
    )


def _env(text: str, level: Sensitivity = Sensitivity.SENSIBLE) -> Envelope[str]:
    return Envelope(payload=text, label=_label(level))


class _RaisingSensor:
    """A semantic pass that raises the verdict to `sensible` (a legitimate raise, D100)."""

    def assess(self, content: str) -> Sensitivity:  # noqa: ARG002
        return Sensitivity.SENSIBLE


class _LoweringSensor:
    """A hostile semantic pass that always claims `public` - must be clamped (D100)."""

    def assess(self, content: str) -> Sensitivity:  # noqa: ARG002
        return Sensitivity.PUBLIC


class _BrokenSensor:
    """A semantic pass that errors - a failed assessment is doubt => `sensible` (D101)."""

    def assess(self, content: str) -> Sensitivity:  # noqa: ARG002
        raise RuntimeError("model unavailable")


class _SpySensor:
    """A semantic pass that RECORDS whether it was consulted - proves the ceiling short-circuit
    (a raise-only pass is skipped when the deterministic base is already at the top, (3)-4b dogfood)."""

    def __init__(self, verdict: Sensitivity = Sensitivity.SENSIBLE) -> None:
        self.calls = 0
        self._verdict = verdict

    def assess(self, content: str) -> Sensitivity:  # noqa: ARG002
        self.calls += 1
        return self._verdict


# --- classifier (D101 / invariant 18) -------------------------------------------------


def test_classifier_conforms_to_the_port() -> None:
    assert isinstance(DeterministicClassifier(), Classifier)
    assert isinstance(NullSemanticSensor(), SemanticSensor)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("transfer IBAN FR76 3000 1007 9412 3456 7890 185", Sensitivity.SENSIBLE),
        ("card 4970 1000 0000 0000", Sensitivity.SENSIBLE),
        ("No. 1 84 12 75 116 001 42", Sensitivity.SENSIBLE),  # French NIR
        ("doctor's prescription, MRI scheduled", Sensitivity.SENSIBLE),
        ("contact john.doe@example.com", Sensitivity.PERSO),
        ("call me at 06 12 34 56 78", Sensitivity.PERSO),
        ("hello world, this is public", Sensitivity.PUBLIC),
    ],
)
def test_pii_floor_by_class(text: str, expected: Sensitivity) -> None:
    # domain_signal=public isolates the floor: max(floor, public, none) == floor.
    verdict = DeterministicClassifier().classify(text, domain_signal=Sensitivity.PUBLIC)
    assert verdict.floor is expected
    assert verdict.sensitivity is expected


def test_classifier_takes_the_max_of_signals() -> None:
    clf = DeterministicClassifier()
    # domain raises a clean text; floor raises past a public domain hint.
    assert clf.classify("nothing", domain_signal=Sensitivity.PERSO).sensitivity is Sensitivity.PERSO
    iban = clf.classify("IBAN FR76 3000 1007 9412", domain_signal=Sensitivity.PUBLIC)
    assert iban.sensitivity is Sensitivity.SENSIBLE


def test_fail_safe_sensible_without_a_domain_hint() -> None:
    clf = DeterministicClassifier()
    assert clf.classify("hello").sensitivity is Sensitivity.SENSIBLE  # doubt => sensible
    # ... but an explicit public domain + clean content clears to public (canal A alive).
    cleared = clf.classify("hello", domain_signal=Sensitivity.PUBLIC)
    assert cleared.sensitivity is Sensitivity.PUBLIC


def test_hostile_semantic_cannot_lower_the_verdict() -> None:
    clf = DeterministicClassifier(semantic=_LoweringSensor())
    # base kept BELOW the ceiling (an email floors at PERSO) so the sensor IS consulted - proving its
    # `public` claim is CLAMPED by max, not obeyed. At the ceiling it would be skipped (tested below).
    verdict = clf.classify("contact john.doe@example.com", domain_signal=Sensitivity.PUBLIC)
    assert (
        verdict.sensitivity is Sensitivity.PERSO
    )  # the PERSO floor holds; the public claim is ignored
    assert verdict.semantic_signal is Sensitivity.PUBLIC  # the opinion is recorded, not obeyed


def test_public_provenance_declassifies_below_the_floor() -> None:
    # The ONE seam that may pull a verdict UNDER the deterministic floor: the standing HUMAN
    # declassification for public-source zones (D100-2 / D107). A published book / YouTube transcript
    # trips PII false positives (an author email, "prescription", an ISBN shaped like a card number) that
    # would floor it to SENSIBLE - public_provenance overrides that to authoritative PUBLIC, and the
    # semantic pass is not even consulted (a published source is public whatever its wording).
    pii = "contact john.doe@example.com - prescription, MRI scheduled - card 4970 1000 0000 0000"
    spy = _SpySensor(Sensitivity.SENSIBLE)
    clf = DeterministicClassifier(semantic=spy)
    assert (
        clf.classify(pii).sensitivity is Sensitivity.SENSIBLE
    )  # no provenance: the PII floor holds
    verdict = clf.classify(pii, public_provenance=True)  # the human gesture: authoritative PUBLIC
    assert verdict.sensitivity is Sensitivity.PUBLIC
    assert verdict.floor is Sensitivity.PUBLIC  # the floor is reset so the invariant holds honestly
    assert verdict.semantic_signal is None and spy.calls == 0  # the pass is bypassed, not obeyed


def test_raising_semantic_lifts_the_verdict() -> None:
    clf = DeterministicClassifier(semantic=_RaisingSensor())
    verdict = clf.classify("harmless text", domain_signal=Sensitivity.PUBLIC)
    assert verdict.sensitivity is Sensitivity.SENSIBLE
    assert verdict.semantic_signal is Sensitivity.SENSIBLE


def test_semantic_error_degrades_to_sensible() -> None:
    clf = DeterministicClassifier(semantic=_BrokenSensor())
    verdict = clf.classify("text", domain_signal=Sensitivity.PUBLIC)
    assert verdict.sensitivity is Sensitivity.SENSIBLE


def test_semantic_pass_is_skipped_when_the_base_is_already_at_the_ceiling() -> None:
    # (3)-4b dogfood: the semantic pass is RAISE-ONLY (invariant 18), so once the deterministic base is
    # SENSIBLE (the fail-safe default with no domain hint) no assessment can change the verdict - it is
    # NOT consulted, saving a wasted (model-backed, ~30 s) call. Behaviour is identical (D100-2).
    spy = _SpySensor()
    clf = DeterministicClassifier(semantic=spy)
    verdict = clf.classify(
        "harmless text"
    )  # no domain hint => domain fail-safes to SENSIBLE (the ceiling)
    assert verdict.sensitivity is Sensitivity.SENSIBLE
    assert spy.calls == 0  # a raise-only pass cannot exceed the ceiling => never consulted
    assert verdict.semantic_signal is None  # honestly recorded: the pass did not run


def test_semantic_pass_still_runs_below_the_ceiling_and_can_raise() -> None:
    # below the ceiling the pass DOES run (it may legitimately raise) - the skip is a pure optimisation
    # at the top, never a loss of discrimination lower down (invariant 18 intact).
    spy = _SpySensor(Sensitivity.PERSO)
    clf = DeterministicClassifier(semantic=spy)
    verdict = clf.classify(
        "harmless text", domain_signal=Sensitivity.PUBLIC
    )  # base = PUBLIC < ceiling
    assert spy.calls == 1  # consulted
    assert verdict.sensitivity is Sensitivity.PERSO  # the raise took effect
    assert verdict.semantic_signal is Sensitivity.PERSO


def test_composite_semantic_maxes_and_stays_raise_only() -> None:
    # (3)-6: the LLM sensor + the Presidio PII sensor share the ONE semantic slot via a MAX composite. A
    # raising sub-sensor lifts the verdict; an abstaining one is ignored - the composite can only RAISE.
    composite = CompositeSemanticSensor((NullSemanticSensor(), _RaisingSensor()))
    assert composite.assess("x") is Sensitivity.SENSIBLE  # max(None, sensible) = sensible
    assert CompositeSemanticSensor((NullSemanticSensor(), NullSemanticSensor())).assess("x") is None
    # wired into the classifier, it lifts a clean text - and a LOWERING sub-sensor still cannot pull
    # below the deterministic floor (the composite maxes, the classifier floors, invariant 18).
    clf = DeterministicClassifier(
        semantic=CompositeSemanticSensor((_LoweringSensor(), _RaisingSensor()))
    )
    verdict = clf.classify("IBAN FR76 3000 1007 9412", domain_signal=Sensitivity.PUBLIC)
    assert (
        verdict.sensitivity is Sensitivity.SENSIBLE
    )  # floor + raising both hold; lowering ignored


def test_classification_records_its_floor_and_never_sits_below_it() -> None:
    verdict = DeterministicClassifier().classify("IBAN FR76 3000 1007 9412")
    assert isinstance(verdict, Classification)
    assert verdict.sensitivity >= verdict.floor  # the structural guarantee (invariant 18)


# --- aiguilleur (D57 write / D65 read) ------------------------------------------------


def test_route_ingest_unclassified_is_never_living() -> None:
    # An unlabeled datum -> Moteur B only, even if the caller declares a living nature.
    route = route_ingest(GovernanceLabel.unlabeled(), nature=ContentNature.BEHAVIOUR)
    assert route.engines == frozenset({Engine.DOCUMENTARY})


def test_route_ingest_by_nature() -> None:
    label = _label(Sensitivity.PERSO)
    assert route_ingest(label).engines == frozenset({Engine.DOCUMENTARY})  # default document
    assert route_ingest(label, nature=ContentNature.BEHAVIOUR).engines == frozenset({Engine.LIVING})
    assert route_ingest(label, nature=ContentNature.OPINION).engines == frozenset({Engine.LIVING})


def test_route_read_asymmetry_defaults_to_both() -> None:
    assert route_read(QueryKind.PERSONAL).engines == frozenset({Engine.LIVING})
    assert route_read(QueryKind.FACTUAL).engines == frozenset({Engine.DOCUMENTARY})
    both = frozenset({Engine.LIVING, Engine.DOCUMENTARY})
    assert route_read(QueryKind.GENERAL).engines == both
    assert route_read().engines == both  # doubt default = both (D65)


def test_read_fusion_is_realized_bubble_scoped_side_by_side() -> None:
    # the D65 read fusion, a LOT 4a seam, is realized in LOT 6: it keeps the two engines side
    # by side (never overwriting) and is bubble-scoped (deep coverage in test_production).
    living = (_env("pref", Sensitivity.PUBLIC),)
    documentary = (_env("fact", Sensitivity.PUBLIC),)
    fused = fuse(living, documentary, bubble=Bubble("b"))
    assert isinstance(fused, FusedAnswer)
    assert fused.frame == living and fused.facts == documentary  # neither overwritten (D65)
    foreign = (Envelope(payload="leak", label=_label(Sensitivity.PERSO, bubble="other")),)
    with pytest.raises(CloisonnementError):
        fuse(foreign, (), bubble=Bubble("b"))


def test_fusion_keeps_working_material_as_a_third_bucket_and_maxes_sensitivity() -> None:
    # D137: Moteur B splits by role - endorsed ``facts`` and ``working_material`` stay SEPARATE (a raw
    # draft is never conflated with a source), and sensitivity is the max over ALL three buckets so a
    # SENSIBLE working-material item still carries sensible-local downstream (D65 / D27).
    living = (_env("pref", Sensitivity.PUBLIC),)
    facts = (_env("endorsed", Sensitivity.PUBLIC),)
    working = (_env("draft", Sensitivity.SENSIBLE),)
    fused = fuse(living, facts, bubble=Bubble("b"), working_material=working)
    assert fused.frame == living and fused.facts == facts and fused.working_material == working
    assert fused.sensitivity is Sensitivity.SENSIBLE  # max INCLUDES the working-material bucket


def test_fusion_refuses_a_foreign_bubble_working_material_item() -> None:
    # D137: the bubble-scope guarantee bites on working material exactly as on frame/facts - a
    # foreign-bubble draft can never fuse into another bubble's answer (invariant 3 / D54-8).
    foreign_working = (Envelope(payload="leak", label=_label(Sensitivity.PERSO, bubble="other")),)
    with pytest.raises(CloisonnementError):
        fuse((), (), bubble=Bubble("b"), working_material=foreign_working)


# --- benne (D85) ----------------------------------------------------------------------


def test_lifecycle_is_forward_only() -> None:
    assert LifecycleState.RAW < LifecycleState.INDEXED < LifecycleState.DISTILLED
    assert LifecycleState.DISTILLED < LifecycleState.VALIDATED
    benne = Benne(capacity=8)
    item, _ = benne.intake(DocId("d"), _env("x"))
    assert item.state is LifecycleState.RAW
    advanced = item.advance(LifecycleState.INDEXED)
    assert advanced.state is LifecycleState.INDEXED
    with pytest.raises(ValueError, match="backward"):
        advanced.advance(LifecycleState.RAW)


def test_benne_advance_stores_the_moved_item() -> None:
    benne = Benne(capacity=8)
    benne.intake(DocId("d"), _env("x"))
    benne.advance(DocId("d"), LifecycleState.INDEXED)
    assert benne.item(DocId("d")).state is LifecycleState.INDEXED


def test_intake_is_bounded_fail_closed() -> None:
    benne = Benne(capacity=1)
    benne.intake(DocId("d1"), _env("one"))
    with pytest.raises(ResourceBoundError):
        benne.intake(DocId("d2"), _env("two"))


def test_from_policy_reads_the_intake_bound() -> None:
    benne = Benne.from_policy(load_policy())
    item, flag = benne.intake(DocId("d"), _env("x"))  # capacity 256 => accepted
    assert item.state is LifecycleState.RAW and flag is None


def test_near_duplicate_is_flagged_non_destructively() -> None:
    benne = Benne(capacity=8)
    a = "the black cat sleeps peacefully on the very large red comfortable couch"
    b = "the black cat sleeps peacefully on the very large blue comfortable couch"
    benne.intake(DocId("d1"), _env(a))
    _, flag = benne.intake(DocId("d2"), _env(b))
    assert isinstance(flag, DuplicateFlag)
    assert flag.doc == DocId("d2") and flag.similar_to == DocId("d1")
    assert flag.similarity >= 0.8
    # non-destructive: BOTH copies are still held (the human arbitrates, D85).
    assert benne.item(DocId("d1")).doc == DocId("d1")
    assert benne.item(DocId("d2")).doc == DocId("d2")


def test_distinct_content_is_not_flagged() -> None:
    benne = Benne(capacity=8)
    benne.intake(DocId("d1"), _env("the black cat sleeps on the couch"))
    _, flag = benne.intake(DocId("d2"), _env("quarterly report on software sales"))
    assert flag is None


def test_benne_preserves_the_raw_source_for_re_extraction() -> None:
    # (3)-4 / D85: a BINARY intake keeps its raw Source on the item (truth-first) - re-extractable if the
    # OCR was poor / failed; a plain-text intake carries source=None (nothing raw to keep).
    benne = Benne(capacity=8)
    src = Source("scan.pdf", b"raw-bytes", "application/pdf")
    item, _ = benne.intake(DocId("d"), _env("extracted text"), source=src)
    assert item.source is src
    plain, _ = benne.intake(DocId("p"), _env("just text"))
    assert plain.source is None


def test_intake_refuses_an_oversize_raw_source() -> None:
    # (3)-6: a per-source BYTE ceiling refuses one huge media before it is buffered (orthogonal to the
    # queue-depth count), so a single over-size file cannot exhaust RAM even on an empty queue (inv. 16).
    benne = Benne(capacity=8, max_source_bytes=16)
    ok = Source("small.bin", b"under-cap", "application/octet-stream")  # 9 bytes < 16 => accepted
    item, _ = benne.intake(DocId("ok"), _env("x"), source=ok)
    assert item.source is ok
    big = Source("huge.mp4", b"x" * 64, "video/mp4")  # 64 bytes ≥ 16 => refused fail-closed
    with pytest.raises(ResourceBoundError):
        benne.intake(DocId("big"), _env("y"), source=big)


def test_byte_cap_does_not_apply_to_text_only_intake() -> None:
    # the byte ceiling guards the RAW source bytes; a plain-text intake (source=None) is never affected.
    benne = Benne(capacity=8, max_source_bytes=1)  # a 1-byte cap
    item, _ = benne.intake(DocId("t"), _env("a long text with many more than one byte"))
    assert item.source is None  # accepted - no raw source to bound


def test_from_policy_reads_the_byte_bound_fail_closed() -> None:
    # from_policy now reads BOTH bounds fail-closed (a missing one raises); a normal source lands well
    # under the 256 MiB protected-zone ceiling.
    benne = Benne.from_policy(load_policy())
    src = Source("doc.pdf", b"a small document", "application/pdf")
    item, _ = benne.intake(DocId("d"), _env("text"), source=src)
    assert item.source is src


# --- source ingestion prise (D125-B5, (3)-4) --------------------------------------------


def test_plain_text_source_reader_is_a_source_reader() -> None:
    reader = PlainTextSourceReader()
    assert isinstance(reader, SourceReader)  # conforms to the promoted ports prise (D125-B5)
    assert (
        reader.read(Source("ref", "already some text".encode("utf-8"), "text/plain"))
        == "already some text"
    )


def test_plain_text_source_reader_never_raises_on_adversarial_bytes() -> None:
    # D100-3: the stub decodes untrusted bytes with errors="replace" - a garbage source degrades to a
    # decodable string (then scored LOW by the fidelity golden), never a crash.
    out = PlainTextSourceReader().read(Source("x", b"\xff\xfe bad", "application/octet-stream"))
    assert isinstance(out, str)


# --- ingestion fidelity golden-set (D125-B6, (3)-4) -------------------------------------


def test_fidelity_golden_trusts_a_faithful_reader() -> None:
    # the utf-8 stub recovers the seed text perfectly => F1 1.0 => trusted (a faithful reader clears it).
    score = score_fidelity(PlainTextSourceReader().read, FIDELITY_SEED)
    assert score.f1 == 1.0 and score.trusted


def test_fidelity_golden_distrusts_a_lossy_reader() -> None:
    # a reader that recovers NOTHING scores recall 0 => below the bar => low-fidelity flag, never trusted.
    def lossy(source: Source) -> str:
        return ""

    score = score_fidelity(lossy, FIDELITY_SEED)
    assert score.recall == 0.0 and not score.trusted


def test_fidelity_golden_is_fail_closed_on_an_empty_set() -> None:
    # D69: a golden with nothing to recover can never vacuously certify a reader - fail-CLOSED (F1 0).
    empty = (FidelityCase(Source("x", b"", "text/plain"), ""),)
    score = score_fidelity(PlainTextSourceReader().read, empty)
    assert score.f1 == 0.0 and not score.trusted


def test_fidelity_golden_scores_a_raising_reader_as_untrusted() -> None:
    # (3)-4a audit: a reader that RAISES on a case is a FAILED recovery (recall loss), scored untrusted -
    # never aborting the run, never certified by silence.
    def raising(source: Source) -> str:
        raise RuntimeError("reader boom")

    score = score_fidelity(raising, FIDELITY_SEED)
    assert score.recall == 0.0 and not score.trusted


# --- benne hardening ((3)-4a audit: the benne is newly load-bearing on the capture path) ------


def test_benne_refuses_re_intake_non_destructively() -> None:
    # audit MAJEUR 1: the benne is append-only (D85 / invariant 2) - re-intaking a held DocId is
    # REFUSED, so a reused id can never silently clobber a preserved raw source (losing the datum).
    benne = Benne(capacity=8)
    src = Source("first.pdf", b"AAAA", "application/pdf")
    benne.intake(DocId("dup"), _env("first"), source=src)
    with pytest.raises(ValueError, match="non-destructive"):
        benne.intake(
            DocId("dup"), _env("second"), source=Source("second.pdf", b"BBBB", "application/pdf")
        )
    assert benne.item(DocId("dup")).source is src  # the original raw source survives (D85)


def test_benne_dedup_is_cloisonnement_scoped() -> None:
    # audit MAJEUR 2: dedup only compares within the SAME partition + bubble (invariant 1 / 3), so a
    # near-duplicate is never flagged across sensitivities - no cross-partition metadata leak.
    benne = Benne(capacity=8)
    benne.intake(DocId("s"), _env("the exact same text", Sensitivity.SENSIBLE))
    _, flag = benne.intake(DocId("p"), _env("the exact same text", Sensitivity.PERSO))
    assert flag is None  # a different sensitivity => never compared, never flagged
    _, same = benne.intake(DocId("s2"), _env("the exact same text", Sensitivity.SENSIBLE))
    assert same is not None and same.similar_to == DocId("s")  # still works WITHIN a cloisonnement


def test_benne_does_not_flag_empty_extractions_as_duplicates() -> None:
    # audit MINEUR 1: two blank / failed extractions (empty text) are NOT "duplicates" - an empty
    # payload is not compared, so a failed OCR never falsely reads as a near-duplicate of another (F3).
    benne = Benne(capacity=8)
    benne.intake(DocId("e1"), _env(""))
    _, flag = benne.intake(DocId("e2"), _env(""))
    assert flag is None


# --- loading a real corpus fidelity golden ((3) ignition) - the gitignored JSON that expands the seed -
# Symmetric to test_stores' retrieval-golden tests. Bytes ride base64 in `data_b64` (a scanned-PDF page
# travels inline, no companion file). Fail-closed (F3 / D100): a malformed golden - including invalid
# base64 - RAISES rather than silently yielding an empty source that could vacuously certify a reader.
# The corpus bytes/text live outside git (perso); these tests use synthetic temp files (form/parsing only).


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _write_fidelity_golden(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "fidelity.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_fidelity_golden_parses_cases_and_decodes_bytes(tmp_path: Path) -> None:
    path = _write_fidelity_golden(
        tmp_path,
        [
            {
                "ref": "a.txt",
                "data_b64": _b64("hello world"),
                "mime": "text/plain",
                "expected_text": "hello world",
            },
            {
                "ref": "b.pdf",
                "data_b64": _b64("%PDF-scan"),
                "mime": "application/pdf",
                "expected_text": "scanned words",
            },
        ],
    )
    cases = load_fidelity_golden(path)
    assert isinstance(cases, tuple) and all(isinstance(c, FidelityCase) for c in cases)
    assert cases[0].source.ref == "a.txt" and cases[0].source.data == b"hello world"
    assert cases[0].source.mime == "text/plain" and cases[0].expected_text == "hello world"
    assert cases[1].source.data == b"%PDF-scan"  # base64 round-trips to the raw source bytes


def test_load_fidelity_golden_ignores_extra_keys(tmp_path: Path) -> None:
    # unknown keys (e.g. an inline `_note` / `_kind`) are ignored, never a parse failure.
    path = _write_fidelity_golden(
        tmp_path,
        [
            {
                "ref": "a.txt",
                "data_b64": _b64("x"),
                "mime": "text/plain",
                "expected_text": "x",
                "_kind": "note",
            }
        ],
    )
    assert load_fidelity_golden(path)[0].source.ref == "a.txt"


def test_loaded_fidelity_golden_feeds_the_scorer_end_to_end(tmp_path: Path) -> None:
    # the wiring the ignition run uses: a loaded golden scores exactly like the seed. A faithful reader
    # (utf-8 decode) clears the bar over the loaded case (F1 1.0); a reader that recovers nothing is
    # fail-closed (recall 0) - the posture an empty scan takes, which is exactly why the scan case matters.
    path = _write_fidelity_golden(
        tmp_path,
        [
            {
                "ref": "a.txt",
                "data_b64": _b64("recover me"),
                "mime": "text/plain",
                "expected_text": "recover me",
            }
        ],
    )
    cases = load_fidelity_golden(path)
    assert score_fidelity(lambda src: src.data.decode("utf-8"), cases).trusted
    assert not score_fidelity(lambda _src: "", cases).trusted


@pytest.mark.parametrize(
    "payload",
    [
        [],  # an empty golden proves nothing - a laxer set must never come from a blank file
        {
            "ref": "a",
            "data_b64": "eA==",
            "mime": "text/plain",
            "expected_text": "x",
        },  # a bare object, not a list
        [{"data_b64": "eA==", "mime": "text/plain", "expected_text": "x"}],  # no ref
        [
            {"ref": "  ", "data_b64": "eA==", "mime": "text/plain", "expected_text": "x"}
        ],  # blank ref
        [{"ref": "a", "mime": "text/plain", "expected_text": "x"}],  # no data_b64
        [{"ref": "a", "data_b64": "eA==", "expected_text": "x"}],  # no mime
        [
            {"ref": "a", "data_b64": "eA==", "mime": "text/plain", "expected_text": 7}
        ],  # expected_text not a string
        [
            {
                "ref": "a",
                "data_b64": "not valid base64!!",
                "mime": "text/plain",
                "expected_text": "x",
            }
        ],  # corrupt base64
    ],
)
def test_load_fidelity_golden_fails_closed_on_a_malformed_file(
    tmp_path: Path, payload: object
) -> None:
    with pytest.raises(ValueError):
        load_fidelity_golden(_write_fidelity_golden(tmp_path, payload))


def test_load_fidelity_golden_raises_on_non_json(tmp_path: Path) -> None:
    # a corrupt (non-JSON) file RAISES (JSONDecodeError is a ValueError) - never a silent empty fallback.
    path = tmp_path / "fidelity.json"
    path.write_text("this is not json {", encoding="utf-8")
    with pytest.raises(ValueError):
        load_fidelity_golden(path)
