"""RefusingSandbox (D99 / D126) - the abstaining OS-isolation default, fail-closed.

The :class:`~mnemosyne.ports.sandbox.Sandbox` seam is the LAST line of defence: OS isolation for any
agent that runs untrusted / arbitrary code (D99). Until a real engine is wired, the safe default is
NOT to run the code unconfined - that would turn a missing brick into a breach. So this stub REFUSES
every run fail-closed: better to abstain (a refused execution, honestly reported) than to execute
outside isolation (D100 - incapacity, not trust).

This keeps the whole suite green with NO sandbox brick installed (D126): the two real tiers -
``anthropic/sandbox-runtime`` (Seatbelt + network allow-list, tier 1) and ``apple/container`` (disposable
micro-VM, tier 2) - land in (3)-5b behind this same seam, sole-importers (invariant 20), injected by
``real_runtime`` at ignition. A drift there degrades to a refused run, never an unconfined one.

Decisions: D99 (two-tier isolation, last line)  -  D126 (brick-free suite, injected real adapter)  -
D100 (structural incapacity, fail-closed). Code & docstrings English (D117).
"""

from __future__ import annotations

from ..ports import Grant, SandboxResult, SandboxSpec

#: POSIX "command cannot execute" - the honest exit code for a run that was refused, not attempted.
_REFUSED_EXIT: int = 126


class RefusingSandbox:
    """The default OS-isolation seam (D99): with no engine wired, untrusted execution is REFUSED.

    A structural :class:`~mnemosyne.ports.sandbox.Sandbox` (duck-typed). It never runs the command:
    it returns a non-zero :class:`~mnemosyne.ports.sandbox.SandboxResult` whose ``violations`` name the
    refusal, so a caller reads an honest failure (F3) and no untrusted code ever runs outside isolation.
    The ``grant`` is accepted for contract parity (a real engine authenticates it, M1) but is moot here:
    the answer is always "refused", regardless of authorisation (fail-closed, D100)."""

    __slots__ = ()

    def run(self, spec: SandboxSpec, command: str, *, grant: Grant) -> SandboxResult:
        """Refuse the run fail-closed (D99 / D126): no isolation engine => no execution."""
        return SandboxResult(
            exit_code=_REFUSED_EXIT,
            output="",
            violations=(
                "no OS-isolation engine wired - untrusted execution refused fail-closed "
                f"(tier {spec.tier.name}); the real sandbox brick lands in (3)-5b (D99 / D126)",
            ),
        )
