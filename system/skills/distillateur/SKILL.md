---
name: distillateur
description: >
  Distils ONE document (book, article, transcript) into its 3-part distilled fiche -
  identity (P1), NEUTRAL attributed description (P2), VERBATIM content (P3) - and writes it to its
  MIRROR place in knowledge/distilled/. To be used to fill knowledge/distilled/ from a .md in
  knowledge/raw/. EVERY agent (local or frontier) invokes THIS skill: there is no bespoke prompt
  to rewrite, you launch the skill, and that is all.
task_class: atomic
sensitivity_max: sensible
version: "1.0"
id: distillateur
date: YYYY-MM-DD
---

# Skill : distillateur (D39-4 / D28 / D143)

Produces the **distilled understanding** of a document - brick (3) of the incarnation (`PLAN_INCARNATION.md`),
the first operational skill behind `SEED_SKILLS['distillateur']`. It is **THE** single path: the local agent, a
frontier agent (Codex / ChatGPT given access to the repo), and the tests all call **the same skill**. The logic is
**never** rewritten in prose; the behaviour lives here, each host is only a thin adapter that
points at it (ponytail principle, `knowledge/raw/Software/Tooling/agents/books/ponytail.md`).

## When to use it
- Fill `knowledge/distilled/` from a `.md` in `knowledge/raw/`.
- One document at a time - the skill splits a book into chapters by itself.

## How to invoke it - the default path
```bash
make distill BOOK="knowledge/raw/<domain>/<Title -- Author>.md"
# long book to cap for a trial: make distill BOOK="..." CHUNKS=8
```
The skill: splits the book into sections (at chapter boundaries), distils each section through the
**governed stack** (Guard + runner + verbatim barrier), assembles **ONE** chaptered fiche, and writes it to its
**mirror place** in `knowledge/distilled/`.

### The 4 routes - they are NOT equivalent (read the "where your books' text goes" column)
| route | who distils | verbatim floor in CODE? | where your books' text goes |
|---|---|---|---|
| `make distill` | **LOCAL** model (MLX) | [done] `distillation.py:546` | **nowhere** - stays on the machine |
| `make distill-apply` | **Haiku** agents (via `distill-emit-split`) | [done] `distill_apply.py:71` | at the agent's host (Claude Code) |
| `make distill-emit` | the frontier agent, **which writes the fiche itself** | [failed] **NONE** - see the GUARANTEES section | at the agent's host |
| `make distill-batch` | **Claude Haiku via the API**, in parallel | [done] (same body as `distill`) | **`api.anthropic.com`** - a third-party cloud |

**`make distill-batch` is the only route that TAKES your books' text out of the local machine by an automatism**
(`runner_anthropic.py` -> `api.anthropic.com`). It is guarded: API key required, **allow-listed** host
mandatory (otherwise it **refuses**, exit 2), public-by-provenance (D144), perso families **excluded by
default**, idempotent. Dry run without sending anything: `make distill-batch DRY=1`.
> WARNING: **Publicness = PROVENANCE, ASSUMED - not verified.** The gate trusts the folder tree: a
> **misfiled non-public** file under a `books/` folder **would leave anyway**. This is the acknowledged residue of
> D144 (the `distill_campaign.py` docstring says so too) - the barrier is the filing, not a
> content inspection.

