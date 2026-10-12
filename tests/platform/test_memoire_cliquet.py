"""THE MEMORY RATCHET GETS JUDGED (D173) — every witness is a sabotage that, without it, would
turn green.

 WHY THIS FILE EXISTS. The defect this ratchet guards against has already happened here: a
compaction pass destroyed the link to a 20 KB card, **nothing pointed to it anymore**, and the
loss survived **several sessions** without any check turning red. It was found only through the
DIFF OF SETS (`226 cards <-> 225 targets`), never through a re-read.

 AND THE FIRST WITNESS IS THE INNOCENT CASE. Without it, a judge that refused EVERYTHING would
pass all the others — *a gate that is already red discriminates against no one.*
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.runtime import memoire


def _dossier(tmp_path: Path, principal: str = "", debordement: str | None = "",
             fiches: tuple[str, ...] = ()) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "MEMORY.md").write_text(principal, encoding="utf-8")
    if debordement is not None:
        (tmp_path / "MEMORY-2.md").write_text(debordement, encoding="utf-8")
    for nom in fiches:
        (tmp_path / nom).write_text("x", encoding="utf-8")
    return tmp_path


def test_une_memoire_SAINE_passe(tmp_path: Path) -> None:
    """ THE INNOCENT CASE, first: an intact bijection must produce NO reason at all."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n- [B](b.md)\n",
                 debordement="- [C](c.md)\n", fiches=("a.md", "b.md", "c.md"))
    raisons, m = memoire.verdict(d)
    assert raisons == [], f"a healthy memory must pass. Reasons: {raisons}"
    assert (m["fiches"], m["cibles"], m["morts"], m["orphelines"]) == (3, 3, 0, 0)


def test_une_ORPHELINE_refuse_et_le_COMPTE_ne_la_verrait_pas(tmp_path: Path) -> None:
    """ THE REAL DEFECT, REPLAYED. A lost card AND an added target leave the COUNT identical
 (2 cards, 2 targets): only the DIFF OF SETS tells them apart.
 *A count cannot see a substitution.*"""
    d = _dossier(tmp_path, principal="- [A](a.md)\n- [Z](z.md)\n",
                 debordement="", fiches=("a.md", "orphan.md"))
    raisons, m = memoire.verdict(d)
    assert m["fiches"] == m["cibles"] == 2, "the trap: the COUNTS are equal"
    assert m["morts"] == 1 and m["orphelines"] == 1
    assert any("ORPHAN" in r for r in raisons), f"the orphan must be NAMED. Seen: {raisons}"
    assert any("DEAD" in r for r in raisons), f"the dead link must be NAMED. Seen: {raisons}"


def test_les_causes_sont_DISCERNABLES(tmp_path: Path) -> None:
    """ *TWO ABSENCES OF RESULT COMPARE EQUAL.* Three distinct defects all produce a non-empty
 list: without this comparison, a judge that gave the SAME sentence to all three would pass the
 witnesses above."""
    mort, _ = memoire.verdict(_dossier(tmp_path / "a", principal="- [Z](z.md)\n"))
    orph, _ = memoire.verdict(_dossier(tmp_path / "b", fiches=("alone.md",)))
    absent, _ = memoire.verdict(_dossier(tmp_path / "c", debordement=None))
    assert len({tuple(mort), tuple(orph), tuple(absent)}) == 3, (
        f"three causes must produce three distinct messages.\n"
        f"  dead_link={mort}\n  orphan={orph}\n  missing_overflow={absent}")


def test_un_index_QUI_GRANDIT_refuse_et_la_BORNE_EXACTE_passe(tmp_path: Path) -> None:
    """ THE TWO BOUNDS, AND IT IS THE PAIR THAT KILLS A SIGN-FLIP SABOTAGE. A `>` changed to
 `>=`, to `<`, or to `> 0` makes one of these two points diverge.
 *A rule written as one inequality only guards one side: both are pinned down.*"""
    gel = memoire.TAILLE_GELEE_DE_L_INDEX
    exact, _ = memoire.verdict(_dossier(tmp_path / "exact", principal="x" * gel))
    assert not any("GROWN" in r for r in exact), "the freeze is INCLUSIVE: reaching it is not growing"
    trop, _ = memoire.verdict(_dossier(tmp_path / "trop", principal="x" * (gel + 1)))
    assert any("GROWN" in r for r in trop), f"ONE more byte must REFUSE. Seen: {trop}"


