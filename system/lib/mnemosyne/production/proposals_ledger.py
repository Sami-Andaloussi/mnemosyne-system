"""ProposalsLedger — the durable, replayable landing for NON-rebuildable living-memory proposals (item 2 / D82).

Sibling to :class:`~mnemosyne.production.human_journal.HumanLayerJournal`, and deliberately SEPARATE from it.
The human-layer journal protects the user's GESTURES (validate / invalidate) — the part of Moteur A that does NOT
rebuild from ``raw/`` (D44 / D82). A *proposal* is not a gesture, and MOST proposals are rebuildable: the bulk
fact extractor (③-3c) re-proposes its fiches on the next ingest, so journaling them would bloat the precious
gesture journal with a derived, reconstructible signal and blur its identity (audit ``ebf0846`` MAJOR-1).

But ONE proposal is not rebuildable: a ``make remember`` LEARNING (:func:`~mnemosyne.production.learning_fiche`)
is a one-shot capture, stored WHOLE, with no documentary backup and nothing that re-proposes it. Held only in
:class:`~mnemosyne.production.memory.LivingMemory`'s RAM it dies with the short-lived ``remember`` process — the
exact loss this ledger closes. So the durability decision lives at the CALL SITE:
:meth:`~mnemosyne.production.memory.LivingMemory.propose` writes here ONLY when its caller passes
``durable=True`` (:meth:`~mnemosyne.api.CoreApi.remember`); the extractor / aggregator paths leave it False,
because they rebuild from ``raw/`` (D44).

Three properties mirror the human journal (D80 / D82); the fourth is consciously relaxed:

* **Append-only, self-contained, ordered.** Each ``propose`` event carries the WHOLE :class:`Fiche` via the
  SAME faithful codec the human journal uses (one round-trip invariant, no drift) — replay reconstructs the
  proposal with no dependency on re-extraction.
* **fsync'd per line.** A capture survives a power loss, not merely a process crash.
* **Fail-closed on write.** :meth:`~mnemosyne.production.memory.LivingMemory.propose` records here BEFORE it
  mutates RAM, so an I/O error leaves neither a ledger line nor a RAM fiche (consistent) — and never PRETENDS a
  capture was saved when it was not (the very bug this fixes). A lost proposal is merely re-capturable (unlike
  an irreversible human gesture), so this is fail-closed for honesty, not for irreversibility.

**Replay is SECOND (D82 restore order).** :func:`~mnemosyne.runtime.bootstrap` replays the human journal FIRST
(validations / invalidations), THEN this ledger: :meth:`~mnemosyne.production.memory.LivingMemory._restore_proposed`
drops any id already VALIDATED or INVALIDATED, so a since-decided learning is never resurrected (closed stays
closed, D60-2).

**Where it lives.** ``system/state/proposals.jsonl`` — the same LOCAL, gitignored (``system/state/*.jsonl``),
Kopia-PRECIOUS convention as the human journal (a LEARNING may be ``perso`` / ``sensible`` — sensible-local,
D27 / D71). Code & docstrings English (D117).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

# The faithful Fiche codec is defined ONCE, in human_journal (the test-suite already imports it cross-module,
# so it is a de-facto shared production codec). Reused here so a proposal and a gesture serialize a fiche
# byte-identically — a single round-trip invariant, no second codec to drift (D44 spirit).
from .human_journal import _decode_fiche, _encode_fiche

if (
    TYPE_CHECKING
):  # avoid the memory ⇄ ledger import cycle — memory.py type-hints ProposalsLedger too
    from pathlib import Path

    from .memory import Fiche, LivingMemory


def _utcnow_iso() -> str:
    """A wall-clock UTC stamp for a durable record — ISO-8601 with a ``Z`` suffix (like the human journal)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class ProposalsLedger:
    """Append-only, replayable ledger of durable (non-rebuildable) living-memory proposals (item 2 / D82).

    Wired into :class:`~mnemosyne.production.memory.LivingMemory` (which calls :meth:`record_propose` on a
    genuine ``durable=True`` registration, BEFORE mutating RAM) and rebuilt at cold start by :meth:`replay`,
    AFTER the human journal so a since-decided id is not resurrected. See the module docstring for WHY this is
    kept separate from :class:`~mnemosyne.production.human_journal.HumanLayerJournal`."""

    #: Event schema version — bumped on any breaking change to the record shape; replay refuses an unknown
    #: ``kind`` rather than silently skip a durably-recorded capture (a NEWER format ⇒ fail-closed, D82).
    _FORMAT: int = 1

    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        self._path = path

    def _append(self, event: dict[str, Any]) -> None:
        """Append one event as an fsync'd JSONL line (open-append-close per line) — fail-CLOSED (D80 / D82).

        The parent dir is created if absent, then the line is written, flushed to the OS AND ``os.fsync``'d so
        the capture survives a power loss, not merely a process crash. ANY I/O error PROPAGATES to the caller
        so the RAM mutation is not applied on a failed record — never a silent swallow."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def record_propose(self, fiche: Fiche) -> None:
        """Durably record a proposal BEFORE it reaches RAM — the whole fiche travels (self-contained)."""
        self._append(
            {
                "v": self._FORMAT,
                "ts": _utcnow_iso(),
                "kind": "propose",
                "fiche": _encode_fiche(fiche),
            }
        )

    def replay(self, memory: LivingMemory) -> None:
        """Rebuild durable proposals from the stream, in append order — idempotent, run AFTER the human journal.

        Each ``propose`` restores its fiche as PROPOSED UNLESS its id was already validated (in ``_fiches`` from
        the human journal) or invalidated (in ``_invalidated``) — :meth:`~mnemosyne.production.memory.LivingMemory._restore_proposed`
        enforces "closed / decided stays so" (D60-2). An absent ledger is a NO-OP.

        Same fail-closed replay discipline as the human journal: a truncated FINAL line (a crash mid-append that
        RAM never saw) is dropped; a malformed INTERNAL line is real corruption and RAISES; an unknown ``kind``
        (a newer format) RAISES — never silently skip a durably-recorded capture."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return  # no ledger yet ⇒ nothing to restore
        lines = raw.splitlines()
        last_nonempty = max((i for i, ln in enumerate(lines) if ln.strip()), default=-1)
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                if idx == last_nonempty:
                    break  # truncated final line ⇒ a never-committed capture — correct to drop (D82)
                raise  # a malformed INTERNAL line is real corruption — fail-closed, never skip a capture
            kind = event["kind"]
            if kind == "propose":
                memory._restore_proposed(_decode_fiche(event["fiche"]))
            else:
                raise ValueError(
                    f"unknown proposals-ledger event kind {kind!r} — refusing to skip a durable capture "
                    "(a newer format? bump the reader, never drop a proposal — item 2 / D82)"
                )
