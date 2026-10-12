"""The juge - verifies a fiche WITHOUT trusting the model that produced it.

The properties that matter: the juge catches the important failure modes - an empty template
(every chapter titled `(section)`, zero verbatim), a P3 paraphrase, AND a STUB (a whole book reduced to
its cover page: little verbatim or mostly-empty chapters). It replays the passages through the
`keep_verbatim` floor: the guarantee is in the code, not trust. `ok` = P3 faithful AND covered. Brick-free."""

from __future__ import annotations

import pytest

import importlib.util
from pathlib import Path

from _invariants import REPO_ROOT
from mnemosyne.production import VERBATIM_BEGIN, VERBATIM_END, JudgeStatus, judge_fiche
from mnemosyne.production.chapter_parsing import PLACEHOLDER_NO_PASSAGE

# run_judge (the juge skill's orchestrator) is loaded from its real file, like the other skill tests;
# judge_fiche (tested further below) is the PURE verdict for a fiche, run_judge walks raw/ vs distilled/.
_JUDGE = REPO_ROOT / "system" / "skills" / "juge" / "judge_library.py"
_spec = importlib.util.spec_from_file_location("judge_library_script", _JUDGE)
judge_library = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(judge_library)

_RAW = (
    "Risk management is the core of quantitative finance. "
    "A prudent investor diversifies across uncorrelated assets. "
    "Position sizing ensures a single loss never threatens the whole portfolio. "
    "The margin of safety is the distance between price and intrinsic value. "
    "Volatility must be measured before any capital is ever put at risk."
)
_S1 = "Risk management is the core of quantitative finance."  # each is a literal substring of _RAW
_S2 = "A prudent investor diversifies across uncorrelated assets."
_S3 = "Position sizing ensures a single loss never threatens the whole portfolio."
_S4 = "The margin of safety is the distance between price and intrinsic value."
_S5 = "Volatility must be measured before any capital is ever put at risk."
_PARA = [  # five paraphrases - none is a literal substring of _RAW
    "Investors ought to spread their bets across many holdings",
    "Keep a cushion between what you pay and what a thing is worth",
    "Watch volatility so no single position can sink you",
    "Never wager the entire account on one idea",
    "Over the long run, value tends to win out over price",
]


def _fiche(chapters: list[tuple[str, list[str]]]) -> str:
    parts = ["---", 'title: "T"', 'type: "book"', "---", "", "# T", "", "## Sommaire", ""]
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


