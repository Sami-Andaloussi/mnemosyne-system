"""Skill I/O contract (D108) - the normed connector every skill exposes.

The standard plug by which skills (trieur, extracteur, compacteur, chercheur...)
fit together - normed connectors, no case-by-case wiring. This is the interface
gabarit of the skeleton ((2)). Its four mandatory volets, identical for all:

1. **Typed I/O** - a verifiable schema, so a malformed output is caught AT THE
   SOURCE, never propagated (same spirit as grammar / tool-calling, D104; a
   D100 barrier).
2. **Normalized errors** - never a silent crash; the orchestrator (D93) learns
   whether to retry, escalate, or FLAG. Carried by
   :class:`~mnemosyne.ports.core.ErrorCode`.
3. **Idempotent resumption** - an interrupted skill is restartable without
   breaking or duplicating (D105 / D44).
4. **Trace** - provenance and a trace handle (D19 / D76), observability from
   day one.

...plus volet (5), the reason this contract matters most: the **governance label
TRAVELS with the data** (D108-(5) / invariant 23). It is not a field of this
Protocol because it rides *inside* every :class:`~mnemosyne.ports.core.Envelope`
that crosses the boundary - the Guard (D89) reads it and enforces cloisonnement
(D54 / D72) and sensible-local (D27 / D66) at each hop. Security becomes a
barrier (the label travels, the Guard reads it, it blocks) instead of resting
on each skill's memory (discipline = fragile = anti-D100).

Decisions: D108 (the contract)  -  D77 (interface contracts between skills)  -
D105 / D44 (idempotent resume)  -  D19 / D76 (trace). Invariants carried: 23
(via the Envelope), substrate of 24, 27.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .core import Envelope, TraceId


@runtime_checkable
class Skill[I, O](Protocol):
    """A unit of work with a typed, governed, resumable, traced interface (D108).

    ``I`` and ``O`` are the skill-specific payload types; both travel inside an
    :class:`~mnemosyne.ports.core.Envelope`, so the governance label rides along
    (volet (5)). The norm is versioned and migrated together in git - a mono-
    deployed local system needs no runtime version negotiation (D108).
    """

    name: str
    version: str

    def run(
        self,
        request: Envelope[I],
        *,
        trace: TraceId,
        resume_key: str | None = None,
    ) -> Envelope[O]:
        """Run the skill on a governed input, returning a governed output.

        * Typed I/O (volet (1)): inputs/outputs conform to the skill schema; a
          malformed payload is rejected at the source, never propagated.
        * Normalized errors (volet (2)): failures raise a
          :class:`~mnemosyne.ports.core.MnemosyneError` carrying an
          :class:`~mnemosyne.ports.core.ErrorCode` - never a bare crash.
        * Idempotent resume (volet (3)): calling twice with the same
          ``resume_key`` after an interruption yields the same final state, with
          no duplication (D105 / D44).
        * Trace (volet (4)): ``trace`` threads this run through the observability
          layer (D19 / D111).

        The returned envelope's label is at least as restrictive as the input's
        (monotonic prudence, invariant 17): a skill may raise the label, never
        lower it.
        """
        ...
