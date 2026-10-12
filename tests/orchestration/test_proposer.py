"""⑤ — the autonomous proposer: propose unbidden, never impose (D119-f / D92 / D115-AV3).

Biting tests for :mod:`mnemosyne.production.proposer` and its wiring on the orchestration engine
(D93). The soul's *proactive* nerve: a background pass INSPECTS the system's own state and DEPOSITS
an unbidden proposal into the meta receptacle (surface f) for the user's return — the system coming
to the user, not only answering when asked. These prove the four structural properties:

* it PROPOSES, never promotes — the deposit sink exposes no apply verb (D92 / D100);
* a source reports a META-signal (a COUNT), never a fiche's content (invariant 22 / cloisonnement);
* one pass is BOUNDED (anti-noise / anti-runaway, D78) and NON-REPEATING (a periodic tick that keeps
  re-filing the same signal would spam);
* the whole chain runs end-to-end through the production ``CoreApi`` + engine (the real path).

Brick-free: nothing installed, deterministic stubs only (D126).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mnemosyne.api.core_api import CoreApi
from mnemosyne.production import (
    AccordChiffreReview,
    BesoinsOuvertsReview,
    AutonomousProposer,
    IntakeBacklogReview,
    LivingQueueReview,
    ProposalDraft,
    RepoTidyReview,
    VeilleReview,
)
from mnemosyne.production.memory import Fiche, FicheType, LivingMemory
from mnemosyne.ports import Bubble, GovernanceLabel, Sensitivity
from mnemosyne.runtime import bootstrap


class _SourceStub:
    """A ProposalSource that emits a scripted list of drafts (deterministic, brick-free)."""

    def __init__(self, *drafts: ProposalDraft) -> None:
        self._drafts = drafts

    def scan(self) -> tuple[ProposalDraft, ...]:
        return self._drafts


class _SinkStub:
    """A MINIMAL ProposalSink: ``submit_proposal`` + ``inbox`` ONLY — no validate / promote verb.

    That the proposer runs fully against this proves the barrier structurally (D92 / D100): the pass
    can only deposit an inert signal and read the pending queue; it has no reachable way to act on a
    proposal. A deposited signal is stored as its ``(source, summary)`` pair (satisfies PendingProposal)."""

    def __init__(self, *pending: ProposalDraft) -> None:
        self._filed: list[ProposalDraft] = list(pending)

    def submit_proposal(self, *, source: str, summary: str) -> ProposalDraft:
        deposited = ProposalDraft(source=source, summary=summary)
        self._filed.append(deposited)
        return deposited

    def inbox(self) -> tuple[ProposalDraft, ...]:
        return tuple(self._filed)


def _draft(summary: str, *, source: str = "src") -> ProposalDraft:
    return ProposalDraft(source=source, summary=summary)


def _label() -> GovernanceLabel:
    return GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("ops"))


def _proposed_memory(n: int) -> LivingMemory:
    """A living memory holding ``n`` PROPOSED fiches — the matière the queue-review source counts."""
    mem = LivingMemory()
    for i in range(n):
        mem.propose(
            Fiche(
                id=f"f{i}",
                ftype=FicheType.PREFERENCE,
                content=frozenset({f"statement {i}"}),
                label=GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("perso")),
            )
        )
    return mem


# --------------------------------------------------------------------------- #
# The proposer mechanism — deposit, bound, dedup, silence (D78 / D92).                          #
# --------------------------------------------------------------------------- #
def test_a_source_draft_is_deposited_into_the_sink() -> None:
    """The pass files a source's draft as an inert proposal — the proactive deposit (D119-f)."""
    sink = _SinkStub()
    proposer = AutonomousProposer(_SourceStub(_draft("2 fiches await your review.")))

    deposited = proposer.run(sink, max_proposals=8, nom_de_la_borne="proposer_fanout")

    assert len(deposited) == 1
    assert sink.inbox()[0].summary == "2 fiches await your review."


def test_one_pass_is_bounded_anti_noise() -> None:
    """A source with many candidates cannot flood one tick — bounded to max_proposals (D78)."""
    sink = _SinkStub()
    proposer = AutonomousProposer(_SourceStub(*(_draft(f"signal {i}") for i in range(5))))

    deposited = proposer.run(sink, max_proposals=2, nom_de_la_borne="proposer_fanout")

    assert len(deposited) == 2
    assert len(sink.inbox()) == 2  # the other three were NOT filed this pass


