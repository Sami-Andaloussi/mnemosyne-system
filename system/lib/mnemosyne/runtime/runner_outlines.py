"""_OutlinesBackend - the SOLE importer of Outlines (D104 / D103 / invariant 20).

Grammar-constrained decoding is STANDARD in the Runner (D104 / invariant 27): a structured completion
is decoded UNDER a grammar so the model CANNOT emit a token that breaks it - a *structural incapacity*,
not a post-filter (D100). This backend realizes that constrained decode with **Outlines** (dottxt-ai,
Apache-2.0; ``oss_registry.md``), by WRAPPING an underlying :class:`~mnemosyne.runtime.runner.GenerationBackend`
(the real MLX model): ``generate`` delegates free-form to the wrapped model; ``generate_structured``
routes through Outlines' schema-constrained generation. It wraps ``outlines`` behind the SAME primitive
seam :class:`~mnemosyne.runtime.runner.LocalRunner` decodes through, so the suite stays green with the
brick NOT installed (D126). Everything that touches Outlines is ``# pragma: no cover``: it needs the
installed brick + a model, absent in CI, so it is exercised only at (3) ignition, where the 1-click smoke
confronts this colle with the real API.

**The grammar barrier is NOT delegated (D100 - capital).** Outlines makes malformed output *unlikely at
the source*, but :class:`LocalRunner` STILL re-checks every structured candidate with
:func:`~mnemosyne.runtime.runner.enforce_grammar` (invariant 27) - the code barrier never trusts the
decoder, so a non-conforming candidate is refused fail-closed, never emitted. This backend is the belt;
``enforce_grammar`` is the braces (D104 / D100-1). The exact Outlines API is confirmed at install; a
drift degrades to a refused structured decode (the runner re-check bites), never a malformed emission.

Decisions: D104 (grammar-constrained decode, standard)  -  D100 / D100-1 (structural incapacity, code
barrier not delegated)  -  D103 (sole importer)  -  D126 (brick-free suite, injected). Code & docstrings
English (D117).
"""

from __future__ import annotations

from .runner import GenerationBackend


def connect_outlines(  # pragma: no cover - needs the brick + a model ((3) ignition)
    model_backend: GenerationBackend,
) -> "_OutlinesBackend":
    """Wrap a model backend so structured decode goes through Outlines (the ``[OPERATOR]`` allumage seam, D104).

    ``model_backend`` is the underlying :class:`~mnemosyne.runtime.runner.GenerationBackend` (the real
    MLX model, :func:`~mnemosyne.runtime.runner_mlx.load_mlx_backend`). Free-form ``generate`` delegates
    to it unchanged; ``generate_structured`` binds decoding to the schema via Outlines. Imports
    ``outlines`` LAZILY so this module is import-safe without it (D126); wired by
    :func:`~mnemosyne.runtime.bootstrap.real_runtime` around the model backend. As with every
    ``pragma: no cover`` adapter, the 1-click smoke confronts this colle with the real Outlines at
    ignition; the runner's ``enforce_grammar`` re-check keeps a drift fail-closed (D100).

    ALLUMAGE NOTE - confronted at ignition against the installed Outlines 1.3.1 (was best-guess):
    Outlines DOES ship a first-class MLX bridge - ``outlines.from_mlxlm(model, tokenizer)`` - taking
    the exact ``mlx_lm.load()`` pair unchanged (no re-load, no HF ``transformers`` detour needed; the
    guessed ``from_transformers`` bridge this replaces does not apply to an mlx-lm model). The modern
    generator is ``outlines.Generator(model, output_type)``; ``output_type`` for a JSON schema MUST be
    ``outlines.json_schema(schema_text)`` - a live probe confirmed that handing ``Generator`` the raw
    schema STRING directly does not raise, it just silently ignores the schema and echoes it back
    (a schema-blind decode, never caught downstream by ``enforce_grammar``'s own JSON check only by
    luck). The older ``outlines.generate.json`` module does not exist in 1.3.1 (removed, not merely
    renamed). ``kind == "gbnf"`` is NOT wired: GBNF (llama.cpp's grammar dialect) is not the same
    grammar language as Outlines' Lark-based ``cfg()``, nothing in this codebase exercises that kind
    yet, and guessing the mapping risks a SILENT wrong grammar rather than a caught one - refused
    fail-closed instead (F3)."""
    import outlines  # noqa: F401 - lazy, machine-only (D103 sole importer)

    return _OutlinesBackend(model_backend)


