"""Tests for BackendRegistry (D7 / D98 / γ) - the routed model-id -> backend seam.

Locks `runtime/backend_registry.py`: a routed model NAMES a backend that materialises just-in-time
(LAZY, D98 - nothing loads at construction) and ONE big model at a time (mono-resident, D95 - a
different model evicts the previous FIRST). ``resolve(None)`` / an unmapped id => ``None`` (the caller
falls back to its default - the router's capable default, D70). Brick-free: weightless stub factories
stand in for the real ``load_mlx_backend`` closures (D126). Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable

from mnemosyne.runtime.backend_registry import BackendRegistry


class _StubBackend:
    """A weightless ``GenerationBackend`` double with a distinct id (structural - no import needed)."""

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def generate(self, prompt: str) -> str:
        return f"[{self._model_id}] {prompt}"

    def generate_structured(self, prompt: str, schema: str, kind: str) -> str:
        return "{}"


def _counting_factory(model_id: str, calls: list[str]) -> Callable[[], _StubBackend]:
    """A factory that RECORDS each load - so a test can prove laziness (loaded only on use) and
    eviction (an evicted model reloads on the next resolve)."""

    def factory() -> _StubBackend:
        calls.append(model_id)
        return _StubBackend(model_id)

    return factory


def test_resolve_none_or_unmapped_returns_none() -> None:
    # None (unrouted) or an id with no factory => None: the caller uses its own default backend
    # (the router's capable default, D70) - the registry never invents a wrong backend.
    reg = BackendRegistry({"a": lambda: _StubBackend("a")})
    assert reg.resolve(None) is None
    assert reg.resolve("unknown") is None
    assert reg.knows("a") is True
    assert reg.knows("unknown") is False
    assert reg.knows(None) is False


def test_resolve_is_lazy_then_cached() -> None:
    # LAZY (D98): nothing loads at construction; the backend materialises on the FIRST resolve, and
    # a second resolve of the resident model reuses it (no reload).
    calls: list[str] = []
    reg = BackendRegistry({"a": _counting_factory("a", calls)})
    assert calls == []  # construction loaded nothing
    first = reg.resolve("a")
    assert first is not None and first.model_id == "a" and calls == ["a"]
    again = reg.resolve("a")
    assert again is first and calls == ["a"]  # resident => reused, not reloaded
    assert reg.resident_id == "a"


def test_mono_resident_evicts_the_previous_model_before_loading_the_next() -> None:
    # D95, one big model at a time. A SINGLE event log - fed by BOTH the factory (a load) and on_evict
    # (an eviction) - pins the INTERLEAVING: the resident model is evicted BEFORE the next is loaded, so
    # two big models never sit in RAM at once. (Two separate lists, as a weaker test, could not catch a
    # load-before-evict inversion - the exact regression that would break the memory guarantee.)
    events: list[str] = []

    def _load_recording(model_id: str) -> Callable[[], _StubBackend]:
        def make() -> _StubBackend:
            events.append(f"load:{model_id}")
            return _StubBackend(model_id)

        return make

    reg = BackendRegistry(
        {"a": _load_recording("a"), "b": _load_recording("b")},
        on_evict=lambda mid: events.append(f"evict:{mid}"),
    )
    reg.resolve("a")  # nothing resident => just a load
    reg.resolve("b")  # evict a, THEN load b
    reg.resolve("a")  # a was evicted => evict b, THEN reload a
    assert events == ["load:a", "evict:a", "load:b", "evict:b", "load:a"]
    assert reg.resident_id == "a"


def test_factories_are_copied_so_a_later_mutation_cannot_widen_the_registry() -> None:
    # The registry copies its factory map at construction - a caller mutating the original afterwards
    # cannot smuggle in a model (the routable set is fixed at wiring, a config act, D26).
    src: dict[str, Callable[[], _StubBackend]] = {"a": lambda: _StubBackend("a")}
    reg = BackendRegistry(src)
    src["b"] = lambda: _StubBackend("b")
    assert reg.knows("b") is False
