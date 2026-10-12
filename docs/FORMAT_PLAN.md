# FORMAT_PLAN — the only way to write a project plan

> **For the agent arriving on a project.** Reads in 30 seconds, applies with nothing to install.
> Requested by the operator on 2026-07-28: *"we need to impose a way of writing things in a folder
> at the frontiers so that it can easily be handed off to the UI"*.
>
> This is not an invention: the shape was **extracted** from five plans already written in this
> repo, by different agents, in three different projects
> (the measurement itself is a private working document and is not part of this distribution). What is
> imposed here is **the small remainder** those five did not have in common.
>
> ⛔ **The 30 seconds cover the FORM (below), not what HOLDS it.** Adopting D176 (mandatory
> fields)? What that actually buys you lives further down in THIS file, in the
> **"The gate"** (line 703) and **"Saying YES"** (line 744) sections — measured on 2026-08-17: a
> probe that arrived via a `grep D176` stopped halfway through the file and never read them.

## Where — **a plan is a FOLDER, not a file**

*(Deliberate reversal from 2026-07-29, decided by the operator: "folder, folder, folder for
plans. I'm changing my mind. This is fundamental, folder." Their reason is scale — see D166, which
carries the number for each clause. The "Where" clause from before is repealed; everything else on
this page still holds.)*

**The gate**: a file named **`PLAN.md`**, at the root of the folder. Always that name — an
interface cannot search for a file whose name each project gets to choose. It carries the
**heading** and the **index**; it does not need to carry items.

**The arcs**: a folder named **`plan/`** beside it, **one file per arc**. An arc carries items; it
does not need a heading, the gate names it for everyone.

```
my-project/
├── PLAN.md the gate: the heading, the index
└── plan/
 ├── arc-c.md an arc: its items
 └── arc-d.md
```

**This folder does not have to be written by hand**— how it is **born** conforming: see further
down, "How a plan is BORN."

**A single-file plan remains perfectly legal.** No `plan/` folder, all items in the gate: that is
the floor, not a degraded case. Example Project holds 26 plan files **flat** and it is the
healthiest planning corpus measured in this repo.

**Any folder carrying a `PLAN.md` is a plan**— the same rule at every level. An arc that grows too
big becomes a sub-folder with its own gate, its own heading, its own scope of identities.
Recursion is **allowed, never imposed**.

**The gain, measured on Mnemosyne's own plan**: a session working on one arc today opens
**1048 lines** to use a few dozen of them. Gate (~40 lines) + median arc (**38**) = **~78**, i.e.
**93% less**. This is the operational translation of "LLM friendly": context is a session's
scarcest resource.

> ⛔ **BEFORE ANY COMMAND FROM THIS DOCUMENT — FROM A PROJECT FOLDER, `make <target>` DOES NOT
> EXIST.**`make` has no root outside this repo: you would get `No rule to make target`, and think
> the tool broken when it is only missing its address. **Every target cited here is pulled, from
> anywhere, in this form**. Here `~/mnemosyne` is wherever you cloned this repository — substitute your own path:
> ```bash
> make -C ~/mnemosyne <target> [VAR=…]
> ```
> And the short form, once the shell function is set up (`J4`): `mnemo <target>`. *A single
> address, no duplicated logic — nothing that can drift from the root.*

**Two commands, and they need no discipline**:

```bash
make plans
```

says, plan by plan, whether it is **readable**, **absent**, or **present but unreadable** (naming
the reason) — and hands you the skeleton to paste for those that have none. `make project-new`
hands the same skeleton the moment a project is proposed, so the format never has to be guessed.
That skeleton is the **single-file** one, the floor. For the **FOLDER** form, nothing is pasted:
the command to run is **`make plan-nouveau`** (the code writes the gate and the first arc) — and
to receive the structure and apply it yourself, **`make plan-emit`**. Both, right below.

`make plans` covers **a declared list of roots**: `projects/<bubble>/<project>/`, and `docs/` —
Mnemosyne's own plan, the only one that cannot live under `projects/` (a separate git repo). It
used to be invisible there, and had needed a separate barrier written for it: that is how a rule
stops applying to whoever wrote it. A declared root is a **line in a list**, not a second
mechanism.

**This skeleton also carries the ADDRESSES** of what Mnemosyne holds for you outside your folder
(`make describe` · this page · `docs/signalements/README.md` · `docs/parentheses/README.md`) —
**D163: the address, never the copy.** This is deliberate: NOT browsing `docs/` is the *correct*
behavior for a project agent (every document read for nothing is burned context), so it is the
sender's job to point, not the reader's job to search. A test checks that **every address exists
on disk**: a dead address reads like a live map and leads nowhere.

## How a plan is BORN — the repo knew how to REPAIR and JUDGE, not how to GIVE BIRTH

`make plan-convertir` knows how to **repair** (a plan that is a file becomes a folder); `make plans`
and the pre-commit barrier know how to **judge**. Giving birth to an **already conforming** plan did
not exist: the repo's only skeleton renders ONE file, so every plan-folder had to be **converted
into existence**, and a hand-written plan-folder was born wrong. Two gestures close that, and they
do not overlap — one **hands the structure to an agent**, the other **writes it in their place**.

**1. `make plan-emit` — the LITERAL structure, never its description.**

```bash
make plan-emit [NOM="my project"]
```

Hands the agent the **exact content to write**— the gate, an arc, the index entry, the statuses,
the accepted **and** refused separators, the named refusals — replayed from the code
(`plan_scaffold`, `plan_convert`, `plan_format`), never copied by hand. **The reason is not
ceremony, it is already written in the repo**: *an agent told "write a plan in the imposed format"
writes something slightly different each time*, and the drift only shows the day an interface
displays nothing (docstring of `plan_skeleton`, `plan_format.py`). This is also why **this very
page does not copy those bytes**: a copy drifts — exactly the class D170 paid for — and a
masterexecutor contract has **a single code home**, emitted to each host. The `planificateur`
skill carries this contract; `make plan-emit` is its seam.

**2. `make plan-nouveau` — the code writes the gate, the arcs folder, and a first arc.**

```bash
make plan-nouveau CHEMIN="projects/<bubble>/<project>" [NOM="…"] [CAP="…"] [ARC="…"] [APPLY=1]
```

**Dry by default**: it shows, byte for byte, what it would write — it writes nothing. `APPLY=1`
runs it. It lays down the gate (the heading, the index), the arcs folder, and a first arc
**carrying an item**: that is the floor of the folder form, not a courtesy — an arc with no item is
not readable *as an arc*, and it would pull the whole plan down with it. Every new file is opened
"create-or-fail", so a file that appeared in the meantime makes it **refuse**, never overwrite.

And nothing of the FORM is re-written there: the index entry comes from `index_entry`, the arc
file's name from `slugify`, the statuses from `plan_format`. A **second expression** of the form
would reopen the class D170 paid for: a reference calibrated on what the tool writes.

 **The guarantee that matters is structural: the READER judges the bytes BEFORE any write.**
It is not the command that declares itself conforming. Before a single byte touches disk,
`verify_readability` replays on the produced strings **exactly** what `read_plan_tree` and the
pre-commit hook do — `read_plan` + `merge_plan` + `index_problems` + `is_readable`. The verdict is
therefore rendered by **the code that will judge the commit**, never by the producer: a producer
grading its own output is the defect already measured here (D75). Direct consequence — **a plan
born through this command passes the barrier on the first try, with no conversion.**And if it did
not pass, nothing is written: the refusal then says that the scaffold and the reader have
**diverged**, which is a defect in Mnemosyne, not a fault in the request.

