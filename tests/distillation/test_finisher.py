"""The finisseur polishes readability WITHOUT ever touching the verbatim P3.

THE property that matters: whatever the re-titling does (heuristic or model), the
``### Contenu (verbatim)`` block of each chapter is copied IDENTICALLY - P3 is sacred by construction.
The rest (bad titles rebuilt, sommaire regenerated) is just polish. Brick-free."""

from __future__ import annotations

from mnemosyne.production import (
    VERBATIM_BEGIN,
    VERBATIM_END,
    chapter_numbers_ok,
    curate_concepts,
    finish_fiche,
    is_bad_title,
    is_templated_description,
    parse_fiche,
)

# A trap fiche (the audit's NO-GO case): a verbatim passage that itself contains a "## N." line. Left
# unguarded, the parser treats it as a chapter boundary and TRUNCATES P3 there. `chapters: 1` in the
# frontmatter disagrees with the 2 headings the regex sees -> ambiguous -> the finisher must refuse it.
_TRAP = (
    '---\ntitle: "T"\nchapters: 1\n---\n\n# T\n\n## Sommaire\n- [[#1. (section)]] - x\n\n'
    "## 1. (section)\n\nDesc.\n\n**Concepts** :\n- x\n\n### Contenu (verbatim)\n\n"
    "A precious verbatim line.\n\n## 2. This heading is really inside a quote\n\nmore precious verbatim.\n"
)

# The SAME quoted "## 2.", but now inside a SELF-DELIMITED verbatim fence: the structural fix. The
# scan masks the fenced span, so the fiche has ONE real chapter (matches frontmatter chapters:1) and is
# parsed cleanly -- the fail-closed refusal above becomes unnecessary because the ambiguity is gone.
_FENCED = (
    '---\ntitle: "T"\nchapters: 1\n---\n\n# T\n\n## Sommaire\n- [[#1. Real]] - x\n\n'
    "## 1. Real\n\nDesc.\n\n**Concepts** :\n- x\n\n### Contenu (verbatim)\n\n"
    + VERBATIM_BEGIN
    + "\n\nA precious verbatim line.\n\n## 2. This heading is really inside a quote\n\nmore precious verbatim.\n\n"
    + VERBATIM_END
    + "\n"
)


def _fiche(chapters: list[tuple[str, tuple[str, ...], list[str]]]) -> str:
    parts = ["---", 'title: "T"', "---", "", "# T", "", "> banner", "", "## Sommaire", ""]
    for i, (title, _c, _p) in enumerate(chapters, 1):
        parts.append(f"- [[#{i}. {title}]] - x")
    for i, (title, concepts, passages) in enumerate(chapters, 1):
        parts += ["", f"## {i}. {title}", "", "A description of the chapter.", "", "**Concepts** :"]
        parts += [f"- {c}" for c in concepts]
        parts += ["", "### Contenu (verbatim)", "", "\n\n".join(passages), ""]
    return "\n".join(parts)


def test_is_bad_title() -> None:
    assert is_bad_title("(section)") and is_bad_title("34 7 8 L9") and is_bad_title("$")
    assert not is_bad_title("Portfolio Theory") and not is_bad_title("Risk Management")


def test_is_templated_description_catches_the_bulk_gabarit_not_a_real_synthesis() -> None:
    # the Codex bulk-polish pattern (91.7% of the corpus): a fixed sentence filled with title + top concepts.
    # These sentences are FRENCH because they ARE the patterns under test: `is_templated_description`
    # recognises the boilerplate a model emits on a French corpus. They are data, not prose to
    # translate - an English paraphrase would match nothing and the check would pass on emptiness.
    assert is_templated_description(
        "L'auteur traite ici de « Risk » et aborde également a, b et c."
    )
    assert is_templated_description(
        "L’auteur présente les éléments relatifs à X et expose les mécanismes."
    )
    assert is_templated_description("Le chapitre reproduit la table des matières de l'ouvrage.")
    assert is_templated_description("Le chapitre présente des éléments biographiques sur l'auteur.")
    # a genuine synthesis is NOT flagged (conservative - never mislabels real work as a template). In
    # particular a synthesis OPENING with "L'auteur examine..." must pass (that generic opener is NOT a marker).
    assert not is_templated_description(
        "Cochrane montre que le facteur d'actualisation stochastique unifie CAPM, APT et consommation."
    )
    assert not is_templated_description(
        "L'auteur examine en profondeur la dynamique des taux courts et ses implications empiriques."
    )
    assert not is_templated_description(
        "A short real note about position sizing under uncertainty."
    )


