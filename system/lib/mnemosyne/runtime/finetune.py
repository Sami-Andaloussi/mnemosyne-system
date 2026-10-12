"""Fine-tune manifest (D76 / D115, invariant 13) - memory lives OUTSIDE the weights.

"Nothing lives in the model" (D76): facts / preferences / history / lessons live OUTSIDE,
versioned, NEVER in the weights. Fine-tuning is allowed for CAPACITY only, and only as a
DERIVED, VERSIONED artifact - reconstructible from an EXTERNAL dataset + training recipe
(D76 / D115). The RECIPE is the truth; the weights are a rebuildable projection.

This module makes that structural: a :class:`FineTuneManifest` cannot be constructed without
a base model and a VERSIONED dataset + recipe reference. So a fine-tuned model is defined
solely by external, versioned memory - wipe the weights, rebuild from the manifest, same
capability - and no fact can hide in the weights (invariant 13). A model with no such
manifest is simply not registrable (the seam that enforces "no memory in weights").

The manifest is a value type; producing the fine-tune itself is a background pass gated by a
golden set + producer != verifier via the Guard (D95 / D75 / D89), and ZERO fine-tunes are
produced in Phase 1 (contenant, not contenu - D98 / D115). Code & docstrings English (D117).

Decisions: D76 (memory outside weights, fine-tuning = reconstructible derivative)  -  D115
(the recipe is the truth)  -  D75 (promotion gated)  -  D100 (no auto-promotion). Invariant
carried: 13.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ports import ErrorCode, MnemosyneError

#: Separator marking a reference as VERSIONED (``name@version`` - a dataset / recipe pin).
_VERSION_SEP = "@"


class ManifestError(MnemosyneError):
    """A fine-tune manifest is incomplete or its refs are unversioned (invariant 13).

    Malformed in the D108-(1) sense: a model whose dataset / recipe is missing or unpinned is
    not reconstructible, so it could hide memory in the weights - refused at construction."""

    code = ErrorCode.MALFORMED


def _is_versioned(ref: str) -> bool:
    """A ref is versioned iff it pins a version (``name@version``) with both parts non-empty."""
    name, sep, version = ref.partition(_VERSION_SEP)
    return bool(name) and bool(sep) and bool(version)


@dataclass(frozen=True, slots=True)
class FineTuneManifest:
    """The reconstructible recipe of a fine-tuned model (D76 / D115, invariant 13).

    A fine-tuned model IS this manifest: a base model plus a VERSIONED dataset and recipe.
    Construction refuses anything unreconstructible (empty or unversioned refs), so memory
    can never live in the weights - it lives in the external, versioned inputs the manifest
    points to."""

    base_model: str
    dataset_ref: str  # versioned pointer to the external training data (name@version)
    recipe_ref: str  # versioned pointer to the training recipe (name@version)
    produced_model_id: str

    def __post_init__(self) -> None:
        if not self.base_model:
            raise ManifestError("a fine-tune manifest needs a base model (D76)")
        if not self.produced_model_id:
            raise ManifestError("a fine-tune manifest needs a produced-model id (D76)")
        if not _is_versioned(self.dataset_ref):
            raise ManifestError(
                f"dataset ref {self.dataset_ref!r} must be versioned ('name@version') so the "
                "model is reconstructible - no memory in the weights (invariant 13 / D76)"
            )
        if not _is_versioned(self.recipe_ref):
            raise ManifestError(
                f"recipe ref {self.recipe_ref!r} must be versioned ('name@version') so the "
                "model is reconstructible - the recipe is the truth (invariant 13 / D115)"
            )

    def is_reconstructible(self) -> bool:
        """Whether the model rebuilds from external, versioned memory (always true if built).

        A constructed manifest is reconstructible by construction (the invariant): its
        dataset and recipe are versioned external refs, so no fact is encoded in the weights."""
        return _is_versioned(self.dataset_ref) and _is_versioned(self.recipe_ref)

    def reconstruct(self) -> tuple[str, str, str]:
        """The external inputs that rebuild the weights - ``(base, dataset, recipe)`` (D76).

        This IS the memory: the model carries none of its own; it is regenerated from these
        versioned references, which is why fine-tuning stays model-agnostic and replayable."""
        return (self.base_model, self.dataset_ref, self.recipe_ref)
