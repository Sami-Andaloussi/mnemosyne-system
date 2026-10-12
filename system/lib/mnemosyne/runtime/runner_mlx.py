"""MlxBackend (D104, ③-2c) — the real local generation brick behind the Runner's decode seam.

The default OSS runner brick is **MLX / mlx-lm** (Apache-2.0, Apple-silicon native), llama.cpp as
fallback (D104 / D88). This file wraps it behind the primitive
:class:`~mnemosyne.runtime.runner.GenerationBackend` seam that
:class:`~mnemosyne.runtime.runner.LocalRunner` decodes through — so the SECURITY barriers
(grant redemption M1, grammar enforcement invariant 27, replay snapshot, label monotonicity)
stay entirely in :class:`LocalRunner` and are unit-tested against a double, while THIS thin
translation to mlx-lm (:class:`_MlxBackend`, the SOLE importer of the brick, D103) is exercised
only by the 1-click smoke at ③ ignition, never by the brick-free suite (D126 — the suite stays
green with nothing installed).

**The grammar barrier is not delegated (D100).** Structured decoding ASKS the engine for
schema-constrained output (Outlines / XGrammar, D104), but :class:`LocalRunner` re-checks every
structured candidate with :func:`~mnemosyne.runtime.runner.enforce_grammar` (invariant 27) — the
code barrier never trusts the model, so a non-conforming candidate is refused fail-closed, never
emitted. The exact grammar engine is confirmed at install.

**The model identity is NOT frozen here any more (C9).** It used to be a hard-coded default on the
line below; it is now the caller's explicit act, checked against the declared basket
(``system/config/models.toml``) and against the disk, both ways, by
:mod:`mnemosyne.production.model_catalog`. Nobody names one ⇒ a named refusal that prints the
basket. Everything runs LOCAL (D27 / D66). Code & docstrings English (D117).

Decisions: D104 (runner, MLX) · D88 (OSS server strategy) · D103 (sole importer) ·
D126 (decoupling / ignition ``[OPERATOR]``) · D95 (one big model at a time, 32 GB budget) ·
C9 (the declared basket; no default).
"""

from __future__ import annotations

from ..ports.core import ResourceBoundError


def refuser_si_tronque(sortie: str, tokenizer: object, plafond: int) -> None:
    """THE SAME DEFECT AS ON THE FRONTIER PATH, BUT WITH NO SIGNAL TO READ (A4 / D165).

    The repo's own memory already named it: *"`_DEFAULT_MAX_TOKENS=512` cuts EVERY local
    generation off mid-word, with no refusal state — unlike the INPUT ceiling (D136), which refuses
    instead of cutting,"* and that **explained several symptoms that were being mistaken for model
    problems**. The lesson was engraved; no barrier held it. Here it is.

    HERE, TRUNCATION IS INFERRED, IT IS NOT READ. `mlx_lm.generate` returns a bare string:
    no `stop_reason` at all. So the output is re-encoded and compared against the ceiling. A generation
    that would NATURALLY stop exactly at the ceiling would be wrongly accused — that is vanishingly rare,
    and it is the right side to err on: *between a silent false green and a loud false red, pick the
    one that shouts*. A tokenizer that does not encode stays silent rather than invent a truncation.
    """
    encode = getattr(tokenizer, "encode", None)
    if plafond <= 0 or not callable(encode):
        return
    try:
        jetons = len(encode(sortie))
    except Exception:  # noqa: BLE001 - a silent tokenizer does not invent a truncation
        return
    if jetons < plafond:
        return
    raise ResourceBoundError(
        f"local generation TRUNCATED by the output ceiling (max_tokens={plafond}, "
        f"{jetons} tokens rendered): the model was cut off before finishing. This is not a "
        f"short answer, it is an INCOMPLETE one. Remedy: raise `max_tokens` on the call to "
        f"`build_backend`, or split the request."
    )


#: **THERE IS NO DEFAULT MODEL ANY MORE (C9).** This line used to read
#: ``_DEFAULT_MODEL_ID = "mlx-community/Qwen2.5-7B-Instruct-4bit"`` and it decided, silently, for
#: every caller who did not think to argue. The user, in their own words: *"you change the default
#: line, you all but remove it, you delete it […] I don't like this thing of locking myself into
#: 'oh, this is the agent I use, not that one.'"* So the branch is GONE, not re-pointed: naming
#: the model is now the caller's act, and :func:`~mnemosyne.production.model_catalog.resolve_model_id`
#: REFUSES — printing the whole basket — when nobody named one. *The default branch is where silence
#: hides*; removing a silent default means replacing it with a refusal that names, never with a
#: better guess.
_DEFAULT_MAX_TOKENS = 512

