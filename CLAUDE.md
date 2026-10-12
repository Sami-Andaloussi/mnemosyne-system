# CLAUDE.md - a template, not gospel

> **Loaded automatically at the start of any Claude Code session opened in this repo.** This is the
> pattern for keeping an agent's behavior consistent across sessions in a large, long-running project.
> Copy the STRUCTURE and replace the CONTENT with your own decisions. A file like
> this earns its cost only if every line in it is something an agent actually needs to know *before*
> acting, every session. Anything that can be looked up on demand belongs in a doc this file points
> to instead - never duplicated here.

## What this repo is

State your project's identity in 2-3 sentences: what it is, who's it for, and what makes it different
from doing the same task without this scaffolding. If you have a longer design rationale, put it in
`ARCHITECTURE.md` and link it here - don't inline it.

## On startup - orient before acting

1. **Find the current state.** Point to wherever your project keeps a living "what's true right now"
   section - a `STATE.md`, the top of your plan file, whatever it is. Say explicitly that a past
   session's blow-by-blow progress is noise, not context, once the state has moved on.
2. **Discover what the system can do.** If you have a self-describing capability surface (this repo's
   is `make describe` / `make arsenal`), point to it here so an agent doesn't have to be told about
   every tool by hand.
3. **State how to talk to the human.** If your collaborator is non-technical, say so, and say what
   that implies (e.g. "explain the concrete implications of an option before asking them to choose
   between options - never hand them a bare, unexplained decision").

## Hard rules - the ones that don't bend

This is the section worth being ruthless about. Each rule here is paid for on every single session,
so only put a rule here if an agent would otherwise get it wrong *and* getting it wrong would be
costly. A short list of real examples, adapt freely:

- **Deleting the human's own data is their gesture, not yours.** An agent can prepare a deletion
  (name what it is, why, and how big) but the human executes it. This one rule prevents an enormous
  class of "the agent was trying to be helpful" incidents.
- **Producer != verifier.** Whatever this session builds, a *separate* pass reviews it - ideally an
  isolated agent that never saw the reasoning behind the choices being reviewed. An agent grading its
  own work will find what it expects to find.
- **Anything irreversible or externally visible gets a human check first.** Pushing code, sending a
  message on someone's behalf, widening a permission, spending money - pause and confirm, even if the
  agent is confident. The cost of asking is a few seconds; the cost of an unwanted irreversible action
  can be much larger.
- **Say what you decided and why, then keep going - don't stall on every judgment call.** The
  counterweight to the rule above: for reversible, low-stakes decisions, make the call, write down why
  in a commit message or a doc, and move on. Treat every reasonable choice as a stopping point and
  your collaborator will spend their whole day approving trivia.
- **Never commit machine-local or personal configuration.** If your repo has any files meant to differ
  per machine or per person (local API endpoints, personal notes, a scratch directory), name them
  explicitly here and enforce it with `.gitignore` - don't rely on an agent remembering not to `git add -A`.

## If the project tracks long-running work

Point here at wherever the current body of work lives, and at the format it follows. The pattern this
repo uses, which you are free to copy: a plan is a *folder*, not a paragraph - a `PLAN.md` door
carrying the current state and an index, plus dated arcs holding the items. The reason it is worth a
line in a file as expensive as this one is that an agent's most common failure on a long project is
not writing bad code, it's losing the thread of what was already decided and re-deciding it.

Two things make the difference between a format that holds and a format that is merely described:
a scaffold, so writing a conforming plan is easier than writing a non-conforming one
(`make plan-nouveau`), and a commit gate, so a plan that starts lying about its own state is refused
(`make plan-gate-emit`). If you only do one, do the gate - see `docs/FORMAT_PLAN.md`.

## Where the truth lives

If your project has more than one place that could plausibly hold "the answer" (a doc, a database, a
generated index), say which one wins when they disagree, and say that derived stores are *supposed* to
be rebuilt from the source of truth rather than treated as a second original. Ambiguity here is where
silent drift comes from.

## At the end of a task that changed the system

A short, repeatable checklist an agent runs through before considering a task done - capture any
durable learning, propose (never auto-apply) any pattern worth turning into a reusable tool, delegate
repeated cheap work rather than doing it by hand every time, keep the repo navigable, and mind how much
context got spent along the way. See this repo's own hooks (`.claude/hooks/stop.sh`) for one way to
have an agent remind itself of this automatically instead of relying on memory.
