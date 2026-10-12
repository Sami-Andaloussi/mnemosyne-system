"""What this session DELEGATED — read from the trace the host already writes (I5).

The half of the learning loop that neither the operator's words nor my commits can carry. An audit
came back with six defects; a run failed; a measurement refuted a hypothesis. None of that is in the
operator's turns (:func:`~.review_signals.detect` reads those), and none of it reaches ``git`` unless
I choose to write it there (:func:`~.review_signals.detect_trace` reads that). Between the two sits
the class the operator named: *"lessons it surfaces for itself from execution, from audits, from an
error or a failed run"*.

**This module exists because the premise of its own plan item was wrong TWICE in one day, and the
measurement won both times.** Worth writing down, because the shape repeats:

1. *"an audit's output passes through repo code"* — no. The audit of 2026-08-14 (Opus, ~209 000
   tokens) is **absent from** ``spend.jsonl``: 15 entries that day, none above 1 000 input tokens.
   It ran through the host's tooling, entirely outside Mnémosyne. And no run journal exists.
2. *"so the trace must be BUILT"* — no again, and this one nearly cost a whole mechanism. The host
   already writes **one durable transcript per sub-agent**, and nothing reads them: **1 137 files
   across 18 sessions**, up to **316 for a single one**.

So there is nothing to journal and no discipline to rely on — *the fix was already asleep in the
repo*. Reading them is local, model-free and network-free, exactly the class of ``sessions.py``:
invariant 1 forbids shipping a transcript to a SECOND model by automatism, never reading one's own
on one's own machine.

**What this does NOT buy, and it is the same warning the trace half already carries.** It says a
delegation HAPPENED, with its exact words. It never says whether the delegation FOUND anything —
judging that from the report's prose would be a text detector, and ``review_signals`` has just
measured what those cost. The judgement stays with the agent.

**Replayed on the 1 137 real transcripts before anything was built on it** — a reader whose only
proof is its own fixtures proves that the fixtures parse:

* **1 137 read across 18 sessions**, 0 without a legible mandate, 0 without a timestamp, and **1
  without a report** — a delegation killed mid-flight, surfaced rather than dropped;
* **139 of 157 session directories delegated NOTHING**, and cost **0.01 ms** to say so. The median
  session costs **0 ms**: silence is the ordinary case and it is free.

**And the cost is published rather than optimised away, because the worst case is real**: the
session holding **316** delegations takes **1.1 s** — every file is read whole, since the mandate is
its first turn and the report its last. Whoever wires this into a hook inherits that number. Two
tempting shortcuts are deliberately NOT taken: filtering on file mtime before parsing (a different
clock from the event timestamps — it would drop delegations silently, and a silent loss is worse
than a slow read), and reading only the head and tail of each file (the turn count would become a
guess). *A door slower than the wall is never used — so the number is stated, not hidden.*

Decisions: D155 · D75 (the audit is delegated, so its output is where the lesson lives) · invariant
1 (a transcript stays local) · invariant 2 (read-only, this module never writes) · D126 (stdlib).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

#: Where the host files a delegated agent's transcript, relative to the session's own directory.
#:
#: Measured rather than assumed: the sub-agent of 2026-08-14 lives at
#: ``…/<project>/<session-id>/subagents/agent-<agent-id>.jsonl``, and the ``.output`` path the tool
#: reports is a SYMLINK to it. Following the symlink is what makes this durable — the link sits in
#: a temp directory that does not survive, the target does.
SUBAGENT_DIR: Final = "subagents"

#: A mandate and a report are quoted, never dumped: one real report was **707 825 bytes**. The bound
#: is exercised by a witness that would fail if it were removed — a bound nothing tests is a comment
#: pretending to be a guarantee, which is exactly what got deleted from ``review_signals``.
_EXCERPT: Final = 400


@dataclass(frozen=True, slots=True)
class Delegation:
    """One delegated sub-agent: who, when, what it was asked, what it answered."""

    agent_id: str
    session_id: str
    started: str
    ended: str
    mandate: str
    report: str
    turns: int
    #: True when the transcript's last event is a turn the agent has NOT answered yet (a tool
    #: result waiting for it). One-way and sound: if it holds, the delegation is still running or
    #: dead — either way its last words are NOT a report. The converse is not knowable, see below.
    awaiting: bool = False

    @property
    def is_complete(self) -> bool:
        """True when the agent said something — NOT that it finished. The distinction is measured.

        **NOTHING IN THESE TRANSCRIPTS SAYS A DELEGATION ENDED.** Checked across every sub-agent
        file on this machine: no terminal field, and the last event's type does not discriminate —
        a finished audit ends on an ``assistant`` turn, and so does a running one between two tool
        calls. Only ``mtime`` separates them, and that is a different clock, the very shortcut this
        module refuses elsewhere because it loses data in silence.

        So this says *"the agent spoke at least once"*, and the renderer never calls its last words
        a report. **Measured the day it was built, in production, on its own author**: the block
        quoted two live agents' mid-flight narration (*"I'll start with the inventory…"*) under the
        label "returned". It read as a verdict. It was a sentence said in passing.
        """
        return bool(self.report)


def _text_of(message: Any) -> str:
    """The spoken text of one transcript message — text blocks only, host scaffolding stripped.

    Borrowed from :mod:`.sessions` rather than re-implemented: two parsers of the same format drift,
    and this one would drift silently because nothing compares them.
    """
    from .sessions import _message_text

    return _message_text(message)


def _events(path: Path) -> Iterator[dict[str, Any]]:
    """Every parsable JSON object of a transcript, tolerant by construction.

    A transcript is appended to while the agent runs, so the last line can be torn. A line that will
    not parse is SKIPPED — fail-open on the read side, like every replay in this package. A file
    that cannot be opened at all yields nothing rather than raising: one unreadable agent must never
    cost the whole session's picture.
    """
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event


def _clip(text: str) -> str:
    """Flatten and bound — enough to recognise the mandate or the verdict, never a wall of text."""
    flat = " ".join(text.split())
    if len(flat) <= _EXCERPT:
        return flat
    cut = flat.rfind(" ", 0, _EXCERPT)
    return flat[: cut if cut > 0 else _EXCERPT] + "…"


def read_delegation(path: Path) -> Delegation | None:
    """One sub-agent transcript → its :class:`Delegation`, or ``None`` when nothing was said.

    The **mandate** is the agent's first user turn — the prompt whoever delegated actually wrote.
    The **report** is its last assistant turn, which the host tells sub-agents *is* the return
    value. Both are quoted, bounded by :data:`_EXCERPT`.
    """
    agent_id = session_id = ""
    started = ended = ""
    mandate = report = ""
    turns = 0
    dernier_genre = ""
    for event in _events(path):
        agent_id = agent_id or str(event.get("agentId") or "")
        session_id = session_id or str(event.get("sessionId") or "")
        stamp = str(event.get("timestamp") or "")
        if stamp:
            started = started or stamp
            ended = stamp
        kind = event.get("type")
        if kind not in ("user", "assistant"):
            continue
        # Tracked on EVERY conversational event, before the emptiness filter: a tool result carries
        # no text block, and it is exactly the shape that proves the agent has not answered yet.
        dernier_genre = str(kind)
        text = _text_of(event.get("message"))
        if not text:
            continue
        turns += 1
        if kind == "user" and not mandate:
            mandate = _clip(text)
        elif kind == "assistant":
            report = _clip(text)
    if not turns:
        return None
    return Delegation(
        agent_id=agent_id or path.stem.removeprefix("agent-"),
        session_id=session_id,
        started=started,
        ended=ended,
        mandate=mandate,
        report=report,
        turns=turns,
        awaiting=dernier_genre == "user",
    )


def delegations_of(session_dir: Path) -> tuple[Delegation, ...]:
    """Every delegation of one session, oldest first — empty when the session delegated nothing.

    ``session_dir`` is the session's own directory beside its transcript. An absent ``subagents/``
    is the ordinary case, not an error: **most sessions delegate nothing**, and the empty tuple is
    what keeps a detector built on this silent by default.
    """
    root = session_dir / SUBAGENT_DIR
    try:
        files = sorted(root.glob("agent-*.jsonl"))
    except OSError:
        return ()
    found = [read_delegation(path) for path in files]
    return tuple(sorted((d for d in found if d), key=lambda d: (d.started, d.agent_id)))


def within(delegations: Sequence[Delegation], *, since: str) -> tuple[Delegation, ...]:
    """Those that ENDED at or after ``since`` — the task window the Stop hook already computes.

    **The filter is on the END, and that is the whole correctness of this function.** A long audit
    launched before the operator's last prompt and landing after it belongs to THIS task: its result
    is what the agent has just read, and its lesson is due now. Filtering on the start would drop
    exactly the delegations worth surfacing — the slow ones.

    An empty ``since`` returns everything rather than nothing: a caller that cannot compute a
    boundary must see the whole picture, never a silently empty one.
    """
    if not since:
        return tuple(delegations)
    return tuple(d for d in delegations if d.ended and d.ended >= since)


#: How many delegations the block QUOTES. Not a cap on the COUNT — the count is always stated in
#: full, and what is dropped is NAMED. Measured reason: one session delegated **316** agents, and a
#: 316-line wall is how a block teaches its reader to skip it. *A silent truncation reads as "I
#: covered everything"; this one says what it left out.*
_CITEES: Final = 3


def rendre(delegations: Sequence[Delegation]) -> str:
    """The block the Stop hook would inject. Empty string when nothing was delegated.

    **PURE, and handed its population — that is the hook's own doctrine, written in ``stop.sh``:**
    *"a judge that fetches its own population can find it EMPTY and return a green"*. Here green
    means *"nothing was delegated, so no lesson"*, which is exactly the sentence a missing directory
    would produce for free. So the caller globs the disk; this function only judges what it is given.

    **It names the MOMENT, never the verdict.** It says a delegation happened and quotes the
    words. It never says the audit found something — reading that from the report's prose would be
    a text detector, and ``review_signals`` measured what those cost. The question it asks is the
    one that cannot be dodged: *what did it come back with?* — where *"did you learn anything?"*
    is dodged every time.
    """
    if not delegations:
        return ""
    total = len(delegations)
    muettes = sum(1 for d in delegations if not d.is_complete)
    lignes = [
        f"[Mnémosyne · end-of-task review — WHAT YOU DELEGATED] This task entrusted "
        f"{total} mandate(s) to an isolated agent. What they found is neither in the operator's "
        f"words, nor in your commits: this is the only place it exists.",
        "",
    ]
    for delegation in delegations[:_CITEES]:
        lignes.append(f"  • {delegation.agent_id} — {delegation.turns} turn(s)")
        if delegation.mandate:
            lignes.append(f"      asked: « {delegation.mandate} »")
        # "LAST WORD", never "report". Nothing in these transcripts says a delegation has
        # ended (measured: no end field, and the last event's type does not discriminate).
        # Calling the last sentence of an agent that is still running its "report" makes a
        # passing narration read as a verdict — happened the same day, on its own author.
        if not delegation.report:
            lignes.append("      last word: NOTHING — this agent never spoke.")
        elif delegation.awaiting:
            lignes.append(f"      last word: « {delegation.report} »")
            lignes.append(
                "      \U000023F3 STILL RUNNING (or dead): it has not answered the last tool "
                "return. This is NOT its report."
            )
        else:
            lignes.append(f"      last word: « {delegation.report} »")
        lignes.append("")
    if total > _CITEES:
        lignes.append(f"  …and {total - _CITEES} more, not quoted here.")
        lignes.append("")
    if muettes:
        lignes.append(
            # Used to say "an agent DIED mid-flight", corrected on 2026-08-15 after a session
            # report from a chat that had believed it. Measured: an agent labelled "dead" by this
            # message returned a complete, useful verdict 12 MINUTES later — the reader had
            # launched a second audit on the strength of that word. The snapshot was accurate AT
            # THE MOMENT it was taken; it was the word that concluded in its place. *An instant
            # state named in the PAST TENSE reads as a DEFINITIVE state.*
            f"\U000026A0\U0000FE0F {muettes} of these mandates RETURNED NOTHING AT THIS INSTANT — an agent may still "
            "speak after this snapshot, check before replacing it. But a silent agent is "
            "not an agent that agrees with you."
        )
        lignes.append("")
    lignes.append(
        "→ The question, and it cannot be dodged: **what did it come back with that you did not "
        "already know?** A defect found by a third party is an ALREADY-PAID lesson — if it is "
        "recorded nowhere, it will only have existed in a conversation."
    )
    lignes.append(
        "If the report held nothing durable, say so in one line and stop — "
        "silence is a valid result, not a failure."
    )
    return "\n".join(lignes)
