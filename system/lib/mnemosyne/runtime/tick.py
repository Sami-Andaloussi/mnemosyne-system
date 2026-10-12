"""tick (autonomy driver, Q1/Q3) — one coordinated drain of ready background work, surfaced.

The DRIVER that makes the proactive nerve (soul ⑤) actually FIRE without a manual call. It runs ONE
governed drain of the orchestration engine (D93) — the autonomous proposer + any other ready background
workflow — through the BoundedScheduler (bounded + health-throttled, invariants 16 / 26 / D111), then
RENDERS the proposals the pass surfaced. Wired into the SessionStart hook (workstream A), it is the
"wake-up": the system comes to the operator of its own accord each session, proposing unbidden (D92 / D119-f).

This is the LEAN first FORM of the trigger — session cadence. A 24/7 daemon or a cron is a later upgrade
that reuses THIS same seam (one ``tick``), never a second driver. Brick-free and read-only w.r.t. the
operator's data: the drained proposer sources are META-only (a count, never the substance — invariant 22),
nothing crosses the knowledge pipeline, and every deposited proposal is INERT until the operator's review
(propose, never impose, D92 / D100). Run::

    make tick
    python -m mnemosyne.runtime.tick

Code & docstrings English (D117)."""

from __future__ import annotations

from pathlib import Path

from ..api.core_api import CoreApi, Proposal
from ..production.proposer import DETTE_PREFIX
from ..guard.walls import DEFAULT_WALLS_PATH, WallLedger
from ..ingest import intake_backlog_count
from ..ports import Bubble, GovernanceLabel, Sensitivity
from ..production.harvest import known_projects
from ..production.moisson_due import (
    ArcVu,
    arcs_a_moissonner,
    arcs_moissonnes,
    moissons_en_attente,
    moissons_sans_panne,
    resume,
    resume_attente,
    resume_candidats,
    suivi_des_moissons,
)
from ..production.parentheses import open_parenthese_count
from ..production.plan_registry import read_plan_tree
from .derive_run import resume_recent
from ..production.documents import compte_orphelins
from .documents_run import suivis
from ..production.rangement import clear_cruft_count
from ..production.proposals import open_proposal_count
from ..production.signalements import (
    oldest_open_signalement_age_days,
    open_signalement_count,
)
from ..production.veille_ledger import DEFAULT_LEDGER_PATH, unsurveyed_fiche_count
from .bootstrap import bootstrap

#: Repo root from this module (``system/lib/mnemosyne/runtime/tick.py`` → parents[4] is the repo).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_KNOWLEDGE_ROOT = _REPO_ROOT / "knowledge"
#: The operator bubble the maintenance drain runs under (``public`` supervision surface, D119-c).
_TICK_BUBBLE = Bubble("ops")


