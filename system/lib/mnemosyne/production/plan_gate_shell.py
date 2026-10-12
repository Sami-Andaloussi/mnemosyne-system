"""J1 -- ``make plan-gate-emit``: the plan gate (D166 clause 4 + D176) becomes installable
elsewhere.

 **THE PATTERN IS PROVEN, AND THIS IS IT**: :func:`~mnemosyne.production.garde_shell.contrat_emis`
emits a five-line POINTER to `runtime.garde_shell_run` -- never a copy of the judge. This
module does the SAME thing for the plan judge: the emitted text calls
``runtime.plan_gate_run`` via ``PYTHONPATH``; it copies neither :func:`~mnemosyne.production.
plan_format.index_problems` nor any of its 40 lines of docstring about the two meanings of
completeness. *One single hearth, emitted, never copied* (D163).

 **THIS IS NOT `.githooks/pre-commit`, AND THAT IS A DELIBERATE, WRITTEN CHOICE.** THIS
repository's hook judges the STAGED GIT INDEX (350 lines of staged/disk ordering cases, specific
to Mnemosyne). The judge emitted here is narrower and simpler: it reads DISK state, the way
`make plans` (`plan_registry.scan_plans`) already does for this repository itself -- **two disk
surfaces already accepted side by side**, never a third invented form. A host that wants the rigor
of the staged git index can always write its own; what this module guarantees is *"the gate bites,
with the same rule as Mnemosyne, on what the disk carries."*

 **D176 (2026-08-17) — THE TEXT PROMISED "IT JUDGES NOTHING ELSE," AND THAT HAD BECOME
FALSE.** `runtime.plan_gate_run.juger()` now also calls `required_field_problems` (the judge for
the field requirement that a gate declares FOR ITSELF via `**Format**:`) -- this module emits a
pointer to that same judge, so the text below must say what the pointer points TO, not what it
pointed to a day ago. **Always conditional, never imposed (D176)**: a gate that declares nothing
stays at zero required fields, exactly the behavior before that day.
"""

from __future__ import annotations