**It refuses rather than overwrite** (inv. 2), and **a single reason blocks the WHOLE birth**— a
half-written plan would be a plan the barrier refuses, to repair before anything else can be
committed. Every refusal also names its **remedy**: a refusal that names a problem without naming
a gesture turns a tool into an obstacle.

| refusal | what triggered it | the gesture it names |
|---|---|---|
| `chemin_manquant` | no path given — we do not guess where a plan should be born | give `CHEMIN=`: a plan is born where the work lives; guessing it means placing it where nobody will look |
| `hors_depot` | the path falls outside the repo root | target a path **under** the root — nothing outside is judged by the barrier |
| `chemin_occupe` | the path already exists and is not a folder | choose another path, or move the file carrying that name: a plan is a FOLDER |
| `plan_existe` | a plan gate already lives there | nothing here — we never overwrite (inv. 2); to grow this plan, add it an arc, or give birth to a SUB-plan under it |
| `arc_existe` | an arc file to write already exists | rename the requested arc, or target another folder — overwriting it would bury what someone already wrote there |
| `collision_de_nom` | two requested arcs yield the same file name | tell the two titles apart: the second would erase the first |
| `arc_sans_titre` | an arc was requested with no title | give it a title — otherwise the tool would have to INVENT a file name, and two silent arcs would carry the same one |
| `nom_manquant` | the plan has no name, and the folder gives none | `NOM="<the project's name>"`: a gate's first line is `# PLAN — <name>` |
| `porte_parente_illisible` | the parent plan cannot receive this sub-plan's index entry | repair the parent gate first (`make plans` names it) — a sub-plan its parent does not index is born ORPHANED |
| `chemin_non_indexable` | the PATH of a **SUB-plan** carries a character the index reader cannot read — its entry in the parent gate would be INVISIBLE, so it would be born orphaned | rename the folder: `l'offre` `l-offre`, `rapports (200)` `rapports-200`. The twelve characters at fault are `"` `'` `(` `)` `,` `;` `<` `>` `[` `]` `` ` `` `\|` — whatever **ends** a path that is quoted, linked, or placed in a cell in real markdown. A **top-level** plan accepts any name at all: its path enters no document |
| `squelette_illisible` | **the reader REFUSES the bytes about to be written**| `make signaler`: the scaffold and the reader have diverged — a defect in Mnemosyne, not a fault in your request |

 **Recursion: the sub-plan and its parent gate's entry, in the SAME gesture.** If the target
folder lives **under the arcs folder of an existing plan**, it is not an independent plan: it is a
**sub-plan**, and the parent gate receives its index entry in the same gesture. Without it, it
would be born **orphaned**— `arc_hors_index` — and the barrier would refuse the commit; a birth
that produces an orphan is a failed birth. The parent chosen is the **closest** plan that truly
carries a gate, never the highest one: placing the entry on the outer gate would be placing it on
a gate that never asked for it. And that parent gate's readability is checked on its **resulting**
tree, sub-gate included — checking it on the tree from BEFORE would be a check valid only in the
state before the edit it is guarding.

 **Allowed, never imposed — and the floor does not move.** The command only gives birth to a
sub-plan if you **target** the inside of a plan; it transforms nothing on its own. A **single-file**
plan **remains perfectly legal**— the "Where" clause above is unchanged, and that is why
`make project-new` keeps handing the single-file skeleton: giving every new project an arcs folder
would impose the recursion D166 deliberately left **optional**. What this skeleton now additionally
carries is the **address** of the two gestures above — D163, the address never the copy: a plan
that grows finds the gesture in the file it already has open, not by rummaging through `docs/`.

## The gate's index is verified BY THE CODE

The gate **names its arcs**. It is enough to write the arc file's name — `plan/arc-c.md`, or even
just `arc-c.md`, in a bullet, a sentence, a table, a link: the **form is free**, only
**completeness** is checked.

 **Two opposite questions, two different rules — and confusing them turned this check into a
wall.**The same measurement on both sides, over the **320 real markdown documents** in this repo
(all of `docs/`, all of `projects/`): **the shipped rule produced 18, all false, 0 true**; the
current rule produces **0**. Those 18 hit **this very page**, the one that specifies the check, the
living plan — including the very paragraph documenting the defect — and **Example Project**, the
project D166 names as the model.

| the question | what counts | why |
|---|---|---|
| **"is this arc named?"** (`arc_hors_index`) | **any mention at all**, anywhere: in prose, inside backticks, even in an example block | getting this wrong costs a forgotten arc; being strict would refuse correct gates, and requiring real links would flag **6 out of 81** at Example Project |
| **"does this named file exist?"** (`index_sans_fichier`) | **only an ENTRY**: the reference lives in a **bullet**, a **table cell**, a **heading**, an **`<li>`**, an `href=` **attribute**, or a **bare line**, **outside a code block** and **outside an indented block**; nothing but **notation** separates it from the marker — and **nothing but notation or a separator follows it**| a page has the right to **cite** a path; only a **declaration** can go stale |

Concretely, **an entry is what the item reader already calls a line**— and these examples live in
a code block because a page that wrote its own examples as prose would be accused by the very
check it describes, which is **exactly** what happened the first time:

~~~markdown
- plan/arc-c.md — a bare bullet
- **ARC-C**⬜ `plan/arc-c.md` — an ITEM: identity, status, then the path
- [ ] plan/arc-c.md — the checkbox, which is the format's FLOOR
- ⬜ plan/arc-c.md — the glyph alone
1. **Arc**— plan/arc-c.md — numbered, bold token, separator
- Arc C — plan/arc-c.md — the path ENDS the bullet
| Arc C | plan/arc-c.md | — a table cell, the first or the n-th
## plan/arc-c.md — a heading
[arc-c]: plan/arc-c.md — a reference link
<li>plan/arc-c.md</li> — the same, in HTML
<a href="plan/arc-c.md">Arc C</a> — an HTML attribute: the quotes bound the path
`plan/arc-c.md` — the line that is ONLY the path
~~~

 **These twelve lines are a TEST**, not an illustration: the suite extracts them from this page
and requires the check to catch them **all**. A page that describes a form the code no longer sees
teaches every agent who copies it a trap — and none of these forms would have gone red anywhere
else, since the table of culprits lives in the test file that freezes it.

 **The dash before each comment above is part of the rule.** What FOLLOWS the path counts as
much as what precedes it: after the path, the check accepts **notation** (a closing tag included)
through to the end of the line, **or** a **separator**— the same vocabulary as before it. Without
this, **any** bullet starting with a path was a declaration regardless of the sentence behind it,
and `- plan/arc-archive.md a ete archive, il n existe plus` — a line of prose about a vanished arc,
exactly what a converted gate writes about its own history — **refused a genuine commit**. A space
is not a separator: one word behind the path, and it is a sentence.

But "a `C1` in `plan/arc-c.md` and a `C1` in `plan/arc-d.md` are a duplicate" is a **sentence**, and
a sentence declares nothing.

 **This paragraph has been WRONG TWICE, and each time a figure said so.** The first version saw
an entry in **any** occurrence: 320 documents **18 accusations, 18 false**. The fix dug the
**symmetric** hole — a **bare** bullet followed by a fixed decoration — so it no longer saw
**ANY** of the forms this repo actually writes: of the **662 lines `read_plan` reads as items**, it
saw **0**. The next one sees **662**… and **662 also with a whole sentence behind the path**,
meaning it stopped **nowhere**.

 **Three figures, never two.***(a)* what the check **catches**· *(b)* what it **wrongly
accuses**· *(c)* **how many times it genuinely fires**. Today, over the 320 documents:
**37 occurrences of `plan/…md` and 0 DECLARATIONS**— so "0 false accusations" is true **and
without force**, a check that never fires has a perfect false-positive rate. That is why the
guarantee rests on the **tables of forms** and the **probe from both sides** (662 seen as entries ·
**0** seen with prose behind them), not on a corpus sweep. A check that no longer condemns anyone
because it no longer sees anything is **the same wall, flipped**; a check that condemns everything
starting with a path is the original wall.

 **The word that carries the boundary is NOTATION**: between the marker and the path, the check
accepts decorations, a checkbox, a **bold** token, a status glyph, a separator — **never a word**.
`- the command \`ls | plan/arc-c.md\` fails` stays a sentence. And this notation's vocabulary is
**the same code object**`read_plan` uses to separate an item's identity from its title: the two
halves of the module can no longer drift apart without a test going red.

 **Column 0 stays strict**, and it is measured: of the 320 documents, **0 lines** of prose start
