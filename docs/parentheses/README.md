# Parentheses — a detour opens beside the plan, and it must RETURN

> **The rule in one sentence:** a parenthesis lives in **its own file**, the plan carries only
> **one line** for it, and it can only be closed by **naming what came back**.

A **parenthesis** is a piece of work that opens **alongside** a plan: a question comes up, a
detour has to be taken. The user's request, verbatim: *"how do we keep a parenthesis from
polluting the main plan, from drifting, from leaving scraps and debt lying around?"*

## The three gestures

> **THIS DOCUMENT IS ADDRESSED TO PROJECTS** (the template `make plan-emit` writes into their
> `PLAN.md` names it) — **and from inside a project folder, `make <target>` does not exist**:
> `make` has no root outside the Mnémosyne repo, you would get `No rule to make target`. **The
> form that works everywhere**, for the three gestures below:
> ```bash
> make -C ~/mnemosyne parentheses          # or: mnemo parentheses  (J4)
> make -C ~/mnemosyne parenthese-ouvrir TITRE="..." PLAN="..." ITEM="..."
> make -C ~/mnemosyne parenthese-fermer FICHIER=... RETOUR="..." DANS=...
> ```
> Here `~/mnemosyne` is wherever you cloned this repository — substitute your own path.

| When | Gesture |
|---|---|
| **A detour opens** | `make parenthese-ouvrir TITRE="..." PLAN="..." ITEM="..." POURQUOI="..." RETOUR_ATTENDU="..."` → paste the rendered line into the plan → **do the work inside the parenthesis file** |
| **At the start of a session** | the tick tells you "N parentheses open"; `make parentheses` shows what each one still owes |
| **The detour is done** | `make parenthese-fermer FICHIER=... RETOUR="what came back" DANS="the file that now carries it"` |

## Why a file, and not a section inside the plan

This isn't a matter of taste, it's a measurement made on this repo on 2026-07-28:

- A parenthesis that lives as a **file with a status** gets drained — a project's `state/audits/`
  (20 folders, 63 files, proven returns, verdicts that **reopen** closed defects);
  `docs/signalements/` (**7 reports, 7 out of 7** marked `traite`).
- A parenthesis that lives as a **section inside a large document** does not get drained — the
  "UI Backlog" section of the project's decisions log: **16 bullet points, not one verifiable
  return**.

## The real failure isn't tidiness, it's the RETURN

This is the central point, and it was measured: **that project's parenthesis was, in fact, a file.** It
is declared **closed**. And a decision it had made — the dependency field, its question Q2 —
**was never executed**: absent from `chantiers.yaml`. Nobody saw it.

So a parenthesis can close **cleanly** while leaving its debt behind. That is exactly the gap the
protocol closes, and it closes it **in code**, not with a house rule:

1. **At opening, `RETOUR_ATTENDU` is mandatory.** Empty → the command **refuses**. This is the
   one moment where nobody yet benefits from leaving it vague.
2. **At closing, you must both name AND place it.** `RETOUR=` (what came back) **and** `DANS=`
   (the file that now carries it, which must **exist**). Naming alone would have let that
   project's case through verbatim: "the dependency field was decided" is a name, and the field still
   wasn't in `chantiers.yaml`.
3. **A parenthesis cannot be closed twice.** A second closing with a different return would claim
   a record that never happened — exactly the silence this protocol exists to forbid.

## The plan carries only one line

That's what keeps it from being polluted. `make parenthese-ouvrir` **hands you the line to
paste** — a single one, with an identifier **computed from the plan itself** so it can never
collide with an existing item (a collision would make the plan *unreadable*, and the `pre-commit`
barrier would then refuse a commit over a line you supplied yourself).

`make parentheses` **flags** a parenthesis its plan doesn't point back to: an open detour nothing
names is invisible from the plan — exactly the leak this exists to catch. It **flags**, it never
blocks: pasting the line is a human gesture, and a tool that refused real work over a missing
paste would be a door slower than the wall.

## The hard rules

- **A parenthesis is never deleted.** Closing it flips its `status:` from `ouverte` to `fermee`
  (invariant 2). The file stays, with its return recorded in its own header.
- **Status lives in the file's own frontmatter**, not in a separate registry — one file, one
  source of truth, nothing that can drift. (Same choice as signalements, same reason.)
- **These files stay out of git** (a structural barrier, `.gitignore`): their prose is written
  from the context of in-progress work, and their **title becomes a permanent filename**. What
  must survive isn't the detour — it's **its return**, and that lands in the plan, which git does
  track. Only this `README.md` stays versioned.
- **The detour is worked on in its own file**, never in the plan. The plan stays the list of what
  is left to do.