def test_a_signal_already_awaiting_review_is_not_refiled() -> None:
    """Non-repeating: an identical (source, summary) already pending is skipped (no periodic spam)."""
    already = _draft("2 fiches await your review.", source="queue")
    sink = _SinkStub(already)  # it is already in the inbox, unreviewed
    proposer = AutonomousProposer(
        _SourceStub(_draft("2 fiches await your review.", source="queue"))
    )

    deposited = proposer.run(sink, max_proposals=8, nom_de_la_borne="proposer_fanout")

    assert deposited == ()  # nothing new
    assert len(sink.inbox()) == 1  # still just the original — never doubled


def test_a_changed_signal_is_a_new_proposal() -> None:
    """A DIFFERENT summary (the count changed) is legitimately new — dedup is exact, not blanket."""
    sink = _SinkStub(_draft("2 fiches await your review.", source="queue"))
    proposer = AutonomousProposer(
        _SourceStub(_draft("3 fiches await your review.", source="queue"))
    )

    deposited = proposer.run(sink, max_proposals=8, nom_de_la_borne="proposer_fanout")

    assert len(deposited) == 1
    assert len(sink.inbox()) == 2


def test_silent_sources_deposit_nothing() -> None:
    """Every source empty ⇒ nothing filed — silence is correct, the pass manufactures no noise."""
    sink = _SinkStub()
    proposer = AutonomousProposer(_SourceStub(), _SourceStub())

    assert proposer.run(sink, max_proposals=8, nom_de_la_borne="proposer_fanout") == ()
    assert sink.inbox() == ()


def test_multiple_sources_all_contribute() -> None:
    """The pass scans every source in turn (bounded across all of them)."""
    sink = _SinkStub()
    proposer = AutonomousProposer(
        _SourceStub(_draft("a", source="s1")), _SourceStub(_draft("b", source="s2"))
    )

    deposited = proposer.run(sink, max_proposals=8, nom_de_la_borne="proposer_fanout")

    assert len(deposited) == 2
    assert {p.source for p in sink.inbox()} == {"s1", "s2"}


def test_a_non_positive_bound_is_a_noop() -> None:
    """A zero / negative ceiling deposits nothing (defensive) — never a silent unbounded pass."""
    sink = _SinkStub()
    proposer = AutonomousProposer(_SourceStub(_draft("x")))

    assert proposer.run(sink, max_proposals=0, nom_de_la_borne="proposer_fanout") == ()
    assert sink.inbox() == ()


def test_an_intra_pass_duplicate_is_deposited_once() -> None:
    """Two sources emitting the SAME (source, summary) in ONE pass deposit it once (dedup, D78)."""
    sink = _SinkStub()
    same = _draft("2 fiches await your review.", source="queue")
    proposer = AutonomousProposer(_SourceStub(same), _SourceStub(same))

    deposited = proposer.run(sink, max_proposals=8, nom_de_la_borne="proposer_fanout")

    assert len(deposited) == 1
    assert len(sink.inbox()) == 1  # the second source's identical draft was skipped


def test_the_bound_spans_all_sources() -> None:
    """The per-pass ceiling counts deposits ACROSS sources, not per source — bounded globally (D78).

 The TOTAL is always bounded to ``max_proposals``: that is the anti-runaway property, and
 it is intact. What changed on 2026-09-08 is WHO occupies the last slot when the
 bound cuts — see :func:`test_une_troncature_se_DECLARE_au_lieu_de_se_taire`."""
    sink = _SinkStub()
    proposer = AutonomousProposer(
        _SourceStub(_draft("a1", source="s1"), _draft("a2", source="s1")),
        _SourceStub(_draft("b1", source="s2"), _draft("b2", source="s2")),
    )

    deposited = proposer.run(sink, max_proposals=3, nom_de_la_borne="proposer_fanout")

    assert len(deposited) == 3  # never more, regardless of the number of sources
    assert {"a1", "a2"} <= {p.summary for p in sink.inbox()}


