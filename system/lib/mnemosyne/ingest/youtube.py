"""YouTube transcript core (sujet 3) — the BRICK-FREE, deterministic logic behind the TranscriptFetcher port.

Three pure functions, testable with nothing installed and no network (D126), so the fetch engine (yt-dlp) can
stay a thin sole-importer adapter around them:

* :func:`parse_youtube_ref` — a URL (``watch?v=`` / ``youtu.be`` / ``shorts`` / ``embed`` / ``live``) or a bare
  11-char id → the canonical video id. Refuses anything else (``ValueError``) rather than guessing.
* :func:`parse_timedtext_json3` — YouTube's ``json3`` timedtext payload → verbatim :class:`~mnemosyne.ports.transcript.TranscriptCue`\\ s.
* :func:`transcript_to_markdown` — a :class:`~mnemosyne.ports.transcript.FetchedTranscript` → an operator-facing
  ``.md``: a provenance header + the words RESTRUCTURED (grouped into readable paragraphs), never reformulated
  (the restructure-not-reformulate rule / P3). Auto-captions are MARKED non-verbatim (honesty on provenance).

Decisions: AV1 (video = a source of more) · D140 (.md-first) · D100-3 (transcript is untrusted DATA) · D126
(brick-free, testable core) · restructure-not-reformulate (verbatim, no LLM paraphrase). Code & docstrings
English (D117); the produced ``.md`` and its provenance marks are French — they land in the operator's corpus
(D117 produit).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Final
from urllib.parse import parse_qs, urlparse

from ..ports import FetchedTranscript, TranscriptCue, TranscriptFetcher
from ..provenance import AUTO_CAPTION_MARK

#: A YouTube video id is exactly 11 chars of the URL-safe base64 alphabet.
_VIDEO_ID_RE: Final = re.compile(r"^[A-Za-z0-9_-]{11}$")

#: Path prefixes that carry the id as the FIRST segment on ``youtube.com`` (``/shorts/<id>``, ``/embed/<id>``…).
_PATH_ID_PREFIXES: Final = frozenset({"shorts", "embed", "live", "v"})

#: Verbatim cues are grouped into paragraphs by this wall-clock window, for readability WITHOUT paraphrase.
_PARAGRAPH_WINDOW_S: Final = 30.0


def _one_line(text: str) -> str:
    """Collapse whitespace / newlines to a single line: untrusted YouTube metadata (a title, a channel name)
    can then never break the ``.md`` layout with an injected heading or blockquote (D100-3, the sujet-2
    zero-trust discipline applied to provenance)."""
    return " ".join(text.split())


def parse_youtube_ref(ref: str) -> str:
    """Extract the canonical 11-char video id from a YouTube URL or a bare id; raise ``ValueError`` otherwise.

    Accepts ``https://www.youtube.com/watch?v=<id>`` (with any extra query params), ``https://youtu.be/<id>``,
    ``https://www.youtube.com/{shorts,embed,live,v}/<id>``, the ``m.`` / ``music.`` hosts, and a bare ``<id>``.
    Deliberately STRICT — a playlist URL, a non-YouTube host, or a malformed id raises rather than guessing, so
    a bad ref fails loud at the door instead of fetching the wrong video."""
    ref = ref.strip()
    if _VIDEO_ID_RE.match(ref):
        return ref  # already a bare id
    parsed = urlparse(ref if "//" in ref else f"https://{ref}")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    candidate = ""
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/", 1)[0]
    elif host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in _PATH_ID_PREFIXES:
                candidate = parts[1]

    if _VIDEO_ID_RE.match(candidate):
        return candidate
    raise ValueError(f"no YouTube video id found in: {ref!r}")


def parse_timedtext_json3(payload: str) -> tuple[TranscriptCue, ...]:
    """Parse YouTube's ``json3`` timedtext payload into verbatim cues (document order).

    ``json3`` shape: ``{"events": [{"tStartMs": int, "segs": [{"utf8": str}, ...]}, ...]}``. Each event's text
    is the concatenation of its segment ``utf8`` runs; events with no ``segs`` (or whose text is blank once
    stripped — the newline-only spacer events) are dropped. ``tStartMs`` → ``start_s`` in seconds. Raises
    ``ValueError`` on a JSON payload that is not a json3 object (e.g. an error page parsed as a JSON array), or
    the stdlib ``json`` error on a non-JSON payload — a corrupt fetch fails loud, never a silent empty
    transcript."""
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError(f"unexpected timedtext json3 payload (not an object): {type(data).__name__}")
    cues: list[TranscriptCue] = []
    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue
        text = "".join(seg.get("utf8", "") for seg in segs).strip()
        if not text:
            continue
        cues.append(TranscriptCue(start_s=event.get("tStartMs", 0) / 1000.0, text=text))
    return tuple(cues)


def _group_paragraphs(cues: Sequence[TranscriptCue], *, dedupe_repeats: bool) -> list[str]:
    """Group verbatim cues into readable paragraphs by :data:`_PARAGRAPH_WINDOW_S`.

    Each cue's text is whitespace-collapsed and appended until the window elapses — this RESTRUCTURES the words
    (regroups them) but never rewrites them (no paraphrase). When ``dedupe_repeats`` is set (auto-captions
    ONLY), a cue equal to the one just kept is skipped — YouTube's ASR re-emits the previous line as a
    rolling-window artefact. It is deliberately NOT applied to MANUAL subtitles, where a repeat is the author's
    intent (a refrain, an insistence) and must stay verbatim (P3 — ③ audit MINEUR-5)."""
    paragraphs: list[str] = []
    current: list[str] = []
    window_start: float | None = None
    last_text = ""
    for cue in cues:
        text = " ".join(cue.text.split())
        if not text or (dedupe_repeats and text == last_text):
            continue
        last_text = text
        if window_start is None:
            window_start = cue.start_s
        if current and cue.start_s - window_start >= _PARAGRAPH_WINDOW_S:
            paragraphs.append(" ".join(current))
            current = []
            window_start = cue.start_s
        current.append(text)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def transcript_to_markdown(transcript: FetchedTranscript) -> str:
    """Render a :class:`FetchedTranscript` as an operator-facing ``.md``: provenance header + verbatim body.

    The header carries the provenance (title, channel, URL, language) so the datum is self-describing; an
    auto-captioned transcript gets the :data:`~mnemosyne.provenance.AUTO_CAPTION_MARK` so a reader SEES it is
    YouTube's ASR guess, never mistaken for human verbatim (the sujet-2 discipline). The provenance fields are
    collapsed to one line
    (:func:`_one_line`) so an untrusted title can't inject a heading / blockquote into the layout; the BODY, by
    contrast, stays VERBATIM (untrusted DATA, D100-3): a cue that reads like ``# heading`` is NOT sanitized,
    because altering it would break the P3 verbatim — downstream treats a transcript as data, never as trusted
    structure. The body is the words grouped into paragraphs (:func:`_group_paragraphs`) — restructured, never
    reformulated. A transcript with no cues renders the header plus an explicit
    ``_(no subtitles available)_`` note (honest emptiness, never a silent blank)."""
    header = [
        f"# {_one_line(transcript.title)}",
        "",
        f"> **Source YouTube** — {_one_line(transcript.uploader)}",
        f"> {_one_line(transcript.webpage_url)}",
        f"> Langue : {_one_line(transcript.language)}",
    ]
    if transcript.auto_generated:
        header.append(f"> {AUTO_CAPTION_MARK}")

    paragraphs = _group_paragraphs(transcript.cues, dedupe_repeats=transcript.auto_generated)
    body = "\n\n".join(paragraphs) if paragraphs else "_(no subtitles available)_"
    return "\n".join(header) + "\n\n" + body + "\n"


def youtube_fetcher_if_available() -> TranscriptFetcher | None:
    """Best-effort YouTube fetcher for real ingestion: the yt-dlp adapter when the brick is installed, else
    ``None`` (D126 — a bricks-less runtime and the suite stay green; yt-dlp is an OPTIONAL ``--extra bricks``).

    Loading the fetcher opens NOTHING. An outbound fetch stays deny-by-default at the Guard until the operator
    allow-lists the host in the policy zone (invariant 5 / 21): a loaded fetcher over an EMPTY egress
    allow-list still refuses every fetch. The allow-list is the switch, not this import — so wiring the
    capability in ``real_runtime`` is safe by construction (:meth:`CoreApi.capture_youtube` is the sole,
    Guard-mediated door). Imported LAZILY through the sole importer so this stays brick-free (D103 / D126)."""
    try:
        from .youtube_ytdlp import (
            connect_ytdlp,
        )  # sole importer; ``import yt_dlp`` happens inside it

        return connect_ytdlp()
    except ImportError:
        return (
            None  # the ``--extra bricks`` optional is not installed — degrade, never crash (D126)
        )
