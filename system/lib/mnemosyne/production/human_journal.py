"""HumanLayerJournal (D82) — the replayable append-only net under Moteur A's HUMAN layer.

D44 ("every derivative rebuilds from ``raw/``") is TRUE for the derived stores (Qdrant /
graph facts, rebuilt from the ``.md`` truth by :class:`~mnemosyne.stores.journal.IntentJournal`,
D105) but FALSE for the HUMAN layer of the living graph (Moteur A): the user's *validations* and
*invalidations* of a fiche are gestures, not derivations — nothing reconstructs them from a
source. Held only in :class:`~mnemosyne.production.memory.LivingMemory`'s RAM
(``_fiches`` / ``_invalidated``), a crash would erase them IRRECOVERABLY, breaking the
non-destructive invariant (D56 / D60) exactly where it matters most. D82 protects this layer
apart, with its own durable journal.

Three properties are structural, not optional:

* **Write-ahead, fail-CLOSED.** :meth:`record_validate` / :meth:`record_invalidate` append the
  gesture to durable disk BEFORE :class:`LivingMemory` mutates its RAM. An I/O error PROPAGATES
  (it is never swallowed), so a caller that fails to journal does NOT apply the mutation — no
  silent loss (D80 fail-closed). This is the deliberate OPPOSITE of the observability sink
  (:mod:`~mnemosyne.runtime.observability_jsonl`, D6 / D111), which is best-effort fail-SAFE
  because a lost trace line is tolerable; a lost human gesture is not.
* **Self-contained.** A ``validate`` event carries the WHOLE validated :class:`Fiche` (via the
  faithful codec below), never a bare id that would depend on the derived layer being rebuilt
  first. Replay reconstructs the human layer with NO dependency on re-extraction — which is
  right, because the human layer is precisely the part that does not rebuild from ``raw/``.
* **Non-destructive, ordered.** Append-only: the file's line order IS the human layer's total
  order (ties broken by position, the D84 substrate). Replay is idempotent — ``validate`` sets
  ``_fiches[id]`` and ``invalidate`` adds to ``_invalidated``, so replaying twice reaches the
  same state (invariant 24 spirit).

**Restore order (D110 / D82).** truth (``.md``/git) → reindex rebuilds Qdrant + graph facts →
THIS journal's :meth:`replay` rebuilds the human layer → smoke test validates. The journal is
part of the PRECIOUS treasure (:data:`~mnemosyne.runtime.backup.PRECIOUS_TARGETS`): it does not
rebuild from anything else.

**Where it lives.** ``system/state/human_layer.jsonl``, LOCAL and gitignored in the code repo
(it holds real, possibly ``perso`` / ``sensible`` fiche content — a ``sensible``-local barrier,
D27 / D71), and protected by the encrypted Kopia backup (D110 / D118). D82's "versioned in git"
lands when the dedicated private truth store (D98) is lit; until then the Kopia PRECIOUS snapshot
is the durable guarantee.

**Snapshots (D82) are deferred, consciously.** D82 pairs the journal with periodic snapshots as a
restore SHORTCUT. At the current human-gesture volume a full replay is instantaneous, so the
shortcut has no value yet; building it now would be lookahead without a known need. The journal —
the part that actually closes the irreversible-loss window — is built here; a checkpoint pass is a
clean later extension keyed off ``_FORMAT`` when the journal grows large enough to matter.

This module lives in ``production`` (not ``stores``) on purpose: it serializes :class:`Fiche`, a
``production`` object, so placing it here keeps the layer hierarchy intact (``production`` may
depend on ``stores`` / ``ports``, never the reverse). Code & docstrings English (D117).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ..ports import Bubble, Domain, GovernanceLabel, Provenance, Sensitivity
from .memory import Fiche

if (
    TYPE_CHECKING
):  # avoid an import cycle — memory.py type-hints HumanLayerJournal in TYPE_CHECKING too
    from pathlib import Path

    from .memory import LivingMemory


def _utcnow_iso() -> str:
    """A wall-clock UTC stamp for a durable record — ISO-8601 with a ``Z`` suffix (like D6's sink)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# --------------------------------------------------------------------------- #
# Faithful Fiche codec — round-trip is an invariant (``decode(encode(f)) == f``).             #
# Nothing is dropped: the human layer is protected by NOT losing a byte of it (D82 / D56).    #
# --------------------------------------------------------------------------- #
def _encode_provenance(prov: Provenance) -> dict[str, Any]:
    """Encode a (recursive) provenance chain — the D54 taint / D19 replay anchor, kept whole."""
    return {
        "origin": prov.origin,
        "produced_by": prov.produced_by,
        "at": prov.at.isoformat(),
        "parents": [_encode_provenance(parent) for parent in prov.parents],
    }


def _decode_provenance(data: dict[str, Any]) -> Provenance:
    return Provenance(
        origin=data["origin"],
        produced_by=data["produced_by"],
        at=datetime.fromisoformat(data["at"]),
        parents=tuple(_decode_provenance(parent) for parent in data["parents"]),
    )


def _encode_label(label: GovernanceLabel) -> dict[str, Any]:
    """Encode the governance label whole — sensitivity by NAME (stable), domains sorted (deterministic)."""
    return {
        "sensitivity": label.sensitivity.name,
        "bubble": str(label.bubble),
        "domains": sorted(str(domain) for domain in label.domains),
        "provenance": _encode_provenance(label.provenance)
        if label.provenance is not None
        else None,
    }


def _decode_label(data: dict[str, Any]) -> GovernanceLabel:
    provenance = data["provenance"]
    return GovernanceLabel(
        sensitivity=Sensitivity[data["sensitivity"]],
        bubble=Bubble(data["bubble"]),
        domains=frozenset(Domain(domain) for domain in data["domains"]),
        provenance=_decode_provenance(provenance) if provenance is not None else None,
    )


def _encode_fiche(fiche: Fiche) -> dict[str, Any]:
    """Encode a fiche whole (content + history sorted for a deterministic, greppable JSON, D6)."""
    return {
        "id": fiche.id,
        "ftype": fiche.ftype,
        "content": sorted(fiche.content),
        "label": _encode_label(fiche.label),
        "state": fiche.state,
        "history": [sorted(version) for version in fiche.history],
    }


def _decode_fiche(data: dict[str, Any]) -> Fiche:
    return Fiche(
        id=data["id"],
        ftype=data["ftype"],
        content=frozenset(data["content"]),
        label=_decode_label(data["label"]),
        state=data["state"],
        history=tuple(frozenset(version) for version in data["history"]),
    )


class HumanLayerJournal:
    """Append-only, replayable journal of Moteur A's human-layer gestures — write-ahead, fail-closed (D82).

    Wired into :class:`~mnemosyne.production.memory.LivingMemory` (which calls
    :meth:`record_validate` / :meth:`record_invalidate` BEFORE mutating RAM); rebuilt at cold start by
    :meth:`replay`. Distinct from :class:`~mnemosyne.stores.journal.IntentJournal` (D105, which rebuilds
    the DERIVED stores from the truth) — this protects the part that does NOT rebuild from anything.

    The append order is the human layer's total order (the D84 tie-break). This assumes SERIALIZED writers
    (Mnémosyne's single-file orchestration, D93 — no concurrent validate / invalidate today); a future
    concurrent writer would need a lock around the check-then-journal-then-mutate of ``validate`` so the RAM
    order cannot diverge from the journal order."""

    #: Event schema version — bumped on any breaking change to the record shape; replay refuses an
    #: unknown ``kind`` rather than silently skip a human gesture (a NEWER format ⇒ fail-closed, D82).
    _FORMAT: int = 1

    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        self._path = path

    def _append(self, event: dict[str, Any]) -> None:
        """Append one event as a JSONL line, flushed and fsync'd to the platter (open-append-close per line).

        Fail-CLOSED (D80 / D82): the parent dir is created if absent, then the line is written, flushed to
        the OS AND ``os.fsync``'d to disk so the record survives a power loss / kernel panic, not merely a
        process crash (the human layer is irreversible, D56 — best-effort is not enough here, unlike the D6
        observability sink). ANY I/O error PROPAGATES to the caller so the human-layer mutation is not
        applied on a failed journal — never a silent swallow (a lost human gesture is unacceptable)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def record_validate(self, fiche: Fiche, *, human_validated: bool) -> None:
        """Durably record a validation BEFORE it reaches RAM — the whole fiche travels (self-contained).

        ``human_validated`` is kept as an AUDIT trace of HOW the gesture cleared (an explicit human gesture
        vs a benign auto-apply, D59-5 / D92); replay restores the VALIDATED state from ``fiche`` itself, so
        the flag is provenance on the record, never replayed control-flow."""
        self._append(
            {
                "v": self._FORMAT,
                "ts": _utcnow_iso(),
                "kind": "validate",
                "human_validated": human_validated,
                "fiche": _encode_fiche(fiche),
            }
        )

    def record_invalidate(self, fiche_id: str) -> None:
        """Durably record an invalidation (bi-temporal close, D60-2) BEFORE it reaches RAM."""
        self._append(
            {
                "v": self._FORMAT,
                "ts": _utcnow_iso(),
                "kind": "invalidate",
                "fiche_id": fiche_id,
            }
        )

    def replay(self, memory: LivingMemory) -> None:
        """Rebuild the human layer from the durable stream, in append order — idempotent (D82 / D84).

        Each ``validate`` restores the whole recorded fiche; each ``invalidate`` closes its id. Replaying
        twice reaches the same state. An absent journal is a NO-OP (a cold, empty human layer). An unknown
        event ``kind`` (a newer format) RAISES rather than silently skip a human gesture (fail-closed).

        **Truncated-final-line recovery.** A crash mid-append can leave the LAST line half-written. Because
        the write is write-ahead (the append returns BEFORE RAM is mutated), a truncated final line is a
        gesture RAM never saw — dropping it is the CORRECT recovery, keeping journal ⇄ RAM consistent (D82).
        So a JSON error is tolerated ONLY on the last non-empty line; a malformed INTERNAL line is real
        corruption and RAISES (never skip a committed gesture in silence — same spirit as unknown-kind)."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return  # no journal yet ⇒ nothing to restore
        lines = raw.splitlines()
        last_nonempty = max((i for i, ln in enumerate(lines) if ln.strip()), default=-1)
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                if idx == last_nonempty:
                    break  # truncated final line ⇒ a never-committed gesture — correct to drop (D82)
                raise  # a malformed INTERNAL line is real corruption — fail-closed, never skip a gesture
            kind = event["kind"]
            if kind == "validate":
                memory._restore_validated(_decode_fiche(event["fiche"]))
            elif kind == "invalidate":
                memory._restore_invalidated(event["fiche_id"])
            else:
                raise ValueError(
                    f"unknown human-layer event kind {kind!r} — refusing to skip a human gesture "
                    "(a newer journal format? bump the reader, never drop a gesture — D82)"
                )
