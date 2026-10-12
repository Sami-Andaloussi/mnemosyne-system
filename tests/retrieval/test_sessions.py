"""D155 - recall over Mnemosyne's own past conversations, and the four ways it could lie.

The capability is trivial to make LOOK right (an index that returns something always looks like it
works), so these tests hold the properties that decide whether it can be trusted:

* it indexes what was SAID, not what was read or injected;
* it does not double-count a message the host recorded twice (measured: one message present four
  times in a single real transcript - more than half of a 24 547-message index was duplicates);
* a prose question still finds an answer, and the tool SAYS when it had to relax the match;
* a delegated sub-agent's monologue never enters the conversation index.
"""

from __future__ import annotations

import json
from pathlib import Path

from mnemosyne.production.sessions import (
    SessionIndex,
    build_match_expression,
    query_terms,
    read_transcript,
)


def _event(**fields: object) -> str:
    return json.dumps(fields, ensure_ascii=False)


def _say(
    uuid: str,
    role: str,
    text: str,
    ts: str = "2026-07-20T10:00:00.000Z",
    session: str = "s1",
    **extra: object,
) -> str:
    """One spoken message. ``session`` is explicit because two fixtures sharing a session id would
    OVERWRITE each other at index time - which once made a scoping test pass for the wrong reason.
    """
    return _event(
        type=role,
        uuid=uuid,
        sessionId=session,
        timestamp=ts,
        message={"role": role, "content": text},
        **extra,
    )


def _write(root: Path, project: str, name: str, lines: list[str]) -> Path:
    directory = root / project
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _index(tmp_path: Path, lines: list[str], project: str = "-repo") -> SessionIndex:
    root = tmp_path / "projects"
    _write(root, project, "s1", lines)
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()
    return index


# --- what gets indexed, and what must not ---------------------------------------------------
def test_a_message_recorded_twice_is_indexed_once(tmp_path: Path) -> None:
    """The measured pathology: the host re-appends a message under the SAME uuid.

    Without this, one answer occupies every slot of a result list and pushes out real ones.
    """
    lines = [
        _say("u1", "user", "the distillateur must cite its source"),
        _say("u1", "user", "the distillateur must cite its source"),
        _say("u1", "user", "the distillateur must cite its source"),
    ]
    index = _index(tmp_path, lines)

    assert index.stats()["messages"] == 1
    assert len(index.search("distillateur")) == 1


def test_two_distinct_messages_with_the_same_words_both_survive(tmp_path: Path) -> None:
    """The counter-proof: dedup keys on the host's uuid, never on the text.

    operator repeating himself in two turns is two facts about the conversation, not a duplicate.
    """
    lines = [
        _say("u1", "user", "tidy that up right now"),
        _say("u2", "user", "tidy that up right now"),
    ]
    index = _index(tmp_path, lines)

    assert index.stats()["messages"] == 2


def test_tool_results_and_file_dumps_never_enter_the_index(tmp_path: Path) -> None:
    """ "What was said, not what was read" - this is what keeps 643 MB from becoming the index."""
    lines = [
        _say("u1", "user", "read the file"),
        _event(
            type="assistant",
            uuid="a1",
            sessionId="s1",
            timestamp="2026-07-20T10:01:00.000Z",
            message={
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "here is what the file says"},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}},
                    {"type": "tool_result", "content": "SECRET_DU_FICHIER_ABCDEF"},
                ],
            },
        ),
    ]
    index = _index(tmp_path, lines)

    assert index.stats()["messages"] == 2
    assert not index.search("SECRET_DU_FICHIER_ABCDEF")
    assert index.search("file")  # the spoken half is still there


def test_injected_scaffolding_is_not_treated_as_something_operator_said(tmp_path: Path) -> None:
    """A hook reminder lives INSIDE a operator message. Indexing it would attribute it to operator."""
    lines = [
        _say(
            "u1",
            "user",
            "<system-reminder>RAPPEL_INJECTE_PAR_LE_HOOK</system-reminder>\ndo the cleanup",
        )
    ]
    index = _index(tmp_path, lines)

    assert not index.search("RAPPEL_INJECTE_PAR_LE_HOOK")
    assert index.search("cleanup")