def test_une_troncature_se_DECLARE_au_lieu_de_se_taire() -> None:
    """ A source that a bound cuts reads EXACTLY like a source that has nothing to say.

 MEASURED on 2026-09-08: the tick carried 12 productive sources for a bound of 8. Wiring
 the two lot-2 sources (`P6`, `P8`) silenced two others — in silence, that very day.
 *An EXCLUDED population is UNJUDGED, never safe.*"""
    sink = _SinkStub()
    proposer = AutonomousProposer(
        _SourceStub(_draft("a1", source="s1"), _draft("a2", source="s1")),
        _SourceStub(_draft("b1", source="s2"), _draft("b2", source="s2")),
    )

    deposited = proposer.run(sink, max_proposals=3, nom_de_la_borne="proposer_fanout")

    aveux = [p for p in deposited if "NOT VISITED" in p.summary or "CUT" in p.summary]
    assert len(aveux) == 1, "the bound cut and did not say so"
    assert "CUT" in aveux[0].summary  # the bound fell WITHIN the last source
    assert (
        "proposer_fanout" in aveux[0].summary
    )  # it NAMES the REAL bound, hence the line to open


def test_l_aveu_distingue_une_source_NON_VISITEE_d_un_signal_COUPE() -> None:
    """ Two ignorances of different natures, and conflating them would lie in one direction.

 Of a signal cut in a source ALREADY scanned, we know it existed. Of a source never
 queried, we don't know **even whether it had something to say** — and asserting it would
 require scanning it, i.e. paying exactly the cost the bound exists to avoid."""
    sink = _SinkStub()
    proposer = AutonomousProposer(
        _SourceStub(
            _draft("a1", source="s1"), _draft("a2", source="s1"), _draft("a3", source="s1")
        ),
        _SourceStub(_draft("b1", source="s2")),
        _SourceStub(_draft("c1", source="s3")),
    )

    (aveu,) = [
        p
        for p in proposer.run(sink, max_proposals=2, nom_de_la_borne="proposer_fanout")
        if "CUT" in p.summary or "NOT VISITED" in p.summary
    ]

    assert "1 signal(s) CUT" in aveu.summary  # a3: seen in s1, already scanned, never retained
    assert "2 source(s) NOT VISITED" in aveu.summary  # s2 and s3: never called, cost avoided


def test_une_source_NON_VISITEE_n_est_JAMAIS_appelee() -> None:
    """ THE COST IS THE VERY REASON THIS BEHAVIOUR EXISTS, SO IT GETS TESTED.

 An earlier version scanned ALL sources before depositing, in order to publish a count of
 signals cut. An isolated audit measured the price: **9,087 ms per tick**, so on every
 session start — of which 7,954 ms for the ONE source the bound happened to cut off.
 *A remedy that costs 9 s at startup is worse than the defect it fixes.*"""
    appels: list[str] = []

    class _Compteuse:
        def __init__(self, nom: str) -> None:
            self._nom = nom

        def scan(self) -> tuple[ProposalDraft, ...]:
            appels.append(self._nom)
            return (_draft(f"x-{self._nom}", source=self._nom),)

    proposer = AutonomousProposer(_Compteuse("s1"), _Compteuse("s2"), _Compteuse("s3"))
    proposer.run(_SinkStub(), max_proposals=1, nom_de_la_borne="proposer_fanout")

    assert appels == ["s1"], f"sources beyond the bound were paid for: {appels}"


def test_l_aveu_ne_se_RE_DEPOSE_pas_a_chaque_passe() -> None:
    """ MEASURED BY AN ISOLATED AUDIT: 5 rounds -> 5 identical admissions stacked in the receptacle.

 v1 appended the admission AFTER the dedup loop, so it escaped `seen`. The method's docstring
 nonetheless promised that *"a PERIODIC pass never re-files an identical, still-unread
 signal"* — it was contradicting itself."""
    sink = _SinkStub()
    sources = (
        _SourceStub(_draft("a1", source="s1")),
        _SourceStub(_draft("b1", source="s2")),
        _SourceStub(_draft("c1", source="s3")),
    )
    proposer = AutonomousProposer(*sources)

    for _ in range(4):
        proposer.run(sink, max_proposals=2, nom_de_la_borne="proposer_fanout")

    aveux = [p for p in sink.inbox() if "NOT VISITED" in p.summary or "CUT" in p.summary]
    assert len(aveux) == 1, f"{len(aveux)} admissions stacked after 4 passes"


def test_sans_troncature_AUCUN_aveu_n_est_depose() -> None:
    """The counter-proof: without it, this witness would only measure my ability to always confess."""
    sink = _SinkStub()
    proposer = AutonomousProposer(_SourceStub(_draft("a1", source="s1")))

    deposited = proposer.run(sink, max_proposals=8, nom_de_la_borne="proposer_fanout")

    assert len(deposited) == 1
    assert all("NOT VISITED" not in p.summary and "CUT" not in p.summary for p in deposited)


