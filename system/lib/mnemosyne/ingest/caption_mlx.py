"""MLX-VLM caption adapter (sujet 2) — a LOCAL vision-language model behind the ImageCaptioner port.

The sujet-2 vision stage needs an EYE that reads a figure / graph into text. This adapter wraps a local
MLX-VLM model (Apple-Silicon-native, the vision analogue of WhisperKit / ocrmac) behind
:class:`~mnemosyne.ports.captioner.ImageCaptioner`. It is a SOLE-importer adapter (D103 / invariant 20): the
one module allowed to touch ``mlx_vlm``, imported LAZILY so the suite stays green with no VLM installed
(D126). LOCAL by construction (invariant 1 / D66): a personal corpus is ``sensible``, so figure bytes never
leave the Mac. Everything here is ``# pragma: no cover``: it runs only at ③ ignition (``uv sync --extra
bricks``), where the 1-click smoke confronts this glue with the real API. A drift is non-catastrophic — a
per-figure failure fails open to ``""`` (the placeholder stays, D85), never a lost book.

**Honesty (F3).** The exact mlx-vlm ``generate`` signature (image kwarg, PIL vs path, chat-template
application) varies across releases; this adapter takes a best-guess call with an explicit IGNITION NOTE, to
be confirmed at the smoke ``[OPERATOR]`` — not invented certainty. The eye this seam was TUNED against stays its
default (:data:`_DEFAULT_MODEL`, restored 2026-08-02 — a measurement is not a silent default); the caller
overrides it through ``MODELE_VISION``, and the declared basket validates whatever is retained. Code & docstrings
English (D117); the caption PROMPT asks for French — the description lands in the operator's French
``.md`` (D117 produit).

Decisions: D43 (enriches Docling) · D103 (sole importer) · D126 (import-safe, brick-free suite) · invariant
1 / D66 (sensible → local) · D100 (output Guard-mediated upstream) · D85 (per-figure fail-open).
"""

from __future__ import annotations

from ..ports import ImageCaptioner

#: **THIS IS A CHOSEN EYE, NOT A SILENT DEFAULT — restored 2026-08-02 after being deleted by
#: mistake.** It was classed as "the second of three silent hard-coded model choices" and removed;
#: The operator stopped it: *"if he tested it, why are you deleting it? It is extremely dangerous."*
#: The
#: line carried its own provenance — *frozen default VLM, strong at documents / charts on Apple
#: Silicon (``oss_registry.md``)* — and the prompt below is tuned to THIS model (pilot 3 measured
#: that the 4-bit Qwen2.5-VL regurgitates a listy answer on a longer instruction).
#:
#: The distinction the C9 mandate failed to write: a DEFAULT is a generic fallback for any caller
#: (``runner_mlx`` had one, and it is rightly gone); a SPECIFICATION is the model picked for ONE task
#: after trying it. Deleting the second destroys the only application of a measurement.
#:
#: It stays OVERRIDABLE, and it reads its OWN variable — ``MODELE_VISION``, never ``MODELE``. One
#: shared name would let a text model set for a distillation silently become the captioner's eye.
_DEFAULT_MODEL = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"

#: The captioning instruction — the SINGLE source of the prompt (anti-drift). Deliberately SHORT and free of
#: parenthesised enumerations and conditional clauses: pilot 3 showed the 4-bit Qwen2.5-VL REGURGITATES a listy
#: prompt's own words, and answers "[]" to an "if illegible, reply empty" clause — while a short ask yields a
#: real caption. Keep it minimal (③ pilot 3). French output — the caption lands in the operator's
#: French .md (D117).
_PROMPT = "Décris cette figure en 1 à 3 phrases, en français. Reste factuel et n'invente rien."

#: Chat special-tokens a 4-bit VLM decode may dribble into the text; stripped defensively (pilot 1 saw
#: ``<|endoftext|>`` leak even mid-caption). The single source of the strip list.
_STRAY_TOKENS = (
    "<|endoftext|>",
    "<|im_end|>",
    "<|im_start|>",
    "<|vision_start|>",
    "<|vision_end|>",
)


def _clean_caption(text: str) -> str:
    """Strip stray chat special-tokens the decode may leak, then collapse to one line — so a marked caption
    stays a single tidy blockquote line downstream (the weave already collapses, this hardens the source)."""
    for token in _STRAY_TOKENS:
        text = text.replace(token, " ")
    return " ".join(text.split()).strip()


