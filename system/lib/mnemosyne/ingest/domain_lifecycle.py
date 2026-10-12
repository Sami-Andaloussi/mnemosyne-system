"""Domain lifecycle (D46) — create a new library domain, codifying the manual shelf-and-declare dance.

Adding a domain to the reference library touches THREE places in lockstep (the ``macro`` dance done by
hand this session): (1) the physical shelf tree ``knowledge/raw/<Fam>/<Grp>/<domain>/<type>/`` (+ the
``distilled/`` mirror); (2) the taxonomy map ``system/config/taxonomy.toml`` (the shelf's single source,
[[contract-single-source-emit]]); (3) the policy declaration ``[domains]."knowledge"`` in
``system/config/policy.toml`` — WITHOUT which every book tagged with the new domain is silently withheld
from recall (deny-by-default, D72 / invariant 4).

This module codifies (1)+(2) so a non-technical hand never mis-edits them, and for (3) it EMITS the exact
line for a human to add: writing the policy zone is a privileged act (POLICY_WRITE) reserved to a human
gesture — Mnémosyne prepares and flags, it never writes policy itself (D114 / the tag/declare lockstep
D72). So the door does the safe two-thirds and hands the governed third to the operator, visibly.

Non-destructive (D44 / D56): shelf creation is idempotent ``mkdir``; the taxonomy write proves the edited
text round-trips through ``tomllib`` (and that the new domain lands INSIDE ``[domains]``) BEFORE touching
the file, and backs the original up once — a governed shelf source is never left corrupt. Read by stdlib
``tomllib`` — no brick, holds before the toolchain (D116). Code & docstrings English (D117); the shelf /
domain / family tokens stay as graven in the toml.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

#: A domain is kebab-case — the fine RAG tag grain (e.g. ``asset-pricing``); family/group are the
#: navigation layers (e.g. ``Finance`` / ``Machine-Learning``). A malformed token fails loud (never
#: mis-shelves, D100). The tail anchor is ``\Z`` (the very end), NOT ``$`` — ``$`` also matches just
#: before a trailing newline, so ``"macro\n"`` would slip through and yield a junk shelf name.
_DOMAIN_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_NAV_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\Z")
#: The shared reference-library bubble (D140). A literal here (not an import) keeps this pure planner
#: import-light; it must match :data:`mnemosyne.ingest.library.KNOWLEDGE_BUBBLE` (the functional lookup
#: in the door uses that real constant — only this hint TEXT uses the literal).
_KNOWLEDGE_BUBBLE = "knowledge"


class DomainLifecycleError(ValueError):
    """A malformed domain request or an un-parseable taxonomy — fail loud, never mis-shelve (D100)."""


@dataclass(frozen=True, slots=True)
class DomainPlan:
    """The planned three-part change for a new domain — pure, computed before any I/O.

    ``taxonomy_line`` is written by :func:`create_domain` (the versioned shelf source); ``policy_hint`` is
    the POLICY_WRITE gesture EMITTED for a human, never written here. ``raw_shelf`` / ``distilled_shelf``
    are RELATIVE to their roots. ``already_mapped`` / ``already_declared`` make the write idempotent and
    tailor the emitted gesture."""

    domain: str
    family: str
    group: str
    raw_shelf: Path
    distilled_shelf: Path
    taxonomy_line: str
    policy_hint: str
    already_mapped: bool
    already_declared: bool


def plan_new_domain(
    domain: str,
    family: str,
    group: str,
    *,
    mapped_domains: frozenset[str],
    declared_domains: frozenset[str],
    default_type: str = "books",
) -> DomainPlan:
    """Validate + compute the three-part change for a new domain (D46). PURE — no I/O.

    Refuses a malformed token rather than mis-shelving. ``already_mapped`` / ``already_declared`` let the
    door skip a redundant write and emit the RIGHT residual gesture (nothing to add if policy already
    declares it)."""
    if not _DOMAIN_RE.match(domain):
        raise DomainLifecycleError(
            f"domain {domain!r} must be kebab-case [a-z0-9-] (the fine RAG tag, e.g. 'asset-pricing')"
        )
    for label, value in (("family", family), ("group", group)):
        if not _NAV_RE.match(value):
            raise DomainLifecycleError(
                f"{label} {value!r} must be a navigation token [A-Za-z0-9-] "
                "(e.g. 'Finance', 'Machine-Learning')"
            )
    rel = Path(family) / group / domain / default_type
    policy_hint = (
        f'add "{domain}" to the "{_KNOWLEDGE_BUBBLE}" array under [domains] in '
        "system/config/policy.toml (POLICY_WRITE — a human gesture; the KB withholds a tagged book "
        "until its domain is declared here, D72 / invariant 4)"
    )
    return DomainPlan(
        domain=domain,
        family=family,
        group=group,
        raw_shelf=rel,
        distilled_shelf=rel,
        taxonomy_line=f'{domain} = ["{family}", "{group}"]',
        policy_hint=policy_hint,
        already_mapped=domain in mapped_domains,
        already_declared=domain in declared_domains,
    )


def _is_table_header(line: str) -> bool:
    t = line.strip()
    return t.startswith("[") and t.endswith("]")


def _index_of(
    lines: list[str], pred: Callable[[str], bool], *, after: int = -1, before: int | None = None
) -> int | None:
    """First index ``i`` in ``(after, before)`` with ``pred(lines[i])`` true, else ``None``."""
    stop = len(lines) if before is None else before
    for i in range(after + 1, stop):
        if pred(lines[i]):
            return i
    return None


def _last_nonblank(lines: list[str], start: int, end: int) -> int:
    """Index of the last non-blank line in ``[start, end)``, or ``start - 1`` if the slice is all blank."""
    for i in range(end - 1, start - 1, -1):
        if lines[i].strip():
            return i
    return start - 1


def insert_taxonomy_line(text: str, domain: str, family: str, group: str) -> str:
    """Insert ``<domain> = ["<family>", "<group>"]`` into the ``[domains]`` table, grouped under its
    ``# --- Famille <family> ---`` block (a new block is created just after the last domain if the family
    is new). PURE string→string; the caller round-trips the result through ``tomllib`` before writing.
    Raises if the ``[domains]`` table is absent (never blind-appends to an unrecognised file)."""
    new_line = f'{domain} = ["{family}", "{group}"]'
    lines = text.splitlines()
    start = _index_of(lines, lambda s: s.strip() == "[domains]")
    if start is None:
        raise DomainLifecycleError(
            "taxonomy has no [domains] table — refusing to guess where to insert"
        )
    end = _index_of(lines, _is_table_header, after=start)
    end = end if end is not None else len(lines)
    header = f"# --- Famille {family} ---"
    fam_at = _index_of(lines, lambda s: s.strip() == header, after=start, before=end)
    if fam_at is not None:
        # Append after the LAST line of this family block: before the next '# ---' or the table's end.
        nxt = _index_of(lines, lambda s: s.strip().startswith("# ---"), after=fam_at, before=end)
        insert_at = nxt if nxt is not None else _last_nonblank(lines, fam_at + 1, end) + 1
    else:
        # A new family: a fresh block appended after the last existing domain (before the trailing [types]).
        insert_at = _last_nonblank(lines, start + 1, end) + 1
        new_line = f"{header}\n{new_line}"
    lines.insert(insert_at, new_line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def create_domain(
    plan: DomainPlan,
    *,
    raw_root: Path,
    distilled_root: Path,
    taxonomy_path: Path,
    write_taxonomy: bool = True,
) -> None:
    """Apply the SAFE two-thirds of ``plan``: make the shelf tree (idempotent) and write the taxonomy line
    (round-trip-verified + backed up). NEVER writes policy — the caller EMITS ``plan.policy_hint`` for a
    human. Idempotent: an existing tree is left as is; an already-mapped domain skips the taxonomy write."""
    (raw_root / plan.raw_shelf).mkdir(parents=True, exist_ok=True)
    (distilled_root / plan.distilled_shelf).mkdir(parents=True, exist_ok=True)
    if write_taxonomy and not plan.already_mapped:
        _write_taxonomy_line(plan, taxonomy_path)


def _write_taxonomy_line(plan: DomainPlan, taxonomy_path: Path) -> None:
    """Insert the taxonomy line, PROVING the result round-trips (and the domain lands inside ``[domains]``)
    before touching the file, and backing the original up once (non-destructive, fail-closed — a governed
    shelf source is never left corrupt)."""
    original = taxonomy_path.read_text(encoding="utf-8")
    updated = insert_taxonomy_line(original, plan.domain, plan.family, plan.group)
    try:
        parsed = tomllib.loads(updated)
    except (
        tomllib.TOMLDecodeError
    ) as exc:  # pragma: no cover - defensive; the pure inserter stays valid
        raise DomainLifecycleError(
            f"refusing to write taxonomy: the edited {taxonomy_path} would not parse ({exc})"
        ) from exc
    if plan.domain not in parsed.get(
        "domains", {}
    ):  # pragma: no cover - defensive; inserter targets it
        raise DomainLifecycleError(
            f"refusing to write taxonomy: {plan.domain!r} did not land inside [domains] after the edit"
        )
    backup = taxonomy_path.parent / (taxonomy_path.name + ".bak")
    backup.write_text(original, encoding="utf-8")
    taxonomy_path.write_text(updated, encoding="utf-8")
