#!/usr/bin/env python3
"""TOOL-CALLING bench: which local model can drive Mnemosyne's agent loop AS IT ACTUALLY IS?

The only honest test (the hard "tool-calling" gate): "succeeding" = Mnemosyne's REAL PARSER
(agents.pydantic_bridge._parse_tool_call) can extract the tool call from the model's output. Each
model is given the SAME tool preamble as Mnemosyne (format <tool_call>{...}</tool_call>, Qwen/Hermes
style, rendered as TEXT because the MLX backend has no native tool template) + a question that
REQUIRES calling search_memory, then scored with the real parser.

Why multi-FAMILY matters: a model from another family (gpt-oss "harmony", Gemma, Phi...) may know how
to tool-call natively but FAIL this test because it does not emit the <tool_call> format Mnemosyne
expects -> a decision-relevant finding: "good model, but adopting it means adapting the parser / using
its native format". That is exactly what this gate is meant to measure BEFORE pairing a model with a role.

Only one BIG resident model at a time (the script loads / benches / RELEASES, sequentially); do NOT
run this script at the same time as another one that loads a model (RAM contention on 32 GB).

Usage:
  PYTHONPATH=system/lib uv run python scripts/bench_tool_calling.py                    # the whole downloaded zoo
  PYTHONPATH=system/lib uv run python scripts/bench_tool_calling.py mlx-community/<id>  # explicit list
"""

from __future__ import annotations

import gc
import json
import sys

from mnemosyne.agents.pydantic_bridge import (
    _parse_tool_call,
)  # Mnemosyne's REAL parser = the honest judge

_DEFAULT_ZOO = [
    "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "mlx-community/Qwen3.6-35B-A3B-4bit",
    "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
    "mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit",
    "mlx-community/gpt-oss-20b-MXFP4-Q8",
    "mlx-community/gemma-3-27b-it-qat-4bit",
    "mlx-community/phi-4-4bit",
]

#: The SAME contract as agents.pydantic_bridge._render_tool_preamble (verbatim, <tool_call>-style
#: format, Qwen). If Mnemosyne's preamble evolves, mirror it here.
_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}
_PREAMBLE = (
    "You have tools to consult the user's memory. Available tools:\n"
    f"- search_memory: Search the configured reference library for relevant passages. "
    f"(arguments JSON schema: {json.dumps(_SEARCH_SCHEMA)})\n"
    "To call a tool, reply with EXACTLY one line and nothing else:\n"
    '<tool_call>{"name": "<tool>", "arguments": {<args>}}</tool_call>\n'
    "You will then see the tool result. When you have enough, write your final answer as plain text "
    "(do NOT wrap the final answer in <tool_call>)."
)
_INSTRUCTIONS = (
    "Ground every claim in retrieved passages. ALWAYS call search_memory before answering."
)
_QUESTION = "What does the literature say about the Kelly criterion? Search the document base."
_MAX_TOKENS = 512  # enough for a reasoning model to think, THEN emit the call


def _chat(tokenizer: object, content: str) -> str:
    apply = getattr(tokenizer, "apply_chat_template", None)
    if apply is None:
        return content
    return apply([{"role": "user", "content": content}], tokenize=False, add_generation_prompt=True)  # type: ignore[no-any-return]


def score(text: str) -> str:
    """Judges the raw output with Mnemosyne's REAL PARSER (+ diagnostics of why it breaks)."""
    call = _parse_tool_call(text)
    if call is not None and call[0] == "search_memory":
        args = call[1]
        good = (
            isinstance(args, dict)
            and isinstance(args.get("query"), str)
            and bool(args["query"].strip())
        )
        return (
            "PASS  -- Mnemosyne parses the call + valid query"
            if good
            else f"PARTIAL -- call parsed, dubious args : {args!r}"
        )
    if call is not None:
        return f"PARTIAL -- tool_call parsed but wrong tool name : {call[0]!r}"
    if "<tool_call>" in text:
        return "FAIL -- <tool_call> marker present but JSON not parsable (truncated / malformed)"
    if "search_memory" in text:
        return "FAIL -- mentions search_memory in a DIFFERENT format -> Mnemosyne's parser is blind to it"
    return "FAIL -- no attempt at a tool call"


def bench_one(model_id: str) -> None:
    from mlx_lm import generate, load

    print(f"\n{'=' * 70}\n{model_id}\n{'=' * 70}")
    try:
        model, tokenizer = load(model_id)
    except Exception as exc:  # noqa: BLE001 - a model that fails must not stop the others
        print(f"  LOAD FAILED : {exc!r}")
        return
    prompt = f"{_PREAMBLE}\n\n[Instructions]\n{_INSTRUCTIONS}\n\n[User]\n{_QUESTION}"
    text = generate(
        model, tokenizer, prompt=_chat(tokenizer, prompt), max_tokens=_MAX_TOKENS
    ).strip()
    print(f"  score  : {score(text)}")
    print(f"  output : {text[:500]}")
    del model, tokenizer
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()  # releases the Metal cache before the next model
    except Exception:  # noqa: BLE001 - the release API can move between versions; never blocking
        pass


def main(argv: list[str] | None = None) -> int:
    ids = (sys.argv[1:] if argv is None else argv) or _DEFAULT_ZOO
    for model_id in ids:
        bench_one(model_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
