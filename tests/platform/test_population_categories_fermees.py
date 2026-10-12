"""Freeze WHICH code can reach the Guard's closed categories - the alarm on arc E's conclusion.

Arc E set out to invert the Guard's default, on the belief that it over-closes. Three measurements
on 2026-07-28 said otherwise: the Guard's closures are either lists already attached to a place (and
three of five already have a door operator's word opens), or walls **no live path reaches**. The four
categories operator named closed - money, messaging in his name, publishing, permanent deletion - are
closed because **no capacity exists**, not because a rule refuses.

That conclusion is only true of a POPULATION, and a population changes. Written in a document it
rots silently; the day someone wires a capacity that acts on the world, the arc-E page keeps saying
"nothing reaches it" and nobody re-reads it. So the population is frozen HERE, where a change is
loud, and the failure message says what to do: **wire operator's door in the SAME commit as the
capacity.** A door deferred to "later" is a door that never exists ([[a-slower-door-is-never-used]]).

Two instrument choices, both deliberate:

* **AST, not grep.** ``Effect.LIFE_ACTION`` appears in a dozen docstrings and comments explaining the
  rule; only a call ARGUMENT actually reaches the Guard. The parser ignores prose by construction,
  which a regex cannot.
* **A named list, never a count.** A frozen count is satisfied by any swap - one site deleted, one
  added, total unchanged, alarm silent. The reference must not be derivable from what it checks.

Scope: the versioned skeleton (see ``_SEARCHED``). ``projects/`` is machine-local and git-ignored, so
it cannot be frozen in a portable test - it is named as excluded below rather than silently dropped,
because an excluded population is UNJUDGED, not safe.

Two things this freeze was BLIND to on its first day, both found by an isolated audit and both fixed
below: ``system/skills`` was outside the search entirely (14 git-tracked modules), and the census
only saw code that WRITES ``Effect.<NAME>`` - so a new module merely CALLING ``api.export(...)``
would have been a live capacity that added no site at all.
"""

from __future__ import annotations

import ast
import tomllib

from _invariants import REPO_ROOT

#: Where a capacity could be wired in the versioned skeleton. ``projects/`` is deliberately out of
#: scope (git-ignored, machine-local): on 2026-07-28 exactly one file there reached the Guard's
#: egress - ``projects/saas/Acme Research/scripts/acquisition_gouvernee.py`` - carrying PUBLIC
#: financial pages. It is UNJUDGED by this freeze, not vouched for.
#:
#: ``system/skills`` was MISSING from the first version, and an isolated audit measured the hole:
#: 14 git-tracked modules, never visited, several of which import ``CoreApi`` and ``bootstrap``. The
#: marker had been chosen on "the folders where I know sites already are" instead of "where a
#: capacity can be wired" - the wrong-marker form of an excluded population being unjudged, not safe.
_SEARCHED = ("system/lib", "system/skills", "scripts")

#: The API methods through which data can LEAVE the machine. Frozen by name because the census above
#: only sees code that WRITES ``Effect.<NAME>``: a brand-new ``mailer_run.py`` calling
#: ``api.export(...)`` would be a live capacity in one of operator's four closed categories and would add
#: no ``Effect.`` site at all. Measured by an isolated audit, and it was right.
_EGRESS_ENTRY_POINTS = frozenset({"export", "render", "caption", "capture_youtube"})

#: Every call to one of those, ``<path>::<enclosing def>``. ``export`` appears NOWHERE - that is the
#: arc-E finding, and freezing it here is what makes the FIRST caller loud.
EGRESS_CALLERS = frozenset(
    {
        "scripts/bench_distillation.py::bench_one",
        "system/lib/mnemosyne/api/core_api.py::render",
        "system/lib/mnemosyne/ingest/source_docling.py::_vlm_caption",
        "system/lib/mnemosyne/runtime/caption_pilot.py::caption",
        "system/lib/mnemosyne/runtime/render.py::render",
        "system/lib/mnemosyne/runtime/smoke.py::run_smoke_test",
        "system/lib/mnemosyne/runtime/youtube_ingest.py::main",
    }
)

