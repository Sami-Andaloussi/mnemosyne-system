"""``make policy-*`` (D159) — widening an authorization becomes a gesture, never a text editor.

Six commands, one pipeline (request -> examine -> approve/refuse -> apply), modeled on
``make endorse``/``make signaler`` (dry-run by default, journaled gesture, nothing is ever
erased) ::

    make policy-queue                              # the state of every request
    make policy-demander [FICHIER=path.toml]        # file a request (or create a template)
    make policy-examiner ID=<id> [VERDICT=file.json]
    make policy-approuver ID=<id>                   # shows you the content, then asks for a LIVE OUI
    make policy-refuser ID=<id> RAISON="..."        # the same gesture, the other way
    make policy-appliquer ID=<id> [CONFIRM=1]

**What this CLI NEVER does**: approve, examine on its own behalf, or write policy.toml without an
approval whose content matches EXACTLY what is about to be applied
(:meth:`~mnemosyne.production.policy_requests.PolicyRequestLedger.approved_items_for_apply` is
fail-closed). ``policy-examiner`` with no ``VERDICT`` merely PRINTS the mandate the calling agent
must then hand to an ISOLATED agent (D75, the most capable model) — this module never launches an
agent itself, exactly as ``make veille`` only orchestrates, never judges.

**The word travels through ``/dev/tty``, never a command-line argument (D159, post-incident
fix).** An agent once typed ``MOT=oui`` on the command line for its OWN request, and the journal
recorded ``"by": "operator"`` — a provenance never actually observed, because that field had a
hardcoded default. The same shape of gesture already existed, for a LESS serious gesture:
:func:`~mnemosyne.runtime.declassify_run._read_terminal_confirmation`. :func:`_read_terminal_confirmation`
below is modeled on it, and ``by=`` no longer has a default anywhere in
:mod:`~mnemosyne.production.policy_requests`: every caller must state what it actually observed,
never assert an identity it never saw.

**The first REAL attempt at this gesture (the operator, on a real terminal) crashed** —
``io.UnsupportedOperation: File or stream is not seekable`` — because neither this one nor the
original ``declassify_run.py`` had ever been exercised against a REAL tty (the test suite only
ever substitutes the whole function). The cause: ``open(..., "r+")`` wraps the descriptor in
``io.BufferedRandom``, which assumes a "seekable" stream — never true for a terminal. Fixed here
with raw ``os.open``/``os.read``/``os.write`` calls (never that wrapper), and verified against a
REAL pty before handing control back to the operator — the same fix was carried over to
``declassify_run.py``.

Brick-free (no model, no dependency). Code in English (D117); what the CLI prints is French in
the source repository (the operator reads it, or an agent summarizes it for them) — this mirror
translates it to English throughout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..production import policy_writer
from ..production.policy_requests import (
    DEFAULT_LEDGER_PATH,
    PolicyRequestError,
    PolicyRequestLedger,
    RequestState,
    render_template,
    request_from_toml,
)
from ..production.policy_writer import PolicyItem, PolicyWriteError
from .human_gate import read_live_confirmation

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_POLICY_PATH = _REPO_ROOT / "system" / "config" / "policy.toml"
_DEFAULT_TEMPLATE_PATH = (
    _REPO_ROOT / "system" / "state" / "policy" / "requests" / "nouvelle-demande.toml"
)

#: Bounds enforced by :func:`_plain` — an agent-controlled field must never be able to push the
#: real request content off the screen a human is about to approve on (D159, 2nd D75 audit).
_MAX_FIELD_LINES = 20
_MAX_FIELD_CHARS = 2000


def _plain(text: str, *, allow_newlines: bool = False) -> str:
    """Defang a string an AGENT controls (title / justification / requested_by / examiner
    notes) before it reaches the operator's terminal — the print-layer half of the 2nd D75 audit's
    finding: :class:`~mnemosyne.production.policy_writer.PolicyItem` already refuses a control
    character in its own ``note`` at construction, but nothing stopped the OTHER four
    agent-controlled strings from carrying raw ANSI escapes or hundreds of blank lines to push
    the actual item list off-screen — an "oui" given to whatever remained visible is not an
    informed approval, even though :func:`~mnemosyne.production.policy_requests._is_item_subset`
    already stops the WIDTH of the request from silently growing.

    Belt and suspenders on top of the construction-time guards in :mod:`.policy_requests`
    (:func:`~mnemosyne.production.policy_requests._no_control_chars`): those reject bad input at
    filing/examination time, but :meth:`~mnemosyne.production.policy_requests.PolicyRequestLedger.
    state` rebuilds a :class:`RequestState` straight from whatever JSON a ledger line carries at
    replay, with no second pass through that validation — this is the one guard every reader of
    the ledger inherits regardless of how the bytes got there."""
    out: list[str] = []
    for ch in text:
        if ch == "\n":
            out.append(ch if allow_newlines else " ")
        elif ord(ch) >= 0x20:
            out.append(ch)
        # else: drop every other control character (ESC, form-feed, ...) outright
    cleaned = "".join(out)
    if allow_newlines:
        lines = cleaned.split("\n")
        if len(lines) > _MAX_FIELD_LINES:
            cleaned = (
                "\n".join(lines[:_MAX_FIELD_LINES])
                + f"\n… ({len(lines) - _MAX_FIELD_LINES} line(s) truncated)"
            )
    if len(cleaned) > _MAX_FIELD_CHARS:
        cleaned = cleaned[:_MAX_FIELD_CHARS] + "… (truncated)"
    return cleaned


def _item_line(item: PolicyItem) -> str:
    if item.kind == "egress":
        return f"egress -> {', '.join(item.values)}" + (f"  ({item.note})" if item.note else "")
    if item.kind == "domains":
        return f'domains["{item.bubble}"] += {", ".join(item.values)}'
    if item.kind == "contract":
        return f"contract {item.contract_from} -> {item.contract_to}"
    return f"{item.kind}: {item}"  # pragma: no cover - closed set, defensive only


def render_queue(states: tuple[RequestState, ...]) -> str:
    if not states:
        return (
            "# Mnémosyne · policy requests\n\n"
            "No request filed. `make policy-demander` to create one.\n"
        )
    lines = ["# Mnémosyne · policy requests", ""]
    for state in states:
        lines.append(f"[{state.stage}] {state.id} — {_plain(state.title)}")
        lines.append(f"  requested by {_plain(state.requested_by)} on {state.filed_at}")
        lines.append(f"  why: {_plain(state.justification, allow_newlines=True).strip()}")
        for item in state.items:
            lines.append(f"    - {_item_line(item)}")
        if state.examined:
            lines.append(f"  examined: {state.examiner_verdict} — {_plain(state.examiner_notes)}")
        if state.refused:
            lines.append(f"  refused: {_plain(state.refused_reason)}")
        if state.approved:
            lines.append(f"  approved on {state.approved_at}")
        if state.applied:
            lines.append(f"  APPLIED on {state.applied_at}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_examination_mandate(state: RequestState) -> str:
    """The adversarial mandate, BOUNDED and CLOSABLE (D75) — to be handed to an ISOLATED agent
    (never the one that filed the request), on the most capable model available. This module
    does not execute it itself: it only prints the text, exactly as a `make veille` prepares the
    corpus without judging in its place."""
    items_desc = "\n".join(f"  {i + 1}. {_item_line(it)}" for i, it in enumerate(state.items))
    return f"""# Adversarial examination mandate -- request {state.id} (D159 / D75)