def render_proposals(proposals: tuple[Proposal, ...]) -> str:
    """Render the proposals a tick surfaced as readable markdown — or an honest 'nothing' line.

    Pure. A faithful projection of what the proactive pass came to say; it never invents a proposal, and
    an empty pass says so plainly (silence is correct — the system had nothing unbidden to raise)."""
    if not proposals:
        # TODO(public-mirror): needs human review — this literal string is asserted verbatim by
        # tests/orchestration/test_tick.py::test_render_is_honest_when_there_is_nothing_to_propose
        # (`assert "Rien à proposer" in render_proposals(())`), which is outside this sanitization
        # batch. Translating it here would break that out-of-scope test, so it is left as-is
        # (checklist rule 8/9): translate the assertion in the same gesture if this string is ever
        # translated, never only one side of the pair.
        return "# Mnémosyne · tick\n\n_Rien à proposer pour l'instant._\n"
    # MEASURED ON 2026-09-08: a signal filed among options IS an option. While this block
    # faithfully published "12 pending reports" on every startup, 12 reports stayed open for
    # 27 days — because the line surfaced between a tidying tip and an invitation to review, under
    # a heading that itself says "propose, never impose". A DEBT flagged by a third party is not a
    # proposal from this system, and filing it as one neutralizes it. So it leaves the block,
    # ahead of it, under its own heading.
    # TODO(public-mirror): needs human review — every literal string built below is asserted
    # verbatim by two out-of-scope tests: tests/orchestration/test_tick.py (the "{n} proposition/
    # propositions" singular/plural wording and adjacency) and
    # tests/orchestration/test_signalements.py::test_the_debt_is_rendered_above_the_propose_never_impose_block
    # (the "dette qu'un TIERS" and "propose, jamais impose" substrings, in that order). Translating
    # them here without updating those two out-of-scope files would silently break them, so the
    # rendered text is left in French (checklist rule 8/9); only this surrounding comment and the
    # docstring above were translated.
    dettes = tuple(p for p in proposals if p.summary.startswith(DETTE_PREFIX))
    reste = tuple(p for p in proposals if not p.summary.startswith(DETTE_PREFIX))
    lines = ["# Mnémosyne · tick", ""]
    if dettes:
        du = "Une dette" if len(dettes) == 1 else f"{len(dettes)} dettes"
        lines += [
            f"{du} qu'un TIERS a constatée — ce n'est pas une proposition, et ça ne se périme pas :",
            "",
        ]
        lines += [f"- {p.summary.removeprefix(DETTE_PREFIX)}" for p in dettes]
        lines.append("")
    if reste:
        noun = "proposition" if len(reste) == 1 else "propositions"
        lines += [
            f"{len(reste)} {noun} non sollicitée(s) — à ta revue (propose, jamais impose) :",
            "",
        ]
        lines.extend(f"- {p.summary}" for p in reste)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _compter_orphelins(repo_root: Path) -> int:
    """How many tracked documents NOTHING cites — a count, never a path (inv. 22 / D66).

    Silent (0) if the population cannot BE drawn — no git repo, `git` missing, a test tree. The
    tick is a proposal nerve, not a gate: it proposes or stays silent, it never cries out over a
    measurement it could not take. Where the absence of a measurement MUST be said, that is on the
    hand-drawn surface (`make documents`), and it says so — rc 2 and the named cause, never an
    invented "no orphan".
    """
    try:
        return compte_orphelins(repo_root, suivis(repo_root, "*.md"), suivis(repo_root))
    except Exception:  # noqa: BLE001 - a proposal nerve never breaks the tick
        return 0


def _derive(repo_root: Path) -> str | None:
    """`D1` — has the delivered share dropped within the monitored project's RECENT window.

    **TWO WINDOWS, AND THAT IS A WRITTEN DECISION.** Clause `(c1)` validates the detector on a
    known swing, in a window **closed forever** (July 15-29): republishing it on every tick would
    manufacture *an alarm nobody can turn off* — the exact defect `I2` was designed to avoid. The
    historical validation therefore runs through `make carte`; the tick itself watches what
    **moves**. *The same judge, two populations.*

    **IT IS SILENT TODAY, AND THE SILENCE IS A STATE**: the monitored repo has committed nothing
    since 2026-07-29. *A clause with no caller looks like a satisfied clause; a clause with no
    population looks like a dormant clause.* The first was a defect — closed since 10:04 — the
    second is a fact, and it will speak again once the sibling project resumes.

    **THE CLOCK IS READ HERE, AT THE EDGE, AND NOWHERE ELSE.** A judge that reads the time hands
    down a verdict that depends on the day it is invoked, and its witnesses with it.
    """
    from datetime import date

    try:
        return resume_recent(repo_root, aujourdhui=date.today().isoformat())
    except Exception as exc:  # noqa: BLE001 - it PUBLISHES the failure, it does not break the tick
        return (
            f"the plan's drift could NOT be measured ({type(exc).__name__}) — "
            "\"no drop\" and \"I could not check\" are not the same sentence."
        )


def _candidats_sans_panne(repo_root: Path) -> str | None:
    """`I3(b)` — the harvests that propose a rule WITHOUT declaring the failure it avoids.

    **THIS EDGE EXISTS SO A GATE STOPS BEING DECORATIVE.** `regle_candidate.py` was built for
    `I3(a)` and its own author measured, AT THE TOP of their audit mandate, that it *"refuses
    nothing to nobody: it refuses IF IT IS CALLED, and nothing calls it"*. Sixth occurrence of the
    class in one day here. This is the line that calls it **on every tick**.

    **LEVEL 1** — like its sibling `_moisson_due`, and for the same reason written in `I2`:
    *a forced harvest manufactures candidates*. It NAMES, it does not refuse.

    **It does NOT stay silent when it could not measure**: the tick IS the surface, so silence
    would make "every harvest declares its failure" and "I could not check" read the same way.
    *Two absent measurements compare equal.*
    """
    try:
        return resume_candidats(moissons_sans_panne(repo_root / "docs" / "moissons"))
    except Exception as exc:  # noqa: BLE001 - it PUBLISHES the failure, it does not break the tick
        return (
            "the harvests with no declared failure could NOT be measured "
            f"({type(exc).__name__}) — \"all declare\" and \"I could not check\" are not "
            "the same sentence."
        )


