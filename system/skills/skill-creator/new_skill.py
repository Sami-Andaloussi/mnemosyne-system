#!/usr/bin/env python3
"""Seam `skill-new` - scaffold a REAL skill DRAFT (D37: generate -> audit -> activate).

Lays down the 3 layers a DRAFT can already have without a precise need being understood yet (D39,
just-in-time): (1) a home STUB in the code, loud if invoked (`NotImplementedError`
- D100, never a silent failure); (2) a thin adapter that calls it; (3) a Make target.
Also adds (4) a lock-test that pins that the stub exists and stays loud. Does NOT lay down an
`-emit` seam: a DRAFT has no model contract to emit yet (some skills, like `juge`,
will never have one - see `audit_skill.py`), and a mechanical skill does not need one either.

Fail-closed: refuses to overwrite an existing skill/file rather than guessing whether it should be
replaced (the same conduct as `chapter_numbers_ok`). Writes NOTHING if even one of the 4
target locations already exists - all or nothing, never a half-laid scaffold.

Usage: make skill-new NEED="what the skill must accomplish" [NAME=kebab-name]
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from mnemosyne.production.skills import SCAFFOLD_MARKERS  # noqa: E402

_SKILLS_ROOT = Path("system/skills")
_PROD_ROOT = Path("system/lib/mnemosyne/production")
_TESTS_ROOT = Path("tests")
_MAKEFILE = Path("Makefile")

#: The SAME literal strings `mnemosyne.production.skills.SCAFFOLD_MARKERS` looks for - IMPORTED, never
#: retyped (lesson 1, applied to the scaffolder itself). This used to retype them, under a comment
#: claiming it imported them: a rename in `skills.py` would then have made `_scaffold_verdict` report
#: `scaffold_only=False` - "this is not a scaffold" - on a WHOLLY EMPTY skeleton, silently (the
#: body-length fallback does not catch it: a bare stub's SKILL.md is ~1126 chars, 3.75x the 300 floor).
#: `tests/identity/test_new_skill.py` pins the no-retyping property at SOURCE level.
#: HONEST RESIDUE - what this does NOT protect: the ORDER. Re-ordering the home tuple silently binds a
#: different marker to each name here, and no test catches it (an assert on `SCAFFOLD_MARKERS[0]` would
#: be tautological - the unpack defines it). Harmless today: `_scaffold_verdict` greps for ANY marker, so
#: detection survives a swap; only the stub's wording would be off. Positional unpack, so a change to the
#: tuple's LENGTH does break loudly.
_MARKER_DESCRIBE, _MARKER_CONTRACT, _MARKER_GUARD = SCAFFOLD_MARKERS


def slugify(text: str, *, max_len: int = 40) -> str:
    """Deterministic kebab-case slug from free text (no model - a scaffold name does not need
    one). Matches the frontmatter lint's ``_NAME_RE`` in ``skills.py`` by construction: lowercase
    letters/digits only, single hyphens, no leading/trailing/doubled hyphen."""
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_len].rstrip("-") or "nouveau-skill"


def _code_home_stub(name: str, need: str) -> str:
    return (
        f'"""{name} (DRAFT, scaffolded by `make skill-new` - D39 / D37) - {_MARKER_DESCRIBE} the\n'
        "real doctrine this skill encodes once the need below is understood.\n\n"
        f"Need, as given to `make skill-new`: {need.strip() or '(none given)'}\n\n"
        "Replace this docstring and the stub function with the real code home: the actual logic,\n"
        "and any model-facing prompt/schema constant (a *_PROMPT / *_TEMPLATE - see\n"
        "system/skills/skill-creator/references/architecture.md). Code & docstrings English (D117).\n"
        '"""\n\n'
        "from __future__ import annotations\n\n\n"
        "def run() -> None:\n"
        '    """DRAFT stub - not yet implemented. Loud on purpose (D100): a stub must never\n'
        '    silently no-op, so nothing downstream can mistake it for a working skill."""\n'
        "    raise NotImplementedError(\n"
        f'        "{_MARKER_GUARD} - implement the {name} code home, see '
        f'system/skills/{name}/SKILL.md"\n'
        "    )\n"
    )


