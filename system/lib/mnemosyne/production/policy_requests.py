"""policy_requests (D159) — the demander -> examiner -> approuver pipeline, durable and content-bound.

The filing signalement names the trap explicitly: "a security agent validates then applies" LOOKS
like it satisfies both "no agent widens its own authority" and "no code / text-editor from the user" —
but it destroys the first guarantee invisibly, because an agent that approves is still an agent.
The correct decomposition keeps FOUR roles distinct, and this module owns the durable state of the
first three (the fourth, actually WRITING policy.toml, is :mod:`.policy_writer`, invoked only after
this ledger confirms an approval matches exactly what is about to be applied):

* **demander** — any agent files a structured, machine-checkable :class:`PolicyChangeRequest`.
* **examiner** — an ISOLATED, adversarial agent (D75: the strongest available model, never the
  filer) may narrow the request. Its verdict is recorded here but never auto-decides anything —
  see :meth:`PolicyRequestLedger.record_examination`, which cannot set ``approved`` or ``refused``.
* **approuver** — ONLY the user, via :meth:`PolicyRequestLedger.approve`, which requires the exact
  word ``"oui"`` (never a near-miss, never inferred from context) and binds the approval to the
  content hash of whatever is on the table AT THAT MOMENT (the examiner's narrowed items if any).

**Fail-closed: a pending request IS a refusal.** :meth:`PolicyRequestLedger.approved_items_for_apply`
is the ONLY way to get items back out for :func:`~mnemosyne.production.policy_writer.apply_to_file`
to consume, and it refuses (never returns a permissive "in progress" value) unless the CURRENT
state is approved, not yet applied, AND its content hash still matches what was actually approved —
so a request re-examined or re-edited AFTER approval cannot silently ride on the old "oui". Be
precise about what this hash binding is and is not: it is a STALENESS guard (it catches a request
that moved on after the user said "oui", the same failure mode :meth:`record_examination`'s subset
check closes on the examiner's side), not a cryptographic seal — anything that can write this
JSONL file at all could forge an "approved" event outright, the same way it could edit
``policy.toml`` directly. This ledger's threat model is a SINGLE-USER local machine (mirrors D147:
the danger axis is *reach toward others*, not a co-located adversary), unlike the Guard's signed
:class:`~mnemosyne.ports.guard.GrantToken`, which really does defend against a hostile in-process
caller — the two are not the same kind of guarantee.

**Durable like a gesture, not like a trace.** Every event here — filed, examined, approved,
refused, applied — is write-ahead and fail-CLOSED (:meth:`PolicyRequestLedger._append` mirrors
:class:`~mnemosyne.production.human_journal.HumanLayerJournal`: an I/O error propagates, because a
"oui" that could not be journaled must not appear to have been given). Replay is fail-closed on a
genuinely malformed internal line (never silently skip a decision) but tolerates a truncated FINAL
line (the write-ahead recovery case: a crash mid-append is a gesture RAM never saw either, D82).

Decisions: D159 (this pipeline) · D75 (producer ≠ verifier — the examiner is isolated from the
filer) · D92 / D100 (propose, never impose — examination informs, it does not decide) · D82
(durable human-gesture journal) · invariant 2 (append-only, non-destructive). Code English
(D117); what the CLI prints is French (the operator reads it).
"""

from __future__ import annotations

import hashlib
import json
import os
import tomllib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from .policy_writer import PolicyItem

_REPO_ROOT: Final = Path(__file__).resolve().parents[4]
DEFAULT_LEDGER_PATH: Final = _REPO_ROOT / "system" / "state" / "policy_requests.jsonl"

#: Event schema version — bumped on any breaking change; replay refuses an unknown ``kind``
#: rather than silently skip a governance-relevant gesture (mirrors human_journal.py's D82 stance).
_FORMAT: Final = 1

