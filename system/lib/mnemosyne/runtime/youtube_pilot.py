"""YouTube transcript pilot (sujet 3) - fetch ONE video's transcript locally so user can judge the quality.

The ``[OPERATOR]`` judgement seam for the YouTube stage: take ONE video ref, fetch its transcript with the real
brick (``connect_ytdlp``), render it to markdown (:func:`~mnemosyne.ingest.youtube.transcript_to_markdown`),
write it as ``<video_id>.youtube.md`` in the current directory, and report the cue count / language / source
kind. This is a LOCAL DIAGNOSTIC artifact for eyeballing, NOT an ingestion into memory - it writes a file and
touches no store; mass ingestion goes through the ordinary capture pipeline, where the Guard mediates the
outbound fetch (invariant 5) and classifies the text (D101). Machine-only for the real path (needs
``uv add --optional bricks yt-dlp``); import-safe (the brick imports lazily via the adapter), so this module is
in no brick-free test yet never breaks the suite (D126). Run it on 1-3 videos BEFORE wiring YouTube into the
capture pipeline. Code & docstrings English (D117).
"""

from __future__ import annotations

import sys
from pathlib import Path


def run_youtube_pilot(
    ref: str,
) -> Path:  # pragma: no cover - needs the brick + network ([OPERATOR] ignition)
    """Fetch ONE video's transcript and write ``<video_id>.youtube.md`` in the cwd; return its path.

    Prints a one-line tally (cue count, language, manual vs auto-caption) so user can eyeball fidelity before
    the stage is deployed. A video with no subtitles writes the provenance header plus an explicit
    ``_(aucun sous-titre disponible)_`` note (the LOCAL ASR fallback via WhisperKit is the next seam)."""
    from ..ingest import connect_ytdlp, transcript_to_markdown

    transcript = connect_ytdlp().fetch(ref)
    out = Path(f"{transcript.video_id}.youtube.md")
    out.write_text(transcript_to_markdown(transcript), encoding="utf-8")
    kind = "auto-generated" if transcript.auto_generated else "manual"
    lang = transcript.language or "none"
    print(
        f"[youtube-pilot] {transcript.video_id}: {len(transcript.cues)} cue(s), language={lang}, {kind}"
    )
    print(f"[youtube-pilot] written -> {out}")
    return out


def main() -> None:  # pragma: no cover - CLI
    if len(sys.argv) != 2:
        print(
            "usage: python -m mnemosyne.runtime.youtube_pilot <youtube-url-or-id>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    run_youtube_pilot(sys.argv[1])


if __name__ == "__main__":  # pragma: no cover
    main()