def connect_mlx_vlm(
    model: str | None = None,
) -> ImageCaptioner:  # pragma: no cover - needs the brick (③ ignition)
    """Wrap a local MLX-VLM as an :class:`ImageCaptioner` (the ``[OPERATOR]`` ignition seam, sujet 2).

    PRECEDENCE: what the caller names wins, then ``MODELE_VISION``, then :data:`_DEFAULT_MODEL` —
    the eye this seam was tuned against. Refusing an unnamed call would throw away a measurement for
    want of retyping it. The basket still VALIDATES whatever is retained
    (:func:`~mnemosyne.production.model_catalog.resolve_model_id`): an id off the basket, absent from
    disk, or whose weights drifted is refused, the chosen eye included. Resolved BEFORE the brick
    import, so a refusal reads as a named refusal rather than an ``ImportError`` about mlx-vlm.

    Imports ``mlx_vlm`` LAZILY, so this module is import-safe without it (D126); wired by
    :func:`~mnemosyne.runtime.bootstrap.real_runtime` when the vision stage is enabled. LOCAL (invariant 1):
    figure bytes never leave the Mac; the caption output is Guard-mediated by the caller (D100).

    IGNITION NOTE (pilots 1-2 confronted, mlx-vlm 0.6.4): a caption needs BOTH (a) the prompt formatted through
    the chat template — ``apply_chat_template(processor, model.config, <text>, num_images=1)`` (a RAW prompt
    loops / leaks tokens, pilot 1); AND (b) the image passed as a FILE PATH, not a PIL object —
    ``generate(model, processor, formatted, image=[path], max_tokens=..., verbose=False)`` → a
    ``GenerationResult`` with ``.text`` (a PIL object left the single ``<|image_pad|>`` un-expanded, so the
    model saw no image and emitted 1-3 chars, pilot 2). ``config`` = ``model.config``; still best-guess until
    the next pilot confirms real captions."""
    from ..production.model_catalog import ENV_VISION_MODEL, resolve_model_id

    import os

    named = model or os.environ.get(ENV_VISION_MODEL, "").strip() or _DEFAULT_MODEL
    resolved = resolve_model_id(named, env_var=ENV_VISION_MODEL)

    from mlx_vlm import generate, load  # the SOLE import of the brick (D103 / invariant 20)
    from mlx_vlm.prompt_utils import apply_chat_template

    loaded_model, processor = load(resolved)
    config = getattr(loaded_model, "config", None)
    return _MlxVlmCaptioner(
        loaded_model, processor, generate, apply_chat_template, config, resolved
    )


class _MlxVlmCaptioner:  # pragma: no cover - real MLX-VLM translation (③-4b ignition, smoke-tested)
    """Thin translation from :class:`ImageCaptioner` to mlx-vlm's ``generate`` (sujet 2 / D103).

    Holds the injected model / processor / generate (so this class never imports at module scope).
    ``caption`` decodes the figure bytes to a PIL image, runs the local VLM with :data:`_PROMPT` (grounded by
    any caption line), and returns the stripped text — running LOCAL on untrusted bytes (D100-3). Per-figure
    FAIL-OPEN (D85): ANY failure returns ``""`` so the pipeline keeps the placeholder rather than losing the
    book; the output is model-generated and Guard-mediated by the caller (D100)."""

    __slots__ = (
        "_model",
        "_processor",
        "_generate",
        "_apply_chat_template",
        "_config",
        "_model_id",
    )

    def __init__(
        self,
        model: object,
        processor: object,
        generate: object,
        apply_chat_template: object,
        config: object,
        model_id: str,
    ) -> None:
        self._model = model
        self._processor = processor
        self._generate = generate
        self._apply_chat_template = apply_chat_template
        self._config = config
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def caption(self, image: bytes, *, context: str = "") -> str:
        try:
            import os
            import tempfile
            from io import BytesIO

            from PIL import Image

            opened = Image.open(BytesIO(image))
            if opened.mode == "RGB":
                pil_image = opened
            else:
                # Flatten any transparency onto WHITE (pilot 4): a bare .convert("RGB") turns a transparent
                # background BLACK, which hid the 4 dark line-art trading CHARTS (they came out as "La" + stop)
                # while opaque figures — a logo, a concept schema — were fine.
                rgba = opened.convert("RGBA")
                pil_image = Image.new("RGB", rgba.size, (255, 255, 255))
                pil_image.paste(rgba, mask=rgba.split()[-1])
            instruction = (
                _PROMPT
                if not context.strip()
                else f"{_PROMPT}\n\nLégende éventuelle : {context.strip()}"
            )
            # Format through the model's chat template FIRST (pilot-1 fix): a RAW prompt makes the VLM loop /
            # leak special tokens / emit grounding coordinates instead of a natural-language caption.
            prompt = self._apply_chat_template(
                self._processor, self._config, instruction, num_images=1
            )
            # mlx-vlm 0.6.4 wants an image PATH (str), NOT a PIL object (pilot 2): a PIL left the single
            # <|image_pad|> un-expanded, so the model saw no image and emitted 1-3 chars. Write a temp PNG.
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                pil_image.save(tmp, format="PNG")
                tmp_path = tmp.name
            try:
                result = self._generate(
                    self._model,
                    self._processor,
                    prompt,
                    image=[tmp_path],
                    max_tokens=200,
                    verbose=False,
                )
            finally:
                os.unlink(tmp_path)
            text = result if isinstance(result, str) else getattr(result, "text", "")
            return _clean_caption(text)
        except Exception:  # noqa: BLE001 - fail-open per figure (D85): a VLM failure never aborts the book
            return ""
