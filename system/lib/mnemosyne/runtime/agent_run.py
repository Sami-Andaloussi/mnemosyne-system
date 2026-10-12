"""agent_run ((3)-5b / D98 / [OPERATOR]) - the live agent shot: reason over the library, end-to-end.

Ignition of the governed agent loop with the REAL brain (MLX) + the ``search_memory`` tool over
Mnémosyne's own :data:`~mnemosyne.ingest.library.KNOWLEDGE_BUBBLE` library. NOT run in CI (needs the
bricks + weights + a running Qdrant); a ``[OPERATOR]`` gesture like ``make calibrate``. Run::

    make agent                                             # the default cross-domain question
    python -m mnemosyne.runtime.agent_run "<your question>"

It builds :func:`~mnemosyne.runtime.bootstrap.real_runtime` (bge-m3 + Qdrant + MLX ...), runs
:func:`~mnemosyne.agents.loop.run_agent` AS the knowledge bubble - so the library's own bubble reads
its own docs (intra-bubble + declared domains + the ``sensible`` partition it was ingested in) - and
prints the grounded answer. ``search_memory`` must be sanctioned in ``tools.toml`` (D114-(5)) or the Guard
refuses it. Code & docstrings English (D117); the question defaults to French (the user's language).
"""

from __future__ import annotations

import sys

from ..agents.loop import run_agent
from ..ingest.library import KNOWLEDGE_BUBBLE
from .bootstrap import real_runtime
from .memory_search import SEARCH_MEMORY

#: The agent's standing instructions: ground every claim in retrieved passages, admit the gaps, cite.
_INSTRUCTIONS = (
    "You are Mnémosyne's agent, answering from the user's OWN reference library. Use the search_memory "
    "tool to look things up: search for each concept you need, read the returned passages, and ground "
    "your answer in them - cross several sources when the question spans domains. If search_memory "
    "returns 'no confident memory', say what you could not find rather than inventing. Cite the doc ids "
    "you relied on. Answer in the user's language (French)."
)

#: The first live task the user chose: a cross-domain synthesis that forces the agent to fuse sources.
_DEFAULT_QUESTION = (
    "En croisant mes sources, quels principes de gestion du risque et de dimensionnement en finance "
    "(par ex. le critère de Kelly, le risque de ruine) éclairent la gestion de l'incertitude et de la "
    "calibration de la confiance dans les systèmes de ML / retrieval (par ex. seuils, abstention) ?"
)


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - [OPERATOR] ignition (bricks + weights)
    args = sys.argv[1:] if argv is None else argv
    question = args[0] if args else _DEFAULT_QUESTION
    print("[agent_run] building real_runtime (bge-m3 + Qdrant + MLX weights)...", flush=True)
    runtime = real_runtime()
    print(
        f"[agent_run] subject={KNOWLEDGE_BUBBLE!r}\n[agent_run] question={question!r}\n", flush=True
    )
    answer = run_agent(
        runtime,
        question,
        subject=KNOWLEDGE_BUBBLE,
        tool_names=(SEARCH_MEMORY,),
        instructions=_INSTRUCTIONS,
    )
    print("\n================ ANSWER ================\n")
    print(answer.payload)
    print(f"\n[label] sensitivity={answer.label.sensitivity}  bubble={answer.label.bubble}")
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] ignition
    raise SystemExit(main())