#: The exact word the user's approval must spell — nothing inferred, nothing fuzzy-matched.
_APPROVAL_WORD: Final = "oui"


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class PolicyRequestError(Exception):
    """A ledger state-machine error — an unknown id, a stale or missing approval, a malformed
    request file. Distinct from :class:`~mnemosyne.production.policy_writer.PolicyWriteError`,
    which is about the TOML text itself, not the request pipeline's state."""


def _encode_item(item: PolicyItem) -> dict[str, object]:
    return {
        "kind": item.kind,
        "bubble": item.bubble,
        "values": list(item.values),
        "contract_from": item.contract_from,
        "contract_to": item.contract_to,
        "bound_name": item.bound_name,
        "bound_value": item.bound_value,
        "note": item.note,
    }


def _decode_item(data: dict[str, object]) -> PolicyItem:
    return PolicyItem(
        kind=str(data.get("kind", "")),
        bubble=str(data.get("bubble", "")),
        values=tuple(str(v) for v in data.get("values", ())),  # type: ignore[union-attr]
        contract_from=str(data.get("contract_from", "")),
        contract_to=str(data.get("contract_to", "")),
        bound_name=str(data.get("bound_name", "")),
        bound_value=int(data.get("bound_value", 0) or 0),  # type: ignore[arg-type]
        note=str(data.get("note", "")),
    )


def _canonical_payload(
    title: str, items: tuple[PolicyItem, ...], justification: str, requested_by: str
) -> str:
    """Deterministic JSON over the SEMANTIC content — the thing an approval is bound to."""
    obj = {
        "title": title,
        "items": [_encode_item(i) for i in items],
        "justification": justification,
        "requested_by": requested_by,
    }
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _content_hash(
    title: str, items: tuple[PolicyItem, ...], justification: str, requested_by: str
) -> str:
    return hashlib.sha256(
        _canonical_payload(title, items, justification, requested_by).encode("utf-8")
    ).hexdigest()


#: Bounds mirroring the CLI's own print-layer defense (`runtime/policy_run.py::_plain`) — enforced
#: HERE too so a field is well-formed at the moment it enters the ledger, not only when printed.
_MAX_FREE_TEXT_CHARS: Final = 2000
_MAX_FREE_TEXT_LINES: Final = 20


def _no_control_chars(text: str, *, field: str, allow_newline: bool = False) -> None:
    """Refuse a control character (or an oversized field) in an agent-controlled free-text field
    — title / justification / requested_by / examiner notes — at the moment it is RECORDED, not
    only when eventually printed (D159, 2nd D75 audit finding): :class:`PolicyItem` already
    refused a control character in its own ``note`` at construction; these four strings did not,
    so an examiner could push the real item list off the operator's terminal with raw ANSI escapes
    or a few hundred blank lines while ``_is_item_subset`` still let the true, wider request through
    to approval. This is the source-side half of the fix; :func:`~mnemosyne.runtime.policy_run.
    _plain` is the print-side half (belt and suspenders: a ledger line could still be replayed
    from a hand-edited or corrupted file, bypassing this constructor)."""
    for ch in text:
        if ch == "\n" and allow_newline:
            continue
        if ord(ch) < 0x20:
            raise PolicyRequestError(f"{field} may not contain a control character")
    if len(text) > _MAX_FREE_TEXT_CHARS:
        raise PolicyRequestError(
            f"{field} is too long ({len(text)} chars, max {_MAX_FREE_TEXT_CHARS})"
        )
    if allow_newline and text.count("\n") > _MAX_FREE_TEXT_LINES:
        raise PolicyRequestError(f"{field} has too many lines (max {_MAX_FREE_TEXT_LINES})")