def test_un_lien_COMMENTE_ne_compte_PAS_comme_un_pointeur(tmp_path: Path) -> None:
    """ THE DEFECT FOUND ON THE RATCHET'S VERY FIRST FIRING, AND IT DECIDED THE DIRECTION OF
 THE ERROR. A `[T](x.md)` inside an HTML comment is **invisible in the rendered index**:
 counting it would turn a card that nothing visible points to GREEN — the exact silent loss
 this ratchet exists to catch. *Between a silent false green and a loud false red, the loud
 one wins.*"""
    d = _dossier(tmp_path, principal="- [A](a.md)\n<!-- - [Ghost](ghost.md) -->\n",
                 fiches=("a.md",))
    _, m = memoire.verdict(d)
    assert m["cibles"] == 1, "the commented-out link must NOT enter the targets"
    assert m["morts"] == 0, "and must therefore NOT produce a dead link"


def test_un_dossier_ABSENT_refuse_sans_conclure_que_la_memoire_est_VIDE(tmp_path: Path) -> None:
    """ *TWO ABSENCES OF MEASUREMENT COMPARE EQUAL.* A path that fails to resolve would produce
 `fiches=0 cibles=0` — the exact signature of a perfectly healthy, empty memory. The refusal
 must say that it is the PATH that is missing, never the memory."""
    raisons, m = memoire.verdict(tmp_path / "this-path-does-not-exist")
    assert any("NOT FOUND" in r for r in raisons), f"the cause must be the PATH. Seen: {raisons}"
    assert "fiches" not in m, "a missing folder must PUBLISH NO card count at all"


def test_le_rendu_ATTESTE_l_emission_par_les_OCTETS_ecrits(tmp_path: Path,
                                                           capsys: pytest.CaptureFixture) -> None:
    """ *THE EFFECT IS MEASURED, NEVER THE INTENT.* `overflow=INJECTED` must follow from the
 bytes ACTUALLY written to the output. An EMPTY overflow file cannot render the same sentence
 as an emitted one — or the line would say "injected" on the day the emission does nothing."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n", debordement="- [C](c.md)\n",
                 fiches=("a.md", "c.md"))
    assert memoire.rendre(d, dette_gelee=2) == 0
    plein = capsys.readouterr().out
    assert "- [C](c.md)" in plein, "the CONTENT of the overflow file must land on the output"
    # FOUND BY A SECOND SURVIVING SABOTAGE: `emis = len(texte.encode())` replaced by
    # `emis = 1` used to pass, because nothing tied the PUBLISHED FIGURE to the measurement it
    # comes from. *A published count that no witness ties back to its own computation is a
    # memory, not a measurement.*
    octets = len((d / "MEMORY-2.md").read_bytes())
    assert f"overflow=INJECTED({octets}b)" in plein, (
        f"the published figure must be the TRUE byte count ({octets}). Seen: {plein}")

    (d / "MEMORY-2.md").write_text("", encoding="utf-8")
    memoire.rendre(d, dette_gelee=2)
    vide = capsys.readouterr().out
    assert "overflow=EMPTY" in vide, f"an empty overflow file must not announce INJECTED. Seen: {vide}"
    # FOUND BY A SURVIVING SABOTAGE, NOT BY RE-READING. Replacing `if texte.strip()` with
    # `if True`, the line still read `EMPTY` — but the HEADER still printed anyway: a hollow
    # channel **looked present**. *A survivor does not declare itself harmless: it names the
    # missing assertion.*
    assert "--- MEMORY-2.md" not in vide, (
        f"an empty overflow file must print NO header at all — an announced, hollow section "
        f"reads as a working channel. Seen: {vide}")


# ── A2 · "a lesson with no barrier is a wish" ───────────────────────────────────────────────────
# Rule imported from another project, where it has governed `state/lecons/lecons.md` since July. Measured on
# 2026-08-09 before importing it: **288 cards out of 293** said nothing about what makes their
# fault impossible — so it did NOT exist here.

def _fiche(dossier: Path, nom: str, corps: str) -> None:
    (dossier / nom).write_text(f"---\nname: {nom[:-3]}\n---\n\n{corps}\n", encoding="utf-8")


def test_une_lecon_SANS_barriere_au_dela_du_gel_REFUSE(tmp_path: Path) -> None:
    """ THE GATE ARMED: the frozen debt is 1, two silent cards arrive."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n- [B](b.md)\n")
    _fiche(d, "a.md", "un simple rappel moral")
    _fiche(d, "b.md", "un autre rappel moral")
    raisons, m = memoire.verdict(d, dette_gelee=1)
    assert m["sans_barriere"] == 2
    assert any("WITH NO BARRIER" in r for r in raisons), raisons
    assert any("b.md" in r for r in raisons), "the guilty card must be NAMED, not just counted"


