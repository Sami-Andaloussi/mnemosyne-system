"""Report documents that are no longer referenced without moving or deleting them."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

#: Public entry documents are retained even when no other document links to them. The set protects
#: future navigation without relying on host-specific instruction files.
PORTES_D_ENTREE: frozenset[str] = frozenset({"README.md", "ARCHITECTURE.md"})

#: Already outside the reading scope: the only place where the obsolete is tolerated (`docs/README.md`,
#: not part of this mirror). Flagging them again would grow the report with permanent noise that no
#: action could ever clear.
DEJA_ARCHIVE: tuple[str, ...] = ("docs/archive/",)

#: Where a dead document goes. The report NAMES it, and never takes it there itself.
DESTINATION = "docs/archive/"


@dataclass(frozen=True, slots=True)
class Orphelin:
    """A document that nothing cites. ``jours`` is indicative only - see :func:`documents_orphelins`."""

    chemin: str
    jours: int
    octets: int


def _est_hors_champ(chemin: str) -> bool:
    return chemin in PORTES_D_ENTREE or any(chemin.startswith(p) for p in DEJA_ARCHIVE)


def documents_orphelins(
    racine: Path,
    documents: tuple[str, ...],
    corpus: tuple[str, ...],
    *,
    maintenant: float | None = None,
) -> tuple[Orphelin, ...]:
    """The documents in ``documents`` that no file in ``corpus`` mentions, oldest first.

    ``documents`` and ``corpus`` are passed in by the caller (paths relative to ``racine``) rather
    than discovered here: the surface pulls them from `git ls-files`, a test drops them into a
    `tmp_path`. A module that called git itself could only ever be judged against the real repo -
    *a check drawn from production makes every other population unjudgeable*, a mistake this
    codebase has already paid for once.

    THE SEARCH MATCHES BOTH THE PATH **AND** THE FILENAME, AND THE DIRECTION OF THE ERROR
    DECIDES THAT CHOICE. Matching the name alone over-detects citations, so it UNDER-reports orphans;
    matching the path alone would call a document dead when it is actually cited by name in prose.
    Between wrongly proposing to archive a living document and staying silent about a dead one, this
    picks silence: the first cost falls on the operator's own files, the second on readability - and
    the second corrects itself on the next pass.

    WARNING: ``jours`` comes from **mtime**, never from git history, and it is only a sort key: a
    fresh `git clone` would put everyone back at zero days without the verdict changing by one bit.
    It is shown to tell today's draft apart from a document dead for three weeks, not to decide
    anything.
    """
    reference = time.time() if maintenant is None else maintenant
    textes: list[str] = []
    for relatif in corpus:
        try:
            textes.append((racine / relatif).read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            # Unreadable => we cannot claim it cites NOTHING. It is skipped as a source, which can
            # only ever ADD orphans... so it is ALSO dropped as proof of absence: that is the only
            # direction that never invents a death.
            continue

    trouves: list[Orphelin] = []
    for relatif in documents:
        if _est_hors_champ(relatif):
            continue
        chemin = racine / relatif
        nom = chemin.name
        cite = False
        for i, texte in enumerate(textes):
            if corpus[i] == relatif:
                continue  # a document does not cite itself just by naming itself
            if relatif in texte or nom in texte:
                cite = True
                break
        if cite:
            continue
        try:
            etat = chemin.stat()
        except OSError:
            continue
        trouves.append(
            Orphelin(
                chemin=relatif,
                jours=max(0, int((reference - etat.st_mtime) // 86_400)),
                octets=etat.st_size,
            )
        )
    return tuple(sorted(trouves, key=lambda o: (-o.jours, o.chemin)))


@dataclass(frozen=True, slots=True)
class LienMort:
    """A relative link that does not resolve. ``gele`` = the target lives under `docs/archive/`."""

    document: str
    ligne: int
    cible: str
    gele: bool


#: A markdown link `[text](target)`. The `#...` anchor is stripped: it does not change the file.
_LIEN = re.compile(r"\[[^\]]*\]\(<?([^)>\s#]+)(?:#[^)>]*)?>?\)")
#: A code-block fence. WITHOUT THIS SKIP, THE CHECK COUNTS EXAMPLES: a document that
#: carries `[docs/FORMAT_PLAN.md](...)` inside a sample JSON payload would have that example read
#: as a false dead link.
_CLOTURE = re.compile(r"^\s*(?:```|~~~)")
_EXTERNE = ("http://", "https://", "mailto:", "tel:")


def liens_morts(racine: Path, documents: tuple[str, ...]) -> tuple[LienMort, ...]:
    """Every relative link in a tracked document that resolves to nothing.

    WHY THIS CHECK EXISTS: *a clean-up is a portability test*. On YYYY-MM-DD, archiving
    the previous plan moved it down one directory level and broke **23** of its relative links in a
    single stroke - nobody noticed for eleven days. The question "can a link die?" had already been
    written down as a planned checkpoint; now it asks itself on its own.

    THIS CHECK DOES NOT DECIDE WHAT GETS ARCHIVED. Documents under `docs/archive/` are
    frozen VERBATIM - the previous plan's restitution was verified as "13 out of 13 arcs identical
    down to the byte". Fixing their links would destroy the one property that matters for them. They
    are therefore marked ``gele=True`` and REPORTED, never corrected: the caller decides, and the
    check only demands zero on the LIVE field.
    """
    trouves: list[LienMort] = []
    for chemin in documents:
        fichier = racine / chemin
        try:
            texte = fichier.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        dans_bloc = False
        for numero, ligne in enumerate(texte.splitlines(), start=1):
            if _CLOTURE.match(ligne):
                dans_bloc = not dans_bloc
                continue
            if dans_bloc:
                continue
            for trouve in _LIEN.finditer(ligne):
                cible = trouve.group(1)
                if cible.startswith(_EXTERNE):
                    continue
                if (fichier.parent / cible).exists():
                    continue
                trouves.append(
                    LienMort(
                        document=chemin,
                        ligne=numero,
                        cible=cible,
                        gele=any(chemin.startswith(p) for p in DEJA_ARCHIVE),
                    )
                )
    return tuple(sorted(trouves, key=lambda m: (m.gele, m.document, m.ligne)))


def compte_orphelins(racine: Path, documents: tuple[str, ...], corpus: tuple[str, ...]) -> int:
    """How many, and NOTHING else - the only thing the tick is allowed to know.

    A count, never a path: a signal that crosses a compartment boundary must never carry substantive
    content, exactly like its neighbour `clear_cruft_count`.
    """
    return len(documents_orphelins(racine, documents, corpus))


def _rendre_liens(morts: tuple[LienMort, ...]) -> list[str]:
    """The links section - kept separate, because its RULE is not the orphans' rule."""
    vivants = [m for m in morts if not m.gele]
    geles = [m for m in morts if m.gele]
    lignes = ["", "## Relative links"]
    if not vivants:
        lignes.append("**No dead link in the live field.**")
    else:
        lignes.append(f"WARNING: **{len(vivants)} dead link(s)** in the live field:")
        lignes += [f"- `{m.document}:{m.ligne}` -> `{m.cible}`" for m in vivants]
        lignes.append(
            "> A moved target gets RE-POINTED; *a clean-up is a portability test*."
        )
    if geles:
        lignes.append(
            f"INFO: {len(geles)} under `docs/archive/` - **dead by construction, and left untouched**: "
            f"these documents are frozen VERBATIM (restitution verified down to the byte). Fixing "
            f"their links would destroy the one property that matters for them. The target can still "
            f"be found by its name."
        )
    return lignes


