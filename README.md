# Mnemosyne

**A local environment for building large, long-running LLM-driven projects - with a memory and a
library - agnostic to which model runs it.**

Mnemosyne is what's left once you stop treating an LLM agent as a one-off script and start treating it
as a long-lived collaborator: something that needs a memory that survives between sessions, a library
it can cite instead of hallucinate from, guardrails that hold even when nobody is watching a given
tool call, and a way to check its own work that doesn't just take its word for it.

Its architecture keeps model providers behind explicit boundaries: the included runtime currently
offers local MLX and optional Anthropic integrations, while other providers require their own adapter.
Neither is selected by default - you choose per task, and the system never silently assumes.

## Why this exists

Agentic coding tools are good at *doing*. They are not, by default, good at:

- **Remembering** what was already decided, so the same mistake isn't relearned every session.
- **Citing** a real source instead of confidently paraphrasing one from a fuzzy memory of it.
- **Refusing** an action a human never actually approved - an API key that leaks to the wrong host,
  a policy that widens itself, a file that gets deleted "because it looked unused."
- **Grading its own homework** - an agent that reviews its own diff will find what it expects to find.

Mnemosyne is a set of concrete, testable answers to those four gaps, built as ordinary Python
libraries, CLI targets, and a couple of editor hooks - not a framework you have to buy into wholesale.
Take the pieces you want (see `make arsenal` once installed); nothing here is a conscription.

## The core ideas

- **The Guard - a deny-by-default reference monitor.** Every external call (a frontier API, an
  egress request, a policy change) is mediated by one place that can say no. An empty allow-list
  authorizes nothing; widening it is always a deliberate, logged, human-approved act - including a
  gate that requires a *live* "yes" typed into a real terminal, which no automated agent can satisfy.
  See [`system/lib/mnemosyne/guard/`](system/lib/mnemosyne/guard/).

- **Compartmentalisation (`cloisonnement`) - least privilege by data domain.** Data lives in
  "bubbles": named working contexts, such as a personal knowledge base or one specific project.
  Crossing between them requires an explicit, declared contract; nothing is readable by default just
  because an agent happens to have filesystem access. A separate axis tags each document `public`,
  `perso` (personal) or `sensible` (**sensitive** - not the English "sensible"), and the two axes are
  checked independently.

- **Non-destructive by construction.** Nothing is ever silently deleted. Tidying moves things aside;
  removing a memory marks it withdrawn but keeps the archive; a plan's history is archived byte-for-byte
  before a single character is rewritten, and the archiving code verifies its own reconstruction
  *before* it writes anything.

- **Producer != verifier.** Anything a session builds is checked by a separate, isolated pass - never
  self-graded. The same rule that governs the humans reviewing this code governs the agents building
  it: an audit that trusts its own author isn't an audit.

- **A knowledge pipeline that verifies instead of trusting.** Ingest your own library (PDFs, EPUBs,
  transcripts) with `make ingest`, distill it into structured notes with `make distill`, then run
  `make judge` - a verbatim-floor checker that flags any distilled note whose claims can't be traced
  back to real text in the source, rather than trusting that a summarization pass didn't quietly
  invent something. Retrieval (`make search`) is hybrid: dense vectors + BM25 + a reranker, with a
  measured, per-domain recall floor instead of one guessed global threshold.

- **Skills that have to prove they help.** A new "skill" (a bounded, reusable agent capability) isn't
  trusted because it reads well. It goes through a differential trial: two arms run the same task,
  one equipped with the skill and one without, judged blind under a secret salt so the judge can't
  infer which is which from context - see `make skill-eprouver` / `skill-juger` / `skill-verdict`.

- **Project engineering that is enforced, not merely recommended.** Long-running work is tracked as
  a `PLAN.md` *door* - a short "what is true right now" header plus an index - with the content
  split into dated *arcs* under `plan/`. What makes this more than a naming convention is that the
  code which reads a plan is the same code that gates commits: a plan whose index does not name an
  arc exactly once, or whose heading claims a phase is done over items that are still open, is
  refused rather than quietly rendered wrong. `make plan-nouveau` scaffolds a plan that already
  conforms, so adopting the format costs nothing; `make plan-gate-emit` installs the gate that keeps
  it conforming, which is the part that actually holds - a standard that is only declared is not a
  standard. Archiving a finished arc is byte-exact by construction: the tool refuses to write until
  it has confirmed that `archive + remaining plan` reassembles the original file exactly. See
  [`docs/FORMAT_PLAN.md`](docs/FORMAT_PLAN.md).

- **Parallel agents without collisions.** When a plan is large enough to want several agents at
  once, the unit of parallelism is the *arc*, and the number of agents is derived from the plan
  rather than chosen by hand. `make lot-emit` cuts the work into disjoint batches and emits each
  agent's contract from a single source instead of copying it - so two agents cannot be handed
  overlapping files, and no batch instruction can silently drift from the others. See
  [`system/lib/mnemosyne/production/orchestration.py`](system/lib/mnemosyne/production/orchestration.py)
  and [`lot_emit.py`](system/lib/mnemosyne/production/lot_emit.py).

