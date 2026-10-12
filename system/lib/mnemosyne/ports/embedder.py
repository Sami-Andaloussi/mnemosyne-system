"""Embedder (D68) - multilingual dense embeddings behind a swap-able seam.

Embedding is a GENERIC brick: the text is the same for any RAG, so we adopt the
state-of-the-art consensus and freeze a sane, swap-able default - no embedding
bench (that is reserved for role LLMs, D69). The interface stays standard
(embed / dimension / max_tokens) so the model is replaceable.

Two structural points (D68):

* **Each vector is tagged** with the model + dimension + version that encoded it,
  enabling a *targeted incremental re-index* when the model changes (no full
  re-encode - D63).
* **The ``sensible`` subset is embedded 100 % LOCALLY by construction** - an
  automatic process, therefore never cloud (invariant 1 / D66); its index is
  physically isolated (see :class:`~mnemosyne.ports.vectorindex.VectorIndex`).

Tokenization and model are encapsulated TOGETHER (each model has its own
pre-processing). Default OSS brick: **bge-m3** (BAAI, MIT, multilingual FR/EN),
paired reranker bge-reranker-v2-m3 - see ``system/config/oss_registry.md`` (D68).

Decisions: D68 (strategy + frozen default)  -  D63 (incremental re-index)  -  D98
(OSS under our rules). Invariant carried: substrate of 1 (local `sensible`
embedding).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

#: A dense embedding vector.
type Vector = tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Embedding:
    """A vector tagged with the model identity that produced it (D68).

    The ``model_id`` / ``dimension`` / ``version`` triple is what lets a model
    swap trigger a *targeted* re-index rather than a full re-encode (D63).
    """

    vector: Vector
    model_id: str
    dimension: int
    version: str


def is_indexable_vector(vector: Vector) -> bool:
    """Whether ``vector`` can be stored AND cosine-matched in the dense index (D68 / invariant 14).

    Indexable iff every coordinate is FINITE and the vector has a non-zero norm. This rejects the two
    ways a real encoder degrades a single passage: a NON-FINITE vector (bge-m3's fp16 path can overflow
    a coordinate to NaN / ±inf on a pathological passage) and a ZERO vector (a chunk that tokenises to
    nothing - a figures-only page - normalises to 0/0). Cosine is undefined for both, and Qdrant REJECTS
    them ("did not match any variant of untagged enum VectorStruct"), so an unguarded upsert fails the
    WHOLE document at the (3) scale-up. The index drops such a passage instead of crashing - its raw text
    stays in the truth store (D56 / D85), still reachable through its neighbours' overlap and the lexical
    leg, so nothing is lost; only that one passage's dense vector is skipped, and the surviving passages
    keep their ordinals (D136). Deterministic and brick-free (D126)."""
    return any(x != 0.0 for x in vector) and all(math.isfinite(x) for x in vector)


@runtime_checkable
class Embedder(Protocol):
    """Encodes text into tagged dense vectors; the model stays swap-able (D68)."""

    @property
    def model_id(self) -> str:
        """Identity of the underlying model (carried onto every :class:`Embedding`)."""
        ...

    @property
    def dimension(self) -> int:
        """Output vector dimension."""
        ...

    @property
    def max_tokens(self) -> int:
        """Maximum input length the encapsulated tokenizer accepts."""
        ...

    @property
    def recall_floor(self) -> float:
        """The low-recall gate (invariant 14) for THIS model's score distribution: a dense hit
        scoring below it is admitted as "I don't know", never invented (D65 / D100). REQUIRED on
        the port so the floor travels WITH the encoder (a swap swaps the floor) and a new adapter
        can never silently inherit a wrong one: the stub hashing encoder -> 0.3, bge-m3 -> 0.53
        (earned at (3)-2b from a corpus golden). This is the CONFORMANT DEFAULT every domain falls
        back to; :class:`~mnemosyne.stores.retrieval.Retriever` resolves a domain-specific override
        from the protected policy zone per call, when one has been earned (D139 - a golden-set task
        per domain, same instrument, materialised just-in-time as the corpus diversifies)."""
        ...

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        """Encode a batch of texts. For ``sensible`` content this MUST run locally
        (invariant 1 / D68): the caller routes via the Guard, which forbids any
        automatic cloud path for non-``public`` data."""
        ...
