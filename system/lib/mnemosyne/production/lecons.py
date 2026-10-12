"""LESSONS, PULLED instead of PUSHED (workstream 0, A1).

THE MEASUREMENT THAT DECIDES THIS MODULE. On 2026-08-09: **290 memory fiches**, a main index
`MEMORY.md` at **24,324 bytes** against a built-in ceiling of **~24,400** (76 bytes of margin), and
an overflow channel `MEMORY-2.md` **born on 2026-08-06** that already weighed **16,735 bytes**
three days later -- roughly ~5.6 KB/day. **The overflow channel hits the same ceiling in turn,
within two days.** Total pushed into EVERY session, indexes alone: **41,059 bytes**. Fiche growth:
13 (June), 113 (July), 164 for the first nine days of August.

THE CAUSE IS A SHAPE, NOT A VOLUME. There are three natures of growth, and the repo used to
treat them all the same way:

  - PUSHED -- injected into every session, cost O(n) paid n times   -> `MEMORY.md`, `MEMORY-2.md`
  - PULLED -- read only when queried, cost O(1)                    -> `make search`, `make rappel`
  - DEAD   -- never re-read, paid for in illegibility               -> disorder

Lessons were the ONE thing built as PUSHED while the whole system's architecture runs on PULL. This
module gives them the pulled path: an FTS5 index over the fiches themselves, no model, no network,
no cost (`sqlite3` is in the standard library).

THIS MODULE NEVER DELETES, MERGES, OR REWRITES A SINGLE FICHE, AND THIS IS NOT A STYLE
PRECAUTION. `MEMORY.md` says so in its own header: *a reminder that a file is getting large is NOT
authorization to delete* -- erasing a memory is the operator's own gesture (D74, inv. 2). Four
compaction passes have already destroyed links there, one of which stayed invisible for several
sessions. This module never touches the CONTENT: it adds an ACCESS PATH. It does exactly one thing
to the memory folder -- it READS it.

AND A PULLED PATH WITHOUT A TRIGGER IS A REGRESSION, NOT PROGRESS. A lesson that is no longer
pushed only fires if someone goes looking for it, and an agent does not look for what it does not
know exists. This module is therefore HALF of A1; the other half is the hook that queries it ON THE
AGENT'S BEHALF. Written here so nobody reads this file as closing out the item.

Code & docstrings in English (D117); this preamble -- which carries the decision -- is translated
into English here too, for the public mirror.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .sessions import _REPO_ROOT, build_match_expression, query_terms

#: THE INDEX DOES NOT LIVE IN THE MEMORY FOLDER, AND THIS IS NOT A TIDINESS DETAIL.
#: Since D173 that folder is a GIT REPO (which is what makes a bad write recoverable): dropping a
#: binary `.sqlite3` file in it would make it show up as `??` on every `git status` of the memory
#: folder, and someday someone would commit it. Checked on 2026-08-09: `git check-ignore` on the
#: memory folder does NOT ignore it. So it lives under `system/state/`, where `*.db` is already
#: gitignored (`.gitignore:99`) and backed up (D110) — the same home as the conversation index.
#: And it is DERIVED: deleting it loses nothing, `refresh()` rebuilds it from the fiches.
DEFAULT_INDEX_PATH = _REPO_ROOT / "system" / "state" / "lecons.db"

#: The two index files are NOT fiches — they point AT them. Indexing them would make every query
#: match the index first, which is precisely the pushed artefact this module exists to bypass.
INDEX_FILENAMES = frozenset({"MEMORY.md", "MEMORY-2.md"})

#: Same tokenizer as the conversation index: `remove_diacritics 2` folds at tokenise time, which is
#: what makes `query_terms` (which folds the QUESTION) line up with what was indexed. Two different
#: foldings on the two sides is a silent no-match, and this repo has already paid that once.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS fiches (
    rowid    INTEGER PRIMARY KEY,
    nom      TEXT UNIQUE NOT NULL,
    titre    TEXT NOT NULL,
    mtime_ns INTEGER NOT NULL,
    taille   INTEGER NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS fiches_fts USING fts5(
    titre,
    corps,
    tokenize="unicode61 remove_diacritics 2"
);
"""

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_DESCRIPTION = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Trouvaille:
    """One matching fiche — its file, its one-line description, and where it matched."""

    nom: str
    titre: str
    extrait: str


