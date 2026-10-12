"""The harvest — what a finished arc of a project owes back to the system (D24 / D37, per
Mnemosyne's foundational "why" document, section 3).

That document says it plainly: *"Running a project WITH Mnemosyne consolidates reusable
skills / workflows: the project becomes a feature of the system."* Measured on 2026-07-27,
that nerve had never fired: a project ran for ten days, used 26 of Mnemosyne's 71
capabilities, produced a repo-layout judge and a grammar of non-circumventable criteria
that Mnemosyne itself lacks — and gave back nothing. `system/workflows/` has been empty
since the day it was created.

This module emits the contract for the missing gesture. It is deliberately an ORCHESTRATION contract
rather than a script, for a reason the repo has already paid for: judging whether a piece of a
project is worth keeping needs domain expertise the system does not have. A repo-layout rule is
judged by someone who knows repos; an economic measurement regime is judged by someone who knows
macro. So the contract's first job is to make the orchestrator RECRUIT — to dispatch agents who are
expert in the project's own field, not to answer alone.

Three things it refuses to do, each because the repo measured the cost of the opposite:

* **it does not promote anything** — the harvest ends in inert proposals (D92 / D100). Promotion is
  the operator's gesture, and a candidate that has not survived a differential trial is a hypothesis;
* **it does not accept a candidate on its finder's word** (D75). The agent that proposes is never
  the agent that judges genericity;
* **it does not measure quantity.** "How many candidates" is the metric that manufactures content —
  a lesson this project has already paid for. The contract asks for the REJECTION RATE instead — a
  harvest that keeps everything has judged nothing.

Print-only, offline, brick-free: this emits a contract; agents execute it. Code in English (D117);
the emitted contract is in English here (French in the private original, per D117). Decisions: D24
(project generator), D37 (skill generator), D42 (a workflow composes skills), D75, D92, D100.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["HarvestError", "HarvestVerdict", "build_harvest_contract"]


class HarvestError(Exception):
    """The harvest could not be emitted — fail closed rather than emit a half contract."""


@dataclass(frozen=True, slots=True)
class HarvestVerdict:
    """One of the four ways a candidate can end. Kept in code so the contract cannot drift."""

    name: str
    meaning: str


#: The four verdicts. `DUPLICATE` matters most and is the one a finder never looks for on its own:
#: on another project, a whole secret-broker was rebuilt from scratch while Mnemosyne's own sat four lines
#: away in a file the project already imported.
HARVEST_VERDICTS: tuple[HarvestVerdict, ...] = (
    HarvestVerdict(
        "GENERIC",
        "a project with ABSOLUTELY NO RELATION to this one would get the same value from it, as "
        "is. Test: a house move, a law-school thesis. If the answer is “yes but it would need "
        "adapting”, it is NOT generic, it is parametrizable.",
    ),
    HarvestVerdict(
        "PARAMETRIZABLE",
        "generic once a domain vocabulary is extracted — which must be NAMED precisely. Without "
        "that list, the verdict is a hope.",
    ),
    HarvestVerdict(
        "DUPLICATE",
        "Mnemosyne ALREADY does this, under another name. It is the MOST USEFUL verdict and the "
        "one nobody looks for: it says the project reinvented instead of reusing, so the existing "
        "capability could not be found at the moment it was needed. Report it by name.",
    ),
    HarvestVerdict(
        "SPECIFIC",
        "belongs to the project. Does not go back up. State WHY in one sentence — a justified "
        "rejection is worth a decision, a silent rejection is worth a forgetting.",
    ),
)

_RULE = "=" * 88

_CONTRACT = """\
PROJECT HARVEST — {project}
{rule}
You are the ORCHESTRATOR. Your job is NOT to read this project yourself and draw your own
conclusions: it is to RECRUIT the people who know, then rule on what they report back.

