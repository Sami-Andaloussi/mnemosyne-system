"""``make obligation`` ("plans" workstream · A2) -- the page that says what each capability OBLIGES.

The judge (:mod:`mnemosyne.production.obligation`) is PURE: it fetches no population itself. It is
HERE, at the edge, that the two files get read -- the ``Makefile`` (the real population) and
the obligation registry file (the TRUTH, ``.md`` + git, D44).

**Three return codes, and they do not say the same thing:**

* ``rc 0`` -- the measurement was taken and published. **Including when nearly all targets declare
  nothing**: A2 says *"the list is published, never refused"*, and a registry that refused outright
  would block the entire repo on the day it was born. *No count is written here: the number moves
  with every target added, and a count locked in by hand silently goes stale.*
* ``rc 1`` -- the registry **lies to itself** (a target that does not exist, a level outside the
  scale, level 2/3 with no mechanism, a duplicate). This blocks no capability: it fixes a table.
* ``rc 2`` -- the measurement itself is **impossible** (unreadable file, no documented target). *Two
  absences of measurement must never compare equal to a green*: "nothing to declare" and "nothing
  could be read" are two opposite sentences.

**WHAT THIS COMMAND IS NOT, and it needs to be written down**: it is called by **no** gate at
all -- not ``pre-commit``, not ``pre-push``, not a hook. It is therefore itself **level 1**. *A
check that only prints is not a gate* -- saying so costs nothing, staying silent about it would
manufacture exactly the over-declaration A2 exists to fight.

**AND IT CANNOT DECLARE ITSELF IN ITS OWN REGISTRY**, as long as the ``make obligation`` target
does not exist in the ``Makefile`` (chat 3's batch, item F1): a line naming it would be a
``ghost`` and would produce ``rc 1``. One version of this docstring claimed *"its own registry
declares it"* -- that was false, found by the isolated audit, and the fix is not to write the line
but to say where it is waiting. The document itself has said so in prose from the start.

Usage::

    make obligation          # once the target lands in the Makefile (chat 3's batch / F1)
    PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.obligation_run   # everywhere, right now

Read-only, brick-free, model-free, network-free. French prose (D117).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from ..production.obligation import (
    DeclarationItem,
    lignes_illisibles,
    lire_le_registre,
    rendre,
    rendre_items,
    rendre_les_incoherences,
    verdict,
    verdict_items,
)

# BOTH ARE IMPORTED, NEVER RE-COPIED -- and this is not a stylistic preference. `cibles_documentees`
# IS the definition of "an offered capability" (a name at the start of a line, followed by a `##`),
# the SAME one `make help` and `make arsenal` already use: two definitions would give two
# populations, hence two truths about "how many targets declare nothing". And `_racine` carries the
# `CLAUDE_PROJECT_DIR` fix -- re-copying it would resurrect a defect that depends on the current
# working directory, the class of defect that NEVER turns red for its own author (measured: 7/11 for
# a third party, 0/11 here).
from ..production.plan_registry import read_plan_tree
from ..production.carte import replier
from .arsenal_run import _racine, cibles_documentees

#: The registry lives in governance, not in code: it is a document the project's owner reads and
#: fixes by hand, and the code is only its reader (D44 -- the `.md` is the arbiter of every
#: reconciliation).
REGISTRE = Path("docs") / "governance" / "OBLIGATION.md"

#: `G4` -- the level pattern, in a plan item's `*Obligation*` field. CALIBRATED on the REAL
#: population: the text writes `**niveau 2**` (sometimes followed by a parenthetical, e.g.
#: `**niveau 2 (barriere)**`), never a bare `**2**` -- a first, narrower pattern missed all 29
#: level-2 items entirely.
_NIVEAU_2_OU_PLUS = re.compile(r"\*\*niveau\s*[23]\b", re.IGNORECASE)

#: A code span carrying a `.py` filename -- full path or a BARE name. **`.py` IS MANDATORY, AND
#: THIS IS NOT A DECORATIVE PRECAUTION.** A first pass also resolved bare words against real files
#: (`STEMS`): `F1` cites `` `distillateur` / `juge` / `veilleur` `` (three SKILL names, an analogy)
#: and `juge.py` really does exist under `production/` -- the bare word would have resolved into a
#: false positive. *A text detector counts citations as instances.* Requiring `.py` removes this
#: case without missing a single one on the measured population.
_SPAN_PY = re.compile(r"`([^`\n]*?([\w.-]+)\.py)`")


def _module_produit(produit: str, stems_connus: frozenset[str]) -> tuple[str | None, str | None]:
    """``(module_resolu, module_non_construit)`` -- at most ONE of the two is non-`None`.

    **`(None, None)` IS THE MOST FREQUENT ANSWER, MEASURED: 25 level-2 items out of 29**
    describe a document, a field, a hook, or a container -- not a single Python module. Forcing a
    verdict here would manufacture an answer instead of naming a reading limit.

    **AUDIT DEFECT (D5b): `C5` NAMES `` `production/parc.py` `` UNAMBIGUOUSLY, AND THE FILE
    SIMPLY DOES NOT EXIST YET.** The old version returned `None` for this case EXACTLY as for an
    item that cites no `.py` at all -- the page then published "names no identifiable module", a
    FALSE sentence for an item that named its target in plain text. The first `.py` span cited,
    resolved or not, is therefore returned in the second element whenever it resolves to NO real
    file -- named, not conflated with the absence of a name."""
    premier_non_resolu = None
    for _span, stem in _SPAN_PY.findall(produit):
        if stem in stems_connus:
            return stem, None
        if premier_non_resolu is None:
            premier_non_resolu = stem
    return None, premier_non_resolu


def _modules_importes(n: ast.AST) -> frozenset[str]:
    """The modules (last segment) that AST node ``n`` imports, under EITHER form.

    **DEFECT FOUND BY THE ISOLATED AUDIT: THE FIRST VERSION ONLY SAW ONE FORM.**
    ``n.module.endswith(module)`` ONLY tests ``from ..production.X import Y`` -- never
    ``from ..production import X``, where ``n.module`` equals ``"production"`` and ``X`` only
    lives in ``n.names``. Measured against the real population: **5 modules with AT LEAST one real
    runtime/ caller returned 0** -- `lot_emit`, `livrables`, `perimetre`, `conseiller`, `intendant`.

    **THE LAST SEGMENT IS COMPARED FOR EQUALITY**, not with `endswith`: audited again, latent
    today (0 measured victim across 142 stems), but `endswith("format")` would also match
    `plan_format` -- a `format.py` module appearing next to `plan_format.py` would inflate one's
    count while looking for the other."""
    if isinstance(n, ast.ImportFrom):
        noms = {a.name for a in n.names}
        if n.module:
            noms.add(n.module.rsplit(".", 1)[-1])
        return frozenset(noms)
    if isinstance(n, ast.Import):
        return frozenset(a.name.rsplit(".", 1)[-1] for a in n.names)
    return frozenset()


def _importe(n: ast.AST, module: str) -> bool:
    """True if AST node ``n`` imports ``module`` -- defined on top of :func:`_modules_importes` so
    the direct probe and the transitive closure read EXACTLY the same import rule."""
    return module in _modules_importes(n)


def _modules_importes_fichier(chemin: Path) -> frozenset[str]:
    """All the modules a FILE imports, in a single AST walk -- :func:`_modules_importes` applied
    to every node of the tree rather than to just one, so each file is parsed only once even when
    :func:`compter_appelants_runtime` searches across dozens of targets."""
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return frozenset()
    noms: set[str] = set()
    for n in ast.walk(arbre):
        noms |= _modules_importes(n)
    return frozenset(noms)


def compter_appelants_runtime(module: str, racine: Path) -> int:
    """`G4`'s CALLER PROBE: how many files under `runtime/` REACH `module`, directly or through a
    `production/` -> `production/` -> ... -> `runtime/` chain.

    **SCOPED TO `runtime/` AS THE ONLY ENTRY POINT, AND THAT IS THE SAME DOCTRINE AS
    ELSEWHERE IN THIS REPO** (`production/` = pure, `runtime/` = the EDGE that wires a module to a
    real surface). A module that NOTHING -- neither directly nor through an internal `production/`
    chain -- connects to `runtime/` has, by construction, no live surface.

    By AST, never by `grep`: text can CITE a module's name without importing it (a docstring, a
    comment), and `grep` cannot tell the difference.

    **`no witnesses` by construction**: `runtime/` contains no tests at all -- excluding them
    from a scope that never visits them is not a filter, it is a consequence of the chosen
    perimeter.

    **FIXED (2026-08-15): THE DIRECT-ONLY VERSION PUBLISHED A FALSE POSITIVE ON A CLOSED
    ITEM.** `production/plan_ordre.py` (item `B1`, CLOSED) returned **0** -- "no caller" -- even
    though it is genuinely reached via `production/carte.py` -> `runtime/carte_run.py`. Found by
    the orchestrator by re-running the probe by hand (`carte.py:36`, a real import, not a
    citation): *"a named false positive is worth less than no probe at all -- a catch with no
    false-accusation rate is a wall, and a wall that wrongly accuses teaches people to ignore the
    alarm."* The probe now follows the `production/` -> `production/` graph from every `runtime/`
    entry point, until it reaches `module` or runs out (cycles are guarded with a `vus` set).

    **WHAT REMAINS A LIMIT, DECLARED, NOT FIXED BY THIS CHANGE**: it is still REACHABILITY BY
    IMPORT, never by CALL -- an imported module LOADS, it is not necessarily EXECUTED. The same
    reservation as everywhere else in this file: an `import` proves a surface, never a usage."""
    dossier_runtime = racine / "system" / "lib" / "mnemosyne" / "runtime"
    if not dossier_runtime.is_dir():
        return 0
    dossier_prod = racine / "system" / "lib" / "mnemosyne" / "production"
    fichiers_prod = tuple(dossier_prod.glob("*.py")) if dossier_prod.is_dir() else ()
    stems_prod = frozenset(f.stem for f in fichiers_prod)
    graphe_prod = {f.stem: _modules_importes_fichier(f) & stems_prod for f in fichiers_prod}

    def _atteint(depart: frozenset[str]) -> bool:
        """Is `module` reachable from `depart` by following `graphe_prod` (BFS/DFS, cycles guarded)?"""
        vus: set[str] = set()
        pile = list(depart)
        while pile:
            stem = pile.pop()
            if stem == module:
                return True
            if stem in vus:
                continue
            vus.add(stem)
            pile.extend(graphe_prod.get(stem, ()))
        return False

    compte = 0
    for f in sorted(dossier_runtime.glob("*.py")):
        entrees = _modules_importes_fichier(f)
        if module in entrees or _atteint(entrees):
            compte += 1
    return compte


def _items_obligation(racine: Path) -> tuple[DeclarationItem, ...] | None:
    """The population of plan items, with module and callers already MEASURED -- `None` if this
    repo's plan is unreadable (two absences never compare equal: see :func:`main`).

    **DEFECT FOUND WHILE FIXING D3, NOT BY THE AUDIT: `p.reading.items` IN THE FILTER CONFLATED
    "UNREADABLE GATE" AND "READABLE GATE, ZERO ITEMS".** A minimal test plan (one valid gate, no
    items) produced `lectures = []`, hence `return None` -- "unreadable plan" -- even though the
    gate had read without any problem. *Two absences of measurement compare equal*, exactly the
    fault this module refuses elsewhere. The filter therefore only keeps ``reading is not None``;
    :func:`replier` accepts a list of readings with ZERO items (checked), and returns an empty
    population, not an exception."""
    plans = read_plan_tree(racine / "docs", "Mnemosyne")
    lectures = [p.reading for p in plans if p.reading is not None]
    if not lectures:
        return None
    reading, _collisions = replier(lectures)
    stems = frozenset(
        f.stem
        for sous in ("production", "runtime")
        for f in (racine / "system" / "lib" / "mnemosyne" / sous).glob("*.py")
    )
    resultat = []
    for it in reading.items:
        obligation = it.field("obligation") or ""
        niveau2 = bool(_NIVEAU_2_OU_PLUS.search(obligation))
        module, module_non_construit = (
            _module_produit(it.field("produit") or "", stems) if niveau2 else (None, None)
        )
        appelants = compter_appelants_runtime(module, racine) if module else None
        resultat.append(
            DeclarationItem(
                ident=it.ident,
                niveau_2_ou_plus=niveau2,
                module=module,
                appelants=appelants,
                module_non_construit=module_non_construit,
            )
        )
    return tuple(resultat)


def _registre_make(racine: Path) -> int:
    """The `make <target>` registry -- code unchanged, only EXTRACTED from `main()`.

    **AUDIT DEFECT (D2): THE TWO SECTIONS WERE NOT "ALWAYS BOTH RUN".** The commit's docstring
    claimed *"one being unreadable must not silence the other"* -- false, measured in a clone:
    `mv Makefile Makefile.parked` made the ENTIRE `G4` section disappear, because this function's
    three `return 2`s, before extraction, cut off all of `main()`'s body that followed. *A sentence
    that asserts independence does not replace two separate functions.* Extraction is the fix:
    each section now has its OWN function, called UNCONDITIONALLY by `main()`, the same way
    `feuilles_executables.tout()` already does for a downstream project's own gate and its sabotage battery."""
    makefile = racine / "Makefile"
    try:
        texte_make = makefile.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"REFUSED: the Makefile is unreadable ({makefile}) — {exc}.", file=sys.stderr)
        print(
            "This is NOT \"no target without a level\": without the real population, the registry "
            "can assert nothing against nothing. Rerun from the root, or set CLAUDE_PROJECT_DIR.",
            file=sys.stderr,
        )
        return 2

    cibles = cibles_documentees(texte_make)
    if not cibles:
        print(f"REFUSED: no documented target (`## `) found in {makefile}.", file=sys.stderr)
        print(
            "An EMPTY population and an ENTIRELY DECLARED population would both return "
            "\"no target without a level\": we refuse rather than return that particular green.",
            file=sys.stderr,
        )
        return 2

    registre = racine / REGISTRE
    try:
        texte_registre = registre.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"REFUSED: the registry is unreadable ({registre}) — {exc}.", file=sys.stderr)
        print(
            "An absent registry is not an empty registry: it would return \"no target declares "
            "anything\", which would be true by accident and false by measurement.",
            file=sys.stderr,
        )
        return 2

    # The two readings of the SAME text: what we managed to read, and what we did NOT manage to
    # read but that looked like a declaration. The second is the silent-loss safety net (isolated
    # audit).
    r = verdict(cibles, lire_le_registre(texte_registre), lignes_illisibles(texte_registre))
    # The listing is ALWAYS printed, even when the registry is incoherent: it is a reading page
    # before it is a gate, and a duplicate must not deprive an agent of the scale.
    print(rendre(r, len(cibles)), end="")
    if r.coherent:
        return 0
    print("\nThe registry lies to itself — every cause is named:\n", file=sys.stderr)
    print(rendre_les_incoherences(r), file=sys.stderr)
    print(
        f"\nRemedy: fix the table in {REGISTRE} — it is the document that is authoritative, "
        "never this code.",
        file=sys.stderr,
    )
    return 1