with a **bare**`.md` path — but **40** start with a path **inside backticks** (what an editor's
re-wrapped paragraph produces). A bare line in column 0 is an entry; a backticked line is one only
if it **is only** the path.

 **A code block is an EXAMPLE, and it is the closing character that says so.** This page can only
document itself by wrapping one block inside another — and that is exactly where the check went
wrong: as long as it counted closings without reading them, the **inner** closing flipped the file
back to "outside a block" and this very page collected an `index_sans_fichier` on its own example.
The block below is therefore both the illustration and the witness:

~~~markdown
```markdown
- plan/arc-c.md — an example: this is NOT an entry
```
~~~

And a block **never closed** would swallow everything that follows: the check would go silent for
the rest of the file. That is the `bloc_non_ferme` refusal — the last thing that could still make
it mute is now **said**.

 **`plan` must be a WHOLE path segment.** Without this left boundary, any directory whose name
*ends* with "plan" was read as the arcs folder — and `state/audits/fin-de-plan/` **exists** at
Example Project, the project D166 names as the model. `projects/example-project/plan/arc-c.md` is still recognized: the
boundary rejects a longer **segment**, never a longer **path**.

 **A bare name only counts if it is a path on its own.** A gate that never indexes
`plan/notes.md` but mentions `mesures/notes.md` **does not certify** the arc — that is the
exact gap this clause exists to close.

```markdown
# PLAN — my project

> **Cap**: what we are trying to get right now.

## The arcs

- plan/arc-c.md — the plan reader
- plan/arc-d.md — the production queue
```

**Two refusals hold this**— `arc_hors_index` and `index_sans_fichier`, defined with all the others
in the table further down: a single place where the refusal vocabulary is read.

**Why this clause and not a convention**— this is measured, not feared. The best-kept project in
the repo (Example Project: **1 orphan out of 28** plan files, versus **25 out of 25** in the trading
workstream) had **already drifted at the time it was measured**: its most recent plan file declares
`lire_en_premier: true` in its own frontmatter, and the gate — written **three hours earlier**—
does not know it exists. A hand-kept index rots on the timescale of the work itself. And over
**146,161 lines** of the trading workstream, there is **zero** links: no hand-kept convention has
ever survived here.

**Why the form is free**: of Example Project's plan graph's 81 references, **75 are plain filename
mentions**and **only 6** are real markdown links. A rule requiring hand-written links would flag
**6 out of 81** on the best student. A capture rate without its false-accusation rate is a wall.

**Accents are compared in NFC.** macOS decomposes file names (**80 paths** in this repo are in
NFD): without this normalization, every accented arc would collect **two** false accusations at
once — `arc_hors_index` on the file, and `index_sans_fichier` on its entry.

## Readable: it depends on what the file IS

| what is judged | readable when |
|---|---|
| the **gate**| it names its heading (its items are optional — they live in the arcs) |
| an **arc**| it carries at least one item (it has no heading — the gate carries that) |
| the **plan**| its gate has a heading **and** the union of its arcs carries at least one item |

For a single-file plan, the third row is exactly the old rule: nothing changes.

## Identities are unique at the scale of the FOLDER

`id_duplique` no longer stops at the file: a `C1` in `plan/arc-c.md` and a `C1` in
`plan/arc-d.md` **are a duplicate** and are refused. Without this, splitting a plan into arcs would
have made every inter-arc collision invisible, **silently**, on the very edit that creates the
arcs.

**And the scope stops there.** Two DIFFERENT plans are perfectly entitled to each carry an `S02` —
at the targeted scale, a hundred theories will each name a strategy `S02`, and each theory is a
distinct plan. A nested plan (its own `PLAN.md`) is a distinct plan, hence its own scope.

## When an arc is closed: it LEAVES the plan, verbatim

A plan carries two roles at odds — *memory of what was* and *list of what remains* — and it is the
second one you open the file to read. Measured on Mnemosyne's plan: **191 1231 lines in two
days**, a quarter of it under already-closed arc titles. A mature plan therefore makes its own
reading unusable, precisely when it matters most.

```bash
make plan-archiver
```

**Dry by default**: it says what it would do, it writes nothing. `APPLY=1` runs it. It moves every
`##` section whose title carries `✅` or `⛔` into `archive/plan-<date>-<slug>.md`, **byte for
byte**— the reconstruction is verified before any write, and the command refuses if it does not
reproduce the original file character for character. The plan keeps one line of prose pointing to
it (`> **Archived on …**· <verbatim title> [link]`), never an item: an item would need a key and
a status, hence a second place where state is declared.

**It refuses rather than guesses**, and it names the gesture:

| refusal | what triggered it |
|---|---|
| the arc declares itself closed and carries items that are not | *real case*: a `✅` title over four `⬜` items — archiving them would bury work still marked as remaining |
| the title declares both a closed and an open state | *real case*: a `✅` slipped into a parenthesis in the title, next to the arc's `🔄` |

The second refusal says one more thing: **a summary of statuses written into a title is a hand-kept
total**, and the next section explains why that rots.

## A detour does NOT live in the plan — it lives beside it, and it comes back

A question comes up, a detour is needed. Do not write it into the plan: open a **parenthesis**.

```bash
make parenthese-ouvrir TITRE="…" PLAN="…" ITEM="…" POURQUOI="…" RETOUR_ATTENDU="…"
make parentheses # what is open, and what each one still OWES back
make parenthese-fermer FICHIER=… RETOUR="what came back" DANS="the file that carries it"
```

The detour lives in **its own file**; the plan carries only **one line pointing to it**, which the
command hands you ready-made (its identifier is computed from your plan, so it can never collide
and make the plan unreadable). That is what keeps it from polluting.

**The `RETOUR_ATTENDU` field is mandatory at opening, and closing is refused until the return is
both named AND placed in a file that exists.**This is not ceremony: measured on Example Project, a
parenthesis that was *already* a file with a status closed cleanly while leaving a decision never
executed. **Tidying was never the problem — the return was.**
Full contract: [`docs/parentheses/README.md`](parentheses/README.md).

## What is imposed — three things, and nothing else

