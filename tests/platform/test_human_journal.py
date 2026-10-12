"""D82 - the replayable, fail-closed net under Moteur A's HUMAN layer.

Biting tests for :mod:`mnemosyne.production.human_journal`. The living graph's human layer (user's
validations / invalidations of a fiche) is the ONE thing that does not rebuild from ``raw/`` (D44 does
not cover it), so a crash would lose it irrecoverably. These prove the net closes that window: the
gesture is journaled to durable disk BEFORE it reaches RAM (write-ahead), a failed journal never
half-applies a gesture (fail-closed, the deliberate opposite of the best-effort observability sink),
the whole fiche survives a crash byte-for-byte (self-contained codec), and replay is idempotent.
"""

from __future__ import annotations

import json
from dataclasses import fields, replace
from datetime import datetime, timezone

from pytest import raises

from mnemosyne.ports import Bubble, Domain, GovernanceLabel, Provenance, Sensitivity
from mnemosyne.production import (
    Fiche,
    FicheType,
    HumanLayerJournal,
    LivingMemory,
    ValidationState,
)
from mnemosyne.production.human_journal import _decode_fiche, _encode_fiche


def _rich_fiche(*, fid: str = "f-rich") -> Fiche:
    """A deliberately RICH sensible fiche - recursive provenance, multiple domains, multi-version history -
    so the round-trip proves the codec drops nothing (the whole human layer is protected, D82 / D56)."""
    parent = Provenance(
        origin="doc:src",
        produced_by="ingest",
        at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )
    prov = Provenance(
        origin="doc:src",
        produced_by="distill",
        at=datetime(2026, 2, 3, 4, 5, 6, 7, tzinfo=timezone.utc),
        parents=(parent,),
    )
    label = GovernanceLabel(
        sensitivity=Sensitivity.SENSIBLE,
        bubble=Bubble("perso"),
        domains=frozenset({Domain("sante"), Domain("finance")}),
        provenance=prov,
    )
    return Fiche(
        id=fid,
        ftype=FicheType.FACT,
        content=frozenset({"fact A", "fact B"}),
        label=label,
        history=(frozenset({"old"}), frozenset({"even older", "x"})),
    )


def test_codec_roundtrip_preserves_the_whole_fiche() -> None:
    """``decode(encode(f)) == f`` for a rich fiche - the fidelity invariant the human layer rests on."""
    fiche = _rich_fiche()
    assert _decode_fiche(_encode_fiche(fiche)) == fiche


def test_writeahead_replay_rebuilds_the_human_layer(tmp_path) -> None:
    """A validated fiche survives a crash: journaled before RAM, replayed byte-for-byte into a fresh memory."""
    path = tmp_path / "human_layer.jsonl"
    memory = LivingMemory(journal=HumanLayerJournal(path))
    fiche = _rich_fiche(fid="f-sensible")
    memory.propose(fiche)
    memory.validate("f-sensible", human_validated=True)  # the explicit human gesture (D59-5)
    assert path.exists()  # the gesture is durable on disk

    revived = LivingMemory()  # a cold start - RAM lost
    HumanLayerJournal(path).replay(revived)
    assert revived.current("f-sensible") == replace(fiche, state=ValidationState.VALIDATED)


def test_validate_is_fail_closed_when_the_journal_cannot_write(tmp_path) -> None:
    """A journal that cannot write RAISES and the RAM is NOT mutated - no silent, half-applied gesture (D80)."""
    blocker = tmp_path / "blocker"
    blocker.write_text(
        "x", encoding="utf-8"
    )  # a FILE where a directory is needed -> the write-ahead fails
    memory = LivingMemory(journal=HumanLayerJournal(blocker / "human_layer.jsonl"))
    memory.propose(_rich_fiche(fid="f-fc"))

    with raises(OSError):
        memory.validate("f-fc", human_validated=True)
    # the fiche is still PROPOSED - the failed journal left no partial validation behind
    current = memory.current("f-fc")
    assert current is not None
    assert current.state == ValidationState.PROPOSED


def test_replay_is_idempotent(tmp_path) -> None:
    """Replaying the journal twice reaches the same state - safe to re-run after a crash mid-replay (inv. 24)."""
    path = tmp_path / "human_layer.jsonl"
    memory = LivingMemory(journal=HumanLayerJournal(path))
    memory.propose(_rich_fiche(fid="f-idem"))
    memory.validate("f-idem", human_validated=True)

    once = LivingMemory()
    HumanLayerJournal(path).replay(once)
    twice = LivingMemory()
    replayer = HumanLayerJournal(path)
    replayer.replay(twice)
    replayer.replay(twice)
    assert once.current("f-idem") == twice.current("f-idem")
    assert twice.current("f-idem").state == ValidationState.VALIDATED


