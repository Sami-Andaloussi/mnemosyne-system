"""RESUMING THE CURRENT PROJECT — what an agent needs to know about a BUBBLE, not about the system.

WHY THIS EXISTS, and it was measured on 2026-08-04, in this very repository.
The `SessionStart` hook already re-anchors an agent after a `/compact`: it pushes `make describe`,
`make tick`, git and the cap. **All of that is MNEMOSYNE — the system. None of it is the PROJECT
being built.** Measured consequence, same day: right after a compaction the hook fired correctly,
and the agent still had to read **108 000 lines of a project by hand** because nothing told it where
to look. The operator had to ask for it explicitly. *An agent reads what it is ORDERED to read.*

WHAT THIS MODULE PUSHES, and the split is the whole design:
 * the DERIVED state — the project's own reprise command, run fresh. It cannot be stale, because
 it is computed, never recopied. That is the half a hook can push honestly.
 * the ADDRESS of the handoff — never its content. *The address, never the copy* (D163): a prose
 handoff copied into every session pays its cost at EVERY session and rots between two.

 THE COMMAND IS DECLARED BY THE PROJECT, NEVER BY THIS FILE. It is read from the `reprise:` field
of the bubble's own `state/FIN-DE-SESSION.md`. Hardcoding one project's command here would make this
module a SECOND source of truth for something the bubble already owns — the exact fault the repo
keeps paying (`a second judge under the same name is the weaker of the two`).

 AND IT IS A CODE-EXECUTION PATH, so it is BOUNDED — a declared string is not a blank cheque:
 (a) the executable must be the repo's own interpreter, resolved here, never taken from the file;
 (b) the script must resolve INSIDE the bubble that declared it — no `..`, no absolute escape;
 (c) only plain `--flags` may follow; no shell, no pipes, no substitution (`shell=False`);
 (d) a timeout, and a bounded number of lines injected.
Each refusal is NAMED and printed. *A silent refusal reads as the absence of a problem.*

FAIL-OPEN by construction, like the hook that calls it: it never raises, it always exits 0. A
reprise that cannot run must never block a session.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
BULLES = RACINE / "projects"
HANDOFF = Path("state") / "FIN-DE-SESSION.md"

#: The interpreter is RESOLVED HERE, never read from the declaring file: that's clause (a) of the
#: boundary. A project declares WHAT to pull, never WITH WHAT.
INTERPRETEUR = RACINE / ".venv" / "bin" / "python"

#: Injection budget. This text is paid for at EVERY session: the derived state is useful, its tail isn't.
MAX_LIGNES = 24
TIMEOUT_S = 30

_FRONT = re.compile(r"\A---\n(.*?)\n---", re.S)
_REPRISE = re.compile(r"^reprise:\s*(?P<cmd>.+?)\s*$", re.M)
_FLAG = re.compile(r"\A--[a-z0-9][a-z0-9-]*\Z")


def _est_une_bulle(d: Path) -> bool:
    """ A SANDBOX IS NOT A BUBBLE, and this module's first run proved it.

 It found THREE candidates: the real project, and **two complete 146 MB copies**
 (`.arch-m10-sandbox*`, 12,000 files each, leftovers from an audit, not tracked by git). They
 carry the same `FIN-DE-SESSION.md` as the original — so **a single `touch` on a copy would
 have been enough to push a sandbox's state at every session**, indistinguishable from the
 real thing.
 Two bounds, and BOTH are needed: a hidden name (`.`) is not a project, and **a real bubble
 is TRACKED BY GIT** — the criterion that a rename cannot bypass.
 """
    if d.name.startswith("."):
        return False
    fini = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(HANDOFF)], cwd=d, capture_output=True, text=True
    )
    return fini.returncode == 0


def _dernier_commit(d: Path) -> int:
    """The timestamp of the bubble's last commit — ``0`` if git doesn't answer.

    ``0`` places the bubble LAST rather than first: *a bubble nobody can confirm is alive doesn't
    win the freshness contest.*"""
    try:
        fini = subprocess.run(
            ["git", "log", "-1", "--format=%ct"], cwd=d, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    try:
        return int(fini.stdout.strip()) if fini.returncode == 0 else 0
    except ValueError:
        return 0


def bulles() -> list[Path]:
    """The bubbles carrying an end-of-session handoff. Derived from disk, never a list.

 **THE RANKING FOLLOWS HISTORY, NOT THE FILE SYSTEM — DEFECT MEASURED ON 2026-09-08.**
 The sort used to run on the handoff's ``mtime``. But **a COPY refreshes an mtime without
 producing anything**, and `projects/` filled up with disposable audit clones and temp folders
 that all carry the same `FIN-DE-SESSION.md`, tracked by git INSIDE THEIR OWN CLONE — so
 indistinguishable to :func:`_est_une_bulle`, whose two bounds targeted copies with a HIDDEN
 name. Measured that day: **11 bubbles seen, the REAL project ranked LAST** (mtime 2026-08-09)
 behind a `tmpm6umirfm` (2026-09-03). This hook runs at the start of EVERY session: it was
 pushing a sandbox's state and ordering its handoff to be read instead. Sorting by the date of
 the last commit puts the real project back on top, because a disposable clone doesn't commit.

 **WHY NEITHER A NAME FILTER, NOR ONE ON THE SHAPE OF `.git`.** Measured: real bubbles have
 a `.git` FILE (a repo relocated out of iCloud, worktrees) and clones a `.git` FOLDER — a
 perfect discriminant *today*. That's exactly the trap paid for elsewhere the same day: *a
 bound that depends on today's content is not a guarantee*. A blacklist of prefixes (`tmp`,
 `audit-`) would age the same way. **Ranking by history excludes no one**: it orders, and a
 bubble that starts committing again climbs back up on its own.

 **RESIDUAL LIMIT, DECLARED RATHER THAN FILTERED**: on a tie in commit date, a worktree of
 the same project can pass ahead of its main repo (the ``mtime`` breaks the tie). It's the
 same project, so the damage is nil — but that's a consequence, not a choice, and I'd rather
 write it down than let it be mistaken for intentional."""
    if not BULLES.is_dir():
        return []
    trouvees = [p.parent.parent for p in BULLES.glob(f"*/*/{HANDOFF}")]
    return sorted(
        (d for d in trouvees if _est_une_bulle(d)),
        key=lambda d: (_dernier_commit(d), (d / HANDOFF).stat().st_mtime),
        reverse=True,
    )


def _commande_declaree(bulle: Path) -> tuple[list[str] | None, str]:
    """(safe argv, reason) — `None` if the project declares nothing or the boundary refuses.

 The boundary is here, and it's the only one: whatever comes out of this function gets executed.
 """
    texte = (bulle / HANDOFF).read_text(encoding="utf-8", errors="ignore")
    if not (m := _FRONT.search(texte)):
        return None, "the handoff has no front-matter — nothing is declared"
    if not (r := _REPRISE.search(m.group(1))):
        return None, (
            f"no `reprise:` field in {HANDOFF}'s front-matter — the project doesn't "
            f"declare how to PULL its state, so only its ADDRESS is pushed"
        )
    try:
        morceaux = shlex.split(r.group("cmd"))
    except ValueError as e:
        return None, f"`reprise:` unreadable ({e})"
    if not morceaux:
        return None, "`reprise:` is empty"

    script, *flags = morceaux
    cible = (bulle / script).resolve()
    if not str(cible).startswith(str(bulle.resolve()) + os.sep):
        return None, f"REFUSED [b] the declared script escapes the bubble: {script}"
    if not cible.is_file():
        return None, f"REFUSED [b] the declared script doesn't exist: {script}"
    if mauvais := [f for f in flags if not _FLAG.match(f)]:
        return None, f"REFUSED [c] only plain --flags are allowed after the script: {mauvais}"
    if not INTERPRETEUR.is_file():
        return None, f"REFUSED [a] the repo's interpreter cannot be found: {INTERPRETEUR}"
    return [str(INTERPRETEUR), str(cible), *flags], f"{script} {' '.join(flags)}".strip()



def phrase_peremption(jours: int | None, commits: int | None) -> str:
    """The PURE JUDGE of a declaration's freshness — it reads neither git nor disk.

 **WHY THIS MODULE NEEDED THIS, AND IT'S MEASURED.** `rendre` announces the state as
 "PULLED right now," and that's true: the DERIVED part cannot go stale. But the
 **declaration that says WHAT to pull** ages in silence. Measured on 2026-09-08: a sibling
 project's handoff carries `reprise: validation/plan/ligne.py --verifier`, written on **2026-08-09**;
 the project kept committing until **2026-09-04**, i.e. **25 days and 1,922 commits later**,
 and a project document written in between names ANOTHER measurement as the only one that
 says whether it's moving. Mnemosyne was therefore serving a FRESH derived state for a STALE
 command, and presenting it as reliable because it was computed. *A correct view of a stale
 source is an exact lie.*

 **NO THRESHOLD, AND THAT'S A CHOICE.** This module PUBLISHES the figure, it doesn't
 judge: *an invented ceiling here would turn a measurement into a verdict*, and nothing says
 a 30-day-old handoff on a paused project is worse than a 3-day-old one on a project that's
 on fire. The reader sees "25 days · 1,922 commits" and decides. Level 1, like the whole of
 this file.

 **IT DOES NOT STAY SILENT WHEN IT COULDN'T MEASURE** — "the handoff is fresh" and "I
 couldn't look" don't read the same.

 ``commits == 0`` is the only case where the line congratulates: the handoff is the bubble's
 last known gesture."""
    if jours is None or commits is None:
        return (
            "handoff freshness: NOT MEASURED (git is silent on this bubble) — \"up to date\" and "
            "\"I couldn't look\" don't read the same."
        )
    if commits == 0:
        return "handoff freshness: up to date — no commit from the bubble since it was written."
    j = "1 day" if jours == 1 else f"{jours} days"
    c = "1 commit" if commits == 1 else f"{commits} commits"
    return (
        f"\U000026A0\U0000FE0F handoff freshness: it hasn't moved in {j} and {c} from the bubble — the state above "
        f"is PULLED right now, but the COMMAND that pulls it is declared in that very handoff. "
        f"Check that it still measures what matters."
    )


def _mesure_peremption(bulle: Path) -> tuple[int | None, int | None]:
    """The EDGE for :func:`phrase_peremption` — it reads git, it doesn't judge.

    Returns ``(None, None)`` as soon as git doesn't answer: *a per-item guarantee that raises
    kills the batch*, and this batch is the session-start hook."""

    def _git(*args: str) -> str | None:
        try:
            fini = subprocess.run(
                ["git", *args], cwd=bulle, capture_output=True, text=True, timeout=TIMEOUT_S
            )
        except (OSError, subprocess.SubprocessError):
            return None
        sortie = fini.stdout.strip()
        return sortie if fini.returncode == 0 and sortie else None

    sha = _git("log", "-1", "--format=%H", "--", str(HANDOFF))
    if sha is None:
        return None, None
    t_bilan = _git("log", "-1", "--format=%ct", "--", str(HANDOFF))
    t_tete = _git("log", "-1", "--format=%ct")
    depuis = _git("rev-list", "--count", f"{sha}..HEAD")
    if t_bilan is None or t_tete is None or depuis is None:
        return None, None
    try:
        return max(0, (int(t_tete) - int(t_bilan)) // 86_400), int(depuis)
    except ValueError:
        return None, None


def rendre(bulle: Path, autres: list[Path]) -> None:
    rel = bulle.relative_to(RACINE)
    print(f"--- THE CURRENT PROJECT: {rel} ---")
    print(
        f"chosen because it's the bubble that COMMITTED most recently, out of {len(autres) + 1} "
        f"carrying a handoff"
        + (
            f" (the others: {', '.join(str(a.name) for a in autres)})"
            if autres
            else " (it's the only one)"
        )
    )

    argv, raison = _commande_declaree(bulle)
    if argv is None:
        print(f"DERIVED state: not pushed — {raison}")
    else:
        print(f"--- its state, PULLED right now ({raison}) ---")
        try:
            fini = subprocess.run(
                argv, cwd=bulle, capture_output=True, text=True, timeout=TIMEOUT_S
            )
            lignes = (fini.stdout or fini.stderr).strip().splitlines()
            for ligne in lignes[:MAX_LIGNES]:
                print(ligne)
            if len(lignes) > MAX_LIGNES:
                print(f"... ({len(lignes) - MAX_LIGNES} more lines — replay the command)")
            if fini.returncode != 0:
                print(
                    f"\U000026A0\U0000FE0F the state command returns {fini.returncode}: READ IT, it's a refusal, "
                    f"not a startup detail."
                )
        except subprocess.TimeoutExpired:
            print(f"(the state command exceeded {TIMEOUT_S}s — pull it yourself)")
        except OSError as e:
            print(f"(the state command couldn't run: {e})")

    print()
    # The FRESHNESS of the declaration travels WITH the derived state it commands.
    print(phrase_peremption(*_mesure_peremption(bulle)))
    print()
    print(f"\U000026D4 READ IT NOW, IN FULL: {rel / HANDOFF}")
    print("   This is the handoff written by the previous session — what's waiting for you, what")
    print("   moved, and the traps already paid for. This hook pushes the STATE (derived, so")
    print(
        "   fresh) and the ADDRESS of the prose; it never recopies the prose, which would be paid"
    )
    print("   for at every session and rot in between. *An agent reads what it is ORDERED to read.*")


def main() -> int:
    try:
        trouvees = bulles()
        if not trouvees:
            print("--- THE CURRENT PROJECT ---")
            print(
                f"no bubble under `projects/` carries {HANDOFF} — nothing to push. A project that "
                f"wants to be resumed after a compaction writes this handoff and declares `reprise:` in it."
            )
            return 0
        rendre(trouvees[0], trouvees[1:])
    except Exception as e:  # noqa: BLE001 — a hook NEVER breaks a session (fail-open)
        print(f"(project reprise unavailable: {type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
