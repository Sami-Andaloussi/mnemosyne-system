#!/usr/bin/env bash
# Stop hook (workstream A — the AUTO-REMINDED essence, item 6). Generalises the PUSH hook: where
# user-prompt-submit.sh reminds ON the operator's signal, this reminds at the OTHER boundary — the
# moment the agent believes a task is DONE. If the finished turn AUTHORED A REPO FILE or COMMITTED, it
# injects the end-of-task ESSENCE ritual (capture / propose / delegate-local / tidy / optimise tokens —
# see CLAUDE.md's end-of-task guidance), so a fresh frontier model that FORGETS still gets reminded.
# Otherwise it stays SILENT (a pure Q&A / read-only turn needs no ritual = zero noise/cost).
#
# HONEST SCOPE (the trigger is a PROXY, not "any change"): a repo Edit/Write/MultiEdit/NotebookEdit, or a
# `git commit`. Deliberately NOT covered (fail-open — the doctrine lives in CLAUDE.md, run the ritual
# yourself): a data mutation done via Bash (`make ingest` / `make distill`, `mv` / `rm`), and work done
# ENTIRELY in a delegated sub-agent with no main-thread authoring afterward. A write OUTSIDE the repo
# (scratchpad / tmp) does NOT count — it is not work on the system.
#
# WHY `decision: block` and not stdout: on a Stop event, exit-0 stdout is NOT shown to the model (debug
# log only — unlike UserPromptSubmit/SessionStart). The ONLY way a Stop reminder reaches the model is
# the JSON `{"decision":"block","reason":...}` form, which feeds `reason` back and lets it act. We fire
# it AT MOST ONCE per task: `stop_hook_active` (set by Claude Code after the first block of a turn-chain)
# is checked FIRST and short-circuits to exit 0 — the structural anti-loop guard. The next user prompt
# re-arms it, so the reminder recurs across tasks without ever looping within one.
#
# PROPORTIONALITY. "Consequential work" = an Edit/Write/MultiEdit/NotebookEdit, or a `git commit`, on the
# MAIN thread since the last real user prompt (tool_result echoes and sidechain/subagent lines excluded).
# A crisp, low-false-positive proxy for "a turn whose product must not be lost/left untidy". Read-only.
#
# FAIL-OPEN toward SILENCE: any trouble (no python3, unparseable payload, missing/torn transcript) exits
# 0 with no output. A missed reminder is benign — CLAUDE.md carries the doctrine (like the PUSH hook, a
# false negative is cheap; here a false POSITIVE would cost a forced turn, so we bias to silence).
# NEVER exits non-zero. Code & comments in English (D117); the ritual text injected below is in English
# in this public mirror (the private original keeps it in French, for its operator).
set -u

payload=$(cat)

# Payload via env (not stdin): the heredoc IS python's stdin (the program). Keeps the injected reason
# text free of shell-quoting hell. python3 is reliably present on this uv/Python dev machine; absent ->
# exit 0.
PAYLOAD="$payload" python3 - <<'PY' || exit 0
import os, json, re, sys

try:
    data = json.loads(os.environ.get("PAYLOAD", ""))
except Exception:
    sys.exit(0)

# 1) Anti-loop guard FIRST: we already reminded once in this turn-chain -> let the stop proceed.
if data.get("stop_hook_active"):
    sys.exit(0)

# The repo root — used to ignore out-of-repo (scratchpad / tmp) writes. Coerced to str: a payload
# with a non-string cwd used to raise inside is_outside_repo, losing the WHOLE ritual on a stderr
# traceback (exit stayed 0, so it failed silently — the worst shape a hook can fail in).
cwd = data.get("cwd") or ""
if not isinstance(cwd, str):
    cwd = ""
transcript = data.get("transcript_path")
if not transcript:
    sys.exit(0)
try:
    with open(transcript, encoding="utf-8") as handle:
        raw_lines = handle.read().splitlines()
except Exception:
    sys.exit(0)

events = []
for line in raw_lines:
    line = line.strip()
    if not line:
        continue
    try:
        events.append(json.loads(line))
    except Exception:
        continue  # tolerate a torn/at-write final line, same discipline as the journals


