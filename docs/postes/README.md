# The POSTS — how several chats work the same plan without colliding

> **The contract, in one sentence**: a chat's `/loop` is **short and never changes**; what it must
> do lives in **its post**, written by the orchestrator, **re-read at every turn**.
>
> The requirement, as stated on 2026-08-14: the ideal of ideals is that things be done with a micro
> prompt, and that the whole of the real prompt be written by the orchestrator — the slash loop asks
> to go and check a document, and it is in that document that the instructions live.

## Why the prompt is SHORT and the instruction is DATA

A long prompt pasted into a chat is **a frozen copy**: it expires the moment the line moves, and
nobody knows it. A micro-prompt that points at a post is **an address** (D163) — *the address,
never the copy*. Three gains, and they are mechanical:

- **Reassignment costs nothing**: a chat that finishes its arc re-reads its post and finds the next
  one there. **No gesture from the operator**, no prompt to paste again.
- **The orchestrator sees everything without questioning anyone**: it reads the same files.
- **This is NOT a discussion channel between chats** — it is a **shared state with a single
  author**. Two chats talking to each other would be a second source of truth with no arbiter; here
  there is one writer and several readers.

## The EXACT micro-prompt — it lives here, not in a conversation

**A `/loop` pasted into a chat and nowhere else disappears at the first compaction.** It is
therefore carved **here**, at its only home. The operator pastes one of these three lines per chat,
**with no interval**:

```
/loop Re-read docs/postes/chat-1.md IN FULL, then apply the protocol of docs/postes/README.md.
```

```
/loop Re-read docs/postes/chat-2.md IN FULL, then apply the protocol of docs/postes/README.md.
```

```
/loop Re-read docs/postes/chat-3.md IN FULL, then apply the protocol of docs/postes/README.md.
```

**And a fourth, for the orchestrator** — it makes the operator unnecessary for follow-up, which is
the whole point. The orchestrator's own post is `chat-0-orchestrateur.md`, written into this folder
like the three others:

```
/loop Re-read docs/postes/chat-0-orchestrateur.md IN FULL, then apply its turn.
```

**The absence of an interval is the mechanism, not an oversight**: without it the harness would
re-arm on a clock that ignores what the chat is doing. With no interval, **it is the chat that
chooses its own delay** — see gesture 6 of the protocol.

## Compaction — you have nothing to ask for, but you do have something to WRITE

**A chat cannot compact itself.** `/compact` is a command **the operator** types; a `/loop` carries
only one command, and a `/loop /compact` would compact without ever working. **So you never ask for
it**: the harness compacts by itself when the context fills up.

**And here, a compaction costs almost NOTHING — that is the very purpose of this folder.** Your
useful context is not in the conversation: it is in **your post** (re-read at every turn), **your
journal** (append-only) and **the line** (`make plans`). A compacted chat re-reads the three and
picks up again. *That is exactly why the instruction is data and not a prompt.*

> **THIS CONTRACT TRAVELS WITH EVERY MANDATE, SO IT IS READ FROM PROJECT FOLDERS — and there,
> `make <target>` does not exist.** `make` has no root outside the Mnemosyne repository: `make
> plans` typed from your project returns `No rule to make target`. **The form that works from
> anywhere**:
> ```bash
> make -C ~/mnemosyne plans        # or: mnemo plans, if the shell function is set up (J4)
> ```
> Here `~/mnemosyne` is wherever you cloned this repository — substitute your own path.
> Same for every target quoted here. *A contract that prescribes a command its reader cannot type
> sends them back to doing it by hand — that is the crutch, not the tool.*

**THE ONLY THING THAT GETS LOST IS WHAT YOU HAVE NOT YET WRITTEN** — Mnemosyne's invariant 15,
*persist before compacting*. So **what your turn learned is written into your journal BEFORE the
turn ends**, never "I will note it next time".

## THE FOUR HARD RULES — they close four named failures

