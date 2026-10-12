"""``make moisson`` - emit the harvest contract for a finished project arc (D24 / D37, soul §3).

    make moisson PROJET="projects/example-project"
    make moisson PROJET="projects/example-project" EXPERTS=5 MECANICIENS=3

Prints an orchestration contract. It runs no agent and calls no model: the orchestrator that
executes it is a frontier agent (or the user's session), and the experts it recruits are its own
sub-agents. Mnemosyne emits contracts; agents execute them.

Refuses an unknown project path rather than emitting a contract about nothing - and lists the
bubbles that do exist, because a mistyped path is the likeliest reason to land here.

Code English (D117); the emitted contract is French, like every other emission seam.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..production.harvest import HarvestError, build_harvest_contract, known_projects

REPO_ROOT = Path(__file__).resolve().parents[3].parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="make moisson",
        description="Emit the harvest contract: what a project arc must return to the system.",
    )
    parser.add_argument("--projet", required=True)
    parser.add_argument(
        "--experts", type=int, default=3, help="floor of DOMAIN expert agents"
    )
    parser.add_argument(
        "--mecaniciens", type=int, default=2, help="floor of mechanical readers"
    )
    parser.add_argument("--racine", type=Path, default=REPO_ROOT)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if not (args.racine / args.projet).is_dir():
        existing = known_projects(args.racine)
        print(
            f"[moisson] REFUSED: {args.projet!r} is not a project folder.\n"
            + ("Known projects:\n" + "\n".join(f"  {p}" for p in existing) if existing else ""),
            file=sys.stderr,
        )
        return 2

    try:
        print(
            build_harvest_contract(
                args.projet, domain_agents=args.experts, mechanic_agents=args.mecaniciens
            ),
            end="",
        )
    except HarvestError as exc:
        print(f"[moisson] REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