#: Every production site whose call passes ``Effect.EXTERNAL_OUTPUT`` - the effect that carries data
#: OFF the machine. Frozen as ``<path>::<enclosing def>``.
EGRESS_SITES = frozenset(
    {
        "scripts/posture_garde.py::cases",
        "system/lib/mnemosyne/api/core_api.py::capture_youtube",
        "system/lib/mnemosyne/api/core_api.py::export",
        "system/lib/mnemosyne/ingest/caption_anthropic.py::caption",
        "system/lib/mnemosyne/runtime/render.py::render",
    }
)

#: Every site whose call passes ``Effect.LIFE_ACTION`` - operator's four closed categories. Exactly ONE,
#: and it is the PROBE that measures the wall, never a capacity: ``posture_garde`` asks and prints
#: the verdict, it redeems no grant and acts on nothing. The rule exists (`monitor.py` always
#: escalates), it is tested, it is cited - and **no code that DOES anything has ever asked for it**.
#: Named rather than hidden by narrowing the search: an excluded population is unjudged, not safe.
LIFE_ACTION_SITES = frozenset({"scripts/posture_garde.py::cases"})

#: The sanctioned tool catalogue, frozen by NAME with the two fields the Guard rules on. A tool
#: absent from ``tools.toml`` is refused fail-closed, so this file is the chokepoint for any capacity
#: reached as a TOOL - **not for every capacity to act**, and the difference was measured: egress
#: keys on ``policy.toml`` instead, where 10 hosts are already allow-listed and 9 have no consumer in
#: this skeleton at all (their callers live in ``projects/``). Two doors, two files; saying "the
#: single chokepoint" would make one of them invisible.
TOOL_MANIFESTS = {"search_memory": ("read_only", "stays_local")}


