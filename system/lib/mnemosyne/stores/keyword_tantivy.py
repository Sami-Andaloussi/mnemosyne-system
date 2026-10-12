"""TantivyKeywordIndex (D68) — the real lexical index behind the KeywordIndex port,
PARTITIONED BY SENSITIVITY (invariant 1).

Wraps **tantivy** (``tantivy-py``, MIT), the default BM25 leg of hybrid retrieval (D68).
Mirrors :mod:`.vector_qdrant`: each sensitivity owns its OWN tantivy index, so a
``sensible`` document lives in a physically separate index and a search is scoped to ONE
index — partitions are never crossed implicitly (invariant 1 / D54).

**Decoupling (D126).** The adapter talks to a small injected ``backend`` in PRIMITIVES
(index name, id, text, payload dict), never to tantivy types — so the partition ROUTING
(the security surface) is unit-tested against a light double WITHOUT tantivy installed. The
real engine is wrapped by :func:`connect_tantivy` at ③ ignition; that thin translation
layer (:class:`_TantivyBackend`, the SOLE importer of the brick, D103) is exercised by the
1-click smoke, not the unit suite. Code & docstrings English (D117); sensitivity tokens stay
French (D33 / D66).
"""

from __future__ import annotations

from typing import Protocol

from ..ports import (
    Bubble,
    DocId,
    Domain,
    GovernanceLabel,
    SearchHit,
    Sensitivity,
)

_INDEX_PREFIX = "mnemosyne"
#: Reverse of :attr:`Sensitivity.token`, to rebuild the enum from a stored payload.
_SENSITIVITY_BY_TOKEN = {s.token: s for s in Sensitivity}


def _sanitize_query(query: str) -> str:
    """Reduce a natural-language query to plain terms tantivy's parser won't read as syntax (③-5b live).

    ``parse_query`` treats ``+ - : ( ) [ ] { } ^ " ~ * ? \\ /`` and ``AND/OR/NOT/IN`` as operators, so a
    real question (« … ML / retrieval, seuils … ») raised a ``Syntax Error``. Replace every
    non-alphanumeric, non-space character with a space (Unicode letters incl. accents are kept), collapse
    whitespace and lowercase — the parser then reads a bag of words (BM25 over terms); the dense leg
    carries the semantics. An empty result (a query of only punctuation) means: no lexical leg this call."""
    cleaned = "".join(c if (c.isalnum() or c.isspace()) else " " for c in query)
    return " ".join(cleaned.split()).lower()


class KeywordBackend(Protocol):
    """The primitive surface :class:`TantivyKeywordIndex` needs from a lexical store.

    Expressed in primitives (no tantivy types) so a light double can stand in for the brick
    in tests (D126). :func:`connect_tantivy` supplies the real one. ``search`` returns
    ``(score, payload)`` rows — the doc id travels inside the payload."""

    def ensure_index(self, index: str) -> None: ...
    def index_doc(self, index: str, doc_id: str, text: str, payload: dict) -> None: ...
    def search(
        self, index: str, query: str, domains: tuple[str, ...], top_k: int
    ) -> list[tuple[float, dict]]: ...
    def delete(self, index: str, doc_id: str) -> None: ...
    def exists(self, index: str, doc_id: str) -> bool: ...


class TantivyKeywordIndex:
    """Real tantivy index behind :class:`~mnemosyne.ports.keywordindex.KeywordIndex` (D68).

    Partition = one index per sensitivity (``mnemosyne_public`` / ``_perso`` / ``_sensible``);
    the index is derived ONLY from the datum's sensitivity, so ``sensible`` is physically
    isolated (invariant 1). The backend is injected (D126)."""

    __slots__ = ("_backend", "_prefix")

    def __init__(self, backend: KeywordBackend, *, prefix: str = _INDEX_PREFIX) -> None:
        self._backend = backend
        self._prefix = prefix

    def _index(self, sensitivity: Sensitivity) -> str:
        """The index for a sensitivity — the partition boundary (invariant 1)."""
        return f"{self._prefix}_{sensitivity.token}"

    def index(self, doc: DocId, text: str, label: GovernanceLabel) -> None:
        """Index ``doc``'s text into the partition of ``label.sensitivity`` — and ONLY there.

        The index is a pure function of ``label.sensitivity``: a ``sensible`` datum can only
        land in the isolated ``sensible`` index (invariant 1). Keyed by ``doc`` ⇒ a re-index
        is idempotent (the journal's replay substrate, invariant 24)."""
        index = self._index(label.sensitivity)
        self._backend.ensure_index(index)
        payload = {
            "doc": str(doc),
            "sensitivity": label.sensitivity.token,
            "bubble": str(label.bubble),
            "domains": sorted(str(d) for d in label.domains),
        }
        self._backend.index_doc(index, str(doc), text, payload)

    def search(
        self,
        query: str,
        *,
        within: Sensitivity,
        domains: frozenset[Domain] = frozenset(),
        top_k: int = 10,
    ) -> list[SearchHit]:
        """Search the SINGLE partition ``within`` (never any other), optionally narrowed to
        ``domains`` (D72). The index queried is a pure function of ``within`` — a ``sensible``
        search stays entirely in its own index (invariant 1 / D54)."""
        index = self._index(within)
        self._backend.ensure_index(index)
        rows = self._backend.search(index, query, tuple(sorted(str(d) for d in domains)), top_k)
        return [
            SearchHit(
                doc=DocId(payload["doc"]), score=score, label=self._label_from_payload(payload)
            )
            for score, payload in rows
        ]

    def invalidate(self, doc: DocId) -> None:
        """Purge ``doc`` from EVERY partition (a derivative purge; truth untouched, D56)."""
        for sensitivity in Sensitivity:
            self._backend.delete(self._index(sensitivity), str(doc))

    def contains(self, doc: DocId) -> bool:
        """Whether ``doc`` is indexed in any partition (integration witness, invariant 24)."""
        return any(self._backend.exists(self._index(s), str(doc)) for s in Sensitivity)

    @staticmethod
    def _label_from_payload(payload: dict) -> GovernanceLabel:
        """Rebuild the governance label from the stored payload (D108-⑤).

        The keyword index is a reconstructible derivative (D56): it carries the sensitivity,
        bubble and domains the Guard reads, but NOT the full provenance chain (that lives in
        the truth store), so ``provenance`` is left ``None`` on a recalled hit."""
        return GovernanceLabel(
            sensitivity=_SENSITIVITY_BY_TOKEN[payload["sensitivity"]],
            bubble=Bubble(payload["bubble"]),
            domains=frozenset(Domain(d) for d in payload.get("domains", ())),
        )


