"""plans — which projects carry a readable ``PLAN.md``, and which do not (arc C2).

The verifiable half of the imposed plan format: a format nobody can check is a suggestion. This
prints, per project, one of three states — readable / absent / present-but-unreadable — and NAMES
every project in each, because a count cannot tell the operator which one slipped.

It reports; it never writes, never creates a plan, and never blocks (D92 — propose, never impose).
Exit code is 0 even when every project is missing its plan: this is a status surface like
``make qdrant``, not a gate, and today the honest answer is that no project has one yet. Run::

    make plans
    python -m mnemosyne.runtime.plans_run

Brick-free and read-only. Code & docstrings English (D117); the source keeps printed output in
French for the operator (D33) — this mirror translates it to English throughout."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Final

from ..production import derives, offre_aux_projets
from ..production.plan_format import (
    PLAN_FILENAME,
    PlanReading,
    plan_skeleton,
    prerequisite_problems,
    produit_resolu_rapport,
)
from ..production import livrables, perimetre
from ..production.plan_registry import (
    ProjectPlan,
    _read_text,
    ABSENT,
    ILLISIBLE,
    LISIBLE,
    PROJECTS_DIRNAME,
    PlanRegistry,
    scan_plans,
    scan_projects,
    top_name,
)

__all__ = ["DEFAULT_PROJECTS_ROOT", "main", "render_registry", "scan_projects", "verifier_problems"]

#: Repo root from this module (``system/lib/mnemosyne/runtime/plans_run.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PROJECTS_ROOT = _REPO_ROOT / PROJECTS_DIRNAME


#: How many refused lines are printed before the rest is counted. A plan can be 900 lines long; a
#: report that scrolls past the screen is as unusable as one that says nothing.
_MAX_SHOWN_PROBLEMS = 5


def _misplaced_block(registry: PlanRegistry) -> list[str]:
    """The bubbles carrying markdown at their own root — the ONE signal a depth rule cannot give.

    Kept out of the main body because it used to sit at the very END of it, after two early returns:
    on a tree whose only project was written ONE LEVEL TOO HIGH — the most natural placement for
    anyone who has not read the rule — the scan found zero projects, returned "exists but holds no
    project", and the warning written expressly for that case was never printed. The guard was
    unreachable exactly when it was the only signal available.
    """
    if not registry.misplaced:
        return []
    return [
        f"\U000026A0\U0000FE0F **Bubble folder(s) carrying markdown at their own root**:"
        f" {', '.join(registry.misplaced)}.",
        "A project written at this level would be invisible here (a project lives at "
        "`projects/<bubble>/<project>/`). Worth checking rather than ignoring.",
        "",
    ]


def _arcs_block(reading: PlanReading) -> list[str]:
    """The arcs of a folder-shaped plan, NAMED and each with ITS OWN item count — plus the empty ones.

 **THE COUNT IS PER ARC, and the total is what hid the defect.** Emptying ``plan/collecte.md``
 by hand took a three-arc plan from *" 3 items"* to *" 2 items"* — no refusal, no file
 name, state ``lisible``. A total cannot say WHICH file went quiet, and this surface is the only
 control that runs on a PROJECT plan at all (``projects/`` is gitignored and lives in a separate
 clone with no ``core.hooksPath``, so the pre-commit barrier never sees it). The line already
 named the arcs; it now says what each one carries, so a file that stops carrying anything is
 read on the line that used to certify it.

 An item-free arc is a **FLAG, never a refusal**, and that boundary is measured rather than
 chosen: **7 of the 12 real arcs of Mnemosyne's own plan carry no item** — prose sections that
 became arc files at conversion (``contexte-en-une-ligne.md``, ``ce-qui-n-est-pas-dans-ce-plan…``).
 Refusing them, which is what an audit proposed, would have made this repo's own plan ILLISIBLE
 and blocked every commit. What IS refused, in ``fold_plan`` and therefore on all four surfaces at
 once, is the blank file — 0 of those same 12.
 """
    if not reading.parts:
        return []
    carried = Counter(item.source for item in reading.items)
    lines = [
        f"      door + {len(reading.parts)} arc(s): "
        + " · ".join(f"{part} ({carried.get(part, 0)})" for part in reading.parts)
    ]
    if empty := [part for part in reading.parts if not carried.get(part, 0)]:
        lines.append(
            f"      \U000026A0\U0000FE0F {len(empty)} arc(s) with no item at all: {' · '.join(empty)} — prose,"
            " not a refusal; worth checking that this isn't an arc that emptied out"
        )
    return lines


#: The ONE status for which "can this still START?" is still a live question.
#:
#: **THE SET IMPLEMENTED HERE WAS A DIFFERENT CLASS FROM THE ONE ITS DOCSTRING NAMED.** It said
#: *"it started, or it never will"* and held only ``{fait, clos}`` — so every item that HAD started
#: was still announced as "nothing says it can start." Measured over the real corpus:
#: **16 ``en cours``, 7 ``prêt``, 5 ``en pause`` — 28 items** accused of being unable to begin,
#: several of them visibly under way. A surface that says that about work in progress is one its
#: reader stops believing.
#:
#: Written as the COMPLEMENT, and partitioned against :data:`STATUS_LABEL` by a witness: a status
#: added to the vocabulary tomorrow cannot land on either side by accident — it reddens a test until
#: someone decides.
_CAN_STILL_START: Final = frozenset({"a_faire"})


def _blocked_block(reading: PlanReading) -> list[str]:
    """What is NOT startable, and WHO can lift it — the surface half of the ``*Prérequis*`` field.

 **THIS FUNCTION EXISTS BECAUSE THE BARRIER HAD NO CALLER — and its first version WAS the
 defect it was written to close.** ``prerequisite_problems`` shipped saying "it's the CALLER
 who carries the scope" with zero callers; the repair imported it here and then judged the
 items with its OWN test (``prerequisite is None``), so the import sat unused (``ruff F401``,
 ``make lint`` red) and ``prerequis_manquant`` was emitted by **no executed path in
 production** — 1,060 items of the corpus declare nothing and the surface said not one word
 about them. *A contract with two homes is a contract whose copies drift*, written by me one
 commit later about somebody else.

 So the judge is called, once, and it is the only thing that decides what is WRONG.

 **It is not the only thing that decides what is SHOWN, and saying otherwise was a lie six
 lines long.** This function drops the verdicts carried by items already ``fait`` or ``clos`` —
 measured on the real corpus, **28 of the judge's 197 refusals, 14%**. That filter is right (a
 settled item is not waiting to start, and announcing it as blocked teaches the reader to stop
 believing the ) but it is a SECOND predicate, and the sentence that hid it would have been
 read as a guarantee. A docstring that contradicts itself six lines apart is the phrase that
 gets quoted, not the code.

 It PUBLISHES and refuses nothing — the level this surface is allowed to have, since 0 of
 The sibling project's 168 items declare the field. What is BLOCKED is named item by item, because that is
 the question the operator actually asks ("what's waiting on me?"). What is merely UNDECLARED
 is published as a COUNT: naming 1,060 items one per line would drown the report, and a surface
 nobody reads to the end is a surface that reports nothing.

 Only an item still ``à faire`` is judged: anything done, closed, under way, ready or paused is
 no longer waiting to START. That filter is a SECOND predicate on top of the judge's verdict,
 and it is named as such rather than hidden behind "the judge, and only the judge, decides."
 """
    refused = {
        (problem.source, problem.line): problem for problem in prerequisite_problems(reading)
    }
    blocked: dict[str, list[str]] = {}
    unreadable: list[str] = []
    undeclared = 0
    for item in reading.items:
        if item.status not in _CAN_STILL_START:
            continue
        name = item.ident or item.title[:16]
        problem = refused.get((item.source, item.line))
        if problem is None:
            if not item.startable:
                blocked.setdefault(item.blocked_by, []).append(name)
        elif problem.kind == "prerequis_inconnu":
            # The judge's own sentence, which is the GLOSSED one. `blocked_by` would have printed
            # "unreadable prerequisite: ''" here — the very "accuses nothing" defect the judge's
            # message was repaired for, left intact on the only path production takes.
            unreadable.append(problem.detail)
        else:
            undeclared += 1
    lines = [
        f"      \U000026D4 {len(idents)} item(s) NOT STARTABLE — {holder}: {' · '.join(sorted(idents))}"
        for holder, idents in sorted(blocked.items())
    ]
    lines += [f"      \U000026A0\U0000FE0F unreadable prerequisite — {detail}" for detail in unreadable]
    if undeclared:
        lines.append(
            f"      \U000026A0\U0000FE0F {undeclared} item(s) with no declared `*Prérequis*` — no way to know what"
            " blocks them, so nothing says they can start; `AUCUN` is free"
        )
    return lines


def _nested_total_suffix(registry: PlanRegistry, top: str) -> str:
    """A total for a project WITH nested children, or ``""`` — constant size (bound 2, C7).

    **C7: `make plans` rendered a TREE WITH NO TOTAL, measured on a real nested project** — the
    very first line of a plan with sub-plans shows the count of its DOOR alone (sub-plans are
    never folded into its own reading, D166 clause 3: see `read_plan_tree`), and nothing adds up
    the rest. A line read alone reads as THE answer. *This is not a missing datum — the sub-plans
    are already listed just below with their real counts — it is a visual hierarchy that lies.*

    **The winning price, measured against two others BEFORE writing a line (C7)**: a GLOBAL
    total (one line at the end of the report, summing everything) answers "how many in total,"
    never "how many FOR THIS project" — the question the first line, misread, already claimed to
    settle. INDENTING sub-plans under their parent makes the hierarchy VISIBLE but still gives NO
    number — a reader in a hurry has to sum it themselves. **This total costs ZERO new lines**: it
    EXTENDS the line that already exists for the root, and only when it has children — a flat
    project (the majority of the corpus) does not see a single extra byte. This is the constant
    size of `make carte` (arc B), applied here to `make plans`.

    Counts only the READABLE sub-plans: an unreadable sub-plan has no reliable count, and silently
    leaving it out of the sum would classify it as "zero items" — the same absence of measurement
    as a zero line. It is therefore named separately, never folded into the total.
    """
    membres = [p for p in registry.projects if top_name(p.name) == top]
    if len(membres) <= 1:
        return ""
    lisibles = [m for m in membres if m.state == LISIBLE and m.reading is not None]
    illisibles = len(membres) - len(lisibles)
    total = sum(len(m.reading.items) for m in lisibles if m.reading is not None)
    sous_plans = len(membres) - 1
    suffix = f" · **{total} total across {sous_plans} sub-plan(s)**"
    if illisibles:
        # `illisibles` includes the root itself if ITS OWN door is unreadable — but this function
        # is only called for a READABLE root (see the caller), so this count only ever names a
        # DESCENDANT, never the member that carries this line.
        suffix += f" ({illisibles} unreadable, not counted)"
    return suffix


def render_registry(registry: PlanRegistry, *, projects_root: Path) -> str:
    """Render the scan as readable text — every project named, nothing summarised into a ratio."""
    lines = ["# Mnémosyne · Project Plans", ""]
    #: ``projects/`` absent is a NOTE, no longer an early return. It said *"nothing to examine"*
    #: and returned — discarding the DECLARED plan roots the scan had already read, so on a fresh
    #: clone (where the directory is gitignored BY DESIGN, as the note itself says) this surface
    #: hid Mnemosyne's own plan entirely. That invisibility is the exact defect clause 1 of D166
    #: exists to close, reopened one branch above the code that closes it. *A red pass discards
    #: everything it measured*, and so does an early return.
    absent = (
        [
            f"\U000026A0\U0000FE0F No `{projects_root}` folder — no PROJECT is examined below.",
            "",
            "*(This is normal on a freshly cloned repo: `projects/` is gitignored by"
            " design.)*",
            "",
        ]
        if not registry.root_exists
        else []
    )
    if not registry.projects:
        lines += absent or [f"`{projects_root}` exists but holds no project.", ""]
        lines += _misplaced_block(registry)
        return "\n".join(lines).rstrip() + "\n"
    lines += absent

    for project in registry.projects:
        if project.state == LISIBLE and project.reading is not None:
            reading = project.reading
            counts = reading.by_status()
            detail = " · ".join(f"{count} {label}" for label, count in _french(counts))
            # C7: the nested sub-plans' total is added ONLY on the root's own line, and
            # only when `project.name` IS that root — a named sub-plan (its own line, further
            # down) never carries this suffix, it would be wrong at its own scale.
            suffixe = (
                _nested_total_suffix(registry, project.name)
                if top_name(project.name) == project.name
                else ""
            )
            lines.append(
                f"- \U00002705 **{project.name}** — {len(reading.items)} items ({detail}){suffixe}"
            )
            lines.append(f"      cap: {reading.cap}")
            # NAMED with their own count, never a total. "4 arcs" cannot tell the operator which
            # one is missing, and this whole arc exists because an index that only says HOW MANY
            # had already rotted.
            lines += _arcs_block(reading)
            lines.append(
                f"      {reading.prose_lines} prose lines, {reading.attached_prose}"
                f" attached to an item"
            )
            # G1 — the DELIVERABLES list precedes the plan. PUBLISHED, NEVER refuses (level 1):
            # measured before wiring, 17 doors in this repo and ONLY ONE carries a list -- a
            # barrier would turn the whole repo red for a convention nobody has been able to
            # apply yet. The plan is a TRANSLATION; without the requester's own words alongside
            # it, nothing confronts it (the origin defect measured: 2 deliverables built out of
            # 10 requests).
            lines += _livrables_block(project)
            # G2 -- corollary of G1: each ITEM points at its deliverable, or declares itself
            # "my own idea." PUBLISHED, never refuses here (report level 1) -- the real refusal
            # (a target that does not exist) lives in the pure judgment itself
            # (production/livrables.py), frozen against the real population by a dedicated
            # witness, the same doctrine as G1/G3 right beside it.
            lines += _rattachements_block(project)
            # G3 -- the NEGATIVE SCOPE. PUBLISHED, never refuses here (level 1): *an exclusion
            # with no destination is a hole; with a destination, it's a ROUTING.* The refusal of
            # a DEAD pointer (level 2) is a separate gate -- a report that refuses is no longer
            # read.
            lines += _perimetre_block(project)
            if reading.untracked:
                lines.append(
                    f"      \U000026A0\U0000FE0F {reading.untracked} item(s) with no identity — displayable, but"
                    " impossible to track from one edit to the next"
                )
            if reading.summary_tables:
                lines.append(
                    f"      \U000026A0\U0000FE0F {len(reading.summary_tables)} table(s) carrying statuses —"
                    " a possible second source; the status lives on the item"
                )
            lines += _blocked_block(reading)
            # DELEGATED AUDIT OF 2026-08-15, C2 -- "the output PRINTS" and nothing printed:
            # produit_resolu_rapport() had NO caller outside its own witnesses. The same class as
            # the prerequisite_problems() barrier paid for just above (see its docstring) -- I
            # cited its REPAIRED version as license to reproduce the very defect it had closed.
            # PUBLISHED, never refuses here (item level 2, not this report's level): it is a
            # measurement, repairing the items goes to the backlog (C5), not a commit refusal.
            lines.append(f"      {produit_resolu_rapport(reading)}")
        elif project.state == ILLISIBLE:
            lines.append(f"- \U000026A0\U0000FE0F **{project.name}** — `{PLAN_FILENAME}` present but UNREADABLE")
            lines.append(f"      {project.why}")
            # "1 line(s) refused: statut_inconnu" on a 400-line plan is a wall: the reading
            # already HOLDS the line number and the offending text, and threw them away at the
            # print. Capped, with the remainder counted — a refusal that does not say WHERE is a
            # refusal nobody can act on.
            problems = project.reading.problems if project.reading is not None else ()
            for problem in problems[:_MAX_SHOWN_PROBLEMS]:
                # `where`, not `line`: a plan spans several files now, and "line 12" names five
                # different places at once. The refusal already HELD the file — printing only the
                # number threw it away, which is the same defect this branch was written to close.
                lines.append(f"      {problem.where}: {problem.detail}")
            if len(problems) > _MAX_SHOWN_PROBLEMS:
                lines.append(f"      … and {len(problems) - _MAX_SHOWN_PROBLEMS} more")
            # The per-arc counts belong HERE too, AFTER the refusals — their absence was the same
            # silence one branch over: a plan refused for one reason still has to say which of its
            # twelve files went quiet, or the reader repairs the named defect and never sees the
            # one beside it. Last, because the refusals are the actionable half.
            if project.reading is not None:
                lines += _arcs_block(project.reading)
        else:
            lines.append(f"- \U00002B1C **{project.name}** — no `{PLAN_FILENAME}`")

    lines.append("")
    absent = registry.named(ABSENT) + registry.named(ILLISIBLE)
    if absent:
        lines += [
            f"**{len(absent)} project(s) with no readable plan**: {', '.join(absent)}.",
            "",
            "The gesture, per project — create the file and fill it in "
            "(full form: `docs/FORMAT_PLAN.md`):",
            "",
            "```markdown",
            plan_skeleton("<project name>").rstrip(),
            "```",
            "",
            # THE address, posted at the one moment it is needed. This branch is what an agent
            # reads when the plan it was asked for does not exist — and until now it handed the
            # bytes of a single-file plan and nothing else, so the folder form and the command
            # that writes it were reachable only by walking Mnemosyne's directories, which a
            # project agent is right not to do. Measured the day this was written: NO file of any
            # project carried this address. A capability nothing points at is a capability nobody
            # uses.
            "*A plan that is going to grow is born as a FOLDER, and the code writes it — it "
            "refuses rather than overwriting, and the reader judges the bytes before they touch "
            "disk:*",
            "",
            "```bash",
            "make plan-emit                                    # the LITERAL structure, to apply",
            'make plan-nouveau CHEMIN="<the project folder>"   # DRY RUN; APPLY=1 writes',
            "```",
            "",
            # MEASURED (2026-08-17, an autonomy probe on a fresh agent): one sentence is enough
            # to DECLARE D176 adoption, never to HOLD it — an agent that faithfully follows THIS
            # block (the six addresses above) never learns there is a second step, writes its
            # declaration, runs `VERIFIER=1`, gets green, stops. This is the sibling project's own defect (D177:
            # declarative adoption never held) remanufactured for the next project, right here, on
            # the surface that is PULLED — so always fresh, never a bet on injected context that
            # may predate the last commit.
            "*Want to ADOPT a field format (D176), not just the form above? A "
            "line `**Format** : <tokens>` at the top of the door (the exact tokens, never "
            "hand-copied — D163: `docs/FORMAT_PLAN.md`) — and DECLARING alone HOLDS NOTHING "
            "(D177):*",
            "",
            "```bash",
            "make plan-gate-emit  # the door that HOLDS the promise -- without it, green and unheld",
            "```",
            "",
        ]
    elif registry.misplaced:
        # NOT "every project" while a directory below may hold a project this scan cannot see:
        # that is the same summary-contradicts-body defect this arc already closed once, in its
        # second form — a completeness claim over a population from which a member was just
        # excluded.
        lines += [
            "**Every project SEEN has a readable plan** (see the warning below).",
            "",
        ]
    else:
        lines += ["**Every project has a readable plan.**", ""]
    lines += _misplaced_block(registry)
    return "\n".join(lines).rstrip() + "\n"


def _courant_format_declare(registry: PlanRegistry, *, repo_root: Path) -> dict[str, str]:
    """The LIVE ``**Format** :`` of every readable door — the ``courant`` half of
    :func:`~..production.derives.verdict_adoption`, built at the boundary (that module reads no
    file, see its own docstring) from THIS scan, never a second one.

    Keyed by the door's path relative to ``repo_root``, POSIX separators — the exact shape
    :data:`~..production.derives.PORTES_QUI_DECLARENT` freezes its population in (verified against
    the 14 real sibling-project doors before this was wired: every key here landed on an entry of that
    tuple, character for character). A key mismatch would make every door read as ERASED — silent,
    total, and it is the reader that would be wrong, not the writer of the gel.
    """
    return {
        project.plan_path.relative_to(repo_root).as_posix(): project.reading.format_declare
        for project in registry.projects
        if project.state == LISIBLE and project.reading is not None
    }


def verifier_problems(registry: PlanRegistry, *, repo_root: Path) -> tuple[str, ...]:
    """What ``VERIFIER=1`` would REFUSE, named — never printed by the default (read) path.

    Two axes, both zero-cost to arm at LEVEL 2 directly (chat 3's precedent on the door: measure
    first, arm without a level-1 intermediate when the measured population is untouched by it —
    0 of 25 real plans are ILLISIBLE and 0 of 14 frozen doors are erased on the day this ships):

    * **ILLISIBLE** — a project's plan exists but the reader refused it. Already computed by the
      scan this function is handed; never re-read.
    * **adoption effacée** — :func:`~..production.derives.verdict_adoption`, THE caller this gel
      lacked (measured: zero callers outside its own test). ``courant`` is built once, from the
      same scan, and handed to the frozen population — this module never decides which doors are
      frozen, that stays :data:`~..production.derives.PORTES_QUI_DECLARENT`'s call (D163: the
      population is Mnemosyne's separate, coordinated gesture, not duplicated here).
    """
    problems: list[str] = []
    illisibles = registry.named(ILLISIBLE)
    if illisibles:
        problems.append(
            f"{len(illisibles)} plan(s) present but UNREADABLE: {', '.join(illisibles)}."
        )
    # `geles=` PASSED EXPLICITLY, never left to `verdict_adoption`'s default: a Python
    # default binds at module IMPORT, not at call time — a `monkeypatch.setattr(derives,
    # "PORTES_QUI_DECLARENT", …)` (or a hot re-edit of `derives.py`) would never reach it. Reading
    # the attribute HERE, on every call, is what makes this module a true CALLER rather than a
    # frozen copy of the population at the moment this file was loaded.
    verdict = derives.verdict_adoption(
        courant=_courant_format_declare(registry, repo_root=repo_root),
        geles=derives.PORTES_QUI_DECLARENT,
    )
    if verdict.refuse:
        problems.append(derives.message_adoption(verdict))
    return tuple(problems)


def _french(counts: dict[str, int]) -> list[tuple[str, int]]:
    """Status counts as ``(label, count)``, in the order a human reads progress."""
    from ..production.plan_format import STATUS_LABEL

    # The tuple is a READING PREFERENCE, never the vocabulary: every status the format holds and
    # this tuple forgets is appended rather than dropped. Measured why — when the format gained
    # `clos` and `en_pause`, this hardcoded copy silently omitted both, so a ten-item plan printed
    # "10 items (2 fait · 0 en cours · 1 à faire · 0 prêt)" and the detail summed to THREE. A copy
    # of a vocabulary ages away from its source, and the loss is silent by construction.
    preferred = ("fait", "en_cours", "a_faire", "pret")
    order = [*preferred, *(token for token in STATUS_LABEL if token not in preferred)]
    return [(STATUS_LABEL[token], counts[token]) for token in order]


def _perimetre_block(project: ProjectPlan) -> tuple[str, ...]:
    """The G3 lines of a project: its exclusions, and the ones that route nowhere.

    Reads the door AND its arcs -- an exclusion lives in an arc far more often than in the door
    (measured: 10 arcs out of 11 exclusions). No raising, ever: the neighbor's reader is reused."""
    if project.reading is None:
        return ()
    dossier = project.plan_path.parent
    fichiers = [project.plan_path] + sorted((dossier / "plan").rglob("*.md"))
    exclusions: tuple[perimetre.Exclusion, ...] = ()
    for f in fichiers:
        texte, _ = _read_text(f)
        if texte is not None:
            # `f.name` alone: 97 lines of the report said `ce-que-cet-arc-ne-porte-pas.md`
            # for 13 DIFFERENT files. The neighbor right beside it already closes this class
            # ("where, not line"); G3 reopened it. The path RELATIVE to the project names the
            # place.
            ou = f.relative_to(dossier) if f.is_relative_to(dossier) else Path(f.name)
            exclusions += perimetre.lire_exclusions(texte, source=str(ou))
    # THE UNIVERSE WAS DRAWN FROM A DIFFERENT SOURCE THAN THE POPULATION: exclusions come from
    # the whole subtree (above), the universe came from `project.reading` -- the DOOR alone.
    # Measured by an isolated audit: **73 refusals printed, 73 FALSE**. Both descend from the
    # same files.
    # `rglob("*.md")` NEVER SEES A FOLDER, and on the sibling project an arc IS a folder
    # (`plan/10-ordonnancement-et-lot/`). My 1st fix took refusals from 73 to **132** by removing
    # the numeric coincidence that had been covering for it by chance, without replacing it.
    # AND A SUB-PLAN'S ARCS ARE ITS SIBLINGS, NOT ITS CHILDREN: `scan_plans` registers the sibling project's
    # 13 sub-arcs as 13 SEPARATE PROJECTS, so each one looked for its arcs under itself and found
    # none. An exclusion in arc 05 that says "it's arc 10" names a SIBLING.
    # And NOTHING else: re-reading every file to pull arc letters out of it is DEAD CODE --
    # `project.reading` is already the FOLDED reading (door + arcs). Sabotage drawn: 25 green
    # witnesses, production unchanged at 0. *A sabotage that changes nothing names code to
    # remove.*
    voisins = [*(dossier / "plan").glob("*"), *dossier.parent.glob("*")]
    arcs = perimetre.arcs_de_l_arborescence(voisins) | perimetre.arcs_existants(project.reading)
    orphelines, morts = perimetre.juger(exclusions, arcs)
    return perimetre.rendre(exclusions, orphelines, morts)


