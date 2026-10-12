"""Generative skill substrate (D36-D39 / D42 / D52) — declare-needs + human-gated activation.

A skill is a role + its method (D25); a *workflow* is a skill whose role is orchestration
(D42). This module is the generative substrate — the "X + generator of X" pattern (D37 / D52)
applied to skills — plus the two structural barriers that keep it safe:

* **A skill DECLARES needs, not rights (D38).** Its manifest states what it *needs*
  (``sensitivity_max``, ``task_class``, network, domains); it never grants itself a right.
  The central policy decides and the Guard (D89) enforces — so adding a skill never reopens
  security skill-by-skill (D38). There is deliberately no ``granted_rights`` field here.
* **No skill goes live without a DISTINCT auditor AND a human gesture (D37 / D39-6).** The
  generator produces a draft conformant to the skill anatomy (D36); a *distinct* adversarial
  auditor (producer ≠ verifier, D75 / D100-6) must pass it; then the operator validates before it
  becomes ACTIVE. :meth:`SkillGenerator.activate` refuses on either gap — fail-closed.

Skills are built just-in-time (D39): the SEED names the few already-real skills; everything
else is generated on a real need. The seed here is *contenant* (names + roles); the concrete
skill bodies are *contenu*, filled at usage (D98). Code & docstrings English (D117).

This module also owns the ``generateur-de-skills`` skill's (D39-7) OWN code home: the anatomy
contract every concrete skill (distillateur / finisseur / juge / …) is built against
(:data:`SKILL_ANATOMY_TEMPLATE`, emitted byte-for-byte by ``make skill-emit`` — never hand-copied
into a SKILL.md, on pain of tripping its own anti-drift lint) and the verify-in-code audit that
checks a candidate skill against it (:func:`audit_skill`, the juge-analog for skills, run by
``make skill-audit``). Dogfood: the meta-skill is built the same way it tells every other skill
to be built.

Decisions: D36 (anatomy) · D37 (generator + double-voie trigger + human validation) · D38
(declare-needs, central policy) · D39 (seed, just-in-time) · D39-7 (generateur-de-skills) · D42
(workflow = orchestration skill) · D52 (project generator, same pattern) · D75 / D100-6
(producer ≠ verifier).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType

from ..ports import ErrorCode, MnemosyneError, Sensitivity
from .verifier import require_distinct


class TaskClass:
    """Marker names for a skill's task class (D36 / D42) — kept as plain constants so the
    seed can name orchestration skills before their bodies exist (D98)."""

    ATOMIC = "atomic"  # a single role + method (D25)
    ORCHESTRATION = "orchestration"  # a workflow: chains other skills (D42)


class ActivationState:
    """The generate → audit → activate lifecycle of a skill (D37)."""

    DRAFT = "draft"  # generated, conformant to the anatomy (D36), not yet audited
    AUDITED = "audited"  # passed a DISTINCT adversarial auditor (D39-6 / D75)
    ACTIVE = "active"  # human-validated → live (D37); the ONLY state that may run


class SkillActivationRefused(MnemosyneError):
    """A skill was pushed toward ACTIVE without a distinct auditor or a human gesture (D37).

    Fail-closed like a Guard denial (``DENIED``): a skill that is not both audited by a
    distinct verifier AND human-validated stays inert — it never runs on trust (D100)."""

    code = ErrorCode.DENIED


@dataclass(frozen=True, slots=True)
class SkillNeeds:
    """What a skill DECLARES it needs (D38) — never a right it grants itself.

    The Guard (D89) reads these against the central policy and enforces; there is no
    ``granted_rights`` field, by design (D38: "a component never defines its own
    security")."""

    sensitivity_max: Sensitivity
    task_class: str  # one of TaskClass.*
    network: bool = False  # declares a *need* for network; the policy decides (D38)
    domains: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class SkillManifest:
    """The normed skill header the Guard reads (D36 / D38), plus its activation state.

    ``role`` is the one-line "what it does"; ``needs`` is the declared security surface. The
    manifest PLAFONNE the bubble's rights (D54-9): a skill can never obtain a right its
    manifest does not declare."""

    name: str
    version: str
    role: str
    needs: SkillNeeds
    state: str = ActivationState.DRAFT

    @property
    def is_active(self) -> bool:
        """Whether the skill may run — ACTIVE only (D37)."""
        return self.state == ActivationState.ACTIVE


#: The skill graine (D39) — the few already-real skills, named as role only. Everything else
#: is generated on a real need (just-in-time, D39); these bodies are contenu, filled at ③.
SEED_SKILLS: dict[str, str] = {
    "recherche": "retrieve a document / fragment with its source (D39-1 / D40)",
    "normaliseur": "raw source → faithful clean markdown, form not substance (D39-2)",
    "trieur": "file from the benne, fill filter metadata, attach to domains (D39-3)",
    "distillateur": "produce the distilled understanding of a document (D39-4)",
    "compagnon": "capture the operator's live salience while they read (D39-5 / D41)",
    "auditeur": "generic adversarial validator, run in an ISOLATED instance (D39-6)",
    "generateur-de-skills": "fabricate new skills conformant to the anatomy (D37 / D39-7)",
    # orchestration skills (D42) — named here, mechanics at their lots / usage
    "ingestion": "full document-entry pipeline; pilots the atomic skills (D39 / D42)",
    "build-idempotent": "rebuild the system repeatably, breaking nothing (D39 / D44)",
    "creation-de-projet": "instantiate a project from the template (D39 / D52)",
}


class SkillGenerator:
    """The meta-skill that fabricates skills (D37) — itself a skill (D37 / D42).

    Produces a DRAFT conformant to the anatomy (D36), which a DISTINCT auditor must pass and
    the operator must validate before it goes ACTIVE. The generator can never shortcut those two
    gates — that is what keeps a generated skill from running on trust (D100)."""

    __slots__ = ()

    def generate(self, *, name: str, version: str, role: str, needs: SkillNeeds) -> SkillManifest:
        """Emit a DRAFT skill manifest from a described need (D37, just-in-time D39)."""
        return SkillManifest(name=name, version=version, role=role, needs=needs)

    def audit(self, manifest: SkillManifest, *, author: str, auditor: str) -> SkillManifest:
        """Mark a draft AUDITED once a DISTINCT adversarial auditor has passed it (D39-6 / D75).

        Refuses when the auditor is the author (producer ≠ verifier, D100-6) — the same
        no-self-validation gate as crystallisation and production."""
        require_distinct(author, auditor, SkillActivationRefused, what="skill audit")
        return replace(manifest, state=ActivationState.AUDITED)

    def activate(self, manifest: SkillManifest, *, human_validated: bool) -> SkillManifest:
        """Promote an AUDITED skill to ACTIVE — only under an explicit human gesture (D37).

        Fail-closed twice over: a skill that was not first AUDITED by a distinct verifier, or
        that lacks the operator's validation, is refused. "Human validation by the operator
        remains mandatory before a skill can become active" (D37)."""
        if manifest.state != ActivationState.AUDITED:
            raise SkillActivationRefused(
                f"skill {manifest.name!r} must be AUDITED by a distinct verifier before "
                f"activation, not {manifest.state!r} (D37 / D39-6)"
            )
        if not human_validated:
            raise SkillActivationRefused(
                f"skill {manifest.name!r} cannot go ACTIVE without the operator's validation "
                "(D37 — human gesture required, never auto)"
            )
        return replace(manifest, state=ActivationState.ACTIVE)


# --------------------------------------------------------------------------- #
# skill-creator (D37 / D39-7 "generateur-de-skills") — the meta-skill's OWN   #
# code home: the anatomy contract every new skill is built against, and the  #
# verify-in-code audit that checks a candidate skill against it (D75).       #
# --------------------------------------------------------------------------- #
#: The skill-creator's contract: the anatomy every skill in this repo shares, plus the six lessons
#: of the distillateur/finisseur/juge arc that a new skill must encode. This is the ONE code home
#: of that contract (contract-single-source-emit) — `skill_emit.py` (`make skill-emit`) prints it
#: BYTE FOR BYTE; the skill-creator's own SKILL.md describes it in prose but never restates it, on
#: pain of tripping its own anti-drift lint (the name ends in `_TEMPLATE`, so `audit_skill` below
#: scans for it exactly like it scans FINISH_PROMPT / `_PROMPT_TEMPLATE` — the dogfood is by
#: construction, not by convention). English (D117): this is a code constant, like FINISH_PROMPT.
SKILL_ANATOMY_TEMPLATE = """\
Every skill in this repo has the SAME anatomy, six layers, always in this order:

  1. CODE HOME       system/lib/mnemosyne/production/<name>.py — the real logic, and any
                      model-facing prompt/schema constant (a *_PROMPT / *_TEMPLATE). ONE file
                      owns the behaviour; nothing about it is duplicated elsewhere.
  2. THIN ADAPTER     system/skills/<name>/<name>_*.py — orchestration only (glob files, call
                      the code home, write output). It imports the code home; it never
                      re-implements it.
  3. MAKE ENTRY       a `make <name>` target in the root Makefile — the ONE way to run the
                      skill (local model, or no model at all, whichever the skill needs).
  4. EMIT SEAM        system/skills/<name>/<name>_emit.py + `make <name>-emit` — prints the
                      EXACT contract (prompt / schema / safety verdict) a FRONTIER host must
                      follow, replaying the code home's real functions. NEVER a hand-written
                      copy of the prompt in SKILL.md: a copy drifts silently.
  5. VERIFY-IN-CODE   a pure verdict function in the code home (judge_fiche is the exemplar)
                      that re-checks the OUTPUT against the source of truth, trusting no
                      producer — local model, frontier agent, or human alike.
  6. LOCK TEST        tests/test_<name>_*.py — asserts the emission carries a REAL fragment of
                      the code-home constant (not a paraphrase), so a future edit to the
                      constant that forgets SKILL.md (or vice versa) turns the suite red.

Two exemplars to imitate, never reinvent:
  - keep_verbatim (mnemosyne.production.distillation) — P3 is SACRED wherever a skill
    restructures a source of truth: a passage is kept ONLY if it is a literal substring of
    the source. Reuse this pattern (or the function itself) wherever a new skill must never
    let a model paraphrase what should be copied.
  - chapter_numbers_ok (mnemosyne.production.finisher) — a FAIL-CLOSED guard: on ANY
    ambiguity, refuse and flag rather than guess. A new skill's guards take this shape: a
    boolean check in code, evaluated BEFORE the skill acts, never a prompt asking the model
    to "be careful".

The six lessons every new skill must encode (skip one and you repeat the arc's own failure):

  1. CONTRACT-SINGLE-SOURCE-EMIT (anti-drift), and the MULTI-VERSION-PER-EXECUTOR doctrine it
     generalises (D150). A prompt or schema a model must follow lives in ONE code home and is
     EMITTED to every EXECUTOR that runs it — the SAME contract, up to three bindings, never
     re-authored: (a) a LOCAL model (`make <name>`, the MLX brain — cheap / repeated volume);
     (b) that same model via API (the GenerationBackend seam — frontier quality per item, at
     scale, no interactive session); (c) a FRONTIER host (Claude Code / Codex), whose version
     MAY BE JUST THIS PROMPT applied in the folder it can reach — NO bespoke `.py` (`make
     <name>-emit`). It is NEVER hand-copied into SKILL.md: a hand-copied prompt drifted (a lost
     clause, an abridged instruction) and silently broke the first frontier pass exactly where
     the local model had worked. "Up to three", not "always three": a model-free skill (the
     juge) has nothing to emit. SKILL.md describes the contract; it does not restate it.
  2. VERBATIM / P3 SACRED. Where a skill restructures a source of truth, the restructured
     content stays byte-for-byte faithful to the source (see keep_verbatim above) — never
     reformulated, never "improved for readability" at the cost of accuracy.
  3. FAIL-CLOSED GUARDS IN CODE. Ambiguity means refuse or flag, never guess (see
     chapter_numbers_ok above). The guard is a function in the code home, exercised by a test
     — not a hope expressed in the prompt.
  4. PRODUCER != VERIFIER. Every governed change gets an audit by a DISTINCT identity
     (require_distinct, D75 / D100-6) before it goes ACTIVE (ActivationState: DRAFT ->
     AUDITED -> ACTIVE, SkillGenerator). Ship a verify-in-code path (lesson 5) so that audit
     has something mechanical to run, not just a read-through.
  5. TEST VIA THE REAL PROD PATH. A skill is proven by plugging a FRESH, UNBIASED agent into
     its natural `make` entry point, with repo access and NO answer handed to it — never a
     hand-picked example the author already knows works.
  6. A FRONTIER AGENT WILL SCRIPT A TEMPLATE on a big generative task. The acceptance check
     for "did it really do the work" lives in CODE, as a SEPARATE axis from correctness (see
     JudgeStatus.n_templated) — surfaced, never silently folded into pass/fail.

Separately, D36 governs the shape of every skill's OWN SKILL.md — a distinct, complementary layer
from the six code-layers above (those are THIS repo's own extra engineering discipline for a
skill that owns real code; D36 is the general document anatomy every skill has, code-owning or
not). Two parts, ALWAYS both present:

  (A) HEADER (frontmatter), NORMED, same controlled-vocabulary spirit as a distilled document:
      name / description (what a router reads to CHOOSE the skill) / task_class (atomic |
      orchestration — the skill's NATURE, D42 refining D36's classe_de_tâche) / sensitivity_max (public | perso | sensible —
      sensible means LOCAL ONLY, D27 / D38) / version (idempotent regeneration / traceability) /
      plus the auto fields id + date ("consistent with the documents", D36).
  (B) BODY = a FLOOR of six MANDATORY sections (never a ceiling — a skill may add its own extra
      sections on top): Role (who the agent becomes) - Method (the steps; deterministic = CODE,
      judgment = agent) - Inputs -> Outputs (what it reads / writes and WHERE) - When to FLAG
      (stop conditions + escalation to the operator) - Validation (the adversarial validator +
      PASS criteria) - Logs (JSONL events).

The fine-grained access perimeter (what a skill may touch) is deliberately NOT a SKILL.md field:
it is DECLARED as needs (SkillNeeds) and ENFORCED centrally by the Guard (D38) — a skill never
authors its own security.
"""

#: Literal placeholder markers ``new_skill.py`` (``make skill-new``) writes into a freshly
#: scaffolded SKILL.md — the SAME strings on both ends (the scaffolder writes them, ``audit_skill``
#: below detects them), so the two can never drift apart (lesson 1, applied reflexively to the
#: scaffolder itself). Their continued presence is the "scaffold_only" axis (lesson 6): a
#: MECHANICAL shell with no real code-home logic behind it yet — a DRAFT is expected to carry
#: these; SURFACED, never silently folded into ``ok`` (a scaffold is a valid DRAFT, not a failure).
#: TODO(public-mirror): needs human review -- these three marker strings stay in French on
#: purpose. They are matched byte-for-byte against what `new_skill.py` (outside this
#: sanitization lot) actually writes into a freshly scaffolded SKILL.md; translating them here
#: without also changing that other file would silently break the match.
SCAFFOLD_MARKERS: tuple[str, ...] = (
    "TODO(skill-creator): decrire",
    "TODO(skill-creator): le contrat",
    "TODO(skill-creator): le garde-fou",
)

#: Frontmatter shape (adapted from Anthropic's skill-creator ``quick_validate.py``, scoped to what
#: THIS repo enforces, D117): kebab-case, lowercase letters/digits, single hyphens, no leading /
#: trailing / doubled hyphen.
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_MAX_DESCRIPTION = 1024  # same cap Anthropic's skill-creator enforces (a description is a trigger,
#                          not a body — an over-long one crowds out every other skill's metadata)
_MIN_SCAFFOLD_BODY_CHARS = 300  # a real "Quand l'utiliser / Comment l'invoquer / ..." body is well
#                                 past this; below it, SKILL.md is a shell regardless of markers


@dataclass(frozen=True, slots=True)
class SkillAudit:
    """The verify-in-code verdict for ONE candidate skill (D75 / D100-6) — the juge-analog for
    skills.py: a mechanical, no-trust pass over a candidate BEFORE a DISTINCT human auditor reads
    it. Mirrors :class:`~mnemosyne.production.juge.FicheVerdict`'s honesty: ``ok`` covers only the
    checkable structural invariants (frontmatter shape, an emit seam, no hand-copied prompt) — it
    is NOT a substitute for :meth:`SkillGenerator.audit`'s DISTINCT-auditor gate
    (:func:`~mnemosyne.production.verifier.require_distinct`), which still governs DRAFT ->
    AUDITED -> ACTIVE (D37 / D39-6): a human auditor runs ``make skill-audit`` as the mechanical
    prerequisite, then — being distinct from the skill's producer — calls
    ``SkillGenerator.audit(manifest, author=..., auditor=...)`` to actually gate activation.
    ``scaffold_only`` is a SEPARATE axis (lesson 6): never folded into ``ok``, so a well-formed-
    but-empty scaffold is surfaced, not silently blessed nor silently failed. Likewise
    ``requires_emit_seam``: a model-FREE skill (no ``*_PROMPT`` / ``*_TEMPLATE`` / ``*_SCHEMA``
    contract to emit — the ``juge`` is the reference case) needs no emit seam, so an absent seam
    there is surfaced INFORMATIONALLY (``has_emit_seam=False`` with ``requires_emit_seam=False``)
    and never flips ``ok`` — the gate must not hard-fail a known-good model-free skill.
    ``anatomy_gaps`` is a THIRD separate axis (D36 — the SKILL.md-level anatomy, distinct from the
    five/six code-layers ``SKILL_ANATOMY_TEMPLATE`` also documents): which D36 frontmatter fields
    or mandatory body sections are missing from THIS candidate. Purely informational, like
    ``scaffold_only`` — it NEVER demotes ``ok``. Deliberately non-blocking: this axis was added
    after every real skill in this repo already existed, none pre-dating it carried this
    frontmatter, and a mechanical check must not retroactively fail a skill sanctioned under the
    older shape (D100 — surface the gap, never silently invent compliance OR silently break)."""

    ok: bool
    name: str
    reasons: tuple[str, ...]  # every failing structural check (empty iff ok)
    has_emit_seam: bool
    anti_drift_hits: tuple[str, ...]  # code-home constants that leaked verbatim into SKILL.md
    scaffold_only: bool  # SEPARATE axis (lesson 6) — surfaced, never affects ok
    scaffold_reason: str
    #: whether an emit seam was REQUIRED (the skill has a model-facing contract). False for a
    #: model-free skill (juge) — an absent seam is then informational, never a `reasons` entry.
    requires_emit_seam: bool = True
    #: D36 anatomy gaps (a missing frontmatter field, or a missing mandatory body section) — a
    #: THIRD separate axis, like scaffold_only: SURFACED, never folded into ok. Empty iff the
    #: candidate's SKILL.md is fully D36-conformant (see :func:`_d36_anatomy_gaps`).
    anatomy_gaps: tuple[str, ...] = ()


def _parse_frontmatter(skill_md: str) -> dict[str, str]:
    """A tiny, dependency-free YAML-frontmatter reader for a SKILL.md (no bricks: `make skill-audit`
    must run with nothing installed beyond the dev toolchain, like `make judge` / `make finish`).
    Handles the two shapes every SKILL.md in this repo uses: a plain ``key: value`` scalar, and a
    folded block scalar (``key: >`` followed by indented continuation lines — YAML line-folding).
    Good enough for the two fields this module reads (``name`` / ``description``); NOT a general
    YAML parser (a real one would need PyYAML, which the skill-creator deliberately avoids)."""
    if not skill_md.lstrip().startswith("---"):
        return {}
    body = skill_md.lstrip()
    end = body.find("\n---", 3)
    block = body[3:end] if end != -1 else body[3:]
    fields: dict[str, str] = {}
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z][\w-]*):[ \t]*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest in (">", "|", ">-", "|-"):  # folded/literal block scalar: gather indented lines
            i += 1
            collected: list[str] = []
            while i < len(lines) and (lines[i][:1] in (" ", "\t") or not lines[i].strip()):
                collected.append(lines[i].strip())
                i += 1
            fields[key] = " ".join(c for c in collected if c).strip()
            continue
        fields[key] = rest.strip('"').strip("'")
        i += 1
    return fields