@dataclass(frozen=True, slots=True)
class Rappel:
    """The result of one question. ``mode`` says WHICH pass answered — strict or loose.

    An empty ``trouvailles`` with ``mode='none'`` means the question carried no searchable word;
    with ``mode='and'`` it means the corpus genuinely holds nothing. The caller must be able to tell
    those apart — "I cannot search that" and "there is nothing" are different answers (inv. 14).
    """

    trouvailles: tuple[Trouvaille, ...]
    mode: str
    termes: tuple[str, ...]


def lire_titre(texte: str) -> str:
    """The fiche's one-line ``description:`` — the same sentence the pushed index carries.

    Returned empty when absent rather than guessed from the body: a description invented here would
    read exactly like one the operator wrote, and this repo's whole ethic is that a fabricated line
    is worse than a missing one.
    """
    entete = _FRONTMATTER.match(texte)
    if not entete:
        return ""
    trouve = _DESCRIPTION.search(entete.group(1))
    if not trouve:
        return ""
    return trouve.group(1).strip().strip('"').strip("'")


def lire_corps(texte: str) -> str:
    """Everything after the frontmatter. The frontmatter itself is indexed via ``titre`` only."""
    entete = _FRONTMATTER.match(texte)
    return texte[entete.end() :] if entete else texte


