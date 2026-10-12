"""Guarded heavy run (Q1) — the ONE seam the heavy CLI entrypoints wrap their work in.

Composes the two Q1 bounds so "one heavy thing at a time, without crashing the resources" holds for the
REAL pipeline (``make ingest`` / ``figures-enrich`` / ``youtube-ingest``), which today cold-start
multi-GB models OUTSIDE any coordination:

* a HEALTH pre-flight — :func:`~mnemosyne.runtime.health.may_start_heavy_run`, the single home of the
  rule: a CRITICAL disk REFUSES the run fail-closed (its writes would be unsafe); a DEGRADED RAM / thermal
  only WARNS (the run still goes local, consistent with ``graceful_degradation``, throttled separately);
* a cross-process CONCURRENCY lock — :class:`~mnemosyne.guard.heavy_lock.HeavyRunLock` (``[bounds]
  concurrency = 1`` made cross-process, D95): a second heavy run finds the lock held and is refused
  fail-closed (:class:`~mnemosyne.guard.heavy_lock.HeavyRunBusy`), naming the current holder.

**Order matters (fail-fast, cheap-before-expensive).** The health pre-flight runs FIRST, then the lock is
taken — so a full disk refuses BEFORE a multi-GB model is loaded, and the lock is only held once the run is
truly cleared to proceed.

**Zero-regression by construction.** Both bounds are OPT-IN. The headless run functions take
``gate=nullcontext()`` by default (their unit tests + notebook callers are untouched — no lock, no probe);
only the CLI ``main()`` — the actual ``make X`` seam — passes a real :func:`guarded_heavy_run`. So the
coordination lands exactly at the command boundary the user cares about, and nothing else changes.

Code & docstrings English (D117); user-facing text French (D33). Decisions: D95 / invariant 26 (one heavy
run at a time) · D111 (health pre-flight) · D78 / invariant 16 (fail-closed) · D100 (fail-safe).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from ..guard.heavy_lock import DEFAULT_LOCK_PATH, HeavyRunLock
from .health import may_start_heavy_run

if TYPE_CHECKING:
    from ..guard.heavy_lock import Locker
    from ..ports import HealthReport


class HeavyRunRefused(RuntimeError):
    """Raised fail-closed when the health pre-flight forbids STARTING a heavy run (e.g. disk CRITICAL, D111).

    Distinct from :class:`~mnemosyne.guard.heavy_lock.HeavyRunBusy` (which means "another heavy run holds the
    lock"): this means "the machine itself is not in a state where a heavy run may safely begin."""


@contextmanager
def guarded_heavy_run(
    name: str,
    *,
    health: Callable[[], HealthReport] | None = None,
    lock: HeavyRunLock | None = None,
    lock_path: Path | str = DEFAULT_LOCK_PATH,
    locker: Locker | None = None,
    on_notice: Callable[[str], None] | None = None,
) -> Iterator[None]:
    """Context manager gating a heavy run: health pre-flight, then the cross-process concurrency lock.

    * ``health`` (optional) — a callable returning the current :class:`~mnemosyne.ports.HealthReport`. When
      given, :func:`~mnemosyne.runtime.health.may_start_heavy_run` decides: a refusal raises
      :class:`HeavyRunRefused` BEFORE the lock or any model load; a warning is surfaced via ``on_notice`` and
      the run proceeds. ``None`` → no health gate (backward-compatible skeleton path).
    * the lock — ``lock`` (an injected :class:`HeavyRunLock`) if given, else one built on ``lock_path`` (and
      an optional injected ``locker`` mechanism, for the suite). Holding it means one heavy run at a time; a
      second raises :class:`~mnemosyne.guard.heavy_lock.HeavyRunBusy`. Released on exit even if the body
      raises (``with`` on the lock).

    ``on_notice`` receives the DEGRADED warning string (the CLI prints it); default is silent. Yields ``None``
    — the caller's ``with`` body is the heavy section."""
    if health is not None:
        ok, reason = may_start_heavy_run(health())
        if not ok:
            raise HeavyRunRefused(reason)
        if reason and on_notice is not None:
            on_notice(reason)  # DEGRADED: surface the warning, the run still proceeds (D111)
    run_lock = lock if lock is not None else HeavyRunLock(lock_path, name, locker=locker)
    with run_lock:
        yield


def default_health_probe() -> Callable[
    [], HealthReport
]:  # pragma: no cover - real hardware read (machine-only)
    """The real hardware-backed health probe the CLI passes as ``guarded_heavy_run(health=...)`` (D111 / D95).

    The DISK read is STDLIB (:func:`shutil.disk_usage`) and needs no brick, so the CRITICAL-disk refusal —
    the one true SAFETY gate — always holds. The RAM read needs ``psutil``; it is wired only when the brick
    is present, and a missing / unreadable ``psutil`` degrades fail-safe to the default-healthy RAM reader
    (RAM is a DEGRADED *warning* that lets the run proceed anyway, never a refusal — so skipping it loses a
    hint, not a safeguard) rather than crashing the CLI with an ``ImportError`` traceback. Thermal stays the
    default-healthy reader until its M4 source is confirmed at ignition (health_probe.py's own note). Reads
    only aggregate hardware stats, no content (invariant 22)."""
    from .health import HealthMonitor
    from .health_probe import SystemHardwareProbe

    try:
        from .health_probe import psutil_ram_reader

        ram_reader = psutil_ram_reader()  # imports psutil lazily; a missing brick raises HERE
    except Exception:  # noqa: BLE001 - psutil absent ⇒ skip only the RAM warning; the disk CRITICAL gate stands
        ram_reader = None
    probe = SystemHardwareProbe(
        ram_reader=ram_reader
    )  # disk = stdlib (real), thermal = default-healthy
    return HealthMonitor(hardware=probe).report
