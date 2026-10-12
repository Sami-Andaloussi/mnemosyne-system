"""THE ARSENAL (track 1 - B2 + B3) - what Mnemosyne OFFERS, sorted by what it BUYS you.

> *"If you want weapons, you have weapons. If you don't want those weapons, don't take them."*
> - the operator, 2026-08-09.

**THIS IS NOT AN OBLIGATION.** This module renders an OFFER. The hard rules (sensitive-stays-local,
non-destructive, cloisonnement, producer != verifier, human oversight) are not here and never will
be: an arsenal is not an absence of laws, it is the TOOLING that becomes optional.

## What this module fixes, measured on 2026-08-09

The problem was never the NUMBER of targets, it is the absence of SORTING:

* ``make help`` - **87 targets, 29,659 bytes**, in Makefile order. The median docstring is
  **243 bytes**, the longest **1,536**, and **77 of the 87 targets exceed 100 bytes**. This is not
  a catalogue, it is a wall. *An offer you cannot browse is not an offer.*
* ``make describe`` - 3,201 bytes, readable, but it renders **7 abstract surfaces** and names no
  command. It says what the system IS, not what it BUYS you.

## The dividing line (B3), and what it does NOT say

> **What is a PROMPT belongs to the agent. What exists only HERE belongs to Mnemosyne.**

Three natures, and only one carries any weight:

* :data:`MNEMOSYNE` - a gate that REFUSES, a state of THIS repo, or a single home whose copy
  drifts. Your frontier host does not have it. **Every entry so labelled MUST name what makes it
  non-portable** (:attr:`Arme.pourquoi_ici`) - without that the label is decorative, and
  :func:`verdict` refuses it. That is the intended asymmetry: what CLAIMS is held to a harder
  standard, not what steps aside.
* :data:`DEJA_PORTE` - a prompt wrapped as a capability. **Your frontier host already does this.**
  Nothing is removed (the plan forbids it): it is flagged, and you take it if it suits you.
* :data:`ATELIER` - THIS repo's own plumbing (venv, index, hooks). Neither of the above.

**THIS CLASSIFICATION DOES NOT MEASURE "45 of 71 capabilities were never used".** That figure is
about a DIFFERENT population - the surfaces + tools + skills from ``make describe``. The Makefile's
87 targets are not the 71 capabilities, and conflating the two would produce a rate over the wrong
population. Here we classify TARGETS, full stop.

## The bijection IS the barrier

The population of targets is **injected** by the caller (:mod:`mnemosyne.runtime.arsenal_run` reads
the Makefile at the edge), never discovered here: this module is a PURE judge. The diff runs in
BOTH directions - a documented target the table does not classify is NAMED (``non_classees``), and
a table entry with no real target is too (``fantomes``). A new capability therefore cannot hide: it
stays red until someone says what it buys.

Decisions: D166 (a plan is a folder) - D170 (the single emitted home) - D137 (endorsement) -
D153 (flagging) - D159 (policy widening) - D92/D100 (propose, never impose) -
invariant 2 (non-destructive). Prose in French (D117: the operator's language; code identifiers
stay English).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

#: **WHAT BREAKS WITHOUT THIS CEILING (D165 / A4).** Without it, the line becomes `make help`'s
#: paragraph again: **average 311 bytes, median 243, max 1,536, and 77 of 87 targets above
#: 100** - that is 29,659 bytes in a heap, exactly the wall this page replaces. Sorting does not
#: save a wall: a shelf of twelve paragraphs is no more browsable than a wall of eighty. This is a
#: ceiling on data WRITTEN BY HAND, not on generated output: it BOUNDS (the author rephrases), it
#: does not DRIVE (nothing is truncated, :func:`verdict` refuses and names). It is the ONLY
#: ceiling in this module - a second one is not invented whose absence never broke anything.
ACHAT_MAX = 100

#: The three natures. ``MNEMOSYNE`` is the only one that claims anything, so it is the only one
#: that must justify itself (see ``pourquoi_ici``).
MNEMOSYNE = "mnemosyne"
DEJA_PORTE = "deja_porte"
ATELIER = "atelier"

#: Glyph + legend per nature, in reading order. The legend is printed ONCE at the top, never
#: recopied on every line: repeating it would rebuild the wall.
NATURES: tuple[tuple[str, str, str], ...] = (
    (MNEMOSYNE, "\U0001F6E1\U0000FE0F", "exists only here: a gate that refuses, a state of the repo, a single home"),
    (DEJA_PORTE, "\U0001F4AC", "a wrapped prompt - your frontier host already does this, take it or not"),
    (ATELIER, "\U0001F527", "this repo's own plumbing: venv, index, hooks"),
)

#: The rayons, in reading order. They answer **"what does this buy me?"**, never "which module
#: does this live in". One more rayon is a code edit, hence reviewed: that is what bounds their
#: number, not an invented ceiling.
RAYONS: tuple[tuple[str, str], ...] = (
    ("demarrer", "You're starting a project"),
    ("savoir", "You need to know something"),
    ("produire", "You're producing at volume"),
    ("tenir", "You want it to hold, not drift"),
    ("mur", "You've hit a wall"),
    ("ranger", "You're filing away what you learned"),
    ("entretenir", "You're maintaining the machine"),
)

#: **A MEASURED LEAK (adoption probe, 2026-08-17)**: `plan-gate-emit` lives under "mur", and a
#: probe that enters via "demarrer" (project-new/plan-nouveau/plan-emit/domain-new) declares D176
#: WITHOUT EVER learning that the gate that HOLDS it lives elsewhere - it stops as soon as it has
#: read the rayon it entered through. *Filing by rayon is correct (plan-gate-emit REFUSES a
#: commit, "mur" is the right home) - that is precisely what makes it a trap: at the moment you
#: start, you don't yet know you'll need the other rayon.*
#:
#: RENVOIS adds a SIGNPOST, never a second entry: each `(rayon, target)` pair points to a target
#: already classified elsewhere in :data:`ARSENAL`, resolved against ITS canonical description
#: (never hand-recopied - D163, the same discipline as `FIELD_NAMES` elsewhere in this repo).
#: `cible` stays classified EXACTLY ONCE in `ARSENAL`; :func:`verdict` never sees this tuple, so a
#: signpost can never be counted as a duplicate.
RENVOIS: tuple[tuple[str, str], ...] = (("demarrer", "plan-gate-emit"),)


@dataclass(frozen=True, slots=True)
class Arme:
    """One offered capability: its make target, its rayon, what it BUYS, and its nature.

    ``pourquoi_ici`` is read only for nature :data:`MNEMOSYNE`, where it is **mandatory**: it
    names what makes the capability non-portable (a gate, a repo state, a measurement). For the
    other two natures it stays empty - a humble label is not asked to defend itself."""

    cible: str
    rayon: str
    achat: str
    nature: str
    pourquoi_ici: str = ""


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the table and the real population owe each other. Everything is NAMED."""

    non_classees: tuple[str, ...]
    fantomes: tuple[str, ...]
    rayons_inconnus: tuple[str, ...]
    natures_inconnues: tuple[str, ...]
    achats_trop_longs: tuple[str, ...]
    sans_pourquoi: tuple[str, ...]
    doublons: tuple[str, ...]

    @property
    def sain(self) -> bool:
        """True when the table and the Makefile line up exactly and nothing is cheating."""
        return not (
            self.non_classees
            or self.fantomes
            or self.rayons_inconnus
            or self.natures_inconnues
            or self.achats_trop_longs
            or self.sans_pourquoi
            or self.doublons
        )


