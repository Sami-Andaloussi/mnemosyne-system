"""ui_contract (arc C3) — the ONE data contract an interface reads: Mnémosyne's queues + every plan.

The operator's requirement, in their own words (2026-07-28): *"an app I can open on my PC or in a
browser, and so that is accessible even without internet,"* and *"a universal form to impose, just
so it's easier to translate into something graphically nice."* This module is that universal form.
It is handed to the UI agent instead of a tour of eleven ``make`` targets.

**A projection, never a second engine.** Every queue here already had a reader — ``open_proposals``,
``open_signalements``, ``PolicyRequestLedger``, the two replayable journals behind the living-memory
queue, and :mod:`~mnemosyne.production.plan_registry` (arc C1/C2). Measured before designing: all five
answered in under 2 ms with NO brick, no Qdrant, no MLX, no network. So the contract adds no source of
truth — it re-shapes what exists. A second reader would rot away from its original exactly like the research project's
``chantiers.yaml`` did.

**Three states per source, never two.** ``lue`` (read; ``items`` is authoritative and may legitimately
be empty), ``absente`` (the storage does not exist — nothing was ever deposited, which is not the same
as drained), ``indisponible`` (it exists and could not be read; ``pourquoi`` names why). A source that
fails must never render as a confident zero: an interface showing "0 signalements" because a directory
was unreadable is worse than one showing nothing at all.

**No count of anything the payload already carries.** Not one field says "N proposals" next to a list
of proposals. That defect — the summary drifting from the body — has been measured three times in this
repo, the last time inside a *generated* report two lines away from the body it contradicted. The only
way to close the class rather than the case is for the number not to exist: the UI calls ``.length``.

**Uniform items.** Every item in every queue carries exactly :data:`ITEM_KEYS`, always present, empty
string when a kind of item has no such thing. A renderer written for one queue renders all six — that
is what "forme universelle" buys. Absent keys would push the defensive coding into the UI, where a
missing field silently renders as nothing at all.

**Local, and it stays local.** Pure reads of local files; nothing is written (the caller prints it),
so the contract creates no new resting copy of ``perso`` material. Each item carries its own
``sensibilite`` and ``bulle`` so a renderer can never display personal matter without knowing it is
personal. Note that the proposals queue deliberately carries paths and titles but **never bodies**:
``make proposals`` states the rule — a proposal is mined from the operator's own library and cites
their sources, so it is read in the file, not digested by a machine surface (invariant 22).

Decisions: D119 (surfaces) · D82 (the two replayable journals) · D159 (the policy pipeline) ·
D153 (signalements) · invariant 2 (nothing here deletes) · invariant 22 (meta-only where it applies).
Code & docstrings English (D117); every string a human reads is French.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from .carte import ArcEtat, _prefixe_commun, carte_par_arc
from .frontmatter_status import split_frontmatter
from .plan_format import DOOR_FILENAMES, PlanReading
from .plan_registry import (
    ABSENT,
    ILLISIBLE,
    LISIBLE,
    PlanRegistry,
    ProjectPlan,
    read_plan_tree,
    scan_projects,
)
from .policy_requests import DEFAULT_LEDGER_PATH as POLICY_LEDGER_PATH
from .policy_requests import PolicyRequestLedger
from .proposals import DEFAULT_PROPOSALS_DIR, open_proposals
from .signalements import DEFAULT_SIGNALEMENTS_DIR, open_signalements

#: Repo root from here (``system/lib/mnemosyne/production/ui_contract.py`` → parents[4]).
_REPO_ROOT: Final = Path(__file__).resolve().parents[4]

#: Contract identity. The UI checks these two before parsing anything else; a breaking change to the
#: shape bumps ``VERSION`` so an old interface fails loudly instead of rendering a field that moved.
NAME: Final = "mnemosyne-ui"
VERSION: Final = 2  # 1 -> 2 on 2026-07-29 (D166): a plan is a FOLDER. The rule "a change in
#: shape bumps VERSION" applied to itself -- a field MOVED, not just was added: `chemin` (in the
#: `runs_parques` queue) used to name the plan and now names the member FILE, and the key of an
#: item with no identity moved from `plan:line` to `file:line` (without which five arcs each
#: having a line 12 rendered as ONE card). A v1 UI would have shown this with no error, which
#: is exactly the case VERSION exists to make loud.

#: The three states a source can be in. See the module docstring for why two would be a defect.
LUE: Final = "lue"
ABSENTE: Final = "absente"
INDISPONIBLE: Final = "indisponible"

#: Every item, in every queue, carries exactly these keys — the "forme universelle" (universal
#: form).
#: ``geste`` is the command that acts on THIS item; empty means nothing awaits the operator on it.
ITEM_KEYS: Final = ("id", "titre", "detail", "chemin", "sensibilite", "bulle", "etat", "geste")

#: The name Mnémosyne's own plan answers to in this payload. Kept ASCII and kept STABLE: it is the
#: ``nom`` a UI has been reading since arc C3, and the registry's own French label (``mnémosyne``)
#: belongs to ``make plans``, not to a key an interface matches on.
_MNEMOSYNE: Final = "mnemosyne"

#: Longest one-line title we derive from a body that has none (a captured learning is a paragraph).
#: The full text always travels in ``detail`` — this is what a card shows, never what it stores.
_TITLE_CHARS: Final = 110

#: Default roots, all injectable so the suite drives the contract against a temp tree (D126).
DEFAULT_PROJECTS_ROOT: Final = _REPO_ROOT / "projects"
DEFAULT_PLAN_PATH: Final = _REPO_ROOT / "docs" / "PLAN.md"
DEFAULT_HUMAN_JOURNAL_PATH: Final = _REPO_ROOT / "system" / "state" / "human_layer.jsonl"
DEFAULT_PROPOSALS_LEDGER_PATH: Final = _REPO_ROOT / "system" / "state" / "proposals.jsonl"
DEFAULT_JUDGE_REPORT_PATH: Final = _REPO_ROOT / "system" / "logs" / "judge_report.md"
DEFAULT_DISTILLED_DIR: Final = _REPO_ROOT / "knowledge" / "distilled"

#: One line of the judge's machine report: ``- **status** — `chemin` — raison``.
_REFUS_RE: Final = re.compile(r"^- \*\*(?P<etat>[^*]+)\*\* — `(?P<chemin>[^`]+)` — (?P<raison>.*)$")


@dataclass(frozen=True)
class Sources:
    """Where every queue is read from. One object so a test isolates the whole contract at once.

    A partial isolation is the trap this shape closes: a suite that redirects four roots and forgets
    the fifth silently measures the real repo from inside ``tmp_path`` — the hermeticity bug
    :mod:`~mnemosyne.runtime.tick` already had to fix twice, source by source.
    """

    repo_root: Path = _REPO_ROOT
    proposals_dir: Path = DEFAULT_PROPOSALS_DIR
    signalements_dir: Path = DEFAULT_SIGNALEMENTS_DIR
    policy_ledger: Path = POLICY_LEDGER_PATH
    human_journal: Path = DEFAULT_HUMAN_JOURNAL_PATH
    proposals_ledger: Path = DEFAULT_PROPOSALS_LEDGER_PATH
    projects_root: Path = DEFAULT_PROJECTS_ROOT
    #: The DOOR of Mnémosyne's own plan. A plan is a folder now (D166), so what is actually read is
    #: this file's PARENT: the door plus every arc in ``plan/`` beside it. The door name stays here
    #: rather than becoming a directory field because it is what a card must NAME, and because the
    #: legacy door name stays legal in :data:`DOOR_FILENAMES` — the tree reader picks whichever door
    #: exists, so this field can be wrong about the NAME without the contract losing a single item.
    mnemosyne_plan: Path = DEFAULT_PLAN_PATH
    judge_report: Path = DEFAULT_JUDGE_REPORT_PATH
    distilled_dir: Path = DEFAULT_DISTILLED_DIR
    #: Where `qui_le_tient` (the `carte` key, B4) reads `arcs:` - one seat per chat, never a project
    #: (no `postes/` mechanism exists there; see :func:`_qui_tient_par_arc`).
    postes_dir: Path = _REPO_ROOT / "docs" / "postes"

    @classmethod
    def under(cls, root: Path) -> "Sources":
        """Every source relocated under ``root`` — the whole tree at once, so none can be forgotten."""
        return cls(
            repo_root=root,
            proposals_dir=root / "knowledge" / "proposals",
            signalements_dir=root / "docs" / "signalements",
            policy_ledger=root / "system" / "state" / "policy_requests.jsonl",
            human_journal=root / "system" / "state" / "human_layer.jsonl",
            proposals_ledger=root / "system" / "state" / "proposals.jsonl",
            projects_root=root / "projects",
            mnemosyne_plan=root / "docs" / "PLAN.md",
            judge_report=root / "system" / "logs" / "judge_report.md",
            distilled_dir=root / "knowledge" / "distilled",
            postes_dir=root / "docs" / "postes",
        )


def item(
    *,
    id: str = "",  # noqa: A002 - the payload key is `id`; renaming it here would mask the shape
    titre: str = "",
    detail: str = "",
    chemin: str = "",
    sensibilite: str = "",
    bulle: str = "",
    etat: str = "",
    geste: str = "",
) -> dict[str, str]:
    """One item with EVERY contract key present — the single place an item is built.

    Structural, not disciplinary: a queue cannot forget a key because it never writes the dict
    itself. The alternative (each reader assembling its own literal) is how five near-identical
    shapes drift into five different ones, and the UI ends up with ``item.chemin ?? item.path ?? ''``.
    """
    return {
        "id": id,
        "titre": titre,
        "detail": detail,
        "chemin": chemin,
        "sensibilite": sensibilite,
        "bulle": bulle,
        "etat": etat,
        "geste": geste,
    }


def _relative(path: Path, root: Path) -> str:
    """``path`` seen from the repo root — an absolute path in a UI leaks the machine's own layout."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _shorten(text: str) -> str:
    """A one-line title from a body that has none, cut on a word boundary, never mid-word."""
    line = " ".join(text.split())
    if len(line) <= _TITLE_CHARS:
        return line
    cut = line[:_TITLE_CHARS].rsplit(" ", 1)[0]
    return (cut or line[:_TITLE_CHARS]) + "…"