1. **The first line**: `# PLAN — <project name>`
2. **The heading**, one line, somewhere near the top: `**Cap**: <what we are trying to get right now>`
3. **The status carried BY each item**— never by a sentence that counts items.

Copy-pasteable as-is:

```markdown
# PLAN — Example Project

> **Cap**: close arc 6 before any production.

## Foundation

- **A1**✅ Universal contract for a research program
- **A2**🔄 Economies, geographies and institutions
- **A3**⬜ Sectors, value chains, products
- **A4**🅿️ The full census run — built, tested, awaiting the operator's gesture
- **A5**⛔ The "second YAML registry" path — vetoed, kept so it is never re-proposed
- **A6**⏸️ The go-to-market arc — paused, resumption expected after the foundation

## Later

- [ ] resume the cross-cutting overlays
- [x] freeze the opposable-criterion grammar
```

**The statuses**, and there are no others:

| glyph | means |
|---|---|
| `⬜` | to do |
| `🔄` | in progress |
| `✅` | done |
| `🅿️` | **ready — built and tested, awaiting a human gesture**|
| `⛔` | **closed — will not be done, and that is decided** (nothing will come back) |
| `⏸️` | **paused — resumption expected** (it will come back) |

`🅿️` is a distinction from the operator (*"something to set up, not under way"*) and it is the only
one ordinary markdown cannot say: a 9-hour run ready to launch is neither done nor to-do, and
showing it "to do" hides that it is only waiting on you.

⛔ **and**⏸️ **were not invented here: they were OBSERVED.** Writers were already writing them —
just where the reader was blind: in a `##` heading, in two table cells, behind a token the key
could not read, in indented prose blocks. Refusing a state disciplines no one: it just pushes the
state out of the machine's reach, silently. That is why the pair matters, and why the two labels
must not be confused — **`⛔` says nothing will come back, `⏸️` says something will.** Showing both
as "not done" re-decides what is already decided, and hides what is genuinely waiting.

 A glyph is read as a status **only in its place**: right after the bold token of a top-level
bullet. `- ⛔ **my figure was wrong**` in the middle of prose stays prose, and
`- [ ] ⏸ read this book` stays a to-do item whose title keeps its `⏸`.

**Two notations, either one, never mixed on the same line:**

- `- **ID**<glyph> text` — every status. The **ID** (`A1`, `D8`, `B6-bis`) is the key: it is what
 lets you say *"A2 moved to in-progress"* after the text itself has been rewritten.
- `- [ ] text` / `- [x] text` — the **floor**. Only two statuses, no ID, but it works with nothing
 to learn. A plan written this way is a readable plan.

## `**Succède à**` (H4) — a GATE field, optional, never required like `**Cap**`

**A plan that EXTENDS a frozen plan says so**: `**Succède à**: <path to the archive>`, one line at
the top of the gate, the same pattern as `**Cap**`. A project's first plan has no predecessor to
link to — `succede_a` stays empty, and that is not a defect, exactly like `*Prérequis* : AUCUN` is
not one either.

⛔ **What this field BUYS, in `plan_archive.filiation_problems`**: every item **not done** in the
referenced frozen plan must either be picked back up **by name** (its identifier reappears, as-is,
in the succeeding plan — a prose mention does not count), or **removed** through the dedicated
mechanism (H1, `plan_retrait.py`), or `⛔` **closed** (which already carries, in its own status, the
declaration "will not be done, and that is decided"). *A promotion that silently loses work is a
deletion in disguise.*

```markdown
# PLAN — Example Research

> **Cap**: the sequel
> **Succède à**: archive/plan-2026-08-12-cap-readaptation.md
```

## An item's detail travels WITH it

**Everything you indent under an item belongs to it**, verbatim — bold, links, sub-bullets kept.
That is what makes the difference between a list and a view: `🅿️ THE FULL RUN` on its own hides
that it takes 9 to 18 hours.

```markdown
- **A4**🅿️ The full census run
 9 to 18 h, **non-destructive**, resumable.
 - do not chain a preview: it costs the same duration.

This paragraph is no longer in A4 (it is not indented).
```

On Mnemosyne's plan, a **minority** of prose lines are attached to an item this way — hence
displayable. The others are not, and that is visible.

*(No figure here, and that is deliberate: this page has already gotten them wrong **twice**, the
second time under a heading reading "measured, not assumed" and at +21%, +33%, +19% off the real
figure. A page that forbids hand-written totals cannot write one. The live measurement is the only
one that is authoritative:*

```bash
make ui-json
```

*key `mnemosyne.prose`. What is durable here is the reporting mechanism — most prose is not
attached — never the decimal.)*

## What is NOT imposed

**Everything else.** Prose, tables, quotes, sections, length, the content's language.
The reader only reads the lines above and **counts** everything it ignored — on Mnemosyne's own
plan, prose is by far the largest mass (`make ui-json`, key `mnemosyne.prose`).
That is normal — reasoning lives in the prose; what must be displayable lives in the items.

## What the reader refuses, by naming it

A refusal stops nothing: the rest of the plan is read. But it is never silent — an item whose
status cannot be read is an item an interface would make disappear **without anyone knowing**.

