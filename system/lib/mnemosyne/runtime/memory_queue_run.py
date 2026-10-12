"""memory_queue_run (item 2 / D115-AV3) — LIST the living-memory validation queue for the operator.

The READ half of the "correct" side of show→propose→correct: a frontier captures learnings INERT (``make
remember``), and THIS shows what is pending the operator's gesture (``make memory-validate`` acts on it). Brain-free
(``real_runtime(load_brain=False)``): the queue is rebuilt at cold start from the human-layer journal + the
proposals ledger (D82 / item 2), so a learning captured in an EARLIER session appears here — the durability
the ledger closed (before it, a proposal died with its short-lived process).

    make memory-queue

Read-only: it lists, it never validates (that is ``make memory-validate``, an explicit gesture). Code &
docstrings English (D117); NOT run in CI (reads the durable state)."""

from __future__ import annotations

#: Cap the previewed learning text so a long one does not flood the terminal — the full text is intact in the
#: ledger and shown when validating; this is a glance, not the record.
_PREVIEW_CHARS = 200


def main() -> int:  # pragma: no cover - [OPERATOR] reads the durable state (bricks + a running Qdrant)
    from ..api import CoreApi
    from .bootstrap import real_runtime

    runtime = real_runtime(load_brain=False)
    api = CoreApi(runtime)
    pending = api.pending_fiches()
    if not pending:
        print("[memory-queue] empty — no learning awaits your validation (propose, never impose).")
        return 0
    print(
        f"[memory-queue] {len(pending)} learning(s) await your gesture — validate with "
        "`make memory-validate ID=<id>`, reject with the same + `DISMISS=1`:\n"
    )
    for fiche in pending:
        preview = " / ".join(sorted(fiche.content))
        if len(preview) > _PREVIEW_CHARS:
            preview = preview[: _PREVIEW_CHARS - 1] + "…"
        print(
            f"  · id={fiche.id}  [{fiche.ftype}]  {fiche.label.sensitivity.token}/{fiche.label.bubble}"
        )
        print(f"      {preview}")
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] entrypoint
    raise SystemExit(main())
