"""TranscriptFetcher (sujet 3 - YouTube) - turn a video URL into its verbatim transcript behind a swap-able seam.

"Voice is just one more source" (AV1) also holds for a YouTube video: the goal is to get its spoken words into
memory as text. The cheap, faithful path is the video's OWN subtitles (manual = human verbatim; failing that,
YouTube's auto-captions = YouTube's ASR). This port is the seam that yields them: given a video ref (a URL or a
bare id) it returns a :class:`FetchedTranscript` - provenance + verbatim cues. The engine that fetches them
(yt-dlp today, a plain API tomorrow) stays swap-able behind the Protocol (D7 / D26); the default adapter is
``connect_ytdlp`` (:mod:`~mnemosyne.ingest.youtube_ytdlp`).

Three structural points a caller MUST respect:

* **Outbound network - NOT local.** Unlike the sujet-2 VLM or WhisperKit (both LOCAL), fetching a transcript
  is an OUTBOUND request to YouTube. It exfiltrates NOTHING ``sensible`` (invariant 1 holds - it only pulls a
  PUBLIC datum in), but it IS an external access, so the wiring routes it through the Guard's external channel
  (deny-by-default, invariant 5). The fetched text is classified at ingestion like any source (D101).
* **Untrusted content, never instruction.** A transcript is third-party text (D100-3): it may contain words
  that read like commands ("ignore your rules..."). It is DATA - captured, searched, distilled - never an
  instruction the system obeys. The caller keeps it behind the Guard, with reduced rights.
* **Auto-captions are non-verbatim.** Manual subtitles are the author's words (faithful P3). Auto-captions are
  YouTube's ASR guess - approximate, not human verbatim. :attr:`FetchedTranscript.auto_generated` carries that
  distinction so the markdown MARKS it (honesty on provenance, the sujet-2 discipline applied to text).

Decisions: AV1 (voice/video = a source of more)  -  D43 (enriches ingestion)  -  D100 / D100-3 (model/third-party
output mediated, untrusted)  -  invariant 1 / D66 (nothing sensible leaves)  -  invariant 5 (external access via
the Guard)  -  D101 (classified at ingestion)  -  D126 (brick-free port). Code & docstrings English (D117).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class TranscriptCue:
    """One verbatim caption cue: its start time (seconds into the video) and its text. Structural, model-free."""

    start_s: float
    text: str


@dataclass(frozen=True, slots=True)
class FetchedTranscript:
    """A YouTube video's transcript as returned by a :class:`TranscriptFetcher`: provenance + verbatim cues.

    ``cues`` empty => the video had no usable subtitles in the requested languages (the caller may then fall
    back to the LOCAL ASR path - download the audio, transcribe via ``connect_whisperkit``). ``auto_generated``
    is ``True`` when the cues came from YouTube's auto-captions (ASR, approximate) rather than manual subtitles
    (human verbatim); it drives the non-verbatim mark in the produced markdown (honesty on provenance)."""

    video_id: str
    title: str
    uploader: str
    webpage_url: str
    language: str
    auto_generated: bool
    cues: tuple[TranscriptCue, ...]


@runtime_checkable
class TranscriptFetcher(Protocol):
    """Fetch ONE YouTube video's transcript into text; the engine stays swap-able (sujet 3).

    OUTBOUND by nature (unlike the LOCAL VLM / WhisperKit): the adapter reaches YouTube, so the caller routes
    it through the Guard's external channel (invariant 5) and treats the returned text as untrusted third-party
    DATA, never instruction (D100-3). It exfiltrates nothing ``sensible`` - it pulls a public datum in
    (invariant 1), classified at ingestion (D101)."""

    def fetch(self, ref: str) -> FetchedTranscript:
        """Return the transcript for a video ``ref`` (a YouTube URL or a bare 11-char id).

        Prefers MANUAL subtitles (human verbatim) over auto-captions (ASR); sets
        :attr:`FetchedTranscript.auto_generated` accordingly. Returns a transcript with empty ``cues`` when the
        video has no usable subtitles (the caller decides whether to fall back to LOCAL ASR). Raises
        ``ValueError`` when ``ref`` carries no extractable video id."""
        ...
