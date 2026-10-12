"""The tick daemon (Q3) — the thin always-on wake that keeps the proactive nerve firing between sessions.

These prove the wake reuses the governed tick end-to-end and records an append-only, non-destructive
heartbeat (the portability floor: a fresh session reads it and resumes), that the status view is honest
when the daemon never woke, and that ``render_install`` produces a launchd plist + ``launchctl`` gesture
FOR THE OPERATOR (a privileged install I prepare, never run). Brick-free over a temp shelf (D126)."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from mnemosyne.runtime.daemon import (
    LAUNCHD_LABEL,
    read_last_heartbeat,
    render_install,
    render_status,
    wake,
)


def _distilled_fiche(tmp_path: Path, rel: str = "finance/porter.md") -> None:
    path = tmp_path / "distilled" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


# ---- wake (one governed tick + a durable heartbeat) ----------------------------------
def test_wake_runs_a_tick_and_records_a_heartbeat(tmp_path: Path) -> None:
    _distilled_fiche(tmp_path)  # an un-surveyed fiche ⇒ the veille source surfaces one proposal
    heartbeat = tmp_path / "state" / "heartbeat.jsonl"
    ledger = tmp_path / "veille.jsonl"

    count = wake(
        knowledge_root=tmp_path,
        ledger_path=ledger,
        heartbeat_path=heartbeat,
        repo_root=tmp_path,  # scan the TEMP tree, never the real repo's OS litter (hermetic count)
        now=datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc),
    )
    assert count == 1  # the veille nudge for the one un-surveyed fiche
    last = read_last_heartbeat(heartbeat)
    assert last is not None
    assert last["proposals"] == 1 and last["at"].startswith("2026-07-15T12:00")


def test_wake_appends_non_destructively(tmp_path: Path) -> None:
    """Two wakes leave two heartbeat lines — append-only, history never rewritten (D44)."""
    heartbeat = tmp_path / "heartbeat.jsonl"
    wake(
        knowledge_root=tmp_path,
        ledger_path=tmp_path / "l.jsonl",
        heartbeat_path=heartbeat,
        repo_root=tmp_path,
    )
    wake(
        knowledge_root=tmp_path,
        ledger_path=tmp_path / "l.jsonl",
        heartbeat_path=heartbeat,
        repo_root=tmp_path,
    )
    assert len(heartbeat.read_text(encoding="utf-8").splitlines()) == 2


# ---- read / status (honest proof-of-life) --------------------------------------------
def test_read_last_heartbeat_is_none_when_never_woke(tmp_path: Path) -> None:
    assert read_last_heartbeat(tmp_path / "absent.jsonl") is None


def test_read_last_heartbeat_skips_a_garbled_tail(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat.jsonl"
    heartbeat.write_text('{"at": "a", "proposals": 2}\n{bad}\n\n', encoding="utf-8")
    last = read_last_heartbeat(heartbeat)
    assert last is not None and last["proposals"] == 2  # the last VALID record, garbage ignored


def test_render_status_is_honest_when_never_woke(tmp_path: Path) -> None:
    out = render_status(tmp_path / "absent.jsonl")
    assert "never woken up" in out and "make daemon" in out


def test_render_status_shows_the_last_wake(tmp_path: Path) -> None:
    """``now`` INJECTED, close to the heartbeat — without it this test would ACCIDENTALLY measure
    the "STOPPED BEATING" branch (the real `datetime.now()` is now well past 2026-07-15), and
    would still pass through a fortuitous substring overlap between the two messages. A witness
    that does not pin time tests nothing reliable in a function that compares dates."""
    heartbeat = tmp_path / "heartbeat.jsonl"
    heartbeat.write_text('{"at": "2026-07-15T12:00:00+00:00", "proposals": 3}\n', encoding="utf-8")
    out = render_status(heartbeat, now=datetime(2026, 7, 15, 12, 5, tzinfo=timezone.utc))
    assert "2026-07-15T12:00:00+00:00" in out and "3 proposals" in out
    assert "STOPPED BEATING" not in out


# ---- render_status: the daemon that STOPPED beating (final audit, 2026-08-17) ---------


def test_render_status_says_the_daemon_stopped_beating_past_the_threshold(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat.jsonl"
    heartbeat.write_text('{"at": "2026-07-28T12:28:00+00:00", "proposals": 2}\n', encoding="utf-8")
    out = render_status(heartbeat, now=datetime(2026, 8, 17, 12, 28, tzinfo=timezone.utc))
    assert "STOPPED BEATING" in out
    assert "20 day(s)" in out
    assert "2026-07-28T12:28:00+00:00" in out, "the old heartbeat stays named, never erased"
    assert "make daemon" in out


def test_render_status_stays_silent_just_UNDER_the_threshold(tmp_path: Path) -> None:
    """The threshold BITES, it does not print at random — just before 24h, the normal message
    still holds."""
    heartbeat = tmp_path / "heartbeat.jsonl"
    heartbeat.write_text('{"at": "2026-08-17T00:00:00+00:00", "proposals": 1}\n', encoding="utf-8")
    out = render_status(heartbeat, now=datetime(2026, 8, 17, 23, 59, tzinfo=timezone.utc))
    assert "STOPPED BEATING" not in out
    assert "Last wake" in out


def test_render_status_fires_AT_the_threshold_not_just_after(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat.jsonl"
    heartbeat.write_text('{"at": "2026-08-16T12:00:00+00:00", "proposals": 1}\n', encoding="utf-8")
    out = render_status(heartbeat, now=datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc))
    assert "STOPPED BEATING" in out


def test_render_status_degrades_without_crashing_on_an_unreadable_timestamp(
    tmp_path: Path,
) -> None:
    """Same fail-open discipline as `read_last_heartbeat`: an unreadable `at` never brings the
    surface down — it only loses the ability to state the age."""
    heartbeat = tmp_path / "heartbeat.jsonl"
    heartbeat.write_text('{"at": "not-a-date", "proposals": 1}\n', encoding="utf-8")
    out = render_status(heartbeat, now=datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc))
    assert "STOPPED BEATING" not in out
    assert "not-a-date" in out


def test_render_status_uses_REAL_now_by_default_not_a_frozen_clock(tmp_path: Path) -> None:
    """Without `now=`, the function must compare against the real clock — not a frozen default
    that would always make the daemon look alive (or always dead)."""
    heartbeat = tmp_path / "heartbeat.jsonl"
    heartbeat.write_text('{"at": "2026-07-15T12:00:00+00:00", "proposals": 3}\n', encoding="utf-8")
    assert "STOPPED BEATING" in render_status(heartbeat)  # 2026-07-15 is far behind TODAY


# ---- render_install (the launchd plist + launchctl gesture — the operator's act) ------
def test_render_install_renders_a_launchd_plist_for_the_repo(tmp_path: Path) -> None:
    out = render_install(repo_root=tmp_path, interval=1800)
    assert f"<string>{LAUNCHD_LABEL}</string>" in out  # the job Label
    assert "<string>wake</string>" in out  # ProgramArguments runs `daemon wake`
    assert "<key>StartInterval</key>" in out and "<integer>1800</integer>" in out
    assert "<key>RunAtLoad</key>" in out  # relaunches at boot
    assert str(tmp_path) in out  # WorkingDirectory + PYTHONPATH bound to THIS repo


def test_render_install_makes_uv_findable_by_the_gui_agent(tmp_path: Path) -> None:
    """A launchd GUI agent does not inherit the shell PATH: the job MUST still locate `uv` or never fires."""
    out = render_install(repo_root=tmp_path)
    assert "<key>PATH</key>" in out  # a PATH is pinned so uv's own subprocesses resolve too
    uv = shutil.which("uv")
    if uv:  # on a machine with uv, either it is invoked absolutely or its dir is on the pinned PATH
        assert f"<string>{uv}</string>" in out or str(Path(uv).parent) in out


def test_render_install_frames_it_as_the_operators_privileged_gesture(tmp_path: Path) -> None:
    out = render_install(repo_root=tmp_path)
    assert "YOUR MOVE" in out  # I prepare; installing a standing agent is the operator's act
    assert "launchctl bootstrap" in out and "bootout" in out  # install + uninstall gesture
