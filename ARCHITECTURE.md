# Architecture

This document explains the design decisions behind Mnemosyne - not a file-by-file tour (the code is
commented for that), but the handful of ideas that recur everywhere and why they exist.

## Design philosophy

Four rules show up in almost every module:

1. **Fail-closed on anything irreversible, fail-open on anything advisory.** A hook that reminds you
   to tidy up must never block a session - if it breaks, it should print nothing and get out of the
   way. A gate that stops an unapproved policy change from taking effect must never let one slip
   through, even if that means refusing when it isn't sure. Knowing which kind of check you're
   writing decides which failure mode is safe.
2. **Propose, never impose.** Nothing gets promoted, deleted, or auto-applied without a human step.
   Automated passes (a periodic library scan, a learning captured mid-conversation, a skill an agent
   thinks might be useful) land as *inert drafts* in a queue - visible, dated, and inert until someone
   reviews them.
3. **Measure, don't assume.** Recall thresholds, cost ceilings, and "is this fast enough" claims are
   backed by a number obtained by actually running the thing, not a plausible-sounding guess. Several
   of the harder bugs this codebase has fixed were caught by a test that ran a real mutation against
   the code and confirmed it actually got caught - not just that the code looked right.
4. **A copy drifts; an address doesn't.** Whenever the same contract needs to reach two places (a
   prompt template used by both a human and an agent, a data schema read by both the backend and the
   UI), the code emits it from one source rather than letting two hand-maintained copies slowly
   diverge. Several `*-emit` targets in the Makefile exist for exactly this reason.

## The Guard

[`system/lib/mnemosyne/guard/`](system/lib/mnemosyne/guard/) is a reference monitor: a single place
every externally-visible action passes through, deny-by-default.

- **Sensitivity routing.** Data is tagged with one of three levels. The tag names are French, and
  two of them are false friends worth stating plainly: `public` means public; `perso` is short for
  *personnel*, i.e. personal-but-not-secret; and `sensible` means **sensitive** - it does *not* mean
  "sensible/reasonable" as the identical English word does. Only `public` data may
  take an automatic path to a third-party cloud call; anything else stays local or waits for an
  explicit human gesture. This is a data-classification axis, not a statement about which *model*
  you're allowed to use - a frontier model is a perfectly fine choice for public data; the guard rails
  are about what data reaches it, not about avoiding frontier models on principle.
- **Egress allow-listing.** A network call leaving the machine is refused unless its destination host
  is on an explicit list in `system/config/policy.toml`. The list ships empty. Adding a host is a
  logged act, not a runtime decision an agent can make for itself.
- **Cross-bubble contracts.** Bubble A cannot read bubble B's data unless a `{from, to}` contract is
  declared for that exact pair. No wildcard, no transitive trust.

**What a refusal actually looks like.** The Guard rules on a request without performing it, and a
denial names its own reason rather than failing silently. With the shipped (empty) allow-list:

```python
from mnemosyne.guard import DeterministicGuard
from mnemosyne.ports.guard import GuardRequest, Effect, Bubble, GovernanceLabel
from mnemosyne.ports.core import Sensitivity

ruling = DeterministicGuard().authorize(GuardRequest(
    effect=Effect.EXTERNAL_OUTPUT,
    subject=Bubble("perso"),
    inputs=(GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble("perso")),),
    target="https://api.example.com/v1/chat",
    descriptor="send a personal note to a third-party API",
))
# Decision.DENY
# egress to 'https://api.example.com/v1/chat' not in allow-list (invariant 21, SE5)
```

Two things to read in that output. The denial is the *default*, not a reaction to something
suspicious about this particular host - no host is allowed until one is explicitly added. And the
reason cites the numbered rule it enforces: the invariants are a fixed, numbered list (see the
registry that ships with the repo), so a refusal can always be traced to the rule that caused it
rather than to a judgement call made at runtime.
- **A policy change requires a live human.** `make policy-approuver` - the only way a requested policy
  widening actually takes effect - must run in a real terminal and prints the full request before
  asking for a typed "yes" on `/dev/tty`. An agent cannot script around this: there is no non-interactive
  path to approval, by design. `make policy-examiner` supports this by generating a closable adversarial
  review mandate for an *isolated* second agent to run against the request first - the same
  producer/verifier split that governs code review applies to policy changes too.

## Cloisonnement: least privilege by domain

*Cloisonnement* is French for compartmentalisation - the watertight-bulkhead sense. It is kept as a
term of art here because it names one specific thing: a partition that holds by default, rather than
one an agent may cross whenever it happens to have filesystem access.

Beyond the Guard's yes/no gate, data is partitioned into **bubbles**. A bubble is a named working
context - typically a personal knowledge base, or one specific project - each with its own declared
domain list in `policy.toml`.

