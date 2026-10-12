"""(6) (2nd source) - the protected skill registry: advertise only what user sanctioned ACTIVE (D37).

Biting tests for :mod:`mnemosyne.production.skill_catalog` (the persisted, deny-by-default registry,
a mirror of ``tools.toml``), its projection through :class:`ActiveSkillsSource`, and its wiring as
``CoreApi.describe_self``'s SECOND capability source. The soul's self-aware nerve now hears the active
skills as well as the authorized tools. These prove the structural properties:

* the catalog is READ-ONLY and DESCRIBE-ONLY - it advertises what the protected zone sanctions ACTIVE;
  it activates and runs NOTHING (persisting an activation is a human ``POLICY_WRITE`` act, D102 / D37);
* only ACTIVE is advertised - a DRAFT / AUDITED registry record is filtered out, so the self-model can
  only ever UNDER-state, never over-state (D37 - ACTIVE alone may run; deny-by-default D73);
* a card is GOVERNANCE-SAFE - role / task-class / network reach only; the sensitivity ceiling (D54-9)
  and domains stay a Guard-enforced plafond, never a leaked datum (invariant 22);
* fail-closed at every seam - a duplicate name is REFUSED at load, an unknown token RAISES, a missing
  file is an EMPTY registry (D89 / D100);
* it is the SECOND source of the SAME model - tools and skills co-exist, de-duplicated by (kind, name).

Brick-free: deterministic manifests / a temp TOML / the real bootstrap, nothing installed (D126).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from _invariants import REPO_ROOT

from mnemosyne.api.core_api import CoreApi
from mnemosyne.ports import Sensitivity
from mnemosyne.production import ActiveSkillsSource, ConfigSkillCatalog
from mnemosyne.production.skills import ActivationState, SkillManifest, SkillNeeds, TaskClass
from mnemosyne.runtime import bootstrap


def _skill(
    name: str,
    *,
    state: str = ActivationState.ACTIVE,
    role: str = "do the thing",
    task_class: str = TaskClass.ATOMIC,
    network: bool = False,
    sensitivity_max: Sensitivity = Sensitivity.PERSO,
) -> SkillManifest:
    return SkillManifest(
        name=name,
        version="1.0",
        role=role,
        needs=SkillNeeds(sensitivity_max=sensitivity_max, task_class=task_class, network=network),
        state=state,
    )


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "skills.toml"
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# ConfigSkillCatalog - active() advertises ACTIVE only, deny-by-default (D37 / D73).            #
# --------------------------------------------------------------------------- #
def test_active_returns_the_sanctioned_active_skill() -> None:
    """A skill user sanctioned ACTIVE is advertised by ``active`` - the registry's terminal truth."""
    catalog = ConfigSkillCatalog([_skill("distillateur")])

    assert [m.name for m in catalog.active()] == ["distillateur"]


def test_a_draft_or_audited_skill_is_never_advertised() -> None:
    """DRAFT / AUDITED records live in the registry but are FILTERED from ``active`` - under-state,
    never over-state (D37: ACTIVE is the only state that may run; deny-by-default)."""
    catalog = ConfigSkillCatalog(
        [
            _skill("draft_one", state=ActivationState.DRAFT),
            _skill("audited_one", state=ActivationState.AUDITED),
            _skill("live_one", state=ActivationState.ACTIVE),
        ]
    )

    assert [m.name for m in catalog.active()] == ["live_one"]


def test_an_empty_catalog_advertises_nothing() -> None:
    """No registry entry => nothing active - deny-by-default, an empty tuple, never an error (D73)."""
    assert ConfigSkillCatalog().active() == ()


def test_a_duplicate_skill_name_is_refused_at_load() -> None:
    """Two entries with the SAME name collide - REFUSED fail-closed, no silent shadow (D100)."""
    with pytest.raises(ValueError, match="duplicate skill name"):
        ConfigSkillCatalog([_skill("distillateur"), _skill("distillateur", role="impostor")])


# --------------------------------------------------------------------------- #
# ConfigSkillCatalog.load - the protected zone, fail-closed parsing (D89 / D100).               #
# --------------------------------------------------------------------------- #
def test_load_a_missing_file_is_an_empty_registry(tmp_path: Path) -> None:
    """A MISSING protected file authorises nothing - an empty registry, never an error (D89)."""
    assert ConfigSkillCatalog.load(tmp_path / "absent.toml").active() == ()


