"""_McpServerTool - the SOLE importer of the MCP Python SDK (D114 / D103 / invariant 20).

An MCP server is one of the THREE back-ends behind the single :class:`~mnemosyne.ports.tools.ToolPlugin`
prise (D114-(1): "MCP client" is NOT a separate architecture). This adapter makes a tool offered by a
third-party MCP server look like any other :class:`ToolPlugin`, via the official **MCP Python SDK**
(``mcp``, MIT; ``oss_registry.md``). It wraps the SDK behind the port, so the pipeline speaks only the
port and the suite stays green with the brick NOT installed (D126). Everything that touches the SDK is
``# pragma: no cover``: it needs the installed brick AND a running server, absent in CI, so it is
exercised only at (3) ignition, where the 1-click smoke confronts this colle with the real API.

**Never bypasses the Guard (D114-(3) / D100).** This plugin is reached ONE way: the
:class:`~mnemosyne.tools.invoke.GovernedToolInvoker`, which already asked the Guard to ``grant`` the
call (allow-list + escalate life-action / non-public egress) and ``redeem``-ed the single-use token
(M1) BEFORE calling ``invoke``. The plugin does NOT re-authorise and does NOT trust the server's reply:
the returned :class:`~mnemosyne.ports.core.Envelope` carries a PROVISIONAL label - the invoker DISCARDS
it and re-floors the untrusted content by the maximum (D101 / D100-3). Do not read this label downstream.

**Not an arbitrary server (D114-(5)).** The connection parameters come from the protected config passed to
:func:`connect_mcp_server` - an agent can NEVER wire itself to an arbitrary MCP server (that is a
privileged human act, ``POLICY_WRITE``). The manifest is the allow-list entry the Guard rules on.

Decisions: D114 (tool prise + MCP as one back-end)  -  D114-(3) (Guard both-ends)  -  D114-(5) (protected
catalog)  -  D103 (sole importer)  -  D126 (import-safe)  -  D101 / D100-3 (untrusted return, re-labelled).
Code & docstrings English (D117); the ``public`` / ``perso`` / ``sensible`` tokens stay French.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..ports import (
    DataEgress,
    Envelope,
    GovernanceLabel,
    Grant,
    Sensitivity,
    ToolBackend,
    ToolEffect,
    ToolManifest,
)


class McpTransport(Enum):
    """How the SDK connects to the MCP server (D114). Both are LOCAL-first; a remote HTTP endpoint is
    still Guard-mediated by the catalog + egress rules (never reached except through the invoker)."""

    STDIO = "stdio"  # launch a local server process and speak over its stdio (default, D27)
    HTTP = "http"  # a streamable-HTTP endpoint (still allow-listed + egress-ruled)


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    """The protected connection parameters for one MCP server (D114-(5)).

    Comes from the protected zone (a privileged human act wires it), NEVER from an agent. For
    ``STDIO`` the SDK launches ``command`` + ``args``; for ``HTTP`` it connects to ``url``. ``tool``
    is the specific tool name to call on that server (this plugin fronts ONE catalog manifest)."""

    transport: McpTransport
    tool: str
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None


def connect_mcp_server(  # pragma: no cover - needs the brick + a running server ((3) ignition)
    manifest: ToolManifest, config: McpServerConfig
) -> "_McpServerTool":
    """Wire an MCP-server tool as a :class:`ToolPlugin` (the ``[OPERATOR]`` allumage seam, D114).

    The ``manifest`` is the catalog entry the Guard rules on (allow-list, egress, effect); the
    ``config`` is the protected connection (a privileged human act, D114-(5)). Imports ``mcp`` LAZILY so
    this module is import-safe without it (D126); the resulting plugin is wired into the
    :class:`~mnemosyne.tools.invoke.GovernedToolInvoker` at (3)-5b. As with every ``pragma: no cover``
    adapter, the 1-click smoke confronts this colle with the real SDK + server at ignition.

    ALLUMAGE NOTE (best-guess API, confronted to the real MCP Python SDK at the smoke ``[OPERATOR]``):
    the SDK is ASYNC. For ``STDIO``: ``from mcp import ClientSession, StdioServerParameters`` +
    ``from mcp.client.stdio import stdio_client``; ``async with stdio_client(StdioServerParameters(
    command=..., args=...)) as (read, write): async with ClientSession(read, write) as s: await
    s.initialize(); res = await s.call_tool(tool, arguments)``. For ``HTTP``: ``from
    mcp.client.streamable_http import streamablehttp_client``; ``async with streamablehttp_client(url)
    as (read, write, _): ...``. The result is a ``CallToolResult`` whose ``.content`` is a list of
    content blocks (``TextContent`` with ``.text``); ``.isError`` flags a tool error. Because our
    :class:`ToolPlugin` port is SYNCHRONOUS, this adapter bridges each call with ``asyncio.run`` over a
    fresh session (no shared event loop; a short-lived connection per call keeps the sync contract and
    avoids a leaked loop). Confirm at ignition: the import paths, ``call_tool`` signature (positional
    name + ``arguments=`` dict), the content-block shape (``.content[i].text``), and the error flag
    (``isError``). A server / SDK failure PROPAGATES to the invoker (never swallowed into a false empty
    result) - the benne/Guard net upstream owns the degradation, not this call."""
    from mcp import ClientSession, StdioServerParameters  # noqa: F401 - lazy, sole importer (D103)

    return _McpServerTool(manifest, config)


class _McpServerTool:  # pragma: no cover - real MCP SDK translation ((3)-5b ignition, smoke-tested)
    """Thin translation from :class:`~mnemosyne.ports.tools.ToolPlugin` to the MCP Python SDK (D114 / D103).

    Fronts ONE server tool named by ``config.tool``. ``invoke`` opens a short-lived session (over stdio
    or streamable-HTTP), calls the tool with the envelope's payload as arguments, joins the returned
    content blocks into text, and wraps it in an Envelope with a PROVISIONAL label - the invoker discards
    that label and re-floors the untrusted content by the maximum (D101 / D100-3). It does NOT redeem the
    grant (the invoker already did, M1) and does NOT trust the server (zero-trust return, D81)."""

    __slots__ = ("manifest", "_config")

    def __init__(self, manifest: ToolManifest, config: McpServerConfig) -> None:
        self.manifest = manifest
        self._config = config

    def invoke(self, call: Envelope[object], *, grant: Grant) -> Envelope[object]:
        """Call the MCP-server tool and return its (UNTRUSTED) text result (D114 / D100-3).

        ``grant`` proves the invoker cleared the outbound side and consumed the single-use token (M1);
        this method does not re-authorise. The returned label is PROVISIONAL and FAIL-SAFE ``sensible``
        (never a claim of ``public``): the invoker re-labels the content by the maximum, so an
        under-stated label here can never launder the reply - it can only be raised (D101 / D100)."""
        import asyncio

        arguments = call.payload if isinstance(call.payload, dict) else {"input": call.payload}
        text = asyncio.run(self._call_tool(arguments))
        # PROVISIONAL, fail-safe sensible: the invoker DISCARDS this and re-floors by the max (D100-3).
        provisional = GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=call.label.bubble)
        return Envelope(payload=text, label=provisional)

    async def _call_tool(self, arguments: dict[str, object]) -> str:
        """Open a short-lived MCP session, call the tool, and join its content blocks into text.

        A fresh connection per call (no shared loop) keeps the synchronous :class:`ToolPlugin` contract.
        The exact SDK surface is confirmed at ignition (ALLUMAGE NOTE on :func:`connect_mcp_server`)."""
        from mcp import ClientSession

        async with self._open() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(self._config.tool, arguments=arguments)
        return _join_content(result)

    def _open(self):
        """Open the transport chosen in config (stdio launches a local process; http connects to a
        streamable endpoint). Both are allow-listed via the catalog + egress rules - never an arbitrary
        server (D114-(5)). Returns the SDK's async context manager yielding ``(read, write)``."""
        if self._config.transport is McpTransport.HTTP:
            from mcp.client.streamable_http import streamablehttp_client

            if self._config.url is None:
                raise ValueError("MCP HTTP transport requires a `url` in the protected config")
            return _drop_session_id(streamablehttp_client(self._config.url))
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        if self._config.command is None:
            raise ValueError("MCP stdio transport requires a `command` in the protected config")
        params = StdioServerParameters(command=self._config.command, args=list(self._config.args))
        return stdio_client(params)