def test_a_subagent_errand_is_not_a_conversation(tmp_path: Path) -> None:
    """557 sub-agent transcripts live under ``subagents/``; 47 conversations live above it.

    Both the directory (not recursed into) and the ``isSidechain`` flag are checked, because the
    host uses both and either alone would let the errands in.
    """
    root = tmp_path / "projects"
    _write(root, "-repo", "s1", [_say("u1", "user", "the real conversation")])
    _write(root, "-repo/subagents", "sub", [_say("x1", "user", "ERRANDE_DELEGUEE", session="sub")])
    _write(
        root,
        "-repo",
        "s2",
        [
            _event(
                type="user",
                uuid="y1",
                sessionId="s2",
                isSidechain=True,
                message={"role": "user", "content": "MONOLOGUE_DE_SOUS_AGENT"},
            )
        ],
    )
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()

    assert index.search("conversation")
    assert not index.search("ERRANDE_DELEGUEE")
    assert not index.search("MONOLOGUE_DE_SOUS_AGENT")


def test_a_compact_summary_is_not_counted_as_a_second_copy(tmp_path: Path) -> None:
    """A compaction summary restates messages already indexed; keeping it double-counts them."""
    lines = [
        _say("u1", "user", "we keep a record of decisions"),
        _say("u2", "user", "summary: we keep a record of decisions", isCompactSummary=True),
    ]
    index = _index(tmp_path, lines)

    assert index.stats()["messages"] == 1


# --- answering a question -------------------------------------------------------------------
def test_a_prose_question_relaxes_rather_than_answering_nothing(tmp_path: Path) -> None:
    """A natural-language question can find zero passages under strict AND.

    Relaxing is right - but the mode must come back, so the caller can say the match was loose.
    """
    index = _index(tmp_path, [_say("u1", "user", "the library books are public")])

    strict = index.search("library books")
    loose = index.search("classification of books as public or personal")

    assert strict.mode == "and" and len(strict) == 1
    assert loose.mode == "or" and len(loose) == 1  # answered, and honest about how


def test_an_exact_match_is_never_buried_under_near_misses(tmp_path: Path) -> None:
    """The counter-proof for the fallback: strict runs FIRST, so a full match wins alone."""
    index = _index(
        tmp_path,
        [
            _say("u1", "user", "the guard refuses by default"),
            _say("u2", "user", "the guard allows everything"),
            _say("u3", "user", "refuses the request"),
        ],
    )

    recall = index.search("guard refuses")

    assert recall.mode == "and"
    assert len(recall) == 1
    assert "default" in recall.hits[0].text


def test_a_question_with_no_answer_abstains_instead_of_inventing(tmp_path: Path) -> None:
    index = _index(tmp_path, [_say("u1", "user", "we're talking about commodities")])

    assert not index.search("zorglub")
    assert not index.search("   ")  # empty query returns nothing, never everything


def test_accents_and_case_do_not_decide_whether_recall_works(tmp_path: Path) -> None:
    """operator types French. ``mémoire`` and ``memoire`` are the same question."""
    index = _index(tmp_path, [_say("u1", "user", "la memoire vivante est validee par operator")])

    assert index.search("MÉMOIRE")
    assert index.search("Mémoire Vivante").mode == "and"


def test_query_syntax_is_matched_as_words_never_executed(tmp_path: Path) -> None:
    """FTS5 reads ``OR``, ``*``, ``NEAR`` and quotes as operators; a question must stay a question.

    The probe is a word the query is a PREFIX of: if ``*`` reached FTS5 as the prefix operator,
    ``gard*`` would match ``garden``. Quoted, it matches only the literal word - which is not in
    the corpus, so an empty result here IS the proof.
    """
    index = _index(
        tmp_path, [_say("u1", "user", "the garden keeper watches"), _say("u2", "user", "heading held")]
    )

    assert not index.search("gard*")
    assert not index.search('" OR "')  # a bare quote would be a syntax error, or match everything
    assert index.search("garden")


def test_a_question_made_only_of_function_words_abstains(tmp_path: Path) -> None:
    """The removed fallback: matching on "the" itself would return a page that looks like an answer."""
    index = _index(tmp_path, [_say("u1", "user", "the system works")])

    recall = index.search("the of a")

    assert not recall.terms
    assert not recall.hits
    assert index.search("system")  # the corpus is reachable - only the non-question is not


# --- keeping the index true ------------------------------------------------------------------
def test_reindexing_an_unchanged_transcript_costs_nothing(tmp_path: Path) -> None:
    index = _index(tmp_path, [_say("u1", "user", "first pass")])

    second = index.reindex()

    assert second["indexed"] == 0 and second["skipped"] == 1