def _frontmatter_issues(skill_md: str) -> tuple[str, ...]:
    """Frontmatter shape checks (adapted from Anthropic's skill-creator ``quick_validate.py``,
    scoped to what this repo enforces): ``name`` present and kebab-case; ``description`` present,
    non-empty, no angle bracket (reads as unclosed markup in a renderer), and within the cap."""
    fields = _parse_frontmatter(skill_md)
    issues: list[str] = []
    name = fields.get("name", "")
    if not name:
        issues.append("frontmatter is missing 'name'")
    elif not _NAME_RE.match(name):
        issues.append(f"name {name!r} is not kebab-case (lowercase letters/digits, single hyphens)")
    description = fields.get("description", "")
    if not description:
        issues.append("frontmatter is missing 'description'")
    else:
        if "<" in description or ">" in description:
            issues.append("description contains an angle bracket ('<' or '>')")
        if len(description) > _MAX_DESCRIPTION:
            issues.append(
                f"description is {len(description)} chars, over the {_MAX_DESCRIPTION} cap"
            )
    return tuple(issues)


#: A hand-copy is never byte-identical for long (the next edit to the code home silently un-syncs
#: it), so the anti-drift scan does not require a full-constant match: any ``_DRIFT_WINDOW``-char
#: contiguous slice of a constant's text, found LITERALLY inside a SKILL.md, is enough to flag it —
#: a coincidence that long is vanishingly unlikely in prose. The stride is 1 so EVERY window is
#: tried: the guaranteed detection floor then equals the window (any 60-char verbatim run is
#: caught), matching the documented "60-char window" exactly — a larger stride would silently raise
#: the real floor (stride 40 made it ~100). Only a handful of short constants are scanned, so the
#: cost is negligible (the whole scan is well under 100 ms).
_DRIFT_WINDOW = 60
_DRIFT_STRIDE = 1


