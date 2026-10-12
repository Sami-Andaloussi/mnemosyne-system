"""EndorsementLedger (D156 / D137) — the durable net under the "citable source" gesture.

D137 makes the whole citability of the corpus rest on one human gesture: a document is
``matière-de-travail`` until the operator endorses it as ``base-de-connaissances``. The gate was built
(:meth:`~mnemosyne.api.core_api.CoreApi.endorse_document`) — and it could not work, for a reason
no one had measured until a project session hit it:

* the truth store is an **in-memory stand-in** (:class:`~mnemosyne.stores.truth.MarkdownTruthStore`),
  so ``set_role`` writes to RAM that dies with the process;
* worse, a library book is not even IN that RAM: :class:`~mnemosyne.ingest.library_truth.
  LibraryTruthStore` serves it from its ``.md`` mirror and returns a HARD-CODED default role. So
  ``endorse_document`` raised ``KeyError`` on every one of the 314 books, and a success would have
  evaporated at process exit anyway.

Endorsement is exactly the case D82 already identified for Moteur A's human layer: **a gesture, not
a derivation.** Nothing reconstructs it from a source — rebuild every index from ``raw/`` and the
endorsements are still gone. So it gets the same treatment as :mod:`.human_journal`: an append-only
journal on durable disk, replayed at cold start.

Three properties, structural rather than optional:

* **Write-ahead, fail-CLOSED.** :meth:`record` appends to disk BEFORE any caller mutates state, and
  an I/O error PROPAGATES — a gesture that could not be journaled must not appear to have been made.
  (The deliberate opposite of the trace sink, where a lost line is tolerable.)
* **Append-only, non-destructive (invariant 2).** Retracting writes a NEW line; nothing is ever
  rewritten or deleted, so the history of what the operator trusted and when stays readable.
* **Last write wins at replay**, and an unreadable line is SKIPPED rather than fatal (fail-open on
  the read side): a corrupt journal degrades to "less endorsed", never to a crashed recall — and
  "less endorsed" is the fail-closed direction, since ``matière-de-travail`` is the safe default.

Lives under ``system/state/`` like its sibling, so it is gitignored by the D82 barrier: which books
the operator trusts is personal matter, exactly like ``library_manifest.json`` that names them.

Decisions: D137 (the endorsement gate) · D82 (a human gesture gets its own durable journal) · D56 /
D44 (derivatives rebuild; gestures do not) · invariant 2 (append-only). Code English (D117).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from ..ports import DocId, DocRole

#: Repo root from here (``system/lib/mnemosyne/production/endorsements.py`` → parents[4]).
_REPO_ROOT: Final = Path(__file__).resolve().parents[4]

#: The append-only endorsement journal. Under ``system/state`` ⇒ gitignored (D82), per-machine.
DEFAULT_ENDORSEMENTS_PATH: Final = _REPO_ROOT / "system" / "state" / "endorsements.jsonl"


def observed_actor() -> str:
    """Who made the gesture — **what the machine OBSERVES**, never a presumed identity.

    Returns ``"<system user>@tty"`` or ``"<system user>@non-tty"``. Both pieces are verifiable
    facts: the OS account running the process, and whether a real terminal exists on standard
    input. Neither one PROVES the operator typed it — an agent runs under their account — but
    neither one CLAIMS it either, and that is the whole difference from the default ``"operator"``
    that used to sign 314 lines with their name (arc F1).

    **What this field CANNOT do, stated here so no one relies on it**: it does not distinguish
    the operator from an agent launched from their terminal. The only thing in the repo that does
    distinguish them is ``read_live_confirmation`` (:mod:`~mnemosyne.runtime.human_gate`, a raw
    read of ``/dev/tty``, fail-closed for a pipe). It is NOT called here, deliberately: endorsing
    is reversible, and a door slower than the wall is never taken. A gesture that, unlike this
    one, commits something (payment, message, publication, deletion) must go through it — not
    through this field.
    """
    import getpass
    import sys

    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001 - no readable account: say so, never invent a name
        user = "unknown-user"
    try:
        canal = "tty" if sys.stdin.isatty() else "non-tty"
    except Exception:  # noqa: BLE001 - detached stdin (daemon, hook): that is a non-tty, and we say so
        canal = "non-tty"
    return f"{user}@{canal}"


#: Wire format for the two roles. Stored as the French governance token (D33), like everywhere else.
_ROLE_TO_WIRE: Final = {
    DocRole.BASE_DE_CONNAISSANCES: "base-de-connaissances",
    DocRole.MATIERE_DE_TRAVAIL: "matiere-de-travail",
}
_WIRE_TO_ROLE: Final = {wire: role for role, wire in _ROLE_TO_WIRE.items()}


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class EndorsementLedger:
    """Durable, append-only record of every endorsement / retraction gesture.

    Pure I/O over one JSONL file — no brick, no model (D126). Constructed with an explicit path so
    the suite drives it against a temp tree instead of the real journal.
    """

    __slots__ = ("_path",)

    def __init__(self, path: Path | str = DEFAULT_ENDORSEMENTS_PATH) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, doc: DocId, role: DocRole, *, by: str) -> None:
        """Append one gesture. Fail-CLOSED: an I/O error propagates, it is never swallowed.

        The caller must journal BEFORE it mutates anything, so a gesture that could not be written
        never takes effect in RAM either — no silent divergence between disk and memory.

        **``by`` NO LONGER HAS A DEFAULT, and that is the fix (arc F1, 2026-07-28).** It used to
        be ``"operator"``. No caller passed it — neither ``endorse_run`` nor ``core_api`` — and
        ``make endorse CONFIRM=1`` has **no human gate at all** (deliberately: endorsing is
        reversible, and a door slower than the wall is never taken). Measured result:
        **314 journal lines claim the operator signed**, all on 2026-07-25, all written by an
        agent. One default was enough to engrave a false attribution into an append-only journal.

        The fix is not to set a "better" default: **the code cannot know who is typing, so it
        must not claim to.** Only what is OBSERVABLE passes through here (the system user,
        whether a real terminal is present) — never a presumed identity.
        A corollary already met elsewhere: a value that names a CHANNEL (``cli``, ``frontier``)
        does not name a producer. It is the same debt as ``distilled_by: (frontier)``.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {"doc": str(doc), "role": _ROLE_TO_WIRE[role], "at": _utcnow_iso(), "by": by},
            ensure_ascii=False,
        )
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def replay(self) -> dict[str, DocRole]:
        """Rebuild ``doc id → role`` from the journal; last gesture per document wins.

        Fail-OPEN on read: a missing file yields ``{}``, and a blank / malformed / unknown-role line
        is SKIPPED. The worst a corrupt journal can do is under-report endorsements, which lands on
        the fail-closed side (a document falls back to ``matière-de-travail``, never the reverse).
        """
        if not self._path.is_file():
            return {}
        roles: dict[str, DocRole] = {}
        with self._path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    event = json.loads(stripped)
                    doc, wire = str(event["doc"]), str(event["role"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue  # a garbled line is skipped, never fatal
                role = _WIRE_TO_ROLE.get(wire)
                if role is not None:
                    roles[doc] = role
        return roles

    def endorsed(self) -> frozenset[str]:
        """The doc ids currently endorsed as citable sources — the read a queue view needs."""
        return frozenset(
            doc for doc, role in self.replay().items() if role is DocRole.BASE_DE_CONNAISSANCES
        )
