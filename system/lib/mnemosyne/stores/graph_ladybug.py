"""LadybugGraphStore (D103 / D84) — the real bi-temporal fact graph behind the GraphStore port.

Wraps **LadybugDB** (in-process graph, MIT / arm64, the default living-memory engine — D103 /
D121-B1; successor to Kuzu), the Moteur A brick (D55). Mirrors :mod:`.vector_qdrant` and
:mod:`.keyword_tantivy`: the rest of Mnémosyne speaks ONLY to this seam (invariant 20), never to
the engine — no module imports LadybugDB outside here.

Two properties are STRUCTURAL, not caller-discipline (D100):

* **Non-destructive** (invariant 2 / D84). The primitive :class:`GraphBackend` surface exposes NO
  hard-delete: :meth:`LadybugGraphStore.invalidate` can only CLOSE a fact's valid-time
  (archival), so the engine's mass-deletes are UNREACHABLE through this seam ("invalidé ≠ effacé",
  D60-2). A past-instant query still sees an invalidated fact.
* **Enveloped entry** (invariant 20 / D89). A fact enters only inside an
  :class:`~mnemosyne.ports.core.Envelope` whose label proves its extraction passed the Guard; a
  naked fact is refused. The content-addressed id makes a re-add idempotent (invariant 24).

**Decoupling (D126).** The adapter talks to the injected ``backend`` in PRIMITIVES (strings, ISO
timestamps), never to LadybugDB types — so the non-destructive guarantee and the bi-temporal
``as_of`` semantics are unit-tested against a light double WITHOUT the engine installed. The real
engine is wrapped by :func:`connect_ladybug` at ③ ignition; that translation layer
(:class:`_LadybugBackend`, the SOLE importer of the brick, D103) is exercised by the 1-click
smoke, not the unit suite. The bi-temporal visibility rule lives in ONE place — :func:`_visible_as_of`,
shared in shape with the in-memory double (:mod:`.graph`), so a fact keeps the same semantics across
a brick swap (no double logic, D84). Code & docstrings English (D117).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Protocol

from ..ports import Envelope, Fact, FactId, NodeId

#: A primitive fact row exchanged with the backend: (subject, predicate, obj, valid_from, valid_to).
#: Every field is a string; timestamps are ISO-8601; ``valid_to`` is ``None`` while still valid.
FactRow = tuple[str, str, str, str, str | None]


def _fact_id(fact: Fact) -> FactId:
    """Content-addressed id: identical facts collapse to one (idempotent add, invariant 24).

    Same key as :mod:`.graph` (the in-memory double), so the stub and the real engine assign a
    fact the SAME id — a fact keeps its identity across a brick swap (D103). MUST stay identical
    to ``graph._fact_id`` — locked by a cross-brick identity test (test_adapters, D103)."""
    key = "\x1f".join(
        (str(fact.subject), fact.predicate, str(fact.obj), fact.valid_from.isoformat())
    )
    return FactId(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16])


def _visible_as_of(fact: Fact, as_of: datetime | None) -> bool:
    """The SINGLE bi-temporal visibility rule (D84) — one place, shared shape with the double.

    Without ``as_of`` the query is "now": a closed (invalidated) fact is archived and NOT visible.
    With ``as_of`` a fact is visible when it was valid then: ``valid_from <= as_of`` and it was not
    yet closed at that instant (``valid_to`` open or strictly after ``as_of``)."""
    if as_of is None:
        return fact.valid_to is None
    if fact.valid_from > as_of:
        return False
    return fact.valid_to is None or fact.valid_to > as_of


class GraphBackend(Protocol):
    """The primitive surface :class:`LadybugGraphStore` needs from a graph engine (D126).

    Expressed in primitives (strings, ISO timestamps) so a light double can stand in for the brick
    in tests. Crucially it exposes NO hard-delete: the ONLY mutation of an existing fact is
    :meth:`close`, which sets a valid-to — so non-destructiveness is a property of the INTERFACE,
    not of caller good behaviour (invariant 2 / D84 / D100)."""

    def upsert(self, fid: str, subject: str, predicate: str, obj: str, valid_from: str) -> None:
        """Record a fact row keyed by ``fid``; re-recording the same id is a no-op (idempotent)."""
        ...

    def close(self, fid: str, valid_to: str) -> None:
        """Set ``fid``'s valid-to (archival) — the sole mutation offered; never a delete (D84)."""
        ...

    def rows(self, subject: str | None, predicate: str | None) -> list[FactRow]:
        """Every fact row matching ``subject`` / ``predicate`` (``None`` = wildcard). The temporal
        ``as_of`` window is applied ABOVE, in the store (bi-temporal rule in one place, D84)."""
        ...


