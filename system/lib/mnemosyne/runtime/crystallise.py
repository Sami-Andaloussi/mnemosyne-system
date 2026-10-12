"""Crystallisation gate (D75, invariant 11) - LLM->code only, producer≠verifier + equivalence.

A workflow that became STABLE and purely DETERMINISTIC may be "crystallised" - its LLM
call replaced by CODE (D75). Judgement is NEVER crystallised. The switch is not "it seems
to work": it is a GATE that refuses unless BOTH structural conditions hold, so a
crystallised path can never silently replace a model on trust (D100):

* **Producer ≠ verifier (D75 / D100-6).** The code is written by one agent and proven by a
  DISTINCT one; a switch where the two are the same identity is refused.
* **Equivalence on a FROZEN golden set (D75 barrier 1 + the shadow switch).** The candidate
  is shadow-run against a golden set FROZEN from replay snapshots (D76-(1), the LLM's own
  input->output history), and only crosses over when the equivalence threshold is met
  (strict equality for structured output). Below threshold => refused.

The golden set is immutable (frozen) so the builder cannot edit it to pass - it lives in
the protected zone (SE4) in production (pyramid étage (2), filled with real data at (3)). Code
touching the Guard / security / a ``sensible`` bubble additionally needs a human gesture
(D75 / D74 grid); an internal, reversible path may switch automatically once the gate
clears, with a rollback net (D75). This is the shadow-runner + equivalence harness the #9
mechanics deferred (D75); the per-workflow scored golden DATA is contenu, not contenant
(D98). Code & docstrings English (D117).

Decisions: D75 (crystallisation, 3 barriers, shadow switch)  -  D100-6 (producer ≠ verifier)
 -  D76-(1) (frozen golden set from snapshots)  -  D74 (human grid for privileged code). Invariant
carried: 11.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..ports import ErrorCode, EscalateToHuman, MnemosyneError
from .snapshots import ReplayId, SnapshotStore


class CrystallisationRefused(MnemosyneError):
    """The gate refused to switch an LLM call to code (fail-closed until proven, D75).

    Fail-closed like a Guard denial (``DENIED``): with producer == verifier, or with
    equivalence below threshold on the frozen golden set, the served source stays the LLM -
    the safe default (D75 / D100)."""

    code = ErrorCode.DENIED


@dataclass(frozen=True, slots=True)
class GoldenCase:
    """One frozen ``input -> expected`` case, taken from a replay snapshot (D75 / D76-(1))."""

    input: str
    expected: str


@dataclass(frozen=True, slots=True)
class GoldenSet:
    """An IMMUTABLE set of cases the candidate must reproduce (D75 barrier 1).

    Frozen so no one can edit it to pass (protected zone, SE4). Build it from the LLM's own
    replay snapshots - the equivalence is measured against what the model actually did."""

    cases: tuple[GoldenCase, ...]

    @classmethod
    def from_snapshots(cls, store: SnapshotStore, ids: tuple[ReplayId, ...]) -> GoldenSet:
        """Freeze a golden set from recorded model calls (D76-(1) -> D75).

        Each snapshot's frozen input/output becomes one case, so the golden set is exactly
        the model's history - never fabricated data (D98)."""
        cases = tuple(
            GoldenCase(input=store.get(rid).prompt.payload, expected=store.get(rid).output.payload)
            for rid in ids
        )
        return cls(cases=cases)

    def __len__(self) -> int:
        return len(self.cases)


class ShadowRunner:
    """Runs a candidate code path IN PARALLEL with the served LLM and scores equivalence.

    The LLM stays the served source (D75); the code runs shadow and is compared on the
    frozen golden set. Equivalence is strict equality here (the criterion for structured
    output, D75); a softer metric per output nature plugs in at (3)."""

    __slots__ = ()

    def equivalence(self, code: Callable[[str], str], golden: GoldenSet) -> float:
        """Fraction of golden cases the code reproduces EXACTLY (strict equivalence, D75).

        An empty golden set scores 0.0 - nothing is proven, so the gate below refuses (no
        switch without evidence)."""
        if len(golden) == 0:
            return 0.0
        matches = sum(1 for case in golden.cases if _safe_call(code, case.input) == case.expected)
        return matches / len(golden)


@dataclass(frozen=True, slots=True)
class CrystallisedPath:
    """A code path that PASSED the gate and may serve in place of the LLM (D75).

    Records the evidence - the distinct producer/verifier and the equivalence crossed on the
    frozen golden set - so the promotion is auditable and the LLM stays a rollback net."""

    code: Callable[[str], str]
    producer: str
    verifier: str
    golden_size: int
    equivalence: float

    def run(self, value: str) -> str:
        """Serve the crystallised code (the switched path)."""
        return self.code(value)


class Crystalliser:
    """The crystallisation gate: LLM->code only when producer≠verifier AND equivalence holds.

    A refusal keeps the LLM as the served source (fail-closed, D75). Privileged code (Guard
    / security / ``sensible``) additionally escalates to a human (D74)."""

    __slots__ = ("_shadow",)

    def __init__(self, shadow: ShadowRunner | None = None) -> None:
        self._shadow = shadow if shadow is not None else ShadowRunner()

    def crystallise(
        self,
        code: Callable[[str], str],
        *,
        producer: str,
        verifier: str,
        golden: GoldenSet,
        threshold: float = 1.0,
        touches_privileged: bool = False,
    ) -> CrystallisedPath:
        """Switch an LLM call to ``code`` - or refuse fail-closed (invariant 11).

        Refuses unless (a) ``producer`` differs from ``verifier`` (D75 / D100-6) AND (b) the
        shadow equivalence on the FROZEN ``golden`` set reaches ``threshold`` (D75). Code
        touching the Guard / security / ``sensible`` needs a human gesture regardless (D74):
        it escalates rather than auto-switching."""
        if producer == verifier:
            raise CrystallisationRefused(
                f"producer must differ from verifier, both {producer!r} (D75 / D100-6)"
            )
        # fail-closed on a nonsensical gate: a threshold that is NaN, zero or out of ``]0, 1]``
        # would let unproven code through (``score < nan`` / ``score < 0`` is False) - refuse it.
        if not 0.0 < threshold <= 1.0:
            raise CrystallisationRefused(
                f"equivalence threshold {threshold!r} must be in ]0.0, 1.0] - a gate that "
                "proves nothing is refused (D75 / D100 fail-closed)"
            )
        if len(golden) == 0:
            raise CrystallisationRefused(
                "cannot crystallise against an EMPTY golden set - nothing is proven (D75)"
            )
        score = self._shadow.equivalence(code, golden)
        if score < threshold:
            raise CrystallisationRefused(
                f"equivalence {score:.3f} below threshold {threshold:.3f} on the frozen "
                f"golden set of {len(golden)} case(s) - the LLM stays the served source (D75)"
            )
        if touches_privileged:
            raise EscalateToHuman(
                "crystallising privileged code (Guard / security / sensible) is a human "
                "gesture (D75 / D74) - no automatic switch"
            )
        return CrystallisedPath(
            code=code,
            producer=producer,
            verifier=verifier,
            golden_size=len(golden),
            equivalence=score,
        )


def _safe_call(code: Callable[[str], str], value: str) -> str | None:
    """Run a shadow candidate; a raised exception is a non-match, never a crash (D75)."""
    try:
        return code(value)
    except Exception:  # noqa: BLE001 - a shadow failure is simply not equivalent
        return None
