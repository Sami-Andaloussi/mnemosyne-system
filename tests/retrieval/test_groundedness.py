"""D148 - the extraction gate measures INVENTION, mechanically: no golden, no judge.

Why this gate exists at all is in `production/golden.py`'s module note (short version: the F1 against a
hand-labelled triple goldens can be uninterpretable for a corpus - one sentence admits many
valid decompositions, so exact match demanded the extractor guess the labeller's framing). What the
trust flag must actually hold is that THE GRAPH DOES NOT FILL WITH LIES, and that is what these pin.

The decisive property - it DISCRIMINATES - is pinned on the real, measured behaviour of both the
un-prompted extractor (which recited its training data) and the prompted one (which read). Brick-free:
the extractor is a callable, so nothing is installed (D126).
"""

from __future__ import annotations

from mnemosyne.production import MIN_GROUNDEDNESS, MIN_YIELD, Triple, score_groundedness

# The passage that exposed the invention, verbatim from the corpus golden (Clean Architecture).
_DIP = (
    "The source code dependencies are inverted against the flow of control, which is why we refer "
    "to this principle as Dependency Inversion."
)

# What the extractor ACTUALLY returned before it had a prompt (measured 2026-07-17): it recited SIX
# triples from training data and missed the one fact the passage states. Four of those six are pinned
# here (enough to prove the gate catches recital); the assertions below count these four.
_RECITED: tuple[Triple, ...] = (
    ("Dependency Inversion Principle", "promotes", "loose coupling and high cohesion"),
    (
        "Dependency Inversion Principle",
        "states",
        "high-level modules should not depend on low-level modules, but both should depend on abstractions",
    ),
    ("Dependency Inversion Principle", "encourages", "the use of interfaces or abstract classes"),
    ("Dependency Inversion Principle", "describes", "a design principle in software engineering"),
)

# What it returns WITH the prompt: exactly what the passage says, nothing more.
_READ: tuple[Triple, ...] = (
    ("source code dependencies", "are inverted", "against the flow of control"),
)


def _extractor(by_passage: dict[str, tuple[Triple, ...]]):
    return lambda passage: frozenset(by_passage.get(passage, ()))


def test_recited_training_data_is_caught_as_ungrounded() -> None:
    # THE case the gate exists for. Every one of these entities is foreign to the passage.
    score = score_groundedness(_extractor({_DIP: _RECITED}), [_DIP])

    assert score.grounded == 0.0
    assert not score.trusted
    assert len(score.foreign) == 4
    # and it says WHY, per triple - a failure must be diagnosable, not merely red. Looked up by
    # triple, never by position: the extractor returns a frozenset, so `foreign`'s order within one
    # passage is not deterministic and must not be asserted.
    words_by_triple = {triple: set(words) for _, triple, words in score.foreign}
    assert {"loose", "coupling", "cohesion"} <= words_by_triple[_RECITED[0]]
    assert {"modules", "abstractions"} <= words_by_triple[_RECITED[1]]


def test_reading_the_passage_is_grounded() -> None:
    score = score_groundedness(_extractor({_DIP: _READ}), [_DIP])

    assert score.grounded == 1.0
    assert score.foreign == ()


def test_the_predicate_is_free_so_an_honest_verb_is_not_an_invention() -> None:
    # Naming a relation is a linguistic act: a passage reading "X's paper Y" legitimately yields the
    # predicate `wrote`, a word it never contains. Scoring the predicate flagged 13/58 REAL triples,
    # every one a false alarm (`wrote`, `outlines`, `equals`) - hence entities only.
    passage = "Jegadeesh and Titman's paper Returns to Buying Winners changed the field."
    triple: Triple = ("Jegadeesh", "wrote", "Returns to Buying Winners")

    score = score_groundedness(_extractor({passage: (triple,)}), [passage])

    assert score.grounded == 1.0  # `wrote` is absent from the passage and that is FINE


def test_silence_can_never_pass_the_gate() -> None:
    # Groundedness alone is trivially gamed: emit nothing, never lie, score 1.0. The yield floor is
    # what closes that, and the vacuous case is fail-CLOSED at 0.0 rather than a vacuous 1.0 -
    # "it never lied because it never spoke" must not certify an extractor (D100).
    score = score_groundedness(lambda _: frozenset(), [_DIP, "another passage entirely"])

    assert score.grounded == 0.0
    assert score.yield_per_passage == 0.0
    assert not score.trusted


def test_a_triple_that_names_no_entity_can_never_pass_the_gate() -> None:
    # THE blocker the D148 audit found. Groundedness asks "are the words from the passage?" - and an
    # EMPTY entity has no words to be foreign, so `("", "", "")` naively scored as grounded. A
    # one-line extractor emitting one such triple per passage - READING NOTHING - then cleared both
    # bars at 1.000. It names nothing, so it is UNGROUNDED, not a free pass. Pinned in three shapes:
    # empty strings, function-words-only, and punctuation-only, since _content_words drops all three.
    passages = ["The GDP deflator is the ratio of nominal to real GDP.", "Inflation erodes value."]
    for vacuous in (("", "", ""), ("the", "is", "a"), (".", "", ".")):
        score = score_groundedness(lambda _p, t=vacuous: frozenset({t}), passages)
        assert score.grounded == 0.0, f"vacuous triple {vacuous!r} scored as grounded"
        assert (
            score.yield_per_passage == 1.0
        )  # it DID emit - so the yield floor alone would pass it
        assert not score.trusted  # ...but groundedness catches that it named nothing
        # the diagnosis says WHY, not a misleading empty foreign-word list
        assert score.foreign[0][2] == ("<no entity named>",)


def test_one_safe_triple_per_two_passages_fails_the_yield_floor() -> None:
    # A subtler abstention: perfectly grounded, but it has started skipping passages.
    other = "Inflation erodes purchasing power."
    score = score_groundedness(_extractor({_DIP: _READ}), [_DIP, other])

    assert score.grounded == 1.0  # nothing it said was invented...
    assert score.yield_per_passage == 0.5  # ...but it barely spoke
    assert not score.trusted  # so it is NOT trusted with the graph


def test_no_passage_is_fail_closed_not_vacuously_perfect() -> None:
    score = score_groundedness(_extractor({}), [])

    assert (score.grounded, score.yield_per_passage, score.passages) == (0.0, 0.0, 0)
    assert not score.trusted


def test_a_raising_extractor_is_a_recall_loss_never_a_crash() -> None:
    def boom(_: str) -> frozenset[Triple]:
        raise RuntimeError("model fell over")

    score = score_groundedness(boom, [_DIP])

    assert not score.trusted  # scores as untrusted...
    assert score.triples == 0  # ...and the calibration still returns a verdict


def test_a_scramble_of_the_passages_own_words_is_the_named_residue() -> None:
    # HONEST RESIDUE, pinned so it cannot be forgotten or later mistaken for a guarantee:
    # groundedness bounds where the material came from, never whether the assembly is TRUE.
    passage = "The capital ratio of a bank is defined as the ratio of its capital to its assets."
    lie: Triple = ("assets", "is defined as", "ratio of capital ratio to bank")

    score = score_groundedness(_extractor({passage: (lie,)}), [passage])

    assert score.grounded == 1.0  # every word IS from the passage - the gate cannot see the lie
    # This is why the bar is necessary, not sufficient. It is not a truth oracle.


def test_the_bars_are_the_two_independent_failure_modes() -> None:
    assert MIN_GROUNDEDNESS == 0.95  # measured 1.000 on the real extractor: headroom, still bites
    assert MIN_YIELD == 1.0  # measured 1.9/passage; the hand labeller wrote 1.6
