"""SessionIndex (D155) — full-text recall over Mnémosyne's OWN past conversations.

Ported in DESIGN (not in code) from ``NousResearch/hermes-agent`` ``tools/session_search_tool.py``
(MIT © 2025 Nous Research, SHA ``3ef6bbd``), the organ their README calls "searches its own past
conversations". Their file is welded to a bespoke SQLite state layer, so nothing is copied: what
crosses is the SHAPE — one index, three calling modes, and **zero LLM anywhere**. A recall that
needed a model would be neither free nor instant, and it would put the operator's words in front of one.

The hole it closes, measured on this machine (2026-07-20): this repo's transcript directory holds
**47 conversations, 643 MB** — and NOTHING read them. Every session started blind to every previous
one, so what we said only survived if a frontier had hand-copied it into memory. This is the
cheapest large capability in the whole audit: ``sqlite3`` ships with Python, FTS5 is compiled in
(verified 3.51.2), and a query costs a disk seek.

The same directory also holds ``<session-id>/subagents/`` subtrees — **560 more transcripts,
193 MB**, measured — and
:meth:`SessionIndex.transcripts` deliberately does NOT recurse into it. A delegated sub-agent is a
bounded errand whose CONCLUSION already came back into the conversation; indexing its internal
monologue would drown 47 real conversations under 557 errands (Hermes hides the same two session
sources, ``subagent`` and ``tool``, for the same reason).

Four properties are structural, not optional:

* **PULLED, never PUSHED.** Nothing here injects anything into a fresh session. ``CLAUDE.md`` is
  right that a past session's *progress* is noise to inherit — that rule targets what is pushed at
  you at startup. An index is the opposite gesture: it answers a question you asked. So this module
  exposes ``search`` / ``window`` / ``recent`` and NO startup hook, deliberately.
* **What was SAID, not what was READ.** Only ``text`` blocks of user / assistant messages are
  indexed; tool calls and tool results are dropped. That is where the 837 MB lives (file dumps,
  command output) and it is not conversation — indexing it would bury "what did we decide about
  the library?" under every file I ever cat-ed. The index is a fraction of the corpus by design.
* **Cloisonné by project (invariant 3).** One transcript directory = one bubble. The default scope
  is THIS repo's directory; a session about another project is not silently in scope.
* **Read-only and local.** The indexer never writes to the transcripts, never touches the network,
  and the database lands under ``system/state/`` — gitignored by the D82 barrier, like every other
  file holding the operator's real words, and covered by the encrypted backup.

**Boundary, stated rather than hidden.** ``CLAUDE.md`` says "stay under ``~/mnemosyne``". This
module READS one directory outside it — ``~/.claude/projects`` — because that is where the host
writes the transcripts of this very repo; there is no in-repo copy to read instead. It writes
nothing there, and the root is a constructor argument so a test never touches the real one. The
derived index stays inside the repo. That asymmetry (read out, write in) is the whole exemption.

**Not wired as an agent tool, deliberately.** This is a CLI surface for the operator and for a
frontier that runs ``make``. Exposing it to the agent loop would require a manifest sanctioned in
``tools.toml`` (D114-⑤) exactly like ``search_memory`` — a privileged human act, not an import.

Decisions: D155 (this) · D82 (the operator's real words live under ``system/state``, gitignored) · D117
(code English) · invariant 3 (cloisonnement). Pure stdlib — no brick (D126).
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

#: Repo root from here (``system/lib/mnemosyne/production/sessions.py`` → parents[4]).
_REPO_ROOT: Final = Path(__file__).resolve().parents[4]

#: The derived index. Under ``system/state`` ⇒ gitignored (D82) and backed up (D110).
DEFAULT_INDEX_PATH: Final = _REPO_ROOT / "system" / "state" / "sessions.db"

#: Where the host writes transcripts. Outside the repo — see the boundary note in the module
#: docstring. Read-only, and injectable so the suite never reads the real one.
DEFAULT_TRANSCRIPT_ROOT: Final = Path.home() / ".claude" / "projects"

#: Injected blocks that appear INSIDE a user message but were never typed by the operator: hook output,
#: recalled memories, local command echoes, and — by far the most common — the host's report that a
#: delegated sub-agent finished (**783 of them in 20 transcripts**, measured). They ride in a
#: ``type: "user"`` event, so nothing but the tag distinguishes them from the operator speaking: left in,
#: they made the signal detector fire on the system congratulating itself. Non-greedy, DOTALL.
_INJECTED_RE: Final = re.compile(
    r"<(task-notification|system-reminder|local-command-[a-z]+|command-(?:name|message|args)"
    r"|recalled)\b.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

#: A LONE scaffolding tag — an opener with no closer, a stray closer, a nested repeat. Neutralised
#: by replacing the tag itself with a space.
#:
#: It used to delete from the marker to the END of the message, and the audit measured what that
#: costs: a message that merely MENTIONS ``<system-reminder>`` lost everything after it — 155 of 185
#: characters in one probe, silently and unboundedly. In a repo whose subject IS hooks and recall,
#: that is a self-inflicted wound that grows with every session about this code. A truncated
#: injection is rare (one message in 25 331 on the real corpus) and its leaked head is the host
#: reporting on itself; unbounded prose loss is the worse failure, so only the tag literal goes.
#: Same lesson as ``guard/fencing.py``: neutralise the marker, never eat the payload.
_INJECTED_OPEN_RE: Final = re.compile(
    r"</?(task-notification|system-reminder|local-command-[a-z0-9]+|command-(?:name|message|args)"
    r"|recalled|task-id|tool-use-id|output-file|summary|status|note|result|usage)\b[^>]*>",
    re.IGNORECASE,
)

#: FTS5 gives every bareword operator meaning (``AND``, ``*``, ``:``, ``"``). The user types French
#: prose, not query syntax, so each run of word characters becomes ONE quoted term — a query can
#: never be a syntax error, and never an injection into the match expression.
_WORD_RE: Final = re.compile(r"\w+", re.UNICODE)

#: Below this, a "word" is punctuation noise that would only widen the match.
_MIN_TERM_LEN: Final = 2

#: French / English function words, dropped before matching. FTS5's implicit operator is AND, so
#: one "des" in a question means every hit must ALSO contain "des" — measured: the natural query
#: "classification des livres publique ou perso" returned ZERO passages until these came out.
#: Deliberately short: it removes words that carry no topic, never words that carry meaning.
_STOPWORDS: Final = frozenset(
    """
    a ai au aux avec ce ces dans de des du elle en est et eu il je la le les leur lui ma mais me
    meme mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se ses son sur ta te tes
    toi ton tu un une vos votre vous y c d j l m n s t qu est ete etre fait faire cela ca ceci
    the of to in is it and or for with that this was were are be been on at as by an from
    """.split()
)

_SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS files (
    path       TEXT PRIMARY KEY,
    size       INTEGER NOT NULL,
    mtime      INTEGER NOT NULL,
    session_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    project    TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    first_ts   TEXT NOT NULL DEFAULT '',
    last_ts    TEXT NOT NULL DEFAULT '',
    n_messages INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY,
    path       TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL,
    uuid       TEXT NOT NULL DEFAULT '',
    role       TEXT NOT NULL,
    ts         TEXT NOT NULL DEFAULT '',
    seq        INTEGER NOT NULL,
    text       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_by_session ON messages (session_id, seq);
CREATE INDEX IF NOT EXISTS messages_by_path ON messages (path);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text,
    content='messages',
    content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);
"""


