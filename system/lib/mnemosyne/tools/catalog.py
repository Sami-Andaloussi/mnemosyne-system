"""ConfigToolCatalog (D114-(5)) - the protected tool / MCP allow-list, deny-by-default.

The concrete :class:`~mnemosyne.ports.tools.ToolCatalog` the Guard reads to govern the 8th effect
(``TOOL_CALL``). It loads ``system/config/tools.toml`` - a sibling of the policy zone, equally
protected (SE4) - into an immutable name -> :class:`~mnemosyne.ports.tools.ToolManifest` map. The
Guard rules from THIS manifest, never the caller's word (D100); a tool absent here is refused
fail-closed, so a surveilled agent can never wire itself to an arbitrary tool / MCP server (D114-(5)).

Read-only is structural: the catalog is built once from the frozen file and hands out manifests,
never a mutable handle on its map (D100 - incapacity, not trust). Adding a tool is a privileged human
act mediated as ``Effect.POLICY_WRITE`` (D102), out of any agent's reach.

Deny-by-default holds at every seam: a missing file, an empty file, or an unknown tool name all
authorize NOTHING (fail-closed, D89). A DUPLICATE name in the file is REFUSED at load - a second
entry must not silently shadow the first (enforce-collisions-structurally: an "improbable" id
collision is cloisonnée by construction, incapacity > probabilistic bet). Read by the standard-library
``tomllib`` - no dependency, so the barrier holds before the toolchain lands (D116). Code & docstrings
English (D117); the governance tokens stay their canonical forms.

Decisions: D114 (tool abstraction + MCP)  -  D114-(5) (protected catalog, privileged wiring)  -  D73 / D89
(deny-by-default reference monitor)  -  D102 / SE4 (protected zone)  -  D100 (structural incapacity).
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import MappingProxyType

from ..ports import (
    DataEgress,
    GuardDenied,
    ToolBackend,
    ToolEffect,
    ToolManifest,
)

#: The protected tool zone: ``<repo>/system/config/tools.toml`` (sibling of ``policy.toml``),
#: resolved from this module's home (``system/lib/mnemosyne/tools/catalog.py`` -> ``parents[3]`` is
#: ``system``). A missing file is deny-by-default (an empty allow-list), never an error.
DEFAULT_TOOLS_PATH: Path = Path(__file__).resolve().parents[3] / "config" / "tools.toml"


def _one_of[E](raw: object, by_token: Mapping[str, E], *, field: str, name: str) -> E:
    """Parse a French/enum token to its member; an unknown token RAISES (never silently widens -
    a typo in the protected zone must fail loudly, not authorise something broader, D100)."""
    if not isinstance(raw, str) or raw not in by_token:
        raise ValueError(
            f"tool {name!r}: {field}={raw!r} is not one of {sorted(by_token)} "
            "(deny-by-default: an unknown token authorises nothing)"
        )
    return by_token[raw]


_BACKEND_BY_TOKEN: Mapping[str, ToolBackend] = MappingProxyType({b.value: b for b in ToolBackend})
_EGRESS_BY_TOKEN: Mapping[str, DataEgress] = MappingProxyType({e.value: e for e in DataEgress})
_EFFECT_BY_TOKEN: Mapping[str, ToolEffect] = MappingProxyType({e.value: e for e in ToolEffect})


class ConfigToolCatalog:
    """The allow-list of tools / MCP servers user has sanctioned (D114-(5)), read from the protected zone.

    A structural :class:`~mnemosyne.ports.tools.ToolCatalog` (duck-typed, like every concrete engine
    in the fabric - never subclassing the Protocol): it exposes ``authorized`` + ``get`` and nothing
    that could mutate the frozen allow-list."""

    __slots__ = ("_by_name",)

    def __init__(self, manifests: Iterable[ToolManifest]) -> None:
        by_name: dict[str, ToolManifest] = {}
        for manifest in manifests:
            if manifest.name in by_name:
                # a duplicate allow-list entry must not silently shadow the first - refuse fail-closed
                # (enforce-collisions-structurally: incapacity > "it won't happen", proven real 3× in (3)).
                raise ValueError(
                    f"duplicate tool name {manifest.name!r} in the allow-list - refused: a second "
                    "entry cannot shadow the first (D114-(5), deny-by-default)"
                )
            by_name[manifest.name] = manifest
        self._by_name: Mapping[str, ToolManifest] = MappingProxyType(by_name)

    @classmethod
    def load(cls, path: Path | None = None) -> ConfigToolCatalog:
        """Load the protected tool allow-list (SE4). Deny-by-default: a MISSING file is an EMPTY
        catalog (every tool refused), never an error - the skeleton ships with no tool wired (D98)."""
        source = path if path is not None else DEFAULT_TOOLS_PATH
        if not source.exists():
            return cls(())
        data = tomllib.loads(source.read_text(encoding="utf-8"))
        return cls(_parse_manifests(data.get("tools", [])))

    def authorized(self) -> tuple[ToolManifest, ...]:
        """The full allow-list of tools user has sanctioned (D114-(5))."""
        return tuple(self._by_name.values())

    def get(self, name: str) -> ToolManifest:
        """The manifest for ``name``, or :class:`GuardDenied` if it is not allow-listed (deny-by-default).

        Raising rather than returning ``None`` keeps the Guard's ``_rule_tool_call`` fail-closed:
        an unknown tool is a refusal, never a guess (D73 / D100)."""
        try:
            return self._by_name[name]
        except KeyError:
            raise GuardDenied(
                f"tool {name!r} is not on the protected allow-list - refused (D114-(5), deny-by-default)"
            ) from None


def _parse_manifests(rows: object) -> tuple[ToolManifest, ...]:
    """Parse the ``[[tools]]`` array of the protected zone into manifests, fail-closed on any
    malformed row (a bad manifest authorises nothing - it raises, never degrades to a laxer tool)."""
    if not isinstance(rows, list):
        raise ValueError("tools zone: [[tools]] must be an array of tables (deny-by-default)")
    manifests: list[ToolManifest] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("tools zone: each [[tools]] entry must be a table")
        name = row.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"tools zone: a [[tools]] entry has no valid name (got {name!r})")
        permissions = tuple(str(p) for p in row.get("permissions", []))
        manifests.append(
            ToolManifest(
                name=name,
                backend=_one_of(row.get("backend"), _BACKEND_BY_TOKEN, field="backend", name=name),
                io_schema=str(row.get("io_schema", "")),
                permissions=permissions,
                egress=_one_of(row.get("egress"), _EGRESS_BY_TOKEN, field="egress", name=name),
                effect=_one_of(row.get("effect"), _EFFECT_BY_TOKEN, field="effect", name=name),
            )
        )
    return tuple(manifests)