def _is_item_subset(narrowed: tuple[PolicyItem, ...], original: tuple[PolicyItem, ...]) -> bool:
    """Whether every atomic ask in ``narrowed`` was already covered by ``original`` — the
    structural guarantee behind a "narrow" verdict (D159, post-audit fix): an examiner can
    shrink a request but can never introduce a host, a domain value, or a contract pair that
    was not already on the table, no matter what its own notes claim."""
    allowed_egress: set[str] = set()
    allowed_domains: dict[str, set[str]] = {}
    allowed_contracts: set[tuple[str, str]] = set()
    allowed_bounds: dict[str, int] = {}
    for item in original:
        if item.kind == "egress":
            allowed_egress.update(item.values)
        elif item.kind == "domains":
            allowed_domains.setdefault(item.bubble, set()).update(item.values)
        elif item.kind == "contract":
            allowed_contracts.add((item.contract_from, item.contract_to))
        elif item.kind == "bound":
            allowed_bounds[item.bound_name] = max(
                allowed_bounds.get(item.bound_name, 0), item.bound_value
            )

    for item in narrowed:
        if item.kind == "egress":
            if not set(item.values) <= allowed_egress:
                return False
        elif item.kind == "domains":
            if not set(item.values) <= allowed_domains.get(item.bubble, set()):
                return False
        elif item.kind == "contract":
            if (item.contract_from, item.contract_to) not in allowed_contracts:
                return False
        elif item.kind == "bound":
            # FOR A BOUND, NARROWING MEANS LOWERING — and the direction is not intuitive: on a
            # list, narrowing removes elements; on a number, narrowing DECREASES the value.
            # An examiner that returned 32 where 16 was asked WOULD WIDEN the request, which
            # D159's structural incapacity forbids. A bound never asked for cannot
            # appear (default 0, so any positive value exceeds it).
            if item.bound_value > allowed_bounds.get(item.bound_name, 0):
                return False
        else:  # pragma: no cover - PolicyItem.__post_init__ already refuses an unknown kind
            return False
    return True


@dataclass(frozen=True, slots=True)
class PolicyChangeRequest:
    """One bundle, filed together. The user's own reasoning in that project's pending block — "one
    decision moment, and only one" — means every item travels as ONE request: salami-slicing a
    widening into "just one more small ask" repeated over time is exactly the failure mode this
    refuses."""

    title: str
    items: tuple[PolicyItem, ...]
    justification: str
    requested_by: str

    def __post_init__(self) -> None:
        if not self.items:
            raise PolicyRequestError("a request needs at least one item")
        if not self.title.strip():
            raise PolicyRequestError("a request needs a non-empty title")
        if not self.justification.strip():
            raise PolicyRequestError(
                "a request needs a non-empty justification — why, not just what"
            )
        _no_control_chars(self.title, field="title")
        _no_control_chars(self.requested_by, field="requested_by")
        _no_control_chars(self.justification, field="justification", allow_newline=True)

    def content_hash(self) -> str:
        return _content_hash(self.title, self.items, self.justification, self.requested_by)


@dataclass(frozen=True, slots=True)
class RequestState:
    """The CURRENT state of one request, folded from the event log. ``items`` reflects the
    examiner's narrowing if one happened — this is deliberate: an approval always binds to what
    is ACTUALLY on the table, never to the filer's original, possibly-wider ask."""

    id: str
    title: str
    items: tuple[PolicyItem, ...]
    justification: str
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
    applied: bool = False
    applied_at: str = ""

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
        return _content_hash(self.title, self.items, self.justification, self.requested_by)