def test_une_troncature_a_UN_SEUL_creneau_rend_l_aveu_SEUL() -> None:
    """The edge case: `max_proposals=1` and two candidates in the same source. The admission takes
    the only slot — better to know you see nothing than to believe you see everything."""
    sink = _SinkStub()
    proposer = AutonomousProposer(_SourceStub(_draft("a1", source="s1"), _draft("a2", source="s1")))

    deposited = proposer.run(sink, max_proposals=1, nom_de_la_borne="proposer_fanout")

    assert len(deposited) == 1
    assert "1 signal(s) CUT" in deposited[0].summary


# --------------------------------------------------------------------------- #
# LivingQueueReview — the first real source: a COUNT, never content (invariant 22).             #
# --------------------------------------------------------------------------- #
def test_living_queue_review_reports_a_count() -> None:
    """It signals HOW MANY fiches await review — a meta pointer, never a fiche's content."""
    (draft,) = LivingQueueReview(lambda: 3).scan()
    assert "3 fiches" in draft.summary
    assert "review" in draft.summary.lower()


def test_living_queue_review_uses_the_singular_for_one() -> None:
    """One fiche reads 'fiche', not 'fiches' — the signal is human-facing (D115-AV3)."""
    (draft,) = LivingQueueReview(lambda: 1).scan()
    assert "1 fiche " in draft.summary
    assert "awaits" in draft.summary  # singular agreement, not "await" (user-facing, NIT)
    assert "fiches" not in draft.summary


def test_living_queue_review_is_silent_when_empty() -> None:
    """An empty queue says nothing — no queue, nothing to propose (no noise)."""
    assert LivingQueueReview(lambda: 0).scan() == ()


# --------------------------------------------------------------------------- #
# IntakeBacklogReview (Q2) — the raw-intake sas DEPTH: a count, never a name (invariant 22).      #
# --------------------------------------------------------------------------- #
def test_intake_backlog_review_reports_a_count_and_points_to_domain_new() -> None:
    """It signals HOW MANY sources sit un-homed and names the remedy (D46) — a meta pointer, never a name."""
    (draft,) = IntakeBacklogReview(lambda: 3).scan()
    assert "3 sources" in draft.summary
    assert (
        "domain-new" in draft.summary
    )  # the human gesture to give the theme a taxonomy home (D46)


def test_intake_backlog_review_uses_the_singular_for_one() -> None:
    (draft,) = IntakeBacklogReview(lambda: 1).scan()
    assert "1 source " in draft.summary and "sits" in draft.summary
    assert "sources" not in draft.summary  # singular agreement, human-facing


def test_intake_backlog_review_is_silent_when_the_sas_is_empty() -> None:
    """An empty intake sas says nothing — nothing un-homed, nothing to propose (no noise)."""
    assert IntakeBacklogReview(lambda: 0).scan() == ()


# --------------------------------------------------------------------------- #
# VeilleReview (Q5) — how many distilled fiches await a veille pass: a count, never a fiche.       #
# --------------------------------------------------------------------------- #
def test_veille_review_reports_a_count_and_points_to_make_veille() -> None:
    """It signals HOW MANY fiches await veille and names the remedy — a meta pointer, never content."""
    (draft,) = VeilleReview(lambda: 5).scan()
    assert "5 distilled fiches" in draft.summary
    assert "make veille" in draft.summary  # the frontier agent's governed mining pass (Q5)


def test_veille_review_uses_the_singular_for_one() -> None:
    (draft,) = VeilleReview(lambda: 1).scan()
    assert "1 distilled fiche " in draft.summary and "awaits" in draft.summary
    assert "fiches" not in draft.summary  # singular agreement, human-facing


def test_veille_review_is_silent_when_the_corpus_is_surveyed() -> None:
    """Every fiche surveyed ⇒ nothing to mine, nothing to propose (no noise)."""
    assert VeilleReview(lambda: 0).scan() == ()


# --------------------------------------------------------------------------- #
# RepoTidyReview (item 3) — the propose-to-automate nerve: a count of CLEAR cruft, never a path.  #
# --------------------------------------------------------------------------- #
def test_repo_tidy_review_reports_a_count_and_points_to_make_rangement() -> None:
    """It signals HOW MANY clear-cruft files sit in the repo and names the automation — never a path."""
    (draft,) = RepoTidyReview(lambda: 4).scan()
    assert "4 clear-cruft files" in draft.summary
    assert (
        "make rangement" in draft.summary
    )  # the non-destructive, reversible automation (D74 / D92)


