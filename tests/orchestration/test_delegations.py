"""I5 — does the system SEE what it delegated, or does it depend on my writing it down?

The trace this module reads is written by the host, so the risks are not the usual ones. Three ways
it could go wrong, and this file holds all three shut:

* it invents delegations (a directory that is absent is the ordinary case, not an error);
* it stays quiet on a session that really delegated — the whole point;
* it drops the SLOW delegations, which are precisely the ones worth surfacing.

Fixtures are shaped like the real files, whose structure was measured before any of this was
written: ``agentId`` · ``sessionId`` · ``timestamp`` on every event · the mandate as the first user
turn · the report as the last assistant turn.
"""

from __future__ import annotations

import json
from pathlib import Path

from mnemosyne.production.delegations import (
    Delegation,
    delegations_of,
    read_delegation,
    within,
)


def _event(kind: str, text: str, *, stamp: str, agent: str = "a1", session: str = "s1") -> dict:
    return {
        "type": kind,
        "agentId": agent,
        "sessionId": session,
        "timestamp": stamp,
        "message": {"role": kind, "content": [{"type": "text", "text": text}]},
    }


def _write(path: Path, events: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return path


def _agent(tmp: Path, name: str, events: list[dict]) -> Path:
    """One sub-agent transcript. The identity is stamped on every EVENT, as the host does — the
    module prefers it to the filename, and a fixture that left them disagreeing would be testing
    the fallback while pretending to test the normal case."""
    stamped = [{**e, "agentId": name} for e in events]
    return _write(tmp / "subagents" / f"agent-{name}.jsonl", stamped)


# --- it reads what the host really writes ------------------------------------------------------
def test_a_delegation_carries_its_mandate_its_report_and_its_window(tmp_path: Path) -> None:
    _agent(
        tmp_path,
        "a1",
        [
            _event("user", "You are an ISOLATED AUDITOR, refute my numbers", stamp="2026-08-14T16:45:34Z"),
            _event("assistant", "looking into it", stamp="2026-08-14T16:50:00Z"),
            _event("assistant", "VERDICT: three numbers do not hold", stamp="2026-08-14T17:08:11Z"),
        ],
    )

    (delegation,) = delegations_of(tmp_path)

    assert delegation.agent_id == "a1"
    assert "ISOLATED AUDITOR" in delegation.mandate  # what was ASKED
    assert "three numbers do not hold" in delegation.report  # what came BACK
    assert delegation.started == "2026-08-14T16:45:34Z"
    assert delegation.ended == "2026-08-14T17:08:11Z"
    assert delegation.turns == 3
    assert delegation.is_complete


def test_the_report_is_the_LAST_word_not_the_first(tmp_path: Path) -> None:
    """An agent narrates while it works; only its final turn is the return value. Quoting the first
    would surface *"I'll start by reading the code"* as the verdict of an audit."""
    _agent(
        tmp_path,
        "a1",
        [
            _event("user", "audit", stamp="2026-08-14T10:00:00Z"),
            _event("assistant", "I'll start by reading the code", stamp="2026-08-14T10:01:00Z"),
            _event("assistant", "CONCLUSION six defects", stamp="2026-08-14T10:30:00Z"),
        ],
    )

    (delegation,) = delegations_of(tmp_path)

    assert delegation.report.startswith("CONCLUSION")
    assert "I'll start" not in delegation.report


def test_a_delegation_that_never_answered_is_reported_not_hidden(tmp_path: Path) -> None:
    """An agent killed mid-flight is a fact about the task. Dropping it would make the count of
    delegations disagree with what the session actually did — and that count is the whole signal."""
    _agent(tmp_path, "dead", [_event("user", "audit this", stamp="2026-08-14T10:00:00Z")])

    (delegation,) = delegations_of(tmp_path)

    assert delegation.turns == 1
    assert not delegation.is_complete  # it is VISIBLE, and marked


# --- it does NOT invent delegations ------------------------------------------------------------
def test_a_session_that_delegated_nothing_is_silent(tmp_path: Path) -> None:
    """Most sessions delegate nothing. The empty tuple is what keeps a detector built on this quiet
    by default — the inverted half of Hermes's design, and the reason it can stay switched on."""
    assert delegations_of(tmp_path) == ()


def test_an_unreadable_or_torn_transcript_costs_only_itself(tmp_path: Path) -> None:
    """A transcript is appended to while the agent runs, so its last line can be torn."""
    path = _agent(tmp_path, "sain", [_event("user", "vas-y", stamp="2026-08-14T10:00:00Z")])
    with (path.parent / "agent-dechire.jsonl").open("w", encoding="utf-8") as handle:
        entier = _event("user", "bon debut", stamp="2026-08-14T11:00:00Z", agent="dechire")
        handle.write(json.dumps(entier) + "\n")
        handle.write('{"type": "assistant", "message": {"role": "assis')  # torn mid-write

    identifiants = {d.agent_id for d in delegations_of(tmp_path)}

    assert identifiants == {"sain", "dechire"}  # the torn one survives on its readable lines


def test_a_transcript_with_nothing_said_is_not_a_delegation(tmp_path: Path) -> None:
    """Tool results and scaffolding carry no text block. A file of nothing but those is not a
    delegation that happened — it is noise, and counting it would inflate the only number here."""
    _agent(
        tmp_path,
        "vide",
        [{"type": "user", "agentId": "vide", "timestamp": "2026-08-14T10:00:00Z", "message": None}],
    )

    assert delegations_of(tmp_path) == ()


def test_the_hosts_scaffolding_is_not_read_as_the_mandate(tmp_path: Path) -> None:
    """``<system-reminder>`` and friends ride inside user messages. Left in, the quoted mandate is
    the harness talking to itself — the exact defect a previous audit removed from the sibling."""
    _agent(
        tmp_path,
        "a1",
        [
            _event(
                "user",
                "<system-reminder>ritual reminder</system-reminder>",
                stamp="2026-08-14T10:00:00Z",
            ),
            _event("user", "here is your REAL mandate", stamp="2026-08-14T10:00:01Z"),
            _event("assistant", "received", stamp="2026-08-14T10:05:00Z"),
        ],
    )

    (delegation,) = delegations_of(tmp_path)

    assert delegation.mandate == "here is your REAL mandate"


# --- the window: the slow delegation is the one worth surfacing --------------------------------
def test_the_window_keeps_a_delegation_that_STARTED_before_the_task(tmp_path: Path) -> None:
    """The filter is on the END. A long audit launched before the operator's last prompt and
    landing after it belongs to THIS task: its result is what the agent has just read. Filtering on
    the start would drop exactly the slow ones — the only kind that carries a real finding."""
    lente = Delegation("lente", "s1", "2026-08-14T09:00:00Z", "2026-08-14T12:00:00Z", "m", "r", 2)
    ancienne = Delegation("vieille", "s1", "2026-08-13T09:00:00Z", "2026-08-13T09:30:00Z", "m", "r", 2)

    gardees = within([ancienne, lente], since="2026-08-14T11:00:00Z")

    assert [d.agent_id for d in gardees] == ["lente"]


def test_an_absent_boundary_shows_everything_rather_than_nothing(tmp_path: Path) -> None:
    """A caller that cannot compute a boundary must see the whole picture. Returning nothing would
    read as "this session delegated nothing", which is the one lie this module must not tell."""
    one = Delegation("a1", "s1", "2026-08-14T09:00:00Z", "2026-08-14T09:30:00Z", "m", "r", 2)

    assert within([one], since="") == (one,)


# --- the excerpt bound actually binds ----------------------------------------------------------
def test_the_excerpt_budget_binds_on_a_report_the_size_of_a_real_one(tmp_path: Path) -> None:
    """Measured: one real report weighed 707 825 bytes. A bound nothing exercises is a comment
    pretending to be a guarantee — this fixture fails the moment ``_EXCERPT`` stops cutting."""
    from mnemosyne.production.delegations import _EXCERPT

    enorme = "defaut numero " * 4000
    _agent(
        tmp_path,
        "bavard",
        [
            _event("user", "audit", stamp="2026-08-14T10:00:00Z"),
            _event("assistant", enorme, stamp="2026-08-14T10:30:00Z"),
        ],
    )

    (delegation,) = delegations_of(tmp_path)

    assert len(delegation.report) <= _EXCERPT + 1  # + the ellipsis
    assert len(delegation.report) < len(enorme)
    assert delegation.report.endswith("…")
    assert not delegation.report.rstrip("…").endswith(" ")  # cut on a word boundary


def test_delegations_come_back_oldest_first(tmp_path: Path) -> None:
    """Order is the reading order of a task: what was asked first, answered first."""
    _agent(tmp_path, "second", [_event("user", "b", stamp="2026-08-14T12:00:00Z")])
    _agent(tmp_path, "premier", [_event("user", "a", stamp="2026-08-14T09:00:00Z")])

    assert [d.agent_id for d in delegations_of(tmp_path)] == ["premier", "second"]


def test_a_missing_transcript_file_is_not_a_crash(tmp_path: Path) -> None:
    assert read_delegation(tmp_path / "nulle-part.jsonl") is None


# --- the block the hook would inject: pure, silent by default, honest about what it drops --------
def test_no_delegation_renders_NOTHING_at_all() -> None:
    """Silence is the default here as in both existing halves: 139 of 157 real sessions delegated
    nothing, and a block that speaks on those is furniture within a week."""
    from mnemosyne.production.delegations import rendre

    assert rendre(()) == ""


def test_the_block_quotes_what_was_ASKED_and_what_came_BACK() -> None:
    from mnemosyne.production.delegations import rendre

    bloc = rendre(
        (
            Delegation("a1", "s1", "2026-08-14T16:45Z", "2026-08-14T17:08Z",
                       "refute my numbers", "three do not hold", 12),
        )
    )

    assert "refute my numbers" in bloc  # the mandate
    assert "three do not hold" in bloc  # its last word
    assert "1 mandate(s)" in bloc
    assert "ALREADY-PAID" in bloc  # why it matters
    assert "silence is a valid result" in bloc  # nothing is demanded


def test_the_block_never_claims_the_audit_FOUND_something() -> None:
    """It names the MOMENT, never the verdict — reading "did it find a defect" from the report's
    prose would be a text detector, and review_signals measured what those cost."""
    from mnemosyne.production.delegations import rendre

    bloc = rendre((Delegation("a1", "s1", "", "", "audit", "all good, nothing to report", 4),))

    assert "what did it come back with" in bloc  # it ASKS
    assert "defect" not in bloc.split("→")[0]  # it does not ASSERT one in the quoted part


def test_a_long_list_says_what_it_LEFT_OUT() -> None:
    """One real session delegated 316 agents. A silent truncation reads as "I covered everything"."""
    from mnemosyne.production.delegations import _CITEES, rendre

    beaucoup = tuple(
        Delegation(f"a{i}", "s1", "", "", "mandat", "rapport", 3) for i in range(_CITEES + 5)
    )

    bloc = rendre(beaucoup)

    assert f"{len(beaucoup)} mandate(s)" in bloc  # the COUNT is whole
    assert "and 5 more, not quoted" in bloc  # what was dropped is NAMED


def test_a_delegation_that_answered_NOTHING_is_flagged_in_the_block() -> None:
    """An agent killed mid-flight is not an agent that agreed with me."""
    from mnemosyne.production.delegations import rendre

    bloc = rendre((Delegation("dead", "s1", "", "", "audit", "", 1),))

    assert "never spoke" in bloc
    assert "not an agent that agrees with you" in bloc  # and it is flagged


def test_une_delegation_EN_COURS_n_est_PAS_presentee_comme_un_rapport(tmp_path: Path) -> None:
    """The defect found IN PRODUCTION, on its own author, an hour after wiring it in.

    The block had quoted two still-running agents' passing narration — *"I'll start with the
    inventory…"* — under the label "report". It reads like a verdict. Measured afterwards: **nothing
    in these transcripts says a delegation has ended** (no end field, and the last event's type does
    not discriminate). So it no longer claims that.

    The inference kept is ONE-WAY and it is sound: if the last event is a tool return the agent has
    not yet picked back up, it has not finished. The converse is not knowable.
    """
    from mnemosyne.production.delegations import rendre

    subagents = tmp_path / "subagents"
    subagents.mkdir(parents=True)
    (subagents / "agent-alive.jsonl").write_text(
        "\n".join(
            json.dumps(e)
            for e in (
                _event("user", "audit", stamp="2026-08-15T10:00:00Z", agent="alive"),
                _event("assistant", "I'll start with the inventory", stamp="2026-08-15T10:05:00Z",
                       agent="alive"),
                # a tool return: no text block, and the agent has not picked it back up yet
                {"type": "user", "agentId": "alive", "timestamp": "2026-08-15T10:06:00Z",
                 "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}},
            )
        ),
        encoding="utf-8",
    )

    (delegation,) = delegations_of(tmp_path)
    bloc = rendre((delegation,))

    assert delegation.awaiting
    assert "STILL RUNNING" in bloc
    assert "NOT its report" in bloc
    assert "report:" not in bloc  # the word that used to lie is gone


def test_une_delegation_TERMINEE_n_est_pas_marquee_en_cours(tmp_path: Path) -> None:
    """The passing case: the last word of an agent that has picked the thread back up IS its report."""
    from mnemosyne.production.delegations import rendre

    _agent(
        tmp_path,
        "finished",
        [
            _event("user", "audit", stamp="2026-08-15T10:00:00Z"),
            _event("assistant", "VERDICT : six defects", stamp="2026-08-15T10:30:00Z"),
        ],
    )

    (delegation,) = delegations_of(tmp_path)
    bloc = rendre((delegation,))

    assert not delegation.awaiting
    assert "STILL RUNNING" not in bloc
    assert "VERDICT : six defects" in bloc
