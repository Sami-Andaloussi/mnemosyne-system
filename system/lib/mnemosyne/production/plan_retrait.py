"""Withdrawing a plan item (H1, D159) — the PIPELINE, not a second implementation.

**What this module RE-USES, and what it does not reinvent.** D159 built a four-role pipeline to
widen an authorisation — request (any agent) → examine (an ISOLATED agent, D75, that can only
NARROW) → approve (the operator, one exact word, LIVE on `/dev/tty`, never an argument) → apply —
and a real incident (D160) showed what breaks when the approval is just a word any caller can
satisfy. `H1` asks for the SAME pipeline for a different question: withdrawing an item from a plan
rather than widening a policy.

What is carried over IDENTICALLY, by IMPORT, never recopied:
:func:`~mnemosyne.runtime.human_gate.read_live_confirmation` — the repo's only tty gate, already
proven against a real pseudo-terminal (D164). What is REBUILT, because the data is different (a
set of plan identifiers, not domain/host `PolicyItem`): the examiner's narrowing, the content hash,
the ledger.

**The `apply` step — written here, still NOT wired to any `make` target.** :func:`applique_retrait`
transforms a TEXT (never a file): it changes each withdrawn item's status glyph to
```` (the ``clos`` status — inv. 2, NOTHING is deleted), and inserts, right after the bullet, a
SINGLE-LINE, self-closing HTML comment carrying the reason and the cost — invisible to the field
reader (the `A1`/`A7` fixes of this same module made it so), so it cannot steal a neighbouring
field's value. :meth:`RetraitLedger.appliquer_verifie` is the ONLY method that writes to disk, and
it journals ``applied`` only AFTER re-reading the file back off disk and confirming the written
text is genuinely there — never on the strength of the text it just produced
(D161: *"an applied that is not re-read afterwards is not an applied, it is an intention"*).

As long as this module is called by NO `make` target, it cannot produce a false refusal for
anyone — which is why it stays built and proven ISOLATED before being wired in.

**The "impossible" threshold, made precise — the same doctrine as D159, not a stronger one.** Only
one public method can produce an ``approved`` event (:meth:`RetraitLedger.approuver_en_direct`),
and it reads `/dev/tty` itself, unconditionally — there is NO second public path with a ``word=``
parameter a caller could satisfy without a terminal (this is exactly the shape of the D160
incident: a word passed as an argument, attributed to the operator without them having typed it).
As with ``policy_requests.py``: this defends against the normal API on a single-user machine, not
against an adversary who can already write this JSONL file directly — this is not the same kind of
guarantee as a signed token, and this module does not claim to be.

Decisions: D159/D160/D164 (the pipeline, the incident, the shared gate) · D75 (isolated examiner) ·
D82/inv. 2 (append-only, non-destructive ledger) · D147 (their decision, never their keystroke —
except the word, which IS the decision). English code for identifiers (D117); status tags stay
French.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from ..runtime.human_gate import read_live_confirmation
from .plan_format import STATUS_BY_GLYPH, read_plan

_REPO_ROOT: Final = Path(__file__).resolve().parents[4]
DEFAULT_LEDGER_PATH: Final = _REPO_ROOT / "system" / "state" / "retraits_requests.jsonl"

#: Bumped on any breaking change to the event shape; replay refuses an unknown ``kind`` rather
#: than silently skip a governance-relevant gesture (mirrors policy_requests.py, D82).
_FORMAT: Final = 1

_MAX_FREE_TEXT_CHARS: Final = 2000
_MAX_FREE_TEXT_LINES: Final = 20


class RetraitError(Exception):
    """Refuses a malformed demand, an impossible narrowing, or an operation on an unknown id."""


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sans_caractere_de_controle(
    text: str, *, champ: str, autorise_saut_de_ligne: bool = False
) -> None:
    """Refuse a control character (or an oversized field) at the moment it is RECORDED, not only
    when eventually printed — the same source-side guard D159's 2nd audit added for policy
    requests, rebuilt here rather than imported because it is `policy_requests`'s own private
    helper, not a shared utility: importing a leading-underscore name across modules would make
    THIS module depend on that one's internals changing underneath it without notice."""
    for ch in text:
        if ch == "\n" and autorise_saut_de_ligne:
            continue
        if ord(ch) < 0x20:
            raise RetraitError(f"{champ} cannot contain a control character")
    if len(text) > _MAX_FREE_TEXT_CHARS:
        raise RetraitError(f"{champ} is too long ({len(text)} char., max {_MAX_FREE_TEXT_CHARS})")
    if autorise_saut_de_ligne and text.count("\n") > _MAX_FREE_TEXT_LINES:
        raise RetraitError(f"{champ} has too many lines (max {_MAX_FREE_TEXT_LINES})")


