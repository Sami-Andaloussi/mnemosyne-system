"""ToolPlugin & MCP (D114) - one normed prise for three back-ends.

A tool is a **local function**, an **API call**, or a tool offered by a
third-party **MCP server** - all seen through ONE normed interface. So "MCP
client" is NOT a separate architecture: it is one of the back-ends behind the
single prise (anti-duplication, D114-(1)). The Guard mediates EVERY call at BOTH
ends (D114-(3)):

* **Outbound** - right to call this tool? and if the tool *leaves* to the
  external world and the arguments carry ``sensible``, it is **blocked
  mechanically** (the label travels with the data, D108-(5); the Guard reads it;
  sensible-local applies by itself - D27 / D66).
* **Return** - a tool result is **UNTRUSTED data** (zero-trust, D81),
  re-labelled by the maximum (D101), able only to raise prudence, never to
  trigger an action alone (D100).

The **catalog of authorized tools / MCP servers** lives in ``system/config``
(protected zone, D73-4): branching a new tool is a PRIVILEGED human act
(FLAG + validation) - an agent can NEVER wire itself to an arbitrary MCP server
(D114-(5)). Tools run inside the two-tier sandbox (D99). Default OSS brick: the
**MCP Python SDK** client; the prise + Guard wiring are ours - see
``system/config/oss_registry.md`` (D114).

Decisions: D114 (tool abstraction + MCP)  -  D108 (I/O schema reuse)  -  D89 / D73
(Guard mediation, protected catalog)  -  D91 (life-action effect)  -  D99
(sandboxed execution)  -  D101 (re-label return). Invariants carried: 21, 22
(substrate of 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from .core import Envelope
from .guard import Grant


class ToolBackend(Enum):
    """The three back-ends behind the single prise (D114-(1))."""

    LOCAL_FUNCTION = "local_function"
    API = "api"
    MCP_SERVER = "mcp_server"


class DataEgress(Enum):
    """Whether a tool keeps data local or sends it outside (D114-(2))."""

    STAYS_LOCAL = "stays_local"
    LEAVES_EXTERNAL = "leaves_external"  # `sensible` args blocked mechanically (D114-(3))


class ToolEffect(Enum):
    """Whether a tool merely reads or acts upon the world (D114-(2) / D91)."""

    READ_ONLY = "read_only"
    LIFE_ACTION = "life_action"  # email / payment / publish / sign / delete (D74)


@dataclass(frozen=True, slots=True)
class ToolManifest:
    """What the Guard reads to govern a tool (D114-(2)). Deny-by-default: no
    manifest -> blocked (D73). The ``io_schema`` reuses the D108 contract."""

    name: str
    backend: ToolBackend
    io_schema: str
    permissions: tuple[str, ...]
    egress: DataEgress
    effect: ToolEffect


@runtime_checkable
class ToolPlugin(Protocol):
    """A single tool, whatever its back-end, governed by the Guard at both ends."""

    manifest: ToolManifest

    def invoke(self, call: Envelope[object], *, grant: Grant) -> Envelope[object]:
        """Invoke the tool. ``grant`` proves the Guard cleared the OUTBOUND side
        (right to call + no ``sensible`` leaving via a ``LEAVES_EXTERNAL`` tool).
        The returned envelope is UNTRUSTED, re-labelled by the maximum (D101) and
        able only to raise prudence (D100)."""
        ...


@runtime_checkable
class ToolCatalog(Protocol):
    """The allow-list of authorized tools / MCP servers (D114-(5)).

    Lives in ``system/config`` (protected, write-only by a privileged human act,
    D73-4) and is read-only to surveilled agents: an agent can never add a tool
    or connect to an arbitrary MCP server by itself.
    """

    def authorized(self) -> tuple[ToolManifest, ...]:
        """The full allow-list of tools user has sanctioned."""
        ...

    def get(self, name: str) -> ToolManifest:
        """Return the manifest for ``name``, or raise
        :class:`~mnemosyne.ports.core.GuardDenied` if it is not allow-listed."""
        ...