**A bubble and a sensitivity tag are two separate axes, and confusing them is the easiest mistake to
make here.** A bubble says *whose working context this is*; the `public` / `perso` / `sensible` tag
says *how sensitive a given document is*. A bubble can hold documents of several sensitivities, and
the same sensitivity appears across many bubbles. The two are checked independently: reaching a
document requires both that your bubble declares its domain and that its sensitivity permits the
route you are taking. (`make project-new` happens to take a `BUBBLE=public` argument - that names a
bubble, and is unrelated to the `public` sensitivity tag.) A
bubble sees only the domains it has explicitly declared; a document tagged with a domain nobody
declared is invisible to retrieval by default, not merely "unlikely to surface." Extending a bubble's
visibility is a config change, reviewable in a diff, never an implicit consequence of an agent's tool
choice.

## Memory

Two independent memory surfaces exist, and neither of them is a single ever-growing chat log:

- **Living memory** (`make remember` / `make memory-queue` / `make memory-validate`) captures a
  concise, durable learning - a fact, a preference, a corrected assumption - as an *inert* candidate.
  It doesn't reach anything an agent reads until you validate it. This keeps a small local model from
  ever silently confusing "an agent guessed this" with "the operator confirmed this."
- **Session recall** (`make rappel`) is full-text search over your own past conversation transcripts -
  no model, no network, no cost, refreshed incrementally. It answers "what did I already decide about
  X" without re-reading an entire history by hand.

Both are designed around the same failure mode: a memory system that silently drops what doesn't fit
is worse than one that visibly refuses to fit and says so. Where a memory index has a hard size
ceiling (many tools that auto-load a memory file impose one), the ratchet in `make memoire` verifies
the overflow channel is a true bijection with the primary index and refuses in *both* directions -
growth and silent shrinkage both fail the check.

## The knowledge pipeline

A four-stage pipeline turns a raw document into a citable, verified source:

```
knowledge/raw/<domain>/book.md    (ingested source, one file per document)
        |  make distill / distill-batch
        down
knowledge/distilled/<domain>/book.md   (a structured note: summary, key claims, verbatim quotes)
        |  make judge / verbatim-check
        down
a verdict: ok / flagged / cut - did every claim trace back to real text in the source?
        |  make finish
        down
polished, chapter-titled, ready to index
        |  make ingest
        down
Qdrant (dense vectors) + BM25 (lexical) + a reranker, queryable via `make search`
```

The **judge** is the piece worth understanding: it isn't a vibe check. It walks every claim in a
distilled note and verifies the underlying text exists, verbatim, in the source document. A note that
paraphrases confidently but can't be traced back is flagged or cut - this is what stops a distillation
pass's own hallucination from quietly becoming "the library says." `make raptor-build` adds a second
retrieval tier on top: hierarchical summaries (book-level, domain-level) so a query can be answered
from a synopsis when the fine-grained passage isn't what's needed.

## Skills, and proving they help

A **skill** (`system/skills/<name>/`) is a bounded, reusable capability with its own `SKILL.md`
contract, a thin adapter, and - critically - a required trial before anyone should trust it:

```
make skill-eprouver   -> two arm mandates + a secret salt, one arm gets the skill, one doesn't
make skill-juger      -> a blind judge scores both real outputs, labelled A/B under that salt
make skill-verdict    -> records differentiates / does-not-differentiate / harms, with blinding stated
```

(A number of target names are French verbs, and they are spelled that way in the Makefile you will
actually type: *eprouver* = to put to the test, *juger* = to judge, *approuver* = to approve,
*examiner* = to review, *archiver* = to archive, *nouveau* = new, *rangement* = tidying up. The code
and its documentation are English; a handful of command names are not.)

The salt exists because a judge who can guess which output came from "the skill" will unconsciously
favor it. A verdict that doesn't explicitly state whether blinding held reads exactly like a clean
one - which is why the schema has no default for that field. The host machinery exists because a skill
that reads convincingly and a skill that measurably helps are not the same claim, and only one of
them is worth keeping.

## Project engineering: plans, gates, and parallel agents

This is the newest part of the system and the one that changes how work actually gets done. A
long-running body of work is tracked as a `PLAN.md` **door** - a short current-state header plus an
index - with the actual content split into dated **arcs** under `plan/`. An arc holds items; an item
states what it produces, when it is finished, what it depends on, and what to read first.

An item is one markdown bullet: an identity, a status, then the text - `- **A3** <status> Sectors,
value chains, products`. The status is not a label the reader skips; it is the value the parser
reads, and there are six of them: *to do*, *in progress*, *done*, *ready* (built and tested, waiting
on a human gesture), *paused* (resumption expected), and *vetoed*. That last one is the reason the
set is worth listing: a rejected path stays in the plan carrying a status that says it was rejected,
instead of being deleted - so the plan records what was decided AGAINST, not only what was done, and
nobody re-proposes it six weeks later. The literal syntax, including the character each status is
written with, is `docs/FORMAT_PLAN.md`, which reads in about thirty seconds.

The format is offered to a project, not imposed on it. But a project that adopts it does not get to
drift back out, because three properties turn the convention into a mechanism:

- **The reader is the same code that gates commits.** A plan whose index doesn't name an arc exactly
  once, or whose heading claims "done" over items that aren't, is refused - not silently accepted and
  displayed wrong later. `make plan-gate-emit` installs that gate. This distinction is the whole
  point: a format that is only *described* in a contributing guide is a wish. The failure mode this
  ends is specific and dull - plan files that declare they follow the format while nothing checks
  that they do, so the declaration and the reality drift apart unnoticed for weeks.
