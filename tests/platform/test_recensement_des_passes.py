"""Witnesses of the pass census (G3) and of the frozen barrier (G5).

**THE FIVE SURFACES ARE COVERED SEPARATELY**, because an isolated audit just found 6 surviving
mutations on a module that had 19 green witnesses — all on the judge and the edge,
**none on the line that turns a verdict into a refusal**:

1. **the JUDGE** — :func:`recenser`, :func:`verdict`, pure, on injected data;
2. **the RC / the DECISION** — `main()` must return 1 on a broken freeze, 2 on a non-measurement;
3. **the PUBLISHED TEXT** — the sentences from :func:`rendre` and :func:`message`, read as-is;
4. **the PRODUCTION VALUE** — `RACINE`, `CHEMIN_PORTE` and `PASSES` judged on the REAL repository,
   never injected: *injecting everywhere leaves the real value untested*;
5. **the PASSING CASE** — the real gate, unmutated, does not turn red.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mnemosyne.production.barriere_gelee import message, verdict
from mnemosyne.production.recensement_des_passes import (
    PASSES,
    PASSES_GELEES,
    PasseDeclaree,
    extraire_le_python,
    recenser,
    rendre,
)
from mnemosyne.runtime import passes_run

# --------------------------------------------------------------------------------------------
# 0. The harness: a MINIATURE gate, the same shape as the real one, that we are allowed to maim.
# --------------------------------------------------------------------------------------------
#
# It is NOT a substitute for the real one: section 4 judges the real repository. It exists to
# ask questions that cannot be asked of a file we are not allowed to damage.

_PORTE_SAINE = """\
#!/bin/sh
set -eu
PYTHONPATH=system/lib uv run python - <<'PYEOF'
import sys


def juger():
    if False:
        sys.stderr.write("[pre-commit] alpha refuse -- commit refuse.\\n")
        sys.exit(1)


juger()
if False:
    sys.stderr.write("[pre-commit] beta refuse -- commit refuse.\\n")
    sys.exit(1)
