"""yt-dlp transcript adapter (sujet 3) - fetch a YouTube video's subtitles behind the TranscriptFetcher port.

The default engine for :class:`~mnemosyne.ports.transcript.TranscriptFetcher`: it wraps **yt-dlp** (Unlicense;
``oss_registry.md``), the reference tool for reading YouTube metadata + subtitle tracks. SOLE-importer adapter
(D103 / invariant 20): the one module allowed to touch ``yt_dlp``, imported LAZILY so the suite stays green
with no brick installed (D126). Everything that reaches the network is ``# pragma: no cover`` - it runs only at
(3) ignition (``uv add --optional bricks yt-dlp``), confronted to the real API by the ``make youtube-pilot``
diagnostic, not by CI.

**Outbound - NOT local (the sujet-3 nuance).** Unlike the sujet-2 VLM or WhisperKit (both LOCAL), this adapter
reaches OUT to YouTube. It exfiltrates nothing ``sensible`` (invariant 1 holds - it pulls a PUBLIC datum in),
but it IS an external access, so at wiring time it is routed through the Guard's external channel
(deny-by-default, invariant 5), and the transcript it returns is UNTRUSTED third-party text (D100-3): captured
and classified at ingestion (D101), never obeyed as instruction.

**Honesty (F3).** The exact shape of yt-dlp's ``extract_info`` result (the ``subtitles`` /
``automatic_captions`` dicts, the ``json3`` track url) is a best-guess taken from the documented format, with
an explicit ALLUMAGE NOTE to confirm at the pilot - not invented certainty. The pure track-selection and the
json3 parse (:mod:`~mnemosyne.ingest.youtube`) are unit-tested; only the network round-trip is uncovered.

Decisions: AV1 (video = a source of more)  -  D103 (sole importer)  -  D126 (import-safe, brick-free suite)  -
invariant 5 (external access via the Guard)  -  invariant 1 / D66 (nothing sensible leaves)  -  D100-3 (untrusted)
 -  restructure-not-reformulate (verbatim subtitles). Code & docstrings English (D117).
"""

from __future__ import annotations

from typing import Final, NamedTuple

from ..ports import FetchedTranscript, TranscriptFetcher
from .youtube import parse_timedtext_json3, parse_youtube_ref

#: Preferred subtitle languages, in order - French first, then English (configured corpus). A ``[OPERATOR]`` config.
_DEFAULT_LANGUAGES: Final = ("fr", "en")
#: The clean, structured timedtext format we parse (:func:`~mnemosyne.ingest.youtube.parse_timedtext_json3`).
_SUBTITLE_FORMAT: Final = "json3"
_TIMEOUT_S: Final = 60.0  # the timedtext payload is small; a generous cap for a slow network


class _SelectedTrack(NamedTuple):
    """One chosen subtitle track: where to fetch it, its language, and whether it is an auto-caption."""

    url: str
    language: str
    auto_generated: bool


def _langs_matching(tracks: dict[str, list[dict[str, str]]], lang: str) -> list[str]:
    """Track-language keys for a preferred base code: the EXACT key first, then regional variants (``en-US``,
    ``fr-FR``...). So a preference for ``en`` still finds a MANUAL ``en-US`` track - a very common shape for human
    subtitles - instead of falling through to an ASR auto-caption or an empty transcript ((3) audit MAJEUR-1)."""
    exact = [key for key in tracks if key == lang]
    regional = [key for key in tracks if key != lang and key.split("-", 1)[0] == lang]
    return exact + regional


def _select_track(
    subtitles: dict[str, list[dict[str, str]]],
    automatic_captions: dict[str, list[dict[str, str]]],
    languages: tuple[str, ...],
) -> _SelectedTrack | None:
    """Pick the best ``json3`` track: MANUAL subtitles before auto-captions, in language order. Pure (tested).

    Manual subtitles are the author's verbatim words, so they win over YouTube's ASR auto-captions even when
    that means a less-preferred (or merely regional) language; within each kind, ``languages`` order decides,
    and for each language an exact match is preferred over a regional variant (:func:`_langs_matching`). Returns
    ``None`` when no ``json3`` track exists in any requested language (the caller then yields an empty
    transcript). The reported language is the track's actual key (e.g. ``en-US``)."""
    for auto_generated, tracks in ((False, subtitles), (True, automatic_captions)):
        for lang in languages:
            for track_lang in _langs_matching(tracks, lang):
                for fmt in tracks[track_lang]:
                    if fmt.get("ext") == _SUBTITLE_FORMAT and fmt.get("url"):
                        return _SelectedTrack(fmt["url"], track_lang, auto_generated)
    return None


