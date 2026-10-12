---
name: finisseur
description: >
  Makes a distilled fiche READABLE and pleasant - good chapter titles + polished synthesis prose (P2)
  + a clean table of contents - WITHOUT EVER touching the verbatim content (P3). To be run on the fiches in
  knowledge/distilled/ after distillation, for reading quality. The judge revalidates P3 behind it.
task_class: atomic
sensitivity_max: sensible
version: "1.0"
id: finisseur
date: YYYY-MM-DD
---

# Skill: finisseur (D42 / point (4) operator / D143)

The distiller guarantees FIDELITY (P3 = the source's own words); the judge guarantees that it holds. The
finisher adds the last layer: **readability**. Chapter titles come out of the raw OCR titles of the source
(often an author's name, `Published by`, gibberish, or the `(section)` placeholder) and the table of
contents inherits them; the P2 prose can be rough. The finisher polishes all of that.

## THE CARDINAL RULE - P3 is SACRED
The finisher **NEVER** touches a chapter's `### Contenu (verbatim)` block. It modifies only the synthesis
layer (P1/P2): **chapter titles, descriptions, concepts, table of contents**. The verbatim is copied back
**word for word, byte for byte**. A fiche in which a P3 passage has moved = FAILURE (the judge will see it).

**On `make finish`, this is true by construction**: `parse_fiche` captures the verbatim block as **raw
text** and `render_fiche` **copies it back** as-is (`finisher.py:238-241,249,264`) - P3 never travels
through the model. Even when a model `retitle` is wired in, it **sees** P3 (`Chapter.contenu`,
`finisher.py:67`) but cannot write it: only the copy-back renders it.

> WARNING: **THE EXCEPTION - `make finish-emit` does NOT have this guarantee, and it is the most dangerous
> path in the repo.** It PRINTS an instruction (`finish_emit.py:72`: "Read the record at OUT,
> **rewrite it** polished at the SAME path"): **it is the agent that rewrites the fiche**, and there is
> **no `finish-apply`** - no code goes back over its output. Unlike `distill-emit`, which *creates* a
> fiche, **`finish-emit` rewrites IN PLACE a fiche that is already good**: an agent that "improves" a
> passage **destroys verbatim that was already validated**. The only safety net is `make judge`, after the
> fact, which tolerates **20 %** of non-verbatim and **restores nothing**. On this path, P3 is **your**
> responsibility: copy it back byte for byte, never touch it, and check `make judge` after your pass.
> **When in doubt, prefer `make finish`.**

**FAIL-CLOSED guard (D143 / D85).** A `## N.` heading can appear INSIDE a verbatim passage (a source line
`## 2.1 Foo`, frequent in OCR) and fool the splitting. `chapter_numbers_ok` detects it (non-sequential
numbers **or** a count != the frontmatter's `chapters:`): such a fiche is **NOT touched** - the finisher
SKIPS it, the judge FLAGS it (`malformed`). Better unfinished than verbatim truncated. For a frontier
agent: a `## N.` inside a passage STAYS in the verbatim block (it is not a chapter), copy it back as-is;
and after your pass, `make judge` must stay green (otherwise you moved verbatim or broke the splitting).

## How to invoke it
- **Deterministic pass (floor, no model, safe, fast)**:
  ```bash
  make finish
  ```
  Rebuilds the CLEARLY bad titles (placeholder / OCR gibberish) from the chapter's concepts + rebuilds the
  table of contents. Does not touch source-unusable flags. Atomic write.
  > It touches **more fiches than "broken titles"** would suggest: a fiche whose titles are **all** good is
  > still rewritten if its **concepts** are noisy (`noisy != 0`, `finish_book.py:46-48`) - `curate_concepts`
  > cleans them (`finisher.py:316`). This is intended; just be aware that `make finish` is not a no-op on a
  > fiche with good titles.
- **Then, always**: `make judge` - verifies that P3 stayed intact.

## For a FRONTIER agent (Codex / ChatGPT) - the FINE polishing
You do the real readability work, fiche by fiche. **The polish contract comes from the CODE, never from a
copy**: do not copy it out by hand (a copy drifts and lies - this is the anti-drift lesson from the
distiller, contract-single-source-emit). For EACH fiche:
1. Run:
   ```bash
   make finish-emit FICHE="knowledge/distilled/<domain>/<book>.md"
   ```
   It PRINTS, everything DERIVED from the code: the path of the fiche (rewrite IN PLACE); a **safety lock**
   (if the splitting is ambiguous - a `## N.` inside a verbatim passage - or if it is a source-unusable
   flag, it says **DO NOT TOUCH, STOP**; better unfinished than verbatim truncated); the **exact polish
   contract** (`FINISH_PROMPT`); and the **state of each chapter** (current title, `[TITLE TO REDO]` if bad,
   concepts).
2. **Apply the printed contract**: a good, short and DESCRIPTIVE title (never an author's name, `Published
   by`, `(section)`, a number); clear P2, NEUTRAL and attributed to the author ("the author shows...", you
   improve, you do not invent). **Each chapter's `### Contenu (verbatim)` block = P3 SACRED: copy it back
   byte for byte, unchanged.** Rebuild the `## Sommaire` from the new titles.
3. **Rewrite** the polished fiche at the SAME path (valid markdown, SAME number of chapters).

**After your pass, `make judge` MUST stay green** (P3 unchanged, same number of verbatim passages as
before) - otherwise you touched the verbatim, and that is a FAILURE.

## Under the hood (the body governs - D70)
- `mnemosyne.production.finish_fiche(text, retitle=None)` - parses the fiche, re-renders only title +
  description, COPIES BACK the verbatim block (P3 sacred by construction). `parse_fiche` / `render_fiche` /
  `is_bad_title`.
- Orchestration (this folder): `finish_book.py` (deterministic pass) + `make finish`. Tests:
  `tests/distillation/test_finisher.py`.
- EMITTED contract (anti-drift): the polish contract `FINISH_PROMPT` has ONE single home (the code);
  `finish_emit.py` prints it to a frontier host together with the fail-closed lock (`chapter_numbers_ok`) +
  the chapter state (target `finish-emit`). The SKILL.md does not copy it. Lock:
  `tests/distillation/test_finish_emit.py`. Principle: contract-single-source-emit.

## State (activation cycle D37)
Built + tested. P3-sacred is proven by test (finish_fiche preserves the verbatim block byte for byte).
Formal activation DRAFT -> AUDITED -> ACTIVE = a distinct auditor (D39-6) + the operator's gesture (D37).

## D36 anatomy (standard floor - six sections)

### Role
The agent becomes **the finisher**: it polishes the readability (chapter titles, P2 prose, table of
contents) of ONE already-distilled fiche, without ever touching the sacred P3 or inventing a fact.

### Method
Deterministic pass by default (`finish_fiche`: rebuilds the clearly bad titles from the concepts, rebuilds
the table of contents, pure CODE); optional fine pass by a frontier agent (JUDGEMENT, title/P2 polishing).
The exact detail lives in "How to invoke it" above.

### Inputs -> Outputs
Input: ONE fiche from `knowledge/distilled/<domain>/`. Output: the SAME fiche rewritten IN PLACE (same
path, same number of chapters) - only titles/P2/table of contents change, never the verbatim.

### When to FLAG
Ambiguous splitting (`chapter_numbers_ok` detects a `## N.` inside a verbatim passage, or a chapter count
inconsistent with the frontmatter) -> the fiche is NOT touched, it is skipped; the judge sees it next and
marks it `malformed`. Better unfinished than verbatim truncated (D143).

### Validation
The associated validator is **the judge** (`make judge`): it must stay GREEN after the finisher has run -
the same number of verbatim passages as before, otherwise the finisher touched P3, FAILURE.

### Logs
No `CoreApi` surface is wired for this skill as of today (unlike the distiller) - so no native JSONL trace
via the Guard. **Acknowledged gap** (D36 requires Logs; to be closed if `make finish` is to become a
production path rather than a CLI development tool).
