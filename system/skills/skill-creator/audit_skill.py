#!/usr/bin/env python3
"""`skill-audit` seam — the judge-analog for a candidate skill (D75 / D100 — producer !=
verifier applied to a skill's anatomy, not to its distilled content).

Does the orchestration (globbing the candidate folder, reading the root Makefile, scanning
`system/lib/mnemosyne/production/*.py` for `*_PROMPT`/`*_TEMPLATE` constants via `ast`) then
calls the PURE verdict `mnemosyne.production.audit_skill(...)` — exactly like `judge_library.py`
walks `knowledge/` and calls the pure `judge_fiche`. NO model / NO brick required here.

Writes nothing (neither the candidate nor a report file): prints a report and exits with the
verdict's return code (0 if `ok`, 1 otherwise) — a skill-audit that checks a single candidate is a
GATE, unlike `make judge`, which sweeps the whole library and always returns 0, informationally.

Usage: make skill-audit DIR="system/skills/<name>"
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

#: Matches a *_PROMPT / *_TEMPLATE / *_SCHEMA constant name, with or without a leading underscore
#: (private module constants like `_PROMPT_TEMPLATE` in distillation.py) — the SAME family
#: `audit_skill`'s anti-drift check scans a candidate SKILL.md against (see skills.py /
#: SKILL_ANATOMY_TEMPLATE). ``_SCHEMA`` is included so a future ``FOO_SCHEMA = \"\"\"...\"\"\"`` a
#: model must follow cannot drift into a SKILL.md undetected (harmless today: ``DISTILL_SCHEMA`` is
#: a ``json.dumps(...)`` call, not a string literal, so it is not among the scanned constants yet).
_CONST_NAME_RE = re.compile(r"^_?[A-Z][A-Z0-9_]*(_PROMPT|_TEMPLATE|_SCHEMA)$")

#: A model-contract TOKEN: any name ending in _PROMPT / _TEMPLATE / _SCHEMA. Used to decide whether
#: a candidate skill has a model-facing contract at all (and so whether it NEEDS an emit seam).
_CONTRACT_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9_]*(_PROMPT|_TEMPLATE|_SCHEMA)$")

#: Where every skill's code home lives — the derived home for a skill named ``<name>`` is
#: ``<name>.py`` here (with hyphens as underscores), exactly what ``make skill-new`` writes.
_PROD_ROOT = Path("system/lib/mnemosyne/production")

_RULE = "=" * 88


def prompt_like_constants(py_root: Path) -> dict[str, str]:
    """Every ``*_PROMPT`` / ``*_TEMPLATE`` / ``*_SCHEMA`` STRING constant defined at module level
    anywhere under ``py_root`` (``system/lib/mnemosyne/production/``, where every skill's code home
    lives) — the exact set the anti-drift check scans a candidate SKILL.md against. AST-based (not a
    regex over source text) so a constant's real, fully-escaped VALUE is compared — what actually
    ends up in a SKILL.md if hand-copied, not its source-code spelling (quotes, continuations, ...)."""
    found: dict[str, str] = {}
    for path in sorted(py_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue  # a candidate skill's own broken stub must never crash the audit (D100)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and _CONST_NAME_RE.match(target.id):
                    found[f"{path.stem}.{target.id}"] = node.value.value
    return found


def _emit_targets_referencing(makefile_text: str, dir_token: str) -> list[str]:
    """Target names ending in ``-emit`` whose RECIPE body mentions this skill's own directory path
    — ties an abbreviated Make target (``distill-emit``, not ``distillateur-emit``: the target is a
    short mnemonic, not the literal folder name) back to the skill it belongs to, without assuming
    any naming convention between the two."""
    hits: list[str] = []
    lines = makefile_text.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^(\S+-emit):", lines[i])
        if not m:
            i += 1
            continue
        target = m.group(1)
        i += 1
        recipe: list[str] = []
        while i < len(lines) and (lines[i].startswith("\t") or not lines[i].strip()):
            recipe.append(lines[i])
            i += 1
        if any(dir_token in line for line in recipe):
            hits.append(target)
    return hits


def has_emit_seam(skill_dir: Path, makefile_text: str) -> bool:
    """A skill has an emit seam iff a ``.py`` file WHOSE NAME MENTIONS "emit" sits in its folder
    (``finish_emit.py``, ``skill_emit.py`` — suffixed — but also ``emit_prompts.py`` — prefixed:
    the convention is "the word appears", not a fixed position), and/or the root Makefile declares
    an ``*-emit:`` target whose recipe runs something from THIS skill's own directory. Either is
    enough; both absent means no frontier host can ever receive the real contract."""
    has_emit_file = any(re.search(r"emit", p.stem, re.IGNORECASE) for p in skill_dir.glob("*.py"))
    dir_token = f"system/skills/{skill_dir.name}/"
    has_make_target = bool(_emit_targets_referencing(makefile_text, dir_token))
    return has_emit_file or has_make_target


def has_model_contract(skill_dir: Path) -> bool:
    """Does this candidate skill have a model-facing contract at all — and so NEED an emit seam?

    True iff any of the skill's own ``*.py`` DEFINES or REFERENCES a name matching
    ``*_PROMPT`` / ``*_TEMPLATE`` / ``*_SCHEMA`` (an assignment target, an import, or a use). This
    covers the repo's real architecture, where the contract constant lives in the code home and the
    skill's thin adapter / emit file merely IMPORTS it (often lazily, inside a function): the
    distillateur references ``DISTILL_SCHEMA``, the finisseur ``FINISH_PROMPT``, this skill-creator
    ``SKILL_ANATOMY_TEMPLATE`` -> True ; the ``juge`` references none (it is pure verification
    logic, nothing to emit) -> False. AST-based so a token inside a comment or docstring string is
    NOT counted (only real ``Name`` / import bindings), and a broken stub never crashes the audit."""
    paths = list(skill_dir.glob("*.py"))
    code_home = code_home_path(skill_dir.name)
    if code_home.exists():
        paths.append(code_home)
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            token: str | None = None
            if isinstance(node, ast.Name):
                token = node.id
            elif isinstance(node, ast.alias):
                token = node.asname or node.name
            if token and _CONTRACT_TOKEN_RE.match(token):
                return True
    return False


def code_home_path(name: str) -> Path:
    """The derived code home for a skill: ``production/<name>.py`` (hyphens -> underscores), exactly
    the path ``make skill-new`` writes. Present for a scaffolded skill; ABSENT for an established
    skill whose home is named differently (distillateur -> distillation.py) — an absent path is
    simply not scanned, which is correct (an established, filled skill is not a scaffold)."""
    return _PROD_ROOT / f"{name.replace('-', '_')}.py"


def scaffold_impl_texts(skill_dir: Path, name: str) -> dict[str, str]:
    """The texts the scaffold-marker scan may inspect BEYOND the SKILL.md: the derived code home
    (``production/<name>.py``) and the ``*_run.py`` adapter(s). Deliberately NARROW — it does NOT
    read every ``*.py`` in the skill dir, because the skill-creator's OWN ``new_skill.py`` /
    ``skills.py`` hold the :data:`SCAFFOLD_MARKERS` strings as constants and would false-positive.
    A ``make skill-new`` stub plants the markers in exactly these two places (home + SKILL.md), so
    this catches a stubbed home without ever flagging a real, filled skill."""
    texts: dict[str, str] = {}
    home = code_home_path(name)
    if home.exists():
        texts[str(home)] = home.read_text(encoding="utf-8", errors="replace")
    for adapter in sorted(skill_dir.glob("*_run.py")):
        texts[str(adapter)] = adapter.read_text(encoding="utf-8", errors="replace")
    return texts


def unparseable_skill_py(skill_dir: Path, name: str) -> list[str]:
    """The skill's OWN ``.py`` files that do not parse — the code home + every ``*.py`` in its dir.
    SURFACED (fed to :func:`audit_skill` as a hard failure) instead of silently swallowed: a broken
    emit/code-home stub must not read as clean. Scoped to THIS skill's files only, so an unrelated
    broken file elsewhere in the tree never fails this skill's audit."""
    targets = sorted(skill_dir.glob("*.py"))
    home = code_home_path(name)
    if home.exists():
        targets.append(home)
    broken: list[str] = []
    for path in targets:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, ValueError, UnicodeDecodeError, OSError):
            broken.append(str(path))
    return broken


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print('Usage: make skill-audit DIR="system/skills/<name>"')
        return 1
    skill_dir = Path(args[0])
    if not skill_dir.is_dir():
        print(f"NOT A DIRECTORY: {skill_dir}")
        return 1
    from mnemosyne.production import audit_skill

    name = skill_dir.name
    skill_mds = sorted(skill_dir.rglob("SKILL.md"))
    skill_md_text = skill_mds[0].read_text(encoding="utf-8", errors="replace") if skill_mds else None
    makefile_text = Path("Makefile").read_text(encoding="utf-8", errors="replace")
    constants = prompt_like_constants(_PROD_ROOT)

    requires_emit_seam = has_model_contract(skill_dir)
    verdict = audit_skill(
        name=name,
        skill_md=skill_md_text,
        n_skill_md_files=len(skill_mds),
        has_emit_seam=has_emit_seam(skill_dir, makefile_text),
        requires_emit_seam=requires_emit_seam,
        prompt_constants=constants,
        impl_texts=scaffold_impl_texts(skill_dir, name),
        unparseable_files=unparseable_skill_py(skill_dir, name),
    )

    if verdict.has_emit_seam:
        emit_note = ""
    elif verdict.requires_emit_seam:
        emit_note = "   [REQUIRED — the skill has a model contract but no seam]"
    else:
        emit_note = "   [not required — skill with no model contract to emit, informational]"
    print(f"AUDIT — {skill_dir}\n{_RULE}")
    print(f"  ok            : {verdict.ok}")
    print(f"  emit seam     : {verdict.has_emit_seam}{emit_note}")
    print(f"  SKILL.md      : {len(skill_mds)} found")
    print(
        f"  scaffold_only : {verdict.scaffold_only}"
        + (f"  ({verdict.scaffold_reason})" if verdict.scaffold_only else "")
        + "   [SEPARATE axis — never affects 'ok']"
    )
    if verdict.anti_drift_hits:
        print(f"  ANTI-DRIFT    : literal excerpt pasted from {', '.join(verdict.anti_drift_hits)}")
    if verdict.anatomy_gaps:
        print(f"  D36 anatomy   : {len(verdict.anatomy_gaps)} gap(s)   [SEPARATE axis — never affects 'ok']")
        for gap in verdict.anatomy_gaps:
            print(f"    - {gap}")
    if verdict.reasons:
        print(f"\n{len(verdict.reasons)} PROBLEM(S):")
        for reason in verdict.reasons:
            print(f"  - {reason}")
    else:
        print("\nNo structural problem.")
    print(
        "\nReminder: this audit checks the ANATOMY (mechanics), not the quality of the content — a "
        "DISTINCT auditor (D39-6) is still required before activation (SkillGenerator.audit)."
    )
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
