# SPDX-License-Identifier: MIT
"""`C1` — the single home of "what is a command," replayed against its ORIGINAL at External Research.

 This file exists to prove that the PORT (`plan_condition.py`) stays faithful to the source
(`condition_commande.py` at External Research), not to rediscover the definition. The reference must never
drift from what it verifies: the ORIGINAL source is imported, never a copy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from mnemosyne.production.plan_condition import (
    EXECUTABLES,
    TEMOINS_NON,
    TEMOINS_OUI,
    est_une_commande,
)

EXTERNE = Path(__file__).resolve().parents[2] / "projects" / "saas" / "External Research"
_EXTERNE_PLAN = EXTERNE / "validation" / "plan"


def _externe_disponible() -> bool:
    return (EXTERNE / ".git" / "HEAD").exists() or (_EXTERNE_PLAN / "condition_commande.py").exists()


needs_externe = pytest.mark.skipif(
    not _externe_disponible(), reason="External Research's real population is not present on this host"
)


@pytest.mark.parametrize("temoin", TEMOINS_OUI)
def test_les_temoins_OUI_du_port_sont_des_commandes(temoin):
    assert est_une_commande(temoin), f"should pass: {temoin!r}"


@pytest.mark.parametrize("temoin", TEMOINS_NON)
def test_les_temoins_NON_du_port_sont_refuses(temoin):
    assert not est_une_commande(temoin), f"should be refused: {temoin!r}"


def test_un_executable_SEUL_sans_argument_ne_tranche_rien():
    """ The missing half of any predicate: a bare executable passes the ENUMERATED list but
 carries no concrete argument. `est_une_commande` must require BOTH."""
    for executable in EXECUTABLES:
        assert not est_une_commande(f"`{executable}`"), f"{executable} alone settles nothing"


@needs_externe
class TestRejeuContreExterne:
    """The ORIGINAL module at External Research is imported once for the whole class — never copied, never
    reimplemented: it is the reference, and a reference that drifts from what it verifies is no
    longer one."""

    @classmethod
    def setup_class(cls):
        sys.path.insert(0, str(_EXTERNE_PLAN))
        import condition_commande as cc
        import feuilles_executables as fe

        cls.cc = cc
        cls.fe = fe

    @classmethod
    def teardown_class(cls):
        for mod in ("condition_commande", "feuilles_executables", "feuilles_motifs",
                    "ancrage_commandes", "ancrage_commandes_mutations"):
            sys.modules.pop(mod, None)
        if str(_EXTERNE_PLAN) in sys.path:
            sys.path.remove(str(_EXTERNE_PLAN))

    def _tranches_reelles(self) -> dict[str, str]:
        """ **D1, isolated audit: THE `A_JUGER` FILTER NARROWS 168 TO 150, AND THIS NARROWING IS
 WHAT MANUFACTURES THE EMPTY SET.** `C1`'s clause states, verbatim, *"replay on the 168
 items."* On the LITERAL population (unfiltered), the refusal set is NOT empty:
 `{F1, F5, F6, P1, P3}`, identical on both sides — measured, not assumed. *A rate measured
 on the wrong population kills a good design*: my `A_JUGER` filter had excluded precisely
 the 5 items that made the measurement non-vacuous, and a `FAUX_REFUS` can only exist among
 REFUSALS."""
        return {ident: self.fe.tranche(bloc, "condition") for _f, ident, _g, bloc in self.fe.items_du_depot()}

    def test_CROISE_mes_temoins_sont_juges_IDENTIQUEMENT_par_EXTERNE(self):
        """ The strongest proof of fidelity: External Research's 23 adversarial witnesses AND the port's 23,
 each judged by BOTH functions. Zero disagreement in EITHER direction."""
        divergences = []
        for t in TEMOINS_OUI:
            if not self.cc.est_une_commande(t):
                divergences.append(f"my YES refused by External Research: {t!r}")
        for t in TEMOINS_NON:
            if self.cc.est_une_commande(t):
                divergences.append(f"my NO accepted by External Research: {t!r}")
        for t in self.cc.TEMOINS_OUI:
            if not est_une_commande(t):
                divergences.append(f"External Research's YES refused by me: {t!r}")
        for t in self.cc.TEMOINS_NON:
            if est_une_commande(t):
                divergences.append(f"External Research's NO accepted by me: {t!r}")
        assert not divergences, "\n".join(divergences)

    def test_REJEU_sur_la_population_LITTERALE_168_rend_le_MEME_ensemble_de_refus(self):
        """`C1`'s *Done when* clause, to the letter: replay on External Research's **168** items — never a
 filtered subset — same refusal set as the original.

 **Non-vacuous by construction**: `{F1, F5, F6, P1, P3}`, measured and published, not an
 empty set that would coincide without proving anything. This is the strongest property
 this replay can carry: it bites on today's REAL population, with no need for fault
 injection to demonstrate it."""
        tranches = self._tranches_reelles()
        assert len(tranches) == 168, f"the clause names 168 items, population read: {len(tranches)}"
        refus_externe = {i for i, t in tranches.items() if not self.cc.est_une_commande(t)}
        refus_moi = {i for i, t in tranches.items() if not est_une_commande(t)}
        assert refus_externe == refus_moi == {"F1", "F5", "F6", "P1", "P3"}, (
            f"expected {{'F1','F5','F6','P1','P3'}} on both sides — "
            f"External Research only: {refus_externe - refus_moi} · mine only: {refus_moi - refus_externe}"
        )

    def test_le_REJEU_MORD_quand_EXECUTABLES_est_AMPUTE(self):
        """ **D2, isolated audit: my two injection witnesses never tested the population at
 all — they tested an ISOLATED string, identical to an existing `TEMOINS_NON` entry.**
 `injectee = dict(tranches)` was built and then NEVER iterated over: only `injectee[cible]`
 was evaluated, which just re-tests `TEMOINS_NON[0]`/`[10]` with none of the claimed
 context. Proof: sabotaging `_tranches_reelles` into a clone returning a fictional
 single-item population still left **both witnesses green**, proving they depended on NO
 population at all.

 **The fix, proposed and measured by the auditor**: amputating `EXECUTABLES` of
 `grep`/`rg` genuinely changes the replay on the LITERAL population — `5 -> 15` refusals.
 That is the divergence the comparison mechanism must produce to prove it actually bites."""
        import mnemosyne.production.plan_condition as mien

        tranches = self._tranches_reelles()
        refus_normal = {i for i, t in tranches.items() if not est_une_commande(t)}
        assert refus_normal == {"F1", "F5", "F6", "P1", "P3"}

        orig_exec, orig_cmd, orig_bloc = mien.EXECUTABLES, mien.COMMANDE, mien.BLOC
        amputes = tuple(e for e in mien.EXECUTABLES if e not in ("grep", "rg"))
        mien.EXECUTABLES = amputes
        mien.COMMANDE = re.compile(
            rf"^\s*{mien._PREFIXE}(?:{'|'.join(amputes)}){mien._VERSION}\b{mien._ARGUMENT}"
        )
        mien.BLOC = re.compile(
            rf"```(?:bash|sh)?\s*\n[^`]*?^\s*{mien._PREFIXE}(?:{'|'.join(amputes)})"
            rf"{mien._VERSION}\b{mien._ARGUMENT}",
            re.M | re.S,
        )
        try:
            refus_sabote = {i for i, t in tranches.items() if not est_une_commande(t)}
        finally:
            mien.EXECUTABLES, mien.COMMANDE, mien.BLOC = orig_exec, orig_cmd, orig_bloc

        assert refus_sabote != refus_normal, (
            "amputating grep/rg from EXECUTABLES must make the replay DIVERGE — otherwise this "
            "sabotage does not bite"
        )
        assert len(refus_sabote) > len(refus_normal), f"expected more refusals, found {len(refus_sabote)}"


@needs_externe
def test_le_TIRAGE_stratifie_est_DETERMINISTE_et_REJOUABLE():
    """External Research's sampling rule (7 shortest, 6 from the middle, 7 longest, with no clock and no
    `random`) must return the SAME sample from one call to the next — otherwise "sample drawn"
    is a lie."""
    sys.path.insert(0, str(_EXTERNE_PLAN))
    try:
        import feuilles_executables as fe

        def tirage():
            juges = sorted(
                (len(b.split("\n")), i)
                for f, i, g, b in fe.items_du_depot()
                if g in fe.A_JUGER
            )
            return juges[:7] + juges[len(juges) // 2 - 3: len(juges) // 2 + 3] + juges[-7:]

        assert tirage() == tirage(), "the draw must be stable — no `random`, no clock"
        assert len(tirage()) == 20, f"20 items expected, {len(tirage())} drawn"
    finally:
        for mod in ("feuilles_executables", "feuilles_motifs",
                    "ancrage_commandes", "ancrage_commandes_mutations"):
            sys.modules.pop(mod, None)
        if str(_EXTERNE_PLAN) in sys.path:
            sys.path.remove(str(_EXTERNE_PLAN))
