"""D156 - endorsement becomes REACHABLE and DURABLE, and what that quietly fixes.

D137 rests the citability of the corpus on one human gesture. This module verifies that the gesture
has a durable, callable path:

* the truth store is an in-memory stand-in, so a role set there dies with the process;
* a library book is not in that store at all - :class:`LibraryTruthStore` serves it from its ``.md``
  mirror and used to return a HARD-CODED default role - so ``set_role`` could fail for library
  documents and a success would have evaporated anyway.

So these tests hold the two halves that make the gesture real: the ledger SURVIVES the process, and
the truth store READS it. Plus the properties that keep it honest - append-only, retraction free,
fail-open on a corrupt journal, and fail-CLOSED where it counts (nothing is citable by default).
"""

from __future__ import annotations

import pytest

from pathlib import Path

from pytest import raises

from mnemosyne.api import CoreApi
from mnemosyne.ingest.library_truth import LibraryTruthStore
from mnemosyne.ports import DocId, DocRole, EscalateToHuman
from mnemosyne.production.endorsements import EndorsementLedger
from mnemosyne.runtime.bootstrap import bootstrap
from mnemosyne.runtime.endorse_run import render_queue, select

_DOCS = {
    "library/aaa": ("Finance/Assets/commodities/books/Storage.md", "commodities"),
    "library/bbb": ("Finance/Assets/commodities/books/Pirrong.md", "commodities"),
    "library/ccc": ("Economics/Macro/macro/books/Woodford.md", "macro"),
}


# --- the ledger: a gesture that survives the process ---------------------------------------
def test_an_endorsement_survives_a_new_ledger_instance(tmp_path: Path) -> None:
    """The whole point. A fresh instance IS what a fresh process sees."""
    path = tmp_path / "endorsements.jsonl"
    EndorsementLedger(path).record(DocId("library/aaa"), DocRole.BASE_DE_CONNAISSANCES, by="test")

    assert EndorsementLedger(path).endorsed() == frozenset({"library/aaa"})


def test_retracting_appends_and_never_erases(tmp_path: Path) -> None:
    """Non-destructive (invariant 2): the history of what was trusted, and until when, stays."""
    path = tmp_path / "endorsements.jsonl"
    ledger = EndorsementLedger(path)
    ledger.record(DocId("library/aaa"), DocRole.BASE_DE_CONNAISSANCES, by="test")
    ledger.record(DocId("library/aaa"), DocRole.MATIERE_DE_TRAVAIL, by="test")

    assert ledger.endorsed() == frozenset()  # last gesture wins
    assert len(path.read_text().strip().splitlines()) == 2  # both are still on disk