def _anti_drift_hits(skill_md: str, prompt_constants: Mapping[str, str]) -> tuple[str, ...]:
    """Which code-home ``*_PROMPT`` / ``*_TEMPLATE`` / ``*_SCHEMA`` constants leaked VERBATIM into a
    SKILL.md (lesson 1, contract-single-source-emit) — the central lesson of the whole arc, made
    runnable. Pure over the passed-in mapping; the orchestrator decides which constants to scan."""
    hits: list[str] = []
    for const_name, text in prompt_constants.items():
        if len(text) < _DRIFT_WINDOW:
            continue  # too short to rule out an innocent coincidental phrase
        for i in range(0, len(text) - _DRIFT_WINDOW + 1, _DRIFT_STRIDE):
            if text[i : i + _DRIFT_WINDOW] in skill_md:
                hits.append(const_name)
                break
    return tuple(hits)


def _scaffold_verdict(
    skill_md: str, impl_texts: Mapping[str, str] = MappingProxyType({})
) -> tuple[bool, str]:
    """Is this candidate still a bare, unfilled scaffold (lesson 6 — a SEPARATE axis, SURFACED,
    never folded into ``ok``)? A scaffold is detected WHEREVER it still is, not only in SKILL.md:
    (a) a literal :data:`SCAFFOLD_MARKERS` placeholder survives in the SKILL.md; (b) a marker
    survives in the skill's CODE HOME / adapter (``impl_texts`` — an un-filled code stub that still
    raises ``NotImplementedError``, e.g. a nicely-written SKILL.md over a stubbed home: the marker
    is right there in the code); (c) the SKILL.md body is too short to be a real description. Any
    one is enough. A DRAFT skill is EXPECTED to trip this; it is not a failure, only an honest
    label. ``impl_texts`` deliberately excludes files that reference the marker strings as CONSTANTS
    (the skill-creator's own ``new_skill.py`` / ``skills.py``) — the orchestrator only feeds the
    derived code home + ``*_run.py`` adapter, so a real filled skill never false-positives."""
    hit = next((marker for marker in SCAFFOLD_MARKERS if marker in skill_md), None)
    if hit is not None:
        return True, f"unfilled scaffold marker still present in SKILL.md: {hit!r}"
    for label, text in impl_texts.items():
        marker = next((m for m in SCAFFOLD_MARKERS if m in text), None)
        if marker is not None:
            return (
                True,
                f"code home still an un-filled stub — scaffold marker in {label}: {marker!r}",
            )
    body = skill_md.split("---", 2)[-1] if skill_md.count("---") >= 2 else skill_md
    if len(body.strip()) < _MIN_SCAFFOLD_BODY_CHARS:
        return True, f"SKILL.md body is only {len(body.strip())} chars — looks like an empty shell"
    return False, ""


