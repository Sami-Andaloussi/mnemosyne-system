"""D155 / D86 — the ceiling stops being a comment and becomes a refusal.

``policy.toml`` promised "the spend counter cuts when a ceiling is hit" and no code read the value.
A decorative guarantee is worse than an absent one, so these tests hold the parts that make it real:
the four token classes are counted apart, an unpriced model is bounded rather than ignored, and a
breach RAISES rather than being logged.
"""

from __future__ import annotations

from pathlib import Path

from pytest import raises

from mnemosyne.guard.bounds import ResourceBoundError
from mnemosyne.production.spend import (
    CanonicalUsage,
    CostStatus,
    SpendLedger,
    price,
    render_spend,
)


class _Usage:
    """An Anthropic usage object, as the SDK shapes it."""

    def __init__(self, **fields: object) -> None:
        for name, value in fields.items():
            setattr(self, name, value)


# --- the four classes -------------------------------------------------------------------------
def test_cache_reads_and_writes_are_counted_apart_from_input() -> None:
    """Folding them into "input" is how a cached run gets misreported, always flatteringly."""
    usage = CanonicalUsage.from_anthropic(
        _Usage(
            input_tokens=100,
            output_tokens=50,
            cache_read_input_tokens=9000,
            cache_creation_input_tokens=400,
        )
    )

    assert (usage.input, usage.output, usage.cache_read, usage.cache_write) == (100, 50, 9000, 400)
    assert usage.total == 9550


def test_a_cached_call_is_priced_far_below_the_same_tokens_as_fresh_input() -> None:
    """The whole reason the split exists: same token count, an order of magnitude apart."""
    cached, _ = price("claude-haiku-4-5", CanonicalUsage(cache_read=1_000_000))
    fresh, _ = price("claude-haiku-4-5", CanonicalUsage(input=1_000_000))

    assert cached < fresh / 5


def test_a_missing_usage_field_degrades_to_zero_and_keeps_the_others() -> None:
    """A provider dropping a field must not stop the counting — that is its whole value."""
    usage = CanonicalUsage.from_anthropic(_Usage(input_tokens=10, output_tokens=None))

    assert usage.input == 10 and usage.output == 0


def test_a_usage_object_with_nothing_on_it_is_survivable() -> None:
    assert CanonicalUsage.from_anthropic(object()).total == 0
    assert CanonicalUsage.from_anthropic(None).total == 0


# --- honesty about the number ------------------------------------------------------------------
def test_a_computed_price_is_never_reported_as_actual() -> None:
    """No provider returns a cost here, and the euro rate is a dated constant. ESTIMATED, forever."""
    _, status = price("claude-haiku-4-5", CanonicalUsage(input=1000))

    assert status is CostStatus.ESTIMATED


def test_an_unknown_model_is_not_given_a_guessed_rate() -> None:
    cost, status = price("a-model-never-seen", CanonicalUsage(input=1_000_000))

    assert status is CostStatus.UNKNOWN
    assert cost == 0.0


