"""Mnemosyne runtime - the kinetic layer (D123 LOT 5).

The engine room: what actually RUNS the models and keeps a long session honest, on
top of the Guard (LOT 3) and the three stores (LOT 4b). Each piece realizes a deferred
barrier and plugs the model seams left by earlier lots - all behind the Guard (D89), all
under non-derivation (D100).

**Barriers realized here (D109 tier (1)).**

* Invariant 27 (grammar-constrained output - :mod:`.runner`): the decoder is bound to a
  grammar, so a malformed tool call is structurally impossible (D104).
* Invariant 12 (replayability - :mod:`.snapshots` + :mod:`.observability`): every model call
  leaves a replayable snapshot in the protected store, and the greppable log is
  ``sensible``-clean (D76-(1) / D111 / D71).
* Invariant 11 (crystallisation - :mod:`.crystallise`): LLM->code only with producer != verifier
  AND equivalence crossed on a frozen golden set (D75).
* Invariant 13 (memory outside the weights - :mod:`.finetune`): a fine-tuned model carries a
  versioned, reconstructible recipe (D76 / D115).
* Invariant 15 (persist-before-compact - :mod:`.compactor`): nothing compacts until the
  durable content is retrievable in external memory (D77-e).
* Invariant 26 (pause -> slot release): realized in the scheduler
  (:class:`~mnemosyne.guard.BoundedScheduler`, with the queue-bound of invariant 16) - a
  suspended item releases its concurrency slot (D96 / D95).

**Model seams filled (D100 / D89).** :mod:`.models` wires the classifier's semantic pass (4a)
and the graph's fact extractor (4b) to the local runner behind the Guard; :mod:`.bootstrap`
assembles the whole stack (D94).

**Scope boundary (lean scaffolding, D98).** The scheduler LIVES with the resource bounds
(:mod:`mnemosyne.guard.bounds`) because concurrency is a bound (D95 / D78); this package holds
the pieces the D93 engine drives. The broader D93 loop - trigger cadence, execute-each-step,
crash recovery from the replayable journal (D82) - and the per-workflow scored golden DATA
(pyramid tier (2), content) carry no LOT 5 invariant and are wired at (3), kept as named seams
rather than hollow adapters. Code & docstrings English (D117); ``public`` / ``perso`` /
``sensible`` keep their French tokens (D33 / D66).
"""

from __future__ import annotations

from .backup import BackupEngine, BackupRefused, KopiaBackup, OffSiteTarget, PRECIOUS_TARGETS
from .bootstrap import Runtime, bootstrap
from .calibration import (
    CalibrationReport,
    GateCalibration,
    calibrate_floor_runtime,
    calibrate_runtime,
    run_calibration,
)
from .compactor import Compactor, CompactionResult, PersistBeforeCompact
from .crystallise import (
    Crystalliser,
    CrystallisationRefused,
    CrystallisedPath,
    GoldenCase,
    GoldenSet,
    ShadowRunner,
)
from .engine import DrainReport, OrchestrationEngine, WorkflowFn
from .finetune import FineTuneManifest, ManifestError
from .health import (
    DegradationPlan,
    HardwareProbe,
    HealthMonitor,
    StubHardwareProbe,
    graceful_degradation,
    may_start_heavy_run,
)
from .heavy import HeavyRunRefused, default_health_probe, guarded_heavy_run
from .model_router import ModelRouter
from .models import ModelFactExtractor, ModelSemanticSensor
from .observability import LocalObservability, TraceSink, fan_out
from .runner import GenerationBackend, LocalRunner, MalformedOutput, enforce_grammar
from .runner_mlx import load_mlx_backend
from .smoke import (
    HumanPrerequisite,
    PrerequisiteState,
    SmokeReport,
    SmokeStep,
    check_human_prerequisites,
    run_smoke_test,
)
from .snapshots import (
    ReplayId,
    ReplaySnapshot,
    SnapshotBackend,
    SnapshotStore,
    connect_snapshot_store,
)

__all__ = [
    # runner (D104 / invariant 27) - barriers host + injectable decode seam ((3)-2c)
    "LocalRunner",
    "GenerationBackend",
    "load_mlx_backend",
    "MalformedOutput",
    "enforce_grammar",
    # replayable snapshots (D76 / invariant 12) - RAM default + on-disk backend (CF3, (3)-11)
    "SnapshotStore",
    "SnapshotBackend",
    "connect_snapshot_store",
    "ReplaySnapshot",
    "ReplayId",
    # observability (D111 / invariant 12 / 22)
    "LocalObservability",
    "TraceSink",
    "fan_out",
    # health view + graceful degradation (D111)
    "HealthMonitor",
    "HardwareProbe",
    "StubHardwareProbe",
    "DegradationPlan",
    "graceful_degradation",
    "may_start_heavy_run",
    # guarded heavy run (Q1) - the seam the heavy CLI entrypoints wrap their work in
    "guarded_heavy_run",
    "HeavyRunRefused",
    "default_health_probe",
    # backup (D110 / D118)
    "KopiaBackup",
    "BackupEngine",
    "OffSiteTarget",
    "BackupRefused",
    "PRECIOUS_TARGETS",
    # smoke test 1-click + human prerequisites (D109 / D121-E4)
    "run_smoke_test",
    "SmokeReport",
    "SmokeStep",
    "check_human_prerequisites",
    "HumanPrerequisite",
    "PrerequisiteState",
    # crystallisation (D75 / invariant 11)
    "Crystalliser",
    "CrystallisedPath",
    "CrystallisationRefused",
    "GoldenSet",
    "GoldenCase",
    "ShadowRunner",
    # fine-tune manifest (D76 / D115 / invariant 13)
    "FineTuneManifest",
    "ManifestError",
    # compactor (D77 / invariant 15)
    "Compactor",
    "CompactionResult",
    "PersistBeforeCompact",
    # model seams behind the Guard (D100 / D89)
    "ModelSemanticSensor",
    "ModelFactExtractor",
    # task-class -> model router (D7 - model-agnostic, config-driven, frontier-default)
    "ModelRouter",
    # orchestration engine (D93) - the loop that DRIVES the scheduler substrate
    "OrchestrationEngine",
    "DrainReport",
    "WorkflowFn",
    # bootstrap (D94)
    "Runtime",
    "bootstrap",
    # calibration - the (3)-7 closure instrument (D69 / golden bars) + the (3)-2a earned recall floor
    "run_calibration",
    "calibrate_runtime",
    "calibrate_floor_runtime",
    "CalibrationReport",
    "GateCalibration",
]