def test_l_AVEU_vaut_declaration_et_c_est_la_clause_ANTI_FABRICATION(tmp_path: Path) -> None:
    """ THE CLAUSE THAT STOPS THIS RULE FROM MANUFACTURING ITS OWN CONTENT. Another project paid for
 exactly the opposite: *a check that requires a PER-CARD quantity manufactures the content it
 demands* — 5 invented clauses in the commit that needed them, 2 of them false for their own
 target. Writing "none" must therefore PASS: as long as the admission is free, nothing pushes
 toward inventing one."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n")
    _fiche(d, "a.md", "**Barrière : aucune — dit comme tel.** C'est de la discipline.")
    raisons, m = memoire.verdict(d, dette_gelee=0)
    assert m["sans_barriere"] == 0, "the admission IS a valid answer"
    assert raisons == [], raisons


def test_la_forme_NIVEAU_prescrite_par_la_doctrine_VAUT_declaration(tmp_path: Path) -> None:
    """ THE JUDGE USED TO READ ONLY ONE OF THE TWO FORMS THE DOCTRINE PRESCRIBES.
 `every-lesson-declares-its-level.md` has established "NIVEAU n" [LEVEL n] since 2026-07-29
 (1 = admission, 2 = barrier in code). This pattern only knew `**Barriere :` — so **the very
 card that PRESCRIBES the form was being counted as a wish by the gate that judges it**, along
 with 9 others.
 Measured on 2026-09-08 through the judge's own accessor, across 708 cards: 10 recognized,
 0 lost, 515 -> 505.
 What this witness holds, and what the global count alone would not: the count will move with
 every card written, but the RECOGNITION OF THE FORM itself must stay true forever."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n- [B](b.md)\n")
    _fiche(d, "a.md", "> \U0001F9F1 **NIVEAU 1 — aveu.** Aucune barriere n'existe. Le geste est procedural.")
    _fiche(d, "b.md", "> \U0001F9F1 **NIVEAU 2 — la barriere.** `test_x` mord si la classe revient.")
    raisons, m = memoire.verdict(d, dette_gelee=0)
    assert m["sans_barriere"] == 0, "the form the doctrine prescribes MUST count as a declaration"
    assert raisons == [], raisons


