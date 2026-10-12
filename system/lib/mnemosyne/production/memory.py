"""Living memory (D58-D60) + aggregator (D120) — propose, validate, reinject, non-destructive.

Moteur A (living memory, D55) holds bi-temporal facts and the operator's evolving preferences /
opinions. A *fiche* has a stable identity: updating it is an in-place non-destructive fusion
(``old ∪ new − contradictions``), never a cohabiting duplicate (D58). The pipeline that
produces or updates a fiche (D59) runs under three structural barriers:

* **Two-speed validation (D59-5).** ``sensible`` / ``perso`` / opinions / facts need an
  EXPLICIT human gesture and are never auto-validated (D54-3 / D27); only a benign
  non-sensible preference may apply directly, then be notified and revoked (D92).
  :meth:`LivingMemory.validate` escalates when the gesture is missing.
* **Bubble-scoped reinjection (D59-6 / D54-8).** A validated fiche is prefetched into context
  ONLY within its own bubble; reinjecting it into another bubble is a cloisonnement breach
  (a `perso` / `sensible` fiche never feeds an outward bubble, D49). Fail-closed.
* **No hard delete (D60-2).** The store offers ``invalidate`` (bi-temporal close), never a
  destructive verb — the only real deletion is an explicit human act (D44 / D53).

Reconciliation A↔B raises a FLAG on contradiction rather than overwriting (D60-3). The
aggregator (D120) is a periodic workflow that feeds living target-documents by PROPOSING —
never imposing (D92) — and never deleting its sources (D120 / decision 19). It is contenant
in P1; the target documents are contenu, filled at usage (D98). Code & docstrings English
(D117); the ``public`` / ``perso`` / ``sensible`` tokens stay French (D33).

Decisions: D58 (fiche format, stable identity, in-place fusion) · D59 (pipeline, two-speed
validation, bubble-scoped reinjection) · D60 (three security locks) · D92 (propose, never
auto-loosen) · D120 (aggregator → living documents, non-destructive).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from ..ports import (
    Bubble,
    CloisonnementError,
    DocId,
    ErrorCode,
    EscalateToHuman,
    Fact,
    GovernanceLabel,
    MnemosyneError,
    MonotonicityError,
    Sensitivity,
)

if (
    TYPE_CHECKING
):  # human-layer journal (D82); TYPE_CHECKING-only to avoid the memory ⇄ journal cycle
    from .human_journal import HumanLayerJournal
    from .proposals_ledger import ProposalsLedger


class FicheType:
    """The OPEN fiche type set (D58: "a floor, not a ceiling"). Extensible without breakage."""

    PREFERENCE = "preference"  # procedural: how to write / act for the operator (benign candidate)
    OPINION = "opinion"  # evolving declarative view (needs explicit validation, D59-5)
    REFLECTION = "reflection"  # an archived chat / thought, updated in place (D58)
    FACT = "fact"  # a bi-temporal fact (needs explicit validation, D59-5)
    NOTE = "note"  # plan B (③-3c / D58): raw `.md` note when extraction isn't trusted enough
    LEARNING = "learning"  # item 2: a concise durable learning captured DURING use (D115-AV3)


class ValidationState:
    """The human-guard state of a fiche (D59)."""

    PROPOSED = "proposed"  # produced by an agent, awaiting the gesture (D59-4)
    VALIDATED = "validated"  # cleared (explicitly, or auto for a benign preference, D59-5)


class ReconciliationFlag(MnemosyneError):
    """Moteur A ↔ Moteur B disagree — raised INSTEAD of overwriting (D60-3).

    Not a failure of the system but a contradiction the operator must arbitrate; carried as a
    normalized error so the orchestrator FLAGs it (D108-② / D60-3)."""

    code = ErrorCode.ESCALATE_HUMAN


@dataclass(frozen=True, slots=True)
class Fiche:
    """One living-memory unit with a STABLE identity (D58).

    ``content`` is a set of statements so the in-place fusion of D58 is a real, testable
    algebra: updating yields ``old ∪ add − remove`` and pushes the old content onto
    ``history`` — nothing is lost (non-destructive, D44 / D58). There is exactly one current
    fiche per subject; prior versions stay consultable in ``history``."""

    id: str
    ftype: str
    content: frozenset[str]
    label: GovernanceLabel  # carries bubble + sensitivity + provenance (D19 / D58 dos commun)
    state: str = ValidationState.PROPOSED
    history: tuple[frozenset[str], ...] = ()

    def update(
        self, *, add: frozenset[str] = frozenset(), remove: frozenset[str] = frozenset()
    ) -> Fiche:
        """In-place non-destructive fusion (D58): ``new = old ∪ add − remove``, old kept.

        The removed statements are not erased — they remain in ``history`` (invalidated, not
        deleted; "invalidated ≠ erased", D55 / D58). A re-update after review re-opens the
        gesture, so an updated fiche returns to PROPOSED. This returns a NEW fiche value;
        persisting it is a fresh :meth:`LivingMemory.propose` — the store does not auto-track
        the returned value."""
        new_content = (self.content | add) - remove
        return replace(
            self,
            content=new_content,
            history=(*self.history, self.content),
            state=ValidationState.PROPOSED,
        )


def _scoped_id(kind: str, bubble: Bubble, tail: str) -> str:
    """A collision-free fiche id over ``(kind, bubble, tail)`` — content-addressed (like a fact id).

    ``tail`` is UNTRUSTED (a content-derived subject, or a doc id — D100-3 content-as-data), so the
    id is NOT a naive ``f"{bubble}:{tail}"``: an unescaped delimiter would let a crafted subject
    forge another (e.g. hierarchical ``work:acme``) bubble's id (integrity breach). The fields are
    joined on ``\\x1f`` (a control byte no bubble/subject carries) and hashed (SHA-256), the same
    injective, non-forgeable scheme the graph uses for a fact id — two distinct triples never
    collide. ``kind`` namespaces the id-space so a subject-fiche and a NOTE can never collide."""
    key = "\x1f".join((kind, str(bubble), tail))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _fiche_id(label: GovernanceLabel, subject: str, *, kind: str = "subject") -> str:
    """The per-subject fiche identity (D58: "exactly one current fiche per subject").

    Scoped by KIND then BUBBLE then subject (injectively — :func:`_scoped_id`): a same-subject fact in
    ANOTHER bubble is a distinct fiche (never a cross-bubble collision, invariant 3), an untrusted
    subject can never forge another bubble's id, and — via ``kind`` — the DETERMINISTIC structural
    fact-space (code identifiers, ``kind="structural"``) is disjoint from the LLM/personal subject
    space (``"subject"``): capturing ``def user():`` can never collide with or clobber the personal
    "user" fiche. Sensitivity is deliberately NOT in the id — one subject has ONE current fiche whose
    label is the MAX sensitivity ever seen (upward-only), so a lower-sensitivity re-capture can never
    fork a parallel, weaker copy; it folds IN under the existing (higher) label, or is a no-op.
    Declassifying that fiche stays a human gesture (D100-2), enforced by :meth:`LivingMemory.propose`."""
    return _scoped_id(kind, label.bubble, subject)


def facts_to_fiches(
    facts: tuple[Fact, ...],
    label: GovernanceLabel,
    *,
    ftype: str,
    current: Callable[[str], Fiche | None],
    kind: str = "subject",
) -> tuple[Fiche, ...]:
    """The rich faits→fiches factory (③-3c / D120): ONE evolving fiche per subject, non-destructively.

    Supersedes ③-3b's per-FACT bridge: N facts about a subject collapse into a single PROPOSED
    fiche (de-duplication by subject), the D58 "one current fiche per subject". Each fiche is the
    D100 gate's raw material — inert until validated & reinjected (D59), carrying the CONTENT's
    label (raise-only, never declassifying what the classifier fixed). ``current`` reads the stored
    fiche for an id (or ``None``); a subject already on file is fused in place (``old ∪ new``,
    non-destructive — the prior content survives in ``history``, D58) under a MOST-RESTRICTIVE label
    (:meth:`GovernanceLabel.merge`: sensitivity → max, domains → union, invariants 17 / 23):

    * an identity re-capture (nothing new, label unchanged) leaves the fiche UNTOUCHED, so a VALIDATED
      fiche is never demoted back to PROPOSED by re-seeing a known fact;
    * a re-capture at a HIGHER sensitivity (or a new domain) RAISES the fiche and re-opens the gesture
      — a fact newly known ``sensible`` can never stay filed ``perso``, nor lose a domain scope;
    * a re-capture at a LOWER sensitivity folds its statements IN under the existing (higher) label
      (over-protective, never a declassification).

    Because the id pins the bubble injectively (:func:`_scoped_id`), ``current`` only ever returns a
    SAME-bubble fiche, so ``merge`` never crosses bubbles; the store's monotone, bubble-safe
    :meth:`LivingMemory.propose` is the backstop for anything a caller constructs by hand. ``kind``
    namespaces the fiche id (default ``"subject"``; the structural pre-pass passes ``"structural"``),
    so two fact SOURCES that name the same subject never collide into one fiche."""
    groups: dict[str, set[str]] = {}
    for fact in facts:
        groups.setdefault(str(fact.subject), set()).add(
            f"{fact.subject} {fact.predicate} {fact.obj}"
        )
    out: list[Fiche] = []
    for subject, statements in groups.items():
        fid = _fiche_id(label, subject, kind=kind)
        existing = current(fid)
        if existing is None:
            out.append(Fiche(id=fid, ftype=ftype, content=frozenset(statements), label=label))
            continue
        merged_label = existing.label.merge(label)  # max sensitivity + union domains, upward-only
        additions = frozenset(statements) - existing.content
        if not additions and merged_label == existing.label:
            out.append(existing)  # identity fusion — untouched, keeps its validation state (D58)
        else:
            fused = (
                existing.update(add=additions) if additions else existing
            )  # ∪ content, history (D58)
            out.append(replace(fused, label=merged_label, state=ValidationState.PROPOSED))
    return tuple(out)


#: A plan-B triage NOTE carries only a bounded PREVIEW of the content (D136 / audit M-2): the full
#: text is already stored truth-first in documentary memory (Moteur B, passage-retrievable), so the
#: note must not copy it whole — an unbounded note would overflow the runner bound once the validated
#: note reinjects into an answer frame. The preview + a pointer to the doc is enough to triage by hand.
_NOTE_PREVIEW_CHARS = 2000


def note_fiche(text: str, label: GovernanceLabel, *, doc: DocId) -> Fiche:
    """Plan B (③-3c / D58): a raw ``.md`` NOTE fiche when extraction isn't trusted enough.

    Below the golden-set threshold (or when the extractor raised), the graph is NOT auto-imposed
    ("no auto-imposed graph") — instead the content lands as a human-readable NOTE for the operator
    to triage into facts by hand. Like every fiche it carries the content's label (raise-only) and is
    PROPOSED; a NOTE is never a benign public preference, so it ALWAYS needs an explicit human
    gesture (:func:`_needs_explicit_human`, fail-closed). Id scoped injectively by bubble+doc in the
    ``note`` namespace (:func:`_scoped_id`) — one note per captured document, never colliding with a
    subject-fiche id even if a subject is literally named ``note:<doc>``. The note carries a BOUNDED
    preview of the content, not the whole text (D136 / audit M-2): the full document is truth-first
    in Moteur B, so a validated note can never overflow the answer runner when it reinjects."""
    return Fiche(
        id=_scoped_id("note", label.bubble, str(doc)),
        ftype=FicheType.NOTE,
        content=frozenset({_note_preview(text, doc)}),
        label=label,
    )


def _note_preview(text: str, doc: DocId) -> str:
    """The bounded preview a plan-B NOTE carries (D136 / audit M-2): the whole text if short, else its
    head plus a pointer to the full document in Moteur B — never the whole document (which would
    overflow the runner bound once the validated note reinjects into an answer)."""
    if len(text) <= _NOTE_PREVIEW_CHARS:
        return text
    head = text[:_NOTE_PREVIEW_CHARS].rstrip()
    return (
        f"{head}\n\n… [note truncated at {_NOTE_PREVIEW_CHARS} chars — "
        f"full document in documentary memory (Moteur B): {doc}]"
    )


#: A LEARNING is a concise durable statement, stored WHOLE (item 2) — unlike a NOTE it has NO
#: documentary backup in Moteur B, so it cannot be previewed-and-pointed-at; it is REFUSED above this
#: ceiling rather than truncated (never a dangling pointer, D100). Well under the runner reinjection
#: bound (D136) so a validated learning never overflows an answer frame. A real learning (a preference,
#: a stated fact, a correction) is a sentence or two — this ceiling only stops a document masquerading
#: as a learning (that is ``capture``'s job, truth-first in the benne).
_LEARNING_MAX_CHARS = 2000


def learning_fiche(text: str, label: GovernanceLabel, *, ftype: str = FicheType.LEARNING) -> Fiche:
    """A living-memory fiche for a concise LEARNING captured DURING use (item 2 / D58 / D115-AV3).

    The "learning while using" unit: as a frontier works, it recognises a durable, reusable learning —
    a stable fact the operator states, a work preference, a correction — and proposes it here, INERT.
    Unlike :func:`note_fiche` (a plan-B triage note BACKED by the full document in Moteur B), a
    learning has NO documentary backup, so it is stored WHOLE and REFUSED fail-closed above
    :data:`_LEARNING_MAX_CHARS` rather than truncated — never a dangling pointer to a doc that does
    not exist (D100 / D136). PROPOSED like every fiche (D59): nothing reinjects into an answer until
    the operator's validation (propose, never impose, D92 / D100) — a LEARNING is never the benign
    PUBLIC PREFERENCE that may auto-apply, so it ALWAYS awaits the gesture
    (:func:`_needs_explicit_human`, fail-closed).

    The id is scoped injectively by the CONTENT in the ``learning`` namespace (:func:`_scoped_id`), so
    re-proposing the SAME learning is idempotent (:meth:`LivingMemory.propose` no-ops it) and a
    learning the operator has dismissed stays closed (never resurfaced, D60-2) — anti-noise by
    construction. ``ftype`` defaults to :data:`FicheType.LEARNING` but a confident caller may pass a
    sharper type (a ``PREFERENCE`` / ``FACT``); the label carries the content's sensitivity
    (raise-only, fail-safe ``sensible`` at the caller)."""
    text = text.strip()
    if not text:
        raise ValueError("a learning must be non-empty (item 2)")
    if len(text) > _LEARNING_MAX_CHARS:
        raise ValueError(
            f"a learning must be concise (<= {_LEARNING_MAX_CHARS} chars) — it is stored whole, never "
            "truncated; capture a document through `capture` instead (item 2 / D136)"
        )
    return Fiche(
        id=_scoped_id("learning", label.bubble, text),
        ftype=ftype,
        content=frozenset({text}),
        label=label,
    )


def _needs_explicit_human(fiche: Fiche) -> bool:
    """Whether a fiche needs an EXPLICIT human gesture (D59-5) — allow-list, fail-closed.

    Only a benign PUBLIC PREFERENCE may auto-apply ("a style preference with nothing at stake",
    D59-5); the auto lane is deliberately RESTRICTED. Everything else needs a human: any ``perso`` /
    ``sensible`` fiche, any opinion or fact, an archived reflection (user content), and any
    UNKNOWN open type (fail-closed on the open type set — D58 "a floor, not a ceiling")."""
    return not (
        fiche.label.sensitivity == Sensitivity.PUBLIC and fiche.ftype == FicheType.PREFERENCE
    )


class LivingMemory:
    """Moteur A's fiche pipeline (D58-D60): propose → validate (two-speed) → reinject (scoped).

    Non-destructive throughout: ``invalidate`` closes a fiche (bi-temporal), it never deletes
    (D60-2). Reinjection is bubble-scoped (D59-6 / D54-8)."""

    __slots__ = ("_fiches", "_invalidated", "_journal", "_proposals_ledger")

    def __init__(
        self,
        journal: HumanLayerJournal | None = None,
        *,
        proposals_ledger: ProposalsLedger | None = None,
    ) -> None:
        self._fiches: dict[str, Fiche] = {}
        self._invalidated: set[str] = set()
        # the human-layer net (D82): when wired (real_runtime), every validate / invalidate is
        # journaled to durable disk BEFORE it reaches RAM. None ⇒ pure in-memory (unit tests) — the
        # prod cold-start ALWAYS wires it (bootstrap) so the irreversible-loss window is closed.
        self._journal = journal
        # the durable landing for NON-rebuildable proposals (item 2): a `make remember` LEARNING dies
        # with its short-lived process unless recorded here — the gesture journal is the wrong home (it
        # rebuilds nothing, but a proposal mostly DOES, D44). None ⇒ pure in-memory. Written only on a
        # `durable=True` propose (remember), never the extractor path; replayed AFTER the human journal.
        self._proposals_ledger = proposals_ledger

    def propose(self, fiche: Fiche, *, durable: bool = False) -> Fiche:
        """Register a candidate fiche as PROPOSED (D59-4) — non-destructively and monotonically.

        Idempotent and upward-only (D58 / D60-2 / D100-2 / invariant 17), so the write path a real
        extractor drives (③-3c) can never silently erase a gesture, declassify, or overwrite across
        bubbles when two data address the same id:

        * a fiche IDENTICAL to a stored one (same content, same label) is a NO-OP that keeps its
          state — a re-capture never demotes a VALIDATED fiche back to PROPOSED;
        * the label is UPWARD-ONLY — a re-proposition may raise the sensitivity but never lower it
          (declassification is a human act, D100-2), refused fail-closed like :meth:`Envelope.relabel`;
        * a re-proposition can never cross bubbles (invariant 3 / D54) — a same-id datum in another
          bubble is a cloisonnement breach, not an overwrite;
        * an INVALIDATED (closed) id is left closed — never resurrected or mutated (D60-2).

        A genuine change (new content, or a raised sensitivity) re-opens the gesture (PROPOSED, D58).

        ``durable`` (item 2): a NON-rebuildable proposal — a ``make remember`` LEARNING with no documentary
        backup — is recorded to the proposals ledger (write-ahead) on a genuine registration, so it survives
        the short-lived ``remember`` process. The extractor / aggregator paths leave it False: they rebuild
        from ``raw/`` (D44), so recording them would bloat the ledger with a reconstructible signal."""
        if fiche.id in self._invalidated:
            # closed stays closed — never resurrected or mutated (D60-2), and INDEPENDENT of `_fiches`
            # presence: a dismissed `make remember` learning may survive a restart only as the invalidate
            # replayed from the human journal (its proposal skipped at replay), so a later re-`remember`
            # of it must still no-op here rather than re-open it (anti-noise, item 2). Never journals.
            existing = self._fiches.get(fiche.id)
            return existing if existing is not None else fiche
        existing = self._fiches.get(fiche.id)
        if existing is not None:
            if fiche.label.bubble != existing.label.bubble:
                raise CloisonnementError(
                    f"fiche {fiche.id!r}: a re-proposition cannot cross bubbles "
                    f"{existing.label.bubble!r}→{fiche.label.bubble!r} (invariant 3 / D54)"
                )
            if fiche.label.sensitivity < existing.label.sensitivity:
                raise MonotonicityError(
                    f"fiche {fiche.id!r}: a re-proposition cannot lower sensitivity "
                    f"{existing.label.sensitivity.token!r}→{fiche.label.sensitivity.token!r} — "
                    "declassification is a human gesture (D100-2 / invariant 17)"
                )
            if fiche.content == existing.content and fiche.label == existing.label:
                return existing  # idempotent: an identical re-capture keeps the gesture (D58)
        candidate = replace(fiche, state=ValidationState.PROPOSED)
        # durable (item 2): a non-rebuildable proposal is recorded BEFORE RAM, so a crash leaves neither a
        # ledger line nor a RAM fiche (consistent) and we never PRETEND a capture was saved. Reached ONLY on
        # a genuine registration — a no-op re-propose or a refused (cross-bubble / declassifying) one above
        # never journals. The extractor path passes durable=False (it rebuilds from raw/, D44).
        if durable and self._proposals_ledger is not None:
            self._proposals_ledger.record_propose(candidate)
        self._fiches[fiche.id] = candidate
        return candidate

    def current(self, fiche_id: str) -> Fiche | None:
        """The stored fiche for ``fiche_id`` (any state), or ``None`` — the factory's read side.

        A read accessor the rich per-subject factory (:func:`facts_to_fiches`) uses to fuse new
        facts ONTO the fiche already on file (D58 in-place fusion), rather than clobber it. Returns
        the fiche verbatim including its validation state and (if closed) its invalidated status —
        the caller fuses, then :meth:`propose` applies the non-destructive, monotone barriers."""
        return self._fiches.get(fiche_id)

    def proposed(self) -> tuple[Fiche, ...]:
        """The fiches still PROPOSED — the living side of the human validation queue (D59-4).

        These await the operator's gesture; none of them reinjects into an answer yet (only
        VALIDATED fiches do, D100 / D59-5). An invalidated (closed) fiche never appears here (D60-2)."""
        return tuple(
            f
            for f in self._fiches.values()
            if f.state == ValidationState.PROPOSED and f.id not in self._invalidated
        )

    def validate(self, fiche_id: str, *, human_validated: bool) -> Fiche:
        """Two-speed validation (D59-5). Escalates when an explicit gesture is required.

        A ``sensible`` / ``perso`` fiche, or any opinion / fact, needs ``human_validated`` —
        else :class:`EscalateToHuman` (never auto-validated, D54-3 / D27). A benign public
        preference may auto-apply (applied then notified / revocable, D92). An unknown fiche id,
        or an invalidated (closed) one, is refused as a normalized error (D108-② / D60-2)."""
        if fiche_id not in self._fiches:
            raise MnemosyneError(f"unknown fiche {fiche_id!r} — nothing to validate (D108-②)")
        if fiche_id in self._invalidated:
            raise MnemosyneError(
                f"fiche {fiche_id!r} is invalidated (closed) — cannot be re-validated (D60-2)"
            )
        fiche = self._fiches[fiche_id]
        if _needs_explicit_human(fiche) and not human_validated:
            raise EscalateToHuman(
                f"fiche {fiche_id!r} ({fiche.ftype}, {fiche.label.sensitivity.token}) needs an "
                "explicit human validation — never auto-validated (D59-5 / D54-3)"
            )
        validated = replace(fiche, state=ValidationState.VALIDATED)
        # write-ahead, fail-closed (D82 / D80): journal the gesture to durable disk BEFORE it reaches
        # RAM. An I/O error propagates, so a failed journal leaves the fiche PROPOSED rather than
        # silently losing a validation the human layer can never reconstruct (D56 / D60).
        if self._journal is not None:
            self._journal.record_validate(validated, human_validated=human_validated)
        self._fiches[fiche_id] = validated
        return validated

    def invalidate(self, fiche_id: str) -> None:
        """Close a fiche (bi-temporal), keeping it consultable — never delete (D60-2 / D53)."""
        # write-ahead, fail-closed (D82): the close is a human gesture — journal it before RAM.
        if self._journal is not None:
            self._journal.record_invalidate(fiche_id)
        self._invalidated.add(fiche_id)

    def _restore_validated(self, fiche: Fiche) -> None:
        """Re-apply a journaled validation at replay (D82) — NO re-journaling, NO re-escalation.

        The gesture already happened and was durably recorded; replay rebuilds RAM from the journal,
        restoring the whole recorded fiche verbatim (self-contained, no dependency on the derived
        layer). The seam :class:`~mnemosyne.production.human_journal.HumanLayerJournal` drives it."""
        self._fiches[fiche.id] = fiche

    def _restore_invalidated(self, fiche_id: str) -> None:
        """Re-apply a journaled invalidation at replay (D82) — rebuilds ``_invalidated`` from the journal."""
        self._invalidated.add(fiche_id)

    def _restore_proposed(self, fiche: Fiche) -> None:
        """Re-apply a durable proposal at replay (item 2 / D82) — run AFTER the human journal.

        A since-VALIDATED id (already in ``_fiches`` from the human journal) or a since-INVALIDATED one (in
        ``_invalidated``) is NOT resurrected — decided stays decided (D60-2). Otherwise the whole recorded
        fiche is restored (encoded PROPOSED), rejoining the validation queue. Driven by
        :class:`~mnemosyne.production.proposals_ledger.ProposalsLedger`."""
        if fiche.id in self._invalidated or fiche.id in self._fiches:
            return
        self._fiches[fiche.id] = fiche

    def reinject(self, bubble: Bubble) -> tuple[Fiche, ...]:
        """Prefetch the VALIDATED fiches of ``bubble`` only — bubble-scoped (D59-6 / D54-8).

        A fiche from another bubble is never returned: a ``perso`` / ``sensible`` fiche never
        crosses into a different bubble's context (anti-fuite, D49 / D54-8). This scoping IS
        the barrier — no cross-bubble prefetch exists."""
        return tuple(
            f
            for f in self._fiches.values()
            if f.label.bubble == bubble
            and f.state == ValidationState.VALIDATED
            and f.id not in self._invalidated
        )

    def reinject_into(self, fiche: Fiche, target: Bubble) -> Fiche:
        """Guarded reinjection of a single fiche: refuses any cross-bubble prefetch (D54-8).

        Fail-closed: an invalidated (closed) fiche is never reinjected (D60-2), and reinjecting
        a fiche whose bubble differs from ``target`` is a cloisonnement breach (invariant 3 /
        D49) — the prefetch never silently crosses."""
        if fiche.id in self._invalidated:
            raise MnemosyneError(
                f"fiche {fiche.id!r} is invalidated (closed) — not reinjected (D60-2)"
            )
        if fiche.label.bubble != target:
            raise CloisonnementError(
                f"cannot reinject a {fiche.label.bubble!r} fiche into bubble {target!r}: "
                "living-memory prefetch is bubble-scoped (D59-6 / D54-8)"
            )
        return fiche

    def reconcile(self, *, invalidated_by_a: frozenset[str], asserted_by_b: frozenset[str]) -> None:
        """A↔B reconciliation (D60-3): FLAG a contradiction, never overwrite silently.

        Moteur A owns volatile facts, Moteur B stable content. A real contradiction is a claim
        Moteur A has INVALIDATED that Moteur B still ASSERTS — the overlap of the two sets. It
        raises a FLAG for the operator rather than picking a silent winner (D60-3 / D65 — "present
        both / flag"). The parameter names say which side each set comes from, so a naive caller
        cannot mistake agreement for contradiction."""
        contradictions = invalidated_by_a & asserted_by_b
        if contradictions:
            raise ReconciliationFlag(
                f"A↔B contradiction on {sorted(contradictions)!r} — presented to the operator, "
                "never overwritten (D60-3)"
            )


@dataclass(frozen=True, slots=True)
class AggregationProposal:
    """What the aggregator PROPOSES (D120) — a fiche update, never an imposed write (D92)."""

    target: str  # the living target-document id being fed
    fiche: Fiche  # PROPOSED, awaiting the operator's gesture through :class:`LivingMemory`
    sources: tuple[str, ...] = field(default_factory=tuple)  # aggregated, NEVER deleted (D120)


class Aggregator:
    """Periodic aggregator → living documents (D120) — pure glue on P1 bricks.

    Reads newly ingested docs, extracts the pertinent, and feeds thematic living target-
    documents by PROPOSING (D92, "continuous re-evaluation"). It never writes directly and never
    deletes its sources (D120 / decision 19) — its output lands in surface (f) (D119) for the
    operator's return. Contenant in P1; the target documents are contenu, at usage (D98)."""

    __slots__ = ("_memory",)

    def __init__(self, memory: LivingMemory) -> None:
        self._memory = memory

    def propose_aggregation(
        self, target: str, fiche: Fiche, *, sources: tuple[str, ...]
    ) -> AggregationProposal:
        """Feed a living target-document by PROPOSING an update (D120 / D92).

        The fiche is registered PROPOSED — it never bypasses validation (propose, never
        impose). Sources are recorded, never removed (non-destructive, D120)."""
        proposed = self._memory.propose(fiche)
        return AggregationProposal(target=target, fiche=proposed, sources=sources)