#: The D36 frontmatter fields beyond `name` / `description` (those two are already covered by
#: `_frontmatter_issues`): the model-routing / security-ceiling / traceability header, plus the
#: two auto plumbing fields D36 asks for "consistent with the documents" (id, date). Presence-only
#: — a stricter shape check would duplicate `_frontmatter_issues`, which this axis deliberately
#: does not (see `_d36_anatomy_gaps`).
_D36_FRONTMATTER_FIELDS: tuple[str, ...] = (
    "task_class",
    "sensitivity_max",
    "version",
    "id",
    "date",
)

#: The six D36 body sections every skill's SKILL.md carries as a FLOOR (never a ceiling — a skill
#: may add sections of its own on top, D36). Matched as a markdown HEADING (a line starting with
#: 1-6 ``#``), tolerant of the accented French spelling AND the accent-free spelling this repo's
#: real SKILL.md files actually use (D117 keeps CODE English; the docs stay French, often
#: accent-free by house style). A simple regex, not a full markdown parser — consistent with
#: `_parse_frontmatter`'s own "good enough, no dependency" scope; a heading inside a fenced code
#: block could theoretically false-match, a known, accepted limitation (no real SKILL.md does this).
#: EXPANDED 2026-09-09 : each pattern accepts the French title OR its English equivalent.
#: WHY, and this is a paid lesson: three of these six patterns accepted ONLY French
#: (`M[eé]thode`, `Entr[eé]es...Sorties`, `Quand FLAG`) -- the accent was optional, the WORD was not.
#: The public mirror must be entirely in English; translating these titles therefore caused
#: the section to DISAPPEAR FROM THE EYES OF THIS JUDGE, IN SILENCE, because the judge lives in a
#: different file than the document. Measurement of the day: 3 SKILL.md out of 8 degraded, including TWO for days,
#: invisible because the witness only judges four "real" skills.
#: The expansion is NOT a blank check: each pattern names TWO spellings and refuses the
#: third -- `test_le_motif_D36_accepte_les_DEUX_langues_et_REFUSE_une_troisieme` proves it in
#: both directions. A pattern that would accept "any title" would measure nothing anymore.
_D36_BODY_SECTIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Role", re.compile(r"(?im)^#{1,6}[ \t]*R[oô]le\b")),
    ("Methode", re.compile(r"(?im)^#{1,6}[ \t]*(?:M[eé]thode|Method)\b")),
    (
        "Entrees -> Sorties",
        re.compile(r"(?im)^#{1,6}[ \t]*(?:Entr[eé]es\b.*\bSorties|Inputs\b.*\bOutputs)\b"),
    ),
    ("Quand FLAG", re.compile(r"(?im)^#{1,6}[ \t]*(?:Quand[ \t]+FLAG|When[ \t]+to[ \t]+FLAG)\b")),
    ("Validation", re.compile(r"(?im)^#{1,6}[ \t]*Validation\b")),
    ("Logs", re.compile(r"(?im)^#{1,6}[ \t]*Logs?\b")),
)


