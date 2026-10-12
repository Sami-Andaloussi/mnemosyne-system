"""Replayable snapshots (D76 corollary 1, invariant 12) - the protected replay store.

Every model call leaves a *replayable snapshot*: the COMPLETE input (prompt + injected
context) and the output, frozen so the call can be REPLAYED or COMPARED (D76-(1)). Two
structural facts, both realized here:

* **Captured at the frontier, held PROTECTED.** A snapshot may contain ``sensible`` -
  so it lives in a SEPARATE, protected store (SE4), NEVER in the greppable JSONL logs
  (that separation is the other half of invariant 12; the log side is
  :class:`~mnemosyne.runtime.observability.LocalObservability`). The ``.md``/git backup
  protects this store as PRECIOUS (D110 / :class:`~mnemosyne.ports.backup.BackupClass`).
* **Per call, replayable.** :meth:`SnapshotStore.replay` reproduces the frozen INPUT of
  a past call - the anchor a shadow-runner / equivalence harness (D75, invariant 11)
  builds a frozen golden set from, and the witness that "I do not know" ≠ "it never ran".

This is NOT :class:`~mnemosyne.ports.backup.SnapshotId` (that is Kopia's *backup* handle,
D110). A replay snapshot is a different concept: the frozen trace of one model call, keyed
by a per-call :data:`ReplayId`.

**On-disk backend (CF3 / D76, (3)-11).** :class:`SnapshotStore` keeps the SAME shape it has
always had (:meth:`capture` / :meth:`get` / :meth:`replay` / :meth:`all_ids` / :meth:`count`)
over an injected primitive backend (D126, mirroring :mod:`.graph_ladybug` /
:mod:`.keyword_tantivy`): ``base_path=None`` is the in-memory dict every caller and test
already relies on (unchanged - the RAM path is not a fallback, it stays exactly what it
was); a path swaps in :class:`_DiskSnapshotBackend`, one JSON file per snapshot under a
derived, reconstructible folder (gitignored, ``knowledge/.snapshotstore/`` - the same
convention as ``.vectorstore`` / ``.keywordstore`` / ``.graphstore``). Unlike those other
brick adapters, there is no external engine to wrap here (pure stdlib ``json`` /
``pathlib``), so the disk backend is exercised by the ordinary unit suite, not only the
1-click smoke. Retention (:meth:`SnapshotStore.count` bounded by ``retain_last``) is a
simple, conservative, NON-destructive cap - the oldest snapshot files past the bound are
pruned only on a new :meth:`capture`, never on read (D78 / D112 named bound). Code &
docstrings English (D117); ``public`` / ``perso`` / ``sensible`` keep their French tokens
(D33 / D66).

Decisions: D76-(1) (replayable snapshot, captured by the Guard)  -  D71 / D111 (no
``sensible`` in greppable logs)  -  D75 (frozen golden set built from snapshots)  -  D110
(the store is PRECIOUS, non-reconstructible)  -  D78 / D112 (retention is a named, active
bound)  -  D126 (primitive-backend decoupling, no brick to wrap). Invariant carried: 12
(substrate of 11).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import NewType, Protocol

from ..config import Policy
from ..ports import Bubble, Domain, Envelope, GovernanceLabel, Provenance, Sensitivity

#: A per-call handle for one replay snapshot (distinct from the Backup ``SnapshotId``).
ReplayId = NewType("ReplayId", str)

#: Reverse of :attr:`Sensitivity.token`, to rebuild the enum from a stored payload.
_SENSITIVITY_BY_TOKEN = {s.token: s for s in Sensitivity}


def _utcnow() -> datetime:
    """Timezone-aware UTC now (D84: time is explicit, never naive)."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ReplaySnapshot:
    """The frozen trace of ONE model call (D76-(1)): its full input and its output.

    Immutable: a snapshot is a fact about a past call, never edited. ``prompt`` and
    ``output`` are governed :class:`Envelope`\\ s, so the snapshot carries the same
    sensitivity it must be protected at - the store keeps it local (never a greppable
    log). ``context`` is the extra material injected into the call (retrieved fiches,
    system framing); ``constraint`` records the grammar a structured call was bound to
    (invariant 27)."""

    id: ReplayId
    model_id: str
    prompt: Envelope[str]
    output: Envelope[str]
    context: tuple[str, ...] = ()
    constraint: str | None = None
    at: datetime = field(default_factory=_utcnow)


def _provenance_to_primitive(prov: Provenance | None) -> dict | None:
    """Recursively flatten a :class:`Provenance` chain to JSON-safe primitives (D76 / D19).

    ``parents`` is itself a tuple of ``Provenance``, so the taint chain is walked all the
    way down - a round-trip through disk must not truncate it (invariant 12: replay is
    FAITHFUL, not a lossy summary)."""
    if prov is None:
        return None
    return {
        "origin": prov.origin,
        "produced_by": prov.produced_by,
        "at": prov.at.isoformat(),
        "parents": [_provenance_to_primitive(p) for p in prov.parents],
    }


