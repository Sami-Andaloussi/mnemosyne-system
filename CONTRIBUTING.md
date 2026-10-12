# Contributing

This repository uses a local test ladder and a few conventions worth knowing before you send a change.

## Setup

```bash
make setup   # uv sync
make hooks   # installs the local pre-push gate (`make test` runs before any push)
make check   # lint + test, the same gate CI would run if there were one
```

The base install is enough for the engine, the test suite, and all the governance tooling (plans,
policy, skills). The knowledge pipeline and local-model runtime need the optional extra:
`uv sync --extra bricks`.

## Ground rules

- **Non-destructive.** If a change needs to remove something, prefer archiving, marking withdrawn, or
  quarantining over deleting. Several tools in this repo (`make plan-archiver`, `make rangement` -
  *rangement* is French for tidying up) exist specifically so nothing has to be deleted to stay tidy.
- **Fail-closed on anything irreversible, fail-open on anything advisory.** See `ARCHITECTURE.md` for
  the reasoning - match new checks to the right failure mode rather than defaulting to one.
- **A copy drifts.** If a contract, prompt, or schema needs to be read by two different consumers,
  emit it from one source (see the `*-emit` Makefile targets for the existing pattern) rather than
  hand-maintaining two copies.
- **No secrets in the repo.** API keys and tokens are read from environment variables, never
  hardcoded - `system/config/policy.toml` and `.gitignore` are already set up to keep it that way.
- **A long change gets a plan, and the plan gets a gate.** Anything spanning more than a session is
  tracked as a plan folder rather than a paragraph in a pull request. Don't hand-write one:
  `make plan-nouveau CHEMIN=<path>` scaffolds a plan that already passes the format gate, and
  `make plan-gate-emit` installs the gate that keeps it passing. `docs/FORMAT_PLAN.md` is the format
  itself and reads in about thirty seconds.
- **Tests accompany behavior changes.** The test ladder (`make test`) is what makes the claims in
  `ARCHITECTURE.md` verifiable rather than aspirational; a change that alters behavior without a test
  covering it is the kind of change most likely to regress silently later.

## Reporting a bug

There's no separate tracker - open an issue on this repo with what you ran, what you expected, and
what happened instead. If you can reduce it to a `make <target>` invocation, that's the fastest path
to a fix.
