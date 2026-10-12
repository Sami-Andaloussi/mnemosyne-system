#!/usr/bin/env python3
"""LIGHT bench for comparing local MLX models (in the spirit of the tool-calling / perf / output gate).

Loads each given model, measures load time + tokens/sec on two fixed prompts (a free-reasoning
prompt, a structured-output prompt for a first coarse signal of JSON discipline), and prints the raw
output for a qualitative eyeball judgment. THIS IS NOT the formal tool-calling bench (reliability in
the hard-gate, grammar sense - see `bench_tool_calling.py`) - it is the "quickly test what runs and
what is fast" the operator asked for; the full formal bench (golden set, grammar, eliminatory gate)
remains a separate undertaking for whenever a model truly needs to be arbitrated for a production role.

Explicitly releases the model before loading the next one (only one BIG resident model at a time on
32 GB of RAM - enforced by the script itself, not just discipline).

Usage:
  PYTHONPATH=system/lib uv run python scripts/bench_local_models.py                       # default = whatever is already downloaded
  PYTHONPATH=system/lib uv run python scripts/bench_local_models.py mlx-community/<id> ... # explicit list

Prerequisites: `uv sync --extra bricks` (mlx-lm) + the weights already fetched (`huggingface-cli download` or
a first `load()` call that downloads them). This script never deletes or writes anything to disk.
"""

from __future__ import annotations

import gc
import sys
import time

#: Already on disk at the time this script was written - the starting point with nothing more
#: to download.
_DEFAULT_CANDIDATES = [
    "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
    "mlx-community/Qwen2.5-7B-Instruct-4bit",
]

#: Two distinct axes: (1) a free-form reasoning question; (2) a STRICTLY structured-output
#: instruction - not proof of real tool-calling, just a first signal of whether the model can stay
#: in a format with no grammar enforced by the engine.
_PROMPTS = [
    (
        "reasoning",
        "In one sentence: why does the Kelly criterion limit position size?",
    ),
    (
        "structured",
        'Reply ONLY with a JSON object {"capital_of_germany": "..."} '
        "(nothing before, nothing after): what is the capital of Germany?",
    ),
]

_MAX_TOKENS = 512  # enough for a REASONING model (e.g. Qwen3 "thinking") to finish its thought + answer


def _chat(tokenizer: object, content: str) -> str:
    """Same shape as `_MlxBackend._chat` (runner_mlx.py): goes through the chat template if available."""
    apply = getattr(tokenizer, "apply_chat_template", None)
    if apply is None:
        return content
    return apply([{"role": "user", "content": content}], tokenize=False, add_generation_prompt=True)  # type: ignore[no-any-return]


def bench_one(model_id: str, *, max_tokens: int = _MAX_TOKENS) -> None:
    from mlx_lm import generate, load  # lazy - machine-only, never in the test suite

    print(f"\n{'=' * 70}\n{model_id}\n{'=' * 70}")
    t0 = time.perf_counter()
    try:
        model, tokenizer = load(model_id)
    except Exception as exc:  # noqa: BLE001 - a model that fails must not stop the others
        print(f"  LOAD FAILED : {exc!r}")
        return
    print(f"  loaded in {time.perf_counter() - t0:.1f}s")

    for label, prompt in _PROMPTS:
        t0 = time.perf_counter()
        text = generate(
            model, tokenizer, prompt=_chat(tokenizer, prompt), max_tokens=max_tokens
        ).strip()
        gen_s = time.perf_counter() - t0
        n_tokens = len(tokenizer.encode(text))
        tps = n_tokens / gen_s if gen_s > 0 else float("inf")
        print(f"\n  [{label}] {gen_s:.1f}s for {n_tokens} tokens -> {tps:.1f} tok/s")
        print(f"  answer : {text[:600]}")

    del model, tokenizer
    gc.collect()
    try:
        import mlx.core as mx  # same brick as above, already imported transitively

        mx.clear_cache()  # best-effort: releases the Metal cache before the next model
    except Exception:  # noqa: BLE001 - the release API can move between versions; never blocking
        pass


def main(argv: list[str] | None = None) -> int:
    ids = (sys.argv[1:] if argv is None else argv) or _DEFAULT_CANDIDATES
    for model_id in ids:
        bench_one(model_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
