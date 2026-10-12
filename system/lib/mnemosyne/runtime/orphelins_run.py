"""`make orphelins` -- the edge: parses the FOUR `mon_lot:` declarations (the three chats + the
orchestrator), lists the real files under `system/lib/`, measures the `Co-Authored-By` models from
their git history. `production/orphelins.py` stays pure; everything that touches disk or `git`
lives here.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from ..production.orphelins import PARTIES, Recensement, recenser, rendre

#: One post per party -- `chat-0-orchestrateur.md` counts as the FOURTH, exactly the
#: file the 2026-08-16 census missed (it has a `mon_lot:` of the same shape as the
#: three chats, but nothing read it as a declaration source).
_POSTE_PAR_PARTIE: dict[str, str] = {
    "chat-1": "chat-1.md",
    "chat-2": "chat-2.md",
    "chat-3": "chat-3.md",
    "orchestrateur": "chat-0-orchestrateur.md",
}

#: A top-level list entry under `mon_lot:` -- two spaces, a dash, the path (this repo's
#: paths never carry a space, so `\S+` stops exactly where the path stops, whether an
#: annotation follows it on the same line or not).
_ENTREE_RE = re.compile(r"^  - (\S+)")

#: A new top-level key -- closes the current `mon_lot:` section.
_CLE_RE = re.compile(r"^\w[\w-]*:")


def _chemins_declares(texte: str) -> frozenset[str]:
    """The RAW entries of `mon_lot:` -- literal paths AND `xxx/**` prefixes, NOT YET
    resolved against the real population (see :func:`_resoudre`)."""
    lignes = texte.splitlines()
    dans_la_section = False
    trouves: list[str] = []
    for ligne in lignes:
        if ligne.strip() == "mon_lot:":
            dans_la_section = True
            continue
        if not dans_la_section:
            continue
        if _CLE_RE.match(ligne):
            break
        m = _ENTREE_RE.match(ligne)
        if m:
            trouves.append(m.group(1))
    return frozenset(trouves)


def _resoudre(entrees: frozenset[str], fichiers_reels: frozenset[str]) -> frozenset[str]:
    """The RAW paths of a declaration, projected onto the real population -- an
    ``xxx/**`` prefix declares every real file starting with ``xxx/``, a literal path declares
    itself (present or not in the population -- a path declared outside the population judged
    here, e.g. ``docs/governance/**``, simply matches nothing, never an error)."""
    resolus: set[str] = set()
    for entree in entrees:
        if entree.endswith("/**"):
            prefixe = entree[: -len("**")]
            resolus.update(f for f in fichiers_reels if f.startswith(prefixe))
        else:
            resolus.add(entree)
    return frozenset(resolus)


def _declarations(postes_dir: Path, fichiers_reels: frozenset[str]) -> dict[str, frozenset[str]]:
    """The `mon_lot:` of the FOUR parties, each resolved against the real population. An
    unreadable post declares an EMPTY set rather than raising -- fail-open, the same discipline as
    `ui_contract._qui_tient_par_arc`."""
    declarations: dict[str, frozenset[str]] = {}
    for partie, nom_fichier in _POSTE_PAR_PARTIE.items():
        chemin = postes_dir / nom_fichier
        try:
            texte = chemin.read_text(encoding="utf-8", errors="replace")
        except OSError:
            declarations[partie] = frozenset()
            continue
        declarations[partie] = _resoudre(_chemins_declares(texte), fichiers_reels)
    return declarations


#: `type(IDENT): sujet` -- the same pattern as `routage_journal_run._SUJET_RE` (scope written
#: there); here it is NOT used to group by ident, only to confirm a commit is a
#: real turn and extract its model -- the ident itself is not the question asked here.
_COAUTHOR_RE = re.compile(r"^Co-Authored-By:\s*(.+?)\s*<", re.MULTILINE)
_SEP = "\x01"


def _modeles_par_fichier(repo_root: Path, fichiers_reels: frozenset[str]) -> dict[str, tuple[str, ...]]:
    """For each real file, the DISTINCT `Co-Authored-By` models from its full history
    (``git log --follow``) -- MEASURED, never inferred from the name of the chat that wrote it. A
    file absent from the result has never been committed (distinct from "orphan" -- see
    `Fichier.jamais_committe`).

    **SCOPE, written like `_SUJET_RE`'s own**: this signal reliably distinguishes
    "orchestrator" (always `Claude Opus 5` in this repo, measured) from "a chat" -- it does
    NOT distinguish ONE chat from ANOTHER when both run on the same model. Named rather than
    hidden: do not read this field as "chat 2 wrote this file"."""
    resultat: dict[str, tuple[str, ...]] = {}
    for chemin in fichiers_reels:
        try:
            sortie = subprocess.run(  # noqa: S603, S607
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "log",
                    "--follow",
                    f"--format={_SEP}%b",
                    "--",
                    chemin,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if sortie.returncode != 0:
            continue
        modeles: set[str] = set()
        for bloc in sortie.stdout.split(_SEP):
            m = _COAUTHOR_RE.search(bloc)
            if m:
                modeles.add(m.group(1))
        if modeles:
            resultat[chemin] = tuple(sorted(modeles))
    return resultat


#: The two folders the 2026-08-16 census swept (166 `.py` files, figure
#: reproduced -- see the log) -- frozen here rather than rediscovered on every call: the
#: scope of the question asked does not change from one turn to the next.
_DOSSIERS: tuple[str, ...] = (
    "system/lib/mnemosyne/production",
    "system/lib/mnemosyne/runtime",
)


def _fichiers_reels(racine: Path) -> frozenset[str]:
    trouves: set[str] = set()
    for dossier in _DOSSIERS:
        base = racine / dossier
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            trouves.add(str(p.relative_to(racine)))
    return frozenset(trouves)


def recensement(racine: Path) -> Recensement:
    """Assembles the real population, the four declarations, and the measured models, and
    returns the PURE verdict from `orphelins.recenser`."""
    fichiers = _fichiers_reels(racine)
    declarations = _declarations(racine / "docs" / "postes", fichiers)
    modeles = _modeles_par_fichier(racine, fichiers)
    return recenser(fichiers, declarations, modeles)


def resume(racine: Path) -> str:
    """The text of `make orphelins` -- fail-open: this LEVEL 1 check never raises, it publishes
    what it was able to measure."""
    try:
        r = recensement(racine)
    except OSError:
        return "orphelins NOT MEASURED -- the disk could not be read.\n"
    return rendre(r)


assert set(_POSTE_PAR_PARTIE) == set(PARTIES)  # the two homes of the party names stay in sync


#: The repo root, derived from this file's own location (``.../runtime/orphelins_run.py`` ->
#: ``parents[4]``). ``CLAUDE_PROJECT_DIR`` takes precedence when set -- the same pattern as
#: `arsenal_run._racine`: a defect that depends on the current directory never turns red for its
#: own author.
def _racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    return Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]


def main() -> int:  # pragma: no cover - [OPERATOR] surface
    print(resume(_racine()), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