def verdict(cibles: Iterable[str], armes: Iterable[Arme]) -> Verdict:
    """PURE judge - the population of targets is INJECTED, never discovered here.

    This is A2's lesson applied: a judge that fetches its own population can find it empty and
    render a green. Here, an empty population makes ``fantomes`` full - a loud refusal."""
    reelles = frozenset(cibles)
    table = tuple(armes)
    noms = [a.cible for a in table]
    doublons = tuple(sorted(nom for nom, combien in Counter(noms).items() if combien > 1))
    connus = frozenset(noms)
    rayons = frozenset(cle for cle, _ in RAYONS)
    natures = frozenset(cle for cle, _, _ in NATURES)
    return Verdict(
        non_classees=tuple(sorted(reelles - connus)),
        fantomes=tuple(sorted(connus - reelles)),
        rayons_inconnus=tuple(sorted({a.cible for a in table if a.rayon not in rayons})),
        natures_inconnues=tuple(sorted({a.cible for a in table if a.nature not in natures})),
        achats_trop_longs=tuple(
            sorted({a.cible for a in table if len(a.achat) > ACHAT_MAX or not a.achat.strip()})
        ),
        sans_pourquoi=tuple(
            sorted({a.cible for a in table if a.nature == MNEMOSYNE and not a.pourquoi_ici.strip()})
        ),
        doublons=doublons,
    )


#: **B4 - A PROJECT'S PLAN DECLARES WHAT IT TAKES.** The exact title of the section, in a
#: plan's DOOR (D166). A cold, one-time, revisable choice - **not a form**: an absent or empty
#: section is a valid answer ("I take what I want when I need it"), and nothing anywhere refuses
#: it. It is the offer applied to itself.
TITRE_DECLARATION = "This project's arsenal"

#: A weapon declared in a door: the same shape as :func:`rendre`'s own output, so a project can
#: PASTE a line from ``make arsenal`` into its plan without rewriting it - hand-recopying is what
#: drifts (12/12 conformant against the tool, 2/10 by hand, D170).
_LIGNE_DECLAREE = re.compile(r"^\s*-\s+`make ([a-zA-Z0-9_-]+)`", re.MULTILINE)

#: **A COMMENT IS NOT A DECLARATION.** Measured on the first run: a **fresh** door used to
#: render ``('verbatim-check',)`` - the target cited as an EXAMPLE in the help comment. A text
#: detector counts citations as instances; comments are therefore stripped BEFORE reading, instead
#: of hoping nobody ever writes one.
_COMMENTAIRE = re.compile(r"<!--.*?-->", re.DOTALL)


def lire_la_declaration(porte: str) -> tuple[str, ...]:
    """The targets a plan's DOOR declares it takes. Empty when the section is absent.

    **AN ABSENT SECTION AND AN EMPTY SECTION RENDER THE SAME THING, ON PURPOSE** - both say
    "this project declared nothing", which is a legitimate answer. This is the exact exception to
    the rule "two absences of measurement must not compare equal": that rule protects a JUDGEMENT
    (where the void reads, wrongly, as a green), and there is no judgement here - nothing ever
    refuses a project that declares nothing."""
    sans_commentaire = _COMMENTAIRE.sub("", porte)
    debut = sans_commentaire.find(f"## {TITRE_DECLARATION}")
    if debut < 0:
        return ()
    reste = sans_commentaire[debut + len(TITRE_DECLARATION) + 3 :]
    suivante = reste.find("\n## ")
    section = reste if suivante < 0 else reste[:suivante]
    return tuple(dict.fromkeys(_LIGNE_DECLAREE.findall(section)))


def armes_declarees(
    declarees: Iterable[str], armes: Iterable[Arme]
) -> tuple[tuple[Arme, ...], tuple[str, ...]]:
    """Render (the retained weapons, in catalogue order; the declarations that name nothing).

    Order comes from the CATALOGUE, not the declaration: a project that pastes its lines out of
    order still reads its rayons in order. An unknown declaration is NAMED and never silent - it
    is the one place this path refuses anything, and it refuses a typo."""
    voulues = tuple(dict.fromkeys(declarees))
    table = tuple(armes)
    connues = {a.cible for a in table}
    return (
        tuple(a for a in table if a.cible in set(voulues)),
        tuple(c for c in voulues if c not in connues),
    )