class LadybugGraphStore:
    """Real LadybugDB graph behind :class:`~mnemosyne.ports.graphstore.GraphStore` (D103 / D84).

    Non-destructive and bi-temporal: :meth:`invalidate` closes valid-time (never deletes — the
    backend has no delete verb), and :meth:`query` may travel ``as_of`` a past instant. The backend
    is injected (D126); the content-addressed id keeps an identical fact from duplicating (inv. 24)."""

    __slots__ = ("_backend",)

    def __init__(self, backend: GraphBackend) -> None:
        self._backend = backend

    def add_fact(self, fact: Envelope[Fact]) -> FactId:
        """Record a fact carried in a governance :class:`Envelope` (Guard passage — D89 / inv. 20).

        A naked :class:`Fact` (not enveloped) is refused: engine output enters the graph only
        bearing its label. Re-adding an identical fact returns its existing id (idempotent, inv.
        24). The label proves the fact's extraction passed the Guard; the graph stores its fields."""
        if not isinstance(fact, Envelope):
            raise TypeError(
                "add_fact requires an Envelope[Fact]: a fact enters the graph only carrying its "
                "governance label (Guard passage — D89 / D103 / invariant 20)"
            )
        payload = fact.payload
        fid = _fact_id(payload)
        self._backend.upsert(
            str(fid),
            str(payload.subject),
            payload.predicate,
            str(payload.obj),
            payload.valid_from.isoformat(),
        )
        return fid

    def invalidate(self, fact: FactId, *, at: datetime) -> None:
        """Close a fact's validity at ``at`` — archival, NOT a hard delete (inv. 2 / D84).

        Delegates to the backend's ``close`` (the only mutation it offers — there is no delete):
        the fact stays recorded with a closed valid-time, so a query ``as_of`` an instant before
        ``at`` still sees it (bi-temporal, non-destructive, D60-2)."""
        self._backend.close(str(fact), at.isoformat())

    def query(
        self,
        *,
        subject: NodeId | None = None,
        predicate: str | None = None,
        as_of: datetime | None = None,
    ) -> list[Fact]:
        """Query facts, optionally *as of* a past instant (bi-temporal travel, D84).

        The backend returns the rows matching ``subject`` / ``predicate``; the temporal window is
        applied HERE via :func:`_visible_as_of` (one place for the bi-temporal rule): without
        ``as_of`` an invalidated fact is archived and NOT returned; with ``as_of`` a fact is visible
        when it was valid then."""
        out: list[Fact] = []
        for subj, pred, obj, valid_from, valid_to in self._backend.rows(
            None if subject is None else str(subject),
            predicate,
        ):
            fact = Fact(
                subject=NodeId(subj),
                predicate=pred,
                obj=NodeId(obj),
                valid_from=datetime.fromisoformat(valid_from),
                valid_to=datetime.fromisoformat(valid_to) if valid_to is not None else None,
            )
            if _visible_as_of(fact, as_of):
                out.append(fact)
        return out


def connect_ladybug(  # pragma: no cover - needs the brick (③ ignition)
    *, base_path: str | None = None
) -> LadybugGraphStore:
    """Build a wired :class:`LadybugGraphStore` over the real LadybugDB engine (③ ignition).

    Lazy import: ``ladybug`` exists only on the machine at ③ ignition (D126 ``[OPERATOR]``), never
    in CI. ``base_path=None`` keeps the graph in RAM — EMPTY on a cold start (the journal replay
    rebuilds the vector / keyword indexes from the truth, but NOT the graph: re-extracting past
    truth into Moteur A is a future concern, F3); a path persists it across restarts (gitignored,
    ``.graphstore/``). Validated by the real 1-click smoke, not the unit suite. This is the SOLE
    importer of the LadybugDB brick (D103 / invariant 20)."""
    return LadybugGraphStore(_LadybugBackend(base_path))


