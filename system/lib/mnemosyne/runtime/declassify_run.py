"""declassify_run (item 8 / D107 / D147) — the human-gated door that declassifies a sensible deliverable.

D147 measured that invariant 1 already GRANTED what the operator wanted — « `sensible` data leaves
only by an explicit human gesture » — and that the real defect was a wiring debt: :class:`~mnemosyne.
production.channels.Declassification` (D107) existed but was reachable by nothing (absent from
``CoreApi``, no ``make`` target). This is the missing surface — and REACHABILITY is itself the new
capability: making an egress door invocable (a ``make`` target an agent could run) changes the risk
surface even though no D107 gate is weakened. That is exactly why ``CONFIRM`` stays the operator's
gesture, never a frontier's (D74)::

    make declassify FILE="knowledge/distilled/<dom>/<doc>.md" PRODUCER=frontier VERIFIER=opus            # DRY-RUN
    make declassify FILE="..." PRODUCER=frontier VERIFIER=opus CONFIRM=1 [OUT="..."] [BUBBLE=perso]      # the gesture

The order IS the safety (fail-closed, D107):

1. read the file as a `sensible` deliverable (a produced draft born of sensible material — fail-safe label);
2. the FIRST gate — a DISTINCT verifier's audit (``PRODUCER`` ≠ ``VERIFIER``, else refused, D100-6). Honest
   scope: this attests the STRUCTURAL gate (a distinct identity ran an audit); the SEMANTIC audit — truly no
   residual sensible trace — is the verifier's own read (content, D98), delegable to an isolated Opus (D75);
3. DRY-RUN by default — it shows what a `public` copy WOULD be and stops. It writes nothing;
4. ``CONFIRM=1`` is only the INTENT; the actual gesture is a LIVE ``OUI`` typed on the controlling terminal
   (``/dev/tty``, not stdin — the operator's 8b choice). No terminal ⇒ refused, so a headless agent CANNOT declassify
   even with ``CONFIRM=1``. Only then is a `public` COPY written beside the original — which is only ever READ,
   never mutated (non-destructive, D44 / D56) — plus a ``<out>.provenance.json`` trace of the gesture.

Declassification does NOT redact: the public copy carries the SAME bytes, now labelled `public`; the distinct
audit is what attests they hold no residual sensible trace. A declassified copy MAY then leave by canal A, so
this gesture is the UPSTREAM of egress and stays the operator's alone (« REACH TOWARD OTHERS », D147 / D74) — a frontier
may PREPARE (run the audit) but can neither pass a forgeable flag nor type the terminal ``OUI``. Brick-free
(``bootstrap``, no retrieval, no Qdrant);
NOT run in CI (it writes a file under CONFIRM). Code & docstrings English (D117); the tokens stay French (D33)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..api import CoreApi
from ..ports import Bubble, Envelope, GovernanceLabel, MnemosyneError, Sensitivity
from .bootstrap import bootstrap
from .human_gate import read_live_confirmation

#: The bubble a declassified deliverable is assumed to come from by default — ``perso`` (a deliverable born
#: of sensible material is personal until proven public). ``--bubble`` overrides it.
_DEFAULT_BUBBLE = "perso"


def _default_out(path: Path) -> Path:
    """The public copy's default location: beside the source, ``<stem>.public<suffix>`` — clearly paired,
    obviously derived, never colliding with the original (which is only ever read)."""
    return path.with_name(f"{path.stem}.public{path.suffix}")


def _read_terminal_confirmation(source: Path) -> bool:
    """Read a LIVE ``OUI`` from the controlling terminal (``/dev/tty``), NEVER stdin — so a piped or
    headless caller cannot feed it. No terminal (an automated agent, CI) → ``False``, fail-closed. This is
    the structural barrier (the operator's 8b choice) that keeps declassification — the one op that flips the Guard
    deny→allow — a human-at-the-keyboard gesture, unforgeable by an agent (D74 / D100, incapacity > trust).

    **Raw OS-level file descriptors, not ``open(..., "r+")``.** A ``"r+"`` text file is wrapped in
    ``io.BufferedRandom``, which assumes a seekable stream — a character device like a tty never
    is, so the wrapper raises ``io.UnsupportedOperation: File or stream is not seekable`` the
    instant it is used, on any platform: this had never actually been exercised against a real
    terminal (only ever monkeypatched in the test suite) until D159 hit the identical bug in its
    own copy of this gate and traced it here. ``os.open`` + raw ``os.read``/``os.write`` on the
    file descriptor never construct that wrapper, so the seek assumption is never made — verified
    against a real pty pair, not just a monkeypatch. **The body now lives in ONE place** —
    :func:`mnemosyne.runtime.human_gate.read_live_confirmation` — because this gate and its sibling
    in ``policy_run`` were hand-mirrored copies, and the seekable bug had to be carried between them
    by hand. This wrapper keeps only the prompt wording."""
    return read_live_confirmation(
        f"[declassify] Type OUI to declassify {source.name} into a PUBLIC copy "
        "(anything else aborts): "
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="make declassify",
        description="Declassify a sensible deliverable into a PUBLIC copy under your explicit gesture "
        "(D107 / D147). DRY-RUN by default; CONFIRM performs the gesture. The original is never touched.",
    )
    parser.add_argument(
        "path", help="the sensible deliverable to declassify (a file under knowledge/ or projects/)"
    )
    parser.add_argument("--producer", required=True, help="who produced the deliverable (identity)")
    parser.add_argument(
        "--verifier",
        required=True,
        help="who audited it for residual sensible traces — MUST differ from --producer (D100-6)",
    )
    parser.add_argument(
        "--bubble",
        default=_DEFAULT_BUBBLE,
        help=f"the bubble it comes from (default: {_DEFAULT_BUBBLE})",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="where to write the public copy (default: <stem>.public<suffix>)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="INTENT to declassify — you are then asked to type OUI LIVE at the terminal (no terminal = "
        "refused, so an agent cannot); without it, DRY-RUN only",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    source = Path(args.path)
    if not source.is_file():
        print(f"[declassify] no such file: {source}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else _default_out(source)

    content: Envelope[str] = Envelope(
        payload=source.read_text(encoding="utf-8"),
        label=GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble(args.bubble)),
    )
    api = CoreApi(
        bootstrap()
    )  # brick-free: declassification is a pure labelling act, no retrieval/model

    # Gate 1 — the DISTINCT audit. A self-audit (producer == verifier) is refused fail-closed here, before
    # anything is shown or written (D100-6).
    try:
        audit = api.audit_declassify(content, producer=args.producer, verifier=args.verifier)
    except MnemosyneError as refused:
        print(f"[declassify] REFUSED at the audit gate: {refused} (D107 / D100-6)", file=sys.stderr)
        return 1

    if not args.confirm:
        print(
            f"[declassify] DRY-RUN — would declassify {source} → a PUBLIC copy at {out}\n"
            f"  gate 1 (audit): {audit.note}\n"
            "  gate 2 (your gesture): NOT given — nothing written.\n"
            "  note: declassification does NOT redact; the public copy carries the SAME content, and the\n"
            "        distinct audit above is what attests it holds no residual sensible trace.\n"
            "  → re-run with CONFIRM=1, then type OUI LIVE at the terminal, to perform the gesture\n"
            "    (a headless agent has no terminal and cannot — D74)."
        )
        return 0

    if (
        out.exists()
    ):  # non-destructive UX pre-check: fail fast before the work (D74 — overwriting is the operator's)
        print(
            f"[declassify] REFUSED: {out} already exists — will not overwrite (choose another --out)",
            file=sys.stderr,
        )
        return 1

    # Gate 2a — the LIVE terminal confirmation (the operator's 8b choice): a 'OUI' typed on /dev/tty, NOT stdin. A
    # headless agent has no controlling terminal, so it CANNOT satisfy this — the structural barrier that
    # keeps this one deny->allow op the operator's alone (D74 / D100). `--confirm` is only the INTENT; THIS is the
    # gesture. Placed after the fail-fast checks so a doomed run never prompts.
    if not _read_terminal_confirmation(source):
        print(
            "[declassify] ABORTED: declassification needs a LIVE 'OUI' typed at the terminal (D74 / D147) "
            "— none given, or no terminal. Nothing declassified; an automated agent cannot do this.",
            file=sys.stderr,
        )
        return 1

    # Gate 2b — the code-level gesture. `declassify` re-checks the distinct audit AND requires
    # human_validated; it returns a FRESH `public` envelope, the original Envelope untouched (D107).
    try:
        public = api.declassify(content, audit=audit, human_validated=True)
    except (
        MnemosyneError
    ) as refused:  # EscalateToHuman ⊂ MnemosyneError — a missing gesture escalates here
        print(f"[declassify] REFUSED at the gesture gate: {refused} (D107)", file=sys.stderr)
        return 1

    # Write the public copy with EXCLUSIVE creation ("x") — atomic, closing the TOCTOU window on the
    # exists() pre-check above: if anything raced us to that path we refuse rather than overwrite, so
    # non-destructiveness is STRUCTURAL, not a check-then-act bet (D74 / D100).
    try:
        with open(out, "x", encoding="utf-8") as handle:
            handle.write(public.payload)
    except FileExistsError:
        print(
            f"[declassify] REFUSED: {out} already exists — will not overwrite (D74)",
            file=sys.stderr,
        )
        return 1

    # Persist a durable TRACE of this egress-door gesture beside the copy (D147: the most sensitive door
    # must leave an auditable record — what was declassified, by whom, audited by whom, when). The chain is
    # already computed in the public label; this writes it where a human can read it later (the copy alone
    # would answer none of those questions).
    sidecar = out.with_name(out.name + ".provenance.json")
    sidecar.write_text(
        json.dumps(
            {
                "source": str(source),
                "public_copy": str(out),
                "from_sensitivity": content.label.sensitivity.token,
                "to_sensitivity": public.label.sensitivity.token,
                "producer": args.producer,
                "verifier": args.verifier,
                "audit_note": audit.note,
                "declassified_at": datetime.now(timezone.utc).isoformat(),
                "gesture": "human-validated (D107 / D74)",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"[declassify] DONE — wrote a PUBLIC copy to {out} (sensitivity={public.label.sensitivity.token}, "
        f"bubble={public.label.bubble!r}).\n"
        f"  original {source} left intact (non-destructive, D44/D56).\n"
        f"  provenance recorded → {sidecar} (source → audit(verifier={args.verifier}) → declassify, D107).\n"
        "  the public copy may now leave by canal A — that egress remains your conscious act (D147/D74)."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] gesture
    raise SystemExit(main())
