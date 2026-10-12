"""Presidio adapters — the SOLE importers of Presidio behind the PII seams (D101 / D103 / invariant 20).

Two accelerating passes behind the ③-6b PII seams, wrapping **Microsoft Presidio** (MIT;
``oss_registry.md``): a :class:`~mnemosyne.ingest.classifier.SemanticSensor` that RAISES a sensitivity
when Presidio's analyzer finds PII, and a :class:`~mnemosyne.ports.renderer.Redactor` that MASKS PII
spans via Presidio's anonymizer. Each is a sole-importer adapter — the one module allowed to touch its
brick (``presidio_analyzer`` / ``presidio_anonymizer``) — so the pipeline speaks only the ports and the
suite stays green with NO Presidio installed (D126). Everything that REACHES A BRICK is
``# pragma: no cover``: it needs the installed package (+ its spaCy models), absent in CI, exercised only
at ③ ignition. The pure entity→sensitivity mapper (:func:`_sensitivity_for_entities`) is deterministic,
brick-free, UNIT-TESTED — it is where an analyzer finding is turned into a verdict.

**A brick is NEVER a barrier (D100 — the whole point of ③-6b).**

* The **sensor** may ONLY RAISE. :meth:`_PresidioSensor.assess` returns a :class:`Sensitivity` when
  Presidio finds PII, else ``None`` to ABSTAIN — it never returns ``PUBLIC`` to pull a label DOWN. The
  deterministic regex floor in :class:`~mnemosyne.ingest.classifier.DeterministicClassifier` stays THE
  barrier; the sensor's opinion enters solely through the classifier's ``max`` (invariant 18). A
  compromised / mis-configured analyzer can only over-flag (fail-safe), never launder.
* The **redactor** only MASKS. Its output is NOT trusted clean: the
  :class:`~mnemosyne.runtime.render.GovernedRenderer` RE-CLASSIFIES the redacted text and emits it as
  public only if the deterministic floor agrees (D100 — a redactor that under-cleans cannot lower the
  verdict). This adapter therefore does not claim its output is safe; it just accelerates the masking.

Decisions: D101 (deterministic floor is the barrier; Presidio accelerates it) · D103 (sole importer) ·
D126 (brick-free suite, injected analyzer / anonymizer) · D100 (governance is our code, not the brick) ·
invariant 18 (raise-only). Code & docstrings English (D117); sensitivity tokens stay French (D33 / D66).
"""

from __future__ import annotations

from collections.abc import Sequence

from ..ports import Sensitivity

#: Presidio entity types that warrant ``SENSIBLE`` (health / financial / national-id — the hard floor,
#: mirroring the deterministic ``SENSIBLE`` rules in classifier.py: IBAN, card, NIR, health). Best-guess
#: Presidio ``entity_type`` names, confirmed at ignition (IGNITION NOTE on :func:`connect_presidio_sensor`).
_SENSIBLE_ENTITIES: frozenset[str] = frozenset(
    {
        "IBAN_CODE",
        "CREDIT_CARD",
        "CRYPTO",
        "MEDICAL_LICENSE",
        "US_SSN",
        "US_BANK_NUMBER",
        "FR_NIR",  # French social-security number (custom recognizer, if wired at ignition)
        "HEALTH",  # health context (custom recognizer, if wired at ignition)
    }
)

#: Presidio entity types that warrant ``PERSO`` (personal-but-not-critical: contact / identity — mirroring
#: the deterministic ``PERSO`` rules: email, phone). Any OTHER recognised entity also floors to ``PERSO``
#: (fail-safe: a recognised person/location is at least personal), so this set is the LOWER bound, not a
#: closed list. Best-guess names, confirmed at ignition.
_PERSO_ENTITIES: frozenset[str] = frozenset(
    {
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "PERSON",
        "LOCATION",
        "IP_ADDRESS",
        "DATE_TIME",
        "NRP",
        "URL",
    }
)


