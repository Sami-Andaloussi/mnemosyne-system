"""The tick daemon (Q3) — a thin, always-on LOCAL heartbeat that keeps the proactive nerve firing.

The SessionStart hook fires ``tick`` when the operator opens a session; this daemon fires the SAME seam
BETWEEN sessions, so the proactive nerve stays warm and a durable heartbeat proves the system is alive
even when no chat is open. It is deliberately the LEAN, ROBUST form the operator asked for: not a
long-lived process that could hang or drift, but a tiny ``wake`` that launchd RE-LAUNCHES on an interval
(``StartInterval``) and at every boot (``RunAtLoad``) — it wakes, runs one ``run_tick``, records a
heartbeat, and exits. launchd owns the cadence and the restart; the daemon owns nothing fragile.

The proposals a wake computes are DERIVED, recomputable state (D44 / inv. 24): they are not buffered,
they are re-surfaced fresh at the next session's ``tick`` (a stored proposal could go stale — the
current state is the truth). So the daemon's job is precisely to keep the nerve firing and leave
proof-of-life, NOT to accumulate proposals for a human who is not there to read them.

**Portability is the cardinal property (the operator).** The daemon holds NO private state: everything
durable lives in the repo (``.md`` / git), the memory, and the append-only ledgers. Its only footprint is
an append-only heartbeat under ``system/state`` (gitignored, reconstructible). So if the operator's
Claude Code account changes, a fresh session reads the repo + the heartbeat and resumes EXACTLY where
things were — the daemon simply keeps ``tick`` alive in the meantime. It keeps the nerve warm and leaves
proof-of-life; it never auto-runs the ingestion pipeline (that heavy, resource-coupled work is Q1's
governed scheduler, not a background executor) — so it can never crash the operator's machine or touch
their data unbidden.

**Installing a launchd agent is a privileged, standing-configuration act — it is the operator's gesture.**
This module RENDERS the exact plist + ``launchctl`` commands (:func:`render_install`); it never loads
them itself (mirrors how ``domain_new`` renders the ``[OPERATOR]`` policy gesture but never writes
policy). Brick-free (D126); ``wake`` reuses the governed ``run_tick`` seam. Code & docstrings English
(D117); operator-facing labels are French in the private repo (D33), translated to English here."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

from ..production.veille_ledger import DEFAULT_LEDGER_PATH
from .tick import DEFAULT_KNOWLEDGE_ROOT, run_tick

#: Repo root from this module (``system/lib/mnemosyne/runtime/daemon.py`` → parents[4] = repo).
_REPO_ROOT = Path(__file__).resolve().parents[4]
#: The append-only heartbeat — proof-of-life a fresh session can read. Gitignored (``system/state/*.jsonl``).
DEFAULT_HEARTBEAT_PATH = _REPO_ROOT / "system" / "state" / "daemon_heartbeat.jsonl"
#: The launchd job label (reverse-DNS, the id ``launchctl`` addresses).
LAUNCHD_LABEL = "com.mnemosyne.tick"
#: Default wake cadence — a gentle 30 min; tune it in the plist. Bounded, never a busy loop.
DEFAULT_INTERVAL_SECONDS = 1800


def wake(
    *,
    knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    heartbeat_path: Path = DEFAULT_HEARTBEAT_PATH,
    repo_root: Path = _REPO_ROOT,
    now: datetime | None = None,
) -> int:
    """One wake: run ONE ``tick`` and append a heartbeat line; return the proposal count surfaced.

    The launchd entrypoint. Reuses the governed ``run_tick`` (bounded, meta-only, inert deposits) — the
    daemon adds only the durable heartbeat (``{"at": <iso>, "proposals": <n>}``), append-only and
    non-destructive (D44), so a later session can see the nerve has been alive. ``now`` and the paths are
    injectable so the suite drives a full wake against a temp shelf + temp heartbeat (brick-free, D126).
    ``repo_root`` is threaded through to ``run_tick`` on purpose: the cruft proposer SCANS it, so a wake
    that dropped it would count the real repo's OS litter (a stray ``.DS_Store``) inside a temp-tree test."""
    proposals = run_tick(
        knowledge_root=knowledge_root, ledger_path=ledger_path, repo_root=repo_root
    )
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    with heartbeat_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": stamp, "proposals": len(proposals)}) + "\n")
    return len(proposals)