#: **WHAT A TICK COSTS, MEASURED ON 2026-09-08 — and it runs on EVERY session startup.**
#: ::
#:
#:     _moisson_due           5,793.7 ms   ← 96% of the total, and PRE-EXISTING before this lot
#:     _sites_de_sortie         466.7 ms
#:     _accord_chiffre          142.0 ms   ← added by lot 2
#:     _derive                   15.6 ms
#:     _besoins_ouverts           3.2 ms   ← added by lot 2
#:     _candidats_sans_panne       2.2 ms
#:     _moissons_en_attente        0.2 ms
#:     TOTAL TICK               ~6,000 ms
#:
#: **Two things this table says that must not be confused.** (a) The two lot-2 sources cost
#: **145 ms out of 6,000** — they are not the cause. (b) An early version of the bound's fix
#: scanned ALL sources before depositing: an isolated audit measured **9,087 ms**, i.e. **+3 s**,
#: of which 7,954 ms was `_moisson_due` even though the bound was skipping it. *A fix that costs
#: 3 s at startup is worse than the defect it repairs* — it was removed, and the proposer stops at
#: the bound again (`proposer.run`).
#:
#: **THE REAL COST IS ELSEWHERE AND IT IS NOT PART OF THIS LOT**: `_moisson_due` walks the plan
#: corpus of ALL projects (46,763 files outside the D166 scope at the time of measurement). This
#: is a real startup defect, measured here so it stops being invisible — and explicitly NOT fixed
#: by this lot, which is not its scope.
def _accord_chiffre(repo_root: Path) -> int | None:
    """`P6` — how many LIVE copies of a computed figure disagree, or ``None``.

    **FAIL-OPEN IS DELIBERATE, AND THAT IS A CHOICE, NOT AN OVERSIGHT**: this source runs at the
    startup of EVERY session. A failure of its instrument must not prevent the session from
    starting — the refusal lives in `make accord-chiffre`, which has its own `rc`."""
    try:
        from .accord_chiffre_run import desaccords_ouverts

        return desaccords_ouverts(repo_root)
    except Exception:
        return None


def _besoins_ouverts(repo_root: Path) -> int | None:
    """`P8` — how many needs await a decision, or ``None`` if the instrument is silent.

    **WHAT CROSSES IS A COUNT** (inv. 22): a need may name the operator's data, its content
    never leaves the channel. Fail-open, for the same reason as its neighbor."""
    try:
        from .besoins_run import besoins_ouverts

        return besoins_ouverts(repo_root)
    except Exception:
        return None


def _sites_de_sortie(repo_root: Path) -> str | None:
    """`G1` — an egress site not declared in `system/lib/`, or ``None`` if the freeze holds.

    **SCOPE, corrected after an isolated audit**: it scans `system/lib/`, the very zone
    `CLAUDE.md` already says has *"no backdoor"* — it VERIFIES that promise, it does NOT close the
    "outside" that same sentence declares open. It PUBLISHES; `make sites-de-sortie` REFUSES.

    **It does NOT stay silent when it could not measure**: a census with ZERO sites is an
    instrument failure (wrong path, empty tree), never a green."""
    try:
        from ..production.sites_de_sortie import SITES_GELES, recenser, resume, verdict

        bibliotheque = repo_root / "system" / "lib"
        if not bibliotheque.is_dir():
            # "THIS IS NOT MY TERRITORY" IS NOT "MY INSTRUMENT IS BROKEN" -- and conflating the
            # two made a neighboring witness turn red from the first minute. A tree with no
            # `system/lib` is not a Mnemosyne repo: there is nothing to survey, and crying
            # "not measured" here would be a false alarm. An instrument failure, by contrast, is a
            # folder that EXISTS and returns NO site at all -- that case stays loud.
            return None
        v = verdict(recenser(bibliotheque), SITES_GELES)
        return None if v.tient and v.compares else resume(v)
    except Exception as exc:  # noqa: BLE001 - it PUBLISHES the failure, it does not break the tick
        return (
            f"the egress sites could NOT be measured ({type(exc).__name__}) — "
            "\"the freeze holds\" and \"I could not check\" are not the same sentence."
        )


