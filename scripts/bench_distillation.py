#!/usr/bin/env python3
"""Bench distillation for Mnemosyne System."""

from __future__ import annotations

import gc
import sys
import time
from pathlib import Path

_CANDIDATES = [
    "mlx-community/GLM-4-9B-0414-4bit",  # 9B dense: fast, concise, clean JSON - distillation favorite
    "mlx-community/Qwen3.6-35B-A3B-4bit",  # 35B MoE: fast + context-capable (the only one available locally)
    "mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit",  # 24B dense: better prose, but slow
]
_RAW = Path("knowledge/raw")
_EXCERPT_CHARS = 24_000  # under the runner ceiling (48k) with margin for the template + schema
_SKIP_CHARS = 40_000  # skip the front-matter / TOC, take from the BODY of the book
_OUT = (
    Path(__file__).resolve().parents[1] / ".bench_distill_fiches"
)  # rendered fiches, for the eye (git-ignored)


def _pick_docs(n: int) -> list[Path]:
    """The first n .md files (stable order) big enough to offer a body excerpt."""
    big = [m for m in sorted(_RAW.rglob("*.md")) if m.stat().st_size > _SKIP_CHARS + _EXCERPT_CHARS]
    return big[:n]


def _excerpt(path: Path) -> str:
    """A ~24k-char window taken from the BODY of the doc (not the front-matter)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[_SKIP_CHARS : _SKIP_CHARS + _EXCERPT_CHARS]


def _make_api(model_id: str):  # noqa: ANN202 - CoreApi, imported lazily (brick)
    """A CoreApi on a Runtime whose decode backend is the REAL MLX model (grammar if available)."""
    from mnemosyne.api import CoreApi
    from mnemosyne.runtime.bootstrap import bootstrap
    from mnemosyne.runtime.runner_mlx import load_mlx_backend

    backend = load_mlx_backend(
        model_id=model_id, max_tokens=3072
    )  # room for the full bounded fiche
    try:
        from mnemosyne.runtime.runner_outlines import connect_outlines

        backend = connect_outlines(
            backend
        )  # grammar: forces pure JSON, cutting off the model's "thinking"
    except Exception as exc:  # noqa: BLE001 - without Outlines, the model must produce valid JSON on its own
        print(
            f"  (Outlines unavailable: {exc!r} -> raw backend; invalid JSON => DistillationMalformed)"
        )
    return CoreApi(bootstrap(generation_backend=backend))


def bench_one(model_id: str, docs: list[Path]) -> None:
    from mnemosyne.ports import Bubble
    from mnemosyne.production import DistillationInput, DistilledType

    print(f"\n{'=' * 70}\n{model_id}\n{'=' * 70}", flush=True)
    t_load = time.perf_counter()
    try:
        api = _make_api(model_id)
    except Exception as exc:  # noqa: BLE001
        print(f"  LOAD FAILED : {exc!r}", flush=True)
        return
    print(f"  loaded in {time.perf_counter() - t_load:.1f}s", flush=True)
    slug = model_id.split("/")[-1]
    for path in docs:
        inp = DistillationInput(
            doc_id=f"library/{path.stem[:40]}",
            source_text=_excerpt(path),
            dtype=DistilledType.BOOK,
            title_hint=path.stem[:60],
        )
        t0 = time.perf_counter()
        try:
            doc = api.distill(inp, subject=Bubble("bench-distill"))
        except Exception as exc:  # noqa: BLE001 - a model that fails must not kill the bench
            print(f"  [{path.stem[:34]:34}] FAILED : {type(exc).__name__}: {exc}", flush=True)
            continue
        dt = time.perf_counter() - t0
        p3_chars = sum(len(p) for p in doc.passages)
        out_file = _OUT / f"{slug}__{path.stem[:40]}.md"
        out_file.write_text(doc.render(), encoding="utf-8")
        print(
            f"  [{path.stem[:34]:34}] {dt:6.1f}s | P3 : {len(doc.passages):2} passages "
            f"({p3_chars} chars verbatim) | title: {doc.title[:44]!r}",
            flush=True,
        )
    del api
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except Exception:  # noqa: BLE001 - the release API can move between versions; never blocking
        pass


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    n_docs = int(args[0]) if args else 1
    _OUT.mkdir(exist_ok=True)
    docs = _pick_docs(n_docs)
    if not docs:
        print(
            f"No .md doc big enough under {_RAW}/ (need > {_SKIP_CHARS + _EXCERPT_CHARS} chars)."
        )
        return 1
    print(f"Docs to distill ({len(docs)}) : " + ", ".join(d.stem[:40] for d in docs))
    print(f"Fiches written to : {_OUT}")
    for model_id in _CANDIDATES:
        bench_one(model_id, docs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