#: How the content + a JSON schema are turned into a decode instruction when no grammar engine is
#: wired. A weak prompt-level constraint on purpose: the HARD barrier is LocalRunner.enforce_grammar,
#: which refuses a non-conforming candidate (invariant 27) — this only nudges the model toward it.
#: The CONTENT is included so the model labels / extracts FROM it, never blind (③-2 closure / F2).
_STRUCTURED_INSTRUCTION = (
    "Given the content below, respond with a single JSON object conforming to this JSON schema, "
    "and nothing else.\n\nContent:\n{content}\n\nJSON schema:\n{schema}"
)


def load_mlx_backend(  # pragma: no cover - needs the brick + weights (③ ignition, smoke-tested)
    *,
    model_id: str | None = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> "_MlxBackend":
    """Load the real MLX weights and return a wired backend (③-2c ignition, D126 ``[OPERATOR]``).

    ``model_id=None`` is NOT a default — it is the refusal path (C9). The id is resolved through
    :func:`~mnemosyne.production.model_catalog.resolve_model_id`, which raises
    :class:`~mnemosyne.production.model_catalog.ModelRefused` (printing the basket) when nobody
    named a model, when the named one is not declared, or when the declaration and the disk
    disagree. The resolution happens BEFORE the lazy ``mlx_lm`` import on purpose: a caller who
    named nothing must read a named refusal, not an import error or thirty seconds of weight
    loading followed by a stack trace.

    Lazy import: ``mlx-lm`` and the weights are absent in CI and present only once installed on
    the machine. Kept off the covered path — its integration is validated by the real 1-click
    smoke (``make smoke``), not the unit suite. This is the SOLE importer of the MLX brick
    (D103); the runner's barriers wrap whatever it decodes (D100)."""
    from ..production.model_catalog import resolve_model_id

    resolved = resolve_model_id(model_id)

    from mlx_lm import load  # lazy, machine-only (D103 sole importer)

    model, tokenizer = load(resolved)
    return _MlxBackend(model, tokenizer, model_id=resolved, max_tokens=max_tokens)


class _MlxBackend:  # pragma: no cover - real mlx-lm translation (③ ignition, smoke-tested)
    """Thin translation from the primitive ``GenerationBackend`` surface to mlx-lm's ``generate``.

    The SOLE place mlx-lm types are touched (D103). Never run by the unit suite; the barriers it
    feeds live in :class:`~mnemosyne.runtime.runner.LocalRunner`. ``generate`` is free-form;
    ``generate_structured`` nudges the engine toward the schema, and LocalRunner re-checks the
    candidate (invariant 27) so a malformed one is refused, never emitted (D100)."""

    def __init__(self, model: object, tokenizer: object, *, model_id: str, max_tokens: int) -> None:
        self._model = model
        self._tokenizer = tokenizer
        self._model_id = model_id
        self._max_tokens = max_tokens

    @property
    def model_id(self) -> str:
        return self._model_id

    def generate(self, prompt: str) -> str:
        """Free-form local completion via mlx-lm (the smoke's answer path, D65 / D104)."""
        return self._run(prompt)

    def generate_structured(self, prompt: str, schema: str, kind: str) -> str:
        """Extract schema-shaped structure FROM the ``prompt`` content; LocalRunner.enforce_grammar
        is the hard barrier (invariant 27).

        The prompt (the content to label / to extract facts from) is handed to the model together
        with the schema — decoding the schema blind to the content would only ever hallucinate
        (③-2 closure / F2). ``kind`` is carried for the grammar engine wired at install (json_schema
        → Outlines / XGrammar, gbnf → a GBNF grammar). Until then the instruction steers the model
        and the runner's re-check keeps it fail-closed — a non-conforming candidate raises, never
        emits."""
        instruction = (
            _STRUCTURED_INSTRUCTION.format(content=prompt, schema=schema)
            if kind == "json_schema"
            else f"{prompt}\n\n{schema}"
        )
        return self._run(instruction)

    def _run(self, content: str) -> str:
        from mlx_lm import generate  # lazy, machine-only (D103 sole importer)

        sortie = generate(
            self._model, self._tokenizer, prompt=self._chat(content), max_tokens=self._max_tokens
        ).strip()
        refuser_si_tronque(sortie, self._tokenizer, self._max_tokens)
        return sortie

    def _chat(self, content: str) -> str:
        """Wrap a bare prompt in the tokenizer's chat template when it exposes one (instruct models)."""
        apply = getattr(self._tokenizer, "apply_chat_template", None)
        if apply is None:
            return content
        return apply(
            [{"role": "user", "content": content}], tokenize=False, add_generation_prompt=True
        )