@dataclass(frozen=True, slots=True)
class Hit:
    """One search result — the session it belongs to, and where inside it."""

    session_id: str
    project: str
    title: str
    role: str
    ts: str
    seq: int
    uuid: str
    snippet: str
    text: str


@dataclass(frozen=True, slots=True)
class Recall:
    """The answer to one question, and HOW it was answered.

    ``mode`` is reported rather than hidden because the two are not equally trustworthy: ``"and"``
    means every passage contains every meaningful word; ``"or"`` means nothing did, so these are
    merely the closest. Presenting a loose match as an exact one is how a recall tool starts lying
    quietly, and the caller can only warn the operator if it is told.
    """

    hits: tuple[Hit, ...]
    mode: str
    terms: tuple[str, ...]

    def __bool__(self) -> bool:
        return bool(self.hits)

    def __len__(self) -> int:
        return len(self.hits)

    def __iter__(self) -> Iterator[Hit]:
        return iter(self.hits)


@dataclass(frozen=True, slots=True)
class SessionRow:
    """One indexed conversation, for the browse mode."""

    session_id: str
    project: str
    title: str
    first_ts: str
    last_ts: str
    n_messages: int


def _message_text(message: Any) -> str:
    """Extract the spoken text of one transcript message — text blocks only.

    A ``content`` is either a plain string or a list of blocks. Only ``text`` blocks are kept:
    ``tool_use`` / ``tool_result`` / ``thinking`` / ``image`` are what makes the corpus 837 MB and
    they are not conversation. Returns ``""`` when nothing was actually said.
    """
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return _strip_injected(content)
    if not isinstance(content, list):
        return ""
    parts = [
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]
    return _strip_injected("\n".join(parts))


