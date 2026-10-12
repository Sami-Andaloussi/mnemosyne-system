"""D159 - the `make policy-*` CLI: the whole demander/examiner/approuver/appliquer walk.

One end-to-end test drives all four verbs through `main()` exactly as the Makefile invokes them,
against a throwaway ledger AND a throwaway policy.toml copy - proof that the wiring (not just
each module in isolation) produces a real file change gated on a real "oui".
"""

from __future__ import annotations

import json
from pathlib import Path

from _pty import ask_over_a_real_pty
from mnemosyne.production.policy_requests import PolicyRequestLedger
from mnemosyne.runtime.policy_run import (
    _read_terminal_confirmation,
    main,
    render_examination_mandate,
    render_queue,
)


def _ask_over_a_real_pty(prompt: str, typed: bytes, *, timeout: float = 5.0) -> bool | None:
    """Call the REAL `_read_terminal_confirmation` against a REAL pty pair - not a monkeypatch.

    This is the test that was missing and let a real bug ship: `io.UnsupportedOperation: File or
    stream is not seekable`, raised the FIRST time a real human ever typed at this gate. Every other
    test here monkeypatches this function entirely, so none of them could have caught it; only
    exercising the real `/dev/tty` open/read/write path does.

    The harness itself now lives in ONE place (`tests/_pty.py`): a second caller of the same gate
    needed it, and a copied harness drifts exactly like the copied gate it was written to guard.
    """
    return ask_over_a_real_pty(_read_terminal_confirmation, prompt, typed, timeout=timeout)


def test_real_tty_confirmation_accepts_a_real_typed_oui() -> None:
    assert _ask_over_a_real_pty("Type OUI: ", b"OUI\n") is True


def test_real_tty_confirmation_rejects_a_real_typed_decline() -> None:
    assert _ask_over_a_real_pty("Type OUI: ", b"no thanks\n") is False


_MINI_POLICY = """[egress]
allowlist = ["www.youtube.com"]

[cloisonnement]
contracts = []

[domains]
"knowledge" = ["macro"]
"""

_REQUEST_TOML = """
title = "Example Research -- test"
requested_by = "example-research (test)"
justification = "measure public series with revisions"

[[items]]
kind = "egress"
values = ["api.stlouisfed.org"]
note = "FRED/ALFRED"
"""


def _run(argv: list[str]) -> int:
    return main(argv)


# --- rendering, in isolation -------------------------------------------------------------------
def test_render_queue_is_honest_when_empty() -> None:
    assert "No request filed" in render_queue(())


def test_render_mandate_carries_the_request_content_and_the_json_schema(tmp_path: Path) -> None:
    from mnemosyne.production.policy_requests import PolicyChangeRequest
    from mnemosyne.production.policy_writer import PolicyItem

    req = PolicyChangeRequest(
        title="Test title",
        items=(PolicyItem(kind="egress", values=("host.example",), note="reason"),),
        justification="because",
        requested_by="me",
    )
    ledger = PolicyRequestLedger(tmp_path / "l.jsonl")
    id_ = ledger.file(req)
    mandate = render_examination_mandate(ledger.state(id_))
    assert "Test title" in mandate
    assert "host.example" in mandate
    assert '"verdict"' in mandate
    assert "narrowed_items" in mandate


