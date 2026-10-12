"""CLI over the field-report channel — file one signalement, or read what is still pending.

    make signaler TITRE="make search crashes on an empty corpus"   # a PROJECT session FILES
    make signalements                                             # a MNEMOSYNE session DRAINS

Thin composition over :mod:`mnemosyne.production.signalements` (the logic lives there, this is the
entry point — ``runtime/`` is the machine room, ``production/`` the output layer). A pure
read/append over ``docs/signalements``: no model, no brick (D126).

The asymmetry is the point. The FILING side is deliberately trivial — a project session that hit a
defect should spend seconds here and go back to its own work, never minutes repairing Mnemosyne in
a context that was not built for it. The DRAINING side lists paths, because the session that
repairs must open and read each report in full.

The title arrives through the ENVIRONMENT (``MNEMO_TITRE``), not interpolated into a shell recipe:
a title is free text a session composes, and backticks or ``$(...)`` in a recipe would execute.

Code & docstrings English (D117); this repo's own convention prints in French - this
public-mirror copy is translated into English throughout."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ..production.carte import replier
from ..production.frontmatter_status import atomic_write, read_text
from ..production.plan_format import ARCS_DIRNAME
from ..production.plan_registry import read_plan_tree
from ..production.signalements import (
    DEFAULT_SIGNALEMENTS_DIR,
    file_signalement,
    identifiant_libre,
    inserer_dans_larc,
    item_de_braise,
    mark_handled,
    open_signalements,
)

#: Repo root from this module (``system/lib/mnemosyne/runtime/signalements.py`` → parents[4]).
_REPO_ROOT = Path(__file__).resolve().parents[4]
#: Where ``make signaler`` passes the title, out of reach of shell interpolation.
_TITLE_ENV = "MNEMO_TITRE"
#: Where ``make signalement-traite`` passes the path, same reason.
_FILE_ENV = "MNEMO_FICHIER"
#: D4 -- the fields that turn a signalement into a BRAISE rather than a plain report. All of them
#: go through the environment, same reason as ``_TITLE_ENV``: COUT is free text a shell recipe
#: must never interpolate.
_NIVEAU_ENV = "MNEMO_NIVEAU"
_COUT_ENV = "MNEMO_COUT"
_PLAN_ENV = "MNEMO_PLAN"


def _racine_du_plan(fichier_arc: Path) -> Path:
    """The folder that carries the GATE above ``fichier_arc`` -- its own parent when no ``plan/``
    folder (:data:`ARCS_DIRNAME`) encloses it (a gate targeted directly, or a single-file plan).
    Same rule as ``_above_arcs`` (``runtime/plan_archiver_run.py``, chat 1) but rewritten here
    rather than imported: that one is private to its own module."""
    return next(
        (parent.parent for parent in fichier_arc.parents if parent.name == ARCS_DIRNAME),
        fichier_arc.parent,
    )


def _shown(path: Path) -> Path:
    """``path`` relative to the repo when it is inside it — otherwise as-is (a temp tree in tests)."""
    try:
        return path.relative_to(_REPO_ROOT)
    except ValueError:
        return path


def render_open(paths: Sequence[Path]) -> str:
    """Render the pending signalements as readable markdown — or an honest 'nothing' line.

    Pure, like :func:`mnemosyne.runtime.tick.render_proposals`: a faithful projection of what is on
    disk. It lists PATHS, never a digest of the reports — the session that drains must read each one
    itself rather than trust a summary."""
    if not paths:
        return "# Mnemosyne · field reports\n\nNo field report pending.\n"
    noun = "field report" if len(paths) == 1 else "field reports"
    lines = [
        "# Mnemosyne · field reports",
        "",
        f"{len(paths)} {noun} waiting for a Mnemosyne session — read each one IN FULL before judging:",
        "",
    ]
    lines.extend(f"- `{_shown(path)}`" for path in paths)
    lines += [
        "",
        "Repair it (or convert it into an ember, I1 -- `make signaler ... NIVEAU=... APPLY=1`), then "
        "set `status:` to `traite` (a report is never deleted).",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _deposer_braise(*, titre: str, chemin_signalement: Path, apply: bool) -> int:
    """D4: the report ALSO becomes a plan item -- the half that ``--nouveau`` used not to do.

 Nothing here is guessed (D2): ``NIVEAU`` triggers the path, and ``COUT``/``PLAN`` are BOTH
 mandatory as soon as it does -- a single missing one refuses rather than choosing on the
 caller's behalf. The signalement itself stays filed no matter what happens next (invariant 2:
 a report is never lost, even when the item cannot be born). WHERE in the file no longer needs
 to be declared separately -- see :func:`~mnemosyne.production.signalements.inserer_dans_larc`.

 **``identifiant_libre`` READS THE WHOLE TREE, NEVER JUST THE TARGET FILE (D75 audit).** A
 first version only looked at ``plan_path``: two braises filed into two DIFFERENT arcs would
 then pick the SAME identifier (each only saw its own file), and the folded plan
 (:func:`~mnemosyne.production.carte.replier`, the one the rest of the repo actually reads)
 would lose one of the two as ``id_duplique`` -- *Fini quand* met all the same, silently. So the
 whole tree is read (:func:`~mnemosyne.production.plan_registry.read_plan_tree`) to pick the
 identifier, and only the single file named by ``PLAN`` gets WRITTEN to.

 DRY-RUN by default, same convention as ``plan-archiver``/``plan-convertir``: shows the item and
 REFUSES to write until ``--apply`` is passed. Read/write via
 :func:`~mnemosyne.production.frontmatter_status.read_text`/``atomic_write`` (``newline=""``) --
 never ``Path.read_text``/``write_text``, which would translate line endings and break the
 byte-for-byte CRLF reconstruction (D75 audit)."""
    niveau = os.environ.get(_NIVEAU_ENV, "").strip()
    if not niveau:
        return 0  # not a braise -- the plain `--nouveau` path already stops before this call
    champs = {
        "COUT": os.environ.get(_COUT_ENV, "").strip(),
        "PLAN": os.environ.get(_PLAN_ENV, "").strip(),
    }
    manquants = [nom for nom, val in champs.items() if not val]
    if manquants:
        print(
            f"NIVEAU given ({niveau!r}) but {' and '.join(manquants)} missing -- the report "
            "stays filed, no item created. Usage: make signaler TITRE=\"...\" NIVEAU=menace "
            'COUT="1 test" PLAN=path/to/plan.md [APPLY=1]',
            file=sys.stderr,
        )
        return 2
    plan_path = Path(champs["PLAN"])
    if not plan_path.is_absolute():
        plan_path = _REPO_ROOT / plan_path
    if not plan_path.is_file():
        print(
            f"Plan not found: {champs['PLAN']} -- the report stays filed, no item created",
            file=sys.stderr,
        )
        return 2
    racine = _racine_du_plan(plan_path)
    lectures = [p.reading for p in read_plan_tree(racine, racine.name) if p.reading is not None]
    if not lectures:
        print(
            f"Plan unreadable under {_shown(racine)} -- the report stays filed, no item created",
            file=sys.stderr,
        )
        return 2
    reading_complet, _collisions = replier(lectures)
    ident = identifiant_libre(frozenset(i.ident for i in reading_complet.items if i.ident))
    texte = read_text(plan_path)
    try:
        bloc = item_de_braise(
            titre=titre,
            niveau=niveau,
            cout=champs["COUT"],
            identifiant=ident,
            chemin_signalement=str(_shown(chemin_signalement)),
        )
    except ValueError as exc:
        print(f"Item refused: {exc} -- the report stays filed, no item created", file=sys.stderr)
        return 2
    resultat = inserer_dans_larc(texte, bloc_item=bloc)
    print(f"Item {ident} ready for {_shown(plan_path)}:\n\n{bloc}")
    if not apply:
        print("DRY RUN -- nothing was written. To apply: make signaler ... APPLY=1")
        return 0
    atomic_write(plan_path, resultat)
    print(f"Item {ident} written into {_shown(plan_path)}.")
    return 0


def main(argv: Sequence[str] | None = None, *, root: Path | None = None) -> int:
    """List the pending signalements, or file a new blank one with ``--nouveau``.

    The title comes from ``argv`` when given, else from ``MNEMO_TITRE``. An empty title is refused
    with a usage line rather than filing an untitled report.

    D4 -- when ``MNEMO_NIVEAU`` is also set, filing ALSO deposits the braise as a plan item (see
    :func:`_deposer_braise`); when it is absent, behaviour is byte-for-byte what it always was."""
    where = DEFAULT_SIGNALEMENTS_DIR if root is None else root
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--nouveau":
        titre = (" ".join(a for a in args[1:] if a != "--apply") or os.environ.get(_TITLE_ENV, "")).strip()
        if not titre:
            print('A title is required: make signaler TITRE="what broke"', file=sys.stderr)
            return 2
        path = file_signalement(titre, root=where)
        print(f"Field report opened: {_shown(path)}")
        print("Fill it in, then GO BACK TO YOUR WORK — do not repair Mnemosyne from this project.")
        return _deposer_braise(titre=titre, chemin_signalement=path, apply="--apply" in args)
    if args and args[0] == "--traite":
        # Symmetric to `--revu` on the proposals queue. Added when that one was built: the contract
        # said "flip status: to traite" and NO command did it, so draining meant hand-editing YAML —
        # the same shape of gap (a gesture with no door) that made endorse_document unreachable.
        raw = (" ".join(args[1:]) or os.environ.get(_FILE_ENV, "")).strip()
        if not raw:
            print("A file is required: make signalement-traite FICHIER=<path>", file=sys.stderr)
            return 2
        path = Path(raw)
        if not path.is_absolute():
            path = _REPO_ROOT / path
        if not path.is_file():
            print(f"Not found: {raw}", file=sys.stderr)
            return 2
        mark_handled(path)
        print(f"Field report marked handled: {_shown(path)}")
        print("The report stays where it is — we never delete (inv. 2).")
        return 0
    print(render_open(open_signalements(where)), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
