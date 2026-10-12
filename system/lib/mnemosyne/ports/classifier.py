"""Classifier (D101) - sensitivity labelling by the maximum, deterministic floor.

How Mnémosyne labels content ``public`` / ``perso`` / ``sensible`` - the label
that decides whether a thing may ever leave the machine (the routing RULE is
D66; D101 is the labelling that feeds it).

The label is the **MAXIMUM of three signals**, never the minimum (D101):

1. the **domain / bubble** (the principal signal - D72: content filed under
   "finances" / "santé" is ``sensible`` by nature, without even reading it);
2. a **deterministic floor** by pattern (regex / PII: IBAN, amounts, health,
   identifiers) - hard, testable code;
3. an **optional semantic pass** (small local model) for contextual sensitivity
   (a private journal with no IBAN is still intimate).

Default in doubt = ``sensible`` (fail-safe). This is a "model in the loop"
(D100): the automatic layers can only RAISE the level; the deterministic floor
is **not bypassable downward** by any model (invariant 18 / D100-2); the
semantic pass runs LOCAL, reduced-rights, content-as-data (zero-trust, D81).
Declassification is always a human gesture.

Default OSS brick: a regex/PII floor (ours) accelerated by an optional
**Presidio** pass - see ``system/config/oss_registry.md`` (D101 / D98). The
patterns and the domains are OURS.

Decisions: D101 (labelling)  -  D33 / D66 (taxonomy + routing)  -  D72 (domain
signal)  -  D100 (non-derivation)  -  D54 (transitive taint). Invariant carried: 18
(feeds 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .core import MonotonicityError, Sensitivity


@dataclass(frozen=True, slots=True)
class Classification:
    """A sensitivity verdict and the signals that produced it (D101).

    The contract: ``sensitivity == max(domain_signal, floor, semantic or
    PUBLIC)`` and ``sensitivity >= floor`` always. The deterministic ``floor``
    is the non-bypassable lower bound (invariant 18); a model can push the
    verdict up via ``semantic_signal`` but can never pull it below ``floor``.
    """

    sensitivity: Sensitivity
    floor: Sensitivity  # deterministic regex/PII floor - non-bypassable downward
    domain_signal: Sensitivity  # from the domain / bubble (D72)
    semantic_signal: Sensitivity | None = None  # optional local semantic pass

    def __post_init__(self) -> None:
        # A verdict below the deterministic floor is unrepresentable (invariant 18
        # / D100-2), mirroring the self-enforcing types in ``core``: the floor is
        # a barrier no model can pull under.
        if self.sensitivity < self.floor:
            raise MonotonicityError(
                f"classification {self.sensitivity.token!r} is below the "
                f"deterministic floor {self.floor.token!r} (invariant 18)"
            )


@runtime_checkable
class Classifier(Protocol):
    """Labels content by the maximum of its signals, defaulting to ``sensible``."""

    def classify(
        self,
        content: str,
        *,
        domain_signal: Sensitivity | None = None,
        public_provenance: bool = False,
    ) -> Classification:
        """Classify ``content``, taking ``domain_signal`` (D72) as a known lower hint.

        Returns a :class:`Classification` whose ``sensitivity`` is the maximum of
        all signals and never below the deterministic ``floor`` (invariant 18).
        In doubt, the verdict is ``sensible`` (fail-safe, D101). Any semantic
        layer runs locally on content treated as untrusted data (D100-3 / D81)
        and may only raise the verdict (D100-2).

        ``public_provenance`` is the standing HUMAN declassification (D100-2 / D107):
        set only by the public-source surfaces (library-book ingest, YouTube
        transcript), it labels the datum ``public`` authoritatively, bypassing the
        deterministic floor - which false-positives on published text yet never on
        the operator-managed data. It is the sole seam that may pull a verdict UNDER the
        floor, and only a human gesture, encoded once, opens it.
        """
        ...

    def floor(self, content: str) -> Sensitivity:
        """The deterministic PII floor of ``content`` alone (D101 signal 2) - pure code,
        no model. The non-bypassable lower bound, also used by the Guard to re-check an
        egress payload against a possibly-lying label (M2 / D89 / D100)."""
        ...
