"""The multi-agent glue ((3)-5b) - Pydantic AI wired so it CANNOT bypass the Guard (D93 / D100).

The orchestration ENGINE is already ours and built (``BoundedScheduler``, ``guard/bounds.py``): bounded
queue (inv. 16), concurrency (D95/D80), suspend->free-slot (inv. 26), ``pause_all`` kill-switch. This
package adds the typed agent GLUE (Pydantic AI, D125-B7) - but under one hard constraint:

**D100 (capital): a Pydantic AI agent NEVER reaches a model or a tool by bypassing the Guard.** Its
model calls go through OUR :class:`~mnemosyne.runtime.runner.LocalRunner` (behind the Guard, grant-gated,
grammar-bound); its tool calls go through OUR :class:`~mnemosyne.tools.invoke.GovernedToolInvoker`
(grant -> redeem -> sandbox -> re-label the untrusted return). Pydantic AI's own provider clients and its
own tool executor are NEVER used to reach a real model / real tool - they are replaced by bridges to our
governed path (:mod:`.pydantic_bridge`).

Sole-importer of ``pydantic_ai`` is :mod:`.pydantic_bridge` (invariant 20); the suite stays green with
the brick NOT installed (D126). Code & docstrings English (D117).
"""

from __future__ import annotations

from .loop import build_grant_source, run_agent, smoke_agent_invokes_runner
from .pydantic_bridge import GovernedToolBridge, RunnerModel, connect_pydantic_agent

__all__ = [
    "GovernedToolBridge",
    "RunnerModel",
    "build_grant_source",
    "connect_pydantic_agent",
    "run_agent",
    "smoke_agent_invokes_runner",
]
