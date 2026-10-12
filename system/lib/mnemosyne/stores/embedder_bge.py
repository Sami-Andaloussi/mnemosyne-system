"""BgeM3Embedder (D68) — the real multilingual encoder behind the Embedder port.

Wraps **bge-m3** (BAAI, MIT), the frozen default (D68 — embedding is a generic brick,
so we adopt the state-of-the-art consensus, no bench). The heavy model is *injected*
as an ``encode`` callable, so this module imports and loads NOTHING at import time: the
adapter is built and tested against a light double WITHOUT the installed brick (D126
decoupling — the suite stays green with no weights), and the real weights are loaded
lazily by :func:`load_bge_m3` at ③ ignition. This file is the SOLE importer of the
embedding brick (D103 encapsulation).

Every vector is tagged with ``model_id`` / ``dimension`` / ``version`` (D68) so a model
swap triggers a *targeted* re-index rather than a full re-encode (D63). Code & docstrings
English (D117).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..ports import Embedding

#: bge-m3 identity (BAAI). ``_VERSION`` is bumped when the weights revision changes,
#: which is what drives the targeted re-index (D63). Frozen default, swap-able (D68).
_MODEL_ID = "bge-m3"
_DIMENSION = 1024
_MAX_TOKENS = 8192
_VERSION = "0"

#: Passages handed to the underlying model per ``encode`` call. A document chunks into as many
#: passages as its length demands (D135, no upper bound), and the transformer's attention memory
#: scales with batch size — an unbounded single call crashed the ③ scale-up on a 2.5 MB book
#: (~1600 passages): a ~19 GiB native Metal allocation that aborted the whole process (not a
#: catchable Python exception), defeating per-book error isolation. Sub-batching bounds the call
#: size independent of how large the source document is.
_ENCODE_BATCH = 32

#: Per-passage token ceiling handed to the encoder (``max_length``). bge-m3's real window is
#: :data:`_MAX_TOKENS` (8192); this operational cap sits far below it ON PURPOSE. Attention memory
#: scales with batch × sequence² — :data:`_ENCODE_BATCH` bounds the batch, this bounds the sequence;
#: the two together cap the transformer's working set. The chunker targets ~1500 CHARS (D135) =
#: ~450 tokens of prose, but 1500 chars of a dense TABLE (digits/symbols, ~one token each) can be
#: 2000–3000 tokens: at 8192 the encoder ingests them whole, exploding attention to ~17 GiB and
#: stalling the GPU — the ③ scale-up's SECOND incident, on a table-heavy 600-page book (the first
#: was the unbounded batch, see :data:`_ENCODE_BATCH`). 1024 leaves prose untouched (never
#: truncated) and clips only pathologically dense passages, with no recall impact (nobody queries a
#: table's 2500th cell). NB purely an ingest/inference guard — it does NOT change ``max_tokens``,
#: the model's advertised capacity.
_ENCODE_MAX_LENGTH = 1024

#: Recall floor for bge-m3's dense-cosine distribution (invariant 14 / D65). EARNED at ③-2b from a
#: golden set drawn from the operator's REAL corpus (12 cases / 50 pairs, EN + FR + cross-lingual; the
#: gitignored knowledge/golden): genuine answers scored 0.535–0.797 (median 0.66), near-topic
#: distractors 0.246–0.529 (median 0.38) — a clean but thin gap. The F1-maximising sweep (D69) put the
#: floor at 0.535; 0.53 is adopted (keeps every relevant, admits no distractor, with a hair of buffer).
#: This REPLACES the hand-set 0.55, which the measurement CONFIRMED over-strict (it dropped 3/14 genuine
#: answers, e.g. the cross-lingual and abstract-mechanism ones). NB a FINANCE-calibrated DEFAULT: one
#: global cosine floor does NOT generalise across domains/languages (the operator's own concern), so it stays
#: exactly that — the CONFORMANT DEFAULT every domain falls back to. D139 supersedes it per-slice: the
#: per-domain table lives in the protected policy zone (:attr:`~mnemosyne.config.Policy.
#: recall_floor_by_domain`, resolved by :class:`~mnemosyne.stores.retrieval.Retriever` PER CALL, never
#: hard-coded here — this constant stays the ONE default, calibrated by this same golden instrument once
#: a domain has enough corpus to draw its own golden from). A conformal guarantee + an LLM sufficiency
#: backstop below the per-domain floor are noted seams, materialised just-in-time as the corpus
#: diversifies (D126) — not built until a calibrated domain makes them reachable. The hybrid RRF leg
#: still revisits the gate for fused (non-cosine) scores.
_RECALL_FLOOR = 0.53

#: An encoder turns a batch of texts into one dense vector each (bge-m3's ``.encode``).
type Encoder = Callable[[Sequence[str]], Sequence[Sequence[float]]]


class BgeM3Embedder:
    """Real bge-m3 encoder behind :class:`~mnemosyne.ports.embedder.Embedder` (D68).

    The model is injected (``encode``), never imported here, so the adapter is testable
    against a double without the brick (D126). Satisfies the Embedder port surface:
    ``model_id`` / ``dimension`` / ``max_tokens`` / ``embed``.
    """

    __slots__ = ("_encode", "_model_id", "_dimension", "_version")

    def __init__(
        self,
        encode: Encoder,
        *,
        model_id: str = _MODEL_ID,
        dimension: int = _DIMENSION,
        version: str = _VERSION,
    ) -> None:
        self._encode = encode
        self._model_id = model_id
        self._dimension = dimension
        self._version = version

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def max_tokens(self) -> int:
        return _MAX_TOKENS

    @property
    def recall_floor(self) -> float:
        """bge-m3's low-recall gate (invariant 14): a hit below this cosine is treated as no
        confident memory rather than invented (D100). The floor travels with the embedder
        because it is a property of its score distribution. See :data:`_RECALL_FLOOR`."""
        return _RECALL_FLOOR

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        """Encode ``texts`` into tagged dense vectors — one :class:`Embedding` per input.

        The injected encoder does the model work; this method only tags and validates the
        shape, in sub-batches of at most :data:`_ENCODE_BATCH` (see its docstring). A wrong
        vector count or dimension is raised as a structural error rather than silently
        indexing a malformed vector (a mismatch means the wrong brick)."""
        batch = list(texts)
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(batch), _ENCODE_BATCH):
            piece = batch[start : start + _ENCODE_BATCH]
            raw = self._encode(piece)
            piece_vectors = [tuple(float(x) for x in vec) for vec in raw]
            if len(piece_vectors) != len(piece):
                raise ValueError(
                    f"bge-m3 returned {len(piece_vectors)} vectors for {len(piece)} texts"
                )
            vectors.extend(piece_vectors)
        for vec in vectors:
            if len(vec) != self._dimension:
                raise ValueError(
                    f"bge-m3 returned dimension {len(vec)} != expected {self._dimension}"
                )
        return [
            Embedding(
                vector=vec,
                model_id=self._model_id,
                dimension=self._dimension,
                version=self._version,
            )
            for vec in vectors
        ]


def load_bge_m3(*, device: str = "cpu") -> BgeM3Embedder:  # pragma: no cover - needs the brick
    """Load the real bge-m3 weights and return a wired :class:`BgeM3Embedder` (③ ignition).

    Lazy import: the brick (``FlagEmbedding``) and the weights are absent in CI and present
    only once installed on the machine (D126 ``[OPERATOR]`` ignition). Kept off the covered path
    — its integration is validated by the real 1-click smoke, not the unit suite. The exact
    library (FlagEmbedding vs sentence-transformers) is confirmed at install; the identity is
    frozen (registry: bge-m3, BAAI/MIT). This is the SOLE importer of the brick (D103).

    ``device`` defaults to ``"cpu"``: bge-m3's attention DEADLOCKS the whole process on the MPS
    (Apple-Metal GPU) backend — torch's ``scaled_dot_product_attention`` hangs forever inside
    ``executeMPSGraph`` on some dense / table-heavy books (a known PyTorch-on-Mac bug, NOT a memory
    issue; it froze the ③ scale-up on book 38 and re-froze on every retry). CPU is slower but
    immune. Pass ``device="mps"`` to try the GPU again once the upstream bug is fixed."""
    from FlagEmbedding import BGEM3FlagModel  # lazy, machine-only (D103 sole importer)

    # fp16 is a GPU optimisation; on CPU it is slower / unsupported, so enable it for the GPU only.
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=(device != "cpu"), devices=device)

    def encode(texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return model.encode(list(texts), max_length=_ENCODE_MAX_LENGTH)["dense_vecs"]

    return BgeM3Embedder(encode)