class IndexDesLecons:
    """The FTS5 index over the memory fiches — refresh it, then ask it questions.

    Pure I/O over one SQLite file, no brick. Constructed with explicit paths so a witness can drive
    it against a temp tree instead of the operator's real memory — a test that writes into the real
    memory folder is the exact accident inv. 2 exists to prevent.
    """

    __slots__ = ("_db_path", "_dossier", "_conn")

    def __init__(self, dossier: Path | str, *, db_path: Path | str | None = None) -> None:
        self._dossier = Path(dossier)
        self._db_path = Path(db_path) if db_path else DEFAULT_INDEX_PATH
        self._conn: sqlite3.Connection | None = None

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def dossier(self) -> Path:
        return self._dossier

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def fiches(self) -> list[Path]:
        """Every fiche on disk, index files excluded. An absent folder yields none, never raises."""
        if not self._dossier.is_dir():
            return []
        return sorted(
            p for p in self._dossier.glob("*.md") if p.name not in INDEX_FILENAMES and p.is_file()
        )

    def refresh(self) -> dict[str, int]:
        """Bring the index level with the disk. Incremental: only changed fiches are re-read.

        Returns what it DID (`ajoutees` / `majes` / `retirees` / `inchangees`), never a bare "ok" —
        a refresh that silently indexed nothing looks identical to one that indexed everything, and
        that is how an empty index passes for a full one.

        A fiche REMOVED from disk is removed from the index too. That is not a deletion of the
        operator's memory: the fiche is already gone: keeping its row would make the index answer
        with a file nobody can open — a hit that cannot be read is worse than no hit.
        """
        conn = self._connect()
        connues = {
            row["nom"]: (row["rowid"], row["mtime_ns"], row["taille"])
            for row in conn.execute("SELECT rowid, nom, mtime_ns, taille FROM fiches")
        }
        vues: set[str] = set()
        bilan = {"ajoutees": 0, "majes": 0, "retirees": 0, "inchangees": 0}

        for chemin in self.fiches():
            nom = chemin.name
            vues.add(nom)
            etat = chemin.stat()
            ancienne = connues.get(nom)
            if ancienne and ancienne[1] == etat.st_mtime_ns and ancienne[2] == etat.st_size:
                bilan["inchangees"] += 1
                continue
            try:
                texte = chemin.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # A fiche we cannot read is skipped, never guessed at — and it stays out of the
                # index rather than entering it empty, which would answer "found nothing inside".
                continue
            titre, corps = lire_titre(texte), lire_corps(texte)
            if ancienne:
                rowid = ancienne[0]
                conn.execute("DELETE FROM fiches_fts WHERE rowid = ?", (rowid,))
                conn.execute(
                    "UPDATE fiches SET titre = ?, mtime_ns = ?, taille = ? WHERE rowid = ?",
                    (titre, etat.st_mtime_ns, etat.st_size, rowid),
                )
                bilan["majes"] += 1
            else:
                cur = conn.execute(
                    "INSERT INTO fiches (nom, titre, mtime_ns, taille) VALUES (?, ?, ?, ?)",
                    (nom, titre, etat.st_mtime_ns, etat.st_size),
                )
                rowid = int(cur.lastrowid or 0)
                bilan["ajoutees"] += 1
            conn.execute(
                "INSERT INTO fiches_fts (rowid, titre, corps) VALUES (?, ?, ?)",
                (rowid, titre, corps),
            )

        for nom, (rowid, _, _) in connues.items():
            if nom not in vues:
                conn.execute("DELETE FROM fiches_fts WHERE rowid = ?", (rowid,))
                conn.execute("DELETE FROM fiches WHERE rowid = ?", (rowid,))
                bilan["retirees"] += 1

        conn.commit()
        return bilan

    def search(self, question: str, *, limit: int = 6) -> Rappel:
        """The fiches that match, best first. Two passes, strict then loose — same law as `rappel`.

        First every meaningful word must appear; only if that finds nothing does it retry on any one
        of them, ranked by ``bm25``. A loose pass run FIRST would bury an exact match under
        near-misses; a strict pass ALONE would answer "nothing" to questions the corpus can answer.

        THE BOUND ON ``limit`` IS NOT CLAMPED HERE, AND THAT IS MEASURED. This method used to
        carry ``limite = max(0, limit)`` as well as the guard in :meth:`_match`. The sabotage
        harness of 2026-08-09 removed this one and **the witness stayed GREEN** — the other clause
        held the property, so nothing reddened. Two owners for one guarantee means either can be
        deleted in silence. The guarantee now lives in ONE place, the last line before the SQL.
        """
        termes = tuple(query_terms(question))
        if not termes:
            return Rappel(trouvailles=(), mode="none", termes=())
        for mode in ("and", "or"):
            trouvailles = self._match(build_match_expression(question, mode=mode), limit)
            if trouvailles:
                return Rappel(trouvailles=tuple(trouvailles), mode=mode, termes=termes)
        return Rappel(trouvailles=(), mode="and", termes=termes)

    def _match(self, expression: str, limite: int) -> list[Trouvaille]:
        """Run one MATCH expression and pack the rows — the half both passes of `search` share.

        THE SOLE OWNER OF THE BOUNDED-READ PROMISE (inv. 16). A negative ``limite`` reaches
        SQLite as "no limit" and dumps the whole corpus — and it is reachable from the command line
        (``make lecons TOPK=-1``). This line is the last one before the query, so nothing can route
        around it; :meth:`search` deliberately no longer clamps, see its docstring.
        """
        if not expression or limite <= 0:
            return []
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT f.nom AS nom,
                   f.titre AS titre,
                   snippet(fiches_fts, 1, '«', '»', ' … ', 14) AS extrait
              FROM fiches_fts
              JOIN fiches AS f ON f.rowid = fiches_fts.rowid
             WHERE fiches_fts MATCH ?
             ORDER BY bm25(fiches_fts, 4.0, 1.0)
             LIMIT ?
            """,
            (expression, limite),
        ).fetchall()
        return [
            Trouvaille(
                nom=row["nom"],
                titre=row["titre"] or "",
                extrait=" ".join((row["extrait"] or "").split()),
            )
            for row in rows
        ]

    def compte(self) -> int:
        """How many fiches the index holds. Published by the surface so an EMPTY index can never
        pass for a library: *a refusal gets read, an emptiness gets believed.*"""
        conn = self._connect()
        row = conn.execute("SELECT COUNT(*) AS n FROM fiches").fetchone()
        return int(row["n"]) if row else 0
