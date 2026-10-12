"""``make depense`` (D155 / D86) — what Mnémosyne's own code spent, and against which ceilings.

Reads the durable ledger and the two ceilings that ``policy.toml`` has always declared and that
nothing read until now (``daily_cost_ceiling_eur``, ``frontier_token_ceiling``)::

    make depense              # today
    make depense JOUR=2026-07-19

**It reports; it does not enforce.** The enforcement lives where the money is actually spent —
:class:`~mnemosyne.runtime.runner_anthropic.AnthropicBackend` checks the ceilings before every
request and refuses fail-closed. This surface exists so the operator can see the number before it becomes a
refusal, which is the whole point of a ceiling being knowable in advance.

**Scope, printed on every run and worth repeating here:** it counts what MNÉMOSYNE'S CODE spends
(distillation campaigns, caption passes, a sibling project's production run). It cannot see the Claude Code
session — that is a subscription, in another process. "€0.00" means "our code did not spend".

Brick-free and read-only. Code English (D117); the report is for the operator, so it prints French.
"""

from __future__ import annotations

import argparse
import sys

from ..production.spend import SpendLedger, policy_ceilings, render_spend


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - [OPERATOR] surface (reads the ledger)
    parser = argparse.ArgumentParser(
        prog="make depense",
        description="Report what Mnémosyne's own code spent today, against the configured ceilings.",
    )
    parser.add_argument(
        "--jour", default="", help="local day to report, full ISO date YYYY-MM-DD (default: today)"
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    cost_ceiling, token_ceiling = policy_ceilings()
    ledger = SpendLedger()
    print(
        render_spend(
            ledger.spent(args.jour or None),
            cost_ceiling_eur=cost_ceiling,
            token_ceiling=token_ceiling,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
