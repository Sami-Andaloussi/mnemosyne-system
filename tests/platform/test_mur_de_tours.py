"""A5  -  THE BITE OF `agent_max_turns` STOPS BEING ANONYMOUS.

WHY THIS FILE EXISTS. `make murs` said *"no refusal recorded"*, and I nearly read it as
"the bounds have never bitten". Measured: biting was **attributed NOWHERE** - the loop relayed
the library's error as-is, and a `UsageLimitExceeded` reads like an ordinary tool failure, never
like *"YOUR bound, at 16, just cut in"*. *Zero refusals can mean the rule is being bypassed.*

AND THIS IS WHAT MAKES A5 DECIDABLE ONE DAY: you cannot measure the value of a bound whose
bite is never attributed. This is not A5 finished - it is A5 that stops waiting for a measurement
nothing takes.
"""

from __future__ import annotations

import pytest

from mnemosyne.agents.loop import traduire_le_mur_de_tours
from mnemosyne.ports import ResourceBoundError


class UsageLimitExceeded(Exception):
    """The name the brick's class carries - the NAME is the contract here (D103)."""


def test_une_limite_de_tours_devient_une_borne_NOMMEE() -> None:
    with pytest.raises(ResourceBoundError) as capture:
        traduire_le_mur_de_tours(UsageLimitExceeded("request limit"), 16)
    dit = str(capture.value)
    assert "agent_max_turns" in dit, f"the bound must be NAMED. Seen: {dit}"
    assert "16" in dit, "the value that bit must be stated"
    assert "policy-demander" in dit, (
        "the refusal must name the GESTURE that lifts it - a refusal that does not state the way "
        "out gets bypassed, and that way out goes through the governed channel, never the protected zone"
    )


def test_la_cause_ORIGINELLE_est_conservee() -> None:
    """A lost `raise ... from exc`, and you end up debugging a bound while thinking you debug a model."""
    origine = UsageLimitExceeded("request limit exceeded")
    with pytest.raises(ResourceBoundError) as capture:
        traduire_le_mur_de_tours(origine, 16)
    assert capture.value.__cause__ is origine


def test_l_INNOCENT_une_panne_ORDINAIRE_passe_INTACTE() -> None:
    """Relabeling any ordinary failure as "bound reached" would send someone to raise a
    ceiling for a defect that has nothing to do with it. Without this witness, a translation that
    ALWAYS raised would pass the one above."""
    for quelconque in (ValueError("something else"), RuntimeError("network"), KeyError("k")):
        traduire_le_mur_de_tours(quelconque, 16)  # does not raise


def test_le_chemin_REEL_traduit_bien_la_morsure() -> None:
    """REACHABILITY - *the barrier that nothing calls*. `run_agent` is `# pragma: no cover`
    (it requires the brick): without this source reading, the translation might never be
    wired in and the three witnesses above would stay green."""
    import inspect

    from mnemosyne.agents import loop

    source = inspect.getsource(loop.run_agent)
    assert "traduire_le_mur_de_tours(exc, ceiling)" in source
    assert source.index("drive_agent(") < source.index("traduire_le_mur_de_tours("), (
        "the translation must wrap the call, not precede it"
    )
