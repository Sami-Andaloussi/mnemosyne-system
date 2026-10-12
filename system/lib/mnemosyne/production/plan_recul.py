"""THE PULL-BACK DETECTOR (D5) — the trigger that "producer ≠ verifier" never states.

> *"How do you FORCE an agent to genuinely step back […] stop being attached to what it just
> built, decide to tear down what needs tearing down, go back, harden, and come back hardened?"*
> — the operator (internal planning notes, D5).

The repo already knew WHAT to do about a drift (D75, arc H). What was missing was WHEN to ask for
it. D5 names four signals; this module covers all **four** — **signal 4** with an explicitly
bounded SCOPE (see below), never hidden.

 **THIS IS NOT ONE MORE AUDIT.** The item says so itself: an audit adds a judgment; this module
judges nothing, it PROPOSES a mandate (*Obligation*: level 1). The authorization to undo lives in
arc H, never here.

## Signal 2 — why this is NOT `produit_resolu_rapport`

 **CORRECTION (2026-08-16), verified twice before writing a line**: this signal's first
diagnosis (internal planning notes, *state of play*, session 2) named "a reusable foundation"
without specifying which one, and a quick read of the text published elsewhere in this repo
(`produits_resolus=N/M`) would have built this signal on `plan_format.produit_resolu_rapport` — a
C2 measurement with no relation (the closure rate of PLAN items, not the share of WORK that goes
to the product). The real foundation is :mod:`~mnemosyne.production.plancher` (D3, closed): its
pure judge, :func:`~mnemosyne.production.plancher.lire_plancher`, already knows whether the floor
is breached — it can only tell the CURRENT state (the last day of a series), never the list of
days on which it was breached. That list is exactly what D5's *Done when* clause requires ("the
list of triggers published with their dates"), and it's all this module adds: a REPLAY, not a
second judge.

## Signal 3 — TWO proofs, published separately, NEVER summed

 **CORRECTION (2026-08-16), verified twice (once by an isolated agent, then directly by me)**:
D5's *state of play* said "same logic as `C6`, verified on `P6`" — **false**, measured twice:
`git log --grep='(P6)' -i` on `projects/.git` AND on that project's nested repo both return **ZERO**
`type(P6):` commits. The real proof of "rewritten K times" on `P6` is a FILE, not a commit:
`state/audits/{conditions,faits}/P6--t*.md` = **25 files**, counted directly (`ls`), not assumed.
`compte_temoins_fichiers` covers this proof.

 **THE "GIT-LOG" HALF IS NOW WIRED, BY CALL — NEVER BY COPY.**
`routage_journal_run.commits_par_ident` (C6) does exactly this counting, on a PARAMETRIZABLE
`repo_root` — **exposed in session 2 on the orchestrator's ruling** (internal chat log,
2026-08-16, *"you CALL it, you do NOT reimplement it"*), removing the leading underscore that made
it private. This module IMPORTS the function; it copies neither its regex nor its logic — *one
contract = one single home for the code, never recopied: a copy drifts.*

 **THE GIT-LOG RETURNS ZERO FOR `P6`, ON BOTH REPOS — AND THAT IS THE MEASUREMENT, NOT A WIRING
DEFECT.** The two proofs are NOT interchangeable: `commits_par_ident` answers "how many times did a
producer commit while REFERENCING this ident"; `compte_temoins_fichiers` answers "how many
revisions has this subject gone through, whatever the channel." On `P6`, the first is genuinely
zero (no commit ever named it) and the second is 25 — **two true facts, not a contradiction.**
Summing them would make "25" read as if it included commits that don't exist.

 **THE POPULATION SWEEP IS NOW BUILT (2026-08-16) — the orchestrator REFUSED to pick a `K`, on
an explicit ruling** (internal chat log): *"choosing a threshold before the replay manufactures the
result."* `balayage_reecriture` publishes, for every `k` in a RANGE, who triggers and when — never
a single threshold decided in advance. Measured on the real population (14 witness idents from
that project) BEFORE writing a line: `P6` carries **25** witnesses, its closest rival (`P13`) only **5** —
any `k` between 6 and 25 isolates `P6` **alone**, a clean separation, not built to arrive there.

 **ONLY HALF OF `P6`'S FILES CAN BE DATED.** `state/audits/conditions/*.md` (the first 4
refutations, `t1`-`t4`) carries an `item`/`tour`/`verdict`/`empreinte_condition` frontmatter — **NO
`date:` field at all**. Only `state/audits/faits/*.md` (`t5`-`t24`) carries one, and even its
format isn't uniform (`date: 2026-08-04` bare, `date: "2026-08-05"` quoted — both observed
side by side on real files). The sweep can therefore date ONLY the `faits/` witnesses — named
explicitly, never hidden; `compte_temoins_fichiers` (the raw count) itself still covers BOTH
folders.

## Signal 4 — "NO precedent" didn't hold up either, a FOURTH time

 **CORRECTION (2026-08-16), verified by an isolated agent**: D5's *state of play* said no
mechanism of this kind existed in this repo. **False.** `plan_retrait.RetraitEtat.denied_count`
(H1) already counts, PER REQUEST, how many times a withdrawal was refused — a REAL, TESTED
mechanism, with REAL DATA on disk (`system/state/retraits_requests.jsonl`, a request refused 4
times on 2026-08-15, during a deliberate H1 audit). This module recomputes nothing: it reads
`denied_count`, already folded by `RetraitLedger`, without reimplementing its logic.

 **CORRECTION #2 (session-3 audit, 2026-08-16), PROVEN BY EXECUTION**: the cited figure (4) is
real, but the MECHANISM the first version of this signal drew from it did NOT measure what its
name promised. `RetraitLedger.refuse()` — the NORMAL refusal gesture — increments `denied_count`
NOWHERE: called 6 times on the same request (scratch ledger, session 3), the counter stays at 0
while 6 real `refused` events pile up on disk. `denied_count` counts **precise bypass attempts**,
not "the door refused K times." See `RefusRepete`: this signal now publishes BOTH proofs (bypass
attempts, AND raw `refused` events counted directly from the JSONL) — separately, never summed.

 **"DOOR" HAS NO SINGLE CATALOGUE IN THIS REPO — four meanings coexist** (the structural sense of
`plan_format.DOOR_FILENAMES`, the generic figurative sense from `CLAUDE.md`, the three "entry
doors" from internal governance notes, and that project's own vocabulary in `validation/`). **This signal
covers ONLY ONE door: the withdrawal one (H1).** `guard.walls.WallLedger` (D159) has the generic
shape that would be needed to cover the Guard's eight `Effect` values, and it is wired in
production (`guard/monitor.py`) — but `system/state/walls.jsonl` **does not exist yet** on this
repo: nothing to replay before a first wall refuses something. Named, never hidden: a future
extension will have to either wait for real data on the walls side, or extend this signal door by
door — never guess at a population that doesn't exist.

 **This signal does NOT replay that other project's history** — the withdrawal ledger belongs to Mnémosyne, not
to that project (neither of that project's two repos has a ledger of this kind). D5's *Done when* clause ("it
triggers at least on 22 July and on `P6`") is already satisfied by signals 2 and 3 alone; this
signal doesn't need to independently re-satisfy it to be a real, measured signal.

## This module is a PURE JUDGE

It reads neither git nor the disk: the edge (:mod:`~mnemosyne.runtime.plan_recul_run`) hands it the
already-built series of :class:`~mnemosyne.production.plan_derive.Jour` (signal 2), or the
already-listed list of file names (signal 3) — denominator/population already bounded, the same
contract as :mod:`~mnemosyne.production.plancher`, whose judge this module reuses without
modifying it.

Decisions: D5 · D3 (the floor check reused, never rewritten) · D75 (stepping back ≠ an audit, the
authorization to undo lives in arc H) · H1 (`denied_count` reused, never rewritten) · role rule 1
(one file, one author) · inv. 2. (English here for the public mirror; the private original's prose
is French, D117.)
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .plancher import N_PLANCHER, X_PLANCHER, Plancher, lire_plancher
from .plan_derive import Jour
from .plan_retrait import RetraitEtat


@dataclass(frozen=True, slots=True)
class Declenchement:
    """A day on which the floor was breached — never a bare boolean, it carries what produced it."""

    date: str
    plancher: Plancher


def rejoue_plancher(
    jours: Sequence[Jour], *, x: float = X_PLANCHER, n: int = N_PLANCHER
) -> tuple[Declenchement, ...]:
    """Signal 2, REPLAYED — every day in ``jours`` on which the floor was breached ON THAT DAY.

 **``lire_plancher`` only returns the CURRENT state** (the last ``n`` days of a whole series)
 — exactly what :func:`~mnemosyne.production.plancher.decision` needs (judging a gesture made
 RIGHT NOW), and exactly what a historical REPLAY is missing (D5 requires "the list of triggers
 … with their dates"). This function does not rewrite the judge: it calls it once per day, over
 the GROWING window ending on that day — the same read anyone following the series day by day
 would have seen.

 **``jours`` must already be in CHRONOLOGICAL order and already bounded to the measured
 project** — the same two preconditions as :func:`~mnemosyne.production.plancher.lire_plancher`,
 not checked here (guaranteeing them is the edge's job).

 Complexity: ``O(len(jours) × n)`` — ``lire_plancher`` trims ``n`` elements on every call.
 Negligible over a plan's window (at most a few dozen days); do NOT reuse as-is over a
 multi-year series without reconsidering it.

 **CORRECTION (session-3 audit, 2026-08-16), proven by execution, not deduced**: a
 ``Jour(total=0)`` (no measurable line that day) was NOT filtered out — ``Jour.part`` returns
 ``0.0`` for it, read as "under the floor" instead of "no data." **Exactly the class that**
 :func:`~mnemosyne.production.plan_derive.plus_grande_chute` **already paid for once and
 explicitly corrects** (``pleins = [j for j in jours if j.total]``) — this module had not
 inherited that fix. Latent on the real population (every measured day carries a real total),
 never proven wrong in practice; fixed anyway — *a population that shelters a defect today can
 reveal it tomorrow* (the same doctrine as D1)."""
    pleins = [j for j in jours if j.total]
    resultats: list[Declenchement] = []
    for i in range(len(pleins)):
        plancher = lire_plancher(pleins[: i + 1], x=x, n=n)
        if plancher.franchi:
            resultats.append(Declenchement(date=pleins[i].date, plancher=plancher))
    return tuple(resultats)


#: `<ident>--t<N>...` -- the naming convention for successive revisions of the same item, observed
#: on `state/audits/{conditions,faits}/P6--t*.md` (25 files, `t1`…`t24` plus one `t13` variant).
#: Anchored at the START of the name (`^`) so `P6--t5.md` never counts for `P`, nor for an ident of
#: which `P6` is merely a prefix — see :func:`compte_temoins_fichiers`.
_TEMOIN_RE = r"^{ident}--t\d+"


def compte_temoins_fichiers(noms: Sequence[str], ident: str) -> int:
    """Signal 3 (the "witness files" HALF only) — how many of ``noms`` are a revision of ``ident``,
 per the ``<ident>--t<N>…`` convention.

 **PURE**: ``noms`` is already the list of file names a folder carries — it is the edge's job
 to list ``state/audits/conditions/`` AND ``state/audits/faits/`` and merge the two before
 calling this function (both folders carry revisions of the SAME ident, `P6` has 4 in
 `conditions/` and 21 in `faits/`).

 ``re.escape(ident)`` guards against an ident that would carry a regex special character (none
 today, but this module never guarantees an ident is alphanumeric)."""
    motif = re.compile(_TEMOIN_RE.format(ident=re.escape(ident)))
    return sum(1 for nom in noms if motif.match(nom))


@dataclass(frozen=True, slots=True)
class Reecriture:
    """Signal 3 — the TWO proofs of "rewritten K times", for one ident, NEVER summed.

 **``commits`` and ``fichiers_temoins`` are TWO DIFFERENT POPULATIONS.** One counts the
 commits that NAME the ident (``type(IDENT):``); the other counts the revisions written as a
 file (``state/audits/**/<ident>--t*.md``). On `P6`, measured: ``commits=0``,
 ``fichiers_temoins=25`` — the first channel is genuinely empty, the second genuinely full.
 *Adding the two together would pass off a REAL ZERO as rounding noise.* Each is ``None``
 separately when ITS OWN source is unreadable — never merged with the other (the same rule as
 :class:`Signal`, applied to two counters instead of one verdict)."""

    ident: str
    commits: int | None
    fichiers_temoins: int | None


@dataclass(frozen=True, slots=True)
class DeclenchementReecriture:
    """Signal 3, REPLAYED — an ident whose file-witnesses reached ``k``, with the date of the
    ``k``-th witness (the one that crossed the threshold) and its real total (may exceed ``k``)."""

    ident: str
    date: str
    total: int


def rejoue_reecriture(
    temoins_par_ident: Mapping[str, Sequence[str]], k: int
) -> tuple[DeclenchementReecriture, ...]:
    """For THIS ``k``, every ident with ``len(dates) >= k`` — the date returned is that of the
 ``k``-th witness once ``dates`` is sorted CHRONOLOGICALLY, never the most recent one: it's the
 day on which this signal would have crossed ``k`` for that ident, not the day of its last
 witness.

 **PURE**: ``dates`` is already extracted by the edge (parsing YAML frontmatters) — this
 function reads neither file nor disk, it sorts and compares ISO strings already in hand.

 **If ``k <= 0``, every ident triggers on its very first date** — consistent with "at least k
 witnesses", but a non-positive ``k`` makes no sense for any real signal; the caller is
 responsible for sweeping a sensible range (see :func:`balayage_reecriture`)."""
    resultats = [
        DeclenchementReecriture(ident=ident, date=(triees := sorted(dates))[k - 1], total=len(triees))
        for ident, dates in temoins_par_ident.items()
        if len(dates) >= k
    ]
    return tuple(sorted(resultats, key=lambda d: (d.date, d.ident)))


@dataclass(frozen=True, slots=True)
class BalayageK:
    """The result for ONE ``k`` value in the sweep — ``declenchements`` can be empty (a ``k`` that
    nobody reaches is a result, not an absence of measurement)."""

    k: int
    declenchements: tuple[DeclenchementReecriture, ...]


def balayage_reecriture(
    temoins_par_ident: Mapping[str, Sequence[str]], k_min: int, k_max: int
) -> tuple[BalayageK, ...]:
    """Sweeps ``k`` from ``k_min`` to ``k_max`` INCLUSIVE — publishes, for every value, WHO
 triggers and WHEN, never a single threshold chosen in advance.

 **It is the clause itself that demands this, not a new requirement**: *"the list of triggers
 is published with its dates, so its false positives can be judged"* — false positives can only
 be judged by SEEING them. A single ``k`` chosen in advance never shows the ones that had to be
 discarded. *A detector whose threshold is fixed before the replay measures the threshold, not
 the phenomenon* (D1: "nothing is calibrated on the answer")."""
    if k_min > k_max:
        raise ValueError(f"k_min ({k_min}) must be <= k_max ({k_max})")
    return tuple(BalayageK(k=k, declenchements=rejoue_reecriture(temoins_par_ident, k)) for k in range(k_min, k_max + 1))


@dataclass(frozen=True, slots=True)
class RefusRepete:
    """Signal 4 (SCOPE: the withdrawal door, H1, ONLY) — the TWO proofs of "refused K times",
 NEVER summed.

 **CORRECTION (session-3 audit, 2026-08-16), PROVEN BY EXECUTION, not deduced**: the first
 version of this signal read ONLY ``denied_count``, naming it "how many times refused."
 **FALSE** — ``RetraitLedger.refuse()`` (the normal refusal GESTURE) INCREMENTS NOTHING: called
 **6 times** on the same request (scratch ledger), ``denied_count`` stays at **0** all six
 times, while 6 real ``refused`` events are written to disk. ``denied_count`` actually counts
 **precise bypass attempts** (an invalid narrow, approving after a refusal, no tty, applying
 without approval, a stale hash) — **never** the normal refusal. A request refused K times in
 the full sense would have returned ``fois=0, cible=""``, indistinguishable from "never
 refused" — which is exactly what this module fixed.

 ``tentatives_bypass``/``cible_bypass``: the worst ``denied_count`` (what this signal already
 measured, now correctly named). ``refus_geste``/``cible_refus``: the worst count of RAW
 ``refused`` events per id — THE literal sense of D5's clause, "how many times has this door
 refused this request."

 **``fois=0`` is a MEASUREMENT, not an absence** on EACH of the two fields — never confused
 with "not yet measurable" (see the edge, which returns ``None`` for as long as the ledger
 doesn't exist on disk). *Two absences of measurement must never compare equal.*"""

    porte: str
    tentatives_bypass: int
    cible_bypass: str
    refus_geste: int
    cible_refus: str


def refus_le_plus_repete(
    etats: Sequence[RetraitEtat], refus_par_id: Mapping[str, int]
) -> RefusRepete:
    """The worst ``denied_count`` among ``etats`` AND the worst count in ``refus_par_id`` —
 published SEPARATELY, never summed (see :class:`RefusRepete`).

 **PURE**: ``etats`` is already folded by :meth:`~mnemosyne.production.plan_retrait.
 RetraitLedger.all_states` (H1); ``refus_par_id`` is already counted by the edge (the raw
 ``refused`` events from the same JSONL, a reading that ``RetraitEtat`` — a boolean, never a
 count — cannot supply). This function rereads nothing and refolds nothing, it compares numbers
 already in hand."""
    tentatives_bypass, cible_bypass = 0, ""
    if etats:
        pire_bypass = max(etats, key=lambda e: e.denied_count)
        if pire_bypass.denied_count:
            tentatives_bypass, cible_bypass = pire_bypass.denied_count, pire_bypass.id
    refus_geste, cible_refus = 0, ""
    if refus_par_id:
        pire_id, pire_compte = max(refus_par_id.items(), key=lambda kv: kv[1])
        if pire_compte:
            refus_geste, cible_refus = pire_compte, pire_id
    return RefusRepete(
        porte="retrait (H1)",
        tentatives_bypass=tentatives_bypass,
        cible_bypass=cible_bypass,
        refus_geste=refus_geste,
        cible_refus=cible_refus,
    )


@dataclass(frozen=True, slots=True)
class Signal:
    """One of D5's four signals — never a bare boolean, it carries its proof OR its absence.

 **``declenche`` HAS THREE VALUES, and confusing them manufactures a false one.** ``True`` =
 the signal was measured and triggers at least once; ``False`` = measured and quiet; ``None`` =
 NOT MEASURABLE this round (the same causes as D1/D2/D3: an unreadable repo, an empty window, or
 no `PRODUIT.md` declaration). *Two absences of measurement must never compare equal* — the same
 rule as everywhere else in this arc, applied here to four signals rather than a single ratchet.
 """

    nom: str
    declenche: bool | None
    preuve: str
    dates: tuple[str, ...] = field(default_factory=tuple)


def mandat_de_recul(signaux: Sequence[Signal]) -> str:
    """The pull-back mandate, PUBLISHED — *Obligation* level 1: it PROPOSES, it never refuses
 anything.

 **This is NOT one more audit.** An audit adds a judgment on a given piece of work; this
 mandate judges no work at all — it names WHEN a third party should request one. The
 authorization to undo what an audit would condemn lives in arc H, never here.

 Renders a print-ready page, in the style of :func:`~mnemosyne.production.plan_derive.rendre` /
 :func:`~mnemosyne.runtime.plancher_run.resume`: it NAMES what it could not measure, it never
 hides it — a ``None`` signal appears on the page, set apart, never merged with the signals that
 are genuinely quiet (``False``)."""
    declenches = [s for s in signaux if s.declenche]
    calmes = [s for s in signaux if s.declenche is False]
    non_mesures = [s for s in signaux if s.declenche is None]
    lignes = ["# MANDAT DE RECUL (D5) — niveau 1, il propose, il ne refuse rien", ""]
    if declenches:
        lignes.append(
            f"\U000026D4 {len(declenches)}/{len(signaux)} signal(aux) DÉCLENCHE(NT) — un recul est proposé :"
        )
        for s in declenches:
            dates = ", ".join(s.dates) if s.dates else "(dates non publiées)"
            lignes.append(f"  \U000025B6 {s.nom} : {s.preuve} — {dates}")
        lignes.append(
            "  Ce mandat ne défait rien lui-même : l'autorisation de défaire vit dans l'arc H."
        )
    else:
        lignes.append("\U00002705 aucun signal mesuré ne déclenche.")
    if calmes:
        lignes.append("")
        lignes.append(f"{len(calmes)} signal(aux) mesuré(s) et CALME(S) :")
        for s in calmes:
            lignes.append(f"  · {s.nom} : {s.preuve}")
    if non_mesures:
        lignes.append("")
        lignes.append(f"\U000026A0\U0000FE0F {len(non_mesures)}/{len(signaux)} signal(aux) NON MESURABLE(S) ce tour :")
        for s in non_mesures:
            lignes.append(f"  · {s.nom} : {s.preuve}")
    return "\n".join(lignes)
