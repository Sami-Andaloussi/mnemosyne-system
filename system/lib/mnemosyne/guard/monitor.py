"""Deterministic Guard (D73 / D89) — the reference monitor, fail-closed.

The single, unbypassable, infalsifiable checkpoint of the runtime. Every cross-
bubble crossing, domain read, model call, egress, secret use and life-action passes
through :meth:`DeterministicGuard.authorize` / :meth:`grant`; a guarded resource acts
only on a :class:`~mnemosyne.ports.guard.Grant` it is handed — sealed by an unforgeable,
single-use token the Guard mints and verifies (:meth:`redeem`, M1 / D89 / D100), so a
forged Grant is refused fail-closed. It is
deterministic CODE, not an LLM (D100) — the root of trust — optionally
assisted by a local agent-juge that can only RAISE prudence (:mod:`.juge`).

**The six controls (D89).** The per-call pipeline is (1) cloisonnement + zero-trust
input · (2) model routing (D66) · (3) budget + circuit-breaker (D80 / D86) · (4)
secret injection at the last instant (D81) · (5) call the backend · (6) snapshot +
journal · (7) anti-leak output. LOT 3 delivers the DECISION controls that wrap the
backend call (step 5) — cloisonnement (1) in :meth:`_rule_cross_bubble` /
:meth:`_rule_domain`, routing (2) in :meth:`route_model`, bounds (3) via
:mod:`.bounds`, secret injection (4 / 7) in :meth:`inject_secret` + :meth:`_audit` —
and mints the capability. Executing the call and its snapshot/journal (5–6) is the
runtime's job (LOT 5); the Guard mediates the frontier, it is not the engine.

**Deny-by-default, fail-closed (invariant 5).** Any effect not explicitly cleared is
refused; a plain refusal is a ``Ruling`` (data the caller and the audit log inspect),
while a *bound breach* (a cycle / over-quota, invariant 7) is a normalized raised
error (D108-②) — never a silent free pass. The policy it keys on is the frozen,
read-only zone (:mod:`..config`, SE4): a surveilled agent cannot loosen it, and the
one effect that would mutate it (``POLICY_WRITE``) is escalated as a privileged human
act (D102).

Decisions: D73 (reference monitor) · D89 (mechanics + the six controls) · D66
(routing) · D74 / D91 (human grid + agent-juge) · D81 (secrets, zero-trust) · D100
(non-derivation) · D102 / SE4 (protected zone). Code & docstrings English (D117).
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable
from secrets import token_bytes, token_hex

from ..config import Policy, load_policy
from ..ports import (
    Channel,
    Classifier,
    DataEgress,
    Decision,
    Effect,
    EscalateToHuman,
    GovernanceLabel,
    Grant,
    GrantToken,
    GuardDenied,
    GuardRequest,
    HumanTier,
    Observability,
    ResourceBoundError,
    Ruling,
    Sensitivity,
    ToolCatalog,
    ToolEffect,
    ToolManifest,
    TraceId,
)
from .juge import AgentJuge, FailSafeJuge, combine_monotone
from .secrets import SecretBroker
from .walls import WallLedger

#: Default TTL (seconds) a minted grant's nonce is retained against replay (③-5 — closes the ③-1
#: unbounded-`_spent` debt). Generous: a grant is redeemed at the point of use, ~immediately; past this
#: window a stale grant is refused EXPIRED and its nonce may be swept. Override: bound ``grant_ttl_seconds``.
_DEFAULT_GRANT_TTL_SECONDS: float = 3600.0
#: Soft cap on the spent-nonce registry before an expiry sweep fires (③-5), bounding memory on a
#: long-lived process. Override: bound ``grant_registry_capacity``.
_DEFAULT_SPENT_CAPACITY: int = 8192


class DeterministicGuard:
    """The reference monitor (D73 / D89): deny-by-default, fail-closed, infalsifiable.

    Construct with a :class:`~mnemosyne.config.Policy` (defaults to the protected
    zone), an optional agent-juge (defaults to the fail-safe stand-in), an optional
    secret vault, an optional observability sink for the audit trail, an optional
    tool catalog (D114) the ``TOOL_CALL`` rule reads to govern the 8th effect, and an
    optional :class:`~mnemosyne.guard.walls.WallLedger` (D159) — absent by default, so
    every existing caller is byte-identical; wired, every non-``ALLOW`` verdict this
    Guard returns is deposited, fail-open (:meth:`_log_wall`)."""

    __slots__ = (
        "_policy",
        "_juge",
        "_secrets",
        "_obs",
        "_classifier",
        "_catalog",
        "_key",
        "_spent",
        "_now",
        "_ttl",
        "_spent_cap",
        "_walls",
    )

    def __init__(
        self,
        policy: Policy | None = None,
        *,
        juge: AgentJuge | None = None,
        secrets: SecretBroker | None = None,
        observability: Observability | None = None,
        classifier: Classifier | None = None,
        catalog: ToolCatalog | None = None,
        walls: WallLedger | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._policy: Policy = policy if policy is not None else load_policy()
        self._juge: AgentJuge = juge if juge is not None else FailSafeJuge()
        self._secrets = secrets
        self._obs = observability
        self._classifier = classifier
        self._catalog = catalog
        self._walls = walls
        # M1 (D89 / D100) — a per-Guard HMAC key seals every Grant this Guard mints; it never leaves the
        # Guard, so only this Guard can mint or verify a token. `_spent` maps each redeemed nonce to its
        # signed mint time, enforcing single-use. ③-5 (closes the ③-1 debt): the registry is BOUNDED by a
        # TTL sliding window — a grant older than `_ttl` is refused EXPIRED (its timestamp is signed, so it
        # cannot be shifted to un-expire), so its nonce may be swept without ever re-enabling a replay; the
        # sweep fires when the registry crosses `_spent_cap`, capping memory on a long-lived process. `now`
        # is injected so expiry is deterministically testable (never a hidden wall-clock dependency).
        self._now = now
        self._ttl = float(self._policy.bounds.get("grant_ttl_seconds", _DEFAULT_GRANT_TTL_SECONDS))
        self._spent_cap = int(
            self._policy.bounds.get("grant_registry_capacity", _DEFAULT_SPENT_CAPACITY)
        )
        self._key = token_bytes(32)
        self._spent: dict[str, float] = {}

    # -- self-model read (⑥ / D114-TO2) -----------------------------------------------
    def authorized_tools(self) -> tuple[ToolManifest, ...]:
        """The allow-list the Guard actually rules from — a READ-ONLY view for the self-model (⑥).

        Returns the manifests of the sanctioned tools (never a mutable handle on the catalog, D100),
        or ``()`` when no catalog is wired (deny-by-default: nothing to describe, never an error).
        This is the single truthful source of "what tools I can call": a ``describe_self`` built on it
        can only advertise what the reference monitor would in fact authorize — never more. Reading is
        not wiring — adding a tool stays the privileged human act ``POLICY_WRITE`` (D102 / D114-⑤)."""
        return self._catalog.authorized() if self._catalog is not None else ()

    # -- public contract (ports.Guard) ------------------------------------------------
    def authorize(self, request: GuardRequest) -> Ruling:
        """Rule on ``request`` without performing it (deny-by-default, invariant 5).

        Returns a :class:`Ruling`. A bound breach (invariant 7) raises
        :class:`ResourceBoundError` — that is an exceptional condition, not a plain
        denial. The agent-juge is consulted only to *raise* prudence (D91 / D100);
        it is never a path to lift a deterministic ``DENY``.

        Every non-``ALLOW`` verdict — the FINAL one, after the juge's consultation,
        which is what the caller actually receives — is deposited via :meth:`_log_wall`
        BEFORE it is returned (D159): "hitting a wall stops being silent". This is
        the single choke point every mediated effect already passes through (:meth:`grant`
        calls this method first), so no caller can obtain a refusal that skipped it."""
        floor = self._rule(request)
        if floor.decision is not Decision.DENY:
            try:
                floor = combine_monotone(floor, self._consult_juge(request, floor))
            except Exception:  # noqa: BLE001 - an unstable/hostile juge opinion is doubt, not a pass
                floor = combine_monotone(
                    floor,
                    Ruling(
                        Decision.ESCALATE,
                        "agent-juge opinion unusable — fail-safe escalation (D74 / D100)",
                        HumanTier.FLAG_ROUTINE,
                    ),
                )
        if floor.decision is not Decision.ALLOW:
            self._log_wall(request, floor)
        return floor

    def _log_wall(self, request: GuardRequest, ruling: Ruling) -> None:
        """Deposit one refusal (D159) — best-effort, fail-open (mirrors D111 observability): a
        down or misbehaving ledger must NEVER change what the Guard actually decided, so this
        wraps the call defensively even though :class:`~mnemosyne.guard.walls.WallLedger.record`
        already swallows its own errors (belt and suspenders on the Guard's own trust root)."""
        if self._walls is None:
            return
        try:
            self._walls.record(request, ruling)
        except Exception:  # noqa: BLE001 - the wall log is best-effort; the verdict never depends on it
            return

    def grant(self, request: GuardRequest) -> Grant:
        """Authorize AND mint a capability, or fail closed.

        Raises :class:`EscalateToHuman` when a human gesture is required first (D74,
        invariant 8) and :class:`GuardDenied` on refusal (invariant 5). The only way
        to obtain a :class:`Grant`."""
        ruling = self.authorize(request)  # may raise ResourceBoundError (invariant 7)
        if ruling.decision is Decision.ESCALATE:
            raise EscalateToHuman(ruling.reason or "human gesture required (D74)")
        if ruling.decision is not Decision.ALLOW:
            raise GuardDenied(ruling.reason or "denied (fail-closed, D89)")
        released = self._released_label(request)
        channel = self._grant_channel(request)
        self._audit(request, released)  # records the effect/handle — never a secret value
        return Grant(
            request=request,
            released_label=released,
            channel=channel,
            token=self._mint_token(request, released, channel),
        )

    def redeem(self, grant: Grant) -> None:
        """Authenticate a Grant and consume it (M1 — the structural non-bypass, D89 / D100).

        The single verification point: a guarded resource acts only on a Grant this returns
        cleanly. It recomputes the HMAC over the granted capability and compares in constant time,
        then marks the nonce spent (single-use). A grant with no token (a forged / bare shape), a
        tampered one (signature mismatch), or a replayed one (nonce already spent) raises
        :class:`GuardDenied` — never a silent pass. Only THIS Guard (holder of the key) verifies a
        token it minted; a grant minted by another Guard does not verify here."""
        token = grant.token
        if token is None or grant.channel is None:
            raise GuardDenied("grant carries no capability token — forged or bare (M1 / D100)")
        expected = self._sign(
            grant.request, grant.released_label, grant.channel, token.nonce, token.issued_at
        )
        if not hmac.compare_digest(expected, token.signature):
            raise GuardDenied("grant token does not verify — forged or tampered (M1 / D100)")
        # TTL (③-5) — a grant AT OR PAST the window is refused EXPIRED. Its mint time is signed, so it
        # cannot be shifted to un-expire (D100); checked BEFORE the spent set, so a nonce dropped by the
        # sweep is refused here first and can never be replayed. The `>=` matches the sweep's drop
        # boundary (`ts <= cutoff` ⟺ `age >= ttl`) EXACTLY, so "swept ⟺ expired": no nonce is ever both
        # forgotten AND still redeemable (audit ③-5a MAJEUR-1 — closes the `age == ttl` replay bord that
        # a coarse-granularity clock would hit). A bare/forged token's `issued_at` defaults to epoch (0.0)
        # → read as ancient → refused (fail-safe, atop the signature check).
        age = self._now() - token.issued_at
        if age >= self._ttl:
            raise GuardDenied(
                f"grant expired — minted {age:.0f}s ago, past the {self._ttl:.0f}s window (M1 / ③-5)"
            )
        if token.nonce in self._spent:
            raise GuardDenied("grant already redeemed — single-use (M1 / D100)")
        self._sweep_expired_if_full()
        self._spent[token.nonce] = token.issued_at

    # -- M1 capability sealing (HMAC + nonce, single-use) -----------------------------
    def _grant_channel(self, request: GuardRequest) -> Channel:
        # only effects that can reach OUTSIDE carry a routable channel; every other grant stays
        # LOCAL (most-restrictive), so e.g. a SECRET_USE grant never reads may_leave_machine True.
        if request.effect is Effect.MODEL_CALL:
            return self.route_model(request.inputs)
        if request.effect is Effect.EXTERNAL_OUTPUT:
            # `_grant_channel` runs only after an ALLOW ruling (grant() gates on it). A NON-PUBLIC egress
            # (by label OR by content, M2) reaches ALLOW by exactly ONE path — the canal-B human gesture
            # (D90) — so seal it CANAL_B. This keeps may_leave_machine False for a gestured leak (it is
            # NOT the automatic public cloud) while the signed token records HOW it was cleared. A public
            # egress auto-routes per D66. SAME predicate as `_rule_egress`, so channel and rule can never
            # diverge (D100): keying on `route_model` alone would MISLABEL a `sensible` payload carried
            # under a `public` LABEL as canal A, the very under-statement M2 exists to catch.
            if self._egress_is_non_public(request):
                return Channel.CANAL_B_HUMAN_GESTURE
            return self.route_model(request.inputs)
        return Channel.LOCAL

    def _mint_token(
        self, request: GuardRequest, released: GovernanceLabel, channel: Channel
    ) -> GrantToken:
        nonce = token_hex(16)
        issued_at = self._now()
        return GrantToken(
            nonce=nonce,
            signature=self._sign(request, released, channel, nonce, issued_at),
            issued_at=issued_at,
        )

    def _sweep_expired_if_full(self) -> None:
        # bound the spent-nonce registry (③-5, closes the ③-1 debt): when it crosses the soft cap, drop
        # every EXPIRED nonce. The drop boundary (`ts <= cutoff` ⟺ `age >= ttl`) is EXACTLY `redeem`'s
        # expiry boundary (audit ③-5a MAJEUR-1), so a dropped nonce is guaranteed refused-expired if
        # re-presented — forgetting it re-enables NO replay (single-use holds even at `age == ttl`).
        # Memory stays bounded on a long-lived process; the cap is a sweep TRIGGER, not a hard limit
        # (the true bound is mint-rate × TTL, the grants mintable within one window).
        if len(self._spent) < self._spent_cap:
            return
        cutoff = self._now() - self._ttl
        self._spent = {nonce: ts for nonce, ts in self._spent.items() if ts > cutoff}

    @staticmethod
    def _canon(*fields: str) -> bytes:
        # collision-free framing: each field is prefixed by its byte length, so no value (a domain
        # holding a separator, a crafted bubble / target) can be read as another. The seal binds
        # structure, not a fragile join — closes the canonicalisation ambiguity the ③-1 audit
        # flagged (m-1). `.token` / `.value` below are the str forms (Sensitivity.value is an int).
        out = bytearray()
        for field in fields:
            raw = field.encode("utf-8")
            out += str(len(raw)).encode("ascii") + b":" + raw
        return bytes(out)

    @staticmethod
    def _label_fields(label: GovernanceLabel) -> tuple[str, ...]:
        # a label flattened to atoms; the domain COUNT precedes the (sorted) domains so the
        # variable-length set is unambiguously delimited from whatever follows.
        domains = sorted(str(domain) for domain in label.domains)
        return (label.sensitivity.token, str(label.bubble), str(len(domains)), *domains)

    def _sign(
        self,
        request: GuardRequest,
        released: GovernanceLabel,
        channel: Channel,
        nonce: str,
        issued_at: float,
    ) -> str:
        # bind the token to the WHOLE capability — effect, subject, target, routed channel, the mint
        # time, the released label AND every input label (the input COUNT delimits the list). So a
        # signed grant cannot be re-presented with different inputs, nor its timestamp shifted to
        # un-expire it (M-1 / ③-5, D100 — structural, no consumer may rely on unsigned request fields).
        # The egress payload, the cosmetic descriptor AND the human_gesture are excluded: none define
        # the capability — the routed `channel` (canal B for a gestured leak) already encodes HOW the
        # flow was cleared and IS signed, so a grant can never be re-presented with a forged gesture.
        fields = (
            nonce,
            repr(issued_at),
            request.effect.value,
            str(request.subject),
            request.target or "",
            channel.value,
            *self._label_fields(released),
            str(len(request.inputs)),
            *(atom for label in request.inputs for atom in self._label_fields(label)),
        )
        return hmac.new(self._key, self._canon(*fields), hashlib.sha256).hexdigest()

    def route_model(self, inputs: tuple[GovernanceLabel, ...]) -> Channel:
        """Choose the channel a model call over ``inputs`` may use (D66, invariant 1).

        Most-restrictive: canal A (automatic cloud) ONLY when every input is public and
        the zone permits public auto-routing; any ``perso`` / ``sensible`` / unlabeled
        input forces ``LOCAL`` — never an automatic cloud path."""
        if (
            inputs
            and all(label.may_use_automatic_cloud() for label in inputs)
            and self._policy.may_route_automatically(Sensitivity.PUBLIC)
        ):
            return Channel.CANAL_A_PUBLIC_AUTO
        return Channel.LOCAL

    # -- fail-closed consultation of the agent-juge (D91 / D100 / M3) ------------------
    def _consult_juge(self, request: GuardRequest, floor: Ruling) -> Ruling:
        """Consult the agent-juge fail-closed: a raised exception or a malformed verdict
        is DOUBT ⇒ a fail-safe ``ESCALATE`` — never a silent pass and never a crash
        (mirrors the classifier's semantic pass, D101). The opinion can only RAISE
        prudence through :func:`combine_monotone` (D91 / D100-2); a broken or hostile
        juge therefore cannot crash the Guard into a free pass (a raised ``Exception``
        degrades to a fail-safe ESCALATE; a ``BaseException`` propagates but mints no Grant
        — still fail-closed) nor lower a barrier (D74)."""
        try:
            opinion = self._juge.judge(request, floor)
        except Exception:  # noqa: BLE001 - a failed judgement is doubt, never a silent pass
            opinion = None
        if not isinstance(opinion, Ruling) or not isinstance(opinion.decision, Decision):
            return Ruling(
                Decision.ESCALATE,
                "agent-juge unavailable or malformed — fail-safe escalation (D74 / D100)",
                HumanTier.FLAG_ROUTINE,
            )
        # Materialise a plain, immutable Ruling: a hostile Ruling SUBCLASS could otherwise
        # re-evaluate ``.decision`` between this check and grant's re-reads (a valid-value
        # TOCTOU the raise-only wrap cannot see) — snapshotting once defeats every flip point,
        # so a compromised juge object still cannot mint a Grant off a raised floor (D100).
        return Ruling(opinion.decision, opinion.reason, opinion.tier)

    # -- last-instant secret injection (D81, invariant 22) ----------------------------
    def inject_secret(self, grant: Grant) -> str:
        """Materialize the secret for a ``SECRET_USE`` grant — the ONLY place a value
        appears, handed straight to the backend (least-privilege, D89). It is in no
        ruling, grant, or log (invariant 22). The grant is AUTHENTICATED and consumed first
        (M1): a forged or replayed grant releases no secret (D100)."""
        if self._secrets is None:
            raise GuardDenied("no secret vault configured (invariant 22)")
        self.redeem(grant)  # M1 — verify + consume before any value is materialized
        return self._secrets.redeem(grant)

    # -- deterministic rule table (the six controls, per effect) ----------------------
    def _rule(self, request: GuardRequest) -> Ruling:
        effect = request.effect
        if effect is Effect.CROSS_BUBBLE:
            return self._rule_cross_bubble(request)
        if effect is Effect.DOMAIN_ACCESS:
            return self._rule_domain(request)
        if effect is Effect.MODEL_CALL:
            return self._rule_model_call(request)
        if effect is Effect.EXTERNAL_OUTPUT:
            return self._rule_egress(request)
        if effect is Effect.SECRET_USE:
            return self._rule_secret(request)
        if effect is Effect.LIFE_ACTION:
            return Ruling(
                Decision.ESCALATE, "life-action is never full-auto (D74)", HumanTier.LIFE_DECISION
            )
        if effect is Effect.POLICY_WRITE:
            return Ruling(
                Decision.ESCALATE,
                "the policy zone is privileged — a human act (D102 / SE4)",
                HumanTier.LIFE_DECISION,
            )
        if effect is Effect.TOOL_CALL:
            return self._rule_tool_call(request)
        # any future / unhandled effect: deny-by-default (invariant 5-iii)
        return Ruling(Decision.DENY, f"deny-by-default: {effect.value} not cleared (D89)")

    def _rule_cross_bubble(self, request: GuardRequest) -> Ruling:
        # anti-runaway (invariant 7 / D78): a self-targeting exchange is a cycle — a bound
        # breach, not a plain denial → raise a normalized error.
        if request.target is not None and request.target == str(request.subject):
            raise ResourceBoundError(
                f"inter-bubble cycle: {request.subject!r} targets itself (invariant 7)"
            )
        # cloisonnement (invariant 3 / D54): a read from another bubble is allowed ONLY
        # through a validated output contract; absent ⇒ deny-by-default.
        for label in request.inputs:
            if label.bubble != request.subject and not self._policy.cross_bubble_allowed(
                label.bubble, request.subject
            ):
                return Ruling(
                    Decision.DENY,
                    f"cross-bubble read {label.bubble!r}→{request.subject!r} without a "
                    "validated contract (invariant 3)",
                )
        if not request.inputs:
            return Ruling(Decision.DENY, "cross-bubble request with no inputs — deny-by-default")
        return Ruling(Decision.ALLOW, "cross-bubble contract validated")

    def _rule_domain(self, request: GuardRequest) -> Ruling:
        # domain cloisonnement (invariant 4 / D72): the subject bubble sees ONLY the
        # domains declared for it; an undeclared domain is denied (deny-by-default).
        requested = frozenset().union(*(label.domains for label in request.inputs))
        # B15 — a DOMAIN_ACCESS naming no domain cannot be cleared by vacuity: an empty
        # loop below would fall through to a silent ALLOW, i.e. a free pass earned by
        # emptiness rather than by a declared right (D100 — structural, not caller-discipline:
        # the sole caller `_may_read` only asks when the hit HAS domains, but the Guard itself
        # must still refuse the vacuous case). Escalate to a human instead of allowing.
        if not requested:
            return Ruling(
                Decision.ESCALATE,
                "domain access names no domain — cannot be cleared by vacuity (B15 / D100)",
                HumanTier.FLAG_ROUTINE,
            )
        for label in request.inputs:
            for domain in label.domains:
                if not self._policy.domain_declared(request.subject, domain):
                    return Ruling(
                        Decision.DENY,
                        f"domain {domain!r} not declared for {request.subject!r} (invariant 4)",
                    )
        return Ruling(Decision.ALLOW, "all requested domains declared")

    def _rule_model_call(self, request: GuardRequest) -> Ruling:
        # deny-by-default (invariant 5): a model call with no justified input is refused
        # fail-closed; route_model decides the channel a justified call may use.
        if not request.inputs:
            return Ruling(Decision.DENY, "model call without inputs — deny-by-default (inv. 5)")
        return Ruling(Decision.ALLOW, f"model call routed {self.route_model(request.inputs).value}")

    def _rule_egress(self, request: GuardRequest) -> Ruling:
        # egress deny-by-default / allow-list (invariant 21 / SE5): a flow leaves only to an
        # allow-listed host. This barrier is ABSOLUTE and comes FIRST — a human gesture never
        # over-rides it (adding a host stays a distinct POLICY_WRITE human act, D102): an un-listed
        # target is DENIED even WITH a gesture, so the two egress barriers are independent and BOTH
        # must hold (D90). No gesture is even consulted until the host is allow-listed.
        if not self._policy.egress_allowed(request.target):
            return Ruling(
                Decision.DENY,
                f"egress to {request.target!r} not in allow-list (invariant 21, SE5)",
            )
        # M2 — the label alone can UNDER-state what leaves; the flow is treated at the MOST-restrictive
        # of (labels, content). A non-public flow may leave ONLY through canal B (D90): a FLAG_ROUTINE
        # human gesture — an explicit human validation BEFORE the effect (D74-b), posed by trusted runtime
        # code, NEVER by the content the Guard mediates — clears exactly this flow to the already-allow-
        # listed host. Strictly FLAG_ROUTINE: BENIGN is a notify-after (not a pre-effect validation) and
        # LIFE_DECISION is never full-auto, so neither clears a leak (fail-safe: any other tier still
        # escalates). Absent the gesture, escalate to a human as before; sensible-local holds (invariant 1).
        if self._egress_is_non_public(request):
            if request.human_gesture is HumanTier.FLAG_ROUTINE:
                return Ruling(
                    Decision.ALLOW,
                    f"non-public egress to allow-listed {request.target!r} cleared by a canal-B "
                    "human gesture (D74-b / D90)",
                )
            return Ruling(
                Decision.ESCALATE,
                "non-public egress (by label or by content) needs a canal-B human gesture "
                "(D66 / D90 / M2)",
                HumanTier.FLAG_ROUTINE,
            )
        return Ruling(Decision.ALLOW, f"egress to allow-listed {request.target!r}")

    def _egress_is_non_public(self, request: GuardRequest) -> bool:
        """Whether an egress is non-public by LABEL or by CONTENT (M2) — the ONE predicate BOTH the
        egress rule (is a gesture required?) and the channel sealing (canal A vs canal B) key on, so the
        two can never diverge (D100 / [[consolidate-crosscutting-rules]]). Most-restrictive: a `sensible`
        payload mislabeled `public`, OR any non-public input label, makes the flow non-public."""
        content_floor = self._egress_content_floor(request)
        return not content_floor.may_use_automatic_cloud() or any(
            not label.may_use_automatic_cloud() for label in request.inputs
        )

    def _egress_content_floor(self, request: GuardRequest) -> Sensitivity:
        """Deterministic PII floor of the egress payload (M2): the label can lie, the raw
        content cannot. The Guard never lets out content it could not read, so it does NOT
        trust the label alone — an egress whose ``payload`` it cannot read as text (``None``,
        or ``bytes`` = binary content like an IMAGE, or any off-contract type) OR with no
        classifier wired is fail-closed ``SENSIBLE`` (forcing a canal-B human gesture), never
        a silent label-only pass (D100 — structural, not caller-discipline: an image is
        non-public by its very type, so it can never leave on a mislabeled ``public``). An
        empty string is valid content and floors to ``PUBLIC``. Pure code (regex, D101 signal
        2) — never a model (D100)."""
        payload = request.payload
        if not isinstance(payload, str) or self._classifier is None:
            return Sensitivity.SENSIBLE
        return self._classifier.floor(payload)

    def _rule_secret(self, request: GuardRequest) -> Ruling:
        # a secret is released only if the Guard holds that handle (invariant 22); the
        # value is injected at the call (:meth:`inject_secret`), never decided here.
        handle = request.target
        if handle is None or self._secrets is None or handle not in self._secrets:
            return Ruling(
                Decision.DENY, f"unknown secret handle {handle!r} — deny-by-default (invariant 22)"
            )
        return Ruling(Decision.ALLOW, f"secret {handle!r} may be injected at the call point")

    def _rule_tool_call(self, request: GuardRequest) -> Ruling:
        # the 8th mediated effect (D114 / D89): a tool runs only if the PROTECTED catalog
        # allow-lists it, and the Guard rules from the tool's manifest — never the caller's
        # word (D100). No catalog wired or no named tool ⇒ deny-by-default (D73); an agent can
        # never wire itself to an arbitrary tool / MCP server (D114-⑤).
        if self._catalog is None or request.target is None:
            return Ruling(
                Decision.DENY,
                "tool call without a wired catalog or a named tool — deny-by-default (D114 / D73)",
            )
        try:
            manifest = self._catalog.get(request.target)
        except GuardDenied as denial:
            return Ruling(Decision.DENY, str(denial) or f"tool {request.target!r} not allow-listed")
        # a tool that ACTS on the world (email / payment / publish / sign / delete) is never
        # full-auto — a human decides (D74 / D91), the strongest tier.
        if manifest.effect is ToolEffect.LIFE_ACTION:
            return Ruling(
                Decision.ESCALATE,
                f"tool {manifest.name!r} is a life-action — never full-auto (D74 / D114)",
                HumanTier.LIFE_DECISION,
            )
        # a tool that LEAVES the machine may not carry non-public data automatically: sensible-local
        # holds by itself (D27 / D66 / D114-③). Escalate on non-public data BY LABEL *or* BY CONTENT:
        # the label can UNDER-state what actually leaves, so the raw arguments are re-floored
        # deterministically (M2, mirrors _rule_egress — audit ③-5a MAJEUR-2). A `sensible` argument
        # mislabeled `public` cannot slip out automatically; unreadable content (a non-str payload or no
        # classifier wired) is fail-safe `SENSIBLE` → canal-B gesture, never a silent leak (D100 —
        # structural, not caller-discipline: the Guard never lets out content it could not read).
        if manifest.egress is DataEgress.LEAVES_EXTERNAL:
            content_floor = self._egress_content_floor(request)
            if not content_floor.may_use_automatic_cloud() or any(
                not label.may_use_automatic_cloud() for label in request.inputs
            ):
                return Ruling(
                    Decision.ESCALATE,
                    f"tool {manifest.name!r} leaves the machine carrying non-public data (by label or "
                    "by content) — a canal-B human gesture is required (D66 / D114-③ / M2)",
                    HumanTier.FLAG_ROUTINE,
                )
        return Ruling(Decision.ALLOW, f"tool {manifest.name!r} cleared ({manifest.effect.value})")

    # -- capability minting helpers ---------------------------------------------------
    def _released_label(self, request: GuardRequest) -> GovernanceLabel:
        # the label released data must wear downstream: most-restrictive over the inputs,
        # minted in the subject bubble (a fresh label, never a silent cross-bubble merge —
        # D89 / invariant 3). No inputs ⇒ fail-safe sensible (invariant 23).
        if not request.inputs:
            return GovernanceLabel.unlabeled()
        sensitivity = max(label.sensitivity for label in request.inputs)
        domains = frozenset().union(*(label.domains for label in request.inputs))
        return GovernanceLabel(sensitivity=sensitivity, bubble=request.subject, domains=domains)

    def _audit(self, request: GuardRequest, released: GovernanceLabel) -> None:
        # the audit trail carries the effect and the human-readable descriptor / handle —
        # NEVER a secret value (invariant 22 / D81). A SECRET_USE target is the handle (a
        # name), safe to record; the value lives only in the vault.
        if self._obs is None:
            return
        trace: TraceId = self._obs.start_trace(request.descriptor or request.effect.value, released)
        self._obs.event(
            trace,
            "guard.grant",
            effect=request.effect.value,
            target=request.target or "",
            descriptor=request.descriptor,
        )
