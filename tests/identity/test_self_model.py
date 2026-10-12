"""⑥ — the self-model: describe what I am, advertise only what the Guard authorizes (D114-TO2 / D25).

Biting tests for :mod:`mnemosyne.production.self_model` and its wiring on ``CoreApi.describe_self``.
The soul's *self-aware* nerve: a fresh LLM asks "what are you, what can you do?" and gets a truthful,
read-only answer — the first breath of the model-of-self before an MCP server is stood up. These
prove the structural properties:

* it is READ-ONLY and TRUTHFUL BY CONSTRUCTION — the model reports exactly the Guard's own
  authorized-tool allow-list (D114-⑤), never more, and wires / activates nothing (D100 / D102);
* a card is GOVERNANCE-SAFE metadata (name / io-schema / effect / reach) — no secret, no fiche
  content (invariant 22); a life-action tool is described honestly, describing ≠ invoking;
* the model is deny-by-default — no source (or an empty allow-list) yields an EMPTY model, an error
  never (D73 / D89);
* each capability KIND is a separate source of the SAME model, de-duplicated by ``(kind, name)``.

Brick-free: deterministic stubs / the real bootstrap catalog, nothing installed (D126).
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.api.core_api import CoreApi
from mnemosyne.guard.monitor import DeterministicGuard
from mnemosyne.ports import (
    Bubble,
    DataEgress,
    Decision,
    Effect,
    GuardRequest,
    ToolBackend,
    ToolEffect,
    ToolManifest,
)
from mnemosyne.production import (
    MNEMOSYNE_IDENTITY,
    AuthorizedToolsSource,
    CapabilityCard,
    SelfModel,
)
from mnemosyne.runtime import bootstrap
from mnemosyne.tools import ConfigToolCatalog


def _manifest(
    name: str,
    *,
    effect: ToolEffect = ToolEffect.READ_ONLY,
    egress: DataEgress = DataEgress.STAYS_LOCAL,
    io: str = "query:str -> passages:str",
) -> ToolManifest:
    return ToolManifest(
        name=name,
        backend=ToolBackend.LOCAL_FUNCTION,
        io_schema=io,
        permissions=("read",),
        egress=egress,
        effect=effect,
    )


def _tools_source(*manifests: ToolManifest) -> AuthorizedToolsSource:
    """An AuthorizedToolsSource over a fixed allow-list — the brick-free stand-in for the Guard's."""
    return AuthorizedToolsSource(lambda: manifests)


class _CardSource:
    """A CapabilitySource emitting scripted cards — lets the assemble tests exercise other KINDs."""

    def __init__(self, *cards: CapabilityCard) -> None:
        self._cards = cards

    def cards(self) -> tuple[CapabilityCard, ...]:
        return self._cards


def _card(kind: str, name: str, *, summary: str = "") -> CapabilityCard:
    return CapabilityCard(
        kind=kind, name=name, summary=summary, effect="read_only", reach="stays_local"
    )


# --------------------------------------------------------------------------- #
# AuthorizedToolsSource — a manifest becomes a governance-safe card (invariant 22).             #
# --------------------------------------------------------------------------- #
def test_a_tool_manifest_becomes_a_governance_safe_card() -> None:
    """One sanctioned tool -> one card projecting name / io-schema / effect / reach — and nothing else."""
    (card,) = _tools_source(_manifest("search_memory")).cards()

    assert card == CapabilityCard(
        kind="tool",
        name="search_memory",
        summary="query:str -> passages:str",
        effect="read_only",
        reach="stays_local",
    )


def test_an_empty_allow_list_yields_no_cards() -> None:
    """No sanctioned tool => nothing to advertise — deny-by-default, an empty source, never an error."""
    assert _tools_source().cards() == ()


def test_a_life_action_tool_is_reported_honestly() -> None:
    """A world-acting / externally-reaching tool is DESCRIBED truthfully — describing is not invoking."""
    (card,) = _tools_source(
        _manifest("send_email", effect=ToolEffect.LIFE_ACTION, egress=DataEgress.LEAVES_EXTERNAL)
    ).cards()

    assert card.effect == "life_action"  # posture stated plainly, not hidden
    assert card.reach == "leaves_external"


# --------------------------------------------------------------------------- #
# SelfModel.assemble - identity, order, structural dedup by (kind, name) (D100).                #
# --------------------------------------------------------------------------- #
def test_assemble_preserves_the_identity() -> None:
    """The drift-proof governance posture is carried verbatim - who I am, not a feature that comes/goes."""
    model = SelfModel.assemble(MNEMOSYNE_IDENTITY)

    assert model.identity == MNEMOSYNE_IDENTITY


def test_no_source_is_an_empty_model_not_an_error() -> None:
    """Assembling over zero sources yields identity + no capabilities - deny-by-default (D73)."""
    model = SelfModel.assemble(MNEMOSYNE_IDENTITY)

    assert model.capabilities == ()


def test_assemble_concatenates_sources_in_order() -> None:
    """Every source contributes, in source order - the model is the union of what each can say."""
    model = SelfModel.assemble(
        MNEMOSYNE_IDENTITY, _CardSource(_card("tool", "a")), _CardSource(_card("skill", "b"))
    )

    assert [(c.kind, c.name) for c in model.capabilities] == [("tool", "a"), ("skill", "b")]


