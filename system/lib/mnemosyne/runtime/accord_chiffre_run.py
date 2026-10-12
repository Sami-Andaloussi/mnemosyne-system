"""``make accord-chiffre`` (P6) — the EDGE: it RECOMPUTES the reference and visits every copy.

The judge (:mod:`mnemosyne.production.accord_chiffre`) reads nothing. Here, and only here, do we
touch disk and git.

**THE REFERENCE IS RECOMPUTED, NEVER RE-READ.** The number is written nowhere in this module: it
is **counted** from the numbered registry that :data:`SECTION` opens inside :data:`SOURCE`
(:func:`reference_invariants`). Pinning the value here would have created exactly the defect this
item fights — *a derivative that ages away from its source* — and the gate would have stayed green
the day one more entry was born.

**AND THE REFERENCE DOES NOT DERIVE FROM WHAT IS VERIFIED.** What we count are the **numbered
entries** of the registry; what we verify are the **prose sentences** that announce their count —
including the source document's own section title, which is a copy like any other and will be
flagged as one if it lies.

Population: what **git TRACKS**, never whatever litters the disk — ``projects/`` and
``knowledge/raw/`` are gitignored, and sweeping them in would mix the repository with dead
sandboxes.

Operator-facing prose is French in the source (D117); translated to English throughout this mirror.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from ..production.accord_chiffre import Recopie, SansRecopie, rendre, verdict

#: The document that CARRIES the registry, and the title of its section. A named PAIR: if the
#: title moves, the section is no longer found and the edge REFUSES, saying so — it does not count
#: a 0.
#:
#: **BOTH ARE SHIPPED BY THIS REPOSITORY**, and that is a condition, not a coincidence: a source of
#: truth that lives in some other repository cannot be recomputed here, and the gate would refuse
#: forever instead of measuring. The registry chosen is the skill architecture reference, whose
#: numbered layers are counted in prose by the skill guide that points at it.
#:
#: :data:`SECTION` STOPS BEFORE THE COUNT. The heading reads ``## Les 5 couches, …``: the prefix
#: matches the heading without swallowing its number, so **the title itself stays a copy like any
#: other** and gets confronted with the recomputed reference instead of being quietly exempted.
SOURCE = "system/skills/skill-creator/references/architecture.md"

#: WIDENED 2026-09-09 -- the heading exists in BOTH languages and the gate must not forbid the
#: translation it is meant to survive. It read ``"## Les"``, a French-only literal; the day the
#: mirror translated the heading to ``## The 5 layers, ...`` the gate stopped finding its section
#: and THREE witnesses went red -- correctly, because a section that cannot be found RAISES here
#: rather than returning 0 (see :func:`reference_couches`). That design is why the breakage was
#: loud instead of a silent wrong verdict.
#: NO lookahead on the count. A first attempt demanded the heading line also carry
#: ``<number> layers``; it was measured WRONG and reverted the same minute -- a witness writes the
#: heading as ``## Les two rules`` (count spelled out) precisely to exercise the no-copy path, and
#: the tighter pattern refused it. The disambiguation that ``## The rules`` would need is already
#: there, one function down: a section with NO numbered entry RAISES. The failure stays LOUD, which
#: is this module's whole doctrine -- never a silent wrong count.
_TITRE_SECTION = re.compile(r"^##[ \t]+(?:Les|The)\b", re.MULTILINE)

#: Human label only -- what the refusal message shows the reader. The MATCH is :data:`_TITRE_SECTION`.
SECTION = "## Les / ## The"

#: One registry entry: a number in COLUMN 0 followed by a period and a space. Column 0 is what
#: distinguishes a top-rank entry from an indented sub-bullet, and it is the only form this
#: registry uses.
_ENTREE = re.compile(r"^\d+\. ", re.MULTILINE)

#: The pattern for prose COPIES of the count. ``couches?`` covers the singular ("1 couche"): a
#: singular copy is still a copy, and a document that carries one must be SEEN before it can be
#: spared by the scope — excluding it from the pattern would amount to silently deciding it does
#: not exist.
_RECOPIE = re.compile(r"\b(\d+)\s+(?:couches?|layers?)\b")

#: The command the reader can re-run to obtain the reference themselves.
COMMANDE = "count of numbered entries in the skill architecture reference § « Les … couches »"

QUOI = "the layer count"


def _racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    return Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]


def reference_invariants(texte: str) -> int:
    """Count the entries of the registry :data:`SECTION` opens — ``ValueError`` if it is not found.

    **A SECTION THAT CANNOT BE FOUND RAISES, IT DOES NOT RETURN 0.** A ``0`` would propagate,
    accusing every copy site of writing a false figure: *a repaired gate has its own error rate*,
    and this one would condemn the entire corpus over a renamed heading.
    """
    trouve = _TITRE_SECTION.search(texte)
    debut = trouve.start() if trouve else -1
    if debut < 0:
        raise ValueError(
            f"section « {SECTION}… » not found in {SOURCE} — the reference cannot be "
            "computed, and 0 would be an accusation against the entire repository"
        )
    suivante = texte.find("\n## ", trouve.end())
    corps = texte[debut : suivante if suivante > 0 else len(texte)]
    combien = len(_ENTREE.findall(corps))
    if combien == 0:
        raise ValueError(
            f"section « {SECTION}… » of {SOURCE} contains NO numbered entry — "
            "a mute instrument, never an empty registry"
        )
    return combien


def documents_suivis(racine: Path) -> tuple[str, ...]:
    """The ``.md`` files git TRACKS. A git failure RAISES — never a silent empty scan.

    **THE MESSAGE ALWAYS NAMES ``git ls-files``, EVEN WHEN GIT ITSELF SPEAKS.** Found by a
    SURVIVING sabotage: replacing this ``raise`` with ``return ()`` left the suite green, because
    the population became empty and the ``SansRecopie`` guard raised further down — **with the
    SAME ``rc 2``**. *Two distinct failures produced identical code*, so only the TEXT can tell
    them apart, and it could not as long as it merely relayed git's own message.
    """
    sortie = subprocess.run(
        ["git", "-C", str(racine), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if sortie.returncode != 0:
        raise RuntimeError(f"git ls-files failed: {sortie.stderr.strip() or 'no message'}")
    return tuple(ligne for ligne in sortie.stdout.splitlines() if ligne.strip())


def recopies(racine: Path, documents: tuple[str, ...]) -> tuple[Recopie, ...]:
    """Every site where the figure is copied — **the module's only disk scan**."""
    trouvees: list[Recopie] = []
    for document in documents:
        chemin = racine / document
        try:
            texte = chemin.read_text(encoding="utf-8")
        except OSError:
            # A tracked but unreadable file is not "without a copy": it is UNREAD. It is left
            # out of the population rather than credited with an agreement we did not measure.
            continue
        for numero, ligne in enumerate(texte.splitlines(), start=1):
            for trouve in _RECOPIE.finditer(ligne):
                trouvees.append(
                    Recopie(
                        document=document,
                        ligne=numero,
                        valeur=int(trouve.group(1)),
                        extrait=ligne.strip()[:120],
                    )
                )
    return tuple(trouvees)