class _EffectArguments(ast.NodeVisitor):
    """Collect ``Effect.<NAME>`` occurrences that are ARGUMENTS of a call, with their enclosing def.

    Anything else - an import, a docstring, an ``if effect is Effect.LIFE_ACTION`` inside the Guard's
    own rule table - is not a site that ASKS for the effect, and counting it would inflate the
    population with the very code that refuses it.
    """

    def __init__(self, relpath: str) -> None:
        self.relpath = relpath
        self.found: set[tuple[str, str]] = set()
        self.callers: set[str] = set()
        self._scope: list[str] = []

    def _visit_scope(self, node: ast.AST, name: str) -> None:
        self._scope.append(name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 - ast API
        self._visit_scope(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802 - ast API
        self._visit_scope(node, node.name)

    def visit_Call(self, node: ast.Call) -> None:
        arguments = list(node.args) + [kw.value for kw in node.keywords]
        scope = self._scope[-1] if self._scope else "<module>"
        for argument in arguments:
            if (
                isinstance(argument, ast.Attribute)
                and isinstance(argument.value, ast.Name)
                and argument.value.id == "Effect"
            ):
                self.found.add((argument.attr, f"{self.relpath}::{scope}"))
        if isinstance(node.func, ast.Attribute) and node.func.attr in _EGRESS_ENTRY_POINTS:
            # ``x.export(...)`` whatever ``x`` is: over-matching is the SAFE direction here. A false
            # name in the frozen list costs one line of churn; a missed one costs the whole alarm.
            self.callers.add(f"{self.relpath}::{scope}")
        self.generic_visit(node)


def _census() -> tuple[dict[str, frozenset[str]], frozenset[str]]:
    """``({effect name: sites}, egress callers)`` over the searched skeleton.

    A missing search root RAISES. That branch is where this freeze would go quietly dead: rename a
    directory, ``rglob`` yields nothing, the census shrinks and the comparison simply reports
    "disparus" - which reads like a deletion someone made on purpose rather than a blind instrument.
    """
    sites: dict[str, set[str]] = {}
    callers: set[str] = set()
    for root in _SEARCHED:
        base = REPO_ROOT / root
        if not base.is_dir():
            raise AssertionError(
                f"_SEARCHED names {root!r}, which does not exist - this freeze no longer watches "
                "what lives there. Fix the path before reading the verdict of the tests below."
            )
        for path in sorted(base.rglob("*.py")):
            relpath = str(path.relative_to(REPO_ROOT))
            visitor = _EffectArguments(relpath)
            visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
            for effect, site in visitor.found:
                sites.setdefault(effect, set()).add(site)
            callers |= visitor.callers
    return {effect: frozenset(found) for effect, found in sites.items()}, frozenset(callers)


def test_the_only_life_action_site_is_the_probe_that_measures_the_wall() -> None:
    """The four closed categories are closed by ABSENCE OF CAPACITY - freeze that, loudly."""
    found = _census()[0].get("LIFE_ACTION", frozenset())
    assert found == LIFE_ACTION_SITES, (
        "the population of CLOSED categories has changed - arc E concluded that only the PROBE "
        f"reaches them.\n  new: {sorted(found - LIFE_ACTION_SITES)}\n  gone: "
        f"{sorted(LIFE_ACTION_SITES - found)}\n"
        "Wire the operator's-word DOOR in THIS SAME commit, not later: a capacity that acts on "
        "the world with no way for the operator to have a say is a wall it cannot climb over. Then "
        "re-measure (scripts/posture_garde.py) and update this freeze's frozen population to match."
    )


def test_the_egress_population_is_the_one_arc_e_measured() -> None:
    """Data leaving the machine is the other half of the four categories (publish / send)."""
    found = _census()[0].get("EXTERNAL_OUTPUT", frozenset())
    assert found == EGRESS_SITES, (
        "the population of EGRESS sites has changed (what can make data LEAVE the "
        f"machine).\n  new: {sorted(found - EGRESS_SITES)}\n  gone: "
        f"{sorted(EGRESS_SITES - found)}\nA new site must state how operator's explicit word "
        "reaches it (today only one knows how: caption_anthropic, via a human_gesture set "
        "ONCE per run). Update this NAMED list at the same time as the code."
    )


def test_the_tool_catalogue_is_the_chokepoint_and_it_is_read_only() -> None:
    """A capacity to ACT can only arrive through ``tools.toml`` - freeze what is sanctioned."""
    manifests = tomllib.loads(
        (REPO_ROOT / "system" / "config" / "tools.toml").read_text(encoding="utf-8")
    ).get("tools", [])
    posture = {entry["name"]: (entry["effect"], entry["egress"]) for entry in manifests}
    assert posture == TOOL_MANIFESTS, (
        f"the sanctioned tool catalogue has changed: {posture}. This is the MANDATORY passage "
        "point for any capacity to ACT (a tool absent is refused fail-closed). If an entry is "
        "life_action or leaves_external, the operator's-word door is wired in THIS SAME commit - "
        "and the back-end code exists BEFORE its manifest, never the reverse (the order search_memory follows)."
    )


def test_the_callers_of_every_egress_door_are_frozen_too() -> None:
    """The census above sees who ASKS the Guard; this sees who USES the door - two different sets.

    A new ``mailer_run.py`` whose body is ``api.export(Envelope(corps), to_host=...)`` is a live
    capacity in one of the four closed categories (sending a message in his name) and writes no
    ``Effect.`` anywhere. Frozen by name, its first appearance is loud.
    """
    _, callers = _census()
    assert callers == EGRESS_CALLERS, (
        "the CALLERS of egress doors have changed (export / render / caption / "
        f"capture_youtube).\n  new: {sorted(callers - EGRESS_CALLERS)}\n  gone: "
        f"{sorted(EGRESS_CALLERS - callers)}\nA new caller is a CAPACITY: say how operator's "
        "explicit word reaches it, in THIS SAME commit, then update this named list."
    )