# --- the CLI, end to end -------------------------------------------------------------------------
def test_the_full_pipeline_walk(tmp_path: Path, capsys, monkeypatch) -> None:
    ledger_path = tmp_path / "requests.jsonl"
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(_MINI_POLICY, encoding="utf-8")
    request_path = tmp_path / "demande.toml"
    request_path.write_text(_REQUEST_TOML, encoding="utf-8")

    # 1. demander
    rc = _run(["--ledger", str(ledger_path), "demander", "--fichier", str(request_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Request filed" in out
    request_id = out.split("Request filed: ")[1].split(" ")[0]

    # 2. examiner - no verdict yet: prints the mandate, changes nothing
    rc = _run(["--ledger", str(ledger_path), "examiner", "--id", request_id])
    assert rc == 0
    assert "Adversarial examination mandate" in capsys.readouterr().out
    assert PolicyRequestLedger(ledger_path).state(request_id).stage == "depose"

    # 2b. examiner - record an "allow" verdict
    verdict_path = tmp_path / "verdict.json"
    verdict_path.write_text(
        json.dumps({"verdict": "allow", "notes": "legitimate host"}), encoding="utf-8"
    )
    rc = _run(
        [
            "--ledger",
            str(ledger_path),
            "examiner",
            "--id",
            request_id,
            "--verdict",
            str(verdict_path),
        ]
    )
    assert rc == 0
    assert PolicyRequestLedger(ledger_path).state(request_id).stage == "examine"

    # 3. approuver - no live terminal (an agent's exact situation, D159 post-incident hardening):
    # `_read_terminal_confirmation` is stubbed here (in-process); production hits the real
    # `/dev/tty` an agent subprocess cannot open (mirrors test_declassify_run.py's convention).
    monkeypatch.setattr(
        "mnemosyne.runtime.policy_run._read_terminal_confirmation", lambda prompt: False
    )
    rc = _run(["--ledger", str(ledger_path), "approuver", "--id", request_id])
    assert rc == 1
    assert PolicyRequestLedger(ledger_path).state(request_id).approved is False

    # 3b. approuver - a live "OUI" (the only thing an agent cannot forge: a real /dev/tty)
    monkeypatch.setattr(
        "mnemosyne.runtime.policy_run._read_terminal_confirmation", lambda prompt: True
    )
    # `--policy-path` is REQUIRED here now: approving WRITES, in the same gesture. Omit it and this
    # test reaches the real `system/config/policy.toml` - which the conftest barrier now refuses.
    rc = _run(
        [
            "--ledger",
            str(ledger_path),
            "approuver",
            "--id",
            request_id,
            "--policy-path",
            str(policy_path),
        ]
    )
    assert rc == 0
    state = PolicyRequestLedger(ledger_path).state(request_id)
    assert state.stage == "applique", "approuver WRITES in the same gesture (a single OUI, D159)"
    assert state.approved_content_hash  # recorded - but see the honesty test below on `by`

    # 4. the write landed with THAT single "OUI" - no second command, no second ceremony.
    written = policy_path.read_text(encoding="utf-8")
    assert "api.stlouisfed.org" in written
    assert "www.youtube.com" in written  # the pre-existing host survives

    # 5. queue reflects the final stage
    rc = _run(["--ledger", str(ledger_path), "queue"])
    assert rc == 0
    assert f"[applique] {request_id}" in capsys.readouterr().out

    # a second apply is refused - no double-write, even with a live "OUI" already stubbed true
    mtime_before = policy_path.stat().st_mtime_ns
    rc = _run(
        [
            "--ledger",
            str(ledger_path),
            "appliquer",
            "--id",
            request_id,
            "--policy-path",
            str(policy_path),
            "--confirm",
        ]
    )
    assert rc == 2
    assert policy_path.stat().st_mtime_ns == mtime_before


def test_approve_without_a_controlling_terminal_never_reaches_the_ledger(
    tmp_path: Path, monkeypatch
) -> None:
    """D159, post-incident hardening - the exact scenario that happened: an agent (no /dev/tty)
    must be refused BEFORE anything is journaled, never able to substitute a CLI argument."""
    ledger_path = tmp_path / "requests.jsonl"
    ledger = PolicyRequestLedger(ledger_path)
    from mnemosyne.production.policy_requests import PolicyChangeRequest
    from mnemosyne.production.policy_writer import PolicyItem

    id_ = ledger.file(
        PolicyChangeRequest(
            title="t",
            items=(PolicyItem(kind="egress", values=("h.example",)),),
            justification="j",
            requested_by="r",
        )
    )
    monkeypatch.setattr(
        "mnemosyne.runtime.policy_run._read_terminal_confirmation", lambda prompt: False
    )
    rc = _run(["--ledger", str(ledger_path), "approuver", "--id", id_])
    assert rc == 1
    assert PolicyRequestLedger(ledger_path).state(id_).stage == "depose"  # nothing journaled


def test_the_by_field_never_claims_an_unobserved_identity(tmp_path: Path, monkeypatch) -> None:
    """D159, post-incident hardening: the CLI's own `by=` must never hardcode a person's name -
    the incident was exactly `by="operator"` written for a gesture the code never actually observed
    coming from operator. The value it DOES record only describes the MECHANISM (a live terminal
    confirmation), never an identity the code has no way to verify."""
    ledger_path = tmp_path / "requests.jsonl"
    ledger = PolicyRequestLedger(ledger_path)
    from mnemosyne.production.policy_requests import PolicyChangeRequest
    from mnemosyne.production.policy_writer import PolicyItem

    id_ = ledger.file(
        PolicyChangeRequest(
            title="t",
            items=(PolicyItem(kind="egress", values=("h.example",)),),
            justification="j",
            requested_by="r",
        )
    )
    monkeypatch.setattr(
        "mnemosyne.runtime.policy_run._read_terminal_confirmation", lambda prompt: True
    )
    # `--policy-path` is NOT optional: approving WRITES. Omitting it aims this test at the real
    # `system/config/policy.toml` - which is exactly how `h.example` once landed in operator-managed
    # protected zone, invisible to git (the file is skip-worktree'd). The conftest barrier catches
    # it now; passing a throwaway target is what makes the barrier never have to.
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(_MINI_POLICY, encoding="utf-8")
    rc = _run(
        [
            "--ledger",
            str(ledger_path),
            "approuver",
            "--id",
            id_,
            "--policy-path",
            str(policy_path),
        ]
    )
    assert rc == 0
    raw = ledger_path.read_text(encoding="utf-8")
    approved_line = [ln for ln in raw.splitlines() if '"kind": "approved"' in ln][0]
    assert '"operator"' not in approved_line
    assert "/dev/tty" in approved_line


def test_refuser_records_a_reason_and_never_deletes_the_request(
    tmp_path: Path, monkeypatch
) -> None:
    ledger_path = tmp_path / "requests.jsonl"
    ledger = PolicyRequestLedger(ledger_path)
    from mnemosyne.production.policy_requests import PolicyChangeRequest
    from mnemosyne.production.policy_writer import PolicyItem

    id_ = ledger.file(
        PolicyChangeRequest(
            title="t",
            items=(PolicyItem(kind="egress", values=("h.example",)),),
            justification="j",
            requested_by="r",
        )
    )
    # no terminal => refused to even record a refusal (same gate, both directions)
    monkeypatch.setattr(
        "mnemosyne.runtime.policy_run._read_terminal_confirmation", lambda prompt: False
    )
    rc = _run(["--ledger", str(ledger_path), "refuser", "--id", id_, "--raison", "false positive"])
    assert rc == 1
    assert PolicyRequestLedger(ledger_path).state(id_).stage == "depose"

    monkeypatch.setattr(
        "mnemosyne.runtime.policy_run._read_terminal_confirmation", lambda prompt: True
    )
    rc = _run(
        [
            "--ledger",
            str(ledger_path),
            "refuser",
            "--id",
            id_,
            "--raison",
            "approval impersonation",
        ]
    )
    assert rc == 0
    state = PolicyRequestLedger(ledger_path).state(id_)
    assert state.stage == "refuse"
    assert state.refused_reason == "approval impersonation"


def test_refuser_requires_a_reason(tmp_path: Path) -> None:
    ledger_path = tmp_path / "requests.jsonl"
    ledger = PolicyRequestLedger(ledger_path)
    from mnemosyne.production.policy_requests import PolicyChangeRequest
    from mnemosyne.production.policy_writer import PolicyItem

    id_ = ledger.file(
        PolicyChangeRequest(
            title="t",
            items=(PolicyItem(kind="egress", values=("h.example",)),),
            justification="j",
            requested_by="r",
        )
    )
    rc = _run(["--ledger", str(ledger_path), "refuser", "--id", id_, "--raison", ""])
    assert rc == 2


def test_demander_without_fichier_creates_a_template_once(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "requests.jsonl"
    template_path = tmp_path / "modele.toml"
    rc = _run(["--ledger", str(ledger_path), "demander", "--template-path", str(template_path)])
    assert rc == 0
    assert template_path.exists()
    first_out = capsys.readouterr().out
    assert "Template created" in first_out

    # running again does not overwrite (non-destructive) - it just points back at it
    rc = _run(["--ledger", str(ledger_path), "demander", "--template-path", str(template_path)])
    assert rc == 0
    assert "already exists" in capsys.readouterr().out


def test_a_malformed_request_file_is_refused_cleanly(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "requests.jsonl"
    bad = tmp_path / "bad.toml"
    bad.write_text('title = "x"\n', encoding="utf-8")  # missing justification/items
    rc = _run(["--ledger", str(ledger_path), "demander", "--fichier", str(bad)])
    assert rc == 2
    assert "Request refused" in capsys.readouterr().err


def test_examining_an_unknown_id_is_refused_cleanly(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "requests.jsonl"
    rc = _run(["--ledger", str(ledger_path), "examiner", "--id", "unknown0000"])
    assert rc == 2
    assert "Unknown request" in capsys.readouterr().err
