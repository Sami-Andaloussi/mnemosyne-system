"""Deterministic sensitivity classifier (D101, invariant 18) - labelling by the MAX.

How Mnémosyne turns content into a ``public`` / ``perso`` / ``sensible`` label - the
label that decides whether a thing may ever leave the machine (the routing RULE is
D66; this is the labelling that feeds it). Concrete implementation of the
:class:`~mnemosyne.ports.classifier.Classifier` port.

**The label is the MAX of three signals** (never the min - D101): the domain / bubble
(the principal signal, D72), a deterministic regex/PII **floor** (IBAN, card, French
NIR, health terms - hard, testable code), and an optional local **semantic pass** for
contextual sensitivity (an intimate journal with no IBAN is still intimate). In doubt
- no domain hint - the verdict is ``sensible`` (fail-safe, D101 / invariant 23).

**Non-derivation (D100).** The automatic layers can only RAISE the level. The
deterministic floor is a barrier no model can pull under: the verdict is
``max(floor, domain, semantic)``, and :class:`~mnemosyne.ports.classifier.Classification`
refuses to hold a sensitivity below its floor. Declassification is always an explicit
human gesture (D100-2 / D107), never a model's say-so.

**Where the Garde fits (D89).** The deterministic parts (floor, domain) are pure code -
they ARE hard barriers (D100-1), not model calls, so they need no mediation. The
semantic pass is the only model in the loop: when a real local model plugs in (LOT 5,
with the runner) it routes its call through the Garde (D89), content-as-data
(D100-3 / D81), and can only raise (its opinion enters solely through the ``max``). LOT
4a ships the fail-safe :class:`NullSemanticSensor` (abstains), mirroring the Guard's
``FailSafeJuge`` (D91).

Default OSS brick for the floor: our regex, optionally accelerated by **Presidio**
(``system/config/oss_registry.md``, D101 / D98) - the patterns and domains are OURS.
Code & docstrings English (D117); sensitivity tokens stay French (D33 / D66).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..ports import DEFAULT_SENSITIVITY, Classification, Sensitivity


@runtime_checkable
class SemanticSensor(Protocol):
    """Optional local-model contextual pass (D101 signal 3) - RAISE-only (D100).

    ``assess`` returns the sensitivity the content *contextually* warrants, or ``None``
    to abstain. It runs LOCAL on content treated as untrusted data (zero-trust,
    D100-3 / D81) and reaches a model only through the Garde (D89). Its opinion can
    only raise the verdict - the classifier feeds it through a ``max``, so a
    compromised or injected sensor can never lower a label (invariant 18 / D100-2)."""

    def assess(self, content: str) -> Sensitivity | None: ...


class NullSemanticSensor:
    """Fail-safe stand-in: abstains until a real local model plugs in (LOT 5, behind
    the Garde). Mirrors the Guard's ``FailSafeJuge`` - the seam exists, the model does
    not yet, and the structural raise-only guarantee holds without it (D100 / D91)."""

    def assess(self, content: str) -> Sensitivity | None:  # noqa: ARG002 - abstains
        return None


class CompositeSemanticSensor:
    """Combine several raise-only :class:`SemanticSensor`s by the MAX (D101 / D100 / invariant 18).

    Lets more than one contextual pass share the classifier's single ``semantic`` slot - e.g. the local
    LLM sensor (contextual sensitivity) AND the Presidio PII sensor ((3)-6b), both raise-only. ``assess``
    returns the MAX sensitivity any sub-sensor warrants, or ``None`` when they ALL abstain - so the
    composite is itself raise-only (it can only push the classifier's verdict UP, never below the
    deterministic floor, invariant 18). A sub-sensor that RAISES is NOT swallowed here: it propagates to
    the classifier's fail-safe wrapper (a failed pass => ``sensible``, D100), the same fail-closed conduct
    as a single sensor - the deterministic floor stays THE barrier regardless."""

    __slots__ = ("_sensors",)

    def __init__(self, sensors: Sequence[SemanticSensor]) -> None:
        self._sensors: tuple[SemanticSensor, ...] = tuple(sensors)

    def assess(self, content: str) -> Sensitivity | None:
        verdict: Sensitivity | None = None
        for sensor in self._sensors:
            level = sensor.assess(content)
            if level is not None:
                verdict = level if verdict is None else max(verdict, level)
        return verdict


@dataclass(frozen=True, slots=True)
class PiiRule:
    """One deterministic pattern that raises the floor to ``sensitivity`` on a match.

    OURS and testable (D101 signal 2) - code, not a trusted model (D100-1). The floor
    is conservative by design: a false positive only RAISES prudence (fail-safe); a
    miss is caught by the domain signal or the semantic pass."""

    name: str
    pattern: re.Pattern[str]
    sensitivity: Sensitivity


def _rule(name: str, pattern: str, sensitivity: Sensitivity) -> PiiRule:
    return PiiRule(name=name, pattern=re.compile(pattern, re.IGNORECASE), sensitivity=sensitivity)


#: The deterministic PII floor (D101 signal 2). High-precision, French-aware patterns;
#: extend via the ``rules`` argument. A match raises the floor to the rule's sensitivity.
DEFAULT_PII_RULES: tuple[PiiRule, ...] = (
    _rule("iban", r"\b[A-Z]{2}\d{2}(?:\s?[A-Za-z0-9]){9,30}\b", Sensitivity.SENSIBLE),
    _rule("card", r"\b\d{4}(?:[ -]?\d{4}){3}\b", Sensitivity.SENSIBLE),
    _rule("nir", r"\b[12](?:[ .]?\d){14}\b", Sensitivity.SENSIBLE),
    _rule(
        "health",
        r"\b(?:ordonnance|diagnostic|diagnosis|sympt[oô]mes?|m[ée]dical\w*|IRM|"
        r"radiographie|prescription)\b",
        Sensitivity.SENSIBLE,
    ),
    _rule("email", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", Sensitivity.PERSO),
    _rule("phone", r"(?:\+\d{6,15}\b|\b0[1-9](?:[ .]?\d{2}){4}\b)", Sensitivity.PERSO),
)

#: The top of the monotonic sensitivity order (invariant 17) - nothing can be raised above it. Derived
#: from the enum (not hard-coded ``SENSIBLE``) so it stays correct if a higher level is ever added.
_CEILING = max(Sensitivity)


class DeterministicClassifier:
    """Labels content by ``MAX(domain, deterministic PII floor, local-semantic)`` with a
    fail-safe ``sensible`` default and a floor no model can pull under (invariant 18).

    Implements :class:`~mnemosyne.ports.classifier.Classifier`. The deterministic floor
    is the root of trust (D100-1); the semantic sensor (default: abstaining) can only
    raise the verdict."""

    __slots__ = ("_rules", "_semantic")

    def __init__(
        self,
        *,
        rules: Sequence[PiiRule] = DEFAULT_PII_RULES,
        semantic: SemanticSensor | None = None,
    ) -> None:
        self._rules: tuple[PiiRule, ...] = tuple(rules)
        self._semantic: SemanticSensor = semantic if semantic is not None else NullSemanticSensor()

    def classify(
        self,
        content: str,
        *,
        domain_signal: Sensitivity | None = None,
        public_provenance: bool = False,
    ) -> Classification:
        """Classify ``content`` as ``MAX(domain, PII floor, semantic)``, never below floor.

        ``domain_signal`` (D72) is a known lower bound; **absent, it fail-safes to
        ``sensible``** (D101 "défaut en cas de doute" - the ingestion layer passes the
        real bubble sensitivity, invariant 23). A model in the loop can only raise.

        ``public_provenance`` is the ONE explicit human declassification the doctrine
        reserves (D100-2 / D107). Set solely by the public-source surfaces - a published
        book, a YouTube transcript - it labels the datum ``public`` AUTHORITATIVELY and
        RESETS the floor to ``public``: the deterministic PII floor false-positives on
        published text (an author's email, the word "diagnostic", an ISBN shaped like a
        card number) but never on the operator-managed data, so a public source stays public
        whatever its wording, killing the recurring mislabel debt at the root. Generic
        capture never sets it - nothing else is declassified; the floor stays THE barrier
        everywhere else (invariant 18)."""
        if public_provenance:
            # Standing human declassification by provenance (D100-2 / D107): authoritative PUBLIC.
            # The floor is reset to PUBLIC so the Classification invariant (sensitivity >= floor)
            # holds honestly - the human gesture, not a measurement, set this label; the semantic
            # pass is not consulted (a published source is public regardless of its wording).
            return Classification(
                sensitivity=Sensitivity.PUBLIC,
                floor=Sensitivity.PUBLIC,
                domain_signal=domain_signal if domain_signal is not None else DEFAULT_SENSITIVITY,
                semantic_signal=None,
            )
        floor = self.floor(content)
        domain = domain_signal if domain_signal is not None else DEFAULT_SENSITIVITY
        base = max(floor, domain)
        # The semantic pass is RAISE-ONLY (invariant 18): it can push the verdict UP, never under the
        # deterministic base. So when the base is ALREADY at the ceiling, no assessment can change the
        # verdict - skip the (model-backed, costly) pass entirely. Provably behaviour-preserving
        # (``max(_CEILING, x) == _CEILING``), so it NEVER lowers a label (D100-2 / invariant 17); it only
        # avoids a wasted model call (~30 s of MLX per document on the fail-safe ``sensible`` path - the
        # (3)-4b dogfood found the semantic pass running then being discarded by the max on every capture).
        semantic = None if base >= _CEILING else self._assess(content)
        verdict = max(base, semantic if semantic is not None else Sensitivity.PUBLIC)
        return Classification(
            sensitivity=verdict, floor=floor, domain_signal=domain, semantic_signal=semantic
        )

    def floor(self, content: str) -> Sensitivity:
        """The deterministic lower bound (``Classifier.floor``): MAX sensitivity over the
        matching PII rules. Pure code (no model), reused by the Guard's egress re-check (M2)."""
        level = Sensitivity.PUBLIC
        for rule in self._rules:
            if rule.sensitivity > level and rule.pattern.search(content):
                level = rule.sensitivity
        return level

    def _assess(self, content: str) -> Sensitivity | None:
        """Run the semantic pass fail-safe: a raised exception is doubt => ``sensible``.

        The opinion is returned raw (recorded on the Classification) but enters the
        verdict only through ``max`` - it can never lower the floor (D100-2)."""
        try:
            return self._semantic.assess(content)
        except Exception:  # noqa: BLE001 - a failed pass is doubt, never a silent low label
            return DEFAULT_SENSITIVITY
