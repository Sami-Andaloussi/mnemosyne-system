"""Ingestion golden-set ((3)-4) - a chiffered FIDELITY bar for any source reader (D125-B6).

The ingestion lot does NOT claim a perfect OCR. It poses a *measurable* bar: score the configured
:class:`~mnemosyne.ports.source.SourceReader` against a labelled golden-set - how faithfully it
recovers known text from known bytes - and, below a threshold, mark the extraction UNTRUSTED. The
text is still ingested (truth-first: the raw source is preserved in the benne, D85), but the receipt
FLAGS it low-fidelity - never silently trusting a doubtful OCR (F3). This mirrors the EXTRACTION
golden (:mod:`~mnemosyne.production.golden`) on the other axis: that one scores fact-from-text, this
one text-from-source; both are fail-closed, brick-free judges that arbitrate any engine (D69 / D109).

**Metric** = token-level precision / recall / F1 over expected vs recovered text (olmOCR-Bench in
spirit: does the reader recover the *words*, not exact bytes). Recall guards against a reader that
DROPS text, precision against one that INVENTS it; a multiset (bag-of-tokens) overlap so a word
recovered too few / too many times is scored honestly. The scorer takes the reader as a callable, so
it measures the stub (utf-8 decode = perfect on text bytes, garbage on non-utf-8) exactly as it will
measure the real Docling / WhisperKit once installed (D126).

**Honesty (F3).** :data:`FIDELITY_SEED` is a hand-labelled SEED, not étage (2)'s corpus - it proves the
mechanism (a faithful reader scores 1.0) and pins the wiring; expanding it against a real OCR corpus,
and measuring the real reader to SET the runtime trust flag (``Runtime.source_extraction_trusted``),
is traced debt at ignition. :data:`MIN_INGEST_FIDELITY` is provisional, to be calibrated like the
retrieval ``min_score`` and the extraction ``MIN_EXTRACTION_F1`` were (D68 / D69).

Decisions: D125-B6 (fidelity golden, olmOCR-Bench) - D69 (calibrate against a golden set) - D85 (raw
preserved) - D100 (untrusted extraction under the net) - D58 (below the bar => honest flag, no silent
trust). Code & docstrings English (D117).
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ..ports import Source

#: Provisional token-F1 bar a reader must clear to be trusted with an extraction (else flagged low
#: fidelity). Calibrate against a real (2) OCR corpus (olmOCR-Bench style), like ``min_score`` (0.55)
#: and ``MIN_EXTRACTION_F1`` (0.6) were - a reader below it still ingests, but honestly flagged.
MIN_INGEST_FIDELITY = 0.7

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> tuple[str, ...]:
    """Lowercased word tokens - the fidelity substrate (order-free, so it proxies OCR recovery)."""
    return tuple(m.group(0).lower() for m in _TOKEN.finditer(text))


@dataclass(frozen=True, slots=True)
class FidelityCase:
    """One labelled example: the raw ``source`` and the text a faithful reader SHOULD recover."""

    source: Source
    expected_text: str


@dataclass(frozen=True, slots=True)
class FidelityScore:
    """The measured fidelity of a source reader over a golden-set - precision / recall / F1 (D69)."""

    precision: float
    recall: float
    f1: float
    cases: int

    @property
    def trusted(self) -> bool:
        """Whether the reader clears :data:`MIN_INGEST_FIDELITY` - the low-fidelity-flag decision."""
        return self.f1 >= MIN_INGEST_FIDELITY


def score_fidelity(read: Callable[[Source], str], cases: Sequence[FidelityCase]) -> FidelityScore:
    """Score ``read`` against ``cases`` - micro-averaged token precision / recall / F1 (D69).

    ``read`` is any Source->text callable (the real reader behind the port, or a test double), so the
    scorer never imports a brick (D126). A golden-set with NOTHING to recover (empty, or every case
    expecting no text) is fail-CLOSED (F1 0, untrusted): a missing or mis-configured golden can never
    vacuously certify a reader (D69) - the same fail-closed posture as the extraction golden."""
    if not any(_tokens(case.expected_text) for case in cases):
        return FidelityScore(precision=0.0, recall=0.0, f1=0.0, cases=len(cases))
    true_positive = false_positive = false_negative = 0
    for case in cases:
        try:
            recovered = read(case.source)
        except Exception:  # noqa: BLE001 - a reader that raises on a case is a FAILED recovery, not an
            recovered = (
                ""  # aborted run: it scores as recall loss (untrusted), never certified by silence
            )
        got = Counter(_tokens(recovered))
        want = Counter(_tokens(case.expected_text))
        true_positive += sum((got & want).values())  # multiset overlap: min count per token
        false_positive += sum((got - want).values())  # invented / over-recovered tokens
        false_negative += sum((want - got).values())  # dropped / under-recovered tokens
    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive)
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative)
        else 1.0
    )
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return FidelityScore(precision=precision, recall=recall, f1=f1, cases=len(cases))


#: A hand-labelled SEED (F3: not étage (2)'s corpus) - enough to prove the bar bites and pin the
#: wiring. With the utf-8 stub these decode perfectly (F1 1.0, trusted); a non-utf-8 / lossy reader
#: scores low -> honest low-fidelity flag. Expand against a real OCR corpus at ignition (traced debt).
FIDELITY_SEED: tuple[FidelityCase, ...] = (
    FidelityCase(
        Source(
            ref="note.txt",
            data="Sample notes are indexed locally.".encode("utf-8"),
            mime="text/plain",
        ),
        expected_text="Sample notes are indexed locally.",
    ),
    FidelityCase(
        Source(
            ref="memo.txt",
            data="The service runs scheduled backups.".encode("utf-8"),
            mime="text/plain",
        ),
        expected_text="The service runs scheduled backups.",
    ),
)


def load_fidelity_golden(path: Path | str) -> tuple[FidelityCase, ...]:
    """Load an ingestion fidelity golden set from a JSON file ((3) ignition).

    The local calibration cases expand the hand-labelled :data:`FIDELITY_SEED` to read off the reader's
    token-F1 over OCR output.

    Symmetric to :func:`~mnemosyne.stores.golden.load_retrieval_golden`. The file lives OUTSIDE git
    (``knowledge/golden/``, gitignored): its bytes and expected text can be verbatim source material,
    so they must never enter tracked history - the same garde-fou as the raw shelf and the bubbles
    (D71 / D137). Shape: a non-empty JSON list of objects
    ``{"ref": str, "data_b64": str, "mime": str, "expected_text": str}`` - ``data_b64`` is the raw
    source bytes base64-encoded (so a scanned-PDF page travels inline, no companion file). This is how
    the MANDATORY image-only scan case rides in: its bytes carry no text layer, so
    the bar only clears if the OCR reader actually recovers the text. Unknown keys (e.g. an inline
    ``_note`` / ``_kind``) are ignored, never a parse failure.

    Fail-closed (F3 / D100): a malformed file RAISES (a :class:`ValueError` - including invalid base64 -
    or a ``JSONDecodeError`` / ``OSError`` from the read) rather than silently yielding a laxer or empty
    golden that could vacuously certify a reader - a broken golden must STOP the calibration, never
    quietly weaken the bar. (An all-``expected_text``-empty golden is still handled by
    :func:`score_fidelity`'s own fail-safe: nothing to recover => F1 0, untrusted.) An ABSENT file is the
    caller's concern: the ignition run falls back to :data:`FIDELITY_SEED` only when no real golden is in
    place yet (the D126 default), never on a present-but-corrupt one."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"fidelity golden {path}: expected a non-empty JSON list of cases")
    cases: list[FidelityCase] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"fidelity golden {path}: case {i} is not a JSON object")
        ref = item.get("ref")
        mime = item.get("mime")
        expected_text = item.get("expected_text")
        data_b64 = item.get("data_b64")
        for name, value in (("ref", ref), ("mime", mime), ("data_b64", data_b64)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"fidelity golden {path}: case {i} field {name!r} must be a non-empty string"
                )
        if not isinstance(expected_text, str):
            raise ValueError(
                f"fidelity golden {path}: case {i} field 'expected_text' must be a string"
            )
        try:
            data = base64.b64decode(data_b64, validate=True)
        except (
            binascii.Error,
            ValueError,
        ) as exc:  # corrupt base64 => STOP, never a silent empty source
            raise ValueError(
                f"fidelity golden {path}: case {i} has invalid base64 in 'data_b64'"
            ) from exc
        cases.append(
            FidelityCase(source=Source(ref=ref, data=data, mime=mime), expected_text=expected_text)
        )
    return tuple(cases)
