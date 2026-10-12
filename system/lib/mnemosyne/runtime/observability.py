"""LocalObservability (D111, invariant 12 / 22) - self-hosted tracing that never leaks.

The greppable side of replayability (invariant 12): traces record *events* (D19) for the
health dashboard (D111), but a grep of the JSONL log must NEVER reveal ``sensible``
content - that lives only in the protected replay store
(:class:`~mnemosyne.runtime.snapshots.SnapshotStore`). The two are opposites by design:
the snapshot store REPRODUCES the sensible input; the log CANNOT.

**Redaction is structural, not discipline (D100).** A trace is opened with the datum's
label; every event under a non-``public`` trace has its field VALUES replaced by a
redaction marker before anything is written. So even a careless caller that passes a
``sensible`` payload as an event field cannot leak it - the barrier is in the sink, not
in trusting the caller (invariant 22 / 12 / D71). Event NAMES and field KEYS still travel
(operational metadata is not content), so the trail stays useful.

Self-hosted **LOCAL** (default brick: Langfuse, ``system/config/oss_registry.md``): traces
may contain ``sensible``, so observability itself must never exfiltrate (D111 / D66). On
the runner going down, conduct is graceful degradation - ``sensible`` work is queued, never
switched to the cloud (that policy lives in the scheduler / health layer, D111).

Decisions: D111 (health + tracing, local)  -  D19 (event logs)  -  D71 (no ``sensible`` in
logs)  -  D108 (normalized codes -> error rate). Invariants carried: 12 (clean logs), 22
(no secret/`sensible` in the trail).
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..guard.redact import redact_sensitive_text
from ..ports import (
    GovernanceLabel,
    HealthReport,
    HealthState,
    Sensitivity,
    TraceId,
)

#: The marker written in place of a redacted value - carries only the level, never content.
_REDACTED = "[redacted]"

#: A trace sink: receives each recorded line for export to a LOCAL dashboard (Langfuse / OTel, (3)-6b).
#: It sees only what ``records()`` holds - lines already redacted to metadata under a non-public trace -
#: so the export inherits the structural cleanliness and can never carry ``sensible`` content (D111).
TraceSink = Callable[[str], None]


class LocalObservability:
    """Local tracing + health whose greppable log is ``sensible``-clean by construction.

    Realizes :class:`~mnemosyne.ports.observability.Observability`. Opening a trace binds
    it to a label; events under a non-``public`` trace are redacted to metadata before the
    line is recorded (invariant 12 / 22)."""

    __slots__ = ("_labels", "_records", "_errors", "_seq", "_sink")

    def __init__(self, *, sink: TraceSink | None = None) -> None:
        self._labels: dict[TraceId, Sensitivity] = {}
        self._records: list[str] = []
        self._errors = 0
        self._seq = 0
        # optional export sink (Langfuse / OTel, (3)-6b): fed each ALREADY-redacted line, so the export
        # never sees `sensible` content (D111). Absent => in-memory only (the skeleton default, D126).
        self._sink = sink

    def start_trace(self, name: str, label: GovernanceLabel) -> TraceId:
        """Open a trace bound to ``label`` - the sensitivity that decides redaction (D111).

        The trace name is metadata (never content), so it is recorded as-is; the label is
        remembered so every later :meth:`event` under this trace redacts fail-safe."""
        self._seq += 1
        trace = TraceId(f"t{self._seq}")
        self._labels[trace] = label.sensitivity
        self._append("trace.start", {"name": name, "level": label.sensitivity.token})
        return trace

    def event(self, trace: TraceId, name: str, **fields: object) -> None:
        """Record a structured event; field VALUES are redacted for a non-``public`` trace.

        Fail-safe: an unknown trace is treated as ``sensible`` (redacted). The event name
        and field keys always travel; only values that could carry ``sensible`` content are
        withheld - the log stays greppable-clean (invariant 12 / 22 / D71)."""
        level = self._labels.get(trace, Sensitivity.SENSIBLE)
        if level is Sensitivity.PUBLIC:
            safe = {k: _public_value(v) for k, v in fields.items()}
        else:
            # non-public => redact every value; keep keys as operational metadata (D100 -
            # structural, not trusting the caller to have stripped `sensible`).
            safe = dict.fromkeys(fields, _REDACTED)
        if str(name).startswith("error"):
            self._errors += 1
        self._append(name, safe)

    def health(self) -> HealthReport:
        """A minimal hardware + functional health snapshot (user's dashboard, D111).

        The skeleton reports OK with a live error rate derived from recorded ``error*``
        events; the real hardware probes (disk / RAM / thermal) plug in at (3). Degraded /
        critical states drive the circuit-breakers (EX5) once wired."""
        total = max(len(self._records), 1)
        return HealthReport(
            state=HealthState.OK,
            disk_ok=True,
            ram_ok=True,
            thermal_ok=True,
            runner_up=True,
            stores_reachable=True,
            queue_depth=0,
            error_rate=self._errors / total,
        )

    def records(self) -> tuple[str, ...]:
        """The greppable JSONL log lines - proven free of ``sensible`` content (inv. 12)."""
        return tuple(self._records)

    def _append(self, name: str, fields: dict[str, str]) -> None:
        line = f"{name} {json.dumps(fields, ensure_ascii=False, sort_keys=True)}"
        self._records.append(line)
        if self._sink is not None:
            try:
                # export the SAME redacted line held in `records()` - the sink inherits the structural
                # cleanliness (values already withheld under a non-public trace), so a Langfuse/OTel export
                # carries operational metadata only, never `sensible` content (D111 / inv. 12 / 22).
                self._sink(line)
            except Exception:  # noqa: BLE001 - a sink failure NEVER propagates into the traced op: the
                # couture GUARANTEES fail-safety structurally (D111 / inv. 22), it does not TRUST the sink
                # to swallow its own errors. records() is already appended above, so the trail degrades to
                # in-memory only - the op being traced runs on untouched.
                pass


def _public_value(value: object) -> str:
    """Render a PUBLIC field value, with any secret in it masked first (D154).

    Sensitivity redaction above is structural and covers ``perso`` / ``sensible``: those
    traces keep keys and drop every value. It does NOT cover this branch - a ``public``
    trace records verbatim, by design, because operational values are what make the log
    useful. But "public" describes the DATA's sensitivity, and says nothing about an API
    key that wandered into it: a project bubble open to the internet is capped at
    ``public`` (D49 / D54-1), so a tool echoing ``ANTHROPIC_API_KEY=sk-ant-...`` writes it
    in clear on the exact traces that also ship to an external collector.

    So the two filters are orthogonal and both needed: sensitivity decides whether a value
    may be recorded at all, redaction decides whether a value we DO record is safe to keep.
    Regex, hence best-effort (see :mod:`~mnemosyne.guard.redact`) - it never licenses
    routing a real secret here; it catches the accident.

    ``code_file=True`` on purpose. Trace values are not shell transcripts: this path carries
    a model's own output (``runner`` records the completion verbatim), config echoes and JSON
    fragments, and the ENV/JSON/YAML passes mangle exactly that - ``MAX_TOKENS=4096`` became
    ``MAX_TOKENS=***``, ``tokens: 128000`` became ``tokens: ***``, a ``"apiKey": "test-fixture"``
    fixture lost its value. A forensic trail that quietly rewrites the numbers it exists to
    record is worse than none. Vendor prefixes, auth headers, private keys, DB connection
    strings, JWTs and URL credentials - every shape that is a secret BY CONSTRUCTION rather
    than by surrounding syntax - are still masked. Upstream makes the same call for
    non-env-dump output.
    """
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return redact_sensitive_text(text, code_file=True)


def fan_out(*sinks: TraceSink) -> TraceSink:
    """Compose several sinks into one - :class:`LocalObservability` accepts a single ``sink`` (D111).

    Feeds each already-redacted line to every leg, ISOLATING them: one raising sink never stops the
    others (defense in depth - the legs are already fail-safe, but a combinator must not couple their
    fates, D100). Used at (3) ignition to fan the trail to BOTH the durable JSONL log (the primary, D6) and
    the local Langfuse dashboard export (the optional mirror). Each leg sees only what ``records()`` holds
    - lines already redacted to metadata - so every export inherits the structural cleanliness (inv. 12)."""

    def _multiplex(line: str) -> None:
        for sink in sinks:
            try:
                sink(line)
            except Exception:  # noqa: BLE001 - one leg down never breaks the others (D111, fail-safe)
                continue

    return _multiplex
