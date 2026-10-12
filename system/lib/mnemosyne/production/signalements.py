"""The field-report channel: a PROJECT session FILES a suspected Mnemosyne defect, then moves on.

The first real project (the research project) will hit Mnemosyne defects. Two things must NOT happen: the
project session must not derail into repairing the system (wrong context, wrong mandate), and the
project's owner must not become the messenger who diagnoses "is this the project or the system?"
and relays it by hand. So the REPO is the channel, not a conversation: the project session drops a
signalement here, works around it, and keeps producing; the tick counts what is pending; a
Mnemosyne session drains it.

Deliberately NOT a ledger. Its sibling :mod:`mnemosyne.production.veille_ledger` keeps state in a
separate ``.jsonl`` because it tracks EXTERNAL artefacts (fiches it does not own). A signalement is
our OWN artefact, so it carries its own state in its own frontmatter — one file, one truth, nothing
to drift out of sync.

GITIGNORED on purpose (``docs/signalements/*.md``), like ``knowledge/proposals/`` and
``system/state/*.jsonl``. The first design tracked them in git — a defect report felt
non-reconstructible (invariant 24) — and an audit killed that: the report is free prose composed
from INSIDE a project's context, so it can name a personal source in its body AND in its title,
which becomes a permanent filename. A warning in a template is discipline; this repo requires an
incapacity (D100 / invariant 17), so the barrier is ``.gitignore``, not prose.

What is genuinely durable is not the complaint but the FIX — and the fix lands in git (the repair
commit, plus the project's internal decision log when it is structural). Draining therefore means
repairing AND recording the lesson where it survives; the report itself is a local work note
(D153).

**A SECOND drain path exists since I1 (D4's braise mechanism): converting a report into a
tracked plan item — see :func:`item_de_braise`/:func:`inserer_dans_larc` and
``docs/signalements/README.md``'s dated section.** There, ``status: traite`` means "the plan now
tracks this," not "repaired" — the real fix is still a separate, later commit. No code here
enforces that a ``traite``-via-conversion report still has a live item pointing back to it; that
link is a fact today (the item's own ``*À lire*`` field), never a checked invariant.

Draining flips a status; it never deletes (invariant 2). Code & docstrings English (D117); the
files a human reads are French in the source repository (governance). This public-mirror copy
translates that prose, but the plan-item FIELD NAMES emitted by :func:`item_de_braise`
(``*Produit*``, ``*Fini quand*``, ``*Obligation*``, ...) stay French: they are the closed
vocabulary :data:`~mnemosyne.production.plan_format.KNOWN_FIELDS` parses.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .frontmatter_status import (
    FRONTMATTER_RE,
    MAX_SLUG,
    STATUS_RE,
    atomic_write,
    create_dated_entry,
    read_text,
    slugify,
    split_frontmatter,
    today_stamp,
    yaml_quoted,
)
from typing import Final

#: Repo root from this module (``system/lib/mnemosyne/production/signalements.py`` → parents[4]).
_REPO_ROOT: Final = Path(__file__).resolve().parents[4]
#: Where signalements live. GITIGNORED except this directory's ``README.md`` (the contract) — the
#: barrier is ``.gitignore``, not prose; see the module docstring for why a report must not enter git.
DEFAULT_SIGNALEMENTS_DIR: Final = _REPO_ROOT / "docs" / "signalements"

#: A signalement still awaiting a Mnemosyne session.
OPEN: Final = "ouvert"
#: A signalement a Mnemosyne session has drained. Kept on disk forever (invariant 2), never deleted.
HANDLED: Final = "traite"
#: Longest slug we put in a filename — from :mod:`~mnemosyne.production.frontmatter_status`, the ONE
#: home. An agent pasting a whole error message as the title is the NOMINAL case, and an untruncated
#: one raises ``OSError: File name too long`` (255 bytes on APFS).
_MAX_SLUG: Final = MAX_SLUG

#: The LEADING frontmatter block, and only it. Anchored at ``\A`` so a body that happens to contain a
#: ``status:`` line — e.g. a report ABOUT the fiche frontmatter writer, quoting its output — can never
#: be mistaken for the real field, nor rewritten by :func:`mark_handled`.
#: Both come from :mod:`~mnemosyne.production.frontmatter_status`, the ONE implementation shared with
#: the proposals queue. Do not re-declare them here: an audit found that an UNBOUNDED status match
#: rewrote the BODY of a report that merely quoted ``status:`` in its prose, and a second copy would
#: risk reintroducing exactly that.
_FRONTMATTER_RE: Final = FRONTMATTER_RE
_STATUS_RE: Final = STATUS_RE
#: A previous drain stamp — stripped before re-stamping, so a manually re-opened report cannot end up
#: carrying two ``traite_le:`` keys.
_HANDLED_AT_RE: Final = re.compile(r"^traite_le:[^\r\n]*\r?\n?", re.MULTILINE)
#: Files that are not signalements (the contract doc lives in the same directory).
_NOT_A_SIGNALEMENT: Final = frozenset({"README.md"})


_read = read_text
_atomic_write = atomic_write


_slug = slugify
_yaml_quoted = yaml_quoted
_frontmatter = split_frontmatter


def _status_of(path: Path) -> str | None:
    """The declared status of one signalement — ``None`` when unreadable, or lacking a status field.

    Fail-OPEN like :mod:`~mnemosyne.production.veille_ledger`: a file we cannot parse is skipped, not
    fatal. The residual is named rather than hidden — a report whose FRONTMATTER BLOCK is destroyed
    (no leading ``---``) stops being counted, so it goes silent instead of blocking the tick. A merely
    odd status value (``Ouvert``, a trailing comment) is still read; only a broken block is lost."""
    try:
        text = _read(path)
    except OSError:
        return None
    parts = _frontmatter(text)
    if parts is None:
        return None
    found = _STATUS_RE.search(parts[1])
    return found.group(1).lower() if found else None


def open_signalements(root: Path = DEFAULT_SIGNALEMENTS_DIR) -> tuple[Path, ...]:
    """Every signalement still awaiting a Mnemosyne session, oldest first.

    Filename order IS chronological: names start with the ISO date and any collision suffix is
    zero-padded, so lexicographic sorting cannot put ``-10`` before ``-02``. Missing directory ⇒
    empty (the channel has simply never been used), never an error."""
    if not root.is_dir():
        return ()
    return tuple(
        path
        for path in sorted(root.glob("*.md"))
        if path.name not in _NOT_A_SIGNALEMENT and _status_of(path) == OPEN
    )


def open_signalement_count(root: Path = DEFAULT_SIGNALEMENTS_DIR) -> int:
    """HOW MANY signalements await — the meta-signal the tick surfaces, never their content (inv. 22)."""
    return len(open_signalements(root))


#: MEASURED ON 2026-09-08, AND THAT IS WHAT GOT THIS FUNCTION WRITTEN. The count ALONE was
#: already published at every session start — and **12 reports stayed open, the oldest for 27
#: days**, while that line kept showing. The field report concluded "the drain has NO trigger";
#: the measurement says the opposite, and it is worse: *the trigger existed, it spoke up, and it
#: did not carry what makes a queue alarming.* "12 open" reads like a normal queue; "the oldest is
#: 27 days old" reads like an outage. It is the SAME data under two descriptions, and only one of
#: the two triggers a gesture.
#: The class: *a count says SIZE, never STASIS.* A stable number of open reports is
#: indistinguishable from a healthy, high-throughput channel — only the AGE of the oldest one
#: tells the two apart.
def oldest_open_signalement_age_days(
    root: Path = DEFAULT_SIGNALEMENTS_DIR,
    *,
    today: date | None = None,
) -> int | None:
    """Age IN DAYS of the oldest signalement still open — ``None`` when the queue is empty.

    The date comes from the FILENAME's ISO stamp, which :func:`file_signalement` writes and which
    :func:`open_signalements` already relies on for chronological order — never from the filesystem
    mtime, which any `git checkout`, copy or iCloud sync rewrites without the report having moved.
    A name whose stamp will not parse is SKIPPED rather than guessed: an unreadable date must not
    manufacture a false age, in either direction. Negative ages (a stamp in the future, clock skew)
    are clamped to 0 — the queue can be fresh, never younger than empty."""
    reference = today or date.today()
    ages: list[int] = []
    for path in open_signalements(root):
        try:
            filed = date.fromisoformat(path.name[:10])
        except ValueError:
            continue  # unparseable stamp — skipped, never guessed (a wrong age is worse than none)
        ages.append(max(0, (reference - filed).days))
    return max(ages) if ages else None


def file_signalement(
    title: str,
    *,
    root: Path = DEFAULT_SIGNALEMENTS_DIR,
    today: date | None = None,
) -> Path:
    """Create one blank, well-formed signalement for ``title`` and return its path.

    The CODE only builds the well-formed shell (frontmatter + the questions to answer); the session
    that hit the defect writes the prose. Two same-titled reports on the same day cannot collide: the
    exclusive create lives in :func:`~mnemosyne.production.frontmatter_status.create_dated_entry`,
    shared with the parenthèses queue — the ``O_EXCL``, not an ``exists()`` look, is what makes the
    guarantee hold for two sessions filing at the same instant."""
    stamp = today_stamp(today)
    body = _TEMPLATE.format(status=OPEN, date=stamp, titre=_yaml_quoted(title), titre_nu=title)
    return create_dated_entry(root, stamp=stamp, title=title, body=body)


def mark_handled(path: Path, *, today: date | None = None) -> Path:
    """Flip one signalement to ``traite`` — the drain gesture. NEVER deletes it (invariant 2).

    Idempotent: re-running on an already-handled (or unparseable) report leaves it untouched. Only
    the LEADING frontmatter block is rewritten — everything after it is spliced back verbatim, so the
    prose a human wrote is preserved byte-for-byte, line endings included."""
    text = _read(path)
    parts = _frontmatter(text)
    if parts is None:
        return path  # no frontmatter block — never rewrite what we did not recognise
    _, inner, rest = parts
    found = _STATUS_RE.search(inner)
    if found is None or found.group(1).lower() != OPEN:
        return path  # already drained, or a status we do not recognise
    stamp = (today or date.today()).isoformat()
    fixed = _HANDLED_AT_RE.sub("", _STATUS_RE.sub(f"status: {HANDLED}", inner, count=1))
    _atomic_write(path, f'---\n{fixed.rstrip()}\ntraite_le: "{stamp}"\n---\n{rest}')
    return path


#: The two levels a braise can declare (D4) — never a third, never guessed.
NIVEAUX_BRAISE: Final = ("invalide", "menace")


def item_de_braise(
    *, titre: str, niveau: str, cout: str, identifiant: str, chemin_signalement: str
) -> str:
    """Renders one well-formed plan-item block from a braise -- PURE, writes nothing to disk.

 **Refuses if ``cout`` is empty** (*Obligation* level 2 of D4: *"a braise with no declared
 cost is refused"*). ``niveau`` must be one of :data:`NIVEAUX_BRAISE` -- any other value raises
 rather than guessing which of the two was meant.

 **Uses ONLY the fields ``plan_format.KNOWN_FIELDS`` recognises** (checked against the real
 reader, not assumed) -- an invented field (``*Origine*``, ``*Coût*``) would be recognised by
 NO accessor: ``read_item_fields`` would see it as a marker, would not find its token in
 ``_FIELD_BY_KEY``, and would swallow it without attaching it to anything -- no error, no
 readable value, a field that looks declared and is declared nowhere. The **cost** therefore
 goes into ``*Taille*`` (the field already established for an estimate in this repo) and the
 **level** into ``*Obligation*`` (the three-level scale, A2) -- both already read by the rest
 of the repo, no third vocabulary home opened here.

 **``identifiant`` MUST stay under 12 characters -- found by checking, not assumed.** A
 first attempt (``BRAISE-2026-08-04``, 18 characters) passed `read_item_fields` alone but
 disappeared ENTIRELY from `read_plan` (the full reader): `plan_format._IDENT_RE` bounds an
 identifier to `[A-Za-z][A-Za-z0-9-]{0,11}`. This function does NOT check that itself (it would
 stop being a PURE judge, knowing `plan_format`'s grammar by heart) -- it is up to the edge that
 generates a real identifier to stay under that bound, proven by
 ``test_un_identifiant_TROP_LONG_disparait_du_lecteur_reel``.

 **ADMISSION (A2, D75 audit): the text ``invalide`` declares a block that NO code actually
 enforces.** Both levels write ``*Dépend de* : AUCUNE`` -- measured against the REAL
 `plan_ordre.py`: an `invalide` braise changes neither wave, nor unblocking, nor cycle, exactly
 like `menace`. D4's ("only `invalide` blocks the arc it was born in") therefore has NO
 barrier today -- it is a sentence that `*Obligation* : niveau 2` **declares**, with no code
 READING it to refuse anything (`obligation_run.py` says so of itself: no gate calls it). D4's
 *Fini quand* only requires the `menace` witness (already proven, see
 `test_une_braise_MENACE_ne_bloque_aucune_etape_deja_existante`); wiring a real block for
 `invalide` is a separate item, not guessed here.

 **CLASS, NOT CASE (the orchestrator, 2026-08-15 22:01): the first FIVE braises were fixed
 one by one (`*Test à trois*` added by hand), and that closed the CASES, not the CLASS -- this
 function still did not emit it, so a sixth braise would have reproduced the same red on
 `test_chaque_item_repond_au_test_a_trois`.** Verified: `grep 'Test à trois'
 production/signalements.py` returned `0`. `*Test à trois*` therefore joins `*Produit*` with
 the SAME admission: at filing time, only the original report carries the diagnosis -- whether
 the fix generalises depends on its final shape, which only whoever picks up the item knows. A
 text that guesses would be worse than a text that NAMES the uncertainty."""
    if niveau not in NIVEAUX_BRAISE:
        raise ValueError(
            f"unknown niveau: {niveau!r} -- must be one of {NIVEAUX_BRAISE}, never guessed"
        )
    if not cout.strip():
        raise ValueError("a braise with no declared cost is refused (*Obligation* niveau 2 of D4)")
    if niveau == "invalide":
        bloque = "BLOCKS the arc it was born in -- the work in progress is FALSE as long as it stands"
        obligation = "niveau 2 -- opening a hardening beneath it is refused (see D3)"
    else:
        bloque = "blocks NO step -- the work in progress stays VALID, merely threatened"
        obligation = "niveau 1 -- published, refuses nothing as long as it remains a threat"
    return (
        f"- **{identifiant}** \U00002B1C **BRAISE -- {titre}**\n"
        f"  Originating field report: `{chemin_signalement}` -- niveau `{niveau}` ({bloque}).\n"
        "  *Produit* : to be specified by whoever picks up the item -- the originating report "
        "carries the full diagnosis.\n"
        "  *Fini quand* : the class described in the field report no longer recurs.\n"
        f"  *Obligation* : {obligation}\n"
        "  *Dépend de* : AUCUNE\n"
        "  *Prérequis* : AUCUN\n"
        f"  *À lire* : `{chemin_signalement}` (the originating report, the only trace of the diagnosis)\n"
        f"  *Taille* : {cout}\n"
        "  *Test à trois* : to be specified by whoever picks up the item -- depends on the shape "
        "of the fix, not on the diagnosis alone.\n"
    )


#: The prefix of every identifier generated by :func:`identifiant_libre` -- never derived from the
#: level (the level already lives in *Obligation*, one single source, not two that could diverge).
_PREFIXE_BRAISE: Final = "BR"


def identifiant_libre(pris: frozenset[str] | set[str], *, prefixe: str = _PREFIXE_BRAISE) -> str:
    """The first ``{prefixe}{n}`` (n >= 1) absent from ``pris`` -- PURE, does not read any plan
    itself.

    **Takes ONLY the set of already-taken identifiers**, never a whole ``PlanReading``: this
    function does not need to know `plan_format` to pick a free name, and staying decoupled avoids
    a cross-import to chat 1's reader for a single signature.

    Stays under `plan_format._IDENT_RE`'s 12 characters as long as ``prefixe`` already is and
    ``pris`` holds fewer than 10**9 identifiers of the same prefix -- no real plan comes within a
    thousandth of that (see `item_de_braise` for the measured, not assumed, bound)."""
    n = 1
    while f"{prefixe}{n}" in pris:
        n += 1
    return f"{prefixe}{n}"


#: The markdown section header (``## …``). Same contract as the ``## N · Title`` shape observed in
#: this repo's arcs, but nothing here requires the middle dot -- only the complete line counts.
_SECTION_RE: Final = re.compile(r"^##[ \t]+.*$", re.MULTILINE)


#: A run of trailing line endings, \r\n/\r/\n alike. ``str.rstrip("\n")`` does NOT understand
#: ``\r\n`` as one unit -- on ``"...x\r\n\r\n"`` it only eats the last ``\n`` and leaves an orphan
#: ``\r``, so ``fin_originale`` loses one of the two blank lines and the original CRLF ends up
#: amputated. Found while testing D4 in CRLF (the D75 audit had already fixed the READ side; the
#: RECONSTRUCTION had the same defect one step further along).
_FIN_DE_LIGNES: Final = re.compile(r"(?:\r\n|\r|\n)+\Z")


def _sans_lignes_finales(texte: str) -> str:
    """``texte`` without its trailing line endings, whatever their style -- see :data:`_FIN_DE_LIGNES`."""
    return _FIN_DE_LIGNES.sub("", texte)


def inserer_item(texte_plan: str, *, sous_section: str, bloc_item: str) -> str:
    """Inserts ``bloc_item`` at the END of section ``sous_section`` of a plan -- never guessed.

    **``sous_section`` must name the section EXACTLY** (the complete ``## …`` line, leading
    spaces included after cleanup) -- this function never chooses which arc receives a braise, it
    carries out a choice already made elsewhere (same D2 doctrine: the product -- here the
    destination -- is DECLARED, it is never guessed).

    **EXACT RECONSTRUCTION outside the insertion point** -- everything that is not the gap
    where ``bloc_item`` gets inserted is copied back BYTE FOR BYTE (same discipline as
    ``plan_archiver``): this function reformats nothing, renumbers nothing, touches no other
    section.

    Raises ``ValueError`` if ``sous_section`` does NOT appear in ``texte_plan`` -- inserting into
    an absent section would silently create a phantom section rather than naming the error.
    """
    sections = tuple(_SECTION_RE.finditer(texte_plan))
    cible = next((m for m in sections if m.group(0).strip() == sous_section.strip()), None)
    if cible is None:
        raise ValueError(
            f"section introuvable : {sous_section!r} — aucune insertion, jamais une section "
            "fantôme créée en silence"
        )
    apres_cible = [m for m in sections if m.start() > cible.start()]
    fin_section = apres_cible[0].start() if apres_cible else len(texte_plan)
    corps_section = texte_plan[cible.end() : fin_section]
    # The item is appended after the last non-blank character of the section, preserving ALL the
    # rest (trailing line breaks included) -- never a `rstrip()` that would lose what the author
    # wrote after the last item (a note, a summary table).
    point = len(_sans_lignes_finales(corps_section))
    fin_originale = corps_section[point:]  # the trailing line endings, exactly as they were
    inseree = corps_section[:point] + "\n\n" + _sans_lignes_finales(bloc_item) + "\n" + fin_originale
    return texte_plan[: cible.end()] + inseree + texte_plan[fin_section:]


def inserer_dans_larc(texte_plan: str, *, bloc_item: str) -> str:
    """Inserts ``bloc_item`` at the END of the arc's BODY -- everything before its FIRST ``## ``,
    or the end of the text if it has none. PURE.

    **FOUND BY AUDITING D4 AGAINST THE REAL CORPUS, NOT ASSUMED.** `inserer_item(sous_section=…)`
    requires a NAMED ``## `` section -- measured on the 10 real arc files in this repo's plan
    corpus (not part of this mirror), each carrying a single ``# ARC X · …``. The Makefile's help
    text additionally documented a shape (``## N · Title``) absent from ALL the real files (a
    `grep '^## [0-9]'` over that corpus -> 0 files).

    **FIXED AFTER A SECOND AUDIT (D75): "ten for ten, EXACTLY one section" was WRONG,
    measured with a `grep -c '^## '` count over that same corpus.** One of those files -- the
    foundation-arc document -- carries TWO: ``## LE TEST À TROIS`` (line 588) *and* ``## Ce que
    cet arc ne porte PAS`` (line 677) -- and the first one is not empty: item **A8** (born the
    same day as this module, from an audit report on a DIFFERENT batch) lives there, on line 626.
    The premise "there is structurally only ever one answer" does therefore NOT hold everywhere in
    the corpus that motivated it -- nine arcs out of ten confirm it, one does not. What remains
    true, measured again after this correction: of the TWO ``## `` sections in that one file, only
    one ("Ce que cet arc ne porte PAS") is never a container for items -- ``## LE TEST À TROIS`` IS
    one, exceptionally.

    **WHAT THE FUNCTION DOES STAYS CORRECT DESPITE THE FALSE PREMISE, AND THAT TOO IS MEASURED,
    NOT ASSUMED** : against the 10 real arcs, including the foundation-arc document, the insertion
    loses no pre-existing item and produces no new kind of problem -- it simply targets the FIRST
    ``## `` it meets, whatever it carries. For the vast majority of the corpus (9/10), that is
    "before the only section, which never contains an item." For that one file, it is "before the
    `LE TEST À TROIS` table, which DOES contain some" -- a less elegant choice than what the
    docstring used to claim, but still lossless and uncorrupted. `inserer_item` stays correct and
    useful for a future caller that targets a REAL named subsection instead.

    Same reconstruction discipline as :func:`inserer_item` -- everything outside the insertion gap
    is copied back BYTE FOR BYTE."""
    premiere = _SECTION_RE.search(texte_plan)
    fin_corps = premiere.start() if premiere else len(texte_plan)
    corps = texte_plan[:fin_corps]
    point = len(_sans_lignes_finales(corps))
    fin_originale = corps[point:]
    inseree = corps[:point] + "\n\n" + _sans_lignes_finales(bloc_item) + "\n" + fin_originale
    return inseree + texte_plan[fin_corps:]


#: The shell the filing session fills in. Translated for this public mirror. The closing
#: note is guidance, not a guard: the guard is ``.gitignore`` (D153), which is why the note can
#: tell the filer to be FRANK about the failure instead of policing what they type.
_TEMPLATE: Final = """---
status: {status}
date: "{date}"
titre: {titre}
---

# {titre_nu}

**What I was doing** -

**What broke** -

**What I expected** -

**How to reproduce it** -

**Workaround** (how I kept going without blocking the project) -

**My diagnosis** - Mnemosyne / the project / I don't know *(doubt is a valid answer:
it is the Mnemosyne session that decides, not you)*

> This report stays **local**: it does not enter the versioned history (structural barrier,
> D153). So describe the failure **frankly**, without self-censoring. What must *survive* is
> not this report - it is the **lesson**, and it will be carved into the repair commit.
"""
