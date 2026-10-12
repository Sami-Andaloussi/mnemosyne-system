#!/usr/bin/env python3
"""Bench context for Mnemosyne System."""

from __future__ import annotations

import gc
import os
import sys
import time

_DEFAULT = ["mlx-community/Qwen3.6-35B-A3B-4bit"]
# Target sizes (tokens, approx ; real counts are printed). Overridable for a sweep FOCUSED on the
# practical range: `BENCH_SIZES=2000,8000,16000 uv run python scripts/bench_context.py <id>` (skips the slow 32k+).
_SIZES = [
    int(x) for x in os.environ.get("BENCH_SIZES", "2000,8000,16000,32000,48000,65000").split(",")
]
_NEEDLE = "REMEMBER THIS ABSOLUTELY: the verification code for this example is NORTHSTAR-2846."
_ANSWER = "ZEPHYR-2846"
_FILLER = (
    "Risk management and position sizing are at the core of quantitative finance. "
    "A prudent investor diversifies, measures volatility, and adjusts exposure over time. "
)
_QUESTION = "\n\nQUESTION: what is the password of the vault mentioned above? Answer in one line."
_MAX_TOKENS = 300  # enough for the answer to come OUT even after a bit of "thinking" (we stop once the needle is found)


def _chat(tokenizer: object, content: str) -> str:
    apply = getattr(tokenizer, "apply_chat_template", None)
    if apply is None:
        return content
    msgs = [{"role": "user", "content": content}]
    try:  # Qwen3 & co : cut the "thinking" for a direct answer (otherwise the token budget goes into <think>)
        return apply(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)  # type: ignore[no-any-return]
    except TypeError:  # tokenizer that does not accept the kwarg -> standard template
        return apply(msgs, tokenize=False, add_generation_prompt=True)  # type: ignore[no-any-return]


def _build(tokenizer: object, n_tokens: int) -> str:
    """Filler up to ~n_tokens, the needle planted in the MIDDLE, the question at the end."""
    unit = len(tokenizer.encode(_FILLER))  # type: ignore[attr-defined]
    reps = max(2, n_tokens // max(1, unit))
    half = reps // 2
    return _FILLER * half + "\n" + _NEEDLE + "\n" + _FILLER * (reps - half) + _QUESTION


def bench_one(model_id: str) -> None:
    from mlx_lm import load, stream_generate

    print(f"\n{'=' * 70}\n{model_id}\n{'=' * 70}", flush=True)
    try:
        model, tokenizer = load(model_id)
    except Exception as exc:  # noqa: BLE001
        print(f"  LOAD FAILED : {exc!r}", flush=True)
        return
    for n in _SIZES:
        prompt = _chat(tokenizer, _build(tokenizer, n))
        real = len(tokenizer.encode(prompt))  # type: ignore[attr-defined]
        t0 = time.perf_counter()
        prefill: float | None = None
        pieces: list[str] = []
        try:
            for resp in stream_generate(model, tokenizer, prompt=prompt, max_tokens=_MAX_TOKENS):
                if prefill is None:
                    prefill = (
                        time.perf_counter() - t0
                    )  # first token = prefill done: THE signal for "loaded != usable"
                pieces.append(resp.text)
                if _ANSWER in "".join(pieces):
                    break  # needle found -> no need to generate more (isolates prefill from the rest)
        except Exception as exc:  # noqa: BLE001 - an OOM/error at this size = the ceiling; we stop here
            print(
                f"  [~{n // 1000}k -> {real} real tok] GENERATION FAILED (CEILING) : {exc!r}",
                flush=True,
            )
            break
        total = time.perf_counter() - t0
        out = "".join(pieces).strip()
        prefill = prefill if prefill is not None else total
        found = "NEEDLE FOUND" if _ANSWER in out else "NEEDLE LOST"
        print(
            f"  [~{n // 1000}k -> {real} tok] prefill {prefill:6.1f}s | total {total:6.1f}s | "
            f"{found} | end: {out[-60:]!r}",
            flush=True,
        )
    del model, tokenizer
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    for model_id in (sys.argv[1:] if argv is None else argv) or _DEFAULT:
        bench_one(model_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
