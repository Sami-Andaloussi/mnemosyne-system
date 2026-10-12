"""The `skill-emit` seam (anti-drift) - the skill-creator's anatomy contract comes from the CODE,
never from a copy.

Same lesson as the distiller/finisher (contract-single-source-emit): the emission carries the REAL
``SKILL_ANATOMY_TEMPLATE`` (mnemosyne.production.skills), not prose copied into SKILL.md.
Pure/offline (no brick, no model). Brick-free."""

from __future__ import annotations

import importlib.util

from _invariants import REPO_ROOT
from mnemosyne.production import SKILL_ANATOMY_TEMPLATE

_SCRIPT = REPO_ROOT / "system" / "skills" / "skill-creator" / "skill_emit.py"
_spec = importlib.util.spec_from_file_location("skill_emit", _SCRIPT)
assert _spec is not None and _spec.loader is not None
skill_emit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skill_emit)


def test_emission_carries_the_real_anatomy_template_byte_for_byte() -> None:
    out = skill_emit.build_emission()
    # the WHOLE constant, not a paraphrase or an excerpt - skill-emit has nothing else to print.
    assert SKILL_ANATOMY_TEMPLATE.rstrip("\n") in out


def test_emission_carries_distinctive_fragments_of_each_of_the_six_lessons() -> None:
    out = skill_emit.build_emission()
    # a spot-check of exact phrases from the code constant - proves the emission replays the code
    # rather than a hand-typed summary that could silently diverge from a future edit.
    assert "CONTRACT-SINGLE-SOURCE-EMIT (anti-drift)" in out
    # the multi-version-per-executor doctrine (D150) is emitted as part of lesson 1, so every
    # skill-builder inherits the three-executor framing (local / local-API / frontier=just-a-prompt).
    assert "MULTI-VERSION-PER-EXECUTOR" in out
    assert "VERBATIM / P3 SACRED" in out
    assert "FAIL-CLOSED GUARDS IN CODE" in out
    assert "PRODUCER != VERIFIER" in out
    assert "TEST VIA THE REAL PROD PATH" in out
    assert "A FRONTIER AGENT WILL SCRIPT A TEMPLATE" in out
    assert "keep_verbatim" in out and "chapter_numbers_ok" in out  # the two named exemplars


def test_emission_takes_no_per_file_argument() -> None:
    # unlike distill-emit/finish-emit (one book/fiche at a time), the anatomy contract is static -
    # main() must not choke on being called with no arguments.
    assert skill_emit.main([]) == 0


def test_emission_carries_the_d36_skill_md_anatomy_header_and_body_floor() -> None:
    # D36's SKILL.md-level anatomy (frontmatter header + six mandatory body sections) is now part
    # of the emitted contract too - a distinct, complementary layer alongside the six code-layers.
    out = skill_emit.build_emission()
    assert "task_class" in out and "sensitivity_max" in out
    assert "Role (who the agent becomes)" in out
    assert "Logs (JSONL events)" in out
