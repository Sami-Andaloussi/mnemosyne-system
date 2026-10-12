"""(3)-6b - the sole-importer BRICK ADAPTERS behind the ops couture (sorties / secrets / backup / obs).

Biting tests for the six adapters that plug real bricks behind the (3)-6a couture, WITHOUT any brick
installed (D126): the injectable executor / runner / client / analyzer / disk-usage seams make each
translation exercisable in CI, and the pure brick-free helpers (fmt normalisation, vault parsing,
snapshot-id parsing, entity->sensitivity mapping, disk math) are unit-tested directly. The governance is
NOT here (it lives in the couture, D100): these tests prove the adapters TRANSLATE faithfully and stay
fail-safe - a raise-only PII sensor, a swallowing observability sink, a fail-safe hardware probe - never
that a brick decides a label.

Plus an encapsulation guard (mirroring ``test_invariants.py::test_invariant_20_...``, self-contained):
after ``import mnemosyne`` + ``bootstrap()`` NONE of the python-import bricks is in ``sys.modules``, and
each new adapter module imports safely with the brick absent (D103 / invariant 20 / D126).

Decisions: D103 (sole importer)  -  D126 (brick-free suite)  -  D100 (governance is the couture's, not the
brick's)  -  D101 / invariant 18 (raise-only PII)  -  D111 (fail-safe observability + health). Code &
docstrings English (D117).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _invariants import REPO_ROOT, direct_imports_of
from pytest import raises

import mnemosyne
from mnemosyne.guard.secrets_sops import (
    _parse_flat_secrets,
    connect_sops_age,
)
from mnemosyne.ingest.pii_presidio import (
    _sensitivity_for_entities,
    connect_presidio_sensor,
)
from mnemosyne.ports import Bubble, GovernanceLabel, RenderRequest, Sensitivity, SnapshotId, TraceId
from mnemosyne.runtime.backup_kopia import (
    _parse_snapshot_id,
    connect_kopia,
)
from mnemosyne.runtime.bootstrap import bootstrap
from mnemosyne.runtime.health_probe import (
    SystemHardwareProbe,
    _disk_free_ratio,
)
from mnemosyne.runtime.observability import LocalObservability, fan_out
from mnemosyne.runtime.observability_jsonl import _line_to_record, open_jsonl_sink
from mnemosyne.runtime.observability_langfuse import connect_langfuse
from mnemosyne.runtime.render_typst import _typst_format, connect_typst

MNEMOSYNE_ROOT = REPO_ROOT / "system" / "lib" / "mnemosyne"


# --------------------------------------------------------------------------- #
# 1. Typst renderer - translation via injected executor + pure fmt normaliser #
# --------------------------------------------------------------------------- #
def test_typst_format_normalises_and_defaults() -> None:
    # pure, brick-free: lower-case, strip a leading dot, default to pdf, refuse the unknown.
    assert _typst_format("PDF") == "pdf"
    assert _typst_format(".svg") == "svg"
    assert _typst_format("  png ") == "png"
    assert _typst_format("") == "pdf"  # unspecified -> the portable default (D108)
    with raises(ValueError):
        _typst_format("docx")  # an unknown format is refused, never wrong bytes emitted (D108-(2))


def test_typst_render_carries_the_compiled_bytes() -> None:
    # injected executor stands in for typst.compile: the adapter passes the SOURCE + normalised format
    # and wraps the returned bytes verbatim in a RenderResult - no governance here (D100).
    calls: list[tuple[bytes, str]] = []

    def fake_compile(source: bytes, *, format: str) -> bytes:  # noqa: A002 - mirrors typst's kwarg
        calls.append((source, format))
        return b"%PDF-fake-bytes"

    renderer = connect_typst(executor=fake_compile)
    result = renderer.render(RenderRequest(body="= Title\nbody", fmt="PDF", title="t"))
    assert result.fmt == "pdf"
    assert result.artifact == b"%PDF-fake-bytes"
    # the body was passed as UTF-8 bytes and the format was normalised before the compiler saw it.
    assert calls == [(b"= Title\nbody", "pdf")]


def test_typst_render_propagates_compile_failure() -> None:
    # a compile error is NOT swallowed into a fabricated artifact - it surfaces to the couture (D108-(2)).
    def boom(_source: bytes, *, format: str) -> bytes:  # noqa: A002
        raise RuntimeError("typst boom")

    with raises(RuntimeError):
        connect_typst(executor=boom).render(RenderRequest(body="x", fmt="pdf"))


# --------------------------------------------------------------------------- #
# 2. SOPS/age decryptor - arg-building + flat-map parsing via injected runner  #
# --------------------------------------------------------------------------- #
def test_sops_parse_flat_secrets_pure() -> None:
    # pure parser: a flat JSON object -> handle->str map; a scalar non-string is stringified.
    parsed = _parse_flat_secrets(b'{"api": "sk-1", "port": 5432}')
    assert parsed == {"api": "sk-1", "port": "5432"}


def test_sops_parse_rejects_nested_and_null() -> None:
    # a nested value or a null is an ambiguous / empty vault -> RAISE (the couture fail-closes empty, D100).
    with raises(ValueError):
        _parse_flat_secrets(b'{"db": {"user": "x"}}')  # nested object
    with raises(ValueError):
        _parse_flat_secrets(b'{"k": null}')  # empty secret
    with raises(ValueError):
        _parse_flat_secrets(b"not json at all")  # un-parseable plaintext


def test_sops_decryptor_builds_command_and_parses_via_runner() -> None:
    # the returned decryptor (SecretDecryptor shape) runs `sops --decrypt --output-type json <vault>`
    # via the injected runner and parses its stdout into the flat map.
    seen: list[list[str]] = []

    def fake_runner(argv: list[str]) -> bytes:
        seen.append(argv)
        return b'{"token": "secret-value"}'

    decrypt = connect_sops_age(runner=fake_runner)
    result = decrypt(b"ENC[vault-ciphertext]")
    assert result == {"token": "secret-value"}
    # the argv is the sops decrypt command, ending in the (temp) vault path the adapter spooled.
    assert len(seen) == 1
    argv = seen[0]
    assert argv[:4] == ["sops", "--decrypt", "--output-type", "json"]
    assert argv[-1].endswith(".vault")


def test_sops_decryptor_raises_on_runner_failure() -> None:
    # a non-zero exit (runner raising) propagates - the couture turns it into a fail-closed empty broker.
    def failing_runner(_argv: list[str]) -> bytes:
        raise RuntimeError("sops: no matching key")

    with raises(RuntimeError):
        connect_sops_age(runner=failing_runner)(b"ENC[...]")


# --------------------------------------------------------------------------- #
# 3. Kopia engine - argv-building + snapshot-id parsing via injected runner    #
# --------------------------------------------------------------------------- #
def test_kopia_parse_snapshot_id_pure() -> None:
    # pure parser: reads the id out of `--json` create output (top-level id, list, or rootID).
    assert _parse_snapshot_id(b'{"id": "abc123"}') == SnapshotId("abc123")
    assert _parse_snapshot_id(b'[{"id": "first"}]') == SnapshotId("first")
    assert _parse_snapshot_id(b'{"rootID": "kfff"}') == SnapshotId("kfff")


def test_kopia_parse_snapshot_id_raises_when_absent() -> None:
    # no recognisable id -> RAISE: never record a fabricated handle for a snapshot (D110).
    with raises(ValueError):
        _parse_snapshot_id(b'{"note": "took a snapshot"}')
    with raises(ValueError):
        _parse_snapshot_id(b"not json")


def test_kopia_create_snapshot_builds_command_and_parses_id() -> None:
    from mnemosyne.ports import BackupClass

    seen: list[list[str]] = []

    def fake_runner(argv: list[str]) -> bytes:
        seen.append(argv)
        return b'{"id": "snap-42"}'

    engine = connect_kopia(runner=fake_runner)
    sid = engine.create_snapshot(BackupClass.PRECIOUS, ("/truth/md", "/config"))
    assert sid == SnapshotId("snap-42")
    assert seen == [["kopia", "snapshot", "create", "--json", "/truth/md", "/config"]]


def test_kopia_restore_builds_command_and_raises_on_failure() -> None:
    seen: list[list[str]] = []

    def fake_runner(argv: list[str]) -> bytes:
        seen.append(argv)
        return b""

    engine = connect_kopia(runner=fake_runner)
    engine.restore_snapshot(SnapshotId("snap-42"), into="/restore/here")
    assert seen == [["kopia", "snapshot", "restore", "snap-42", "/restore/here"]]

    # a non-zero exit (runner raising) is NOT swallowed into a false ok (D110).
    def failing_runner(_argv: list[str]) -> bytes:
        raise RuntimeError("kopia: repository not connected")

    with raises(RuntimeError):
        connect_kopia(runner=failing_runner).restore_snapshot(SnapshotId("x"), into="/tmp/x")


# --------------------------------------------------------------------------- #
# 4. Langfuse sink - fail-safe: a raising client never propagates              #
# --------------------------------------------------------------------------- #
def test_langfuse_sink_forwards_line_to_client() -> None:
    # the sink (TraceSink shape) ships the already-redacted line to the injected client via a known
    # ingest method; the line travels verbatim (no un-redaction, D111 / inv. 12).
    received: list[dict[str, object]] = []

    class FakeClient:
        def event(self, **payload: object) -> None:
            received.append(payload)

    sink = connect_langfuse(client=FakeClient())
    sink('trace.start {"level": "public", "name": "x"}')
    # confirmed at ignition (Langfuse 4.13.0): create_event has no `message` kwarg, so the line
    # travels under `metadata` instead (ALLUMAGE NOTE on _line_to_event).
    assert received == [
        {
            "name": "mnemosyne.trace",
            "metadata": {"message": 'trace.start {"level": "public", "name": "x"}'},
        }
    ]


def test_langfuse_sink_swallows_client_error() -> None:
    # observability must NEVER break the app: a raising client is swallowed, not propagated (D111).
    class BoomClient:
        def event(self, **_payload: object) -> None:
            raise RuntimeError("langfuse instance down")

    sink = connect_langfuse(client=BoomClient())
    # must not raise - a down dashboard degrades the trail to in-memory only, it never crashes the op.
    assert sink("some redacted line") is None


def test_langfuse_sink_swallows_missing_ingest_method() -> None:
    # a mismatched SDK (no known ingest method) is caught by the same swallow - degrade, never crash.
    class EmptyClient:
        pass

    assert connect_langfuse(client=EmptyClient())("line") is None


# --------------------------------------------------------------------------- #
# 4b. JSONL durable sink + fan_out - the D6 append-only trail, sensible-clean  #
# --------------------------------------------------------------------------- #
def test_jsonl_record_stamps_ts_and_keeps_the_line_verbatim() -> None:
    # pure, brick-free: the durable record wraps the already-redacted line VERBATIM under `line`, gaining
    # only a wall-clock `ts` (the provenance the in-memory records lack, D33). `ts` first for readability.
    record = _line_to_record('trace.start {"level": "public"}', now="2026-07-10T12:00:00.000000Z")
    assert record == {
        "ts": "2026-07-10T12:00:00.000000Z",
        "line": 'trace.start {"level": "public"}',
    }
    assert list(record) == ["ts", "line"]


def test_jsonl_sink_appends_one_json_object_per_line(tmp_path: Path) -> None:
    # each call appends exactly one JSON object (append-only, never truncate): two calls => two lines, each
    # a valid JSON record round-tripping the line under `line` (D6, one event per line, greppable).
    log = tmp_path / "trace.jsonl"
    sink = open_jsonl_sink(log)
    sink('a {"x": 1}')
    sink('b {"y": 2}')
    lines = log.read_text(encoding="utf-8").splitlines()
    assert [json.loads(row)["line"] for row in lines] == ['a {"x": 1}', 'b {"y": 2}']


def test_jsonl_sink_creates_a_missing_parent_dir(tmp_path: Path) -> None:
    # the trail lives at system/logs/<...>; open_jsonl_sink creates the parent if absent, never requiring
    # the caller to pre-make it.
    log = tmp_path / "logs" / "sub" / "trace.jsonl"
    open_jsonl_sink(log)("evt {}")
    assert log.exists() and json.loads(log.read_text(encoding="utf-8"))["line"] == "evt {}"


def test_jsonl_sink_swallows_a_write_error(tmp_path: Path) -> None:
    # observability must NEVER break the app: an unwritable target (here the path IS a directory, so the
    # append open raises) is swallowed, not propagated - a full / read-only disk degrades the trail (D111).
    sink = open_jsonl_sink(tmp_path)  # a directory => open(tmp_path, "a") raises IsADirectoryError
    assert sink("some redacted line") is None  # must not raise


def test_jsonl_trail_is_sensible_clean_end_to_end(tmp_path: Path) -> None:
    # THE D6 BARRIER, proven to DISK: a `sensible` event driven through the couture into the durable file
    # has its VALUES redacted - a grep of the file can never surface `sensible` content; only the event
    # name + field KEYS (operational metadata) travel (inv. 12 / 22 / D71).
    log = tmp_path / "trace.jsonl"
    obs = LocalObservability(sink=open_jsonl_sink(log))
    trace = obs.start_trace(
        "agent",
        GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble("b"), domains=frozenset()),
    )
    obs.event(trace, "tool_return", iban="FR76-SECRET-3000-4000")
    text = log.read_text(encoding="utf-8")
    assert "FR76-SECRET-3000-4000" not in text  # the value is WITHHELD - the barrier holds to disk
    assert (
        "[redacted]" in text and "tool_return" in text and "iban" in text
    )  # name + key still travel


def test_jsonl_trail_keeps_public_values_useful(tmp_path: Path) -> None:
    # the barrier is SCOPED, not blanket: a PUBLIC trace's values DO travel to disk, so the trail stays
    # useful (redaction fires only for non-`public` traces - the couture's rule, mirrored to the file).
    log = tmp_path / "trace.jsonl"
    obs = LocalObservability(sink=open_jsonl_sink(log))
    trace = obs.start_trace(
        "build",
        GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("b"), domains=frozenset()),
    )
    obs.event(trace, "indexed", doc="library/abc123")
    assert "library/abc123" in log.read_text(encoding="utf-8")


def test_fan_out_forwards_each_line_to_every_leg() -> None:
    # LocalObservability takes a single sink; fan_out composes several so the trail reaches BOTH the
    # durable JSONL log and the Langfuse export at once ((3)-6b wiring).
    a: list[str] = []
    b: list[str] = []
    fan_out(a.append, b.append)("redacted line")
    assert a == ["redacted line"] and b == ["redacted line"]


def test_fan_out_isolates_a_failing_leg() -> None:
    # defense in depth: one raising leg never stops the others (a down sink must not couple the fates of
    # its siblings, D111 / D100). The boom leg is FIRST, proving the loop continues past it.
    seen: list[str] = []

    def boom(_line: str) -> None:
        raise RuntimeError("sink down")

    fan_out(boom, seen.append)("line")  # must not raise
    assert seen == ["line"]


def test_jsonl_trail_redacts_perso_to_disk(tmp_path: Path) -> None:
    # the barrier covers PERSO too, not only SENSIBLE (redaction fires for EVERY non-`public` level).
    # Pinned to DISK so a plausible refactor of the predicate (`is PUBLIC` -> `!= SENSIBLE`) can't silently
    # leak `perso` to the permanent log - exactly the "green suite, real bug" trap of the D-CI arc.
    log = tmp_path / "trace.jsonl"
    obs = LocalObservability(sink=open_jsonl_sink(log))
    trace = obs.start_trace(
        "agent",
        GovernanceLabel(sensitivity=Sensitivity.PERSO, bubble=Bubble("b"), domains=frozenset()),
    )
    obs.event(trace, "note", email="operator.private@example.com")
    text = log.read_text(encoding="utf-8")
    assert "operator.private@example.com" not in text  # perso value WITHHELD to disk
    assert "[redacted]" in text and "note" in text and "email" in text


def test_jsonl_trail_redacts_an_unknown_trace_to_disk(tmp_path: Path) -> None:
    # fail-safe: an event under an UNKNOWN trace id is treated as SENSIBLE (redacted) all the way to disk
    # (LocalObservability.event defaults an unseen trace to SENSIBLE), so a mis-wired caller cannot leak.
    log = tmp_path / "trace.jsonl"
    obs = LocalObservability(sink=open_jsonl_sink(log))
    obs.event(TraceId("t-never-started"), "leak", secret="TOPSECRET-XYZ")
    assert "TOPSECRET-XYZ" not in log.read_text(encoding="utf-8")


def test_localobservability_never_lets_a_sink_break_the_traced_op() -> None:
    # structural fail-safe (D111 / inv. 22): the couture GUARANTEES a sink failure never propagates into
    # the traced op - it does not TRUST the sink to swallow its own errors. A naive raising sink is
    # contained at _append, and the in-memory trail stays intact (degrade to memory-only, never crash).
    def raising(_line: str) -> None:
        raise RuntimeError("sink down")

    obs = LocalObservability(sink=raising)
    trace = obs.start_trace(
        "x",
        GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("b"), domains=frozenset()),
    )
    obs.event(trace, "evt", k="v")  # neither start_trace nor event may raise
    assert obs.records()  # the trail survived the failing sink


def test_jsonl_sink_round_trips_non_ascii(tmp_path: Path) -> None:
    # ensure_ascii=False: an accented PUBLIC value survives write->read intact (byte-faithful UTF-8),
    # so the greppable log stays readable for FR/EN content (book titles, French fields).
    log = tmp_path / "trace.jsonl"
    obs = LocalObservability(sink=open_jsonl_sink(log))
    trace = obs.start_trace(
        "build",
        GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("b"), domains=frozenset()),
    )
    obs.event(trace, "indexed", titre="Économétrie & séries temporelles")
    assert "Économétrie & séries temporelles" in log.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 5. Presidio sensor - raise-only entity->sensitivity mapping via injection     #
# --------------------------------------------------------------------------- #
def test_presidio_entity_mapping_is_raise_only() -> None:
    # pure mapper: health/financial/id -> SENSIBLE; other recognised entities -> at least PERSO; the MAX
    # over findings; empty -> None (ABSTAIN - never PUBLIC, so the sensor can only RAISE, invariant 18).
    assert _sensitivity_for_entities(["CREDIT_CARD"]) is Sensitivity.SENSIBLE
    assert _sensitivity_for_entities(["EMAIL_ADDRESS"]) is Sensitivity.PERSO
    assert (
        _sensitivity_for_entities(["EMAIL_ADDRESS", "CREDIT_CARD"]) is Sensitivity.SENSIBLE
    )  # max
    assert (
        _sensitivity_for_entities(["PERSON"]) is Sensitivity.PERSO
    )  # any recognised entity ≥ PERSO
    assert _sensitivity_for_entities([]) is None  # abstain, NOT PUBLIC (raise-only, D100)


def test_presidio_sensor_assess_via_injected_analyzer() -> None:
    # injected analyzer stands in for AnalyzerEngine: the sensor collects entity types and maps them,
    # returning a Sensitivity on a finding and None on an empty result (abstain).
    class Result:
        def __init__(self, entity_type: str) -> None:
            self.entity_type = entity_type

    class FindingAnalyzer:
        def analyze(self, *, text: str, language: str) -> list[Result]:  # noqa: ARG002
            return [Result("IBAN_CODE")]

    class EmptyAnalyzer:
        def analyze(self, *, text: str, language: str) -> list[Result]:  # noqa: ARG002
            return []

    assert (
        connect_presidio_sensor(analyzer=FindingAnalyzer()).assess("my IBAN")
        is Sensitivity.SENSIBLE
    )
    assert connect_presidio_sensor(analyzer=EmptyAnalyzer()).assess("nothing here") is None


# --------------------------------------------------------------------------- #
# 6. Hardware probe - disk math (stdlib) + fail-safe RAM/thermal readers       #
# --------------------------------------------------------------------------- #
class _Usage:
    """A shutil.disk_usage-shaped stand-in (bytes free / total)."""

    def __init__(self, free: int, total: int) -> None:
        self.free = free
        self.total = total


def test_disk_free_ratio_pure() -> None:
    assert _disk_free_ratio(_Usage(free=50, total=100)) == 0.5
    assert (
        _disk_free_ratio(_Usage(free=0, total=0)) == 0.0
    )  # unreadable total => 0 (fail-safe full)


def test_hardware_probe_disk_ok_via_injected_usage() -> None:
    # injected disk_usage -> the ratio threshold decides ok / not-ok (STDLIB, real math, unit-tested).
    ample = SystemHardwareProbe(
        disk_usage=lambda _p: _Usage(free=80, total=100), min_free_ratio=0.1
    )
    assert ample.disk_ok() is True  # 0.8 free ≥ 0.1
    full = SystemHardwareProbe(disk_usage=lambda _p: _Usage(free=2, total=100), min_free_ratio=0.1)
    assert full.disk_ok() is False  # 0.02 free < 0.1 -> CRITICAL in the couture


def test_hardware_probe_disk_read_failure_is_fail_safe() -> None:
    # an unreadable disk (a vanished mount) assumes full -> NOT-ok, never a false green (D100 / D111).
    def boom(_p: str) -> object:
        raise OSError("mount gone")

    assert SystemHardwareProbe(disk_usage=boom).disk_ok() is False


def test_hardware_probe_ram_reader_healthy_by_default_and_threshold() -> None:
    # default RAM reader is HEALTHY until psutil is wired (D126); an injected reader honours the threshold.
    assert (
        SystemHardwareProbe(disk_usage=lambda _p: _Usage(1, 1)).ram_ok() is True
    )  # default healthy
    low = SystemHardwareProbe(disk_usage=lambda _p: _Usage(1, 1), ram_reader=lambda: 0.5)
    assert low.ram_ok() is True  # 0.5 used ≤ 0.92
    high = SystemHardwareProbe(
        disk_usage=lambda _p: _Usage(1, 1), ram_reader=lambda: 0.99, max_ram_used=0.92
    )
    assert high.ram_ok() is False  # 0.99 used > 0.92 -> DEGRADED


def test_hardware_probe_raising_ram_reader_is_not_ok() -> None:
    # a reader that RAISES assumes pressure -> NOT-ok (a probe that cannot read assumes the worse, D100).
    def boom() -> float:
        raise RuntimeError("psutil exploded")

    probe = SystemHardwareProbe(disk_usage=lambda _p: _Usage(1, 1), ram_reader=boom)
    assert probe.ram_ok() is False


def test_hardware_probe_thermal_default_healthy_and_raising_is_not_ok() -> None:
    # thermal defaults healthy (the stub reported OK, so an un-wired signal never falsely degrades);
    # a raising reader assumes throttling -> NOT-ok (fail-safe, D111).
    assert SystemHardwareProbe(disk_usage=lambda _p: _Usage(1, 1)).thermal_ok() is True

    def boom() -> bool:
        raise RuntimeError("no thermal source")

    probe = SystemHardwareProbe(disk_usage=lambda _p: _Usage(1, 1), thermal_reader=boom)
    assert probe.thermal_ok() is False


# --------------------------------------------------------------------------- #
# 7. Encapsulation (invariant 20, self-contained) - bricks stay isolated       #
# --------------------------------------------------------------------------- #
def test_output_bricks_are_encapsulated() -> None:
    # D103 / invariant 20 ((3)-6b): the ops-layer bricks are bricks too - each imported by ONLY its
    # designated sole-importer adapter, so the couture speaks only the ports and the suite runs with NONE
    # installed (D126). Two complementary guards, both self-contained here:
    #
    # (a) STRUCTURAL (process-independent, the real invariant): no module OUTSIDE its adapter imports a
    #     python-import brick. This is the robust guarantee - it does not depend on what a pytest plugin
    #     or an earlier test happened to load. sops/age + kopia are CLI (subprocess) bricks with NO
    #     python module to isolate, so there is nothing to forbid for them (their encapsulation is that
    #     secrets_sops.py / backup_kopia.py are the only subprocess callers). psutil is exempted in its
    #     OWN adapter (health_probe.py) - where it is imported LAZILY inside a factory.
    forbidden = {"typst", "langfuse", "presidio_analyzer", "presidio_anonymizer", "psutil"}
    adapters = frozenset(
        {
            "runtime/render_typst.py",
            "runtime/observability_langfuse.py",
            "ingest/pii_presidio.py",
            "runtime/health_probe.py",
        }
    )
    leaks = direct_imports_of(MNEMOSYNE_ROOT, forbidden, exempt=adapters)
    assert leaks == {}, f"a module reaches an ops brick outside its adapter: {leaks}"

    # (b) RUNTIME DELTA: a cold-start of the default (stub) runtime pulls in NO ops brick. Measured as a
    #     delta around bootstrap() rather than absolute absence, because a brick may already be resident
    #     as a transitive dependency of the test environment (e.g. psutil) - what must hold is that
    #     Mnémosyne's own cold-start never reaches for one (D126). Any adapter's lazy brick import fires
    #     only at (3) ignition, never here.
    before = set(sys.modules)
    bootstrap()
    newly_loaded = (set(sys.modules) - before) & forbidden
    assert newly_loaded == set(), f"bootstrap() pulled in an ops brick: {newly_loaded}"

    # each new adapter module imports safely with the brick absent (the import itself must not touch it -
    # already imported at the top of this file, which is itself the proof; re-assert for clarity).
    for name in (
        "mnemosyne.runtime.render_typst",
        "mnemosyne.guard.secrets_sops",
        "mnemosyne.runtime.backup_kopia",
        "mnemosyne.runtime.observability_langfuse",
        "mnemosyne.ingest.pii_presidio",
        "mnemosyne.runtime.health_probe",
    ):
        assert name in sys.modules, f"adapter {name} failed to import with its brick absent"
    _ = mnemosyne  # referenced so the top-level import is not flagged unused
