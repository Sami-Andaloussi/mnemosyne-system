"""Guard (``Guard``) - the runtime reference monitor (D73 / D89).

The single, unbypassable, fail-closed checkpoint. Every model call, every
external output, every secret use, and every cross-bubble crossing passes
through it (D89: "the Guard mediates boundaries, not the interior"). The unforgeable
token that would seal a Grant against forgery is deferred to (3) (M1); today the
non-bypass rests on the mediation path (see :class:`Grant`). It is deterministic code,
not an LLM (D100-1) - the root of trust -
optionally assisted by a local *agent-juge* (D91) that can only RAISE prudence,
never lower a barrier.

Deterministic pipeline of one guarded call (D89): (1) cloisonnement check +
zero-trust input; (2) model choice per D66; (3) budget + circuit-breaker
(D80 / D86); (4) secret injection at the last instant (D81 / invariant 22);
(5) call the backend; (6) snapshot + journal (D76 / D71); (7) anti-leak output
check (D81). Two natures of barrier: a hardcoded deterministic root of trust,
and the agent-juge for semantic judgement only - itself bounded by the hard
barriers (D89-b / D100).

This port is OUR glue, not an OSS engine (registry: ``Guard`` = code maison /
inspi.). It is sketched here as a contract; the deterministic implementation,
the agent-juge, and the protected ``system/config`` policy zone land in LOT 3.

Decisions: D89 (mechanics)  -  D73 (reference monitor)  -  D74 / D91 (human grid +
agent-juge)  -  D66 (sensitivity routing)  -  D81 (secrets, zero-trust)  -  D100
(non-derivation). Invariants carried: 5, 6, 7, 8, 17, 21, 22 (mediation of
1, 3, 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from .core import Bubble, GovernanceLabel


class HumanTier(Enum):
    """The 3-level human-guard grid (D74)."""

    BENIGN = "benign"  # (a) applied automatically, then notified / revocable (D59)
    FLAG_ROUTINE = "flag_routine"  # (b) explicit human validation BEFORE effect
    LIFE_DECISION = "life_decision"  # (c) never full-auto (D74): irreversible /
    #     high-stakes / outbound to the real world


class Effect(Enum):
    """The frontier kinds the Guard mediates (D89). Raw intra-bubble reads/writes
    are NOT here - they are structurally compartmented (D89, realized by D99),
    not Guard-checked; the *domain* frontier within a bubble is (DOMAIN_ACCESS)."""

    CROSS_BUBBLE = "cross_bubble"  # inter-bubble crossing -> validated contract (inv. 3)
    DOMAIN_ACCESS = "domain_access"  # knowledge read gated by the bubble's declared
    #     domains (D72, inv. 4) - the domain frontier the Guard mediates (wired LOT 3)
    MODEL_CALL = "model_call"  # any call to a model (D89 aiguilleur, D66)
    EXTERNAL_OUTPUT = "external_output"  # egress -> allow-list, deny-by-default (inv. 21)
    TOOL_CALL = "tool_call"  # a plug-in / MCP tool invocation (D114)
    SECRET_USE = "secret_use"  # a secret is needed (injected last instant, inv. 22)
    LIFE_ACTION = "life_action"  # email / payment / publish / sign / delete (D74)
    POLICY_WRITE = "policy_write"  # mutate the protected system/config zone - a
    #     privileged human act, never agent-auto (inv. 5-ii, D102 / SE4 ; wired LOT 3)


class Channel(Enum):
    """Where a model call may be routed (D66 matrix, applied by the Guard, D89)."""

    LOCAL = "local"  # always allowed; the only channel for `sensible` processing
    CANAL_A_PUBLIC_AUTO = "canal_a"  # automatic third-party cloud - `public` ONLY (inv. 1)
    CANAL_B_HUMAN_GESTURE = "canal_b"  # semi-manual file bridge for `perso` / `sensible` (D90)


class Decision(Enum):
    """The Guard's verdict. Default is DENY (deny-by-default, D73 / invariant 5)."""

    ALLOW = "allow"
    DENY = "deny"  # fail-closed
    ESCALATE = "escalate"  # route to a human (carries a HumanTier)


