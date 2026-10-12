"""``make rappel`` (D155) - ask Mnémosyne what was already said, in a past session.

The read surface over :class:`~mnemosyne.production.sessions.SessionIndex`. Three shapes, chosen by
what you pass, the way ``session_search_tool.py`` does it upstream - no mode flag to remember::

    make rappel Q="qu'est-ce qu'on avait décidé sur la classification des livres"
    make rappel                                    # no question -> the latest conversations
    make rappel-fenetre SESSION=<id> SEQ=<n>       # the messages around one hit

**Brick-free and free.** No model is called, no network is touched, nothing is embedded: this is
SQLite FTS5 over text (``sqlite3`` is stdlib). A query costs a disk seek, which is why it can
afford to refresh the index on every invocation instead of asking to be maintained.

**It refreshes itself, incrementally.** Each run re-reads only the transcripts whose size or mtime
changed - a stat per file otherwise. So the session you are IN is searchable the moment you ask,
including the turn that just happened, with no build step to remember and no daemon to run.

**Pulled, never pushed** (see the module docstring of the index): no hook injects this, nothing
appears at startup. It answers when asked, and stays silent otherwise. Code English (D117); what it
prints is for the operator, so it prints French.
"""

from __future__ import annotations

import argparse
import sys

from ..production.sessions import SessionIndex, default_project_dir

#: How many passages one question returns. Bounded like every other read surface (invariant 16):
#: enough to recognise the right conversation, never a dump to wade through.
_TOP_K = 8

#: How many conversations the browse mode lists when there is no question.
_RECENT = 12

#: Messages on each side of a hit in the window mode.
_RADIUS = 4

#: A printed passage is trimmed to this; the window mode is how you read one in full.
_PREVIEW = 400


def _short(text: str, limit: int = _PREVIEW) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "..."


def _speaker(role: str) -> str:
    return "OPERATOR" if role == "user" else "MOI "


def render_hits(recall, query: str) -> str:
    """The discovery view: who said it, when, in which conversation, and how to read around it.

    Says out loud when the answer came from the LOOSE pass. A near-miss presented as an exact hit
    is how a recall surface starts being believed more than it deserves.
    """
    if not recall:
        return (
            f"Aucun passage ne correspond à « {query} ».\n"
            "Rien n'est inventé : si ça n'a pas été dit, l'index ne le fabrique pas.\n"
            "Essaie moins de mots, ou des mots plus rares."
        )
    if recall.mode == "or":
        header = (
            f"{len(recall)} passage(s) APPROCHANTS pour « {query} » - aucun ne contient tous les "
            f"mots ({', '.join(recall.terms)}), voici les plus proches :"
        )
    else:
        header = f"{len(recall)} passage(s) pour « {query} » - du plus pertinent au moins :"
    lines = [header, ""]
    for hit in recall:
        stamp = hit.ts[:16].replace("T", " ") if hit.ts else "date inconnue"
        title = hit.title or "(sans titre)"
        lines.append(f"[{_speaker(hit.role)}] {stamp} - {title}")
        lines.append(f"   {_short(hit.snippet or hit.text)}")
        lines.append(f"   -> make rappel-fenetre SESSION={hit.session_id} SEQ={hit.seq}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_recent(rows: list) -> str:
    """The browse view: the latest conversations, when you do not have a question yet."""
    if not rows:
        return (
            "Aucune conversation indexée.\n"
            "Si c'est la toute première fois, l'index vient d'être construit : relance la commande."
        )
    lines = [f"{len(rows)} dernière(s) conversation(s) :", ""]
    for row in rows:
        stamp = row.last_ts[:16].replace("T", " ") if row.last_ts else "date inconnue"
        lines.append(f"{stamp} - {row.title or '(sans titre)'}  ({row.n_messages} messages)")
        lines.append(f"   session {row.session_id}")
    return "\n".join(lines)


def render_window(hits: list, session_id: str, seq: int) -> str:
    """The scroll view: a hit put back in the order it was said."""
    if not hits:
        return f"Rien à afficher autour de SEQ={seq} dans la session {session_id}."
    lines = [f"Session {session_id}, autour du message {seq} :", ""]
    for hit in hits:
        marker = ">" if hit.seq == seq else " "
        lines.append(f"{marker} [{_speaker(hit.role)}] #{hit.seq}")
        lines.append(f"   {_short(hit.text, 900)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - [OPERATOR] surface (reads the host tree)
    parser = argparse.ArgumentParser(
        prog="make rappel",
        description="Search Mnémosyne's own past conversations. No model, no network, no cost.",
    )
    parser.add_argument("query", nargs="?", default="", help="what to look for (free French prose)")
    parser.add_argument("--session", default="", help="window mode: the session id to open")
    parser.add_argument("--seq", type=int, default=-1, help="window mode: the message to centre on")
    parser.add_argument(
        "--top-k", type=int, default=_TOP_K, help=f"passages to return (default {_TOP_K})"
    )
    parser.add_argument(
        "--all-projects", action="store_true", help="search beyond this repo's sessions"
    )
    parser.add_argument("--stats", action="store_true", help="print what is indexed, and stop")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    project = None if args.all_projects else default_project_dir()
    index = SessionIndex()
    counts = index.reindex(project=project)
    if counts["indexed"]:
        print(
            f"[rappel] {counts['indexed']} conversation(s) (re)lue(s), "
            f"{counts['messages']} messages indexés.",
            flush=True,
        )

    if args.stats:
        stats = index.stats()
        print(
            f"[rappel] {stats['sessions']} conversations  -  {stats['messages']} messages  -  "
            f"index {index.db_path}"
        )
        return 0
    if args.session and args.seq >= 0:
        print(
            render_window(
                index.window(args.session, around_seq=args.seq, radius=_RADIUS),
                args.session,
                args.seq,
            )
        )
        return 0
    if not args.query.strip():
        print(render_recent(index.recent(limit=_RECENT, project=project)))
        return 0
    print(render_hits(index.search(args.query, limit=args.top_k, project=project), args.query))
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
