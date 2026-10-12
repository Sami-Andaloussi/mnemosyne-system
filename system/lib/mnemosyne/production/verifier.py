"""Producer ≠ verifier - the shared no-self-validation gate (D75 / D100-6).

One named home for the rule that recurs across the output tissu: a thing is never validated
by the same identity that produced it. Crystallisation (LOT 5) states it inline; skill
activation, production promotion and canal-B expurgation all reuse *this* helper so the gate
reads identically wherever a distinct verifier is required (D100-6). Code & docstrings
English (D117).

Decisions: D75 (producer ≠ verifier at build)  -  D73-8 (never self-validate at runtime)  -
D100-6 (structural, not trust).
"""

from __future__ import annotations


def require_distinct[E: Exception](
    producer: str, verifier: str, error: type[E], *, what: str
) -> None:
    """Raise ``error`` unless ``producer`` and ``verifier`` are two distinct identities (D100-6).

    Fail-closed and hardened against a spoofed "distinct": both must be real, non-empty
    strings (a non-``str`` or blank identity is refused, so an object with a custom ``__eq__``
    cannot masquerade as distinct), and they are compared stripped so trailing whitespace is
    not a loophole. Each site keeps its own normalized code (``DENIED``) while sharing the rule."""
    if not isinstance(producer, str) or not isinstance(verifier, str):
        raise error(f"{what}: producer / verifier must be string identities (D75 / D100-6)")
    p, v = producer.strip(), verifier.strip()
    if not p or not v:
        raise error(f"{what}: producer / verifier must be non-empty identities (D75 / D100-6)")
    if p == v:
        raise error(
            f"{what}: producer and verifier must be distinct identities, both "
            f"{p!r} (producer ≠ verifier, D75 / D100-6)"
        )
