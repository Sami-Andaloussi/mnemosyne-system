"""open_jsonl_sink — the DURABLE leg of the observability seam: append-only JSONL on local disk (D6 / D82).

The brick-free twin of :mod:`~mnemosyne.runtime.observability_langfuse`. Where Langfuse is the OPTIONAL
dashboard mirror (needs the brick + a running instance), this is the PRIMARY, always-available trail
(pure stdlib): every already-redacted trace line is appended as one JSON object per line to
``system/logs/trace_<UTC>.jsonl`` — the greppable, append-only journal D6 mandates. It is wired ALONGSIDE
Langfuse via :func:`~mnemosyne.runtime.observability.fan_out` at ③ ignition (:func:`real_runtime`).

**Clean by construction, not by discipline (inv. 12 / 22 / D100).** The sink receives the SAME line held
in :meth:`~mnemosyne.runtime.observability.LocalObservability.records` — values already withheld under a
non-``public`` trace — and writes it VERBATIM under a single ``line`` key. Like the Langfuse adapter it
does NOT parse the datum back out (parsing risks re-surfacing content the seam deliberately flattened):
the durable log inherits the structural cleanliness of the greppable log it mirrors, so a ``grep`` of the
file can NEVER surface ``sensible`` content — the D6 barrier, proven end-to-end to DISK in the suite.
Event NAMES and field KEYS still travel (operational metadata, not content — the seam's rule); the
durable log makes that permanent, so a trace name or field key must never carry content (every caller
today honors this — the barrier redacts VALUES, the naming discipline keeps names/keys operational).

**Provenance = ``when`` (D6 / D19 / D33).** The in-memory records carry the event name + field keys but
no time; the durable trail is read hours or days later, so the sink stamps each record with a wall-clock
UTC ``ts``. Append-only line order IS the journal's total order (ties on an equal ``ts`` broken by
position, D82). The rest of the provenance (``who`` / ``which model``) rides in the line's own fields
where the seam lets a value travel — the sink adds only the time the records lack.

**Observability must never break the app (D111, fail-safe).** A disk / permission error is SWALLOWED,
never raised into the traced operation — a full or read-only disk degrades the trail, it does not take
down the op being traced. The record-building (:func:`_line_to_record`) is pure and UNIT-TESTED; the
``__call__`` swallow is proven with an unwritable path. Retention: kept, append-only, archivable (D6 / D44).

Stdlib only — no brick, so no D103 (sole importer) / D126 (brick-free suite) concern: this default trail
is ALWAYS present, which is exactly why it is the D6 log of record while Langfuse is the optional mirror.

Decisions: D6 (JSONL append-only, greppable, clean) · D19 / D33 (event log + provenance) · D82 (replayable
journal / total order) · D111 (fail-safe, LOCAL) · D71 (no ``sensible`` in logs, local-only) · inv. 12 / 22.
Code & docstrings English (D117).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .observability import TraceSink


def _utcnow_iso() -> str:
    """A wall-clock UTC stamp for a durable record — ISO-8601 with microseconds and a ``Z`` suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _line_to_record(line: str, *, now: str) -> dict[str, str]:
    """Wrap one already-redacted trace line into the durable JSONL record (pure, UNIT-TESTED).

    A faithful, opaque wrapping: the line travels VERBATIM under ``line`` (it is already redacted
    metadata — the seam withheld every ``sensible`` value before the sink saw it, so there is nothing
    to strip here, inv. 12), gaining only a wall-clock ``ts`` (the provenance the in-memory records lack,
    D33). It does NOT parse the line back into fields — parsing risks re-surfacing content the seam
    deliberately flattened, so this mirrors the Langfuse adapter's no-parse discipline (inv. 12)."""
    return {"ts": now, "line": line}


def open_jsonl_sink(path: Path) -> TraceSink:
    """Wire an append-only JSONL file as a :class:`~mnemosyne.runtime.observability.TraceSink` (D6).

    Returns a ``Callable[[str], None]`` — the exact seam shape — that appends each already-redacted line
    as one ``{"ts", "line"}`` JSON object to ``path``, creating the parent directory if needed and
    SWALLOWING any I/O error (observability must never break the app, D111). Injected into
    :class:`~mnemosyne.runtime.observability.LocalObservability` (usually via
    :func:`~mnemosyne.runtime.observability.fan_out`, beside the Langfuse export) at ③ ignition; tests
    pass a ``tmp_path``. The file is opened per line (append + close), so every event is flushed to disk
    at once — a crash mid-run keeps the trail up to the last recorded event (D82, resumption)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except (
        OSError
    ):  # unwritable location ⇒ degrade to a best-effort no-op trail, never break the app (D111)
        pass
    return _JsonlSink(path)


class _JsonlSink:
    """A callable :class:`TraceSink` appending already-redacted lines to a JSONL file, fail-safe (D111).

    ``__call__`` builds the durable record (pure :func:`_line_to_record`) and appends it, SWALLOWING any
    exception so a down / full disk never breaks the traced operation. The record-building is unit-tested
    pure; the swallow is proven with an unwritable path — the same fail-safe contract as
    :class:`~mnemosyne.runtime.observability_langfuse._LangfuseSink`."""

    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        self._path = path

    def __call__(self, line: str) -> None:
        """Append one already-redacted trace line as a JSONL record; swallow any error (D111, fail-safe).

        The line is opaque, already-clean metadata (the seam redacted it upstream, inv. 12) — this
        never un-redacts or re-parses it. Any I/O failure is caught and dropped: a durable-log write must
        NEVER raise into the operation being traced (D111)."""
        try:
            record = _line_to_record(line, now=_utcnow_iso())
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001 - observability is best-effort: a down sink never breaks the app
            return