def _livrables_block(project: ProjectPlan) -> tuple[str, ...]:
    """The G1 lines of a project: its deliverables list, or its NAMED absence.

    Pure in the rendering sense (it only reads) and has no effect on the exit code: `make plans`
    does not refuse a plan with no DELIVERABLES, it NAMES it. *Publishing what is missing is not
    refusing.*"""
    fichier = livrables.fichier_livrables(project.plan_path)
    if fichier is None:
        return livrables.rendre(project.plan_path, None, ())
    # THE KILL THE AUDIT FOUND: a BARE `read_text` made `make plans` RAISE entirely -- a
    # LIVRABLES.md written in Latin-1 (the realistic case: a non-UTF-8 editor, French accents), a
    # binary file, or a `chmod 000` returned `rc=1`, a traceback, and THE WHOLE REPORT LOST. A
    # LEVEL 1 clause that kills the surface it annotates is worse than no clause.
    # We IMPORT the neighboring module's reader -- its docstring already says *"never an
    # exception, on any hostile tree"* and it NAMES a symlink as its refusal. Copying it would
    # have manufactured a second version that drifts; bolting on beside it without reusing it was
    # the mistake.
    texte, pourquoi = _read_text(fichier)
    if texte is None:
        return (
            f"      \U000026A0\U0000FE0F {fichier.name} unreadable ({pourquoi}) — G1 does not judge, and does not block",
        )
    declares = livrables.lire_livrables(texte)
    textes = (
        tuple("\n".join((item.title, *item.detail)) for item in project.reading.items)
        if project.reading is not None
        else ()
    )
    return livrables.rendre(
        project.plan_path, declares, livrables.livrables_non_servis(declares, textes)
    )