def _retrecissement_valide(retreci: tuple[str, ...], original: tuple[str, ...]) -> bool:
    """Whether ``retreci`` is a genuine, non-empty SUBSET of ``original`` — the structural
    guarantee behind a "narrow" verdict, ported from D159's ``_is_item_subset`` to a simpler
    payload (bare identifiers, not typed policy items): an examiner can drop an item from the
    retrait, never add one that was not already on the table, no matter what its notes claim."""
    return bool(retreci) and set(retreci) <= set(original)


def _hash_contenu(items: tuple[str, ...], motif: str, cout: str, requested_by: str) -> str:
    """Deterministic hash over the SEMANTIC content — what an approval binds to. ``items`` is
    sorted before hashing so two callers requesting the same set in a different order collide
    on the same id, exactly like ``PolicyChangeRequest`` — filing is meant to be idempotent."""
    payload = json.dumps(
        {"items": sorted(items), "motif": motif, "cout": cout, "requested_by": requested_by},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


#: The glyph a withdrawal sets — ``clos`` (STATUS_BY_GLYPH), inv. 2: nothing is deleted, the item
#: stays in the same place, at the same position in the order, with its text intact. Only its status changes.
_GLYPHE_RETRAIT: Final = "\U000026D4"

#: Recognises ONLY the canonical form `read_plan` knows how to read — bullet, `**IDENT**`, a known
#: glyph. An item written in another notation (a checkbox, an unknown glyph) is left intact and
#: `applique_retrait` REFUSES rather than guess where to cut a line it does not recognise.
_PUCE_GLYPHE_RE: Final = re.compile(r"^(\s*[-*]\s*\*\*[^*]+\*\*\s*)(\S+)")


def _sur_une_seule_ligne_de_commentaire(text: str) -> str:
    """Makes ``text`` safe inside a self-closing, SINGLE-LINE HTML comment.

    AUDIT DELEGATED ON 2026-08-15, WITHIN H1's CLAUSE: `RetraitDemande` allows a line break in
    `motif` (a motif can be a multi-sentence explanation) — but the comment `applique_retrait`
    writes is a SINGLE element of `lines`, inserted as one line. A motif carrying a `\\n`
    **silently breaks this assumption**: `"\\n".join` turns it back into SEVERAL physical lines.
    Worse, a motif carrying `-->` (even without a line break — the same CommonMark rule turn 3 of
    A7 learned the hard way: the FIRST `-->` closes it, no exceptions) closes the comment BEFORE
    the intended end, and everything that follows — including an item bullet the attacker placed
    inside the motif — becomes REAL plan content. Measured by the auditor: a PHANTOM item
    injected, accepted by the real CLI.

    Line breaks remain a legitimate SEMANTIC value of `motif`/`cout` (displayed as-is by
    `queue`) — it is only AT WRITE TIME inside THIS specific comment that they are dangerous.
    """
    aplati = " / ".join(text.splitlines())
    return aplati.replace("-->", "--⁠>")  # ⁠ = WORD JOINER, invisible, breaks the sequence


def applique_retrait(
    texte: str, items: tuple[str, ...], *, motif: str, cout: str, id_retrait: str, quand: str
) -> str:
    """Closes each item of ``items`` in ``texte`` — PURE: takes text, returns text, writes
 nothing. :meth:`RetraitLedger.appliquer_verifie` is the only one allowed to act on it.

 For each item: its bullet's glyph switches to ```` (``clos``) and a self-closing, single-line
 HTML comment line is inserted right after — never a rewrite of the item's text, never a
 deletion. The comment is invisible to the field reader (the same mechanism `A1`/`A7` close
 elsewhere in this module), so it cannot steal a neighbouring field's value nor fabricate one.

 **REFUSES rather than guessing**, in three cases: an item absent from ``texte`` (the plan
 changed since the approval); an item already ``clos`` (a duplicate withdrawal, the trace
 already exists); a bullet whose shape is not one the reader recognises (`_PUCE_GLYPHE_RE`
 does not match) — a named refusal beats a line cut in the wrong place.

 Checks AFTER the transformation, before returning anything, that **every non-targeted item
 is read back IDENTICALLY** — the same guarantee each citation fix measured against the real
 corpus this session: a withdrawal that moves a neighbour is not a withdrawal, it is a bug.
 """
    before = read_plan(texte)
    by_ident = {it.ident: it for it in before.items}
    manquants = [i for i in items if i not in by_ident]
    if manquants:
        raise RetraitError(f"item(s) absent from the plan at the moment of applying: {manquants}")
    deja_clos = [i for i in items if by_ident[i].status == "clos"]
    if deja_clos:
        raise RetraitError(f"item(s) already closed -- duplicate withdrawal: {deja_clos}")

    lines = texte.split("\n")
    # Bottom to top: inserting a line above shifts every line number BELOW it, never the ones
    # above — processing in DECREASING line order is what keeps each already-computed `item.line`
    # still accurate by the time it is used.
    cible = sorted((by_ident[i].line for i in items), reverse=True)
    for ligne_1_based in cible:
        rang = ligne_1_based - 1
        m = _PUCE_GLYPHE_RE.match(lines[rang])
        if not m or m.group(2) not in STATUS_BY_GLYPH:
            raise RetraitError(
                f"line {ligne_1_based} does not have the recognised bullet form -- refusing "
                "rather than guessing"
            )
        lines[rang] = m.group(1) + _GLYPHE_RETRAIT + lines[rang][m.end(2) :]
        motif_safe = _sur_une_seule_ligne_de_commentaire(motif)
        cout_safe = _sur_une_seule_ligne_de_commentaire(cout)
        commentaire = (
            f"  <!-- RETRAIT (H1) id={id_retrait} le={quand} motif={motif_safe} cout={cout_safe} -->"
        )
        lines.insert(rang + 1, commentaire)
    after = "\n".join(lines)

    # The proof is about the ITEM, not the TEXT: two plans can differ byte for byte (a closed
    # bullet shifts every line number below it) while still being the SAME plan for anyone reading
    # it by identifier — which is what `read_plan` already does to publish a stable map.
    reread_after = read_plan(after)
    apres_par_ident = {it.ident: it for it in reread_after.items}
    for it in before.items:
        if it.ident in items:
            continue
        autre = apres_par_ident.get(it.ident)
        if autre is None or autre.fields != it.fields:
            raise RetraitError(
                f"the withdrawal changed a NON-TARGETED item ({it.ident}) -- refusing, nothing is "
                "written"
            )
    for i in items:
        if apres_par_ident[i].status != "clos":
            raise RetraitError(f"item {i}: the glyph did not become 'clos' after transformation")
    return after


@dataclass(frozen=True, slots=True)
class RetraitDemande:
    """One filed ask: retire these plan items, for this reason, at this cost.

    ``items`` travels as an immutable, sorted, de-duplicated tuple — the same identifier given
    twice is not two reasons to retire it, and the ORDER a caller happened to list them in must
    never change the id two equivalent requests get.
    """

    items: tuple[str, ...]
    motif: str
    cout: str
    requested_by: str

    def __post_init__(self) -> None:
        deduped = tuple(sorted({item.strip() for item in self.items if item.strip()}))
        if not deduped:
            raise RetraitError("a withdrawal request must target at least one item")
        object.__setattr__(self, "items", deduped)
        if not self.motif.strip():
            raise RetraitError(
                "a withdrawal request must carry a non-empty motif — the why, not just the what"
            )
        if not self.cout.strip():
            raise RetraitError(
                "a withdrawal request must carry a non-empty cout — even 'aucun', but written"
            )
        _sans_caractere_de_controle(self.motif, champ="motif", autorise_saut_de_ligne=True)
        _sans_caractere_de_controle(self.cout, champ="cout")
        _sans_caractere_de_controle(self.requested_by, champ="requested_by")

    def content_hash(self) -> str:
        return _hash_contenu(self.items, self.motif, self.cout, self.requested_by)


@dataclass(frozen=True, slots=True)
class RetraitEtat:
    """The CURRENT state of one request, folded from the event log. ``items`` reflects the
    examiner's narrowing if one happened — an approval always binds to what is ACTUALLY on the
    table, never to the filer's original, possibly-wider ask (same stance as `RequestState`)."""

    id: str
    items: tuple[str, ...]
    motif: str
    cout: str
    requested_by: str
    filed_at: str
    examined: bool = False
    examiner_verdict: str = ""
    examiner_notes: str = ""
    approved: bool = False
    approved_at: str = ""
    approved_content_hash: str = ""
    refused: bool = False
    refused_reason: str = ""
    refused_by: str = ""
    refused_at: str = ""
    applied: bool = False
    applied_at: str = ""
    #: AUDIT DELEGATED ON 2026-08-15, OUTSIDE H1's clause but measured AGAINST it: the clause
    #: "and by the trace of what the refusal wrote" was EMPTY — a withdrawal with no GO failed
    #: (RetraitError raised), but NOTHING touched disk: neither the refusal to apply without
    #: approval, nor the failure of an attempt to forge the approval. Measured 0 bytes, 4 times.
    #: An agent could hammer `approuver`/`appliquer --confirm` indefinitely, zero footprint.
    denied_count: int = 0
    last_denied_at: str = ""
    last_denied_reason: str = ""
    last_denied_by: str = ""

    @property
    def stage(self) -> str:
        if self.applied:
            return "applique"
        if self.refused:
            return "refuse"
        if self.approved:
            return "approuve"
        if self.examined:
            return "examine"
        return "depose"

    def content_hash(self) -> str:
        return _hash_contenu(self.items, self.motif, self.cout, self.requested_by)


class RetraitLedger:
    """Append-only, replayable ledger of the demander/examiner/approuver pipeline (D159/D82),
    for plan-item retraits. Stops at `approuve`/`refuse` on purpose — see the module docstring."""

    __slots__ = ("_path",)

    def __init__(self, path: Path | str = DEFAULT_LEDGER_PATH) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _append(self, event: dict[str, object]) -> None:
        """Write-ahead, fail-CLOSED: flushed and fsync'd before returning, and any I/O error
        PROPAGATES — a gesture that could not be journaled must not appear to have been made."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    # -- the request gesture (any agent) -------------------------------------------------------
    def file(self, demande: RetraitDemande) -> str:
        """Assign a stable id (a content-hash prefix) and journal the ``filed`` event. Filing the
        SAME content twice returns the SAME id rather than duplicating an entry."""
        id_ = demande.content_hash()[:12]
        if self.state(id_) is not None:
            return id_
        self._append(
            {
                "v": _FORMAT,
                "kind": "filed",
                "id": id_,
                "at": _utcnow_iso(),
                "items": list(demande.items),
                "motif": demande.motif,
                "cout": demande.cout,
                "requested_by": demande.requested_by,
            }
        )
        return id_

    # -- the examine gesture (an isolated, adversarial agent — D75) ----------------------------
    def record_examination(
        self,
        id_: str,
        *,
        verdict: str,
        narrowed_items: tuple[str, ...] | None = None,
        notes: str = "",
        examiner: str = "isolated agent",
    ) -> None:
        """Record what the examiner found. NEVER sets ``approved`` or ``refused`` — a "reject"
        verdict is a strong recommendation the operator sees, not an automatic refusal (D100:
        examination informs, it does not decide).

        A "narrow" verdict is checked to be a genuine, non-empty SUBSET of the current items
        (:func:`_retrecissement_valide`): an examiner cannot smuggle a brand-new identifier in
        under the "narrow" label, regardless of what its own notes claim."""
        if verdict not in ("allow", "narrow", "reject"):
            raise RetraitError(f"unknown examiner verdict: {verdict!r}")
        _sans_caractere_de_controle(notes, champ="notes", autorise_saut_de_ligne=True)
        prior = self.state(id_)
        if prior is None:
            raise RetraitError(f"cannot examine an unknown request: {id_!r}")
        event: dict[str, object] = {
            "v": _FORMAT,
            "kind": "examined",
            "id": id_,
            "at": _utcnow_iso(),
            "verdict": verdict,
            "notes": notes,
            "examiner": examiner,
        }
        if verdict == "narrow":
            if not narrowed_items:
                raise RetraitError("a 'narrow' verdict requires at least one narrowed item")
            if not _retrecissement_valide(narrowed_items, prior.items):
                # AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): "the exact same class" as the
                # member judged by H1's clause, on D159's CENTRAL attack -- an isolated examiner
                # smuggling in an identifier never on the table under the 'narrow' label.
                # Measured: 5 attempts, 0 bytes. An examiner could hammer this attempt
                # indefinitely, zero footprint.
                self._append(
                    {
                        "v": _FORMAT,
                        "kind": "denied",
                        "id": id_,
                        "at": _utcnow_iso(),
                        "reason": (
                            "invalid 'narrow' verdict -- narrowed_items contains an identifier "
                            "absent from the current request (D159)"
                        ),
                        "stade": prior.stage,
                        "by": examiner,
                    }
                )
                raise RetraitError(
                    "a 'narrow' verdict can only WITHDRAW, never add -- narrowed_items contains "
                    "an identifier absent from the current request (D159)"
                )
            event["narrowed_items"] = list(narrowed_items)
        self._append(event)

    # -- the refuse gesture (the operator, or a caller relaying their word) ---------------------
    def refuse(self, id_: str, *, reason: str, by: str) -> None:
        state = self.state(id_)
        if state is None:
            raise RetraitError(f"unknown withdrawal request: {id_!r}")
        # AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): nothing guarded this case -- a withdrawal
        # ALREADY APPLIED (already written to a real plan) could still be "refused", leaving a
        # contradictory state: `stage` answers 'applique' (it looks at `applied` first), but
        # `render_queue` ALSO prints the refusal line, because it tests `state.refused`
        # independently of `stage`. A refusal does not undo a write already made (inv. 2) -- the
        # gesture that applies here is not "refuse", it is withdrawing the item a second time.
        if state.stage == "applique":
            raise RetraitError(
                f"request {id_!r} already applied on {state.applied_at} — a refusal does not "
                "undo a write already made"
            )
        if not reason.strip():
            raise RetraitError("a refusal must carry a non-empty reason")
        _sans_caractere_de_controle(reason, champ="reason", autorise_saut_de_ligne=True)
        _sans_caractere_de_controle(by, champ="by")
        self._append(
            {
                "v": _FORMAT,
                "kind": "refused",
                "id": id_,
                "at": _utcnow_iso(),
                "reason": reason,
                "by": by,
            }
        )

    # -- the approve gesture (the operator, ONE word, LIVE) — the ONLY path in, see module doc --
    def approuver_en_direct(self, id_: str, *, by: str) -> bool:
        """The ONLY method that can produce an ``approved`` event. Reads ``/dev/tty`` itself,
        unconditionally — there is no ``word=`` parameter here for a caller to satisfy without a
        terminal, which is precisely the shape of the D160 incident this pipeline exists to make
        structurally unrepeatable.

        Fails CLOSED: returns ``False`` (never raises for a "no") on refusal, a typo, or no
        controlling terminal at all (an agent subprocess, a pipe, CI) — a level-3 incapacity does
        not distinguish "declined" from "cannot be asked here"; both mean no gesture happened.

        ``by`` has no default (D160's fix, carried here identically): this method cannot verify
        who is at the keyboard, so it must never silently CLAIM an identity either. The caller
        states the MECHANISM it actually observed, e.g. ``by="terminal (/dev/tty), D159"``.
        """
        state = self.state(id_)
        if state is None:
            raise RetraitError(f"unknown withdrawal request: {id_!r}")
        if state.refused:
            # AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): this branch is ONE LINE above the one
            # the first fix instrumented in this SAME method -- missed. Measured: 5 attempts, 0
            # bytes, exactly the same class as the member the clause judges. An attempt to
            # approve an already-refused request hammered indefinitely left the same zero
            # footprint.
            self._append(
                {
                    "v": _FORMAT,
                    "kind": "denied",
                    "id": id_,
                    "at": _utcnow_iso(),
                    "reason": "request already refused — file a new request",
                    "stade": state.stage,
                    "by": by,
                }
            )
            raise RetraitError(f"request {id_!r} already refused — file a new request")
        prompt = (
            f"\nWITHDRAWAL requested — items: {', '.join(state.items)}\n"
            f"motif: {state.motif}\n"
            f"cout : {state.cout}\n"
            "Type YES live to approve, anything else to refuse: "
        )
        if not read_live_confirmation(prompt):
            # AUDIT DELEGATED ON 2026-08-15: this path returned `False` WITHOUT JOURNALLING
            # ANYTHING -- a forgery attempt (or a plain "no") left ZERO trace. Journalled HERE,
            # not only in the CLI that calls this method: a future second caller (as
            # `_cmd_refuser`/`_cmd_appliquer` learned the hard way) must not be able to forget to
            # trace a failed approval.
            self._append(
                {
                    "v": _FORMAT,
                    "kind": "denied",
                    "id": id_,
                    "at": _utcnow_iso(),
                    "reason": "no LIVE confirmation received on /dev/tty",
                    "stade": state.stage,
                    "by": by,
                }
            )
            return False
        self._append(
            {
                "v": _FORMAT,
                "kind": "approved",
                "id": id_,
                "at": _utcnow_iso(),
                "content_hash": state.content_hash(),
                "by": by,
            }
        )
        return True

    # -- the apply gesture — writes, then RE-READS FROM DISK before it believes itself -----------
    def appliquer_verifie(self, id_: str, *, chemin: Path, by: str) -> None:
        """The ONLY method that writes a retrait to a plan file — and the ONLY one that can
        journal ``applied``. Never trusts the text it just produced: it writes, closes the
        handle, RE-READS the file back off disk, and only journals if what comes back contains
        the change it meant to make (D161 — a write that is not re-verified after the fact is an
        intention, not an application; this repo already paid for that gap once).

        Requires ``approuve`` — an item cannot be applied off a request that was never approved,
        or one whose approval no longer matches the CURRENT items (the same staleness guard
        `approved_content_hash` already gives `policy_requests.py`).
        """
        state = self.state(id_)
        if state is None:
            raise RetraitError(f"unknown withdrawal request: {id_!r}")
        # Validates `by` BEFORE any disk write, including the two refusals just below: otherwise
        # a malformed `by` (a control character) would reach the journal through the refusal
        # branch without ever going through the check the success branch already imposes below.
        _sans_caractere_de_controle(by, champ="by")
        # AUDIT DELEGATED ON 2026-08-15: "a withdrawal with no GO is refused" held (RetraitError
        # raised), but its clause "and by the trace of what the refusal wrote" was EMPTY -- these
        # two refusals wrote NOTHING to disk. Measured: 0 bytes, 4 times. Journalled HERE, before
        # raising, so the refusal itself leaves a trace independently of who calls this method or
        # of what its caller chooses to print.
        if state.stage != "approuve":
            self._append(
                {
                    "v": _FORMAT,
                    "kind": "denied",
                    "id": id_,
                    "at": _utcnow_iso(),
                    "reason": f"stage {state.stage!r} -- only 'approuve' can be applied",
                    "stade": state.stage,
                    "by": by,
                }
            )
            raise RetraitError(
                f"request {id_!r} is at stage {state.stage!r} — only 'approuve' can be applied"
            )
        if state.approved_content_hash != state.content_hash():
            self._append(
                {
                    "v": _FORMAT,
                    "kind": "denied",
                    "id": id_,
                    "at": _utcnow_iso(),
                    "reason": "the approved content no longer matches the current state",
                    "stade": state.stage,
                    "by": by,
                }
            )
            raise RetraitError(
                f"request {id_!r}: the approved content no longer matches the current state"
            )

        before = chemin.read_text(encoding="utf-8")
        quand = _utcnow_iso()
        after = applique_retrait(
            before, state.items, motif=state.motif, cout=state.cout, id_retrait=id_, quand=quand
        )
        chemin.write_text(after, encoding="utf-8")

        # **THE RE-READ COMES FROM DISK, NEVER FROM `after`.** A correct `after` in memory
        # proves nothing about what ACTUALLY HAPPENED — a missing fsync, a concurrent write, a
        # second withdrawal on the same file between the write and this point, and the disk would
        # carry something other than what we believe we wrote. This is exactly what D161 closed
        # elsewhere.
        reread = chemin.read_text(encoding="utf-8")
        if reread != after:
            raise RetraitError(
                f"the write to {chemin} was not read back identically — withdrawal NOT journalled"
            )
        relecture = read_plan(reread)
        by_ident = {it.ident: it for it in relecture.items}
        for item_ident in state.items:
            releu = by_ident.get(item_ident)
            if releu is None or releu.status != "clos":
                raise RetraitError(
                    f"item {item_ident}: read back from disk, its status is NOT 'clos' — "
                    "withdrawal NOT journalled"
                )

        self._append(
            {
                "v": _FORMAT,
                "kind": "applied",
                "id": id_,
                "at": quand,
                "chemin": str(chemin),
                "by": by,
            }
        )

    # -- replay ---------------------------------------------------------------------------------
    def state(self, id_: str) -> RetraitEtat | None:
        return self._replay().get(id_)

    def all_states(self) -> tuple[RetraitEtat, ...]:
        return tuple(self._replay().values())

    def _replay(self) -> dict[str, RetraitEtat]:
        """Fold every event into the current state per id. Fail-closed on a genuinely malformed
        internal line (never silently skip a decision); tolerates a truncated FINAL line — the
        write-ahead recovery case, a crash mid-append is a gesture RAM never saw either (D82)."""
        states: dict[str, RetraitEtat] = {}
        if not self._path.exists():
            return states
        lines = self._path.read_text(encoding="utf-8").splitlines()
        for offset, raw in enumerate(lines):
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                if offset == len(lines) - 1:
                    break  # truncated write-ahead tail — not a decision, a crash mid-append
                raise RetraitError(f"line {offset + 1} of the withdrawal journal is corrupt")
            if event.get("v") != _FORMAT:
                raise RetraitError(f"line {offset + 1} carries an unknown format version")
            kind = event.get("kind")
            id_ = event["id"]
            if kind == "filed":
                states[id_] = RetraitEtat(
                    id=id_,
                    items=tuple(event["items"]),
                    motif=event["motif"],
                    cout=event["cout"],
                    requested_by=event["requested_by"],
                    filed_at=event["at"],
                )
            elif kind == "examined":
                prior = states[id_]
                items = (
                    tuple(event["narrowed_items"]) if event["verdict"] == "narrow" else prior.items
                )
                # **THIS BRANCH REBUILT THE STATE FROM SCRATCH — the only one of the five NOT
                # using `replace()`.** An examination happening AFTER an approval (or a refusal)
                # silently erased `approved`/`approved_content_hash`/`refused`, letting them fall
                # back to their defaults (False/""), so `stage` REGRESSED from "approuve" to
                # "examine" instead of staying "approuve" with a now-STALE hash — exactly what
                # `appliquer_verifie` is supposed to catch explicitly. Found by a witness that was
                # testing something else (the hash's staleness) and bit here first. *A rewrite
                # loses what it does not recopy* -- the same fault A1/A7 closed on the READER
                # side, here on the STATE side.
                states[id_] = replace(
                    prior,
                    items=items,
                    examined=True,
                    examiner_verdict=event["verdict"],
                    examiner_notes=event["notes"],
                )
            elif kind == "approved":
                # `replace()`, never `**prior.__dict__`: a `slots=True` dataclass has NO
                # `__dict__` — the first version of this line would have raised `AttributeError`
                # on its very first call, never tested in isolation from the class that carries it.
                states[id_] = replace(
                    states[id_],
                    approved=True,
                    approved_at=event["at"],
                    approved_content_hash=event["content_hash"],
                )
            elif kind == "refused":
                # AUDIT DELEGATED ON 2026-08-15: `by` and `at` already travelled in the EVENT
                # (see refuse()) but this fold discarded them — RetraitEtat, the ONLY thing
                # render_queue reads, could therefore never show them. The trace existed for a
                # reader of the raw JSONL, not for the operator. Sabotage-proven: removing
                # `by`/`at` from here made no witness turn red before this fix.
                states[id_] = replace(
                    states[id_],
                    refused=True,
                    refused_reason=event["reason"],
                    refused_by=event.get("by", ""),
                    refused_at=event["at"],
                )
            elif kind == "denied":
                prior = states[id_]
                states[id_] = replace(
                    prior,
                    denied_count=prior.denied_count + 1,
                    last_denied_at=event["at"],
                    last_denied_reason=event["reason"],
                    last_denied_by=event["by"],
                )
            elif kind == "applied":
                states[id_] = replace(states[id_], applied=True, applied_at=event["at"])
            else:
                raise RetraitError(
                    f"line {offset + 1} carries an unknown event kind: {kind!r}"
                )
        return states
