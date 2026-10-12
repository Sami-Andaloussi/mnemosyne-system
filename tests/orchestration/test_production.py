"""Behavior tests for the production tissu (LOT 6) - the depth behind invariant 19 + the seams.

Pytest-hard (like ``test_runtime`` / ``test_stores``): exercises skills, projects, the
production workflow, living memory + aggregator, canal B XL + declassification, and the D65
read fusion beyond the one-slice-each the invariant suite pins. Invariant 19 is the hard
barrier (see ``test_invariants``); this is the surrounding contract. Code & docstrings English
(D117); ``public`` / ``perso`` / ``sensible`` keep their French tokens (D33 / D66).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mnemosyne.ingest import FusedAnswer, fuse
from mnemosyne.ports import (
    Bubble,
    CloisonnementError,
    DocId,
    Envelope,
    EscalateToHuman,
    Fact,
    GovernanceLabel,
    MnemosyneError,
    MonotonicityError,
    NodeId,
    Provenance,
    Sensitivity,
)
from mnemosyne.production import (
    GOLDEN_SEED,
    ActivationState,
    Aggregator,
    CanalBXL,
    CanalBXLRefused,
    Declassification,
    DeclassificationAudit,
    ExpurgationAttestation,
    Fiche,
    FicheType,
    GoldenCase,
    LivingMemory,
    Project,
    ProjectActivationRefused,
    ProjectGenerator,
    ProjectManifest,
    ProductionWorkflow,
    PromotionRefused,
    ReconciliationFlag,
    ReturnedDiff,
    ReturnPoint,
    SecuritySheet,
    SkillActivationRefused,
    SkillGenerator,
    SkillNeeds,
    TaskClass,
    ValidationState,
    facts_to_fiches,
    learning_fiche,
    load_extraction_golden,
    note_fiche,
    score_extraction,
)

PUB, PERSO, SENS = Sensitivity.PUBLIC, Sensitivity.PERSO, Sensitivity.SENSIBLE


# --- builders -------------------------------------------------------------------------
def _label(level: Sensitivity, bubble: str = "b") -> GovernanceLabel:
    return GovernanceLabel(sensitivity=level, bubble=Bubble(bubble))


def _env(payload: str, level: Sensitivity = SENS, bubble: str = "b") -> Envelope[str]:
    return Envelope(payload=payload, label=_label(level, bubble))


# ============================ skills (D36-D39 / D42 / D52) ============================
def _draft_skill(gen: SkillGenerator):
    needs = SkillNeeds(sensitivity_max=PERSO, task_class=TaskClass.ATOMIC)
    return gen.generate(name="trieur", version="0", role="file from the benne", needs=needs)


def test_a_generated_skill_starts_as_a_draft() -> None:
    skill = _draft_skill(SkillGenerator())
    assert skill.state == ActivationState.DRAFT
    assert not skill.is_active


def test_a_skill_audit_refuses_the_author_as_its_own_auditor() -> None:
    gen = SkillGenerator()
    skill = _draft_skill(gen)
    with pytest.raises(SkillActivationRefused):
        gen.audit(skill, author="alice", auditor="alice")


def test_a_skill_cannot_activate_without_being_audited_first() -> None:
    gen = SkillGenerator()
    skill = _draft_skill(gen)  # still DRAFT, never audited
    with pytest.raises(SkillActivationRefused):
        gen.activate(skill, human_validated=True)


def test_an_audited_skill_still_needs_a_human_gesture_to_activate() -> None:
    gen = SkillGenerator()
    audited = gen.audit(_draft_skill(gen), author="alice", auditor="bob")
    assert audited.state == ActivationState.AUDITED
    with pytest.raises(SkillActivationRefused):
        gen.activate(audited, human_validated=False)


def test_a_skill_goes_active_only_when_audited_and_human_validated() -> None:
    gen = SkillGenerator()
    audited = gen.audit(_draft_skill(gen), author="alice", auditor="bob")
    active = gen.activate(audited, human_validated=True)
    assert active.is_active


def test_a_skill_manifest_declares_needs_not_granted_rights() -> None:
    # D38: a skill declares needs; there is deliberately no granted-rights field.
    skill = _draft_skill(SkillGenerator())
    assert not hasattr(skill.needs, "granted_rights")
    assert skill.needs.sensitivity_max is PERSO


# ============================ projects (D49-D54) =====================================
def test_an_internet_bubble_may_hold_only_public_data() -> None:
    # anti-fuite dure (D49 / D54-1): internet + a ceiling above public cannot even exist.
    with pytest.raises(ProjectActivationRefused):
        SecuritySheet(bubble=Bubble("scraper"), ceiling=PERSO, internet=True)


def test_a_local_bubble_may_hold_sensible() -> None:
    sheet = SecuritySheet(bubble=Bubble("journal"), ceiling=SENS, internet=False)
    assert sheet.ceiling is SENS


def test_the_deny_by_default_profile_is_the_most_restrictive() -> None:
    sheet = SecuritySheet.deny_by_default(Bubble("new"))
    assert sheet.ceiling is PUB and sheet.internet is False and not sheet.domains


def test_a_project_cannot_activate_without_a_human_validated_profile() -> None:
    gen = ProjectGenerator()
    draft = gen.propose(name="quant", goal="research", bubble=Bubble("quant"))
    with pytest.raises(ProjectActivationRefused):
        gen.activate(draft, human_validated=False)


def test_a_human_validated_project_activates() -> None:
    gen = ProjectGenerator()
    draft = gen.propose(name="quant", goal="research", bubble=Bubble("quant"))
    active = gen.activate(draft, human_validated=True)
    assert active.is_active


def test_a_proposed_project_has_no_subprojects_by_default() -> None:
    draft = ProjectGenerator().propose(name="research", goal="research", bubble=Bubble("research"))
    assert draft.subprojects == ()


def test_a_subproject_is_nested_deny_by_default_and_never_inherits_parent_rights() -> None:
    # D50 / D54-2: a sub-project shares the anatomy but is SEALED - even a PERMISSIVE parent (a local
    # bubble holding `sensible`) yields a locked-down child (its own bubble, `public` ceiling, no network,
    # no domains). Nesting grants nothing and activates nothing (the child stays PAUSED).
    gen = ProjectGenerator()
    permissive_parent = ProjectManifest(
        name="research",
        goal="research",
        security=SecuritySheet(bubble=Bubble("research"), ceiling=SENS, internet=False),
    )
    parent = gen.propose_subproject(
        permissive_parent, name="ingest", goal="etl", bubble=Bubble("ingest")
    )
    assert len(parent.subprojects) == 1
    child = parent.subprojects[0]
    assert child.security == SecuritySheet.deny_by_default(
        Bubble("ingest")
    )  # NOT the parent's SENS/rights
    assert child.state == "paused"  # never auto-activated
    assert permissive_parent.subprojects == ()  # non-destructive: the original parent is untouched


def test_project_new_renders_an_honest_deny_by_default_proposal() -> None:
    # Ch.7 door: the PROPOSE surface renders the least-privilege profile and says plainly it is not live.
    from mnemosyne.runtime.project_new import render_proposal

    draft = ProjectGenerator().propose(
        name="research", goal="macro research", bubble=Bubble("research")
    )
    out = render_proposal(draft)
    assert "research" in out and "macro research" in out
    assert "deny-by-default" in out and "not activated" in out.lower()
    assert "ceiling**: public" in out and "internet**: no" in out and "domains**: none" in out


def test_archiving_is_non_destructive_and_reactivation_re_checks_policy() -> None:
    gen = ProjectGenerator()
    active = gen.activate(
        gen.propose(name="quant", goal="research", bubble=Bubble("quant")), human_validated=True
    )
    project = Project(manifest=active).archive()
    assert project.manifest.state == "archived"
    # a profile the CURRENT policy no longer permits escalates instead of silently returning.
    with pytest.raises(EscalateToHuman):
        project.reactivate(permits=lambda _sheet: False)
    # a still-permitted profile reactivates.
    back = project.reactivate(permits=lambda _sheet: True)
    assert back.manifest.is_active


# ============================ production workflow (D79 / D121-D1) =====================
def test_a_background_routine_may_draft_automatically() -> None:
    wf = ProductionWorkflow()
    draft = wf.draft(_env("brouillon", PERSO), producer="agent", automatic=True)
    assert draft.automatic is True


def test_promotion_refuses_a_self_audit() -> None:
    wf = ProductionWorkflow()
    draft = wf.draft(_env("brouillon", PERSO), producer="alice")
    with pytest.raises(PromotionRefused):
        wf.promote(draft, verifier="alice", human_validated=True)


def test_promotion_needs_a_human_gesture_even_with_a_distinct_verifier() -> None:
    wf = ProductionWorkflow()
    draft = wf.draft(_env("brouillon", PERSO), producer="alice", automatic=True)
    with pytest.raises(EscalateToHuman):
        wf.promote(draft, verifier="bob", human_validated=False)


def test_a_distinct_verifier_and_a_human_gesture_promote_the_deliverable() -> None:
    wf = ProductionWorkflow()
    draft = wf.draft(_env("brouillon", PERSO), producer="alice")
    deliverable = wf.promote(draft, verifier="bob", human_validated=True)
    assert deliverable.producer == "alice" and deliverable.verifier == "bob"
    assert deliverable.provenance.produced_by.startswith("promotion")


# ============================ living memory + aggregator (D58-D60 / D120) =============
def _fiche(fid: str, ftype: str, level: Sensitivity, bubble: str = "b") -> Fiche:
    return Fiche(id=fid, ftype=ftype, content=frozenset({"a"}), label=_label(level, bubble))


def test_updating_a_fiche_is_a_non_destructive_fusion() -> None:
    fiche = _fiche("f1", FicheType.PREFERENCE, PUB)
    updated = fiche.update(add=frozenset({"b"}), remove=frozenset({"a"}))
    assert updated.content == frozenset({"b"})  # old ∪ add − remove
    assert fiche.content in updated.history  # the removed statement survives in history
    assert updated.state == ValidationState.PROPOSED  # a re-update re-opens the gesture


def test_a_sensible_fiche_is_never_auto_validated() -> None:
    mem = LivingMemory()
    mem.propose(_fiche("f1", FicheType.PREFERENCE, SENS))
    with pytest.raises(EscalateToHuman):
        mem.validate("f1", human_validated=False)


def test_an_opinion_needs_explicit_validation_even_when_public() -> None:
    mem = LivingMemory()
    mem.propose(_fiche("op", FicheType.OPINION, PUB))
    with pytest.raises(EscalateToHuman):
        mem.validate("op", human_validated=False)


def test_a_benign_public_preference_may_auto_apply() -> None:
    mem = LivingMemory()
    mem.propose(_fiche("pref", FicheType.PREFERENCE, PUB))
    validated = mem.validate("pref", human_validated=False)
    assert validated.state == ValidationState.VALIDATED


def test_re_proposing_an_identical_fiche_is_idempotent_and_keeps_the_gesture() -> None:
    # D58 / D60-2: a re-capture IDENTICAL to a validated fiche is a NO-OP that keeps its state -
    # re-proposing the same content never silently demotes a VALIDATED fiche back to PROPOSED.
    mem = LivingMemory()
    fiche = _fiche("f", FicheType.PREFERENCE, PUB)
    mem.propose(fiche)
    mem.validate("f", human_validated=False)  # benign public preference -> validated
    again = mem.propose(fiche)  # identical re-capture
    assert again.state == ValidationState.VALIDATED  # not reset to PROPOSED (gesture preserved)
    assert [f.id for f in mem.reinject(Bubble("b"))] == ["f"]  # still reinjects


def test_re_proposing_cannot_declassify_an_existing_fiche() -> None:
    # D100-2 / invariant 17: a re-proposition is UPWARD-only. A lower-sensitivity re-capture of an
    # existing fiche is refused (never an automatic declassification), and the stored fiche stands.
    mem = LivingMemory()
    mem.propose(_fiche("f", FicheType.PREFERENCE, SENS))
    mem.validate("f", human_validated=True)  # explicit gesture (sensible)
    with pytest.raises(MonotonicityError):
        mem.propose(_fiche("f", FicheType.PREFERENCE, PUB))  # would drop sensible->public
    assert [f.id for f in mem.reinject(Bubble("b"))] == ["f"]  # the sensible fiche is untouched


def test_re_proposing_cannot_cross_bubbles_on_a_shared_id() -> None:
    # Invariant 3 / D54: two data addressing the same id in DIFFERENT bubbles never overwrite each
    # other - the second is a cloisonnement breach, not a destructive last-writer-wins.
    mem = LivingMemory()
    mem.propose(_fiche("f", FicheType.PREFERENCE, PUB, bubble="x"))
    with pytest.raises(CloisonnementError):
        mem.propose(_fiche("f", FicheType.PREFERENCE, PUB, bubble="y"))


# --- faits->fiches factory + golden-set + plan B ((3)-3c / D120 / D69 / D58) -------------
def _fact(subject: str, predicate: str, obj: str) -> Fact:
    return Fact(
        NodeId(subject),
        predicate,
        NodeId(obj),
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_score_extraction_measures_precision_and_recall() -> None:
    # (3)-3c / D69: the chiffered exit criterion. A perfect extractor clears the bar (trusted); an
    # abstaining one scores recall 0 (plan B); a hallucinating one scores precision 0 (plan B).
    cases = (GoldenCase("x", frozenset({("a", "b", "c")})),)
    assert score_extraction(lambda _t: frozenset({("a", "b", "c")}), cases).trusted
    assert not score_extraction(lambda _t: frozenset(), cases).trusted  # abstain -> recall 0
    assert score_extraction(lambda _t: frozenset({("w", "r", "g")}), cases).precision == 0.0
    assert GOLDEN_SEED and all(c.expected for c in GOLDEN_SEED)  # the seed is real, not empty (F3)
    # fail-CLOSED on a golden with nothing to find: empty, or every case expecting no triple - a
    # mis-configured golden must never vacuously certify an extractor into the graph (audit MINEUR).
    assert not score_extraction(lambda _t: frozenset(), ()).trusted
    assert not score_extraction(
        lambda _t: frozenset({("a", "b", "c")}), (GoldenCase("x", frozenset()),)
    ).trusted


def test_score_extraction_scores_a_raising_extractor_as_untrusted() -> None:
    # audit (3)-7 M1: a raising extractor is a FAILED extraction (recall loss), not an aborted run - so
    # one flaky brick on one seed yields a verdict (untrusted, plan B) instead of crashing the
    # calibration main() with a traceback (symmetric with score_fidelity's raising-reader handling).
    def raising(_content: str) -> frozenset[tuple[str, str, str]]:
        raise RuntimeError("model drift")

    score = score_extraction(raising, GOLDEN_SEED)
    assert score.f1 == 0.0 and not score.trusted  # fail-closed, never a crash


def test_score_extraction_matches_surface_variants_of_the_same_triple() -> None:
    # (3)-7 diagnostic: the real MLX extractor prints a claim in prose surface ("Low price" / "high rate
    # of return") while the golden snake-cases it ("low_price" / "high_rate_of_return"). Those are the
    # SAME extraction, and score_extraction canonicalises both sides before the overlap - so a correct
    # extractor clears the bar on SENSE, not on the spelling it happened to emit (surface ≠ a miss).
    golden = (
        GoldenCase(
            "x",
            frozenset({("low_price", "implies", "high_rate_of_return")}),
        ),
    )

    def prose(_content: str) -> frozenset[tuple[str, str, str]]:
        return frozenset({("Low price", "implies", "high rate of return")})

    score = score_extraction(prose, golden)
    assert score.precision == 1.0 and score.recall == 1.0 and score.f1 == 1.0  # a perfect match

    def hyphen(_content: str) -> frozenset[tuple[str, str, str]]:
        return frozenset({("Low-price", "implies", "high-rate-of-return")})

    assert (
        score_extraction(hyphen, golden).f1 == 1.0
    )  # hyphen/underscore/space fold to one canonical form


def test_score_extraction_normalization_stays_conservative() -> None:
    # the fold is separator/case ONLY (D69): two genuinely different words STILL score as a miss, so the
    # bar keeps biting - the normalization never fuzzes distinct senses together (no stemming, no synonyms).
    golden = (GoldenCase("x", frozenset({("low_price", "implies", "high_return")})),)
    assert (
        score_extraction(lambda _t: frozenset({("low_price", "implies", "low_return")}), golden).f1
        < 1.0
    )
    # and it never collapses a word-BOUNDARY shift across fields: ("a b","c") ≠ ("a","b c") after canon.
    from mnemosyne.production.golden import _canon_triple

    assert _canon_triple(("a b", "r", "c")) != _canon_triple(("a", "r", "b c"))
    assert _canon_triple(("Low  price", "IMPLIES", "high-rate")) == (
        "low_price",
        "implies",
        "high_rate",
    )


def test_fiche_ids_are_injective_over_bubble_and_subject() -> None:
    # audit MAJEUR: the id must not collide when a `:` in a (hierarchical) bubble name meets an
    # UNTRUSTED, content-derived subject. (bubble "a:b", subject "c") and (bubble "a", subject "b:c")
    # once forged the SAME id `a:b:c` - a cross-bubble write + gesture-erasure. Now distinct.
    from mnemosyne.production.memory import _fiche_id  # noqa: PLC0415, SLF001 - lock the private id

    assert _fiche_id(_label(PERSO, "a:b"), "c") != _fiche_id(_label(PERSO, "a"), "b:c")
    # a NOTE never collides with a subject-fiche id, even if a subject is literally named `note:<doc>`
    note = note_fiche("x", _label(PERSO, "a"), doc=DocId("d"))
    assert note.id != _fiche_id(_label(PERSO, "a"), "note:d")


def test_facts_to_fiches_namespaces_structural_and_subject_facts_apart() -> None:
    # audit MAJEUR 1 (root): the SAME subject in the "structural" namespace (a code identifier) and
    # the default "subject" namespace (a personal subject) yields DISTINCT fiche ids - so a captured
    # `def operator():` can never collide with or clobber the personal "operator" fiche.
    fact = (_fact("operator", "x", "y"),)
    [subj] = facts_to_fiches(fact, _label(PERSO), ftype=FicheType.FACT, current=lambda _i: None)
    [struct] = facts_to_fiches(
        fact, _label(PERSO), ftype=FicheType.FACT, current=lambda _i: None, kind="structural"
    )
    assert subj.id != struct.id  # disjoint id-spaces - no cross-source collision


def test_facts_to_fiches_unions_domains_on_recapture() -> None:
    # audit MINEUR (invariant 4): re-capturing a subject with a NEW domain must UNION it, never drop
    # it (else a domain-scoped statement would later read under an undeclared domain). merge unions.
    from dataclasses import replace as _replace

    from mnemosyne.ports import Domain

    base = _replace(_label(PERSO), domains=frozenset({Domain("d1")}))
    more = _replace(_label(PERSO), domains=frozenset({Domain("d2")}))
    mem = LivingMemory()
    [first] = facts_to_fiches(
        (_fact("s", "x", "y"),), base, ftype=FicheType.FACT, current=mem.current
    )
    mem.propose(first)
    [fused] = facts_to_fiches(
        (_fact("s", "x", "z"),), more, ftype=FicheType.FACT, current=mem.current
    )
    assert fused.label.domains == frozenset({Domain("d1"), Domain("d2")})  # unioned, never dropped


def test_facts_to_fiches_aggregates_by_subject() -> None:
    # (3)-3c / D120: N facts about a subject collapse into ONE fiche (de-duplication by subject);
    # distinct subjects yield distinct fiches. A first pass has nothing on file (current -> None).
    facts = (
        _fact("operator", "lives_in", "Paris"),
        _fact("operator", "likes", "tea"),
        _fact("mnemosyne", "in", "Python"),
    )
    fiches = facts_to_fiches(facts, _label(PERSO), ftype=FicheType.FACT, current=lambda _id: None)
    assert len({f.id for f in fiches}) == 2  # two subjects -> two fiches
    operator = next(f for f in fiches if any("operator" in s for s in f.content))
    assert len(operator.content) == 2  # both operator statements in one fiche
    assert all(f.state == ValidationState.PROPOSED for f in fiches)  # inert until validated (D100)


def test_facts_to_fiches_raises_a_subject_on_a_more_sensitive_recapture() -> None:
    # invariant 17 upward-only: a subject first filed PERSO, re-seen SENSIBLE, is RAISED (never stays
    # perso) and re-opened for the gesture - a fact newly known sensible can't stay filed low.
    mem = LivingMemory()
    [perso] = facts_to_fiches(
        (_fact("operator", "x", "y"),), _label(PERSO), ftype=FicheType.FACT, current=mem.current
    )
    mem.propose(perso)
    mem.validate(perso.id, human_validated=True)  # validated PERSO
    [raised] = facts_to_fiches(
        (_fact("operator", "x", "y"),), _label(SENS), ftype=FicheType.FACT, current=mem.current
    )
    assert raised.label.sensitivity is SENS  # raised upward (invariant 17)
    assert raised.state == ValidationState.PROPOSED  # re-opened for validation


def test_facts_to_fiches_is_idempotent_on_a_known_fact() -> None:
    # D58: re-seeing a KNOWN fact at the same sensitivity leaves a validated fiche UNTOUCHED (never
    # demoted) - the de-duplication that keeps the validation queue humane at ingestion scale.
    mem = LivingMemory()
    [fiche] = facts_to_fiches(
        (_fact("operator", "x", "y"),), _label(PERSO), ftype=FicheType.FACT, current=mem.current
    )
    mem.propose(fiche)
    mem.validate(fiche.id, human_validated=True)
    [again] = facts_to_fiches(
        (_fact("operator", "x", "y"),), _label(PERSO), ftype=FicheType.FACT, current=mem.current
    )
    assert again.state == ValidationState.VALIDATED  # identity fusion - the gesture is preserved


def test_a_plan_b_note_always_needs_an_explicit_human_gesture() -> None:
    # (3)-3c / D58: a plan-B `.md` NOTE is never a benign public preference - even PUBLIC it escalates,
    # so a doubtful extraction's raw dump can never auto-apply into memory (fail-closed).
    mem = LivingMemory()
    note = mem.propose(note_fiche("raw dump", _label(PUB), doc=DocId("d1")))
    assert note.ftype == FicheType.NOTE
    with pytest.raises(EscalateToHuman):
        mem.validate(note.id, human_validated=False)


def test_plan_b_note_is_bounded_not_the_whole_document() -> None:
    # audit M-2: a plan-B NOTE carries a bounded preview + a pointer, never the whole document - else a
    # validated note would overflow the answer runner when it reinjects (D136). The full text stays
    # truth-first in Moteur B.
    (packed,) = tuple(note_fiche("x" * 50_000, _label(PUB), doc=DocId("d")).content)
    assert len(packed) < 3000  # bounded, not 50k
    assert "Moteur B" in packed and "d" in packed  # a pointer to the full document
    (short,) = tuple(note_fiche("brief", _label(PUB), doc=DocId("d2")).content)
    assert short == "brief"  # a short note is unchanged


def test_a_public_reflection_still_needs_a_human_gesture() -> None:
    # the auto lane is RESTRICTED to public preferences (D59-5); user content (a reflection),
    # like any non-preference, needs an explicit gesture - fail-safe.
    mem = LivingMemory()
    mem.propose(_fiche("refl", FicheType.REFLECTION, PUB))
    with pytest.raises(EscalateToHuman):
        mem.validate("refl", human_validated=False)


# ============================ item 2 - learning_fiche (learn while using) =============
def test_learning_fiche_is_stored_whole_and_proposed() -> None:
    # unlike a plan-B NOTE (bounded preview + doc pointer), a learning has no Moteur B backup, so it is
    # stored WHOLE and lands PROPOSED as a LEARNING (inert until validated, D59).
    fiche = learning_fiche("user prefers make targets over ad-hoc scripts", _label(PERSO, "perso"))
    (stored,) = tuple(fiche.content)
    assert stored == "user prefers make targets over ad-hoc scripts"  # whole, not truncated
    assert fiche.ftype == FicheType.LEARNING and fiche.state == ValidationState.PROPOSED


def test_learning_fiche_refuses_an_over_long_learning_never_truncates() -> None:
    # a learning is stored whole with NO documentary backup, so an over-long one is REFUSED fail-closed
    # (never a dangling pointer to a doc that does not exist) - capture a document via `capture` instead.
    with pytest.raises(ValueError, match="concise"):
        learning_fiche("x" * 2001, _label(PERSO, "perso"))


def test_learning_fiche_refuses_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        learning_fiche("   ", _label(PERSO, "perso"))


def test_learning_fiche_id_is_content_scoped_so_re_proposing_is_idempotent() -> None:
    # anti-noise: the id is scoped by the CONTENT, so proposing the SAME learning twice collapses to ONE
    # queue entry (idempotent), while a DIFFERENT learning is a distinct candidate.
    mem = LivingMemory()
    mem.propose(learning_fiche("use metric units", _label(PERSO, "perso")))
    mem.propose(learning_fiche("use metric units", _label(PERSO, "perso")))  # identical -> no-op
    mem.propose(
        learning_fiche("cite doc ids in answers", _label(PERSO, "perso"))
    )  # different -> new
    assert len(mem.proposed()) == 2


def test_a_learning_never_auto_applies_always_awaits_the_gesture() -> None:
    # a LEARNING is never the benign PUBLIC PREFERENCE that may auto-apply (D59-5) - even public, it needs
    # an explicit human gesture (fail-closed on the open type set, D58).
    mem = LivingMemory()
    fiche = learning_fiche("prefer short answers", _label(PUB, "perso"))
    mem.propose(fiche)
    with pytest.raises(EscalateToHuman):
        mem.validate(fiche.id, human_validated=False)


def test_an_invalidated_fiche_cannot_be_re_validated_or_reinjected() -> None:
    mem = LivingMemory()
    mem.propose(_fiche("f", FicheType.PREFERENCE, PUB, bubble="b"))
    mem.invalidate("f")
    with pytest.raises(MnemosyneError):
        mem.validate("f", human_validated=True)
    with pytest.raises(MnemosyneError):
        mem.reinject_into(_fiche("f", FicheType.PREFERENCE, PUB, bubble="b"), Bubble("b"))


def test_validating_an_unknown_fiche_is_a_normalized_error() -> None:
    mem = LivingMemory()
    with pytest.raises(MnemosyneError):  # never a raw KeyError (D108-(2))
        mem.validate("ghost", human_validated=True)


def test_reinjection_is_bubble_scoped() -> None:
    mem = LivingMemory()
    mem.propose(_fiche("here", FicheType.PREFERENCE, PUB, bubble="b"))
    mem.propose(_fiche("there", FicheType.PREFERENCE, PUB, bubble="other"))
    mem.validate("here", human_validated=True)
    mem.validate("there", human_validated=True)
    got = mem.reinject(Bubble("b"))
    assert [f.id for f in got] == ["here"]  # never the other bubble's fiche


def test_a_cross_bubble_single_reinjection_is_refused() -> None:
    mem = LivingMemory()
    fiche = _fiche("f", FicheType.PREFERENCE, PERSO, bubble="b")
    with pytest.raises(CloisonnementError):
        mem.reinject_into(fiche, Bubble("other"))


def test_reconciliation_flags_a_contradiction_instead_of_overwriting() -> None:
    mem = LivingMemory()
    # B still asserts a claim A has invalidated => FLAG, never a silent winner (D60-3).
    with pytest.raises(ReconciliationFlag):
        mem.reconcile(invalidated_by_a=frozenset({"x"}), asserted_by_b=frozenset({"x"}))


def test_living_memory_offers_no_destructive_verb() -> None:
    # D60-2: the store closes (invalidate), it never deletes.
    verbs = {n for n in dir(LivingMemory) if not n.startswith("_")}
    assert "invalidate" in verbs
    assert not (verbs & {"delete", "remove", "destroy", "drop", "erase", "purge"})


def test_the_aggregator_proposes_it_never_imposes() -> None:
    mem = LivingMemory()
    agg = Aggregator(mem)
    fiche = _fiche("agg", FicheType.REFLECTION, PUB)
    proposal = agg.propose_aggregation("living-doc", fiche, sources=("doc1", "doc2"))
    assert proposal.fiche.state == ValidationState.PROPOSED  # never VALIDATED directly
    assert proposal.sources == ("doc1", "doc2")  # sources recorded, never deleted


# ============================ canal B XL + declassification (D90 / D102 / D107) =======
def _clean_copy(xl: CanalBXL):
    return xl.open_copy(
        batch=(_label(PUB),),
        return_point=ReturnPoint(ref="c", confirmed=True),
        attestation=ExpurgationAttestation(producer="maker", verifier="checker", clean=True),
    )


def test_a_cleared_xl_copy_has_no_git_history_and_derives_its_bubbles() -> None:
    copy = _clean_copy(CanalBXL())
    assert copy.has_git_history is False  # fresh export, not a clone (D90)
    assert copy.bubbles == frozenset({Bubble("b")})  # derived from the batch labels, not a param


def test_an_empty_xl_batch_is_refused() -> None:
    xl = CanalBXL()
    with pytest.raises(CanalBXLRefused):
        xl.open_copy(
            batch=(),
            return_point=ReturnPoint(ref="c", confirmed=True),
            attestation=ExpurgationAttestation(producer="m", verifier="c", clean=True),
        )


def test_an_unpaired_return_diff_is_refused() -> None:
    xl = CanalBXL()
    copy = _clean_copy(xl)  # its return point is "c"
    with pytest.raises(CanalBXLRefused):
        xl.merge(
            copy,
            ReturnedDiff(produced_by="frontier", payload="x", return_ref="OTHER"),
            verifier="local",
        )


def test_privilege_derivation_is_deny_by_default_and_evasion_resistant() -> None:
    from mnemosyne.production.channels import _is_privileged

    # benign ONLY for a canonical content-SHAPED path in a content root; everything the untrusted
    # frontier can rephrase into is privileged (fail-closed) - closes the naive matcher (P3) AND
    # privileged files nested under a project (P4).
    assert _is_privileged(("knowledge/notes.md",)) is False  # legit knowledge
    assert _is_privileged(("knowledge/sub/deep.md",)) is False  # knowledge at any depth
    assert _is_privileged(("projects/quant/deliverables/report.md",)) is False  # deliverable
    assert _is_privileged(("projects/quant/data/export.csv",)) is False  # project data dir
    for evasive in (
        (),  # unknown scope => privileged-until-proven-benign
        ("system/config/policy.toml",),  # plain privileged
        ("./system/config/policy.toml",),  # dot-relative rephrase
        ("/abs/system/config/policy.toml",),  # absolute
        ("System/config/policy.toml",),  # cased
        (" system/config/policy.toml",),  # leading space
        ("knowledge/../system/config",),  # traversal escape out of a content root
        (".claude/settings.json",),  # harness config outside system/
        ("CLAUDE.md",),  # root config file
        ("agents/rogue.md",),  # agent definition
        (".mcp.json",),  # MCP wiring
        ("projects/quant/skills/x.py",),  # project-local skill (D54-9)
        ("projects/p/.claude/settings.json",),  # harness config nested under a project
        ("projects/p/hooks/pre.sh",),  # a hook nested under a project
        # P4 misses: marker-free privileged files nested under a project ---------------------
        ("projects/p/system/juge.py",),  # app / Guard code nested in a project
        ("projects/p/CLAUDE.md",),  # agent steering doc (content extension, harness basename)
        ("projects/p/commands/deploy.md",),  # harness slash-command def (privileged dir)
        ("projects/p/settings.json",),  # harness settings (no marker, non-dotted)
        ("projects/p/mcp.json",),  # MCP wiring (non-dotted)
        ("projects/p/bubble.yaml",),  # bubble manifest under an alt name
        ("projects/p/Makefile",),  # build harness (no content extension)
        ("projects/p/setup.py",),  # build script (code extension)
        ("projects/q/capabilities/x.py",),  # skill dir renamed to shed the token - caught by .py
        ("projects/p/requirements.txt",),  # dependency manifest (content ext, project-root file)
        ("projects/p/security.md",),  # security sheet in a doc extension, project-root
        ("projects/p/allowlist.txt",),  # capability allowlist, project-root
        # P4 v2 misses: harness dirs / doc-manifests the deny-list enumeration forgot ----------
        ("projects/p/workflows/nightly.md",),  # workflows/ = auto-executed harness (D67 / D70)
        ("projects/p/policy/rules.md",),  # Guard policy dir
        ("projects/p/policies/egress.md",),  # plural policy dir
        ("projects/p/plugins/x.md",),  # plugin dir
        ("projects/p/settings.json.md",),  # double-extension dodge
        ("projects/p/manifest.md",),  # manifest authored as .md, project-root
        ("projects/p/CLAUDE .md",),  # trailing-space stem of the harness steering doc
        ("projects/p/report.md",),  # a project-ROOT deliverable is privileged (no content dir)
        ("projects/p/workspace/CLAUDE.md",),  # harness doc NAMED into a content dir (D-in-depth)
        ("knowledge/CLAUDE.md",),  # harness basename even under knowledge/
        ("knowledge/../projects/p/CLAUDE.md",),  # re-entry to a nested harness file
        ("knowledge/doc.md", "projects/p/system/x.py"),  # one privileged path taints the batch
        (123,),  # non-str entry => privileged, and no crash (D108-(2))
    ):
        assert _is_privileged(evasive) is True, evasive


def test_an_evasive_privileged_path_still_needs_a_human_through_merge() -> None:
    xl = CanalBXL()
    copy = _clean_copy(xl)
    # a dot-relative rephrase of a Guard-policy path must NOT sneak past the human gate.
    with pytest.raises(EscalateToHuman):
        xl.merge(
            copy,
            ReturnedDiff(
                produced_by="frontier",
                payload="x",
                return_ref="c",
                target_paths=("./system/config/policy.toml",),
            ),
            verifier="local",
            human_validated=False,
        )


def test_a_non_privileged_merge_stays_untrusted_in_origin() -> None:
    xl = CanalBXL()
    copy = _clean_copy(xl)
    merged = xl.merge(
        copy,
        ReturnedDiff(
            produced_by="frontier", payload="x", return_ref="c", target_paths=("knowledge/d.md",)
        ),
        verifier="local",
    )
    assert merged.untrusted_origin is True and merged.privileged is False
    assert merged.return_point.confirmed is True


def test_declassification_audit_needs_a_distinct_verifier() -> None:
    dec = Declassification()
    with pytest.raises(CanalBXLRefused):
        dec.audit_declassify(_env("draft", SENS), producer="alice", verifier="alice")


def test_declassify_rejects_a_self_audited_attestation() -> None:
    # Defence in depth (cloture): declassify RE-checks producer ≠ verifier, so a fabricated
    # self-audit cannot declassify even with the human gesture (symmetric with the canal-B merge).
    dec = Declassification()
    forged = DeclassificationAudit(producer="alice", verifier="alice", note="forged self-audit")
    with pytest.raises(CanalBXLRefused):
        dec.declassify(_env("draft", SENS), audit=forged, human_validated=True)


def test_declassification_never_happens_automatically() -> None:
    dec = Declassification()
    audit = dec.audit_declassify(_env("draft", SENS), producer="alice", verifier="bob")
    with pytest.raises(EscalateToHuman):
        dec.declassify(_env("draft", SENS), audit=audit, human_validated=False)


def test_a_human_gesture_declassifies_into_a_public_copy_leaving_the_original() -> None:
    dec = Declassification()
    original = _env("draft", SENS)
    audit = dec.audit_declassify(original, producer="alice", verifier="bob")
    public_copy = dec.declassify(original, audit=audit, human_validated=True)
    assert public_copy.label.sensitivity is PUB  # a fresh public copy
    assert original.label.sensitivity is SENS  # the original is untouched (non-destructive)
    assert public_copy.payload == original.payload


# ============================ aiguilleur LECTURE fusion (D65) =========================
def test_fusion_keeps_the_two_engines_side_by_side() -> None:
    living = (_env("pref", PUB, "b"),)
    documentary = (_env("fact", PUB, "b"),)
    fused = fuse(living, documentary, bubble=Bubble("b"))
    assert isinstance(fused, FusedAnswer)
    assert fused.frame == living and fused.facts == documentary  # neither overwritten


def test_fusion_carries_the_max_sensitivity() -> None:
    fused = fuse((_env("p", PERSO, "b"),), (_env("f", SENS, "b"),), bubble=Bubble("b"))
    assert fused.sensitivity is SENS  # sensible-local carried downstream (D65 / D27)


def test_fusion_is_bubble_scoped() -> None:
    foreign = (_env("leak", PERSO, "other"),)
    with pytest.raises(CloisonnementError):
        fuse(foreign, (), bubble=Bubble("b"))


def test_provenance_chains_source_audit_declassify() -> None:
    labelled = Envelope(
        payload="x",
        label=GovernanceLabel(
            sensitivity=SENS,
            bubble=Bubble("b"),
            provenance=Provenance(origin="notes", produced_by="author", at=_now()),
        ),
    )
    dec = Declassification()
    audit = dec.audit_declassify(labelled, producer="author", verifier="checker")
    public_copy = dec.declassify(labelled, audit=audit, human_validated=True)
    prov = public_copy.label.provenance
    assert prov is not None and prov.parents  # the audit step is chained in
    assert prov.parents[0].origin == "declassification-audit"  # source -> audit -> declassify (§4)


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


# --- loading a real corpus extraction golden ((3) ignition) - the gitignored JSON that expands the seed -
# Symmetric to test_stores' retrieval-golden tests. Fail-closed (F3 / D100): a malformed golden RAISES
# rather than silently yielding a laxer/empty set that could vacuously certify an extractor. The passages
# themselves live outside git (perso); these tests use synthetic temp files (form/parsing only, brick-free).


def _write_extraction_golden(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "extraction.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_extraction_golden_parses_cases(tmp_path: Path) -> None:
    path = _write_extraction_golden(
        tmp_path,
        [
            {"content": "c1", "expected": [["s1", "p1", "o1"], ["s2", "p2", "o2"]]},
            {"content": "c2", "expected": [["s3", "p3", "o3"]]},
        ],
    )
    cases = load_extraction_golden(path)
    assert isinstance(cases, tuple) and all(isinstance(c, GoldenCase) for c in cases)
    assert cases[0].content == "c1"
    assert cases[0].expected == frozenset({("s1", "p1", "o1"), ("s2", "p2", "o2")})
    assert cases[1].expected == frozenset({("s3", "p3", "o3")})


def test_load_extraction_golden_allows_empty_expected_and_extra_keys(tmp_path: Path) -> None:
    # `expected` is optional (a case with nothing to find is valid, like GoldenCase); unknown keys
    # (e.g. an inline `_note` / `_domain` / `_source`) are ignored, never a parse failure.
    path = _write_extraction_golden(
        tmp_path, [{"content": "c", "_note": "documented inline", "_domain": "finance"}]
    )
    cases = load_extraction_golden(path)
    assert cases[0].content == "c" and cases[0].expected == frozenset()


def test_loaded_extraction_golden_feeds_the_scorer_end_to_end(tmp_path: Path) -> None:
    # the wiring the ignition run uses: a loaded golden scores exactly like the seed. A perfect oracle
    # clears the bar over the loaded cases (F1 1.0), an abstaining one is fail-closed (recall 0).
    path = _write_extraction_golden(tmp_path, [{"content": "c", "expected": [["a", "b", "c"]]}])
    cases = load_extraction_golden(path)
    assert score_extraction(lambda _t: frozenset({("a", "b", "c")}), cases).trusted
    assert not score_extraction(lambda _t: frozenset(), cases).trusted


@pytest.mark.parametrize(
    "payload",
    [
        [],  # an empty golden proves nothing - a laxer set must never come from a blank file
        {"content": "c", "expected": []},  # a bare object, not a list of cases
        [{"expected": [["a", "b", "c"]]}],  # a case with no content
        [{"content": "  ", "expected": [["a", "b", "c"]]}],  # a blank content
        [{"content": "c", "expected": "nope"}],  # expected not a list
        [{"content": "c", "expected": [["a", "b"]]}],  # a triple that is not 3 parts
        [{"content": "c", "expected": [["a", "b", ""]]}],  # an empty-string part
        [{"content": "c", "expected": [["a", "b", 7]]}],  # a non-string part
    ],
)
def test_load_extraction_golden_fails_closed_on_a_malformed_file(
    tmp_path: Path, payload: object
) -> None:
    with pytest.raises(ValueError):
        load_extraction_golden(_write_extraction_golden(tmp_path, payload))


def test_load_extraction_golden_raises_on_non_json(tmp_path: Path) -> None:
    # a corrupt (non-JSON) file RAISES (JSONDecodeError is a ValueError) - never a silent empty fallback.
    path = tmp_path / "extraction.json"
    path.write_text("this is not json {", encoding="utf-8")
    with pytest.raises(ValueError):
        load_extraction_golden(path)
