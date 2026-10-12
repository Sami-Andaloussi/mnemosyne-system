"""The tools fabric ((3)-5) - governed tool execution + OS-isolation seam.

The couture NÔTRE of the "agents & outils" lot: the concrete tool allow-list, the governed executor
that mediates a tool call at both ends, the exercised local-function stub, and the abstaining sandbox
default. The Guard already RULES a ``TOOL_CALL`` (``guard.monitor._rule_tool_call``) and seals the
routed channel into the grant (M1); this package supplies the missing CONSUMERS:

* :class:`ConfigToolCatalog` - the protected allow-list (D114-(5)) the Guard reads, deny-by-default.
* :class:`GovernedToolInvoker` - grant -> **redeem** (the non-local consumer that closes the (3)-1 egress
  debt) -> invoke -> re-label the untrusted return by the maximum (D101 / D100).
* :class:`LocalFunctionTool` - the exercised ``LOCAL_FUNCTION`` stub plugin.
* :class:`RefusingSandbox` - the fail-closed OS-isolation default (D99 / D126); real Seatbelt +
  micro-VM engines land in (3)-5b behind this seam.

The MCP / API back-ends, the real sandbox engines, Outlines (constrained decode, in the Runner) and
Pydantic AI (the multi-agent glue) are (3)-5b. Code & docstrings English (D117).
"""

from __future__ import annotations

from .catalog import ConfigToolCatalog
from .invoke import GovernedToolInvoker, LocalFunctionTool
from .mcp_client import McpServerConfig, McpTransport, connect_mcp_server, default_mcp_manifest
from .sandbox import RefusingSandbox
from .sandbox_microvm import connect_apple_container
from .sandbox_seatbelt import connect_sandbox_runtime

__all__ = [
    # (3)-5a couture (pure code, no brick)
    "ConfigToolCatalog",
    "GovernedToolInvoker",
    "LocalFunctionTool",
    "RefusingSandbox",
    # (3)-5b real bricks behind the seams (sole-importer, lazy, # pragma: no cover)
    "connect_sandbox_runtime",  # Seatbelt tier-1 (anthropic/sandbox-runtime)
    "connect_apple_container",  # micro-VM tier-2 (apple/container)
    "connect_mcp_server",  # MCP ToolPlugin back-end (MCP Python SDK)
    "McpServerConfig",
    "McpTransport",
    "default_mcp_manifest",
]
