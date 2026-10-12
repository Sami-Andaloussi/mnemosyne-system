# Anti-drift - why a prompt is NEVER hand-copied

The central lesson of the whole distillateur -> finisseur -> juge arc, engraved here so that a future
skill does not rediscover it the hard way a fourth time.

## What happened (the fact, not the theory)

The distillateur's first `SKILL.md` described the distillation prompt in PROSE, hand-copied from
`build_prompt` (the code). That copy DRIFTED from the code without anyone noticing:
it got abridged, and a key instruction of the real prompt - « never drop or alter a
verbatim passage below because of it » - disappeared from the copy. The LOCAL model kept
running correctly (it always reads the REAL `build_prompt`, never the copy). But the first
run handed to a FRONTIER agent (which, for its part, READS the SKILL.md to know what to do) produced
empty templates where the local model produced a real distillation - because the frontier agent
was faithfully following a copy that had itself lost the instruction that mattered.

The bug was in NEITHER of the two models. It was in the gap between two versions of the same text
that a human (or an agent) had let widen by hand-copying.

## The remedy is STRUCTURAL, not disciplinary

"Take care to keep the copy in sync" is not enough - that is exactly what failed.
The remedy: the prompt (or any contract a model must follow) has ONE SINGLE home, the CODE
(`FINISH_PROMPT`, `_PROMPT_TEMPLATE`, `DISTILL_SCHEMA`, here `SKILL_ANATOMY_TEMPLATE`), and is
WRITTEN NOWHERE ELSE. An `-emit` seam (`emit_prompts.py`, `finish_emit.py`,
`skill_emit.py`) REPLAYS the real functions of the code and PRINTS the contract to a frontier host -
byte for byte, never a transcription. The SKILL.md describes the contract (so that a reader
understands the intent), it never RESTATES it word for word.

This is the [[contract-single-source-emit]] principle: a multi-host contract lives in ONE code home
and is EMITTED to each host; never hand-copied.

## How `make skill-audit` makes this VERIFIABLE, not just a pious wish

`audit_skill(...)` scans, in the production code, every constant named `*_PROMPT`,
`*_TEMPLATE` or `*_SCHEMA` (via `ast`, on the REAL VALUE of the string - not its escaped source
form), then looks for whether a sliding window of 60 contiguous characters of that constant
appears LITERALLY in the candidate's SKILL.md. The window's step is 1: every verbatim sequence
of 60 characters is therefore caught (the guaranteed floor EQUALS the documented window - a
larger step would silently raise the real floor). A copy is almost never
byte-identical for long (the next edit of the code desynchronizes it silently), so
the audit does not demand total equality - a 60-character extract that matches is already
sufficient proof that a hand pasted source text rather than EMITTING it.

This lint is not cosmetic: it is the SAME rule that, applied to the distillateur in a retro-audit
(`241e525`), confirmed that the old SKILL.md was missing precisely the lost P3 instruction.

## Dogfood: this skill applies the rule to itself

`SKILL_ANATOMY_TEMPLATE` (in `skills.py`) ends with `_TEMPLATE`: `audit_skill` therefore scans it
EXACTLY as it scans `FINISH_PROMPT`. This skill-creator's `SKILL.md` describes
the anatomy and the 6 lessons in its OWN words (not pasted extracts) - precisely so that
`make skill-audit DIR=system/skills/skill-creator` passes the anti-drift axis with no special exception.
If one day this SKILL.md starts pasting a long extract of `SKILL_ANATOMY_TEMPLATE`, the audit must
detect it - on itself, as on any other skill.
