"""The GATE on the verbatim floor (`make verbatim-check`) - what the bulk wall `make judge` cannot render.

`make judge` writes a batch report; an `ok` fiche must also be able to receive a NAMED verdict.
This gate therefore answers directly the question "does the fiche I just wrote hold up?".
The properties that make this gate more than a synonym:

1. the DELIVERED SHELL LINE prints the verdict and returns the right exit code (what is delivered is
   `make verbatim-check`, not a function);
2. it TURNS RED - an `exit 1` on a paraphrased fiche, otherwise it is not a gate but a report;
3. it NAMES the dropped passages - the calculation that `judge_fiche` makes and then DROPS (`juge.py`),
   and the one actionable thing a producer can hold onto;
4. it WRITES NOTHING to the repo - verified by fingerprinting the whole tree, not by docstring;
5. it REFUSES to bless if its own count and the judge's diverge (a duplicated extraction).

Pure/offline: no brick, no model, no dependency on a local shelf."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest
from _invariants import REPO_ROOT
from mnemosyne.production.chapter_parsing import PLACEHOLDER_NO_PASSAGE

_SCRIPT = REPO_ROOT / "system" / "skills" / "juge" / "verbatim_check.py"
_spec = importlib.util.spec_from_file_location("verbatim_check_script", _SCRIPT)
assert _spec is not None and _spec.loader is not None
verbatim_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verbatim_check)

_RAW = (
    "Risk management is the core of quantitative finance. "
    "A prudent investor diversifies across uncorrelated assets. "
    "Position sizing ensures a single loss never threatens the whole portfolio. "
    "The margin of safety is the distance between price and intrinsic value. "
    "Volatility must be measured before any capital is ever put at risk."
)
_TRUE = [  # each one is a LITERAL excerpt of _RAW
    "Risk management is the core of quantitative finance.",
    "A prudent investor diversifies across uncorrelated assets.",
    "Position sizing ensures a single loss never threatens the whole portfolio.",
    "The margin of safety is the distance between price and intrinsic value.",
]
_FAUX = "Investors ought to spread their bets across many different holdings."  # not a substring

#: caches the tooling legitimately writes to - the REST of the repo must stay byte-identical.
_CACHES = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


def _fiche(chapters: list[tuple[str, list[str]]]) -> str:
    """The shape of a real fiche: frontmatter, sommaire, then `## N.` / `### Contenu (verbatim)`."""
    parts = [
        "---",
        'title: "T"',
        'type: "book"',
        'distilled_by: "test"',
        "---",
        "",
        "# T",
        "",
        "## Sommaire",
        "",
    ]
    for i, (title, _) in enumerate(chapters, 1):
        parts.append(f"- [[#{i}. {title}]] - a, b, c")
    for i, (title, passages) in enumerate(chapters, 1):
        body = "\n\n".join(passages) if passages else PLACEHOLDER_NO_PASSAGE
        parts += [
            "",
            f"## {i}. {title}",
            "",
            "Desc.",
            "",
            "**Concepts** :",
            "- x",
            "",
            "### Contenu (verbatim)",
            "",
            body,
            "",
        ]
    return "\n".join(parts)


def _paire(tmp_path: Path, passages: list[str], raw: str = _RAW) -> tuple[Path, Path]:
    """Writes (fiche, raw) into tmp and returns their paths - outside the repo, so nothing there is touched."""
    fiche = tmp_path / "fiche.md"
    source = tmp_path / "livre.md"
    fiche.write_text(
        _fiche([("Chapter One", passages[:2]), ("Chapter Two", passages[2:])]), encoding="utf-8"
    )
    source.write_text(raw, encoding="utf-8")
    return fiche, source


def _shell(fiche: Path, book: Path | None = None) -> subprocess.CompletedProcess[str]:
    """The REAL delivered line - Makefile recipe, flag plumbing and exit code included."""
    cmd = ["make", "verbatim-check", f"FICHE={fiche}"]
    if book is not None:
        cmd.append(f"BOOK={book}")
    return subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=300, check=False
    )


def _empreinte(root: Path) -> dict[str, tuple[int, int]]:
    """(size, mtime_ns) of EVERY file in the repo outside caches - a write ANYWHERE turns this red."""
    seen: dict[str, tuple[int, int]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _CACHES]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                st = path.stat()
            except OSError:
                continue  # broken link / race: absence is not a write
            seen[str(path)] = (st.st_size, st.st_mtime_ns)
    return seen


def test_la_ligne_de_shell_livree_PASSE_sur_une_fiche_fidele(tmp_path: Path) -> None:
    """What is delivered is `make verbatim-check`: so it is the shell line that gets run."""
    fiche, book = _paire(tmp_path, _TRUE)
    done = _shell(fiche, book)
    assert done.returncode == 0, done.stderr
    assert "VERDICT: PASSE" in done.stdout
    assert "4/4 passages verbatim (rendement 100%)" in done.stdout
    assert str(fiche) in done.stdout  # the fiche is NAMED - which `make judge` does not do


def test_la_ligne_de_shell_ROUGIT_sur_une_fiche_paraphrasee(tmp_path: Path) -> None:
    """A report informs; a GATE refuses. Without a nonzero exit, nothing stops the fiche from entering.

    The DELIVERED code is `make`'s, not the script's: make returns **2** for any recipe
    failure, so the script's `1` never reaches the caller as-is. We pin down the real contract
    (0 = pass, nonzero = must not enter) rather than the intent - this is the test that fixed
    the Makefile help text, which used to announce "Exit 1".
    """
    fiche, book = _paire(tmp_path, [*_TRUE[:2], _FAUX, _FAUX.replace("many", "several")])
    done = _shell(fiche, book)
    assert done.returncode == 2, done.stdout
    assert "VERDICT: REJECTED" in done.stdout
    assert "paraphrased" in done.stdout


def test_par_make_un_REJET_et_un_REFUS_partagent_le_code_mais_pas_la_sortie(tmp_path: Path) -> None:
    """Make collapses both into 2: the distinction only survives on stdout/stderr, and it must be there.

    The collapse is fail-closed (both say "do not proceed"), so it is acceptable - but a caller who
    wants to know WHY must be able to read it. Without this check, a usage refusal would look like
    a substantive verdict, and we would "fix" a healthy fiche.
    """
    fiche, _ = _paire(tmp_path, _TRUE)
    refus = _shell(fiche)  # BOOK is absent and the fiche does not live under knowledge/distilled/
    assert refus.returncode == 2
    assert "VERDICT:" not in refus.stdout and "REFUS" in refus.stderr


def test_la_porte_NOMME_les_passages_que_le_plancher_jette(tmp_path: Path, capsys) -> None:
    """The calculation exists and `judge_fiche` DROPS it (`kept, _dropped = ...`). Here it is printed."""
    fiche, book = _paire(tmp_path, [*_TRUE[:2], _FAUX, _FAUX.replace("many", "several")])
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 1
    out = capsys.readouterr().out
    assert "2 passage(s) DROPPED" in out
    assert _FAUX in out  # the exact text, not a count: this is what gets fixed
    for tenu in _TRUE[:2]:
        assert tenu not in out  # we do not drown the repair list under what already holds


def test_la_liste_des_jetes_est_PLAFONNEE_et_le_dit(tmp_path: Path, capsys) -> None:
    """A silent cap reads as "that's all": the total count is stated, the rest is announced."""
    faux = [f"Invented sentence number {i} that the source never contains." for i in range(14)]
    fiche, book = _paire(tmp_path, faux)
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 1
    out = capsys.readouterr().out
    assert "14 passage(s) DROPPED" in out
    assert "+4 other(s) not shown" in out


def test_le_rendement_n_est_JAMAIS_arrondi_a_100_quand_un_passage_est_TOMBE(
    tmp_path: Path, capsys
) -> None:
    """The fixture crosses the rounding boundary so a dropped passage cannot display as 100%."""
    vrais = [f"Sentence number {i} states one plain fact about markets." for i in range(200)]
    raw = " ".join([*vrais, "An unrelated closing line."])
    fiche, book = _paire(
        tmp_path, [*vrais, "A sentence the source never contained at all."], raw=raw
    )
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 0  # 200/201 = the judge says ok
    out = capsys.readouterr().out
    assert "200/201 passages verbatim (rendement 99.5%)" in out
    assert "rendement 100%" not in out
    assert "1 passage(s) DROPPED" in out
    assert "TOLERATES" in out  # and we STATE that the verdict tolerates them, instead of crying out for a fix


def test_100_pour_cent_ne_s_imprime_que_si_RIEN_n_est_tombe(tmp_path: Path, capsys) -> None:
    """The counterpart: the rounding floor must not make `100%` unreachable either."""
    fiche, book = _paire(tmp_path, _TRUE)
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 0
    assert "4/4 passages verbatim (rendement 100%)" in capsys.readouterr().out


def test_la_porte_n_ECRIT_RIEN_dans_le_depot(tmp_path: Path, capsys) -> None:
    """"print-only" is proven on the WHOLE tree, not on the one file we suspect.

    `make judge` writes `system/logs/judge_report.md` - that is what makes it unrunnable in a
    read-only session. Closing the CASE ("does not write judge_report.md") would let any other
    file through; we close the CLASS: the entire repo outside caches must stay byte-identical.
    """
    fiche, book = _paire(tmp_path, _TRUE)
    avant = _empreinte(REPO_ROOT)
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 0
    capsys.readouterr()
    apres = _empreinte(REPO_ROOT)
    assert apres == avant, (
        f"the gate wrote: {sorted(set(apres) ^ set(avant))[:5] or 'file(s) modified'}"
    )


def test_le_raw_se_DEDUIT_du_chemin_miroir_et_JAMAIS_par_devinette() -> None:
    """Deriving from `distilled/` is safe; guessing elsewhere would bless a fiche against the wrong book."""
    assert verbatim_check.mirror_raw(Path("knowledge/distilled/Eco/Macro/x.md")) == Path(
        "knowledge/raw/Eco/Macro/x.md"
    )
    assert verbatim_check.mirror_raw(Path("/tmp/brouillon/fiche.md")) is None


def test_refus_EXPLICITE_quand_le_raw_ne_peut_pas_etre_deduit(tmp_path: Path, capsys) -> None:
    fiche, _ = _paire(tmp_path, _TRUE)
    assert verbatim_check.main([str(fiche)]) == 2
    err = capsys.readouterr().err
    assert "REFUS" in err and "BOOK=" in err  # the refusal NAMES the action that unblocks it


def test_refus_quand_le_raw_est_ABSENT_plutot_que_benir_a_l_aveugle(tmp_path: Path, capsys) -> None:
    fiche, book = _paire(tmp_path, _TRUE)
    book.unlink()
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 2
    assert "raw not found" in capsys.readouterr().err


def test_une_fiche_source_unusable_PASSE_car_le_flag_est_legitime(tmp_path: Path, capsys) -> None:
    """`flagged` is not a failure: the source is rotten and the fiche SAYS so. The gate follows the judge."""
    fiche, book = _paire(tmp_path, _TRUE)
    fiche.write_text("---\nstatus: source-unusable\n---\n", encoding="utf-8")
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 0
    out = capsys.readouterr().out
    assert "VERDICT: PASSE" in out
    assert "no passage reached the floor" in out  # and we do not pretend to have measured anything


def test_la_porte_REFUSE_de_benir_si_elle_DIVERGE_du_juge(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """The verdict and the list come from the same home. If they contradict each other, a copy has drifted.

    This is the anti-`contract-single-source-emit` barrier: it can only bite if someone
    rewrites the passage extraction elsewhere - so we put it to the test by simulating exactly that.
    """
    import mnemosyne.production as production

    fiche, book = _paire(tmp_path, _TRUE)
    vrai = production.verbatim_split
    monkeypatch.setattr(
        production,
        "verbatim_split",
        lambda f, r: (vrai(f, r)[0][:-1], vrai(f, r)[1]),  # one kept passage lost
    )
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 2
    assert "DIVERGE" in capsys.readouterr().err


@pytest.mark.parametrize("statut", ["ok", "paraphrased"])
def test_le_verdict_de_la_porte_est_CELUI_du_juge_jamais_un_second_bareme(
    tmp_path: Path, capsys, statut: str
) -> None:
    """Two scoring systems = two truths. The gate must return exactly what `make judge` would return."""
    from mnemosyne.production import judge_fiche

    passages = _TRUE if statut == "ok" else [*_TRUE[:2], _FAUX, _FAUX.replace("many", "several")]
    fiche, book = _paire(tmp_path, passages)
    attendu = judge_fiche(fiche.read_text(encoding="utf-8"), book.read_text(encoding="utf-8"))
    assert attendu.status == statut
    verbatim_check.main([str(fiche), "--raw", str(book)])
    assert f"verdict  : {statut}" in capsys.readouterr().out


_S5_LOCAL = "Volatility must be measured before any capital is ever put at risk."
#: a LONG and NON-REPETITIVE source: a self-similar source makes "the tail shown is not the
#: beginning" undecidable - the first version repeated a sentence, and its own beginning
#: reappeared in its tail.
_RAW_LONG = " ".join(
    f"Clause number {i} states one distinct thing about markets, risk and patience."
    for i in range(40)
)


def _coupe_au_plafond(source: str, cap: int) -> str:
    """The first extract of `source` that hits the cap EXACTLY, LANDING MID-WORD."""
    for start in range(len(source) - cap):
        span = source[start : start + cap]
        if span[-1].isalnum() and source[start + cap].isalnum():
            return span
    raise AssertionError("no mid-word cut found in this source")


def test_la_porte_NOMME_les_passages_TRONQUES_que_le_plancher_ne_voit_pas(tmp_path, capsys) -> None:
    """A passage cut at the schema's cap remains a literal PREFIX: `keep_verbatim` blesses it.

    A cut at the cap can stay literal and pass the floor, while still amputating the fiche.
    The gate SAYS so, with the exact end of each cut: that is what you look up in the source.
    """
    from mnemosyne.production import passage_cap

    coupe = _coupe_au_plafond(_RAW_LONG, passage_cap())
    raw = _RAW_LONG + " " + _RAW
    fiche, book = _paire(tmp_path, [coupe, *_TRUE], raw=raw)
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 0  # truncated is NOT a rejection
    out = capsys.readouterr().out
    assert "1 passage(s) CUT CLEAN at the schema ceiling (maxLength=500)" in out
    assert coupe[-60:] in out  # the exact END - the CUT, not the start of the passage
    assert coupe[:40] not in out  # showing the start of a truncated passage serves no purpose


def test_un_DOUBLON_est_une_MESURE_et_non_une_fausse_accusation(tmp_path, capsys) -> None:
    """`keep_verbatim` SILENTLY DEDUPLICATES.

    The divergence barrier must not assume every claimed passage is distinct.
    A fixture with a duplicate proves this distinction; only a NEGATIVE gap remains impossible.
    """
    # 5 distinct + 1 duplicate: the duplicate counts in the DENOMINATOR without counting in the
    # numerator (5/6 = 83%), so there must be enough passages to stay above the 80% threshold.
    fiche, book = _paire(tmp_path, [*_TRUE, _S5_LOCAL, _TRUE[0]])
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 0
    sortie = capsys.readouterr()
    assert "DIVERGE" not in sortie.err
    assert "1 passage(s) claimed in DUPLICATE" in sortie.out


# ---- the hole an isolated audit found, and the guards no test covered -----------------------------


def test_pointer_BOOK_sur_la_FICHE_ELLE_MEME_est_REFUSE(tmp_path: Path, capsys) -> None:
    """The flaw: `BOOK=` is chosen by THE ONE BEING JUDGED.

    A fiche whose citations are entirely invented can otherwise appear valid to a coarse check.
    `4/4  -  rendement 100%  -  VERDICT: PASSE` by pointing `BOOK` at itself. This was the worst case of
    the threat model, produced by one extra word on the command line, and no test covered it.
    """
    fiche, book = _paire(tmp_path, ["Entirely invented citation number one." for _ in range(4)])
    assert (
        verbatim_check.main([str(fiche), "--raw", str(book)]) == 1
    )  # against the REAL book: rejected
    capsys.readouterr()
    assert verbatim_check.main([str(fiche), "--raw", str(fiche)]) == 2  # against itself: REFUSED
    assert "IS the fiche itself" in capsys.readouterr().err


def test_pointer_BOOK_sur_UNE_AUTRE_FICHE_est_REFUSE_AUSSI(tmp_path: Path, capsys) -> None:
    """We close the CLASS, not the case: any fiche used as the source makes verbatim tautological.

    Self-reference is only one instance. A NEIGHBORING fiche containing the same citations would pass
    just as well - and a `resolve() ==` alone would not catch it.
    """
    fiche, _ = _paire(tmp_path, _TRUE)
    autre = tmp_path / "autre_fiche.md"
    autre.write_text(fiche.read_text(encoding="utf-8"), encoding="utf-8")
    assert verbatim_check.main([str(fiche), "--raw", str(autre)]) == 2
    assert "is a DISTILLED FICHE" in capsys.readouterr().err


def test_le_refus_FICHE_INTROUVABLE_est_eprouve(tmp_path: Path, capsys) -> None:
    """Removing this guard survived the whole suite: the `REFUS` message was proven by nothing."""
    assert verbatim_check.main([str(tmp_path / "absente.md"), "--raw", str(tmp_path)]) == 2
    assert "fiche not found" in capsys.readouterr().err


def test_l_entete_des_TRONQUES_et_sa_LISTE_sortent_du_MEME_decompte(tmp_path: Path, capsys) -> None:
    """Header and detail list derive from the same de-duplicated count."""
    from mnemosyne.production import passage_cap

    coupe = _coupe_au_plafond(_RAW_LONG, passage_cap())
    raw = _RAW_LONG + " " + _RAW
    fiche, book = _paire(tmp_path, [coupe, coupe, *_TRUE], raw=raw)  # the TRUNCATED one is DUPLICATED
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 0
    out = capsys.readouterr().out
    entete = next(ligne for ligne in out.splitlines() if "CUT CLEAN" in ligne)
    annonce = int(entete.split()[0])
    montres = sum(1 for line in out.splitlines() if line.strip().startswith("[") and "..." in line)
    assert annonce == montres, f"the header announces {annonce}, the list shows {montres}"


def test_la_ligne_de_shell_LIVREE_n_ecrit_rien_non_plus(tmp_path: Path) -> None:
    """The "writes nothing" check used to call the FUNCTION; what is delivered is the `make` recipe.

    A write added to the Makefile recipe used to pass green - measured by an isolated audit, which
    made the recipe write into a ghost copy and watched all 17 tests stay green.
    """
    fiche, book = _paire(tmp_path, _TRUE)
    avant = _empreinte(REPO_ROOT)
    done = _shell(fiche, book)
    assert done.returncode == 0, done.stderr
    apres = _empreinte(REPO_ROOT)
    assert apres == avant, f"the RECIPE wrote: {sorted(set(apres) ^ set(avant))[:5]}"


# --------------------------------------------------------------------------------------------- #
# What a 4th isolated audit opened up (2026-07-28) - two exploits that worked WITHOUT any mutation
# --------------------------------------------------------------------------------------------- #


def _etagere(tmp_path: Path, passages: list[str], raw: str = _RAW) -> tuple[Path, Path]:
    """A fiche that REALLY lives under `knowledge/distilled/`, with its mirror under `knowledge/raw/`.

    This file's fixtures write outside the shelf; that is precisely the population where the mirror
    rule does NOT apply. Without this shape, the guarantee would have no test - the audit showed
    that a fixture whose structure does not match the real thing proves nothing.
    """
    rel = Path("domain") / "book.md"
    fiche = tmp_path / "knowledge" / "distilled" / rel
    source = tmp_path / "knowledge" / "raw" / rel
    fiche.parent.mkdir(parents=True, exist_ok=True)
    source.parent.mkdir(parents=True, exist_ok=True)
    fiche.write_text(
        _fiche([("Chapter One", passages[:2]), ("Chapter Two", passages[2:])]), encoding="utf-8"
    )
    source.write_text(raw, encoding="utf-8")
    return fiche, source


def test_une_fiche_de_l_etagere_ne_se_juge_QUE_contre_SON_MIROIR(
    tmp_path, monkeypatch, capsys
) -> None:
    """The reference is DERIVED from the path, it is never DESIGNATED - otherwise it is the one being
    judged who chooses.

    The exploit produced by the audit: `grep -v '^distilled_by:' fiche.md > faux_livre.md`, then BOOK=
    pointed at it. ONE LINE removed from a file the attacker owns, and a fiche with entirely invented
    citations came back `963/963  -  rendement 100%  -  VERDICT: PASSE`. The guard at the time was a
    CONTENT marker: a blacklist, never a closure of the class.
    """
    monkeypatch.chdir(tmp_path)
    fiche, miroir = _etagere(tmp_path, _TRUE)
    faux = tmp_path / "faux_livre.md"
    # the EXACT attack: the fiche copied, minus the one line the old guard looked at
    faux.write_text(
        "\n".join(
            x
            for x in fiche.read_text(encoding="utf-8").splitlines()
            if not x.startswith("distilled_by:")
        ),
        encoding="utf-8",
    )
    assert "distilled_by:" not in faux.read_text(
        encoding="utf-8"
    )  # the old guard really is blind

    assert verbatim_check.main([str(fiche), "--raw", str(faux)]) == 2
    out = capsys.readouterr()
    assert "VERDICT: REFUSE" in out.out
    assert "PASSE" not in out.out  # the documented contract is "read the VERDICT: line"
    assert "mirror" in out.err

    # and the mirror, for its part, passes - the rule CLOSES without breaking the nominal case
    assert verbatim_check.main([str(fiche), "--raw", str(miroir)]) == 0
    assert "DERIVED from the mirror" in capsys.readouterr().out


def test_AUCUN_refus_ne_peut_imprimer_PASSE_sur_stdout(tmp_path, monkeypatch, capsys) -> None:
    """An audit showed that moving one three-line guard made stdout carry `yield 100%` AND
    `VERDICT: PASSE` while stderr carried the REFUSAL. A producer following the documented
    procedure ("read the VERDICT: line") therefore read PASSE on a record that had been refused.
    The fix is not to put the guard back where it was - it is that ONE SINGLE place prints
    `VERDICT:`, so no rearrangement can ever make two of them disagree again."""
    monkeypatch.chdir(tmp_path)
    fiche, miroir = _etagere(tmp_path, _TRUE)
    autre = tmp_path / "autre.md"
    autre.write_text(_fiche([("X", _TRUE)]), encoding="utf-8")

    for source in (fiche, autre, tmp_path / "absent.md", miroir.parent / "pas_le_miroir.md"):
        (miroir.parent / "pas_le_miroir.md").write_text(_RAW, encoding="utf-8")
        code = verbatim_check.main([str(fiche), "--raw", str(source)])
        out = capsys.readouterr().out
        assert code == 2, f"{source.name} should have been REFUSED"
        assert "PASSE" not in out, f"{source.name}: stdout carries PASSED on a REFUSAL -\n{out}"


def test_un_paragraphe_INVENTE_prefixe_par_un_underscore_est_JUGE_et_non_saute(
    tmp_path, capsys
) -> None:
    """`_chapters` used to skip EVERY paragraph starting with `_(`. But `_(...)_` renders as VISIBLE
    ITALICS in the rendered fiche: a producer could lodge fabricated citations there that the floor
    never saw. Reproduced before the fix: `6/6 passages verbatim (rendement 100%)  -  PASSE` on
    a fiche carrying three entirely invented citations under `### Contenu (verbatim)`."""
    invente = "_(The market will crash in March 2027, the author formally predicts it.)_"
    fiche, book = _paire(tmp_path, [*_TRUE, invente])
    assert invente in fiche.read_text(encoding="utf-8")  # the text really IS in the fiche

    code = verbatim_check.main([str(fiche), "--raw", str(book)])
    out = capsys.readouterr().out
    assert "4/5 passages verbatim (rendement 80%)" in out, (
        f"the invention was not counted -\n{out}"
    )
    assert invente[:40] in out, f"the invention is not NAMED in the dropped list -\n{out}"
    # WARNING: the exit code stays 0: at 4/5 the judge still says `ok`. Its THRESHOLD is a SEPARATE axis from
    # this fix - what changes here is that before, the invention was INVISIBLE (`4/4  -  100%`), and it is
    # now counted, named, and removed from the yield. A threshold that tolerates 20% fabrication is
    # a separate question, and sneaking it into this test would hide it.
    assert code == 0


def test_le_PLACEHOLDER_legitime_reste_saute_lui(tmp_path, capsys) -> None:
    """The counterpart: closing the class must not turn our own scaffolding into an accusation.
    `_(no verbatim passage kept)_` is written by the distillateur when a chapter is empty."""
    fiche, book = _paire(
        tmp_path, _TRUE
    )  # `_paire` puts the placeholder in chapter 2 if it is empty
    vide = tmp_path / "vide.md"
    vide.write_text(_fiche([("Chapter One", _TRUE), ("Chapter Two", [])]), encoding="utf-8")
    assert PLACEHOLDER_NO_PASSAGE in vide.read_text(encoding="utf-8")
    assert verbatim_check.main([str(vide), "--raw", str(book)]) == 0
    assert "4/4 passages verbatim (rendement 100%)" in capsys.readouterr().out


def test_un_commentaire_HTML_qui_n_est_PAS_le_notre_est_JUGE(tmp_path, capsys) -> None:
    """A symmetric error, alive too: `startswith("<!--")` used to exempt
    `<!-- formula-not-decoded -->` - a marker that comes from OCR SOURCES, hence genuinely quoted
    text. On the real shelf, 48 paragraphs escaped judgement this way, 39 of which are NOT
    in their source. Only OUR namespace (`<!-- mnemosyne:`) is scaffolding."""
    from mnemosyne.production.chapter_parsing import is_structural_marker

    assert is_structural_marker("<!-- mnemosyne:source-unusable letters=0.2 -->")
    assert is_structural_marker(PLACEHOLDER_NO_PASSAGE)
    assert not is_structural_marker("<!-- formula-not-decoded -->")
    assert not is_structural_marker("_(a fabricated citation)_")

    # The internal `strip()` CARRIES the guarantee, it is not decorative: `_chapters` already strips,
    # so a mutation that removes it left the suite GREEN (found by mutation testing, YYYY-MM-DD). Without a
    # test, this would be dead defensive code that READS like a guarantee - and the day a caller passes a
    # non-normalized paragraph, our own scaffolding gets ACCUSED of being an invention.
    assert is_structural_marker(f"\n  {PLACEHOLDER_NO_PASSAGE}  \n")
    assert is_structural_marker("  <!-- mnemosyne:distill-failed chunk=3 -->\n")
    assert not is_structural_marker("  _(a fabricated citation)_  ")

    fiche, book = _paire(tmp_path, [*_TRUE, "<!-- formula-not-decoded -->"])
    assert verbatim_check.main([str(fiche), "--raw", str(book)]) == 0
    assert "4/5 passages verbatim (rendement 80%)" in capsys.readouterr().out  # judged, no longer exempt


def test_la_marque_de_FICHE_est_cherchee_dans_TOUT_le_fichier_pas_dans_une_fenetre(
    tmp_path, capsys
) -> None:
    """The marker is searched across the whole file rather than a fixed-size header window."""
    fiche, _ = _paire(tmp_path, _TRUE)
    profond = tmp_path / "fiche_au_marqueur_profond.md"
    # the marker DELIBERATELY beyond any plausible window: 20,000 characters of prose before it
    profond.write_text(
        "Some filler text here. " * 800 + '\ndistilled_by: "agent"\n', encoding="utf-8"
    )
    assert profond.read_text(encoding="utf-8").index("distilled_by:") > 15_000

    assert verbatim_check.main([str(fiche), "--raw", str(profond)]) == 2
    out = capsys.readouterr()
    assert "DISTILLED FICHE" in out.err
    assert "VERDICT: REFUSE" in out.out and "PASSE" not in out.out

    # and the marker mid-SENTENCE (not at the start of a line) does NOT accuse a book that quotes it
    cite = tmp_path / "livre_qui_cite.md"
    cite.write_text(_RAW + " The distilled_by: field is used to trace production.", encoding="utf-8")
    assert verbatim_check.main([str(fiche), "--raw", str(cite)]) == 0