def _join_content(result: object) -> str:  # pragma: no cover - real content mapping ((3) ignition)
    """Join a ``CallToolResult``'s content blocks into one text string (best-guess, confirmed at
    ignition). Reads ``.content`` (a list of blocks) and concatenates each block's ``.text`` when
    present; a non-text block is stringified. Absent content => empty string (never a fabricated value).
    The result is UNTRUSTED - the invoker re-floors it (D100-3)."""
    content = getattr(result, "content", None)
    if content is None:
        return ""
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        parts.append(text if isinstance(text, str) else str(block))
    return "".join(parts)


def _drop_session_id(cm):  # pragma: no cover - streamable-http yields a 3-tuple ((3) ignition)
    """Adapt ``streamablehttp_client`` (which yields ``(read, write, get_session_id)``) to the
    ``(read, write)`` shape the caller expects, so both transports share one call path. Confirmed at
    ignition; a stdio client already yields the 2-tuple directly."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _wrapper():
        async with cm as triple:
            read, write = triple[0], triple[1]
            yield read, write

    return _wrapper()


#: Best-guess default manifest for an MCP tool when the protected catalog does not pin one. Fail-safe:
#: a server tool is assumed to LEAVE the machine (it is a third party) and to be READ_ONLY unless the
#: catalog says otherwise - so the Guard escalates non-public egress by default (D114-(3), deny-by-default).
def default_mcp_manifest(name: str) -> ToolManifest:  # pragma: no cover - convenience for ignition
    """A conservative :class:`ToolManifest` for an MCP tool (deny-by-default posture, D114).

    ``LEAVES_EXTERNAL`` by default (a third-party server is off-machine) so the Guard mechanically
    escalates a call carrying non-public data (M2), and ``READ_ONLY`` so a life-action must be OPTED
    into explicitly in the protected catalog. The real manifest is the catalog entry user sanctions."""
    return ToolManifest(
        name=name,
        backend=ToolBackend.MCP_SERVER,
        io_schema="input -> text",
        permissions=(),
        egress=DataEgress.LEAVES_EXTERNAL,
        effect=ToolEffect.READ_ONLY,
    )