@dataclass(frozen=True, slots=True)
class GuardRequest:
    """A request to perform one guarded effect.

    The Guard decides from the *labels* - the etiquette travels (D108-(5)) - and never
    trusts the caller's good behaviour (D100). The one exception is EGRESS: a label can
    UNDER-state what actually leaves, so ``payload`` (the raw outbound content) lets the
    Guard re-derive a deterministic PII floor and refuse a mislabeled leak (M2). It may be
    ``str`` (text the floor CAN read) or ``bytes`` (binary content - an image - the floor
    CANNOT read, so it fail-closes to ``SENSIBLE``, forcing a canal-B gesture): the type
    itself carries "unreadable => non-public", so no caller can smuggle an image out as
    ``public`` by mislabeling it. It is read-only, used only for ``EXTERNAL_OUTPUT``, and
    never logged. ``descriptor`` is the human-readable action shown on a FLAG and journalled.

    ``human_gesture`` is the semi-manual canal-B door (D90): an explicit human validation that a
    NON-PUBLIC egress may leave. It is set by trusted RUNTIME CODE after an interactive human
    confirmation - never derived from the (untrusted) content the Guard mediates (an image or a
    document cannot authorize its own exfiltration, D100). It relaxes ONLY the sensitivity
    escalation, and ONLY for ``EXTERNAL_OUTPUT``: the allow-list barrier is independent and
    absolute (an un-listed host stays DENIED even with a gesture - adding a host is a distinct
    ``POLICY_WRITE`` human act). The two egress barriers therefore both hold (D90).
    """

    effect: Effect
    subject: Bubble  # the bubble making the request
    inputs: tuple[GovernanceLabel, ...]  # labels of every datum involved
    target: str | None = None  # destination: model backend / egress host / tool / bubble
    descriptor: str = ""
    # egress only: raw content, re-floored against its label (M2); repr-hidden so the content can never
    # surface in a log line via repr(request)/repr(grant) (inv22). ``bytes`` = binary the floor cannot
    # read => fail-closed SENSIBLE (an image is gesture-gated by its very TYPE, not by caller discipline).
    payload: str | bytes | None = field(default=None, repr=False)
    # egress only: a canal-B human gesture (D74-b / D90) authorizing a NON-PUBLIC flow to leave.
    # Posed by trusted runtime code after an interactive confirmation, never by content (D100).
    # ``None`` (the default) = no gesture, so every pre-existing request is byte-identical to before.
    human_gesture: HumanTier | None = None


@dataclass(frozen=True, slots=True)
class Ruling:
    """The Guard's reasoned verdict (returned by :meth:`Guard.authorize`)."""

    decision: Decision
    reason: str = ""
    tier: HumanTier | None = None  # set when ``decision is Decision.ESCALATE``


@dataclass(frozen=True, slots=True)
class GrantToken:
    """The unforgeable seal of a :class:`Grant` (M1 - D89 / D100): a single-use HMAC over the
    granted capability. Only the Guard (holder of the key) can mint one, and only the Guard can
    verify and consume it (:meth:`Guard.redeem`); a forged, tampered, or replayed token is
    refused fail-closed. Safe to log - it reveals neither the key nor any secret (invariant 22).

    ``issued_at`` is the mint time (UTC epoch seconds), BOUND INTO the signature so it cannot be
    shifted to un-expire a stale grant. It lets the monitor bound its spent-nonce registry by a TTL
    sliding window ((3)-5 - closes the (3)-1 debt where the registry grew unbounded): a grant at or past
    the TTL is refused as expired on the SAME boundary its nonce is swept, so a forgotten nonce is
    always refused-expired and can never re-enable a replay (audit (3)-5a). A bare / forged token
    defaults to ``0.0`` (epoch) - read as ancient, hence refused expired.
    """

    nonce: str
    signature: str
    issued_at: float = 0.0


