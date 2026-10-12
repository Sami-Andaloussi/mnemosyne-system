# Signalements — when a project breaks against Mnémosyne

> **The rule in one sentence:** a project **flags**, it never **repairs**.
> Repairing is the business of a Mnémosyne session, in its own context.

This folder is the **channel between two work contexts** that must never mix: the session that
**produces** (a project) and the session that **builds Mnémosyne**. The
channel is **the repository** — not a conversation. Nobody has to act as the messenger.

## Why this separation

A project session that starts repairing Mnémosyne loses its production context, and does the
repair badly: it has neither the build history nor the mandate. And if the only channel were "the
operator tells the bug to the other session," then **the operator becomes the messenger** — they
would have to diagnose, themselves, "does this come from the project or from the system?", which
is not their job.

So: the project files a report here, **works around it, and keeps going**. The tick counts what is
waiting and surfaces it on its own. A Mnémosyne session drains the queue.

## The three gestures

| Who | When | Gesture |
|---|---|---|
| **Project session** | something breaks and it smells like the system | `make signaler TITRE="..."` → fill it in → **go back to your own work** |
| **You** | at the start of a session | the tick tells you "N signalements pending" — you have nothing to relay |
| **Mnémosyne session** | when asked | `make signalements` → read → repair (or convert to an ember, `I1`) → flip `status:` to `traite` |

**`make signaler` does NOT exist from inside a project folder — and this is the most serious
failure this contract could have had: the gesture it prescribes to the project session is exactly
the one it cannot type.** *Measured (`J4`): from `projects/<anything>`, same as from an empty
folder, `make` returns `No rule to make target` — it is not the project that is broken, it is that
`make` has no root outside this repository.*
**The workaround works everywhere, right away, with nothing to install**:

```
make -C ~/mnemosyne signaler TITRE="..."
```

Here `~/mnemosyne` is wherever you cloned this repository — substitute your own path.

**And the short form, which only the operator can set up** (one line in their own shell, outside
this repository — Mnémosyne cannot force it): `mnemo() { make -C ~/mnemosyne "$@"; }` — then
`mnemo signaler TITRE="..."`, `mnemo plans`, `mnemo lot-emit ARC=…` from anywhere. *No duplicated
logic, so nothing that can drift from the root.*

## The hard rules

- **Describe the failure honestly.** These reports **do not enter the versioned history**: the
  barrier is structural (`.gitignore`), not a house rule. So you can be precise without
  self-censoring — that is exactly why we took them out of git.
- **What must survive is the lesson — not the report.** Draining a signalement **by repairing
  it** means repairing **and** recording the failure + its fix in the **commit message** (and in
  the decision log if it is structural). The report is a sticky note; the commit is the memory.
  *(Second draining path, without an immediate repair: see the D4/I1 section below — this is not
  an exemption from this rule, it is a second, named door.)*
- **A signalement is never deleted.** Draining it means flipping its `status:` from `ouvert` to
  `traite` (invariant 2). The local history of failures stays useful material, not waste.
- **"I don't know" is a valid answer** to the diagnostic field. It is the Mnémosyne session that
  decides project-vs-system, not the session filing the report.

## D4/I1 — the SECOND draining path: converting to an ember

**AMENDMENT (I1, 2026-08-15): "draining = repairing" was not the ONLY legitimate path, and
leaving it written as if it were would have made it false the first time D4 was actually used.**
The rule above (and the table row further up) describes the case where a Mnémosyne session repairs
the defect **directly**. Since `D4`, a signalement can also become a **schedulable plan item** — an
ember, produced by `mnemosyne.production.signalements.item_de_braise`/`inserer_dans_larc` and filed
by `make signaler … NIVEAU=… COUT=… PLAN=… APPLY=1` — and THIS path drains the signalement too,
**even if the underlying code is not fixed yet**:

- **This is NOT the same as another, older internal registry (D3), found by an isolated audit
  (I1) and corrected here.** That other artifact is the register of shielding-openings refused by
  the floor. It states itself, in plain terms, that it is NOT the ember → item pipeline. Confusing
  the two would send a reader to an empty file that denies the very mechanism that pointed them
  there;
- the tracking does not disappear, it **moves** from a hidden queue (gitignored, invisible to any
  other chat) to a public, governed queue (the plan — declared cost, level, position in the
  dependency graph, subject to the `D3` floor);
- the diagnostic trail survives intact: the item's `*To read*` field points to THIS signalement
  (never copied — a copy drifts);
- here, `status: traite` means *"picked up by the plan mechanism,"* not *"fixed."* The REAL fix
  stays a separate gesture, with its own commit and its own recorded lesson — it is that gesture,
  when the item closes, that satisfies the substance of the original rule.

**ADMISSION (A2, I1 audit): NO CODE HOLDS THE LINK BETWEEN THE TWO HALVES.** The item's
`*To read*` field pointing back to the signalement is a FACT at the time of writing, never an
invariant checked afterward. If the item disappeared or closed without the real fix ever
happening, the signalement would stay `traite` with no trace connecting it to anything anymore. No
barrier prevents this today — wiring that check (for instance: a control that re-reads every
`traite` signalement with no recent `traite_le` and looks for its path in the folded plan's `*To
read*` fields) is a separate item, not guessed at here.

**Both paths remain valid, neither replaces the other.** Repairing directly still always drains
(original rule, unchanged). Converting to an ember also drains, since `I1`. Named here so that
neither one stays a false rule on paper.

## Why OUT of git (the choice was overturned by an audit)

The first version versioned these reports: a failure report seemed non-reconstructible (invariant
24). An audit tore that down, rightly. A signalement is **free-form prose written from a project's
context**: it can name a personal source in its body — and above all **in its title, which becomes
a permanent file name**. And this repository demands **incapabilities, not discipline** (D100 /
invariant 17): a warning in a template would only have been a house rule, and invariant 2 forbids
erasing what has entered the history.

The piece of reasoning that still needed fixing: what is **durable** is not the complaint, it is
the **fix** — and that lives in git. Hence the rule above: *draining = repairing + recording the
lesson in the commit*. Only this `README.md` stays versioned, so that a fresh checkout still learns
what this folder is for.

## On status

Status lives in the file's own **frontmatter**, not in a separate register — unlike the watch
ledger, which tracks *external* records it does not own. A signalement is our own artifact: **one
file, one truth**, nothing that can drift.
