"""The D109 test pyramid - étages (2)(3)(4) (the three non-invariant tiers).

D109 separates the *hard barrier* (étage (1) = the 27 invariants, in
``test_invariants.py``) from *quality / convergence / liveness*:

* **(2) Golden sets** - per-workflow ``input -> expected`` cases, scored by a metric
  (DeepEval), the promotion gate (D69) and the OSS-bump safety net (EX7).
* **(3) Three-store integration** - after a write cycle ``.md``/git <-> Qdrant <->
  graph converge, and a crash mid-cycle replays idempotently (D105).
* **(4) One-click smoke** - one command: ingest -> index -> retrieve -> answer; the
  "everything-is-fine" button a non-technical user runs after any change.

At LOT 2 these are *frames*, not data: each fixes the contract of its tier and
stays ``xfail`` pending the lot that fills it. No golden data is fabricated and no
``sensible`` is exported to be tested (contenant, not contenu - D98; D27 / D66).
The harness lives in ``_invariants`` (pytest-optional, D116). Code English (D117).
"""

from __future__ import annotations

from _invariants import PYRAMID, methods, pending, pyramid_tier

from mnemosyne.ports import Classifier, IntentLog, Runner, Skill, TruthStore, VectorIndex
from mnemosyne.runtime import GoldenCase, GoldenSet, ShadowRunner, run_smoke_test


@pyramid_tier(2, name="golden sets per workflow (quality gate)", lot="5")
def test_pyramid_2_golden_sets_gate_promotion() -> None:
    # Live (LOT 5) - the *contenant* is built: a FROZEN golden set scores a candidate by
    # equivalence (D75), the mechanism a DeepEval-scored per-workflow gate drives. Building
    # this harness is what makes invariant 11 (crystallisation) green.
    golden = GoldenSet(cases=(GoldenCase(input="2+2", expected="4"),))
    assert ShadowRunner().equivalence(lambda _q: "4", golden) == 1.0  # a match scores 1.0
    assert ShadowRunner().equivalence(lambda _q: "5", golden) == 0.0  # a miss scores 0.0
    # Pending - the per-workflow, DeepEval-scored golden DATA (the *contenu*) is deferred to
    # usage: no golden data is fabricated now, none exported to be tested (D98 / D27 / D66).
    pending("per-workflow DeepEval golden DATA (protected zone SE4)", lot="5")


@pyramid_tier(3, name="three-store integration (.md/git <-> Qdrant <-> graph)", lot="4b")
def test_pyramid_3_three_stores_converge_and_replay_is_idempotent() -> None:
    # Live - the three store ports exist and the idempotent-replay mechanism (the
    # crash-safety substrate of invariant 24) is on the IntentLog.
    assert {"write", "read", "invalidate"} <= methods(TruthStore)
    assert "replay" in methods(IntentLog)
    # Pending - after a write cycle the truth, the vector index and the graph
    # CONVERGE, and a crash mid-cycle replays to the same final state (D105).
    # The hard-barrier facet is invariant 24; this tier is the end-to-end check.
    pending("end-to-end 3-store convergence + crash replay", lot="4b")


@pyramid_tier(4, name="one-click smoke test", lot="7")
def test_pyramid_4_one_click_smoke() -> None:
    # Live - every port the smoke path threads exists: the Skill I/O contract, the
    # Classifier, the VectorIndex and the Runner (ingest -> index -> retrieve -> answer).
    for port in (Skill, Classifier, VectorIndex, Runner):
        assert getattr(port, "_is_protocol", False), f"{port.__name__} must be a Protocol"
    # Realized (LOT 7) - the contenant is built: run_smoke_test drives one command end to end
    # on the assembled runtime (bootstrap -> capture -> index -> retrieve -> answer), all LOCAL,
    # and FLAGs the human, out-of-band prerequisites (D109 (4) / D121-E4). This is the
    # "everything-is-fine" button a non-technical user runs after any change.
    report = run_smoke_test()
    assert report.passed, "the 1-click smoke must go green on the assembled runtime"
    names = [s.name for s in report.steps]
    assert names == [
        "bootstrap",
        "capture",
        "source",
        "index",
        "graph",
        "living",
        "retrieve",
        "recall",
        "answer",
        "tools",
        "agent",
        "render",
    ]
    assert len(report.flags) == 3  # ADP / Kopia key / API ceiling all FLAG by default (E4)
    # Realized ((3)-3c) - the smoke FRAME now threads ALL FIVE bricks behind the ports: the retrieval
    # legs (bge-m3 + Qdrant + tantivy, (3)-2a/2b), the MLX runner (answer, (3)-2c) AND the LadybugDB
    # graph ((3)-3a) with Moteur A's faits->fiches factory + plan-B valve (the "living" step, (3)-3c).
    # Pending - only the SAME smoke over the REAL installed bricks rather than the stubs: a running
    # server / real weights can't gate the brick-free suite (D126), so that run stays the out-of-band
    # `make smoke`. No sensible is ever exported to test it (D98 / D27 / D66).
    pending("1-click smoke over the real installed bricks (out-of-band make smoke)", lot="7")


def test_pyramid_registers_the_three_non_invariant_tiers() -> None:
    # Étage (1) is the 27 invariants (test_invariants.py); étages (2)(3)(4) are here.
    assert set(PYRAMID) == {2, 3, 4}, f"étages (2)(3)(4) must be registered; got {sorted(PYRAMID)}"
