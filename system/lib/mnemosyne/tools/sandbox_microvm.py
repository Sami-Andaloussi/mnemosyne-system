"""_MicroVMSandbox — the SOLE importer of apple/container (D99 / D103 / invariant 20).

Tier 2 of the two-tier OS isolation (D99): a **disposable micro-VM** — hardware isolation, a clean
kernel, DESTROYED after the run — the heavy confinement for any agent running UNTRUSTED / arbitrary
code (the case where Seatbelt tier 1 is not enough). It wraps ``apple/container`` (Apple, Apache-2.0;
preferred over microsandbox — ``oss_registry.md``) behind the :class:`~mnemosyne.ports.sandbox.Sandbox`
port, so the rest of Mnémosyne talks only to the port and the suite stays green with the brick NOT
installed (D126). Everything here is ``# pragma: no cover``: it needs the installed brick (and the
Apple ``container`` runtime / macOS 15+), absent in CI, so it is exercised only at ③ ignition, where
the 1-click smoke test confronts this glue with the real API.

**Single-use, destroyed after the run (D99).** A micro-VM is created for ONE ``run`` and torn down in a
``finally`` — a fresh kernel every time, no state carried between untrusted executions.

**The GRANT is NOT redeemed here (capital rule, ③-5b).** As with tier 1: the
:class:`~mnemosyne.tools.invoke.GovernedToolInvoker` redeemed the single-use grant (M1), the ONE
consumption point. This sandbox accepts the ``grant`` for contract parity and provides the ISOLATION,
never the re-verification (D89 / D100). Deny-by-default is structural (empty allow-lists grant nothing).

Decisions: D99 (two-tier isolation, tier 2, disposable micro-VM) · D103 (sole importer) · D126
(brick-free suite, injected real adapter) · D100 (isolation is incapacity, not trust). Code &
docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable

from ..ports import Grant, SandboxResult, SandboxSpec

#: Default disposable base image for the micro-VM. A minimal Linux userland is enough to run a confined
#: command; the exact image + how apple/container names it is confirmed at ignition (IGNITION NOTE).
_DEFAULT_IMAGE = "docker.io/library/alpine:latest"


def connect_apple_container(  # pragma: no cover - needs the brick + container runtime (③ ignition)
    *, image: str = _DEFAULT_IMAGE, launcher: Callable[..., object] | None = None
) -> "_MicroVMSandbox":
    """Wire apple/container as a tier-2 :class:`Sandbox` (the ``[OPERATOR]`` ignition seam, D99).

    Imports ``container`` LAZILY so this module is import-safe without it (D126); wired by
    :func:`~mnemosyne.runtime.bootstrap.real_runtime` ONLY where untrusted / arbitrary code must run
    (tier 2 is the heavy line — the default engine is Seatbelt tier 1). As with every ``pragma: no
    cover`` adapter, the 1-click smoke test confronts this glue with the real API at ignition; a drift
    degrades to a refused / failed run behind the fail-closed default, never an unconfined one.

    IGNITION NOTE (best-guess API, confronted to the real apple/container at the smoke ``[OPERATOR]``):
    ``apple/container`` is primarily a Swift CLI (``container run``) with an XPC API; the Python glue is
    best guessed as either (a) a thin subprocess wrapper around ``container run --rm <image> sh -c
    <command>`` with ``--volume`` for allow-listed files and ``--network none`` when no host is
    allow-listed, or (b) a ``container`` Python binding exposing an ephemeral-container run. Confirm at
    ignition: (1) whether a Python binding exists or this must shell out to the ``container`` CLI; (2)
    the disposable-VM flags (``--rm`` / auto-destroy) and the mount / network-deny flags; (3) the base
    image name; (4) how blocked attempts / non-zero exits surface. Pass ``launcher`` in tests / at
    ignition to inject the resolved run callable and keep the translation exercised without the brick."""
    if launcher is None:
        import container  # lazy, machine-only (D103 sole importer)

        launcher = container.run  # the ephemeral-run entrypoint (name confirmed at ignition)
    return _MicroVMSandbox(launcher, image=image)


class _MicroVMSandbox:  # pragma: no cover - real apple/container translation (③-5b ignition)
    """Thin translation from :class:`~mnemosyne.ports.sandbox.Sandbox` to apple/container (D99 / D103).

    Holds the brick's run/launch callable (injected so this class never imports at module scope). ``run``
    creates a disposable micro-VM, mounts ONLY the allow-listed files, denies the network unless a host
    is allow-listed, runs the command, and DESTROYS the VM in a ``finally`` (single-use, D99). It maps
    the outcome onto :class:`~mnemosyne.ports.sandbox.SandboxResult`, does NOT redeem the grant (the
    invoker already did, M1), and does NOT trust the command (isolation is the whole job, D100). A brick
    failure is not swallowed into a false success — it surfaces to the caller."""

    __slots__ = ("_launch", "_image")

    def __init__(self, launch: Callable[..., object], *, image: str) -> None:
        self._launch = launch
        self._image = image

    def run(self, spec: SandboxSpec, command: str, *, grant: Grant) -> SandboxResult:
        """Run ``command`` in a disposable micro-VM (tier 2), destroyed after the run. ``grant`` is
        accepted for contract parity but NOT redeemed here (the invoker consumed the single-use token
        upstream, M1) — the sandbox provides hardware isolation, not re-authorisation (D99 / D100)."""
        handle = self._launch(
            image=self._image,
            command=command,
            mounts=list(spec.allow_files),
            # deny-by-default: no allow-listed host ⇒ the micro-VM has NO network (D99).
            network=list(spec.allow_hosts) if spec.allow_hosts else None,
            ephemeral=True,  # single-use: auto-destroyed after the run
        )
        try:
            return _to_result(handle)
        finally:
            _destroy(handle)  # a fresh kernel next time — no state carried between untrusted runs


def _to_result(
    handle: object,
) -> SandboxResult:  # pragma: no cover - real result mapping (③ ignition)
    """Map the micro-VM run handle onto :class:`SandboxResult` (best-guess accessors, confirmed at
    ignition): ``exit_code``, ``output`` else ``stdout``, and ``violations`` else ``denied``. Missing
    pieces default fail-safe — never a fabricated success."""
    exit_code = int(getattr(handle, "exit_code", 0))
    output = getattr(handle, "output", None)
    if output is None:
        output = getattr(handle, "stdout", "")
    violations = getattr(handle, "violations", None)
    if violations is None:
        violations = getattr(handle, "denied", ())
    return SandboxResult(
        exit_code=exit_code, output=str(output), violations=tuple(str(v) for v in violations)
    )


def _destroy(handle: object) -> None:  # pragma: no cover - real teardown (③-5b ignition)
    """Tear down the disposable micro-VM (single-use, D99). Best-guess: a ``destroy`` / ``stop`` /
    ``close`` method on the handle — whichever the brick exposes is called; the exact name is confirmed
    at ignition. Teardown failures are not re-raised over a genuine result (the VM is disposable)."""
    for method in ("destroy", "stop", "close", "remove"):
        teardown = getattr(handle, method, None)
        if callable(teardown):
            try:
                teardown()
            except Exception:  # noqa: BLE001 - teardown of a disposable VM must not mask the result
                pass
            return