def read_last_heartbeat(heartbeat_path: Path = DEFAULT_HEARTBEAT_PATH) -> dict[str, object] | None:
    """The most recent heartbeat record — or ``None`` if the daemon never woke (fail-open read).

    A missing heartbeat, or a file whose tail is blank / garbled, yields the last VALID record (or
    ``None``): the status view degrades to 'never woke', it never crashes over one bad byte."""
    if not heartbeat_path.is_file():
        return None
    last: dict[str, object] | None = None
    for line in heartbeat_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            continue  # a garbled line never sinks the read — fail-open
        if isinstance(record, dict):
            last = record
    return last


#: **PAST THIS THRESHOLD, THE SURFACE STOPS SAYING "last wake" — measured on 2026-08-17 (final
#: audit): `render_status` was still displaying `Last wake: 2026-07-28…` TWENTY DAYS later, never
#: once comparing that date to today — a heartbeat from twenty days ago read EXACTLY like a
#: heartbeat from two minutes ago. And this is THE channel supposed to surface reports and
#: proposals to the operator once the session is archived: dead, it reads as alive, and nothing
#: else triggers it (no git remote, 0 workflow, pre-commit does not run pytest). Pattern ADOPTED,
#: not invented (D163): `make plancher` states its age (*"N day(s) ago"*), `make carte` REFUSES
#: rather than reassure on a stale source. 24h — comfortably above the wake cadence (30 min,
#: `DEFAULT_INTERVAL_SECONDS`) to absorb a machine turned off for a night, short enough that a
#: real stoppage (days, weeks) never reads as a live state.
SILENCE_THRESHOLD_HOURS: Final = 24.0


def render_status(
    heartbeat_path: Path = DEFAULT_HEARTBEAT_PATH,
    *,
    now: datetime | None = None,
    silence_threshold_hours: float = SILENCE_THRESHOLD_HOURS,
) -> str:
    """Render the daemon's proof-of-life for a returning session — honest when it never woke (D25),
    and honest when it has STOPPED waking (past ``silence_threshold_hours``, the heading changes
    from "Last wake" to "STOPPED BEATING" — an instrument that lies about its own death is worse
    than a dead instrument). ``now`` injectable (D126); an unreadable ``at`` degrades to the
    message WITHOUT an age, never an exception (the same fail-open discipline as
    :func:`read_last_heartbeat`). Pure."""
    last = read_last_heartbeat(heartbeat_path)
    if last is None:
        return (
            "# Mnémosyne · daemon\n\n"
            "_The daemon has never woken up (no heartbeat). "
            "To turn it on: `make daemon` (the install gesture is yours)._\n"
        )
    at = last.get("at", "?")
    count = last.get("proposals", "?")
    noun = "proposal" if count == 1 else "proposals"
    age = _age_since(at, now)
    if age is not None and age >= timedelta(hours=silence_threshold_hours):
        jours = age.days
        heures = age.seconds // 3600
        depuis = f"{jours} day(s)" if jours else f"{heures} hour(s)"
        return (
            "# Mnémosyne · daemon\n\n"
            f"\U000026D4 **THE DAEMON HAS STOPPED BEATING** for {depuis} — last wake: **{at}**, "
            f"{count} {noun} surfaced then. Restarting is the operator's gesture: `make daemon`.\n"
        )
    return (
        "# Mnémosyne · daemon\n\n"
        f"Last wake: **{at}** — {count} {noun} surfaced at the last tick.\n"
    )


