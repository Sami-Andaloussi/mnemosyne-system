"""H6 — the wiring: `mandat_derive`/`rendre_mandat` derive a mandate from `file_d_attente` (B2),
without ever fabricating the comment, the warning, or the reminder a human writes by hand.

Level 1: these witnesses prove that the DERIVATION is correct, never that it replaces the manual one
— `H6` does not require that, the item says so explicitly (level 2 awaits a judged diff).

**12:5x — status and load added, not prose**: two non-producers (chat 1, chat 2) measured
that this module was publishing ONLY `items` -- status and the `*À lire*` load are facts of the plan
already read/proven elsewhere, never an invented comment. See `plan_mandat.py`'s docstring.
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.production.plan_format import read_plan
from mnemosyne.production.plan_mandat import MandatDerive, mandat_derive, rendre_mandat

HEAD = ("# PLAN — demo", "", "> **Cap** : prove the mandate", "")

#: No fixture below carries an `*À lire*` field (except the dedicated section at the bottom of
#: the file) -- `charge_en_octets` returns `None` before ever touching the disk, so THIS root
#: is never actually resolved. A REAL `Path` rather than an invented one, so a future reader
#: never has to wonder whether a dummy value means something elsewhere.
_RACINE_SANS_A_LIRE = Path(__file__).resolve().parent


def plan(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def item(ident: str, depend: str, statut: str = "\U00002B1C") -> tuple[str, ...]:
    return (f"- **{ident}** {statut} an item.", f"  *Dépend de* : {depend}")


# ---- mandat_derive: the derivation itself -------------------------------------------------
def test_LE_PLUS_DEBLOQUANT_EST_LA_TETE_DU_MANDAT() -> None:
    reading = read_plan(
        plan(*HEAD, *item("Z1", "AUCUNE"), *item("A9", "AUCUNE"), *item("B1", "Z1"), *item("B2", "Z1"))
    )
    mandat = mandat_derive(reading, racine=_RACINE_SANS_A_LIRE)
    assert [r.ident for r in mandat.rangs] == ["Z1", "A9"]
    assert mandat.total_range == 2


def test_N_BORNE_LE_NOMBRE_DE_TETES_SANS_MENTIR_SUR_LE_TOTAL() -> None:
    reading = read_plan(
        plan(*HEAD, *item("A1", "AUCUNE"), *item("A2", "AUCUNE"), *item("A3", "AUCUNE"))
    )
    mandat = mandat_derive(reading, racine=_RACINE_SANS_A_LIRE, n=1)
    assert len(mandat.rangs) == 1
    assert mandat.total_range == 3, "the total must stay the REAL count, not the truncated size"


def test_FAITS_PAR_DEFAUT_SE_DERIVE_DU_STATUT_pas_devine_a_vide() -> None:
    """Same measurement as `carte.py:312-321`: `faits=frozenset()` by default had missed
    startable ranks on this very repo. `mandat_derive` must derive `faits` from status ``fait``,
    never leave the value empty by default."""
    reading = read_plan(
        plan(*HEAD, *item("A1", "AUCUNE", statut="\U00002705"), *item("A2", "A1"))
    )
    mandat = mandat_derive(reading, racine=_RACINE_SANS_A_LIRE)
    assert [r.ident for r in mandat.rangs] == ["A2"], (
        "A2 must be startable: its dependency A1 is done"
    )


def test_UNE_FILE_VIDE_NE_LEVE_PAS() -> None:
    reading = read_plan(plan(*HEAD, *item("A1", "AUCUNE", statut="\U00002705")))
    mandat = mandat_derive(reading, racine=_RACINE_SANS_A_LIRE)
    assert mandat.rangs == ()
    assert mandat.total_range == 0
    assert mandat.statuts == () and mandat.charges == ()


def test_STATUTS_S_ALIGNE_SUR_RANGS_MEME_INDEX() -> None:
    """**Measured while writing this witness, not assumed**: `mandat_derive` pins
 `a_faire=frozenset({"a_faire"})` when calling `file_d_attente` (`plan_mandat.py`) -- a `pret`
 item (``, "awaits YOUR gesture", the same status as `H2`/`B4` tonight) NEVER enters
 `rangs`. `statuts` therefore always equals `a_faire` in practice today -- checked here rather
 than hidden, and the length remains the alignment proof that matters: one fewer item in the
 plan removes one entry from BOTH `rangs` and `statuts`, at the same index."""
    reading = read_plan(plan(*HEAD, *item("Z1", "AUCUNE"), *item("A9", "AUCUNE")))
    mandat = mandat_derive(reading, racine=_RACINE_SANS_A_LIRE)
    assert dict(zip([r.ident for r in mandat.rangs], mandat.statuts, strict=True)) == {
        "Z1": "a_faire",
        "A9": "a_faire",
    }
    reading_single = read_plan(plan(*HEAD, *item("Z1", "AUCUNE", statut="\U0001F17F"), *item("A9", "AUCUNE")))
    mandat_single = mandat_derive(reading_single, racine=_RACINE_SANS_A_LIRE)
    assert [r.ident for r in mandat_single.rangs] == ["A9"], "pret excluded from startable, measured"
    assert mandat_single.statuts == ("a_faire",)


def test_CHARGE_EST_NONE_SANS_CHAMP_A_LIRE_JAMAIS_UN_ZERO_INVENTE() -> None:
    reading = read_plan(plan(*HEAD, *item("A1", "AUCUNE")))
    mandat = mandat_derive(reading, racine=_RACINE_SANS_A_LIRE)
    assert mandat.charges == (None,)


def test_CHARGE_RESOUT_REELLEMENT_LE_CHAMP_A_LIRE_SUR_DISQUE(tmp_path: Path) -> None:
    """A second population, genuinely different: a REAL file on disk, resolved by
    `a_lire.charge_en_octets` -- not a quoted value, a value RECOMPUTED here.

    The token carries a `/`: `a_lire._resoudre` NEVER resolves a token with no slash (deliberate
    caution, `a_lire.py:97`) -- a lesson from this very repo, not a surprise here."""
    (tmp_path / "sub").mkdir()
    cible = tmp_path / "sub" / "leaf.md"
    cible.write_text("twelve bytes\n", encoding="utf-8")
    reading = read_plan(
        plan(*HEAD, "- **A1** \U00002B1C an item.", "  *Dépend de* : AUCUNE", "  *À lire* : `sub/leaf.md`")
    )
    mandat = mandat_derive(reading, racine=tmp_path)
    (charge,) = mandat.charges
    assert charge is not None
    assert charge.octets == cible.stat().st_size
    assert charge.references_resolues == ("sub/leaf.md",)


# ---- rendre_mandat: the published output, deliberately poor -----------------------------------
def test_LE_RENDU_NOMME_LE_RANG_LE_DEBLOCAGE_ET_LA_RAISON() -> None:
    reading = read_plan(plan(*HEAD, *item("Z1", "AUCUNE"), *item("B1", "Z1")))
    lignes = rendre_mandat(mandat_derive(reading, racine=_RACINE_SANS_A_LIRE))
    # The OPENING PAREN is load-bearing: `plan_ordre` composes `r.raison` as
    # "unblocks N step(s) — ...", so a bare "unblocks 1" would also match the reason and stay
    # green even if this module stopped rendering the count itself. "(unblocks 1" matches only
    # the literal THIS module builds.
    assert any(
        "Z1" in ligne and "#1" in ligne and "(unblocks 1" in ligne for ligne in lignes
    ), lignes


def test_LE_RENDU_NOMME_LE_STATUT_ET_UN_COMPTE_DE_CHARGE_JAMAIS_LA_LISTE(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    cible = tmp_path / "sub" / "leaf.md"
    cible.write_text("x", encoding="utf-8")
    reading = read_plan(
        plan(*HEAD, "- **A1** \U00002B1C an item.", "  *Dépend de* : AUCUNE", "  *À lire* : `sub/leaf.md`")
    )
    lignes = rendre_mandat(mandat_derive(reading, racine=tmp_path))
    assert "[a_faire]" in lignes[1]
    assert "1 ref." in lignes[1] and "1 b)" in lignes[1]
    assert "leaf.md" not in lignes[1], "a COUNT, never the reference itself (a_lire.py lists it)"


def test_LE_RENDU_D_UNE_FILE_VIDE_LE_DIT_EXPLICITEMENT() -> None:
    mandat = MandatDerive(rangs=(), total_range=0, statuts=(), charges=())
    lignes = rendre_mandat(mandat)
    assert len(lignes) == 1 and "empty" in lignes[0]


def test_LE_RENDU_NE_FABRIQUE_AUCUNE_PROSE_QUE_LE_PLAN_NE_PORTE_PAS() -> None:
    """A direct safeguard on the module's docstring, rewritten for the 12:5x addition: the
    rendering must contain only facts ALREADY read (`Rang`, status) or already proven elsewhere
    (load, as a COUNT) — never a word this generator would have invented itself."""
    reading = read_plan(plan(*HEAD, *item("A1", "AUCUNE")))
    mandat = mandat_derive(reading, racine=_RACINE_SANS_A_LIRE)
    lignes = rendre_mandat(mandat)
    r = mandat.rangs[0]
    assert r.ident in lignes[1] and r.raison in lignes[1]
    assert lignes[1].count(r.ident) == 1, "no repetition that would look like an added comment"