def test_invalidate_is_journaled_and_replayed(tmp_path) -> None:
    """An invalidation (bi-temporal close) is journaled too - replay keeps the closed fiche closed (D60-2)."""
    path = tmp_path / "human_layer.jsonl"
    memory = LivingMemory(journal=HumanLayerJournal(path))
    memory.propose(_rich_fiche(fid="f-inv"))
    memory.validate("f-inv", human_validated=True)
    memory.invalidate("f-inv")

    revived = LivingMemory()
    HumanLayerJournal(path).replay(revived)
    assert all(f.id != "f-inv" for f in revived.reinject(Bubble("perso")))  # never resurfaces
    with raises(Exception):  # re-validating a closed fiche is refused (D60-2)
        revived.validate("f-inv", human_validated=True)


def test_no_journal_keeps_pure_in_memory_behaviour() -> None:
    """LivingMemory() with no journal behaves exactly as before - non-regression for unit tests (D126)."""
    memory = LivingMemory()
    memory.propose(_rich_fiche(fid="f-nojrnl"))
    validated = memory.validate("f-nojrnl", human_validated=True)
    assert validated.state == ValidationState.VALIDATED


def test_replay_refuses_an_unknown_event_kind(tmp_path) -> None:
    """An unknown event kind (a newer format) RAISES - replay never silently skips a human gesture (D82)."""
    path = tmp_path / "human_layer.jsonl"
    path.write_text(
        json.dumps({"v": 999, "kind": "teleport", "fiche_id": "x"}) + "\n", encoding="utf-8"
    )
    with raises(ValueError):
        HumanLayerJournal(path).replay(LivingMemory())


def test_replay_recovers_from_a_truncated_final_line(tmp_path) -> None:
    """A crash mid-append leaves a half-written final line; replay drops it (a never-committed gesture) and
    still restores every committed gesture - the very crash D82 exists to survive (F1)."""
    path = tmp_path / "human_layer.jsonl"
    memory = LivingMemory(journal=HumanLayerJournal(path))
    for fid in ("f-a", "f-b"):
        memory.propose(_rich_fiche(fid=fid))
        memory.validate(fid, human_validated=True)
    with path.open("a", encoding="utf-8") as handle:  # a torn tail: valid JSON prefix, no newline
        handle.write('{"v": 1, "ts": "2026-07-12T00:00:00Z", "kind": "vali')

    revived = LivingMemory()
    HumanLayerJournal(path).replay(revived)
    assert revived.current("f-a").state == ValidationState.VALIDATED
    assert revived.current("f-b").state == ValidationState.VALIDATED


def test_replay_raises_on_a_malformed_internal_line(tmp_path) -> None:
    """A malformed line that is NOT the last is real corruption - replay RAISES, never skips a committed
    gesture in silence (fail-closed, F1)."""
    path = tmp_path / "human_layer.jsonl"
    memory = LivingMemory(journal=HumanLayerJournal(path))
    for fid in ("f-a", "f-b"):
        memory.propose(_rich_fiche(fid=fid))
        memory.validate(fid, human_validated=True)
    good = path.read_text(encoding="utf-8").splitlines()
    path.write_text(good[0] + "\n" + "{garbage not json\n" + good[1] + "\n", encoding="utf-8")
    with raises(json.JSONDecodeError):
        HumanLayerJournal(path).replay(LivingMemory())


def test_encoder_covers_every_dataclass_field() -> None:
    """Structural guard (F5): every field of Fiche / GovernanceLabel / Provenance is encoded. A field added
    later that the codec forgets fails HERE, loudly, rather than vanishing from a validated fiche (D56)."""
    encoded = _encode_fiche(_rich_fiche())
    assert {f.name for f in fields(Fiche)} <= set(encoded)
    assert {f.name for f in fields(GovernanceLabel)} <= set(encoded["label"])
    assert {f.name for f in fields(Provenance)} <= set(encoded["label"]["provenance"])


def test_invalidate_is_fail_closed_when_the_journal_cannot_write(tmp_path) -> None:
    """Symmetric to validate (F6): a journal that cannot write makes invalidate RAISE and leaves the fiche
    OPEN - a close half-applied in RAM but unjournaled would re-surface VALIDATED at the next replay."""
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    memory = LivingMemory(journal=HumanLayerJournal(blocker / "human_layer.jsonl"))
    memory.propose(_rich_fiche(fid="f-inv-fc"))
    with raises(OSError):
        memory.invalidate("f-inv-fc")
    assert any(f.id == "f-inv-fc" for f in memory.proposed())  # still open, not closed