def test_finish_preserves_every_verbatim_block_exactly() -> None:
    # THE guarantee: whatever the finisher does to titles/prose, P3 blocks are byte-identical.
    fiche = _fiche(
        [
            (
                "(section)",
                ("risk", "sizing"),
                ["A precious verbatim passage.", "A second exact quote."],
            ),
            ("Real Title", ("value",), ["A third verbatim line, untouched."]),
        ]
    )
    before = [ch.contenu for ch in parse_fiche(fiche)[1]]
    after = [ch.contenu for ch in parse_fiche(finish_fiche(fiche))[1]]
    assert before == after
    assert all(block for block in before)  # non-empty, really compared


def test_finish_rebuilds_a_bad_title_from_concepts_and_keeps_a_good_one() -> None:
    fiche = _fiche(
        [
            ("(section)", ("risk management", "position sizing"), ["p1"]),
            ("Portfolio Theory", ("obj",), ["p2"]),
        ]
    )
    _header, chapters = parse_fiche(finish_fiche(fiche))
    assert (
        chapters[0].title == "Chapitre 1 — risk management, position sizing"
    )  # bad -> from concepts
    assert chapters[1].title == "Portfolio Theory"  # decent -> kept


def test_finish_uses_an_injected_retitle_but_still_never_touches_p3() -> None:
    fiche = _fiche([("(section)", ("x",), ["A precious verbatim line."])])
    out = finish_fiche(fiche, retitle=lambda ch: ("Model Title", "A polished description."))
    _header, chapters = parse_fiche(out)
    assert chapters[0].title == "Model Title"
    assert chapters[0].description == "A polished description."
    assert chapters[0].contenu == parse_fiche(fiche)[1][0].contenu  # P3 untouched by the model path
    assert "A precious verbatim line." in out


def test_finish_refuses_a_false_heading_inside_a_passage_fail_closed() -> None:
    # THE audit's NO-GO case: a "## 2." inside a passage would truncate P3 if parsed. The guard
    # catches it (frontmatter chapters:1 != 2 headings) and finish_fiche returns the fiche UNCHANGED.
    assert not chapter_numbers_ok(_TRAP)
    assert finish_fiche(_TRAP) == _TRAP  # not rewritten -> the verbatim is never truncated


def test_chapter_numbers_ok_accepts_the_same_heading_when_fenced() -> None:
    # THE structural fix: fenced, the quoted "## 2." is masked -> ONE real chapter == frontmatter
    # chapters:1 -> ok. What was fail-closed-refused unfenced is now parsed cleanly.
    assert chapter_numbers_ok(_FENCED)


def test_finish_preserves_a_fenced_verbatim_that_quotes_a_heading() -> None:
    before = parse_fiche(_FENCED)[1]
    after = parse_fiche(finish_fiche(_FENCED))[1]
    assert len(before) == len(after) == 1  # the quoted "## 2." did NOT split the chapter in two
    assert (
        before[0].contenu == after[0].contenu
    )  # P3 (fence + quoted heading included) carried byte-for-byte
    assert (
        "## 2. This heading is really inside a quote" in after[0].contenu
    )  # the quote survived verbatim


def test_chapter_numbers_ok_accepts_a_well_formed_fiche() -> None:
    good = _fiche(
        [("A", ("x",), ["p1"]), ("B", ("y",), ["p2"])]
    )  # no frontmatter chapters: -> seq-only
    assert chapter_numbers_ok(good)


def test_curate_concepts_drops_the_formula_not_decoded_placeholder() -> None:
    # the real corpus's #1 noise source (~1700 chapters): a formula the distiller could not decode, leaked
    # in as a fake "concept". Always junk, case-insensitive.
    assert curate_concepts(["independence", "assumption", "formula-not-decoded"]) == [
        "independence",
        "assumption",
    ]
    assert curate_concepts(["Correlations", "FORMULA-NOT-DECODED", "count"]) == [
        "Correlations",
        "count",
    ]


