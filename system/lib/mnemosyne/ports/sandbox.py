"""Sandbox (D99) - two-tier OS isolation, the last line behind the Guard.

The Guard intercepts upstream (the frontiers); OS isolation is the LAST line if
the Guard ever lets something through. Two tiers, reused from OSS behind a
replaceable seam (D99):

* **Tier 1 - current (default, light): Seatbelt + network proxy.** Allow-listed
  files, network denied by default, near-zero overhead; for agents of bounded
  trust (including ingestion agents in reduced rights, D81).
* **Tier 2 - heavy: disposable micro-VM.** Hardware isolation, clean kernel,
  destroyed after use; for any agent running UNTRUSTED / arbitrary code.

The rest of Mnémosyne talks to this abstraction (run / execute / destroy),
never to a precise engine - changing engine is a local swap (method D68 / D88).
Default OSS bricks: **anthropic/sandbox-runtime** (tier 1, Seatbelt profiles +
network allow-list + violation journal) and **apple/container** (tier 2,
penchant; alternative microsandbox - bench (2)) - see
``system/config/oss_registry.md`` (D99).

Decisions: D99 (two-tier isolation)  -  D81 (reduced-rights ingestion)  -  D72
(bubble grain)  -  D98 (OSS under our rules). Invariant carried: substrate of 4,
7, 20 (containment of untrusted execution).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol, runtime_checkable

from .guard import Grant


class IsolationTier(IntEnum):
    """Which isolation stage to run under (D99). Higher = stronger containment."""

    SEATBELT = 1  # light: Seatbelt + network proxy, allow-list files, deny network
    MICROVM = 2  # heavy: disposable micro-VM for untrusted / arbitrary code


@dataclass(frozen=True, slots=True)
class SandboxSpec:
    """The confinement to apply (D99). Deny-by-default: nothing is allowed unless
    listed. ``allow_files`` / ``allow_hosts`` are the explicit allow-lists."""

    tier: IsolationTier
    allow_files: tuple[str, ...] = ()
    allow_hosts: tuple[str, ...] = ()  # empty => network denied (default)


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Outcome of a confined run, including the blocked attempts it observed."""

    exit_code: int
    output: str
    violations: tuple[str, ...] = ()  # blocked file/network attempts (D99 monitoring)


@runtime_checkable
class Sandbox(Protocol):
    """Runs code under one of the two isolation tiers; the engine stays swap-able."""

    def run(self, spec: SandboxSpec, command: str, *, grant: Grant) -> SandboxResult:
        """Run ``command`` under ``spec``. ``grant`` proves the Guard authorized
        the execution (D89). A ``MICROVM`` sandbox is single-use and destroyed
        after the run; blocked file/network attempts are reported in
        :attr:`SandboxResult.violations` (D99 real-time monitoring)."""
        ...