@dataclass(frozen=True, slots=True)
class Grant:
    """A capability minted by the Guard that authorizes ONE guarded effect.

    Guarded resources (Runner, egress, tools, secrets, graph writes) require a ``Grant`` to act,
    so every guarded effect is mediated by the Guard. A grant is single-use and scoped, and
    carries the (possibly raised) ``released_label`` the data must wear downstream, the
    ``channel`` it was routed to (D66), and - the structural non-bypass, not mere discipline
    (D100), completed by M1 - an unforgeable ``token`` the Guard verifies AND consumes at the
    point of use (:meth:`Guard.redeem`). A resource that authenticates the token acts only on a
    genuine, unspent grant; a ``Grant`` built without the Guard carries no valid token and is
    refused fail-closed. The ``channel`` / ``token`` default to ``None`` so a bare shape is still
    expressible (a test double, a forged grant) - but such a grant never passes ``redeem``.
    """

    request: GuardRequest
    released_label: GovernanceLabel
    channel: Channel | None = None
    token: GrantToken | None = None

    @property
    def may_leave_machine(self) -> bool:
        """Whether this capability was routed to the automatic public cloud (canal A, D66).

        A non-local back-end MUST refuse a grant for which this is false: ``perso`` / ``sensible``
        - and every non-routed grant - stays ``LOCAL`` (sensible-local holds structurally, D27 /
        D66). The ``channel`` is sealed inside the signed ``token``, so it cannot be forged upward.
        """
        return self.channel is Channel.CANAL_A_PUBLIC_AUTO


@runtime_checkable
class Guard(Protocol):
    """The reference monitor. Deny-by-default, fail-closed; every minted Grant is sealed by an
    infalsifiable single-use token the monitor mints (:meth:`grant`) and verifies + consumes
    (:meth:`redeem`) - the structural non-bypass M1 (D89 / D100)."""

    def authorize(self, request: GuardRequest) -> Ruling:
        """Rule on a request WITHOUT performing it.

        Returns a :class:`Ruling`; never raises for a plain denial - the verdict
        is data the caller (and the audit log) can inspect. Deny-by-default: no
        explicit allow -> ``Decision.DENY`` (invariant 5).
        """
        ...

    def grant(self, request: GuardRequest) -> Grant:
        """Authorize AND mint a capability for the effect, or fail closed.

        Raises :class:`~mnemosyne.ports.core.GuardDenied` on denial and
        :class:`~mnemosyne.ports.core.EscalateToHuman` when a human gesture is
        required first (D74). The only way to obtain a :class:`Grant`.
        """
        ...

    def redeem(self, grant: Grant) -> None:
        """Authenticate a Grant and consume it - the single verification point (M1, D89 / D100).

        A guarded resource acts only on a grant this returns cleanly. Raises
        :class:`~mnemosyne.ports.core.GuardDenied` for a forged, tampered, or replayed grant
        (single-use). Only the minting monitor can verify its own tokens.
        """
        ...

    def route_model(self, inputs: tuple[GovernanceLabel, ...]) -> Channel:
        """Choose the channel allowed for a model call over these labels (D66).

        ``public`` may use canal A (automatic cloud); ``perso`` / ``sensible``
        may only run ``LOCAL`` or wait for a canal-B human gesture - never canal A
        automatically (invariant 1). Fail-safe: any unlabeled input forces the
        most restrictive routing.
        """
        ...

    def inject_secret(self, grant: Grant) -> str:
        """Materialize a ``SECRET_USE`` secret at the call point - the ONLY place a value appears
        (D81, invariant 22). The grant is authenticated (M1) and consumed first; a forged grant
        releases nothing. Raises :class:`~mnemosyne.ports.core.GuardDenied` fail-closed.
        """
        ...