> WARNING: Give the **`.md`** (Mnemosyne's source of truth), **never the PDF**: the P3 verbatim is validated
> character-by-character against THAT `.md`. Any other source text => everything drops.

## What it GUARANTEES - by construction, not by trust (D100)
- **Source-quality gate (D85)**: BEFORE distilling, the raw is assessed (`assess_source_quality`). A
  rotten source - broken extraction, maths / tables / code (too few letters or too little continuous prose, too
  many digits, **or fewer than 5,000 characters** - `_MIN_SOURCE_CHARS`, the case of a source reduced to its cover
  page; thresholds documented by the policy) - is **FLAGGED + SKIPPED**, never distilled into mush.
  The verbatim floor guarantees "faithful to the source"; this gate guarantees "the source is worth the trouble"
  (a verbatim of mush passes the floor, but not the gate). Marker `<!-- mnemosyne:source-unusable -->`
  -> routing to re-extraction (OCR campaign).
- **P3 = VERBATIM - on 3 routes out of 4.** Every passage is a **literal** extract of the source;
  `keep_verbatim` drops everything else. A model that paraphrases -> passage rejected at the source. This is the
  anti-mediocrity barrier (D143). **Where the CODE actually enforces it**: `make distill` local and
  `make distill-batch` (`distillation.py:546`), `make distill-apply` (`distill_apply.py:71`).
  **WARNING: THE EXCEPTION, to know before choosing your route: `make distill-emit` does NOT have this floor.** That
  route PRINTS a contract; it is the agent that assembles and **writes the fiche itself**, and **no code
  passes its output back through `keep_verbatim`**. The only AUTOMATIC net there is `make judge`, **after the fact**:
  it blesses `ok`
  up to **20% non-verbatim** (`_MIN_VERBATIM_YIELD = 0.8`) and **never removes anything**. An agent's
  report may overstate how verbatim its outputs are; on `distill-emit`, those outputs enter
  without this filter. **Prefer `distill-apply`** (same
  speed, floor in code); `distill-emit` = for a host that cannot return JSON per section.
  **The MANUAL gate does exist**: `make verbatim-check FICHE="..."` replays the floor on your single
  fiche, print-only, and names the discarded passages. It is not automatic - you are the one who walks through it
  (step 5 of the recipe) - but it makes the floor **reachable** at the moment you write, instead
  of after the fact and drowned in a batch of documents.
- **P2 = neutral and attributed**: "the author argues...", never the book's marketing as a fact.
- **Robustness net (D85), per section**: (1) the decoder **repairs** a near-miss JSON and **re-validates**;
  (2) otherwise auto **sub-chunk** (cut in two, distil, merge); (3) otherwise **visible flag** + machine
  marker `<!-- mnemosyne:distill-failed chunk=N -->`. **Never lost silently** (the raw remains the source).
- **Mirror**: the fiche lands at the raw's path with `raw/` -> `distilled/` (same tree + same name).
- **Atomic write**: an interrupted re-run does **not** destroy the previous fiche.

## For a FRONTIER agent (Codex / ChatGPT with repo access) - YOU ARE THE MODEL
Here, a skill = **the real distillation prompt executed IN A LOOP** over the book's sections: the SAME
work as the local model, section by section. You are not "filling in a template" and you do NOT write a script
that plugs holes. A fiche where every chapter repeats `(section)` / "the author presents the elements
associated with..." / concepts `section, source, analyse` / "no verbatim passage" is a **TOTAL FAILURE**: it
proves you have neither READ nor DISTILLED the content. You really READ and DISTIL each section.

**The contract comes from the CODE, never from a copy.** NEVER recopy the prompt by hand: a copy DRIFTS from the
code (it abridges itself, loses an instruction, and lies) - this is precisely what made the first
frontier pass fail where the local model worked. You receive the contract EMITTED from the code, byte for byte.

**The loop, for EACH book:**
1. Run:
   ```bash
   make distill-emit BOOK="knowledge/raw/<domain>/<Title -- Author>.md"
   ```
   It PRINTS, everything DERIVED from the code (single source of truth, no brick required): the output
   **mirror path**; the **verdict of the source-quality gate** (if NOT-OK: the exact flag-fiche to write, then STOP,
   no distillation); the **JSON schema**; the **exact frontmatter** (with the right `chapters: N`); and **ONE
   exact prompt per section** (identical, byte for byte, to the one the local model receives).
2. For EACH `### PROMPT SECTION N/M` block, **you ARE the model**: produce the JSON conforming to the printed schema.
   The `passages` = **LITERAL** contiguous citations from the section. description + concepts speak about the
   REAL CONTENT of the section, never a generic template.
   > WARNING: **On THIS route, nothing catches you.** Unlike `distill-apply`, no code passes your
   > output back through `keep_verbatim`: you write the fiche yourself. A paraphrase you let through **enters
   > the base and stays there** (`make judge` will only see it after the fact, and only beyond 20%). The
   > floor is **your** responsibility here, not the repo's. Copy-paste, do not reformulate.
   > **You can still submit yourself to it**, once the fiche is written (step 5):
   > `make verbatim-check FICHE="<your fiche>"` - print-only, ONE fiche, and it **NAMES the
   > passages the floor discards**. An `ok` fiche appears neither on screen nor in the report.
3. **Assemble** ONE chaptered fiche by recopying the **`ASSEMBLY SKELETON`** block that the emission
   prints just after the frontmatter. **This block is not an example: it is the format**, rendered by
   `_section_md` / `_toc_block` - the very functions with which `make distill` and `make distill-apply`
   write real fiches. **This SKILL therefore carries NO copy of it**, and that is deliberate: the assembly
   format was the only thing the contract deferred to prose, on the exact surface where this
   skill warns that a copy drifts (defect G4, differential trial of YYYY-MM-DD).
   > **The WHY, however, is not emitted**: the sentinels **self-delimit** the verbatim, so that a line
   > `## N.` quoted from the source (frequent in OCR) is no longer taken for a chapter title by the judge /
   > the finisher. Change NOTHING in the text quoted between them (P3 is sacred, verified by `keep_verbatim`). And the
   > trap that cost dearly: **without the blank line** before/after, a passage stuck to a sentinel is
   > **swallowed** (count short -> fiche flagged). Recopying the skeleton avoids it; retyping it from memory,
   > does not.
4. **Write** the fiche at the printed mirror path (REAL newlines, never escaped `\n`).
5. **Submit it to the floor**, on itself alone and without writing anything:
   ```bash
   make verbatim-check FICHE="knowledge/distilled/<dom>/<book>.md"   # the raw is DEDUCED from the mirror
   ```
   `VERDICT: PASSE` (code 0) = it may enter. **Any other code = it must not** (`make` returns 2 for
   any refusal: read the `VERDICT:` line to distinguish a rejection from a refusal of use). The discarded passages are
   named in clear text: those are the ones to re-copy from the source, not to reformulate.

Then **`make judge` MUST be green** - the verdict on the whole shelf writes a report and names no
`ok` fiche: it is the batch, not your fiche. Placeholders, paraphrase of P3, or
a fiche on a rotten source = FAILURE.

## PARALLEL AGENTS route

**When**: a batch of books to distil without waiting. Parallel agents can process the
independent sections, while the code keeps the assembly and the checks.

**What differs from the route above, and that is ALL**: **the agent assembles NOTHING**. The CODE chunks
(`chunk_book`), applies the verbatim floor (`keep_verbatim`), REQUIRES completeness and assembles the fiche.
The agent only **fills in one JSON per section** - its strength. An agent that *drives* botches the job and declares
itself falsely complete; under a code barrier, it no longer can. **The barrier is the code, never the agent's
zeal** (D100).

### The recipe (replayable as-is)

```bash
make distill-emit-split BOOK="knowledge/raw/<dom>/<book>.md" OUT="<emission_dir>"   # 1. emits + prints the PLAN
# 2. dispatch N HAIKU agents (~5 sections each) - short prompt pointing at AGENT_BRIEF.md (the plan says so)
make distill-apply BOOK="knowledge/raw/<dom>/<book>.md" SECTIONS="<json_dir>"       # 3. the CODE sews it back
make judge                                                                          # 4. independent verdict
```

# Deployment-specific measurement omitted; the behavior is covered by tests.

1. **FINE sections - NEVER pass `HAIKU=1` to the chunking.** Counter-intuitive: the "Haiku-size" profile
   (60k) yields a **THIN** fiche, because each section returns ~the same amount of notes - fewer sections =
   less fiche. The same book: 13 large sections -> **40 KB**; 29 fine sections -> **86 KB**. Haiku's
   200k context is there to give it **more sections**, not larger sections.
2. **<= 5 sections per agent (`SECTIONS_PER_AGENT`); it is the NUMBER of agents that adapts to the book.** An
   agent sends back all its accumulated context at every tool call: loading it costs far more than adding
   agents, and it botches the end of a long list. **Do not compute the slices by hand** - `distill-emit-split`
   prints the plan (`agent_slices` balances the remainder: 36 sections -> 8 agents of 5,5,5,5,4,4,4,4, never
   a 1-section crumb-slice).
3. **NEVER believe an agent's report.** They all declare "10 exact verbatim passages, no
   paraphrase"; the floor **discards 25-45% of them**. Without it, that many false citations would have entered the base.
   Only the measurement counts (`keep_verbatim`, `make judge`) - cf. [[agent-vs-backend-faithful-production]].

**Known trap, parried in code**: an LLM does not know how to escape JSON when it quotes - either it forgets to escape
the book's quotation marks, or (once warned) it OVER-escapes the one that CLOSES the string. Both seen for real (~3
sections/66). `distill_apply._REPAIRS` repairs in cascade, the 1st that parses wins, **only after failure of the
strict parse** (a valid JSON is never rewritten); an irreparable file is **NAMED**, never skipped.
**What the repair guarantees - and what it does not** (Opus audit, measured): it CANNOT
let a false citation in (`keep_verbatim` re-tests **after** the repair -> a damaged passage is
*discarded*, never invented - that one is structural; the fuzz of YYYY-MM-DD, 20,000 adversarial trials / 0
non-literal admitted, **confirmed** it, but no test locks that run: it is a measurement, not a
proof), and it CANNOT silently truncate
`description`/`summary` (a repair that cuts a scalar would have to fabricate a key to parse -> the check
of the schema's 6 keys refuses it). **Acknowledged residue**: it can split a TABLE item (one `concept` that
becomes two) without anything catching it - a cosmetic degradation of the agent's synthesis, never of P3.

