"""A4  -  the LOCAL runner's OUTPUT ceiling, and it is INFERRED instead of read.

THE LESSON WAS ENGRAVED, NO BARRIER HELD IT. The repo's memory has said for weeks
that `_DEFAULT_MAX_TOKENS=512` *"cuts EVERY local generation off mid-word, with no refusal state -
unlike the INPUT ceiling (D136), which refuses instead of cutting"*, and that this explained
several symptoms that were being mistaken for model defects. A lesson without a barrier is a wish
(rule A2): these witnesses are the barrier.

WARNING: HERE THERE IS NO `stop_reason` AT ALL TO READ - `mlx_lm.generate` returns a bare string. The
truncation is INFERRED by re-encoding the output. The witnesses therefore also cover what the
inference must refuse to do: inventing a truncation when the tokenizer does not respond.
"""

from __future__ import annotations

import pytest

from mnemosyne.ports.core import ResourceBoundError
from mnemosyne.runtime.runner_mlx import refuser_si_tronque


class _Tok:
    """A minimal tokenizer: one token per character, which keeps the count readable at a glance."""

    def encode(self, texte: str) -> list[int]:
        return [ord(c) for c in texte]


class _TokMuet:
    def encode(self, texte: str) -> list[int]:
        raise RuntimeError("this tokenizer cannot encode")


def test_une_generation_COLLEE_au_plafond_REFUSE() -> None:
    with pytest.raises(ResourceBoundError) as capture:
        refuser_si_tronque("x" * 512, _Tok(), 512)
    dit = str(capture.value)
    assert "512" in dit and "INCOMPLETE" in dit, dit


def test_l_INNOCENT_une_generation_SOUS_le_plafond_passe() -> None:
    """Without it, a refusal that always raised would also pass the witness above."""
    refuser_si_tronque("x" * 511, _Tok(), 512)


def test_un_tokenizer_MUET_n_invente_JAMAIS_une_troncature() -> None:
    """*The default branch is where silence hides* - but here silence is the RIGHT choice:
    accusing a truncation that was not measured would fail whole generations."""
    refuser_si_tronque("x" * 9999, _TokMuet(), 512)
    refuser_si_tronque("x" * 9999, object(), 512)  # no `encode` at all


def test_un_plafond_NUL_ou_NEGATIF_ne_declenche_rien() -> None:
    """A ceiling of zero would make EVERY output "truncated" - a wall, not a door."""
    refuser_si_tronque("x", _Tok(), 0)
    refuser_si_tronque("x", _Tok(), -1)


def test_le_defaut_du_runner_local_est_bien_celui_que_la_lecon_NOMME() -> None:
    """The lesson's own figure (512) must be the code's: *a count without its command is a
    memory*, and a lesson that cites a stale figure stops being enforceable."""
    from mnemosyne.runtime import runner_mlx

    assert runner_mlx._DEFAULT_MAX_TOKENS == 512
