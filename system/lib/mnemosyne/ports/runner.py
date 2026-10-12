"""Runner (D104) - local model execution, behind the Guard, grammar-constrained.

How Mnémosyne runs its models locally. The strategy is fixed (D88: an OSS
OpenAI-compatible server, BEHIND the Guard D89, engine not married). The runner
sits behind the Guard's provider aiguilleur and only ever runs a model the Guard
authorized and routed (a :class:`~mnemosyne.ports.guard.Grant` is required).

Two structural rules (D104 / D100, invariant 27):

* **Grammar-constrained output is STANDARD, not an option** - decoding is
  constrained by a grammar / schema so the output CANNOT be malformed: a
  *structural incapacity* to emit an invalid tool call or JSON (a D100 code
  barrier, not a trusted model). See :meth:`Runner.complete_structured`.
* **Tool-calling is a hard gate** - a structured / tool-calling completion
  REQUIRES a :class:`GrammarConstraint`; reliability of tool-calling is an
  eliminatory bench criterion (D104 / D69), never bought back by raw speed.

The engine is chosen **per model** in config (compatible -> MLX for speed,
otherwise -> llama.cpp); both sit behind this one seam (the Guard is the
OpenAI-compatible aiguilleur), so a swap costs nothing architecturally. Default
OSS brick: **MLX / mlx-lm**, repli **llama.cpp** - see
``system/config/oss_registry.md`` (D104). Load/unload policy to juggle a configured capacity
(one big model at a time, D95) is wired at LOT 5.

Decisions: D104 (runner)  -  D88 (strategy)  -  D89 (behind the Guard)  -  D100
(structural safety)  -  D95 (one big model at a time). Invariant carried: 27
(substrate of 5, 16).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .core import Envelope
from .guard import Grant


@dataclass(frozen=True, slots=True)
class GrammarConstraint:
    """A grammar / schema the decoder MUST obey (D104 / invariant 27).

    ``schema`` is a JSON-schema or GBNF grammar (default bricks: Outlines /
    XGrammar). Passing one makes malformed output *structurally impossible* -
    the barrier is in the decoder, not in trusting the model (D100-1).

    ``repair`` is an OPTIONAL deterministic recovery for a *near-miss* candidate
    (e.g. an unterminated JSON string). When set, :func:`enforce_grammar` applies
    it to a candidate that fails to PARSE, then RE-VALIDATES the result against the
    same grammar - so a repair can never smuggle a non-conforming output past the
    barrier: the guarantee "valid under the schema, or raise" is untouched (a
    repaired-but-still-nonconforming candidate still raises); repair only turns a
    near-miss from *refused* into *recovered-then-revalidated*. OPT-IN by design -
    only a caller whose downstream carries its own floor supplies one. The
    distillateur does (its verbatim floor, [[restructure-not-reformulate]], drops
    any passage a repair could mangle); a classifier does not (no floor -> it keeps
    the strict fail-closed refusal by leaving ``repair`` None).
    """

    schema: str
    kind: str = "json_schema"  # or "gbnf"
    repair: Callable[[str], str] | None = None


@runtime_checkable
class Runner(Protocol):
    """Runs local models behind the Guard; structured output is a built-in (D104)."""

    def complete(
        self,
        prompt: Envelope[str],
        *,
        grant: Grant,
        constraint: GrammarConstraint | None = None,
    ) -> Envelope[str]:
        """Free-form local completion. ``grant`` proves the Guard authorized and
        routed this call (D89); ``constraint`` may still be supplied to bound the
        output. The result envelope's label is at least as restrictive as the
        prompt's (invariant 17)."""
        ...

    def complete_structured(
        self,
        prompt: Envelope[str],
        *,
        grant: Grant,
        constraint: GrammarConstraint,
    ) -> Envelope[str]:
        """Structured / tool-calling completion. The ``constraint`` is REQUIRED
        (the hard gate of invariant 27): the decoder is grammar-bound so the
        output cannot be a malformed tool call or JSON."""
        ...