def _provenance_from_primitive(raw: dict | None) -> Provenance | None:
    """Inverse of :func:`_provenance_to_primitive` - rebuild the full parent chain."""
    if raw is None:
        return None
    return Provenance(
        origin=raw["origin"],
        produced_by=raw["produced_by"],
        at=datetime.fromisoformat(raw["at"]),
        parents=tuple(_provenance_from_primitive(p) for p in raw["parents"]),
    )


def _label_to_primitive(label: GovernanceLabel) -> dict:
    """Flatten a :class:`GovernanceLabel` to JSON-safe primitives, provenance included -
    a disk snapshot carries the FULL label, unlike a reconstructible derivative index
    (:mod:`.keyword_tantivy`) which may drop provenance (D56 vs. D110: this store is
    PRECIOUS, not a rebuildable projection)."""
    return {
        "sensitivity": label.sensitivity.token,
        "bubble": str(label.bubble),
        "domains": sorted(str(d) for d in label.domains),
        "provenance": _provenance_to_primitive(label.provenance),
    }


def _label_from_primitive(raw: dict) -> GovernanceLabel:
    """Inverse of :func:`_label_to_primitive`."""
    return GovernanceLabel(
        sensitivity=_SENSITIVITY_BY_TOKEN[raw["sensitivity"]],
        bubble=Bubble(raw["bubble"]),
        domains=frozenset(Domain(d) for d in raw.get("domains", ())),
        provenance=_provenance_from_primitive(raw.get("provenance")),
    )


def _envelope_to_primitive(env: Envelope[str]) -> dict:
    """Flatten an ``Envelope[str]`` (payload + label) to JSON-safe primitives."""
    return {"payload": env.payload, "label": _label_to_primitive(env.label)}


def _envelope_from_primitive(raw: dict) -> Envelope[str]:
    """Inverse of :func:`_envelope_to_primitive`."""
    return Envelope(payload=raw["payload"], label=_label_from_primitive(raw["label"]))


def _snapshot_to_primitive(snap: ReplaySnapshot) -> dict:
    """Flatten a whole :class:`ReplaySnapshot` to a JSON-safe dict (the on-disk row)."""
    return {
        "id": str(snap.id),
        "model_id": snap.model_id,
        "prompt": _envelope_to_primitive(snap.prompt),
        "output": _envelope_to_primitive(snap.output),
        "context": list(snap.context),
        "constraint": snap.constraint,
        "at": snap.at.isoformat(),
    }


def _snapshot_from_primitive(raw: dict) -> ReplaySnapshot:
    """Inverse of :func:`_snapshot_to_primitive` - a faithful reload (D76-(1) replayability)."""
    return ReplaySnapshot(
        id=ReplayId(raw["id"]),
        model_id=raw["model_id"],
        prompt=_envelope_from_primitive(raw["prompt"]),
        output=_envelope_from_primitive(raw["output"]),
        context=tuple(raw.get("context", ())),
        constraint=raw.get("constraint"),
        at=datetime.fromisoformat(raw["at"]),
    )


class SnapshotBackend(Protocol):
    """The primitive surface :class:`SnapshotStore` needs from a backend (D126).

    Mirrors :class:`~mnemosyne.stores.graph_ladybug.GraphBackend` /
    :class:`~mnemosyne.stores.keyword_tantivy.KeywordBackend`: a small, primitive seam so
    :class:`SnapshotStore`'s capture/replay/append-only shape is unit-tested against either
    backend without caring which one is behind it. Rows are exchanged as already-frozen
    :class:`ReplaySnapshot`\\ s (no engine type leaks through)."""

    def append(self, snap: ReplaySnapshot) -> None:
        """Record ``snap`` (its ``id`` is already unique - assigned by the store)."""
        ...

    def get(self, rid: ReplayId) -> ReplaySnapshot:
        """The full snapshot for ``rid``; unknown id raises ``KeyError``."""
        ...

    def all_ids(self) -> tuple[ReplayId, ...]:
        """Every id, in capture order."""
        ...


class _InMemorySnapshotBackend:
    """The RAM backend (D126 default) - exactly the dict + list ``SnapshotStore`` has
    always used. No behaviour change: this is the same store every existing caller and
    test already exercises, only lifted into the injected-backend shape."""

    __slots__ = ("_snapshots", "_order")

    def __init__(self) -> None:
        self._snapshots: dict[ReplayId, ReplaySnapshot] = {}
        self._order: list[ReplayId] = []

    def append(self, snap: ReplaySnapshot) -> None:
        self._snapshots[snap.id] = snap
        self._order.append(snap.id)

    def get(self, rid: ReplayId) -> ReplaySnapshot:
        return self._snapshots[rid]

    def all_ids(self) -> tuple[ReplayId, ...]:
        return tuple(self._order)