def test_les_deux_points_HORS_du_gras_valent_EN_TETE_DE_LIGNE_seulement(tmp_path: Path) -> None:
    """ THIRD FORM — AND IT IS POSITION THAT DECIDES, NOT THE FORM ITSELF.
 `**Barriere** :` (colon outside the bold) is used by 6 cards in the corpus as of 2026-09-08:
 **5 real declarations, 1 ordinary sentence** ("above all something started — a **barrier**:
 this session measured..."). The chosen discriminant is therefore POSITION: a declaration OPENS
 its line, a sentence continues it. This witness holds BOTH sides in a single verdict — without
 the second case, widening to absurdity would pass green, and *a capture rate with no measured
 false-positive rate is a wall, not a gate*."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n- [B](b.md)\n- [C](c.md)\n")
    _fiche(d, "a.md", "\U0001F6E1\U0000FE0F **Barrière** : le foyer unique `_lister_moissons`, deux temoins.")
    _fiche(d, "b.md", "- \U0001F9F1 **Barrière** : `H5` du plan, et son appelant est nomme.")
    _fiche(d, "c.md", "Il fallait une chose commencée — surtout une **barrière** : on a mesuré.")
    # freeze at 0: the gate must be ARMED, or a green witness only measures its own silence.
    raisons, m = memoire.verdict(d, dette_gelee=0)
    assert m["sans_barriere"] == 1, "the 2 declarations at the start of the line pass, the SENTENCE does not"
    assert any("c.md" in r for r in raisons), f"it is the SENTENCE that must be named. Seen: {raisons}"


def test_niveau_MINUSCULE_ne_vaut_PAS_declaration_car_c_est_un_MOT_FRANCAIS(tmp_path: Path) -> None:
    """ CASE IS THE DISCRIMINANT, AND IT WAS MEASURED BEFORE BEING CHOSEN.
 In the 2026-09-08 corpus: uppercase "NIVEAU" = **12 occurrences, all 12 declarative**;
 lowercase "niveau" = **107 occurrences across 164 cards**, ordinary French. Setting
 `re.IGNORECASE` as a GLOBAL flag — the obvious move — would have passed 27 cards on the
 ordinary word alone: *a TEXT detector counts citations as instances*. Hence `(?i:...)` on
 `Barriere` ALONE. This witness is the half its neighbor is missing: without it, widening to
 absurdity would pass green. **A capture rate with no measured false-positive rate is a wall,
 not a gate.**"""
    d = _dossier(tmp_path, principal="- [A](a.md)\n")
    _fiche(d, "a.md", "On descend au niveau 2 de l'arborescence, puis niveau 3. Rien de declaratif.")
    raisons, m = memoire.verdict(d, dette_gelee=0)
    assert m["sans_barriere"] == 1, "a lowercase « niveau » is an ordinary French word, not a declaration"
    assert any("a.md" in r for r in raisons), raisons


def test_la_forme_Barriere_en_MINUSCULES_reste_reconnue_NON_REGRESSION(tmp_path: Path) -> None:
    """ THE HALF A WIDENING SILENTLY LOSES. The original pattern carried `re.IGNORECASE` as a
 flag; replacing it with an alternation makes it fall silently, and the first candidate written
 here DROVE THE COUNT UP to 542 for this exact reason — *"before" and "after" must be THE SAME
 measurement*. 27 cards depend on it."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n- [B](b.md)\n")
    _fiche(d, "a.md", "**barriere : aucune.** minuscules, sans accent.")
    _fiche(d, "b.md", "**BARRIÈRES : le temoin Y.** majuscules, pluriel, accentue.")
    _, m = memoire.verdict(d, dette_gelee=0)
    assert m["sans_barriere"] == 0, "case-insensitivity on « Barriere » must NOT regress"


def test_la_dette_qui_BAISSE_refuse_AUSSI_et_NOMME_le_chiffre_a_ecrire(tmp_path: Path) -> None:
    """ *A RATCHET ABOVE WHICH THE CORPUS FLOATS IS JUST WAITING TO BE WRECKED.* Given any
 slack, an empty lesson gets in FOR FREE. And the refusal must say WHICH figure to write —
 *the refusal message names the way out*, or it gets worked around."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n")
    _fiche(d, "a.md", "**Barrière : le temoin X.**")
    raisons, _ = memoire.verdict(d, dette_gelee=5)
    assert any("FALLEN" in r for r in raisons), raisons
    assert any("DETTE_SANS_BARRIERE = 0" in r for r in raisons), (
        f"the refusal must name the exact figure to write. Seen: {raisons}")


def test_une_fiche_ILLISIBLE_compte_comme_SANS_barriere(tmp_path: Path) -> None:
    """*The default branch is where silence hides.* A card that cannot be read must not be able
    to LOWER the debt: that would be banking green without ever writing a barrier."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n")
    (d / "a.md").write_bytes(b"\xff\xfe pas de l'utf-8 valide \xff")
    assert memoire.fiches_sans_barriere(d) == ["a.md"]


