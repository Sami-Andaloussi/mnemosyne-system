"""remember_run (item 2 / D115-AV3) - the "apprendre en utilisant" door for a FRONTIER host.

The ACTIVE half of learn-while-using: as a frontier (Claude Code / Codex) works, it recognises a durable,
reusable learning - a stable fact the user states, a work preference, a correction - and deposits it, INERT,
into the living-memory validation queue::

    make remember LEARNING="user prefers make targets over ad-hoc scripts for any repeatable action"
    python -m mnemosyne.runtime.remember_run "<the learning>" [--within perso] [--bubble perso]

Propose, never impose (D92 / D100): the learning lands PROPOSED - it reinjects into NO answer until the user's
validation gesture. What makes it "automatic" is NOT this command firing on its own; it is the essence memo
(item 6) reminding a frontier to run it each time it finishes a task. The anti-noise is structural: the
fiche id is content-scoped, so re-proposing the same learning is idempotent and a dismissed learning stays
closed (:func:`~mnemosyne.production.learning_fiche`).

WHAT to capture (avoid the noise): a DURABLE, reusable learning - not ephemeral chatter, not a restatement
of what a file already says. A learning is a sentence or two; a whole document is ``make ingest`` /
``capture``'s job, not this. WHEN: at the end of a task, when something worth carrying to the next session
emerged.

Retrieval-free and brain-free (``real_runtime(load_brain=False)``): a pure living-memory write, persisted
through the durable proposals ledger (:class:`~mnemosyne.production.proposals_ledger.ProposalsLedger`,
``system/state/proposals.jsonl``) and replayed at every cold start (item 2 / D82) - so the capture reaches
the user's validation queue in a LATER session instead of dying with this short-lived process. Its counterpart is
``make memory-queue`` (list the queue) + ``make memory-validate`` (validate / dismiss). Code & docstrings
English (D117); the learning text is in whatever language it was stated. NOT run in CI (writes the ledger)."""

from __future__ import annotations

import argparse
import sys

from ..api import CoreApi
from ..ports import Bubble, Sensitivity
from .bootstrap import real_runtime

#: The bubble a frontier-captured learning lands in by default - ``perso`` (a learning about the user / how to
#: work for them is personal). ``--bubble`` overrides it for a work-scoped learning.
_DEFAULT_BUBBLE = "perso"

#: Human token ("public" / "perso" / "sensible") -> member - ``Sensitivity`` is an IntEnum whose ``.token``
#: is the french label (D33). Default ``perso``: a personal learning, local by construction (invariant 1);
#: the label is raise-only at the store, so this is a floor, never a declassification.
_SENSITIVITY_BY_TOKEN = {s.token: s for s in Sensitivity}


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - [OPERATOR] ignition (writes the journal)
    parser = argparse.ArgumentParser(
        prog="make remember",
        description="Deposit ONE concise LEARNING into living memory, INERT, awaiting the user's validation "
        "(the learn-while-using door).",
    )
    parser.add_argument(
        "learning", help="the concise, durable learning to remember (a sentence or two)"
    )
    parser.add_argument(
        "--within",
        default=Sensitivity.PERSO.token,
        choices=sorted(_SENSITIVITY_BY_TOKEN),
        help="sensitivity to label the learning (default: perso - a personal learning, kept local)",
    )
    parser.add_argument(
        "--bubble",
        default=_DEFAULT_BUBBLE,
        help=f"the bubble the learning belongs to (default: {_DEFAULT_BUBBLE})",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    within = _SENSITIVITY_BY_TOKEN[args.within]

    print("[remember] building real_runtime (living memory only; no MLX brain)...", flush=True)
    runtime = real_runtime(load_brain=False)
    api = CoreApi(runtime)
    fiche = api.remember(args.learning, subject=Bubble(args.bubble), within=within)
    print(
        f"[remember] PROPOSED learning {fiche.id} in bubble={args.bubble!r} within={within.token} "
        f"(state={fiche.state}).\n"
        "It is INERT - it reinjects into no answer until you validate it in the living-memory queue "
        "(propose, never impose)."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] ignition
    raise SystemExit(main())
