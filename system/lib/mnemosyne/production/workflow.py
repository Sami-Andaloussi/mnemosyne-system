"""Production workflow (D79 / D121-D1) - produce -> audit -> promote -> output, draft-only auto.

Producing is a first-order finality (D79), not an afterthought: ``projects/`` is the
fabrication engine, and this is its *contenant* - the orchestration skill (D42) that turns a
draft into a validated deliverable (D121-D1). The concrete per-project production workflows
are *contenu*, generated just-in-time (D37 / D98); what LOT 6 graves is the cycle and its
barrier.

The barrier sits where the risk is - at PROMOTION / OUTPUT, not on the free internal
iteration (D79):

* **Audit by a DISTINCT verifier (D79 / D75 / D100-6).** A draft is iterated freely in the
  bubble; promoting it to a validated deliverable requires a verifier ≠ its producer.
* **Promotion + distribution = a human gesture (D79 / D96).** A background routine MAY
  fabricate a draft automatically, but promotion and output are never auto: the automation
  produces, it does not publish (D79 / D96 - nothing sensible leaves in auto, D66).

So :meth:`ProductionWorkflow.promote` fails closed on a self-audit (``PromotionRefused``,
DENIED) and escalates on a missing human gesture (``EscalateToHuman``, ESCALATE_HUMAN) - two
distinct normalized outcomes (D108-(2)). Output itself crosses the frontier through the Guard
(egress / output contract - invariants 21 / 1 / 3), not reimplemented here. Code & docstrings
English (D117).

Decisions: D79 (production = 1st-order finality; audit at promotion; auto = draft-only)  -
D121-D1 (the contenant)  -  D75 / D100-6 (producer ≠ verifier)  -  D96 (auto stalls on a human
gesture, never degrades silently)  -  D42 / D108 (orchestration skill).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..ports import Envelope, ErrorCode, EscalateToHuman, MnemosyneError, Provenance
from .verifier import require_distinct


class PromotionRefused(MnemosyneError):
    """A draft was promoted by its own producer (self-audit) - refused fail-closed (D79/D75).

    Like a Guard denial (``DENIED``): a deliverable never promotes on the producer's own word;
    a DISTINCT verifier must sign off first (D100-6)."""

    code = ErrorCode.DENIED


@dataclass(frozen=True, slots=True)
class Draft:
    """A work-in-progress deliverable, iterated freely inside its bubble (D79).

    ``automatic`` records whether a background routine produced it (D67): that is allowed, but
    it changes nothing at promotion - the human gesture is still required (D79 / D96). The
    payload's label carries the sensitivity (``sensible`` by default until declassified,
    D107); this class does not relabel it."""

    content: Envelope[str]
    producer: str
    automatic: bool = False


@dataclass(frozen=True, slots=True)
class Deliverable:
    """A promoted, audited, human-validated deliverable ready to be output (D79).

    Records the evidence - the distinct verifier and that a human validated - so the
    promotion is auditable (D71 / D19). Output (canal A public / canal B, or an output
    contract to another bubble) goes through the Guard afterwards (invariants 21 / 1 / 3)."""

    content: Envelope[str]
    producer: str
    verifier: str
    provenance: Provenance


class ProductionWorkflow:
    """The production contenant (D121-D1): an orchestration skill (D42) with a gated promotion.

    ``draft`` produces freely (auto allowed, D67); ``promote`` is the single barrier - distinct
    verifier + human gesture - after which output is a Guard-mediated egress (not here)."""

    __slots__ = ()

    name: str = "production"
    version: str = "0"

    def draft(self, content: Envelope[str], *, producer: str, automatic: bool = False) -> Draft:
        """Produce a draft inside the bubble (D79). Free iteration; auto is allowed (D67).

        The barrier is not here - a draft carries no promotion authority; it is inert until
        :meth:`promote` clears both gates."""
        return Draft(content=content, producer=producer, automatic=automatic)

    def promote(self, draft: Draft, *, verifier: str, human_validated: bool) -> Deliverable:
        """Promote a draft to a validated deliverable - or refuse / escalate (D79 / D96).

        Fails closed on a self-audit (``PromotionRefused``); escalates when the human gesture
        is absent (``EscalateToHuman``) - an automatic draft can never promote itself, so
        "the automatism PRODUCES, it does not PUBLISH alone" (D79)."""
        require_distinct(draft.producer, verifier, PromotionRefused, what="production promotion")
        if not human_validated:
            raise EscalateToHuman(
                "promotion + distribution is a human gesture (D79 / D96): a background "
                "routine may draft, never promote - no auto publish"
            )
        parent = draft.content.label.provenance
        provenance = Provenance(
            origin=draft.producer,
            produced_by=f"promotion(verifier={verifier})",
            at=datetime.now(timezone.utc),  # UTC (D84)
            parents=(parent,) if parent is not None else (),
        )
        return Deliverable(
            content=draft.content,
            producer=draft.producer,
            verifier=verifier,
            provenance=provenance,
        )