class _OutlinesBackend:  # pragma: no cover - real Outlines translation ((3)-5b ignition, smoke-tested)
    """Thin wrapper: free-form delegates to the model; structured decodes under an Outlines grammar (D104).

    Holds the wrapped :class:`~mnemosyne.runtime.runner.GenerationBackend` and lazily builds an Outlines
    model from it (injected constructors so this class never imports at module scope). The SOLE place
    ``outlines`` types are touched (D103); the runner's ``enforce_grammar`` re-check wraps whatever this
    decodes (D100), so a non-conforming candidate is refused, never emitted. Reports the wrapped model's
    ``model_id`` (the identity that tags snapshots/traces is the model's, not the decoder's)."""

    __slots__ = ("_model", "_outlines_model")

    def __init__(self, model_backend: GenerationBackend) -> None:
        self._model = model_backend
        self._outlines_model: object | None = None  # built lazily on first structured decode

    @property
    def model_id(self) -> str:
        """The wrapped model's id - Outlines is a decode STRATEGY, not a different model (D104)."""
        return self._model.model_id

    def generate(self, prompt: str) -> str:
        """Free-form completion: delegate to the wrapped model unchanged (no grammar to bind, D104)."""
        return self._model.generate(prompt)

    def generate_structured(self, prompt: str, schema: str, kind: str) -> str:
        """Schema-constrained completion via Outlines (invariant 27). Decodes the ``prompt`` content
        UNDER the ``schema`` so the output obeys the grammar at the source; :class:`LocalRunner` then
        re-checks the candidate with ``enforce_grammar`` (the hard barrier, D100). ``kind`` selects the
        JSON-schema vs GBNF/regex path (confirmed at ignition)."""
        import outlines

        generator = self._structured_generator(outlines, schema, kind)
        # Honor the wrapped backend's max_tokens. Without it, Outlines' own default can cut a long
        # structured output mid-string -> truncated, unterminated JSON (the distillation schema is long:
        # confirmed at ignition, all models truncated at ~320 tokens). Defensive (F3): an Outlines build
        # that does not take max_tokens as a call kwarg falls back to its default rather than raising.
        max_tokens = getattr(self._model, "_max_tokens", None)
        if isinstance(max_tokens, int) and max_tokens > 0:
            try:
                return str(generator(prompt, max_tokens=max_tokens))
            except TypeError:
                pass
        return str(generator(prompt))

    def _structured_generator(self, outlines: object, schema: str, kind: str) -> object:
        """Build (once) the Outlines model, then a schema-bound generator for this schema.

        Confirmed at ignition (Outlines 1.3.1): only ``kind == "json_schema"`` is wired, via
        ``outlines.Generator(model, outlines.json_schema(schema))`` - the schema text MUST be wrapped
        with :func:`outlines.json_schema`, a raw string as ``output_type`` is silently ignored (see the
        ALLUMAGE NOTE on :func:`connect_outlines`). Any other ``kind`` (e.g. ``"gbnf"``) is refused
        fail-closed: GBNF is not Outlines' grammar dialect and nothing here exercises it yet (F3). A
        per-schema generator is fine here (rebuilt per call); ignition may cache it."""
        if kind != "json_schema":
            raise NotImplementedError(
                f"Outlines structured decode for kind={kind!r} is not wired (only 'json_schema' is "
                "confirmed - GBNF is a different grammar dialect than Outlines' cfg()); the runner's "
                "enforce_grammar barrier still applies regardless (D100)."
            )
        if self._outlines_model is None:
            self._outlines_model = self._build_outlines_model(outlines)
        return outlines.Generator(self._outlines_model, outlines.json_schema(schema))

    def _build_outlines_model(self, outlines: object) -> object:
        """Bridge the wrapped model backend into an Outlines model (confirmed at ignition).

        The wrapped backend (:class:`~mnemosyne.runtime.runner_mlx._MlxBackend`) holds the real
        ``mlx_lm`` model + tokenizer under ``._model`` / ``._tokenizer``; Outlines' first-class MLX
        bridge, ``outlines.from_mlxlm``, takes that exact pair unchanged (confirmed live - no re-load,
        no HF ``transformers`` detour, unlike the ``from_transformers`` guess this replaces)."""
        model = getattr(self._model, "_model", None)
        tokenizer = getattr(self._model, "_tokenizer", None)
        from_mlxlm = getattr(outlines, "from_mlxlm", None)
        if from_mlxlm is not None and model is not None and tokenizer is not None:
            return from_mlxlm(model, tokenizer)
        # No clean bridge exposed - confirmed/adjusted at ignition. Raising here (rather than guessing)
        # keeps F3: we do not pretend a bridge that is not wired.
        raise NotImplementedError(
            "Outlines MLX bridge unavailable: the wrapped backend does not expose an mlx_lm "
            "model/tokenizer pair (._model/._tokenizer), or outlines.from_mlxlm is missing. Wire the "
            "correct bridge at ignition; the runner's enforce_grammar re-check enforces the grammar "
            "regardless (D100)."
        )