def rendre(
    orphelins: tuple[Orphelin, ...],
    *,
    examines: int,
    morts: tuple[LienMort, ...] = (),
) -> str:
    """What the operator reads. The report says what it LOOKED AT, not only what it found.

    Publishing the population examined is not decoration: a report that says "0 orphans"
    because it scanned nothing reads exactly like a healthy repo. *A refusal reads as one, an empty
    result is taken on faith.*
    """
    lignes = [f"# Mnemosyne  -  documents - {examines} document(s) examined"]
    if not orphelins:
        lignes.append("")
        lignes.append(
            "No orphan document: everything tracked is cited by something."
        )
        return "\n".join(lignes + _rendre_liens(morts))

    lignes.append("")
    lignes.append(
        f"{len(orphelins)} document(s) that **nothing points to** - *a document that nothing points "
        f"to does not exist*. Oldest first (age indicative only, mtime):"
    )
    lignes.append("")
    for o in orphelins:
        lignes.append(f"- `{o.chemin}` - {o.jours} d  -  {o.octets} b")
    lignes.append("")
    lignes.append(
        f"> **A proposal, not an action**: what is dead goes down into `{DESTINATION}` "
        f"(non-destructive: it leaves the reading scope, not the repo). "
        f"**This report moves NOTHING**: archiving is a judgment call on a document's value, "
        f"and moving one of the operator's files is THEIR gesture to make."
    )
    lignes.append(
        "WARNING: An orphan is not necessarily dead: it can be a **living document that nobody has "
        "linked to yet**. The fix then is to CITE it, not to archive it."
    )
    return "\n".join(lignes + _rendre_liens(morts))
