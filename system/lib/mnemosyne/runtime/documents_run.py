"""Implementation behavior is covered by tests."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from ..production.documents import documents_orphelins, liens_morts, rendre
from ..production.sessions import _REPO_ROOT


def suivis(racine: Path, motif: str | None = None) -> tuple[str, ...]:
    """What git tracks. A git failure returns nothing AND says so - never a silent empty scan."""
    argv = ["git", "-C", str(racine), "ls-files"]
    if motif:
        argv.append(motif)
    sortie = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    if sortie.returncode != 0:
        raise RuntimeError(sortie.stderr.strip() or "git ls-files failed")
    return tuple(ligne for ligne in sortie.stdout.splitlines() if ligne.strip())


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - [OPERATOR] surface (host tree)
    parser = argparse.ArgumentParser(
        description="List the documents that nothing cites anymore (read-only, moves nothing)."
    )
    parser.add_argument("--racine", type=Path, default=_REPO_ROOT, help="repo to examine")
    args = parser.parse_args(argv)

    try:
        documents = suivis(args.racine, "*.md")
        corpus = suivis(args.racine)
    except (OSError, RuntimeError, subprocess.SubprocessError) as echec:
        # Do NOT return "0 orphans" when the population could not be drawn: a scan that
        # looked at nothing would read as a healthy repo. The cause is named, and the rc bites.
        print(
            f"REFUSED: could not draw the population tracked by git: {echec}\n"
            f"This is NOT 'no orphan document' - nothing was examined.",
            file=sys.stderr,
        )
        return 2

    orphelins = documents_orphelins(args.racine, documents, corpus)
    morts = liens_morts(args.racine, documents)
    print(rendre(orphelins, examines=len(documents), morts=morts))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