def rendre(
    armes: Iterable[Arme], *, detail: bool = False, renvois: Iterable[tuple[str, str]] = RENVOIS
) -> str:
    """Render the offer: one rayon per title, ONE line per weapon, the legend printed once.

 ``detail`` adds, under every weapon of nature :data:`MNEMOSYNE`, what makes it non-portable.
 Off by default: this module's promise is the 30-second page, and the justification is held by
 the test, not by the display.

 ``renvois`` (default :data:`RENVOIS`) adds, per rayon, a SIGNPOST toward a target classified
 elsewhere - never a second entry. A parameter rather than read off the module, like ``armes``:
 this render stays a PURE judge, its whole population is injected. The signpost starts with
 ``- `` (never `` - `make `` at the head, and never ``↳`` - reserved for ``detail`` mode):
 neither the shape :func:`lire_la_declaration` recognizes as an adoption (a project that pastes
 a signpost into its door does not accidentally declare a target it only looked up), nor the
 shape ``detail`` mode uses."""
    table = tuple(armes)
    par_cible = {a.cible: a for a in table}
    titres = dict(RAYONS)
    lignes = [
        "# The arsenal - what Mnemosyne offers you",
        "",
        "Take what you want. Nothing here is mandatory: the hard rules are not on this page, the",
        "tooling is. Sorted by what it BUYS you, not by order of appearance.",
        "",
    ]
    lignes.extend(f"{glyphe} {legende}" for _, glyphe, legende in NATURES)
    glyphes = {cle: glyphe for cle, glyphe, _ in NATURES}
    for cle, titre in RAYONS:
        rayon = tuple(a for a in table if a.rayon == cle)
        renvois_ici = tuple(
            par_cible[cible]
            for renvoi_cle, cible in renvois
            if renvoi_cle == cle and cible in par_cible
        )
        lignes.extend(("", f"## {titre}"))
        if not rayon and not renvois_ici:
            lignes.append("_nothing in this rayon_")
            continue
        for arme in rayon:
            lignes.append(f"- `make {arme.cible}` {glyphes.get(arme.nature, '?')} {arme.achat}")
            if detail and arme.pourquoi_ici:
                lignes.append(f"      ↳ {arme.pourquoi_ici}")
        for arme in renvois_ici:
            lignes.append(
                f'- \U000025B6 `make {arme.cible}` (filed under "{titres.get(arme.rayon, arme.rayon)}") '
                f"{glyphes.get(arme.nature, '?')} {arme.achat}"
            )
    return "\n".join(lignes).rstrip() + "\n"


def rendre_le_verdict(v: Verdict) -> str:
    """Render the gaps, each with its cause NAMED. Empty when everything lines up."""
    causes = (
        (
            "non_classees",
            v.non_classees,
            "target documented in the Makefile that the table does not classify",
        ),
        ("fantomes", v.fantomes, "table entry that names no documented target"),
        ("doublons", v.doublons, "target classified more than once"),
        ("rayons_inconnus", v.rayons_inconnus, "rayon outside of RAYONS"),
        ("natures_inconnues", v.natures_inconnues, "nature outside of NATURES"),
        (
            "achats_trop_longs",
            v.achats_trop_longs,
            f'"what it buys" empty or > {ACHAT_MAX} chars',
        ),
        (
            "sans_pourquoi",
            v.sans_pourquoi,
            "labelled mnemosyne without saying what makes it non-portable",
        ),
    )
    lignes: list[str] = []
    for nom, cibles, explication in causes:
        if cibles:
            lignes.append(f"- **{nom}** ({len(cibles)}) - {explication}: {', '.join(cibles)}")
    return "\n".join(lignes)


