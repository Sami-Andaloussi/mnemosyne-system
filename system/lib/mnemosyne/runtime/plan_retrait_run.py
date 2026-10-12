"""``make item-retirer`` (H1) — withdrawing a plan item becomes a gesture, never a text
editor.

Five commands, one single pipeline (demander -> examiner -> approuver/refuser -> appliquer),
modeled on ``make policy-*`` (D159) — same shape, different home. **A single Makefile target**, a
pass-through to this CLI (chat 3, ``ARGS=``) — not six targets like ``policy-*`` ::

    make item-retirer ARGS="queue"                                    # the state of every request
    make item-retirer ARGS="demander --items A1,B2 --motif ... --cout ... --requested-by ..."
    make item-retirer ARGS="examiner --id <id> [--verdict fichier.json]"
    make item-retirer ARGS="approuver --id <id>"     # shows the content, then asks for a LIVE yes
    make item-retirer ARGS="refuser --id <id> --raison ..."
    make item-retirer ARGS="appliquer --id <id> --fichier chemin/vers/plan.md [--confirm]"

**What this CLI NEVER does**: approve, examine on its own behalf, or write a plan file without an
approval whose content matches EXACTLY what is about to be applied
(:meth:`~mnemosyne.production.plan_retrait.RetraitLedger.appliquer_verifie` is fail-closed on the
content hash). The ``examiner`` subcommand without ``--verdict`` only PRINTS the mandate that the
calling agent must then hand to an ISOLATED agent (D75, the most capable model available) — this
module never launches an agent itself.

**The word passes through ``/dev/tty``, never through a command-line argument** (same gesture as
``policy_run.py``, same reason: D159/D160, a post-incident fix). The whole pipeline
(``RetraitDemande``, ``RetraitLedger``) lives in :mod:`mnemosyne.production.plan_retrait` — this
module is only a caller, exactly what H1 states: "the mechanism already exists, we APPLY it, we
never reinvent it".

Brick-free (no model, no dependency). Code and CLI output are both English (D117)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..production.plan_retrait import (
    DEFAULT_LEDGER_PATH,
    RetraitDemande,
    RetraitError,
    RetraitEtat,
    RetraitLedger,
)


def _item_ligne(items: tuple[str, ...]) -> str:
    return ", ".join(items)


def render_queue(states: tuple[RetraitEtat, ...]) -> str:
    if not states:
        return (
            "# Mnemosyne · withdrawal requests\n\n"
            'No request filed. `make item-retirer ARGS="demander ..."` to create one.\n'
        )
    lines = ["# Mnemosyne · withdrawal requests", ""]
    for state in states:
        lines.append(f"[{state.stage}] {state.id} — {_item_ligne(state.items)}")
        lines.append(f"  filed by {state.requested_by} on {state.filed_at}")
        lines.append(f"  reason : {state.motif}")
        lines.append(f"  cost   : {state.cout}")
        if state.examined:
            lines.append(f"  review: {state.examiner_verdict} — {state.examiner_notes}")
        if state.refused:
            # AUDIT DELEGATED ON 2026-08-15: `by`/`at` already existed in the journal but never
            # here — the ONLY surface the operator reads used to pass over in silence who refused,
            # and when. A reader had to open the gitignored `.jsonl` by hand to see them.
            lines.append(f"  refused on {state.refused_at} by {state.refused_by}: "
                         f"{state.refused_reason}")
        if state.approved:
            lines.append(f"  approved on {state.approved_at}")
        # AUDIT DELEGATED ON 2026-08-15: an attempt to apply without a GO, or to forge an
        # approval, left NO visible trace here — zero bytes, measured 4 times. An agent could
        # hammer these two gestures indefinitely without the operator ever seeing anything of it.
        if state.denied_count:
            lines.append(
                f"  {state.denied_count} attempt(s) refused, last on "
                f"{state.last_denied_at} by {state.last_denied_by}: {state.last_denied_reason}"
            )
        if state.applied:
            lines.append(f"  APPLIED on {state.applied_at}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_examination_mandate(state: RetraitEtat) -> str:
    """The adversarial mandate, BOUNDED and CLOSABLE (D75) — to be handed to an ISOLATED agent
    (never the one who filed the request), on the most capable model available. This module never
    executes it itself: it only prints the text."""
    return f"""# Adversarial examination mandate -- withdrawal request {state.id} (H1 / D75)

You are examining a request to WITHDRAW items from Mnemosyne's plan. You are NOT the one who filed
this request, and your verdict does not approve or refuse ANYTHING -- only the operator, by a word
typed LIVE, can do that. Your role is to NARROW the request if it goes beyond what its reason
covers.

## The request

Items targeted: {_item_ligne(state.items)}
Filed by: {state.requested_by}
Reason: {state.motif}
Declared cost: {state.cout}