- **Adopting the format costs nothing.** `make plan-nouveau CHEMIN=<path>` scaffolds a plan that
  already passes the gate, so the cheapest way to write a conforming plan is to let the tool write
  it. A standard nobody can accidentally violate beats a standard everybody is asked to remember.
- **Archiving verifies its own reconstruction before writing anything.** Moving a finished arc into
  `archive/` is only allowed once the tool confirms that `archive + remaining plan` reassembles the
  original file byte-for-byte. If it can't verify that, it refuses instead of guessing.

**Running one plan across several agents.** Once a plan is large, the interesting question is not
"can an agent do this" but "how do several agents work on it at once without destroying each other's
output". The answer here has three parts, and each is a piece of code rather than a guideline:

- **The arc is the unit of parallelism**, not the item and not the file. An item is one to three
  gestures - too small to be worth its own context; an arc already shares a subject, and the format
  already carries it.
- **The number of agents is derived, not chosen.** It is the smaller of how many arcs are actually
  startable right now (read from the live plan) and how many arbitrations one coordinator can absorb
  per round (a figure taken from a recorded observation, cited with its source, never re-guessed).
  Adding agents past that point buys coordination overhead instead of throughput.
- **Batches are disjoint and their contracts are emitted, never copied.** `make lot-emit` cuts the
  work and produces each agent's mandate from one source. Two agents cannot be handed overlapping
  files, and no batch instruction can quietly diverge from the others - the same "a copy drifts, an
  address doesn't" rule that governs the rest of the codebase.

See [`docs/FORMAT_PLAN.md`](docs/FORMAT_PLAN.md) for the format itself (it reads in about thirty
seconds); the parallel-execution rules live in
[`system/lib/mnemosyne/production/orchestration.py`](system/lib/mnemosyne/production/orchestration.py),
which derives the agent count, and in
[`lot_emit.py`](system/lib/mnemosyne/production/lot_emit.py), which emits each batch's mandate.

## Agent-governance hooks

[`.claude/hooks/`](.claude/hooks/) turns several of the ideas above into things that fire
automatically in an editor session, rather than depending on an agent remembering to run them:

- **`session-start.sh`** pushes the self-model, a memory-ratchet check, and a pointer to the current
  state at the start of every session - including after a context compaction, which is exactly when
  an agent is most likely to have forgotten where it was.
- **`user-prompt-submit.sh`** watches only the human's own prompt (parsed out of the event payload,
  never the surrounding metadata) for an intent to file something into the system, and reminds the
  agent to do it immediately rather than "later". It is silent otherwise, because a hook that fires
  on every turn is a hook nobody reads.
- **`stop.sh`** is a proxy for "did this turn do something worth not losing" (it wrote a file or
  committed) and, only then, reminds the agent to run the propose/capture/tidy ritual - plus it
  actively detects learning signals (a correction, an explicit "remember this") and quotes them back
  rather than firing a generic reminder nobody reads twice.
- **`stop-dispatch.sh`** exists because the editor allows exactly one blocking decision per
  turn-chain. Two hooks registered on the same event do not cooperate - they compete for the single
  slot, and whichever runs first silently spends it. So one dispatcher decides which handler speaks.
  This is a general lesson about hook systems, not a quirk of this repo.
- **`pre-compact.sh`** writes the "where was I" breadcrumb to disk *before* the context is
  summarised, and writes it mechanically before asking the model to read it. A hook that merely told
  the model to persist would be a wish: the model could ignore it and the file would not exist. Here
  the file lands whether or not anyone obeys.
- **`pre-tool-use.sh`** is the one hook in this set that actually *blocks* something: it refuses a
  shell command containing a backtick the shell would substitute, closing off one class of accidental
  command injection from an agent's own tool calls.

Every one of them fails open except `pre-tool-use.sh`, which fails closed - see the design philosophy
section above for why that split is deliberate rather than inconsistent. The reason the blocking one
is worth its risk is that a rule an agent re-reads every turn still gets violated; a rule the shell
refuses to run does not. A lesson without a barrier is only a wish.

## The local assistant UI

[`ui/`](ui/) is a small, dependency-free (standard-library-only) HTTP server plus a vanilla JS/CSS
frontend, implementing two roles backed by a locally-running model:

- a **task steward**, holding a lightweight task/subtask store with a tool-calling loop (search notes,
  read further back in the conversation, create/rename/move/delete a task);
- a **decision advisor**, with its own tool set (weighted-matrix scoring, decision-under-uncertainty
  frameworks, a scratch notebook, a sandboxed code-execution tool).

Both roles share one **worker process** that keeps a model loaded between turns (a cold start costs
several seconds; a warm turn costs a fraction of that) behind a single lock, because only one large
model runs at a time on a single machine. Stopping the worker is a real process termination - not a
"pause" that leaves gigabytes of a loaded model sitting in memory pretending to be stopped. See
[`ui/README.md`](ui/README.md) for how to run it.