**1 · ONE FILE, ONE AUTHOR.**
The **orchestrator** writes the `chat-<N>.md` files (the posts) and **nothing else**.
Each **chat** writes `journal-chat-<N>.md` — **its own**, never another's, never a post.
*Without this, three chats overwrite each other — and this repository has already measured what a
shared home costs: on another project, a "one agent per barrier" delegation failed because every
barrier froze its signature in a single shared census file.*

**2 · THE POST IS RE-READ AT EVERY TURN, IN FULL.**
A post read once is not a post followed: the chat would execute a stale instruction with no signal
saying so. It is the same principle as the line's table — *there exists no path by which it can be
consulted stale.*

**3 · THE CHAT ACKNOWLEDGES RECEIPT, AND IT IS A FINGERPRINT, NOT A SENTENCE.**
At every turn, the chat writes into its journal the `sha256` (12 chars) of the post it is executing.
The orchestrator compares. *An order whose receipt is never verified is an order you only believe
you gave* — and a "got it" sentence can be satisfied without having read anything.

```bash
shasum -a 256 docs/postes/chat-2.md | cut -c1-12
```

**4 · YOU WORK ONLY ON YOUR OWN BATCH — AND WHAT IS NAMED NOWHERE IS TAKEN AND DECLARED.**
The post names the chat's files **and the ones it must not touch**. Batches are **derived** (no
write collision), never chosen. A file **in another chat's `pas_a_moi`** is never taken: the chat
writes it as `ARBITRAGE:` in its journal, works around it, and carries on.

**A FILE ONLY CHANGES HANDS THROUGH A WRITTEN TRANSFER — never because it looks free.**
Formulated by the session working outside the posts on 2026-08-15, and the contract did not say it:

> *"A closed ITEM does not release an assigned FILE — and a clean `git status` is an INTERVAL, not a
> release."*

That session needed a line in `stop.sh`; `I4(b)` was closed, the file was clean, nobody was touching
it. **It asked instead of taking**, and it was right: *the absence of a conflict at instant `t` is
not a permission* — it is the same class as `OBS-17` (presence is not freshness) and as `OBS-25` (a
closure glyph is a photograph, not a state).
**The transfer is a gesture of the orchestrator, written into BOTH posts**: removed from one, given
to the other, with the date. Without that, two actors can believe in good faith that a file is
theirs — and **no `git status` will reveal it before the collision**.

**`pas_a_moi` FORBIDS WRITING, NEVER READING** — and this is not a detail (`OBS-28`). Chat 3
refrained from covering a piece of wiring *"because a parallel session is editing that file"*, and
**the orchestrator approved**: both times, the reason was **too broad**. *An abstention is justified
by a REAL collision, never by proximity.* **You may READ anything**, including what another is
rewriting — you may not **write** to it. Measured: by insisting, it found that its witness **did not
bite**; the abstention would have closed the item on a dead witness.

**But an enumeration does not cover what did not exist when it was written** (measured:
`docs/FORMAT_PLAN.md` taken by chat 1 rightly, a new directory created under `knowledge/` with no
status — `OBS-12`, and it is the same class as `OBS-7` on `.gitignore`). **The default is therefore
explicit: a file that is in NO batch and in NO `pas_a_moi` is TAKEN, and DECLARED by an `ARBITRAGE:`
line.** *Asking would recreate the bottleneck this whole arrangement exists to remove; you decide,
you write it down, it is contestable afterwards.*

## FORBIDDEN WHILE SEVERAL CHATS ARE WORKING: `make fmt`

**`make fmt` runs `ruff format .` — over the WHOLE repository.** Measured on 2026-08-14: **127
files, +2045/−760**, and the count was still growing on the next turn.

**It is nobody's fault — it is a design trap**: a chat that sees `make lint` red tries to repair it,
and `fmt` is the line **just below** it in the `Makefile`. The gesture is natural; its blast radius
is not.

**What it costs, and none of this is data loss**:
- the other chats' diffs are **drowned** in 127 files of noise — *a `git diff` that returns 127 files
  does not get re-read, so nobody checks what they are committing any more*;