def test_repo_tidy_review_uses_the_singular_for_one() -> None:
    (draft,) = RepoTidyReview(lambda: 1).scan()
    assert "1 clear-cruft file " in draft.summary and "sits" in draft.summary
    assert "files" not in draft.summary  # singular agreement, human-facing


def test_repo_tidy_review_is_silent_when_the_repo_is_clean() -> None:
    """No clear cruft ⇒ nothing to tidy, nothing to propose (no noise — the repo is already navigable)."""
    assert RepoTidyReview(lambda: 0).scan() == ()


# --------------------------------------------------------------------------- #
# The production path — ⑤ wired on the engine, through CoreApi (D93 / D119-f).                  #
# --------------------------------------------------------------------------- #
def test_prod_path_proposer_deposits_a_queue_review_into_the_inbox() -> None:
    """schedule_work + run_background run ⑤ as MANAGED work; the receptacle gets the unbidden signal."""
    api = CoreApi(replace(bootstrap(), living_memory=_proposed_memory(2)))
    wid = api.schedule_work("autonomous_proposer", label=_label())

    assert wid in api.run_background().completed
    inbox = api.inbox()
    assert len(inbox) == 1
    assert "2 fiches" in inbox[0].summary
    assert inbox[0].reviewed is False  # inert until the user's review — proposed, never imposed (D92)


def test_prod_path_proposer_is_silent_on_an_empty_queue() -> None:
    """With nothing pending the pass still COMPLETEs (healthy), but deposits nothing (no noise)."""
    api = CoreApi(replace(bootstrap(), living_memory=_proposed_memory(0)))
    wid = api.schedule_work("autonomous_proposer", label=_label())

    assert wid in api.run_background().completed
    assert api.inbox() == ()


def test_prod_path_proposer_does_not_spam_across_ticks() -> None:
    """Two periodic ticks over the same pending queue leave ONE proposal — non-repeating (D78)."""
    api = CoreApi(replace(bootstrap(), living_memory=_proposed_memory(2)))

    api.schedule_work("autonomous_proposer", label=_label())
    api.run_background()
    api.schedule_work("autonomous_proposer", label=_label())
    api.run_background()

    assert (
        len(api.inbox()) == 1
    )  # the second tick re-filed nothing — the signal was already pending


def test_prod_path_proposer_watches_the_intake_sas_when_wired() -> None:
    """Q2: with a raw-intake counter wired, the pass deposits the un-homed-backlog nudge (D46)."""
    api = CoreApi(
        replace(bootstrap(), living_memory=_proposed_memory(0)), intake_backlog_count=lambda: 3
    )
    wid = api.schedule_work("autonomous_proposer", label=_label())

    assert wid in api.run_background().completed
    inbox = api.inbox()
    assert len(inbox) == 1
    assert "3 sources" in inbox[0].summary and "domain-new" in inbox[0].summary
    assert inbox[0].reviewed is False  # inert until the user's review — proposed, never imposed (D92)


def test_prod_path_proposer_ignores_the_intake_when_not_wired() -> None:
    """Zero regression: no intake counter wired ⇒ the intake source is absent (only the queue runs)."""
    api = CoreApi(
        replace(bootstrap(), living_memory=_proposed_memory(0))
    )  # no intake_backlog_count
    wid = api.schedule_work("autonomous_proposer", label=_label())
    # the pass COMPLETES healthy (a None counter would build IntakeBacklogReview(None) → scan raises →
    # the job would FAIL, not complete): this asserts the absent-source guard, so the test bites alone.
    assert wid in api.run_background().completed
    assert api.inbox() == ()  # empty queue + no intake source ⇒ nothing deposited


def test_prod_path_proposer_runs_both_the_queue_and_the_intake_sources() -> None:
    """Queue + intake both non-empty ⇒ both meta-signals deposited (within the fanout bound, D78)."""
    api = CoreApi(
        replace(bootstrap(), living_memory=_proposed_memory(2)), intake_backlog_count=lambda: 4
    )
    api.schedule_work("autonomous_proposer", label=_label())
    api.run_background()

    summaries = " || ".join(p.summary for p in api.inbox())
    assert "2 fiches" in summaries and "4 sources" in summaries  # both sources fired