def _fiche_desc(chapters: list[tuple[str, str, list[str]]]) -> str:
    """Like ``_fiche`` but with a per-chapter P2 DESCRIPTION - to exercise the templating axis."""
    parts = ["---", 'title: "T"', 'type: "book"', "---", "", "# T", "", "## Sommaire", ""]
    for i, (title, _d, _p) in enumerate(chapters, 1):
        parts.append(f"- [[#{i}. {title}]] - a, b, c")
    for i, (title, desc, passages) in enumerate(chapters, 1):
        body = "\n\n".join(passages) if passages else PLACEHOLDER_NO_PASSAGE
        parts += [
            "",
            f"## {i}. {title}",
            "",
            desc,
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


def test_judge_ok_on_faithful_covered_fiche() -> None:
    v = judge_fiche(_fiche([("C1", [_S1, _S2]), ("C2", [_S3, _S4]), ("C3", [_S5])]), _RAW)
    assert v.status == JudgeStatus.OK and v.n_verbatim == 5 and v.ok


def test_judge_reports_templated_p2_as_separate_axis_not_a_fidelity_failure() -> None:
    # P2 template = a SEPARATE signal: the fiche stays OK on P3 FIDELITY, but n_templated marks the non-synthesis.
    fiche = _fiche_desc(
        [
            # The fixtures below stay in FRENCH on purpose: the judge grades records distilled
            # from a French-language corpus, and the templated-description detector it relies on
            # matches French boilerplate. Translate these and the test measures nothing.
            ("C1", "L'auteur traite ici de « C1 » et aborde également a, b et c.", [_S1, _S2]),
            ("C2", "L'auteur traite ici de « C2 » et aborde également d, e et f.", [_S3, _S4]),
            (
                "C3",
                "Cette section montre pourquoi la volatilité doit être mesurée avant tout risque.",
                [_S5],
            ),
        ]
    )
    v = judge_fiche(fiche, _RAW)
    assert v.status == JudgeStatus.OK and v.ok  # P3 faithful -> the juge does NOT fail on P2
    assert v.n_templated == 2  # the 2 templates spotted, the real synthesis is not (separate axis)


def test_judge_hollow_on_placeholder_shell() -> None:
    # THE first Codex failure: every chapter titled "(section)", no real content.
    v = judge_fiche(_fiche([("(section)", []), ("(section)", [])]), _RAW)
    assert v.status == JudgeStatus.HOLLOW and not v.ok


def test_judge_hollow_when_no_passages_claimed() -> None:
    assert judge_fiche(_fiche([("Real Chapter", [])]), _RAW).status == JudgeStatus.HOLLOW


def test_judge_thin_on_stub_few_verbatim() -> None:
    # the live audit false-OK: a whole book reduced to its cover page - 2 verbatim, faithful but a STUB.
    v = judge_fiche(_fiche([("Published by", [_S1, _S2])]), _RAW)
    assert v.status == JudgeStatus.THIN and not v.ok


def test_judge_thin_on_mostly_empty_chapters() -> None:
    # enough verbatim, but most chapters carry nothing (the failed-chunk case) -> under-covered.
    fiche = _fiche([("C1", [_S1, _S2, _S3]), ("C2", []), ("C3", []), ("C4", []), ("C5", [])])
    assert judge_fiche(fiche, _RAW).status == JudgeStatus.THIN


def test_judge_paraphrased_when_passages_are_not_verbatim() -> None:
    # claims five passages, but NONE survives the floor -> the model paraphrased P3 (not the source's words).
    assert judge_fiche(_fiche([("Ch", _PARA)]), _RAW).status == JudgeStatus.PARAPHRASED


def test_judge_malformed_on_escaped_newlines() -> None:
    # the escaped-\n serialization bug: literal backslash-n, no real newlines -> invalid fiche markdown.
    assert (
        judge_fiche('---\\ntitle: "x"\\n---\\n\\n## 1. a\\n' * 3, _RAW).status
        == JudgeStatus.MALFORMED
    )


def test_judge_flagged_on_source_unusable() -> None:
    v = judge_fiche(
        "---\nstatus: source-unusable\n---\n\n# x\n<!-- mnemosyne:source-unusable -->\n", _RAW
    )
    assert v.status == JudgeStatus.FLAGGED and v.ok  # a legitimate flag is not a failure


def test_judge_raw_missing_when_no_source() -> None:
    assert judge_fiche(_fiche([("Ch", [_S1, _S2, _S3])]), None).status == JudgeStatus.RAW_MISSING


def test_judge_flags_an_ambiguous_false_heading_fiche() -> None:
    # shared blind spot closed: a "## 2." inside a passage (chapters:1 disagrees with 2 headings) makes the
    # chapter parsing ambiguous -> the juge FLAGS it (malformed) instead of silently mis-counting verbatim.
    trap = (
        '---\ntitle: "T"\nchapters: 1\n---\n\n# T\n\n## 1. Ch\n\nDesc.\n\n**Concepts** :\n- x\n\n'
        "### Contenu (verbatim)\n\nA line.\n\n## 2. A heading really inside a quote\n\nmore.\n"
    )
    assert judge_fiche(trap, _RAW).status == JudgeStatus.MALFORMED


def test_judge_ok_on_a_fenced_fiche_whose_passage_quotes_a_heading() -> None:
    # THE structural fix: a passage legitimately quotes "## 2." from the OCR source. Inside a verbatim
    # fence it is NOT a chapter boundary -> the fiche is well-formed (1 chapter) and judged on its real
    # verbatim, NOT flagged malformed as its unfenced twin above is.
    quoted_line = "## 2. A heading quoted verbatim from the OCR source."
    raw = _RAW + " " + quoted_line  # the quote is a genuine literal substring of the source
    body = _S1 + "\n\n" + quoted_line + "\n\n" + _S2
    fiche = (
        '---\ntitle: "T"\ntype: "book"\nchapters: 1\n---\n\n# T\n\n## Sommaire\n- [[#1. Ch]] - a\n\n'
        "## 1. Ch\n\nDesc.\n\n**Concepts** :\n- x\n\n### Contenu (verbatim)\n\n"
        + VERBATIM_BEGIN
        + "\n\n"
        + body
        + "\n\n"
        + VERBATIM_END
        + "\n"
    )
    v = judge_fiche(fiche, raw)
    assert (
        v.status == JudgeStatus.OK and v.n_chapters == 1
    )  # one real chapter, the quoted "## 2." masked
    assert (
        v.n_verbatim == 3
    )  # S1, the quoted heading line, S2 -- each a literal substring of raw, all kept


def test_run_judge_never_claims_veille_tooling_as_missing(tmp_path: Path) -> None:
    # A raw book with no distilled mirror is normally "missing" (a source still to distil). But a veille
    # fiche - taxonomy group "Tooling" - is ALREADY a self-contained synthesis, not a raw source, so
    # run_judge must NOT claim it missing (it stays RAG-indexed via discover_books). A README* is skipped too.
    raw, distilled = tmp_path / "raw", tmp_path / "distilled"
    real = raw / "Finance" / "Investing" / "value-investing" / "books"
    veille = raw / "Software" / "Tooling" / "agents" / "books"
    real.mkdir(parents=True)
    veille.mkdir(parents=True)
    (real / "real book.md").write_text("# a real book", encoding="utf-8")
    (veille / "langchain.md").write_text("# langchain, a veille fiche", encoding="utf-8")
    (veille / "README.md").write_text("# shelf docs", encoding="utf-8")
    distilled.mkdir()

    statuses = {rel: status for status, rel, _ in judge_library.run_judge(raw, distilled)}

    # only the real book is missing; the veille fiche (Tooling) and the README never surface
    assert statuses == {"Finance/Investing/value-investing/books/real book.md": "missing"}


# --------------------------------------------------------------------------------------------------
# P3 TRUNCATED - the only STRUCTURAL blind spot of the verbatim floor (measured 2026-07-28)
# 77,155 passages on the shelf: 4,276 are EXACTLY 500 characters long (~9x the neighbouring density)
# and 96 % end on no punctuation at all, against 5 % on a control of 51,344 passages of 300-480.
# A passage truncated at the schema limit can remain a literal prefix: keep_verbatim accepts it,
# while the loss is otherwise silent.
# --------------------------------------------------------------------------------------------------

from mnemosyne.production import passage_cap, truncated_passages  # noqa: E402


#: a LONG and NON-REPETITIVE source: a self-similar source makes "the tail shown is not the
#: beginning" undecidable - the first version repeated a sentence, and its own beginning
#: reappeared in its tail.
_PLACEHOLDER = "(section)"  # distill_book's fallback title -> a HOLLOW fiche
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


def test_un_passage_AU_PLAFOND_coupe_en_plein_mot_est_signale() -> None:
    cap = passage_cap()
    coupe = _coupe_au_plafond(_RAW_LONG, cap)
    assert len(coupe) == cap and coupe[-1].isalnum()  # cut CLEAN, mid-word
    assert truncated_passages((coupe,)) == (coupe,)


def test_un_passage_au_plafond_qui_FINIT_PROPREMENT_n_est_PAS_accuse() -> None:
    """The false-positive control: without it, a capture rate is only a wall."""
    cap = passage_cap()
    propre = ("mot " * 200)[: cap - 1] + "."
    assert len(propre) == cap
    assert truncated_passages((propre,)) == ()


def test_un_passage_COURT_coupe_en_plein_mot_n_est_PAS_accuse() -> None:
    """It's the CONJUNCTION that is the signal: outside the cap, an ending with no period is ordinary.

    5% of the control's passages end this way - accusing all of them would produce 2,729 false accusations.
    """
    assert truncated_passages(("un passage court sans ponctuation finale",)) == ()


def test_le_plafond_de_LONGUEUR_a_ete_RETIRE_du_schema_que_lisent_les_agents() -> None:
    """[judge] REPEALS `test_le_plafond_est_LU_dans_le_schema_et_non_RECOPIE` (YYYY-MM-DD).

    **What the old test defended, and what still holds**: a RECOPIED number survives the schema, and the
    detector would then silently start accusing the wrong length. This requirement is not deleted -
    its DOMAIN is REDUCED, because the thing it guarded no longer exists.

    **What changed**: the length cap on a passage was REMOVED. The measurement that decided it - a
    cap on a GENERATED output does not bound, it STEERS: never reached, and yet median 292 vs
    500 against 477 vs 1200, with a short/long gap that goes from 3.5x to 11x once removed. There is
    therefore no more "cap read from the schema" to read: it no longer exists.

    **What replaces it, and what this test pins down**:
      1. the schema that ALL agents read no longer carries any maximum passage length;
      2. the only surviving maximum is the DECODER GUARDRAIL, in its own schema, because it
         names a concrete failure (a grammar-constrained decoder that cannot stop emits until invalid
         JSON) - that is the test a cap must pass to exist;
      3. `PLAFOND_HISTORIQUE` is FROZEN BY HAND, dated, and is no longer a rule: it is what lets us
         recognize the 6,087 amputations already on the shelf without blaming today's producer for them.
    """
    import json

    from mnemosyne.production import juge as juge_mod
    from mnemosyne.production.distillation import (
        DISTILL_SCHEMA,
        GRAMMAR_PASSAGE_MAX,
        GRAMMAR_SCHEMA,
    )

    passages_vus_par_les_agents = json.loads(DISTILL_SCHEMA)["properties"]["passages"]
    assert "maxLength" not in passages_vus_par_les_agents["items"], (
        "the LENGTH cap is back in the schema the agents read - it STEERS the output"
    )
    assert passages_vus_par_les_agents["maxItems"] == 10, "SELECTIVITY, however, stays bounded"

    passages_du_decodeur = json.loads(GRAMMAR_SCHEMA)["properties"]["passages"]
    assert passages_du_decodeur["items"]["maxLength"] == GRAMMAR_PASSAGE_MAX
    assert GRAMMAR_PASSAGE_MAX > 1433, (
        "the decoder guardrail must stay FAR above the longest passage ever measured without "
        "a cap (1433), or it becomes a steering wheel instead of a safety net"
    )

    assert juge_mod.PLAFOND_HISTORIQUE == 500  # FROZEN BY HAND: never derived from what it checks
    assert juge_mod.passage_cap() == 500
    assert juge_mod.truncated_passages(("a" * 500,)) == ("a" * 500,)


def test_la_troncature_ne_change_JAMAIS_le_verdict() -> None:
    """Like the P2 template axis: it SURFACES a loss, it never degrades a faithful fiche.

    A truncated passage IS the source's own words - just not all of them. Degrading it to `paraphrased`
    would accuse the producer of a fault it did not commit: it is the schema that cut it.
    """
    cap = passage_cap()
    coupe = _coupe_au_plafond(_RAW_LONG, cap)
    raw = _RAW_LONG + " " + _RAW
    assert len(coupe) == cap
    verdict = judge_fiche(_fiche([("A", [coupe, _S2, _S3]), ("B", [_S4, _S5])]), raw)
    assert verdict.status == JudgeStatus.OK
    assert verdict.n_truncated == 1


# ---- what three isolated audits found NOT PROVEN (YYYY-MM-DD) --------------------------------------


def test_la_troncature_se_mesure_BLANCS_DE_QUEUE_COMPRIS() -> None:
    """The cut lands at N characters *whitespace included*: a `.strip()` upstream makes it INVISIBLE.

    Measured: **1,967 truncations out of 6,087 (32%)** were missed because `_chapters` cleaned
    the paragraph before the detector measured its length. The detector nonetheless knew the
    tail carried whitespace - it writes `p.rstrip()` to test the punctuation.
    """
    cap = passage_cap()
    coupe = _coupe_au_plafond(_RAW_LONG, cap - 2) + " \t"  # 500 total, tail whitespace included
    assert len(coupe) == cap and coupe.rstrip()[-1].isalnum()
    # The defect lives in `_chapters` (it cleaned up BEFORE the length was measured), not in the
    # detector: calling `truncated_passages` directly does NOT prove it. So we go through the juge,
    # i.e. through the path a real fiche actually takes.
    raw = _RAW_LONG + " " + _RAW
    assert judge_fiche(_fiche([("A", [coupe, _S2]), ("B", [_S3, _S4])]), raw).n_truncated == 1
    assert truncated_passages((coupe,)) == (coupe,)  # and the detector alone, once properly fed


def test_un_passage_AU_DESSUS_du_plafond_n_est_PAS_accuse() -> None:
    """`==`, not `>=`: above the cap, the cut did NOT happen (22 real passages exceed it).

    This direction used to be caught by the neighboring test (the one about the cap read from the
    schema), via an incidental assertion - so the conjunction these tests NAME was only half proven.
    """
    cap = passage_cap()
    long = _coupe_au_plafond(_RAW_LONG, cap) + " and the rest continues well beyond the cap"
    assert len(long) > cap
    assert truncated_passages((long,)) == ()


def test_le_jeu_des_FINALES_est_GELE_a_la_main() -> None:
    """A name is not a test: adding `s` to `_FINALES` would silently erase 181 accusations.

    The reference is written HERE, character by character. Deriving it from the frozenset would make it
    blind to any drift in the frozenset - the tautology already paid for twice today.
    """
    from mnemosyne.production.juge import _FINALES

    assert _FINALES == frozenset('.!?"»)…:;')


@pytest.mark.parametrize("statut", ["hollow", "thin", "paraphrased"])
def test_la_troncature_SURVIT_sur_chaque_branche_de_verdict(statut: str) -> None:
    """Zeroing out `n_truncated` on 4 of the 5 branches survived the whole suite.

    What was protecting this was not a test but an EMPTY POPULATION: the shelf today is `ok`
    everywhere. The day a fiche comes back THIN or PARAPHRASED - the juge's very use case - its loss
    would go silent again.
    """
    cap = passage_cap()
    coupe = _coupe_au_plafond(_RAW_LONG, cap)
    raw = _RAW_LONG + " " + _RAW
    if statut == "hollow":
        fiche = _fiche([(_PLACEHOLDER, [coupe]), (_PLACEHOLDER, [_S2])])
    elif statut == "thin":
        fiche = _fiche([("A", [coupe]), ("B", []), ("C", []), ("D", [])])
    else:
        fiche = _fiche([("A", [coupe, *_PARA[:3]]), ("B", _PARA[3:])])
    verdict = judge_fiche(fiche, raw)
    assert verdict.status == statut
    assert verdict.n_truncated == 1, "the loss goes silent again as soon as the fiche is no longer `ok`"


def test_la_troncature_SURVIT_meme_sans_raw_miroir() -> None:
    """A truncation reads off the passage ITSELF: the absence of a source does not erase it."""
    coupe = _coupe_au_plafond(_RAW_LONG, passage_cap())
    verdict = judge_fiche(_fiche([("A", [coupe, _S2]), ("B", [_S3])]), None)
    assert verdict.status == JudgeStatus.RAW_MISSING
    assert verdict.n_truncated == 1


def test_la_ligne_P3_TRONQUE_de_make_judge_dit_le_MEME_nombre_a_l_ecran_et_dans_le_rapport(
    tmp_path, monkeypatch, capsys
) -> None:
    """`grep -rn "P3 tronque" tests/` returned NOTHING: the line that would justify a re-distillation
    was held by no test. Three mutations survived there - including one that prints DOUBLE in
    the machine report while the screen body tells the truth (the summary lies, the body tells the truth).
    """
    from mnemosyne.production.juge import FicheVerdict

    rows = [
        ("ok", "a.md", FicheVerdict("ok", 3, 30, 30, "r", n_templated=0, n_truncated=7)),
        ("ok", "b.md", FicheVerdict("ok", 2, 20, 20, "r", n_templated=0, n_truncated=5)),
        ("ok", "c.md", FicheVerdict("ok", 2, 20, 20, "r", n_templated=0, n_truncated=0)),
    ]
    monkeypatch.setattr(judge_library, "run_judge", lambda *a, **k: rows)
    monkeypatch.setattr(judge_library, "_REPORT", tmp_path / "rapport.md")
    monkeypatch.setattr(judge_library, "_RAW", tmp_path / "raw")
    monkeypatch.setattr(judge_library, "_DISTILLED", tmp_path / "distilled")
    (tmp_path / "raw").mkdir()
    (tmp_path / "distilled").mkdir()
    assert judge_library.main([]) == 0
    ecran = capsys.readouterr().out
    rapport = (tmp_path / "rapport.md").read_text(encoding="utf-8")
    assert "P3 truncated  : 12 passage(s)" in ecran and "in 2 fiche(s)" in ecran
    # the REPORT and the SCREEN cross-check each other: editing one without the other must go red
    assert "12 passage(s) in 2 fiche(s)" in rapport


def test_le_compte_de_troncatures_n_est_PAS_pilotable_par_un_BLANC_de_queue() -> None:
    """A published number must not depend on a character that the THING BEING MEASURED chooses to add.

    Found by an isolated audit (YYYY-MM-DD): with the strict equality `len(p) == cap`, adding **one
    trailing space** to each passage of a real fiche pushed the length to 501 and the count
    dropped from **182 to 1** - with no other number moving, since `keep_verbatim` normalizes
    whitespace. Reproduced by hand on `Irrational Exuberance` before the fix; after: 182 -> 182.
    """
    cap = passage_cap()
    coupe = _coupe_au_plafond(_RAW_LONG, cap)
    assert truncated_passages((coupe,)) == (coupe,)

    for bourrage in (" ", "  ", "\t", " \n", "   \t "):
        padded = coupe + bourrage
        assert len(padded) > cap  # the strict equality would now be blind
        assert truncated_passages((padded,)) == (padded,), (
            f"padding {bourrage!r} erased the accusation"
        )

    # and the INVERSE direction still holds: above the cap, the cut did not happen
    vraiment_long = coupe + " and the rest continues well beyond the cap"
    assert len(vraiment_long.rstrip()) > cap
    assert truncated_passages((vraiment_long,)) == ()


# --- the completeness FLOOR - it replaces the removed cap, and it BITES ------------------------------


def test_le_plancher_accuse_une_coupe_EN_PLEIN_MOT_lue_dans_la_source() -> None:
    """Completeness is READ from the source: we look at the character that FOLLOWS the passage."""
    from mnemosyne.production.juge import cut_mid_word

    raw = "The margin of safety is the distance between price and intrinsic value."
    entier = "The margin of safety is the distance between price and intrinsic value."
    coupe = "The margin of safety is the distance between price and intrin"  # cut inside "intrinsic"
    propre = "The margin of safety is the distance between price and"  # stops on a word boundary

    assert cut_mid_word((entier,), raw) == ()
    assert cut_mid_word((coupe,), raw) == (coupe,)
    assert cut_mid_word((propre,), raw) == ()  # incomplete, yes - but no WORD is cut
    assert (
        cut_mid_word(("a passage absent from the source",), raw) == ()
    )  # the VERBATIM floor's business


def test_le_plancher_EXCLUT_les_amputations_de_l_ANCIEN_plafond() -> None:
    """Legacy truncation must be excluded before evaluating the mid-word completeness floor."""
    from mnemosyne.production.juge import cut_mid_word, passage_cap, truncated_passages

    cap = passage_cap()
    raw = _RAW_LONG
    ampute = _coupe_au_plafond(raw, cap)
    assert truncated_passages((ampute,)) == (ampute,), (
        "the fixture must REALLY be an amputation"
    )
    assert cut_mid_word((ampute,), raw) == (ampute,), "and it really does cut mid-word"

    # the juge, for its part, must spare it: it is the subtraction that carries the guarantee
    amputes = set(map(id, truncated_passages((ampute,))))
    restants = tuple(p for p in (ampute,) if id(p) not in amputes)
    assert cut_mid_word(restants, raw) == ()


def test_une_fiche_COUPEE_EN_PLEIN_MOT_est_REFUSEE_et_le_dit() -> None:
    """The floor BITES: `ok` becomes `cut`, with the count and the reason - not a mere counter.

    This is what sets it apart from the two other axes (`n_templated`, `n_truncated`), which never
    change a verdict: a mid-word cut is a fault the producer can REPAIR RIGHT AWAY.
    """
    raw = "Risk management is the core of quantitative finance and it governs everything else here."
    bons = [
        "Risk management is the core of quantitative finance",
        "and it governs everything else here.",
        "is the core of quantitative finance and it governs",
    ]
    fiche = _fiche([("One", bons), ("Two", ["Risk management is the core of quantitat"])])
    verdict = judge_fiche(fiche, raw)
    assert verdict.status == "cut"
    assert verdict.ok is False, "a status that is not `ok` must also refuse the fiche"
    assert verdict.n_cut_midword == 1
    assert "MID-WORD" in verdict.reason

    # and without the cut, the SAME fiche passes - the floor accuses the fault, not the fiche
    assert judge_fiche(_fiche([("One", bons)]), raw).status == "ok"
