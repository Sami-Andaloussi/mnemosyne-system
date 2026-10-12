"""item 2 / D82 - the durable landing that makes ``make remember`` actually persist.

Biting tests for :mod:`mnemosyne.production.proposals_ledger`. A ``make remember`` LEARNING is proposed in a
SHORT-LIVED process; before this ledger the proposal lived only in that process's RAM and evaporated on exit
(audit ``ebf0846`` MAJOR-1, found live: the human-gesture journal records validate / invalidate, never a
proposal). These prove the ledger closes that window WITHOUT resurrecting a since-decided learning:

* a ``durable=True`` proposal survives a cold start (the bug fix), a ``durable=False`` one does NOT (the
  rebuildable extractor path stays out, D44);
* the write is fail-closed (a ledger that cannot write leaves no RAM fiche either);
* replay runs AFTER the human journal, so a since-VALIDATED learning is not demoted and a since-DISMISSED one
  is not resurrected - even when it is later re-``remember``ed (the closed-stays-closed contract, D60-2);
* the same fail-closed replay discipline as the human journal (unknown kind raises, torn final line drops).
"""

from __future__ import annotations

import json

from pytest import raises

from mnemosyne.ports import Bubble, GovernanceLabel, Sensitivity
from mnemosyne.production import (
    HumanLayerJournal,
    LivingMemory,
    ProposalsLedger,
    ValidationState,
    learning_fiche,
)


def _learning(text: str, *, bubble: str = "perso", sens: Sensitivity = Sensitivity.SENSIBLE):
    """A realistic captured LEARNING fiche - the exact object ``make remember`` proposes durably."""
    return learning_fiche(text, GovernanceLabel(sensitivity=sens, bubble=Bubble(bubble)))


def _cold_start(human_path, ledger_path) -> LivingMemory:
    """Rebuild a fresh living memory exactly as ``bootstrap`` does: human journal FIRST, ledger SECOND."""
    memory = LivingMemory(
        journal=HumanLayerJournal(human_path), proposals_ledger=ProposalsLedger(ledger_path)
    )
    HumanLayerJournal(human_path).replay(memory)
    ProposalsLedger(ledger_path).replay(memory)
    return memory


def test_durable_proposal_survives_a_cold_start(tmp_path) -> None:
    """THE bug fix: a `make remember` learning proposed durably reappears in the queue after the process dies."""
    ledger_path = tmp_path / "proposals.jsonl"
    memory = LivingMemory(proposals_ledger=ProposalsLedger(ledger_path))
    fiche = _learning("user prefers make targets over ad-hoc scripts")
    memory.propose(fiche, durable=True)
    assert ledger_path.exists()  # the capture is durable on disk, not RAM-only

    revived = LivingMemory()  # a cold start - RAM lost
    ProposalsLedger(ledger_path).replay(revived)
    assert [f.id for f in revived.proposed()] == [fiche.id]  # it rejoined the validation queue


def test_non_durable_proposal_is_not_ledgered(tmp_path) -> None:
    """The extractor path (durable=False, the default) rebuilds from raw/ - it must leave NO ledger line."""
    ledger_path = tmp_path / "proposals.jsonl"
    memory = LivingMemory(proposals_ledger=ProposalsLedger(ledger_path))
    memory.propose(_learning("a rebuildable extractor fiche"))  # durable defaults False
    assert not ledger_path.exists()

    revived = LivingMemory()
    ProposalsLedger(ledger_path).replay(revived)
    assert revived.proposed() == ()  # nothing to restore - it comes back from raw/, not here


def test_durable_write_is_fail_closed(tmp_path) -> None:
    """A ledger that cannot write RAISES and the RAM is NOT mutated - never PRETEND a capture was saved (D80)."""
    blocker = tmp_path / "blocker"
    blocker.write_text(
        "x", encoding="utf-8"
    )  # a FILE where a directory is needed -> the append fails
    memory = LivingMemory(proposals_ledger=ProposalsLedger(blocker / "proposals.jsonl"))
    with raises(OSError):
        memory.propose(_learning("doomed capture"), durable=True)
    assert memory.proposed() == ()  # write-ahead failed before RAM - no half-applied proposal


