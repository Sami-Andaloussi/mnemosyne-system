"""``make plan-gate-emit`` — EMIT the plan gate to another host (D163: the address, not
the copy).

**THIS MODULE WAS MISSING, AND IT WAS THE FIRST GAP THAT `J1` DID NOT CLOSE.** `runtime/
plan_gate_run.py` is the JUDGE (installed on the host, it refuses or lets through); this one is
the EMITTER (pulled HERE, it prints the text to install) — the same distinction as `garde_shell_run`
(judge) vs `garde_emit_run` (emitter) for the bash guard. Conflating them would have left `J1`
without a command even though its `*Produit*` names one.

The boundary: it resolves Mnémosyne's root and hands it to the single source
(:func:`~mnemosyne.production.plan_gate_shell.contrat_emis`), which renders the exact text to install.
This module writes NOTHING anywhere — installing it is the host's own gesture.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ..production.plan_gate_shell import contrat_emis


def main() -> int:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    racine = Path(depuis_env) if depuis_env else Path(__file__).resolve().parents[4]
    if not (racine / "system" / "lib" / "mnemosyne").is_dir():
        print(
            f"REFUSED: `{racine}` does not contain `system/lib/mnemosyne` — the emitted contract "
            "would point at a judge that cannot be found, and the gate would REFUSE every commit "
            "on the host (R3/R4, 2026-08-17: an invocation failure now blocks, it no longer passes "
            "silently). Re-run this from the repository root, or set CLAUDE_PROJECT_DIR.",
            file=sys.stderr,
        )
        return 2
    print(contrat_emis(str(racine)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