def test_les_DEUX_index_ne_comptent_PAS_dans_la_dette(tmp_path: Path) -> None:
    """`MEMORY.md` and `MEMORY-2.md` POINT to the lessons, they are not lessons themselves.
    Counting them would inflate the debt by 2 forever, with no barrier ever able to close them."""
    d = _dossier(tmp_path, principal="- [A](a.md)\n")
    _fiche(d, "a.md", "**Barrière : aucune.**")
    assert memoire.fiches_sans_barriere(d) == []


def test_le_VRAI_chemin_applique_le_gel_de_PRODUCTION(tmp_path: Path) -> None:
    """ REACHABILITY — *the barrier that NOTHING calls.* `verdict()` has a freeze that
 defaults to `None`, so a witness can set it; if the real caller forgot to pass it, the gate
 would be disarmed IN PRODUCTION without a single witness above so much as flinching."""
    import inspect
    defaut = inspect.signature(memoire.rendre).parameters["dette_gelee"].default
    assert defaut == memoire.DETTE_SANS_BARRIERE, (
        f"the real path must carry the production freeze, seen: {defaut}")

    d = _dossier(tmp_path, principal="- [A](a.md)\n- [B](b.md)\n")
    _fiche(d, "a.md", "rappel moral")
    _fiche(d, "b.md", "rappel moral")
    assert memoire.rendre(d, dette_gelee=1) == 1, "the rc must BITE, not just print"


def test_le_gel_de_production_est_GELE_a_sa_valeur_MESUREE() -> None:
    """ Without this literal freeze, setting `DETTE_SANS_BARRIERE` to 999 would disarm the gate
 without turning a single witness red — this is the exact sabotage that SURVIVED on the seed
 this morning (a witness that reads the very constant being judged judges nothing). 288,
 measured on 2026-08-09 across 293 cards.

 AND IT REALLY BIT ON 2026-08-10. A session had tightened the constant to 272 without
 touching this witness: the repository carried a freeze that nothing confirmed anymore. This
 was the only check that saw it — the gate itself was returning GREEN, since it judges against
 the constant. *A figure read from inside the judge cannot be judged by that same judge.*
 Lowering the freeze remains a deliberate gesture, and that gesture has TWO sides."""
    assert memoire.DETTE_SANS_BARRIERE == 267


def test_le_refus_nomme_la_fiche_LA_PLUS_RECENTE_pas_la_derniere_ALPHABETIQUEMENT(
    tmp_path: Path,
) -> None:
    """ DEFECT FOUND THROUGH REAL USE, NOT THROUGH RE-READING. The gate bit three times on the
 day it was set up; twice its message named innocent cards several weeks old — the last ones
 in ALPHABETICAL order — instead of the lesson that had just been written.
 *A refusal that names the wrong culprit sends someone off to fix what is already fine.*"""
    import os

    d = _dossier(tmp_path, principal="- [Z](zzz-old.md)\n- [A](aaa-new.md)\n")
    _fiche(d, "zzz-old.md", "rappel moral, mais ancienne")
    _fiche(d, "aaa-new.md", "rappel moral, ecrite a l'instant")
    vieux = (d / "zzz-old.md").stat().st_mtime - 40 * 86_400
    os.utime(d / "zzz-old.md", (vieux, vieux))

    assert memoire.fiches_sans_barriere(d)[0] == "aaa-new.md", "the most RECENT one first"
    raisons, _ = memoire.verdict(d, dette_gelee=1)
    fautif = next(r for r in raisons if "WITH NO BARRIER" in r)
    assert "aaa-new.md" in fautif, f"the refusal must name the guilty card. Seen: {fautif}"
