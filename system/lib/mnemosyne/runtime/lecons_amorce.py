"""THE PRIMER — the hook that QUERIES the lessons on the agent's behalf (workstream 0, A1, 2nd half).

WHY THIS FILE EXISTS. `production/lecons.py` gave lessons a PULLED path. A lesson that is no
longer pushed only fires if someone goes looking for it — and an agent does not look for what it
does not know exists. This repo has already paid for this exact class of failure: the memory's git
repo (D173) was pulled only once, the day it was born. *A safety net that is never pulled looks
exactly like a safety net.* This module is the trigger; without it, A1 would have traded one wall
for a different kind of forgetting.

THE MEASUREMENT THAT DESTROYED THE RULE WRITTEN IN THE PLAN. The plan required injecting only on
a STRICT match (`mode="and"`: every word of the prompt inside the same fiche). Replayed on
**1,538 real operator prompts** (33 sessions, `system/state/sessions.db`), this predicate turns out
to be **INVERTED**:

    prompts of   1 term   -> fires on  92.9% of cases
    prompts of  2-3 terms ->            32.7%
    prompts of  4-8 terms ->            15.3%
    prompts of 9-20 terms ->             5.5%
    prompts of > 20 terms ->             0.0%   <-- the prompts that carry SUBSTANCE, never served

A conjunction over ALL words is trivial at one word and impossible at thirty: it fires exactly when
the prompt carries the LEAST information and stays silent when it carries the MOST. Worse, an
ordinary conversational verb acts as a hard filter: on *"can you commit"* the one fiche that
matters (`commit-continuously`) is EXCLUDED, and three unrelated fiches get through.

Three replacement predicates were measured on the same population, all rejected: anchoring on a
RARE term (df <= 5% of the corpus) fires on 89.5% of prompts; two co-occurring rare terms, 69.4%;
four, 43.2% — and across 290 fiches, rarity is not relevance: the anchors it picked were "etc,"
"see," "know," "big," "9b."

THE CONCLUSION IS THEREFORE AN ACKNOWLEDGED LIMIT, NOT A TUNING KNOB: on this corpus, no
word-based ranking decides RELEVANCE. This module therefore never claims otherwise — it returns
**candidates**, named as such, never a verdict. That is what makes a mediocre ranking harmless: the
agent reads and judges, instead of receiving two fiches presented as the truth.

THIS MODULE NEVER WRITES TO THE MEMORY FOLDER. It READS it (D74, inv. 2). Its only state lives
in `system/state/lecons-amorce.db`, derived and gitignored: deleting it loses nothing.

Code & docstrings in English (D117) except this preamble, which carries the decision.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from ..production.lecons import DEFAULT_INDEX_PATH, IndexDesLecons, Trouvaille
from ..production.sessions import query_terms
from .memoire import dossier_de_memoire

#: Same derived, gitignored home as the index it serves (`.gitignore:99`). Deleting it loses
#: nothing: at worst a session is offered a fiche it already saw.
AMORCE_DB_PATH = DEFAULT_INDEX_PATH.parent / "lecons-amorce.db"

#: MEASURED, NOT A TUNING KNOB. Below this many meaningful terms the prompt does not open work,
#: it continues it ("ok", "continue," "can you commit") — and those are exactly the prompts the
#: measured `and` predicate fired on 92.9% of the time. What breaks without it (D165): the trigger
#: inverts, spending its budget on the prompts that carry the least intent.
MIN_TERMES = 6

#: How many NEW fiches one firing may offer. Three fits on a screen; the agent opens what carries.
PAR_TIR = 3

#: THE PER-SESSION CEILING, AND IT IS NAMED BY ITS OWN MEASUREMENT (D165's test: *name what
#: breaks without it*). The set-difference rule alone does NOT bound the worst case: replayed over
#: the 33 real sessions, it injects a median of 5,070 bytes but **41,873 bytes on one session** —
#: MORE than the 41,059 bytes of pushed index it is supposed to replace, across 169 fiches and 96
#: firings. With this ceiling, the measured worst case drops to **2,783 bytes**. This is the only
#: form of ceiling A4 allows: a bound on what a model READS, never on what it WRITES.
PLAFOND_SESSION = 12

#: A description is one line by construction; this only guards a pathological frontmatter.
TITRE_MAX = 150

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vues (
    session TEXT NOT NULL,
    nom     TEXT NOT NULL,
    PRIMARY KEY (session, nom)
);
"""


def cle_de_session(payload: dict) -> str:
    """Which session this prompt belongs to — the key the per-session budget is counted against.

    Derived from ``transcript_path`` first because that field is the one `stop.sh` already relies
    on, so it is proven present on this host. An unknown session gets a stable constant rather than
    a random one: sharing one budget is a bounded loss, while a fresh key per prompt would silently
    disable both the cap and the de-duplication — the two guarantees that make this affordable.
    """
    chemin = payload.get("transcript_path") or ""
    if chemin:
        return Path(chemin).name
    return str(payload.get("session_id") or "session-inconnue")


