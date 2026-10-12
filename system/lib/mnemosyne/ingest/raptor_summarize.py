"""RAPTOR summarizer seam (Ch.5 / D89 / D104) - abstractive synopsis, inert until a model answers.

:mod:`~mnemosyne.runtime.runner`'s stub decoder ECHOES a free-form prompt verbatim, so a
stub-backed summarizer would emit prompt junk as a "synopsis" - unlike the classifier's semantic
pass or the fact extractor (:mod:`~mnemosyne.runtime.models`), whose STRUCTURED completions parse
to an honest abstention against the stub. Therefore this seam is a swapped PAIR, not a single class
whose behaviour happens to degrade gracefully:

* :class:`NullRaptorSummarizer` - the abstaining default (D126): ALWAYS returns ``None``, so a
  brick-free build creates ZERO summary nodes and the suite stays green with no model installed.
* :class:`RunnerRaptorSummarizer` - the real prise, mirroring
  :class:`~mnemosyne.production.refiners.RunnerGenerator`: mints a fresh ``MODEL_CALL`` grant per
  cluster through an injected :data:`GrantSource` (never self-granted, D100), then asks the
  governed :class:`~mnemosyne.ports.runner.Runner` for a FREE-FORM synopsis. Wired by
  ``real_runtime`` the same way the OTHER real model seams are (behind the Guard, D89).

Unlike ``RunnerGenerator`` (whose role/label is fixed for one ``produce()`` call), a RAPTOR
summarizer instance is built ONCE at bootstrap and reused across an entire corpus walk - many
clusters, each at its OWN ``(sensitivity, bubble, domain)`` - so :meth:`RaptorSummarizer.summarize`
takes ``label`` PER CALL rather than baking it into the constructor.

Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from typing import Protocol, runtime_checkable

from ..ports import Envelope, GovernanceLabel, Grant, Runner
from .chunk import chunk_text

#: The Guard grant lifecycle a summarizer needs: mints a fresh single-use ``MODEL_CALL`` grant for
#: ONE summarization call, given the cluster's label (D89 / D100 / M1) - never self-granted. The
#: identical shape as ``production.refiners.GrantSource`` / ``production.distillation.GrantSource``,
#: independently declared here too (same established precedent: this ``Callable`` is trivial enough
#: that a shared import is not worth it, and ``ingest`` must not depend on ``production``, D126
#: layering - ``ingest`` sits BELOW it).
GrantSource = Callable[[GovernanceLabel], Grant]

_SUMMARIZE_TEMPLATE = """\
Produce a faithful synopsis of the passages below. Return ONLY the synopsis text, nothing else.

