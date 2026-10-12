"""A HAND-MAINTAINED DERIVATIVE IS A LIAR ON A DELAY (phase 2 · C4).

The source document named below is authoritative. The documents that DERIVE from it and speak in
its name used to announce its RANGE, copied by hand — two derivatives, two different numbers, one
object, and none of them turned red when the source moved past both. The fix is not to correct the
numbers — that would just re-sign the same debt: **the bound is removed entirely**. The range is
read from the source (D163 — the address, never the copy).

This module is the PURE judge of this class. It reads no file: the population is INJECTED at the
boundary. It judges ONLY the derivatives declared below — a detector let loose on the whole
repository would count CITATIONS of the defect (the plan, the measurements, this very docstring)
as instances, a mistake already measured five times elsewhere.

WHAT IT DOES NOT JUDGE, AND THAT MUST BE SAID: the count of **27 invariants**, copied into about
twenty files. It is TRUE today (`tests/test_invariants.py` derives 27 of them), and re-checking it
is item **D3** of phase 3. No barrier here covers it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

#: THE SOURCE. The public technical reference is authoritative: it derives from nothing, so it is
#: never judged here as its own derivative — a range quoted INSIDE it dates one block of its own
#: history and makes no claim about the overall range.
SOURCE = "ARCHITECTURE.md"

#: The documents that DERIVE from the source and speak in its name.
#: A named SET, never a count: a renamed file must turn RED (`absents`), never silently drop out
#: of judgment.
DERIVES: tuple[str, ...] = (
    "README.md",
    "docs/FORMAT_PLAN.md",
)

#: `D1→D124`, `D1->D124`, `D1-D124`, `D1 à D124` — every form found in this repository.
#: THE HYPHEN REQUIRES A `D` ON ITS RIGHT, and that is not fussiness: `D48-1`, `D54-2`,
#: `D119-a` are SUB-decisions, not ranges. A looser pattern used to accuse the crystallized-doctrine document five
#: times over perfectly true lines. The unambiguous separators (`→`, `->`, the French `à`) do not
#: have this problem and tolerate an implicit `D`.
_PLAGE = re.compile(r"\bD\d+\s*(?:→|->|à)\s*D?\d+\b|\bD\d+\s*[-—–]\s*D\d+\b")
#: `143 décisions`, `123 décisions` — the same debt, written as a count instead of a range.
_COMPTE = re.compile(r"\b\d{2,}\s+d[ée]cisions\b", re.IGNORECASE)
#: A PROCLAIMED EXECUTOR DEFAULT (D174). `local-first` lived 23 days too long in these documents
#: after D149 overturned it; D149 replaced it with `frontier-first`, which would have perished the
#: same way. The decision is to proclaim NONE of them — so the shape `<word>-first` no longer
#: belongs here, **not even negated**: to tell the story of the abandoned identity, say
#: "all-local", or tell it in the plan and the measurements, which are not judged here.
_DEFAUT = re.compile(r"\b(?:local|frontier|frontière|cloud|on-?prem)[-\s]first\b", re.IGNORECASE)

PLAGE = "plage"
COMPTE = "compte"
DEFAUT = "defaut_d_executant"

#: THE FROZEN WEIGHT OF `CLAUDE.md` — the only doctrine paid on EVERY session (D4).
#: THIS IS NOT A CHOSEN CEILING, IT IS A RATCHET, and the difference is the one A4/D165
#: imposes: a ceiling on a GENERATED output steers, but `CLAUDE.md` is WRITTEN BY HAND, and a
#: ratchet fixes no desirable value — it freezes WHAT IS and refuses in BOTH DIRECTIONS.
#: **What breaks without it, measured**: between 2026-08-02 and 2026-08-09, this file went from
#: 12,007 to 14,581 bytes (+21%) without anyone noticing. Without a ratchet, D4 is a one-off
#: cleanup to be redone — exactly what A3 avoids for orphaned documents.
#: **2026-08-16, +521 B (12,007 -> 12,528), a deliberate move**: the section "project engineering
#: is OFFERED, never imposed (D176)" buys that an agent starting a project — including a
#: SUB-AGENT, which never receives the SessionStart injection — can no longer miss the standard's
#: three addresses (make plan-nouveau / FORMAT_PLAN.md / ORCHESTRATION.md). Measured before this
#: move: the standard was cited 8 times across the whole auto-loaded corpus, against 54 for the
#: Guard — and all 8 lived in the one channel that drops to zero in degraded mode.
#: **2026-08-17, +312 B (12,528 -> 12,840), a deliberate move**: a 4th address, `make
#: plan-gate-emit`, for the gate that HOLDS the standard — without it, adoption stays
#: declarative. Measured before this move, on a real adopter project (D176): 14 gates declare
#: `**Format**: produced`, 0 mention of `plan_format`/`index_problems` in its real pre-commit hook
#: (400 lines). The three earlier addresses carry the SHAPE, the EXECUTION, the BIRTH of a plan;
#: none carried WHAT HOLDS IT — D177 violated by the standard itself, until this point.
#: RAISED on 2026-08-18: 12,840 -> 12,931 (+91 B). WHAT THESE BYTES BUY ON EVERY SESSION: the
#: line "In a project session" used to prescribe `make signaler TITRE=...` — the gesture that its
#: reader was **the only one unable to type it** (`make` has no root outside this repository). The
#: operator found this defect TWICE, by hand; an isolated auditor measured that it still lived
#: here, verbatim, while a brand-new barrier claimed to have closed it — `CLAUDE.md` had served as
#: the SOURCE for establishing that barrier's population, and was not part of it.
#: The 91 bytes carry the `-C` flag and the sentence that generalizes it to EVERY target cited
#: here. *Without them, every project session re-reads the instruction to type a command that does
#: not exist on its side.*
POIDS_GELE_CLAUDE_MD = 13_065


def poids_doctrine(octets: int, *, gel: int = POIDS_GELE_CLAUDE_MD) -> str:
    """The ratchet's verdict: an EMPTY string if there is nothing to say, otherwise the refusal
    that names the way out."""
    if octets > gel:
        return (
            f"`CLAUDE.md` weighs {octets} B for a freeze at {gel} — +{octets - gel} B. "
            "It is the ONLY doctrine paid on EVERY session: whatever grows here is paid "
            "everywhere. REMOVE it, or MOVE it to `docs/` and leave only the ADDRESS (D163). "
            "If the addition truly must live there, raise `POIDS_GELE_CLAUDE_MD` IN THE SAME "
            "COMMIT and say in the message what these bytes buy on every session."
        )
    if octets < gel:
        return (
            f"`CLAUDE.md` weighs {octets} B for a freeze at {gel} — {gel - octets} B of slack. "
            "A loosened ratchet no longer ratchets: lower `POIDS_GELE_CLAUDE_MD` to "
            f"{octets} to bank the gain, or it will quietly be lost again with nothing turning red."
        )
    return ""


#: THE FIRST ADOPTER'S PATTERN, CARRIED UP TO THE COMMON HOME (D163 — the address, never the copy,
#: applied here to a MECHANISM rather than a document). That project built its own `PORTES_QUI_DECLARENT` freeze
#: to close a MEASURED defect (2026-08-17, adversarial audit): a gate that declares a format can
#: erase its `**Format**:` line — TWENTY characters — and the guard that judges this declaration
#: turns GREEN again in silence, because a gate that was never adopted and a gate that JUST LOST
#: its adoption return exactly the same empty state. **Without this freeze, every adopter has to
#: reinvent the same protection — the copy that D163 forbids.**
#:
#: **2026-08-17, FIXED AFTER AN ADVERSARIAL AUDIT: AN EMPTY TUPLE MADE THIS FREEZE DOUBLY
#: INERT** (empty set, zero caller outside tests) — the same class of defect this module exists to
#: close, remanufactured one level up. **Populating the population is NOT an adopter's gesture: it
#: is Mnemosyne MEASURING what the first adopter has ALREADY declared** (adoption dated, D176, 2026-07-29),
#: exactly as `test_CLAUDE_md_du_depot_REEL_tient_son_gel` measures THIS repository without asking
#: its permission. That project's 14 real gates, `**Format**: produced` confirmed line by line
#: (`/usr/bin/grep -n`, not a loose pattern) on 2026-08-17:
PORTES_QUI_DECLARENT: tuple[str, ...] = (
    "projects/saas/example-project/PLAN.md",
    "projects/saas/example-project/plan/01-arc/PLAN.md",
    "projects/saas/example-project/plan/02-arc/PLAN.md",
    "projects/saas/example-project/plan/03-arc/PLAN.md",
    "projects/saas/example-project/plan/04-arc/PLAN.md",
    "projects/saas/example-project/plan/05-arc/PLAN.md",
    "projects/saas/example-project/plan/06-arc/PLAN.md",
    "projects/saas/example-project/plan/07-arc/PLAN.md",
    "projects/saas/example-project/plan/08-arc/PLAN.md",
    "projects/saas/example-project/plan/09-arc/PLAN.md",
    "projects/saas/example-project/plan/10-arc/PLAN.md",
    "projects/saas/example-project/plan/11-arc/PLAN.md",
    "projects/saas/example-project/plan/12-arc/PLAN.md",
    "projects/saas/example-project/plan/13-arc/PLAN.md",
    # 2026-08-18 — THE SECOND ADOPTER, AND IT ADOPTED ITSELF ALL ALONE. It was born while
    # this repository was closing out the "project engineering" ticket; nobody told it to declare
    # a format. Its gate came out of `make plan-nouveau` (the D176 block of `plan_scaffold` is
    # intact in it) and it declares TWO tokens, not six — the offer was received AS an offer.
    # **It was the test that found it, not me**: `test_ecart_adoption_..._AUJOURD_HUI` turned red,
    # naming the file and the gesture (*"this adoption is held by NOTHING as long as no gesture
    # registers it in PORTES_QUI_DECLARENT"*). *A hand-written freeze needs a canary that rings
    # when the world grows — otherwise it protects a past.*
    # Measured line by line like the 14 above (`/usr/bin/grep -rn "^> \*\*Format\*\*"`):
    # exactly ONE declaring gate in the whole of that second adopter's own project folder.
    "projects/personal/second-example/PLAN.md",
)
#: **WHAT STAYS OUTSIDE THIS GESTURE, NAMED SO IT IS NEVER MANUFACTURED**: the production CALLER
#: (`.githooks/pre-commit` never sees `projects/`, gitignored; the only surface that actually runs
#: on a project's plan is `plans_run.py:82`, chat 1's batch, which returns `rc=0` even on an
#: unreadable plan — a separate piece of work, coordinated by this repository, not duplicated
#: here). **The REAL caller today is the test that follows**: it reads the 14 gates ON DISK on
#: every `pytest` run, not a frozen text — a real caller, bounded to the measurement, never a
#: pre-commit hook faked to pretend it is armed.


@dataclass(frozen=True, slots=True)
class Effacee:
    """A FROZEN gate that no longer declares anything — the adoption just erased itself in silence."""

    porte: str


@dataclass(frozen=True, slots=True)
class VerdictAdoption:
    """The verdict of the freeze over the SET of declaring gates — never over the count.

    A frozen gate ABSENT from `courant` counts as erased — the same rule as `absents` for
    `DERIVES` below: a rename must not silently remove a gate from judgment.
    """

    effacees: tuple[Effacee, ...]
    tenues: tuple[str, ...]

    @property
    def refuse(self) -> bool:
        return bool(self.effacees)


def verdict_adoption(
    *, courant: Mapping[str, str], geles: tuple[str, ...] = PORTES_QUI_DECLARENT
) -> VerdictAdoption:
    """Judges the freeze: every gate in `geles` must still declare in `courant` (injected at the
    boundary — this module reads no file, see the module docstring)."""
    effacees: list[Effacee] = []
    tenues: list[str] = []
    for porte in geles:
        if courant.get(porte, "").strip():
            tenues.append(porte)
        else:
            effacees.append(Effacee(porte=porte))
    return VerdictAdoption(effacees=tuple(effacees), tenues=tuple(tenues))


def message_adoption(v: VerdictAdoption) -> str:
    """The refusal NAMES the erased gate(s) — never a silent green."""
    if not v.refuse:
        return f"{len(v.tenues)} frozen gate(s): all of them still declare."
    noms = ", ".join(e.porte for e in v.effacees)
    return (
        f"ADOPTION ERASED WITH NO FREEZE AND NO ALERT: {noms} used to declare a format and no "
        "longer declares anything — twenty characters are enough (measured). A gate frozen in "
        "`PORTES_QUI_DECLARENT` must keep declaring, or the refusal must be named, never "
        "silently turn green again. Pattern carried up from the first adopter (`PORTES_QUI_DECLARENT`, D163)."
    )


#: 2026-08-17 — THE FREEZE HOLDS FOR THE FIRST ADOPTER ONLY: `PORTES_QUI_DECLARENT` is hand-written, and
#: nothing registers a NEW adopter's gate. A fresh project can declare `**Format**: produced` and
#: then erase it without any refusal ever seeing it — the same defect just closed for the first adopter,
#: reopened for anyone else. **Level 1 first (measured before choosing): as of 2026-08-17, the first adopter
#: is the ONLY project declaring anywhere under `projects/`** (`/usr/bin/grep -rl
#: '\*\*Format\*\* :'` over every gate of every project, zero second candidate) — a REGISTRATION
#: gesture (option (b) of the ticket: `make adoption-geler`) would therefore have NOTHING real to
#: exercise today, and a control that cannot bite on its first shot is disarmed on its first shot.
#: `ecart_adoption` (option (c)) closes the half that costs zero and makes the oversight VISIBLE
#: as soon as a second project declares — registration stays named as the NEXT gesture, not built
#: ahead of the population that would justify it.
def ecart_adoption(
    *, declare: Mapping[str, str], geles: tuple[str, ...] = PORTES_QUI_DECLARENT
) -> tuple[str, ...]:
    """The gates that DECLARE on disk but are NOT in the freeze — the oversight that must stay
    VISIBLE as long as no gesture registers a new gate. `declare` (gate → declared text) is
    injected at the boundary; sorted, so that two runs that find the same gap NAME it in the same
    order."""
    geles_set = frozenset(geles)
    return tuple(
        sorted(porte for porte, texte in declare.items() if texte.strip() and porte not in geles_set)
    )


#: The insertion anchor: the end of the :data:`PORTES_QUI_DECLARENT` tuple. Anchored on the
#: CLOSING PARENTHESIS in column 0 that follows the assignment, never on the last registered
#: project — a block that moves or shrinks carries a named anchor along with it.
_ANCRE_GEL: Final = re.compile(
    r"(?P<tete>PORTES_QUI_DECLARENT: tuple\[str, \.\.\.\] = \(\n)(?P<corps>.*?)(?P<fin>^\)$)",
    re.DOTALL | re.MULTILINE,
)


class GelError(RuntimeError):
    """A registration into the freeze that was refused — named, never silent."""


def inscrire_porte(source: str, porte: str) -> str:
    """Adds `porte` to the :data:`PORTES_QUI_DECLARENT` tuple — PURE: takes text, returns text.

    **WHY THIS GESTURE EXISTS (2026-08-18), AND IT WAS ANNOUNCED**: the note under
    :func:`ecart_adoption` wrote *"registration stays named as the NEXT gesture, not built ahead
    of the population that would justify it."* **The population has arrived**: the second adopter adopted on
    its own, and two other projects are following. Until now, registering a gate meant EDITING
    THIS FILE BY HAND, in a Mnemosyne session — a manual step per adopting project, on production
    code.

    **REFUSES rather than guessing**, in three cases, and each has its own reason:
    *(a)* a gate that does NOT DECLARE anything on disk — the freeze certifies *"this gate used to
    declare"*, registering it without measuring would manufacture the very attestation it is
    supposed to make falsifiable;
    *(b)* a gate ALREADY frozen — a duplicate would make `ecart_adoption` inconsistent with
    itself;
    *(c)* a source file whose anchor is not found exactly once — a named refusal beats a line
    inserted in the wrong place of a production module.

    The VERIFICATION that the gate really declares is NOT done here: this function touches no
    disk. That belongs to the boundary (`runtime/gel_inscrire_run.py`), which reads the disk and
    passes it in as an argument — the same split as `applique_retrait` / `appliquer_verifie`.
    """
    if porte in PORTES_QUI_DECLARENT:
        raise GelError(f"gate already frozen: {porte!r} — nothing to do, the freeze already holds it")
    if '"' in porte or "\\" in porte or "\n" in porte:
        raise GelError(f"path not representable in the freeze: {porte!r}")
    trouvees = _ANCRE_GEL.findall(source)
    if len(trouvees) != 1:
        raise GelError(
            f"insertion anchor found {len(trouvees)} times in the source, expected exactly 1 "
            "— the PORTES_QUI_DECLARENT tuple changed shape, fix `_ANCRE_GEL` before writing"
        )

    def _inserer(m: re.Match[str]) -> str:
        return f'{m.group("tete")}{m.group("corps")}    "{porte}",\n{m.group("fin")}'

    nouveau = _ANCRE_GEL.sub(_inserer, source, count=1)
    # Re-reads its own result BEFORE returning it: the line must be there, and the entry count
    # must have grown by EXACTLY one. A `sub` that returns plausible-looking text but inserted
    # nothing is exactly the kind of silent success this repository has already paid for.
    if f'    "{porte}",\n' not in nouveau:
        raise GelError("the insertion did not take — the returned source does not carry the expected line")
    avant = source.count('    "')
    if nouveau.count('    "') != avant + 1:
        raise GelError("the insertion changed more than one line — refusing, nothing is written")
    return nouveau


def message_ecart(ecart: tuple[str, ...]) -> str:
    """Publish the gap — level 1: nothing refuses, but the oversight becomes impossible to ignore."""
    if not ecart:
        return "0 gates declare outside the freeze: nothing to register."
    noms = ", ".join(ecart)
    # THE MESSAGE NAMES THE COMMAND, NOT JUST THE FILE (2026-08-18). It used to say "as long as
    # no gesture registers it in PORTES_QUI_DECLARENT (…/derives.py)" — which describes a
    # HAND EDIT OF CODE, i.e. a Mnemosyne session, an editor, and a human who does not misplace a
    # comma. The second adopter read it and rightly answered "from a project session, I report, I
    # do not repair." *A message that names a file to edit names a gesture its reader cannot pose;
    # one that names a command names one they can.*
    # The `make -C` form makes it reachable FROM a project folder (J4).
    # ONE COMMAND PER GATE, NEVER `ecart[:1]` (fixed on 2026-08-18, found by an isolated
    # auditor): the message ANNOUNCED N gates and only printed ONE gesture. *A message that counts
    # N and only shows one makes the reader think the first one covers them all* — and whoever
    # pastes it walks away believing they are done.
    gestes = "\n".join(f"    make gel-inscrire PORTE={p} APPLY=1" for p in ecart)
    return (
        f"{len(ecart)} GATE(S) DECLARE A FORMAT AND ARE NOT FROZEN: {noms}. This "
        "adoption is held by NOTHING — no refusal, no acknowledgment — until a gesture registers "
        f"it into the freeze.\n  THE GESTURE, one command PER gate:\n{gestes}\n"
        "  (from a project folder: `make -C ~/mnemosyne gel-inscrire PORTE=… APPLY=1`)"
    )


@dataclass(frozen=True, slots=True)
class Recopie:
    """One corpus bound, hand-copied into a document that derives from it."""

    document: str
    ligne: int
    texte: str
    forme: str


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the judge saw — and, just as important, what it could NOT see."""

    recopies: tuple[Recopie, ...]
    juges: tuple[str, ...]
    absents: tuple[str, ...]

    @property
    def refuse(self) -> bool:
        """An absent derivative REFUSES as much as a lying one, and so does an empty population.

        A rename would remove a document from judgment without any assertion moving: the green
        would become a silence. Here it becomes a red instead.
        """
        return bool(self.recopies) or bool(self.absents) or not self.juges


