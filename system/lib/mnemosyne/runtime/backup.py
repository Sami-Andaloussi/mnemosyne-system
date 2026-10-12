"""KopiaBackup (D110 / D118) — asymmetric, encrypted, restore-tested backup.

The adapter-stub realizing :class:`~mnemosyne.ports.backup.Backup` behind the Kopia default
brick (``oss_registry.md``). It encodes the two rules that make the backup safe, as code:

* **Asymmetry (D110 / D56).** The three stores are not equal. Only the non-reconstructible
  truth is PRECIOUS — ``.md``/git, replayable snapshots (D76), the graph's human-layer journal
  (D82), the config / policy zone; the derived stores (Qdrant / GraphStore) are ``DERIVED``, an
  opportunistic snapshot that never matters because they rebuild from the truth (FL3). So a
  disaster only has to protect ONE treasure.
* **Off-site is zero-knowledge or it does not carry non-public data (D118).** The local-only
  repo versions the ``sensible`` (D71), so a PRECIOUS snapshot holds non-public content; an
  off-site copy of it is refused unless the target is client-side / zero-knowledge encrypted —
  ``sensible`` never leaves in clear (D27 / D66). Keys live OUT-OF-BAND (D110): an encrypted
  backup whose key sits beside it is worthless, and losing the key makes it unrecoverable
  (surfaced as a human prerequisite, D121-E4).

And the golden rule — *a backup never restored is not a backup* — is enforced by
:meth:`KopiaBackup.verify_restore`: restore the latest precious snapshot into a disposable
bubble (D99) and run the 1-click smoke test (D109). Restore order is truth-first (``.md``/git →
reindex → journal replay), exactly FL3 / bootstrap (D94).

Decisions: D110 (asymmetric backup) · D118 (off-site zero-knowledge) · D56 / FL3 (derived
rebuilds) · D71 (local-only versions the sensible) · D99 (disposable restore bubble) · D109
(restore = smoke). Invariant carried: substrate of 24 (truth as the protected arbiter).
Code & docstrings English (D117); ``public`` / ``perso`` / ``sensible`` stay French (D33 / D66).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..ports import BackupClass, ErrorCode, MnemosyneError, RestoreReport, SnapshotId

if TYPE_CHECKING:
    from collections.abc import Callable

    from .bootstrap import Runtime

#: The PRECIOUS treasure (D110): what does NOT rebuild from anything else. Named, not implied.
PRECIOUS_TARGETS: tuple[str, ...] = (
    ".md/git (the truth arbiter, D56)",
    "replayable snapshots (D76)",
    "graph human-layer journal (D82) — system/state/human_layer.jsonl",
    "system/config policy zone (SE4)",
)


class BackupRefused(MnemosyneError):
    """A backup would place non-public data on a non-zero-knowledge off-site target — refused.

    Fail-closed like a Guard denial (``DENIED``): the off-site copy is encrypted client-side or
    it carries no ``sensible`` — never ``sensible`` in clear off the machine (D118 / D27 / D66)."""

    code = ErrorCode.DENIED


@dataclass(frozen=True, slots=True)
class OffSiteTarget:
    """An off-site backup destination and its encryption posture (D118).

    ``encrypted`` + ``zero_knowledge`` (client-side, the provider sees only opaque blobs) is the
    only posture allowed to receive non-public data; ``keys_stored_separately`` records that the
    decryption key is kept out-of-band (D110) — the barrier is on the target, not on trust."""

    name: str
    encrypted: bool = False
    zero_knowledge: bool = False
    keys_stored_separately: bool = False

    def may_receive_non_public(self) -> bool:
        """Whether this target may hold ``perso`` / ``sensible`` blobs (D118).

        The machine-verifiable half of the barrier: client-side zero-knowledge encryption (the
        provider sees only opaque blobs). Key hygiene — ``keys_stored_separately`` (D110) — is a
        HUMAN prerequisite the build cannot enforce, surfaced as a FLAG (D121-E4), not a code
        gate: a key kept beside the blob defeats the backup, but that is caught by the
        prerequisite FLAG, not here."""
        return self.encrypted and self.zero_knowledge


@runtime_checkable
class BackupEngine(Protocol):
    """The snapshot / restore I/O behind the asymmetric barrier (the Kopia CLI at ③-6b).

    A sub-seam of :class:`~mnemosyne.ports.backup.Backup` (like the runner's ``GenerationBackend``):
    it does the actual encrypted snapshot + restore, NOTHING else. The SECURITY barrier — the off-site
    zero-knowledge refusal (D118) and the asymmetry (only the PRECIOUS truth is critical, D110) — lives
    in the :class:`KopiaBackup` couture and is applied BEFORE this engine is ever reached, so a swapped
    engine can never widen it (D100)."""

    def create_snapshot(self, klass: BackupClass, targets: tuple[str, ...]) -> SnapshotId:
        """Take one encrypted snapshot of ``targets`` and return its handle."""
        ...

    def restore_snapshot(self, snapshot: SnapshotId, *, into: str) -> None:
        """Restore ``snapshot`` ``into`` a location (truth-first); raise on failure, never a false ok."""
        ...


class _StubBackupEngine:
    """The in-process default :class:`BackupEngine` (D126-green): mints deterministic ids, does NO real
    I/O — so the suite runs with no Kopia CLI installed. ``real_runtime`` injects the real
    ``connect_kopia()`` engine at ③-6b; the restore is validated by the smoke test either way (D109)."""

    __slots__ = ("_seq",)

    def __init__(self) -> None:
        self._seq = 0

    def create_snapshot(self, klass: BackupClass, targets: tuple[str, ...]) -> SnapshotId:
        self._seq += 1
        return SnapshotId(f"kopia-{klass.value}-{self._seq}")

    def restore_snapshot(self, snapshot: SnapshotId, *, into: str) -> None:
        return (
            None  # no real restore in-process; the smoke test (D109) validates the rebuilt system
        )


class KopiaBackup:
    """Encrypted, asymmetric backup of the non-reconstructible truth (D110 / D118).

    Realizes :class:`~mnemosyne.ports.backup.Backup`. Construct with an optional
    :class:`OffSiteTarget` (absent ⇒ local-only, D71), whether the treasure holds non-public data
    (default ``True``, fail-safe — the repo versions the ``sensible``, D71), and an optional
    :class:`BackupEngine` (absent ⇒ the in-process stub, so the suite runs with no Kopia CLI; ③-6b
    injects the real engine). The off-site barrier is checked on every :meth:`snapshot` BEFORE the
    engine runs; :meth:`verify_restore` proves the backup by restoring + smoke-testing it."""

    __slots__ = (
        "_off_site",
        "_contains_non_public",
        "_engine",
        "_last_precious",
        "_restore_runtime",
    )

    def __init__(
        self,
        *,
        off_site: OffSiteTarget | None = None,
        contains_non_public: bool = True,
        engine: BackupEngine | None = None,
        restore_runtime: Callable[[str], Runtime] | None = None,
    ) -> None:
        self._off_site = off_site
        self._contains_non_public = contains_non_public
        self._engine: BackupEngine = engine if engine is not None else _StubBackupEngine()
        self._last_precious: SnapshotId | None = None
        #: Builds the smoke's runtime FROM the restored location (audit ③-7 M1). ``real_runtime`` injects a
        #: from-path factory at ignition so the restore proof exercises the RESTORED tree; absent (brick-
        #: free) the smoke runs the in-memory pipeline, proving the mechanism (D109 / D110).
        self._restore_runtime = restore_runtime

    def snapshot(self, klass: BackupClass = BackupClass.PRECIOUS) -> SnapshotId:
        """Take an encrypted Kopia snapshot; PRECIOUS by default (the only critical class, D110).

        Fail-closed off-site barrier (D118): if an off-site target is configured and the treasure
        holds non-public data, the target MUST be zero-knowledge encrypted — else
        :class:`BackupRefused`. ``contains_non_public`` is the caller's honest claim about the
        payload (default ``True``, fail-safe); at ③ it derives from the real content / store — so a
        ``DERIVED`` snapshot of ``sensible`` embeddings is protected by the same barrier, not by a
        flag. ``DERIVED`` snapshots are opportunistic and never critical (they rebuild from the
        truth, FL3). Keys are stored separately (D110), never inside the blob."""
        if (
            self._off_site is not None
            and self._contains_non_public
            and not self._off_site.may_receive_non_public()
        ):
            raise BackupRefused(
                f"off-site target {self._off_site.name!r} is not zero-knowledge encrypted; "
                "non-public data never leaves in clear (D118 / D27 / D66)"
            )
        # barrier cleared → the engine does the actual encrypted snapshot (the stub in-process, the real
        # Kopia CLI at ③-6b). PRECIOUS protects the named non-reconstructible treasure (D110).
        sid = self._engine.create_snapshot(klass, PRECIOUS_TARGETS)
        if klass is BackupClass.PRECIOUS:
            self._last_precious = sid
        return sid

    def restore(self, snapshot: SnapshotId, *, into: str) -> RestoreReport:
        """Restore ``snapshot`` ``into`` a location, truth-first, then validate by smoke (D110).

        Order (FL3 / D94): the truth (``.md``/git) is restored first, then bootstrap / reindex
        rebuilds Qdrant and the journal replay (D82) rebuilds the graph's human layer — the
        derived stores are never restored as sources (D56). The rebuilt system is validated by
        the 1-click smoke test (D109); ``smoke_test_passed`` carries its verdict.

        **The proof reads the RESTORED tree (audit ③-7 M1).** The smoke runs against the runtime the
        injected ``restore_runtime`` factory builds FROM ``into`` — so at ignition it exercises the
        actually-restored bytes, not an unrelated fresh stub (a backup restored but never READ is not
        proven, D110). Brick-free the factory is absent and the smoke runs the in-memory pipeline,
        proving the MECHANISM (round-trip fidelity is proven at ignition, when ``real_runtime`` supplies
        the from-path factory). Fail-closed: a factory that cannot rebuild the runtime from the restored
        tree is a FAILED restore (``smoke_test_passed`` False), never a false ok (D109 / D100)."""
        self._engine.restore_snapshot(snapshot, into=into)  # real I/O at ③-6b; the stub is a no-op
        # lazy import: the backup ← smoke ← bootstrap ← backup cycle (bootstrap assembles the backup at
        # ③-6) is broken here, where run_smoke_test is only needed at restore time, not module load.
        from .smoke import run_smoke_test

        try:
            restored = self._restore_runtime(into) if self._restore_runtime is not None else None
        except Exception:  # noqa: BLE001 - a restore whose runtime cannot be rebuilt is NOT proven (M1)
            return RestoreReport(snapshot=snapshot, restored_into=into, smoke_test_passed=False)
        # None (brick-free) ⇒ the smoke bootstraps its own in-memory runtime (mechanism proof); a factory
        # ⇒ the smoke runs against the RESTORED tree (round-trip proof at ignition), FL3 truth-first replay.
        report = run_smoke_test(restored)
        return RestoreReport(snapshot=snapshot, restored_into=into, smoke_test_passed=report.passed)

    def verify_restore(self) -> RestoreReport:
        """Prove the backup: restore the latest precious snapshot into a disposable target (D99)
        and run the smoke test (D109) — *a backup never restored is not a backup* (D110).

        Ensures a precious snapshot exists (taking one if needed), then restores it into a throwaway
        target and smoke-tests the RESTORED result (via the ``restore_runtime`` factory, see
        :meth:`restore`); nothing touches the live system. IGNITION ([OPERATOR]): at ignition
        ``real_runtime`` injects a from-path ``restore_runtime`` factory and the Kopia engine restores
        into a real disposable directory (the ``into`` path), so the smoke exercises the restored tree
        end-to-end over the real bricks — brick-free this proves the wiring, not the round-trip."""
        snapshot = self._last_precious if self._last_precious is not None else self.snapshot()
        return self.restore(
            snapshot, into="disposable-restore-verify"
        )  # a path-safe disposable target
