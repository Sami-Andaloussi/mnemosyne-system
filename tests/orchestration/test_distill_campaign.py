"""Frontier distillation CAMPAIGN - the Guard gate + fail-closed refusal, proven with NO key, NO cloud.

The safety-critical claim is the egress gate: the frontier backend is reachable ONLY for a label the
Guard's ``route_model`` routes to canal A (public), AND only when the host is allow-listed. A ``sensible``
label (route_model -> LOCAL) or an un-listed host must fail CLOSED - a ``sensible`` doc can never reach
Haiku. All exercised against fakes; the real ``anthropic`` wiring is confronted at the (3) pilot.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from _invariants import REPO_ROOT

# The distillateur scripts live outside the package path; put their dir on sys.path so `distill_campaign`
# and its sibling `distill_book` import naturally (exactly as when run as `make distill-batch`).
_SKILL_DIR = REPO_ROOT / "system" / "skills" / "distillateur"
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

import distill_campaign as dc  # noqa: E402

# the true bootstrap SUBMODULE (its `bootstrap` function is re-exported in runtime/__init__, so both
# `import ... as` and a string monkeypatch target resolve to the function, not the module - go via sys.modules)
import importlib  # noqa: E402

bootstrap_mod = importlib.import_module("mnemosyne.runtime.bootstrap")

from mnemosyne.ports import Channel, Sensitivity  # noqa: E402


class _FakePolicy:
    def __init__(self, *, egress: bool) -> None:
        self._egress = egress

    def egress_allowed(self, host: str | None) -> bool:
        return self._egress


class _FakeGuard:
    def __init__(self, channel: Channel) -> None:
        self._channel = channel
        self.routed: list[tuple] = []

    def route_model(self, inputs: tuple) -> Channel:
        self.routed.append(inputs)
        return self._channel


def _fake_rt(*, egress: bool, channel: Channel) -> SimpleNamespace:
    return SimpleNamespace(policy=_FakePolicy(egress=egress), guard=_FakeGuard(channel))


_LABEL = object()  # _egress_cleared passes it straight through to the fakes


# -- the safety core: _egress_cleared ---------------------------------------------------------


def test_egress_denied_when_host_not_allow_listed() -> None:
    ok, reason = dc._egress_cleared(
        _fake_rt(egress=False, channel=Channel.CANAL_A_PUBLIC_AUTO), _LABEL
    )
    assert ok is False
    assert "allow-list" in reason and "POLICY" in reason


def test_egress_denied_when_route_is_local_even_if_host_listed() -> None:
    # a non-public label routes LOCAL - the structural proof that `sensible` never reaches the cloud
    rt = _fake_rt(egress=True, channel=Channel.LOCAL)
    ok, reason = dc._egress_cleared(rt, _LABEL)
    assert ok is False
    assert "route_model" in reason
    assert rt.guard.routed == [(_LABEL,)]  # the Guard's own router made the call


def test_egress_cleared_only_for_public_canal_a_on_listed_host() -> None:
    ok, reason = dc._egress_cleared(
        _fake_rt(egress=True, channel=Channel.CANAL_A_PUBLIC_AUTO), _LABEL
    )
    assert ok is True
    assert reason == ""


def test_public_label_is_public_and_carries_the_domain() -> None:
    label = dc._public_label("macro")
    assert label.sensitivity is Sensitivity.PUBLIC
    assert "macro" in label.domains


# -- the campaign refuses / previews without a key --------------------------------------------


def _books(*names: str) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(mirror=Path(f"{n}.md"), domain="macro", rel=Path(f"{n}.md")) for n in names
    ]


def test_dry_run_lists_without_touching_the_cloud(monkeypatch, capsys) -> None:
    monkeypatch.setattr(dc, "_select_books", lambda *a, **k: _books("a", "b"))
    # if the cloud were touched, load_anthropic_backend (no key) would raise - assert it is NEVER called
    monkeypatch.setattr(
        "mnemosyne.runtime.runner_anthropic.load_anthropic_backend",
        lambda **k: _fail_cloud(),
    )
    rc = dc.run_campaign(dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out and "a.md" in out and "b.md" in out


def test_campaign_fails_closed_when_egress_not_cleared(monkeypatch, capsys) -> None:
    monkeypatch.setattr(dc, "_select_books", lambda *a, **k: _books("a"))
    # a stub runtime whose policy refuses the egress -> run_campaign must return 2 BEFORE any key is needed
    monkeypatch.setattr(
        bootstrap_mod,
        "bootstrap",
        lambda *a, **k: _fake_rt(egress=False, channel=Channel.CANAL_A_PUBLIC_AUTO),
    )
    monkeypatch.setattr(
        "mnemosyne.runtime.runner_anthropic.load_anthropic_backend",
        lambda **k: _fail_cloud(),
    )
    rc = dc.run_campaign()
    assert rc == 2
    assert "REFUSED" in capsys.readouterr().err


# -- selection: personal exclude + the small-file tripwire (audit MAJEUR-1) -------------------


def _bref(rel_str: str, *, domain: str = "macro", mirror: Path | None = None) -> SimpleNamespace:
    rel = Path(rel_str)
    return SimpleNamespace(
        rel=rel, mirror=mirror if mirror is not None else Path("/nonexistent") / rel, domain=domain
    )


def test_select_books_excludes_personal_family_by_default(monkeypatch) -> None:
    books = [_bref("Economics/Macro/macro/books/a.md"), _bref("General/Misc/misc/books/perso.md")]
    monkeypatch.setattr("mnemosyne.ingest.library.discover_books", lambda root: books)
    got = dc._select_books(Path("knowledge/raw"), domain=None, force=True, limit=None)
    rels = [str(b.rel) for b in got]
    assert any("Economics" in r for r in rels)
    assert not any(r.startswith("General") for r in rels)  # personal family excluded by default


def test_select_books_includes_personal_only_on_opt_in(monkeypatch) -> None:
    books = [_bref("General/Misc/misc/books/perso.md")]
    monkeypatch.setattr("mnemosyne.ingest.library.discover_books", lambda root: books)
    got = dc._select_books(
        Path("knowledge/raw"), domain=None, force=True, limit=None, include_personal=True
    )
    assert len(got) == 1  # the conscious override lets it through


def test_suspect_files_flags_small_source_but_not_a_short_md_guide(tmp_path) -> None:
    guide, small = tmp_path / "guide.md", tmp_path / "small.md"
    guide.write_bytes(b"x" * (dc._MIN_BOOK_BYTES + 1))  # a short but legit .md book - NOT flagged
    small.write_bytes(b"x" * 100)  # a stray note / artifact
    books = [_bref("d/books/guide.md", mirror=guide), _bref("d/books/small.md", mirror=small)]
    assert [s[0].mirror for s in dc._suspect_files(books)] == [small]


def test_suspect_files_flags_non_md_source_even_when_large(tmp_path) -> None:
    # the two known parasites are large-ish .txt session artifacts - caught by extension, not size
    txt = tmp_path / "COMPLETION_REPORT.txt"
    txt.write_bytes(b"x" * (dc._MIN_BOOK_BYTES * 4))
    assert dc._suspect_files([_bref("d/books/COMPLETION_REPORT.txt", mirror=txt)])


def _fail_cloud() -> object:
    raise AssertionError(
        "the cloud backend must not be built when the egress is not cleared / on dry-run"
    )