#: **THE TABLE.** One line per documented Makefile target, and the bijection above keeps it
#: aligned: adding a target without saying what it buys makes the suite go RED. The order inside
#: a rayon is reading order (what you do first, first), not alphabetical.
#:
#: TODO(public-mirror): needs human review - six entries below (bilan, tick, reprise, signaler,
#: signalements, signalement-traite) name Makefile targets that this public mirror's own Makefile
#: does NOT ship (see the contract's "Makefile targets dropped in the export" list). Left
#: unchanged rather than removed, for the same reason as the analogous note in
#: offre_aux_projets.py: this is curated judgment data, not prose, and only a human can decide
#: whether to trim the catalogue for the public copy or accept that the bijection tests below
#: (tests/platform/test_arsenal.py) will report these six as `fantomes` against this export's
#: Makefile.
ARSENAL: tuple[Arme, ...] = (
    # ── You're starting a project ────────────────────────────────────────────────────────────
    Arme(
        "arsenal",
        "demarrer",
        "THIS page - what Mnemosyne offers, sorted by what it buys; you take what you want",
        MNEMOSYNE,
        "bijection checked against the Makefile: a new, unclassified target is NAMED, "
        "it cannot hide",
    ),
    Arme(
        "describe",
        "demarrer",
        "what you have access to -- identity, active tools/skills (code), surfaces (kept by hand)",
        ATELIER,
    ),
    Arme(
        "project-new",
        "demarrer",
        "a cloisonned bubble with its deny-by-default profile, PROPOSED - never activated on its own",
        MNEMOSYNE,
        "the cloisonnement profile is computed here; activation stays a human gesture (D54-3b)",
    ),
    Arme(
        "plan-nouveau",
        "demarrer",
        "a plan that is BORN conformant: door, arcs, index entry - a sub-plan registers with its parent",
        MNEMOSYNE,
        "the READER itself (plan_format) judges the bytes BEFORE any write: born here, "
        "a plan clears the pre-commit barrier on the first try",
    ),
    Arme(
        "plan-emit",
        "demarrer",
        "the LITERAL structure of a plan, replayed from the code instead of being hand-copied",
        MNEMOSYNE,
        "measured (D170): 12/12 conformant against the tool, 2/10 by hand - a copy drifts",
    ),
    Arme(
        "domain-new",
        "demarrer",
        "a library domain + the exact policy line for the operator to sign off on",
        MNEMOSYNE,
        "writing into the protected zone is the operator's gesture: the target EMITS the line, it never writes it",
    ),
    Arme(
        "cours",
        "demarrer",
        "the exact mandate to write a sourceable course on ONE project",
        DEJA_PORTE,
    ),
    Arme(
        "cours-emit",
        "demarrer",
        "the same course mandate, printed for a frontier host",
        DEJA_PORTE,
    ),
    Arme(
        "cours-verifier",
        "demarrer",
        "the gate that refuses a course that is empty, sourceless, or too template-like",
        MNEMOSYNE,
        "checks the course's structure against its expected sources; this repo-side check does not live at the host",
    ),
    # ── You need to know something ───────────────────────────────────────────────────────────
    Arme(
        "search",
        "savoir",
        "the corpus's passages, cited and traceable - retrieval only, no model loaded",
        ATELIER,
    ),
    Arme(
        "qdrant",
        "savoir",
        "how much the index REALLY contains: an empty index can no longer pass for the library",
        MNEMOSYNE,
        "counts the points per collection: without this figure, \"0 results\" reads as \"the corpus "
        "doesn't have it\"",
    ),
    Arme(
        "qdrant-up",
        "savoir",
        "restart the index that went dark - the gesture that search's own refusal NAMES",
        ATELIER,
    ),
    Arme(
        "rappel",
        "savoir",
        "what was said in our past sessions - full text, zero model, zero cost, ~2 s",
        MNEMOSYNE,
        "THIS repo's own transcripts: no host carries them, and it is PULLED, nothing is injected",
    ),
    Arme(
        "rappel-fenetre",
        "savoir",
        "the messages around a hit, put back in the order they were said",
        MNEMOSYNE,
        "same local source: a conversation excerpt cannot be reconstructed from memory",
    ),
    Arme(
        "lecons",
        "savoir",
        "lessons PULLED instead of pushed on you: you ask, instead of receiving everything at startup",
        MNEMOSYNE,
        "41,059 bytes of index used to be PUSHED into every session; here the fiches are queried, "
        "and the count of fiches searched is always printed",
    ),
    Arme(
        "endorse-queue",
        "savoir",
        "which documents are CITABLE and which are still work in progress (D137)",
        MNEMOSYNE,
        "endorsement is a logged state of the repo, not a judgement redone from memory",
    ),
    Arme(
        "endorse",
        "savoir",
        "endorse a BATCH of sources as citable - your gesture, an append-only log, nothing erased",
        MNEMOSYNE,
        "append-only journal; RETRACT always narrows for free (invariant 2)",
    ),
    # ── You're producing at volume ───────────────────────────────────────────────────────────
    Arme(
        "distill-sommaire",
        "produire",
        "the book's map: where a chapter lives, without printing the book",
        MNEMOSYNE,
        "measured: finding a chapter used to cost 1,008,988 bytes of stdout",
    ),
    Arme(
        "distill-emit",
        "produire",
        "the exact prompts + schema + source verdict for ONE book, ready to hand to agents",
        MNEMOSYNE,
        "carries the REAL source verdict and breakdown of the book - an agent cannot invent them",
    ),
    Arme(
        "distill-emit-split",
        "produire",
        "one prompt PER SECTION + the split plan: a big book does not fit in one agent",
        MNEMOSYNE,
        "the split comes from the real text, not an estimate",
    ),
    Arme(
        "distill-apply",
        "produire",
        "assembles the fiche from agents' answers and DEMANDS completeness",
        MNEMOSYNE,
        "applies the verbatim floor (D143): a paraphrased fiche is refused, not merely flagged",
    ),
    Arme("distill", "produire", "distill ONE book locally (MLX)", ATELIER),
    Arme(
        "distill-batch",
        "produire",
        "distill IN PARALLEL via Haiku - a frontier campaign, idempotent, resumable",
        ATELIER,
    ),
    Arme(
        "verbatim-check",
        "produire",
        "the verbatim floor replayed on ONE fiche: exit != 0, it does not enter the base",
        MNEMOSYNE,
        "a deterministic gate no frontier host carries - and it NAMES the discarded passages",
    ),
    Arme(
        "judge",
        "produire",
        "the same floor over ALL of distilled/ - 249 books in 9.79 s, a written report",
        MNEMOSYNE,
        "same home as verbatim-check, in bulk: the judgment is never redone by eye",
    ),
    Arme(
        "finish",
        "produire",
        "the readability floor, deterministic, that NEVER touches the fiche's body",
        MNEMOSYNE,
        "rebuilds chapter titles without a model; P3 is untouchable by construction",
    ),
    Arme(
        "finish-emit",
        "produire",
        "the exact polishing contract for a frontier host, with the real chapter state",
        MNEMOSYNE,
        "carries the fail-closed verdict and this fiche's real chapter state",
    ),
    Arme(
        "lot-emit",
        "produire",
        "E4: an arc chat's mandate - its items, its aggregated *À lire*, its check-in",
        MNEMOSYNE,
        "assembled from fields ALREADY published in this repo's plan, never an orchestrator's "
        "invented reasoning - a test goes red if that leaks",
    ),
    Arme(
        "ingest",
        "produire",
        "re-index the shelf into the real stores - non-destructive, resumable",
        ATELIER,
    ),
    Arme(
        "local-run",
        "produire",
        "hand ONE bounded task to the local model and read its answer",
        ATELIER,
    ),
    Arme("agent", "produire", "the governed agent for real, on the real bricks", ATELIER),
    Arme(
        "modeles",
        "produire",
        "the local model basket, checked against disk in BOTH directions; no defaults",
        MNEMOSYNE,
        "declared-but-absent, present-but-undeclared, and drifted weights are three named refusals",
    ),
    Arme(
        "declassify",
        "produire",
        "declassify a sensitive deliverable into a public copy - your gesture, a DISTINCT audit required",
        MNEMOSYNE,
        "the only wired egress gate (D107/D147): it demands a verifier distinct from the producer",
    ),
    Arme(
        # Chat 2's target (I6). The "achat" is taken from ITS OWN Makefile help line, not
        # invented: classifying someone else's target without reading what it says would fabricate
        # a false description in the very table that claims to say what each weapon buys.
        "rendement",
        "tenir",
        "how many DETECTED lessons produced a fiche -- and the same count when nothing is detected",
        MNEMOSYNE,
        "the no-detection witness is not optional: without it, a rate reads without its denominator",
    ),
    Arme(
        "enqueter",
        "savoir",
        "a project question -> a mandate that CALLS the engines, and a SOURCED fiche or nothing",
        MNEMOSYNE,
        "the gate refuses to file a fiche if a single claim has no RESOLVED source",
    ),
    Arme(
        "completude",
        "tenir",
        "the plan checked against a reference that does NOT derive from it: the gaps are published",
        MNEMOSYNE,
        "precedence is MEASURED via git, never declared; and it refuses a reference that shrinks",
    ),
    Arme(
        "veille",
        "produire",
        "extract principles / skills / hypotheses from a batch of fiches, as inert drafts",
        DEJA_PORTE,
    ),
    Arme(
        "moisson",
        "produire",
        "what a finished project arc owes back to the system, as a mandate for domain experts",
        DEJA_PORTE,
    ),
    Arme(
        "figures-enrich",
        "produire",
        "fill a .md's figure holes from its source PDF, in place",
        ATELIER,
    ),
    Arme(
        "caption-pilot",
        "produire",
        "caption ONE book's figures with the local VLM (pilot)",
        ATELIER,
    ),
    Arme("youtube-pilot", "produire", "fetch the transcript of ONE video (pilot)", ATELIER),
    Arme(
        "youtube-ingest",
        "produire",
        "capture a YouTube transcript INTO memory, through the Guard",
        ATELIER,
    ),
    Arme(
        "raptor-build",
        "produire",
        "the RAPTOR summary tree (RAG level 2) - many calls, in series",
        ATELIER,
    ),
    Arme(
        "raptor-report",
        "produire",
        "the dry view of raptor-build: what it would do, without calling or writing anything",
        ATELIER,
    ),
    # ── You want it to hold, not drift ───────────────────────────────────────────────────────
    Arme("test", "tenir", "the local test ladder (pytest)", ATELIER),
    Arme("lint", "tenir", "ruff", ATELIER),
    Arme("fmt", "tenir", "format", ATELIER),
    Arme("check", "tenir", "lint + test: the complete local gate", ATELIER),
    Arme(
        "plans",
        "tenir",
        "which plans are READABLE and which are not - names each one, never blocks",
        MNEMOSYNE,
        "the plan reader (D166) judges the real bytes of THIS repo's own plans",
    ),
    Arme(
        "carte",
        "tenir",
        "WHERE THINGS STAND on one page that does not GROW: 168 steps and 10,000 render the same lines",
        MNEMOSYNE,
        "every bounded section SAYS how much it is hiding - a silent excerpt reads as a complete "
        "list; and it REFUSES to draw over an unreadable plan rather than render an honest view "
        "of a stale source",
    ),
    Arme(
        "plan-archiver",
        "tenir",
        "move what is DONE out of a live plan - moves bytes, rewrites NONE of them",
        MNEMOSYNE,
        "the reconstruction (archive + remainder = original, byte for byte) is verified "
        "BEFORE any write, or the command refuses",
    ),
    Arme(
        "plan-convertir",
        "tenir",
        "a file-plan becomes a folder-plan - the same exact-reconstruction requirement",
        MNEMOSYNE,
        "refuses rather than guessing: seven named causes, and any single one blocks the WHOLE conversion",
    ),
    Arme(
        "plan-corbeille",
        "tenir",
        "move ONE already-withdrawn item (H1) to the permanent trash - a memory of the WITHDRAWN",
        MNEMOSYNE,
        "same pattern as plan-archiver: reconstruction verified BEFORE writing, trash first, "
        "arc last (invariant 2, a failure between the two duplicates, never loses)",
    ),
    Arme(
        "memoire",
        "tenir",
        "the memory overflow index + its ratchet: dead links, orphans, an index that keeps growing",
        MNEMOSYNE,
        "bijection by SET diff across the two indexes; refuses in BOTH directions",
    ),
    Arme(
        "skill-audit",
        "tenir",
        "verify IN CODE that a candidate skill respects the anatomy",
        MNEMOSYNE,
        "the emit seam and anti-drift are checked by code, not proofread by eye",
    ),
    Arme(
        "skill-eprouver",
        "tenir",
        "the differential trial, step 1: two mandates + a secret salt, blindness holds",
        MNEMOSYNE,
        "the bare arm's mandate is built by a function that never receives the skill's name",
    ),
    Arme(
        "skill-juger",
        "tenir",
        "step 2: the judge's mandate, A/B under the salt - REFUSES if an output names its own arm",
        MNEMOSYNE,
        "measured on the first real run: the equipped arm cited its own artefact, so blindness would have failed",
    ),
    Arme(
        "skill-verdict",
        "tenir",
        "step 3: record what the trial showed - blindness has NO defect",
        MNEMOSYNE,
        "a verdict silent about its own blindness reads exactly like a clean verdict: it refuses",
    ),
    Arme(
        "skill-epreuves",
        "tenir",
        "the trial log - `nuit` verdicts first, and unreadable lines COUNTED",
        MNEMOSYNE,
        "a verdict nobody can read is a verdict that does not exist: it counts them",
    ),
    Arme(
        "skill-new",
        "tenir",
        "the scaffolding for a draft skill - your host already writes this very well on its own",
        DEJA_PORTE,
    ),
    Arme(
        "skill-emit", "tenir", "a skill's anatomy + the list of the 6 lessons, as text", DEJA_PORTE
    ),
    Arme(
        "harnais-de-sabotage",
        "tenir",
        "deliberately breaks a guarantee to prove a test BITES, never that it is merely assumed green",
        MNEMOSYNE,
        "measured (flagship project's harvest, 2026-08-17): the flagship project reinvented this harness 3 times separately "
        "(2026-08-07/09/10), 5 to 9 days BEFORE this skill even existed as a draft here -- "
        "a frontier host does not reliably produce it alone. Differential trial: the arm "
        "WITH it produces a whole class of proof (a control mutation) absent from the arm WITHOUT "
        "(`system/state/skill_trials.jsonl`, outcome `differencie`).",
    ),
    Arme(
        "orphelins",
        "tenir",
        "declared owner vs. measured producer, for every production/runtime file",
        MNEMOSYNE,
        "reads the FOUR declared mon_lot: values (the three chats and the orchestrator) and the "
        "real Co-Authored-By of THIS repo's own git history - a gap that exists nowhere else",
    ),
    Arme(
        "orchestration-borne",
        "tenir",
        "E2: the number of chats to launch, DERIVED - never a hand-written value",
        MNEMOSYNE,
        "measures live the width of this repo's REAL plan (startable arcs), reuses "
        "ArcEtat.demarrable from make carte, no second calculation",
    ),
    Arme(
        "regle-promouvoir",
        "tenir",
        "level 1: NAMES (never runs) the chain toward a rule's differential trial",
        MNEMOSYNE,
        "a real gate that REFUSES if the failure is not declared - the caller stays optional (I3)",
    ),
    Arme(
        "obligation",
        "tenir",
        "PUBLISHES the obligation scale (1 nudge / 2 barrier / 3 incapacity) for every target",
        MNEMOSYNE,
        "the registry lives in this repository's own governance docs - a state of THIS repo, never "
        "a general rule; refuses (rc 1) if the registry contradicts itself",
    ),
    Arme(
        "fermeture-isolee",
        "tenir",
        "PUBLISHES closed items whose git history names NO second identity (H5)",
        MNEMOSYNE,
        "reads THIS repo's real Co-Authored-By history - a floor, never proof that an audit "
        "took place (chats sharing the same model stay indistinguishable)",
    ),
    # ── You've hit a wall ────────────────────────────────────────────────────────────────────
    Arme(
        "murs",
        "mur",
        "every Guard refusal, grouped by effect - hitting a wall stops being silent",
        MNEMOSYNE,
        "reads THIS repo's own Guard journal: it is the only place a refusal is ATTRIBUTED",
    ),
    Arme(
        "policy-demander",
        "mur",
        "file a structured request to widen the policy",
        MNEMOSYNE,
        "an isolated agent can only NARROW a request; widening it is an incapacity (D159)",
    ),
    Arme(
        "policy-queue",
        "mur",
        "where each request stands: filed, examined, approved, refused, applied",
        MNEMOSYNE,
        "the state lives in the repo, never in a conversation",
    ),
    Arme(
        "policy-examiner",
        "mur",
        "the adversarial-review mandate for a request, to hand to an ISOLATED agent",
        MNEMOSYNE,
        "producer != verifier (D75): the review never decides, it only narrows or recommends",
    ),
    Arme(
        "policy-approuver",
        "mur",
        "the operator's own gesture - a YES typed LIVE on their terminal, and nothing else",
        MNEMOSYNE,
        "requires /dev/tty: an agent can neither type it nor forge it (hardened after an incident)",
    ),
    Arme(
        "policy-refuser",
        "mur",
        "the same gesture in reverse, with its reason - the request is not erased",
        MNEMOSYNE,
        "same /dev/tty gate; invariant 2: a refusal is archived, it does not erase",
    ),
    Arme(
        "policy-appliquer",
        "mur",
        "write the approved items into policy.toml - refuses anything not exactly approved",
        MNEMOSYNE,
        "fail-closed: the comparison runs item by item against the approval, dry by default",
    ),
    Arme(
        "item-retirer",
        "mur",
        "H1: withdrawing an item from a plan becomes a gesture - request/examine/approve/refuse/apply",
        MNEMOSYNE,
        "same gate as make policy-* (D159): an isolated agent can only narrow, never widen",
    ),
    Arme(
        "gel-inscrire",
        "mur",
        "D176: register an adopting door in the freeze - or it could silently erase its own declaration",
        MNEMOSYNE,
        "refuses a door that declares nothing, a door already frozen, and any path outside the repo",
    ),
    Arme(
        "plan-gate-emit",
        "mur",
        "emit the plan barrier (D166 clause 4) to ANOTHER host, with its two trial runs",
        MNEMOSYNE,
        "a five-line pointer to the single judge (plan_format.index_problems), never a "
        "copy - same reason as garde-emit (D163)",
    ),
    Arme(
        "plancher",
        "mur",
        "refuse to open a shield when the repo's drift crosses its floor, days in a row",
        MNEMOSYNE,
        "measured over the repo's GIT HISTORY (PAR_LIGNE bounded to the project) -- ouvrir_produit/fermer never refuse",
    ),
    Arme(
        "signaler",
        "mur",
        "flag a Mnemosyne failure FROM your project, then go back to your own product",
        MNEMOSYNE,
        "D153: you flag it, you do not fix it - the tick surfaces the queue to the operator on its own",
    ),
    Arme(
        "signalements",
        "mur",
        "the flagged failures nobody has drained yet",
        MNEMOSYNE,
        "outside git by construction (D153): so the failure can be described honestly",
    ),
    Arme(
        "signalement-traite",
        "mur",
        "mark a failure fixed - never deleted (invariant 2)",
        MNEMOSYNE,
        "the report stays on file; only its status changes",
    ),
    # ── You're filing away what you learned ──────────────────────────────────────────────────
    Arme(
        "remember",
        "ranger",
        "file ONE durable lesson, INERT, awaiting the operator's validation",
        MNEMOSYNE,
        "nothing self-promotes (D92): the entry is inert and durably logged",
    ),
    Arme(
        "memory-queue",
        "ranger",
        "the queue of captured lessons awaiting the operator's gesture",
        MNEMOSYNE,
        "rebuilt from the durable log, replayed cold",
    ),
    Arme(
        "memory-validate",
        "ranger",
        "validate (or drop) ONE lesson from the queue - the explicit, logged gesture",
        MNEMOSYNE,
        "D59-5 / D82: validation is a traced human act, never a side effect",
    ),
    Arme(
        "proposals",
        "ranger",
        "the inert proposals the watch and the agents have filed",
        MNEMOSYNE,
        "a list of paths, never a summary: they cite YOUR sources, you read them yourself",
    ),
    Arme(
        "proposal-reviewed",
        "ranger",
        "mark a proposal seen-and-decided - this does NOT promote it",
        MNEMOSYNE,
        "turning a draft into a real skill stays a separate act (D92)",
    ),
    Arme(
        "parenthese-ouvrir",
        "ranger",
        "open a detour that WILL HAVE to return to the plan - refuses if the expected return is empty",
        MNEMOSYNE,
        "measured: one of the flagship project's parentheses closed while leaving a decision never carried out",
    ),
    Arme(
        "parentheses",
        "ranger",
        "the open detours and what each one still owes back to its plan",
        MNEMOSYNE,
        "flags the ones the plan does not point to - the invisible one is the exact waste",
    ),
    Arme(
        "parenthese-fermer",
        "ranger",
        "close a detour - refuses until the return is NAMED and PLACED in a file",
        MNEMOSYNE,
        "naming without placing is closing on a promise - that is what left a debt",
    ),
    Arme(
        "documents",
        "ranger",
        "the documents nothing cites anymore - no threshold: the criterion is CITATION, age just sorts",
        MNEMOSYNE,
        "the population comes from git; nothing is moved, archiving the operator's own file is THEIR gesture (D74)",
    ),
    Arme(
        "rangement",
        "ranger",
        "quarantine the CLEAR clutter - reversible, never a deletion",
        MNEMOSYNE,
        "invariant 2: moves to quarantine, never erases; dry by default",
    ),
    Arme(
        "rangement-emit",
        "ranger",
        "the tidying contract + the judgment pass, as text",
        DEJA_PORTE,
    ),
    Arme(
        "garde-emit",
        "mur",
        "emit the shell guard to ANOTHER host - the judge's address, never a copy",
        MNEMOSYNE,
        "a five-line hook that POINTS at the single home: recopying the judge to every "
        "host would produce as many versions as hosts, and they would drift (D163)",
    ),
    Arme(
        "bilan",
        "ranger",
        "the end-of-session summary, at a STABLE address - the state PULLED, never recopied",
        MNEMOSYNE,
        "the figures come from the repo's own counters and `VERIFIER=1` REFUSES when the block has "
        "drifted: a stale resumption document is WORSE than absent, it reads as up to date",
    ),
    # ── You're maintaining the machine ───────────────────────────────────────────────────────
    Arme(
        "help",
        "entretenir",
        "the 87 targets in a heap, exactly as the Makefile declares them (29,659 b)",
        ATELIER,
    ),
    Arme("setup", "entretenir", "create the venv and sync the toolchain (uv)", ATELIER),
    Arme(
        "lock",
        "entretenir",
        "regenerate uv.lock - pinned, on the supply-chain side",
        ATELIER,
    ),
    Arme("hooks", "entretenir", "install the local pre-push hook (CI is local)", ATELIER),
    Arme("smoke", "entretenir", "the 1-click smoke test on the REAL bricks", ATELIER),
    Arme("calibrate", "entretenir", "measure the two golden bars on the real bricks", ATELIER),
    Arme(
        "tick",
        "entretenir",
        "a coordinated drain of background work + what the system proposes, unprompted",
        MNEMOSYNE,
        "counts the repo's real queues (flags, proposals, parentheses); proposes, "
        "never imposes (D92)",
    ),
    Arme(
        "reprise",
        "entretenir",
        "THE bubble you're working in and its state - the PROJECT, where describe renders the SYSTEM",
        MNEMOSYNE,
        "pulls the state command the bubble DECLARES for itself; the project says what to pull, "
        "never with what (5 sabotages refused by naming their cause)",
    ),
    Arme(
        "depense",
        "entretenir",
        "what Mnemosyne's own code spent today against the two declared ceilings",
        MNEMOSYNE,
        "reads THIS repo's observability log; it does not see your Claude Code session, and SAYS so",
    ),
    Arme(
        "daemon",
        "entretenir",
        "the launchd plist + the gesture to run tick 24/7 on THIS machine",
        ATELIER,
    ),
    Arme(
        "daemon-status",
        "entretenir",
        "proof of life for the daemon - honest when it has never once woken up",
        ATELIER,
    ),
    Arme(
        "ui-json",
        "entretenir",
        "the data contract a UI reads: 6 queues + every plan, as JSON",
        ATELIER,
    ),
    Arme(
        "manifest-realign",
        "entretenir",
        "realign the manifest's paths onto the current shelf",
        ATELIER,
    ),
    Arme(
        "orphans-report",
        "entretenir",
        "the vectors whose source book has left the shelf - read-only",
        ATELIER,
    ),
    Arme(
        "orphans-purge",
        "entretenir",
        "the same, purged - drift only, the manifest is backed up once",
        ATELIER,
    ),
    # ── Batch 2 of the flagship project's harvest (2026-09-08) - 15 gates surfaced from the field ───────────
    Arme(
        "sites-de-sortie",
        "tenir",
        "every `file::module` in system/lib that can EXIT (network, process), frozen as a SET",
        MNEMOSYNE,
        "its v1 froze 27 sites, 14 of them modules ABSENT from the repo and ZERO model clients: an "
        "isolated audit made an SSH-key exfiltration pass it at rc=0. Repaired, it then bit SEVEN "
        "TIMES the same day, on fresh code written by four agents who did not know of each other.",
    ),
    Arme(
        "passes",
        "tenir",
        "the pre-commit passes, frozen and AST-inventoried: their WIRING and their REACHABILITY",
        MNEMOSYNE,
        "flagship project's harvest G3+G5. A floor, not an equality: a new pass is published, never refused. "
        "The denominator is the FREEZE -- an inventory that shrinks would declare itself complete.",
    ),
    Arme(
        "batterie",
        "tenir",
        "the battery that cannot MELT: a failure, a SKIP, and a MUTE test all three refuse",
        MNEMOSYNE,
        "flagship project's harvest G4. Measured here: 42 skip sites, 14 mute tests out of 4,232. Costs 2.56 s, "
        "so too slow for the commit path as is -- written rather than wired in.",
    ),
    Arme(
        "clotures",
        "tenir",
        "a closure with no AUTHOR is refused -- what nobody can verify is not closed",
        MNEMOSYNE,
        "flagship project's harvest P1. Measured here: 22 closures, ZERO authors, 7 without even a date.",
    ),
    Arme(
        "fermeture-glyphe",
        "tenir",
        "a closure DECLARED in a commit demands the glyph FLIP in that SAME commit",
        MNEMOSYNE,
        "flagship project's harvest P9, and the diagnosis Mnemosyne had already made FIVE DAYS EARLIER without "
        "ever building the gate. Measured over 2,196 commits: 5 refusals, ZERO false positives. Its "
        "real home is a commit-msg hook that does NOT EXIST -- level 1 until it does.",
    ),
    Arme(
        "disjoncteur",
        "tenir",
        "on the 3rd negative verdict it ANNOUNCES, on the 4th it SPLITS -- nobody sees the loop from inside",
        MNEMOSYNE,
        "flagship project's harvest G2. Pulled from the real plan: 3 trips, one of them an item with 9 repairs "
        "in a row. Admission: without a verdict registry, an item repaired WITHOUT A COMMIT is invisible to it.",
    ),
    Arme(
        "attribution",
        "demarrer",
        "who holds which arc, at the SOURCE -- a collision REFUSES instead of publishing itself",
        MNEMOSYNE,
        "flagship project's harvest P2. A real collision existed on the day it was measured (arc H claimed by "
        "two chats) and `make ui-json` published it as fact, without a word.",
    ),
    Arme(
        "passation",
        "tenir",
        "declare a peer's state by INDEPENDENT measurement, never on their word",
        MNEMOSYNE,
        "flagship project's harvest G10. Measured here: 21 commits declare a peer's state, and the word "
        "handoff appeared nowhere in the orchestration doctrine.",
    ),
    Arme(
        "precedence",
        "tenir",
        "the repo's own PROCEDURE outranks the mandate's PROMPT -- what lets it catch its own mandate",
        MNEMOSYNE,
        "flagship project's harvest G9. The rule was written NOWHERE while 17 commits name a mandate error. "
        "Emitted by lot-emit: otherwise it would live where the recipient does not read.",
    ),
    Arme(
        "plafond-rotation",
        "ranger",
        "a log past its ceiling MUST rotate, and a cut with no archive is refused",
        MNEMOSYNE,
        "flagship project's harvest P4. The logs grew x14 in four days (6,038-7,199 lines) while the protocol "
        "PRESCRIBED re-reading them: the prescription became impossible IN SILENCE.",
    ),
    Arme(
        "commit-garde",
        "produire",
        "wait for a calm window WITH a ceiling, then PROVE via HEAD that the commit happened",
        MNEMOSYNE,
        "flagship project's harvest P5+G7+G12. The budget is in CPU, not wall time: re-measured HERE, 10 "
        "interleaved pairs give x1.80 wall against x1.28 CPU, 10 times out of 10.",
    ),
    Arme(
        "diffusion",
        "tenir",
        "an emitted rule NAMES the population it was measured on, and the receiver can check it",
        MNEMOSYNE,
        "flagship project's harvest G8. Measured here: 0 of the 6 *-emit targets carried a commit or a date. "
        "Publishes instead of refusing, and writes why: at 0/6 a gate would be born red and unable to go green.",
    ),
    Arme(
        "avancement",
        "savoir",
        "the WEIGHTED ladle beside the plain count, with the number of unweighted items on the line",
        MNEMOSYNE,
        "flagship project's harvest P3. Measured here: 86 items declare a size, only 6 render a readable "
        "weight -- a ladle whose weights are missing degrades into a plain count WITHOUT SAYING SO.",
    ),
    Arme(
        "accord-chiffre",
        "tenir",
        "a figure recopied into prose is checked against EVERY SITE, never against a total",
        MNEMOSYNE,
        "flagship project's harvest P6. The invariant count is recopied 41 times across 30 tracked files, and "
        "derives.py already admitted no barrier covered it. The reference is RECOMPUTED.",
    ),
    Arme(
        "besoins",
        "mur",
        "file, in writing, what cannot be decided alone -- refuses without a written PIVOT; then pivot",
        MNEMOSYNE,
        "flagship project's harvest P8. Measured here: 48 tracked files carried a wait on the operator's "
        "gesture, with no status and no drain -- and the channel had already been reinvented by hand twice.",
    ),
    # ── The public-mirror track - classified here so the bijection holds ────────────────────
    Arme(
        "public-mirror",
        "entretenir",
        "the deterministic plan for the public copy: what's in scope, what isn't",
        MNEMOSYNE,
        "the scope is DERIVED from this repo's own state (tracked files, gitignore, sync freeze), not a hand-written list: no frontier host can compute it without the repo.",
    ),
    Arme(
        "public-mirror-verify",
        "entretenir",
        "the fail-closed gates on the public export, before any commit into the copy",
        MNEMOSYNE,
        "fail-closed gates that read this repo's own git INDEX before the export -- a refusal here is a state of the repo, never a matter of style.",
    ),
    Arme(
        "public-mirror-mark-synced",
        "entretenir",
        "record the sync baseline after a successful export",
        MNEMOSYNE,
        "it WRITES the sync baseline into this repo's own state: it is a single home, and two copies of that baseline would silently diverge.",
    ),
    Arme(
        "public-mirror-emit",
        "entretenir",
        "the complete, self-sufficient contract for the mirror track, for any model",
        DEJA_PORTE,
    ),
    Arme(
        "portes",
        "tenir",
        "the repo's 5 GREEN gates in one run (2.7 s) -- called by `make check`",
        MNEMOSYNE,
        "it exists because a gate nothing pulls is a barrier nothing calls: the "
        "batch-2 gates existed as 15 targets, none of them pulled automatically. The 4 gates from "
        "that batch that DO refuse today (fermeture-glyphe, disjoncteur, attribution, plafond-rotation) "
        "are NOT in it, and that is measured: a gate born red would block every commit.",
    ),
    Arme(
        "besoin",
        "mur",
        "file what you cannot decide alone -- refuses without a written PIVOT",
        MNEMOSYNE,
        "the channel lives in git and travels across chats, unlike docs/signalements/ which is "
        "gitignored by design. Measured: 48 tracked files carried a wait on the "
        "operator's gesture, with no status and no drain, and the channel had already been reinvented by hand twice.",
    ),
    Arme(
        "besoin-trancher",
        "mur",
        "settle a need -- demands a written DECISION, and never deletes the file",
        MNEMOSYNE,
        "invariant 2 applied to an arbitration channel: the decision stays readable for whoever "
        "reads it later, and a settled need keeps its question next to its answer",
    ),
)
