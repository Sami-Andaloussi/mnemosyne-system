"""connect_kopia — the SOLE user of the Kopia CLI as a :class:`BackupEngine` (D110 / D103).

The snapshot / restore I/O engine behind the :class:`~mnemosyne.runtime.backup.BackupEngine` sub-seam
(③-6b): it drives **Kopia** (Apache-2.0; ``oss_registry.md``) via **subprocess** to take one encrypted
snapshot of the targets and to restore a snapshot into a location. Kopia is a CLI (there is no stable
Python import), so this module isolates the CLI call, not a Python module. Nothing runs at module load;
the actual ``kopia`` invocation is ``# pragma: no cover`` (it needs the binary + a repository, absent in
CI, exercised only at ③ ignition, where the 1-click smoke confronts this glue with the real binary).
The pure id-parser (:func:`_parse_snapshot_id`) is deterministic, brick-free, UNIT-TESTED — it is where
the created snapshot's handle is read out of Kopia's output.

**The engine does I/O ONLY — the barrier is upstream (D100).** The off-site zero-knowledge refusal
(D118) and the asymmetry (only the PRECIOUS non-reconstructible truth is critical, D110) live in the
:class:`~mnemosyne.runtime.backup.KopiaBackup` seam and are applied BEFORE this engine is ever
reached, so a swapped engine can never widen them. This adapter never checks, weakens, or re-decides the
off-site posture; it just runs the snapshot / restore it is told to. A non-zero exit RAISES (never a
false ok) so the seam surfaces the failure — a backup that silently did nothing is worse than a loud
failure (D110: *a backup never restored is not a backup*).

Decisions: D110 (asymmetric encrypted backup) · D118 (off-site zero-knowledge — enforced upstream) ·
D103 (sole importer / isolator) · D126 (brick-free suite, injected runner) · D100 (barrier is the
seam, not the engine). Code & docstrings English (D117); ``precious`` / ``derived`` follow D110.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..ports import BackupClass, SnapshotId

#: A subprocess runner: given the ``kopia`` argv, run it and return captured stdout bytes; a non-zero
#: exit MUST raise (fail-closed — the seam surfaces the failure). Injected in tests / at ignition so
#: the arg-building + id-parsing translation is exercised WITHOUT the ``kopia`` binary (D126).
KopiaRunner = Callable[[list[str]], bytes]


def _snapshot_create_argv(targets: tuple[str, ...]) -> list[str]:
    """Build the ``kopia snapshot create`` argv over ``targets`` (pure, brick-free, UNIT-TESTED).

    ``--json`` so the created snapshot's id is machine-parseable (:func:`_parse_snapshot_id`) rather
    than scraped from human text. Each target path is appended verbatim — the seam already chose the
    PRECIOUS treasure paths (D110); the engine does not re-decide them. The exact ``kopia`` subcommand /
    ``--json`` flag is confirmed at ignition (ALLUMAGE NOTE on :func:`connect_kopia`)."""
    return ["kopia", "snapshot", "create", "--json", *targets]


def _snapshot_restore_argv(snapshot: SnapshotId, into: str) -> list[str]:
    """Build the ``kopia snapshot restore <id> <into>`` argv (pure, brick-free, UNIT-TESTED).

    Restores ``snapshot`` into the ``into`` location the seam passes (truth-first order is the
    seam's concern, D110 / FL3 — the engine just restores what it is told). The exact restore
    subcommand spelling is confirmed at ignition (ALLUMAGE NOTE on :func:`connect_kopia`)."""
    return ["kopia", "snapshot", "restore", str(snapshot), into]


def _parse_snapshot_id(stdout: bytes) -> SnapshotId:
    """Read the created snapshot's id out of ``kopia snapshot create --json`` output (pure, UNIT-TESTED).

    Kopia's ``--json`` create output carries the new snapshot's id. Best-guess accessors, tried in
    order: a top-level ``"id"`` string; else the first element's ``"id"`` if the output is a JSON list;
    else a top-level ``"rootID"`` / ``"root"`` (Kopia sometimes keys the content root there). Fails
    LOUDLY with a ``ValueError`` if no id is found — the seam must never record a fabricated / empty
    handle for a snapshot it cannot later restore (D110). The exact JSON field is confirmed at ignition
    (ALLUMAGE NOTE on :func:`connect_kopia`)."""
    try:
        loaded = json.loads(stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"kopia snapshot output is not valid JSON: {exc}") from exc
    if isinstance(loaded, list):
        loaded = loaded[0] if loaded else {}
    if isinstance(loaded, dict):
        for key in ("id", "rootID", "root"):
            value = loaded.get(key)
            if isinstance(value, str) and value:
                return SnapshotId(value)
    raise ValueError(
        "kopia snapshot output carries no recognisable id (tried id / rootID / root); "
        "the exact field is confirmed at ignition ([USER]) — never record a fabricated handle (D110)"
    )


def connect_kopia(*, runner: KopiaRunner | None = None) -> "_KopiaBackupEngine":
    """Wire the Kopia CLI as a :class:`~mnemosyne.runtime.backup.BackupEngine` (the ``[USER]`` seam, D110).

    Injected by ``real_runtime`` into :class:`~mnemosyne.runtime.backup.KopiaBackup` at ③-6b, which
    applies the off-site zero-knowledge barrier (D118) BEFORE this engine runs. Import-safe with no
    binary present (D126): ``kopia`` only runs when a snapshot / restore method is CALLED. Pass ``runner``
    in tests / at ignition to inject the resolved subprocess callable and keep the arg-building +
    id-parsing exercised without the binary.

    ALLUMAGE NOTE (best-guess CLI, confronted to the real ``kopia`` binary at the smoke ``[USER]``):
    ``kopia snapshot create --json <targets...>`` takes an encrypted snapshot and prints a JSON object
    carrying the new snapshot's ``id`` (Kopia manifests can also expose it as ``rootID`` — parsed
    best-effort); ``kopia snapshot restore <id> <into>`` restores it into a directory; both exit 0 on
    success, non-zero on failure. The repository must already be connected (``kopia repository connect``)
    with its password / encryption configured OUT-OF-BAND (D110) — this adapter never passes a key.
    Confirm at ignition: (1) that ``--json`` on create emits the snapshot id and under which field
    (``id`` vs ``rootID``); (2) the restore subcommand argument order (``restore <id> <target>``); (3)
    that the repository is expected pre-connected (vs a per-call ``--config-file``); (4) that failures
    exit non-zero so the runner raises → the seam surfaces it (never a silent no-op backup). The
    default runner shells out with :mod:`subprocess`, capturing stdout and raising on a non-zero exit."""
    resolved = runner if runner is not None else _default_kopia_runner
    return _KopiaBackupEngine(resolved)


class _KopiaBackupEngine:
    """Thin translation from :class:`~mnemosyne.runtime.backup.BackupEngine` to the Kopia CLI (D103).

    Holds the injected subprocess runner (so this class touches no binary at construction). Both methods
    are brick-free translation (they only build argv, call the injected runner, and parse), so they are
    UNIT-TESTED with an injected fake runner; only :func:`_default_kopia_runner` (the real subprocess) is
    ``pragma: no cover``. The engine does the snapshot / restore I/O and NOTHING else — the off-site
    zero-knowledge barrier (D118) and asymmetry (D110) already ran in the seam (D100). A non-zero exit
    (the runner raising) is NOT swallowed into a false ok: it propagates, so the seam surfaces the
    failure (D110 — a silently-failed backup is worse than a loud one)."""

    __slots__ = ("_run",)

    def __init__(self, runner: KopiaRunner) -> None:
        self._run = runner

    def create_snapshot(self, klass: BackupClass, targets: tuple[str, ...]) -> SnapshotId:
        """Take one encrypted Kopia snapshot of ``targets`` and return its parsed handle.

        ``klass`` (PRECIOUS / DERIVED, D110) is the seam's classification; Kopia snapshots the same
        way either way (the asymmetry is in what the seam chooses to protect and how it treats the
        result, not in the CLI call). Raises (via the runner) on a non-zero exit — never a fabricated
        id for a snapshot that did not take (D110)."""
        stdout = self._run(_snapshot_create_argv(targets))
        return _parse_snapshot_id(stdout)

    def restore_snapshot(self, snapshot: SnapshotId, *, into: str) -> None:
        """Restore ``snapshot`` ``into`` a location; raise on failure, never a false ok.

        The seam drives the truth-first ordering (D110 / FL3) across snapshots and validates the
        rebuilt system by the smoke test (D109); this method just performs the one restore it is asked
        for. A non-zero exit (the runner raising) propagates — a restore that silently did nothing must
        not read as success (*a backup never restored is not a backup*, D110)."""
        self._run(_snapshot_restore_argv(snapshot, into))


def _default_kopia_runner(
    argv: list[str],
) -> bytes:  # pragma: no cover - needs the binary (③ ignition)
    """Run ``argv`` (a ``kopia`` command) and return stdout bytes; raise on a non-zero exit.

    The default :class:`KopiaRunner`: a plain :mod:`subprocess` call with ``check=True`` so a snapshot /
    restore failure becomes a ``CalledProcessError`` the engine lets propagate — the seam surfaces the
    failure rather than recording a false ok (D110)."""
    import subprocess

    completed = subprocess.run(argv, capture_output=True, check=True)  # noqa: S603 - argv is ours, not shell
    return completed.stdout
