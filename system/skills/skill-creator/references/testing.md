# Testing a skill - the production path, under real conditions

A skill is never proven by re-reading it, nor by the author replaying their own demo. It is proven by
watching an agent who does not know the answer follow the REAL invocation path.

## The recipe

1. **A FRESH, UNBIASED agent.** A new thread (or an independent sub-agent) that did NOT take part in
   building the skill - it must know nothing of the expected answer, otherwise the test measures its
   memory, not the skill.
2. **The skill's natural `make` entry point.** Never a script called by hand, never a shortcut the author
   knows but the SKILL.md does not document - if the skill only works through an undocumented path, it does
   not work.
3. **Access to the repo, without being handed the answer.** It reads the SKILL.md the way any future agent
   will read it, discovers `make <name>-emit` if it needs to, and applies the printed contract.
4. **A REAL task, not a toy.** The same level of demand as the operator's quality validation on *Carver*
   for the distiller, or the GUARD-SAFE Opus audits of the agent loop: a real document / a real need, not
   an example built to succeed.

## What this catches that re-reading misses

The Opus audit that followed the distiller's first frontier run found, under real conditions (not by
re-reading the code), that the agent was SCRIPTING a template on a large generative task - every
`(section)` chapter, every description "here the author deals with..." - where a re-reading of the SKILL.md
would have seen nothing wrong: the contract was well written, the agent just... did not follow it all the
way through 6600 chapters. That is why lesson 6 exists: testing under real conditions is necessary, but
insufficient on its own - acceptance must ALSO be a verification IN CODE (see `audit_skill.py`, the
`scaffold_only` axis), never a mere reading impression ("it looks well produced").

## Applied to skill-creator itself

For this skill specifically: a fresh agent receives an instruction of the form "use the skill-creator to
build a skill that does X" (never "here is skill-creator, check that it works") - and it must, without
being shown this page, reach `make skill-emit`, `make skill-new`, fill in the DRAFT, then get `make
skill-audit DIR=...` green on its own. If a step has to be whispered to it, the SKILL.md or the `-emit`
seam has a hole to fill - fix it BEFORE trying again, not by giving the answer to the test agent.