def _registre_g4(racine: Path) -> int:
    """`G4` -- the second population (the plan items), ALWAYS called by `main()`.

    ``rc 0`` -- measurement taken and published, whatever its content (even 100% `sans_appelant`:
    **level 1, it publishes, it never refuses on CONTENT**). ``rc 2`` -- the measurement itself is
    IMPOSSIBLE (unreadable plan, or no item declares level >= 2 while the population is not empty).

    **AUDIT DEFECT (D3): A POPULATION JUDGED EMPTY WAS PUBLISHED AS A GREEN `0/0`.** If the
    `_NIVEAU_2_OU_PLUS` pattern stopped matching (a pattern regression, or a population read but
    entirely outside its perimeter), the output was `obligations_cablees=0/0`, `rc 0`, empty
    stderr -- indistinguishable from a genuinely healthy population. The SAME doctrine
    :func:`_registre_make` already applies to ``cibles`` ("an EMPTY population... we refuse rather
    than return that particular green") did not apply here. *Two absences of measurement must
    never compare equal to a green.*
    """
    try:
        items = _items_obligation(racine)
    except Exception as exc:  # noqa: BLE001 - G4 must never silence the `make` registry
        print(
            f"G4 not returned ({exc.__class__.__name__}) — the `make` registry itself stays complete.",
            file=sys.stderr,
        )
        return 2
    if items is None:
        print(
            "G4 NOT MEASURED: this repo's plan is unreadable from "
            f"{racine / 'docs'} — \"no level 2 item without a caller\" and \"I could not "
            "look\" are not the same sentence.",
            file=sys.stderr,
        )
        return 2
    r = verdict_items(items)
    if items and r.total_juge == 0:
        print(
            f"G4 REFUSED: {len(items)} plan item(s) read and NONE declares level >= 2 — "
            "the detection pattern has probably changed shape under it, not the repo's real "
            "population. \"no level 2\" and \"the detector sees nothing any more\" must never "
            "read the same.",
            file=sys.stderr,
        )
        return 2
    print(rendre_items(r), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Publish the scale, then `G4` -- ALWAYS both, never one short-circuiting the other.

    ``rc``: the WORST of the two sub-verdicts (`0` published - `1` `make` registry incoherent -
    `2` at least one of the two measurements is IMPOSSIBLE). *An `and` short-circuits and leaves
    the second measurement untaken* -- a lesson from a downstream project (`feuilles_executables.tout()`),
    re-measured here by an isolated audit after an earlier version claimed to hold it without
    actually holding it."""
    racine = _racine()
    code_make = _registre_make(racine)
    print()
    code_g4 = _registre_g4(racine)
    return max(code_make, code_g4)


if __name__ == "__main__":
    raise SystemExit(main())
