"""E3 - WHAT WAS WRITTEN AND THAT NOBODY COMMITTED, named at the end of the task.

> *"Commit things, the changes. You're the first one responsible for having to commit when you
> do things."* - the operator.

**And it's stronger than what that quote says.** If N chats work in parallel on the same plan,
the shared state **must** be committed continuously, or **they can't see each other**: the commit
is not an end-of-day comfort, it is the **protocol** by which three sessions learn what the other
two did. With no continuous commit, there is no parallelism at all. A default already measured to
close this: ``plan/TABLEAU.md`` committed **32 h stale**.

## This module is a PURE JUDGE - it talks to no git at all

Its population is **INJECTED**: the edge (:mod:`.claude/hooks/stop.sh`) runs the ``git status``
calls and hands it what they said. *A judge that fetches its own population can find it empty
and return a green* - and here green would mean "everything is committed," the exact false
sentence an absent ``git`` would produce all by itself.

## PARKED PATHS ARE NEVER PROPOSED - and the trap is MEASURED

``CLAUDE.md`` forbids committing five things. Three are **gitignored**, so ``git status`` already
does not show them (``scripts/perso/``, ``system/state/*.jsonl``): they risk nothing, and
believing the rule protects **them** is the mistake. **The two that matter are TRACKED BY
GIT** - ``system/config/domains.toml`` and ``system/config/policy.toml``: their local
modifications **do appear** in ``git status`` (verified on 2026-08-14: no ``skip-worktree`` on
this clone, ``git ls-files -v`` returns no lowercase line), and a naive gesture would propose
them.

So the rule closes the **CLASS**, not the case: **all** of ``system/config/`` is parked, not
just the two known files. A third config file added tomorrow is protected without anyone having
to think about it. *Closing the case leaves the class open.*

Decisions: E3 (commit as protocol) · D82 (the journal stays local) · inv. 2 (non-destructive)
· D117 (this repo's own convention keeps the operator output French - this public-mirror copy is
translated into English throughout). Pure stdlib.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

#: The PARKED prefixes, as classes and never as named files. A path starting with one of
#: them is **never** proposed for commit, whatever its git state.
#:
#: ``system/config/`` is one of `CLAUDE.md`'s THREE WALLS (money · ``system/config/`` · the
#: operator's data): changing it requires a word typed LIVE on ``/dev/tty``, which no agent can
#: type. Proposing it for commit would be proposing to cross a wall.
#:
#: **``system/state/`` WAS REMOVED FROM THIS LIST BY AN AUDIT, and the reasoning matters more
#: than the case.** ``CLAUDE.md`` parks ``system/state/*.jsonl`` - files that are **gitignored**,
#: so they NEVER appear in a ``git status --porcelain``. Parking them here buys nothing and
#: costs a lot: the prefix was swallowing their **GIT-TRACKED** neighbours
#: (``system/state/README.md``, ``system/state/.gitkeep``), which no doctrine parks. Measured:
#: ``git check-ignore -v system/state/README.md`` -> **no rule**, and a file written there
#: was **not named** at the end of the task - E3's clause 1 failing on a real class.
#: *A class closed too wide does not protect better: it silently swallows innocents.*
#: ``scripts/perso/`` stays, though, because the WHOLE folder is parked by doctrine and
#: **nothing in it is tracked** - it has no neighbour to swallow.
PARQUES: Final = (
    "system/config/",
    "scripts/perso/",
)

#: How many OTHER PEOPLE's files the block cites before saying "and N more."
#:
#: **NEVER BOUND ``a_moi``**, and that is the whole rule: what THE TASK wrote and did not
#: commit is precisely what gets lost - it is never truncated, no exceptions. What gets bounded
#: is what belongs to SOMEONE ELSE: the reader has nothing to do with it beyond knowing it
#: exists.
#:
#: **Born of real use, measured 2026-08-15**: a ``ruff format`` run across the whole repo left
#: **125 modified files** (identical AST on 125/125 - zero change in meaning), and the block
#: started rendering **127 lines at the end of every task, for all three chats**. *A check that
#: stays silent is worse than one that talks too much - but a wall of 127 names IS how you learn
#: to ignore a block.* The cut always SAYS what it leaves out, and names the command that shows
#: the rest.
AUTRES_CITES: Final = 8


@dataclass(frozen=True, slots=True)
class Depot:
    """A repo and what its ``git status --porcelain`` said. ``etiquette`` is what the operator reads."""

    etiquette: str
    chemins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Attente:
    """What a repo still owes: what gets committed, and what was SET ASIDE because it is parked.

    ``a_moi`` / ``aux_autres`` is amendment **OBS-6**, born from three-chat use: the block used
    to name five files, **none** of which belonged to the task that triggered it. With a single
    chat it is a useful reminder; with three, everyone sees themselves accused of the others'
    work - and *the first time someone answers "that's not mine" is the first time they learn to
    ignore the block*.
    **This is NOT a filter that hides**: both lists are printed. A file forgotten by
    EVERYONE must stay visible - *a check that stays silent is worse than one that talks too
    much*.
    """

    etiquette: str
    a_committer: tuple[str, ...]
    parques: tuple[str, ...]
    a_moi: tuple[str, ...] = ()
    aux_autres: tuple[str, ...] = ()


def _chemin(ligne: str) -> str:
    """The path from a ``git status --porcelain`` line - two status columns, a space, the rest.

    ``R  old -> new`` returns the **new** one: it is the one that exists after the commit, so
    the only one that can be proposed for adding. A line that is too short returns an empty
    string, never an exception: a ``git`` that stutters must not silence the whole reminder.
    """
    reste = ligne[3:].strip() if len(ligne) > 3 else ""
    if " -> " in reste:
        reste = reste.split(" -> ", 1)[1]
    return reste.strip('"')


def est_parque(chemin: str) -> bool:
    """True if this path belongs to a class that NEVER gets committed."""
    return any(chemin.startswith(prefixe) for prefixe in PARQUES)


def lire(etiquette: str, porcelain: str) -> Depot:
    """A raw ``git status --porcelain`` output -> the paths it names. Pure function."""
    return Depot(
        etiquette=etiquette,
        chemins=tuple(
            chemin
            for chemin in (_chemin(ligne) for ligne in porcelain.splitlines() if ligne.strip())
            if chemin
        ),
    )


def attentes(depots: Iterable[Depot], ecrits: Iterable[str] = ()) -> tuple[Attente, ...]:
    """What each repo owes - parked paths SET ASIDE, never silently dropped.

    A repo that owes nothing **disappears** from the result: the reminder must stay silent when
    it has nothing to say (*a detector that always talks says nothing*). A repo where
    EVERYTHING is parked also disappears - it owes nothing committable, and announcing "2 parked
    files" with nothing to do would be noise that teaches people to ignore the block.
    """
    mien = frozenset(ecrits)
    rendu = []
    for depot in depots:
        a_committer = tuple(c for c in depot.chemins if not est_parque(c))
        if not a_committer:
            continue
        rendu.append(
            Attente(
                etiquette=depot.etiquette,
                a_committer=a_committer,
                parques=tuple(c for c in depot.chemins if est_parque(c)),
                a_moi=tuple(c for c in a_committer if c in mien),
                aux_autres=tuple(c for c in a_committer if c not in mien),
            )
        )
    return tuple(rendu)


def rendre(attentes_: Sequence[Attente]) -> str:
    """The block the hook injects. EMPTY string when everything is committed - silence is a
    result.

    Paths are NAMED, one by one: *"there are still things to commit"* is exactly the
    generic reminder that gets skipped. A name can be checked, an exhortation gets worked
    around.
    """
    if not attentes_:
        return ""
    lignes = [
        "[Mnemosyne · E3 — the commit is the PROTOCOL, not a comfort] This task wrote "
        "files that NOTHING has committed. If other chats are working the same plan, they cannot "
        "see them:",
        "",
    ]
    for a in attentes_:
        lignes.append(f"  \U000025B8 {a.etiquette} — {len(a.a_committer)} file(s) pending:")
        # The SEPARATION, never the masking (OBS-6). When it is not known who wrote what (no
        # write information was injected), we fall back to the single list - saying "to
        # others" without knowing would be worse than not sorting at all.
        if a.a_moi or a.aux_autres:
            if a.a_moi:
                lignes.append("      — WRITTEN BY THIS TASK:")
                lignes.extend(f"          {chemin}" for chemin in a.a_moi)
            if a.aux_autres:
                lignes.append(
                    "      — already there BEFORE your turn (another chat, or an older oversight) "
                    "— NOT to be committed in their place, but not to be ignored either:"
                )
                lignes.extend(f"          {chemin}" for chemin in a.aux_autres[:AUTRES_CITES])
                reste = len(a.aux_autres) - AUTRES_CITES
                if reste > 0:
                    lignes.append(
                        f"          …and {reste} more — `git status --porcelain` lists them all."
                    )
        else:
            lignes.extend(f"      {chemin}" for chemin in a.a_committer)
        if a.parques:
            lignes.append(
                f"      \U000026D4 {len(a.parques)} PARKED path(s) set aside — they are NEVER committed "
                f"({', '.join(PARQUES)})."
            )
        lignes.append("")
    lignes.append(
        "The gesture: a NAMED `git add` (never `git add -A`), an ASCII message with no accents "
        "ending with the `Co-Authored-By` of the model that actually produced it, and the "
        "pre-commit barrier stays the judge. `index.lock` refuses? wait a few seconds and try "
        "again — never force, never delete a `.lock`."
    )
    lignes.append(
        "If a file must NOT be committed, say so in one line and finish — a red fragment "
        "deliberately left out is a valid answer, forgetting it is not."
    )
    return "\n".join(lignes)