def test_load_round_trips_an_active_skill(tmp_path: Path) -> None:
    """A well-formed ACTIVE entry loads into an advertised manifest carrying its declared needs."""
    path = _write(
        tmp_path,
        """
        [[skills]]
        name = "distillateur"
        version = "2.0"
        role = "produce the distilled understanding of a document"
        state = "active"
        sensitivity_max = "perso"
        task_class = "atomic"
        network = false
        domains = ["trading"]
        """,
    )

    (skill,) = ConfigSkillCatalog.load(path).active()

    assert skill.name == "distillateur"
    assert skill.role == "produce the distilled understanding of a document"
    assert skill.needs.sensitivity_max is Sensitivity.PERSO
    assert skill.needs.task_class == TaskClass.ATOMIC
    assert skill.needs.domains == frozenset({"trading"})


def test_load_keeps_a_draft_record_but_does_not_advertise_it(tmp_path: Path) -> None:
    """A DRAFT entry is a legitimate persisted record, yet ``active`` still filters it out (D37)."""
    path = _write(
        tmp_path,
        """
        [[skills]]
        name = "compagnon"
        version = "0.1"
        role = "capture salience"
        state = "draft"
        sensitivity_max = "perso"
        task_class = "atomic"
        """,
    )

    assert ConfigSkillCatalog.load(path).active() == ()


@pytest.mark.parametrize(
    ("field", "line"),
    [
        ("sensitivity_max", 'sensitivity_max = "secret"'),  # not one of public/perso/sensible
        ("task_class", 'task_class = "workflow"'),  # not one of atomic/orchestration
        ("state", 'state = "live"'),  # not one of draft/audited/active
    ],
)
def test_load_refuses_an_unknown_token(tmp_path: Path, field: str, line: str) -> None:
    """An unknown token in the protected zone RAISES - a typo fails loudly, never widens (D100)."""
    lines = [
        "[[skills]]",
        'name = "x"',
        'version = "1.0"',
        'role = "r"',
        'state = "active"',
        'sensitivity_max = "perso"',
        'task_class = "atomic"',
    ]
    body = "\n".join(ln for ln in lines if not ln.startswith(f"{field} ")) + "\n" + line + "\n"

    with pytest.raises(ValueError, match=field):
        ConfigSkillCatalog.load(_write(tmp_path, body))


def test_load_refuses_an_entry_with_no_name(tmp_path: Path) -> None:
    """A nameless entry authorises nothing - refused fail-closed (deny-by-default)."""
    with pytest.raises(ValueError, match="no valid name"):
        ConfigSkillCatalog.load(_write(tmp_path, '[[skills]]\nstate = "active"\n'))


def test_load_refuses_a_non_boolean_network(tmp_path: Path) -> None:
    """A quoted ``network = "false"`` is a STRING, not a boolean - refused fail-closed, never coerced
    to a truthy over-statement of reach (D100). Only a real TOML ``true`` / ``false`` is accepted."""
    body = (
        "[[skills]]\n"
        'name = "x"\n'
        'version = "1.0"\n'
        'role = "r"\n'
        'state = "active"\n'
        'sensitivity_max = "perso"\n'
        'task_class = "atomic"\n'
        'network = "false"\n'
    )
    with pytest.raises(ValueError, match="network"):
        ConfigSkillCatalog.load(_write(tmp_path, body))


# --------------------------------------------------------------------------- #
# ActiveSkillsSource - an ACTIVE manifest becomes a governance-safe card (invariant 22).        #
# --------------------------------------------------------------------------- #
def test_an_active_skill_becomes_a_governance_safe_card() -> None:
    """One ACTIVE skill -> one card projecting role / task-class / reach - and nothing sensitive."""
    (card,) = ActiveSkillsSource(
        ConfigSkillCatalog([_skill("distillateur", role="distill")]).active
    ).cards()

    assert (card.kind, card.name, card.summary) == ("skill", "distillateur", "distill")
    assert (card.effect, card.reach) == ("atomic", "stays_local")


def test_a_network_skill_declares_its_reach_honestly() -> None:
    """A skill that DECLARES a network need has its reach stated plainly - describing ≠ granting."""
    (card,) = ActiveSkillsSource(
        ConfigSkillCatalog(
            [_skill("fetcher", task_class=TaskClass.ORCHESTRATION, network=True)]
        ).active
    ).cards()

    assert card.effect == "orchestration"
    assert card.reach == "needs_network"