class _DiskSnapshotBackend:
    """On-disk backend (CF3 / D76, (3)-11) - one JSON file per snapshot under ``base_path``.

    **Location.** A derived, reconstructible folder (D56 caveat: reconstructible only in the
    sense that losing it loses REPLAY history, not the truth itself - D110 still backs it up
    as PRECIOUS); the caller decides the path (:func:`connect_snapshot_store` defaults to
    ``knowledge/.snapshotstore``, the same convention as ``.vectorstore`` / ``.keywordstore``
    / ``.graphstore``, all gitignored - never versioned, never synced by iCloud when that
    folder itself sits under an excluded root).

    **Retention (D78 / D112, non-destructive by default).** ``retain_last=None`` keeps
    everything (append-only, matching the RAM backend); a positive bound prunes the OLDEST
    files past the cap on every :meth:`append` - never on read, never more than one snapshot
    over the bound at a time, so a crash mid-write never destroys more than the newest entry.

    **Replayable.** Capture order is NOT filesystem mtime (unreliable across filesystems) -
    it is carried explicitly in a small ``_order.json`` index, so :meth:`all_ids` reloads in
    the exact order calls happened even after a process restart (round-trip fidelity)."""

    _ORDER_FILE = "_order.json"

    __slots__ = ("_base_path", "_retain_last")

    def __init__(self, base_path: Path, *, retain_last: int | None = None) -> None:
        if retain_last is not None and retain_last < 1:
            raise ValueError(f"retain_last must be >= 1 or None, got {retain_last}")
        self._base_path = base_path
        self._retain_last = retain_last
        self._base_path.mkdir(parents=True, exist_ok=True)

    def append(self, snap: ReplaySnapshot) -> None:
        order = list(self._read_order())
        order.append(str(snap.id))
        self._write_file(snap.id, _snapshot_to_primitive(snap))
        # Retention (D78 / D112): prune the oldest past the bound, non-destructive by
        # default (retain_last=None never prunes). Pruned AFTER the new file lands, so a
        # crash mid-append leaves the bound exceeded by at most one - never a gap.
        if self._retain_last is not None:
            while len(order) > self._retain_last:
                stale = ReplayId(order.pop(0))
                self._path_for(stale).unlink(missing_ok=True)
        self._write_order(order)

    def get(self, rid: ReplayId) -> ReplaySnapshot:
        try:
            raw = json.loads(self._path_for(rid).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(rid) from None
        return _snapshot_from_primitive(raw)

    def all_ids(self) -> tuple[ReplayId, ...]:
        return tuple(ReplayId(rid) for rid in self._read_order())

    def _path_for(self, rid: ReplayId) -> Path:
        return self._base_path / f"{rid}.json"

    def _read_order(self) -> list[str]:
        order_path = self._base_path / self._ORDER_FILE
        if not order_path.exists():
            return []
        return list(json.loads(order_path.read_text(encoding="utf-8")))

    def _write_order(self, order: list[str]) -> None:
        (self._base_path / self._ORDER_FILE).write_text(
            json.dumps(order, ensure_ascii=False), encoding="utf-8"
        )

    def _write_file(self, rid: ReplayId, payload: dict) -> None:
        self._path_for(rid).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _seq_of(rid: ReplayId) -> int:
    """The numeric suffix of an ``"r<n>"`` id (the only shape :meth:`SnapshotStore.capture`
    mints) - used ONLY to resume the sequence past a re-opened disk folder's highest id."""
    return int(str(rid)[1:])


class SnapshotStore:
    """The protected replay store (D76-(1) / SE4): one snapshot per model call, replayable.

    Holds the FULL input/output of every call - including ``sensible`` - so it must stay
    local and protected, never a greppable log (invariant 12). Append-only and
    non-destructive (invariant 2): a snapshot is never overwritten or erased (retention, when
    configured, prunes only the OLDEST past a conservative bound - D78/D112 - never the
    live window a shadow-runner / golden-set build (D75) reads from).

    ``base_path=None`` (the default) is the in-memory store every existing caller - the
    runner (:mod:`.runner`), the golden-set builder (:mod:`.crystallise`), bootstrap
    (:mod:`.bootstrap`) - already relies on; behaviour is UNCHANGED (CF3 / D76). Passing a
    path swaps in the on-disk backend (:class:`_DiskSnapshotBackend`) behind the exact same
    ``capture`` / ``get`` / ``replay`` / ``all_ids`` / ``count`` shape (D126) - no caller,
    and no existing test, needs to change.

    Re-opening an existing disk folder resumes the sequence PAST the highest id already on
    disk (never re-issuing ``r1`` into an occupied slot) - a fresh process reloading a
    populated store stays collision-free, the other half of "replayable" alongside a
    faithful :meth:`get` round-trip."""

    __slots__ = ("_backend", "_seq")

    def __init__(
        self,
        *,
        base_path: str | Path | None = None,
        retain_last: int | None = None,
    ) -> None:
        self._backend: SnapshotBackend = (
            _InMemorySnapshotBackend()
            if base_path is None
            else _DiskSnapshotBackend(Path(base_path), retain_last=retain_last)
        )
        # Resume the sequence past whatever this backend already holds (a re-opened disk
        # folder), so a fresh id never collides with one already on disk. ids are "r<seq>"
        # (see capture); parsing the numeric suffix of the highest existing one is exact
        # because that is the ONLY shape this store ever mints.
        self._seq = max((_seq_of(rid) for rid in self._backend.all_ids()), default=0)

    @classmethod
    def from_policy(cls, policy: Policy, *, base_path: str | Path | None = None) -> SnapshotStore:
        """Build a store whose retention bound is read from the protected zone (D78 / D112),
        mirroring :meth:`~mnemosyne.guard.bounds.BoundedScheduler.from_policy`: the ceiling is
        *configured* (``[bounds] snapshot_retain_last`` in ``policy.toml``), not hard-coded.
        ``base_path=None`` still keeps the RAM backend (retention is then moot - the in-memory
        backend is append-only, unbounded, exactly as before CF3); pass a path to persist AND
        bound at once."""
        return cls(base_path=base_path, retain_last=policy.bound("snapshot_retain_last"))

    def capture(
        self,
        *,
        model_id: str,
        prompt: Envelope[str],
        output: Envelope[str],
        context: tuple[str, ...] = (),
        constraint: str | None = None,
    ) -> ReplayId:
        """Freeze one model call and return its :data:`ReplayId` (D76-(1)).

        Each call gets its OWN snapshot (per-call id), so the store size equals the
        number of calls - the witness a call actually happened, kept out of the logs."""
        self._seq += 1
        rid = ReplayId(f"r{self._seq}")
        self._backend.append(
            ReplaySnapshot(
                id=rid,
                model_id=model_id,
                prompt=prompt,
                output=output,
                context=context,
                constraint=constraint,
            )
        )
        return rid

    def get(self, rid: ReplayId) -> ReplaySnapshot:
        """The full frozen snapshot (input + output); unknown id raises ``KeyError``."""
        return self._backend.get(rid)

    def replay(self, rid: ReplayId) -> Envelope[str]:
        """Reproduce the frozen INPUT of a past call, to re-run or compare (D76-(1) / D75).

        Returns the exact prompt envelope the call was made with - the anchor a golden
        set (invariant 11) is frozen from, protected with its original label."""
        return self._backend.get(rid).prompt

    def all_ids(self) -> tuple[ReplayId, ...]:
        """Every replay id, in capture order (one per model call; bounded by retention
        when the disk backend is configured with ``retain_last`` - D78)."""
        return self._backend.all_ids()

    def count(self) -> int:
        """Number of captured calls currently held (== ``len(all_ids())``; append-only,
        modulo retention pruning the oldest - never the live window, D78/D112)."""
        return len(self._backend.all_ids())


def connect_snapshot_store(
    *, base_path: str | Path | None = None, retain_last: int | None = None
) -> SnapshotStore:
    """Build a :class:`SnapshotStore` over the on-disk backend (CF3 / D76, (3)-11).

    ``base_path=None`` keeps snapshots in RAM (the D126 default, unchanged skeleton
    behaviour); a path persists them under ``base_path`` - conventionally
    ``knowledge/.snapshotstore`` (gitignored, reconstructible-derivative convention shared
    with ``.vectorstore`` / ``.keywordstore`` / ``.graphstore``). Unlike
    :func:`~mnemosyne.stores.graph_ladybug.connect_ladybug` and its siblings, there is no
    external brick to lazy-import here (pure stdlib), so this factory - and the disk
    backend behind it - runs in the ordinary unit suite, not only the 1-click smoke.
    ``retain_last`` is the conservative, non-destructive retention bound (D78 / D112):
    ``None`` (default) keeps every snapshot ever captured. Prefer
    :meth:`SnapshotStore.from_policy` to read that bound from the protected zone instead of
    hard-coding it at each call site."""
    return SnapshotStore(base_path=base_path, retain_last=retain_last)