| refusal | what triggered it |
|---|---|
| `statut_inconnu` | a glyph outside the table above (`- **H2**…`) — quoted, truncated to 12 characters |
| `statut_manquant` | an ID with no glyph |
| `double_notation` | a checkbox **and** a glyph behind a bold token (`- [x] **A1**⬜ …`) |
| `id_duplique` | two items share the same key — **in either notation**, and **at the scale of the whole plan folder**, not the file |
| `identite_illisible` | the line **declares** something (a glyph, known or not), but its bold token is not a readable key (`- **Step 1**⬜ …`, `- **Infrastructure**⬜ …`, `- **E2-vetoed**⛔ …`) |
| `arc_hors_index` | a file exists in `plan/` and **the gate names it nowhere**|
| `index_sans_fichier` | the gate names a `plan/…md` that **does not exist**|
| `bloc_non_ferme` | the gate **or an arc** opens a code block (` ``` ` or `~~~`) it **never closes**— everything after it stops being checked, and the check would go silent **without a word**; that is the one thing that could still make it mute, so it is **said**|
| `arc_vide` | an arc file exists and is **BLANK**— its items vanished from the displayed count without a word. **An arc with no items at all is NOT refused**: it is a **warning** in `make plans`, never a refusal, because **7 of the 12 real arcs in this repo** carry none (prose sections turned into files at conversion time). Refusing there would have made Mnemosyne's own plan UNREADABLE and blocked every commit |
| `bloc_document_non_ferme` | a code block opened **at document level** (A7) is **never closed**— same defect as `bloc_non_ferme`, its twin **inside `read_plan`** rather than at folder scale |
| `commentaire_document_non_ferme` | a `<!-- … -->` comment opened **at the start of a line** (A7) is **never closed**— without this refusal, it silently swallowed the rest of the file, with no refusal ever saying so (audit of 2026-08-15) |
| `succede_a_hors_porte` | (H4) an ARC file declares `**Succède à**` — the field counts only on the GATE, same rule as `**Cap**` ("the gate wins"). **Unlike a stray `** Cap**`, which breaks no guarantee**, a stray `**Succède à**` SILENTLY disarms the one barrier H4 exists to raise — found by an isolated audit that went looking for a bypass route other than `--no-verify` and measured a real one: the field was read by `read_plan` on the arc, then silently dropped by `merge_plan` |
| `arc_illisible` | an arc file exists and does not open (permissions, broken link). Raised by the REGISTRY, not the reader |
| `dependance_inconnue` | **PREPARED, NOT CALLED**— like the three that follow: the ORDER judge exists and no surface invokes it yet. A `*Dépend de*` names a step that does not exist. **Never** ignored: an unreadable dependency that gets erased becomes a FREE step, which is worse |
| `dependance_sur_soi` | an item declares itself dependent on itself — unsatisfiable by construction |
| `liste_illisible` | a non-empty `*Dépend de*` whose HEAD is not a list (a sentence). Write the identifiers first, or `AUCUN` |
| `cycle_de_dependances` | steps wait on each other in a loop — the row does not exist. **Named, never raised**: the rest of the plan keeps its order |
| `champ_requis_manquant` | an item does not fill in a field the caller made REQUIRED — **absent OR declared empty**: a question asked and left unanswered is not a question answered. ⛔ **"Empty" reads as a HUMAN sees it, not as `str.split()` sees it**: a field holding only invisible code points (`U+200B`, `U+00AD`, `U+2060`, `U+FEFF`, `U+200D`, `U+034F`) or only an HTML comment (`<!-- … -->`) is EMPTY. *Two escapes proven by real accepted commits, and a third found while fixing it: the class is not "the invisible unicode ones", it is **everything the gate COUNTS that the reader DOES NOT SEE**.* ✅ **ARMED on 2026-08-15**, scope **DERIVED** from `DOOR_FILENAMES` by `champs_requis_pour` — this repo's own root plan gate and its "current" variant, and any `.md` under `docs/plan/`; elsewhere `required=()`, so level 1. *It was written as a list and forgot `PLAN_COURANT.md`: a `git mv` was enough to make the whole obligation disappear.* Measured: **49 items, 0 refusals**, and a real commit carrying an amputated item is REFUSED |
| `prerequis_manquant` | an item declares **no**`*Prérequis*` at all. **This refusal does NOT come from the reader**: it lives in a separate judge (`prerequisite_problems`) the caller decides to call, because wired into the reader it would refuse **168 of Example Project's 168 items** the day it was installed. Level 2 applies to Mnemosyne's plan; elsewhere the field **invites**|
| `prerequis_inconnu` | a `*Prérequis*` whose first word falls outside the closed vocabulary `AUCUN` · `OWNER` · `MONDE` · `AUTRE-PROJET`. Without it, the field would be free text carrying the name of a schema |
| `produit_est_un_dossier` | an item's `*Produit*` cites at least one path in backticks, and **none** of them names a file — all of them end in `/`. **This refusal does NOT come from the reader**: it lives in a separate judge (`produit_problems`) the caller decides to call, NOT wired into `.githooks/pre-commit` — measured before writing it (55 real items: 30 cite no path at all, out of this refusal's reach; 2 cite only folders). An item whose `*Produit*` cites NO path at all is never accused: this clause does not judge absence, only the shape of what is cited |
| `item_perdu_a_la_promotion` | (H4) an item **not done** in the frozen plan `**Succède à**` references is neither picked back up by name in the succeeding plan (an IDENTITY, never a prose mention), nor removed through the dedicated mechanism (H1), nor `closed` (which already carries, in its own status, the declaration "out of scope"). **This refusal does NOT come from the reader**: it lives in a separate judge (`plan_archive.filiation_problems`) the caller decides to call, with the set of removals already applied — this function touches no disk |

> **WHEN YOU TALK ABOUT A FIELD IN PROSE, THE READER DOES NOT KNOW YOU ARE TALKING ABOUT IT.**
> It reads a marker followed by `:` and stops there. Measured, live in the repo: item `A3`
> declared its `*Prérequis*` as `AUCUN`, a line of narrative cited the same field seven lines
> above, and **the item published itself as NOT STARTABLE by its own documentation**.
>
> ⛔ **A GATE WAS REMOVED HERE ON 2026-08-15, AND THE ADMISSION REPLACES THE PROMISE.** A
> `champ_duplique` refusal was meant to punish prose that steals a declaration. It was **removed**:
> it refused **the very remedy this document ORDERS you to write**— an item whose decorated field
> adds its canonical declaration was REFUSED, and **224 decorated declarations across 149 items**
> were one line away from that refusal. It was not bounded the way the rest of level 2 is, its
> message was wrong, and it protected no output (`make plans`, the queue and `ui-json` publish at
> level 1).
> *A gate that refuses the correct gesture gets removed, not patched.*
>
> **The code discards citations that carry a DELIMITER**— a code span (any number of backticks),
> `«…»`, `"…"`, `“…”`, an HTML comment (single- and multi-line, bullet line included) — and
> **nothing else**.
> ⛔ **WHAT REMAINS OPEN, measured**: a **decorated** citation (`**Default.***Prérequis* : …`) or
> one placed at the start of a **continuation line** still steals the value of a real declaration,
> because the reader renders the **first** marker. No signal tells them apart at line level, and the
> arbiter tried to sort them produced four false refusals.
> **Your protection is therefore human, and it is simple: when you TALK ABOUT a field, put it in
> backticks or quotes.**Both are safe by the code.
> ⛔ **WHAT REMAINS OPEN, and here is its CAUSE — measured, not guessed.** An item that does
> **NOT** declare a field but whose prose cites one: the citation **CREATES** the field, and the
> level-2 barrier counts it as filled in (*proven by a real commit*).
> **The cause is not the delimiter, it is the absence of a RIVAL**: a citation can only be
> discarded by **comparison** with a canonical declaration. Where there is none, there is nothing
> to compare against — the arbiter does not arbitrate a lone candidate.
> **And it cannot be closed by judging the character before the marker**: measured across the
> whole corpus, the **332 real decorated declarations** are preceded by `.` (163), `*` (125),
> `|` (32) … **and by `'` (3)**— the same character as the citation we would want to discard. *The
> two populations overlap: any rule on that character would refuse the genuine ones too.*
> **What protects you is therefore yours, and fits in one line: declare ALL your fields in
> canonical form.**A declared field can no longer be stolen; a field never declared can be
> invented by your own prose. A `«` opened on one line and closed on the next also escapes, the
> guard being **per line**.
> *These two residuals are measured and named here rather than promised closed — that is the
> difference between a gate and a wish.*

### A code block and a start-of-line comment cite the DOCUMENT, not a field

Everything above closes the citation at the **item** level — a field marker cited in prose is no
longer read as a declaration. `A7` closes the same class one level up, at the **document** level:
the question is no longer "does this marker declare?" but **"is this whole line a plan, or the
citation of a plan?"**

⛔ **Measured, live: `docs/FORMAT_PLAN.md` — this very document — saw its own teaching examples
read as real items.**A ```` ```markdown ```` block illustrating the syntax, or a draft parked in a
`<!-- … -->` comment **opened in column 0**, produced real, incomplete items — `make plans` and any
direct caller of `read_plan` refused the document that explains the format. The same class bit a
second, independent module two hours later: *"a teaching example is not an order, but nothing tells
the two apart when they share the same form"*.
 **Correction (audit of 2026-08-15, H7): NOT at the commit itself, for THIS specific file.**
`.githooks/pre-commit` only selects `PLAN.md`/`PLAN_COURANT.md` (at any depth) and any `.md` under
a `plan/` segment — `docs/FORMAT_PLAN.md` matches neither, so `champs_requis_pour("docs/FORMAT_PLAN.md")`
renders `()` and this specific file is **never** judged at commit time. The damage was real at the
scale of the **library**, not the **gate**— and it was a commit message (`d48249f`), not this
page, that had hardened one into the other.

 **The reader now ignores two regions at document level**: any closed code block
(```` ``` ```` or `~~~`, 0 to 3 spaces of indentation) and any HTML comment opened at **0-3 spaces
of indentation**— the same tolerance as the fence, since the 5th audit of `A7` (G4). Nothing else
is structurally recognized there — no heading, no cap, no section, no item — for as long as the
region stays open.
 **Correction (G4): this page used to say "strict column 0, an indented draft stays covered by