You are examining a request to WIDEN Mnemosyne's security policy
(system/config/policy.toml). You are NOT the one who filed this request, and your verdict
neither approves nor refuses ANYTHING -- only the operator, by a word, can do that. Your role is
to NARROW the request if it exceeds what its own justification covers, and to inform their decision.

## The request

Title: {_plain(state.title)}
Requested by: {_plain(state.requested_by)}
Justification given:
{_plain(state.justification, allow_newlines=True)}

Requested items:
{items_desc}

## What you must check, item by item

1. Does each concrete value PLAUSIBLY serve the given justification? A value with no obvious
   link to the justification is a candidate for narrowing.
2. For an "egress" item: is a host a MODEL API (e.g. api.anthropic.com, api.openai.com), or a
   payment platform / social network? That would merge two distinct Guard effects (MODEL_CALL
   and EXTERNAL_OUTPUT) and must be removed.
3. For a "domains" item: do the values stay within the SAME general subject the bubble claims?
   A `sante`/`intime`/personal domain mixed into a public-data project is a strong signal that
   narrowing is needed.
4. For a "contract" item: is the direction (from -> to) correct and minimal? Could the need be
   met WITHOUT this contract?
5. Is there, among the items, a value the justification does NOT explain (a silent request added
   on top of what is stated)? That is the most important signal: remove it.

## Your answer -- ONLY this JSON, nothing else

{{
  "verdict": "allow" | "narrow" | "reject",
  "notes": "short explanation of your verdict, in French",
  "narrowed_items": [ ... only if verdict == "narrow", same shape as the items above ... ]
}}

