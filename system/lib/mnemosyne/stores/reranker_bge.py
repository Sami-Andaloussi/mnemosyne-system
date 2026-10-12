"""BgeReranker (D68) - the real cross-encoder behind the Reranker port.

Wraps **bge-reranker-v2-m3** (BAAI, MIT), the frozen default paired with the bge-m3 embedder
(D68 - reranking is a generic brick, so we adopt the state-of-the-art consensus, no bench). The
heavy model is *injected* as a ``score`` callable, so this module imports and loads NOTHING at
import time: the adapter is built and tested against a light double WITHOUT the installed brick
(D126 decoupling - the suite stays green with no weights), and the real weights are loaded lazily
by :func:`load_bge_reranker` at (3) ignition. This file is the SOLE importer of the reranking brick
(D103 encapsulation).

The cross-encoder reads the query and each candidate passage TOGETHER, so for ``sensible``
content it runs 100 % LOCALLY by construction (invariant 1 / D66) - exactly like the embedder.
Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

#: bge-reranker-v2-m3 identity (BAAI). Frozen default, swap-able (D68 / registry).
_MODEL_ID = "bge-reranker-v2-m3"

#: (query, passage) pairs scored per underlying ``compute_score`` call. A rerank pool is bounded
#: (:data:`~mnemosyne.stores.reranked_retriever._RERANK_POOL`), but a cross-encoder's attention memory
#: still scales with batch × sequence² - sub-batching bounds the call independent of the pool size,
#: mirroring the embedder's :data:`~mnemosyne.stores.embedder_bge._ENCODE_BATCH` guard.
_SCORE_BATCH = 16

#: A cross-encoder turns a batch of ``(query, passage)`` pairs into one relevance score each.
type CrossEncoder = Callable[[Sequence[tuple[str, str]]], Sequence[float]]


class BgeReranker:
    """Real bge-reranker-v2-m3 cross-encoder behind :class:`~mnemosyne.ports.reranker.Reranker` (D68).

    The model is injected (``score``), never imported here, so the adapter is testable against a
    double without the brick (D126). Satisfies the Reranker port surface: ``model_id`` / ``rerank``.
    """

    __slots__ = ("_score", "_model_id")

    def __init__(self, score: CrossEncoder, *, model_id: str = _MODEL_ID) -> None:
        self._score = score
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float] | None:
        """Score every ``(query, passage)`` pair - one float per passage, order preserved.

        The injected cross-encoder does the model work; this method only pairs, sub-batches (at most
        :data:`_SCORE_BATCH` per call) and validates the count. Never abstains (a real model always
        has an opinion - the ``None`` abstention is :class:`~mnemosyne.ports.reranker.NullReranker`'s);
        an empty shortlist scores empty. A wrong score count is raised as a structural error rather
        than silently mis-ordering the shortlist (a mismatch means the wrong brick)."""
        pairs = [(query, p) for p in passages]
        if not pairs:
            return ()
        scores: list[float] = []
        for start in range(0, len(pairs), _SCORE_BATCH):
            piece = pairs[start : start + _SCORE_BATCH]
            raw = self._score(piece)
            piece_scores = [float(x) for x in raw]
            if len(piece_scores) != len(piece):
                raise ValueError(
                    f"bge-reranker returned {len(piece_scores)} scores for {len(piece)} pairs"
                )
            scores.extend(piece_scores)
        return scores


def load_bge_reranker(*, device: str = "cpu") -> BgeReranker:  # pragma: no cover - needs the brick
    """Load the real bge-reranker-v2-m3 weights and return a wired :class:`BgeReranker` ((3) ignition).

    Lazy import: the brick (``FlagEmbedding``) and the weights are absent in CI and present only once
    installed on the machine (D126 ``[OPERATOR]`` ignition). Kept off the covered path - its integration
    is validated by the real 1-click smoke, not the unit suite. The identity is frozen (registry:
    bge-reranker-v2-m3, BAAI/MIT). This is the SOLE importer of the brick (D103).

    ``device`` defaults to ``"cpu"`` for the same reason as the embedder (:func:`~mnemosyne.stores.
    embedder_bge.load_bge_m3`): the Apple-Metal (MPS) attention path can deadlock on dense passages;
    CPU is slower but immune. Pass ``device="mps"`` once the upstream PyTorch-on-Mac bug is fixed."""
    from FlagEmbedding import FlagReranker  # lazy, machine-only (D103 sole importer)

    # normalize=True squashes the raw logit to [0, 1] - a stable, model-agnostic relevance scale
    # (the ordering is identical either way; normalization only helps a future absolute-threshold seam).
    model = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=(device != "cpu"), devices=device)

    def score(pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        computed = model.compute_score([[q, p] for q, p in pairs], normalize=True)
        # compute_score returns a bare float for a single pair, and a list OR a numpy ndarray for many
        # (version-dependent) - normalize to a plain list of floats so BgeReranker.rerank's float() never
        # chokes on an ndarray (a numpy array is not a list, so an isinstance(list) test alone would
        # wrongly wrap the whole array as a single [ndarray] element).
        if isinstance(computed, (int, float)):
            return [float(computed)]
        return [float(x) for x in computed]

    return BgeReranker(score)
