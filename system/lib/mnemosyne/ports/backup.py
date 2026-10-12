"""Backup (D110 / D118) - asymmetric protection of the one non-reconstructible truth.

The three stores are not equal: ``.md``/git = THE truth; Qdrant + GraphStore =
reconstructible derivatives (D56). The backup strategy inherits that asymmetry,
so it is simple and robust:

* **Precious** (the only thing that does not rebuild) - ``.md``/git, replayable
  snapshots (D76), the graph's human-layer journal (D82), config / policy zone.
* **Derived** - Qdrant / GraphStore: an *opportunistic* backup (saves time),
  NEVER critical; they regenerate from the truth.

Encrypted with **Kopia** (snapshots, dedup, versioned, retention); secrets stay
encrypted (SOPS + age, D81) and the **decryption keys are stored SEPARATELY** -
an encrypted backup nobody can read is worthless. The off-site target is
zero-knowledge encrypted (D118). And the golden rule: *a backup never restored
is not a backup* -> a periodic, automated restore test into a disposable bubble
(D99) followed by the 1-click smoke test (D109).

Restore order: truth first (``.md``/git) -> bootstrap / reindex rebuilds Qdrant ->
journal replay (D82) rebuilds the graph's human layer -> smoke test validates.
Default OSS brick: **Kopia** - see ``system/config/oss_registry.md``
(D110 / D118).

Decisions: D110 (asymmetric backup)  -  D118 (off-site zero-knowledge)  -  D71
(local-only repo, periphery)  -  D56 (asymmetry)  -  D109 (restore = smoke test).
Invariant carried: substrate of 24 (truth as the protected arbiter).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType, Protocol, runtime_checkable

#: A backup snapshot handle.
SnapshotId = NewType("SnapshotId", str)


class BackupClass(Enum):
    """What a snapshot covers (D110). Only ``PRECIOUS`` is critical."""

    PRECIOUS = "precious"  # truth + snapshots (D76) + human-layer journal (D82) + config
    DERIVED = "derived"  # Qdrant / GraphStore - opportunistic, regenerable, never critical


@dataclass(frozen=True, slots=True)
class RestoreReport:
    """Outcome of a restore or a restore TEST (D110 / D109)."""

    snapshot: SnapshotId
    restored_into: str
    smoke_test_passed: bool


@runtime_checkable
class Backup(Protocol):
    """Encrypted, asymmetric backup of the non-reconstructible truth (D110 / D118)."""

    def snapshot(self, klass: BackupClass = BackupClass.PRECIOUS) -> SnapshotId:
        """Take an encrypted snapshot (Kopia). Defaults to the PRECIOUS class -
        the only truth that does not rebuild; keys are stored separately (D110)."""
        ...

    def restore(self, snapshot: SnapshotId, *, into: str) -> RestoreReport:
        """Restore ``snapshot`` ``into`` a location, following the truth-first
        order (``.md``/git -> reindex -> journal replay, D110 / FL3)."""
        ...

    def verify_restore(self) -> RestoreReport:
        """Restore the latest precious snapshot into a disposable bubble (D99) and
        run the 1-click smoke test (D109) - a backup never restored is not a
        backup (D110)."""
        ...