Reminder: "reject" is a RECOMMENDATION, not a refusal -- the operator will decide either way. A
"narrow" verdict MUST reduce at least one item; it can never ADD one."""


def _load_verdict(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyRequestError(f"unreadable verdict ({path}): {exc}") from exc
    if not isinstance(data, dict) or "verdict" not in data:
        raise PolicyRequestError(
            "the verdict must be a JSON object with at least a 'verdict' field"
        )
    return data


def _verdict_items(raw: object) -> tuple[PolicyItem, ...]:
    """Build items from a verdict's ``narrowed_items`` — DEFENSIVELY typed (D159, post-incident
    hardening): a hand- or agent-written JSON file is untrusted input. Two shapes a naive
    ``it.get(...)`` would silently mis-accept: an item that is not an object at all (``.get``
    would raise ``AttributeError`` — an unhelpful crash, not a clear refusal), and ``values``
    given as a bare STRING rather than a list — Python happily iterates a string character by
    character, so ``values = "macro"`` would silently become five single-letter "domains" and
    the request would be filed without a word of complaint."""
    if not isinstance(raw, list):
        raise PolicyRequestError("'narrowed_items' must be a list of objects")
    items = []
    for it in raw:
        if not isinstance(it, dict):
            raise PolicyRequestError(f"an item must be a JSON object, not {type(it).__name__}")
        values = it.get("values", [])
        if not isinstance(values, list):
            raise PolicyRequestError(f"'values' must be a list, not {type(values).__name__}")
        items.append(
            PolicyItem(
                kind=str(it.get("kind", "")),
                bubble=str(it.get("bubble", "")),
                values=tuple(str(v) for v in values),
                contract_from=str(it.get("contract_from", "")),
                contract_to=str(it.get("contract_to", "")),
                note=str(it.get("note", "")),
            )
        )
    return tuple(items)


def _read_terminal_confirmation(prompt: str) -> bool:
    """Read a LIVE ``OUI`` on ``/dev/tty`` — delegated to the ONE gate (D159, post-incident).

    This used to hold its own copy of the device read, mirrored by hand from ``declassify_run``. The
    duplication cost real money: the ``io.BufferedRandom``-is-not-seekable bug had to be found here
    and carried back there. The body now lives in :mod:`mnemosyne.runtime.human_gate`; this wrapper
    stays only to keep the prompt wording and the monkeypatch seam the tests already target."""
    return read_live_confirmation(prompt)


def _cmd_queue(ledger: PolicyRequestLedger, _args: argparse.Namespace) -> int:
    print(render_queue(ledger.all_states()), end="")
    return 0


def _cmd_demander(ledger: PolicyRequestLedger, args: argparse.Namespace) -> int:
    if not args.fichier:
        template_path = Path(args.template_path)
        if template_path.exists():
            print(
                f"A template already exists: {template_path}\nEdit it, then re-run with FICHIER=..."
            )
            return 0
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(render_template(), encoding="utf-8")
        print(
            f"Template created: {template_path}\nFill it in, then re-run: make policy-demander FICHIER={template_path}"
        )
        return 0
    try:
        request = request_from_toml(Path(args.fichier).read_text(encoding="utf-8"))
    except (OSError, PolicyRequestError, PolicyWriteError) as exc:
        print(f"Request refused: {exc}", file=sys.stderr)
        return 2
    id_ = ledger.file(request)
    print(f"Request filed: {id_} — {request.title}")
    print(f"Next: make policy-examiner ID={id_}")
    return 0


def _cmd_examiner(ledger: PolicyRequestLedger, args: argparse.Namespace) -> int:
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
        narrowed = _verdict_items(raw["narrowed_items"]) if raw.get("narrowed_items") else None
        ledger.record_examination(
            args.id,
            verdict=str(raw["verdict"]),
            narrowed_items=narrowed,
            notes=str(raw.get("notes", "")),
            examiner=str(raw.get("examiner", "isolated agent")),
        )
    except (PolicyRequestError, PolicyWriteError) as exc:
        print(f"Verdict refused: {exc}", file=sys.stderr)
        return 2
    print(f"Examination recorded for {args.id}: {raw['verdict']}")
    print(f"Next: make policy-approuver ID={args.id} MOT=oui   (if the operator approves)")
    return 0


def _print_request_content(state: RequestState) -> None:
    """Show the full content of a request before it is approved / refused (D159, post-audit
    fix — invariant 2 of the filing signalement: a decision needs its implications shown, never
    a naked choice). Every agent-controlled string is DEFANGED first (2nd D75 audit: title /
    justification / examiner notes carried no control-character guard, so an examiner could push
    the ITEM LIST — printed LAST, on purpose, so bounded free text above it can never bury it —
    off-screen)."""
    print(f"Request {state.id} — {_plain(state.title)}")
    print(f"Requested by: {_plain(state.requested_by)}")
    print(f"Justification: {_plain(state.justification, allow_newlines=True).strip()}")
    if state.examined:
        print(f"Examination ({state.examiner_verdict}): {_plain(state.examiner_notes)}")
    else:
        print("Note: this request has not been examined yet (make policy-examiner).")
    print("Items:")
    for item in state.items:
        print(f"  - {_item_line(item)}")


def _cmd_approuver(ledger: PolicyRequestLedger, args: argparse.Namespace) -> int:
    if not args.id:
        print("ID= is required.", file=sys.stderr)
        return 2
    state = ledger.state(args.id)
    if state is None:
        print(f"Unknown request: {args.id}", file=sys.stderr)
        return 2
    _print_request_content(state)
    # D159, post-incident hardening: the word is read LIVE from the controlling terminal, never
    # from a CLI argument — a `MOT=oui` an agent could type on its own behalf is exactly what let
    # an unattended agent's approval be journaled as if the operator had given it. No terminal (an
    # agent, a headless run) => refused outright, before even asking.
    if not _read_terminal_confirmation(
        f"[policy-approuver {args.id}] Type OUI to approve EXACTLY what is shown above: "
    ):
        print(
            "ABANDONED: no 'OUI' given LIVE on a terminal (D159/D74) — an agent cannot "
            "satisfy this gate, whatever it passes as an argument. Nothing is approved.",
            file=sys.stderr,
        )
        return 1
    try:
        ledger.approve(args.id, word="oui", by="terminal (/dev/tty), D159")
    except PolicyRequestError as exc:
        print(f"Approval refused: {exc}", file=sys.stderr)
        return 2
    print(f"Request {args.id} approved.")
    # ONE gesture, ONE word (2026-07-28). The write follows the approval immediately, right behind
    # the ONE live 'OUI' that was just typed: the operator should not pay for a second ceremony for
    # what they just authorized, and a gate slower than the wall right beside it is never taken
    # (measured 2026-07-27, 20:1). If the write fails, the approval STILL HOLDS and
    # `policy-appliquer` remains the recovery path — with its own terminal gate.
    try:
        items = ledger.approved_items_for_apply(args.id)
    except (
        PolicyRequestError
    ) as exc:  # pragma: no cover - approve() just succeeded right above
        print(f"Approved, but nothing to apply: {exc}", file=sys.stderr)
        return 2
    code = _perform_apply(ledger, args.id, items, Path(args.policy_path))
    if code != 0:
        print(
            f"The approval HOLDS. Recovery: make policy-appliquer ID={args.id} CONFIRM=1",
            file=sys.stderr,
        )
    return code


def _cmd_refuser(ledger: PolicyRequestLedger, args: argparse.Namespace) -> int:
    if not args.id:
        print("ID= is required.", file=sys.stderr)
        return 2
    state = ledger.state(args.id)
    if state is None:
        print(f"Unknown request: {args.id}", file=sys.stderr)
        return 2
    if not args.raison.strip():
        print("RAISON= is required (why you are refusing).", file=sys.stderr)
        return 2
    _print_request_content(state)
    if not _read_terminal_confirmation(
        f"[policy-refuser {args.id}] Type OUI to refuse this request: "
    ):
        print(
            "ABANDONED: no 'OUI' given LIVE on a terminal (D159/D74) — nothing is refused.",
            file=sys.stderr,
        )
        return 1
    try:
        ledger.refuse(args.id, reason=args.raison, by="terminal (/dev/tty), D159")
    except PolicyRequestError as exc:
        print(f"Refusal refused (!): {exc}", file=sys.stderr)
        return 2
    print(f"Request {args.id} refused: {args.raison}")
    print("Nothing is erased (inv. 2) — the full history stays readable in the journal.")
    return 0


def _cmd_appliquer(ledger: PolicyRequestLedger, args: argparse.Namespace) -> int:
    if not args.id:
        print("ID= is required.", file=sys.stderr)
        return 2
    try:
        items = ledger.approved_items_for_apply(args.id)
    except PolicyRequestError as exc:
        print(f"Application refused: {exc}", file=sys.stderr)
        return 2
    policy_path = Path(args.policy_path)
    if not args.confirm:
        print(f"[DRY-RUN] {len(items)} item(s) would be applied to {policy_path}:")
        for item in items:
            print(f"  - {_item_line(item)}")
        print("\nNothing was written. Re-run with CONFIRM=1 to make the gesture.")
        return 0
    # ── THE GATE OF THE GESTURE, on the path that WRITES (D159, hardened 2026-07-28) ───────────
    # An isolated audit showed, and a counter-proof confirmed end to end, that the /dev/tty seal
    # only lived in `approuver`: a ledger whose path the caller chooses (`--ledger`) validates
    # against itself (`approved_content_hash` and `content_hash()` come from the SAME file), and
    # `appliquer --confirm` wrote without ever asking for a terminal. The seal was not bypassed:
    # it was simply not on that path. It is now, and the prompt NAMES the target file — a target
    # diverted via `--policy-path` can no longer be invisible at the moment the human accepts.
    if not _read_terminal_confirmation(
        f"[policy-appliquer {args.id}] Type OUI to WRITE these {len(items)} item(s) to "
        f"{policy_path}: "
    ):
        print(
            "ABANDONED: no 'OUI' given LIVE on a terminal (D159/D74). Nothing was written. A "
            "journaled approval is not enough to write: it is the living gesture that authorizes "
            "the write, and an agent cannot make it.",
            file=sys.stderr,
        )
        return 1
    return _perform_apply(ledger, args.id, items, policy_path)


def _perform_apply(
    ledger: PolicyRequestLedger, id_: str, items: tuple[PolicyItem, ...], policy_path: Path
) -> int:
    """Write the approved items and journal the diff. **Callers gate this on a live terminal word.**

    Extracted so the ONE write path is shared by ``approuver`` (which applies in the same breath as
    the approval — one command, one word, no second ceremony) and by ``appliquer`` (the retry, for
    when the write itself failed). Two call sites, one body: a hardening added to the gate can never
    protect one verb and miss the other."""
    try:
        applied = policy_writer.apply_to_file(policy_path, items)
    except PolicyWriteError as exc:
        print(f"Write refused: {exc}", file=sys.stderr)
        return 2
    diff = {
        "egress_added": list(applied.egress_added),
        "domains_added": [[b, list(v)] for b, v in applied.domains_added],
        "contracts_added": [list(pair) for pair in applied.contracts_added],
    }
    ledger.record_application(id_, diff=diff)
    if applied.is_noop:
        print(f"Nothing new to write for {id_} (already present in {policy_path}).")
    else:
        print(f"{policy_path} updated:")
        for host in applied.egress_added:
            print(f"  + egress: {host}")
        for bubble, values in applied.domains_added:
            print(f"  + domains[{bubble}]: {', '.join(values)}")
        for source, target in applied.contracts_added:
            print(f"  + contract: {source} -> {target}")
    print("The journal is append-only: nothing was erased (inv. 2).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="policy",
        description="The request -> examine -> approve -> apply pipeline (D159).",
    )
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH), help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("queue", help="the state of every request")

    p_demander = sub.add_parser("demander", help="file a request (or create a template)")
    p_demander.add_argument("--fichier", default="")
    p_demander.add_argument(
        "--template-path", default=str(_DEFAULT_TEMPLATE_PATH), help=argparse.SUPPRESS
    )

    p_examiner = sub.add_parser("examiner", help="print the mandate, or record a verdict")
    p_examiner.add_argument("--id", default="")
    p_examiner.add_argument("--verdict", default="")

    # D159, post-incident hardening: NO `--mot`/argument here. The word is read LIVE from
    # /dev/tty (see `_read_terminal_confirmation`) — an agent that could once type `MOT=oui` on
    # its own behalf cannot satisfy a terminal it does not control, no matter what it passes here.
    p_approuver = sub.add_parser(
        "approuver", help="the operator's gesture — a OUI typed LIVE on the terminal"
    )
    p_approuver.add_argument("--id", default="")
    # The approval WRITES, in the same gesture: the target is therefore its own too (canonical by
    # default, hidden — the tests inject it, the human never types it).
    p_approuver.add_argument(
        "--policy-path", default=str(_DEFAULT_POLICY_PATH), help=argparse.SUPPRESS
    )

    p_refuser = sub.add_parser("refuser", help="the same gesture, the other way")
    p_refuser.add_argument("--id", default="")
    p_refuser.add_argument("--raison", default="")

    p_appliquer = sub.add_parser("appliquer", help="write policy.toml — dry-run by default")
    p_appliquer.add_argument("--id", default="")
    p_appliquer.add_argument("--confirm", action="store_true")
    p_appliquer.add_argument(
        "--policy-path", default=str(_DEFAULT_POLICY_PATH), help=argparse.SUPPRESS
    )

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    ledger = PolicyRequestLedger(Path(args.ledger))

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