def _d36_anatomy_gaps(skill_md: str) -> tuple[str, ...]:
    """Which D36 SKILL.md-anatomy elements are missing — an INFORMATIONAL, SEPARATE axis (mirrors
    ``scaffold_only``, lesson 6): a gap here never flips ``ok`` (see :data:`SkillAudit.anatomy_gaps`).
    Checks the frontmatter fields D36 requires beyond name/description (:data:`_D36_FRONTMATTER_FIELDS`),
    and the six mandatory body sections (D36-B, :data:`_D36_BODY_SECTIONS`) — PRESENCE only, matched
    as a markdown heading; the CONTENT of a present section is noyau libre (D36), not graded here.
    Safe on an empty string (a missing SKILL.md reports every element missing, never raises)."""
    fields = _parse_frontmatter(skill_md)
    gaps = [
        f"frontmatter missing '{field}' (D36 header)"
        for field in _D36_FRONTMATTER_FIELDS
        if not fields.get(field)
    ]
    gaps.extend(
        f"SKILL.md body missing the '{label}' section (D36 floor)"
        for label, pattern in _D36_BODY_SECTIONS
        if not pattern.search(skill_md)
    )
    return tuple(gaps)


def audit_skill(
    *,
    name: str,
    skill_md: str | None,
    n_skill_md_files: int,
    has_emit_seam: bool,
    requires_emit_seam: bool = True,
    prompt_constants: Mapping[str, str] = MappingProxyType({}),
    impl_texts: Mapping[str, str] = MappingProxyType({}),
    unparseable_files: Sequence[str] = (),
) -> SkillAudit:
    """Verify-in-code pass over ONE candidate skill (D75 / D100-6) — PURE, given already-read
    texts and precomputed facts (no filesystem I/O here; the orchestration in
    ``system/skills/skill-creator/audit_skill.py`` does the globbing/reading and calls this,
    exactly as ``judge_library.py`` globs ``knowledge/`` and calls the pure
    :func:`~mnemosyne.production.juge.judge_fiche`). Runs the checks the skill-anatomy contract
    (:data:`SKILL_ANATOMY_TEMPLATE`) requires of every new skill: (a) an emit seam exists WHEN the
    skill has a model-facing contract to emit (``requires_emit_seam`` — a model-FREE skill like the
    ``juge`` legitimately has none, so an absent seam there is INFORMATIONAL, never a failure); (b)
    no code-home ``*_PROMPT`` / ``*_TEMPLATE`` / ``*_SCHEMA`` constant leaked verbatim into SKILL.md
    (anti-drift, lesson 1); (c) frontmatter is well-formed and there is EXACTLY one SKILL.md; (d)
    scaffold-only is measured over the SKILL.md AND the code home / adapter (``impl_texts`` — a
    marker in a stubbed home counts) and reported as a SEPARATE axis (lesson 6) — it never demotes
    ``ok``; (e) ``unparseable_files`` (the skill's own ``.py`` that do not parse) is a hard failure
    — a broken skill must not audit as clean; (f) the D36 SKILL.md-anatomy (frontmatter fields
    beyond name/description, the six mandatory body sections) is measured as ``anatomy_gaps`` — a
    THIRD SEPARATE axis (:func:`_d36_anatomy_gaps`), informational like scaffold_only, so a skill
    built before this axis existed is surfaced honestly rather than retroactively failed."""
    reasons: list[str] = []
    if n_skill_md_files == 0:
        reasons.append("no SKILL.md found")
    elif n_skill_md_files > 1:
        reasons.append(f"{n_skill_md_files} SKILL.md files found — exactly one is required")
    # An emit seam is required ONLY when the skill has a model contract to emit. A model-free skill
    # (juge) has nothing to emit, so its absent seam is surfaced informationally, never a `reason`.
    if not has_emit_seam and requires_emit_seam:
        reasons.append("no emit seam found (a <name>-emit Makefile target and/or a *_emit.py)")
    # A skill whose own .py does not parse is broken — surfaced as a hard failure, never clean.
    for broken in unparseable_files:
        reasons.append(f"skill python does not parse (syntax error): {broken}")
    text = skill_md or ""
    reasons.extend(_frontmatter_issues(text))
    drift = _anti_drift_hits(text, prompt_constants) if text else ()
    if drift:
        reasons.append(
            "SKILL.md contains a verbatim excerpt of a code-home constant (anti-drift): "
            + ", ".join(drift)
        )
    # scaffold_only scans the SKILL.md AND the code home / adapter (impl_texts): a stub home with a
    # nicely-written SKILL.md is still a scaffold. Even with no SKILL.md, an impl marker counts.
    scaffold_only, scaffold_reason = _scaffold_verdict(text, impl_texts)
    if not text and not scaffold_only:
        scaffold_only, scaffold_reason = True, "no SKILL.md to read"
    # D36 SKILL.md-anatomy gaps: a THIRD separate axis (lesson 6 pattern) — informational only,
    # never appended to `reasons`, so it can never flip `ok` (SkillAudit.anatomy_gaps docstring).
    anatomy_gaps = _d36_anatomy_gaps(text)
    return SkillAudit(
        ok=not reasons,
        name=name,
        reasons=tuple(reasons),
        has_emit_seam=has_emit_seam,
        anti_drift_hits=drift,
        scaffold_only=scaffold_only,
        scaffold_reason=scaffold_reason,
        requires_emit_seam=requires_emit_seam,
        anatomy_gaps=anatomy_gaps,
    )
