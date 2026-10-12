"""Harness for the 27 executable invariants (LOT 2) - the hard line for this project's testing pyramid.

This project's internal constitution lists 27 invariants in its section 5. Its governing decision on
testing (tier (1) of the four-tier pyramid) demands each exist *as a test that fails the build when
the rule is violated* - "a written rule is a wish; only a barrier that says 'no' on its own is a
guardrail". This module is the scaffolding that turns those 27 lines into 27 tests, plus the other
three pyramid tiers (golden sets / 3-store integration / smoke), and guarantees the set stays
complete and traceable.

**Progressive red (the ratchet).** Most invariants guard behaviour of components
that land in later lots (the Guard in LOT 3, the stores in LOT 4b, the runner in
LOT 5...). Their tests cannot pass yet, so they are written in full and marked
``xfail(strict=True, raises=InvariantPending)``: each asserts everything already
enforceable against the LOT 1 contracts, then reaches :func:`pending`, which marks
the exact point where the not-yet-built barrier takes over. The day that lot lands
and the barrier becomes real, the test stops raising ``InvariantPending`` and
PASSES - turning the suite red (``XPASS`` under ``strict``) and *forcing* the
builder to drop the marker (set ``lot=None``). A regression in the already-live
part raises ``AssertionError`` (not ``InvariantPending``) and is reported as a
real failure. Invariants whose barrier is *already* fully realized by the LOT 1
value-types carry ``lot=None`` and must pass outright.

**pytest-optional (D116).** The toolchain (``pytest`` / ``uv``) is installed only
at setup; until then the registry, the decorators and :func:`raises` work on the
standard library alone, so the constitutional barriers are verifiable *before* the
toolchain exists - which is itself the point (a barrier that needs absent tooling
to be checked is still a wish). Under real pytest the ``xfail`` markers attach and
report normally; without it they are no-ops and the bodies run directly (verified
now by the pytest-free proof runner under ``scratchpad``).

Authority: this project's internal constitution crystallises the numbered list in its section 5;
its internal decision log is the source of truth behind it (neither is part of this public mirror).
Code and docstrings are English.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Never

try:  # the toolchain lands at install (D116); everything here works without it.
    import pytest
except ImportError:  # pragma: no cover - exercised by the pytest-free proof runner
    pytest = None  # type: ignore[assignment]


def _find_repo_root() -> Path:
    """Walk up from this file to the directory containing ``pyproject.toml``.

    ``tests/_invariants.py`` itself always stays at the repo's ``tests/`` root, so
    this resolves correctly regardless of caller depth. Tests nested one level
    deeper (``tests/<theme>/test_x.py``) import :data:`REPO_ROOT` from here instead
    of deriving their own ``Path(__file__).resolve().parent.parent`` - that motif
    only lands on the repo root for a file directly under ``tests/``; one level
    deeper it would resolve to ``tests/`` itself."""
    here = Path(__file__).resolve()
    for anc in (here, *here.parents):
        if (anc / "pyproject.toml").is_file():
            return anc
    raise RuntimeError("repo root (pyproject.toml) introuvable depuis tests/_invariants.py")


#: The repo root, resolved once. Shared by every test that needs a path relative
#: to the repo (fixtures under ``system/skills/``, governance artefacts, ...).
REPO_ROOT = _find_repo_root()


class InvariantPending(Exception):
    """Raised by :func:`pending` at the point an invariant needs a not-yet-built
    component. Invariant tests are ``xfail(strict, raises=InvariantPending)`` on
    exactly this exception, so they stay red until their lot lands and then force
    their own promotion (see the module docstring)."""


# --------------------------------------------------------------------------- #
# Registries - the 27 invariants (tier (1)) and the 3 other pyramid tiers        #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class InvariantSpec:
    """One registered invariant test, traceable back to this project's invariant registry (its
    internal constitution's section 5).

    The per-invariant decisions (D...) live authoritatively in §5, bound here by
    ``number`` (the traceability meta-test asserts the two never diverge), so we
    do not duplicate them on the spec."""

    number: int  # 1..27, the constitution's numbering
    title: str  # the invariant's one-line name
    lot: str | None  # the lot that makes it pass; None => already enforced (green)
    test_name: str  # the test function carrying it


@dataclass(frozen=True, slots=True)
class TierSpec:
    """One of the three non-invariant pyramid tiers (tiers (2)(3)(4))."""

    number: int  # 2, 3 or 4 (tier (1) is the 27 invariants themselves)
    name: str
    lot: str
    test_name: str


#: invariant number -> spec. Populated by the :func:`invariant` decorator.
REGISTRY: dict[int, InvariantSpec] = {}
#: pyramid tier (2|3|4) -> spec. Populated by :func:`pyramid_tier`.
PYRAMID: dict[int, TierSpec] = {}

#: The total number of executable invariants (this project's constitution, section 5). The suite asserts
#: the registry covers exactly ``1..N_INVARIANTS`` - no gap, no duplicate.
N_INVARIANTS = 27


def _mark_pending(fn: Callable[..., object], *, raises: type[BaseException], reason: str):
    """Attach ``xfail(strict, raises=...)`` if pytest is present; else a no-op."""
    if pytest is None:  # pragma: no cover - pytest-free path
        return fn
    return pytest.mark.xfail(raises=raises, strict=True, reason=reason)(fn)


def invariant(number: int, *, title: str, lot: str | None = None):
    """Register a test as the executable form of invariant ``number`` from this project's
    constitution, section 5.

    ``lot=None`` means the barrier is already realized by the LOT 1 value-types,
    so the test must pass now. A non-``None`` ``lot`` names the lot that realizes
    it; the test is marked ``xfail(strict, raises=InvariantPending)`` and must
    reach :func:`pending` (progressive red).
    """

    def deco(fn: Callable[..., object]) -> Callable[..., object]:
        if number in REGISTRY:
            raise ValueError(
                f"invariant {number} already registered by {REGISTRY[number].test_name!r}"
            )
        if not 1 <= number <= N_INVARIANTS:
            raise ValueError(f"invariant number {number} out of range 1..{N_INVARIANTS}")
        REGISTRY[number] = InvariantSpec(number, title, lot, fn.__name__)
        fn.__invariant__ = REGISTRY[number]  # type: ignore[attr-defined]
        if lot is not None:
            fn = _mark_pending(
                fn,
                raises=InvariantPending,
                reason=f"invariant {number} pending LOT {lot} (tier (1), progressive red)",
            )
        return fn

    return deco


def pyramid_tier(number: int, *, name: str, lot: str):
    """Register a test as one of the non-invariant tiers (tiers (2)(3)(4)).

    These are frames, not data: they fix the *contract* of each tier and stay
    ``xfail`` pending the lot that fills them (no golden data is fabricated now -
    the container, not its contents)."""

    def deco(fn: Callable[..., object]) -> Callable[..., object]:
        if number in PYRAMID:
            raise ValueError(f"pyramid tier {number} already registered")
        PYRAMID[number] = TierSpec(number, name, lot, fn.__name__)
        fn.__tier__ = PYRAMID[number]  # type: ignore[attr-defined]
        return _mark_pending(
            fn,
            raises=InvariantPending,
            reason=f"pyramid tier {number} ({name}): filled in LOT {lot}",
        )

    return deco


def pending(component: str, *, lot: str) -> Never:
    """Mark the boundary where an invariant needs a component built in a later lot.

    Everything above the call is asserted against today's contracts and acts as a
    live barrier; this call keeps the test red until LOT ``lot`` supplies
    ``component``.

    **Promotion discipline (read before turning a test green).** When that lot
    lands, do NOT merely delete this call: a body that then passes on its
    already-green substrate assertions alone leaves the new barrier untested - a
    *hollow promotion*. Replace this call with the forward assertion that actually
    exercises ``component``, and let the lot's own isolated audit verify the
    promoted test binds.
    """
    raise InvariantPending(f"{component} - built in LOT {lot}")


# --------------------------------------------------------------------------- #
# Contract introspection - assert on a port's *shape* (its barrier surface)     #
# --------------------------------------------------------------------------- #
def members(enum_cls: type) -> set[str]:
    """The member names of an ``Enum`` (e.g. the verdicts a Decision can take)."""
    return {m.name for m in enum_cls}


def methods(proto: type) -> set[str]:
    """The public method/attribute names a port Protocol offers (no dunders).

    Used to assert a contract's *shape* - e.g. that a store offers ``invalidate``
    and no destructive verb (invariant 2), which is a build-failing barrier on the
    LOT 1 surface itself."""
    return {name for name in dir(proto) if not name.startswith("_")}


def fields(dc: type) -> set[str]:
    """The dataclass field names of a value type (e.g. an Envelope's slots)."""
    return set(getattr(dc, "__dataclass_fields__", {}))


@contextmanager
def raises(exc: type[BaseException]) -> Iterator[None]:
    """Minimal ``pytest.raises`` replacement (pytest-free, D116).

    Asserts the block raises ``exc``; re-raises any other exception as an
    ``AssertionError`` and fails if nothing is raised. Identical behaviour under
    real pytest, so the suite reads the same with or without the toolchain."""
    try:
        yield
    except exc:
        return
    except BaseException as other:  # noqa: BLE001 - normalise into a clear assertion
        raise AssertionError(
            f"expected {exc.__name__}, but got {type(other).__name__}: {other}"
        ) from other
    raise AssertionError(f"expected {exc.__name__}, but nothing was raised")


def direct_imports_of(
    root: Path, forbidden: set[str], *, exempt: frozenset[str] = frozenset()
) -> dict[str, set[str]]:
    """Map each module under ``root`` to the forbidden top-level packages it imports.

    A build-failing *encapsulation* barrier (invariant 20 / D103): a swap-able engine
    reached *outside its designated adapter* shows up here. The adapter - the ONE
    legitimate door that imports the real brick at (3) (D103) - is passed in ``exempt``
    (a ``root``-relative path), so wiring the brick into it does not self-trip the barrier
    while any OTHER module reaching the engine still fails the build. Parses each ``.py``
    with :mod:`ast` (no imports executed) and records any ``import``/``from`` whose
    top-level package is in ``forbidden``; empty => the seam holds."""
    hits: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*.py")):
        rel = str(path.relative_to(root))
        if rel in exempt:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {alias.name.split(".")[0] for alias in node.names} & forbidden
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in forbidden:
                    found.add(node.module.split(".")[0])
        if found:
            hits[rel] = found
    return hits