def _strip_injected(text: str) -> str:
    """Remove blocks that the host injected into a message rather than a human typing them."""
    cleaned = _INJECTED_RE.sub(" ", text)
    cleaned = _INJECTED_OPEN_RE.sub(" ", cleaned)
    return cleaned.strip()


def _is_conversation(event: dict[str, Any]) -> bool:
    """True for an event that carries something a human or the agent actually said.

    Excluded, each for its own reason: a **sidechain** turn belongs to a delegated sub-agent, not to
    the conversation with the operator; a **meta** event is hook scaffolding; a **compact summary** is a
    reconstruction of messages already indexed, so keeping it would double-count the same words.
    """
    if event.get("type") not in ("user", "assistant"):
        return False
    return not (event.get("isSidechain") or event.get("isMeta") or event.get("isCompactSummary"))


def read_transcript(path: Path) -> tuple[str, str, list[tuple[str, str, str, str]]]:
    """Parse one ``.jsonl`` transcript → ``(session_id, title, [(uuid, role, ts, text), …])``.

    Tolerant by construction: a transcript is appended to while a session runs, so the last line
    can be torn. A line that will not parse is SKIPPED — a half-written tail must never cost the
    whole file (fail-open on the read side, like every replay in this package).

    **Deduplicated by uuid**, and that is not defensive coding: the host really does re-append a
    message it already wrote (measured — one message present FOUR times under a single uuid in a
    7 877-line transcript, presumably on resume / branch). Without this, one answer crowds out three
    others in every result list. The uuid is the host's own identity for a message, so it is the
    right key; the FIRST occurrence wins and an event with no uuid is never deduplicated.
    """
    session_id, title, rows = "", "", []
    seen_uuids: set[str] = set()
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return "", "", []
    with handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            session_id = session_id or str(event.get("sessionId") or "")
            kind = event.get("type")
            # A session carries both a human-set and a generated title; the human one wins.
            if kind == "custom-title" and event.get("customTitle"):
                title = str(event["customTitle"])
            elif kind == "ai-title" and not title and event.get("aiTitle"):
                title = str(event["aiTitle"])
            if not _is_conversation(event):
                continue
            uuid = str(event.get("uuid") or "")
            if uuid:
                if uuid in seen_uuids:
                    continue
                seen_uuids.add(uuid)
            text = _message_text(event.get("message"))
            if not text:
                continue
            rows.append(
                (
                    str(event.get("uuid") or ""),
                    str((event.get("message") or {}).get("role") or event.get("type") or ""),
                    str(event.get("timestamp") or ""),
                    text,
                )
            )
    return session_id, title, rows