def test_prod_path_proposer_watches_the_corpus_when_veille_is_wired() -> None:
    """Q5: with a distilled-corpus counter wired, the pass deposits the veille nudge (`make veille`)."""
    api = CoreApi(
        replace(bootstrap(), living_memory=_proposed_memory(0)), unsurveyed_count=lambda: 7
    )
    wid = api.schedule_work("autonomous_proposer", label=_label())

    assert wid in api.run_background().completed
    inbox = api.inbox()
    assert len(inbox) == 1
    assert "7 distilled fiches" in inbox[0].summary and "make veille" in inbox[0].summary
    assert inbox[0].reviewed is False  # inert until the user's review — proposed, never imposed (D92)


def test_prod_path_proposer_ignores_the_corpus_when_veille_is_not_wired() -> None:
    """Zero regression: no corpus counter wired ⇒ the veille source is absent (the None guard bites)."""
    api = CoreApi(replace(bootstrap(), living_memory=_proposed_memory(0)))  # no unsurveyed_count
    wid = api.schedule_work("autonomous_proposer", label=_label())
    # a None counter would build VeilleReview(None) → scan raises → the job would FAIL, not complete;
    # asserting completion proves the absent-source guard, so this test bites alone under that mutation.
    assert wid in api.run_background().completed
    assert api.inbox() == ()  # empty queue + no veille source ⇒ nothing deposited


def test_prod_path_proposer_watches_the_repo_when_rangement_is_wired() -> None:
    """Item 3: with a repo-cruft counter wired, the pass deposits the propose-to-automate nudge (`make rangement`)."""
    api = CoreApi(
        replace(bootstrap(), living_memory=_proposed_memory(0)), repo_cruft_count=lambda: 6
    )
    wid = api.schedule_work("autonomous_proposer", label=_label())

    assert wid in api.run_background().completed
    inbox = api.inbox()
    assert len(inbox) == 1
    assert "6 clear-cruft files" in inbox[0].summary and "make rangement" in inbox[0].summary
    assert inbox[0].reviewed is False  # inert until the user's review — proposed, never imposed (D92)


def test_prod_path_proposer_ignores_the_repo_when_rangement_is_not_wired() -> None:
    """Zero regression: no repo-cruft counter wired ⇒ the repo-tidy source is absent (the None guard bites)."""
    api = CoreApi(replace(bootstrap(), living_memory=_proposed_memory(0)))  # no repo_cruft_count
    wid = api.schedule_work("autonomous_proposer", label=_label())
    # a None counter would build RepoTidyReview(None) → scan raises → the job would FAIL, not complete;
    # asserting completion proves the absent-source guard, so this test bites alone under that mutation.
    assert wid in api.run_background().completed
    assert api.inbox() == ()  # empty queue + no repo-tidy source ⇒ nothing deposited


# --------------------------------------------------------------------------- #
# AccordChiffreReview / BesoinsOuvertsReview — the TWO lot-2 sources, and the   #
# only ones that run on EVERY session start.                                   #
# --------------------------------------------------------------------------- #
def test_accord_chiffre_review_publie_le_COMPTE_des_desaccords() -> None:
    """ What crosses is a COUNT, never a document excerpt (inv. 22)."""
    (draft,) = AccordChiffreReview(lambda: 3).scan()
    assert "3 live copy(ies)" in draft.summary
    assert "accord-chiffre" in draft.summary  # it NAMES the target that refuses


def test_accord_chiffre_review_se_TAIT_a_zero_desaccord() -> None:
    """ Mutation: the silence clause removed -> SURVIVED before this witness.

 A repo in agreement must not produce noise on every startup: *a check that speaks up
 when everything is fine stops being read when things go wrong.*"""
    assert AccordChiffreReview(lambda: 0).scan() == ()


def test_accord_chiffre_review_se_tait_aussi_quand_l_INSTRUMENT_est_muet() -> None:
    """`None` = "I was not able to look." The tick PUBLISHES, it does not refuse: the refusal lives
    in `make accord-chiffre`, which has its own rc. Shouting here would make an alarm nobody can
    turn off at a session's startup."""
    assert AccordChiffreReview(lambda: None).scan() == ()


def test_besoins_review_publie_le_COMPTE_et_JAMAIS_le_contenu() -> None:
    """ inv. 22, and here it really bites: **a need can name the user's own data.**"""
    (draft,) = BesoinsOuvertsReview(lambda: 2).scan()
    assert "2 open need(s)" in draft.summary
    assert "make besoins" in draft.summary  # the address to read them, never their text
    assert "PIVOT" in draft.summary  # what distinguishes this channel from a plain queue


