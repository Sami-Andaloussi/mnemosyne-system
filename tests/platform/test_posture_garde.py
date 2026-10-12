"""The posture instrument must reflect the Guard the system REALLY starts (arc E, E1).

Why this file exists at all - `scripts/` has no other test. The instrument's first version built a
bare ``DeterministicGuard()`` and published `REFUS - tool call without a wired catalog` where the
real system answers `PASSE`. Nothing was wrong with the Guard: the HARNESS was wrong, and a wrong
harness publishes a posture nobody runs. That failure mode is mechanical, so it gets a barrier
rather than a note: if `build_guard()` ever drifts back toward a bare Guard, the wired tool flips
from PASSE to REFUS and this test reddens.

It drives the SHELL LINE the measure document tells a reader to run - not the Python function under
it. A test named after a command that spawns no command leaves the whole boundary (PYTHONPATH, the
module path, the exit code) unproven; that exact misnomer was found and fixed elsewhere in this
suite the same day.
"""

from __future__ import annotations

import os
import subprocess

from _invariants import REPO_ROOT


def _run_posture() -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": "system/lib"}
    return subprocess.run(
        ["uv", "run", "python", "scripts/posture_garde.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        check=False,
    )


def test_the_posture_COMMAND_reports_the_wired_tool_as_passing() -> None:
    """THE line a reader is told to run, driven exactly as documented.

    ``search_memory`` is the one sanctioned tool (``system/config/tools.toml``, versioned): it PASSES
    only when the protected catalog is wired, exactly as ``bootstrap.py`` wires it. A bare Guard
    answers REFUS here - which is the harness drift this test exists to catch."""
    done = _run_posture()
    assert done.returncode == 0, done.stderr[-2000:]
    tool_lines = [line for line in done.stdout.splitlines() if "search_memory" in line]
    assert len(tool_lines) == 1, f"expected exactly one wired-tool line, got: {tool_lines!r}"
    assert tool_lines[0].startswith("PASSE"), (
        "the wired tool must PASS - a REFUS here means the instrument built a Guard the system "
        f"never starts (no catalog). Line was: {tool_lines[0]!r}"
    )


def test_the_posture_pairs_on_the_SENSITIVITY_axis_not_only_on_the_host() -> None:
    """The defect this closes, and it published a false headline before an audit caught it.

    Version 1 paired every egress case on the HOST axis only, leaving each label ``public`` - so it
    printed "the sensitivity default never refuses", when on ``EXTERNAL_OUTPUT`` a ``perso`` or
    ``sensible`` flow ESCALATES even toward an allow-listed host. The instrument must therefore
    carry BOTH polarities on the SAME host: drop the non-public pair and this reddens.

    WARNING: **This ran on ONE machine and nowhere else, and nothing said so.** The instrument names
    ``www.sec.gov`` as "an allow-listed host", but the VERSIONED ``policy.toml`` allow-lists no host
    at all - the entry lives only in the local, PARKED delta (``git ls-files -v`` -> ``S``). So the
    line read ``PASSE`` here and ``REFUS`` on every clone, and the test failed there. Measured in a
    fresh worktree of ``HEAD``, not remembered. The property is judged the same way regardless now:
    the requests come from the instrument, the allow-listing is supplied by the test, so the guard's
    escalation rule is asserted on every machine and the SHELL line is checked for consistency with
    whatever the local policy really lists - never assumed to list anything.
    """
    import importlib.util
    from dataclasses import replace

    from mnemosyne.config import load_policy
    from mnemosyne.ports import Effect

    # Loaded from the SAME file the command above runs - ``scripts/`` is not a package, and reading
    # the cases from anywhere else would be a second copy of the material the instrument publishes.
    spec = importlib.util.spec_from_file_location(
        "_posture_under_test", REPO_ROOT / "scripts" / "posture_garde.py"
    )
    assert spec is not None and spec.loader is not None
    instrument = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instrument)
    build_guard, cases = instrument.build_guard, instrument.cases

    egress = [(what, req) for what, req in cases() if req.effect is Effect.EXTERNAL_OUTPUT]
    hosts = {req.target for _what, req in egress}
    assert len(hosts) >= 2, f"the instrument must oppose two hosts, not just one: {hosts!r}"
    listed = min(h for h in hosts if h is not None and "sec.gov" in h)
    # The guard the system really starts, with ONE thing substituted: the allow-list. Everything
    # else - classifier, catalog, secrets - is the real one, so this judges the real rule.
    guard = build_guard()
    guard._policy = replace(guard._policy, egress_allowlist=frozenset({listed}))  # noqa: SLF001
    verdicts = {
        what: guard.authorize(req).decision.name
        for what, req in egress
        if req.target == listed and "canal-B" not in what
    }
    public = [w for w in verdicts if "public" in w]
    non_public = [w for w in verdicts if "PERSO" in w or "SENSIBLE" in w]
    assert public and non_public, f"both polarities must exist on {listed}: {verdicts!r}"
    assert all(verdicts[w] == "ALLOW" for w in public), verdicts
    assert all(verdicts[w] == "ESCALATE" for w in non_public), (
        "a NON PUBLIC flow toward the SAME allow-listed host must escalate - it is the only wall "
        f"that is a sensitivity rule, and without it the instrument cannot see it: {verdicts!r}"
    )
    # ... and the printed posture must agree with the active policy allow-list.
    lines = [line for line in _run_posture().stdout.splitlines() if "allow-listed host" in line]
    if listed in load_policy().egress_allowlist:
        assert any(line.startswith("PASSE") for line in lines), lines
        assert any(line.startswith("HUMAIN") for line in lines), lines
    else:  # a clone: the host is not listed here, so the same lines must all REFUSE - never PASSE
        assert lines and all(line.startswith("REFUS") for line in lines), (
            f"{listed} is not in this policy's allowlist: none of these lines can "
            f"pass. {lines!r}"
        )


def test_the_posture_shows_REFUSALS_too_so_it_can_never_read_as_all_green() -> None:
    """A posture that only ever prints PASSE would be indistinguishable from a broken instrument.

    The pairs are the point (a declared domain against an undeclared one), so both polarities must
    appear. This also pins the two escalations: the four categories user keeps closed (money,
    messaging in his name, publishing, permanent deletion) reach the Guard as ``life_action``, and
    a rule that stopped escalating them would silently open all four."""
    out = _run_posture().stdout
    assert "REFUS" in out, (
        "an instrument that never refuses proves nothing about a deny-by-default guard"
    )
    life = [line for line in out.splitlines() if "life_action" in line]
    assert len(life) == 1 and life[0].startswith("HUMAIN"), (
        f"life-action must escalate to a human, never pass or be absent - got: {life!r}"
    )