def connect_ytdlp(
    *, languages: tuple[str, ...] = _DEFAULT_LANGUAGES
) -> TranscriptFetcher:  # pragma: no cover - needs the brick ((3) ignition)
    """Wrap yt-dlp as a :class:`TranscriptFetcher` (the ``[OPERATOR]`` allumage seam, sujet 3).

    Imports ``yt_dlp`` LAZILY, so this module is import-safe without it (D126). OUTBOUND: wired behind the
    Guard's external channel (invariant 5); the returned text is untrusted DATA (D100-3), classified at
    ingestion (D101).

    ALLUMAGE NOTE (``extract_info`` shape CONFIRMED at pilot 1; the ``ydl.urlopen`` fetch is the pilot-1 fix):
    ``yt_dlp.YoutubeDL({"skip_download": True, "quiet": True}).extract_info(url, download=False)`` returns an
    ``info`` dict exposing ``title``, ``uploader`` (or ``channel``), ``webpage_url``, and the subtitle maps
    ``subtitles`` / ``automatic_captions`` shaped ``{lang: [{"ext": "json3", "url": ...}, ...]}``. The timedtext
    payload is fetched with ``ydl.urlopen(url).read()`` - NOT a bare urllib, which YouTube ``429``\\ s for its
    naked ``Python-urllib`` signature (pilot 1). Confirm at the next pilot that ``ydl.urlopen`` is exposed on
    the YoutubeDL instance (it is yt-dlp's own request method, carrying its headers + rate-limit handling)."""
    import yt_dlp  # the SOLE import of the brick (D103 / invariant 20)

    return _YtDlpTranscriptFetcher(yt_dlp, languages)


class _YtDlpTranscriptFetcher:  # pragma: no cover - real network client ((3) ignition, pilot-confronted)
    """Thin translation from :class:`TranscriptFetcher` to yt-dlp + the timedtext download (sujet 3 / D103).

    ``fetch`` resolves the ref to a video id, asks yt-dlp for the info (no video download), selects the best
    json3 track (:func:`_select_track`), and downloads that small payload THROUGH yt-dlp's own HTTP session
    (``ydl.urlopen``) - which carries the right headers (User-Agent...) and rate-limit handling, so YouTube does
    not ``429`` a bare ``Python-urllib`` request ((3) pilot 1). A video with no usable subtitles yields an empty
    transcript (``cues == ()``), never an error - the caller decides whether to fall back to LOCAL ASR."""

    __slots__ = ("_yt_dlp", "_languages")

    def __init__(self, yt_dlp: object, languages: tuple[str, ...]) -> None:
        self._yt_dlp = yt_dlp
        self._languages = languages

    def fetch(self, ref: str) -> FetchedTranscript:
        video_id = parse_youtube_ref(ref)
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": _TIMEOUT_S,
        }
        with self._yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
            info = ydl.extract_info(url, download=False)
            webpage_url = info.get("webpage_url") or url
            title = info.get("title") or video_id
            uploader = info.get("uploader") or info.get("channel") or ""

            track = _select_track(
                info.get("subtitles") or {}, info.get("automatic_captions") or {}, self._languages
            )
            if track is None:
                return FetchedTranscript(video_id, title, uploader, webpage_url, "", False, ())

            if not track.url.lower().startswith("https://"):
                # defense-in-depth (D100-3): only ever fetch over HTTPS - never a file:// / data:// url
                # smuggled through the info dict. YouTube's timedtext endpoint is always HTTPS; fail closed.
                raise ValueError(f"non-HTTPS subtitle track refused: {track.url[:60]!r}")
            # Download THROUGH yt-dlp's session (right headers + rate-limit handling) - a bare urllib gets 429.
            payload = ydl.urlopen(track.url).read().decode("utf-8")
        cues = parse_timedtext_json3(payload)
        return FetchedTranscript(
            video_id, title, uploader, webpage_url, track.language, track.auto_generated, cues
        )
