"""YouTube ingestion CLI (sujet 3 / C3) - capture a video's transcript INTO MEMORY, Guard-mediated.

The real, machine-only entry for "a YouTube URL -> its transcript in memory": build the REAL runtime (which
wires the yt-dlp fetcher when the optional brick is installed) and drive :meth:`CoreApi.capture_youtube` - the
ONE Guard-mediated door (an ``EXTERNAL_OUTPUT`` grant is asked BEFORE any fetch, deny-by-default). Nothing
here bypasses the Guard: it is a THIN CLI over the audited surface, the real sibling of the ``youtube-pilot``
diagnostic (which only writes a local ``.md`` and touches no store).

Usage: ``make youtube-ingest URL="https://youtu.be/<id>" [BUBBLE=perso]``
   or:  ``PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.youtube_ingest <url> [--bubble perso]``

``[OPERATOR]`` prerequisites - BOTH are their gestures, and the flow is deny-by-default until they are done:
(1) install the OPTIONAL brick (``uv add --optional bricks yt-dlp``) - without it the fetch is refused
fail-closed (D126); (2) allow-list the host in the protected policy zone
(``[egress] allowlist = ["www.youtube.com"]`` in ``system/config/policy.toml``) - without it the Guard
refuses every fetch (invariant 5 / 21). The transcript is UNTRUSTED third-party DATA (D100-3), classified at
capture (D101); a YouTube ASR transcript is marked non-verbatim and stripped from the verbatim floor at
distillation (C2). Code & docstrings English (D117); the user-facing prints are French (D33)."""

from __future__ import annotations


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - real bricks + network (machine-only)
    """CLI: capture a YouTube transcript into memory through the governed surface (the ``make youtube-ingest`` seam)."""
    import argparse

    from ..api import CoreApi
    from ..guard.heavy_lock import HeavyRunBusy
    from ..ports import Bubble, EscalateToHuman, GuardDenied
    from .bootstrap import real_runtime
    from .heavy import HeavyRunRefused, default_health_probe, guarded_heavy_run

    parser = argparse.ArgumentParser(
        description="Capture a YouTube transcript into memory (sujet 3 / C3)."
    )
    parser.add_argument(
        "url", help="a YouTube URL (watch / youtu.be / shorts / embed / live) or a bare id"
    )
    parser.add_argument(
        "--bubble", default="perso", help="the bubble to capture into (default: perso)"
    )
    args = parser.parse_args(argv)

    # Q1: cold-starting real_runtime loads a multi-GB model, so this capture holds the heavy-run lock too -
    # it never collides with a concurrent `make ingest` / `figures-enrich`, and a held lock refuses fast.
    try:
        with guarded_heavy_run("youtube-ingest", health=default_health_probe(), on_notice=print):
            api = CoreApi(real_runtime())
            # The URL / egress diagnostics below belong to the CAPTURE door only - hug capture_youtube, so a
            # failure while BUILDING the runtime (e.g. a config error) surfaces as its own distinct error
            # rather than being mislabeled "URL invalide" (the lock still wraps both, as it must).
            try:
                receipt = api.capture_youtube(args.url, bubble=Bubble(args.bubble))
            except (
                ValueError
            ) as exc:  # a non-YouTube ref, refused at the door before any egress (D55)
                print(f"Invalid YouTube URL: {exc}")
                return 2
            except (
                GuardDenied
            ) as exc:  # deny-by-default: no fetcher wired, or the host is not allow-listed
                print(f"REFUSED (Guard): {exc}")
                print(
                    "  -> check the 2 [OPERATOR] gestures: (1) `uv add --optional bricks yt-dlp` ; "
                    '(2) `[egress] allowlist = ["www.youtube.com"]` in system/config/policy.toml.'
                )
                return 1
            except (
                EscalateToHuman
            ) as exc:  # non-public egress would need a canal-B human gesture (D66 / D90)
                print(f"ESCALATION (channel B, human gesture required): {exc}")
                return 1
    except (
        HeavyRunBusy,
        HeavyRunRefused,
    ) as exc:  # another heavy run holds the lock, or disk CRITICAL
        print(f"REFUSED: {exc}")
        return 1

    if (
        receipt.capture is None
    ):  # honest emptiness (F3): a video with no usable subtitles memorizes nothing
        print(
            f"No usable subtitle for {receipt.video_id!r} ({receipt.title!r}) - nothing memorised "
            "(a local audio transcription, AV1, remains a future track)."
        )
        return 0
    kind = "auto-generated (ASR, non-verbatim)" if receipt.auto_generated else "manual (verbatim)"
    print(
        f"OK - {kind} transcript of {receipt.title!r} [{receipt.language}] memorised "
        f"(doc {receipt.capture.doc}, sensitivity {receipt.capture.sensitivity.name})."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
