"""connect_langfuse — the SOLE importer of the Langfuse brick as a :class:`TraceSink` (D111 / D103).

The export leg behind the :data:`~mnemosyne.runtime.observability.TraceSink` seam (③-6b): it forwards
each ALREADY-redacted trace line to a **LOCAL, self-hosted Langfuse** instance (MIT; ``oss_registry.md``)
for the user's health dashboard. It wraps the brick behind the sink callable so the rest of Mnémosyne talks
only to the seam and the suite stays green with the brick NOT installed (D126). Everything that REACHES
THE BRICK is ``# pragma: no cover``: it needs the installed package + a running local instance, absent
in CI, exercised only at ③ ignition, where the 1-click smoke confronts this glue with the real API. The
pure event mapper (:func:`_line_to_event`) is deterministic, brick-free, UNIT-TESTED.

**Never un-redacts, never re-fetches (D111 / inv. 12 / 22).** The sink receives the SAME line held in
:meth:`~mnemosyne.runtime.observability.LocalObservability.records` — values already withheld under a
non-``public`` trace — so the export inherits that structural cleanliness and can never carry
``sensible`` content. This adapter forwards the line verbatim; it does not parse the datum back out, does
not enrich it, does not phone a remote. Langfuse is LOCAL — observability itself must never exfiltrate.

**Observability must never break the app (D111, fail-safe).** A client / network error is SWALLOWED
here, never raised into the caller: a down dashboard degrades the trail to in-memory only, it does not
take down the operation being traced. (This mirrors the seam contract in
:class:`~mnemosyne.runtime.observability.LocalObservability`, which feeds every recorded line to the
sink.) The swallow is the ONE place a brick error is not propagated — because a trace export is
best-effort telemetry, not a governed action.

Decisions: D111 (health + tracing, LOCAL, best-effort) · D103 (sole importer) · D126 (brick-free suite,
injected client) · D100 (redaction is the seam's; the sink never un-does it) · inv. 12 / 22 (clean
trail). Code & docstrings English (D117).
"""

from __future__ import annotations

from .observability import TraceSink

#: The event name under which a raw trace line is shipped to Langfuse. The line is opaque, already-clean
#: metadata; Langfuse stores it as one event on the local dashboard. The exact client method / event
#: shape is confirmed at ignition (IGNITION NOTE on :func:`connect_langfuse`).
_EXPORT_EVENT = "mnemosyne.trace"


def _line_to_event(line: str) -> dict[str, object]:
    """Map one already-redacted trace line to the event payload shipped to Langfuse (pure, UNIT-TESTED).

    A trivial, faithful wrapping: the line travels verbatim under a fixed ``message`` key (it is
    already redacted metadata — the seam withheld every ``sensible`` value before the sink saw it, so
    there is nothing to strip here, D111). This helper does NOT parse the line back into structured
    fields — parsing risks re-surfacing content the seam deliberately flattened; forwarding the opaque
    line keeps the export as clean as the greppable log it mirrors (inv. 12).

    Confirmed at ignition (Langfuse 4.13.0, OTel-based SDK): ``create_event`` has no ``message``
    parameter — a live probe raised ``TypeError`` on it — so the line travels under ``metadata``
    (``create_event`` accepts ``name`` / ``input`` / ``output`` / ``metadata`` / ...); this is the
    brick-free payload the client is handed."""
    return {"name": _EXPORT_EVENT, "metadata": {"message": line}}