def connect_tantivy(  # pragma: no cover - needs the brick (③ ignition)
    *,
    base_path: str | None = None,
    prefix: str = _INDEX_PREFIX,
) -> TantivyKeywordIndex:
    """Build a wired :class:`TantivyKeywordIndex` over the real tantivy engine (③ ignition).

    Lazy import: ``tantivy`` exists only on the machine at ③ ignition (D126 ``[OPERATOR]``), never
    in CI. ``base_path=None`` keeps each per-sensitivity index in RAM (rebuilt from the truth
    on cold start, D56); a path persists them under ``base_path/<index>`` (gitignored,
    ``.keywordstore/``). Validated by the real 1-click smoke, not the unit suite. This is the
    SOLE importer of the tantivy brick (D103)."""
    return TantivyKeywordIndex(_TantivyBackend(base_path), prefix=prefix)


class _TantivyBackend:  # pragma: no cover - real tantivy translation (③ ignition, smoke-tested)
    """Thin translation from the primitive :class:`KeywordBackend` surface to the real tantivy
    API (SchemaBuilder / Index / Document / Query). The SOLE place tantivy types are built
    (D103). One tantivy index per sensitivity partition; ``domains`` are filtered from the
    stored payload after the BM25 query. Never run by the unit suite."""

    def __init__(self, base_path: str | None) -> None:
        self._base_path = base_path
        self._indexes: dict[str, object] = {}

    def _schema(self):
        import tantivy

        builder = tantivy.SchemaBuilder()
        builder.add_text_field("doc_id", stored=True, tokenizer_name="raw")
        builder.add_text_field("body", stored=False)  # searchable, not returned
        builder.add_text_field("sensitivity", stored=True, tokenizer_name="raw")
        builder.add_text_field("bubble", stored=True, tokenizer_name="raw")
        builder.add_text_field("domains", stored=True, tokenizer_name="raw")
        return builder.build()

    def ensure_index(self, index: str) -> None:
        import os

        import tantivy

        if index in self._indexes:
            return
        if self._base_path is None:
            self._indexes[index] = tantivy.Index(self._schema())  # RAM
            return
        path = os.path.join(self._base_path, index)
        os.makedirs(path, exist_ok=True)
        self._indexes[index] = tantivy.Index(self._schema(), path=path)

    def index_doc(self, index: str, doc_id: str, text: str, payload: dict) -> None:
        import tantivy

        idx = self._indexes[index]
        writer = idx.writer()
        writer.delete_documents("doc_id", doc_id)  # keyed by doc ⇒ upsert (idempotent, inv. 24)
        writer.add_document(
            tantivy.Document(
                doc_id=doc_id,
                body=text,
                sensitivity=payload["sensitivity"],
                bubble=payload["bubble"],
                domains=list(payload.get("domains", ())),
            )
        )
        writer.commit()
        idx.reload()

    def search(
        self, index: str, query: str, domains: tuple[str, ...], top_k: int
    ) -> list[tuple[float, dict]]:
        idx = self._indexes[index]
        idx.reload()
        searcher = idx.searcher()
        terms = _sanitize_query(query)
        if not terms:
            return []  # a query of only punctuation reduces to no terms — no lexical leg (dense carries)
        parsed = idx.parse_query(terms, ["body"])
        # Over-fetch when a domain filter is active, then narrow from the stored payload.
        limit = top_k * 5 if domains else top_k
        rows: list[tuple[float, dict]] = []
        for score, address in searcher.search(parsed, limit).hits:
            doc = searcher.doc(address)
            doc_domains = tuple(doc.get_all("domains"))
            if domains and not (set(domains) & set(doc_domains)):
                continue
            payload = {
                "doc": doc["doc_id"][0],
                "sensitivity": doc["sensitivity"][0],
                "bubble": doc["bubble"][0],
                "domains": list(doc_domains),
            }
            rows.append((float(score), payload))
            if len(rows) >= top_k:
                break
        return rows

    def delete(self, index: str, doc_id: str) -> None:
        if index not in self._indexes:
            return
        idx = self._indexes[index]
        writer = idx.writer()
        writer.delete_documents("doc_id", doc_id)
        writer.commit()
        idx.reload()

    def exists(self, index: str, doc_id: str) -> bool:
        if index not in self._indexes:
            return False
        idx = self._indexes[index]
        idx.reload()
        searcher = idx.searcher()
        parsed = idx.parse_query(doc_id, ["doc_id"])
        return bool(searcher.search(parsed, 1).hits)