def test_curate_concepts_strips_stray_edge_punctuation() -> None:
    # real corpus fragments: an extraction n-gram cut mid-quote or mid-hyphenation.
    assert curate_concepts(["hypothesis", "control", "Testing'"]) == [
        "hypothesis",
        "control",
        "Testing",
    ]
    assert curate_concepts(["func-", "'Elle-'", "points-"]) == ["func", "Elle", "points"]


def test_curate_concepts_keeps_language_names_with_trailing_symbols() -> None:
    # C++/C#/F# are REAL concepts (e.g. Design Patterns is a C++ book): the trailing +/# is load-bearing,
    # not edge noise. The list carries a token that survives on its own ("risk") so the empty-list fallback
    # can NOT mask a wrongful drop -- if the +/# were stripped, C++/C#/F# would collapse to len<2 and vanish.
    assert curate_concepts(["C++", "C#", "F#", "risk"]) == ["C++", "C#", "F#", "risk"]


def test_curate_concepts_drops_stopwords_empties_and_pure_numbers() -> None:
    assert curate_concepts(["risk", "the", "and", "42", "--", "x", "sizing"]) == ["risk", "sizing"]
    # borderline SHORT content words must survive -- the stopword set is small and undeniable on purpose
    assert curate_concepts(["null", "four", "size"]) == ["null", "four", "size"]


def test_curate_concepts_dedupes_case_insensitively_keeping_first_casing_and_order() -> None:
    assert curate_concepts(["Bayes", "estimator", "bayes", "Estimator"]) == ["Bayes", "estimator"]


def test_curate_concepts_leaves_a_real_concept_list_untouched() -> None:
    # CONSERVATIVE DOCTRINE: nothing to clean here -> nothing changes, not even casing.
    clean = ["large-scale", "inference", "Bayes", "empirical", "estimator"]
    assert curate_concepts(clean) == clean


def test_curate_concepts_never_empties_a_chapter_falls_back_to_original() -> None:
    # if EVERY token is noise, curation would starve the title fallback / sommaire gloss -> keep the
    # original list instead of returning an empty one (a conservative floor).
    assert curate_concepts(["formula-not-decoded"]) == ["formula-not-decoded"]
    assert curate_concepts(["the", "42"]) == ["the", "42"]


def test_finish_curates_concepts_in_both_chapter_block_and_sommaire() -> None:
    raw_concepts = ("independence", "formula-not-decoded", "Testing'", "assumption", "independence")
    fiche = _fiche(
        [
            (
                "Independence Assumption",
                raw_concepts,
                ["A precious verbatim passage about independence."],
            )
        ]
    )
    before = [ch.contenu for ch in parse_fiche(fiche)[1]]
    out = finish_fiche(fiche)
    after = [ch.contenu for ch in parse_fiche(out)[1]]
    assert before == after and all(before)  # P3 byte-identical, really compared

    curated = curate_concepts(list(raw_concepts))
    assert curated == [
        "independence",
        "Testing",
        "assumption",
    ]  # junk dropped, deduped, punctuation stripped

    _header, chapters = parse_fiche(out)
    assert list(chapters[0].concepts) == curated  # the chapter's own **Concepts** block
    sommaire = out.split("## 1.", 1)[0]  # the rebuilt Sommaire, before the chapter body
    gloss_sep = "—"
    assert (
        f"{gloss_sep} {', '.join(curated)}" in sommaire
    )  # same curated concepts feed the sommaire gloss
    assert "formula-not-decoded" not in out


def test_finish_denoises_a_title_without_touching_a_legitimate_one() -> None:
    fiche = _fiche(
        [
            ("Portfolio Theory*", ("value",), ["p1"]),
            ("Does It Matter Empirically?", ("value",), ["p2"]),
        ]
    )
    _header, chapters = parse_fiche(finish_fiche(fiche))
    assert (
        chapters[0].title == "Portfolio Theory"
    )  # trailing footnote asterisk stripped -- safe, unambiguous
    assert (
        chapters[1].title == "Does It Matter Empirically?"
    )  # legitimate trailing "?" left untouched


def test_finish_strips_a_leaked_formula_not_decoded_suffix_from_a_title() -> None:
    fiche = _fiche([("Standardization formula-not-decoded", ("standardization",), ["p1"])])
    _header, chapters = parse_fiche(finish_fiche(fiche))
    assert chapters[0].title == "Standardization"