def request_from_toml(text: str) -> PolicyChangeRequest:
    """Parse a hand-editable request file (the shape :func:`render_template` produces).

    Raises :class:`PolicyRequestError` on a missing top-level field and lets
    :class:`~mnemosyne.production.policy_writer.PolicyWriteError` propagate from a malformed item
    (wrong kind, missing bubble, unsafe token, …) — the item validation already lives there,
    reusing it here rather than duplicating it."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PolicyRequestError(f"the request file is not valid TOML: {exc}") from exc
    try:
        title = str(data["title"])
        justification = str(data["justification"])
        requested_by = str(data["requested_by"])
        raw_items = data["items"]
    except KeyError as exc:
        raise PolicyRequestError(f"missing field in the request file: {exc}") from exc
    if not isinstance(raw_items, list) or not raw_items:
        raise PolicyRequestError("the request file declares no [[items]]")
    items = []
    for it in raw_items:
        if not isinstance(it, dict):
            raise PolicyRequestError(f"an [[items]] entry must be a table, not {type(it).__name__}")
        values = it.get("values", [])
        if not isinstance(values, list):
            # D159, post-incident hardening: `values = "macro"` is valid TOML (a bare string) and
            # `tuple(str(v) for v in "macro")` would silently iterate it into FIVE single-letter
            # "domains" (m/a/c/r/o) — each individually a valid token, so nothing downstream would
            # ever complain. Refuse the shape outright instead of guessing what was meant.
            raise PolicyRequestError(f"'values' must be a list, not {type(values).__name__}")
        items.append(
            PolicyItem(
                kind=str(it.get("kind", "")),
                bubble=str(it.get("bubble", "")),
                values=tuple(str(v) for v in values),
                contract_from=str(it.get("contract_from", "")),
                contract_to=str(it.get("contract_to", "")),
                bound_name=str(it.get("bound_name", "")),
                bound_value=int(it.get("bound_value", 0) or 0),  # type: ignore[arg-type]
                note=str(it.get("note", "")),
            )
        )
    return PolicyChangeRequest(
        title=title, items=tuple(items), justification=justification, requested_by=requested_by
    )


def render_template() -> str:
    """A fresh, hand-editable request file — the same "blank template a human fills in" shape as
    ``make signaler``'s report. Brick-free, no model."""
    return '''# Request to widen policy.toml (D159).
# ONE SINGLE block = ONE SINGLE decision moment for the user -- do not split one need into
# several small successive requests.

title = "short title, what this block opens up"
requested_by = "you (session / project / date)"
justification = """
Why -- not just what. What a refusal concretely prevents, and why THESE specific values
and not others.
"""

# One [[items]] per WIDENING. kind = "egress" | "domains" | "contract".

# [[items]]
# kind = "egress"
# values = ["api.example.org"]
# note = "short reason -- becomes a comment in policy.toml"

# [[items]]
# kind = "domains"
# bubble = "my-project"
# values = ["macro", "commodities"]

# [[items]]
# kind = "contract"
# contract_from = "knowledge"
# contract_to = "my-project"
'''