the item mechanism". FALSE in a measured case**: if the `<!--` OPENER is indented but the CONTENT
(an item bullet) comes back to column 0, neither this mechanism nor the item's own (which only
sees the block of one bullet) covered it — and a bullet in column 0 inside it could steal a real
item's identity. Closed by widening the tolerance to 0-3 spaces; cost measured at **0** across the
1733 real documents in the repo.
 *No signal of this kind exists for NON-closed text*: an item example written in plain prose,
with no backticks or comment around it, stays indistinguishable from a real item — as with the
field-level citation, the only protection is to write the example **inside** one of the two
recognized forms.

⛔⛔ **DELEGATED AUDIT OF 2026-08-15 (D75): THE FIRST VERSION OF THIS GUARD DID NOT HOLD.** An
isolated third party found two defects INSIDE the clause, both born of the same fault: a block's
closing was a simple **toggle**, with no regard for the delimiter's character or length —
*not* the CommonMark rule (same character, a run at least as long, nothing but an info string
after it).
- A ```` ```markdown ```` **nested inside a**`~~~` — the form this very page must use to show an
 example without the renderer closing it prematurely — closed on the wrong delimiter and gave
 birth to a parasitic, refused item.
- A fence **unmatched inside a comment** (an output excerpt pasted into a draft, an ordinary
 thing) toggled the state while still inside the comment; the real `-->` then fell into the wrong
 `continue` and was never seen — **both regions stayed open until the end of the file**,
 swallowing every real item that followed, without raising a single refusal.

 **Fixed: a single state, strict priority to whichever block is already open.** As long as a
comment is open, no line inside it opens or closes a fence, and vice versa — exactly what a real
HTML block does, governing until ITS OWN closing. Closing a fence reuses the same predicate as
`_scan_fences`/`live_lines` (a single home for the CommonMark rule, called at both sites) instead
of carrying a second, weaker copy.


 **`identite_illisible` exists because the silence used to.** A key must be ASCII, no spaces,
≤ 12 characters — so `**Step 1**`, `**Infrastructure**`, `**Arc C**` fell into **prose** and
vanished, on a format imposed on plans written in French. A line that declares nothing
(`- **Incarne**: …`) stays prose: it is the **glyph** that separates an accusation from a false
one.

 **And the silence had one last corner: the CROSSING of the two defects.** A line whose token is
unreadable **and** whose glyph is unknown fell into no rule at all — neither item, nor refusal, no
trace. The reader owed three outcomes per line and rendered a fourth: nothing. This is measured on
Mnemosyne's own plan, which declared itself *readable* while hiding a line. The rule is now set on
the **class**: a bold token followed by a **pictogram**, whatever it is, is either read or refused
by name — never silently skipped.

The net was measured **before** being written, over every `.md` in the repo: among the bold-token
bullets the reader leaves as prose, the character following the token is a pictogram **exactly
once**— the line above. A broader Unicode category (mathematical symbols) would have accused
**194 others**, including the 33 ordinary sentences of the form `- **X** y` this repo writes
everywhere. A capture rate without its false-accusation rate is a wall.

## The one rule with no barrier — and I am saying so

**Write no hand-made total.** No "8 of 13 arcs closed", no summary table of statuses: the tool
computes them from the items. This one rule is **not** held by code, it is held by your own
discipline — so it will break.

This is not a fear, it is measured, and it is Example Project that wrote it in its own registry:

> *"This field announced 'the 17 still-blocking defects' and 'FIVE bodies of work' when the file
> listed SEVEN workstreams and the counter found TWENTY-ONE. […] A computed number cannot rot, a
> copied number does within three days."*
> — `projects/saas/example-project/state/registres/chantiers.yaml`, field `meta.role`

The reader **flags** tables that contain status glyphs (a second possible source), without
refusing them — a table can carry something other than status, and refusing broadly would kill the
good with the bad.

## Where projects stand today — measured, not assumed

*(This table says WHO is readable and WHY — never how much. The two conforming plans change with
every edit, so their figures are pointed at `make ui-json`: copied here, they had drifted from
+21% to +33% in six commits, in a table sold as measured. The non-conforming rows, by contrast,
carry a stable state — it is their FORM that makes them unreadable, not their size.)*

| plan | readable? | items | prose (of which attached to an item) |
|---|---|---|---|
| Mnemosyne (its own root plan) | **yes**| *(see `make ui-json`)* | *(same)* |
| `projects/mnemosyne/ui/PLAN.md` | **yes**| *(see `make ui-json`)* | *(same)* |
| `trading/example-lab/ROADMAP.md` | no — no `**Cap**` | **9** (checkboxes, no ID) | 79 (0) |
| Example Project (`ROADMAP.md` + `STATE.md`) | no | **0**— the plan lives in tables | 194 (0) |
| `governance/PLAN_INCARNATION.md` | no | **0**— prose | 181 (0) |

**Two plans out of five have nothing a machine can read.** Converting them is not this arc's job —
and above all, **Example Project is never touched from a Mnemosyne session**: it is an Example Project session that
will lay down its own `PLAN.md`.

The **first project to receive the format** was the UI (`projects/mnemosyne/ui/PLAN.md`, laid down
on 2026-07-28): `make plans` showed it `absent` until then. It cost nothing to write — which is the
only valid argument for imposing a form.

 **Mnemosyne's own plan was NON-CONFORMING** until 2026-07-28: no `# PLAN — …` title, no
`**Cap**:` line. This page was therefore imposing on projects a rule its own author was exempt
from, and nothing said so — because `make plans` only looks at `projects/`. That is fixed, and
above all **`make ui-json` now publishes this very plan's state** on the same footing as every
project's: the repo's conformance to its own rule is no longer something only a test could see.

## The reader

`system/lib/mnemosyne/production/plan_format.py` — a pure function, writes nothing, guesses
nothing. The markdown example above is re-read by the test suite: if it stops conforming, a test
goes red. A format page that lies while the code tells the truth is the defect already measured
here.

**And the writer**: `system/lib/mnemosyne/production/plan_scaffold.py` — also pure, it computes
bytes and refusals, it opens and writes nothing (the effects live in
`system/lib/mnemosyne/runtime/plan_new_run.py`). It **never** grades its own output: it is the
reader above that declares it readable, and before it ever touches disk.

## The gate — TWO paths that HOLD adoption, a third that does not

This document states the FORM. For it to HOLD at whoever adopts it, there are two measured paths —
and taking neither remains a declaration, never a held adoption.

