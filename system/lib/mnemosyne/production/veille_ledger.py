"""The veille ledger (Q5) — which distilled fiches a frontier veille pass has ALREADY surveyed.

Soul ⑤'s richest source is the *veille*: a FRONTIER agent (Claude Code — the master that reads, per
the cohabitation doctrine) sweeps the distilled corpus, extracts principles / skills / hypotheses, and
deposits them as INERT drafts for the operator (propose, never impose, D92). For the proactive nerve to
nudge "there is veille to do" WITHOUT crying wolf, it must know what was ALREADY surveyed — otherwise it
would re-propose the whole corpus every session (the perpetual-false-nudge failure the tick smoke caught).

This module is that memory: an APPEND-ONLY ledger (``system/state/veille_ledger.jsonl``, gitignored by
the ``system/state/*.jsonl`` barrier, D82) recording the id of each fiche a pass has surveyed. It is
NON-DESTRUCTIVE (D44): a pass only ever appends; nothing is rewritten or erased. The fiche id is its
path RELATIVE to the distilled root (e.g. ``finance/porter-competitive-strategy.md``) — stable,
human-readable, and directly resolvable back to the file to read.

The read side is FAIL-OPEN (a missing ledger, a blank or garbled line ⇒ "not surveyed", never a crash):
the worst a corrupt line can do is re-surface a fiche for another (idempotent, non-destructive) veille
pass. Pure and brick-free (D126) — every function takes explicit paths so the suite drives it against a
temp shelf. Code & docstrings English (D117)."""

from __future__ import annotations

import json
from pathlib import Path

#: Repo root from this module (``system/lib/mnemosyne/production/veille_ledger.py`` → parents[4] = repo).
_REPO_ROOT = Path(__file__).resolve().parents[4]
#: The append-only surveyed-fiche ledger. Under ``system/state`` ⇒ gitignored (D82), a per-machine memory.
DEFAULT_LEDGER_PATH = _REPO_ROOT / "system" / "state" / "veille_ledger.jsonl"

#: Stems (case-insensitive) that are NOT fiches — navigation / index files the reorg scattered on the
#: shelf. Counting them would manufacture a false "veille due" nudge (the tick-README lesson), so skip.
_NON_FICHE_STEMS = frozenset({"readme", "moc", "index"})


def _is_fiche(path: Path) -> bool:
    """A real distilled fiche — a ``.md`` file that is not a dot-file nor a navigation / index stub."""
    return (
        path.is_file()
        and not path.name.startswith(".")
        and path.stem.lower() not in _NON_FICHE_STEMS
    )


def fiche_id(distilled_root: Path, fiche_path: Path) -> str:
    """The stable id of a fiche — its POSIX path relative to the distilled root (the ledger key)."""
    return fiche_path.resolve().relative_to(distilled_root.resolve()).as_posix()


def surveyed_ids(ledger_path: Path = DEFAULT_LEDGER_PATH) -> frozenset[str]:
    """The ids of fiches already surveyed by a veille pass — read the append-only ledger (fail-open).

    A missing ledger is an empty set (nothing surveyed yet). A blank or non-conforming line is SKIPPED,
    never fatal: the ledger is a best-effort memory, and the fail-safe direction is to survey again
    (idempotent) rather than to crash the proactive pass over one bad byte."""
    if not ledger_path.is_file():
        return frozenset()
    ids: set[str] = set()
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            continue  # a garbled line never sinks the read — fail-open (re-survey, never crash)
        fiche = record.get("fiche") if isinstance(record, dict) else None
        if isinstance(fiche, str) and fiche:
            ids.add(fiche)
    return frozenset(ids)


def mark_surveyed(fiche: str, *, ledger_path: Path = DEFAULT_LEDGER_PATH) -> None:
    """Record that a fiche has been surveyed — append one line (NON-DESTRUCTIVE, D44), idempotent.

    Appends ``{"fiche": <id>}`` to the ledger, creating it (and ``system/state``) on first use. If the
    fiche is already recorded, it is a no-op — the ledger never grows an identical line twice, and it
    NEVER rewrites or removes history (append-only is the whole non-destructive guarantee)."""
    if fiche in surveyed_ids(ledger_path):
        return  # already surveyed — no duplicate line (still strictly append-only)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"fiche": fiche}, ensure_ascii=False) + "\n")


def unsurveyed_fiches(
    distilled_root: Path, *, ledger_path: Path = DEFAULT_LEDGER_PATH
) -> tuple[str, ...]:
    """The veille WORKLIST — distilled fiche ids present on the shelf but NOT yet in the ledger (sorted).

    The set difference ``{fiches on disk} - {surveyed}``. Sorted for a deterministic worklist (the emit
    prints it, the suite asserts on it). An absent distilled root ⇒ empty (nothing to survey)."""
    if not distilled_root.is_dir():
        return ()
    done = surveyed_ids(ledger_path)
    present = {
        fiche_id(distilled_root, path) for path in distilled_root.rglob("*.md") if _is_fiche(path)
    }
    return tuple(sorted(present - done))


def unsurveyed_fiche_count(distilled_root: Path, *, ledger_path: Path = DEFAULT_LEDGER_PATH) -> int:
    """How many distilled fiches still await a veille pass — the META-signal :class:`VeilleReview` reports.

    A COUNT only: the proactive source is handed THIS, never the fiche ids or their content, so it
    structurally cannot leak matière across the cloisonnement (invariant 22 / D66)."""
    return len(unsurveyed_fiches(distilled_root, ledger_path=ledger_path))
