"""D159 - policy_writer: targeted, format-preserving edits to the protected policy zone.

The filing report's own proof-of-done is Acme Research's REAL pending block (5 domains for the
``research`` bubble, one ``knowledge -> research`` contract, 10 egress hosts) applied to a COPY of the
REAL ``policy.toml`` and re-verified with the exact checks that block's own verification checklist
names. That end-to-end test is the anchor; the rest exercise every edge the splicing
logic has to get right on its own.

``system/config/policy.toml`` is held with ``git update-index --skip-worktree``: it carries a
per-machine local delta that is deliberately never committed, so its content ON DISK is not its
content IN GIT. Every expectation the end-to-end test makes about that file is therefore a DELTA
measured against the same copy's own ``before`` state - never an absolute count, never a
hard-coded host. The absolute forms (``len(egress_allowlist) == 11``, ``"www.youtube.com" in
egress_allowlist``) were facts about ONE machine's delta: green where they were written, red on
every fresh clone, whose committed ``allowlist`` is empty.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pytest import raises

from mnemosyne.production.policy_writer import (
    Applied,
    PolicyItem,
    PolicyWriteError,
    add_contract,
    add_domain_values,
    add_egress_hosts,
    apply_items,
    apply_to_file,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_POLICY = _REPO_ROOT / "system" / "config" / "policy.toml"


# --- PolicyItem validation: fail fast, at construction ------------------------------------------
def test_an_egress_item_needs_at_least_one_host() -> None:
    with raises(PolicyWriteError):
        PolicyItem(kind="egress", values=())


def test_a_domains_item_needs_a_bubble_and_values() -> None:
    with raises(PolicyWriteError):
        PolicyItem(kind="domains", bubble="", values=("macro",))
    with raises(PolicyWriteError):
        PolicyItem(kind="domains", bubble="research", values=())


def test_a_contract_item_needs_both_ends() -> None:
    with raises(PolicyWriteError):
        PolicyItem(kind="contract", contract_from="knowledge", contract_to="")


def test_items_cannot_mix_fields_across_kinds() -> None:
    with raises(PolicyWriteError):
        PolicyItem(kind="egress", values=("host.example",), bubble="research")
    with raises(PolicyWriteError):
        PolicyItem(kind="contract", contract_from="a", contract_to="b", values=("x",))


def test_an_unsafe_token_is_refused_not_smuggled_into_toml() -> None:
    with raises(PolicyWriteError):
        PolicyItem(kind="egress", values=('evil"] # \n[egress',))
    with raises(PolicyWriteError):
        PolicyItem(kind="domains", bubble="research", values=("has space",))


def test_unknown_kind_is_refused() -> None:
    with raises(PolicyWriteError):
        PolicyItem(kind="model_routing", values=("x",))


def test_a_control_character_in_a_note_is_refused() -> None:
    """D75 post-audit fix: a raw ESC/form-feed passed a bare newline check but broke the TOML
    comment it becomes (or, worse, could inject terminal escapes into whatever prints it)."""
    with raises(PolicyWriteError):
        PolicyItem(kind="egress", values=("host.example",), note="reason\x0cwith a form-feed")
    with raises(PolicyWriteError):
        PolicyItem(kind="egress", values=("host.example",), note="\x1b[31mred")


# --- egress: append to the existing single-line allowlist ---------------------------------------
_MINI_EGRESS = """[egress]
allowlist = ["www.youtube.com"]  # 2026-07-17 (user gesture) -- existing note