⛔ **Correction of 2026-08-17, the fault is named rather than erased (inv. 2).** This section used
to claim *"Example Project's adoption was declarative, never held"* — **that was FALSE**, written before
checking reachability: `/usr/bin/grep plan_format scripts/pre_commit.py` returned `0`, and the
word's absence became a defect without asking whether a level of INDIRECTION was missing. It was:
`scripts/pre_commit.py` **calls**`validation/plan/index_des_arcs.py`, which **imports**
`plan_format` directly (line 192) — Example Project built ITS OWN gate rather than install ours. Replayed
just now: `index_des_arcs=pass (14 gate(s) judged, 0 index problem)`, `format produit` over the 14
gates, **168/168 items, 0 divergence**. The adoption held all along.

**The two paths, each measured:**

1. **Install the EMITTED gate**— `make plan-gate-emit` renders a pointer (never a copy, D163) to
 the single judge (`plan_format.index_problems`). THREE gestures, real only at the third:
 1. **write** the file it renders to `.githooks/plan-gate` on your own machine;
 2. **wire** your own pre-commit to call it;
 3. **TEST IT**— two opposite runs (it must REFUSE an unindexed arc, and LET THROUGH an honest
 commit). Either run alone is not enough: a guard that refuses everything passes the first.
2. **Build your own gate that IMPORTS the judge**— Example Project's path: its pass imports `plan_format`
 directly instead of installing the emitted file, and its pre-commit genuinely calls it. Just as
 sound as path 1, on one condition: check BOTH ends (the import AND the real call from
 pre-commit) — a `grep` that checks only one leads exactly to the fault above.

**What the gate refuses, once installed by EITHER path — two rules, never confused:**
1. an arc nothing in the gate cites (`arc_hors_index`), or a file the gate cites that no longer
 exists (`index_sans_fichier`);
2. IF the gate declares `**Format**: <fields>` (D176, a CHOICE never imposed — declaring nothing
 leaves this rule at zero), an item that does not fill in one of the chosen fields. `AUCUN`
 remains a valid, free answer.

 **Measured, not hypothetical**: installing the EMITTED file (path 1) has already broken TWO
native guards on a walled host (Example Project) — an anti-exfiltration freeze on the sites allowed
to launch a subprocess (this very file IS one, absent from that freeze before it was added), and a
folder-documentation check. The `*-emit` pattern assumes a NEUTRAL host; a host that already has its
own guards can collide with the new one — **which is precisely why Example Project took path 2.** Path 1's
third gesture must test that YOUR EXISTING guards still hold, not merely that the new one bites.

## Saying YES, and in which words — the adoption syntax (D176)

⛔ **Measured on 2026-08-17: a good-faith project writing `** Format**: Produit, Fini quand,
Dépend de` believes it is adopting three fields. The judge (`plan_format.champs_requis_pour`) keeps
**ONE**, and nothing tells it so.**Tokens are compared **in lowercase, accents and spaces
INCLUDED**— no unfolding — so only the exact form below counts:

```
git status --short
python3 -c "from mnemosyne.production.plan_format import champs_requis_pour as c; \
 print(c('projects/x/y/PLAN.md', 'Produit, Fini quand, Dépend de'))"
# -> ('produit',) 1/6: only 'produit' folds itself into lowercase
python3 -c "from mnemosyne.production.plan_format import champs_requis_pour as c; \
 print(c('projects/x/y/PLAN.md', 'produit, fini_quand, depend_de, prerequis, a_lire, taille'))"
# -> ('produit', 'fini_quand', 'depend_de', 'prerequis', 'a_lire', 'taille') 6/6
```

**The syntax**: a `**Format**: <tokens>` line at the top of THE GATE (never an arc), read ONCE —
the wanted tokens, comma-separated, in the literal spelling below.
**The exact six tokens**, copied from their one real home — `FIELD_NAMES` in
[`system/lib/mnemosyne/production/plan_format.py`](../system/lib/mnemosyne/production/plan_format.py)
— replay the command above if in doubt; **the only thing that would make them go red: the keys of
`FIELD_NAMES` changing, which only the code can decide, never this page**:

```
produit, fini_quand, depend_de, prerequis, a_lire, taille
```

⛔ **Do not copy this list by hand anywhere else — that is exactly the copy that produced the gap
between this page and the code (D163).**A misspelled token, a wrong accent, or the wrong
separator character is **never refused**: it is silently ignored, and the item stays NOT obligated
on that field — no error, no warning.

> ## ⛔ DECLARING IS NOT ENOUGH: YOUR DECLARATION IS HELD BY NOTHING UNTIL A GESTURE RECORDS IT
>
> **The defect this freeze closes, measured**: a gate that declares a format can **erase its
> `**Format**:` line**— twenty characters — and the guard that judges that declaration
> **silently turns GREEN again**, because a gate *never adopted* and a gate that *just lost* its
> adoption render exactly the same empty state.
> **The gesture, once per gate, from anywhere**:
> ```bash
> make -C ~/mnemosyne gel-inscrire PORTE="projects/<bubble>/<project>/PLAN.md" APPLY=1
> ```
> **`make plans` reminds you on its own**: as long as your gate declares without being recorded,
> it prints the gap AND the exact command, one per gate. *Nothing refuses — it is a flag, not a
> wall: adoption stays optional (D176).*
> It **refuses** to record a gate that declares nothing: the freeze certifies *"it declared"*,
> putting it in without measuring would fabricate the very attestation it makes falsifiable.

 **And the sentence that was missing**: **declaring zero tokens obligates NOTHING — it is a
valid, free answer**, exactly like `AUCUN` for `*Prérequis*` (below). A project that adopts the
Format (folder, heading, per-item status) without ever writing `**Format**:` owes **none** of the
six level-2 fields — only level 1 (this document, above) applies.

 **Two figures published on EVERY line of `make plans`, measured on 2026-08-17 as defined
nowhere useful — an earlier probe read one of the two as a D176 conformance rate and chased a false
drift for four steps.**Neither one is among the six tokens above:
- `produits_resolus=N/N` — the share of items whose `*Produit*` cites at least one real path (not
 only a folder). A purely conceptual product is neither resolved nor at fault: it is OUTSIDE this
 population, never counted against you.
- `terrain_declare=N/N` — the share of items whose `*État du terrain*` is filled in (even "nothing
 occupies this role" counts). A field that is KNOWN but **never required** (neither by level 1,
 nor by any D176 token) — do not confuse it with format adoption.

⛔ **And the freeze that arms `VERIFIER=1` (`derives.PORTES_QUI_DECLARENT`) is HAND-WRITTEN.** A
new gate — even one born from `plan-nouveau FORMAT=...` — does not enter it on its own. `make plans`
will see it as OUTSIDE THE FREEZE (nothing refuses or protects it) until someone explicitly records
it there.

## The `*Prérequis*` field — what NEVER lifts on its own

⛔ **A prerequisite is NOT a dependency, and the whole field exists to stop the two from being
confused.**A `*Dépend de*` is a **step of the plan**: it lifts the day that step turns `✅`. A
`*Prérequis*` is **outside the plan**— a human gesture, a state of the world, a datum living
elsewhere — and **nothing inside the plan can lift it**.

| token | who can lift it |
|---|---|
| `AUCUN` | nobody: there is nothing to lift. **It is a valid, FREE answer**|
| `OWNER` | **this project's human guardian**— a role, never a name: the extraction factory and Example Research have no owner [in that role] |
| `MONDE` | a state of the world — nobody here can lift it |
| `AUTRE-PROJET` | another project — it will lift there, never here |