def test_a_grown_transcript_gains_its_new_messages_without_duplicating_the_old(
    tmp_path: Path,
) -> None:
    """A session is appended to WHILE it runs - this is the path taken on every single call."""
    root = tmp_path / "projects"
    path = _write(root, "-repo", "s1", [_say("u1", "user", "first message")])
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_say("u2", "user", "second message") + "\n")
    index.reindex()

    assert index.stats()["messages"] == 2
    assert len(index.search("first")) == 1  # the re-read did not leave a stale copy


def test_a_removed_message_stops_matching(tmp_path: Path) -> None:
    """External-content FTS5 keeps a deleted row's terms unless it is told; then recall lies."""
    root = tmp_path / "projects"
    path = _write(
        root,
        "-repo",
        "s1",
        [_say("u1", "user", "ANCIENNE_PHRASE"), _say("u2", "user", "kept")],
    )
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()
    assert index.search("ANCIENNE_PHRASE")

    path.write_text(_say("u2", "user", "kept") + "\n", encoding="utf-8")
    index.reindex()

    assert not index.search("ANCIENNE_PHRASE")
    assert index.search("kept")


def test_a_torn_last_line_does_not_cost_the_whole_transcript(tmp_path: Path) -> None:
    """A live session's file is being written to as we read it."""
    root = tmp_path / "projects"
    directory = root / "-repo"
    directory.mkdir(parents=True)
    (directory / "s1.jsonl").write_text(
        _say("u1", "user", "complete message") + "\n" + '{"type": "user", "uuid": "u2", "mess',
        encoding="utf-8",
    )
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()

    assert index.search("complete")


def test_the_window_puts_a_hit_back_in_the_order_it_was_said(tmp_path: Path) -> None:
    index = _index(
        tmp_path,
        [_say(f"u{n}", "user", f"message number {n}") for n in range(10)],
    )

    window = index.window("s1", around_seq=5, radius=2)

    assert [hit.seq for hit in window] == [3, 4, 5, 6, 7]


def test_a_missing_transcript_root_is_empty_not_an_error(tmp_path: Path) -> None:
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=tmp_path / "nowhere")

    assert index.reindex()["scanned"] == 0
    assert not index.search("anything at all")


# --- the pure helpers ------------------------------------------------------------------------
def test_the_match_expression_quotes_every_term() -> None:
    assert build_match_expression("guard refuses") == '"guard" "refuses"'
    assert build_match_expression("guard refuses", mode="or") == '"guard" OR "refuses"'
    assert build_match_expression("the of a") == ""  # nothing meaningful => no expression at all


def test_terms_are_folded_and_deduplicated() -> None:
    assert query_terms("Mémoire mémoire MÉMOIRE") == ["memoire"]
    assert query_terms("la memoire de l'operateur") == ["memoire", "operateur"]


def test_reading_a_transcript_reports_its_title_and_id(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "-repo",
        "s1",
        [
            _event(type="ai-title", aiTitle="generated title", sessionId="s1"),
            _event(type="custom-title", customTitle="operator's title", sessionId="s1"),
            _say("u1", "user", "hello"),
        ],
    )

    session_id, title, rows = read_transcript(path)

    assert session_id == "s1"
    assert title == "operator's title"  # the human-set title wins over the generated one
    assert len(rows) == 1


# --- what the audit found broken on the REAL corpus -------------------------------------------
def test_two_transcripts_claiming_one_session_id_do_not_erase_each_other(tmp_path: Path) -> None:
    """The blocker: 1 023 real messages (9,3 %) vanished on the very first run, and the run said
    it had indexed them.

    ``read_transcript`` reports the FIRST ``sessionId`` it sees, and a resumed conversation opens by
    naming its parent - so two files claim one id. Deleting by id made the second erase the first,
    while ``files`` (keyed by path) kept both marked done, so the erased one never came back.
    """
    root = tmp_path / "projects"
    _write(root, "-repo", "a", [_say("u1", "user", "CONVERSATION_A", session="shared")])
    _write(root, "-repo", "b", [_say("u2", "user", "CONVERSATION_B", session="shared")])
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)

    index.reindex()

    assert index.search("CONVERSATION_A"), "the first file was erased by the second"
    assert index.search("CONVERSATION_B")
    assert index.stats()["messages"] == 2  # and the count matches what was reported


def test_a_deleted_transcript_stops_matching(tmp_path: Path) -> None:
    """Without reconciliation, a removed conversation matched forever and every hit pointed at a
    window that could no longer be opened. ``reindex`` only VISITS files that still exist, so the
    check has to come from the index side."""
    root = tmp_path / "projects"
    path = _write(root, "-repo", "s1", [_say("u1", "user", "CONVERSATION_SUPPRIMEE")])
    _write(root, "-repo", "s2", [_say("u2", "user", "conversation gardee", session="s2")])
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()
    assert index.search("CONVERSATION_SUPPRIMEE")

    path.unlink()
    counts = index.reindex()

    assert counts["removed"] == 1
    assert not index.search("CONVERSATION_SUPPRIMEE")
    assert index.stats()["files"] == 1  # the honest denominator stays honest
    assert index.search("gardee")