def contrat_emis(racine_mnemosyne: str) -> str:
    """The contract to install on an OTHER host -- the address, never a copy (D163).

    ``racine_mnemosyne`` is INJECTED by the boundary: this module does not know where it is
    installed, and a guessed path would be exactly the defect the gate fights -- the same
    principle as :func:`~mnemosyne.production.garde_shell.contrat_emis`."""
    return f"""\
# THE MNEMOSYNE PLAN GATE — to install on your side (D166 clause 4).
#
# \U000026D4\U000026D4 WHAT IT DOES NOT DO YET: until it is installed on your side (the three moves below:
# written, wired to your pre-commit, proven), the guarantee is not there. Reading this text
# is not the same as having installed it -- this is exactly the original defect this gate exists
# to close (field report of 2026-08-04): a guarantee that is written down but does not run where
# it is written is worse than an outage, it is falsely reassuring.
#
# \U000026A0\U0000FE0F\U000026A0\U0000FE0F INSTALLING THIS FILE CAN BREAK YOUR OWN GATES -- A REAL MEASUREMENT, NOT A HYPOTHESIS.
# On a MATURE host (another real project), installing it made TWO of that host's native gates fail: an
# anti-exfiltration freeze on the sites allowed to launch a subprocess (this file IS such a site,
# absent from that freeze's allowlist before you add it) and a folder-documentation check (a
# top-level folder with no map). The `*-emit` pattern assumes a NEUTRAL host; a host that already
# has its own gates can collide with yours. This is NOT hypothetical: after move 1, check that
# YOUR existing gates still hold, not just that this one bites (see move 3).
#
# What it does, ONCE installed -- TWO rules, never conflated:
#   (1) it REFUSES a commit whose plan (gate `PLAN.md` + `plan/` folder) is not
#       STRUCTURALLY READABLE -- EXACTLY what `is_readable()` already judges for Mnemosyne
#       itself, its TWO halves: an arc that nothing in the gate cites, a cited file that no
#       longer exists, an unreadable status or identity, a code block that is never closed, ...
#       (12 kinds, `READER_REFUSALS`) -- AND an empty title, an empty cap, or no item at all
#       (`unreadable_reasons`, the OTHER half of the same conjunction, missed in this text's
#       first pass and fixed since).
#   (2) IF your gate declares `**Format**: <fields>` (D176 -- a CHOICE, never imposed: declaring
#       nothing leaves this rule at zero, exactly as before), it also REFUSES an item that does
#       not fill in one of the fields YOU yourself chose to make required. `NONE` is a valid,
#       free answer for a field that does not apply.
# \U000026D4\U000026D4 WHAT IT DOES NOT JUDGE (2026-08-17, named after measurement -- "adopting buys this, not
# that," and CORRECTED a second time after an isolated 2nd audit found that "neither more nor
# less" was still too strong a claim):
#   - `*Prérequis*` and `*Produit* : <a folder>` -- two LEVEL-2 clauses that Mnemosyne does
#     NOT wire into its own hook either (their scope, there too, stays with the CALLER). Wiring
#     them in here would be STRICTER than what Mnemosyne imposes on itself -- the same disguised
#     ceiling this module already refuses to impose on `**Format**`.
#   - dependency ORDER (`plan_ordre.ordonner`, 4 kinds), LINEAGE
#     (`plan_archive.filiation_problems`, 1 kind), and `ARC_ILLISIBLE` (`plan_registry`, 1 kind) --
#     THREE ENTIRELY DIFFERENT code hearths that `.githooks/pre-commit` ALSO judges, never
#     mentioned here before this line. This gate is NOT a complete mirror of Mnemosyne's hook: it
#     equals `is_readable()` (structural readability) plus D176, nothing more -- this text no
#     longer claims otherwise.
# An item's free-form content, outside these rules, remains yours.
#
# \U000026D4 THIS FILE IS A POINTER, NOT A COPY. The judge lives in ONE single place:
#   {racine_mnemosyne}/system/lib/mnemosyne/production/plan_format.py  (READER_REFUSALS, is_readable)
# Do not copy it to your side: a copy drifts, and you would lose the fixes.
#
# \U000026D4\U000026D4 TWO DIFFERENT QUESTIONS, DECIDED DIFFERENTLY (2026-08-17, reserves R3/R4 of the final
# audit) -- DO NOT CONFLATE THEM:
#   - FOLDER WITH NO PLAN, GATE NOT FOUND, UNREADABLE PLAN -> the command PASSES. Nothing to
#     judge: a project that has not adopted the format has nothing to be refused for. UNCHANGED.
#   - THE JUDGE ITSELF CANNOT RUN (python3 missing, Mnemosyne module not found, PYTHONPATH
#     broken, ...) -> the command REFUSES (rc=2), with a message that NAMES the breakage and
#     the escape hatch (`git commit --no-verify`). CHANGED, AND THAT IS DELIBERATE, NOT AN
#     OVERSIGHT: this module used to follow the SAME pattern as
#     :func:`~mnemosyne.production.garde_shell.contrat_emis` (fail-open everywhere except an
#     explicit refusal).
# \U00002696\U0000FE0F WHY GARDE_SHELL STAYS FAIL-OPEN AND THIS GATE NO LONGER IS ON THIS POINT: garde_shell
# installs inside an INTERACTIVE Claude Code session -- the agent that triggered the call sees
# stderr on EVERY turn, a silent breakage has an immediate reader there. This gate installs into
# `pre-commit`, fired ~40 times a day by human committers AND scripts -- nobody re-reads stderr at
# that pace (a real measurement). The SAME fail-open has a different cost depending on who is
# watching behind it. And another project, the reference adopter, has already settled this exact case in its
# own code (`validation/plan/index_des_arcs.py`): *"Mnemosyne absent REFUSES, it does not skip --
# the temptation is `try: import ... except ImportError: return 0`, that IS the fault."* This gate
# now aligns itself with that position for an invocation failure -- a guarantee that evaporates
# without a word is worse than no guarantee at all, which is this text's opening line, taken at
# its word.
# \U000026D4\U000026D4 WHAT THIS CHOICE COSTS YOU, MEASURED FOR REAL, NOT A HYPOTHESIS: your `python3` must be
# able to import `mnemosyne` (Python >= 3.11 for `tomllib` in the stdlib -- measured: the
# `/usr/bin/python3` shipped by Xcode Command Line Tools is still on 3.9 on a Mac that never
# updated it). If that is NOT your case, PROVE IT (move 3): the 1st firing will return `rc=1`
# (broken invocation) instead of `rc=2`.
# \U000026D4\U000026D4 AND THE CONSEQUENCE IS WHAT MATTERS, FROM THIS DOCTRINE CHOICE: if you install it WITHOUT
# noticing, EVERY commit will be refused from now on, until you fix `python3` (or uninstall this
# gate). Move 1's error message will tell you so ("broken invocation"), with
# `git commit --no-verify` as an immediate escape hatch -- but it is better to know this BEFORE
# installing than after your first refused commit.

# ── MOVE 1: write this file to <your-repo>/.githooks/plan-gate, then chmod +x ─────────────────
#!/usr/bin/env bash
sortie=$(env PYTHONPATH="{racine_mnemosyne}/system/lib" \\
  python3 -m mnemosyne.runtime.plan_gate_run "$(git rev-parse --show-toplevel)" "$1" 2>&1)
rc=$?
# plan_gate_run.main() only ever returns 0 (nothing to refuse) or 2 (a real refusal) -- any OTHER
# code (python missing, module not found on a bare python3 with no tomllib, broken PYTHONPATH,
# ...) is an INVOCATION FAILURE, never a verdict from the judge. rc=2 blocks for a REAL refusal;
# any OTHER rc now ALSO blocks, for a DIFFERENT reason, named in plain text (doctrine above, R3/R4).
if [ "$rc" -eq 2 ]; then
  printf '%s\\n' "$sortie" >&2
  exit 2
fi
if [ "$rc" -ne 0 ]; then
  printf 'plan-gate: broken invocation (rc=%s) -- the guarantee for this repository is no longer in place.\\n%s\\nFix PYTHONPATH/python3/the Mnemosyne module, or "git commit --no-verify" just this once.\\n' "$rc" "$sortie" >&2
  exit 2
fi
exit 0

# ── MOVE 2: call it from YOUR pre-commit, with the plan folder to judge ─────────────────
# \U000026D4\U000026D4 FOUND BY AN AUTONOMY PROBE (D75, 2026-08-17), NOT BY AN AUDIT: this move ASSUMED a host
# that ALREADY has a pre-commit. Measured on a real fresh repository (another project): `.githooks`
# ABSENT, `.git/hooks/` EMPTY of anything but `.sample` files, `core.hooksPath` NOT SET. The
# `*-emit` pattern assumes a NEUTRAL host; it turns out it also assumed a host ALREADY TOOLED UP.
#
# \U000026D4\U000026D4 FIRST OF ALL (2026-08-17, an ADOPTION probe this time, on a real project belonging to the
# user): IS YOUR PROJECT ITS OWN REPOSITORY? THE MEASUREMENT, from your project's folder:
#   git rev-parse --show-toplevel
# If that does NOT return your project's folder (it returns a parent SHARED with other projects),
# the TWO branches below place your gate at the ROOT of that parent -- where your NEIGHBORS also
# live, and they have adopted NOTHING. A commit touching ONLY a neighbor would still trigger YOUR
# judge, and could be REFUSED by a defect in YOUR plan that has nothing to do with what that
# neighbor is committing.
# *A project installs its gate and imposes it on its neighbors, without knowing it.*
# \U000026D4 THREE WAYS OUT, AND IT IS NOT THIS TEXT'S PLACE TO CHOOSE FOR YOU (`git init` is a move on
# YOUR data):
#   (a) `git init` inside your project -- it becomes its own repository, the two branches below
#       then apply unchanged. COST: it splits your project's history off from the shared
#       repository's, from now on -- a decision about YOUR structure, not ours.
#   (b) SCOPE the gate to your subfolder, WITHOUT touching the shared repository -- install the
#       SAME line as the branches below, but guarded: the judge fires ONLY if the commit actually
#       touches your project.
#         if git diff --cached --name-only --diff-filter=ACMR | grep -q '^<your-project>/'; then
#           .githooks/plan-gate "<folder-of-YOUR-gate>" || exit 1
#         fi
#     (replace `<your-project>` with YOUR folder's path from the shared repository's root, and
#     `<folder-of-YOUR-gate>` with where YOUR PLAN.md gate lives FROM THAT SAME ROOT -- not
#     necessarily "<your-project>/docs": exactly the same ADAPTABLE "docs" as the two branches
#     below, never a fixed assumption about your structure.) \U000026D4 THE `if ... ; then ... fi` FORM
#     MATTERS, NOT `A && B`: under `set -e`, a `grep -q`
#     with NO MATCH (the normal case, your project is not touched) would make the WHOLE hook exit
#     with an error via `&&` -- measured for real, a bare `&&` blocked EVERY commit that did not
#     touch your project, the exact opposite of the goal. `if` is exempt from `set -e`, whatever
#     the condition's exit code.
#     \U000026A0\U0000FE0F If ANOTHER project in the same shared repository has already adopted this pattern, ADD
#     your `if` block next to theirs in the same file -- never overwrite it (same rule as "YOU
#     ALREADY HAVE ONE" below).
#   (c) DO NOT install here -- a written admission is worth more than a gate that spills onto
#       neighbors who asked for nothing.
#
# YOU ALREADY HAVE a pre-commit running (`.git/hooks/pre-commit` executable, OR `core.hooksPath`
# already points to a folder YOU CONTROL and that EXISTS) -- add this line inside it:
#   .githooks/plan-gate "docs" || exit 1
# (adapt "docs" to the folder where YOUR PLAN.md gate lives)
#
# YOU HAVE NOTHING -- check first (`test -e .git/hooks/pre-commit && echo "WARNING: already
# exists, do not overwrite"`), then create GIT'S DEFAULT PATH, which requires NO configuration:
#   printf '#!/usr/bin/env bash\\nset -e\\n.githooks/plan-gate "docs" || exit 1\\n' > .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
# (adapt "docs" to the folder where YOUR PLAN.md gate lives -- and DO NOT TOUCH `core.hooksPath`:
# it stays unset, exactly as before this move, and that is what makes this path safe.)
#
# \U000026D4\U000026D4 ONLY SET `core.hooksPath` IF YOU ALREADY KNOW WHY -- THIS CORPUS ALREADY CARRIES THIS
# FAILURE, PAID FOR FOR REAL. `git config core.hooksPath <folder>` pointing to an ABSENT or
# poorly populated folder SILENTLY DISABLES ALL your hooks -- no error, no warning: every commit
# effectively becomes a `--no-verify`, including YOUR EXISTING GATES, not just this one.
# `.git/hooks/pre-commit` (the move above) never runs this risk: it is the path git reads with NO
# configuration at all, so there is nothing that can point wrong.

# ── MOVE 3: PROVE IT, do not just believe it. Two firings, two directions ─────────────────────
# TODO(public-mirror): needs human review -- the example PLAN.md/plan/orphelin.md content below
# (between the printf quotes) is left in French. It exercises this repository's own plan format
# (see docs/FORMAT_PLAN.md), and some of its tokens (e.g. `**Cap**`, `## Les items`, `**Format**`,
# `produit`) may be literal keywords the parser matches on rather than free text; mistranslating
# them would make this "prove it yourself" example silently stop demonstrating what it claims to.
# Only a reader who has also confirmed docs/FORMAT_PLAN.md's own English/French status should
# translate these fixture strings.
# It must BITE (expected: rc=2) — create an arc the gate does not cite:
#   mkdir -p /tmp/plan-epreuve/plan && cd /tmp/plan-epreuve
#   printf '# PLAN — Epreuve\\n\\n**Cap** : test\\n\\n## Les items\\n\\n- **A1** \U00002B1C un.\\n' > PLAN.md
#   printf '# orphelin\\n' > plan/orphelin.md
#   env PYTHONPATH="{racine_mnemosyne}/system/lib" python3 -m mnemosyne.runtime.plan_gate_run . . ; echo "rc=$?"
# It must LET an honest commit THROUGH (expected: rc=0) — cite the arc in the gate:
#   printf '# PLAN — Epreuve\\n\\n**Cap** : test\\n\\n## Les items\\n\\n- **A1** \U00002B1C un.\\n\\nvoir `plan/orphelin.md`.\\n' > PLAN.md
#   env PYTHONPATH="{racine_mnemosyne}/system/lib" python3 -m mnemosyne.runtime.plan_gate_run . . ; echo "rc=$?"
# \U000026D4 Either firing alone is not enough: a gate that refuses EVERYTHING passes the first one.
#
# IF YOU DECLARE `**Format** :` (D176, optional) — a third firing, it must BITE too:
#   rm -f plan/orphelin.md
#   printf '# PLAN — Epreuve\\n\\n**Cap** : test\\n\\n> **Format** : produit\\n\\n## Les items\\n\\n- **A1** \U00002B1C un.\\n' > PLAN.md
#   env PYTHONPATH="{racine_mnemosyne}/system/lib" python3 -m mnemosyne.runtime.plan_gate_run . . ; echo "rc=$?"
# Expected: rc=2, ONE SINGLE refusal, naming `champ_requis_manquant`. If you declare nothing, this
# firing does not apply -- the absence of Format is never a refusal (D176, never imposed).
# \U000026D4 THE `rm` MATTERS: without it, `plan/orphelin.md` (created on the first firing) becomes an arc
# this new gate does not cite again, and rc=2 would come from `arc_hors_index` -- this firing would
# bite for the WRONG reason, even if D176 were completely broken. Check the KIND named in the
# refusal, not just the rc.
# \U000026A0\U0000FE0F AND CHECK THAT YOUR OWN GATES STILL HOLD AFTER THESE TWO FIRINGS -- not just that this one
# bites. Replay YOUR existing test suite / pre-commit; a security freeze or a tidiness check on
# your side may not know about this new file (see the warning at the top of this text).
"""
