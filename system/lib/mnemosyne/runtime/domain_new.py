"""domain-new (D46) — create a new library domain from the CLI (shelf + taxonomy, EMIT the policy line).

Codifies the manual shelf-and-declare dance (:mod:`mnemosyne.ingest.domain_lifecycle`): it makes the
shelf tree and writes the taxonomy line (the versioned shelf source), then EMITS the one policy line for a
human to add — writing the policy zone is a privileged gesture (POLICY_WRITE), never Mnémosyne's (D114 /
the tag/declare lockstep D72). Run::

    make domain-new DOMAIN=macro FAMILY=Economics GROUP=Macro
    python -m mnemosyne.runtime.domain_new --domain macro --family Economics --group Macro

Reads the CURRENT taxonomy + policy declarations so it stays idempotent (an already-mapped domain is left
alone) and emits the RIGHT residual gesture (nothing to add if policy already declares it). Code &
docstrings English (D117)."""

from __future__ import annotations

from pathlib import Path

from ..ingest.domain_lifecycle import DomainPlan

#: Repo root from this module (``system/lib/mnemosyne/runtime/domain_new.py`` → parents[4] is the repo).
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RAW_ROOT = _REPO_ROOT / "knowledge" / "raw"
DEFAULT_DISTILLED_ROOT = _REPO_ROOT / "knowledge" / "distilled"
DEFAULT_TAXONOMY = _REPO_ROOT / "system" / "config" / "taxonomy.toml"


def render_domain_result(plan: DomainPlan) -> str:
    """Render what was done + the ONE governed step that remains, as readable markdown.

    Honest by construction: it names the shelf tree and the taxonomy edit it made, then FLAGS the residual
    POLICY_WRITE gesture as the user's (never done here) — or states the domain is ready when policy already
    declares it. It never implies a tagged book is searchable before its domain is declared (D72)."""
    lines = [
        f"# Domain — {plan.domain}",
        "",
        f"- **shelf (raw)**: knowledge/raw/{plan.raw_shelf}/",
        f"- **shelf (distilled)**: knowledge/distilled/{plan.distilled_shelf}/",
    ]
    if plan.already_mapped:
        lines.append("- **taxonomy**: already mapped — left unchanged")
    else:
        lines.append(f"- **taxonomy**: added `{plan.taxonomy_line}` to system/config/taxonomy.toml")
    lines += ["", "## [OPERATOR] one governed step remains — POLICY_WRITE"]
    if plan.already_declared:
        lines.append(
            f"Policy already declares `{plan.domain}` — nothing to add. The domain is ready."
        )
    else:
        lines.append(f"To make books tagged `{plan.domain}` searchable, {plan.policy_hint}.")
        lines.append(
            "Until then the shelf exists but its books stay withheld from recall (deny-by-default)."
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI over the real config/shelf
    """Parse DOMAIN/FAMILY/GROUP, create the shelf + taxonomy line, print the result + the policy gesture."""
    import argparse

    from ..config import load_policy
    from ..ingest.domain_lifecycle import create_domain, plan_new_domain
    from ..ingest.library import KNOWLEDGE_BUBBLE
    from ..ingest.taxonomy import all_domains

    parser = argparse.ArgumentParser(description="Create a new library domain (D46).")
    parser.add_argument("--domain", required=True, help="kebab-case RAG tag, e.g. macro")
    parser.add_argument("--family", required=True, help="navigation Famille, e.g. Economics")
    parser.add_argument("--group", required=True, help="navigation Groupe, e.g. Macro")
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--distilled-root", type=Path, default=DEFAULT_DISTILLED_ROOT)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    args = parser.parse_args(argv)

    declared = frozenset(load_policy().declared_domains.get(KNOWLEDGE_BUBBLE, frozenset()))
    plan = plan_new_domain(
        args.domain,
        args.family,
        args.group,
        mapped_domains=all_domains(),
        declared_domains=declared,
    )
    create_domain(
        plan,
        raw_root=args.raw_root,
        distilled_root=args.distilled_root,
        taxonomy_path=args.taxonomy,
    )
    print(render_domain_result(plan), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
