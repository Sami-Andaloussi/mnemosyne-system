"""D159 - policy_requests: the demander -> examiner -> approuver pipeline.

The trap the filing signalement names is "un agent de securite valide puis applique" - it looks
safe but an agent that approves is still an agent. These tests hold the shape that avoids it:
examination can only ever NARROW or RECOMMEND, never approve or refuse; only the literal word
"oui" from :meth:`PolicyRequestLedger.approve` does; and a pending request is a REFUSAL, not a
permissive "in progress" (:meth:`PolicyRequestLedger.approved_items_for_apply` is fail-closed).
"""

from __future__ import annotations

from pathlib import Path

from pytest import raises

from mnemosyne.production.policy_requests import (
    PolicyChangeRequest,
    PolicyRequestError,
    PolicyRequestLedger,
    render_template,
    request_from_toml,
)
from mnemosyne.production.policy_writer import PolicyItem


def _request(**overrides: object) -> PolicyChangeRequest:
    defaults: dict[str, object] = {
        "title": "Example Research -- public statistical sources",
        "items": (PolicyItem(kind="egress", values=("api.stlouisfed.org",)),),
        "justification": "measure series with revisions for the V0.1 finish line",
        "requested_by": "example-research (project session)",
    }
    defaults.update(overrides)
    return PolicyChangeRequest(**defaults)  # type: ignore[arg-type]


