"""Policy loader - the protected zone (SE4), read-only, model-agnostic (D70).

Loads ``system/config/policy.toml`` into a frozen :class:`Policy` that the Guard
(D89) consults at every frontier. Read-only is *structural*: ``Policy`` is a frozen
dataclass over immutable collections (``frozenset`` / ``tuple`` / ``MappingProxyType``),
so a surveilled agent that obtains a handle on the running policy still cannot
mutate a barrier (D100: incapacity, not trust - SE4). Changing the policy on disk
is a privileged human act, itself guarded as ``Effect.POLICY_WRITE`` (D102).

Deny-by-default: a missing or empty section authorizes NOTHING (fail-closed, D89).
Read by the standard-library ``tomllib`` - no dependency, so the barrier holds
before the toolchain lands (D116). Code & docstrings English (D117); the
sensitivity *values* keep their French tokens (D33 / D66):
``public`` / ``perso`` / ``sensible``.

Decisions: D89 (the Guard consults the zone)  -  SE4 (read-only protected zone)  -
SE5 (egress allow-list)  -  D66 (routing)  -  D72 (domain cloisonnement)  -  D78 / D112
(bounds)  -  D86 (quotas)  -  D70 (declarative, model-agnostic)  -  D139 (per-domain
recall floor).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .ports import Bubble, Domain, RoutingClass, Sensitivity

#: token -> Sensitivity (reverse of :attr:`Sensitivity.token`), to read the French
#: data tokens carried in the zone (D33 / D66).
_SENSITIVITY_BY_TOKEN: Mapping[str, Sensitivity] = MappingProxyType(
    {s.token: s for s in Sensitivity}
)

#: The protected policy zone: ``<repo>/system/config``, resolved from this module's
#: home (``system/lib/mnemosyne/config.py`` -> ``parents[2]`` is ``system``).
DEFAULT_POLICY_PATH: Path = Path(__file__).resolve().parents[2] / "config" / "policy.toml"


@dataclass(frozen=True, slots=True)
class Contract:
    """A validated cross-bubble output contract (invariant 3): a read from
    ``source`` may cross into ``target``. Absent => denied (deny-by-default)."""

    source: Bubble
    target: Bubble


@dataclass(frozen=True, slots=True)
class Policy:
    """The frozen, read-only policy the Guard keys its verdicts on (SE4).

    Every field is an immutable collection, so a handle on a live ``Policy`` cannot
    loosen a barrier at runtime (D100: structural, not trusted). Query it through
    the methods; the fields are the declarative form of the zone."""

    profile: str
    canal_a_auto: frozenset[Sensitivity]  # sensitivities that may auto-route to canal A
    egress_allowlist: frozenset[str]  # SE5 - hosts a flow may leave to
    contracts: tuple[Contract, ...]  # validated cross-bubble crossings
    declared_domains: Mapping[Bubble, frozenset[Domain]]  # D72 - per-bubble visibility
    bounds: Mapping[str, int]  # D78 / D112 - active resource ceilings
    quotas: Mapping[str, float]  # D86 - cost / token ceilings
    #: D139 - per-domain recall-floor recalibration. Empty by default (the D126 default: no
    #: domain has been recalibrated yet), which is exactly retro-compatible with the pre-D139
    #: behaviour (every domain reads the embedder's one declared `recall_floor`). Query through
    #: :meth:`recall_floor_for`, never this mapping directly, so a missing domain always resolves
    #: to the caller-supplied default rather than a `KeyError`.
    recall_floor_by_domain: Mapping[Domain, float] = MappingProxyType({})
    #: D7 / D70 - the task-class -> model routing table (model-agnostic). Empty by default: every
    #: :class:`~mnemosyne.ports.RoutingClass` falls back to the capable default (:meth:`model_for`
    #: -> ``None`` -> the wired default runner, "frontier suffices for the majority", D66). The bench
    #: (D69) fills it empirically; adding a model is then a CONFIG change, never a code change.
    #: Query through :meth:`model_for`, never this mapping directly.
    model_routing: Mapping[str, str] = MappingProxyType({})

    def may_route_automatically(self, sensitivity: Sensitivity) -> bool:
        """Whether ``sensitivity`` may take an automatic cloud path (canal A, inv. 1)."""
        return sensitivity in self.canal_a_auto

    def egress_allowed(self, host: str | None) -> bool:
        """Whether ``host`` is on the egress allow-list (SE5, inv. 21). ``None`` => no."""
        return host is not None and host in self.egress_allowlist

    def cross_bubble_allowed(self, source: Bubble, target: Bubble) -> bool:
        """Whether a validated contract lets ``source`` cross into ``target`` (inv. 3)."""
        return any(c.source == source and c.target == target for c in self.contracts)

    def domain_declared(self, bubble: Bubble, domain: Domain) -> bool:
        """Whether ``bubble`` declares ``domain`` (D72, inv. 4). Undeclared => denied."""
        return domain in self.declared_domains.get(bubble, frozenset())

    def bound(self, name: str) -> int:
        """A configured resource bound (D78 / D112, inv. 16). Missing => ``KeyError`` -
        an unbounded resource is a bug, never a silent default (fail-closed)."""
        return self.bounds[name]

    def recall_floor_for(self, domain: Domain | None, *, default: float) -> float:
        """The recall floor for ``domain`` (D139, inv. 14): its calibrated value if one has been
        earned, else ``default`` (the caller's embedder-declared floor - unchanged behaviour).

        ``domain`` is ``None`` when a retrieval call carries no single domain to key on (no
        domain filter, or more than one - D139 keys the floor on a FACT of the query, never a
        guess at which of several domains should win); it resolves straight to ``default``, exactly
        the pre-D139 shape. A calibrated domain OVERRIDES the default; an un-calibrated one falls
        back to it - never a silent 0.0 or a ``KeyError`` for a domain this policy has not measured
        yet (fail-closed toward the conservative, already-earned default, D100)."""
        if domain is None:
            return default
        return self.recall_floor_by_domain.get(domain, default)

    def model_for(self, routing_class: RoutingClass, *, default: str | None = None) -> str | None:
        """The model id a task-class routes to (D7 router), or ``default`` when the class has no
        configured entry - the model-agnostic default (``None`` => the wired capable runner, so
        "frontier suffices for the majority" holds until the bench, D69, maps a class to a small
        local model). Model-agnostic (D70): the mapping is CONFIG, never a hard-coded name; a class
        this policy has not mapped never raises - it falls back to the capable default (fail-safe)."""
        return self.model_routing.get(routing_class.value, default)


def _read_sensitivities(tokens: list[str]) -> frozenset[Sensitivity]:
    """Parse French sensitivity tokens; an unknown token raises (never silently
    widens - a typo must fail loudly)."""
    return frozenset(_SENSITIVITY_BY_TOKEN[t] for t in tokens)


def load_policy(path: Path | None = None) -> Policy:
    """Load the protected policy zone into a frozen :class:`Policy` (SE4, read-only).

    Deny-by-default: a missing section becomes an empty allow-set. ``path`` overrides
    the default zone (used by tests); production reads :data:`DEFAULT_POLICY_PATH`.
    """
    source = path if path is not None else DEFAULT_POLICY_PATH
    data = tomllib.loads(source.read_text(encoding="utf-8"))

    routing = data.get("routing", {})
    egress = data.get("egress", {})
    cloisonnement = data.get("cloisonnement", {})
    domains_raw = data.get("domains", {})
    bounds = data.get("bounds", {})
    quotas = data.get("quotas", {})
    recall_floor_raw = data.get("recall_floor", {})
    model_routing = data.get(
        "model_routing", {}
    )  # D7 / D70 - task-class -> model (empty => default)

    contracts = tuple(
        Contract(source=Bubble(c["from"]), target=Bubble(c["to"]))
        for c in cloisonnement.get("contracts", [])
    )
    declared_domains = MappingProxyType(
        {Bubble(b): frozenset(Domain(d) for d in doms) for b, doms in domains_raw.items()}
    )
    return Policy(
        profile=str(data.get("profile", "default")),
        canal_a_auto=_read_sensitivities(routing.get("canal_a_auto", [])),
        egress_allowlist=frozenset(egress.get("allowlist", [])),
        contracts=contracts,
        declared_domains=declared_domains,
        bounds=MappingProxyType({k: int(v) for k, v in bounds.items()}),
        quotas=MappingProxyType({k: float(v) for k, v in quotas.items()}),
        # D139 - absent (the D126 default, no domain calibrated yet) => an empty mapping, so
        # every domain falls back to the caller's default via recall_floor_for (retro-compatible).
        recall_floor_by_domain=MappingProxyType(
            {Domain(d): float(v) for d, v in recall_floor_raw.items()}
        ),
        # D7 / D70 - absent (the D126 default) => empty => every class falls back to the capable
        # default via model_for (model-agnostic; the bench D69 fills this, never the code).
        model_routing=MappingProxyType({str(k): str(v) for k, v in model_routing.items()}),
    )