def verdict(textes: Mapping[str, str]) -> Verdict:
    """Judges the DECLARED derivatives, from their text injected at the boundary."""
    recopies: list[Recopie] = []
    juges: list[str] = []
    absents: list[str] = []

    for nom in DERIVES:
        contenu = textes.get(nom)
        if contenu is None:
            absents.append(nom)
            continue
        juges.append(nom)
        for numero, ligne in enumerate(contenu.splitlines(), start=1):
            for motif, forme in ((_PLAGE, PLAGE), (_COMPTE, COMPTE), (_DEFAUT, DEFAUT)):
                for trouve in motif.finditer(ligne):
                    recopies.append(
                        Recopie(document=nom, ligne=numero, texte=trouve.group(0), forme=forme)
                    )

    return Verdict(recopies=tuple(recopies), juges=tuple(juges), absents=tuple(sorted(absents)))


def message(v: Verdict) -> str:
    """The refusal NAMES the way out — without that, the next reader loosens the judge."""
    if not v.refuse:
        return (
            f"{len(v.juges)} derivative(s) judged: none copies the corpus range, "
            "none proclaims an executor default."
        )

    lignes: list[str] = []
    if not v.juges:
        lignes.append(
            "EMPTY POPULATION: no derivative was read. A judge with no population returns a "
            "green that measures nothing — refuse instead of reassuring."
        )
    if v.absents:
        lignes.append(
            "DERIVATIVES NOT FOUND: "
            + ", ".join(v.absents)
            + " — renamed or moved? Update `DERIVES` in "
            "`system/lib/mnemosyne/production/derives.py`; do not let a document "
            "leave judgment in silence."
        )
    for r in v.recopies:
        if r.forme == DEFAUT:
            lignes.append(
                f"{r.document}:{r.ligne} proclaims an EXECUTOR DEFAULT — « {r.texte} ». "
                "Mnemosyne is AGNOSTIC (D174): frontier and local are two entry points, "
                "neither is the default. REMOVE IT without replacing it — `frontier-first` "
                "would perish just as `local-first` perished. To tell the story of the "
                "abandoned identity, write « all-local ». \U000026A0\U0000FE0F This touches NO data barrier: "
                "`sensible` stays local (inv. 1), and so do intimate families (D149)."
            )
            continue
        lignes.append(
            f"{r.document}:{r.ligne} copies the corpus range — « {r.texte} ». "
            f"REMOVE the bound: `{SOURCE}` carries its own range, a derivative POINTS to it "
            "(D163). And if you meant to CITE the defect rather than commit it, cite it "
            "elsewhere — these documents carry none of it, not even as an example."
        )
    return "\n".join(lignes)
