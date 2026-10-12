"""The ``PreToolUse`` hook for the shell guard — the EDGE.

The judge (:mod:`mnemosyne.production.garde_shell`) is pure. Here we read the hook's JSON payload
on standard input, extract the command from it, and decide.

**THIS ONE ACTUALLY BITES — it is the only one in this repo that PREVENTS a gesture.** Two
consequences we own in writing:

* **``rc 2`` blocks the tool** and returns the reason to the model (``PreToolUse`` convention). All
  of Mnémosyne's other gates print; this one refuses.
* **EVERYTHING ELSE IS FAIL-OPEN, without exception.** Unreadable JSON, an unknown tool, a missing
  field, a bug in the judge: we return ``0`` and let it through. A guard that broke the ability to
  run commands would be pulled within the hour — and *a gate slower than the wall is never taken*.
  We would rather miss a bite than block an innocent command.

**It only protects sessions that load THIS `.claude/` folder.** A host without this setting
stays outside its perimeter. This is written here so no one reads its presence as a coverage it
does not give.

## I8 — the second judge is wired HERE, and this is the ONLY place that runs `git`

The judge (:func:`~mnemosyne.production.garde_shell.cibles_checkout_restore` /
:func:`~mnemosyne.production.garde_shell.contient_reset_hard`) is pure on TEXT. Knowing whether a
target is DIRTY requires `git status --porcelain` -- I/O, so it lives here, at the edge, like the
JSON read. :func:`_chemins_sales` is fail-open by construction (empty frozenset if `git` is
absent, the folder is not a repo, or the timeout expires): a path we cannot confirm DIRTY is never
treated as dirty.

**POST-AUDIT FIX (D75, a NO verdict from `I8`'s isolated audit)**: a first version compared the
command's RAW TOKEN against `git status --porcelain`'s paths by STRING EQUALITY. Four REAL forms,
measured and EXECUTED by the auditor in a disposable repo, got around this and genuinely
destroyed: an ABSOLUTE path (`git status --porcelain` ALWAYS returns paths relative to the repo's
ROOT, whatever the calling cwd -- verified empirically, never wrong twice the same way);
`git checkout -- .` (the whole dirty repo overwritten); a dirty DIRECTORY as the target; and the
hook's `cwd` in a subdirectory (the command's token is relative to THIS cwd, not the root). *The
gate was weaker than its written condition* -- this module now resolves EVERYTHING into one common
ABSOLUTE frame of reference before comparing, and treats a directory/`.` as a threat to its whole
subtree, not an exact-equality match.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from ..production.garde_shell import (
    backticks_substitues,
    cibles_checkout_restore,
    contient_reset_hard,
    refus,
    refus_ecrasement,
)

#: The tools whose argument goes to the shell. A tool outside this list is never judged — judging
#: text that will never reach the shell would manufacture refusals out of plain prose.
OUTILS_SHELL = frozenset({"Bash", "BashOutput"})


def _racine_depot() -> str | None:
    """The ABSOLUTE root (symlinks resolved) of the current repo, or `None` if unavailable.

    Fail-open like :func:`_chemins_sales`: outside a repo, `git` absent, timeout exceeded -> `None`,
    and the caller then treats NO path as dirty."""
    try:
        fait = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if fait.returncode != 0 or not fait.stdout.strip():
        return None
    return os.path.realpath(fait.stdout.strip())


def _chemins_sales(racine: str) -> frozenset[str]:
    """The ABSOLUTE paths (symlinks resolved) whose `git status --porcelain` WORKING-TREE column
    is neither blank nor `?` -- exactly what a `checkout --` / `restore` / `reset --hard` would
    overwrite.

    `git status --porcelain` ALWAYS returns paths relative to `racine`, whatever the calling cwd
    (verified empirically: identical whether launched from the root, a subdirectory, or with
    `-C`) -- they are resolved here to absolute so they compare in the SAME frame of reference as
    the command's targets, never guessed by string equality.

    EMPTY frozenset if unavailable: the EDGE fails open, never the judge -- a path we cannot
    confirm dirty is never treated as dirty."""
    try:
        fait = subprocess.run(
            ["git", "status", "--porcelain", "--no-renames"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if fait.returncode != 0:
        return frozenset()
    sales: set[str] = set()
    for ligne in fait.stdout.splitlines():
        if len(ligne) < 4:
            continue
        colonne_travail = ligne[1]
        if colonne_travail in (" ", "?"):
            continue
        chemin = ligne[3:].strip()
        if chemin.startswith('"') and chemin.endswith('"'):
            chemin = chemin[1:-1]
        if " -> " in chemin:  # porcelain rename form, out of caution despite --no-renames
            chemin = chemin.split(" -> ", 1)[1]
        sales.add(os.path.realpath(os.path.join(racine, chemin)))
    return frozenset(sales)


def _sous_ou_egal(chemin: str, cible: str) -> bool:
    """Is `chemin` (absolute) `cible` (absolute) itself, or strictly BELOW it?

    This is what makes a `.` target or a dirty DIRECTORY threaten its whole subtree, not just a
    file whose name would match word for word."""
    if chemin == cible:
        return True
    return chemin.startswith(cible.rstrip(os.sep) + os.sep)


def _ecrasements(commande: str) -> tuple[str, ...]:
    """The edge: cross-references the TEXTUAL (pure) targets with the REAL state of the repo (I/O),
    in one common ABSOLUTE frame of reference. () if nothing destructive is recognised in
    `commande`, or if the repo's root/state cannot be confirmed -- in all three cases, `git` is
    either not even launched for the first, or its result fails open for the other two.

    **TWO KNOWN RESERVATIONS, MEASURED BY THE SECOND ISOLATED AUDIT (D75), NEITHER FIXED NOR SILENT**:

    1. **`os.path.realpath` on the TARGETS can over-refuse a CLEAN symlink pointing at a dirty
       file** -- `git checkout -- link.py` only touches the symlink entry itself (independent of
       its target), but this module treats it as targeting its resolved destination. SAFE
       direction (a false refusal, never a loss), and measured: **0 symlinks tracked by git in
       this repo** at the time of the fix -- unreachable in practice today, not fixed so as not to
       reopen the class of bug (frame-of-reference confusion) this module has just closed.
    2. **Neither `~`, nor `$VAR`/`${VAR}`, nor `$( … )`, nor an earlier `cd` WITHIN THE SAME
       command are resolved** -- `cibles_checkout_restore` is a judge on TEXT alone (see its
       docstring). `git checkout -- ~/…/foo.py` on a dirty target, or
       `cd subdir && git checkout -- child.py`, remain UNRECOGNISED and DO destroy for real
       (executed and measured by the audit, both BEFORE and AFTER this fix -- not a regression of
       it). *Simulating shell expansion is a different, broader problem than resolving a path
       frame of reference* -- a follow-up item, not an extension of this one."""
    cibles = cibles_checkout_restore(commande)
    menace_totale = contient_reset_hard(commande)
    if not cibles and not menace_totale:
        return ()
    racine = _racine_depot()
    if racine is None:
        return ()
    sales = _chemins_sales(racine)
    if not sales:
        return ()
    cwd = os.getcwd()
    cibles_abs = tuple(os.path.realpath(os.path.join(cwd, c)) for c in cibles)
    ecrasees = set(sales) if menace_totale else set()
    ecrasees |= {s for s in sales if any(_sous_ou_egal(s, c) for c in cibles_abs)}
    return tuple(sorted(os.path.relpath(s, racine) for s in ecrasees))


def main() -> int:
    try:
        charge = json.load(sys.stdin)
        if charge.get("tool_name") not in OUTILS_SHELL:
            return 0
        commande = charge.get("tool_input", {}).get("command", "")
        if not isinstance(commande, str) or not commande:
            return 0
    except Exception:  # noqa: BLE001 - fail-open, deliberate: see the module docstring
        return 0

    try:
        morsures = backticks_substitues(commande)
    except Exception:  # noqa: BLE001
        morsures = ()
    if morsures:
        print(refus(morsures), file=sys.stderr)
        return 2

    try:
        ecrasees = _ecrasements(commande)
    except Exception:  # noqa: BLE001
        ecrasees = ()
    if ecrasees:
        print(refus_ecrasement(ecrasees), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