class Amorce:
    """The per-session ledger of what has already been offered. Pure I/O over one SQLite file."""

    __slots__ = ("_db_path", "_conn")

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else AMORCE_DB_PATH
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._db_path)
            self._conn.executescript(_SCHEMA)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def deja_vues(self, session: str) -> set[str]:
        conn = self._connect()
        return {
            row[0] for row in conn.execute("SELECT nom FROM vues WHERE session = ?", (session,))
        }

    def note(self, session: str, noms: list[str]) -> None:
        conn = self._connect()
        conn.executemany(
            "INSERT OR IGNORE INTO vues (session, nom) VALUES (?, ?)",
            [(session, nom) for nom in noms],
        )
        conn.commit()


def choisir(index: IndexDesLecons, prompt: str, deja: set[str]) -> list[Trouvaille]:
    """The fiches this prompt earns — new ones only, within the session's remaining budget.

    SOLE OWNER OF ALL THREE PROMISES: the short-prompt silence, the no-repeat rule, and the
    per-session cap. They live in ONE function on purpose. The sabotage harness of 2026-08-09
    already caught the alternative on the sibling module: the bounded-read promise was held by two
    clauses, so removing one left the other holding it and **the witness stayed green**. *A
    guarantee held by two owners erodes silently.*
    """
    if len(query_terms(prompt)) < MIN_TERMES:
        return []
    budget = min(PAR_TIR, PLAFOND_SESSION - len(deja))
    if budget <= 0:
        return []
    # We ask for the BEST matches for THIS prompt, never "the best ones not yet seen." The
    # difference decides the behavior on a subject already served: here the top 3 are already
    # seen so the firing stays SILENT, whereas digging further down would return the 4th, the
    # 5th... spending the ceiling on progressively worse matches. Measured: digging further
    # saturated 23 of 33 sessions; not digging saturates 1.
    rappel = index.search(prompt, limit=PAR_TIR)
    neufs = [t for t in rappel.trouvailles if t.nom not in deja]
    return neufs[:budget]


def rendre(trouvailles: list[Trouvaille], *, compte: int, dossier: Path, premiere: bool) -> str:
    """What lands in the agent's context. Short by construction — this is PUSHED bytes.

    The wording never claims relevance, and that is the measurement talking, not modesty: no
    word-ranking over 290 fiches decides pertinence (see the module docstring). Announcing
    candidates keeps a mediocre ranking harmless; announcing findings would make it authoritative.
    """
    lignes = [
        f"[Mnemosyne · PULLED lessons] {len(trouvailles)} candidate(s) out of {compte} indexed "
        f"fiches — RANKED BY WORDS, this is NOT a verdict of relevance. Open the ones that carry "
        f"weight, ignore the rest. A lesson cited is not a lesson applied."
    ]
    for t in trouvailles:
        titre = (t.titre or "(no description)")[:TITRE_MAX]
        lignes.append(f"  - {t.nom} — {titre}")
    if premiere:
        lignes.append(
            f'  (they live in {dossier} · `make lecons Q="..."` to search for more)'
        )
        # Closes the 2026-08-02 field report: the END ritual exists (Stop hook), the START one
        # did not. Once per session only — repeated on every firing, this constant text would be
        # pure noise, and that is exactly the redundancy this workstream fights.
        lignes.append(
            "[START ritual — symmetric to the end ritual] 1. pull the workstream's state and "
            "READ it (`make plans` / `make tick`); 2. is what you are about to do at the top of "
            "that output — if not, say why; 3. is what you were about to ask the operator really "
            "theirs to answer (work that is mine to do · a derived step · a gesture only they can "
            "make)?"
        )
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - [OPERATOR] surface (host tree)
    """Read the hook payload on stdin, print at most a few lines, ALWAYS succeed.

    FAIL-OPEN IS THE POINT, NOT A COURTESY. This runs on every prompt the operator types: a
    trigger that can break a session is worse than zero lessons recalled. Every failure mode — no
    payload, bad JSON, missing memory folder, unreadable index — leaves the prompt untouched and
    returns 0.
    """
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        prompt = str(payload.get("prompt") or "")
        dossier = dossier_de_memoire()
        if not prompt.strip() or not dossier.is_dir():
            return 0

        session = cle_de_session(payload)
        amorce, index = Amorce(), IndexDesLecons(dossier)
        try:
            deja = amorce.deja_vues(session)
            index.refresh()
            trouvailles = choisir(index, prompt, deja)
            if trouvailles:
                print(
                    rendre(trouvailles, compte=index.compte(), dossier=dossier, premiere=not deja)
                )
                amorce.note(session, [t.nom for t in trouvailles])
        finally:
            index.close()
            amorce.close()
    except Exception:  # noqa: BLE001 - fail-open by design; see the docstring
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