WHY THIS GESTURE EXISTS (read it, it changes how you search)
"Running a project WITH Mnemosyne consolidates reusable skills and workflows: the
project becomes a feature of the system." That is a nerve of Mnemosyne's soul, and it had
never fired — measured on 2026-07-27: a ten-day project used 26 of the system's 71
capabilities, built tools Mnemosyne does not have, and gave nothing back.

{rule}
PHASE 1 — GET YOUR BEARINGS (you, alone, before recruiting)
  a. `make describe` and `make help`: the EXHAUSTIVE map of what Mnemosyne already knows
     how to do. You cannot say "this is new" without this list in front of you.
  b. Read the README and the project's state. Determine its real DOMAIN (macroeconomics?
     law? software design?) — you are going to recruit experts OF THAT DOMAIN.
  c. Determine what the project produced: code, method documents, decisions, checks,
     templates.

{rule}
PHASE 2 — RECRUIT, and this is the heart of the gesture
Send agents in READ-ONLY, in parallel. Two families, and BOTH are required:

  • The DOMAIN EXPERTS (at least {domain_agents}). An agent who knows the project's
    business judges what no code reader can judge: is this rule a rule of the trade, or a
    local quirk? does this check measure what matters in this trade? Without them, what
    gets surfaced is what is well WRITTEN instead of what is well THOUGHT.
  • The MECHANICAL READERS (at least {mechanic_agents}). They read the code and the
    procedures with no knowledge of the trade, and answer: what would work elsewhere?

Give each of them: the project's path, phase 1's capability map, and the order to modify
NOTHING. Ask them for CITED candidates (path + excerpt), never impressions. A candidate
with no citation does not exist.

\U000026A0\U0000FE0F The producer does not judge its own candidate (D75). The agent that FINDS a piece is
never the one who rules on its genericity: cross-check, or have another agent judge it.

{rule}
PHASE 3 — RULE (you)
For each candidate, one verdict and only one:

{verdicts}
Then the FORM, and the distinction is the operator's — do not merge it:
  • WORKFLOW = a TOOL, code that executes, a mechanical sequence.
  • SKILL    = a CAPABILITY, a way of doing something that a model applies.
An empirical criterion beats a definition: **if several runs have reinvented the same
piece of code, the capability must become a tool.** Look for that trace.

{rule}
PHASE 4 — WHAT YOU HAND BACK
  1. The count of candidates EXAMINED, and the count REJECTED. A low rejection rate is a
     warning sign, not good news: a harvest that keeps everything has judged nothing. Do
     not aim for ANY number of candidates kept — chasing volume manufactures volume.
  2. The DUPLICATES first. They say that an existing capability could not be found at the
     moment it was needed: that is a defect of Mnemosyne, not of the project.
  3. For each one kept: name, path, what it does in one sentence, verdict, form
     (workflow/skill), and **what would need to be measured to prove it is useful**.
  4. What you were NOT able to judge, and why.

{rule}
PHASE 5 — WHAT HAPPENS NEXT, AND IT IS NOT YOU
You promote NOTHING. A kept candidate is an INERT PROPOSAL (D92): it waits for the
operator's gesture. And before being promoted, it must pass the DIFFERENTIAL TRIAL — the
same task, with and without, judged blind:

    make skill-eprouver SKILL=<nom> TACHE="..." OUT=/tmp/epreuve-<nom>

A candidate nobody has tried is a hypothesis, no matter how good its file looks. An
artifact that differentiates nothing is decorative; some exist.