def _sensitivity_for_entities(entity_types: Sequence[str]) -> Sensitivity | None:
    """Map Presidio entity types to a RAISE-only sensitivity (pure, brick-free, UNIT-TESTED).

    Returns the MAX sensitivity the found entities warrant, or ``None`` to ABSTAIN when Presidio found
    NOTHING. Never returns ``PUBLIC`` — abstention is ``None``, not a low verdict — so the sensor can
    only ever RAISE the classifier's ``max`` (invariant 18 / D100). A health / financial / national-id
    entity (:data:`_SENSIBLE_ENTITIES`) floors to ``SENSIBLE``; ANY other recognised entity floors to at
    least ``PERSO`` (fail-safe — a recognised entity is personal at minimum, even if unlisted). Empty ⇒
    ``None`` (abstain). The exact Presidio entity-type names are confirmed at ignition (IGNITION NOTE on
    :func:`connect_presidio_sensor`); this is the deterministic mapping OUR code owns, not the brick's."""
    if not entity_types:
        return None
    verdict: Sensitivity | None = None
    for entity in entity_types:
        if entity in _SENSIBLE_ENTITIES:
            level = Sensitivity.SENSIBLE
        else:
            # any recognised entity is at least PERSO (fail-safe — over-flag, never launder, D100).
            level = Sensitivity.PERSO
        verdict = level if verdict is None else max(verdict, level)
    return verdict


def connect_presidio_sensor(  # pragma: no cover - needs the brick + models (③ ignition)
    *, analyzer: object | None = None
) -> "_PresidioSensor":
    """Wire Presidio's analyzer as a raise-only :class:`SemanticSensor` (the ``[OPERATOR]`` seam, D101).

    Imports ``presidio_analyzer`` LAZILY so this module is import-safe without it (D126); injected into
    :class:`~mnemosyne.ingest.classifier.DeterministicClassifier` as its ``semantic`` pass at ③-6b, where
    its verdict enters ONLY through the ``max`` (invariant 18). Pass ``analyzer`` in tests / at ignition
    to inject a resolved analyzer and keep the entity→sensitivity mapping exercised without the brick.

    IGNITION NOTE (best-guess API, confronted to the real ``presidio_analyzer`` at the smoke ``[OPERATOR]``):
    ``from presidio_analyzer import AnalyzerEngine`` → ``analyzer = AnalyzerEngine()`` (loads a spaCy NLP
    model, a heavy first-run download) → ``results = analyzer.analyze(text=content, language="en")``
    yields a list of ``RecognizerResult`` each with ``.entity_type`` (e.g. ``"CREDIT_CARD"``,
    ``"EMAIL_ADDRESS"``), ``.score``, ``.start``, ``.end``. Confirm at ignition: (1) the import +
    constructor and the spaCy model prerequisite (an ``[OPERATOR]`` install step); (2) the ``analyze``
    signature (``text=`` + ``language=``, and whether a ``score_threshold`` should be passed to drop
    low-confidence hits — a false positive only RAISES prudence, so a LOW threshold is fail-safe here);
    (3) the exact ``entity_type`` names so :data:`_SENSIBLE_ENTITIES` / :data:`_PERSO_ENTITIES` map them
    correctly (especially French NIR / health, which need CUSTOM recognizers wired at ignition — until
    then those fall through to the deterministic regex floor, which already covers them, D101). Its
    opinion can only raise the verdict — the classifier feeds it through ``max``."""
    if analyzer is None:
        from presidio_analyzer import AnalyzerEngine  # lazy, sole importer (D103 / invariant 20)

        analyzer = AnalyzerEngine()
    return _PresidioSensor(analyzer)


def connect_presidio_redactor(  # pragma: no cover - needs the brick + models (③ ignition)
    *, analyzer: object | None = None, anonymizer: object | None = None
) -> "_PresidioRedactor":
    """Wire Presidio's anonymizer as a masking :class:`Redactor` (the ``[OPERATOR]`` seam, D101 / D66).

    Imports ``presidio_analyzer`` + ``presidio_anonymizer`` LAZILY so this module is import-safe without
    them (D126); injected into the :class:`~mnemosyne.runtime.render.GovernedRenderer` at ③-6b, which
    RE-CLASSIFIES the redacted output (a redactor that under-cleans cannot lower the verdict, D100). Pass
    ``analyzer`` / ``anonymizer`` in tests / at ignition to inject resolved engines and keep the
    translation exercised without the bricks.

    IGNITION NOTE (best-guess API, confronted to the real Presidio at the smoke ``[OPERATOR]``):
    ``from presidio_anonymizer import AnonymizerEngine`` + an ``AnalyzerEngine`` (redaction is
    analyze-then-anonymize): ``results = analyzer.analyze(text=content, language="en")`` then
    ``AnonymizerEngine().anonymize(text=content, analyzer_results=results).text`` returns the masked
    string (default operator replaces each span with ``<ENTITY_TYPE>``). Confirm at ignition: (1) both
    imports + constructors and the shared spaCy model prerequisite; (2) that ``anonymize`` takes
    ``analyzer_results=`` and exposes the masked string on ``.text``; (3) the default masking operator
    (a placeholder vs a hash) — a placeholder is fine because the seam RE-FLOORS the output anyway
    (D100). The redactor only masks; its word is NOT the barrier."""
    if analyzer is None:
        from presidio_analyzer import AnalyzerEngine  # lazy, sole importer (D103 / invariant 20)

        analyzer = AnalyzerEngine()
    if anonymizer is None:
        from presidio_anonymizer import (
            AnonymizerEngine,
        )  # lazy, sole importer (D103 / invariant 20)

        anonymizer = AnonymizerEngine()
    return _PresidioRedactor(analyzer, anonymizer)