**Reference (6 macro books, YYYY-MM-DD)** - fiches **86 / 142 / 131 / 161 / 203 / 282 KB** for
29/30/36/51/59/86 sections, **judge `ok` on all 6** (local GLM benchmark: 56-147 KB). Verbatim kept ~72% with
the current brief (54% without). *(That run was dispatched by hand into 6/6/7/10/12/17 agents with slices
up to 6; `distill-emit-split` now computes the plan - follow it, do not retype it.)*

**Immutable rule (operator)**: **HAIKU only, never Sonnet.** And a book from a **perso** family
(`General/Misc`, health/intimacy) NEVER goes to a frontier agent - that one stays local.

> WARNING: **This "NEVER" is an operator rule, NOT a code incapacity - say it honestly.** On
> `distill-batch`, perso families are excluded **by default** (`_EXCLUDED_FAMILIES`), but
> **`make distill-batch PERSO=1` (-> `--include-personal`) LIFTS exactly this exclusion** and would send
> `General/Misc` to `api.anthropic.com`. The flag exists and it works. **Never type it**: what
> holds here is the hand on the keyboard, not a barrier. On the agent routes (`distill-emit*`), there is
> not even an exclusion: it is the choice of the book you pass.

## Under the hood (the governed body - D70, in the lib)
- Atomic body: `mnemosyne.production.distillation.Distillateur` (Skill[I, O], D108) + `keep_verbatim`
  (the verbatim floor, D143) - the governed decoder repairs the near-miss JSON (`close_json`, safe thanks to the
  floor).