{rule}
PHASE 6 — IF YOU BUILD: THE FIVE SURFACES, AND THEY ARE PAID FOR
\U000026D4 A GATE is not judged by a skill's differential trial: it is judged by SABOTAGE. On
2026-09-08, the first gate from a harvest on another project shipped GREEN — 19 witnesses, 8 sabotages
killed — and an isolated audit got an SSH key exfiltration through it at rc=0. The 19
witnesses covered the JUDGE and the EDGE. None read the line that turns a verdict into a
refusal.

  1. THE JUDGE — pure verdicts, injected population, no disk access.
  2. THE RC — the line `return 0 if ... else 1` is a surface in its own right. Hardcode
     `return 0` there: if nothing turns red, the gate has not been tried.
  3. THE PUBLISHED TEXT — a witness reads THE SENTENCE, never just the data that feeds it.
     And never through a token common to several branches: a word present everywhere
     distinguishes NO branch.
  4. THE PRODUCTION VALUE — if your witnesses inject a root, a threshold, or a
     population, a SEPARATE witness judges the module's real value. Injecting everywhere
     leaves the real value naked.
  5. THE PASSING CASE — the counter-proof. Without it, you only measure your own ability
     to refuse everything.

\U000026D4 AND TWO RULES THAT COST MORE THAN THE FIVE ABOVE:
  - PULL THE COMMAND THAT SHOWS THE OBJECT **HERE** FIRST. A reference list written in
    advance can have zero intersection with reality: 14 of the 18 modules of one freeze
    existed nowhere in the repo. A ZERO is a MEASURED REFUSAL, and it is a COMPLETE
    deliverable — 3 items out of 22 produced no code at all, with their number stated.
  - MEASURE WHAT YOUR FIX COSTS. One remedy cost 3 s at the start of EVERY session to
    publish a number that a free measurement gave almost as well.

The measured detail lives in the private harvest register (not part of this public
mirror). The address, never the copy (D163).
"""


def build_harvest_contract(
    project: str, *, domain_agents: int = 3, mechanic_agents: int = 2
) -> str:
    """Assemble the harvest contract from its ONE code home — emitted, never hand-copied.

    ``domain_agents`` / ``mechanic_agents`` are FLOORS, not targets: a project with three distinct
    fields deserves more experts, and the contract says so. They are parameters because the right
    number depends on the project, and a number frozen in prose would be obeyed as a ceiling."""
    if not project.strip():
        raise HarvestError("no project named — a harvest with no field reaps nothing")
    if domain_agents < 1:
        raise HarvestError(
            "at least ONE domain expert is required: without one the harvest judges the shape of "
            "the code and never the business value of what it carries"
        )
    verdicts = "\n".join(f"  {v.name} — {v.meaning}\n" for v in HARVEST_VERDICTS)
    return _CONTRACT.format(
        project=project.strip(),
        rule=_RULE,
        domain_agents=domain_agents,
        mechanic_agents=mechanic_agents,
        verdicts=verdicts,
    )


def known_projects(root: Path) -> tuple[str, ...]:
    """The project bubbles that exist, for a caller that mistyped a path.

    **HIDDEN DIRECTORIES ARE EXCLUDED, AND THAT IS A MEASURED FIX, NOT A PRECAUTION.** The
    tick's `I2` source names the closed arcs that owe a harvest; on 2026-09-08 it named **36 arcs
    that all lived inside throwaway mutation copies** (`projects/saas/.repo-layout-mutations-*`),
    burying the real ones. The failure mode had been *written down* by `_moisson_due`'s own author
    on 2026-08-15 — *"none of them carries an arc, so none enters the population — but that is a
    property of their CONTENT, not a guarantee from the enumerator"* — and 24 days later the content
    changed. Measured the day of the fix: **51 directories enumerated, 16 hidden**, including
    `projects/.git/objects` and `projects/.git/refs` — the git store itself was being offered as a
    project bubble. *A limit that depends on today's content is not a guarantee; the enumerator now
    carries it.*

    A leading dot marks tooling, scratch or VCS internals by universal convention — never a project
    a human named. The filter applies at **both** levels (family and bubble), because the noise
    appeared at both."""
    projects = root / "projects"
    if not projects.is_dir():
        return ()
    return tuple(
        sorted(
            str(p.relative_to(root))
            for family in projects.iterdir()
            if family.is_dir() and not family.name.startswith(".")
            for p in family.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )
    )
