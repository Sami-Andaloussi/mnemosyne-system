"""SystemHardwareProbe — the real hardware signals behind the :class:`HardwareProbe` port (D111 / D103).

The concrete probe that swaps in for :class:`~mnemosyne.runtime.health.StubHardwareProbe` at ③-6b,
realizing :class:`~mnemosyne.runtime.health.HardwareProbe` (``disk_ok`` / ``ram_ok`` / ``thermal_ok``).
Two natures of signal, deliberately split:

* **Disk is STDLIB, not a brick.** :meth:`disk_ok` reads free space via :func:`shutil.disk_usage` — a
  real, dependency-free measurement — so it is NOT ``pragma``'d and IS unit-tested (the disk-full →
  ``CRITICAL`` path drives the couture's circuit-breakers, so its math must be proven). ``disk_usage`` is
  injectable so the ratio arithmetic is tested against synthetic totals.
* **RAM / thermal are a BRICK (``psutil`` + IOKit).** :meth:`ram_ok` / :meth:`thermal_ok` read from
  ``psutil`` (BSD; ``oss_registry.md``) and, for M4 thermal state, macOS IOKit — imported LAZILY so this
  module is import-safe without the brick (D126). Their brick-touching readers are ``# pragma: no
  cover``; the probe accepts INJECTABLE readers that DEFAULT to healthy until the real reads are wired at
  ignition, and a reader that RAISES is treated fail-safe as NOT-ok (a probe that cannot read pressure
  assumes pressure — D100 / D111).

**Fail-safe is the doctrine (D111).** The health couture folds these into a state where a full disk is
``CRITICAL`` (breaks store AND backup writes) and RAM / thermal pressure is ``DEGRADED``. This probe only
REPORTS; it decides no conduct. When it cannot measure, it reports the WORSE value, never a reassuring
one — so a mis-wired reader can only surface a false alarm, never hide a real one.

Decisions: D111 (health dashboard + graceful degradation) · D95 (RAM juggling) · D103 (sole importer of
psutil / IOKit) · D126 (brick-free suite, injected readers) · D100 (unknown ⇒ the prudent value). Code &
docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable

#: A disk-usage reader: given a path, return an object with ``.free`` and ``.total`` byte counts (the
#: :func:`shutil.disk_usage` shape). STDLIB — real, injectable for tests, NOT a brick.
DiskUsageReader = Callable[[str], object]

#: A RAM reader: return the fraction of memory currently USED in ``[0.0, 1.0]`` (higher = more pressure).
#: Defaults to a healthy reader until ``psutil`` is wired; a reader that raises ⇒ NOT-ok (fail-safe).
RamReader = Callable[[], float]

#: A thermal reader: return ``True`` when the machine is thermally OK (NOT throttling). Defaults to
#: healthy until the IOKit read is wired; a reader that raises ⇒ NOT-ok (fail-safe).
ThermalReader = Callable[[], bool]

#: Default free-space ratio below which the disk is considered full (``CRITICAL`` in the couture). Kept
#: conservative: a nearly-full disk breaks store AND backup writes (D111), so 5% headroom is the floor.
_DEFAULT_MIN_FREE_RATIO = 0.05

#: Default RAM-used fraction above which memory is under pressure (``DEGRADED`` in the couture). M4
#: juggling (D95): past ~92% used, model / index writes start to thrash.
_DEFAULT_MAX_RAM_USED = 0.92


def _disk_free_ratio(usage: object) -> float:
    """Free-space ratio ``free / total`` from a :func:`shutil.disk_usage`-shaped result (pure, UNIT-TESTED).

    Reads ``.free`` and ``.total`` (bytes). A zero / missing ``total`` is treated as NO free space
    (ratio ``0.0``) — fail-safe: an unreadable disk reports full, never falsely empty (D100). This pure
    helper is where the disk math lives, so :meth:`SystemHardwareProbe.disk_ok` stays a thin threshold
    check and the arithmetic is unit-tested against synthetic totals."""
    total = float(getattr(usage, "total", 0) or 0)
    if total <= 0:
        return 0.0
    free = float(getattr(usage, "free", 0) or 0)
    return free / total


class SystemHardwareProbe:
    """Real :class:`~mnemosyne.runtime.health.HardwareProbe`: disk via stdlib, RAM / thermal via psutil.

    Realizes the probe protocol structurally (duck-typed, not subclassed). Construct with optional
    injectables so every path is testable without the brick:

    * ``disk_usage`` (defaults to :func:`shutil.disk_usage`) + ``min_free_ratio`` — the STDLIB disk read;
      unit-tested (synthetic totals → ok / not-ok), NOT ``pragma``'d.
    * ``ram_reader`` / ``thermal_reader`` (default HEALTHY until wired) + ``max_ram_used`` — the psutil /
      IOKit signals; a reader that raises is caught and reported as NOT-ok (fail-safe, D100 / D111).

    The probe only REPORTS; the couture (:class:`~mnemosyne.runtime.health.HealthMonitor`) folds the
    three booleans into a state and decides conduct. ``real_runtime`` wires the psutil-backed readers at
    ③-6b (:func:`psutil_ram_reader` / :func:`iokit_thermal_reader`)."""

    __slots__ = (
        "_disk_usage",
        "_min_free_ratio",
        "_ram_reader",
        "_max_ram_used",
        "_thermal_reader",
    )

    def __init__(
        self,
        *,
        disk_usage: DiskUsageReader | None = None,
        min_free_ratio: float = _DEFAULT_MIN_FREE_RATIO,
        path: str = "/",
        ram_reader: RamReader | None = None,
        max_ram_used: float = _DEFAULT_MAX_RAM_USED,
        thermal_reader: ThermalReader | None = None,
    ) -> None:
        if disk_usage is None:
            import shutil  # STDLIB — real disk read, dependency-free (NOT a brick)

            disk_usage = shutil.disk_usage
        # bind the path into the reader so `disk_ok()` stays argument-free (the port signature)
        self._disk_usage: Callable[[], object] = lambda: disk_usage(path)
        self._min_free_ratio = min_free_ratio
        # default HEALTHY until the psutil / IOKit readers are wired at ignition (D126): the stub reported
        # all-OK, so an un-wired real probe must not suddenly cry pressure. A wired reader that RAISES is
        # caught below and reported NOT-ok (fail-safe — an unreadable signal assumes the worse, D100).
        self._ram_reader: RamReader = ram_reader if ram_reader is not None else (lambda: 0.0)
        self._max_ram_used = max_ram_used
        self._thermal_reader: ThermalReader = (
            thermal_reader if thermal_reader is not None else (lambda: True)
        )

    def disk_ok(self) -> bool:
        """True when free space is at least ``min_free_ratio`` of total (STDLIB, unit-tested).

        Reads free / total via the injected :func:`shutil.disk_usage`-shaped reader and compares the
        ratio to the threshold. Fail-safe: if the read RAISES (a vanished mount) the disk is reported
        NOT-ok — a full disk is ``CRITICAL`` in the couture, and an unreadable disk assumes the worse
        (D100 / D111), never a false green."""
        try:
            ratio = _disk_free_ratio(self._disk_usage())
        except Exception:  # noqa: BLE001 - an unreadable disk assumes full (fail-safe, D100)
            return False
        return ratio >= self._min_free_ratio

    def ram_ok(self) -> bool:
        """True when RAM used is at or below ``max_ram_used`` (psutil signal, fail-safe).

        Reads the used fraction via the injected ``ram_reader`` (default healthy until psutil is wired,
        D126). A reader that RAISES ⇒ NOT-ok: a probe that cannot read memory pressure assumes pressure
        (DEGRADED in the couture — D95 / D100), never a reassuring green."""
        try:
            used = self._ram_reader()
        except Exception:  # noqa: BLE001 - an unreadable RAM signal assumes pressure (fail-safe, D100)
            return False
        return used <= self._max_ram_used

    def thermal_ok(self) -> bool:
        """True when the machine is NOT thermally throttling (IOKit signal, fail-safe).

        Reads the thermal state via the injected ``thermal_reader`` (default healthy until IOKit is
        wired, D126). A reader that RAISES ⇒ NOT-ok: an unreadable thermal signal assumes throttling
        (DEGRADED in the couture — D100), never a false green."""
        try:
            return bool(self._thermal_reader())
        except Exception:  # noqa: BLE001 - an unreadable thermal signal assumes throttling (fail-safe)
            return False


def psutil_ram_reader() -> RamReader:  # pragma: no cover - needs the brick (③ ignition)
    """Build a :data:`RamReader` backed by ``psutil`` (the ``[OPERATOR]`` allumage seam, D95 / D111).

    Imports ``psutil`` LAZILY so this module is import-safe without it (D126); the resulting reader is
    injected into :class:`SystemHardwareProbe` by ``real_runtime`` at ③-6b. A raise inside the reader is
    caught by :meth:`SystemHardwareProbe.ram_ok` (fail-safe NOT-ok), so a psutil hiccup degrades to a RAM
    alarm, never a crash.

    ALLUMAGE NOTE (best-guess API, confronted to the real ``psutil`` at the smoke ``[OPERATOR]``):
    ``import psutil`` → ``psutil.virtual_memory().percent`` returns the USED percentage (0–100); the
    reader returns it as a fraction (``/ 100.0``). Confirm at ignition: (1) the import + that
    ``virtual_memory().percent`` is used-percent (not free); (2) whether to prefer ``.available /
    .total`` for the same fraction more directly. Runs LOCAL, reads only aggregate memory stats (no
    content, inv. 22)."""
    import psutil  # lazy, machine-only (D103 sole importer)

    def _read() -> float:
        return float(psutil.virtual_memory().percent) / 100.0

    return _read


def iokit_thermal_reader() -> ThermalReader:  # pragma: no cover - needs psutil / IOKit (③ ignition)
    """Build a :data:`ThermalReader` for the M4's thermal state (the ``[OPERATOR]`` allumage seam, D111).

    Imports the thermal source LAZILY so this module is import-safe without it (D126); injected into
    :class:`SystemHardwareProbe` by ``real_runtime`` at ③-6b. A raise inside the reader is caught by
    :meth:`SystemHardwareProbe.thermal_ok` (fail-safe NOT-ok), so a missing source degrades to a thermal
    alarm, never a crash.

    ALLUMAGE NOTE (best-guess API, confronted to the real source at the smoke ``[OPERATOR]`` — the LEAST
    settled of the readers): macOS exposes thermal pressure via IOKit / ``pmset -g therm`` /
    ``ProcessInfo.thermalState`` (Swift), none with a clean cross-version Python binding. Best guess:
    read ``pmset -g therm`` via subprocess and treat a non-nominal ``CPU_Speed_Limit`` < 100 as
    throttling; OR, if ``psutil.sensors_temperatures()`` is populated on this machine, treat an
    over-threshold core temp as throttling. This is the MOST uncertain read — until confirmed at
    ignition the DEFAULT healthy reader stands (the stub reported OK), and thermal never falsely
    degrades. Confirm at ignition: which source is actually readable on the operator's M4, and the
    throttling threshold; then return a reader that maps it to ``True`` = OK. Reads only aggregate
    thermal state (no content, inv. 22)."""
    raise NotImplementedError(
        "M4 thermal reader to be wired at ignition ([OPERATOR]): choose the readable source "
        "(pmset -g therm subprocess vs psutil.sensors_temperatures vs an IOKit binding) and the "
        "throttling threshold — until then SystemHardwareProbe's default healthy thermal reader stands "
        "(the stub reported OK, so an un-wired thermal signal never falsely degrades, D111 / F3)"
    )