def test_besoins_review_se_TAIT_quand_la_file_est_vide() -> None:
    """ Mutation of the silence clause -> SURVIVED before this witness."""
    assert BesoinsOuvertsReview(lambda: 0).scan() == ()
    assert BesoinsOuvertsReview(lambda: None).scan() == ()


def test_les_deux_sources_du_lot_2_deposent_sous_la_MEME_source() -> None:
    """They are both follow-throughs on another project: their `source` must tie them back to the harvest, or
    a reader cannot trace a proposal back to the registry entry that authorized it."""
    (a,) = AccordChiffreReview(lambda: 1).scan()
    (b,) = BesoinsOuvertsReview(lambda: 1).scan()
    assert a.source == b.source


def test_la_PHRASE_publiee_est_lue_pas_seulement_ses_donnees() -> None:
    """ Mutation: the phrase replaced by a sabotage string -> SURVIVED before this witness.

 *The witnesses read the DATA that feeds the phrase, never the phrase itself.* This is
 corollary #1 of this lot's contract, and it had been violated on its own two sources."""
    (draft,) = BesoinsOuvertsReview(lambda: 7).scan()
    assert draft.summary.startswith("7 open need(s)")
    assert "awaiting a decision" in draft.summary


# --------------------------------------------------------------------------- #
# THE PROPOSER'S CEILING — its DEDICATED key, and the historical borrowing as a fallback. #
# --------------------------------------------------------------------------- #
#
# Written after an isolated adversarial review (D75/D159) that refused a request to widen
# `agent_fanout` from 8 to 14. Its finding: this bound carries the name and comment of an
# ANTI-RUNAWAY guard (inv. 7), and raising it to widen a DISPLAY pre-authorizes a real agent
# fan-out the day someone wires it under its name.
class _PolicyStub:
    def __init__(self, bornes: dict[str, int]) -> None:
        self._bornes = bornes

    def bound(self, nom: str) -> int:
        return self._bornes[nom]  # KeyError if absent — the repo's fail-closed default


def test_le_plafond_prend_la_cle_DEDIEE_quand_elle_existe() -> None:
    from mnemosyne.api.core_api import _plafond_du_proposeur

    assert _plafond_du_proposeur(_PolicyStub({"proposer_fanout": 15, "agent_fanout": 8})) == (
        15,
        "proposer_fanout",
    )


def test_le_plafond_RETOMBE_sur_l_emprunt_historique() -> None:
    """The fallback exists so this code runs BOTH BEFORE AND AFTER the dedicated key is written into
    the protected zone. *A fix that requires a human gesture to avoid breaking is a fix
    that breaks* — and that gesture is one only the user can make."""
    from mnemosyne.api.core_api import _plafond_du_proposeur

    assert _plafond_du_proposeur(_PolicyStub({"agent_fanout": 8})) == (8, "agent_fanout")


def test_sans_AUCUNE_des_deux_bornes_le_fail_closed_est_INTACT() -> None:
    """ The counter-proof, and it is what protects the fallback from being a backdoor.

 *An unbounded resource is a bug, never a silent defect*: a fallback that returned an
 invented number when nothing is configured would turn the fail-closed into a fail-open, in silence."""
    from mnemosyne.api.core_api import _plafond_du_proposeur

    with pytest.raises(KeyError):
        _plafond_du_proposeur(_PolicyStub({}))


def test_la_cle_DEDIEE_et_son_REPLI_sont_deux_noms_DISTINCTS() -> None:
    """If the two constants carried the same name, the three witnesses above would all pass
    while measuring a single key — and the borrowing we just undid would have come back through the window."""
    from mnemosyne.api.core_api import _PROPOSER_FANOUT_BOUND, _PROPOSER_FANOUT_REPLI

    assert _PROPOSER_FANOUT_BOUND == "proposer_fanout"
    assert _PROPOSER_FANOUT_REPLI == "agent_fanout"
    assert _PROPOSER_FANOUT_BOUND != _PROPOSER_FANOUT_REPLI


