"""(6) (consumption) - render the self-model so a fresh agent discovers & uses Mnemosyne (D25 / D114-TO2).

Biting tests for the AGENT-SURFACES source (the orienting map of what Mnemosyne does) and the
``describe`` render + one-command entry - the in-repo, brick-free incarnation of "Mnemosyne as an MCP":
a blank agent runs one command and learns "what are you, what can you do?". These prove:

* the map advertises the D119 a-f agent-facing surfaces, and is HONEST about privilege (a human-gated /
  privileged surface says so - the map never implies an agent may cross a frontier it cannot, D102);
* rendering is faithful and honest - every card shows its governed posture; an empty group says so,
  it never invents a capability (deny-by-default, D73);
* the entry is a PURE READ over the brick-free runtime (D126): it prints the model and returns 0,
  crossing no frontier;
* through ``CoreApi``, describe_self now carries THREE kinds - surfaces, tools, active skills.

Brick-free: the default bootstrap runtime, nothing installed (D126).
"""

from __future__ import annotations

from mnemosyne.api.core_api import CoreApi
from mnemosyne.production import AGENT_SURFACES, AgentSurfacesSource, SelfModel
from mnemosyne.production.self_model import CapabilityCard
from mnemosyne.runtime import bootstrap
from mnemosyne.runtime.describe import main, render_self_model


class _Src:
    """A minimal CapabilitySource emitting scripted cards - a render test vehicle."""

    def __init__(self, *cards: CapabilityCard) -> None:
        self._cards = cards

    def cards(self) -> tuple[CapabilityCard, ...]:
        return self._cards


def _card(kind: str, name: str, *, summary: str = "s", effect: str = "read_only") -> CapabilityCard:
    return CapabilityCard(kind=kind, name=name, summary=summary, effect=effect, reach="stays_local")


# --------------------------------------------------------------------------- #
# AgentSurfacesSource - the D119 a-f map, honest about privilege (D102).                        #
# --------------------------------------------------------------------------- #
def test_agent_surfaces_source_advertises_the_d119_surfaces() -> None:
    """The map names Mnemosyne's own agent-facing surfaces - the whole of what it does, at a glance.

    The comparison stays an EQUALITY, not a superset: it must catch a surface that quietly
    disappears just as much as one that quietly appears. Growing the map means growing this line -
    which is the point, since the map is what a fresh agent reads to know what exists. (``modeles``
    joined at C9: the six D119 surfaces plus the answer to "which local models do I have".)"""
    cards = AgentSurfacesSource().cards()

    assert {c.name for c in cards} == {
        "capture",
        "search",
        "supervision",
        "production",
        "governance",
        "proposals",
        "modeles",
        "choix_du_modele",
        "plan",
        "execution",
        "signalement",
    }
    assert all(c.kind == "surface" for c in cards)


def test_agent_surfaces_are_honest_about_privilege() -> None:
    """A privileged / human-gated surface SAYS so in its effect - the map never implies an agent may
    wire a tool or promote on its own (D102 / D79)."""
    by_name = {c.name: c for c in AGENT_SURFACES}

    assert "privileged" in by_name["governance"].effect  # wiring a tool = POLICY_WRITE, human
    assert "human_gated" in by_name["production"].effect  # promotion is a human gate


def test_agent_surfaces_source_is_a_curated_map_not_a_live_handle() -> None:
    """The surfaces are a static curated map (default = AGENT_SURFACES); reading wires/runs nothing."""
    assert AgentSurfacesSource().cards() == AGENT_SURFACES


# --------------------------------------------------------------------------- #
# render_self_model - faithful, honest markdown (D73).                                          #
# --------------------------------------------------------------------------- #
def test_render_shows_identity_and_every_section() -> None:
    """The render leads with identity, then a section per kind - the shape a fresh agent reads."""
    out = render_self_model(SelfModel.assemble("I am X", AgentSurfacesSource()))

    assert out.startswith("# Mnémosyne")
    assert "I am X" in out
    assert "## Surfaces" in out and "## Tools" in out and "## Skills" in out
    assert "**capture**" in out


def test_render_says_an_empty_group_so_honestly() -> None:
    """A kind with no card shows its honest empty message - under-states, never invents one (D73)."""
    out = render_self_model(SelfModel.assemble("I am X"))  # no sources -> every group empty

    assert "no tool sanctioned yet" in out
    assert "no skill active yet" in out


def test_render_shows_a_cards_governed_posture() -> None:
    """Each advertised card carries its name, summary and governed posture (effect  -  reach)."""
    out = render_self_model(
        SelfModel.assemble("id", _Src(_card("tool", "search_memory", summary="query -> passages")))
    )

    assert "**search_memory** — query -> passages" in out
    assert "[read_only · stays_local]" in out


def test_render_never_silently_drops_an_unknown_kind() -> None:
    """A future source's card (a kind the render does not yet know) STILL appears - never silently
    dropped, so the self-model can never quietly under-state a real capability (fail loud, D73)."""
    out = render_self_model(
        SelfModel.assemble("id", _Src(_card("governance", "posture", summary="deny-by-default monitor")))
    )

    assert "**posture**" in out
    assert "deny-by-default monitor" in out


# --------------------------------------------------------------------------- #
# The entry + the production path - one command, three kinds (D114-TO2 / D119).                 #
# --------------------------------------------------------------------------- #
def test_main_prints_the_self_model_and_returns_zero(capsys) -> None:
    """The one-command entry is a pure read over the brick-free runtime: it prints the model, returns 0."""
    rc = main()
    out = capsys.readouterr().out

    assert rc == 0
    assert out.startswith("# Mnémosyne")
    assert "## Surfaces" in out
    assert "search_memory" in out  # the sanctioned tool really shows up for a fresh agent


def test_prod_describe_self_carries_surfaces_tools_and_skills() -> None:
    """Through CoreApi, the self-model now assembles THREE kinds - the map plus the invokables."""
    model = CoreApi(bootstrap()).describe_self()

    assert {c.kind for c in model.capabilities} >= {"surface", "tool"}  # skills empty at cold start
    assert len([c for c in model.capabilities if c.kind == "surface"]) == len(AGENT_SURFACES)
    assert model.capabilities[0].kind == "surface"  # the MAP is read first (orientation before detail)