def _thin_adapter_stub(name: str) -> str:
    return (
        "#!/usr/bin/env python3\n"
        f'"""Thin adapter for the {name} skill (DRAFT, scaffolded by `make skill-new`) -\n'
        "orchestration ONLY: it must glob/read what the skill needs and call the code home in\n"
        f"{_PROD_ROOT}/{name}.py - never reimplement logic that belongs there (see\n"
        "system/skills/skill-creator/references/architecture.md).\n\n"
        f"Usage: make {name}\n"
        '"""\n\n'
        "from __future__ import annotations\n\n\n"
        "def main() -> int:\n"
        f"    from mnemosyne.production.{name.replace('-', '_')} import run\n\n"
        "    run()\n"
        "    return 0\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )


def _skill_md_stub(name: str, need: str) -> str:
    need_line = need.strip().replace("\n", " ") or "(need not yet described)"
    description = (need_line[:200] + "...") if len(need_line) > 200 else need_line
    return (
        "---\n"
        f"name: {name}\n"
        f"description: >\n"
        f"  {_MARKER_DESCRIBE} what this skill does and WHEN to use it (the real trigger) -\n"
        f"  starting need: {description}\n"
        "---\n\n"
        f"# Skill: {name} (DRAFT - scaffolded via `make skill-new`)\n\n"
        f"> {_MARKER_DESCRIBE} in one sentence what this skill accomplishes once real.\n\n"
        "## When to use it\n"
        f"{_MARKER_DESCRIBE} the concrete situations that trigger this skill.\n\n"
        "## How to invoke it\n"
        "```bash\n"
        f"make {name}\n"
        "```\n\n"
        "## What it GUARANTEES - by construction, not by trust (D100)\n"
        f"{_MARKER_GUARD} of this skill (ambiguity -> refuse/flag, never guess) - see "
        "`chapter_numbers_ok` as an example (`references/architecture.md`).\n\n"
        "## Under the hood (the body governs - D70)\n"
        f"- Home: `mnemosyne.production.{name.replace('-', '_')}.run` - {_MARKER_CONTRACT} exact "
        "once the home is filled in (and an `-emit` seam if this skill calls a model - "
        "see `references/anti-drift.md`).\n"
        f"- Adapter: `system/skills/{name}/{name}_run.py`. Lock-test: "
        f"`tests/test_{name.replace('-', '_')}.py`.\n\n"
        "## Status (activation cycle D37)\n"
        "DRAFT. Next steps: fill in the home + the adapter, `make skill-audit "
        f'DIR="system/skills/{name}"` must turn green, then a **separate** auditor (D39-6) '
        "and the **operator's gesture** (D37) before any activation.\n"
    )


def _test_stub(name: str) -> str:
    mod = name.replace("-", "_")
    return (
        f'"""Lock-test stub for the {name} skill (DRAFT, scaffolded by `make skill-new` - D109).\n\n'
        f"{_MARKER_DESCRIBE} replace this with REAL tests once {_PROD_ROOT}/{name}.py is filled\n"
        "in. Until then this only pins that the scaffold exists and stays LOUD if invoked (D100: a\n"
        "stub must never silently no-op) - implementing the real function without updating this\n"
        'test makes it FAIL, which is the point: a placeholder, not a spec."""\n\n'
        "from __future__ import annotations\n\n"
        "import pytest\n\n\n"
        f"def test_{mod}_stub_is_not_yet_implemented() -> None:\n"
        f"    from mnemosyne.production.{mod} import run\n\n"
        "    with pytest.raises(NotImplementedError):\n"
        "        run()\n"
    )


def _append_makefile_target(text: str, name: str, need: str) -> str:
    if re.search(rf"^{re.escape(name)}:", text, re.MULTILINE):
        raise SystemExit(
            f"refused: a '{name}:' target already exists in {_MAKEFILE} - choose NAME=..."
        )
    phony = re.search(r"^(\.PHONY:.*)$", text, re.MULTILINE)
    if phony and re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", phony.group(1)) is None:
        text = text[: phony.start(1)] + phony.group(1) + f" {name}" + text[phony.end(1) :]
    need_comment = (need.strip().replace("\n", " ") or "describe the need")[:80]
    block = (
        f"\n{name}: ## DRAFT (make skill-new) - {need_comment}. Usage: make {name}\n"
        f"\tPYTHONPATH=system/lib uv run python system/skills/{name}/{name}_run.py\n"
    )
    return text.rstrip("\n") + "\n" + block


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    need = args[0] if args else ""
    name_override = args[1].strip() if len(args) > 1 and args[1].strip() else ""
    if not need.strip() and not name_override:
        print('Usage: make skill-new NEED="what the skill must accomplish" [NAME=kebab-name]')
        return 1

    name = slugify(name_override or need)
    skill_dir = _SKILLS_ROOT / name
    home_path = _PROD_ROOT / f"{name.replace('-', '_')}.py"
    test_path = _TESTS_ROOT / f"test_{name.replace('-', '_')}.py"

    # Fail-closed, ALL-or-nothing: refuse rather than half-scaffold or silently overwrite (D100).
    existing = [p for p in (skill_dir, home_path, test_path) if p.exists()]
    if existing:
        print(f"REFUSED: already present, nothing is written -> {', '.join(str(p) for p in existing)}")
        print("        choose a different NAME, or complete/delete the existing scaffold.")
        return 1
    if not _MAKEFILE.exists():
        print(f"REFUSED: {_MAKEFILE} not found (run from the repo root)")
        return 1
    try:
        makefile_text = _append_makefile_target(_MAKEFILE.read_text(encoding="utf-8"), name, need)
    except SystemExit as exc:
        print(str(exc))
        return 1

    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(_skill_md_stub(name, need), encoding="utf-8")
    (skill_dir / f"{name}_run.py").write_text(_thin_adapter_stub(name), encoding="utf-8")
    home_path.write_text(_code_home_stub(name, need), encoding="utf-8")
    test_path.write_text(_test_stub(name), encoding="utf-8")
    _MAKEFILE.write_text(makefile_text, encoding="utf-8")

    print(f"DRAFT scaffolded: {name}\n")
    for p in (skill_dir / "SKILL.md", skill_dir / f"{name}_run.py", home_path, test_path):
        print(f"  + {p}")
    print(f"  ~ {_MAKEFILE} ('{name}:' target added)")
    print(
        f"\nNext steps: fill in the home ({home_path}) and the SKILL.md ("
        f"TODO(skill-creator) markers), then:\n"
        f'  make skill-audit DIR="{skill_dir}"\n'
        "  make test\n"
        "Formal activation only after a SEPARATE auditor (D39-6) + the operator's gesture (D37)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
