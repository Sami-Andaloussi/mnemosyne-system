"""local_run (item 1 / D7 / the cohabitation doctrine) — the frontier→LOCAL dispatch surface.

The WRITE-analog of ``make search``. ``make search`` lets a FRONTIER host (Claude Code / Codex) READ
Mnémosyne's memory from a shell; THIS lets a frontier DELEGATE a bounded unit of mechanical decode to
the LOCAL MLX brain and take back the result — the master (frontier) reasons and orchestrates, the local
executor abates the volume (:mod:`~mnemosyne.production` ``production-delegation-doctrine`` /
``context-minimization``). It is how a frontier "sends a local agent to do local work", the way Claude
Code sends a sub-agent — but toward the free, private, on-machine model::

    make local-run PROMPT="Turn this paragraph into 3 factual bullets: <text>"
    make local-run PROMPT="Extract the fields" SCHEMA=path/to/schema.json     # structured (JSON)
    python -m mnemosyne.runtime.local_run "<prompt>" [--within sensible] [--schema <file>] [--bubble work]

WHY it exists (the user, item 1): the local model is far more limited than a frontier, but it is FREE (no
token cost) and PRIVATE (nothing leaves the machine). So a frontier hands it the repeated / mechanical /
cheap work — saving up the frontier budget for the fine reasoning — and orchestrates the pieces.

THE RULE this surface serves: be aware of the local model's CONTEXT and CAPABILITIES, and give it a task
PRECISE and granular ENOUGH to answer correctly. ONE bounded task per call; the frontier chains them. The
"bounded" half is enforced structurally (the runner's D136 input ceiling REFUSES an over-large prompt,
never truncates); the "precise + granular" half is the caller's craft.

Fully governed (:meth:`~mnemosyne.api.core_api.CoreApi.run_local`): the call mints a fresh single-use
``MODEL_CALL`` grant through the Guard and decodes through the runtime's Runner (grant redemption M1,
replay snapshot, redacted trace, grammar enforcement when ``--schema`` is given). The decode is LOCAL —
so ``--within`` safely defaults to the fail-safe ``sensible`` (a frontier may dispatch even personal work;
it never leaves the machine, invariant 1). The output is matière-de-travail, never an endorsed fact.

Unlike ``make search`` (retrieval-only, ``load_brain=False``), this DOES load the generative brain — it is
a decode. Code & docstrings English (D117). NOT run in CI (needs the MLX brick + weights)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..api import CoreApi
from ..ports import Bubble, Sensitivity
from .bootstrap import real_runtime

#: The bubble frontier-dispatched local work runs in — a plain matière-de-travail bubble, distinct from
#: the knowledge library (``make search``) and the ops supervision surface. The dispatched task is decode,
#: not a knowledge read, so it neither reads nor writes the user's corpus.
_DEFAULT_BUBBLE = "work"

#: Human token ("public" / "perso" / "sensible") → member — ``Sensitivity`` is an IntEnum whose ``.token``
#: is the french label (D33), so ``--within sensible`` resolves cleanly (never the int ``.value``). Default
#: is the fail-safe ``sensible`` (the decode is local either way; the label only scopes the output).
_SENSITIVITY_BY_TOKEN = {s.token: s for s in Sensitivity}


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - [OPERATOR] ignition (needs the MLX brain)
    parser = argparse.ArgumentParser(
        prog="make local-run",
        description="Dispatch ONE bounded task to Mnémosyne's LOCAL model and PRINT its completion "
        "(the frontier→local delegation surface).",
    )
    parser.add_argument("prompt", help="the bounded, PRECISE task to hand the local model")
    parser.add_argument(
        "--within",
        default=Sensitivity.SENSIBLE.token,
        choices=sorted(_SENSITIVITY_BY_TOKEN),
        help="sensitivity partition to label the output (default: sensible — the decode is local regardless)",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="path to a JSON-schema file — when given, the output is STRUCTURED (grammar-bound JSON)",
    )
    parser.add_argument(
        "--bubble",
        default=_DEFAULT_BUBBLE,
        help=f"the matière-de-travail bubble to run in (default: {_DEFAULT_BUBBLE})",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    within = _SENSITIVITY_BY_TOKEN[args.within]
    schema = Path(args.schema).read_text(encoding="utf-8") if args.schema else None

    print("[local_run] building real_runtime (bge-m3 + Qdrant + MLX brain)…", flush=True)
    runtime = real_runtime()  # brain LOADED (default) — this surface decodes, unlike make search
    api = CoreApi(runtime)
    mode = "structured (JSON schema)" if schema is not None else "free-form"
    print(
        f"[local_run] bubble={args.bubble!r} within={within.token} mode={mode}\n",
        flush=True,
    )
    out = api.run_local(args.prompt, subject=Bubble(args.bubble), within=within, schema=schema)
    print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] ignition
    raise SystemExit(main())