def test_a_transcript_rewritten_under_a_new_session_id_leaves_nothing_behind(
    tmp_path: Path,
) -> None:
    root = tmp_path / "projects"
    path = _write(root, "-repo", "s1", [_say("u1", "user", "ANCIENNE_SESSION", session="s1")])
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()

    path.write_text(_say("u2", "user", "NOUVELLE_SESSION", session="s9") + "\n", encoding="utf-8")
    index.reindex()

    assert not index.search("ANCIENNE_SESSION")
    assert index.search("NOUVELLE_SESSION")
    assert index.stats()["sessions"] == 1


def test_a_broken_symlink_does_not_take_the_whole_recall_down(tmp_path: Path) -> None:
    """``stat()`` used to live in the sort KEY - outside every guard - so one dangling link raised
    through the entire call."""
    root = tmp_path / "projects"
    _write(root, "-repo", "s1", [_say("u1", "user", "the real conversation")])
    (root / "-repo" / "casse.jsonl").symlink_to(tmp_path / "does-not-exist.jsonl")

    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()

    assert index.search("conversation")


def test_writing_ABOUT_a_scaffolding_tag_does_not_delete_the_rest_of_the_message(
    tmp_path: Path,
) -> None:
    """Unbounded prose loss, in a repo whose subject IS hooks: an unclosed opener used to eat
    everything after it - 155 of 185 characters in the audit's probe."""
    index = _index(
        tmp_path,
        [
            _say(
                "u1",
                "user",
                "the hook injects a <system-reminder> and THEN it RELAUNCHES the turn",
            )
        ],
    )

    assert index.search("RELAUNCHES")  # the tail survived
    assert index.search("hook")


def test_a_decomposed_accent_does_not_shatter_the_question(tmp_path: Path) -> None:
    """macOS hands out NFD. Splitting before folding turned ``dépôt`` into the fragment ``po``."""
    import unicodedata

    index = _index(tmp_path, [_say("u1", "user", "on garde la memoire du depot")])

    nfd = unicodedata.normalize("NFD", "mémoire dépôt")
    recall = index.search(nfd)

    assert recall.terms == ("memoire", "depot")
    assert recall.mode == "and" and len(recall) == 1


def test_the_project_scope_is_a_real_barrier(tmp_path: Path) -> None:
    """Cloisonnement (invariant 3) - correct in the code, pinned by nothing until now."""
    root = tmp_path / "projects"
    _write(root, "-projA", "a", [_say("u1", "user", "SECRET_DU_PROJET_A", session="a")])
    _write(root, "-projB", "b", [_say("u2", "user", "note for project B", session="b")])
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()

    assert not index.search("SECRET_DU_PROJET_A", project="-projB")
    assert index.search("SECRET_DU_PROJET_A", project="-projA")
    assert index.search("SECRET_DU_PROJET_A")  # unscoped still sees it


def test_a_negative_limit_does_not_dump_the_corpus(tmp_path: Path) -> None:
    """``TOPK=-1`` reached SQLite as "no limit" - the exact opposite of a bounded read (inv. 16)."""
    index = _index(tmp_path, [_say(f"u{n}", "user", f"passage number {n}") for n in range(30)])

    assert len(index.search("passage", limit=-1)) == 0
    assert len(index.search("passage", limit=5)) == 5
    assert len(index.window("s1", around_seq=5, radius=10**9)) <= 101


def test_a_torn_line_in_the_MIDDLE_is_skipped_not_a_stop_sign(tmp_path: Path) -> None:
    """The earlier fixture put the tear last, so ``break`` passed too - it proved nothing."""
    root = tmp_path / "projects"
    directory = root / "-repo"
    directory.mkdir(parents=True)
    (directory / "s1.jsonl").write_text(
        _say("u1", "user", "BEFORE the tear")
        + "\n"
        + '{"type": "user", "uuid": "u2", "mess'
        + "\n"
        + _say("u3", "user", "AFTER the tear")
        + "\n",
        encoding="utf-8",
    )
    index = SessionIndex(tmp_path / "sessions.db", transcript_root=root)
    index.reindex()

    assert index.search("BEFORE")
    assert index.search("AFTER")  # parsing RESUMED past the bad line