def connect_langfuse(*, client: object | None = None) -> TraceSink:
    """Wire a LOCAL Langfuse instance as a :class:`TraceSink` (the ``[OPERATOR]`` ignition seam, D111).

    Returns a ``Callable[[str], None]`` — the exact :data:`~mnemosyne.runtime.observability.TraceSink`
    shape — that forwards each already-redacted line to the local dashboard, SWALLOWING any client error
    (observability must never break the app, D111). Imports ``langfuse`` LAZILY so this module is
    import-safe without it (D126); injected into
    :class:`~mnemosyne.runtime.observability.LocalObservability` as its ``sink`` at ③-6b. Pass ``client``
    in tests / at ignition to inject a resolved client and keep the mapping + fail-safe exercised without
    the brick.

    IGNITION NOTE (best-guess API, confronted to the real ``langfuse`` package at the smoke ``[OPERATOR]``):
    ``from langfuse import Langfuse`` → ``client = Langfuse(host="http://localhost:3000", public_key=...,
    secret_key=...)`` pointing at the SELF-HOSTED local instance; a line is shipped best-guess via
    ``client.event(name=..., metadata={...})`` or ``client.create_event(...)`` (older SDKs use a
    ``client.trace(...)``/``span`` builder). The keys come from the protected local config (a local
    instance, no third-party egress — D66). Confirm at ignition: (1) the import + constructor
    (``Langfuse(host=..., ...)``); (2) the single-line ingest method (``event`` vs ``create_event`` vs a
    ``trace``/``generation`` builder) and whether a ``flush()`` is needed to push buffered events; (3)
    that the host is the LOCAL instance (never a hosted Langfuse cloud — that would exfiltrate); (4) the
    error type a down instance raises (so the swallow catches it). The swallow is deliberate and total:
    telemetry export never propagates into the traced operation (D111)."""
    if client is None:
        from langfuse import Langfuse  # noqa: F401 - lazy, sole importer (D103)

        client = Langfuse()  # host / keys resolved from local config (confirmed at ignition)
    return _LangfuseSink(client)


class _LangfuseSink:
    """A callable :class:`TraceSink` forwarding already-redacted lines to Langfuse, fail-safe (D111).

    Holds the injected client (so this class never imports at module scope — :func:`connect_langfuse`
    does the sole lazy import). ``__call__`` maps the line to an event and ships it, SWALLOWING any
    exception so a down dashboard never breaks the traced operation. The ``__call__`` body is brick-free
    (it calls only the injected client + the pure mapper), so it is UNIT-TESTED with a raising fake
    client to prove the swallow; only :func:`connect_langfuse` touches the real import (``pragma``)."""

    __slots__ = ("_client",)

    def __init__(self, client: object) -> None:
        self._client = client

    def __call__(self, line: str) -> None:
        """Ship one already-redacted trace line to Langfuse; swallow any error (D111, fail-safe).

        The line is opaque, already-clean metadata (the seam redacted it before the sink, inv. 12) —
        this never un-redacts or re-fetches it. Any client / network failure is caught and dropped: a
        best-effort telemetry export must NEVER raise into the operation being traced (D111)."""
        try:
            self._emit(_line_to_event(line))
        except Exception:  # noqa: BLE001 - observability is best-effort: a down sink never breaks the app
            return

    def _emit(
        self, event: dict[str, object]
    ) -> None:  # pragma: no cover - real client call (③ ignition)
        """Hand one event to the Langfuse client (confirmed at ignition, was best-guess).

        Tries the SDK ingest methods in order (``event`` → ``create_event`` → a ``log`` fallback).
        Confirmed at ignition (Langfuse 4.13.0): the client exposes no plain ``event``, so this resolves
        to ``create_event`` (a real OTel-backed call — constructing the client and calling it locally
        does not raise; delivery to an unreachable local instance is retried/logged internally by the
        SDK's own OTel exporter, never surfaced as an exception here). Raises if no known method exists
        — but :meth:`__call__` swallows that, so a mismatched SDK degrades the trail to in-memory only,
        it does not break the app (D111)."""
        for method_name in ("event", "create_event", "log"):
            method = getattr(self._client, method_name, None)
            if callable(method):
                method(**event)
                return
        raise AttributeError(
            "Langfuse client exposes no known single-event ingest method "
            "(tried event / create_event / log) — confirm at ignition ([OPERATOR])"
        )


#: A fail-safe no-op sink: swallows every line. Not the export path — a convenience for a caller that
#: wants the sink SEAM present with export disabled (e.g. a config toggle) without threading ``None``.
def null_langfuse_sink(_line: str) -> None:  # noqa: D401 - trivial no-op sink
    """Drop the line (export disabled) — the trail stays in-memory only (D111 default)."""
    return None