- Activation surface: `CoreApi.distill` (behind the Guard, D89).
- Book orchestration (this folder): `distill_book.py` - chunk -> distil each section -> net -> mirror ->
  write. Invocation = the `distill` target of the `Makefile`.
- EMITTED contract (anti-drift): `emit_prompts.py` replays the real `build_prompt` + `chunk_book` + the source gate
  to print to a frontier host the SAME contract, byte for byte (target `distill-emit`). The prompt
  (`build_prompt`) and the schema (`DISTILL_SCHEMA`) have ONE single home: the code. Lock:
  `tests/distillation/test_emit_prompts.py`.
- Cloud campaign: `distill_campaign.py` (+ `runtime/runner_anthropic.py`) - target `distill-batch`.
  Locks: `tests/orchestration/test_distill_campaign.py`, `tests/orchestration/test_runner_anthropic.py`.
- Assembly of the agents route: `distill_apply.py` - target `distill-apply`. Lock:
  `tests/distillation/test_distill_apply.py`.
- Fiche format: D28 (3 parts). Tests: `tests/distillation/test_distill_book.py` (the same path as
  production).

## State (D37 activation cycle)
Seed skill `SEED_SKILLS['distillateur']`. Body + net + mirror: **built, tested, audited** (Opus GO)
and **quality validated by operator on Carver** (D37 gesture). The formal activation DRAFT -> AUDITED -> ACTIVE
(`SkillGenerator`, `skills.py`) requires a **distinct** auditor (D39-6) + the **operator's gesture** (D37) - a skill
never runs on trust alone.

## D36 anatomy (normed floor - six sections)

### Role
The agent becomes **the distiller**: it turns ONE already-normalised document
(`knowledge/raw/`) into its 3-part distilled fiche, without ever speaking in its own name nor
inventing a fact the source does not carry (D25).

### Method
Chunking into sections at chapter boundaries (CODE, deterministic) then distillation of
each section through the governed stack (JUDGMENT, local or frontier agent), then assembly of ONE
chaptered fiche (CODE). The exact detail lives in "How to invoke it" and "Under the hood"
above - this section only names the three steps, never rewrites them elsewhere.

### Inputs -> Outputs
Input: ONE `.md` from `knowledge/raw/<domain>/` (never the source PDF). Output: its mirror fiche
in `knowledge/distilled/<domain>/` (same tree, same name), or a `source-unusable`
flag-fiche if the source-quality gate refuses the source.

### When to FLAG
Rotten source (source-quality gate NOT-OK) -> flag-fiche, distillation skipped, never forced.
A section that fails even after the net (decoder + sub-chunk) -> machine marker
`<!-- mnemosyne:distill-failed -->`, visible, never lost silently (D85).

### Validation
The associated validator is **the judge** (`make judge`, `system/skills/juge/SKILL.md`): it replays
`keep_verbatim` + `assess_source_quality` on the produced fiche. PASS = P3 faithful (literal
verbatim) AND covered (enough chapters); neither the P2 prose nor the fine chunking is its concern.

### Logs
Via `CoreApi.distill` (the Guard, D89), the call is a `MODEL_CALL` traced by the runtime's
observability layer (D6 / D82). The direct CLI entry `make distill` does not log by
itself today - **acknowledged gap** (D36 requires Logs; to be closed if this CLI path must
remain the production route, not just development).