def _frontmatter_field(text: str, field: str) -> str:
    """One ``field: value`` from a leading frontmatter block, unquoted. Empty when absent.

    Deliberately not a YAML parse: these files are written by our own templates, and pulling a YAML
    dependency into a read surface that must work offline buys nothing here.
    """
    split = split_frontmatter(text)
    if split is None:
        return ""
    for line in split[1].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == field:
            return value.strip().strip('"').strip("'")
    return ""


def _title_of_markdown(path: Path) -> str:
    """A displayable title for a markdown file: its ``titre:`` field, else its first ``# `` heading.

    Falls back to the filename — an interface must always have something to write on the card, and a
    title that failed to parse is not a reason to hide the item it belongs to.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return path.stem
    titled = _frontmatter_field(text, "titre")
    if titled:
        return titled
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


# --- the six queues ------------------------------------------------------------------------------


def _queue(
    clef: str,
    titre: str,
    *,
    source: str,
    geste: str,
    reader: Any,
) -> dict[str, Any]:
    """Run one reader and wrap it in the three-state envelope; an unexpected failure never propagates.

    A raised exception here would blank the WHOLE contract — every other queue lost because one
    ledger was corrupt. The interface must degrade one card at a time, and say which one.
    """
    try:
        etat, pourquoi, items = reader()
    except Exception as exc:  # noqa: BLE001 - one broken source degrades ITSELF, never the contract
        etat, pourquoi, items = (
            INDISPONIBLE,
            f"lecture impossible — {type(exc).__name__}: {exc}",
            [],
        )
    return {
        "clef": clef,
        "titre": titre,
        "source": source,
        "geste": geste,
        "etat": etat,
        "pourquoi": pourquoi,
        "items": items,
    }


def _assert_tree_is_readable(root: Path) -> None:
    """Raise if any directory or ``.md`` file under ``root`` cannot be read.

    The readers below sit on ``entries_with_status``, which is fail-OPEN **by design** (the tick must
    never die on one bad file). Chained to a queue, that design becomes the exact lie this contract
    forbids: ``rglob`` swallows a directory it cannot enter, ``status_of`` swallows a file it cannot
    read, and the card renders ``lue`` with an empty list — "0 signalement" as good news. Measured on
    2026-07-28: one unreadable FILE was enough to make an item vanish from a queue declared read.

    So the fail-open reader is left alone (the tick still needs it) and readability is asserted HERE,
    where a raise is caught by :func:`_queue` and becomes ``INDISPONIBLE`` with a reason. One byte
    per file: these directories hold tens of entries, not thousands.
    """
    for dirpath, _dirnames, filenames in root.walk(on_error=_reraise):
        for name in filenames:
            if name.endswith(".md"):
                with (dirpath / name).open("rb") as handle:
                    handle.read(1)


def _reraise(error: OSError) -> None:
    """``Path.walk`` swallows errors unless its handler raises — silence is the default here too."""
    raise error


def _read_propositions(sources: Sources) -> tuple[str, str, list[dict[str, str]]]:
    """Inert drafts awaiting review — paths and titles, NEVER bodies (see the module docstring)."""
    if not sources.proposals_dir.exists():
        return ABSENTE, "no proposal has ever been filed", []
    _assert_tree_is_readable(sources.proposals_dir)
    items = [
        item(
            id=_relative(path, sources.repo_root),
            titre=_title_of_markdown(path),
            chemin=_relative(path, sources.repo_root),
            etat="à relire",
            geste=f"make proposal-reviewed FICHIER={_relative(path, sources.repo_root)}",
        )
        for path in open_proposals(sources.proposals_dir)
    ]
    return LUE, "", items


def _read_signalements(sources: Sources) -> tuple[str, str, list[dict[str, str]]]:
    """Field reports a project filed against Mnémosyne and that no Mnémosyne session has drained."""
    if not sources.signalements_dir.exists():
        return ABSENTE, "no field report has ever been filed", []
    _assert_tree_is_readable(sources.signalements_dir)
    items = [
        item(
            id=path.stem,
            titre=_title_of_markdown(path),
            chemin=_relative(path, sources.repo_root),
            etat="ouvert",
            geste=f"make signalement-traite FICHIER={_relative(path, sources.repo_root)}",
        )
        for path in open_signalements(sources.signalements_dir)
    ]
    return LUE, "", items


def _read_fiches_refusees(sources: Sources) -> tuple[str, str, list[dict[str, str]]]:
    """Fiches the judge REFUSED — so a refusal lands somewhere instead of dying silently.

    **The operator's constraint, 2026-07-28**: *"when it's refused, it has to go somewhere [...]
    we shouldn't end up with a pile of corpses [...] ideally it should get relayed to the UI."* A
    floor that refuses without a destination manufactures a graveyard, so the floor and this queue
    ship together — never the floor alone.

    **A projection, never a second engine** (this module's rule): the verdicts already exist, written
    by ``make judge`` into its machine report. Re-judging 249 books here would cost ~10 s at every
    refresh AND fork the verdict — the door and the wall would then disagree about the same fiche.

    **A derivative ages away from its source.** The report is a snapshot; the shelf keeps moving.
    So the freshness is COMPUTED, not assumed: if any fiche is newer than the report, the card says
    so by name. And an absent report is ``ABSENTE`` with the reason spelled out — never an empty list,
    which a renderer would show as the good news "no refusals".
    """
    if not sources.judge_report.is_file():
        return (
            ABSENTE,
            "the judge has never run here — this is NOT 'no refusals', it is 'nothing has "
            "been judged'. Run `make judge`.",
            [],
        )
    lignes = sources.judge_report.read_text(encoding="utf-8", errors="replace").splitlines()
    items = [
        item(
            id=m.group("chemin"),
            titre=Path(m.group("chemin")).stem,
            detail=m.group("raison"),
            chemin=f"knowledge/distilled/{m.group('chemin')}",
            etat=m.group("etat"),
            # The TARGETED gate, not the wall: it names the passages to fix on THIS record.
            geste=f'make verbatim-check FICHE="knowledge/distilled/{m.group("chemin")}"',
        )
        for m in (_REFUS_RE.match(ligne) for ligne in lignes)
        if m is not None
    ]
    return LUE, _fraicheur_du_rapport(sources), items


def _fraicheur_du_rapport(sources: Sources) -> str:
    """Empty when the report is at least as recent as the shelf; otherwise it NAMES what moved.

    A stale card that looks fresh is the silent death this queue exists to prevent — one rung worse
    than no card at all, because it is believed.
    """
    if not sources.distilled_dir.exists():
        return ""
    stamp = sources.judge_report.stat().st_mtime
    plus_recentes = [p for p in sources.distilled_dir.rglob("*.md") if p.stat().st_mtime > stamp]
    if not plus_recentes:
        return ""
    exemple = _relative(plus_recentes[0], sources.repo_root)
    return (
        f"\U000026A0\U0000FE0F STALE: {len(plus_recentes)} record(s) have moved since the last `make judge` "
        f"(e.g. {exemple}). What is read here is the state from BEFORE. Re-run `make judge`."
    )


def _read_memoire(sources: Sources) -> tuple[str, str, list[dict[str, str]]]:
    """The living-memory validation queue, rebuilt from its two durable journals — brick-free.

    The same replay ``bootstrap`` performs (human journal FIRST so a since-decided id is not
    resurrected, then the proposals ledger), with no runtime around it: ``make memory-queue`` reads
    this through ``real_runtime``, which loads bge-m3 + a reranker + Qdrant and costs ~11 s. An
    interface cannot pay that, and a UI that hangs on a stopped container is a UI nobody opens.
    """
    # Local imports: these three pull the memory algebra, which nothing else in this module needs.
    from .human_journal import HumanLayerJournal
    from .memory import LivingMemory
    from .proposals_ledger import ProposalsLedger

    if not sources.proposals_ledger.exists() and not sources.human_journal.exists():
        return ABSENTE, "no learning has ever been captured (`make remember`)", []
    memory = LivingMemory()
    HumanLayerJournal(sources.human_journal).replay(memory)
    ProposalsLedger(sources.proposals_ledger).replay(memory)
    items = [
        item(
            id=fiche.id,
            titre=_shorten(" / ".join(sorted(fiche.content))),
            detail="\n\n".join(sorted(fiche.content)),
            sensibilite=fiche.label.sensitivity.token,
            bulle=str(fiche.label.bubble),
            etat=fiche.ftype,
            geste=f"make memory-validate ID={fiche.id}",
        )
        for fiche in memory.proposed()
    ]
    return LUE, "", items


#: What to do next with a policy request, by stage (D159). A closed request has no gesture: an
#: interface must be able to show it WITHOUT offering a button that would do nothing.
_POLICY_GESTURE: Final = {
    "depose": "make policy-examiner ID={id}",
    "examine": "make policy-approuver ID={id}",
    "approuve": "make policy-appliquer ID={id}",
    "refuse": "",
    "applique": "",
}


def _policy_detail(state: Any) -> str:
    """What was asked, preceded by every verdict already rendered on it.

    ``stage`` alone LOSES a fact that changes the conclusion. A request that was refused and then
    had its application cancelled reports ``applique`` — the property tests ``applied`` first — and
    an interface showing that stage alone would put "applied" on screen next to a request the
    operator refused with the words *"approval falsified by an agent, never given by me."*
    ``make policy-queue`` prints the stage AND a separate ``refuse:`` line for exactly this reason;
    a projection that keeps only the stage is a silent loss where the shape changed.
    """
    verdicts = []
    if state.examined:
        verdicts.append(f"REVIEW ({state.examiner_verdict}): {state.examiner_notes}")
    if state.approved:
        verdicts.append(f"APPROVED on {state.approved_at}")
    if state.refused:
        verdicts.append(f"REFUSED: {state.refused_reason}")
    if state.applied:
        verdicts.append(f"APPLIED on {state.applied_at}")
    return "\n\n".join([*verdicts, state.justification])


def _read_policy(sources: Sources) -> tuple[str, str, list[dict[str, str]]]:
    """Every policy-widening request and its stage — closed ones included, with no gesture.

    Showing only the pending ones would make the pipeline look empty and its history unreachable;
    ``make policy-queue`` lists them all for the same reason. The stage travels, so the UI filters.
    """
    if not sources.policy_ledger.exists():
        return ABSENTE, "no widening request has ever been filed", []
    items = [
        item(
            id=state.id,
            titre=state.title,
            detail=_policy_detail(state),
            sensibilite="",
            etat=state.stage,
            geste=_POLICY_GESTURE.get(state.stage, "").format(id=state.id),
        )
        for state in PolicyRequestLedger(sources.policy_ledger).all_states()
    ]
    return LUE, "", items


def _member_file(plan: str, source: str) -> str:
    """Repo-relative path of the FILE a plan line was read from — the door, or one of its arcs.

    A plan is a folder now (D166): the door names the cap, and the items live in ``plan/*.md`` beside
    it. ``PlanItem.source`` is that arc's path relative to the door's own directory, so joining it to
    the door's directory is what turns it back into something a UI can open. Empty ``source`` means
    the door itself, and then this returns exactly what every caller passed before the folder form
    existed — the mono-file plan is the floor, not a degraded case.
    """
    if not source:
        return plan
    folder = plan.rsplit("/", 1)[0] if "/" in plan else ""
    return f"{folder}/{source}" if folder else source


def _parked_from(reading: PlanReading, *, plan: str) -> list[dict[str, str]]:
    """The items of one plan — built and tested, waiting on a human gesture and nothing else."""
    return [
        item(
            # Qualified by its plan ALWAYS, not only in the fallback branch. This queue aggregates
            # every plan in the repo, and `A4` is a perfectly ordinary identity in each of them: keyed
            # on a bare id, an interface renders ONE card for three parked runs and a 9-to-18-hour run
            # disappears without a word. The test that should have seen it compared SETS.
            #
            # An IDENTITY stays keyed on the PLAN, never on the file: a plan folder is exactly the
            # scope in which the reader guarantees identities are unique (`ident_seen` threaded
            # across the arcs), and keying on the file would mint a brand-new card the day an item
            # moves from one arc to another. It would also imply that two DIFFERENT plans may not
            # both carry an `S02` — they may, and at the scale this format targets a hundred theories
            # will each name a strategy `S02`.
            #
            # The FALLBACK is where the folder form breaks the old key: without an identity, `line`
            # was the whole discriminator, and five arcs all have a line 12. So the file — which for
            # a mono-file plan IS the plan — carries it. Same reason `chemin` is the member file:
            # sending the operator to the door for an item that is not in it is a cul-de-sac.
            id=f"{plan}#{entry.ident}"
            if entry.ident
            else f"{_member_file(plan, entry.source)}:{entry.line}",
            titre=entry.title,
            detail="\n".join(entry.detail),
            chemin=_member_file(plan, entry.source),
            etat=entry.status,
        )
        for entry in reading.items
        if entry.status == "pret"
    ]


def _read_runs_parques(
    sources: Sources, registry: PlanRegistry, mnemosyne: tuple[ProjectPlan, ...]
) -> tuple[str, str, list[dict]]:
    """Everything marked anywhere — Mnémosyne's own plan AND every readable project plan.

 Scoping this to one file would be a queue that is right today and wrong the moment a project
 parks its own run: the status exists precisely to say "this awaits YOU", and a run that
 awaits the operator inside ``projects/`` awaits them just as much. ``chemin`` says which FILE
 it came from, so nothing here is an unattributed duplicate of what the ``projets`` section
 shows.

 ``mnemosyne`` arrives already read (see :func:`build_contract`) rather than being re-read here.
 This used to open ``PLAN.md`` by hand and parse the bytes of that ONE file, which is the
 mono-file assumption sitting in the queue whose whole promise is "nothing but you is holding this
    up": on a
 plan that is a folder, the door carries the cap and the ARCS carry the items, so every parked run
 would have vanished from the list — with ``etat: lue``, no reason, and nothing to notice. A queue
 that is silently empty reads as good news.
 """
    items: list[dict[str, str]] = []
    manques: list[str] = []
    for plan in mnemosyne:
        if plan.reading is not None:
            items.extend(
                _parked_from(plan.reading, plan=_relative(plan.plan_path, sources.repo_root))
            )
        elif plan.state == ABSENT:
            # A qualification on a READ state, not a third one: the queue really was read, over the
            # plans that exist. Silence here would be the defect — an empty list means "nothing is
            # parked", and the one place a parked run is most likely to live went unread.
            manques.append(
                "Mnémosyne's plan is not found — no door "
                f"({' or '.join(DOOR_FILENAMES)}) in "
                f"{_relative(sources.mnemosyne_plan.parent, sources.repo_root)}/ — only the project "
                "plans were read"
            )
        else:
            # The folder form adds a way to lose EVERYTHING: the tree reader is fail-closed on an arc
            # it cannot open, so one bad arc costs the door and all its siblings. Named rather than
            # tolerated — a loss that says its own name is survivable, a silent one is not.
            manques.append(
                f"plan not read ({_relative(plan.plan_path, sources.repo_root)}): {plan.why} — "
                "its parked runs are invisible here"
            )
    for project in registry.projects:
        if project.reading is not None:
            items.extend(
                _parked_from(project.reading, plan=_relative(project.plan_path, sources.repo_root))
            )
    # The qualification above was written for the BENIGN case (Mnémosyne's plan absent) and omitted
    # for the dangerous one: a project whose PLAN.md exists and cannot be read contributes nothing,
    # while a queue titled "Runs ready" declares a clean read. `named` returns NAMES, not a count.
    unread = registry.named(ILLISIBLE)
    if unread:
        manques.append(
            f"project plan(s) not read, so their parked runs are invisible here: {', '.join(unread)}"
        )
    return LUE, " — ".join(manques), items


# --- the projects ---------------------------------------------------------------------------------


def _plan_item(entry: Any, *, plan: str) -> dict[str, str]:
    """One plan line, in the same universal shape as a queue item, plus its status and place.

    ``fichier`` is half of that place, and it stopped being optional with D166: ``ligne 12`` located a
    line exactly as long as a plan was one file. Repo-relative like every other path in this contract,
    so a UI opens it without having to join it to anything (``PlanItem.source`` is plan-relative).
    """
    return {
        **item(
            id=entry.ident,
            titre=entry.title,
            detail="\n".join(entry.detail),
            etat=entry.status,
        ),
        "libelle": entry.label,
        "section": entry.section,
        "fichier": _member_file(plan, entry.source),
        "ligne": entry.line,
    }


def _project_payload(project: Any, sources: Sources) -> dict[str, Any]:
    """One project: its state, and — when readable — its cap, its items and what was NOT read."""
    payload: dict[str, Any] = {
        "nom": project.name,
        "bulle": project.bubble,
        "etat": project.state,
        "pourquoi": project.why,
        "chemin": _relative(project.plan_path, sources.repo_root),
        "titre": "",
        "cap": "",
        "arcs": [],
        "items": [],
        "refus": [],
        "prose": {},
    }
    reading = project.reading
    if reading is None:
        return payload
    plan = payload["chemin"]
    payload["titre"] = reading.project
    payload["cap"] = reading.cap
    # The arc files merged into this reading, NAMED and never counted — "4 arcs" cannot tell the
    # operator which one is missing. Empty for a plan that is a single file, which stays perfectly
    # legal.
    #
    # `parts` and `PlanItem.source` are the same namespace, and that is now ENFORCED upstream rather
    # than trusted: they did drift apart (`c/b.md` against `plan/c/b.md`, both docstrings claiming
    # the same thing), this file re-glued the prefix by hand with a comment begging nobody to tidy it
    # away, and `merge_plan` now refuses a pair whose key and whose lines disagree.
    payload["arcs"] = [_member_file(plan, part) for part in reading.parts]
    payload["items"] = [_plan_item(entry, plan=plan) for entry in reading.items]
    payload["refus"] = [
        # `fichier` for the same reason items carry one: a refusal nobody can locate is barely better
        # than silence, and a line number alone points into the door of a five-file plan.
        # (``PlanProblem.where`` says the same in one French string, but plan-relative — this contract
        # speaks repo-relative paths everywhere, so it composes the pair itself.)
        {
            "fichier": _member_file(plan, problem.source),
            "ligne": problem.line,
            "genre": problem.kind,
            "detail": problem.detail,
        }
        for problem in reading.problems
    ]
    # The only numbers in the contract, and they describe what is NOT in it: lines the reader
    # ignored. A caller cannot show "12 items" without being able to show what it walked past.
    #
    # `lignes_rattachees` USED TO BE HERE and was the exception that broke the rule: it counts the
    # `detail` lines this very payload carries, so it was a derived total — measured equal, 293 vs
    # 293. The barrier that forbids counters could not see it (it only compares an integer to the
    # `len()` of a SIBLING list, and these lines live in strings, inside a list, inside another
    # node). Removed rather than excused: an interface that wants the number sums `detail`, exactly
    # as it does for every other length in this contract.
    payload["prose"] = {
        "lignes_prose": reading.prose_lines,
        "lignes_total": reading.total_lines,
        "sans_identite": reading.untracked,
        "tableaux_de_synthese": list(reading.summary_tables),
    }
    return payload


def _projects_payload(
    sources: Sources, registry: PlanRegistry, *, failure: str = ""
) -> dict[str, Any]:
    """Every project, in all three states, named — plus the bubbles the depth rule cannot see into."""
    if failure:
        # The third state, for the one section that did not have it: `absente` would claim there are
        # no projects, which is the confident zero this contract exists to refuse.
        return {
            "etat": INDISPONIBLE,
            "pourquoi": failure,
            "racine": _relative(sources.projects_root, sources.repo_root),
            "mal_placees": [],
            "items": [],
        }
    if not registry.root_exists:
        return {
            "etat": ABSENTE,
            "pourquoi": (
                "no `projects/` folder — normal on a fresh repo, it is gitignored by "
                "design"
            ),
            "racine": _relative(sources.projects_root, sources.repo_root),
            "mal_placees": [],
            "items": [],
        }
    return {
        "etat": LUE,
        "pourquoi": "",
        "racine": _relative(sources.projects_root, sources.repo_root),
        "mal_placees": list(registry.misplaced),
        "items": [_project_payload(project, sources) for project in registry.projects],
    }


# --- the map, by arc (B4) ----------------------------------------------------------------------

#: A token in an `arcs:` line: optional `**` (markdown bold), one letter, optional digits.
#: Measured against the THREE real seats before writing this, not against the idealized shape of
#: the seat documents' own README (``<letter(s)> — <title>``): the real line is PROSE --
#: ``A (l'obligation) · E (le commit) · D (la dérive) · B (la carte, transférée)`` -- not a machine
#: format. Each segment cut on `·` carries its token up front, followed by free commentary.
_ARCS_LIGNE_RE: Final = re.compile(r"^arcs:\s*(.*)$", re.MULTILINE)
_ARC_TOKEN_RE: Final = re.compile(r"\*{0,2}([A-Z]\d*)\b")


def _arcs_du_poste(texte: str) -> tuple[str, ...]:
    """The arc letters ONE seat declares it holds, normalised like `carte._etiquette_de_arc`.

    ``_prefixe_commun`` (imported, never redescribed) reduces each token to the same scheme the
    map itself applies to a lone ident (``B6`` -> ``B``) -- the join key is thereby GUARANTEED
    identical to what `carte_par_arc` computes, by construction, never by coincidence."""
    trouve = _ARCS_LIGNE_RE.search(texte)
    if not trouve:
        return ()
    tokens: list[str] = []
    for segment in trouve.group(1).split("·"):
        m = _ARC_TOKEN_RE.match(segment.strip())
        if m:
            tokens.append(_prefixe_commun((m.group(1),)))
    return tuple(dict.fromkeys(tokens))  # distinct, order of appearance kept


#: What `qui_le_tient` shows for an arc with no known holder when the READ itself
#: failed -- never guessed, never confused with "nobody holds it" (an empty list that stays
#: honest only when the read itself succeeded).
INCONNU: Final = "inconnu"


def _qui_tient_par_arc(postes_dir: Path) -> tuple[dict[str, tuple[str, ...]], bool]:
    """Each arc letter -> the seat(s) that declare it, read from each seat's own `chat-*.md` file,
    plus a second member: ``True`` if at least one read failed (folder or file).

    Deliberately scoped to ``chat-*.md``: this includes ``chat-0-orchestrateur.md`` (no `arcs:`
    line, contributes nothing) but NEVER ``journal-chat-*.md`` (different prefix) nor
    ``OBSERVATIONS.md`` (a lessons file that contains the word ``arcs:`` inside an EXAMPLE code
    block, not a real seat header -- *a text detector that counted occurrences would have been
    caught out by it; this glob does not need to think about it*).

    **THIS PARSER READS FILES IT DOES NOT WRITE — a coupling named by the orchestrator
    BEFORE it existed** (in one seat's own chat file, 21:4x): `pas_a_moi` forbids WRITING to
    the seat-tracking directory, never READING it, but the day the shape of the `arcs:` field changes, this
    panel can start lying or breaking WITHOUT ANYONE KNOWING -- nothing tells whoever writes the
    seat files that a machine reader exists. Hence the second member: an unreadable seat (or the
    folder itself) NEVER lets an exception rise up to `build_contract` -- a view that breaks on
    free-form prose is a view that gets switched off; a view that ADMITS "I don't know" stays
    useful."""
    if not postes_dir.exists():
        return {}, False
    try:
        chemins = sorted(postes_dir.glob("chat-*.md"))
    except OSError:
        return {}, True
    tenants: dict[str, list[str]] = {}
    degrade = False
    for path in chemins:
        try:
            texte = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            degrade = True
            continue
        for arc in _arcs_du_poste(texte):
            tenants.setdefault(arc, []).append(path.stem)
    return {arc: tuple(postes) for arc, postes in tenants.items()}, degrade


def _arc_payload(arc: ArcEtat, *, plan: str, qui_le_tient: tuple[str, ...] = ()) -> dict[str, Any]:
    """An `ArcEtat` as JSON, plus `qui_le_tient` — a field `carte.py` cannot fill in itself
    (it would stop being pure, since it would have to read the seat-tracking directory), so it is added HERE,
    at the edge that already reads everything.

    ``fichier`` passes through `_member_file` like every other path in this contract:
    `ArcEtat.fichier` is relative to the plan's DIRECTORY (`carte.py` ignores the repo root by
    construction — a pure module knows no "root"), and a path a UI could not open without
    recomposing it itself would break the rule "every path in this contract is already relative to
    the repo". Empty (a FLAT plan, no item has a `source`) falls back to the door itself — the
    documented behaviour of `_member_file`, not a special case invented here."""
    return {
        "etiquette": arc.etiquette,
        "fichier": _member_file(plan, arc.fichier),
        "total": arc.total,
        "fait": arc.fait,
        "en_cours": arc.en_cours,
        "a_faire": arc.a_faire,
        "etat": arc.etat,
        "attend": list(arc.attend),
        "demarrable": arc.demarrable,
        "qui_le_tient": list(qui_le_tient),
    }


def _carte_payload(
    sources: Sources, mnemosyne: tuple[ProjectPlan, ...], registry: PlanRegistry
) -> dict[str, Any]:
    """By arc, for Mnémosyne's own plan and for every project -- NEVER truncated (`ArcEtat`, B4).

    Every project appears here EVEN IF unreadable (``arcs: []``) rather than being omitted: a
    project absent from this list would read as "does not exist", whereas ``projets.items``
    already shows it with its state — the same entry must never tell two different truths.

    ``qui_le_tient`` only makes sense for Mnémosyne's own plan: no `postes/` mechanism exists
    for a project, and an empty list when the notion does not apply is already this contract's
    convention (see the universal shape of an item)."""
    tenants, degrade = _qui_tient_par_arc(sources.postes_dir)
    lecture_mnemosyne = mnemosyne[0].reading
    plan_mnemosyne = _relative(mnemosyne[0].plan_path, sources.repo_root)
    arcs_mnemosyne = (
        [
            _arc_payload(
                arc,
                plan=plan_mnemosyne,
                # A DEGRADED read says nothing about the arcs an unreadable seat might have
                # claimed -- an arc with NO known holder therefore shows "inconnu" rather than an
                # empty list that would read as "nobody, and I'm sure of it". An arc that ALREADY
                # has a known holder (from another seat, read successfully) keeps its real list:
                # that fact stays true even if another file, elsewhere, could not be read.
                qui_le_tient=tenants.get(arc.etiquette) or ((INCONNU,) if degrade else ()),
            )
            for arc in carte_par_arc(lecture_mnemosyne)
        ]
        if lecture_mnemosyne is not None
        else []
    )
    return {
        "mnemosyne": arcs_mnemosyne,
        "projets": [
            {
                "nom": project.name,
                "arcs": (
                    [
                        _arc_payload(arc, plan=_relative(project.plan_path, sources.repo_root))
                        for arc in carte_par_arc(project.reading)
                    ]
                    if project.reading is not None
                    else []
                ),
            }
            for project in registry.projects
        ],
    }


# --- the contract ---------------------------------------------------------------------------------

#: The three project states, re-exported so a UI does not hardcode French strings it cannot check.
ETATS_PROJET: Final = {"lisible": LISIBLE, "absent": ABSENT, "illisible": ILLISIBLE}


def build_contract(
    sources: Sources | None = None, *, now: datetime | None = None
) -> dict[str, Any]:
    """The whole contract as plain JSON-able data — every queue, every project, nothing written.

    ``now`` is injectable so the payload is byte-stable in a test; ``sources`` relocates every root
    at once (see :meth:`Sources.under`). Pure reads: this function creates nothing, deletes nothing,
    and touches no network — the offline guarantee is structural, not a promise, because nothing it
    imports can reach one.
    """
    sources = sources or Sources()
    stamp = (now or datetime.now(UTC)).isoformat()
    # `scan_projects` was the ONE call outside every guard: the six queues degrade card by card,
    # this one raised `PermissionError` straight through the CLI — exit 1, ZERO bytes on stdout, no
    # page at all. `_visible_dirs` uses `iterdir`, which (unlike `glob`) hides nothing.
    try:
        registry, projects_failure = scan_projects(sources.projects_root), ""
    except OSError as error:
        registry = PlanRegistry(projects=(), misplaced=())
        projects_failure = f"lecture impossible — {type(error).__name__}: {error}"
    # Mnémosyne's own plan, read ONCE as a folder (door + arcs + any plan nested inside it) and
    # handed to BOTH consumers below. Two calls would be two reads of the same bytes that could
    # answer differently the day one of them is edited — the `mnemosyne` card and the parked-runs
    # queue disagreeing about the same plan is precisely the drift this module refuses to create.
    mnemosyne = read_plan_tree(sources.mnemosyne_plan.parent, _MNEMOSYNE)
    return {
        "contrat": NAME,
        "version": VERSION,
        "genere_le": stamp,
        "racine": str(sources.repo_root),
        "files": [
            _queue(
                "propositions",
                "Inert proposals to review",
                source=_relative(sources.proposals_dir, sources.repo_root),
                geste="make proposals",
                reader=lambda: _read_propositions(sources),
            ),
            _queue(
                "memoire",
                "Learnings awaiting your validation",
                source=_relative(sources.proposals_ledger, sources.repo_root),
                geste="make memory-queue",
                reader=lambda: _read_memoire(sources),
            ),
            _queue(
                "policy",
                "Policy widening requests",
                source=_relative(sources.policy_ledger, sources.repo_root),
                geste="make policy-queue",
                reader=lambda: _read_policy(sources),
            ),
            _queue(
                "signalements",
                "Failures reported by projects",
                source=_relative(sources.signalements_dir, sources.repo_root),
                geste="make signalements",
                reader=lambda: _read_signalements(sources),
            ),
            _queue(
                "fiches_refusees",
                "Records REFUSED by the judge — to re-process",
                source=_relative(sources.judge_report, sources.repo_root),
                geste="make judge",
                reader=lambda: _read_fiches_refusees(sources),
            ),
            _queue(
                "runs_parques",
                "Runs ready — built, tested, awaiting your gesture",
                # The door the tree reader actually FOUND, not the name this module defaults to:
                # the legacy door name stays legal in `DOOR_FILENAMES`, so a plan root may still
                # carry it. A card naming a file that does not exist is a card nobody trusts twice.
                source=_relative(mnemosyne[0].plan_path, sources.repo_root),
                geste="",
                reader=lambda: _read_runs_parques(sources, registry, mnemosyne),
            ),
        ],
        # Mnémosyne's own plan, graded by the rule it imposes on everyone else and shown the same
        # way. Two reasons, and the second is the one that matters: an interface whose whole purpose
        # is "where I stand" cannot omit the system's own cap; and a rule its author is exempt from
        # stops being a rule — this is what makes the missing `**Cap** :` line VISIBLE rather than a
        # detail only a test knows about.
        # `mnemosyne[0]` is the plan rooted at that folder; the rest of the tuple are plans NESTED
        # inside it, which have their own cap and their own identity scope and are therefore not this
        # one. They are not lost: every they carry is in the `runs_parques` queue above, which
        # walks the whole tuple.
        "mnemosyne": _project_payload(mnemosyne[0], sources),
        "projets": _projects_payload(sources, registry, failure=projects_failure),
        # By arc, never truncated (B4) — a SECOND view of the same truth, not a third
        # read: `carte_par_arc` (already pure) and `mnemosyne` (already read above) are reused
        # as-is, only `qui_le_tient` reads something new (the seat-tracking directory).
        "carte": _carte_payload(sources, mnemosyne, registry),
    }