def desaccords_ouverts(racine: Path) -> int:
    """How many LIVE claims lie — **for the tick**. ``0`` if the instrument is mute.

    **The fail-open lives HERE AND NOWHERE ELSE**, exactly as with ``besoins_ouverts``: the tick
    asks this question at every session start, including on a fresh clone or outside a git
    repository, and letting it raise would block the session. The surface a human reads
    (:func:`main`) does refuse, and distinguishes its three outcomes.
    """
    try:
        reference = reference_invariants((racine / SOURCE).read_text(encoding="utf-8"))
        return len(verdict(reference, recopies(racine, documents_suivis(racine))).desaccords)
    except (OSError, ValueError, RuntimeError, SansRecopie, subprocess.SubprocessError):
        return 0


def main(argv: list[str] | None = None) -> int:
    """``rc 0`` in agreement · ``rc 1`` at least one LIVE claim lies · ``rc 2`` instrument failure."""
    racine = _racine()
    try:
        reference = reference_invariants((racine / SOURCE).read_text(encoding="utf-8"))
        sites = recopies(racine, documents_suivis(racine))
        accord = verdict(reference, sites)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as panne:
        print(f"REFUSED: {panne}", file=sys.stderr)
        print(
            "This is NOT 'the repository is in agreement': the instrument did not measure.",
            file=sys.stderr,
        )
        return 2
    except SansRecopie as panne:
        print(f"REFUSED: {panne}", file=sys.stderr)
        return 2

    print(rendre(accord, quoi=QUOI, commande=COMMANDE))
    return 0 if accord.accorde else 1


if __name__ == "__main__":
    raise SystemExit(main())
