# Projects

`projects/` is the local workspace for work that needs its own plan, operating context, and bounded
set of source material. Mnemosyne treats a project as a first-class boundary: its files are not just
another folder in the library, and an agent should not cross into it without an explicit policy
contract.

This public repository intentionally ships with no project content. The directory is ignored by Git
apart from this guide, so local plans, notes, datasets, and working documents cannot be committed by
accident.

## A minimal project

Create a project folder when a piece of work has a durable outcome and deserves its own execution
history:

```text
projects/
  example-project/
    PLAN.md
    plan/
      arc-a.md
      arc-b.md
    notes/
    sources/
```

`PLAN.md` is the door: it states the project's current objective, cap, and the arcs that are active.
Files under `plan/` hold those arcs separately so longer work can be read, checked, and archived
without turning one document into an unmanageable timeline. See [the plan format](../docs/FORMAT_PLAN.md)
for the accepted structure and the commands that validate it.

`notes/` and `sources/` are suggestions, not required names. Use the layout that makes the work
legible, then declare any access or sensitivity boundary through the policy configuration before a
tool reads across it.

## What belongs here

- A research, engineering, or analysis effort with a concrete outcome.
- Its plan and locally useful working context.
- Inputs that should remain scoped to that project rather than becoming shared library material.

## What does not belong here

- Credentials, generated state, downloaded models, or copies of the shared engine.
- Unreviewed personal material you intend to publish later.
- A public example containing real client, employer, library, or conversation data.

If you want to share a reusable example, create a synthetic example outside this ignored workspace
and document its assumptions explicitly.
