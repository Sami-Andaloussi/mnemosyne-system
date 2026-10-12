#!/usr/bin/env bash
# SessionStart hook (workstream A -- plug-and-play). Injects Mnemosyne's LIVING STATE at the start of
# every session (startup / resume / clear / compact) so any agent -- frontier or local -- is plugged
# into the system without being asked: it turns `make describe` from PULL into PUSH, and re-anchors
# the agent after a /compact. Read-only. FAIL-OPEN by construction: no `set -e`, always exits 0 --
# a hook must NEVER block a session. Code & comments in English (D117); this public mirror's displayed
# text is English throughout.
set -u

# ${CLAUDE_PROJECT_DIR} is exported by Claude Code; fall back to the repo root relative to this file.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_DIR" 2>/dev/null || exit 0

echo "=== Mnemosyne -- living state (injected at startup, workstream A) ==="
echo "You are in the Mnemosyne repository. CLAUDE.md (auto-loaded) carries your hard rules and doctrine."
echo "Reminders: French with the operator (non-technical -- explain the implications); producer != verifier;"
echo "never commit the 5 parked files; deleting the operator's data is their own gesture."
echo "At the end of a task that changes the system: the essence ritual (capture / propose / delegate-locally /"
echo "tidy / optimize tokens) -- see CLAUDE.md; the Stop hook reminds you there."
# THESE 3 LINES LIVE IN THE BLOCK THAT IS ALWAYS PRINTED, AND THAT IS THEIR ENTIRE POINT (2026-08-16).
# Measured with an adversarial agent: this hook renders 61,449 bytes and 8 mentions of the project
# standard in the nominal case, but 1,849 bytes and **ZERO** when `uv` is unavailable -- and all 8
# mentions lived in the output of `make describe`, which is exactly what drops out. *A fail-open channel
# only carries a doctrine as long as it does not degrade.* The Guard itself lives in CLAUDE.md.
# ITS OWN HEADING, AND A THIRD PARTY ASKED FOR IT (chat 1, verdict from 2026-08-16 19:5x --
# "would increase salience without changing the content"). Without it, these 3 lines read as the
# continuation of the generic reminders paragraph, while EVERY other block in this hook carries a
# `--- title ---`. *True text filed under the wrong heading reads as something else.* This is the
# same class of defect as the `make plans` bug (a tree with no total): the information was there, the
# visual hierarchy was lying.
echo
echo "--- ARE YOU BUILDING A PROJECT? (Mnemosyne's project engineering, OFFERED, never imposed -- D176) ---"
echo "Once adopted, it no longer bends. Two addresses, never copied:"
echo "  docs/FORMAT_PLAN.md .............. a plan's shape, read in 30 s"
echo "  make plan-nouveau CHEMIN=... ..... gives BIRTH to a plan that is already conformant"
echo "From a PROJECT folder, none of these targets exist (make has no root outside of here)."
echo "  make -C ~/mnemosyne <target> ... works from ANYWHERE, zero new files (J4)"
echo "  and the line only the operator can set in their own shell: mnemo() { make -C ~/mnemosyne \"\$@\"; }"
echo

# 1) Self-model: identity + surfaces + tools + active skills. Brick-free, read-only (make describe / capability ⑥).
echo "--- make describe (your self-model: what Mnemosyne can do) ---"
if ! PYTHONPATH=system/lib uv run --no-sync python -m mnemosyne.runtime.describe 2>/dev/null; then
  echo "(make describe unavailable in this context -- run it yourself: make describe)"
fi
echo

# 1b) Wake-up (autonomy trigger, make tick): ONE coordinated engine drain (soul ⑤) surfaces any UNBIDDEN
# proposals -- the system coming to the operator of its own accord each session. Brick-free, meta-only,
# read-only, propose-never-impose. Fail-open like the rest: a tick that cannot run must NEVER block a
# session.
# THIS BANNER NO LONGER DESCRIBES WHAT IT WRAPS (isolated audit D75, 2026-09-08).
# It announced the whole block as "unsolicited proposals, propose-never-impose". But the tick now
# publishes TWO things of opposite nature: proposals from the system, and DEBTS that a THIRD PARTY
# flagged (12 open signalements, the oldest 27 days). A frame that declares "propose, never impose"
# makes everything it contains optional -- exactly the defect fixed INSIDE the tick the same day,
# which survived ONE LEVEL UP in this very file. *Fixing a block does not fix the frame wrapping it.*
# The tick now carries its own headings, one per nature; this line only opens the section.
echo "--- make tick (the system comes to you) ---"
if ! PYTHONPATH=system/lib uv run --no-sync python -m mnemosyne.runtime.tick 2>/dev/null; then
  echo "(make tick unavailable in this context -- run it yourself: make tick)"