def test_the_source_advertises_no_draft_skill() -> None:
    """The source reads ``active`` - a registry of only non-active skills yields no card at all."""
    catalog = ConfigSkillCatalog([_skill("draft_one", state=ActivationState.DRAFT)])

    assert ActiveSkillsSource(catalog.active).cards() == ()


# --------------------------------------------------------------------------- #
# The production path - describe_self carries BOTH sources, through CoreApi (D114-TO2 / D119).  #
# --------------------------------------------------------------------------- #
def test_prod_path_describe_self_advertises_an_active_skill() -> None:
    """describe_self surfaces an ACTIVE registry skill as a governance-safe skill card, ALONGSIDE the
    authorized tools - two truthful sources of ONE self-model (D114-TO2)."""
    catalog = ConfigSkillCatalog([_skill("distillateur", role="distill a document")])
    api = CoreApi(bootstrap(skill_catalog=catalog))

    model = api.describe_self()
    skills = [c for c in model.capabilities if c.kind == "skill"]

    assert [c.name for c in skills] == ["distillateur"]
    (card,) = skills
    assert (card.summary, card.effect, card.reach) == (
        "distill a document",
        "atomic",
        "stays_local",
    )
    assert any(c.kind == "tool" for c in model.capabilities)  # the tool source is still there


def test_prod_path_advertises_exactly_the_skills_that_exist_on_disk() -> None:
    """The SHIPPED registry names every skill the repo actually carries - no more, no less.

    This test USED to pin the opposite ("the shipped registry is honestly empty"). That premise held
    while the skeleton carried no skill (D98: the CONTENANT, not the CONTENU) and expired the day the
    repo started shipping working ones: on 2026-07-17 five skills were versioned under
    `system/skills/` and `distillateur` + `juge` had already produced the whole macro campaign, while
    the registry still said "no skill active yet" to every fresh agent (`make describe` rides the
    SessionStart hook). "Honestly empty" had quietly become a LIE BY OMISSION - the exact thing the
    self-aware nerve exists to prevent. user sanctioned the five (D37/D39-6 ritual: anatomy -> DISTINCT
    Opus content audit -> activation).

    So this now pins the harder property, across the skill LIFECYCLE (D37: a freshly-built skill is
    DRAFT until the distinct-auditor ritual + user's activation - tracked in the zone, but not yet
    advertised). A THREE-way agreement, each leg the structural barrier against a distinct bug
    returning (D100: incapacity, not vigilance):
      - a skill dir added and never DECLARED in the zone => invisible to every fresh agent => FAILS;
      - a name declared with no skill dir behind it => the catalogue promises a ghost => FAILS;
      - `describe` advertises EXACTLY the ACTIVE subset => a draft can never leak out as sanctioned,
        nor a live one be silently dropped => FAILS.
    All three derived from the FILESYSTEM / protected zone, never a hand-typed list (a third home to
    drift)."""
    on_disk = {
        d.name for d in (REPO_ROOT / "system" / "skills").iterdir() if (d / "SKILL.md").is_file()
    }
    zone = tomllib.loads((REPO_ROOT / "system" / "config" / "skills.toml").read_text("utf-8"))
    declared = {s["name"] for s in zone["skills"]}
    active_declared = {s["name"] for s in zone["skills"] if s.get("state") == "active"}

    api = CoreApi(bootstrap())
    model = api.describe_self()
    advertised = {c.name for c in model.capabilities if c.kind == "skill"}

    # 1) every on-disk skill is declared (no invisible skill) AND every declared name exists (no ghost)
    assert declared == on_disk, (
        "system/skills/ and the protected zone disagree - an undeclared skill is invisible to every "
        "fresh agent, a declared-but-absent one is a promise nothing can keep"
    )
    # 2) describe advertises EXACTLY the ACTIVE ones - a DRAFT is tracked in the zone but never advertised
    assert advertised == active_declared, (
        "describe_self must advertise exactly the ACTIVE skills (D37) - not a draft (would over-state a "
        "skill that skipped the audit ritual), not fewer (would under-state a live one)"
    )
    assert advertised, (
        "the repo ships ACTIVE skills; a registry that advertises none lies by omission"
    )
    assert any(c.kind == "tool" for c in model.capabilities)


def test_prod_path_describe_self_stays_a_pure_read_with_skills() -> None:
    """Describing is not acting: with a skill advertised, two reads are still equal (a value, D100)."""
    api = CoreApi(bootstrap(skill_catalog=ConfigSkillCatalog([_skill("distillateur")])))

    assert api.describe_self() == api.describe_self()