[domains]
"knowledge" = ["macro"]
"""


def test_egress_appends_new_hosts_and_keeps_the_existing_one() -> None:
    text, added = add_egress_hosts(_MINI_EGRESS, ("api.stlouisfed.org", "api.bls.gov"))
    assert added == ("api.stlouisfed.org", "api.bls.gov")
    parsed = tomllib.loads(text)
    assert parsed["egress"]["allowlist"] == ["www.youtube.com", "api.stlouisfed.org", "api.bls.gov"]
    assert "2026-07-17 (user gesture)" in text  # the pre-existing comment survives untouched


def test_egress_is_idempotent_on_a_host_already_present() -> None:
    text, added = add_egress_hosts(_MINI_EGRESS, ("www.youtube.com",))
    assert added == ()
    assert text == _MINI_EGRESS  # byte-identical no-op


def test_egress_carries_a_trailing_comment_on_the_last_new_line() -> None:
    text, _ = add_egress_hosts(_MINI_EGRESS, ("api.bls.gov",), comment="request abc123")
    assert '"api.bls.gov"  # request abc123' in text


def test_egress_on_an_empty_array() -> None:
    text = "[egress]\nallowlist = []\n"
    new_text, added = add_egress_hosts(text, ("host.example",))
    assert added == ("host.example",)
    assert tomllib.loads(new_text)["egress"]["allowlist"] == ["host.example"]


def test_egress_handles_a_pre_existing_trailing_comma() -> None:
    text = '[egress]\nallowlist = [\n  "a",\n]\n'
    new_text, added = add_egress_hosts(text, ("b",))
    assert added == ("b",)
    assert tomllib.loads(new_text)["egress"]["allowlist"] == ["a", "b"]


def test_egress_handles_a_trailing_comma_hidden_behind_a_comment() -> None:
    """D75 post-audit fix: the array's last real token WAS a comma, but a comment sat between it
    and the newline - `inner.rstrip()` alone never saw the comma, so it inserted a SECOND one,
    producing an empty array slot (invalid TOML). This is the exact shape of the REAL
    `[domains] "knowledge"` array (see the end-to-end test below), reproduced in isolation."""
    text = '[egress]\nallowlist = [\n  "a",  # a comment with an apostrophe: it\'s right here\n]\n'
    new_text, added = add_egress_hosts(text, ("b",))
    assert added == ("b",)
    assert tomllib.loads(new_text)["egress"]["allowlist"] == ["a", "b"]
    assert tomllib.loads(new_text)["egress"]["allowlist"] == ["a", "b"]


def test_egress_section_missing_raises() -> None:
    with raises(PolicyWriteError):
        add_egress_hosts("[domains]\n", ("h",))


# --- domains: new bubble vs. extending an existing one -------------------------------------------
_MINI_DOMAINS = """[domains]
"knowledge" = [
  "macro", "commodities",
]

# --- Per-domain recall floor ---
[recall_floor]
"""


def test_domains_declares_a_brand_new_bubble_after_the_last_entry_not_before_the_next_comment() -> (
    None
):
    text, added = add_domain_values(_MINI_DOMAINS, "research", ("macro", "microeconomics"))
    assert added == ("macro", "microeconomics")
    parsed = tomllib.loads(text)
    assert parsed["domains"]["research"] == ["macro", "microeconomics"]
    assert parsed["domains"]["knowledge"] == ["macro", "commodities"]  # untouched
    # the new bubble line lands BEFORE the next section's comment preamble, not after it
    research_pos = text.index('"research"')
    comment_pos = text.index("Per-domain recall floor")
    assert research_pos < comment_pos


def test_domains_unions_new_values_into_an_existing_bubble() -> None:
    text, added = add_domain_values(_MINI_DOMAINS, "knowledge", ("macro", "statistics"))
    assert added == ("statistics",)  # macro already there - only the new one is reported
    assert tomllib.loads(text)["domains"]["knowledge"] == ["macro", "commodities", "statistics"]


def test_domains_is_a_noop_when_every_value_already_declared() -> None:
    text, added = add_domain_values(_MINI_DOMAINS, "knowledge", ("macro",))
    assert added == ()
    assert text == _MINI_DOMAINS


def test_domains_extends_an_array_whose_comma_hides_behind_a_comment() -> None:
    """The egress twin of this case has its own test above; this is the DOMAINS one. It used to
    be exercised ONLY through the real-file test at the bottom - that is, only on a machine whose
    never-committed local delta happens to end the `"knowledge"` array with `"runtime",  # veille
    d'outils -> ...`, a comma whose newline a comment sits in front of. The committed file ends
    that array `"optimization",` with no trailing comment, so on any fresh clone the shape went
    untested while the suite still reported green. Owned fixture, so it bites everywhere."""
    text = '[domains]\n"knowledge" = [\n  "macro",  # veille d\'outils -> Software/Tooling\n]\n'
    new_text, added = add_domain_values(text, "knowledge", ("robotics",))
    assert added == ("robotics",)
    assert tomllib.loads(new_text)["domains"]["knowledge"] == ["macro", "robotics"]


def test_a_second_new_bubble_lands_after_the_first_one_added() -> None:
    once, _ = add_domain_values(_MINI_DOMAINS, "research", ("macro",))
    twice, _ = add_domain_values(once, "trading2", ("crypto",))
    parsed = tomllib.loads(twice)
    assert parsed["domains"]["research"] == ["macro"]
    assert parsed["domains"]["trading2"] == ["crypto"]
    assert (
        twice.index('"research"')
        < twice.index('"trading2"')
        < twice.index("Per-domain recall floor")
    )


# --- contracts: the empty sentinel, then repeat additions ----------------------------------------
_MINI_CLOISONNEMENT = """[cloisonnement]
contracts = []

