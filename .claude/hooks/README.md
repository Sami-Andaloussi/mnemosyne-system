# Claude Code hooks - Mnemosyne's PUSH incarnation (track A)

These hooks make Mnemosyne **self-triggering**: simply opening a Claude Code session in this repo
activates them (wired in [`../settings.json`](../settings.json), **versioned** - so the repo *carries*
its own automation, on any machine). They are **read-only** and **fail-open**: never blocking, they
cannot break a session (no `set -e`, always `exit 0`).

This is the **PULL -> PUSH** shift: instead of the agent having to invoke Mnemosyne's capabilities,
Mnemosyne presents itself to the agent - even in a plain frontier chat.

## `session-start.sh` - `SessionStart` event

On every startup (`startup` / `resume` / `clear` / `compact`), injects into the agent's context:

1. a **hard-rules reminder** (talk to the operator in French, producer != verifier, the 5 parked paths
   that must never be committed, deletion is the operator's own gesture);
2. **`make describe`** - the self-model (identity + surfaces + tools + active skills): PUSH, not PULL;
3. a short **git status** (a reminder of the 5 parked paths, commit selectively);
4. a **pointer toward the current state** (in this public template, README.md / ARCHITECTURE.md).

Re-injected after a `/compact` -> the agent **re-anchors** to Mnemosyne instead of starting over blind.

## `user-prompt-submit.sh` - `UserPromptSubmit` event

Watches every prompt from the operator. If it **signals an addition to the system** ("put this in
Mnemosyne", "keep this", "tidy this up", "ingest this", "remember this", "add to the corpus"...), it
injects a short **reminder**: do it right away, classify + ingest under the Guard, delegate the volume
if needed. Otherwise, **silent** (zero noise). **Always `exit 0`** - never `exit 2`, which would erase
the prompt.

## `stop.sh` - `Stop` event

The **end-of-task reminder** - generalising the PUSH reflex to the OTHER boundary: the moment the agent
believes it is **done**. If the finishing turn **wrote a repo file** (`Edit` / `Write` / `MultiEdit` /
`NotebookEdit`) **or committed** (`git commit`), on the main thread since the operator's last real
message, it injects the **end-of-task ritual** (capture / propose / delegate-to-local / tidy / mind the
token budget - see the repository's own end-of-task guidance). Otherwise (a plain Q&A, a read-only
turn), **silent** - zero noise, zero cost.

**Since D155, it does more than remind: it DETECTS.** Before adding the ritual, the hook asks
`mnemosyne.production.review_signals` whether this task contains a **learning signal** - a correction
from the operator, an explicit instruction to remember something, a stated work preference - and, if
so, it injects **the operator's own words, quoted**, plus the "DO NOT CAPTURE" list (looted from
`hermes-agent`: a negative claim about a tool *"hardens into a refusal the agent holds against itself
for months after the problem has been fixed"*). A generic reminder gets skipped; a quote, much less so.

**THIS HOOK NOW READS FOUR SOURCES, NOT ONE - and this paragraph described only one of them for three
weeks.** Added on 2026-08-14/15 (items `I4`(b), `I5`, `E3`), each silent by default:

| block | what it reads | its judge |
|---|---|---|
| the operator's words | this task's turns | `production/review_signals.detect` |
| **my own trace** | my commits - an admitted mistake in a title, an item added to the plan | `review_signals.detect_trace` |
| **what I delegated** | sub-agent transcripts, the mandate, and the last word | `production/delegations` |
| uncommitted work | `git status`, every repo | `production/non_committe` |

*The yield of all this - how many signals actually turn into a fiche - is NOT here: pull it with
`make rendement`. A global table printed at the end of every task would turn into furniture.*

Three properties worth knowing before touching this file:

- **Silence stays the default.** No signal => no review block (only the ritual passes). This is the
  opposite of Hermes's own bias ("a pass that captures nothing is a missed opportunity"): here, every
  capture spends the operator's attention. **The rate once written here - "12.7% of turns" - dated
  from 2026-07-21 and no longer holds** (widening the net to cover calm disagreement pushed it past
  double that). *A rate copied into a document ages away from the measurement that produced it*: the
  one that counts is pulled from `review_signals.py`'s own docstring, which publishes **its own
  measurement** alongside it.
- **The task boundary is SHARED with the detector** (`is_task_boundary`), and that sharing is a fix,
  not a detail: the hook used to accept any `type: user` event, so a `<task-notification>` from the
  host could open a task - in **433 tasks out of 1,048**, the window examined started *after* the
  operator's real message.
- **Fail-open all the way down.** The import lives in a `try`: a missing module, a torn transcript, an
  unexpected payload -> the review block is lost, never the ritual, and **never** a non-zero exit code.

The trigger is an **honest proxy, not "any change"** (`[[honest-docstrings-not-flattering]]`).
**Deliberately not covered** (fail-open - the doctrine lives in `CLAUDE.md`, run the ritual yourself): a
data mutation **via Bash** (`make ingest` / `make distill`, `mv` / `rm`), and work done **entirely
inside a delegated sub-agent** with no main-thread write afterward (the lead's own follow-up - a commit
or an edit - usually catches it anyway). A write **outside the repo** (scratchpad / tmp) doesn't count -
that is not work on the system.

One `Stop`-specific quirk (unlike `UserPromptSubmit`): on a `Stop` event, an `exit 0`'s stdout **never
reaches the model** (debug log only). The only channel that does is the JSON
`{"decision":"block","reason":...}` form - it hands control back to the model along with the ritual. It
fires **at most once per task**: `stop_hook_active` (set by Claude Code after the first block of a
chain) is checked **first** and short-circuits to `exit 0` -> **a structural anti-loop guard**. The
operator's next message re-arms the reminder: it **recurs** across tasks without ever looping inside
one. **Fails open toward SILENCE**: any trouble (no `python3`, an unreadable payload/transcript) ->
`exit 0` quietly (a missed reminder is benign - `CLAUDE.md` carries the doctrine; a false POSITIVE, on
the other hand, would cost a forced turn, hence the bias toward silence). Read-only, never a non-zero
`exit`.

## Settings

- **`SessionStart` matchers**: the group has **no matcher**, so it reliably targets **every** source
  (`startup` / `resume` / `clear` / `compact`) (per the official docs). Only add explicit matchers to
  *restrict* the hook to specific sources instead.
- **Intent markers** (`UserPromptSubmit`): widen or narrow by editing the `grep -iqE` pattern in
  `user-prompt-submit.sh`. A false positive is one extra reminder (harmless); a false negative is no
  reminder (`CLAUDE.md` already carries the doctrine).
- **Dependencies**: bash + `git` + `grep` only; `uv` is required only for `make describe` (the script
  falls back to a message if `uv` is unavailable). No dependency on `jq`.

## Verify / enable

The wiring lives in `settings.json` (versioned). Hooks load **at session start**: they take effect on
the **next** session opened in this repo (not the current one). Test a script in isolation:

```sh
echo '{"source":"startup","cwd":"'"$PWD"'"}' | .claude/hooks/session-start.sh
echo '{"prompt":"put this in Mnemosyne"}'     | .claude/hooks/user-prompt-submit.sh
```
