"""BackendRegistry (D7 / D98) — make a routed model-id TAKE EFFECT, one big model at a time.

:class:`~mnemosyne.runtime.model_router.ModelRouter` NAMES the model a task class should run on
(D7); until now that name only rode the request as ``target`` for provenance — a single backend
actually decoded. This registry is the just-in-time seam (D98) the router's docstring promised: it
maps the routed model-id to the :class:`~mnemosyne.runtime.runner.GenerationBackend` that serves
it, so the router's choice finally SWITCHES the decoder — "with zero change to the router or its
callers" (:class:`~mnemosyne.runtime.runner.LocalRunner` reads ``grant.request.target`` and asks
this registry; ``models.py`` and the router are untouched).

**Lazy (D98).** A backend materialises on the FIRST call routed to it, never at wiring: a
weightless config entry per model, loaded only when a task class is actually mapped to it. Adding a
model is therefore a CONFIG change (a factory), never a code change (D7 / D26).

**Mono-resident (D95, one big model at a time — the 32 GB budget).** At most ONE registry backend
is resident: loading a different model EVICTS the currently-resident one FIRST (its reference is
dropped before the new load, so its weights are freed before the next allocation, never two big
models fighting for RAM). A call routed to the already-resident model reuses it (no reload). The
runner's OWN default backend is separate and always available (used for the unmapped / default
route) — this registry manages only the NON-default bench models the router can name.

Factories are injectable, so the suite drives every path with weightless stubs (D126, brick-free)
while the real wiring passes :func:`~mnemosyne.runtime.runner_mlx.load_mlx_backend` closures. Code &
docstrings English (D117).

Decisions: D7 (router by task class) · D98 (just-in-time backend swap) · D95 / invariant 26
(one big model at a time) · D26 (adding a model is config) · D126 (brick-free double).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .runner import GenerationBackend


class BackendRegistry:
    """Resolve a routed model-id to its decode backend — lazy, mono-resident (D7 / D98 / D95).

    Constructed with a ``{model_id: factory}`` map (each factory a zero-arg loader returning a
    :class:`~mnemosyne.runtime.runner.GenerationBackend`). :meth:`resolve` returns the backend for a
    mapped id (loading it on first use, evicting any other resident model first) or ``None`` for an
    unmapped / absent id, so the caller falls back to its default. Stateless over its factories; the
    only mutable state is the single resident slot. An optional ``on_evict`` hook is called with the
    evicted model-id (test / observability), never for correctness.

    **Single-threaded per instance.** The one resident slot is mutated without a lock, so two
    concurrent :meth:`resolve` of DIFFERENT ids could both evict-then-load and leave two big models
    resident (violating D95). Safe by construction today: each process owns its registry and the
    heavy-run lock is cross-PROCESS (D95), so model calls are sequential within a process — a future
    intra-process concurrent caller would add a lock around :meth:`resolve`."""

    __slots__ = ("_factories", "_on_evict", "_resident_id", "_resident")

    def __init__(
        self,
        factories: dict[str, Callable[[], GenerationBackend]],
        *,
        on_evict: Callable[[str], None] | None = None,
    ) -> None:
        # copy so a caller cannot mutate the mapping under us after construction (SE4-adjacent)
        self._factories = dict(factories)
        self._on_evict = on_evict
        self._resident_id: str | None = None
        self._resident: GenerationBackend | None = None

    def knows(self, model_id: str | None) -> bool:
        """Whether ``model_id`` is a mapped bench model (a pure lookup — never loads anything)."""
        return model_id is not None and model_id in self._factories

    def resolve(self, model_id: str | None) -> GenerationBackend | None:
        """The backend for ``model_id``, loaded on first use — or ``None`` when unmapped / ``None``.

        ``None`` or an id with no factory ⇒ ``None`` (the caller uses its default backend — the
        router's capable default, D70). A mapped id already resident ⇒ that backend (no reload). A
        DIFFERENT mapped id ⇒ evict the resident one FIRST (drop its reference so its weights free
        before the next load — one big model at a time, D95), then lazily load and cache the new one.
        Loading is the factory's concern; any failure propagates (fail-closed, never a silent wrong
        backend)."""
        if model_id is None or model_id not in self._factories:
            return None
        if self._resident_id == model_id and self._resident is not None:
            return self._resident  # already the resident model — reuse, no reload (D95)
        self._evict()  # free the previous big model BEFORE allocating the next (D95)
        backend = self._factories[
            model_id
        ]()  # lazy load — the one place a model materialises (D98)
        self._resident_id, self._resident = model_id, backend
        return backend

    def _evict(self) -> None:
        """Drop the currently-resident backend so its weights free before the next load (D95).

        Reference-drop only — the backend has no explicit close in the ``GenerationBackend`` seam;
        releasing the last reference lets the model's buffers be reclaimed (MLX / GC) before the next
        allocation. The optional ``on_evict`` hook fires with the evicted id for observability."""
        if self._resident_id is None:
            return
        evicted = self._resident_id
        self._resident_id, self._resident = None, None
        if self._on_evict is not None:
            self._on_evict(evicted)

    @property
    def resident_id(self) -> str | None:
        """The model-id currently held resident, or ``None`` — read-only (introspection / trace)."""
        return self._resident_id