## What you must verify

1. Is each targeted item PLAUSIBLY covered by the given reason? An item with no obvious link to
   the reason is a candidate for narrowing.
2. Is the declared cost honest -- does it name what is genuinely lost (work, other items'
   dependencies, history) rather than minimizing it?
3. Does another plan item depend on one of the targeted items (`*Depend de*`)? A withdrawal that
   breaks a dependency not mentioned in the reason is a strong signal for narrowing.
4. Among the targeted items, is there one with no obvious link to the others -- a silent request
   riding along with what is stated? This is the most important signal: remove it.

## Your answer -- ONLY this JSON, nothing else

{{
  "verdict": "allow" | "narrow" | "reject",
  "notes": "a short explanation, in English, of your verdict",
  "narrowed_items": [ ... only if verdict == "narrow", a SUBSET of the targeted items ... ]
}}

Reminder: "reject" is a RECOMMENDATION, not a refusal -- the operator decides regardless. A
"narrow" verdict MUST remove at least one item from the list; it can never ADD one."""


def _load_verdict(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RetraitError(f"unreadable verdict ({path}): {exc}") from exc
    if not isinstance(raw, dict) or "verdict" not in raw:
        raise RetraitError(f"malformed verdict ({path}): at least {{'verdict': ...}} is required")
    return raw


def _cmd_queue(ledger: RetraitLedger, _args: argparse.Namespace) -> int:
    print(render_queue(ledger.all_states()), end="")
    return 0


def _cmd_demander(ledger: RetraitLedger, args: argparse.Namespace) -> int:
    items = tuple(x for x in (part.strip() for part in args.items.split(",")) if x)
    try:
        demande = RetraitDemande(
            items=items, motif=args.motif, cout=args.cout, requested_by=args.requested_by
        )
        id_ = ledger.file(demande)
    except RetraitError as exc:
        print(f"Request refused: {exc}", file=sys.stderr)
        return 2
    print(f"Request filed: {id_} — {_item_ligne(demande.items)}")
    print(f'Next: make item-retirer ARGS="examiner --id {id_}"')
    return 0


def _cmd_examiner(ledger: RetraitLedger, args: argparse.Namespace) -> int:
    if not args.id:
        print("ID= is required.", file=sys.stderr)
        return 2
    state = ledger.state(args.id)
    if state is None:
        print(f"Unknown request: {args.id}", file=sys.stderr)
        return 2
    if not args.verdict:
        print(render_examination_mandate(state))
        return 0
    try:
        raw = _load_verdict(Path(args.verdict))
        narrowed_raw = raw.get("narrowed_items")
        narrowed = tuple(str(x) for x in narrowed_raw) if narrowed_raw else None
        ledger.record_examination(
            args.id,
            verdict=str(raw["verdict"]),
            narrowed_items=narrowed,
            notes=str(raw.get("notes", "")),
            examiner=str(raw.get("examiner", "isolated agent")),
        )
    except RetraitError as exc:
        print(f"Verdict refused: {exc}", file=sys.stderr)
        return 2
    print(f"Review recorded for {args.id}: {raw['verdict']}")
    print(f'Next: make item-retirer ARGS="approuver --id {args.id}"   (if the operator approves)')
    return 0


def _print_request_content(state: RetraitEtat) -> None:
    """Shows a request's full content before it is approved — same discipline as
    ``policy_run._print_request_content``: a decision needs to see its implications."""
    print(f"Request {state.id} — items: {_item_ligne(state.items)}")
    print(f"Filed by: {state.requested_by}")
    print(f"Reason: {state.motif}")
    print(f"Cost  : {state.cout}")
    if state.examined:
        print(f"Review ({state.examiner_verdict}): {state.examiner_notes}")
    else:
        print(
            'Warning: this request has not been reviewed yet (make item-retirer ARGS="examiner ...").'
        )


def _cmd_approuver(ledger: RetraitLedger, args: argparse.Namespace) -> int:
    if not args.id:
        print("ID= is required.", file=sys.stderr)
        return 2
    state = ledger.state(args.id)
    if state is None:
        print(f"Unknown request: {args.id}", file=sys.stderr)
        return 2
    if state.stage == "applique":
        print(f"Request {args.id} already applied on {state.applied_at}.", file=sys.stderr)
        return 2
    if state.stage == "refuse":
        print(f"Request {args.id} already refused: {state.refused_reason}", file=sys.stderr)
        return 2
    _print_request_content(state)
    try:
        # AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): `by="terminal (/dev/tty), H1"` was true
        # ONLY on the success path -- but that same `by` ALSO landed in the `denied` event when
        # the read failed (a pipe, a detached subprocess), where it attested to a real terminal
        # for a refusal CAUSED BY ITS ABSENCE. Same fault already closed for
        # `_cmd_refuser`/`_cmd_appliquer`: name the ATTEMPT (true in both cases), never a result
        # (true in only one).
        approuve = ledger.approuver_en_direct(
            args.id, by="CLI item-retirer, /dev/tty read attempted"
        )
    except RetraitError as exc:
        print(f"Approval refused: {exc}", file=sys.stderr)
        return 2
    if not approuve:
        print("No live YES received — nothing is approved.")
        return 1
    print(f"Approved: {args.id}")
    print(
        f'Next: make item-retirer ARGS="appliquer --id {args.id} --fichier <plan.md> --confirm"'
    )
    return 0


def _cmd_refuser(ledger: RetraitLedger, args: argparse.Namespace) -> int:
    if not args.id:
        print("ID= is required.", file=sys.stderr)
        return 2
    if not args.raison:
        print("RAISON= is required.", file=sys.stderr)
        return 2
    try:
        # AUDIT DELEGATED ON 2026-08-15, WITHIN H1'S CLAUSE: this line used to write
        # `by="terminal (/dev/tty), H1"` even though `refuse()` reads NO tty at all — a literal
        # attestation only attests to itself, never to the gesture. `refuse()` serves "the
        # operator, or a caller relaying their word" (see its docstring): the CLI verifies
        # nothing itself, so `by` must say so, not claim the opposite.
        ledger.refuse(args.id, reason=args.raison, by="CLI item-retirer (no live verification)")
    except RetraitError as exc:
        print(f"Refusal refused (!): {exc}", file=sys.stderr)
        return 2
    print(f"Refused: {args.id} — {args.raison}")
    return 0


def _cmd_appliquer(ledger: RetraitLedger, args: argparse.Namespace) -> int:
    if not args.id:
        print("ID= is required.", file=sys.stderr)
        return 2
    if not args.fichier:
        print("FICHIER= is required (the plan that carries the targeted items).", file=sys.stderr)
        return 2
    state = ledger.state(args.id)
    if state is None:
        print(f"Unknown request: {args.id}", file=sys.stderr)
        return 2
    chemin = Path(args.fichier)
    if not args.confirm:
        print(f"DRY-RUN — {args.id} would apply onto {chemin}:")
        _print_request_content(state)
        print("Run again with CONFIRM=1 to actually write.")
        return 0
    try:
        # AUDIT DELEGATED ON 2026-08-15, WITHIN H1'S CLAUSE: the same fault as for the refusal
        # -- `appliquer_verifie` opens no tty either, it writes and re-reads a FILE. The only
        # `/dev/tty` gesture in this whole pipeline happened EARLIER, at approval -- attributing a
        # tty to THIS gesture would be an attestation matching no real observation.
        ledger.appliquer_verifie(
            args.id, chemin=chemin, by="CLI item-retirer (no live verification)"
        )
    except RetraitError as exc:
        print(f"Application refused: {exc}", file=sys.stderr)
        return 2
    print(f"Applied: {args.id} onto {chemin}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="item-retirer",
        description="The demander -> examiner -> approuver -> appliquer pipeline, for an item withdrawal (H1).",
    )
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH), help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("queue", help="the state of every request")

    p_demander = sub.add_parser("demander", help="file a withdrawal request")
    p_demander.add_argument("--items", default="", help="comma-separated identifiers")
    p_demander.add_argument("--motif", default="")
    p_demander.add_argument("--cout", default="")
    p_demander.add_argument("--requested-by", default="")

    p_examiner = sub.add_parser("examiner", help="print the mandate, or record a verdict")
    p_examiner.add_argument("--id", default="")
    p_examiner.add_argument("--verdict", default="")

    # H1/D159, same hardening as policy_run.py: NO --mot argument. The word is read LIVE
    # on /dev/tty (see mnemosyne.runtime.human_gate.read_live_confirmation).
    p_approuver = sub.add_parser(
        "approuver", help="the operator's gesture — a YES typed LIVE on the terminal"
    )
    p_approuver.add_argument("--id", default="")

    p_refuser = sub.add_parser("refuser", help="the same gesture, the other way")
    p_refuser.add_argument("--id", default="")
    p_refuser.add_argument("--raison", default="")

    p_appliquer = sub.add_parser(
        "appliquer", help="write the withdrawal onto the plan — dry-run by default"
    )
    p_appliquer.add_argument("--id", default="")
    p_appliquer.add_argument("--fichier", default="")
    p_appliquer.add_argument("--confirm", action="store_true")

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    ledger = RetraitLedger(Path(args.ledger))

    handlers = {
        "queue": _cmd_queue,
        "demander": _cmd_demander,
        "examiner": _cmd_examiner,
        "approuver": _cmd_approuver,
        "refuser": _cmd_refuser,
        "appliquer": _cmd_appliquer,
    }
    return handlers[args.command](ledger, args)


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
