"""_SeatbeltSandbox — the SOLE driver of the native macOS Seatbelt (D99 / D103 / invariant 20).

Tier 1 of the two-tier OS isolation (D99): **Seatbelt confinement, driven via the NATIVE macOS
``/usr/bin/sandbox-exec`` binary** (subprocess) — the light, near-zero-overhead confinement for agents
of BOUNDED trust (including the reduced-rights ingestion agents, D81). This is NOT the pip
``sandbox_runtime`` port (rejected at ignition: it is a third-party wrapper — we drive the OS mechanism
directly, exactly as the Kopia / SOPS adapters shell out to their CLIs). Like WhisperKit there is **no
importable Python brick** here: the "brick" is the macOS kernel sandbox, and this module is the one
place we shell out to it (invariant 20 — sole driver). It wraps that behind the
:class:`~mnemosyne.ports.sandbox.Sandbox` port so the rest of Mnémosyne talks only to the port; the
actual ``sandbox-exec`` spawn is ``# pragma: no cover`` (exercised at ③ ignition / by the negative
smoke), while the pure profile-string builder (:func:`_seatbelt_profile`) — the security surface where
an allow-list path is embedded and thus where an injection would live — is deterministic, brick-free,
UNIT-TESTED.

**Posture confronted at ignition (macOS Darwin 25 / ``sandbox-exec``).** A strict ``(deny default)``
profile cannot even ``execvp`` a binary, and the standard base profiles (``system.sb`` / ``bsd.sb``)
are gone from modern macOS, so there is nothing to ``(import ...)`` — hand-enumerating every system
read / mach lookup a binary needs is precisely the fragile job the rejected brick automated. So tier 1
uses the robust posture the kernel actually enforces: ``(allow default)`` — the confined command can
run — then the TWO capabilities that matter for a tier-1 bounded-trust agent are DENIED and re-opened
only by allow-list. The **network** (egress) is denied unless a host is allow-listed; file **writes**
are denied outside the allow-listed zone. Read-isolation / arbitrary UNTRUSTED code is NOT tier 1's
promise — that is tier 2 (the disposable micro-VM, :mod:`.sandbox_microvm`). macOS Seatbelt filters the
network COARSELY (on / off), not per host — per-host allow-listing is the "network proxy" leg of D99,
DEFERRED (not wired here); so a non-empty ``allow_hosts`` opens the network wholesale, an empty one
denies it (deny-by-default).

**The GRANT is NOT redeemed here (capital rule, ③-5b).** In the tool flow it is the
:class:`~mnemosyne.tools.invoke.GovernedToolInvoker` that redeems the single-use grant (M1), the ONE
consumption point; re-redeeming it here would burn a second time and break the round-trip. The sandbox
accepts the ``grant`` for contract parity and provides the ISOLATION, never the re-verification — the
authorisation was already checked upstream (D89 / D100). Deny-by-default is structural: an empty
``allow_hosts`` denies the network, an empty ``allow_files`` grants no write path (D99).

Decisions: D99 (two-tier isolation, tier 1) · D81 (reduced-rights ingestion) · D103 (sole driver) ·
D126 (brick-free suite — the mechanism is the OS itself) · D100 (isolation is incapacity, not trust).
Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable

from ..ports import Grant, IsolationTier, SandboxResult, SandboxSpec

#: The native macOS Seatbelt driver (D99): the OS binary that applies a ``.sb`` profile to a command.
_SANDBOX_EXEC = "/usr/bin/sandbox-exec"

#: POSIX "command cannot execute" — the honest exit code for a run REFUSED, not attempted (the same
#: idiom as :class:`~mnemosyne.tools.sandbox.RefusingSandbox`, ``tools/sandbox.py``).
_REFUSED_EXIT: int = 126

#: A Seatbelt executor: given ``(profile_text, command)``, apply the profile and run the command,
#: returning ``(exit_code, combined_output)``. Injected in tests / at ignition so the profile-building
#: and result-mapping translation is exercised WITHOUT actually spawning ``sandbox-exec`` (D126). The
#: default is the native subprocess driver :func:`_default_seatbelt_executor` below.
SeatbeltExecutor = Callable[[str, str], tuple[int, str]]


def connect_sandbox_runtime(  # pragma: no cover - drives the native macOS sandbox (③ ignition)
    *, executor: SeatbeltExecutor | None = None
) -> "_SeatbeltSandbox":
    """Wire the native macOS Seatbelt as a tier-1 :class:`Sandbox` (the ``[OPERATOR]`` ignition seam, D99).

    Drives ``/usr/bin/sandbox-exec`` via subprocess — no Python brick to import (D126: the mechanism is
    the OS kernel sandbox). Wired by :func:`~mnemosyne.runtime.bootstrap.real_runtime` as the default
    OS-isolation engine; the factory NAME is retained (``connect_sandbox_runtime``) as the stable seam
    name real_runtime knows, though it no longer touches the rejected ``sandbox_runtime`` pip port. A
    drift in the OS mechanism degrades to a refused / failed run behind the fail-closed default, never an
    unconfined one (D100). Pass ``executor`` in tests / at ignition to inject the resolved run callable
    and keep the profile-building + result mapping (:class:`_SeatbeltSandbox`) exercised without
    spawning ``sandbox-exec``."""
    return _SeatbeltSandbox(executor if executor is not None else _default_seatbelt_executor)


class _SeatbeltSandbox:  # pragma: no cover - real sandbox-exec translation (③-5b ignition, smoke-tested)
    """Thin translation from :class:`~mnemosyne.ports.sandbox.Sandbox` to native ``sandbox-exec`` (D99 / D103).

    Holds the Seatbelt executor (injected so this class spawns nothing at construction). ``run`` builds a
    DYNAMIC Seatbelt profile from ``spec.allow_files`` / ``spec.allow_hosts`` (deny-by-default: empty
    ``allow_hosts`` ⇒ network denied, writes confined to the allow-listed zone), runs the command under
    it, and maps the outcome onto :class:`~mnemosyne.ports.sandbox.SandboxResult`. It does NOT redeem the
    grant (the invoker already did, M1) and does NOT trust the command: isolation is the whole job
    (D100). A launch failure is not swallowed into a false success — it surfaces to the caller."""

    __slots__ = ("_run",)

    def __init__(self, run: SeatbeltExecutor) -> None:
        self._run = run

    def run(self, spec: SandboxSpec, command: str, *, grant: Grant) -> SandboxResult:
        """Run ``command`` under a dynamic Seatbelt profile (tier 1). ``grant`` is accepted for
        contract parity but NOT redeemed here (the invoker consumed the single-use token upstream,
        M1) — the sandbox provides isolation, not re-authorisation (D99 / D100).

        TIER FAIL-CLOSED (D99 / D100): the Seatbelt engine provides tier 1 ONLY. A request for a
        HIGHER tier (``MICROVM`` — the disposable micro-VM, tier 2, DEFERRED / unwired) is REFUSED
        here — returned BEFORE any profile is built — never silently DOWNGRADED to run under weaker
        Seatbelt confinement (that would be the exact silent-downgrade breach D99 forbids). Same idiom
        as :meth:`~mnemosyne.tools.sandbox.RefusingSandbox.run`: a non-zero exit + a ``violations``
        line naming the refusal, so the caller reads an honest failure (F3), never a false confinement.

        The allow-list paths are CANONICALISED to their realpath before the profile is built: macOS
        Seatbelt matches ``(subpath …)`` against the KERNEL-canonical path (``/tmp`` → ``/private/tmp``,
        ``/var`` → ``/private/var``, a symlinked scratch dir → its target), so an UN-resolved symlink
        would silently DENY a legitimate in-zone write — fail-CLOSED, but a real bug. Resolving HERE
        keeps :func:`_seatbelt_profile` pure / string-only (its unit test stays machine-independent),
        and the injection-check inside it still applies to the RESOLVED path.

        A blocked file / network attempt surfaces as a non-zero ``exit_code`` and an EPERM line in
        ``output`` (the kernel logs the denial to the unified log out-of-band; native ``sandbox-exec``
        hands us no per-run violations journal, so :attr:`SandboxResult.violations` stays empty here —
        the ENFORCEMENT is the kernel's and is real regardless, monitored out-of-band, D99)."""
        if spec.tier > IsolationTier.SEATBELT:  # a tier-2 request this tier-1 engine cannot honour
            return SandboxResult(
                exit_code=_REFUSED_EXIT,
                output="",
                violations=(
                    f"tier-2 micro-VM unavailable — refused fail-closed (requested tier "
                    f"{spec.tier.name} > SEATBELT); a higher-tier request is never downgraded to "
                    "Seatbelt (D99 / D100)",
                ),
            )
        import os

        real_files = tuple(os.path.realpath(path) for path in spec.allow_files)
        profile = _seatbelt_profile(real_files, spec.allow_hosts)
        exit_code, output = self._run(profile, command)
        return SandboxResult(exit_code=exit_code, output=output, violations=())


#: Characters an allow-list path must NOT contain to be safely embedded in a Seatbelt (.sb) profile
#: S-expression string: the quote closes the string, the backslash escapes, and control chars break the
#: directive line. A path carrying one is REFUSED fail-closed — a security allow-list path never
#: legitimately holds them — so a crafted path cannot escape its quoted string to inject a directive
#: (e.g. re-open the network or widen the write zone). Structural incapacity, not a probabilistic bet
#: (audit ③-5 MINOR-1 / D99 / D100 — the sandbox is the last line, it may not be talked into widening
#: itself).
_PROFILE_UNSAFE: tuple[str, ...] = ('"', "\\", "\n", "\r", "\x00")

#: Device nodes a confined command legitimately writes to — else ``(deny file-write*)`` would break
#: ordinary programs that touch ``/dev/null``, the tty, or the std streams. Fixed literals: no
#: allow-list input reaches them, so they carry no injection surface.
_DEVICE_WRITES: tuple[str, ...] = (
    "/dev/null",
    "/dev/dtracehelper",
    "/dev/tty",
    "/dev/stdout",
    "/dev/stderr",
)


def _seatbelt_profile(allow_files: tuple[str, ...], allow_hosts: tuple[str, ...]) -> str:
    """Build the tier-1 Seatbelt (``.sb``) profile the native ``sandbox-exec`` applies (pure, UNIT-TESTED).

    The posture confronted at ignition (see the module docstring): ``(allow default)`` so the confined
    command can run at all, then DENY the two capabilities that matter for a bounded-trust agent and
    re-open them only by allow-list — the NETWORK is denied unless ``allow_hosts`` is non-empty (coarse
    on / off; per-host is the deferred proxy leg of D99), and file WRITES are denied outside the
    ``allow_files`` zone (Seatbelt evaluates rules in order, last match wins: ``(allow default)`` →
    ``(deny file-write*)`` → ``(allow file-write* (subpath …))`` leaves a write allowed IFF it is under
    the zone). A path containing a profile-string metacharacter (:data:`_PROFILE_UNSAFE` — quote /
    backslash / a control char) is REFUSED fail-closed, so a crafted allow-list entry cannot escape its
    quoted string to inject a directive (audit ③-5 MINOR-1 / D100 — incapacity, not a bet)."""
    lines = ["(version 1)", "(allow default)"]
    if (
        not allow_hosts
    ):  # network denied unless a host is explicitly allow-listed (deny-by-default, D99)
        lines.append("(deny network*)")
    lines.append("(deny file-write*)")  # writes denied everywhere, then re-opened ONLY in the zone
    for path in allow_files:
        if any(ch in path for ch in _PROFILE_UNSAFE):
            raise ValueError(
                f"unsafe sandbox allow-list path {path!r}: a profile-string metacharacter "
                "(quote / backslash / control char) is refused fail-closed (D99 / D100)"
            )
        lines.append(f'(allow file-write* (subpath "{path}"))')
    devices = " ".join(f'(literal "{node}")' for node in _DEVICE_WRITES)
    lines.append(
        f"(allow file-write-data {devices})"
    )  # sane device writes (/dev/null, tty, std streams)
    return "\n".join(lines)


def _default_seatbelt_executor(  # pragma: no cover - spawns the OS sandbox (③ ignition)
    profile: str, command: str
) -> tuple[int, str]:
    """Apply ``profile`` via the native macOS ``sandbox-exec`` and run ``command`` confined.

    Writes the generated profile to a private temp ``.sb`` file (``sandbox-exec`` reads ``-f <file>``),
    runs the command through ``/bin/sh -c`` UNDER the profile (the shell — and anything it spawns —
    inherits the kernel confinement), and returns ``(exit_code, stdout+stderr)``. A non-zero exit is a
    legitimate RESULT (a denied operation, surfacing as an EPERM line on stderr), NOT an exception — the
    caller reads ``exit_code`` / ``output``. Only a failure to LAUNCH ``sandbox-exec`` itself (e.g. the
    binary absent) raises, surfacing to the caller — never a false unconfined success (D100)."""
    import subprocess
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkstemp(suffix=".sb")[1])
    try:
        tmp.write_text(profile, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603 - argv is ours; the command runs CONFINED by the profile
            [_SANDBOX_EXEC, "-f", str(tmp), "/bin/sh", "-c", command],
            capture_output=True,
            text=True,
        )
    finally:
        tmp.unlink(missing_ok=True)
    return completed.returncode, completed.stdout + completed.stderr