def _moissons_en_attente(repo_root: Path) -> str | None:
    """`I2-bis` — the harvests whose SELECTED candidates were never put to the test.

    **THIS EDGE EXISTS BECAUSE THE REGISTRY LOST A TOOL.** Measured on 2026-09-08: the candidate
    selected on 2026-08-17 was never revisited, and the sibling project **rebuilt it alone 16 days later**. The
    `I2` trigger listened for the EXISTENCE of an entry; what was missing was listening to its
    PROGRESS.

    **LEVEL 1** — like its two siblings, and for the same reason written in `I2`: *a forced
    harvest manufactures candidates*, and a forced trial would manufacture trials.

    **It does NOT stay silent when it could not measure**: the tick IS the surface, so silence
    would make "nothing is dormant" and "I could not check" read the same way.
    """
    try:
        suivis = suivi_des_moissons(repo_root / "docs" / "moissons")
        if suivis is None:
            # The registry exists but could not be read -- "nothing is dormant" and "I could
            # not check" do not read the same. Found by an isolated audit: a `chmod 000` was
            # silencing this source while the docstring asserted the opposite in bold.
            return (
                "the selected candidates with no trial could NOT be measured: the registry "
                "`docs/moissons/` is present but unreadable."
            )
        return resume_attente(moissons_en_attente(suivis))
    except Exception as exc:  # noqa: BLE001 - it PUBLISHES the failure, it does not break the tick
        return (
            "the selected candidates with no trial could NOT be measured "
            f"({type(exc).__name__}) — \"nothing is dormant\" and \"I could not check\" are not "
            "the same sentence."
        )


def _moisson_due(repo_root: Path) -> str | None:
    """I2 — the sentence that NAMES the closed arcs with no harvest, or ``None`` if there is
    nothing to say.

    The edge of :mod:`mnemosyne.production.moisson_due`: this is WHERE the disk gets opened, and
    through the SHARED reader (``read_plan_tree``) -- the sole enumeration of a plan's arcs. The
    judge itself reads nothing: it receives its population. *A judge that goes fetch its own
    population can find it empty and hand down a green.*

    **AND IT DOES NOT STAY SILENT WHEN IT COULD NOT MEASURE -- IT SAYS SO.** This is the one
    difference from its neighbor `_compter_orphelins`, and it is deliberate: that one stays silent
    because its measurement has a hand-drawn surface (`make documents`) where the absence declares
    itself as rc 2. **The due harvest has no second surface: the tick IS the surface.** An `except`
    that returned `None` would therefore make "no arc owes a harvest" and "I could not check" read
    **identically** -- *two absent measurements compare equal*, and that is how a detector dies
    without turning red. Level 1 to the end: it PUBLISHES the fact that it could not measure, it
    refuses nothing and does not break the tick.

    **THIS LIMIT ACTUALLY HAPPENED, AND THE COMMIT THAT CLOSED IT HAD LEFT THIS PARAGRAPH
    SAYING THE OPPOSITE (fixed on 2026-09-08, flagged by an isolated audit).** The original text
    (2026-08-15) stated: *"`known_projects` also returns noise […] none carries an arc, so none
    enters the population -- but that is a property of their CONTENT, not a guarantee from the
    enumerator. 17 folders enumerated, 2 carry arcs"*. **Twenty-four days later the content had
    changed**: this source named **36 closed arcs, all living inside disposable mutation
    copies**, and the enumerator was offering `projects/.git/objects` as a project bubble
    (51 enumerated, 16 hidden). The enumerator now CARRIES the guarantee (`known_projects`
    excludes hidden folders at both levels) -- measured on 2026-09-08: **35 enumerated, 0
    hidden**, and none of the three examples cited above still exists. *A docstring that outlives
    the defect it describes becomes an exact lie.*
    """
    try:
        # READ BEFORE THE LOOP, which was not the case in the first draft: assigned INSIDE the
        # loop, it stayed undefined when no project exists -- a `NameError` on the test tree, i.e.
        # the least-taken path, exactly where silence hides.
        deja = arcs_moissonnes(repo_root / "docs" / "moissons")
        arcs: list[ArcVu] = []
        for projet in known_projects(repo_root):
            for plan in read_plan_tree(repo_root / projet, Path(projet).name):
                lecture = plan.reading
                if lecture is None or not lecture.items:
                    continue
                arcs.append(
                    ArcVu(
                        identifiant=plan.name,
                        total=len(lecture.items),
                        faits=sum(1 for item in lecture.items if item.status == "fait"),
                    )
                )
        return resume(arcs_a_moissonner(arcs, deja))
    except Exception as exc:  # noqa: BLE001 - it PUBLISHES the failure, it stays vocal and breaks nothing
        return (
            "the closed arcs with no harvest could NOT be measured "
            f"({type(exc).__name__}) — \"no arc owes a harvest\" and \"I could not "
            "check\" are not the same sentence, and this nerve has no second surface to say so."
        )