def test_an_unpriced_call_makes_the_day_total_a_floor_not_a_truth(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    ledger.record("claude-haiku-4-5", CanonicalUsage(input=1000))
    ledger.record("a-model-never-seen", CanonicalUsage(input=5_000_000))

    today = ledger.spent()

    assert today.calls == 2
    assert today.unpriced_calls == 1
    assert not today.is_complete  # the report must not present this total as the truth


# --- the ceilings ------------------------------------------------------------------------------
def test_reaching_the_euro_ceiling_raises_rather_than_logs(tmp_path: Path) -> None:
    """The line policy.toml claimed for months: "the spend counter cuts when a ceiling is hit"."""
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    ledger.record("claude-opus-4-8", CanonicalUsage(input=2_000_000))  # ≈ 9,20 EUR

    ledger.check_ceilings(cost_ceiling_eur=50.0, token_ceiling=0)  # under: passes
    with raises(ResourceBoundError):
        ledger.check_ceilings(cost_ceiling_eur=5.0, token_ceiling=0)


def test_the_token_ceiling_is_what_bounds_a_model_with_no_known_price(tmp_path: Path) -> None:
    """The asymmetry that makes the design hold: euros bound the priced, tokens bound everything."""
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    ledger.record("a-model-never-seen", CanonicalUsage(input=300_000))

    ledger.check_ceilings(cost_ceiling_eur=5.0, token_ceiling=0)  # unpriced ⇒ euros see nothing
    with raises(ResourceBoundError):
        ledger.check_ceilings(cost_ceiling_eur=5.0, token_ceiling=200_000)


def test_an_unconfigured_ceiling_never_becomes_an_accidental_kill_switch(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    ledger.record("claude-opus-4-8", CanonicalUsage(input=9_000_000))

    ledger.check_ceilings(cost_ceiling_eur=0.0, token_ceiling=0)  # must not raise


def test_yesterdays_spend_does_not_block_today(tmp_path: Path) -> None:
    """A DAILY ceiling that summed the whole journal would seize up permanently after one big run."""
    path = tmp_path / "spend.jsonl"
    path.write_text(
        '{"at": "2020-01-01T10:00:00+00:00", "model": "claude-opus-4-8", "cost_eur": 999.0, '
        '"status": "estimated", "usage": {"input": 9000000, "output": 0, '
        '"cache_read": 0, "cache_write": 0}}\n'
    )
    ledger = SpendLedger(path)

    assert ledger.spent().cost_eur == 0.0
    ledger.check_ceilings(cost_ceiling_eur=5.0, token_ceiling=200_000)
    assert ledger.spent("2020-01-01").cost_eur == 999.0  # still readable, just not today's problem


# --- the journal -------------------------------------------------------------------------------
def test_a_charge_survives_the_process(tmp_path: Path) -> None:
    path = tmp_path / "spend.jsonl"
    SpendLedger(path).record("claude-haiku-4-5", CanonicalUsage(input=1000, output=500))

    assert SpendLedger(path).spent().calls == 1


def test_a_garbled_line_is_skipped_rather_than_fatal(tmp_path: Path) -> None:
    path = tmp_path / "spend.jsonl"
    ledger = SpendLedger(path)
    ledger.record("claude-haiku-4-5", CanonicalUsage(input=1000))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{this is not json\n\n")

    assert ledger.spent().calls == 1


def test_an_unwritable_journal_does_not_abort_a_call_that_already_succeeded(tmp_path: Path) -> None:
    """Fail-OPEN here, unlike the human-gesture journals — and the docstring says why.

    Failing closed would raise AFTER the paid request returned: money spent, work thrown away.
    """
    ledger = SpendLedger(tmp_path / "not-a-dir" / "x" / "spend.jsonl")
    (tmp_path / "not-a-dir").write_text("I am a file, not a directory")

    charge = ledger.record("claude-haiku-4-5", CanonicalUsage(input=1000))

    assert charge.persisted is False  # it says the row did not land…
    assert charge.status is CostStatus.ESTIMATED  # …without pretending it could not be PRICED
    assert charge.cost_eur > 0
    assert ledger.spent().calls == 0


def test_a_missing_journal_is_an_empty_day_not_an_error(tmp_path: Path) -> None:
    assert SpendLedger(tmp_path / "never-written.jsonl").spent().calls == 0


# --- the report --------------------------------------------------------------------------------
def test_an_empty_day_refuses_to_be_read_as_nothing_was_spent(tmp_path: Path) -> None:
    """The single most likely misreading of this tool, so the report pre-empts it."""
    report = render_spend(
        SpendLedger(tmp_path / "spend.jsonl").spent(), cost_ceiling_eur=5.0, token_ceiling=200_000
    )

    assert "Claude Code" in report and "subscription" in report


def test_the_report_shows_the_four_classes_and_flags_what_it_could_not_price(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    ledger.record("claude-haiku-4-5", CanonicalUsage(input=10, output=20, cache_read=30, cache_write=40))
    ledger.record("a-model-never-seen", CanonicalUsage(input=50))

    report = render_spend(ledger.spent(), cost_ceiling_eur=5.0, token_ceiling=200_000)

    assert "cache read 30" in report and "cache write 40" in report
    assert "FLOOR" in report  # the total is not presented as the truth
    assert "estimate" in report


# --- what the audit proved was unpinned, or plainly wrong --------------------------------------
def test_the_full_published_model_id_is_priced_not_treated_as_unknown() -> None:
    """``claude-haiku-4-5-20251001`` IS the default model's own published identifier.

    Undecorated lookup priced it at 0,00 € for ever, leaving the euro ceiling permanently blind on
    the very model the campaign runs on.
    """
    dated, status = price("claude-haiku-4-5-20251001", CanonicalUsage(input=1_000_000))
    bedrock, _ = price("anthropic.claude-opus-4-8", CanonicalUsage(input=1_000_000))
    plain, _ = price("claude-haiku-4-5", CanonicalUsage(input=1_000_000))

    assert status is CostStatus.ESTIMATED and dated == plain
    assert bedrock > 0
    assert price("claude-opus-4-7", CanonicalUsage(input=1_000_000))[1] is CostStatus.UNKNOWN


def test_the_report_names_which_ceiling_actually_binds() -> None:
    """Measured: 200 k tokens cap out at 4,60 €, under a 5 € ceiling — so euros can never fire.

    Printing "0.92 € out of a 5.00 € ceiling" without saying so invites reading 18 % of the budget
    where the truth is 100 % of the bound.

    Re-verified 2026-08-21 after the ``gpt-5.6-*`` rows joined the price table (D159): none of the
    three prices claude-opus-4-8 (25 $/Mtok output) as the table's dearest row — the closest,
    gpt-5.6-sol, is 20 $/Mtok — so this fact survives unchanged. It did NOT survive a first, wrong
    sol figure ($30/Mtok) this session briefly carried before a second fetch corrected it; this test
    caught that error.
    """
    from mnemosyne.production.spend import binding_ceiling

    which, at_eur = binding_ceiling(5.0, 200_000)

    assert which == "tokens"
    assert at_eur < 5.0


def test_one_negative_line_cannot_neutralise_both_ceilings(tmp_path: Path) -> None:
    """It drove the total to −999 999 950 € and let everything through — falsifying the docstring
    that claimed a corrupt journal "can only make the system think it has spent less"."""
    path = tmp_path / "spend.jsonl"
    ledger = SpendLedger(path)
    ledger.record("claude-opus-4-8", CanonicalUsage(input=2_000_000))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            '{"at": "%s", "model": "x", "cost_eur": -999999999.0, "status": "estimated", '
            '"usage": {"input": -999000000, "output": 0, "cache_read": 0, "cache_write": 0}}\n'
            % _today_iso()
        )

    with raises(ResourceBoundError):
        SpendLedger(path).check_ceilings(cost_ceiling_eur=5.0, token_ceiling=0)


def test_a_line_with_no_date_is_charged_to_today_not_lost_for_ever(tmp_path: Path) -> None:
    """One missing field used to hide a charge from every day there is — a forged-entry shape."""
    path = tmp_path / "spend.jsonl"
    path.write_text(
        '{"model": "claude-opus-4-8", "cost_eur": 999.0, "status": "estimated", '
        '"usage": {"input": 9000000, "output": 0, "cache_read": 0, "cache_write": 0}}\n'
    )

    assert SpendLedger(path).spent().calls == 1
    with raises(ResourceBoundError):
        SpendLedger(path).check_ceilings(cost_ceiling_eur=5.0, token_ceiling=0)


def test_a_valid_json_line_with_wrong_types_does_not_kill_the_paid_call(tmp_path: Path) -> None:
    """It raised ValueError/AttributeError BEFORE the request — production stopped, not overspend."""
    path = tmp_path / "spend.jsonl"
    path.write_text(
        '{"at": "%s", "cost_eur": "lots", "usage": ["not", "a", "dict"]}\n' % _today_iso()
        + '{"at": "%s", "cost_eur": 1.0, "usage": {"input": "lots"}}\n' % _today_iso()
    )
    ledger = SpendLedger(path)

    assert ledger.spent().calls == 2  # both counted, neither fatal
    ledger.check_ceilings(cost_ceiling_eur=5.0, token_ceiling=200_000)


def test_an_invalid_byte_does_not_poison_the_journal_for_ever(tmp_path: Path) -> None:
    """A write torn mid-character made every LATER call die with UnicodeDecodeError before spending."""
    path = tmp_path / "spend.jsonl"
    SpendLedger(path).record("claude-haiku-4-5", CanonicalUsage(input=1000))
    with path.open("ab") as handle:
        handle.write(b'{"at": "2026-07-20T10:00:00+00:00", "kind": "distill\xc3')

    assert SpendLedger(path).spent().calls >= 1
    SpendLedger(path).check_ceilings(cost_ceiling_eur=5.0, token_ceiling=200_000)


def test_a_byte_order_mark_does_not_swallow_the_first_charge(tmp_path: Path) -> None:
    path = tmp_path / "spend.jsonl"
    body = (
        '{"at": "%s", "model": "claude-haiku-4-5", "cost_eur": 9.2, "status": "estimated", '
        '"usage": {"input": 1000, "output": 0, "cache_read": 0, "cache_write": 0}}\n' % _today_iso()
    )
    path.write_bytes(b"\xef\xbb\xbf" + body.encode())

    assert SpendLedger(path).spent().calls == 1


def test_being_exactly_at_the_ceiling_already_refuses(tmp_path: Path) -> None:
    """"reached" means >=. The >= → > mutation was invisible to every earlier test."""
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    ledger.record("a-model-never-seen", CanonicalUsage(input=200_000))

    with raises(ResourceBoundError):
        ledger.check_ceilings(cost_ceiling_eur=0.0, token_ceiling=200_000)


def test_a_negative_ceiling_is_not_configured_not_a_veto(tmp_path: Path) -> None:
    ledger = SpendLedger(tmp_path / "spend.jsonl")

    ledger.check_ceilings(cost_ceiling_eur=-1.0, token_ceiling=-1)  # must not raise


def test_a_day_is_a_full_date_not_a_prefix(tmp_path: Path) -> None:
    """``--jour 2026-07`` silently reported a whole month under a day's label."""
    path = tmp_path / "spend.jsonl"
    path.write_text(
        '{"at": "2026-07-19T10:00:00+00:00", "cost_eur": 1.0, "usage": {}}\n'
        '{"at": "2026-07-20T10:00:00+00:00", "cost_eur": 2.0, "usage": {}}\n'
    )
    ledger = SpendLedger(path)

    assert ledger.spent("2026-07").calls == 0  # not "the whole month"
    assert ledger.spent("2026-07-19").calls == 1


def test_the_scope_warning_is_on_the_NON_empty_report_too(tmp_path: Path) -> None:
    """The dangerous misreading is not "0,00 € = nothing was spent" on an empty day — it is the
    operator reading a REAL figure and taking it for their whole day. Only the empty path was
    covered."""
    ledger = SpendLedger(tmp_path / "spend.jsonl")
    ledger.record("claude-haiku-4-5", CanonicalUsage(input=1000))

    report = render_spend(ledger.spent(), cost_ceiling_eur=5.0, token_ceiling=200_000)

    assert "Claude Code" in report and "subscription" in report


def _today_iso() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat()
