"""THE OPERATOR'S MEMORY — its overflow, and the ratchet that measures it (D173).

THE MEASUREMENT THAT DECIDED THIS MODULE, AND IT HAD NEVER BEEN TAKEN. The memory folder
(`~/.claude/projects/<slug>/memory/`) was **under no repository at all**, and `~/.claude/backups/`
was **empty**: 1.67 MB of lessons where no bad write was recoverable. A `git init` was placed
there on 2026-08-06 (228 files, byte-for-byte restore verified). *On non-recoverable storage,
anything that WRITES is a bet with no safety net; only what APPENDS is acceptable.*

THE PROBLEM THIS MODULE SOLVES. `MEMORY.md` is loaded by the **Claude Code built-in**, which
reads **only one file** and stops reading it past ~24,400 bytes. The index weighed in at
**24,344**: 56 bytes of margin, and **not one more bold line left to wring out** (~107 bytes per
entry). The only way out that destroys nothing is a **SECOND channel** — but a `MEMORY-2.md`
sitting next to it would be invisible: the harness doesn't load it. Measured proof: the 227
record files (1.67 MB) sit on disk and are **absent from context**. It therefore needs a CARRIER
THAT PUSHES, and that is the hook.

WHAT THIS CHANNEL IS NOT WORTH, AND IT MUST BE READ BEFORE RELYING ON IT. The `SessionStart`
hook is **FAIL-OPEN by construction** (its own header: *"always exits 0"*): if it breaks, it
**stays silent**. The overflow is therefore **structurally less reliable** than the built-in's own
channel. That is why `MEMORY.md` is FROZEN rather than emptied: what is already in it stays on the
safe channel — only what is NEW takes the backup channel. *A backup channel is not compared to the
one it doubles for.*

AND THE REFUSAL THIS MODULE RETURNS IS NOT A BARRIER AT STARTUP. Fired by the hook, its `rc`
is **discarded** (fail-open). What it does there is PRINT — and *a check that prints is not a
gate*. The real gate is `make memoire`, run by hand or by a script: there, the `rc` bites.
Written here so nobody reads the ratchet as a guarantee it does not have.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

#: THE BUILT-IN'S WALL, AND IT IS NOT OURS. Beyond it, `MEMORY.md` stops being loaded.
#: WHAT EXACTLY HAPPENS PAST IT HAS NEVER BEEN OBSERVED — the test would mean crossing the
#: limit, i.e. causing the very damage being avoided. This is an INFERENCE, stated as such.
MUR_DU_BUILTIN = 24_400

#: THE FROZEN SIZE OF THE MAIN INDEX, AND IT IS WHAT MAKES THE WORD "FROZEN" REAL.
#: Without this ratchet, "MEMORY.md no longer grows" would be an intention: the next hand that
#: adds a line to it would cross the wall without anything turning red. A CORRECTION remains
#: possible — it passes if the final size does not RISE. Lowering this number to let an
#: addition through is a loosening: it is the NEW content that goes into the overflow, never the
#: wall being pushed back.
TAILLE_GELEE_DE_L_INDEX = 24_344

#: "A LESSON WITH NO BARRIER IS A WISH" (A2) — the rule governing a downstream project's lessons
#: since July, imported here. Each lesson names the code that makes its fault impossible, or ADMITS
#: outright that no barrier exists. The admission is a valid answer, and that matters: that project
#: paid for the opposite — *a check that demands a quantity PER RECORD manufactures the content it demands*
#: (5 clauses invented in the commit that needed them, 2 of them false). Here, writing "none" is
#: free and always available: nothing pushes anyone to invent a barrier.
#:
#: WHAT THIS PATTERN DOES NOT JUDGE, AND IT HAS TO BE SAID: it checks that the QUESTION got a
#: WRITTEN answer, never that the answer is TRUE. A cited barrier that doesn't exist would pass —
#: *a name is not a test*. The truth of the content is judged on reading, not here.
#: TWO FORMS, BECAUSE THE DOCTRINE PRESCRIBES TWO -- and this judge used to read only ONE.
#: The lesson that establishes the required form has, since 2026-07-29, instituted the "NIVEAU n"
#: shape (French for "LEVEL n": 1 = admission, 2 = barrier in code, 3 = inert reminder). This
#: pattern didn't know about it: **the very lesson that PRESCRIBES the form was itself counted as
#: a wish by the gate that judges it.** A class already paid for here -- *a census blind to the
#: form its own doctrine prescribes*.
#: Measured 2026-09-08, through the judge's own accessor over 708 records: **10 more
#: recognized, 0 lost**, and the not-barriered count **515 -> 505** — the gate stays RED (freeze
#: at 267), so the widening buys **no** green at all: not an opportunistic loosening, and that is
#: the only thing that makes it legitimate.
#: CASE IS THE DISCRIMINANT, AND IT IS MEASURED: capitalized "NIVEAU" appears **12 times**, all
#: 12 genuine declarations (checked one by one, in context); lowercase "niveau" appears **107
#: times** across 164 records, in ordinary French prose. Hence `(?i:...)` on `Barriere` ALONE —
#: putting `IGNORECASE` as a global flag would let 27 records through on the ordinary word.
#: Measured: the first, broader candidate pushed the count UP to 542, because it had dropped the
#: original's `IGNORECASE` — *"before" and "after" must be THE SAME measurement*, or two different
#: instruments are being compared.
#: WHAT IT ADMITS TOO MUCH OF, AND IT HAS TO BE SAID: the lesson that prescribes the form names
#: "NIVEAU n" inside META SECTION TITLES, without declaring its own. It therefore passes without
#: having answered for itself -- 1 record out of 708. That is the contract already written above
#: (*the QUESTION got a WRITTEN answer, never that the answer is TRUE*), not a regression: a
#: pattern is not tightened against a single case at the cost of a second parser.
#: A THIRD FORM, MEASURED THE SAME DAY: the colon OUTSIDE the bold (`**Barriere** :`). 6
#: records use it; 5 are genuine declarations, **1 is an ordinary sentence** (roughly: "...and
#: especially a **barrier**: this session measured..."). The discriminant is therefore not the
#: shape but the POSITION: a declaration OPENS its line (after a bullet or an emoji), a sentence
#: continues one. `[^\w\n]{0,12}` lets `- `, `> `, emoji, and spaces through, never a word.
#: Measured: 4 kept, 1 sentence excluded, not-barriered count **505 -> 501**, gate still RED.
#: AND WHAT IT STILL EXCLUDES, KNOWINGLY: a 5th genuine declaration sits in the MIDDLE of a
#: line (roughly: "...that case. **Barrier**: ..."). Widening the pattern to catch it would
#: re-admit the ordinary sentence too. So that one record was REFORMATTED instead of loosening
#: the judge — *between a silent false green and a loud false red, the one that shouts is
#: chosen*, and here the red is fixed by moving a line break.
_DECLARATION_DE_BARRIERE = re.compile(
    r"(?i:\*\*Barri[eè]res?\s*:)"                          # "**Barriere: ..." (colon INSIDE the bold)
    r"|NIVEAU\s*[0-9]"                                       # the form the doctrine prescribes
    r"|(?im:^[^\w\n]{0,12}\*\*Barri[eè]res?\*\*\s*:)"     # "**Barriere** : ..." at the START of a line
)

#: THE FROZEN DEBT, AND IT IS A RATCHET THAT CAN ONLY GO DOWN. Measured 2026-08-09:
#: **288 records out of 293** did not say what makes their fault impossible — that downstream
#: project's rule therefore did NOT exist here yet, and the 5 exceptions had been written in the previous nine
#: days.
#: What breaks without this ratchet (D165's test): the rule would remain a wish ABOUT wishes, and
#: nothing would turn red when the next purely moral lesson gets added.
#: 2026-08-09, same day: **288 -> 287 -> 286 -> 285**. The debt is being paid down, and the
#: ratchet REQUIRES tightening — it refuses slack as much as overshoot.
#: The 288 are not RETROACTIVELY REWRITTEN: mass-rewriting the operator's own records is his
#: gesture, not this module's (D74, inv. 2). The debt gets paid down as records are touched, one
#: at a time, over time.
DETTE_SANS_BARRIERE = 267

_LIEN = re.compile(r"\]\(([^)]+\.md)\)")

#: A COMMENTED-OUT LINK IS NOT A POINTER, AND THE DIRECTION OF THE ERROR DECIDES THIS LINE.
#: Measured, on this ratchet's very first run: the example `- [Title](record-name.md)` sitting
#: inside an HTML comment in MEMORY-2.md produced targets=228, dead=1. The two directions are NOT
#: equivalent. Counting a commented-out link means a record **nothing visible** points to would
#: go GREEN (a silent loss, exactly the class that has already survived several sessions here).
#: NOT counting it means, at worst, an orphan wrongly flagged — which is visible and self-corrects.
#: *Between a silent false green and a loud false red, the one that shouts is chosen.*
_COMMENTAIRE = re.compile(r"<!--.*?-->", re.DOTALL)


def dossier_de_memoire(projet: Path | None = None) -> Path:
    """Where this repository's memory lives. Derived, never guessed — and its absence is SAID."""
    racine = Path(projet or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()
    return Path.home() / ".claude" / "projects" / str(racine).replace("/", "-") / "memory"


def index_principal(dossier: Path) -> Path:
    return dossier / "MEMORY.md"


def index_de_debordement(dossier: Path) -> Path:
    return dossier / "MEMORY-2.md"


def bijection(dossier: Path) -> tuple[set[str], set[str]]:
    """The targets POINTED TO by BOTH indexes, and the records PRESENT on disk.

    SETS are returned, never their counts. A lost target and an added target cancel out
    **perfectly** in a count, and that is exactly how a compaction pass destroyed a link here: the
    record still weighed 20 KB on disk, nothing pointed to it any more, no check turned red, and
    the loss survived **several sessions**.
    """
    index = {index_principal(dossier), index_de_debordement(dossier)}
    pointees: set[str] = set()
    for i in index:
        if i.exists():
            visible = _COMMENTAIRE.sub("", i.read_text(encoding="utf-8"))
            pointees |= set(_LIEN.findall(visible))
    presentes = {p.name for p in dossier.glob("*.md") if p not in index}
    return pointees, presentes


def _horodate(chemin: Path) -> float:
    """The mtime, 0.0 if unreadable — a record we know nothing about sorts to the BACK, never the front."""
    try:
        return chemin.stat().st_mtime
    except OSError:
        return 0.0


def fiches_sans_barriere(dossier: Path) -> list[str]:
    """The records that do NOT SAY what makes their fault impossible — MOST RECENT FIRST.

    An unreadable record counts as WITHOUT a declaration, never as compliant: *the default branch
    is where silence hides*, and a read error that let a record pass as green would lower the debt
    without any barrier ever having been written.

    THE ORDERING IS A DEFECT FOUND BY REAL USE, NOT A CONVENIENCE. The gate bit THREE times the
    day it was installed; the first two times, its message named the three records that sort LAST
    alphabetically — three innocent ones, weeks old — instead of the actual culprit just written.
    *A refusal that names the wrong party sends someone off to fix what already works*, and it
    burns the gate's credibility every time it fires.
    """
    manquantes: list[tuple[float, str]] = []
    for chemin in sorted(dossier.glob("*.md")):
        if chemin.name in {index_principal(dossier).name, index_de_debordement(dossier).name}:
            continue
        try:
            texte = chemin.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            manquantes.append((_horodate(chemin), chemin.name))
            continue
        if not _DECLARATION_DE_BARRIERE.search(texte):
            manquantes.append((_horodate(chemin), chemin.name))
    return [nom for _, nom in sorted(manquantes, reverse=True)]


def verdict(
    dossier: Path, *, dette_gelee: int | None = None
) -> tuple[list[str], dict[str, object]]:
    """The JUDGMENT, rendered PURE so a witness can exercise it without a real folder.

    Deliberately extracted from the printing: as long as a verdict lives inside the function
    that prints it, no witness can reach it without replaying the whole render — *a syntactic
    freeze says nothing about reachability*, and this repository has already paid for a floor
    whose COMPARISON nobody was judging (`if joues < PLANCHER` sabotaged into `if joues < 0`: the
    sabotage SURVIVED).
    """
    raisons: list[str] = []
    if not dossier.is_dir():
        return (
            [
                f"memory folder NOT FOUND: {dossier}. This is not 'empty', it's a "
                f"path that does not resolve — conclude nothing about the memory from this refusal."
            ],
            {"dossier": str(dossier)},
        )

    principal, debordement = index_principal(dossier), index_de_debordement(dossier)
    pointees, presentes = bijection(dossier)
    morts, orphelines = sorted(pointees - presentes), sorted(presentes - pointees)
    #: ABSENT IS NOT SMALL. `... else 0` compared 0 to the freeze, and 0 passes UNDER every
    #: threshold: the ratchet went green exactly where it measured NOTHING. Measured 2026-09-09
    #: on this very distribution, which does not ship the memory folder: `0 > 24_344` is false,
    #: no reason raised, a DEAD ratchet shipped in silence. `None` forces the third branch.
    octets = principal.stat().st_size if principal.exists() else None
    octets_deb = debordement.stat().st_size if debordement.exists() else 0

    if morts:
        raisons.append(
            f"{len(morts)} DEAD link(s) — pointed to by an index, absent from disk: "
            f"{', '.join(morts[:5])}. The remedy is to RESTORE the record or remove "
            f"the link, never to delete what remains."
        )
    if orphelines:
        raisons.append(
            f"{len(orphelines)} ORPHAN record(s) — on disk, POINTED TO BY "
            f"NOTHING: {', '.join(orphelines[:5])}. An orphan is not a record to "
            f"delete, it's a link to restore: *a document nothing points to "
            f"does not exist*."
        )
    if octets is None:
        raisons.append(
            f"the main index is ABSENT ({principal.name}): the size freeze was NOT evaluated."
            f" An absent index is not a small one -- reading it as a pass would make the"
            f" ratchet green exactly where it measures nothing."
        )
    elif octets > TAILLE_GELEE_DE_L_INDEX:
        raisons.append(
            f"the main index has GROWN: {octets} bytes against a freeze at "
            f"{TAILLE_GELEE_DE_L_INDEX} bytes (built-in wall: {MUR_DU_BUILTIN}). New "
            f"content goes into MEMORY-2.md — the freeze is never pushed back to let an "
            f"addition in."
        )
    if not debordement.exists():
        raisons.append(
            f"the overflow channel is ABSENT ({debordement.name}). Without it, "
            f"every new lesson falls back onto an index already at the wall."
        )
    # THE FREEZE IS AN ARGUMENT, NOT A CONSTANT READ HERE, AND A MEASUREMENT DECIDED THAT.
    # First written by reading `DETTE_SANS_BARRIERE` directly, this judge — which is PURE and
    # exercises on any folder at all — compared every 3-record fixture to a debt of 288: two
    # existing witnesses turned red instantly. *A check pulled from PRODUCTION makes every other
    # population unjudgeable.* The real caller passes the freeze; a witness passes its own.
    without_barrier = fiches_sans_barriere(dossier)
    if dette_gelee is not None and len(without_barrier) > dette_gelee:
        newest = ", ".join(without_barrier[:3])
        raisons.append(
            f"{len(without_barrier)} record(s) WITH NO BARRIER against a debt frozen at {dette_gelee} "
            f"— a new lesson was carved in as a plain moral reminder (e.g. {newest}). "
            f"*A lesson with no barrier is a wish* (A2): name the code that makes the fault "
            f"impossible, or WRITE that nothing prevents it — the admission is a valid, and "
            f"free, answer. This freeze is never lowered to let one more lesson in."
        )
    elif dette_gelee is not None and len(without_barrier) < dette_gelee:
        # A RATCHET THE CORPUS FLOATS ABOVE IS ONLY WAITING TO BE DESTROYED. As long as the
        # margin isn't zero, a new barrier-less lesson enters the game FOR FREE. The message
        # names the number to write — a refusal that doesn't say the gesture gets worked around.
        raisons.append(
            f"the debt has FALLEN: {len(without_barrier)} record(s) with no barrier against a freeze at "
            f"{dette_gelee} — {dette_gelee - len(without_barrier)} notch(es) of slack, meaning that many "
            f"empty lessons could pass without turning red. Write "
            f"DETTE_SANS_BARRIERE = {len(without_barrier)} in system/lib/mnemosyne/runtime/memoire.py."
        )
    return raisons, {
        "fiches": len(presentes),
        "cibles": len(pointees),
        "morts": len(morts),
        "orphelines": len(orphelines),
        "sans_barriere": len(without_barrier),
        "octets": octets,
        "octets_debordement": octets_deb,
        "dossier": str(dossier),
    }


def rendre(dossier: Path | None = None, *, dette_gelee: int | None = DETTE_SANS_BARRIERE) -> int:
    """Emits the overflow, THEN publishes the ratchet — in that order, and the order IS the check.

    The ratchet reports the overflow as injected by counting the bytes **actually written to
    output**, after writing them. Publishing the intent before the act would have produced the
    same sentence on a day the emission fails. *The EFFECT is measured, never the intent.*
    """
    dossier = dossier or dossier_de_memoire()
    raisons, m = verdict(dossier, dette_gelee=dette_gelee)

    emis = 0
    debordement = index_de_debordement(dossier)
    if debordement.exists():
        texte = debordement.read_text(encoding="utf-8")
        if texte.strip():
            print(
                "--- MEMORY-2.md (index overflow: the built-in only loads MEMORY.md) ---"
            )
            print(texte.rstrip())
            print()
            emis = len(texte.encode("utf-8"))

    etat = f"INJECTED({emis}b)" if emis else ("EMPTY" if debordement.exists() else "ABSENT")
    print(
        f"memory: records={m.get('fiches', '?')} <-> targets={m.get('cibles', '?')} · "
        f"dead={m.get('morts', '?')} · orphans={m.get('orphelines', '?')} · "
        f"index={m.get('octets') if m.get('octets') is not None else 'ABSENT'}"
        f"/{MUR_DU_BUILTIN} (freeze {TAILLE_GELEE_DE_L_INDEX}) · "
        f"no_barrier={m.get('sans_barriere', '?')}/{DETTE_SANS_BARRIERE} · "
        f"overflow={etat}"
    )
    for raison in raisons:
        print(raison)
    if not raisons:
        print(
            "EVERY NEW LESSON IS WRITTEN INTO MEMORY-2.md, AND ITS POINTER TOO — "
            "MEMORY.md is FROZEN (it sits at the built-in's wall). The records themselves don't move."
        )
    return 1 if raisons else 0