def default_project_dir(root: Path = DEFAULT_TRANSCRIPT_ROOT, repo: Path = _REPO_ROOT) -> str:
    """The transcript directory name the host derives for ``repo`` (its path, slashes → dashes).

    Returned as a NAME, not a path, so it can be compared to what is on disk without assuming the
    directory exists (a repo whose sessions were never recorded simply has no directory).
    """
    del root  # kept in the signature: the caller reads "the directory under this root"
    return str(repo).replace("/", "-")


def _fold(term: str) -> str:
    """Lowercase and strip accents — the same folding ``remove_diacritics 2`` applies at index time.

    Without it the stopword set would have to list every accented spelling, and ``"même"`` typed by
    the operator would not be recognised as the function word ``meme``.
    """
    decomposed = unicodedata.normalize("NFD", term.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def query_terms(query: str) -> list[str]:
    """The meaningful words of a question, folded, in order, deduplicated.

    A question made only of function words ("on y va") yields NO terms, and the caller abstains.
    The tempting fallback — match on the stopwords themselves — was tried and removed: it turns a
    non-question into a page of every message containing "le", which is worse than a clean "je ne
    trouve pas" because it looks like an answer.

    **The whole query is folded BEFORE it is split into words**, and the order matters more than it
    looks: macOS hands out decomposed text (NFD), where the accent of ``dépôt`` is its own character
    — so splitting first cut the word into ``de`` / ``po`` / ``t`` and searched for the fragment
    ``po``. The operator would have been told "aucun passage ne contient tous les mots (po)". The index side
    was never affected (SQLite's ``remove_diacritics 2`` folds at tokenise time); it was purely the
    question that arrived mangled.
    """
    words = [word for word in _WORD_RE.findall(_fold(query)) if len(word) >= _MIN_TERM_LEN]
    seen: dict[str, None] = {}
    for word in words:
        if word not in _STOPWORDS:
            seen.setdefault(word, None)
    return list(seen)


def build_match_expression(query: str, *, mode: str = "and") -> str:
    """Turn free French prose into a safe FTS5 MATCH expression of quoted terms.

    Every term is quoted, so ``NEAR``, ``OR``, ``*`` and a stray quote are matched as words instead
    of steering the query — a question can never be a syntax error, and never an injection into the
    match expression. ``mode="and"`` demands every term (precise); ``mode="or"`` demands one and
    lets ``bm25`` rank (the fallback when nothing contains them all). Returns ``""`` when nothing
    usable remains: the caller must then return no hits rather than run an empty match, which FTS5
    rejects outright.
    """
    terms = query_terms(query)
    if not terms:
        return ""
    joiner = " OR " if mode == "or" else " "
    return joiner.join(f'"{term}"' for term in terms)


class SessionIndex:
    """The FTS5 index over past conversations — build it, then ask it questions.

    Pure I/O over one SQLite file (no brick, D126). Constructed with explicit paths so the suite
    drives it against a temp tree instead of the real transcripts.
    """

    __slots__ = ("_db_path", "_root", "_conn")

    def __init__(
        self,
        db_path: Path | str = DEFAULT_INDEX_PATH,
        *,
        transcript_root: Path | str = DEFAULT_TRANSCRIPT_ROOT,
    ) -> None:
        self._db_path = Path(db_path)
        self._root = Path(transcript_root)
        self._conn: sqlite3.Connection | None = None

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def transcript_root(self) -> Path:
        return self._root

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

    # --- building -------------------------------------------------------------------------
    def transcripts(self, project: str | None = None) -> list[Path]:
        """Every transcript in scope, newest first. ``project=None`` means every project.

        Non-recursive on purpose (``glob``, never ``rglob``): the host nests delegated sub-agent
        runs under ``<project>/subagents/``, and those are errands, not conversations — see the
        module docstring. On this machine that is the difference between 47 files and 604.
        """
        if not self._root.is_dir():
            return []
        dirs = (
            [self._root / project]
            if project
            else sorted(child for child in self._root.iterdir() if child.is_dir())
        )
        found: list[tuple[int, Path]] = []
        for directory in dirs:
            if not directory.is_dir():
                continue
            for path in directory.glob("*.jsonl"):
                try:
                    # stat() INSIDE the loop, not in the sort key: a broken symlink or a file that
                    # vanishes mid-scan raised from the key function, outside every guard, and took
                    # the whole `make rappel` down with it.
                    found.append((path.stat().st_mtime_ns, path))
                except OSError:
                    continue
        return [path for _, path in sorted(found, key=lambda pair: pair[0], reverse=True)]

    def reindex(
        self, *, project: str | None = None, paths: Iterable[Path] | None = None
    ) -> dict[str, int]:
        """Index every transcript in scope that CHANGED since last time; report what was done.

        Incremental on ``(size, mtime)``: a session that has not been touched is not re-read, so a
        second run over 604 transcripts costs a stat per file. A file that HAS grown is re-read
        whole and its rows replaced — transcripts are append-only in practice, but replacing is the
        only way that is also correct when the host rewrites one.
        """
        conn = self._connect()
        candidates = list(paths) if paths is not None else self.transcripts(project)
        counts = {
            "scanned": len(candidates),
            "indexed": 0,
            "skipped": 0,
            "messages": 0,
            "removed": 0,
        }
        counts["removed"] = self._prune_vanished(conn, project=project if paths is None else None)
        for path in candidates:
            try:
                stat = path.stat()
            except OSError:
                continue
            key = str(path)
            # mtime_ns, not int(mtime): truncating to the second let a same-size rewrite inside one
            # second look unchanged, so the old rows stayed and the new ones never landed.
            mtime = stat.st_mtime_ns
            row = conn.execute("SELECT size, mtime FROM files WHERE path = ?", (key,)).fetchone()
            if row is not None and row["size"] == stat.st_size and row["mtime"] == mtime:
                counts["skipped"] += 1
                continue
            session_id, title, rows = read_transcript(path)
            if not session_id:
                counts["skipped"] += 1
                continue
            counts["messages"] += self._replace_session(
                conn,
                path=key,
                stat_size=stat.st_size,
                stat_mtime=mtime,
                session_id=session_id,
                project=path.parent.name,
                title=title,
                rows=rows,
            )
            counts["indexed"] += 1
        self._drop_orphan_sessions(conn)
        conn.commit()
        return counts

    def _replace_session(
        self,
        conn: sqlite3.Connection,
        *,
        path: str,
        stat_size: int,
        stat_mtime: int,
        session_id: str,
        project: str,
        title: str,
        rows: list[tuple[str, str, str, str]],
    ) -> int:
        """Swap one FILE's rows for freshly parsed ones, FTS mirror included.

        **Keyed on the PATH, never on the declared session id**, and that is a repaired blocker
        rather than a preference. ``read_transcript`` reports the first ``sessionId`` it sees, and on
        a resumed or forked conversation that first line names the PARENT — so two files claimed one
        id. Deleting by id then made the second file erase the first, while ``files`` (keyed by path)
        kept both marked as indexed, so the erased conversation never came back on any later run.
        Measured on the real corpus: **1 023 messages, two whole conversations, gone on the very
        first run** — and the run still reported them as indexed. The file is the unit that exists on
        disk; the session id is metadata that files can disagree about.
        """
        # External-content FTS5 needs the 'delete' command to forget a row's terms; dropping the
        # base row alone would leave the term index pointing at a rowid that no longer exists, and
        # the stale terms would keep matching forever.
        self._forget_path(conn, path)
        for seq, (uuid, role, ts, text) in enumerate(rows):
            cursor = conn.execute(
                "INSERT INTO messages (path, session_id, uuid, role, ts, seq, text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (path, session_id, uuid, role, ts, seq, text),
            )
            conn.execute(
                "INSERT INTO messages_fts(rowid, text) VALUES (?, ?)", (cursor.lastrowid, text)
            )
        stamps = [ts for (_, _, ts, _) in rows if ts]
        conn.execute(
            "INSERT INTO sessions (session_id, project, title, first_ts, last_ts, n_messages) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET "
            "project=excluded.project, title=excluded.title, first_ts=excluded.first_ts, "
            "last_ts=excluded.last_ts, n_messages=excluded.n_messages",
            (
                session_id,
                project,
                title,
                min(stamps, default=""),
                max(stamps, default=""),
                len(rows),
            ),
        )
        conn.execute(
            "INSERT INTO files (path, size, mtime, session_id) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime, "
            "session_id=excluded.session_id",
            (path, stat_size, stat_mtime, session_id),
        )
        return len(rows)

    @staticmethod
    def _forget_path(conn: sqlite3.Connection, path: str) -> int:
        """Drop every row that came from one file, FTS terms included. Returns how many went."""
        rows = conn.execute("SELECT id, text FROM messages WHERE path = ?", (path,)).fetchall()
        for row in rows:
            conn.execute(
                "INSERT INTO messages_fts(messages_fts, rowid, text) VALUES ('delete', ?, ?)",
                (row["id"], row["text"]),
            )
        conn.execute("DELETE FROM messages WHERE path = ?", (path,))
        return len(rows)

    def _prune_vanished(self, conn: sqlite3.Connection, *, project: str | None) -> int:
        """Forget files that are no longer on disk — the reconciliation ``reindex`` used to skip.

        Without it a deleted (or renamed) transcript kept matching forever, and every hit pointed at
        a ``make rappel-fenetre`` that could never be opened. ``reindex`` only ever VISITED files
        that still exist, so nothing on the write path could ever notice a disappearance: the check
        has to come from the index side, not the disk side.
        """
        gone = 0
        for row in conn.execute("SELECT path FROM files").fetchall():
            path = row["path"]
            if Path(path).is_file():
                continue
            if project and Path(path).parent.name != project:
                continue  # out of scope for this pass — another project's pass will reconcile it
            self._forget_path(conn, path)
            conn.execute("DELETE FROM files WHERE path = ?", (path,))
            gone += 1
        return gone

    @staticmethod
    def _drop_orphan_sessions(conn: sqlite3.Connection) -> None:
        """Forget session rows that no longer own a single message.

        Runs at the END of a pass, never at the start: a file rewritten under a NEW session id
        replaces its messages during the pass, so the old id only becomes an orphan once the
        replacements are done. Pruning first left it in the browse view, pointing at nothing.
        """
        conn.execute(
            "DELETE FROM sessions WHERE session_id NOT IN (SELECT DISTINCT session_id FROM messages)"
        )

    # --- asking ---------------------------------------------------------------------------
    def search(self, query: str, *, limit: int = 10, project: str | None = None) -> Recall:
        """DISCOVERY — the passages that match, best first, with a highlighted snippet.

        Two passes, strict then loose. First every meaningful word must appear (``and``); only if
        that finds nothing does it retry on any one of them (``or``, ranked by ``bm25``). Prose
        questions rarely land word-for-word in a past message, so a single strict pass would answer
        "rien" to questions the corpus can actually answer — but a loose pass run FIRST would bury
        an exact match under near-misses. The mode used comes back in the :class:`Recall` so the
        caller can say which one answered.

        An empty or punctuation-only query returns NO hits rather than everything: a recall that
        answers a non-question is worse than one that abstains (invariant 14's spirit).
        """
        terms = tuple(query_terms(query))
        if not terms:
            return Recall(hits=(), mode="none", terms=())
        # A negative limit reaches SQLite as "no limit" and dumps the corpus — reachable from the
        # command line as TOPK=-1, and the exact opposite of the bounded-read promise (invariant 16).
        limit = max(0, limit)
        for mode in ("and", "or"):
            hits = self._match(
                build_match_expression(query, mode=mode), limit=limit, project=project
            )
            if hits:
                return Recall(hits=tuple(hits), mode=mode, terms=terms)
        return Recall(hits=(), mode="and", terms=terms)

    def _match(self, expression: str, *, limit: int, project: str | None) -> list[Hit]:
        """Run one MATCH expression and pack the rows — the half both passes of ``search`` share."""
        if not expression:
            return []
        conn = self._connect()
        sql = (
            "SELECT m.session_id, m.uuid, m.role, m.ts, m.seq, m.text, "
            "       s.project, s.title, "
            "       snippet(messages_fts, 0, '«', '»', '…', 14) AS snip "
            "FROM messages_fts f "
            "JOIN messages m ON m.id = f.rowid "
            "JOIN sessions s ON s.session_id = m.session_id "
            "WHERE messages_fts MATCH ? "
        )
        params: list[Any] = [expression]
        if project:
            sql += "AND s.project = ? "
            params.append(project)
        sql += "ORDER BY bm25(messages_fts) LIMIT ?"
        params.append(limit)
        return [
            Hit(
                session_id=row["session_id"],
                project=row["project"],
                title=row["title"],
                role=row["role"],
                ts=row["ts"],
                seq=row["seq"],
                uuid=row["uuid"],
                snippet=" ".join(row["snip"].split()),
                text=row["text"],
            )
            for row in conn.execute(sql, params)
        ]

    def window(self, session_id: str, *, around_seq: int, radius: int = 4) -> list[Hit]:
        """SCROLL — the messages surrounding a hit, in order, so a snippet regains its context."""
        conn = self._connect()
        radius = max(0, min(radius, 50))  # bounded like every other read (invariant 16)
        rows = conn.execute(
            "SELECT m.session_id, m.uuid, m.role, m.ts, m.seq, m.text, s.project, s.title "
            "FROM messages m JOIN sessions s ON s.session_id = m.session_id "
            "WHERE m.session_id = ? AND m.seq BETWEEN ? AND ? ORDER BY m.seq",
            (session_id, around_seq - radius, around_seq + radius),
        )
        return [
            Hit(
                session_id=row["session_id"],
                project=row["project"],
                title=row["title"],
                role=row["role"],
                ts=row["ts"],
                seq=row["seq"],
                uuid=row["uuid"],
                snippet="",
                text=row["text"],
            )
            for row in rows
        ]

    def recent(self, *, limit: int = 15, project: str | None = None) -> list[SessionRow]:
        """BROWSE — the latest conversations, newest first, when there is no query to ask."""
        conn = self._connect()
        sql = "SELECT * FROM sessions "
        params: list[Any] = []
        if project:
            sql += "WHERE project = ? "
            params.append(project)
        sql += "ORDER BY last_ts DESC LIMIT ?"
        params.append(limit)
        return [
            SessionRow(
                session_id=row["session_id"],
                project=row["project"],
                title=row["title"],
                first_ts=row["first_ts"],
                last_ts=row["last_ts"],
                n_messages=row["n_messages"],
            )
            for row in conn.execute(sql, params)
        ]

    def stats(self) -> dict[str, int]:
        """How much is indexed — the honest denominator behind any recall claim."""
        conn = self._connect()
        return {
            "sessions": conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
            "messages": conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "files": conn.execute("SELECT COUNT(*) FROM files").fetchone()[0],
        }

    def __enter__(self) -> SessionIndex:
        self._connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
