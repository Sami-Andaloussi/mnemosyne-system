"""Veilleur (Q5) -- the SINGLE-SOURCE contract for a corpus veille pass (pure, no brick, no model).

The veille is a FRONTIER agent's act (see ARCHITECTURE.md for the cohabitation model): it sweeps a
BOUNDED batch of the distilled corpus, extracts principles / skills / hypotheses per fiche, and deposits
each as an INERT draft markdown under ``knowledge/proposals/veille/`` for operator's review -- propose, NEVER
impose (D92). This module owns that contract exactly once: the worklist (which fiches, this pass), the
extraction SCHEMA every finding conforms to, and the printed instructions a frontier host follows.
``make veille`` (``emit_veille.py``, the thin adapter) prints this contract byte-for-byte; nothing here
runs a model or touches a brick -- the extraction itself is the frontier agent's OWN governed reading,
exactly like ``distill-emit`` hands a host the real ``build_prompt``, never a hand-copy
(contract-single-source-emit, the anti-drift lesson).

The worklist is NOT recomputed from scratch here: ``unsurveyed_fiches`` (the ledger,
``mnemosyne.production.veille_ledger``, already built) is the set-difference {on-disk} - {surveyed};
this module only BOUNDS it to :data:`DEFAULT_BATCH` fiches (invariant 16 spirit: a pass stays tractable,
never a "read the whole library" runaway) and turns it into the printed contract. The ledger is
append-only (D44): once a fiche's draft is written, the frontier agent calls ``mark_surveyed`` on it,
and the proactive nerve (``VeilleReview``, ``mnemosyne.production.proposer``) stops nudging for exactly
that fiche.

Code & docstrings are English (D117); the emitted contract is normally kept in the operator's own
language internally (D33) -- this mirror's contract has been translated to English (still ASCII-only,
the same convention ``distill-emit``'s own printed headers already follow)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from mnemosyne.production.veille_ledger import (
    DEFAULT_LEDGER_PATH,
    mark_surveyed,
    unsurveyed_fiches,
)

#: The completion call the contract tells the frontier agent to make - DERIVED from the real symbol
#: (never hand-typed), so a rename / module move of ``mark_surveyed`` updates the emitted contract
#: instead of shipping a dead reference (contract-single-source-emit, the anti-drift lesson).
_MARK_SURVEYED_REF = f"{mark_surveyed.__module__}.{mark_surveyed.__qualname__}"

#: A veille pass is BOUNDED (invariant 16 spirit): survey at most this many fiches per pass, so the
#: frontier agent applying the contract always faces a tractable batch -- never a "whole corpus" runaway.
DEFAULT_BATCH = 20

#: Draft-filename length cap. Real fiche ids run 200+ chars (long book titles), which overruns the APFS
#: 255-byte filename limit -- a slug beyond this is truncated + suffixed with a digest of the FULL id, so
#: the write never fails ENAMETOOLONG and two long-titled fiches never collide onto the same draft path.
_SLUG_MAXLEN = 80

#: Relative marker for where the frontier agent writes ONE inert draft markdown per surveyed fiche.
#: Under ``knowledge/`` so it is gitignored like local corpus data -- this module NEVER
#: creates the directory; the applier (the frontier agent, at veille time) creates it lazily on its
#: first write.
STAGING_DIR = Path("knowledge/proposals/veille")

#: The JSON schema ONE veille finding conforms to (mirrors DISTILL_SCHEMA's shape/spirit). ``kind`` names
#: WHAT was extracted; ``statement`` is the finding itself; ``rationale`` grounds it in the fiche (why it
#: matters / what in the text supports it); ``source`` is the fiche id it came from; ``proposed_test`` is
#: operator's "propose + test" floor -- how a LATER pass could validate the finding, never a bare assertion.
VEILLE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["principle", "skill", "hypothesis"]},
        "statement": {"type": "string", "maxLength": 600},
        "rationale": {"type": "string", "maxLength": 800},
        "source": {"type": "string", "maxLength": 200},
        "proposed_test": {"type": "string", "maxLength": 400},
    },
    "required": ["kind", "statement", "rationale", "source", "proposed_test"],
}

_RULE = "=" * 88
_THIN = "-" * 88


def _slug(fiche_id: str) -> str:
    """Draft-filename stem for a fiche id: lowercase, ``.md`` dropped, path seps/spaces -> ``-``.

    E.g. ``finance/porter.md`` -> ``finance-porter-<digest>``. The readable base is bounded to
    :data:`_SLUG_MAXLEN` (long book titles overrun the APFS 255-byte filename limit) and ALWAYS suffixed
    with a short digest of the FULL id -- so two distinct ids that normalize to the same base (e.g.
    ``a/b.md`` and ``a-b.md``) can never collide onto one draft path and overwrite a finding (D44)."""
    stem = fiche_id[:-3] if fiche_id.endswith(".md") else fiche_id
    base = re.sub(r"[/\s]+", "-", stem.strip().lower()).strip("-")
    digest = hashlib.sha1(fiche_id.encode("utf-8")).hexdigest()[:10]
    return base[:_SLUG_MAXLEN].strip("-") + "-" + digest


def build_worklist(
    distilled_root: Path,
    *,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    batch: int = DEFAULT_BATCH,
) -> tuple[str, ...]:
    """The first ``batch`` fiche ids still awaiting a veille pass (sorted -- ``unsurveyed_fiches``' order).

    Thin: ``unsurveyed_fiches`` already computes the full {on-disk} - {surveyed} set-difference, sorted;
    this only applies the per-pass bound so one ``make veille`` never hands a frontier agent more than it
    can responsibly apply in one sitting."""
    return unsurveyed_fiches(distilled_root, ledger_path=ledger_path)[:batch]


def build_contract(worklist: tuple[str, ...], *, distilled_root: Path) -> str:
    """Assemble the full emitted veille contract -- the ONE thing ``make veille`` prints.

    Pure and offline: given an already-computed worklist and the distilled root, this only formats
    text (no filesystem read of its own). An empty worklist means the whole corpus is already
    surveyed, so the contract collapses to that single fact -- no schema / output / completion
    section, since there is nothing to apply this pass."""
    header = [
        "VEILLE CONTRACT (Q5) -- mine the distilled corpus into principles / skills / hypotheses",
        _RULE,
        "",
        "Propose, NEVER impose (D92): every finding is an INERT draft written to disk,",
        "never applied or promoted here -- only the operator's review promotes a draft.",
        "Guard grant required: READ on knowledge/distilled (read-only access to the already-distilled corpus).",
        "",
    ]
    if not worklist:
        return (
            "\n".join(
                header
                + [
                    "Nothing to survey: no distilled fiche is awaiting a veille pass (an empty corpus, "
                    "or one already fully covered by the system/state/veille_ledger.jsonl ledger)."
                ]
            )
            + "\n"
        )

    lines = list(header)
    lines.append(
        f"WORKLIST -- {len(worklist)} fiche(s) to survey this pass "
        f"(DEFAULT_BATCH cap={DEFAULT_BATCH}):"
    )
    lines.append(_THIN)
    for fiche in worklist:
        lines.append(f"  - {fiche}")
        lines.append(f"      read   : {distilled_root / fiche}")
        lines.append(f"      write  : {STAGING_DIR / (_slug(fiche) + '.md')}")
    lines += [
        "",
        "JSON SCHEMA -- every finding (kind = principle / skill / hypothesis) MUST conform to it:",
        json.dumps(VEILLE_SCHEMA, indent=2, ensure_ascii=False),
        "",
        "OUTPUT -- for EACH fiche listed above: read it IN FULL, then write ONE inert draft",
        "at the 'write' path shown above, with a small frontmatter:",
        _THIN,
        "---",
        'source: "<fiche id>"',
        'date: "<current date, YYYY-MM-DD>"',
        "status: draft",
        "---",
        _THIN,
        "then the list of your findings (kind/statement/rationale/source/proposed_test), EACH",
        "conforming to the schema above.",
        "",
        "COMPLETION -- once (and only once) a fiche's draft is written, mark it",
        "surveyed so the proactive nerve stops flagging it again (non-repeating):",
        f'  {_MARK_SURVEYED_REF}("<fiche id>")',
    ]
    return "\n".join(lines) + "\n"