PASSAGES:
{passages}
"""

#: The fence between passages inside ONE prompt (a boundary the model reads between members).
_JOIN = "\n\n---\n\n"

#: Fixed chars the template wraps around the joined passages - subtracted from the input ceiling to
#: get the budget available for passage CONTENT in a single call.
_TEMPLATE_OVERHEAD = len(_SUMMARIZE_TEMPLATE) - len("{passages}")

#: FALLBACK input ceiling for a hand-built / unit-test summarizer only. In production ``bootstrap``
#: passes the runner's OWN resolved ceiling (``runner.max_prompt_chars``), so the summarizer's per-call
#: budget derives from the EXACT number the runner enforces - never an independent constant that could
#: drift above the runner's bound (D136 / audit MINOR). NOT imported from :mod:`~mnemosyne.runtime.
#: runner` - ``ingest`` sits BELOW ``runtime`` in the layering (D126), same reason :data:`GrantSource`
#: is re-declared here; the value mirrors the runner's default so a brick-free build stays consistent.
_DEFAULT_MAX_PROMPT_CHARS = 48_000

#: A ceiling on reduce ROUNDS - a structural backstop against a non-converging summarizer (a model
#: that never compresses its input). Each round shrinks the cluster toward the single-prompt base
#: case; this bound leaves ample headroom, and reaching it ABSTAINS honestly (``None``) rather than looping
#: forever (D100, invariant 16).
_MAX_REDUCE_DEPTH = 12


def _joined_len(texts: Sequence[str]) -> int:
    """Chars a single-prompt join of ``texts`` would occupy - the content plus the fences between."""
    return sum(len(t) for t in texts) + len(_JOIN) * max(len(texts) - 1, 0)


def _group(texts: Sequence[str], *, budget: int) -> Iterator[list[str]]:
    """Pack ``texts`` into groups whose single-prompt join is ``<= budget`` (the map step's windows).

    Any single member longer than ``budget`` is first split on passage boundaries
    (:func:`~mnemosyne.ingest.chunk.chunk_text`, overlap-free) so no atom can itself exceed the
    budget - this is what GUARANTEES the map step makes progress (every group summarizes to one
    shorter partial, so the reduce converges) even for a pathological oversized member. Members are
    normally fit the configured budget, so the split is pure defense-in-depth (D100)."""
    atoms: list[str] = []
    for text in texts:
        if len(text) <= budget:
            atoms.append(text)
        else:  # a corrupted / oversized member - never in a real build, but must not overflow (D136)
            atoms.extend(p.text for p in chunk_text(text, target=budget, overlap=0))
    group: list[str] = []
    size = 0
    for atom in atoms:
        added = len(atom) + (len(_JOIN) if group else 0)
        if group and size + added > budget:
            yield group
            group, size = [atom], len(atom)
        else:
            group.append(atom)
            size += added
    if group:
        yield group


@runtime_checkable
class RaptorSummarizer(Protocol):
    """Produces (or honestly declines) an abstractive synopsis over one cluster's member texts."""

    def summarize(self, member_texts: Sequence[str], *, label: GovernanceLabel) -> str | None:
        """A faithful synopsis of ``member_texts``, or ``None`` to ABSTAIN (skip the node, F3).

        Abstaining is honest emptiness, never a crash: the caller
        (:func:`~mnemosyne.ingest.raptor_build.build_raptor_tree`) simply creates no node for this
        cluster this round - mirrors :class:`~mnemosyne.runtime.models.ModelSemanticSensor`
        abstaining against the stub decoder, and every other ``Null*`` stand-in's fail-safe posture."""
        ...


class NullRaptorSummarizer:
    """The abstaining default (D126) - ALWAYS returns ``None``, never fabricates a synopsis.

    Wired by :func:`~mnemosyne.runtime.bootstrap.bootstrap` so a brick-free build creates ZERO
    RAPTOR nodes: the suite stays green with no model installed, exactly like
    :class:`~mnemosyne.ingest.structural.NullStructuralExtractor` /
    :class:`~mnemosyne.ingest.caption.NullImageCaptioner`."""

    def summarize(self, member_texts: Sequence[str], *, label: GovernanceLabel) -> str | None:
        return None


class RunnerRaptorSummarizer:
    """A :class:`RaptorSummarizer` on a governed Runner (D89 / D104), mirroring
    :class:`~mnemosyne.production.refiners.RunnerGenerator`.

    Mints a fresh ``MODEL_CALL`` grant per call through the injected :data:`GrantSource` (never
    self-granted, D100), then asks the runner for a FREE-FORM completion - a synopsis is allowed to
    be abstractive (the verbatim floor, [[restructure-not-reformulate]], is NOT required here, unlike
    the distillateur). LOCAL for ``sensible`` content by construction: the Guard's own
    ``route_model`` decides the channel from ``label`` (invariant 1); this prise never talks to a
    backend directly.

    **Map-reduce - RAPTOR's essence, not a one-shot join.** A sufficiently large document can overflow
    the model's context window and the runner's fail-closed ``_MAX_PROMPT_CHARS`` bound (D136).
    This summarizer therefore builds a HIERARCHY: it packs the members into
    budget-sized groups (:func:`_group`), summarizes each into a partial synopsis (the *map*), then
    recursively summarizes those partials (the *reduce*) until the whole cluster fits ONE prompt - the
    base case, byte-for-byte the old single-call behaviour for a small book. Each call stays under the
    budget, so the runner bound is never tripped; a big book simply costs several LOCAL calls. This is
    exactly the tree-of-summaries RAPTOR is (:mod:`~mnemosyne.stores.raptor`), applied WITHIN one
    book's own passages as well as across a domain's book synopses."""

    __slots__ = ("_runner", "_grant_source", "_budget", "identity")

    def __init__(
        self,
        runner: Runner,
        grant_source: GrantSource,
        *,
        max_prompt_chars: int | None = None,
        identity: str = "raptor-summarizer",
    ) -> None:
        self._runner = runner
        self._grant_source = grant_source
        # The per-call content budget = the runner's own input ceiling minus this template's fixed
        # overhead (D136). bootstrap passes the SAME policy bound the runner gets, so a group packed
        # to `_budget` yields a prompt of `<= max_prompt_chars` - never over the runner's bound.
        ceiling = max_prompt_chars if max_prompt_chars is not None else _DEFAULT_MAX_PROMPT_CHARS
        if ceiling <= _TEMPLATE_OVERHEAD:
            raise ValueError(
                f"max_prompt_chars {ceiling} leaves no room for content past the "
                f"{_TEMPLATE_OVERHEAD}-char summarize template (D136)"
            )
        self._budget = ceiling - _TEMPLATE_OVERHEAD
        self.identity = identity

    def summarize(self, member_texts: Sequence[str], *, label: GovernanceLabel) -> str | None:
        """A faithful synopsis of ``member_texts`` via the guarded runner, MAP-REDUCED to fit.

        Abstains on an EMPTY cluster (nothing to summarize, honest emptiness) WITHOUT minting a grant
        or calling the model - never spends a call for nothing. A non-empty cluster is summarized
        hierarchically (see the class docstring): one call when it fits a single prompt, otherwise a
        map over budget-sized groups then a reduce over the partials. A Guard denial propagates, netted
        by the corpus pass (mirroring ``ingest_book``'s per-book isolation, D140); the only abstention
        this prise itself introduces past the empty-cluster gate is the fail-safe of a non-converging
        model (:data:`_MAX_REDUCE_DEPTH`) or every group coming back blank - both honest emptiness (F3)."""
        texts = [t for t in member_texts if t.strip()]
        if not texts:
            return None
        return self._reduce(texts, label=label, depth=0)

    def _reduce(self, texts: list[str], *, label: GovernanceLabel, depth: int) -> str | None:
        """Summarize ``texts`` to one synopsis, recursing until they fit a single prompt (the base)."""
        # Base case: the whole cluster fits ONE prompt - a single synopsis call (the small-book path,
        # byte-for-byte the pre-map-reduce behaviour). Every recursion bottoms out here.
        if _joined_len(texts) <= self._budget:
            return self._summarize_once(texts, label=label)
        if depth >= _MAX_REDUCE_DEPTH:
            return None  # pathological non-convergence - abstain, never loop (D100 / invariant 16)
        # Map: pack into budget-sized groups, summarize each into a partial synopsis.
        partials = [
            summary
            for group in _group(texts, budget=self._budget)
            if (summary := self._summarize_once(group, label=label)) and summary.strip()
        ]
        if not partials:
            return None  # every group abstained / came back blank - honest emptiness (F3)
        # Reduce: recurse on the partials - a HIERARCHICAL summary, converging toward the base case.
        return self._reduce(partials, label=label, depth=depth + 1)

    def _summarize_once(self, texts: Sequence[str], *, label: GovernanceLabel) -> str:
        """One guarded model call over ``texts`` joined into a single prompt.

        Mints a fresh single-use ``MODEL_CALL`` grant (never self-granted, D100). The caller
        guarantees ``_joined_len(texts) <= self._budget``, so the prompt never trips the runner's
        fail-closed ceiling (D136)."""
        prompt = _SUMMARIZE_TEMPLATE.format(passages=_JOIN.join(texts))
        grant = self._grant_source(label)
        completion = self._runner.complete(Envelope(payload=prompt, label=label), grant=grant)
        return completion.payload