class _PresidioSensor:
    """Raise-only :class:`SemanticSensor` over Presidio's analyzer (D101 signal 3 / invariant 18).

    Holds the injected analyzer (so this class never imports at module scope — the factory does the sole
    lazy import). :meth:`assess` runs the analyzer LOCAL on untrusted content (zero-trust, D100-3 / D81),
    collects the found entity types, and maps them to a sensitivity via the pure
    :func:`_sensitivity_for_entities` — returning ``None`` to ABSTAIN when nothing is found. It can only
    RAISE the classifier's ``max`` (never returns ``PUBLIC``); a compromised analyzer over-flags at
    worst, never launders (D100). The analyzer CALL is ``pragma: no cover`` (needs the brick); the
    entity→sensitivity decision is the pure helper, which IS unit-tested."""

    __slots__ = ("_analyzer",)

    def __init__(self, analyzer: object) -> None:
        self._analyzer = analyzer

    def assess(self, content: str) -> Sensitivity | None:
        """Return the sensitivity Presidio's findings warrant, or ``None`` to abstain (raise-only, D100).

        Runs the analyzer, extracts the found entity types, and maps them by
        :func:`_sensitivity_for_entities`. Never lowers a label — ``None`` means abstain (the classifier
        keeps its floor / domain verdict), a level means RAISE (through the ``max``, invariant 18). Runs
        LOCAL on content treated as untrusted data (D100-3)."""
        entity_types = self._entity_types(content)
        return _sensitivity_for_entities(entity_types)

    def _entity_types(
        self, content: str
    ) -> list[str]:  # pragma: no cover - real analyzer (③ ignition)
        """Run Presidio's analyzer and return the found entity types (best-guess, confirmed at ignition).

        Calls ``analyzer.analyze(text=content, language="en")`` and reads ``.entity_type`` off each
        ``RecognizerResult`` (IGNITION NOTE on :func:`connect_presidio_sensor`). Any exception is left to
        propagate: the classifier's ``_assess`` wraps the sensor fail-safe (a failed pass ⇒ ``sensible``,
        never a silent low label, D100) — so raising here is the correct, fail-safe behaviour."""
        results = self._analyzer.analyze(text=content, language="en")
        return [str(getattr(r, "entity_type", "")) for r in results]


class _PresidioRedactor:
    """Masking :class:`Redactor` over Presidio's analyzer + anonymizer (③-6b / D66).

    Holds the injected analyzer + anonymizer (so this class never imports at module scope — the factory
    does the sole lazy imports). :meth:`redact` analyzes the content, masks the found spans, and returns
    the masked string. It makes NO safety claim about its output: the
    :class:`~mnemosyne.runtime.render.GovernedRenderer` re-classifies the result and emits it as public
    only if the deterministic floor agrees (D100 — a redactor that under-cleans cannot lower the
    verdict). The whole class touches the bricks, so it is ``pragma: no cover`` (exercised at ignition);
    nothing here decides governance."""

    __slots__ = ("_analyzer", "_anonymizer")

    def __init__(
        self, analyzer: object, anonymizer: object
    ) -> None:  # pragma: no cover - holds bricks
        self._analyzer = analyzer
        self._anonymizer = anonymizer

    def redact(
        self, content: str
    ) -> str:  # pragma: no cover - real analyzer + anonymizer (③ ignition)
        """Return a copy of ``content`` with PII spans masked (Presidio analyze-then-anonymize).

        Best-guess (IGNITION NOTE on :func:`connect_presidio_redactor`): analyze, then
        ``anonymizer.anonymize(text=content, analyzer_results=results).text``. The masked string is NOT
        trusted clean — the seam RE-FLOORS it (D100); this only accelerates the masking. A failure
        propagates to the seam, which handles it (never a silently-unredacted string returned)."""
        results = self._analyzer.analyze(text=content, language="en")
        anonymized = self._anonymizer.anonymize(text=content, analyzer_results=results)
        return str(getattr(anonymized, "text", content))