What follows the token is **free text** and is kept for the human: `*Prérequis* : OWNER — they
must type the word live`. A prerequisite that is **lifted** gets rewritten as
`**AUCUN — LIFTED on <date>.**`: the item stops waiting that same day, otherwise the decision-maker's
queue starts lying.

⛔ **Silence is NOT permission to start.** An item that declares nothing is rendered **NOT
STARTABLE**, and that is the asymmetry carrying the whole field: the opposite — absence meaning "go
ahead" — is exactly *validating on a hypothesis*.

### What the SURFACE does with it, and at what level it bites

 **`make plans` PUBLISHES, it does not refuse — it is a level 1.** This needs saying here because
the items carrying this field declare a **level 2**, and the gap is real for as long as nobody has
decided. Today:

| what the surface shows | shape | why |
|---|---|---|
| a **to-do** item, prerequisite declared and not lifted | ⛔ named, with WHO can lift it | this is what is waiting on a gesture |
| an **unreadable** prerequisite (outside the vocabulary) | named, with the word as written | a typo is easy to fix |
| items **without**`*Prérequis*` | a **COUNT**, not a list | there are hundreds of them; naming them would drown out the rest |
| an item **done · closed · in-progress · ready · paused**| nothing | the question "can it start?" no longer applies |

 **None of these three signals blocks a commit.** The pre-commit gate only judges a plan's
READABILITY; arming level 2 is a decision that has not been made, and it is written here rather
than left as a gap between three documents.

## What the reader can read WITHOUT requiring it

⛔ **Two lists, and confusing them is costly.** There is what an item **must** answer, and what the
reader **can** read. Merging the two would mean that adding a field for ONE item silently widens
what ALL the others must declare.

| field | required? | who reads it |
|---|---|---|
| `*Produit*` · `*Fini quand*` · `*Dépend de*` · `*Prérequis*` · `*À lire*` · `*Taille*` | **yes**| its absence is NAMED, never guessed |
| `*Test à trois*` | **no**| **"The three", named (2026-08-16) — the definition lived in USAGE, never in a sentence.** Confront the item with **three real projects at DIFFERENT SCALES**— `Example Project`, `the extraction factory`, `Example Research` (~1,500 plans) — and see which one breaks it. *The case that decides the design is the largest of the three, never the first one encountered*: a clean example on `H2`, *"a GO per removal holds at Example Project, holds at the factory, and DOES NOT HOLD at Example Research — ~1,500 plans there would produce a queue nobody empties"*. Measured on this plan's 64 real items (through the reader's own accessor, not a `grep`): `Example Research` cited in 17 values, `Example Project` in 15, `the factory` in 15 — most items just write "✅ all three" without naming the projects, which explains why the field only explained itself to those who already knew. Read and rendered as-is; no item is ever "short" on it |
| `*Obligation*` | **no**| ⛔ **ADDED on 2026-08-15, and the silence was the defect.** It is declared by **45 of the 50 items** in this plan and was known to nobody: not being a marker, it opened no field — **its value was concatenated onto the preceding field's**, and `missing_fields` stayed empty. *A field the grammar ignores does not disappear: it moves in with its neighbor.* The level-2 barrier produced **0 refusals**: it could not see it. **Known, NOT required**— same precedent as `*Test à trois*`: making it readable is not making it mandatory, and confusing the two would have refused 5 items at once. This is what makes `A2` verifiable: the three-level scale was **engraved but unreadable**|
| `*État du terrain*` | **no**| ⛔ **ADDED on 2026-08-15 (C2), AND ITS ABSENCE FROM THIS PAGE WAS ITSELF THE DEFECT — found by an isolated audit.**Declares what ALREADY occupies the role an item promises to fill; "nothing occupies this role" is a **valid and required** answer (the same precedent as `AUCUN` for `*Prérequis*`). **Declared by 0 of the 55 real items** at the moment this field is added — just as `*Prérequis*` was by 0 of Example Project's 168 items when `prerequisite_problems` was built. The difference that matters: this document exists, so this `0` can become something else; **before this line, no agent writing a plan could learn the field existed except by reading the Python code**|
| `*Sert*` | **no**| ⛔ **ADDED on 2026-08-16 (G2), a corollary of G1**: *"a plan item that matches no deliverable citation is an idea of my own — legitimate, but to be announced as such"*. Cites a deliverable by its number ("serves deliverable 2") or declares `idée à moi` (own idea, case- and accent-insensitive) — an item that says neither stays in the NORMAL state of adoption, never refused. **The only real refusal: citing a deliverable that DOES NOT EXIST**— named, never guessed, exactly like `*Prérequis*` refuses a vocabulary outside the closed list. The logic (`production/livrables.py`, `juger_rattachements`) already existed before this field, built on manufactured pairs while waiting for `item.field("sert")` — **0 of this plan's 61 real items** declare it at the moment the field is added |

⛔ **`*Obligation*` and `*Test à trois*` are RESERVED to Mnemosyne — a project cannot ADOPT them
via `**Format**:` (D176), even if it declares them**(2026-08-16, the operator: *"I'm following
your recommendation"* on the option that names the reason instead of leaving it a gap). This is not
just prose: the gate that reads a declaration (`plan_format.champs_requis_pour`) only filters
against the **six** fields in `FIELD_NAMES` — `obligation`/`test_a_trois` live in
`EXTRA_FIELD_NAMES`, a separate vocabulary no `**Format**:` can reach. *Measured, not just
written*: `champs_requis_pour(porte, "produit, obligation, test_a_trois")` returns `('produit',)` —
the two reserved ones fall away, silently, like any unknown token.

**The reason, measured before being written**: `*Obligation*` carries FREE PROSE starting with
"level 1/2/3" — the scale from `governance/OBLIGATION.md` (published / refuses / incapacity),
a vocabulary whose MEANING is Mnemosyne-specific. A project adopting it would inherit a word that
means nothing in its own domain, or would reuse ours to mean something else — a MEANING COLLISION,
not a gain in rigor. `*Test à trois*` has the same structural defect: its three names (`Example Project` /
`the factory` / `Example Research`, above) are Mnemosyne's three projects — an outside project does not have
those three to compare against, the question does not even arise for it.

An optional field reads exactly like the others — `*Name* :`, or `**Name**:`, or `_Name_ :` —
and its value stops at the first of: **the next field**· **a blank line**· **a code block**·
**a table row**· **a line opening with a pictogram**· **the end of the item's block**.

 **Three residuals, named rather than discovered**:
- a marker placed behind a **bare word** (`… 1 file *Taille* : B`) is a MENTION, so the field
 reads as ABSENT — **and the item is then accused of not having declared it**, even though it
 wrote it. A decoration in front (`**·***Taille* : B`) is enough to make it readable. Measured:
 **1 occurrence out of the 732 published fields** in the repo;
- the "code block" boundary reads a delimiter up to **3 spaces** of indentation. Beyond that,
 markdown already reads an indented block, but this reader does not see it as a closing. Measured:
 **8 of 8** such blocks under an item live at 2 spaces, so none is blind today;
- what follows a `*Prérequis*` token is free text and is never parsed: `AUCUN, but actually the
 OWNER must validate` reads as `AUCUN`. It is the author contradicting themselves, not the
 reader guessing.

 **Named residual**: a marker placed behind a **bare word** (`… 1 file *Test à trois* : …`) is a
MENTION, not a declaration — the field reads as ABSENT. That is the price of the guard that keeps
"if the *Fini quand* is a command" from being read as a field.
