"""Agent-juge (D91) - semantic judgement that can only RAISE prudence (D100).

The Guard's second nature of barrier (CONSTITUTION §3.5): a *local micro-model*
consulted for the semantic judgement a deterministic rule cannot make (is this
outbound action irreversible? is this borderline egress risky?). It is bounded on
every side by the hard barriers (D100): **local, reduced rights, escalation-only**.

The load-bearing guarantee is not the judge's good behaviour - a model is
faillible and manipulable (D100) - but :func:`combine_monotone`: whatever verdict
the judge returns is folded into the deterministic floor by taking the MORE
prudent of the two. A compromised or prompt-injected judge that answers ``ALLOW``
therefore cannot lower a floor of ``ESCALATE`` / ``DENY``; it can only push a
verdict UP the prudence order. That is non-derivation as *structural incapacity*,
not trust (D100-2).

At LOT 3 there is no local judge model yet, so :class:`FailSafeJuge` abstains
(returns the floor unchanged). It still cannot lower anything - by construction of
the combine - so the barrier is real now; the real micro-model plugs in behind the
same :class:`AgentJuge` port later without touching the Guard.

Decisions: D91 (agent-juge: escalation-only, local, reduced rights)  -  D100
(non-derivation)  -  D74 (human grid). Code & docstrings English (D117).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ports import Decision, GuardRequest, Ruling

#: Prudence order over verdicts (D100-2): a model-in-the-loop may move a verdict
#: only UP this ladder, never down. ``ALLOW`` < ``ESCALATE`` < ``DENY``.
_PRUDENCE: dict[Decision, int] = {
    Decision.ALLOW: 0,
    Decision.ESCALATE: 1,
    Decision.DENY: 2,
}


def combine_monotone(floor: Ruling, opinion: Ruling) -> Ruling:
    """Fold a judge's ``opinion`` into the deterministic ``floor``, upward-only (D100).

    Returns the MORE prudent ruling. The judge can raise ``ALLOW`` -> ``ESCALATE`` /
    ``DENY`` (add caution) but can NEVER lower the floor: a hostile ``ALLOW`` against
    a floor of ``DENY`` yields ``DENY``. This is the structural clamp that makes the
    agent-juge safe to consult (D91 / D100-2) - the barrier is the algebra, not the
    model's honesty.
    """
    return opinion if _PRUDENCE[opinion.decision] > _PRUDENCE[floor.decision] else floor


@runtime_checkable
class AgentJuge(Protocol):
    """A local judge consulted for semantic doubt (D91). Advisory and bounded.

    It receives the deterministic ``floor`` and returns its own verdict; the Guard
    reconciles the two with :func:`combine_monotone`, so an implementation *cannot*
    lower prudence whatever it returns. It must treat ``request`` content as DATA,
    never as instruction (zero-trust, D81) - but even a breach of that cannot loosen
    a barrier, only (at worst) fail to add caution."""

    def judge(self, request: GuardRequest, floor: Ruling) -> Ruling:
        """Return a verdict at least as prudent as ``floor`` (enforced by the Guard)."""
        ...


class FailSafeJuge:
    """The LOT 3 stand-in: no local judge model yet, so it abstains (D100-4).

    Returns the deterministic floor unchanged - it adds no judgement it cannot back,
    and, being fed through :func:`combine_monotone`, it structurally cannot lower a
    barrier. The real micro-model (D91) replaces it behind :class:`AgentJuge` with no
    change to the Guard."""

    def judge(self, request: GuardRequest, floor: Ruling) -> Ruling:  # noqa: ARG002 - port shape
        return floor