def test_l_aveu_nomme_la_borne_REELLEMENT_lue_jamais_une_constante() -> None:
    """ IT HARD-NAMED `agent_fanout` — measured by an isolated adversarial review.

 With `proposer_fanout = 4` in effect, the tick used to publish verbatim
 *"the bound `agent_fanout` (4) stopped this pass"*: **wrong key, and a value that
 key does not carry**. This is the ONE sentence whose written role is to name the wall to
 move — it was sending the reader to the wrong line of `policy.toml`.

 And three assertions in this file PINNED the stale name: fixing the sentence would have
 turned them red. *A witness that freezes a false constant defends the very fault it should catch.*
 """
    sink = _SinkStub()
    proposer = AutonomousProposer(
        _SourceStub(_draft("a1", source="s1"), _draft("a2", source="s1")),
        _SourceStub(_draft("b1", source="s2")),
    )

    deposited = proposer.run(sink, max_proposals=1, nom_de_la_borne="une_borne_inventee")

    (aveu,) = [p for p in deposited if "NOT VISITED" in p.summary or "CUT" in p.summary]
    assert "une_borne_inventee" in aveu.summary, (
        "the sentence does not name the bound it was passed"
    )
    assert "agent_fanout" not in aveu.summary, "a hard-coded name survived in the sentence"


def test_LE_SITE_D_APPEL_de_production_passe_par_le_resolveur() -> None:
    """ THE GAP THE REVIEW NAMED AS THE MOST SERIOUS: nothing forced `CoreApi` to read the
 approved key. Putting `policy.bound("agent_fanout")` back hard-coded at the call site left **57
 green witnesses** — the key the user had just approved via a live gesture was held by nothing.

 The resolver returns a **pair** `(value, name)` precisely so this workaround no longer
 compiles. This witness records it, because a property only the signature defends
 disappears at the first refactor that "simplifies" a type."""
    from pathlib import Path

    from mnemosyne.api import core_api

    source = Path(core_api.__file__).read_text(encoding="utf-8")
    corps = source[source.find("def _workflow_autonomous_proposer") : source.find("def costs")]

    assert "_plafond_du_proposeur(" in corps, "the call site no longer calls the resolver"
    assert "nom_de_la_borne=" in corps, "the call site no longer passes the bound's name"
    for interdit in ('bound("agent_fanout")', "bound('agent_fanout')", 'bound("proposer_fanout")'):
        assert interdit not in corps, f"a bound is re-read HARD-CODED at the call site: {interdit}"


def test_le_resolveur_rend_le_NOM_avec_la_valeur() -> None:
    """The counter-proof of the witness above: if the resolver went back to being a plain integer,
    the workaround would become invisible again — and the text witness above, alone, would not say so."""
    from mnemosyne.api.core_api import _plafond_du_proposeur

    valeur, nom = _plafond_du_proposeur(_PolicyStub({"proposer_fanout": 15, "agent_fanout": 8}))
    assert (valeur, nom) == (15, "proposer_fanout")
    valeur, nom = _plafond_du_proposeur(_PolicyStub({"agent_fanout": 8}))
    assert (valeur, nom) == (8, "agent_fanout")


def test_une_panne_AUTRE_qu_une_cle_absente_se_PROPAGE() -> None:
    """ SURVIVING MUTATION at the reviewer's: `except KeyError` → `except Exception`, and
 **679 witnesses stayed green**.

 The difference is not theoretical. `KeyError` says *"this key is not configured"* — a
 normal fact, which the fallback exists to absorb. Any OTHER exception says *"the policy is
 broken"* (unreadable file, invalid TOML, corrupted protected zone): absorbing it would silently
 fall back to the historical borrowing, and the system would run on a bound nobody
 approved while believing it read the config.

 *An `except` that is too broad turns a fail-closed into a fail-open, without changing a single value.*
 """

    class _PolicyCasseeSurLaPremiere:
        """ It RAISES on the dedicated key and ANSWERS on the fallback — that is what makes the
 witness discriminating. A stub that raises on BOTH would let the error propagate even with
 an `except Exception`, and the witness would then be measuring its own stub, not the code.
 *Test the DIFFERENTIATION, never mere conformity.*"""

        def bound(self, nom: str) -> int:
            if nom == "proposer_fanout":
                raise RuntimeError("policy.toml unreadable")
            return 8

    from mnemosyne.api.core_api import _plafond_du_proposeur

    with pytest.raises(RuntimeError):
        _plafond_du_proposeur(_PolicyCasseeSurLaPremiere())


def test_une_cle_ABSENTE_est_bien_absorbee_elle() -> None:
    """The counter-proof: without it, the witness above would be satisfied by a removed `except` —
    and the fallback, which is this function's whole reason for existing, would disappear without turning red."""
    from mnemosyne.api.core_api import _plafond_du_proposeur

    assert _plafond_du_proposeur(_PolicyStub({"agent_fanout": 8})) == (8, "agent_fanout")