fi
echo

# 1c) The MAP (B3): "where things stand" at a CONSTANT size -- a plan with 10,000 steps renders the
# same number of lines as one with 168, and each section SAYS how much it is hiding. This is the
# item's level-1 *Obligation*, written in black and white: "pushed by SessionStart".
# IT WAS MISSING, and an isolated audit measured it: `grep -rn carte .claude/hooks/` returned
# NOTHING. The manual target existed and worked; the PUSHED half did not exist. *A written obligation
# that no caller pulls is a wish, not a level 1.*
# Fail-open like its neighbors -- and that is PRECISELY why `make carte` must stay pullable
# by hand: a hook that breaks STAYS SILENT, so a capability that only lives in this channel does not
# exist on the days it goes down. Measured cost: 0.15 s on this repo's plan.
echo "--- make carte (where things stand, at a constant size: what remains, what is blocked, what is NOT MOVING) ---"
if ! PYTHONPATH=system/lib uv run --no-sync python -m mnemosyne.runtime.carte_run 2>/dev/null; then
  echo "(make carte unavailable in this context -- pull it yourself: make carte)"
fi
echo

# 1c) THE MEMORY (D173). `MEMORY.md` is loaded by Claude Code's BUILT-IN, which reads exactly ONE
# file and stops loading past ~24,400 bytes; the index sits at 24,344 -- 56 bytes of margin, and no
# prose left to wring (~107 bytes per entry). The only exit that destroys nothing is a SECOND channel,
# and a second file alone would be invisible: MEASURED -- the 227 entries (1.67 MB) are on disk and
# absent from context. So it needs a carrier that PUSHES, and that is this hook.
# This hook is FAIL-OPEN by construction, so the ratchet's rc is DISCARDED here: it only PRINTS.
# The gate that bites is `make memoire` run by hand or by a script. Said plainly so nobody reads
# this line as a guarantee it cannot give -- *a control that prints is not a door*.
echo "--- make memoire (index overflow + bijection ratchet) ---"
if ! PYTHONPATH=system/lib uv run --no-sync python -m mnemosyne.runtime.memoire_run 2>/dev/null; then
  echo "(memory ratchet RED or unavailable -- pull it yourself: make memoire)"
fi
echo

# 1d) THE END-OF-SESSION SUMMARY (B5) -- drift is caught HERE, at the exact moment you are about to
# trust the file. The operator, 2026-07-30: "it must not drift, not even after compaction." A stale
# handoff document is WORSE than absent: it reads as current.
# Same admission as for the ratchet above: this hook is FAIL-OPEN, the rc is discarded, it only
# PRINTS. The gate that actually bites is `make bilan VERIFIER=1` run by hand.
# And the check only sees the NUMBERS: stale prose still passes green. There is no barrier for
# that, only the gesture -- pull the summary again JUST BEFORE compacting.
echo "--- make bilan VERIFIER=1 (has the end-of-session summary drifted?) ---"
if ! VERIFIER=1 PYTHONPATH=system/lib uv run --no-sync python -m mnemosyne.runtime.bilan_run 2>/dev/null; then
  echo "(summary DRIFTED or unavailable -- treat it with suspicion, then: make bilan)"
fi
echo

# 2) Git: current branch + short status. Surfaces the 5 parked files as a standing reminder.
echo "--- git (reminder: never commit the 5 parked files, selective commits only) ---"
echo "branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
git status --short 2>/dev/null | head -n 20
echo

# 3) Orientation in this mirror: there is no live "current state" file here (that lives in the private
# working repo this mirror is generated from). Use README.md and CLAUDE.md to get oriented instead.
echo "--- orientation ---"
echo "This public mirror carries no live state file. Read README.md and CLAUDE.md before acting."
echo

# 4) THE CURRENT PROJECT. Everything above is MNEMOSYNE -- the system. None of it is the PROJECT being
# built, and that gap was MEASURED on 2026-08-04: right after a compaction this hook fired correctly,
# and the agent still had to read 108,000 lines of a project bubble BY HAND because nothing told it
# where to look. The operator had to ask for it. *An agent reads what it is ORDERED to read.*
# Pushes the DERIVED state (computed fresh, so it cannot be stale) + the ADDRESS of the handoff --
# never its prose, which would be paid at EVERY session and would rot between the two (D163).
# Placed LAST on purpose: it is the most actionable thing an agent reads before its first gesture.
echo "--- the BUBBLE you are working in (the system above is not the project) ---"
if ! PYTHONPATH=system/lib uv run --no-sync python -m mnemosyne.runtime.reprise 2>/dev/null; then
  echo "(project handoff unavailable in this context -- run it yourself: make reprise)"
fi

exit 0