def _rattachements_block(project: ProjectPlan) -> tuple[str, ...]:
    """The G2 lines of a project: each item's attachment to a deliverable, or "my own idea."

    Corollary of G1 (:func:`_livrables_block` right above): the same ``LIVRABLES`` file, the same
    reading -- :func:`~mnemosyne.production.livrables.juger_rattachements` consumes ``*Sert*``
    where G1 consumed the item's whole text. Nothing to publish with no declared deliverables: G1
    already names that absence, repeating it here would be noise over a gap one block already
    states.

    **DELEGATED AUDIT OF 2026-08-16 (G2, Q2): a readable ``LIVRABLES`` file with NO NUMBERED
    title AT ALL manufactured refusals.** G1 already names this case as "no number, hence not
    citable" (a warning); G2 treated the same situation as "the target does not exist" and
    refused EVERY item citing a number, even the most legitimate — the wrong file was blamed.
    *Nothing to cite* is not *a missing target*: with no number declared at all, there is
    structurally nothing to judge against, exactly as with no file at all.
    """
    if project.reading is None:
        return ()
    fichier = livrables.fichier_livrables(project.plan_path)
    if fichier is None:
        return ()
    texte, pourquoi = _read_text(fichier)
    if texte is None:
        return ()
    declares = livrables.lire_livrables(texte)
    if not any(liv.numero for liv in declares):
        return ()
    paires = tuple((item.ident, item.field("sert")) for item in project.reading.items if item.ident)
    return livrables.rendre_rattachements(livrables.juger_rattachements(declares, paires))


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI side effect
    """Scan every DECLARED plan root and print the report.

    Default: ``rc 0`` always — a status surface, never a gate, exactly as before. ``VERIFIER=1``
    (env, the same pattern as ``make bilan VERIFIER=1``) RETURNS the same reading view then
    REFUSES (``rc 1``) if a plan is UNREADABLE or if a frozen door (:data:`~..production.derives.
    PORTES_QUI_DECLARENT`) has lost its declaration — see :func:`verifier_problems`. This module
    remains the ONLY surface that runs on a PROJECT's plan (``projects/`` is gitignored, this
    repo's pre-commit never sees it); without this flag, it was the barrier missing from the
    adoption freeze, measured elsewhere as doubly inert.

    ``--repo-root`` rather than ``--projects-root`` since D166: the scan is over a declared list of
    roots of which ``projects/`` is one and ``docs/`` — Mnemosyne's own plan, the single plan that
    cannot live under ``projects/`` — is another. That plan was invisible to this surface for as
    long as the surface knew only one tree.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Which plans are readable — declared roots + projects (arc C2 · D166)."
    )
    parser.add_argument("--repo-root", default=str(_REPO_ROOT))
    parser.add_argument("--verifier", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.repo_root)
    verifier = args.verifier or os.environ.get("VERIFIER", "").strip() == "1"
    registry = scan_plans(root)
    print(render_registry(registry, projects_root=root / PROJECTS_DIRNAME), end="")

    # 2026-08-17 — THE ADOPTION GAP (`derives.ecart_adoption`), WIRED IN HERE BECAUSE NOBODY
    # WAS CALLING IT: built, sabotage-proven, ZERO callers outside its own test — the same class
    # `verdict_adoption` had three hours earlier, in the SAME file. LEVEL 1 DELIBERATELY: it
    # PUBLISHES, it NEVER refuses here (the refusal stays under `VERIFIER=1`,
    # `verifier_problems`, on the ONLY doors already frozen). A new adopter who declares but is
    # not yet in `PORTES_QUI_DECLARENT` is not at fault: it is waiting on a gesture.
    # `_courant_format_declare` is ALREADY built for `verifier_problems` (the same scan, never a
    # second walk of the disk) — it is exactly the `declare=` this function expects.
    # `geles=` PASSED EXPLICITLY, SAME REASON AS FOR `verdict_adoption` BELOW: a Python default
    # binds at module IMPORT, not at call time — I forgot it HERE first, on this very gesture,
    # before a test turned it red. Reading the attribute on EVERY call is what makes this module a
    # true CALLER rather than a frozen copy of the population.
    ecart = derives.ecart_adoption(
        declare=_courant_format_declare(registry, repo_root=root),
        geles=derives.PORTES_QUI_DECLARENT,
    )
    print(f"\n{derives.message_ecart(ecart)}")

    # IS THE OFFER TO PROJECTS REACHABLE? (2026-08-18) — WIRED IN HERE BECAUSE THIS IS THE
    # ONLY SURFACE AN ADOPTER ALREADY PULLS. The operator, verbatim: *"what I don't want is for
    # us to start using crutches when we already have the main tool"* — they found the defect
    # TWICE IN TWO DAYS, by hand, and no gate was watching. LEVEL 1 DELIBERATELY: it PUBLISHES,
    # it does not refuse here — the refusal lives in `tests/platform/test_offre_aux_projets.py`,
    # which judges the REAL repo on every `pytest` run. *A misaddressed document is not the
    # adopter's fault: it is ours, and it is on us to say so.*
    # The documents are read HERE, at the boundary: the production module touches no disk.
    textes = {
        chemin: (root / chemin).read_text(encoding="utf-8")
        for chemin in offre_aux_projets.DOCUMENTS_LUS_PAR_UN_PROJET
        if (root / chemin).is_file()
    }
    print(
        "\n"
        + offre_aux_projets.message_offre(
            offre_aux_projets.capacites_non_adressees(textes),
            offre_aux_projets.documents_sans_forme_atteignable(textes),
        )
    )

    if not verifier:
        return 0
    problems = verifier_problems(registry, repo_root=root)
    if problems:
        print("\n\U000026D4 VERIFIER=1 REFUSES:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nVERIFIER=1: no refusal (0 unreadable plans, every frozen door still declares).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