def run_tick(
    *,
    knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    repo_root: Path = _REPO_ROOT,
    walls_path: Path = DEFAULT_WALLS_PATH,
) -> tuple[Proposal, ...]:
    """Run ONE coordinated drain of ready background work; return the proposals it surfaced.

    A pure-ish read: the drain goes through the engine + BoundedScheduler (bounded / health-throttled),
    the proposer sources are meta-only, and every deposit is inert (no pipeline, no write to the
    operator's data). ``knowledge_root``, ``ledger_path`` and ``repo_root`` are injectable so the
    suite drives it against a temp shelf, a temp review ledger and a temp tree (brick-free, D126).
    The report directory is DERIVED from ``repo_root`` rather than defaulted, so a test that
    isolates the tree isolates this source too — a hardcoded default would silently count the real
    repo's reports from inside tmp_path.

    ``walls_path`` wires a REAL :class:`~mnemosyne.guard.walls.WallLedger` into the Guard this drain
    builds (D159): `tick` is the 24/7-capable autonomous loop — the highest-value place for a silent
    refusal to matter, since nothing here is a one-shot command the operator is watching. Injectable
    for the same hermeticity reason as the three paths above."""
    api = CoreApi(
        bootstrap(walls=WallLedger(walls_path)),
        intake_backlog_count=lambda: intake_backlog_count(knowledge_root),
        unsurveyed_count=lambda: unsurveyed_fiche_count(
            knowledge_root / "distilled", ledger_path=ledger_path
        ),
        repo_cruft_count=lambda: clear_cruft_count(str(repo_root)),
        # A3, derived from repo_root for the same hermeticity reason as its neighbors: a
        # hardcoded default would count the REAL repo's orphans from inside a tmp_path.
        documents_orphelins_count=lambda: _compter_orphelins(repo_root),
        signalement_count=lambda: open_signalement_count(repo_root / "docs" / "signalements"),
        # The AGE, not just the count: it is what distinguishes a queue from STASIS.
        oldest_signalement_age_days=lambda: oldest_open_signalement_age_days(
            repo_root / "docs" / "signalements"
        ),
        # Derived from knowledge_root for the same hermeticity reason as its sibling above: a
        # hardcoded default would count the real repo's drafts from inside a tmp_path test.
        proposal_count=lambda: open_proposal_count(knowledge_root / "proposals"),
        # C8-c, derived from repo_root for the same reason as the report counter beside it.
        parenthese_count=lambda: open_parenthese_count(repo_root / "docs" / "parentheses"),
        # I2, derived from repo_root for the same hermeticity reason as its neighbors. This is the
        # ONLY source that NAMES instead of counting: what crosses is a PLAN ARC identifier (a
        # file path, the same meta `make plans` already prints), never an item title, and the
        # list is bounded to three names + a count.
        moisson_due_resume=lambda: _moisson_due(repo_root),
        candidats_sans_panne_resume=lambda: _candidats_sans_panne(repo_root),
        # I2-bis, the same edge and the same bound as its siblings: what crosses is a harvest
        # FILE NAME, never a candidate title.
        moissons_en_attente_resume=lambda: _moissons_en_attente(repo_root),
        # G1: what crosses is a `file::module`, never a line of code.
        sites_de_sortie_resume=lambda: _sites_de_sortie(repo_root),
        # P6 / P8: what crosses is a COUNT, never a document excerpt or the content of a need --
        # a need may name the operator's data (inv. 22).
        accord_chiffre_compte=lambda: _accord_chiffre(repo_root),
        besoins_ouverts_compte=lambda: _besoins_ouverts(repo_root),
        derive_resume=lambda: _derive(repo_root),
    )
    label = GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=_TICK_BUBBLE)
    api.schedule_work("autonomous_proposer", label=label)
    api.run_background()
    return api.inbox()


def main() -> int:  # pragma: no cover - CLI over the real shelf
    """Run one tick over the real shelf and print what the system proposes. A pure read (D25)."""
    print(render_proposals(run_tick()), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
