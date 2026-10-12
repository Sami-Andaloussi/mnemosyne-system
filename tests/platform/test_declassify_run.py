"""item 8 / D107 / D147 - the `make declassify` CLI wiring, the egress door's most critical path.

The audit of arc 3 flagged that ``declassify_run.main`` - where ``CONFIRM`` becomes ``human_validated=True``,
the non-overwrite guard, and "dry-run writes nothing" all live - had NO test. These drive ``main([...])`` in
``tmp_path`` (no repo touched): the gesture flag is honoured EXACTLY, the dry-run is side-effect-free, the
copy is non-destructive, and a self-audit / an existing target are refused fail-closed."""

from __future__ import annotations

import json

from mnemosyne.runtime.declassify_run import main


def _src(tmp_path, text="a deliverable born of sensible material"):
    p = tmp_path / "deliverable.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_dry_run_writes_nothing(tmp_path) -> None:
    """No ``--confirm`` -> exit 0, and NOTHING is written (the default is a pure preview, no egress)."""
    src = _src(tmp_path)
    out = tmp_path / "deliverable.public.md"
    assert main([str(src), "--producer", "frontier", "--verifier", "opus", "--out", str(out)]) == 0
    assert not out.exists()  # dry-run is side-effect-free
    assert not (tmp_path / "deliverable.public.md.provenance.json").exists()


def test_confirm_writes_a_public_copy_with_provenance_leaving_the_original_intact(
    tmp_path, monkeypatch
) -> None:
    """The gesture path: ``--confirm`` PLUS a live terminal 'OUI' writes the public copy (same bytes) + a
    provenance sidecar; the original file is never touched (non-destructive, D44 / D56). The terminal read
    is stubbed here (in-process); production still hits the real ``/dev/tty`` an agent-subprocess cannot."""
    monkeypatch.setattr(
        "mnemosyne.runtime.declassify_run._read_terminal_confirmation", lambda source: True
    )
    src = _src(tmp_path, "publishable once the distinct audit clears it")
    out = tmp_path / "pub.md"
    rc = main(
        [str(src), "--producer", "frontier", "--verifier", "opus", "--confirm", "--out", str(out)]
    )
    assert rc == 0
    assert (
        out.read_text(encoding="utf-8") == "publishable once the distinct audit clears it"
    )  # same bytes
    assert (
        src.read_text(encoding="utf-8") == "publishable once the distinct audit clears it"
    )  # ORIGINAL intact
    trace = json.loads((tmp_path / "pub.md.provenance.json").read_text(encoding="utf-8"))
    assert trace["producer"] == "frontier" and trace["verifier"] == "opus"
    assert trace["from_sensitivity"] == "sensible" and trace["to_sensitivity"] == "public"


def test_confirm_without_a_live_terminal_oui_aborts(tmp_path, monkeypatch) -> None:
    """The structural barrier (8b): ``--confirm`` alone is not enough - without a live 'OUI' at the terminal
    (here: no controlling terminal / not 'OUI') declassification ABORTS, exit 1, nothing written. This is
    what a headless agent hits: it cannot type the terminal gesture (D74 / D100, incapacity > trust)."""
    monkeypatch.setattr(
        "mnemosyne.runtime.declassify_run._read_terminal_confirmation", lambda source: False
    )
    src = _src(tmp_path)
    out = tmp_path / "pub.md"
    assert (
        main(
            [
                str(src),
                "--producer",
                "frontier",
                "--verifier",
                "opus",
                "--confirm",
                "--out",
                str(out),
            ]
        )
        == 1
    )
    assert not out.exists()
    assert not (tmp_path / "pub.md.provenance.json").exists()


def test_confirm_refuses_a_self_audit_and_writes_nothing(tmp_path) -> None:
    """``producer == verifier`` is refused at the audit gate (D100-6) - exit 1, no copy, even under confirm."""
    src = _src(tmp_path)
    out = tmp_path / "pub.md"
    assert (
        main([str(src), "--producer", "x", "--verifier", "x", "--confirm", "--out", str(out)]) == 1
    )
    assert not out.exists()


def test_confirm_refuses_to_overwrite_an_existing_target(tmp_path) -> None:
    """Non-destructive: an existing output is never clobbered (exit 1) - the original AND the target stand."""
    src = _src(tmp_path)
    out = tmp_path / "already.md"
    out.write_text("PRE-EXISTING - must not be overwritten", encoding="utf-8")
    assert (
        main(
            [
                str(src),
                "--producer",
                "frontier",
                "--verifier",
                "opus",
                "--confirm",
                "--out",
                str(out),
            ]
        )
        == 1
    )
    assert out.read_text(encoding="utf-8") == "PRE-EXISTING - must not be overwritten"


def test_a_missing_source_file_is_refused(tmp_path) -> None:
    """A non-existent source is refused at the door (exit 2), before any runtime is built."""
    assert main([str(tmp_path / "nope.md"), "--producer", "a", "--verifier", "b"]) == 2