def _age_since(at: object, now: datetime | None) -> timedelta | None:
    """``now - at`` — ``None`` if ``at`` is not a readable ISO date (fail-open, never an
    exception that would take down the whole surface for one spoiled byte of the heartbeat)."""
    if not isinstance(at, str):
        return None
    try:
        stamp = datetime.fromisoformat(at)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) - stamp


def render_install(
    *,
    repo_root: Path = _REPO_ROOT,
    interval: int = DEFAULT_INTERVAL_SECONDS,
    label: str = LAUNCHD_LABEL,
) -> str:
    """Render the launchd plist + the exact ``launchctl`` gesture — for the OPERATOR to install
    (never me). Pure.

    Installing a standing background agent is a privileged, persistent-configuration act (like
    editing policy): I PREPARE it, the operator runs it. The plist re-launches ``daemon wake``
    every ``interval`` seconds and at boot (``RunAtLoad``), in the repo, with the local
    ``PYTHONPATH`` — no long-lived process, so nothing to leak or hang. Its stdout/stderr land in
    ``system/state/daemon.log`` (gitignored).

    Rendered ON the operator's machine, so it resolves ``uv``'s ABSOLUTE path now (via
    ``shutil.which``) and pins a ``PATH``: a launchd GUI agent does NOT inherit the interactive
    shell's PATH, so a bare ``uv`` would resolve against launchd's minimal default (no Homebrew)
    and every wake would exit 127 — the job would silently never beat. The absolute program + a
    PATH covering ``uv``'s dir close that trap."""
    repo = str(repo_root)
    log = str(repo_root / "system" / "state" / "daemon.log")
    uv = shutil.which("uv")
    uv_program = (
        uv or "uv"
    )  # resolved absolute path on the operator's machine; bare fallback if not on PATH now
    uv_dir = str(Path(uv).parent) if uv else "/opt/homebrew/bin"
    path_env = f"{uv_dir}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    program = (uv_program, "run", "--no-sync", "python", "-m", "mnemosyne.runtime.daemon", "wake")
    program_lines = "\n".join(f"        <string>{arg}</string>" for arg in program)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{program_lines}
    </array>
    <key>WorkingDirectory</key>
    <string>{repo}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{path_env}</string>
        <key>PYTHONPATH</key>
        <string>{repo}/system/lib</string>
    </dict>
    <key>StartInterval</key>
    <integer>{interval}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
</dict>
</plist>
"""
    plist_target = f"~/Library/LaunchAgents/{label}.plist"
    return (
        "# Mnémosyne · daemon — install launchd (YOUR MOVE)\n\n"
        "The daemon wakes Mnemosyne every "
        f"{interval // 60} min on THIS machine (never the cloud), and relaunches itself on "
        "reboot. Installing a launchd agent = permanent system configuration = **your move**; "
        "I prepare everything, you paste these two steps into a terminal.\n\n"
        f"## 1) Save the plist to `{plist_target}`\n\n"
        "```xml\n"
        f"{plist}"
        "```\n\n"
        "## 2) Load it (once)\n\n"
        "```sh\n"
        f"launchctl bootstrap gui/$(id -u) {plist_target}\n"
        f"launchctl enable gui/$(id -u)/{label}\n"
        f"launchctl kickstart -k gui/$(id -u)/{label}\n"
        "```\n\n"
        "## To uninstall it later\n\n"
        "```sh\n"
        f"launchctl bootout gui/$(id -u)/{label}\n"
        "```\n\n"
        "Current state: `make daemon-status`.\n"
    )


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI over the real shelf
    """``daemon wake|status|install`` — the launchd entrypoint (wake) + the human-facing views."""
    parser = argparse.ArgumentParser(description="Mnémosyne tick daemon (Q3)")
    parser.add_argument(
        "action", choices=("wake", "status", "install"), nargs="?", default="status"
    )
    action = parser.parse_args(argv).action
    if action == "wake":
        wake()  # the launchd cadence — one governed tick + a heartbeat, then exit
        return 0
    print(render_install() if action == "install" else render_status(), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
