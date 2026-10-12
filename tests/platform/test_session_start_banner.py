"""THE MISSING WITNESS — found by an isolated audit (D75), on 2026-09-08.

`.claude/hooks/session-start.sh` is the REAL surface where everything the tick publishes reaches a
session: it is this file, and this file alone, that the user and every agent read at startup. It had
**no witness at all** (`/usr/bin/grep -rl` over `tests/` → 0).

**What that cost, measured.** The very same day, the tick was fixed to lift DEBTS (defect reports a
third party filed, not yet drained) out of the proposals block — because *a signal filed among
options IS an option*. The fix worked inside `render_proposals`… and THIS file's banner still
announced the whole block, debt included, as *"unsolicited proposals, propose-never-impose"*. ***The
defect survived one floor above its own fix, in a file the fix's author had never opened.***

**The class, and it is general: fixing a block does not fix the FRAME wrapped around it.** An
enclosing header is a claim about all of its content; once that content turns heterogeneous, the
header lies without a single thing changing inside the block itself.
"""

from __future__ import annotations

import re

from _invariants import REPO_ROOT

#: The words that make what they announce OPTIONAL. They are accurate for a proposal coming from the
#: system (D92) and false for a debt a third party has reported — so they are forbidden in a frame
#: that wraps both. The list targets the BANNER alone: inside the tick, every header qualifies its
#: own nature, and "propose, never impose" is correct there.
_MOTS_QUI_RENDENT_FACULTATIF = ("propose-jamais-impose", "propose, jamais impose", "non sollicitee")

_HOOK = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"


def _banniere_du_tick() -> str:
    """The `echo` line that OPENS the tick's block — the frame, never its content."""
    lignes = _HOOK.read_text(encoding="utf-8").splitlines()
    appel = next(i for i, l in enumerate(lignes) if "mnemosyne.runtime.tick" in l)
    # The banner is the last `echo "--- … ---"` BEFORE the call: we walk back, we never guess.
    return next(
        l for l in reversed(lignes[:appel]) if l.strip().startswith('echo "---')
    )


def test_le_hook_de_demarrage_appelle_bien_le_tick() -> None:
    """The witness below only holds if this file REALLY launches the tick — without that it
    would just be measuring a string inside a dead file."""
    assert "mnemosyne.runtime.tick" in _HOOK.read_text(encoding="utf-8")
    assert _HOOK.is_file()


def test_la_banniere_du_tick_ne_rend_pas_facultatif_ce_qu_elle_enveloppe() -> None:
    """THE CORE. The banner OPENS; it does not qualify. The tick publishes two opposite
    natures — proposals from the system AND debts reported by a third party — and a frame that
    declares "propose, never impose" makes the debt optional without touching a single line of the
    tick."""
    banniere = _banniere_du_tick().lower()
    fautifs = [m for m in _MOTS_QUI_RENDENT_FACULTATIF if m in banniere]
    assert not fautifs, (
        f"the tick's banner qualifies its own content ({fautifs}): {banniere!r}. "
        "The tick carries its own headers, one per nature — this line only opens the block."
    )


def test_aucune_banniere_du_hook_n_enveloppe_le_tick_dans_un_cadre_facultatif() -> None:
    """The CLASS, not the case: a neighbouring banner added higher up would reintroduce the
    defect without touching this one. The witness above would close one case; this one closes the
    class — EVERYTHING that opens a block before the call to the tick is judged, not just the
    closest line."""
    lignes = _HOOK.read_text(encoding="utf-8").splitlines()
    appel = next(i for i, l in enumerate(lignes) if "mnemosyne.runtime.tick" in l)
    cadres = [l.lower() for l in lignes[:appel] if re.match(r'\s*echo "---', l)]
    coupables = [
        (c, m) for c in cadres for m in _MOTS_QUI_RENDENT_FACULTATIF if m in c
    ]
    assert not coupables, coupables