# --- filing: stable, idempotent ids ---------------------------------------------------------
def test_filing_assigns_a_stable_id(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    assert len(id_) == 12
    state = ledger.state(id_)
    assert state is not None
    assert state.stage == "depose"
    assert state.title == "Example Research -- public statistical sources"


def test_refiling_identical_content_is_idempotent(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_a = ledger.file(_request())
    id_b = ledger.file(_request())
    assert id_a == id_b
    assert len(ledger.path.read_text().strip().splitlines()) == 1  # no duplicate event


def test_a_different_justification_is_a_different_request(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_a = ledger.file(_request())
    id_b = ledger.file(_request(justification="a different reason"))
    assert id_a != id_b


def test_a_request_needs_items_title_and_justification() -> None:
    with raises(PolicyRequestError):
        _request(items=())
    with raises(PolicyRequestError):
        _request(title="  ")
    with raises(PolicyRequestError):
        _request(justification="")


# --- the examiner: narrows or recommends, NEVER decides --------------------------------------
def test_an_allow_verdict_leaves_the_items_and_hash_unchanged(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    original_hash = ledger.state(id_).content_hash()

    ledger.record_examination(
        id_, verdict="allow", notes="legitimate host, matches the justification"
    )
    state = ledger.state(id_)
    assert state.stage == "examine"
    assert state.examiner_verdict == "allow"
    assert state.content_hash() == original_hash  # "allow" does not change the items


def test_a_narrow_verdict_actually_shrinks_the_items(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    wide = _request(
        items=(PolicyItem(kind="egress", values=("api.stlouisfed.org", "unrelated-host.example")),)
    )
    id_ = ledger.file(wide)
    narrowed_items = (PolicyItem(kind="egress", values=("api.stlouisfed.org",)),)
    ledger.record_examination(
        id_,
        verdict="narrow",
        narrowed_items=narrowed_items,
        notes="unrelated-host.example does not match anything in the justification",
    )
    state = ledger.state(id_)
    assert state.items == narrowed_items
    assert (
        state.content_hash() != wide.content_hash()
    )  # narrowing changed what an approval binds to


def test_a_narrow_verdict_cannot_smuggle_in_a_new_host(tmp_path: Path) -> None:
    """D75 post-audit fix: the exact trap, one level down. An examiner labelling its verdict
    "narrow" must not be able to WIDEN - add a host that was never asked for - under that name."""
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request(items=(PolicyItem(kind="egress", values=("api.stlouisfed.org",)),)))
    with raises(PolicyRequestError):
        ledger.record_examination(
            id_,
            verdict="narrow",
            narrowed_items=(
                PolicyItem(
                    kind="egress", values=("api.stlouisfed.org", "webhook.attacker.example")
                ),
            ),
        )
    assert ledger.state(id_).stage == "depose"  # the bogus examination never landed


def test_a_narrow_verdict_cannot_invent_a_new_bubble_or_contract(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(
        _request(items=(PolicyItem(kind="domains", bubble="research", values=("macro",)),))
    )
    with raises(PolicyRequestError):
        ledger.record_examination(
            id_,
            verdict="narrow",
            narrowed_items=(
                PolicyItem(kind="domains", bubble="research", values=("macro", "sante")),
            ),
        )
    with raises(PolicyRequestError):
        ledger.record_examination(
            id_,
            verdict="narrow",
            narrowed_items=(
                PolicyItem(kind="contract", contract_from="sante", contract_to="research"),
            ),
        )


def test_a_reject_verdict_does_not_auto_refuse(tmp_path: Path) -> None:
    """The exact trap: an examiner recommendation is not a decision."""
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    ledger.record_examination(id_, verdict="reject", notes="does not match the justification")
    state = ledger.state(id_)
    assert state.examiner_verdict == "reject"
    assert state.stage == "examine"  # NOT "refuse" -- only user's word moves it there
    assert not state.refused


def test_examining_an_unknown_request_raises(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    with raises(PolicyRequestError):
        ledger.record_examination("unknown00000", verdict="allow")


# --- the approuver: exactly "oui", nothing inferred ------------------------------------------
def test_approve_rejects_anything_other_than_oui(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    for near_miss in ("yes", "ok", "oui!", "non", "", "d'accord"):
        with raises(PolicyRequestError):
            ledger.approve(id_, word=near_miss, by="test")
    assert ledger.state(id_).approved is False


def test_approve_and_refuse_require_by_explicitly(tmp_path: Path) -> None:
    """D159, post-incident hardening: `by` has NO default - the incident showed a hardcoded
    `by="operator"` default let an unattended agent's own approval read as if user had given it."""
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    with raises(TypeError):
        ledger.approve(id_, word="oui")  # type: ignore[call-arg]
    with raises(TypeError):
        ledger.refuse(id_, reason="no thank you")  # type: ignore[call-arg]


def test_approve_accepts_case_and_whitespace_variants(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    ledger.approve(id_, word="  OUI  ", by="test")
    assert ledger.state(id_).approved is True
    assert ledger.state(id_).stage == "approuve"


def test_refusing_is_recorded_and_non_destructive(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    ledger.refuse(id_, reason="no need for that host", by="test")
    state = ledger.state(id_)
    assert state.stage == "refuse"
    assert state.refused_reason == "no need for that host"
    # user can change his mind -- both events stay on disk (append-only), latest wins
    ledger.approve(id_, word="oui", by="test")
    assert ledger.state(id_).stage == "approuve"
    assert (
        len(ledger.path.read_text().strip().splitlines()) == 3
    )  # filed + refused + approved, all kept


# --- the fail-closed gate into apply ----------------------------------------------------------
def test_a_pending_request_refuses_apply_fail_closed(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    with raises(PolicyRequestError):
        ledger.approved_items_for_apply(id_)


def test_a_refused_request_refuses_apply(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    ledger.refuse(id_, reason="non", by="test")
    with raises(PolicyRequestError):
        ledger.approved_items_for_apply(id_)


def test_an_unknown_id_refuses_apply(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    with raises(PolicyRequestError):
        ledger.approved_items_for_apply("000000000000")


def test_an_approved_request_yields_its_current_items(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    req = _request()
    id_ = ledger.file(req)
    ledger.approve(id_, word="oui", by="test")
    assert ledger.approved_items_for_apply(id_) == req.items


def test_a_second_apply_is_refused(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    id_ = ledger.file(_request())
    ledger.approve(id_, word="oui", by="test")
    ledger.approved_items_for_apply(id_)
    ledger.record_application(id_, diff={"egress_added": ["api.stlouisfed.org"]})
    with raises(PolicyRequestError):
        ledger.approved_items_for_apply(id_)
    assert ledger.state(id_).stage == "applique"


def test_narrowing_after_approval_invalidates_the_stale_approval(tmp_path: Path) -> None:
    """The exact non-repudiation property: an approval binds to content, not to an id."""
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    wide = _request(
        items=(PolicyItem(kind="egress", values=("api.stlouisfed.org", "other.example")),)
    )
    id_ = ledger.file(wide)
    ledger.approve(id_, word="oui", by="test")
    ledger.record_examination(
        id_,
        verdict="narrow",
        narrowed_items=(PolicyItem(kind="egress", values=("api.stlouisfed.org",)),),
    )
    with raises(PolicyRequestError):
        ledger.approved_items_for_apply(id_)  # the "oui" was for the OLD (wider) content


# --- replay robustness (mirrors human_journal.py's D82 contract) ------------------------------
def test_a_truncated_final_line_is_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "requests.jsonl"
    ledger = PolicyRequestLedger(path)
    id_ = ledger.file(_request())
    with path.open("a", encoding="utf-8") as handle:
        # a half-written JSON line, simulating a crash mid-append (D82 write-ahead recovery)
        handle.write('{"v": 1, "kind": "approved", "id": "' + id_ + '", "at": "2026')
    fresh = PolicyRequestLedger(path)
    assert fresh.state(id_).stage == "depose"  # the truncated approval never happened


def test_a_malformed_internal_line_raises(tmp_path: Path) -> None:
    path = tmp_path / "requests.jsonl"
    ledger = PolicyRequestLedger(path)
    id_ = ledger.file(_request())
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{this is not valid json}\n")
        handle.write(
            '{"v": 1, "kind": "approved", "id": "'
            + id_
            + '", "at": "x", "content_hash": "y", "by": "operator"}\n'
        )
    with raises(Exception):
        PolicyRequestLedger(path).state(id_)


def test_an_unknown_event_kind_raises(tmp_path: Path) -> None:
    path = tmp_path / "requests.jsonl"
    ledger = PolicyRequestLedger(path)
    id_ = ledger.file(_request())
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"v": 1, "kind": "mystery", "id": "' + id_ + '"}\n')
    with raises(PolicyRequestError):
        PolicyRequestLedger(path).state(id_)


def test_an_event_for_a_never_filed_id_raises(tmp_path: Path) -> None:
    path = tmp_path / "requests.jsonl"
    path.write_text(
        '{"v": 1, "kind": "approved", "id": "never-filed", "at": "x", "content_hash": "y", "by": "operator"}\n'
    )
    with raises(PolicyRequestError):
        PolicyRequestLedger(path).state("never-filed")


def test_all_states_are_sorted_by_filing_time(tmp_path: Path) -> None:
    ledger = PolicyRequestLedger(tmp_path / "requests.jsonl")
    ledger.file(_request(title="first"))
    ledger.file(_request(title="second", justification="another reason"))
    titles = [s.title for s in ledger.all_states()]
    assert titles == ["first", "second"]


# --- the hand-editable request file --------------------------------------------------------
def test_the_template_is_a_valid_starting_point_once_uncommented() -> None:
    template = render_template()
    assert "title" in template
    assert "[[items]]" in template


def test_request_from_toml_parses_a_full_bundle() -> None:
    text = """
title = "test"
requested_by = "me"
justification = "because"

[[items]]
kind = "egress"
values = ["a.example"]

[[items]]
kind = "domains"
bubble = "research"
values = ["macro"]

[[items]]
kind = "contract"
contract_from = "knowledge"
contract_to = "research"
"""
    req = request_from_toml(text)
    assert req.title == "test"
    assert len(req.items) == 3
    assert req.items[0].kind == "egress"
    assert req.items[1].bubble == "research"
    assert req.items[2].contract_to == "research"


def test_request_from_toml_requires_the_top_level_fields() -> None:
    with raises(PolicyRequestError):
        request_from_toml('title = "x"\n')


def test_request_from_toml_rejects_invalid_toml() -> None:
    with raises(PolicyRequestError):
        request_from_toml("this is [ not valid")


def test_request_from_toml_rejects_an_empty_items_list() -> None:
    with raises(PolicyRequestError):
        request_from_toml('title="x"\nrequested_by="y"\njustification="z"\nitems=[]\n')