def test_assemble_dedups_identical_capability_keeping_the_first() -> None:
    """Two sources advertising the SAME (kind, name) collapse to ONE card - the first wins (D100)."""
    model = SelfModel.assemble(
        MNEMOSYNE_IDENTITY,
        _CardSource(_card("tool", "search_memory", summary="first")),
        _CardSource(_card("tool", "search_memory", summary="second")),
    )

    assert len(model.capabilities) == 1
    assert model.capabilities[0].summary == "first"  # structural dedup, first occurrence kept


def test_assemble_keeps_the_same_name_under_a_different_kind() -> None:
    """Dedup is by (kind, name), not name alone - a tool and a skill may share a name (cloisonnement)."""
    model = SelfModel.assemble(
        MNEMOSYNE_IDENTITY,
        _CardSource(_card("tool", "distill")),
        _CardSource(_card("skill", "distill")),
    )

    assert {(c.kind, c.name) for c in model.capabilities} == {
        ("tool", "distill"),
        ("skill", "distill"),
    }


# --------------------------------------------------------------------------- #
# The Guard accessor - the single truthful source of the tool allow-list (D114-⑤).             #
# --------------------------------------------------------------------------- #
def test_guard_authorized_tools_returns_the_allow_list() -> None:
    """The Guard hands out the manifests it actually rules from - the self-model's ground truth."""
    catalog = ConfigToolCatalog([_manifest("search_memory"), _manifest("read_file")])
    guard = DeterministicGuard(catalog=catalog)

    assert {m.name for m in guard.authorized_tools()} == {"search_memory", "read_file"}


def test_guard_with_no_catalog_authorizes_no_tools() -> None:
    """No catalog wired => an empty allow-list, never an error - deny-by-default holds at the seam (D73)."""
    assert DeterministicGuard().authorized_tools() == ()


# --------------------------------------------------------------------------- #
# The production path - describe_self mirrors the Guard, through CoreApi (D114-TO2 / D119).     #
# --------------------------------------------------------------------------- #
def test_prod_path_describe_self_mirrors_the_guard_allow_list() -> None:
    """describe_self advertises EXACTLY the Guard's authorized tools - truthful by construction."""
    api = CoreApi(bootstrap())

    model = api.describe_self()

    assert model.identity == MNEMOSYNE_IDENTITY
    tool_cards = [c for c in model.capabilities if c.kind == "tool"]
    assert {c.name for c in tool_cards} == {m.name for m in api._guard.authorized_tools()}
    # The model carries surfaces + tools + the skills the operator sanctioned (2026-07-17: this used to
    # assert `<= {"surface", "tool"}` because the shipped registry was empty — it no longer is, and an
    # empty one would now under-state the five live skills). The skill source is proven in
    # test_skill_catalog.py (which pins registry == system/skills/ on disk); the surfaces map in
    # test_describe.py. Here the point is only that describe_self invents no THIRD kind.
    assert {c.kind for c in model.capabilities} <= {"surface", "tool", "skill"}
    # the agent's own read tool is sanctioned in the protected zone (tools.toml) and shows up honestly
    search = next(c for c in model.capabilities if c.name == "search_memory")
    assert (search.effect, search.reach) == ("read_only", "stays_local")


def test_prod_path_describe_self_is_a_pure_read() -> None:
    """Describing is not acting: two reads are equal and the Guard's allow-list is untouched (D100)."""
    api = CoreApi(bootstrap())
    before = api._guard.authorized_tools()

    assert api.describe_self() == api.describe_self()  # idempotent - a value, no side effect
    assert api._guard.authorized_tools() == before  # nothing wired, nothing mutated


def test_prod_path_an_advertised_tool_is_exactly_one_the_guard_authorizes() -> None:
    """Truthful ⟺ ENFORCED, bound LOCALLY: a tool describe_self advertises is one the Guard would
    clear (never refused as unlisted); a name it does NOT advertise is denied by-default (D114-⑤).

    This makes barrier C bite in this file — the advertised set and the enforced allow-list cannot
    diverge, because both read the Guard's single ``_catalog`` (``authorize`` rules without acting)."""
    api = CoreApi(bootstrap())
    advertised = {c.name for c in api.describe_self().capabilities}
    assert "search_memory" in advertised  # the sanctioned read tool is really advertised

    def _rule(name: str) -> Decision:
        return api._guard.authorize(
            GuardRequest(
                effect=Effect.TOOL_CALL,
                subject=Bubble("operator"),
                inputs=(),
                target=name,
                descriptor=f"probe {name!r}",
            )
        ).decision

    # advertised ⇒ allow-listed: the Guard never refuses it as unknown (a read tool clears full-auto;
    # a life-action/leaving one would ESCALATE, never DENY — either way it is NOT deny-by-default).
    assert _rule("search_memory") is not Decision.DENY
    # not advertised ⇒ deny-by-default: an unlisted name is refused (the model cannot under-state).
    assert _rule("definitely_not_a_tool") is Decision.DENY


def test_choix_du_modele_card_addresses_a_doc_that_REALLY_EXISTS() -> None:
    """D163 — address, never copy. `make describe` names a doc it does not restate; a card that
    outlives the file it points at would advertise a dead link to every fresh agent that reads it."""
    api = CoreApi(bootstrap())
    card = next(c for c in api.describe_self().capabilities if c.name == "choix_du_modele")

    assert "docs/governance/CHOIX_DU_MODELE.md" in card.summary
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / "docs/governance/CHOIX_DU_MODELE.md").is_file()