sys.exit(0)
PYEOF
"""

_DEUX = (PasseDeclaree("alpha", "alpha refuse"), PasseDeclaree("beta", "beta refuse"))


def _python(shell: str) -> str:
    corps = extraire_le_python(shell)
    assert corps is not None
    return corps


# --------------------------------------------------------------------------------------------
# 1. THE JUDGE — pure verdicts, on injected data.
# --------------------------------------------------------------------------------------------


def test_le_CAS_PASSANT_deux_passes_ecrites_et_atteignables_sont_vivantes() -> None:
    """Without this witness, we would only be measuring its ability to refuse everything."""
    r = recenser(_python(_PORTE_SAINE), _DEUX)
    assert [p.identifiant for p in r.passes if p.vivante] == ["alpha", "beta"]
    assert r.non_declarees == ()
    assert r.sites == 2
    assert verdict(r.vivantes, {"alpha", "beta"}).refuse is False


def test_une_passe_RETIREE_de_la_porte_n_est_plus_ni_cablee_ni_vivante() -> None:
    """The original defect: *removing a pass left the repository green*."""
    ampute = _PORTE_SAINE.replace(
        '    sys.stderr.write("[pre-commit] beta refuse -- commit refuse.\\n")\n    sys.exit(1)\n',
        "    pass\n",
    )
    assert ampute != _PORTE_SAINE, (
        "the harness mutation changed nothing — this witness would measure falsely"
    )
    r = recenser(_python(ampute), _DEUX)
    perdue = next(p for p in r.passes if p.identifiant == "beta")
    assert perdue.cablee is False and perdue.vivante is False
    assert verdict(r.vivantes, {"alpha", "beta"}).disparues == ("beta",)


def test_l_axe_EXECUTION_attrape_ce_que_l_axe_CABLAGE_declare_VERT() -> None:
    """THE CENTRAL PROPERTY: a refusal block that is **intact**, moved into a function nobody
    calls anymore, stays perfectly grep-able — and no longer runs."""
    endormie = _PORTE_SAINE.replace("\njuger()\n", "\n", 1)
    assert endormie != _PORTE_SAINE
    r = recenser(_python(endormie), _DEUX)
    alpha = next(p for p in r.passes if p.identifiant == "alpha")
    assert alpha.cablee is True, "the header is still written: the WIRING axis sees nothing"
    assert alpha.atteignable is False, "but nothing calls it anymore"
    assert alpha.vivante is False
    assert alpha.portee == "juger"


def test_un_en_tete_qui_n_est_QUE_cite_ne_compte_pas_pour_un_cablage() -> None:
    """*A text detector counts citations as instances* — not this one: only a string that is the
    **argument of a call** counts as wiring."""
    citante = _PORTE_SAINE.replace(
        '    sys.stderr.write("[pre-commit] beta refuse -- commit refuse.\\n")\n',
        '    "[pre-commit] beta refuse -- commit refuse."\n',
    )
    assert citante != _PORTE_SAINE
    r = recenser(_python(citante), _DEUX)
    assert next(p for p in r.passes if p.identifiant == "beta").cablee is False


def test_une_en_tete_CONSTRUITE_par_concatenation_reste_un_cablage() -> None:
    """**SABOTAGE FIX.** The first version only read the ARGUMENT position: a header assembled
    (`"[pre-commit] beta refuse" + suffix`, an f-string) rendered the pass ABSENT even though it
    was refusing perfectly — and the sabotage that widened the reading SURVIVED, for lack of a
    witness that demands that widening. *A sabotage that makes the module more correct survives
    as long as nothing demands that correctness.*

    **THE LIMIT, WRITTEN DOWN RATHER THAN DISCOVERED**: a header cut RIGHT IN THE MIDDLE of the
    prefix (`"[pre-commit] " + "beta refuse"`) stays invisible — no single constant then carries
    both the prefix AND the marker. This is the real boundary of any static string reader."""
    construite = _PORTE_SAINE.replace(
        '    sys.stderr.write("[pre-commit] beta refuse -- commit refuse.\\n")',
        '    sys.stderr.write("[pre-commit] beta refuse" + " -- commit refuse.")',
    )
    assert construite != _PORTE_SAINE
    r = recenser(_python(construite), _DEUX)
    assert next(p for p in r.passes if p.identifiant == "beta").vivante is True


def test_un_en_tete_sans_sortie_en_code_NON_NUL_n_est_pas_une_passe() -> None:
    """*A check that prints is not a barrier, it is a comment.*"""
    bavarde = _PORTE_SAINE.replace(
        '    sys.stderr.write("[pre-commit] beta refuse -- commit refuse.\\n")\n    sys.exit(1)\n',
        '    sys.stderr.write("[pre-commit] beta refuse -- commit refuse.\\n")\n',
    )
    assert bavarde != _PORTE_SAINE
    r = recenser(_python(bavarde), _DEUX)
    assert next(p for p in r.passes if p.identifiant == "beta").cablee is False


def test_une_passe_NEUVE_hors_du_gel_est_PUBLIEE_jamais_refusee() -> None:
    """The FLOOR: `frozen ⊆ alive`. An equality would refuse the commit that adds a pass."""
    r = recenser(_python(_PORTE_SAINE), (_DEUX[0],))
    v = verdict(r.vivantes, {"alpha"})
    assert v.refuse is False
    assert v.neuves and any("beta" in n for n in v.neuves)
    assert r.non_declarees, "a gate pass outside the freeze must stay VISIBLE"


def test_un_ECHANGE_de_passes_laisse_le_COMPTE_identique_et_le_gel_le_NOMME() -> None:
    """*A swap would leave 2 = 2, silent.* This is why the freeze is keyed on the SET."""
    v = verdict(("alpha", "gamma"), {"alpha", "beta"})
    assert len(("alpha", "gamma")) == len({"alpha", "beta"})
    assert v.disparues == ("beta",) and v.neuves == ("gamma",)
    assert v.refuse is True


def test_zero_passe_vivante_est_une_PANNE_D_INSTRUMENT_jamais_un_vert() -> None:
    v = verdict((), {"alpha"})
    assert v.non_mesure is True
    assert v.refuse is True, "the disappearance is real ALSO when nothing was read"
    assert verdict((), ()).non_mesure is True


def test_le_heredoc_absent_ou_double_rend_None_jamais_une_chaine_vide() -> None:
    assert extraire_le_python("#!/bin/sh\necho nothing\n") is None
    assert extraire_le_python(_PORTE_SAINE + _PORTE_SAINE) is None


# --------------------------------------------------------------------------------------------
# 2. THE PUBLISHED TEXT — the sentence, not just the data feeding it.
# --------------------------------------------------------------------------------------------


def test_le_DENOMINATEUR_publie_est_LE_GEL_jamais_ce_qui_a_ete_VU() -> None:
    """The exact fault from a real project's audit (`36/38`, denominator `len(ran)`): when a pass
    DISAPPEARS, an observed denominator shrinks and the rate **goes back up**."""
    ampute = _PORTE_SAINE.replace(
        '    sys.stderr.write("[pre-commit] beta refuse -- commit refuse.\\n")\n    sys.exit(1)\n',
        "    pass\n",
    )
    page = rendre(recenser(_python(ampute), _DEUX), frozenset({"alpha", "beta"}))
    assert "1/2" in page, page
    assert "2/2" not in page and "1/1" not in page


def test_la_page_NOMME_la_passe_absente_et_la_passe_ENDORMIE_separement() -> None:
    """The two causes do not share a single bucket: *a remedy written against the wrong diagnosis
    leaves the mechanism intact*."""
    endormie = _PORTE_SAINE.replace("\njuger()\n", "\n", 1)
    page = rendre(recenser(_python(endormie), _DEUX), frozenset({"alpha", "beta"}))
    assert "ABSENT" not in page, page
    assert "UNREACHABLE" in page and "alpha" in page and "juger" in page


def test_le_message_de_REFUS_nomme_la_passe_ET_le_geste() -> None:
    """*The refusal message names the way out* — without which the reader loosens the judge."""
    texte = message(verdict(("alpha",), {"alpha", "beta"}))
    assert "GEL ROMPU" in texte and "beta" in texte
    assert "RETABLIS" in texte or "retire-la du gel" in texte
    assert "1 " in texte, "the compared cardinal must travel WITH the verdict"


def test_le_texte_de_NON_MESURE_ne_se_lit_pas_comme_un_vert() -> None:
    texte = message(verdict((), ()))
    assert "NON MESURE" in texte
    assert "zero paire est vraie par construction" in texte
    vide = rendre(recenser("import sys\n", _DEUX))
    assert "NOT SURVEYED" in vide and "instrument failure" in vide


# --------------------------------------------------------------------------------------------
# 3. THE RC — the line that turns a verdict into a refusal is a surface of its own.
# --------------------------------------------------------------------------------------------


def _faux_depot(tmp_path: Path, shell: str) -> Path:
    (tmp_path / ".githooks").mkdir()
    (tmp_path / ".githooks" / "pre-commit").write_text(shell, encoding="utf-8")
    return tmp_path


def test_le_rc_vaut_0_sur_une_porte_SAINE(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    racine = _faux_depot(tmp_path, _PORTE_SAINE)
    assert passes_run.main(racine=racine, declarees=_DEUX) == 0
    assert "gel tenu" in capsys.readouterr().out


def test_le_rc_vaut_1_quand_une_passe_GELEE_a_disparu(tmp_path: Path) -> None:
    racine = _faux_depot(tmp_path, _PORTE_SAINE)
    manquante = (*_DEUX, PasseDeclaree("disparue", "disparue refuse"))
    assert passes_run.main(racine=racine, declarees=manquante) == 1


def test_le_rc_vaut_2_sur_une_porte_ILLISIBLE_pas_1_ni_0(tmp_path: Path) -> None:
    """*Two absences of measurement never compare equal to a green result* — nor to a refusal."""
    assert passes_run.main(racine=tmp_path, declarees=_DEUX) == 2


def test_le_rc_vaut_2_quand_le_HEREDOC_a_disparu(tmp_path: Path) -> None:
    racine = _faux_depot(tmp_path, "#!/bin/sh\nexit 0\n")
    assert passes_run.main(racine=racine, declarees=_DEUX) == 2


def test_le_rc_vaut_2_quand_le_bloc_python_NE_PARSE_PAS(tmp_path: Path) -> None:
    casse = _PORTE_SAINE.replace("import sys", "import sys\ndef (:")
    racine = _faux_depot(tmp_path, casse)
    assert passes_run.main(racine=racine, declarees=_DEUX) == 2


def test_le_rc_vaut_2_et_non_0_quand_la_porte_ne_porte_AUCUNE_passe(tmp_path: Path) -> None:
    """The most dangerous case: an EMPTY freeze compared against an EMPTY gate would return
    `refuse=False`."""
    racine = _faux_depot(
        tmp_path, "#!/bin/sh\nuv run python - <<'PYEOF'\nimport sys\nsys.exit(0)\nPYEOF\n"
    )
    assert passes_run.main(racine=racine, declarees=(), gelees=frozenset()) == 2


# --------------------------------------------------------------------------------------------
# 4. THE PRODUCTION VALUE — judged on the REAL repository, never injected.
# --------------------------------------------------------------------------------------------
#
# This is how a `parents[4]` changed to `parents[3]` survived 19 witnesses elsewhere in this
# repository: all of them injected their own root, and the real value stayed untested.


def test_le_CHEMIN_de_production_designe_le_hook_REEL_et_il_porte_un_heredoc() -> None:
    chemin = passes_run.RACINE / passes_run.CHEMIN_PORTE
    assert chemin.is_file(), f"{chemin} — the production RACINE does not point at the repository"
    assert extraire_le_python(chemin.read_text(encoding="utf-8")) is not None


def test_les_CINQ_marqueurs_geles_sont_ECRITS_dans_la_porte_REELLE() -> None:
    """The freeze certifies *"these passes existed"*: a marker that matches nothing would make
    that false on one side, with no refusal ever saying so."""
    texte = (passes_run.RACINE / passes_run.CHEMIN_PORTE).read_text(encoding="utf-8")
    absents = [p.identifiant for p in PASSES if p.marqueur not in texte]
    assert absents == [], f"marker(s) not found in the real gate: {absents}"


def test_le_CAS_PASSANT_de_PRODUCTION_la_porte_REELLE_ne_rougit_pas(
    capsys: pytest.CaptureFixture,
) -> None:
    """The witness for the legitimate case, on the REAL population and the REAL freeze — no
    injection."""
    assert passes_run.main() == 0
    sortie = capsys.readouterr().out
    assert f"{len(PASSES_GELEES)}/{len(PASSES_GELEES)}" in sortie


def test_le_gel_de_production_est_un_ENSEMBLE_derive_de_la_table_ecrite_a_la_main() -> None:
    assert PASSES_GELEES == frozenset(p.identifiant for p in PASSES)
    assert len(PASSES_GELEES) == len(PASSES), "two passes share the same identifier"


def test_le_bord_IMPORTE_le_gel_il_ne_le_RELIT_PAS_par_motif() -> None:
    """The property G5 promises: *read by importing the object, never by `grep`*.

    A freeze re-read by text pattern disarms itself at the first reformatting — **silently**, a
    pattern that no longer matches renders an empty set, hence "nothing to compare," hence a
    green result."""
    source = Path(passes_run.__file__).read_text(encoding="utf-8")
    assert "from ..production.recensement_des_passes import" in source
    assert "PASSES_GELEES" in source
    for interdit in ('re.compile("PASSES_GELEES', 'read_text(encoding="utf-8").split'):
        assert interdit not in source
    assert passes_run.PASSES_GELEES is PASSES_GELEES


def test_la_porte_REELLE_amputee_d_une_passe_est_REFUSEE(tmp_path: Path) -> None:
    """THE PROOF THAT COUNTS: the REAL gate, copied then maimed. A miniature harness proves the
    mechanism works; this one proves it bites **on the production population**."""
    racine = tmp_path / "clone"
    (racine / ".githooks").mkdir(parents=True)
    reelle = passes_run.RACINE / passes_run.CHEMIN_PORTE
    shutil.copy(reelle, racine / passes_run.CHEMIN_PORTE)
    assert passes_run.main(racine=racine) == 0, "the faithful copy must pass"

    cible = racine / passes_run.CHEMIN_PORTE
    avant = cible.read_text(encoding="utf-8")
    apres = avant.replace('"[pre-commit] cycle de dependances', '"[commentaire] cycle')
    assert apres != avant, "the mutation changed nothing — this witness would measure falsely"
    cible.write_text(apres, encoding="utf-8")
    assert passes_run.main(racine=racine) == 1