- **A local, offline-first assistant UI.** [`ui/`](ui/) is a small dashboard, backed by a Python
  standard-library HTTP server and a locally-running model, implementing two LLM-backed roles - a
  task steward and a decision advisor - with a tool-calling loop, thread persistence, and process
  lifecycle management that actually frees memory when you stop it. See [`ui/README.md`](ui/README.md).

Full write-up: [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Quick start

```bash
git clone https://github.com/Sami-Andaloussi/mnemosyne-system.git
cd mnemosyne-system
make setup   # uv sync - creates the venv, installs the dev toolchain
make hooks   # wires the local pre-push test gate
make help    # every target, one line each
make arsenal # the same targets, organized by what they actually buy you
make project-new NAME=example-project GOAL="a bounded research question" BUBBLE=public
make plan-nouveau CHEMIN=docs/plan   # scaffold a plan that already passes the format gate
```

`make project-new` prints a deny-by-default project proposal; it does not write or activate anything.
When you are ready to create local working material, see [`projects/`](projects/) for the workspace
layout and [`docs/FORMAT_PLAN.md`](docs/FORMAT_PLAN.md) for the required plan format.

Most of the engine (linting, tests, the plan/skill/policy tooling) needs nothing beyond the base
install. The knowledge pipeline and the local-model runtime need the optional `bricks` extra
(`uv sync --extra bricks`) plus your own document library under `knowledge/raw/` - this repo ships
with that folder empty on purpose; it's your library, not a bundled one.

**What runs where.** The split is along one line: anything that loads a model locally, or launches
the dashboard, currently targets macOS on Apple Silicon (it uses MLX, and the launcher is a zsh
script). Everything else is portable Python.

| portable (plain `make setup`) | macOS + Apple Silicon only |
|---|---|
| the test suite, linting, `make check` | the dashboard, and `make ui-json` behind it |
| the plan engine (`plan-nouveau`, `plan-archiver`, `plan-gate-emit`, `lot-emit`) | `make local-run` - local model generation via MLX |
| the policy and Guard tooling (`policy-approuver`, `policy-examiner`) | `make modeles` - the local model registry |
| the skill tooling (`skill-eprouver`, `skill-juger`, `skill-verdict`) | |
| memory and session recall (`remember`, `rappel`, `memoire`) | |

The knowledge pipeline (`ingest`, `distill`, `judge`, `search`) sits in between: it is portable
Python, but needs the optional `bricks` extra and a running Qdrant, and its distillation step needs
*some* model - local or remote, your choice.

## What the suite does here, measured

Run `pytest` in a fresh clone and you get **4767 passed, 139 failed, 62 skipped** (measured
2026-09-09 on this tree). That number is stated rather than hidden, because a portfolio that
claims a green suite it cannot deliver is worth less than one that says exactly where the line is.

**The 139 are one cause, not 139 problems.** They are the engine's checks against *this
repository's own working material* - its live plan under `docs/`, its session-instruction file, its
git history, the real folder tree it grew in. That material is deliberately not published (see
"Template data" below), so those checks have nothing to read here. They concentrate accordingly:
**108 of the 139 are in `tests/orchestration/`**, the plan engine, which is the part most tied to a
repository's actual contents.

**They are kept, not deleted, and that is a deliberate choice.** Deleting them would produce a
green suite that proves less: a check which reads the real tree is the only kind that catches a
tool drifting away from the thing it manages, and it is a large part of what this engine is *for*.
Twenty-five of them carry a `TODO(public-mirror)` comment naming the exact dependency they need.

**What this does mean:** the 4767 that pass are the portable core - the Guard, redaction, the plan
format itself, the skill and policy tooling, retrieval, the sanitization gate you are reading
about. Point `pytest` at any single module and it either passes or tells you, in the test's own
name, which private file it wanted.

## Layout

```
system/lib/mnemosyne/   the engine: guard, ingest, retrieval stores, production tooling, runtime CLIs
system/skills/          bounded, reusable agent capabilities (distillation, judging, planning, ...)
system/config/          declarative policy, domain taxonomy, model registry - all human-editable TOML
docs/                   the plan format, plus the contracts for a few specific tools
projects/               local project workspaces, deliberately empty in the public repository
tests/                  the test suite backing the claims above - see "What the suite does here"
ui/                     the local dashboard (Python server + vanilla JS/CSS frontend)
.githooks/              local Git hooks installed by `make hooks`
ARCHITECTURE.md         the design in depth
.claude/                optional local-agent hooks
CLAUDE.md                optional Claude Code session-instructions template
```

## Template data

The repository ships without a document library, session history, runtime state, or credentials.
Configure those locally for your own use; only the engine, tooling, and interface design are tracked.
Project workspaces under [`projects/`](projects/) follow the same rule: the repository includes their
format and boundaries, not anyone's working material.

[`CLAUDE.md`](CLAUDE.md) is likewise a reusable, optional template for Claude Code session
instructions. It demonstrates how to keep an agent oriented without duplicating the architecture or
embedding local decisions; other agents can use the same pattern in their own instructions.

## License

[PolyForm Noncommercial 1.0.0](LICENSE) - free to read, run, and modify for any non-commercial
purpose. Commercial use requires the author's permission.
