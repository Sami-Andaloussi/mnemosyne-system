"""The `finish-emit` seam (anti-drift) - the finisseur's polish contract comes from the CODE, never a copy.

Same lesson as the distillateur (contract-single-source-emit): the emission carries the REAL FINISH_PROMPT (not
prose recopied into SKILL.md), and the finisseur's fail-closed LOCK (chapter_numbers_ok) cuts off an ambiguous
fiche BEFORE any frontier polish. Pure/offline (no brick, no model). Brick-free."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from _invariants import REPO_ROOT
from mnemosyne.production import FINISH_PROMPT

_SCRIPT = REPO_ROOT / "system" / "skills" / "finisseur" / "finish_emit.py"
_spec = importlib.util.spec_from_file_location("finish_emit", _SCRIPT)
assert _spec is not None and _spec.loader is not None
finish_emit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(finish_emit)

# A well-formed fiche: 2 sequential chapters, count matches frontmatter `chapters: 2`, chapter 1 has a BAD title.
_GOOD = (
    '---\ntitle: "T"\nchapters: 2\n---\n\n# T\n\n## Sommaire\n- [[#1. (section)]] - a\n- [[#2. Risk]] - b\n\n'
    "## 1. (section)\n\nDesc one.\n\n**Concepts** :\n- risk management\n- sizing\n\n"
    "### Contenu (verbatim)\n\nA precious verbatim line.\n\n"
    "## 2. Risk Management\n\nDesc two.\n\n**Concepts** :\n- value\n\n"
    "### Contenu (verbatim)\n\nAnother verbatim line.\n"
)
# The finisseur audit's NO-GO trap: `chapters: 1` but a "## 2." lives inside a passage -> ambiguous -> STOP.
_TRAP = (
    '---\ntitle: "T"\nchapters: 1\n---\n\n# T\n\n## 1. Ch\n\nDesc.\n\n**Concepts** :\n- x\n\n'
    "### Contenu (verbatim)\n\nA line.\n\n## 2. A heading really inside a quote\n\nmore.\n"
)
_FLAG = '---\ntitle: "x"\nstatus: source-unusable\n---\n\n# x\n<!-- mnemosyne:source-unusable -->\n'
_OUT = Path("knowledge/distilled/quant/x.md")


def test_emission_carries_the_real_finish_prompt_not_a_handcopy() -> None:
    out = finish_emit.build_emission(_GOOD, _OUT)
    # a distinctive phrase from FINISH_PROMPT (the code home) - proves the emission replays the code, not a copy.
    assert "COPY it byte-for-byte, unchanged" in out
    assert FINISH_PROMPT.rstrip("\n") in out


def test_emission_lists_chapters_and_flags_only_the_bad_title() -> None:
    out = finish_emit.build_emission(_GOOD, _OUT)
    assert (
        "1. current title: '(section)'   [TITLE TO REDO]" in out
    )  # bad title flagged for rework
    assert "2. current title: 'Risk Management'" in out  # decent title present...
    assert "'Risk Management'   [TITLE TO REDO]" not in out  # ...and NOT flagged
    assert "risk management, sizing" in out  # its concepts help the agent write a good title
    assert str(_OUT) in out


def test_emission_refuses_an_ambiguous_fiche_fail_closed() -> None:
    out = finish_emit.build_emission(_TRAP, _OUT)
    assert "STOP" in out and "DO NOT TOUCH" in out
    assert "POLISH CONTRACT" not in out  # it never emits the polish contract for an unsafe fiche


def test_emission_refuses_a_source_unusable_flag() -> None:
    out = finish_emit.build_emission(_FLAG, _OUT)
    assert "STOP" in out and "POLISH CONTRACT" not in out