def test_validated_learning_is_not_demoted_by_the_ledger(tmp_path) -> None:
    """Replay order (human journal FIRST): a since-VALIDATED learning is not knocked back to PROPOSED."""
    human_path, ledger_path = tmp_path / "human.jsonl", tmp_path / "proposals.jsonl"
    memory = LivingMemory(
        journal=HumanLayerJournal(human_path), proposals_ledger=ProposalsLedger(ledger_path)
    )
    fiche = _learning("a learning user later validated")
    memory.propose(fiche, durable=True)  # -> ledger (PROPOSED)
    memory.validate(fiche.id, human_validated=True)  # -> human journal (VALIDATED)

    revived = _cold_start(human_path, ledger_path)
    assert (
        revived.current(fiche.id).state == ValidationState.VALIDATED
    )  # ledger did NOT resurrect PROPOSED


def test_dismissed_learning_is_not_resurrected_even_when_re_remembered(tmp_path) -> None:
    """The resurrection hole this fix closes: a DISMISSED learning stays closed at replay AND on a later
    re-`remember` - the invalidate survives only in the human journal (its proposal skipped), so `propose`
    must no-op on `_invalidated` INDEPENDENT of `_fiches` presence (D60-2 / anti-noise, item 2)."""
    human_path, ledger_path = tmp_path / "human.jsonl", tmp_path / "proposals.jsonl"
    memory = LivingMemory(
        journal=HumanLayerJournal(human_path), proposals_ledger=ProposalsLedger(ledger_path)
    )
    fiche = _learning("a learning user dismissed")
    memory.propose(fiche, durable=True)
    memory.invalidate(fiche.id)  # user rejects it -> human journal (invalidate)

    revived = _cold_start(
        human_path, ledger_path
    )  # human replay: _invalidated only; ledger: skipped
    assert revived.proposed() == ()  # not resurrected at cold start
    assert fiche.id not in {f.id for f in revived.proposed()}

    # re-`remember` the SAME learning in the new session: still a no-op, and NOT re-written to the ledger
    lines_before = ledger_path.read_text(encoding="utf-8").count("\n")
    revived.propose(_learning("a learning user dismissed"), durable=True)
    assert revived.proposed() == ()  # closed stays closed
    assert ProposalsLedger(ledger_path)  # ledger object usable
    assert (
        ledger_path.read_text(encoding="utf-8").count("\n") == lines_before
    )  # no new line appended


def test_ledger_replay_is_idempotent(tmp_path) -> None:
    """Replaying the ledger twice reaches the same state - safe to re-run after a crash mid-replay (inv. 24)."""
    ledger_path = tmp_path / "proposals.jsonl"
    memory = LivingMemory(proposals_ledger=ProposalsLedger(ledger_path))
    fiche = _learning("an idempotently-replayed learning")
    memory.propose(fiche, durable=True)

    twice = LivingMemory()
    replayer = ProposalsLedger(ledger_path)
    replayer.replay(twice)
    replayer.replay(twice)
    assert [f.id for f in twice.proposed()] == [fiche.id]


def test_no_ledger_keeps_pure_in_memory_behaviour(tmp_path) -> None:
    """LivingMemory() with no ledger accepts durable=True as a plain in-memory propose - non-regression (D126)."""
    memory = LivingMemory()
    fiche = _learning("a learning with no durable store wired")
    proposed = memory.propose(fiche, durable=True)
    assert proposed.state == ValidationState.PROPOSED
    assert [f.id for f in memory.proposed()] == [fiche.id]


def test_ledger_replay_refuses_an_unknown_event_kind(tmp_path) -> None:
    """An unknown event kind (a newer format) RAISES - replay never silently drops a durable capture (D82)."""
    ledger_path = tmp_path / "proposals.jsonl"
    ledger_path.write_text(json.dumps({"v": 999, "kind": "teleport"}) + "\n", encoding="utf-8")
    with raises(ValueError):
        ProposalsLedger(ledger_path).replay(LivingMemory())


def test_ledger_replay_recovers_from_a_truncated_final_line(tmp_path) -> None:
    """A crash mid-append leaves a half-written final line; replay drops it (a never-committed capture) and
    still restores every committed proposal - same discipline as the human journal."""
    ledger_path = tmp_path / "proposals.jsonl"
    memory = LivingMemory(proposals_ledger=ProposalsLedger(ledger_path))
    fiche = _learning("a committed learning before the crash")
    memory.propose(fiche, durable=True)
    with ledger_path.open(
        "a", encoding="utf-8"
    ) as handle:  # a torn tail: valid JSON prefix, no newline
        handle.write('{"v": 1, "ts": "2026-07-17T00:00:00Z", "kind": "prop')

    revived = LivingMemory()
    ProposalsLedger(ledger_path).replay(revived)
    assert [f.id for f in revived.proposed()] == [fiche.id]