# --- Declared domains ---
[domains]
"knowledge" = ["macro"]
"""


def test_first_contract_ever_replaces_the_empty_sentinel() -> None:
    text, added = add_contract(_MINI_CLOISONNEMENT, "knowledge", "research")
    assert added is True
    parsed = tomllib.loads(text)
    assert parsed["cloisonnement"]["contracts"] == [{"from": "knowledge", "to": "research"}]
    assert "contracts = []" not in text


def test_a_second_contract_is_appended_after_the_first_not_after_the_comment() -> None:
    once, _ = add_contract(_MINI_CLOISONNEMENT, "knowledge", "research")
    twice, added = add_contract(once, "knowledge", "soin")
    assert added is True
    parsed = tomllib.loads(twice)
    assert {"from": "knowledge", "to": "research"} in parsed["cloisonnement"]["contracts"]
    assert {"from": "knowledge", "to": "soin"} in parsed["cloisonnement"]["contracts"]
    assert len(parsed["cloisonnement"]["contracts"]) == 2
    assert (
        twice.index('to   = "research"')
        < twice.index('to   = "soin"')
        < twice.index("Declared domains")
    )


def test_a_second_contract_after_a_NOTED_first_one_still_works() -> None:
    """D75 post-audit fix: `_CONTRACT_HEADER_RE` did not allow the trailing comment `add_contract`
    itself writes when a note is given - so a first contract WITH a note (exactly the shape of the
    real Acme Research request) made every later contract addition raise, having lost the `contracts
    = []` sentinel it was replacing and unable to find its own header to append after."""
    once, _ = add_contract(_MINI_CLOISONNEMENT, "knowledge", "research", comment="first note")
    assert "[[cloisonnement.contracts]]  # first note" in once
    twice, added = add_contract(once, "knowledge", "soin")
    assert added is True
    parsed = tomllib.loads(twice)
    assert len(parsed["cloisonnement"]["contracts"]) == 2


def test_contract_is_idempotent_on_the_exact_same_pair() -> None:
    once, _ = add_contract(_MINI_CLOISONNEMENT, "knowledge", "research")
    twice, added = add_contract(once, "knowledge", "research")
    assert added is False
    assert twice == once


def test_contract_direction_matters_the_reverse_pair_is_a_new_addition() -> None:
    once, _ = add_contract(_MINI_CLOISONNEMENT, "knowledge", "research")
    twice, added = add_contract(once, "research", "knowledge")
    assert added is True
    parsed = tomllib.loads(twice)
    assert len(parsed["cloisonnement"]["contracts"]) == 2


def test_contract_section_missing_both_sentinel_and_blocks_raises() -> None:
    with raises(PolicyWriteError):
        add_contract("[domains]\n", "knowledge", "research")


# --- the fail-closed regression net --------------------------------------------------------------
def test_apply_items_orders_multiple_kinds_in_one_bundle() -> None:
    items = (
        PolicyItem(kind="domains", bubble="research", values=("macro",)),
        PolicyItem(kind="contract", contract_from="knowledge", contract_to="research"),
        PolicyItem(kind="egress", values=("api.stlouisfed.org",)),
    )
    text = (
        '[egress]\nallowlist = ["www.youtube.com"]\n\n'
        "[cloisonnement]\ncontracts = []\n\n"
        '[domains]\n"knowledge" = ["macro"]\n'
    )
    new_text, applied = apply_items(text, items)
    assert applied.domains_added == (("research", ("macro",)),)
    assert applied.contracts_added == (("knowledge", "research"),)
    assert applied.egress_added == ("api.stlouisfed.org",)
    assert not applied.is_noop


def test_verify_write_landed_catches_each_kind_of_missing_value(tmp_path: Path) -> None:
    """Each write claim is verified directly; the integration test proves the call path from
    `apply_to_file`."""
    from mnemosyne.production.policy_writer import Applied, _verify_write_landed

    claims = (
        Applied(egress_added=("never-written.example",)),
        Applied(domains_added=(("research", ("never-written",)),)),
        Applied(contracts_added=(("nope", "research"),)),
    )
    for i, claimed in enumerate(claims):
        path = tmp_path / f"policy-{i}.toml"
        path.write_text(_MINI_EGRESS, encoding="utf-8")
        with raises(PolicyWriteError):
            _verify_write_landed(path, claimed)


def test_apply_to_file_refuses_when_something_overwrites_it_right_after_the_write(
    tmp_path: Path, monkeypatch
) -> None:
    """The exact incident, simulated: something (a concurrent process, a manual revert) races
    this write and reverts the file to its ORIGINAL content immediately after the atomic
    replace. Without the post-write re-read, `apply_to_file` would return a clean `Applied` and
    the caller would record "applied" for a change the disk no longer carries."""
    import mnemosyne.production.policy_writer as pw

    path = tmp_path / "policy.toml"
    original = _MINI_EGRESS
    path.write_text(original, encoding="utf-8")

    real_replace = Path.replace

    def racing_replace(self: Path, target):
        real_replace(self, target)
        Path(target).write_text(original, encoding="utf-8")  # a "concurrent" revert, right after

    monkeypatch.setattr(Path, "replace", racing_replace)
    with raises(PolicyWriteError):
        pw.apply_to_file(path, (PolicyItem(kind="egress", values=("api.bls.gov",)),))
    assert path.read_text(encoding="utf-8") == original  # the race's own write, left as-is


def test_apply_to_file_is_atomic_and_noop_leaves_the_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "policy.toml"
    path.write_text(_MINI_EGRESS, encoding="utf-8")
    mtime_before = path.stat().st_mtime_ns
    applied = apply_to_file(path, (PolicyItem(kind="egress", values=("www.youtube.com",)),))
    assert applied.is_noop
    assert path.stat().st_mtime_ns == mtime_before  # never rewritten for a no-op


def test_apply_to_file_writes_and_is_readable_by_a_fresh_read(tmp_path: Path) -> None:
    path = tmp_path / "policy.toml"
    path.write_text(_MINI_EGRESS, encoding="utf-8")
    applied = apply_to_file(path, (PolicyItem(kind="egress", values=("api.bls.gov",)),))
    assert applied.egress_added == ("api.bls.gov",)
    assert "api.bls.gov" in tomllib.loads(path.read_text(encoding="utf-8"))["egress"]["allowlist"]
    assert not path.with_suffix(".toml.tmp").exists()  # the temp file never lingers


def test_apply_to_file_refuses_an_already_broken_original(tmp_path: Path) -> None:
    """D75 post-audit fix: a raw `tomllib.TOMLDecodeError` must never reach the CLI as an
    unhandled traceback - it is wrapped as our own `PolicyWriteError`."""
    path = tmp_path / "policy.toml"
    path.write_text("this is [ not valid toml", encoding="utf-8")
    with raises(PolicyWriteError):
        apply_to_file(path, (PolicyItem(kind="egress", values=("h",)),))


def test_apply_to_file_wraps_a_transform_that_would_produce_invalid_toml(
    tmp_path: Path, monkeypatch
) -> None:
    """If a future splicer bug ever produced invalid TOML, it must surface as PolicyWriteError,
    not a raw TOMLDecodeError - proven by forcing exactly that with a monkeypatched apply_items."""
    import mnemosyne.production.policy_writer as pw

    path = tmp_path / "policy.toml"
    path.write_text(_MINI_EGRESS, encoding="utf-8")
    monkeypatch.setattr(
        pw, "apply_items", lambda text, items: ("this becomes [ broken", Applied(("x",)))
    )
    with raises(PolicyWriteError):
        pw.apply_to_file(path, (PolicyItem(kind="egress", values=("h",)),))


def test_a_regression_in_the_transform_is_refused_before_any_write() -> None:
    """Directly prove the safety net fires: hand-craft a `before` that has content and an `after`
    that DROPPED it (simulating a hypothetical bug in a splicer), and confirm the check raises."""
    from mnemosyne.production.policy_writer import _assert_no_regression

    before = '[egress]\nallowlist = ["a", "b"]\n'
    after = '[egress]\nallowlist = ["a"]\n'  # "b" vanished
    with raises(PolicyWriteError):
        _assert_no_regression(before, after)


# --- the end-to-end proof: a REAL pending block against a COPY of the REAL file -----------------
#: The bundle exactly as the requesting project filed it, named once so the assertions below can be DERIVED from
#: it instead of restating its size as a literal (a literal is what pinned `== 11`).
_RESEARCH_DOMAINS = ("macro", "commodities", "microeconomics", "econometrics", "statistics")
_RESEARCH_HOSTS = (
    "api.stlouisfed.org",
    "api.bls.gov",
    "apps.bea.gov",
    "ec.europa.eu",
    "api.worldbank.org",
    "sdmx.oecd.org",
    "comtradeapi.un.org",
    "www.sec.gov",
    "data.sec.gov",
    "publicreporting.cftc.gov",
)
#: Targets for the two "does a SECOND write still splice?" probes below. They must be values the
#: real file cannot already declare, on ANY machine: if a local delta happened to carry them, the
#: probe would silently apply nothing and assert its way to green while proving nothing.
_PROBE_BUBBLE = "zz-probe-second-contract"
_PROBE_DOMAIN = "zz-probe-appended-domain"


def test_the_real_research_block_applies_cleanly_to_a_copy_of_the_real_policy_toml(
    tmp_path: Path,
) -> None:
    """This is proof-of-done #1 from the filing report, automated: the exact bundle from a real
    historical policy-change request for the Acme Research project, applied to a faithful COPY of
    the real `system/config/policy.toml`, re-checked against that request's own verification
    checklist expectations - the 5 research domains, contract True, reverse False, the 10 hosts,
    routing untouched.

    Read every expectation as a UNION: the end state is the start state plus exactly what was
    asked, and the ledger names exactly what was MISSING from the start state. That phrasing is
    true whatever the copy starts with, which is the point - `system/config/policy.toml` is held
    with `git update-index --skip-worktree`, so the file on disk carries a per-machine delta that
    git does not have. The earlier absolute forms (`len(policy.egress_allowlist) == 11`, and
    `"www.youtube.com" in policy.egress_allowlist`) described one machine's delta: on the
    committed file, whose `allowlist` is empty, they read 10 and absent."""
    copy_path = tmp_path / "policy.toml"
    copy_path.write_text(_REAL_POLICY.read_text(encoding="utf-8"), encoding="utf-8")

    from mnemosyne.config import load_policy
    from mnemosyne.ports import Bubble, Domain, Sensitivity

    research, knowledge = Bubble("research"), Bubble("knowledge")
    want_hosts = frozenset(_RESEARCH_HOSTS)
    want_domains = frozenset(Domain(d) for d in _RESEARCH_DOMAINS)

    # Measured through the JUDGE's own accessor, on the very text about to be spliced.
    before = load_policy(copy_path)
    missing_hosts = want_hosts - before.egress_allowlist
    missing_domains = want_domains - before.declared_domains.get(research, frozenset())
    contract_missing = not before.cross_bubble_allowed(knowledge, research)

    items = (
        PolicyItem(kind="domains", bubble="research", values=_RESEARCH_DOMAINS),
        PolicyItem(
            kind="contract",
            contract_from="knowledge",
            contract_to="research",
            note="research 2026-07-26 (D159) -- read-only, one-way",  # matches the REAL filed request
        ),
        PolicyItem(kind="egress", values=_RESEARCH_HOSTS),
    )
    applied = apply_to_file(copy_path, items)
    policy = load_policy(copy_path)

    # The ledger reports exactly what was missing - no less (nothing skipped that wasn't already
    # there) and no more (already-present values are never re-announced as new).
    assert frozenset(applied.egress_added) == missing_hosts
    assert (
        frozenset(
            Domain(v)
            for bubble, values in applied.domains_added
            if bubble == "research"
            for v in values
        )
        == missing_domains
    )
    assert (("knowledge", "research") in applied.contracts_added) is contract_missing
    assert applied.is_noop == (not missing_hosts and not missing_domains and not contract_missing)

    # The verification checklist, applied as unions rather than counts.
    assert policy.egress_allowlist == before.egress_allowlist | want_hosts
    assert policy.declared_domains.get(research, frozenset()) == (
        before.declared_domains.get(research, frozenset()) | want_domains
    )
    assert policy.cross_bubble_allowed(knowledge, research) is True
    assert policy.cross_bubble_allowed(research, knowledge) is False  # direction still matters
    # Nothing was dropped: the bundle names no `knowledge` domain, so that bubble must survive the
    # splice EXACTLY equal - strictly stronger than spot-checking one domain, and indifferent to
    # which domains a given machine's file happens to declare. (The committed file declares
    # `"finance"`; a configuration delta can drop it - that is precisely the kind of fact no assertion
    # here may depend on.)
    assert policy.declared_domains.get(knowledge, frozenset()) == before.declared_domains.get(
        knowledge, frozenset()
    )
    assert policy.canal_a_auto == before.canal_a_auto  # a policy WRITE never touches routing
    # Deliberately absolute, and the only assertion left that reads the real file's content: a
    # widened canal_a_auto is an invariant-1 alarm (inv. 1, sensible-local), so it should be loud
    # wherever it happens rather than machine-dependently silent. Green on both the committed file
    # and this machine's delta, measured.
    assert sorted(s.value for s in policy.canal_a_auto) == [Sensitivity.PUBLIC.value]

    # D75 post-audit fix, proven on the REAL file: a SECOND contract after the first one (which
    # carries a note, exactly like the real request above) must still apply - BLOQUANT 3.
    twice = apply_to_file(
        copy_path,
        (PolicyItem(kind="contract", contract_from="knowledge", contract_to=_PROBE_BUBBLE),),
    )
    assert twice.contracts_added == (("knowledge", _PROBE_BUBBLE),)
    assert load_policy(copy_path).cross_bubble_allowed(knowledge, Bubble(_PROBE_BUBBLE)) is True

    # D75 post-audit fix, proven on the REAL file: extending the PRE-EXISTING "knowledge" bubble
    # must not double a trailing comma into an invalid, empty array slot - BLOQUANT 2. This is the
    # one case the DOMAINS proof above never exercises (it only ever adds a BRAND NEW bubble,
    # never extends an EXISTING array). The nastiest shape of that array - a comma hidden behind a
    # trailing comment - is only present on a machine whose local delta puts it there, so it has
    # its own owned-fixture test above; what THIS one proves is that the extension lands on
    # whatever shape the real file actually has.
    thrice = apply_to_file(
        copy_path, (PolicyItem(kind="domains", bubble="knowledge", values=(_PROBE_DOMAIN,)),)
    )
    assert thrice.domains_added == (("knowledge", (_PROBE_DOMAIN,)),)
    reloaded = load_policy(copy_path)
    assert reloaded.declared_domains.get(knowledge, frozenset()) == (
        before.declared_domains.get(knowledge, frozenset()) | {Domain(_PROBE_DOMAIN)}
    )