def test_a_corrupt_line_is_skipped_and_lands_on_the_fail_closed_side(tmp_path: Path) -> None:
    """Fail-open on read, and the degradation direction is the safe one: LESS endorsed."""
    path = tmp_path / "endorsements.jsonl"
    ledger = EndorsementLedger(path)
    ledger.record(DocId("library/aaa"), DocRole.BASE_DE_CONNAISSANCES, by="test")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{this is not json\n\n")
        handle.write('{"doc": "library/zzz", "role": "unknown-role"}\n')

    assert ledger.endorsed() == frozenset({"library/aaa"})  # survivor kept, junk ignored


def test_a_missing_journal_is_empty_not_an_error(tmp_path: Path) -> None:
    assert EndorsementLedger(tmp_path / "never-written.jsonl").endorsed() == frozenset()


# --- the truth store: it READS the ledger, instead of hard-coding the role -----------------
def test_the_library_store_reads_the_endorsed_set(tmp_path: Path) -> None:
    """This is the line that made D137 unreachable: it returned the default for every book."""
    manifest = tmp_path / "m.json"
    manifest.write_text(
        '{"version": 1, "records": {"library/aaa": '
        '{"rel": "Finance/x.md", "domain": "commodities", "status": "done", "chars": 10, '
        '"at": "2026-07-20T00:00:00+00:00", "error": ""}}}'
    )
    plain = LibraryTruthStore(manifest_path=manifest, raw_root=tmp_path)
    endorsed = LibraryTruthStore(
        manifest_path=manifest, raw_root=tmp_path, endorsed=frozenset({"library/aaa"})
    )

    assert plain.role(DocId("library/aaa")) is DocRole.MATIERE_DE_TRAVAIL  # fail-closed default
    assert endorsed.role(DocId("library/aaa")) is DocRole.BASE_DE_CONNAISSANCES
    with raises(KeyError):
        endorsed.role(DocId("library/unknown"))  # not a book at all - still an error, never a guess


# --- the API gate: journaled first, and never auto-endorsed --------------------------------
def test_endorsing_without_the_human_gesture_still_escalates(tmp_path: Path) -> None:
    """D156 must not have loosened D137: an automatic routine may propose, never endorse."""
    api = CoreApi(bootstrap(endorsements=EndorsementLedger(tmp_path / "e.jsonl")))
    with raises(EscalateToHuman):
        api.endorse_document(DocId("library/aaa"), human_validated=False)
    assert not (tmp_path / "e.jsonl").exists()  # a refused gesture writes NOTHING


def test_endorsing_a_book_absent_from_ram_is_journaled_rather_than_crashing(tmp_path: Path) -> None:
    """The measured failure: a library book has no entry in the in-memory store, so the old code
    raised KeyError on all 314. With a ledger wired, the durable record is what carries it."""
    ledger = EndorsementLedger(tmp_path / "e.jsonl")
    api = CoreApi(bootstrap(endorsements=ledger))

    assert (
        api.endorse_document(DocId("library/aaa"), human_validated=True)
        is DocRole.BASE_DE_CONNAISSANCES
    )
    assert ledger.endorsed() == frozenset({"library/aaa"})


def test_without_a_ledger_the_old_in_memory_behaviour_is_unchanged(tmp_path: Path) -> None:
    """Zero regression for a stub / unit-test runtime: no ledger => the KeyError still propagates."""
    api = CoreApi(bootstrap())
    with raises(KeyError):
        api.endorse_document(DocId("library/absent"), human_validated=True)


# --- the lot: the unit a human can actually decide ----------------------------------------
def test_a_scope_selects_a_branch_and_a_single_book_alike() -> None:
    assert select(_DOCS, scope="Finance/Assets", domain=None) == ("library/aaa", "library/bbb")
    assert select(_DOCS, scope="Finance/Assets/commodities/books/Storage.md", domain=None) == (
        "library/aaa",
    )
    assert select(_DOCS, scope="finance/assets", domain=None) == ("library/aaa", "library/bbb")


def test_a_domain_selects_across_the_shelf() -> None:
    assert select(_DOCS, scope=None, domain="macro") == ("library/ccc",)
    assert select(_DOCS, scope="Finance", domain="macro") == ()  # both filters apply


def test_the_queue_view_reports_what_is_citable_and_what_is_not() -> None:
    out = render_queue(_DOCS, frozenset({"library/aaa"}))
    assert "1 document(s) CITABLES sur 3" in out
    assert "commodities — 1/2 citables" in out
    assert "macro — 0/1 citables" in out
    assert "WORKING MATERIAL" in out  # says what an UNendorsed document still does


def test_the_queue_view_is_honest_on_an_empty_shelf() -> None:
    assert "Aucun document indexé" in render_queue({}, frozenset())


def test_le_champ_BY_n_a_plus_de_DEFAUT_et_ne_pretend_aucune_identite(tmp_path) -> None:
    """The default ``by="operator"`` must not assert an identity the code cannot know.

    ``make endorse CONFIRM=1`` deliberately has no terminal gate because endorsement is reversible.
    The remedy is not a "better" default: ``by`` is required, and the recorded value is observable
    context (system account plus terminal presence), never an assumed identity.
    """
    import inspect

    from mnemosyne.production.endorsements import observed_actor

    signature = inspect.signature(EndorsementLedger.record)
    assert signature.parameters["by"].default is inspect.Parameter.empty, (
        "a default crept back onto `by` - that is exactly what signed 314 lines with the operator's name"
    )
    with pytest.raises(TypeError):
        EndorsementLedger(tmp_path / "j.jsonl").record(  # type: ignore[call-arg]
            DocId("library/x"), DocRole.BASE_DE_CONNAISSANCES
        )

    # and what the observer returns CLAIMS nothing: it carries its own channel, so it is falsifiable
    actor = observed_actor()
    assert actor.endswith(("@tty", "@non-tty")), actor
    assert actor != "operator", (
        "a hard-coded identity is a claim the machine cannot back up"
    )