class PolicyRequestLedger:
    """Append-only, replayable ledger of the demander/examiner/approuver pipeline (D159 / D82).

    Every event is self-contained (the WHOLE request travels in ``filed``, never a bare id that
    depends on some other store), so replay never depends on anything outside this one file."""

    __slots__ = ("_path",)

    def __init__(self, path: Path | str = DEFAULT_LEDGER_PATH) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def _append(self, event: dict[str, object]) -> None:
        """Write-ahead, fail-CLOSED (mirrors :class:`~.human_journal.HumanLayerJournal`): flushed
        and fsync'd before returning, and any I/O error PROPAGATES — a gesture that could not be
        journaled must not appear to have been made."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    # -- the demander gesture (any agent) -----------------------------------------------------
    def file(self, request: PolicyChangeRequest) -> str:
        """Assign a stable id (a content-hash prefix) and journal the ``filed`` event.

        Filing the SAME content twice returns the SAME id (idempotent) rather than duplicating
        an entry — re-running ``make policy-demander`` on an unchanged file is always safe."""
        id_ = request.content_hash()[:12]
        if self.state(id_) is not None:
            return id_
        self._append(
            {
                "v": _FORMAT,
                "kind": "filed",
                "id": id_,
                "at": _utcnow_iso(),
                "title": request.title,
                "items": [_encode_item(i) for i in request.items],
                "justification": request.justification,
                "requested_by": request.requested_by,
            }
        )
        return id_

    # -- the examiner gesture (an isolated, adversarial agent — D75) --------------------------
    def record_examination(
        self,
        id_: str,
        *,
        verdict: str,
        narrowed_items: tuple[PolicyItem, ...] | None = None,
        notes: str = "",
        examiner: str = "agent isole",
    ) -> None:
        """Record what the examiner found. NEVER sets ``approved`` or ``refused`` — a "reject"
        verdict is a strong recommendation the user sees, not an automatic refusal (the trap this
        whole pipeline exists to avoid: an agent that decides is still an agent, D100).

        A "narrow" verdict is checked to be a genuine SUBSET of the current items
        (:func:`_is_item_subset`) — an isolated D75 audit of this pipeline found that nothing
        previously stopped a compromised or buggy examiner from smuggling brand-new hosts /
        domains / contracts in under the "narrow" label while the CLI printed nothing for the user
        to catch it: the label was a name, not a test. This makes it a structural incapacity
        instead: an examiner literally cannot widen a request, regardless of what it claims."""
        if verdict not in ("allow", "narrow", "reject"):
            raise PolicyRequestError(f"unknown examiner verdict {verdict!r}")
        _no_control_chars(notes, field="notes", allow_newline=True)
        prior = self.state(id_)
        if prior is None:
            raise PolicyRequestError(f"cannot examine unknown request {id_!r}")
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
                raise PolicyRequestError("a 'narrow' verdict needs at least one narrowed item")
            if not _is_item_subset(narrowed_items, prior.items):
                raise PolicyRequestError(
                    "a 'narrow' verdict can only REMOVE, never add — narrowed_items "
                    "contains a value/domain/contract absent from the current request (D159)"
                )
            event["narrowed_items"] = [_encode_item(i) for i in narrowed_items]
        self._append(event)

    # -- the approuver gesture (the user, one word) -------------------------------------------
    def approve(self, id_: str, *, word: str, by: str) -> None:
        """The ONLY way ``approved`` becomes true. ``word`` must be EXACTLY ``"oui"`` (case /
        whitespace insensitive, nothing else — never inferred, never a near-miss).

        ``by`` has NO default (post-incident fix, D159): the ledger cannot verify identity, so
        it must never silently CLAIM one either — an incident showed a hardcoded ``by="operator"``
        default let an unattended agent's own approval read, in the durable record, as if the user
        had given it. Every caller now states plainly what it actually observed (the CLI's own
        caller records the MECHANISM — a live ``/dev/tty`` confirmation — never a person's name
        it cannot verify)."""
        state = self.state(id_)
        if state is None:
            raise PolicyRequestError(f"unknown request {id_!r}")
        if word.strip().lower() != _APPROVAL_WORD:
            raise PolicyRequestError(
                f"the approval word must be exactly {_APPROVAL_WORD!r}"
            )
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

    def refuse(self, id_: str, *, reason: str, by: str) -> None:
        """``by`` has no default either — see :meth:`approve`; the same honesty applies to a
        refusal recorded on someone's behalf."""
        if self.state(id_) is None:
            raise PolicyRequestError(f"unknown request {id_!r}")
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

    # -- the appliqueur (a tool, gated on the exact approved content) -------------------------
    def approved_items_for_apply(self, id_: str) -> tuple[PolicyItem, ...]:
        """The items to hand to :func:`~mnemosyne.production.policy_writer.apply_to_file` — the
        ONLY exit from this ledger that releases items for a real write. Fail-closed: a request
        that is unknown, refused, not yet approved, already applied, or whose content has moved
        on since the approval (a later examination narrowed it further) all raise rather than
        return anything — "pending" is never treated as "go ahead"."""
        state = self.state(id_)
        if state is None:
            raise PolicyRequestError(f"unknown request {id_!r}")
        if state.applied:
            raise PolicyRequestError(f"request {id_!r} was already applied at {state.applied_at}")
        if state.refused:
            raise PolicyRequestError(f"request {id_!r} was refused: {state.refused_reason}")
        if not state.approved:
            raise PolicyRequestError(
                f"request {id_!r} is not approved — pending is a refusal (fail-closed)"
            )
        if state.approved_content_hash != state.content_hash():
            raise PolicyRequestError(
                f"request {id_!r} changed since it was approved — re-approve the current content"
            )
        return state.items

    def record_application(self, id_: str, *, diff: dict[str, object]) -> None:
        self._append(
            {"v": _FORMAT, "kind": "applied", "id": id_, "at": _utcnow_iso(), "diff": diff}
        )

    # -- reads ---------------------------------------------------------------------------------
    def state(self, id_: str) -> RequestState | None:
        return self._replay().get(id_)

    def all_states(self) -> tuple[RequestState, ...]:
        return tuple(sorted(self._replay().values(), key=lambda s: s.filed_at))

    def _replay(self) -> dict[str, RequestState]:
        """Fold the event log into current state per id. Fail-closed on a malformed INTERNAL
        line (never silently skip a governance gesture); tolerates a truncated FINAL line (a
        crash mid-append is a gesture RAM never saw either — write-ahead recovery, D82)."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        lines = raw.splitlines()
        last_nonempty = max((i for i, ln in enumerate(lines) if ln.strip()), default=-1)
        states: dict[str, RequestState] = {}
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                if idx == last_nonempty:
                    break  # truncated final line — a never-committed gesture, correct to drop
                raise
            kind = event["kind"]
            id_ = event["id"]
            if kind == "filed":
                if id_ in states:
                    # D159, post-audit fix: a SECOND "filed" event for an id already in progress
                    # must never silently reset it back to "depose" — `file()` already guards the
                    # happy path (same content ⇒ same id ⇒ no re-append), but replay is the
                    # AUTHORITY and must hold even if a stray duplicate line ever reaches the
                    # ledger some other way. First filing wins; later ones are ignored.
                    continue
                states[id_] = RequestState(
                    id=id_,
                    title=event["title"],
                    items=tuple(_decode_item(i) for i in event["items"]),
                    justification=event["justification"],
                    requested_by=event["requested_by"],
                    filed_at=event["at"],
                )
                continue
            prior = states.get(id_)
            if prior is None:
                raise PolicyRequestError(f"{kind} event for a request never filed: {id_!r}")
            if kind == "examined":
                new_items = prior.items
                if event.get("verdict") == "narrow" and event.get("narrowed_items") is not None:
                    new_items = tuple(_decode_item(i) for i in event["narrowed_items"])
                    if not _is_item_subset(new_items, prior.items):
                        # D159, 2nd D75 audit: `record_examination` already refuses this at the
                        # API boundary, but REPLAY is the authority — a hand-edited or corrupted
                        # ledger line must not bypass the same guarantee just because it skipped
                        # the method. Fail-closed: the whole ledger refuses to load rather than
                        # silently accept a widened "narrow".
                        raise PolicyRequestError(
                            f"ledger corruption: a 'narrow' event for {id_!r} widens the request "
                            "— refusing to replay (D159)"
                        )
                states[id_] = replace(
                    prior,
                    items=new_items,
                    examined=True,
                    examiner_verdict=str(event.get("verdict", "")),
                    examiner_notes=str(event.get("notes", "")),
                )
            elif kind == "approved":
                states[id_] = replace(
                    prior,
                    approved=True,
                    approved_at=event["at"],
                    approved_content_hash=event["content_hash"],
                    refused=False,
                    refused_reason="",
                )
            elif kind == "refused":
                states[id_] = replace(
                    prior, refused=True, refused_reason=str(event.get("reason", "")), approved=False
                )
            elif kind == "applied":
                states[id_] = replace(prior, applied=True, applied_at=event["at"])
            else:
                raise PolicyRequestError(
                    f"unknown event kind {kind!r} — refusing to skip a governance gesture (D82 spirit)"
                )
        return states