class _LadybugBackend:  # pragma: no cover - real LadybugDB translation (③-3a ignition, smoke-tested)
    """Thin translation from the primitive :class:`GraphBackend` surface to the real LadybugDB API
    (``ladybug`` 0.18, the Kuzu-compatible fork). The SOLE place LadybugDB types are built (D103 /
    invariant 20). API confirmed at ignition: ``Database(None)`` in-process + ``Connection``, a
    DECLARED schema is mandatory (``CREATE NODE/REL TABLE``), facts are inserted in TWO steps (MERGE
    the endpoint nodes, then create the edge — no combined node+edge MERGE), and results come back
    from ``get_all()`` as positional rows. An OPEN fact carries ``valid_to = ''`` (empty), mapped
    back to ``None`` on read — no engine NULL to juggle. Never run by the unit suite (D126)."""

    _OPEN = ""  # sentinel for an open (still-valid) fact — empty string, mapped to None on read

    def __init__(self, base_path: str | None) -> None:
        self._base_path = base_path
        self._conn_obj: object | None = None  # opened lazily on first use

    def _conn(self) -> object:
        import ladybug  # the SOLE import of the brick (D103 / invariant 20)

        if self._conn_obj is None:
            db = ladybug.Database(self._base_path)  # None ⇒ in-memory (rebuilt from truth, D56)
            conn = ladybug.Connection(db)
            conn.execute("CREATE NODE TABLE IF NOT EXISTS Node(id STRING, PRIMARY KEY(id))")
            conn.execute(
                "CREATE REL TABLE IF NOT EXISTS Fact("
                "FROM Node TO Node, fid STRING, predicate STRING, valid_from STRING, valid_to STRING)"
            )
            self._conn_obj = conn
        return self._conn_obj

    def upsert(self, fid: str, subject: str, predicate: str, obj: str, valid_from: str) -> None:
        conn = self._conn()
        conn.execute("MERGE (:Node {id: $s})", {"s": subject})  # endpoints first (2-step insert)
        conn.execute("MERGE (:Node {id: $o})", {"o": obj})
        existing = conn.execute(
            "MATCH ()-[f:Fact {fid: $fid}]->() RETURN f.fid LIMIT 1", {"fid": fid}
        )
        if existing.has_next():
            return  # idempotent: this content-addressed fact is already recorded (invariant 24)
        conn.execute(
            "MATCH (s:Node {id: $s}), (o:Node {id: $o}) "
            "CREATE (s)-[:Fact {fid: $fid, predicate: $p, valid_from: $vf, valid_to: $vt}]->(o)",
            {
                "s": subject,
                "o": obj,
                "fid": fid,
                "p": predicate,
                "vf": valid_from,
                "vt": self._OPEN,
            },
        )

    def close(self, fid: str, valid_to: str) -> None:
        self._conn().execute(
            "MATCH ()-[f:Fact {fid: $fid}]->() SET f.valid_to = $vt",
            {"fid": fid, "vt": valid_to},  # archival — the edge stays, only its valid_to is set
        )

    def rows(self, subject: str | None, predicate: str | None) -> list[FactRow]:
        conn = self._conn()
        clauses: list[str] = []
        params: dict[str, str] = {}
        if subject is not None:
            clauses.append("s.id = $s")
            params["s"] = subject
        if predicate is not None:
            clauses.append("f.predicate = $p")
            params["p"] = predicate
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        query = (
            "MATCH (s:Node)-[f:Fact]->(o:Node)"
            + where
            + " RETURN s.id, f.predicate, o.id, f.valid_from, f.valid_to"
        )
        return [
            (row[0], row[1], row[2], row[3], row[4] or None)  # '' (open) ⇒ None
            for row in conn.execute(query, params).get_all()
        ]
