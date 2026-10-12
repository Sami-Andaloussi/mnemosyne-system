"""``make garde-emit`` - EMIT the shell guard to another host (D163: the address, not the copy).

The edge: it resolves Mnemosyne's root and hands it to the single home
(:func:`~mnemosyne.production.garde_shell.contrat_emis`), which renders the exact text to install.
This module writes nothing on the host: installation stays an explicit gesture by that host.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ..production.garde_shell import contrat_emis


def main() -> int:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    racine = Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]
    if not (racine / "system" / "lib" / "mnemosyne").is_dir():
        print(
            f"REFUSED: `{racine}` does not contain `system/lib/mnemosyne` - the emitted contract "
            "would point to a judge that cannot be found, and the hook would fail OPEN silently on "
            "the host. Re-run from the repo root, or set CLAUDE_PROJECT_DIR.",
            file=sys.stderr,
        )
        return 2
    print(contrat_emis(str(racine)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
