"""The autonomous proposer (⑤) — the *proactive* nerve: propose unbidden, never impose.

Mnémosyne's soul is not only "an assistant you query": it also comes to the user of its own accord.
This module is that nerve — a background pass that INSPECTS the system's own state and DEPOSITS a
proposal in the meta receptacle (surface f, D119) for the user's return. It runs on the orchestration
engine (D93) as a registered workflow; a real cron / watcher that fires it on a cadence is
just-in-time (D67), today a CLI / test tick drives it (the same governed path).

Three properties are structural, not optional:

* **Propose, NEVER auto-promote (D92 / D100).** The proposer is handed a NARROW :class:`ReceptacleSink`
  that exposes ONLY ``submit_proposal`` (deposit an INERT proposal) and ``inbox`` (read what awaits) —
  never the fuller facade behind them. A validate / promote / review verb is therefore unreachable at
  RUNTIME (``.review`` raises ``AttributeError``), so the barrier is STRUCTURAL, not a convention of
  this module's code: the human gesture (``review``) is the only thing that ever acts on a proposal.
* **A meta-signal, never the matière (invariant 22 / D66 / cloisonnement).** A :class:`ProposalSource`
  reports a COUNT or a POINTER — never the content of the data it watched. :class:`LivingQueueReview`
  is handed a ``pending_count`` callable returning an ``int``, so it structurally cannot read (or
  leak) a fiche's content across a bubble boundary.
* **Bounded + non-repeating (D78 / invariant 16).** One pass deposits at most ``max_proposals``
  proposals (anti-noise, the same anti-runaway floor the scheduler and engine carry), and it never
  re-files a signal identical to one already awaiting review — a periodic pass does not spam.

The sources are PORTS, injected at wiring (:meth:`~mnemosyne.api.core_api.CoreApi._workflow_autonomous_proposer`
assembles the concrete ones). The first real source, :class:`LivingQueueReview`, is the proactive
bridge from the PASSIVE validation queue (``LivingMemory.proposed()`` — fiches the user must go and
consult) to the ACTIVE receptacle (the system taps the user on the shoulder). Its MECHANISM is proven
brick-free here against deterministic stubs (D126). Richer sources are LATER impls of the same
:class:`ProposalSource` port — a by-subject aggregator over living documents (D120, once the graph
is fed), a "distill an un-distilled book" pass over the corpus (③), the show→propose→learn memory
loop (D115-AV3) — each a new source, not a change to this loop. Code & docstrings English (D117).

Decisions: D119-f (the meta receptacle) · D92 / D100 (propose, never auto-loosen) · D115-AV3
(show → propose → correct) · D120 (aggregator → living documents) · D67 (background régime) · D78 /
invariant 16 (bounded, anti-runaway) · invariant 22 / D66 (no secret / cloisonnement) · D93 (runs on
the orchestration engine).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Protocol

#: Stable ``source`` tag for the living-memory queue-review proposals (the audit trail / dedup key).
_LIVING_QUEUE_SOURCE = "autonomous-proposer · living-memory queue review"
#: Stable ``source`` tag for the raw-intake backlog proposals (the audit trail / dedup key).
_INTAKE_BACKLOG_SOURCE = "autonomous-proposer · raw-intake backlog"
#: Stable ``source`` tag for the corpus-veille proposals (the audit trail / dedup key).
_VEILLE_SOURCE = "autonomous-proposer · corpus veille"
#: Stable ``source`` tag for the repo-tidy proposals (the audit trail / dedup key).
_REPO_TIDY_SOURCE = "autonomous-proposer · repo tidy"
#: Stable ``source`` tag for the field-signalement proposals (the audit trail / dedup key).
_SIGNALEMENT_SOURCE = "autonomous-proposer · signalements terrain"

#: WHAT LIFTS A LINE OUT OF THE PROPOSAL RANKS. The tick files everything under "propose, never
#: impose" (D92) — that is fair for what it INVENTS, and wrong for what a THIRD PARTY has observed. A
#: signalement in stasis is not a suggestion from the system: it is a debt filed by a project that
#: had to work around a defect to keep going. This prefix is the only thing
#: :func:`~mnemosyne.runtime.tick.render_proposals` looks at to lift it out of the block.
#: This is a PROMOTION, never a refusal: nothing here forces a session to drain the queue (A2).
DETTE_PREFIX: Final = "\U000026D4 DEBT — "
_DOCUMENTS_SOURCE = "autonomous-proposer · documents orphelins"
#: The inert-proposal queue — what the system DEPOSITED and nobody has looked at yet.
_PROPOSAL_QUEUE_SOURCE = "autonomous-proposer · propositions inertes"
#: Open parentheses — detours running beside a plan, each owing it a return (the audit trail / dedup key).
_PARENTHESE_SOURCE = "autonomous-proposer · parentheses ouvertes"
#: Closed plan arcs that never harvested anything back into the system (I2, the audit trail / dedup key).
_MOISSON_SOURCE = "autonomous-proposer · moissons dues"


@dataclass(frozen=True, slots=True)
class ProposalDraft:
    """A candidate proposal a :class:`ProposalSource` emits — a meta-signal, never the matière.

    ``source`` names the behaviour proposing (recorded on the audit trail, D119-f); ``summary`` is
    the human-facing signal. Both are META (a count, a pointer) — NEVER the content of the data the
    source watched (invariant 22 / cloisonnement). The pair also IS the dedup identity: two passes
    that would say exactly the same thing deposit it once (see :meth:`AutonomousProposer.run`)."""

    source: str
    summary: str


class ProposalSource(Protocol):
    """A watcher over some slice of the system's state that PROPOSES when it has something to say.

    :meth:`scan` returns the drafts to deposit this pass — EMPTY when there is nothing to report
    (silence is correct; a source must not manufacture noise). A source reports a meta-signal only
    (a count / pointer), never the content it watched (invariant 22 / D66)."""

    def scan(self) -> tuple[ProposalDraft, ...]:
        """The candidate proposals right now — possibly empty (nothing to say)."""
        ...


class PendingProposal(Protocol):
    """The read view of a proposal already awaiting review — just enough to dedup against it.

    Structural (:class:`~mnemosyne.api.core_api.Proposal` satisfies it) so this module never imports
    the facade (no ``production`` ⇄ ``api`` cycle): the proposer reads only ``source`` / ``summary``."""

    source: str
    summary: str


class ProposalSink(Protocol):
    """Where the proposer DEPOSITS — and ONLY deposits (D92 / D100).

    Exposes ``submit_proposal`` (file an inert proposal, D119-f) and ``inbox`` (read what still
    awaits review, to dedup) — and NO validate / promote / apply verb. The concrete
    :class:`ReceptacleSink` closes over exactly those two callables of the facade, so at runtime the
    proposer is incapable of acting on a proposal (that is the user's ``review`` gesture, unreachable)."""

    def submit_proposal(self, *, source: str, summary: str) -> object:
        """Deposit an INERT meta/transverse proposal (D119-f) — never applied until review."""
        ...

    def inbox(self) -> tuple[PendingProposal, ...]:
        """The proposals still awaiting the user's review — read to avoid re-filing a duplicate."""
        ...


@dataclass(frozen=True, slots=True)
class ReceptacleSink:
    """A NARROW :class:`ProposalSink` over a receptacle's deposit + read callables (D92 / D100).

    The proposer is handed THIS — closing over ONLY a ``deposit`` and a ``pending`` callable — never
    the fuller facade that owns them. A promote / validate / review verb is thus unreachable at
    RUNTIME (``.review`` raises ``AttributeError``), making the propose-never-impose barrier
    STRUCTURAL rather than a convention of the pass's code. The facade
    (:class:`~mnemosyne.api.core_api.CoreApi`) builds one from its own ``submit_proposal`` / ``inbox``."""

    deposit: Callable[..., object]
    pending: Callable[[], tuple[PendingProposal, ...]]

    def submit_proposal(self, *, source: str, summary: str) -> object:
        return self.deposit(source=source, summary=summary)

    def inbox(self) -> tuple[PendingProposal, ...]:
        return self.pending()


class AutonomousProposer:
    """The proactive pass (⑤): scan the sources, deposit new signals, bounded and non-repeating.

    Holds only its :class:`ProposalSource` ports (injected at wiring). :meth:`run` is one pass — a
    :data:`~mnemosyne.runtime.engine.WorkflowFn` closes over it and the engine drives the cadence
    (D93). It NEVER promotes: it can only deposit through the :class:`ProposalSink` it is handed,
    which exposes no apply verb (D92 / D100)."""

    __slots__ = ("_sources",)

    def __init__(self, *sources: ProposalSource) -> None:
        self._sources = sources

    def run(
        self, sink: ProposalSink, *, max_proposals: int, nom_de_la_borne: str
    ) -> tuple[object, ...]:
        """One proactive pass: deposit at most ``max_proposals`` NEW signals into ``sink`` (D78).

        Bounded (anti-runaway, D78 / invariant 16): the pass stops at ``max_proposals`` deposits —
        across ALL sources — so a source that reports many candidates cannot flood the receptacle in
        one tick. Non-repeating: a draft whose ``(source, summary)`` is ALREADY awaiting review, or
        was already deposited earlier IN THIS pass, is skipped — the pending inbox is the single
        source of truth, so a PERIODIC pass never re-files an identical, still-unread signal (no
        cross-tick hidden state to drift).

        The dedup is against STILL-PENDING proposals: if the user dismisses a signal (``review``) while
        its condition genuinely still holds, a later pass resurfaces it — a deliberate recurring
        reminder, not spam. Returns the deposited proposals (possibly empty — every source was
        silent, or every candidate was already pending)."""
        if max_proposals <= 0:
            return ()
        # dedup against what already awaits review — the pending inbox is the only state consulted.
        seen = {(p.source, p.summary) for p in sink.inbox()}
        retenus: list[ProposalDraft] = []
        non_visitees = 0
        coupes_connus = 0
        for rang, source in enumerate(self._sources):
            if len(retenus) >= max_proposals:
                non_visitees = len(self._sources) - rang
                break
            for draft in source.scan():
                signature = (draft.source, draft.summary)
                if signature in seen:
                    continue  # already awaiting review (or just filed this pass) — never a duplicate
                if len(retenus) >= max_proposals:
                    # This source has ALREADY been scanned: finishing the count of its candidates is
                    # free, and it is information of a different NATURE than `non_visitees` --
                    # here we KNOW how many we are cutting, there we don't even know if there was something.
                    coupes_connus += 1
                    continue
                seen.add(signature)
                retenus.append(draft)
        # WE STOP AT THE BOUND, AND WE COUNT THE SOURCES WE DID NOT QUERY.
        # An earlier version of this fix scanned ALL sources before depositing, in order to
        # publish the number of SIGNALS cut. An isolated audit measured the price: **9,087 ms** of
        # scan on every tick, so on every session start -- of which 7,954 ms for the ONE
        # source the bound happened to cut off. *A remedy that costs 9 s at startup is worse than
        # the defect it fixes.*
        #
        # WHAT WE PUBLISH CHANGES NATURE, AND IT IS MORE HONEST: SOURCES not visited, not
        # signals cut. We ignore what they would have said -- precisely because we did not
        # query them; asserting it would require paying the 9 s.
        #
        # AND THIS COUNT IS STABLE, which closes a second defect measured by the same audit:
        # v1's admission was appended AFTER the dedup loop, so it was RE-DEPOSITED on every pass --
        # 5 rounds, 5 identical admissions stacked up. It now goes through `seen` like everything else.
        #
        # THE BOUND ITSELF IS NOT TOUCHED: it lives in `system/config/policy.toml`
        # (`proposer_fanout`, or `agent_fanout` as a fallback), a wall only a human gesture
        # moves. *A wall DECLARES itself* (D159) -- and it declares itself BY ITS REAL NAME: the
        # sentence receives `nom_de_la_borne` from the caller, never a constant written here. An
        # isolated review measured the cost of the reverse: it hard-named `agent_fanout`, so it
        # sent the reader to the wrong line of policy.toml. --
        # the admission takes the LAST slot, and the total deposited stays exactly `max_proposals`.
        if non_visitees or coupes_connus:
            morceaux = []
            if coupes_connus:
                morceaux.append(f"{coupes_connus} signal(s) CUT")
            if non_visitees:
                morceaux.append(f"{non_visitees} source(s) NOT VISITED")
            aveu = ProposalDraft(
                source="proposer",
                summary=(
                    f"\U000026D4 {' and '.join(morceaux)} — the bound `{nom_de_la_borne}` "
                    f"({max_proposals}) "
                    "stopped this pass. This is NOT silence: for a source not visited, we don't "
                    "even know what it would have said. The bound lives in "
                    "`system/config/policy.toml` and only a human gesture moves it."
                ),
            )
            retenus = [*retenus[: max_proposals - 1], aveu]
        deposited = [sink.submit_proposal(source=d.source, summary=d.summary) for d in retenus]
        return tuple(deposited)


class LivingQueueReview:
    """⑤'s first real source: watch the living-memory validation queue, report its DEPTH (D59-4).

    The proactive bridge from the PASSIVE queue (``LivingMemory.proposed()`` — fiches the user must go
    and consult) to the ACTIVE receptacle (surface f). It is handed a ``pending_count`` callable
    returning an ``int``: it reports HOW MANY fiches await review, never WHICH or their content, so
    it structurally cannot leak a fiche across the cloisonnement (invariant 22 / D66). Silent when
    the queue is empty (no queue, nothing to say). If the user dismisses the nudge while fiches still
    await, a later pass resurfaces it — the condition genuinely still holds (a recurring reminder)."""

    __slots__ = ("_pending_count",)

    def __init__(self, pending_count: Callable[[], int]) -> None:
        self._pending_count = pending_count

    def scan(self) -> tuple[ProposalDraft, ...]:
        pending = self._pending_count()
        if pending <= 0:
            return ()  # empty queue — silence, not noise
        noun = "fiche" if pending == 1 else "fiches"
        verb = "awaits" if pending == 1 else "await"
        return (
            ProposalDraft(
                source=_LIVING_QUEUE_SOURCE,
                summary=(
                    f"{pending} {noun} {verb} your review in the living-memory validation "
                    "queue (D59-4)."
                ),
            ),
        )


class IntakeBacklogReview:
    """⑤'s taxonomy nerve (Q2): watch the raw-intake sas DEPTH and propose giving its items a home.

    The proactive bridge from the PASSIVE ``knowledge/raw/_intake`` basket — where triage parks a
    SOURCE it could not shelve under any declared taxonomy domain (D85 / D137), never lost, never
    mis-filed — to the ACTIVE receptacle (surface f). It is handed an ``unshelved_count`` callable
    returning an ``int``: it reports HOW MANY sources sit un-homed, never WHICH, nor their names or
    content, so it structurally cannot leak matière across the cloisonnement (invariant 22 / D66).

    The remedy it points to is ``make domain-new`` (D46): creating a taxonomy branch stays a HUMAN
    gesture — the proposer proposes the ACT of giving the theme a home, it never edits the taxonomy
    itself (propose, never impose, D92). Silent when the sas is empty (nothing to say). If the user
    dismisses the nudge while items still sit un-homed, a later pass resurfaces it — the condition
    genuinely still holds (a recurring reminder, not spam)."""

    __slots__ = ("_unshelved_count",)

    def __init__(self, unshelved_count: Callable[[], int]) -> None:
        self._unshelved_count = unshelved_count

    def scan(self) -> tuple[ProposalDraft, ...]:
        pending = self._unshelved_count()
        if pending <= 0:
            return ()  # empty intake sas — silence, not noise
        noun = "source" if pending == 1 else "sources"
        verb = "sits" if pending == 1 else "sit"
        return (
            ProposalDraft(
                source=_INTAKE_BACKLOG_SOURCE,
                summary=(
                    f"{pending} {noun} {verb} un-homed in the raw-intake sas with no taxonomy "
                    "domain — consider `make domain-new` to give the theme a home, or place them "
                    "(D46 / D137)."
                ),
            ),
        )


class VeilleReview:
    """⑤'s veille nerve (Q5): watch how many distilled fiches were NEVER surveyed for principles/skills.

    The proactive bridge from the distilled CORPUS to the ACTIVE receptacle (surface f) — the richest
    source of the proactive nerve. It is handed an ``unsurveyed_count`` callable returning an ``int``: it
    reports HOW MANY fiches still await a veille pass, never WHICH, nor a word of their content, so it
    structurally cannot leak matière across the cloisonnement (invariant 22 / D66).

    The remedy it points to is ``make veille``. The rich extraction is deliberately NOT this source's job:
    per the cohabitation doctrine, reading matière with the subtlety to distil a real principle is the
    FRONTIER master's act (Claude Code), not a local scan — so the source only NUDGES, and a frontier
    agent then reads a batch under the Guard, extracts principles / skills / hypotheses, and DEPOSITS each
    as an INERT draft for the user's review (propose, never impose, D92). Silent when every fiche is surveyed
    (no corpus-to-mine, nothing to say). If the user dismisses the nudge while un-surveyed fiches remain, a
    later pass resurfaces it — the condition genuinely still holds (a recurring reminder, not spam)."""

    __slots__ = ("_unsurveyed_count",)

    def __init__(self, unsurveyed_count: Callable[[], int]) -> None:
        self._unsurveyed_count = unsurveyed_count

    def scan(self) -> tuple[ProposalDraft, ...]:
        pending = self._unsurveyed_count()
        if pending <= 0:
            return ()  # every fiche surveyed — silence, not noise
        noun = "fiche" if pending == 1 else "fiches"
        verb = "awaits" if pending == 1 else "await"
        return (
            ProposalDraft(
                source=_VEILLE_SOURCE,
                summary=(
                    f"{pending} distilled {noun} {verb} a veille pass — run `make veille` to have a "
                    "frontier agent mine principles / skills / hypotheses from the corpus (inert "
                    "drafts, propose-never-impose)."
                ),
            ),
        )


class RepoTidyReview:
    """⑤'s propose-to-automate nerve (item 3): watch the repo for the CLEAR cruft the rangement skill automates.

    The first concrete incarnation of the autonomy nerve the user named — recognise a repetitive, automatable
    chore and PROPOSE the automation UNBIDDEN, without being asked (item 3). It is handed a ``cruft_count``
    callable returning an ``int``: how many files the DETERMINISTIC rangement scan
    (:func:`mnemosyne.production.rangement.clear_cruft_count`, deny-by-default, ``NEVER_TOUCH``-guarded) can
    name as clear cruft right now. It reports HOW MANY, never WHICH nor a path (a count, a meta-signal), so
    it structurally cannot leak matière across the cloisonnement (invariant 22 / D66) — and by construction
    the scan only ever sees the PATHS of clear cruft, never the content of a source of truth (those are
    ``NEVER_TOUCH``).

    The remedy it points to is ``make rangement`` (dry-run by default) — a REVERSIBLE, non-destructive
    quarantine, never a delete (emptying the quarantine stays the user's gesture, D74). Propose, never impose
    (D92): the nerve NUDGES, it never tidies on its own. The BROADER judgment — noticing a NEW recurring
    automatable request and proposing a whole new skill — is deliberately NOT this scan's job; like veille's
    rich mining, that is the FRONTIER master's act (the self-reminding essence memo, item 6), not a
    deterministic count. Silent when the repo is clean at the deterministic grain (nothing to say). If the user
    dismisses the nudge while clear cruft remains, a later pass resurfaces it — the condition genuinely still
    holds (a recurring reminder, not spam)."""

    __slots__ = ("_cruft_count",)

    def __init__(self, cruft_count: Callable[[], int]) -> None:
        self._cruft_count = cruft_count

    def scan(self) -> tuple[ProposalDraft, ...]:
        pending = self._cruft_count()
        if pending <= 0:
            return ()  # repo clean at the deterministic grain — silence, not noise
        noun = "file" if pending == 1 else "files"
        verb = "sits" if pending == 1 else "sit"
        return (
            ProposalDraft(
                source=_REPO_TIDY_SOURCE,
                summary=(
                    f"{pending} clear-cruft {noun} {verb} in the repo — run `make rangement` to "
                    "quarantine them (reversible, non-destructive, dry-run by default; D74 / D92)."
                ),
            ),
        )


class DocumentsOrphelinsReview:
    """A3's nerve: watch for documents NOTHING points at any more — the tsunami's early warning.

    The user named the tsunami precisely: documents produced once, never tidied, never reused, until
    the repo becomes illegible. The one-off cleanup is workstream 2; THIS source is what stops it coming
    back on its own, by making the condition surface unbidden instead of waiting for someone to
    think of looking. Measured on 2026-08-09: 4 documents out of 79 tracked, two of them FOUR DAYS
    OLD — it reforms continuously, so the answer is a permanent detector, not a sweep.

    A COUNT, never a path (invariant 22 / D66), exactly like its `RepoTidyReview` sibling. The
    remedy it names — `make documents` — is READ-ONLY and moves nothing: archiving is a judgment on
    a document's worth, and moving the user's files is their gesture (D74). Silent at zero.
    """

    __slots__ = ("_orphan_count",)

    def __init__(self, orphan_count: Callable[[], int]) -> None:
        self._orphan_count = orphan_count

    def scan(self) -> tuple[ProposalDraft, ...]:
        pending = self._orphan_count()
        if pending <= 0:
            return ()  # every tracked document is cited — silence, not noise
        noun = "document" if pending == 1 else "documents"
        verb = "is no longer cited" if pending == 1 else "are no longer cited"
        return (
            ProposalDraft(
                source=_DOCUMENTS_SOURCE,
                summary=(
                    f"{pending} {noun} in the repo {verb} by anything — `make documents` "
                    f"names them (read-only, moves NOTHING; A3 / D74). *A document that "
                    f"nothing points to does not exist.*"
                ),
            ),
        )


class SignalementReview:
    """The field-report nerve: surface what a PROJECT session filed against Mnemosyne itself.

    The first real project (the research project) runs ON Mnemosyne and will hit its defects. Two failure
    modes are designed out here: the project session derailing into repairing the system (wrong
    context, wrong mandate), and the user becoming the messenger who diagnoses "project or system?" and
    relays it by hand. The project FILES a signalement in the repo and keeps producing; THIS source
    is what makes the queue come to the user unbidden, through the same nerve as every other proposal
    rather than a second, parallel one.

    It is handed a ``signalement_count`` callable returning an ``int``: how many reports still carry
    ``status: ouvert`` (:func:`mnemosyne.production.signalements.open_signalement_count`). It reports
    HOW MANY — never a title, never a path (a count, a meta-signal) — which matters more here than
    for its siblings, since the filing session works inside ANOTHER project's context (invariant 22 /
    D66).

    Silent when nothing is filed (silence is correct, not a gap). Draining is a Mnemosyne session's
    act and FLIPS a status, never deletes the report (invariant 2) — so the queue goes quiet on its
    own with nothing destroyed. Propose, never impose (D92): this nudges, it never repairs.

    **WHAT THE 2026-09-08 MEASUREMENT CHANGED HERE.** This source used to publish the COUNT alone,
    and it published it on every startup — while **12 reports stayed open, the oldest 27 days**. The
    field report concluded from this "the drain has NO trigger"; that was wrong, and the truth is
    worse: *it had one, it was speaking, and nobody moved.* Two causes, both fixed here, neither of
    them being "publish more":

    1. **The count states the SIZE, never the STASIS.** "12 open" reads like a healthy queue;
       "the oldest is 27 days old" reads like a failure. Same data, two descriptions, only one
       triggers a gesture — hence :func:`~mnemosyne.production.signalements.oldest_open_signalement_age_days`.
    2. **A signal filed among options IS an option.** The line used to appear in the middle of seven
       proposals under the header *"propose, never impose"*, indistinguishable from a tidying
       suggestion. But a signalement is NOT a proposal from this system: it is a **debt a third
       party has observed**. The :data:`DETTE_PREFIX` prefix therefore LIFTS it out of the
       proposals block via :func:`~mnemosyne.runtime.tick.render_proposals`.

    **What this still does NOT do, stated rather than discovered**: nothing here REFUSES
    anything. A session can read the line and disregard it — that is a stronger signal, never a
    barrier (A2). The threshold below is a readability convention, not a guarantee."""

    #: Past this many days, the oldest report is no longer a queue: it is STASIS, and the line
    #: comes out of the proposal ranks. 7 days = one full work-week during which a project worked
    #: around a defect nobody looked at. This threshold decides the PROMOTION, never what is
    #: published: below the threshold, the report is still surfaced.
    STASE_JOURS: Final = 7

    __slots__ = ("_signalement_count", "_oldest_age_days")

    def __init__(
        self,
        signalement_count: Callable[[], int],
        oldest_age_days: Callable[[], int | None] | None = None,
    ) -> None:
        self._signalement_count = signalement_count
        #: Optional so every existing caller keeps working: an absent age degrades to the old
        #: count-only line rather than raising. A missing age must never SILENCE the signal.
        self._oldest_age_days = oldest_age_days

    def scan(self) -> tuple[ProposalDraft, ...]:
        pending = self._signalement_count()
        if pending <= 0:
            return ()  # nothing filed against the system — silence, not noise
        noun = "field signalement" if pending == 1 else "field signalements"
        age = self._oldest_age_days() if self._oldest_age_days is not None else None
        if age is None:
            # No age available — say so plainly rather than inventing one, and keep the old line.
            corps = (
                f"{pending} {noun} awaiting a Mnémosyne session (age not measured) — "
                "`make signalements` says what a project flagged as broken (a project FILES, it "
                "never repairs; D92)."
            )
            return (ProposalDraft(source=_SIGNALEMENT_SOURCE, summary=corps),)
        jour = "day" if age <= 1 else "days"
        corps = (
            f"{pending} {noun} awaiting, **the oldest is {age} {jour} old** — "
            "`make signalements` says what a project flagged as broken (a project FILES, it never "
            "repairs; D92). Draining = fixing AND recording the lesson; the report is never deleted."
        )
        # Past the staleness threshold this stops being a proposal and becomes a debt: the prefix is
        # what lifts it out of the "propose, never impose" block, where it was being read as optional.
        return (
            ProposalDraft(
                source=_SIGNALEMENT_SOURCE,
                summary=(f"{DETTE_PREFIX}{corps}" if age >= self.STASE_JOURS else corps),
            ),
        )


class ProposalQueueReview:
    """The RETURN path of the ``proposals`` surface — what the system deposited, unseen.

    ``make describe`` advertises "receive non-solicited proposals and review them". The deposit
    half worked: the veilleur mines the distilled corpus into inert drafts, and an agent can file a
    candidate skill the same way. The return half did not exist — eight drafts sat correctly filed
    and permanently invisible until a project session filed a signalement about it. This source
    closes that loop, through the SAME nerve as its five siblings rather than a parallel one.

    It is handed a ``proposal_count`` callable returning an ``int``: how many drafts still carry
    ``status: draft`` (:func:`mnemosyne.production.proposals.open_proposal_count`). It reports HOW
    MANY and nothing else — and here the discipline bites hardest of all six: a proposal's body is
    mined from the user's own library and can name a personal source, so the count is the only thing
    allowed to cross (invariant 22 / D66).

    Silent when the queue is empty. Reviewing flips a status, never deletes a draft (invariant 2),
    so the nudge goes quiet on its own — the alternative, a counter with no way to clear it, is the
    perpetual false alarm ``veille_ledger`` already warns about. Propose, never impose (D92): this
    surfaces the queue, it never promotes anything out of it."""

    __slots__ = ("_proposal_count",)

    def __init__(self, proposal_count: Callable[[], int]) -> None:
        self._proposal_count = proposal_count

    def scan(self) -> tuple[ProposalDraft, ...]:
        pending = self._proposal_count()
        if pending <= 0:
            return ()  # nothing deposited, or everything reviewed — silence is correct
        noun = "inert proposal" if pending == 1 else "inert proposals"
        verb = "awaits" if pending == 1 else "await"
        return (
            ProposalDraft(
                source=_PROPOSAL_QUEUE_SOURCE,
                summary=(
                    f"{pending} {noun} {verb} your review — run `make proposals` to read what the "
                    "veille and the agents deposited (inert drafts; reviewing is not promoting, D92)."
                ),
            ),
        )


class ParentheseReview:
    """The forgotten-detour nerve (C8-c): watch how many parentheses are running beside a plan.

    A parenthèse is work opened IN THE MARGIN of a plan — a question that surfaces, a detour that
    has to be taken. The user's own words name the failure it must not have: *"no scraps left
    behind, no debt left lingering."* A detour nobody remembers is exactly that, and unlike its
    five siblings this queue has a SECOND way to rot: a parenthèse can close cleanly and still leave
    its debt behind (measured on the research project — file closed, decision never executed). Closing is where
    that half is refused in code; THIS source only handles the first half — being forgotten while
    still open.

    It is handed a ``parenthese_count`` callable returning an ``int``: how many carry
    ``status: ouverte`` (:func:`mnemosyne.production.parentheses.open_parenthese_count`). It reports
    HOW MANY — never a title, never the plan it departs from (invariant 22 / D66), which matters for
    the same reason it does on signalements: a detour is opened from inside whatever context was
    being worked, and its title can name it.

    Silent when nothing is open (silence is correct — no detour running is the normal state). The
    nudge goes quiet on its own the moment each one is closed, and closing flips a status rather
    than deleting the file (invariant 2), so no "alarm nobody can clear" is created here."""

    __slots__ = ("_parenthese_count",)

    def __init__(self, parenthese_count: Callable[[], int]) -> None:
        self._parenthese_count = parenthese_count

    def scan(self) -> tuple[ProposalDraft, ...]:
        pending = self._parenthese_count()
        if pending <= 0:
            return ()  # no detour running — silence, not noise
        noun = "parenthèse is" if pending == 1 else "parenthèses are"
        return (
            ProposalDraft(
                source=_PARENTHESE_SOURCE,
                summary=(
                    f"{pending} {noun} still open beside a plan — run `make parentheses` to see what "
                    "each one still owes its plan (closing without naming the return is refused)."
                ),
            ),
        )


class DeriveReview:
    """`D1` — whether the plan is drifting toward its own machinery, measured over the project's RECENT window.

    **IT DOES NOT PUBLISH THE FROZEN WINDOW FROM `(c1)`**, and that is what keeps it from being noise:
    a July swing is closed forever, so republishing it on every tick would be *an alarm nobody
    can turn off* — the failure `ProposalQueueReview` flags and that `I2` avoids.

    **WHAT CROSSES IS A SHARE AND TWO DATES**, never a file path or a step title: the
    measurement is a **statistic of the monitored repo**, not its content.

    **NO THRESHOLD** — it returns the largest drop the series carries, whatever it is.
    `D1` forbids a date or a threshold living in the detector; this source does not add one
    at the edge. *A detector calibrated on the answer detects nothing.*

    Silent when the recent window carries no commit — today's state."""

    __slots__ = ("_resume",)

    def __init__(self, resume: Callable[[], str | None]) -> None:
        self._resume = resume

    def scan(self) -> tuple[ProposalDraft, ...]:
        phrase = self._resume()
        if not phrase:
            return ()  # nothing moved in the monitored window — silence, not noise
        return (ProposalDraft(source=_MOISSON_SOURCE, summary=phrase),)


class CandidatSansPanneReview:
    """`I3(b)` — a harvest proposes a rule WITHOUT declaring the MEASURED failure it avoids.

    **THIS SOURCE EXISTS SO THAT A GATE STOPS BEING DECORATIVE.**
    :mod:`~mnemosyne.production.regle_candidate` was built for `I3(a)`, and its own author
    measured, **at the very top of their own audit mandate**, that *"as it stands it refuses
    nothing to anyone: it refuses IF IT IS CALLED, and nothing calls it."* This is the chain that calls it.

    **WHAT CROSSES IS A HARVEST FILE NAME**, never its content nor the text of the
    proposed rule — the same mechanical distinction as its sibling below, and the same bound
    (``moisson_due.NOMS_MAX``). A harvest that declares badly points at itself; it does not get copied.

    **LEVEL 1, AND THIS IS THE INHERITED `I2` DECISION**: *a forced harvest manufactures
    candidates*. It publishes, it refuses nothing. The **level 2** half of `I3`
    (``exiger_panne_declaree``, which RAISES) still has **no call site at all** — measured: zero
    real harvest in the registry, and the proof chain takes a skill name, not a fiche. *A
    measured admission is a valid answer; a gate resting on an assumed call site is the fault we close.*

    Silent when every harvest declares its failure — and silent too when there is no
    harvest at all, which is the state of the registry today."""

    __slots__ = ("_resume",)

    def __init__(self, resume: Callable[[], str | None]) -> None:
        self._resume = resume

    def scan(self) -> tuple[ProposalDraft, ...]:
        phrase = self._resume()
        if not phrase:
            return ()  # every harvest declares its failure — silence, not noise
        return (ProposalDraft(source=_MOISSON_SOURCE, summary=phrase),)


class SitesDeSortieReview:
    """`G1` — an exit site appeared in `system/lib/` WITHOUT being declared.

    **THE GAP THIS SOURCE FLAGS IS NAMED IN THE PROJECT'S OWN GOVERNANCE DOC**: outside the
    library, nothing structurally stops an `import requests` from reaching the network. The research project built
    this barrier while the doctrine still only documented its absence; this is the follow-through on
    its mechanism (harvest of 2026-09-08, G1).

    **WHAT CROSSES IS A `file::module`** -- a source path and a standard-library module name, never
    a line of code nor data (inv. 22). Bounded like its siblings.

    **LEVEL 1 HERE, LEVEL 2 ELSEWHERE**: the tick PUBLISHES (its rc is discarded), the
    `make sites-de-sortie` target REFUSES with rc=1. *A check that merely prints is not a gate* -- both
    exist, and this source is the half that makes the other reachable at the moment of acting."""

    __slots__ = ("_resume",)

    def __init__(self, resume: Callable[[], str | None]) -> None:
        self._resume = resume

    def scan(self) -> tuple[ProposalDraft, ...]:
        phrase = self._resume()
        if not phrase:
            return ()  # the freeze holds — silence, not noise
        return (ProposalDraft(source=_MOISSON_SOURCE, summary=phrase),)


class AccordChiffreReview:
    """`P6` — a number CALCULATED and copied into prose has drifted from its calculation.

    **THE REFERENCE IS RECOMPUTED, NEVER RE-READ.** The module hard-codes no `27`: it
    counts the numbered entries of the repository's governing constitution document. *A reference derived from the checked value can
    refute nothing* — this is the exact fault this source exists to make impossible.

    **WHAT CROSSES IS A COUNT**, never a document excerpt (inv. 22): the number of
    LIVE copies in disagreement. Zero disagreement = silence.

    **LEVEL 1 HERE**: the tick publishes, `make accord-chiffre` refuses. Follow-through on the
    research project's harvest of 2026-09-08 (item `P6`) — measured that day: the invariant count was copied
    **41 times across 30 tracked files**, and `derives.py` already admitted no barrier covered
    it."""

    __slots__ = ("_compter",)

    def __init__(self, compter: Callable[[], int | None]) -> None:
        self._compter = compter

    def scan(self) -> tuple[ProposalDraft, ...]:
        n = self._compter()
        if not n:
            return ()  # zero disagreement, or a silent instrument: the refusal lives in the target, not here
        return (
            ProposalDraft(
                source=_MOISSON_SOURCE,
                summary=(
                    f"\U000026D4 figure agreement: {n} live copy(ies) disagree with the calculation. "
                    "`make accord-chiffre` names each site — a total that agrees on one side and is "
                    "wrong on the other is the real case, not the hypothesis."
                ),
            ),
        )


class BesoinsOuvertsReview:
    """`P8` — needs are awaiting a decision, and nobody sees them.

    **A NEED THAT IS NOT PUBLISHED IS A DISGUISED STOP.** The channel exists so that a chat
    can file what it cannot decide alone **and then PIVOT**; if you have to go read it to find out
    it is waiting, the pivot becomes a wait. This source is the half that makes the channel real.

    **WHAT CROSSES IS A COUNT**, never the content of a need (inv. 22) — a need can
    name the user's own data.

    **LEVEL 1**: it publishes, it refuses nothing. Follow-through on the research project's harvest of
    2026-09-08 (item `P8`) — measured that day: **48 tracked `.md` files** carried a wait on a
    gesture from the user, with no status, no date, no drain."""

    __slots__ = ("_compter",)

    def __init__(self, compter: Callable[[], int | None]) -> None:
        self._compter = compter

    def scan(self) -> tuple[ProposalDraft, ...]:
        n = self._compter()
        if not n:
            return ()
        return (
            ProposalDraft(
                source=_MOISSON_SOURCE,
                summary=(
                    f"{n} open need(s) are awaiting a decision — `make besoins` names them. "
                    "Each one carries its PIVOT: what its author did WHILE WAITING."
                ),
            ),
        )


class MoissonEnAttenteReview:
    """`I2-bis` — a harvest RETAINED candidates, and nothing has ever put them to the test.

    **THIS SOURCE EXISTS BECAUSE THE REGISTRY LOST A TOOL, AND THAT IS MEASURED.** Its sibling
    :class:`MoissonDueReview` listens for the EXISTENCE of an entry — it goes quiet as soon as an arc
    has its own, *"not a queue to drain,"* and that is the right choice for what it measures. But it
    makes **two silences** indistinguishable: *nothing to report* and *something written that nobody
    will ever read again*. On 2026-09-08: the candidate RETAINED on 2026-08-17, recorded at its
    official home with the measurement still to produce and described as *an absence on both sides
    of the repo*, had never been re-read — **the research project rebuilt it alone 16 days later** while Mnemosyne
    still did not have it. *The very mechanism meant to make the item visible was making it
    invisible forever.*

    **WHAT CROSSES IS A HARVEST FILE NAME**, never a candidate's title nor a
    line from its file — the same mechanical distinction as its siblings, the same bound
    (``moisson_due.NOMS_MAX``).

    **LEVEL 1, AND THIS IS THE INHERITED `I2` DECISION**: *a forced harvest manufactures
    candidates* — and a forced test would manufacture tests. It NAMES what is dormant; it
    refuses nothing, writes nothing, runs no test.

    Silent when every harvest has tested what it retained, when a harvest retained nothing
    (``retenus: 0`` — *an honest harvest can keep nothing*), and when the registry is
    empty."""

    __slots__ = ("_resume",)

    def __init__(self, resume: Callable[[], str | None]) -> None:
        self._resume = resume

    def scan(self) -> tuple[ProposalDraft, ...]:
        phrase = self._resume()
        if not phrase:
            return ()  # nothing dormant — silence, not noise
        return (ProposalDraft(source=_MOISSON_SOURCE, summary=phrase),)


class MoissonDueReview:
    """I2's nerve: a plan arc CLOSED without ever harvesting anything back into the system.

    ``make moisson`` exists, it is well designed — and it had **never been pulled once**. That is
    the textbook case of the user's remark: *the pattern exists, nothing obliges it.* This source is the
    half that was missing: not another harvest, but the act of NOTICING that an arc closed and
    rendered nothing. Measured on 2026-07-27: a ten-day project used 26 of the system's 71
    capabilities, built tools Mnémosyne does not have, and gave nothing back.

    **LEVEL 1, AND THE ITEM SAYS WHY** — *"a forced harvest manufactures candidates."* It
    publishes; it refuses nothing, blocks nothing, writes nothing. Raised to a gate, it would buy
    harvests pulled to silence an alarm, and a harvest that keeps everything has judged nothing.

    **IT NAMES WHERE ITS SEVEN SIBLINGS COUNT, and the distinction is mechanical.** They report a
    count because a fiche / signalement / parenthèse title can carry a bubble's matière. What
    crosses HERE is a plan-arc IDENTIFIER (``<project>/plan/03-captation``) — a plan file's path, the
    same meta ``make plans`` already prints for the whole tree. No item title, no line of the plan.
    And the list is BOUNDED (``moisson_due.NOMS_MAX``): three paths are a pointer, fifty are a
    project's structure. The bound is what makes the naming compatible with invariant 22 — not an
    intention. It is handed a callable returning the already-composed sentence (or ``None``), so
    this class holds no plan-reading power of its own: the judging lives in
    :mod:`~mnemosyne.production.moisson_due`, the disk lives at the edge.

    Silent when nothing is due — the normal state of a plan in progress. It goes quiet on its own
    the moment an arc's entry lands in its harvest record; nothing here has to be deleted, so no
    "alarm nobody can clear" is created (the failure ``ProposalQueueReview`` warns about)."""

    __slots__ = ("_resume",)

    def __init__(self, resume: Callable[[], str | None]) -> None:
        self._resume = resume

    def scan(self) -> tuple[ProposalDraft, ...]:
        phrase = self._resume()
        if not phrase:
            return ()  # no closed arc owes a harvest — silence, not noise
        return (ProposalDraft(source=_MOISSON_SOURCE, summary=phrase),)