def on_main_thread(event):
    """Ignore sidechain (delegated subagent) lines — the ritual is the MAIN agent's task boundary."""
    return not event.get("isSidechain")


def _fallback_is_real_user_prompt(event):
    """A genuine user turn — NOT a tool_result echo (those are also type==user).

    The FALLBACK only. The real definition is `review_signals.is_task_boundary`, imported below:
    this one accepts a <task-notification> (the host's report that a subagent finished — it rides in
    a type==user event carrying a text block), which in 433 of 1048 real tasks made the host talking
    to itself the task boundary, pushing the operator's actual prompt out of the reviewed window. Kept
    only so the ritual still fires when the import fails; the shared predicate wins whenever available."""
    if event.get("type") != "user" or not on_main_thread(event):
        return False
    content = (event.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(isinstance(c, dict) and c.get("type") != "tool_result" for c in content)
    return False


# ONE definition of "the operator spoke", shared with the detector (a copy drifts, and this one
# already had). Import failure is survivable: the fallback above keeps the ritual working, just with
# the looser boundary — never a dead hook.
try:
    sys.path.insert(0, os.path.join(cwd, "system", "lib"))
    from mnemosyne.production.review_signals import is_task_boundary

    def is_real_user_prompt(event):
        return on_main_thread(event) and is_task_boundary(event)
except Exception:
    is_real_user_prompt = _fallback_is_real_user_prompt


def is_outside_repo(path):
    """True ONLY when we can PROVE a file is outside the repo — an ABSOLUTE path not under cwd (a
    scratchpad / tmp write). A relative or unknown path counts as in-repo (bias to firing, not silence)."""
    return bool(cwd) and isinstance(path, str) and path.startswith("/") and not path.startswith(cwd)


# 2) Scope to THIS task: everything after the last real user prompt on the main thread.
last_prompt = -1
for i, event in enumerate(events):
    if is_real_user_prompt(event):
        last_prompt = i
if last_prompt < 0:
    sys.exit(0)

# 3) Did this turn author a REPO file (not a scratchpad / tmp write) or commit?
MUTATING_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
consequential = False
for event in events[last_prompt + 1 :]:
    if event.get("type") != "assistant" or not on_main_thread(event):
        continue
    for block in (event.get("message") or {}).get("content") or []:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name = block.get("name")
        if name in MUTATING_TOOLS:
            # a repo-file authoring counts; a write to the scratchpad / tmp (outside the repo) does not
            if not is_outside_repo((block.get("input") or {}).get("file_path", "")):
                consequential = True
                break
        elif name == "Bash":
            command = (block.get("input") or {}).get("command", "")
            if isinstance(command, str) and "git commit" in command:
                consequential = True
                break
    if consequential:
        break

if not consequential:
    sys.exit(0)

# 3-bis) LEARNING SIGNALS (D155). The ritual below is a generic reminder, and a generic reminder is
# exactly what gets skipped. This asks the repo's own detector whether THIS task contains a
# correction / an explicit order to remember / a stated preference, and — when it does — prepends
# the operator's actual words plus the "do NOT capture" rules. Detection lives in ONE home
# (mnemosyne.production.review_signals), never copied here: a copy drifts.
#
# Scope: from the LAST real user prompt (the turn that opened this task) to the end. A correction
# made two tasks ago is out of scope — accepted, because widening it would re-show the same block
# on every later task until it became furniture.
#
# FAIL-OPEN, always: the import needs nothing installed (pure stdlib), but any trouble at all —
# missing path, syntax error, unexpected transcript shape — must leave the ritual untouched rather
# than cost the turn. A missing signal block is benign; a broken Stop hook is not.
signal_block = ""
try:
    from mnemosyne.production.review_signals import detect, render_review

    signal_block = render_review(detect(events[last_prompt:]))
except Exception:
    signal_block = ""

# 3-ter) THE OTHER HALF (I4 clause b) — MY OWN TRACE, and E3's uncommitted work. Both read `git`,
# both are EDGE work: the judges (`review_signals.detect_trace`, `non_committe.attentes`) are pure
# and are handed their population, because a judge that fetches its own population can find it EMPTY
# and return a green — and here green means "nothing to commit" and "no lesson", the two sentences a
# missing `git` would produce for free.
#
# WHY THIS IS NOT invariant 1: nothing is shipped anywhere. No transcript moves, no model is called,
# no network is touched. It reads commits I authored, in a repo already on this disk.
#
# FAIL-OPEN, always, and bounded: every git call carries a timeout and every failure degrades to an
# empty block. A missing reminder is benign; a Stop hook that hangs is not.
GIT_TIMEOUT = 10
#: Aggregate bound on the trace half: `GIT_TIMEOUT` is PER CALL, so without this a window of 579
#: commits would carry a 96-minute theoretical ceiling. What exceeds it is NAMED, never dropped.
COMMITS_MAX = 25
PLAN_PATHSPECS = ["*PLAN.md", "*PLAN_COURANT.md", "*plan/*.md"]


def git(root, *args):
    """`git -C root …` — its stdout, or "" for ANY trouble (absent binary, timeout, non-zero rc)."""
    import subprocess

    try:
        done = subprocess.run(
            ["git", "-C", root, *args], capture_output=True, text=True, timeout=GIT_TIMEOUT
        )
    except Exception:
        return ""
    return done.stdout if done.returncode == 0 else ""


def enclosing_repo(path):
    """The nearest ancestor of `path` holding a `.git` — or None. Bounded walk, no filesystem crawl."""
    current = os.path.dirname(os.path.abspath(path))
    for _ in range(12):
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return None


# The repos are DERIVED, never counted: item E3 says "the three repos", and the measurement says
# SIX carry a `.git` under this root plus the memory one outside it. So the set is built from what
# this task actually touched — freeze the SET, never the COUNT.
roots = {}
if cwd and os.path.exists(os.path.join(cwd, ".git")):
    roots[os.path.realpath(cwd)] = "this repository"
# The memory repo lives OUTSIDE the project, and its path is derived from the transcript's own
# folder (`~/.claude/projects/<slug>/`) rather than re-encoding the slug rule a second time.
memory = os.path.join(os.path.dirname(os.path.abspath(transcript)), "memory")
if os.path.exists(os.path.join(memory, ".git")):
    roots.setdefault(os.path.realpath(memory), "memory (outside the repo)")

# THE THIRD REPO — the one that carries the PROJECT, and it was MUTE. E3's condition says "across
# the three repos"; the detector only saw two, because it only knew the working repo, memory, and
# whichever repos the task had WRITTEN to. `projects/` is none of the three when the task doesn't
# touch it — yet it carried six uncommitted files at the moment the orchestrator measured it. *That
# is where REAL work gets lost, not in the system.*
#
# BOUNDED, and declared as such: depth 2 under the root. This repo carries SIX nested `.git`
# (`projects/`, `projects/mnemosyne/ui`, `projects/saas/another project`…) and a `git status` per
# repo at EVERY end of task costs too much for a gate that must stay faster than the wall it guards.
# At depth 2 we catch `projects/` — the one the condition names — and any deeper repo stays queried
# as soon as the task WROTE to it (the loop further down), at any depth. A hidden folder or a
# `node_modules` is not descended into: they carry none of the operator's work.
for niveau1 in sorted(os.listdir(cwd) if cwd and os.path.isdir(cwd or "") else []):
    if niveau1.startswith(".") or niveau1 in ("node_modules", "venv"):
        continue
    chemin1 = os.path.join(cwd, niveau1)
    if not os.path.isdir(chemin1):
        continue
    if os.path.exists(os.path.join(chemin1, ".git")):
        roots.setdefault(os.path.realpath(chemin1), niveau1 + "/ (nested repo)")

trace_block = ""
commit_block = ""
# Every file this task authored, in ABSOLUTE form. Two consumers below: the set of repos to
# question, and the pathspec that keeps the trace half from reading OTHER chats' commits.
def chemins_d_un_git_add(commande):
    """The paths a `git add` names in a Bash command — the tokens after it, flags and globs aside.

    WITHOUT THIS, THE TRACE HALF IS MUTE ON 16 % OF REAL TASKS. `MUTATING_TOOLS` only sees
    Edit/Write; a task that writes with `cat >>` or a script and then commits authored nothing by
    that measure, so the window had no pathspec and the half fell silent. Measured by the isolated
    audit over 12 transcripts: **183 of 1,122 consequential tasks committed without a single
    Edit/Write**. A `git add` names exactly what the task claims to have produced — it is the most
    honest list available, and it costs no new tool.

    **IT READS TEXT, NOT A COMMAND — SO IT CAN BE WRONG, AND THREE RULES BOUND THE DAMAGE.**
    An isolated audit showed the first version reopening the very false attribution it exists to
    close: MULTI-LINE Bash, a heredoc quoting `git add`, or a commit message containing those words
    would pull in `ls`, `docs`, `tests`, `system`, `EOF` — and `docs`/`tests`/`system` are REAL
    directories, so the window widened to another chat's commits.
      1. `git add` only counts at the START OF A COMMAND (start of line, or after `&&`, `;`, `|`, `(`);
      2. reading stops at the end of the LINE;
      3. **the path must LOOK LIKE a path** — a file that exists, an extension, or a `/`. That is
         what eliminates `ls`, `docs`, `tests`, `system`, `EOF`, `then`, `push`.
         The first hardening required `isfile` ALONE, and an audit measured what that cost:
         **88 mute tasks out of 1,028 versus 46** — because `isfile` is evaluated AT STOP TIME, not
         at the moment of the action. It killed an entire, legitimate class: **a task that stages a
         DELETION** (`git add deleted-file.md`) — the file no longer exists, and that is precisely
         the work to report. Globs (`reports/*.md`) fell too, even though a glob is a perfectly
         valid pathspec for `git log`.
    """
    trouves = []
    for ligne in commande.splitlines():
        for morceau in re.split(r"&&|\|\||;|\||\(", ligne):
            # `git add`, `git -C <dir> add`, `git add --`: the real forms, not just one.
            depart = re.match(r"\s*git\s+(?:-C\s+\S+\s+)?add\b(?:\s+--)?", morceau)
            if not depart:
                continue
            for jeton in morceau[depart.end() :].split():
                if jeton.startswith(("-", ">", "<")) or jeton in (".", "*"):
                    break
                chemin = jeton.strip("'\"")
                absolu = chemin if os.path.isabs(chemin) else os.path.join(cwd or ".", chemin)
                # A file DELETED by the task is exactly what we want to report: the shape of the
                # path is enough, existence is only a shortcut for when it happens to be true.
                # A DIRECTORY IS REJECTED, and that is a trade-off between two wrongs. The shape
                # rule that lets globs back through let directories back through with them:
                # measured end to end, `git add docs/` reattributes to this task the confession AND
                # the item of ANOTHER chat. That is exactly the class scope exists to close.
                # Price paid, measured over 12 transcripts: **9 of 220 real `git add` calls (4.1 %)**
                # target a directory; those tasks will get no trace half. *Too narrow a scope stays
                # SILENT; too wide a scope ACCUSES someone else* — between the two wrongs, we take
                # the silence.
                if chemin.endswith("/") or os.path.isdir(absolu):
                    continue
                if os.path.isfile(absolu) or "/" in chemin or re.search(r"\.[A-Za-z0-9]{1,6}$", chemin):
                    trouves.append(chemin)
    return trouves


ecrits = []
for event in events[last_prompt + 1 :]:
    if event.get("type") != "assistant" or not on_main_thread(event):
        continue
    for block in (event.get("message") or {}).get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("name") == "Bash":
            commande = (block.get("input") or {}).get("command", "")
            if isinstance(commande, str) and "git add" in commande:
                ecrits += [
                    chemin if os.path.isabs(chemin) else os.path.join(cwd or ".", chemin)
                    for chemin in chemins_d_un_git_add(commande)
                ]
        if block.get("name") not in MUTATING_TOOLS:
            continue
        written = (block.get("input") or {}).get("file_path", "")
        if not isinstance(written, str) or not written:
            continue
        if not os.path.isabs(written):
            written = os.path.join(cwd or ".", written)
        ecrits.append(written)
        # A scratchpad / tmp write has NO enclosing repo, so it drops out on its own — no second
        # rule needed, and no list of places to forget one of.
        root = enclosing_repo(written)
        if root:
            roots.setdefault(os.path.realpath(root), os.path.basename(root))

# TWO SEPARATE `try`s, AND THAT IS A REPAIR, NOT A STYLE. They shared one, so ANY failure of the
# trace half — a half-written `review_signals.py` on a repo where three chats commit in parallel,
# a non-string timestamp — wiped the ALREADY COMPUTED commit block. Measured by the isolated audit:
# appending `def ((` to the module made the E3 reminder vanish with rc 0 and an empty stderr. One
# broken half must cost its own half, never the other's.
def charger_par_chemin(nom, relatif):
    """Load ONE module from its FILE, without importing the package around it.

    THE PACKAGE `__init__` IS EAGER: `mnemosyne/production/__init__.py` imports ~30 sibling
    modules, so a SyntaxError in ANY of them takes down `from mnemosyne.production.x import y` for
    every x — including modules that share nothing with the broken one. The isolated audit measured
    exactly that: a half-written `review_signals.py` (three chats commit in parallel; it happens)
    made the E3 reminder vanish, and splitting the `try` was NOT enough because the failure is at
    IMPORT of the package, not at import of the module.
    `non_committe` is pure stdlib with no relative import, so it can be loaded alone — and the file
    half then survives anything happening elsewhere in the layer. The trace half cannot: it reaches
    a sibling through a relative import, and that needs the package. Declared rather than pretended.
    """
    import importlib.util

    chemin = os.path.join(cwd or "", "system", "lib", "mnemosyne", "production", relatif)
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    # REGISTERED BEFORE EXECUTION, and it is not a formality: `@dataclass` resolves its own class
    # through `sys.modules[cls.__module__]`, so a module absent from that table raises
    # `AttributeError: 'NoneType' object has no attribute '__dict__'` the moment it defines one.
    # Found by the witness that fires the hook for real — never by reading this function.
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


try:
    non_committe = charger_par_chemin("mnemo_non_committe", "non_committe.py")
    attentes, lire, rendre = non_committe.attentes, non_committe.lire, non_committe.rendre

    # `ecrits` reaches all the way to the judge: OBS-6 — separate what THIS task wrote from what
    # was already lying around. Paths are rendered relative to their repo, the shape `git status
    # --porcelain` produces.
    relatifs = []
    for chemin in ecrits:
        for racine in roots:
            reel = os.path.realpath(chemin)
            if reel.startswith(racine + os.sep):
                relatifs.append(os.path.relpath(reel, racine))
    commit_block = rendre(
        attentes(
            (lire(label, git(root, "status", "--porcelain")) for root, label in roots.items()),
            relatifs,
        )
    )
except Exception:
    commit_block = ""

try:
    from mnemosyne.production.review_signals import (
        Commit,
        detect_trace,
        items_ajoutes,
        render_trace,
    )

    # The window: from the timestamp of the user prompt that opened this task. `--since` parses the
    # ISO stamp in git, not here. A missing or non-string stamp -> no trace half (fail-open): the
    # `cwd` payload field was already hardened this way, and the audit found this field one step
    # behind — `"--since=" + since` on an int raises, and used to take the E3 block down with it.
    since = (events[last_prompt] or {}).get("timestamp")
    since = since if isinstance(since, str) else ""

    # SCOPED TO THE FILES THIS TASK WROTE, and this is the second repair. `--since` is WALL-CLOCK:
    # on a repo where three chats commit in parallel it returned 11 commits of which ONE was this
    # task's, and the block then said "this task" about someone else's work — the exact friction
    # already recorded for the file half. A pathspec of what this task actually authored is derived,
    # not guessed. When nothing was authored inside this repo, there is nothing to attribute and the
    # half stays silent rather than widening back to everyone.
    #
    # AND HERE IS WHAT THIS PATHSPEC CANNOT DO — A WRITTEN BOUND, NOT A FALSE BARRIER.
    # Flagged by chat 3 on 2026-08-16, verified by me before writing it down:
    #     git log -30 --format=%an  ->  30 out of 30, A SINGLE identity.
    # The four actors on this repo commit under the SAME git name. This block filters nowhere by
    # author (`grep -n "author\|%an\|%ae"` on this file: no filter) — it separates by PATH, and
    # that is what saves it in the general case.
    # BUT ON A SHARED PATH — a memory index, a plan file two chats both edit — the pathspec no
    # longer separates anything, and that is exactly where identity would have been the
    # discriminant. It is shared. *So there is NO way to tell the two actors apart on a shared
    # path: the commit carries no session identity, and git knows nothing of it.*
    # The block's title ("YOUR OWN TRACE") therefore promises, on this subset, more than the
    # mechanism can hold. NOT FIXED, and that is not an oversight: fixing it would need a
    # per-actor identity inside the commit, which is not mine to decide alone.
    # The original report's conclusion ("structurally impossible") was TOO BROAD: it assumed an
    # author filter that does not exist. *A true premise can carry a conclusion that is too broad —
    # and adopting it would have weakened a mechanism that works.*
    dans_le_depot = [
        os.path.relpath(chemin, cwd)
        for chemin in ecrits
        if cwd and os.path.realpath(chemin).startswith(os.path.realpath(cwd) + os.sep)
    ]
    commits, trop = [], 0
    if since and cwd and dans_le_depot:
        listing = git(
            cwd, "log", "--reverse", "--pretty=format:%H\x1f%s", "--since=" + since,
            "--", *sorted(set(dans_le_depot)),
        )
        lignes = [l for l in listing.splitlines() if "\x1f" in l]
        # An AGGREGATE budget, because `GIT_TIMEOUT` is per call: one `git show` per commit at ~7 ms
        # measured, but a pathological window (a stamp git reads as very old) would multiply a
        # 10 s ceiling by the number of commits. What is dropped is NAMED rather than truncated in
        # silence — a silent cut reads as "I looked at everything".
        # The MOST RECENT ones, never the oldest: `--reverse` then a cut at the head used to throw
        # away the END of the task — exactly the commits carrying the confession and the added item.
        # Measured by the audit: 30 commits in the window, the confession in the last one, block EMPTY.
        trop = max(0, len(lignes) - COMMITS_MAX)
        for ligne in lignes[-COMMITS_MAX:]:
            sha, subject = ligne.split("\x1f", 1)
            diff = git(cwd, "show", sha, "--unified=0", "--format=", "--", *PLAN_PATHSPECS)
            added, removed = [], []
            for l in diff.splitlines():
                if l.startswith("+") and not l.startswith("+++"):
                    added.append(l[1:])
                elif l.startswith("-") and not l.startswith("---"):
                    removed.append(l[1:])
            commits.append(
                # BOTH sides of the diff: closing an item rewrites its line, so reading only `+`
 # made every ` -> ` look like a birth (measured: 22 false alarms out of 30).
                Commit(sha=sha, subject=subject, plan_items_added=items_ajoutes(added, removed))
            )
    # Truncation happens at RENDER time, never in the population: a sentinel slipped in among the
    # commits carries neither an item nor a confession, so it never crosses the judge and is never
    # printed.
    trace_block = render_trace(detect_trace(commits), trop)
except Exception:
    trace_block = ""

# 3-quinquies) THE THIRD SOURCE — WHAT I DELEGATED (item I5). Neither the operator's words nor my
# commits can carry it: an audit that comes back with six defects is a lesson ALREADY PAID FOR, and
# until it is written down it exists only in a conversation. Measured the day this was built: an
# audit of ~209 000 tokens left NO trace in Mnemosyne (absent from `spend.jsonl`) and no run journal
# exists — but the host had been filing one durable transcript per sub-agent all along, **1 137 of
# them across 18 sessions**, and nothing read them. Nothing to build; something to read.
#
# WHY THIS IS NOT invariant 1, same argument as the trace half: nothing is shipped anywhere. These
# transcripts are read on this machine, by stdlib, with no model and no network. Invariant 1 forbids
# handing a transcript to a SECOND model by automatism — never reading one's own.
#
# Same discipline as its neighbours: the JUDGE is pure and is HANDED its population. The globbing
# happens HERE, so an unreadable directory cannot hand `rendre` an empty tuple that would print as
# "nothing was delegated, therefore no lesson" — the green a missing directory produces for free.
#
# `rendre` is ALREADY BOUND in this script (non_committe's, above), so this import is aliased.
# MEASURED, and the honest version is weaker than it looks: removing the alias leaves the suite
# at 35/35 green, because `commit_block` is built a hundred lines ABOVE and rebinding the name
# afterwards can no longer cost it anything. The alias is a PRECAUTION against a future reordering,
# not a live guard — and the witness that claimed to arm it was deleted rather than kept green.
delegation_block = ""
try:
    from pathlib import Path

    from mnemosyne.production.delegations import (
        delegations_of,
        within,
    )
    from mnemosyne.production.delegations import rendre as rendre_delegations

    # The session's own directory is the transcript path minus its extension — verified on this
    # machine before being written here, not inferred from the shape of the name.
    delegation_block = rendre_delegations(
        within(
            delegations_of(Path(os.path.splitext(transcript)[0])),
            # The boundary filters on when a delegation ENDED, never when it started: a slow audit
            # launched before the operator's last prompt and landing after it belongs to THIS task,
            # and the slow ones are exactly the ones carrying a real finding.
            since=str((events[last_prompt] or {}).get("timestamp") or ""),
        )
    )
except Exception:
    delegation_block = ""

# 4) Consequential + first stop of the chain -> remind, ONCE. `reason` reaches the model and lets it act.
#
# GESTURE 1 IS REPLACED, NOT DOUBLED, WHEN THE TRACE SPOKE (item I4, clause b). *"Has a durable
# learning emerged?"* is a question one answers "no" to without looking — the module says it
# itself: all the value is in DETECTING the signal in code and then NAMING it. When `detect_trace`
# has named what happened (N items added, N commits avowing an error), repeating the generic line
# under it would restore the very question the specific one exists to retire. The four other
# gestures are untouched: they are not about capture.
capter = (
    "1. CAPTURE — the SPECIFIC question is above (it replaces this generic reminder): "
    "answer it before you conclude. → make remember if something durable comes out of it.\n"
    # The delegation block counts here for the same reason the trace does: it asks *"what did it
    # come back with that you did not know?"*, which cannot be answered "no" without looking.
    if trace_block or delegation_block
    else "1. CAPTURE — has a durable learning (fact, preference, correction) "
    "emerged? → make remember (it waits for the operator's validation; nothing is lost).\n"
)
reason = (
    "[Mnemosyne · essence ritual] This task wrote to the repo (or committed); "
    "before you conclude, run back through the essence (CLAUDE.md, end-of-task guidance):\n"
    + capter
    + (
    "2. PROPOSE — has a recurring/automatable pattern appeared? Propose it (never "
    "self-promoted, D92/D100).\n"
    "3. DELEGATE — should repeated, cheap volume move to local execution (frontier "
    "reserved for the fine-grained parts), as precise, granular tasks?\n"
    "4. TIDY — does the repo stay navigable? → make rangement (non-destructive).\n"
    "5. TOKENS/CONTEXT — have you preserved context (delegated the "
    "volume, avoided noise)?\n"
    "If everything is already done or not applicable, say so in ONE line and stop — do not "
    "restart this ritual."
    )
)
# The specific blocks go FIRST, the generic ritual last, and the order among them is the order of
# what they cost to ignore: the operator's own words, then what a THIRD PARTY found for me, then
# what my trace says I did, then the work no commit holds. Reversing any of it would bury the parts
# that name what actually happened in this task.
#
# The delegated report sits second on purpose: it is the only one of the four that carries a finding
# someone ELSE already paid to produce. My trace says something happened; a returned audit says what
# it was, and losing it costs the whole delegation.
for block in (commit_block, trace_block, delegation_block, signal_block):
    if block:
        reason = block + "\n\n" + reason
print(json.dumps({"decision": "block", "reason": reason}))
sys.exit(0)
PY

exit 0
