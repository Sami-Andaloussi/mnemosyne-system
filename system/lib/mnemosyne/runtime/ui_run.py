"""Ui run for Mnemosyne System."""

from __future__ import annotations

import json

from ..production.ui_contract import Sources, build_contract


def render_contract(sources: Sources | None = None) -> str:
    """The contract, JSON, indented and unescaped - a human can read it, a machine does not care.

    ``sources`` is injectable for one reason: the SERIALISATION is the half an interface actually
    consumes, and a mutation trial found it covered by nothing - every test drove the payload
    builder directly, so a render that emitted Python ``repr`` instead of JSON passed them all.
    """
    return json.dumps(build_contract(sources), ensure_ascii=False, indent=2) + "\n"


def main() -> int:  # pragma: no cover - CLI over the real tree
    print(render_contract(), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