- several of this repository's barriers **freeze fingerprints**: a reformat changes the bytes without
  changing the meaning, and the temptation to "fix the freeze" **disarms the gate**.

**The rule, as long as more than one chat is working**: format **your own file**, never the
repository — `uv run ruff format <your_file.py>`. **And if `make fmt` has already run**: do not undo
it either (you would crush other people's work). **Write it as `ARBITRAGE:`** — it is a mass gesture,
and **the ORCHESTRATOR settles it**: it is the only one who can see whether all three chats are idle.

**This line used to say "it belongs to the operator". That was FALSE, and corrected on 2026-08-15**
(`OBS-30`). The operator's gestures are **exhaustively three**: **MONEY** · **`system/config/`** ·
**deleting their data**. `make fmt` is none of them. *A gesture falsely attributed to the operator
never happens — it does not fail, it WAITS, and nobody knows it is waiting.* This fault held **16
items** of the plan behind a pre-commit hook nobody was arming.
**Before writing "that's the operator's" anywhere, the question is closed**: is it money,
`system/config/`, or deleting their data? **No → it is yours or the orchestrator's.**

## Committing in parallel — what actually happens

The chats **commit by green fragment**, on `main`, each their own files. **That is how they see each
other**: without continuous commits, three chats work blind.

**Two simultaneous commits corrupt nothing**: git places an `index.lock` and the second one **fails
cleanly**. The gesture is therefore to **wait a few seconds and retry**, never to force, never to
delete a `.lock`. And the `pre-commit` hook runs every time: a commit takes a while, that is normal,
it is not a blockage.

## THE PROTOCOL OF A TURN — this is what the `/loop` applies, and it does not recopy it

The `/loop` is **two lines** and **never** changes. Everything that follows lives here, so it
improves here, for all the chats at once — *a contract has a single home, otherwise the copies
drift.*

1. **RE-READ your post IN FULL**, before anything else. It may have changed since the previous turn.
2. **ACKNOWLEDGE RECEIPT**: open a new entry in your journal with the post's fingerprint
   (`shasum -a 256 docs/postes/chat-<N>.md | cut -c1-12`). **Append-only.**
3. **DO** what the post says — **one step at a time**, in the order it gives. The item's
   `*Fini quand*` condition **settles it**; your word does not.
3 bis. **A VERDICT IN FLIGHT DOES NOT BLOCK YOUR TURN.** You are right not to mark an item closed on
   your own word (D75) — but a step *awaiting audit* is not a step *in progress*. **You take the next
   one in your post and you carry on.** Waiting for an auditor with your arms folded is exactly the
   parallelism we are trying to gain, reduced to zero.
   *Measured on 2026-08-14: the three chats finished their production in 30 minutes and all three
   ended up waiting for a verdict, on posts that gave them nothing else to do.* If your post provides
   for nothing, **write it as `ARBITRAGE:` and take the next item of your arc** — it is your
   recommendation, contestable afterwards, not blocking beforehand.
   **THIS STAYS, measured alive (`H5`, 2026-08-16), not a bandage to be removed**: this gesture was
   **exercised that very night** by a chat pivoting onto `H3`/`BR4` while their audits were in
   flight. `B1` will one day give it a formal 4th state (*awaiting verdict*) — but as long as the
   line exists only in this protocol, removing it would delete a rule in real use.

4. **COMMIT by green fragment** — selectively, never `git add -A`, message in **ASCII without
   accents**, ending with the `Co-Authored-By` of the model that actually produced it. `index.lock`
   refuses? **Wait and retry** — never force, never delete a `.lock`.
5. **WRITE** `done / in-progress / blocked` in **YOUR** journal — **then commit it**, same rule as
   gesture 4. *A journal outside git is read by nobody: the channel between chats IS the repository.*
   **REQUIREMENT, 23:10: we commit WHEN WE FINISH A THING, not when we finish the turn.** A file
   written and not committed is invisible to the other chats **and** to the orchestrator, who works
   from `git`. *What is not committed does not exist for the others.*
   **And if you hit a snag in the MECHANISM itself** — an instruction in the post that does not work,
   a pointless wait, a collision, a rule that slows you down without buying anything — add an
   **`OBS:`** line. We are in an **experimental phase**: the mechanism is tested by the use we make
   of it, and the orchestrator carries those lines up into `OBSERVATIONS.md`, the observations
   register it maintains in this folder. *A friction seen and not written down never happened.*
6. **RE-ARM — and the delay starts FROM THE END OF YOUR TURN, never during it.**
   The `/loop` is launched **WITHOUT an interval**: it is **you** who call your own wake-up
   (`ScheduleWakeup`) at the moment you hand back. It therefore **structurally cannot** fire while
   you are working. Two delays, and the choice is **derived from your situation**, not decided:

   | your situation when you hand back | delay | why |
   |---|---|---|
   | **truly finished** — without a wake-up, nothing would move again | **120 s** | *when it is finished, it is finished* |
   | **a sub-agent is still running** in the background | **1200 s, and it is a NET** | **the harness re-invokes you ALL BY ITSELF** when it ends — polling at 120 s would only burn turns for nothing. The long wake-up only serves if the sub-agent hangs |

   **`stop: true`** — only when your post says `etapes: RIEN`.

**YOU STOP ONLY when your post says `etapes: RIEN`.** Nothing else stops the loop: a red carried by
an item is normal work.
**Faced with an arbitration**: you take your recommendation, you **WRITE** what you decided and why,
and you carry on. *Contestable afterwards rather than blocking beforehand.*
**THREE WALLS** that "do not stop" does not lift: **MONEY** · **`system/config/`** · **deleting the
operator's data**. A gesture that belongs to them alone **ACCUMULATES** in your journal, you work
around it, you take the next step.
**THE AUDIT GOES TO AN ISOLATED THIRD PARTY** (D75), never to you. *Following your recommendations is
not believing yourself* — measured: in a single day, half of an agent's conclusions were corrected by
a third party.

## Why THREE chats are possible here when item `E5` says "one first"

`E5` speaks of a first batch **on a large external project**, and its caution is measured: **8
isolated executors → 8 stops**, because **90 %** of that project's items have **no executable
command** and **21 %** name only a folder.

**The 44 items of THIS plan do not have that defect**: they were written with `*Produit*`,
`*Fini quand*` (a command), `*Dépend de*`, `*Prérequis*` and `*À lire*` — that is, **to the standard
that `C1` and `C2` will make mandatory**. **Three chats on our own plan are therefore legitimate —
and it is the format's first real trial.** *If our items are not self-sufficient, we will learn it in
three hours instead of discovering it on the large external plan.*

## The shape of a post

```markdown
# POSTE — chat <N>
emis_le: 2026-08-14
arcs: <letter(s)> — <title>
etapes: <ID> → <ID> → <ID>            (in this order; "RIEN" if the chat must stop)
mon_lot: <the paths this chat writes>
pas_a_moi: <the paths it must not touch under any pretext>
quand_j_ai_fini: <what it writes in its journal, and what it re-reads>
```

**`etapes:` is WRITTEN BY HAND by the orchestrator, and that is a measured bandage, not an oversight
(`H5`, 2026-08-16).** `B2` (`plan_ordre.ordonner()`) **exists and is proven**: a chat's next step is
**derivable** from the graph, it no longer needs to be **listed**. But nothing has **switched over**
to it yet — every post read that night, without exception, was rewritten by hand. **Built, not
wired**: the manual list therefore remains the real practice until that switch is made, and this line
says so rather than letting the shape above lie by silence.

## The shape of a journal (written by the chat, APPEND-ONLY)

```markdown
## <timestamp> — post <12-char fingerprint>
fait: <what passed, with the command that settled it>
en cours: <the step and its remaining clause>
bloqué: <what is missing, and WHOSE it is — or RIEN>
```

**Append-only.** A wrong entry is corrected by **one more** entry, never by an edit — the same
discipline as the Advisor's notebook and the Guard's journal.

## WHO CLOSES AN ITEM — the question nobody was asking, and it cost 17 to 1

**Measured on 2026-08-14, 90 minutes after the first shot: 17 commits announcing an item, ONE box
checked.** This is not negligence, it is a **design hole** — and it is the mechanical cause of the
drift measured on another project (*41 commits, 0/52 closed*), found here in one evening.

Chat 3, in its journal: *"They stay unchecked: it is for the orchestrator to close them, not for me —
nobody closes on their producer's word, and two turns have shown what my word is worth here."*
**It was right, and nobody had been designated.**

**SETTLED, and it is a rule of the contract from now on:**

| who | may they check the box? | why |
|---|---|---|
| **the producer** (the chat that wrote the code) | **never** | D75 — *nobody closes on their own word* |
| **the isolated auditor** | **never** | it returns a **verdict**, it does not decide the plan's state |
| **the orchestrator** | **yes, and it is THEIR gesture** | they produced no item — which is exactly what authorises them |

**And they check on TWO proofs, never on a declaration**: the item's `*Fini quand*` condition
**pulled** (the command, not the journal's prose) **and** the verdict of an isolated audit, returned.

**THEY CLOSE BY PULLING, NEVER BY WAITING — and this is a correction that was paid for.** Measured on
2026-08-14: `F3` stayed open although its producer had returned its verdict **clause by clause, with
the command for each**, and its 81 witnesses were passing. **The item was not waiting for work: it
was waiting for the orchestrator to READ.** It was raised from outside that the rule saying things
can only be closed by the orchestrator looks odd.
**The rule was not at fault, its implementation was.** *Pulling a condition costs a minute; waiting
for a report costs an item.* **If the condition is pullable, we pull it — right away, and we close.**
*A box checked on a journal that says "it's done" is worth no more than a producer closing on
themselves — it merely moves the signature.*

**Batch consequence**: inside `docs/plan/**`, **the content of an item belongs to the chat working
it, the BOX belongs to the orchestrator.** It is the only shared zone of the arrangement; it holds
because it is *one line*, and because only one of the two touches it at a time.

**THIS MANUAL CLOSURE IS NOT (YET) REPLACEABLE — measured, not supposed (`H5`, 2026-08-16).** `H5`'s
table designated it as replaced by "a gate" (`A1`/`H4`); the measurement says the opposite. `A1`
closes on the READING of the six fields, never on their truth; `H4` guards one precise instant (the
promotion of a plan), never each ordinary closure. **No mechanism in this repository today refuses a
closure glyph placed without proof, on an ordinary day.** The table designated the wrong
replacement — it is not my gesture to settle that alone (`H5` says so: the arbitration belongs to
whoever writes the clause), so this section remains the REAL practice, not a bandage on borrowed
time.

## We are in an EXPERIMENTAL PHASE — and that is an instruction, not an excuse

The requirement, 2026-08-14: we test what we are building by building what we are testing, and this
must be added as a continuous, imposed measure.

This folder is not a proven contract: it is **its first shot**. So every friction met while using it
is worth as much as the work itself — *a directive that does not work, a chat we do not know how to
supervise, an interposed discussion that costs more than it returns.*

**They go into `OBSERVATIONS.md`**, the register the orchestrator keeps in this folder: the chats
flag them with an `OBS:` line in their journal, the orchestrator carries them up, and **each one
carries its outcome or admits it has none**. Nothing there becomes a commitment until it is written
into an arc.

## What this folder is NOT

- **Not a plan.** The state is authoritative in the plan document at the root of `docs/` and is
  pulled with `make plans`. A post says **who does what right now**; it never replaces an item.
- **Not a messaging system.** No chat writes to another chat. The channel is the repository.
- **Not a progress trace.** Progress lives on the items (the closure glyph), not in a journal.
