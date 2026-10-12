"""The EDGE of :mod:`mnemosyne.production.plan_recul` (D5) — this is where ``git`` gets opened.

Fully reuses the D1/D2/D3 edge (:mod:`~mnemosyne.runtime.derive_run`,
:mod:`~mnemosyne.runtime.plancher_run`): same repo (``projects/.git``), same window, same
``PRODUIT.md`` declaration, same denominator bounded to the measured project
(:func:`~mnemosyne.runtime.plancher_run.borne_au_projet`). *A shared guard gets repaired at its
home, never at each of its callers one by one.*

 **NOT YET CALLED BY ``make carte``, and that is a named choice** — same posture as
:mod:`~mnemosyne.runtime.plan_duree_run` (D6): wiring a new measurement into the map is a separate
gesture, decided by whoever reads it, not by whoever builds it.

## Signal 1 — a SECOND repo, never ``projects/.git``

 **CORRECTION (2026-08-16), the third on this item**: the *State of the ground* cited "~257
revisions" — the TOTAL commit count of ``projects/.git`` (the one D1/D2/D3 read), which contains
**NO** commit touching the sibling project's ``plan/`` at all (``.gitignore`` has excluded it since
its very first commit). The real history of that sibling project's plan revisions lives in its own **NESTED**
repo (its own ``.git``), an ENTIRELY different window (2026-08-07 → 2026-08-15,
versus 2026-07-15 → 2026-07-30 for D1/D3) — **167** of its 288 commits touch ``plan/``.

 **THIS NESTED REPO HAS ITS OWN ROOT, AND IT IS A SQUASH, NOT A REAL GENESIS** — its first
commit (``socle: DEPOT NEUF après la perte d'objets``) reconstructs the state of an OLD repo of
~915 commits, unrecoverable after an object loss. *The immobility measured here CANNOT see past
this root* — an even more stagnant stretch that began BEFORE it would stay invisible. Named, never
hidden: see :func:`signal_immobilite`.

 **The JUDGE is already built and already tested (D1)**: :func:`~mnemosyne.production.plan_derive.
immobilite` — this module only builds the :class:`~mnemosyne.production.plan_derive.Tour` objects
it consumes; it rewrites NOTHING of the judgment.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from ..production.plan_derive import PAR_LIGNE, Immobilite, Tour, immobilite, part_produit
from ..production.plan_recul import (
    BalayageK,
    Declenchement,
    Reecriture,
    RefusRepete,
    Signal,
    balayage_reecriture,
    compte_temoins_fichiers,
    mandat_de_recul,
    refus_le_plus_repete,
    rejoue_plancher,
)
from ..production.plan_retrait import RetraitLedger
from ..production.plancher import N_PLANCHER, X_PLANCHER
from .derive_run import DEPUIS, JUSQUA, RACINE_PRODUIT, lire_tours, predicat_produit
from .plancher_run import borne_au_projet
from .routage_journal_run import commits_dates_par_ident, commits_par_ident

NOM_SIGNAL_PLANCHER = "signal 2 -- the product share under the floor"

#: The two folders where an item revision carries its name `<ident>--t<N>…md` -- `P6` has 4 in
#: `conditions/` (the initial refutations) and 21 in `faits/` (the replays that followed).
_DOSSIERS_TEMOINS: tuple[str, ...] = ("state/audits/conditions", "state/audits/faits")


def declenchements_plancher(
    repo_root: Path,
    *,
    x: float = X_PLANCHER,
    n: int = N_PLANCHER,
    est_produit: Callable[[str], bool] | None = None,
) -> tuple[Declenchement, ...] | None:
    """Signal 2 REPLAYED over the declared window, or ``None`` if the measurement could not be taken.

 **``None`` covers the same TWO distinct causes as
 :func:`~mnemosyne.runtime.plancher_run.etat_plancher`** — unreadable repo/window, or no
 ``PRODUIT.md`` declaration. It is :func:`signal_plancher` that carries the message naming them.

 **INJECTED ``est_produit`` replays the HISTORICAL validation — without it, the CURRENT
 measurement, and the sibling project has NOT declared a ``PRODUIT.md`` today, so without injection this
 function always returns ``None``.** Same distinction as everywhere else in this arc (D1/D2/D3):
 a historical verdict replays on ITS population, never on what the disk carries today.
 """
    tours = lire_tours(repo_root, depuis=DEPUIS, jusqua=JUSQUA)
    if not tours:
        return None
    predicat = est_produit
    if predicat is None:
        predicat, _motifs = predicat_produit(repo_root)
        if predicat is None:
            return None
    mesurables = [t for t in tours if len(t.lignes) == len(t.chemins)]
    bornes = [borne_au_projet(t, RACINE_PRODUIT) for t in mesurables]
    jours = part_produit(bornes, predicat, unite=PAR_LIGNE)
    return rejoue_plancher(jours, x=x, n=n)


def signal_plancher(
    repo_root: Path,
    *,
    x: float = X_PLANCHER,
    n: int = N_PLANCHER,
    est_produit: Callable[[str], bool] | None = None,
) -> Signal:
    """D5's signal 2, in the shape that :func:`~mnemosyne.production.plan_recul.mandat_de_recul`
    consumes — NAMES what it could not measure, never stays silent about it."""
    declenchements = declenchements_plancher(repo_root, x=x, n=n, est_produit=est_produit)
    if declenchements is None:
        return Signal(
            nom=NOM_SIGNAL_PLANCHER,
            declenche=None,
            preuve=(
                f"PRODUCT SHARE NOT MEASURED — `projects/{RACINE_PRODUIT}` declares no "
                "PRODUIT.md, or the repo/window is unreadable (D2)"
            ),
        )
    if not declenchements:
        return Signal(
            nom=NOM_SIGNAL_PLANCHER,
            declenche=False,
            preuve=f"never breached (X={x:.0f}%, N={n}) over the measured window",
        )
    return Signal(
        nom=NOM_SIGNAL_PLANCHER,
        declenche=True,
        preuve=f"breached (X={x:.0f}%, N={n}) {len(declenchements)} day(s)",
        dates=tuple(d.date for d in declenchements),
    )


def temoins_fichiers(repo_root: Path, ident: str) -> int | None:
    """Signal 3, "witness files" proof — how many
    ``state/audits/{conditions,faits}/<ident>--t*.md`` files under the monitored project, or
    ``None`` if NEITHER folder exists (measurement not taken, never confused with "zero real
    revision"). See :func:`reecriture` to combine it with the git-log proof."""
    racine = repo_root / "projects" / RACINE_PRODUIT
    dossiers = [racine / d for d in _DOSSIERS_TEMOINS]
    existants = [d for d in dossiers if d.is_dir()]
    if not existants:
        return None
    noms = [p.name for d in existants for p in d.iterdir() if p.is_file()]
    return compte_temoins_fichiers(noms, ident)


#: Extracts an ident at the head of the name, same convention as `plan_recul._TEMOIN_RE`, generic
#: (no specific ident injected) since here we enumerate ALL witness idents, not just one.
_IDENT_TEMOIN_RE = re.compile(r"^([A-Za-z0-9]+)--t\d+")

#: `date: 2026-08-04` (bare) OR `date: "2026-08-05"` (quoted) -- the TWO forms observed side by
#: side on real `state/audits/faits/*.md` files before this module was written. The quotes are
#: NEVER in the captured group.
_DATE_TEMOIN_RE = re.compile(r'^date:\s*"?(\d{4}-\d{2}-\d{2})"?', re.MULTILINE)


def _date_temoin(chemin: Path) -> str | None:
    """The ISO date from ONE witness file's frontmatter, or ``None`` if it carries none (the case
    for ALL `state/audits/conditions/*.md` files — see the module docstring)."""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError:
        return None
    trouve = _DATE_TEMOIN_RE.search(texte)
    return trouve.group(1) if trouve else None


def temoins_dates_par_ident(repo_root: Path) -> dict[str, tuple[str, ...]] | None:
    """All idents with at least one DATABLE witness file, each with the list of its dates —
 ``None`` if NEITHER `state/audits/conditions/` NOR `state/audits/faits/` exists.

 **A witness file WITHOUT `date:` (`conditions/*.md`) is SILENTLY ABSENT from here** — never
 counted at a made-up date. `temoins_fichiers`/`compte_temoins_fichiers` (the RAW count) remain
 the only measure that includes them. An ident whose witnesses are ALL non-datable does not
 appear at all in the returned dict (no key with an empty list)."""
    racine = repo_root / "projects" / RACINE_PRODUIT
    dossiers = [racine / d for d in _DOSSIERS_TEMOINS]
    existants = [d for d in dossiers if d.is_dir()]
    if not existants:
        return None
    par_ident: dict[str, list[str]] = {}
    for dossier in existants:
        for fichier in dossier.iterdir():
            if not fichier.is_file():
                continue
            trouve = _IDENT_TEMOIN_RE.match(fichier.name)
            if not trouve:
                continue
            date = _date_temoin(fichier)
            if date is not None:
                par_ident.setdefault(trouve.group(1), []).append(date)
    return {ident: tuple(dates) for ident, dates in par_ident.items()}


def balayage_reecriture_sibling(
    repo_root: Path, *, k_min: int = 1, k_max: int = 30
) -> tuple[BalayageK, ...] | None:
    """Signal 3, THE FULL SWEEP over the sibling project's REAL population — ``None`` if no witness folder
 exists.

 **``k_max=30`` is NOT a trigger threshold** — it is just wide enough to cover the worst
 measured case (`P6`, 25 raw witnesses counted, ~21 datable) with margin; sweeping further would
 only return empty pages. *Nothing here is calibrated on what we want to find.*"""
    par_ident = temoins_dates_par_ident(repo_root)
    if par_ident is None:
        return None
    return balayage_reecriture(par_ident, k_min, k_max)


def commits_type_ident(repo_root: Path, ident: str) -> int | None:
    """Signal 3, "git-log" proof — how many commits in the sibling project's NESTED history reference ``ident``
 via the ``type(IDENT):`` convention, or ``None`` if that repo is unreadable.

 **CALLS ``routage_journal_run.commits_par_ident`` (C6), DOES NOT REIMPLEMENT IT** —
 orchestrator's call (recorded in the project's internal session log, 2026-08-16), executed once the name was exposed
 on the chat-2 side. *One contract = one single code home, never recopied.*

 **Counts ALL commit types** (`feat`/`fix`/`test`/`docs`/`plan`/`orch`), not just C6's
 "turns" (`TYPES_DE_TOUR`, which excludes `docs`/`plan`/`orch`) — signal 3 asks "how many times
 rewritten", a broader question than "how many attempts by the producer", and
 `commits_par_ident` already groups all types before any filter."""
    sibling_root = repo_root / "projects" / _SIBLING_NICHE
    tous = commits_par_ident(sibling_root)
    if tous is None:
        return None
    return len(tous.get(ident, ()))


def balayage_reecriture_git_sibling(
    repo_root: Path, *, k_min: int = 1, k_max: int = 25
) -> tuple[BalayageK, ...] | None:
    """Signal 3, THE GIT-LOG SWEEP over the sibling project's ENTIRE population (119 idents with at least one
 commit, measured on 2026-08-16 after C6's dash fix) — ``None`` if its history is unreadable.

 **NO new pure logic**: ``balayage_reecriture`` (D5, this module) is generic — it takes any
 ``dict[ident, sorted dates]`` — that was already true for the witness-files half
 (:func:`balayage_reecriture_sibling`), and it holds here for the git-log half, over
 ``commits_dates_par_ident`` (C6) rather than a second parser.

 **``k_max=25`` is NOT a trigger threshold** — the worst measured case (``A05-2``, 20
 commits) plus a margin, the same discipline as :func:`balayage_reecriture_sibling`."""
    par_ident = commits_dates_par_ident(repo_root / "projects" / _SIBLING_NICHE)
    if par_ident is None:
        return None
    return balayage_reecriture(par_ident, k_min, k_max)


def reecriture(repo_root: Path, ident: str) -> Reecriture:
    """FULL signal 3 for ``ident`` — both proofs, each independently ``None`` if ITS source is
 unreadable, never merged (see :class:`~mnemosyne.production.plan_recul.Reecriture`).

 **NOT YET A ``Signal``, DELIBERATELY**: the trigger threshold ("rewritten K times", which
 K?) and the sweep over the sibling project's entire item population remain to be decided — publishing the
 raw counts is honest; wrapping them in a `declenche` verdict before the threshold has been
 decided would not be."""
    return Reecriture(
        ident=ident,
        commits=commits_type_ident(repo_root, ident),
        fichiers_temoins=temoins_fichiers(repo_root, ident),
    )


#: The sibling project's own NESTED repo -- NEVER `projects/.git` (see the module docstring, signal-1 section).
#: `RACINE_PRODUIT` stays the RELATIVE root shared by D1-D5; here it locates the nested `.git`
#: itself, not to filter paths inside it.
_SIBLING_NICHE = "saas/Sibling Research"

#: `- **IDENT** STATUS ...` -- the status convention of THIS repo (`docs/FORMAT_PLAN.md`), shared
#: by that sibling project (confirmed by reading its HEAD directly before this module was written). Anchored at
#: the start of a line: a status cited in PROSE (not at the head of a bullet) must never count,
#: the same trap as `A7` (a teaching example mistaken for a real item).
_ITEM_STATUT_RE = re.compile("^- \\*\\*([A-Za-z0-9-]+)\\*\\* (\U00002B1C|\U0001F504|\U00002705|\U0001F17F\U0000FE0F|\U000026D4|\U000023F8\U0000FE0F)", re.MULTILINE)


def _sibling_faits(sha: str, git_dir: Path, work_tree: Path) -> frozenset[str] | None:
    """The idents whose status is DONE (````) in the `plan/` tree at commit ``sha`` -- ``None``
 if the tree could not be read at that commit (never confused with "zero items done").

 **``git grep`` RETURNS ``rc=1`` WHEN IT FINDS NOTHING — that is NOT an error.** Git's own
 convention (0 = found, 1 = no match, ≥2 = real error) differs from most commands in this repo;
 conflating them would make an empty arc read as an unreadable tree."""
    try:
        sortie = subprocess.run(  # noqa: S603, S607
            ["git", "--git-dir", str(git_dir), "--work-tree", str(work_tree), "grep", "-h", "-E",
             _ITEM_STATUT_RE.pattern, sha, "--", "plan/"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if sortie.returncode not in (0, 1):
        return None
    faits = {
        m.group(1) for ligne in sortie.stdout.splitlines() if (m := _ITEM_STATUT_RE.match(ligne))
        if m.group(2) == "\U00002705"
    }
    return frozenset(faits)


def _sibling_tours(repo_root: Path) -> tuple[Tour, ...] | None:
    """The ENTIRE history of the sibling project's nested repo, each commit carrying the set of ```` idents
 right after it -- ``None`` if the nested repo is absent or unreadable.

 **``faits`` is ONLY RECOMPUTED on commits touching ``plan/`` (167/288)** — a commit outside
 plan/ cannot move the set of , and recomputing it would be a `git grep` wasted on a tree
 unchanged for what matters here; the others INHERIT the last known set, exactly what
 `immobilite` expects (a run of commits, not only the ones touching the measured subject)."""
    git_dir = repo_root / "projects" / _SIBLING_NICHE / ".git"
    work_tree = repo_root / "projects" / _SIBLING_NICHE
    if not git_dir.is_dir():
        return None
    try:
        historique = subprocess.run(  # noqa: S603, S607
            ["git", "--git-dir", str(git_dir), "--work-tree", str(work_tree), "log",
             "--first-parent", "--reverse", "--format=%H%x09%ad", "--date=short"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        touchent_plan_brut = subprocess.run(  # noqa: S603, S607
            ["git", "--git-dir", str(git_dir), "--work-tree", str(work_tree), "log",
             "--first-parent", "--format=%H", "--", "plan/"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if historique.returncode != 0 or touchent_plan_brut.returncode != 0:
        return None
    touchent_plan = set(touchent_plan_brut.stdout.split())

    tours: list[Tour] = []
    faits_courants: frozenset[str] | None = None
    for ligne in historique.stdout.splitlines():
        if not ligne.strip():
            continue
        sha, _, date = ligne.partition("\x09")
        if sha in touchent_plan:
            nouveaux = _sibling_faits(sha, git_dir, work_tree)
            if nouveaux is None:
                return None  # one unreadable tree breaks the whole series -- never a silent hole
            faits_courants = nouveaux
        tours.append(Tour(sha=sha, date=date, chemins=(), faits=faits_courants))
    return tuple(tours)


def immobilite_sibling(repo_root: Path) -> Immobilite | None:
    """Signal 1 -- the longest immobility over the REAL history of the sibling project's plan (its nested repo,
 not ``projects/.git``), or ``None`` if that history could not be read.

 **NOT YET A ``Signal``, DELIBERATELY — same discipline as :func:`temoins_fichiers`**: the
 trigger threshold ("immobile for N turns", which N?) is written nowhere in the item, and
 inventing it would be exactly the fault D1 already forbids. Publishing the raw measurement
 (:class:`~mnemosyne.production.plan_derive.Immobilite`) is honest; wrapping it in a
 `declenche` verdict before N has been decided would not be.

 **Sees nothing BEFORE the nested repo's root** (see the module docstring) — an even longer
 immobility, begun in the lost history, would stay invisible here."""
    tours = _sibling_tours(repo_root)
    if tours is None:
        return None
    longue, _echanges = immobilite(tours)
    return longue


def _refus_bruts_par_id(chemin: Path) -> dict[str, int]:
    """Counts RAW ``kind == "refused"`` events by ``id``, reading the JSONL directly — BYPASSES
 ``RetraitLedger.all_states()``, which folds ``refused`` into a simple boolean and so CANNOT
 distinguish "refused once" from "refused six times".

 **THIS IS THE FIX FROM THE CHAT-3 AUDIT, 2026-08-16, PROVEN BY EXECUTION**: `RetraitLedger.
 refuse()` has NO anti-repetition guard and does NOT increment `denied_count` ANYWHERE — called
 6 times on the same request, `denied_count` stayed at 0 while 6 real `refused` events piled up
 on disk, invisible to the old version of this signal.

 **Does NOT reimplement `plan_retrait._replay()`** — that one handles SIX event types and
 builds a complete state; this function does only ONE thing, tallying ONE SINGLE event type
 per id, a genuinely narrower task than the full fold. A corrupted/truncated line is ignored
 HERE (reading `denied_count` via `RetraitLedger` remains the authority that raises on REAL
 corruption; this count is a supplement, not a replacement)."""
    comptes: dict[str, int] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        try:
            evenement = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        if evenement.get("kind") == "refused":
            id_ = evenement.get("id")
            if isinstance(id_, str) and id_:
                comptes[id_] = comptes.get(id_, 0) + 1
    return comptes


def refus_repete_retrait(repo_root: Path) -> RefusRepete | None:
    """Signal 4 (SCOPE: the retrait gate, H1, ONLY) — the TWO proofs of "refused K times" (see
 :class:`~mnemosyne.production.plan_recul.RefusRepete`), or ``None`` if the ledger does not yet
 exist on disk (never confused with "measured, nobody was ever refused twice").

 **READS H1's LEDGER, DOES NOT REWRITE IT** for `denied_count` — `RetraitLedger.all_states()`
 has already folded each count from the raw events. For the raw `refused` events (which
 `RetraitLedger` does NOT count, see :func:`_refus_bruts_par_id`), this module reads the same
 file directly — a supplement to H1's public API, never a copy of its fold."""
    chemin = repo_root / "system" / "state" / "retraits_requests.jsonl"
    if not chemin.exists():
        return None
    etats = RetraitLedger(path=chemin).all_states()
    refus_bruts = _refus_bruts_par_id(chemin)
    return refus_le_plus_repete(etats, refus_bruts)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI over the REAL bricks
    """CLI: publishes the pull-back mandate with the signals measurable TODAY (D5, level 1).

 Injects NO predicate: like :func:`~mnemosyne.runtime.derive_run.resume` and
 :func:`~mnemosyne.runtime.plancher_run.resume`, TODAY's measurement reads the project's own
 declaration, never the frozen predicate from historical validation (that one lives only in the
 witnesses that replay D5)."""
    repo_root = Path.cwd()
    print(mandat_de_recul([signal_plancher(repo_root)]))
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main(sys.argv[1:]))
