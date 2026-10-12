"""Frontmatter status for Mnemosyne System."""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Final

#: The LEADING frontmatter block only, anchored at ``\A``. Bounding it is the whole point: a status
#: line quoted anywhere in the body can never be mistaken for the real field, nor rewritten.
FRONTMATTER_RE: Final = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
#: The ``status:`` field inside that block. Case-insensitive and tolerant of a trailing comment, so a
#: hand-edited ``Ouvert`` still counts instead of silently dropping the entry out of its queue.
STATUS_RE: Final = re.compile(
    r"^status:[ \t]*\"?([A-Za-z_-]+)\"?[ \t]*(?:#[^\r\n]*)?[ \t\r]*$", re.MULTILINE | re.IGNORECASE
)
#: Longest slug we put in a filename. An agent pasting a whole error message as the title is the
#: NOMINAL case, and an untruncated one raises ``OSError: File name too long`` (255 bytes on APFS).
MAX_SLUG: Final = 80


def read_text(path: Path) -> str:
    """Read preserving line endings verbatim (``newline=""``) - nothing is normalised behind our back."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def atomic_write(path: Path, text: str) -> None:
    """Write DURABLY: temp sibling + ``os.replace``, so a crash mid-write leaves the destination intact.

    These files are hand-written matter that no rebuild can reconstruct, so truncating one in place
    would contradict the reason it is kept at all (D44 / invariant 2)."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    os.replace(tmp, path)


def split_frontmatter(text: str) -> tuple[str, str, str] | None:
    """``(whole block, its inner body, the rest of the file)`` - or ``None`` when there is no block."""
    found = FRONTMATTER_RE.match(text)
    return None if found is None else (found.group(0), found.group(1), text[found.end() :])


def slugify(title: str, *, max_len: int = MAX_SLUG) -> str:
    """A filesystem-safe ASCII kebab slug for ``title``, bounded to ``max_len`` characters."""
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    kebab = re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", folded.lower())).strip("-")
    return kebab[:max_len].rstrip("-") or "untitled"


def yaml_quoted(value: str) -> str:
    """``value`` as a safe double-quoted YAML scalar - quotes escaped, newlines flattened."""
    flat = " ".join(value.splitlines()).strip()
    return '"' + flat.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _field_re(name: str) -> re.Pattern[str]:
    """The compiled matcher for one scalar frontmatter key - bounded to a single line."""
    return re.compile(rf"^{re.escape(name)}:[ \t]*(.*?)[ \t\r]*$", re.MULTILINE)


def field_of(path: Path, name: str) -> str:
    """One scalar field of ``path``'s LEADING frontmatter - ``""`` when absent or unreadable.

    Fail-OPEN for the same reason :func:`status_of` is: a queue that raises blocks the tick. The
    value is un-quoted symmetrically with :func:`yaml_quoted`, so a title carrying ``"`` survives the
    round trip; anything else is returned raw, because inventing a YAML parser to read four keys
    would be a second, richer source of truth about a format this module already owns.
    """
    try:
        text = read_text(path)
    except OSError:
        return ""
    parts = split_frontmatter(text)
    if parts is None:
        return ""
    found = _field_re(name).search(parts[1])
    if found is None:
        return ""
    raw = found.group(1).strip()
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return raw


def create_dated_entry(root: Path, *, stamp: str, title: str, body: str) -> Path:
    """Write ``body`` to a fresh ``<stamp>-<slug>.md`` under ``root`` and return its path.

    Two entries with the same title on the same day cannot collide: the file is created with
    ``O_EXCL`` and the suffix bumped on refusal, so the guarantee holds even for two sessions writing
    at the same instant - the exclusive create, not an ``exists()`` look, is what makes it
    structural. The suffix is zero-padded so lexicographic order stays chronological (``-02`` before
    ``-10``), which is what lets every caller sort by filename instead of stat-ing each file.
    """
    root.mkdir(parents=True, exist_ok=True)
    base = f"{stamp}-{slugify(title)}"
    for n in range(1, 100):
        path = root / (f"{base}.md" if n == 1 else f"{base}-{n:02d}.md")
        try:
            with path.open("x", encoding="utf-8", newline="") as handle:
                handle.write(body)
        except FileExistsError:
            continue
        return path
    raise OSError(f"99 entries already share the name {base!r} today - rename this one")


def today_stamp(today: date | None = None) -> str:
    """Today in ISO form - injectable, so every caller's filenames are deterministic under test."""
    return (today or date.today()).isoformat()


def status_of(path: Path) -> str | None:
    """The declared status of one entry - ``None`` when unreadable, or lacking a status field.

    Fail-OPEN: a file we cannot parse is skipped, not fatal. A merely odd value (``Ouvert``, a
    trailing comment) is still read; only a destroyed block is lost, and that entry goes silent.
    """
    try:
        text = read_text(path)
    except OSError:
        return None
    parts = split_frontmatter(text)
    if parts is None:
        return None
    found = STATUS_RE.search(parts[1])
    return found.group(1).lower() if found else None


def entries_with_status(
    root: Path, wanted: str, *, skip_names: frozenset[str] = frozenset()
) -> tuple[Path, ...]:
    """Every ``.md`` directly under ``root`` (recursively) whose status is ``wanted``, sorted.

    A missing directory yields ``()`` - a queue that does not exist yet is simply empty, never an
    error (the tick asks this question at every session start, including on a fresh clone).
    """
    if not root.is_dir():
        return ()
    found = [
        path
        for path in sorted(root.rglob("*.md"))
        if path.name not in skip_names and status_of(path) == wanted
    ]
    return tuple(found)


def set_status(path: Path, new_status: str, *, extra_lines: tuple[str, ...] = ()) -> Path:
    """Rewrite ONLY the leading frontmatter so ``status:`` becomes ``new_status``; body untouched.

    ``extra_lines`` are appended inside the block (e.g. a drain stamp). Raises ``ValueError`` when
    the file has no frontmatter block or no status field - refusing loudly rather than inventing
    structure in a file a human wrote.
    """
    text = read_text(path)
    parts = split_frontmatter(text)
    if parts is None:
        raise ValueError(f"{path} has no frontmatter block - refusing to invent one")
    block, inner, body = parts
    if STATUS_RE.search(inner) is None:
        raise ValueError(f"{path} has no status: field - refusing to invent one")
    updated = STATUS_RE.sub(f"status: {new_status}", inner, count=1)
    for line in extra_lines:
        updated = f"{updated}\n{line}"
    atomic_write(path, block.replace(inner, updated, 1) + body)
    return path
