"""Structural tests for pre-ingestion triage (D137 / D85, Étape 3).

The triage module is the front door before the benne: it sorts a raw project folder into
SOURCE (books/papers -> the domain shelf), WORKING (project material -> the project bubble) and NOISE
(dependencies / data / binaries -> excluded) with pure, deterministic path rules (D126 brick-free).
These tests pin the disposition rules, the dependency-dir pruning (the reason a venv-vendored PDF
is never taken for a source), content dedup, and the dry-run-by-default execution. Producer ≠
verifier (D75): an isolated audit checks this independently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.ingest import (
    Disposition,
    TriagePlan,
    execute_plan,
    intake_backlog_count,
    plan_triage,
    resolve_moves,
)
from mnemosyne.ports import DocRole, Bubble, Domain

TRADING = Bubble("trading")
QUANT = Domain(
    "quant-trading"
)  # a taxonomy-mapped domain (Finance/Trading), shelved via taxonomy.toml
QT_SHELF = (
    Path("Finance") / "Trading" / "quant-trading" / "books"
)  # quant-trading's raw-relative shelf
CS_SHELF = (
    Path("Software") / "Foundations" / "computer-science" / "books"
)  # computer-science's shelf


def _write(path: Path, content: bytes | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # default to UNIQUE content (path-derived) so distinct files never accidentally dedup;
    # the dedup/collision tests pass explicit bytes to control identity.
    path.write_bytes(content if content is not None else str(path).encode())


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A synthetic mixed corpus: books, project notes, market data, caches, a binary, and an unknown blob."""
    root = tmp_path / "raw_project"
    # sources of truth (books / papers), some buried
    _write(root / "Books-All" / "Market Microstructure Theory - O'Hara.pdf")
    _write(root / "theories" / "T002" / "sources" / "Lakonishok_1988.pdf")
    _write(root / "ExamplePilot" / "Orchestration" / "Adaptive Markets - Lo.epub")
    _write(root / "Books-All" / "Computer Architecture - Hennessy.pdf")  # non-finance domain hint
    # a document VENDORED inside a venv (must be NOISE, never a source)
    _write(root / "ExamplePilot" / "app" / ".venv" / "lib" / "matplotlib" / "filesave.pdf")
    # project working material
    _write(root / "theories" / "T002" / "README_theorie.md", b"# turn of month\n")
    _write(root / "tools" / "analysis_lib.py", b"def f():\n    return 1\n")
    _write(root / "lean.json", b"{}\n")  # canonical config -> rescued as working
    # noise: market data, bulk-data json, cache, binary, unknown blob, OS cruft
    _write(root / "data" / "prices.parquet")
    _write(root / "data" / "history.csv")
    _write(
        root / "ExamplePilot" / "results" / "opt_run_001.json", b'{"sharpe": 1.2}'
    )  # data blob -> noise
    _write(root / "tools" / "__pycache__" / "analysis_lib.cpython-312.pyc")
    _write(root / "app" / "ext.so")
    _write(root / "weird.xyz")
    _write(root / ".DS_Store")
    return root


def _dispositions(plan: TriagePlan) -> dict[str, Disposition]:
    return {str(e.relative): e.disposition for e in plan.entries}


def test_documents_are_sources_working_text_is_working_data_is_noise(corpus: Path) -> None:
    plan = plan_triage(corpus, project=TRADING, primary_domain=QUANT)
    d = _dispositions(plan)
    assert d["Books-All/Market Microstructure Theory - O'Hara.pdf"] is Disposition.SOURCE
    assert d["theories/T002/sources/Lakonishok_1988.pdf"] is Disposition.SOURCE
    assert d["ExamplePilot/Orchestration/Adaptive Markets - Lo.epub"] is Disposition.SOURCE
    assert d["theories/T002/README_theorie.md"] is Disposition.WORKING
    assert d["tools/analysis_lib.py"] is Disposition.WORKING
    assert d["lean.json"] is Disposition.WORKING  # allowlisted config rescued
    assert (
        d["ExamplePilot/results/opt_run_001.json"] is Disposition.NOISE
    )  # bulk data json -> noise
    assert d["data/prices.parquet"] is Disposition.NOISE
    assert d["data/history.csv"] is Disposition.NOISE
    assert d["app/ext.so"] is Disposition.NOISE
    assert d["weird.xyz"] is Disposition.NOISE  # unknown -> fail-closed noise
    assert d[".DS_Store"] is Disposition.NOISE


def test_venv_vendored_document_is_pruned_never_a_source(corpus: Path) -> None:
    """The crux (real bug this prevents): a PDF inside a nested .venv must NOT become a source."""
    plan = plan_triage(corpus, project=TRADING, primary_domain=QUANT)
    rels = {str(e.relative) for e in plan.entries}
    # the vendored filesave.pdf is under a pruned .venv - it never even surfaces as an entry.
    assert not any(".venv" in r for r in rels)
    assert not any("filesave.pdf" in r for r in rels)
    # and the .venv dir is recorded as pruned (F3 - excluded, not invisible).
    assert any(".venv" in str(p) for p in plan.pruned_dirs)
    # pycache is pruned too.
    assert not any("__pycache__" in r for r in rels)


def test_pycache_pruned_but_sibling_source_file_kept(corpus: Path) -> None:
    plan = plan_triage(corpus, project=TRADING, primary_domain=QUANT)
    rels = {str(e.relative) for e in plan.entries}
    assert "tools/analysis_lib.py" in rels  # the real file kept
    assert not any(r.endswith(".pyc") for r in rels)  # its cache pruned


def test_domain_proposal_primary_by_default_hint_reshelves(corpus: Path) -> None:
    plan = plan_triage(corpus, project=TRADING, primary_domain=QUANT)
    by_rel = {str(e.relative): e for e in plan.entries}
    assert by_rel["Books-All/Market Microstructure Theory - O'Hara.pdf"].domain == QUANT
    # an unambiguous CS title is re-shelved off the finance default (a proposal, not a verdict).
    assert by_rel["Books-All/Computer Architecture - Hennessy.pdf"].domain == Domain(
        "computer-science"
    )


def test_proposed_role_matches_disposition(corpus: Path) -> None:
    plan = plan_triage(corpus, project=TRADING, primary_domain=QUANT)
    by_rel = {str(e.relative): e for e in plan.entries}
    assert (
        by_rel["Books-All/Market Microstructure Theory - O'Hara.pdf"].role
        is DocRole.BASE_DE_CONNAISSANCES
    )
    assert by_rel["tools/analysis_lib.py"].role is DocRole.MATIERE_DE_TRAVAIL
    assert by_rel["data/prices.parquet"].role is None  # noise is never filed


def test_resolve_moves_shelves_sources_by_domain_keeps_working_tree(
    tmp_path: Path, corpus: Path
) -> None:
    plan = plan_triage(corpus, project=TRADING, primary_domain=QUANT)
    kroot, proots = tmp_path / "knowledge", tmp_path / "projects"
    moves = resolve_moves(plan, knowledge_root=kroot, projects_root=proots)
    dest_by_name = {m.src.name: m.dest for m in moves}
    # a quant-trading source is shelved on its hierarchical taxonomy path (.../<domain>/<type>/)
    assert (
        dest_by_name["Market Microstructure Theory - O'Hara.pdf"]
        == kroot / "raw" / QT_SHELF / "Market Microstructure Theory - O'Hara.pdf"
    )
    # the CS source lands on its own domain shelf, derived the same taxonomy way
    assert dest_by_name["Computer Architecture - Hennessy.pdf"].parent == kroot / "raw" / CS_SHELF
    # working material keeps its relative tree under the project bubble, namespaced by source root
    assert (
        dest_by_name["analysis_lib.py"]
        == proots / "trading" / "raw_project" / "tools" / "analysis_lib.py"
    )
    assert (
        dest_by_name["README_theorie.md"]
        == proots / "trading" / "raw_project" / "theories" / "T002" / "README_theorie.md"
    )
    # noise never resolves to a move
    assert not any(m.src.suffix == ".parquet" for m in moves)


def test_identical_books_dedup_to_one_shelf_copy(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    _write(root / "folderA" / "book.pdf", b"IDENTICAL BYTES")
    _write(root / "folderB" / "book copy.pdf", b"IDENTICAL BYTES")
    plan = plan_triage(root, project=TRADING, primary_domain=QUANT)
    moves = resolve_moves(plan, knowledge_root=tmp_path / "k", projects_root=tmp_path / "p")
    actions = sorted(m.action for m in moves)
    assert actions == ["dedup-skip", "move"]  # one real move, one dedup


def test_same_name_different_bytes_collision_renamed(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    _write(root / "a" / "book.pdf", b"CONTENT ONE")
    _write(root / "b" / "book.pdf", b"CONTENT TWO")
    plan = plan_triage(root, project=TRADING, primary_domain=QUANT)
    moves = resolve_moves(plan, knowledge_root=tmp_path / "k", projects_root=tmp_path / "p")
    dests = {m.dest.name for m in moves}
    assert "book.pdf" in dests
    assert any(name != "book.pdf" and name.endswith(".pdf") for name in dests)  # the renamed one


def test_execute_dry_run_moves_nothing(tmp_path: Path, corpus: Path) -> None:
    plan = plan_triage(corpus, project=TRADING, primary_domain=QUANT)
    kroot, proots = tmp_path / "knowledge", tmp_path / "projects"
    report = execute_plan(plan, knowledge_root=kroot, projects_root=proots, dry_run=True)
    assert report.dry_run is True
    assert not kroot.exists() and not proots.exists()  # nothing written
    # the source file is still in place, untouched
    assert (corpus / "Books-All" / "Market Microstructure Theory - O'Hara.pdf").exists()
    assert report.count("move") > 0  # but the report says what WOULD move


def test_execute_real_move_relocates_and_dedups(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    _write(root / "a" / "book.pdf", b"SAME")
    _write(root / "b" / "dup.pdf", b"SAME")
    _write(root / "notes.md", b"# mine\n")
    _write(root / "data.parquet", b"\x00\x01")
    plan = plan_triage(root, project=TRADING, primary_domain=QUANT)
    kroot, proots = tmp_path / "knowledge", tmp_path / "projects"
    report = execute_plan(plan, knowledge_root=kroot, projects_root=proots, dry_run=False)
    assert report.dry_run is False
    # exactly one shelved copy of the identical book (dedup), on the quant-trading taxonomy shelf
    shelved = list((kroot / "raw" / QT_SHELF).glob("*.pdf"))
    assert len(shelved) == 1
    # working material relocated under the project bubble (namespaced by the source root "raw")
    assert (proots / "trading" / "raw" / "notes.md").exists()
    # noise left where it was (not moved, not deleted)
    assert (root / "data.parquet").exists()


def test_working_material_namespaced_by_source_root_avoids_cross_root_collision(
    tmp_path: Path,
) -> None:
    """Two raw roots merged into ONE bubble must not overwrite each other's like-named files."""
    root_a, root_b = tmp_path / "example_lab", tmp_path / "usine"
    _write(root_a / "README.md", b"alpha readme")
    _write(root_b / "README.md", b"usine readme")
    kroot, proots = tmp_path / "k", tmp_path / "p"
    seen: dict = {}
    for root in (root_a, root_b):
        plan = plan_triage(root, project=TRADING, primary_domain=QUANT)
        execute_plan(
            plan, knowledge_root=kroot, projects_root=proots, dry_run=False, seen_hashes=seen
        )
    assert (proots / "trading" / "example_lab" / "README.md").read_bytes() == b"alpha readme"
    assert (proots / "trading" / "usine" / "README.md").read_bytes() == b"usine readme"


def test_summary_reports_counts_and_pruned(corpus: Path) -> None:
    plan = plan_triage(corpus, project=TRADING, primary_domain=QUANT)
    text = plan.summary()
    assert "SOURCE" in text and "WORKING" in text and "NOISE" in text
    assert "quant-trading" in text  # domain breakdown present
    assert "trading" in text  # project named


# --- audit D75 fixes ----------------------------------------------------------------------------


def test_containment_guard_refuses_escaping_bubble(tmp_path: Path) -> None:
    """Audit M3: a malformed bubble/domain name with '..' must not write the IP outside its zone."""
    root = tmp_path / "raw"
    _write(root / "notes.md", b"mine")
    plan = plan_triage(root, project=Bubble("../escaped"), primary_domain=QUANT)
    with pytest.raises(ValueError, match="escape its gitignored zone|outside"):
        resolve_moves(plan, knowledge_root=tmp_path / "k", projects_root=tmp_path / "p")


def test_source_shelved_via_taxonomy_hierarchical_path(tmp_path: Path) -> None:
    """A SOURCE with a MAPPED domain is shelved on its full taxonomy path
    ``<Famille>/<Groupe>/<domain>/<type>`` - read from taxonomy.toml (the single mapping source), not the
    old flat ``knowledge/raw/<domain>/``."""
    root = tmp_path / "raw"
    _write(root / "book.pdf", b"a mapped book")
    kroot = tmp_path / "k"
    plan = plan_triage(root, project=TRADING, primary_domain=QUANT)
    moves = resolve_moves(plan, knowledge_root=kroot, projects_root=tmp_path / "p")
    m = next(mv for mv in moves if mv.src.name == "book.pdf")
    assert m.dest == kroot / "raw" / QT_SHELF / "book.pdf"


def test_unmapped_or_malformed_domain_is_contained_in_intake(tmp_path: Path) -> None:
    """With taxonomy shelving, a domain OUTSIDE the mapping (or a malformed '..' label) can no longer
    reach a raw path segment: it is routed to the ``_intake`` sas - surfaced for a human, never guessed
    onto a shelf and never escaping the gitignored zone (D85 / the _ensure_within garde-fou still holds).
    The escaping-bubble test above still exercises that guard's RAISE on the project side."""
    root = tmp_path / "raw"
    _write(root / "off.pdf", b"off-taxonomy")
    _write(root / "bad.pdf", b"malformed label")
    kroot = tmp_path / "k"
    for name, primary in (("off.pdf", Domain("astrology")), ("bad.pdf", Domain("../../escape"))):
        plan = plan_triage(root, project=TRADING, primary_domain=primary)
        moves = resolve_moves(plan, knowledge_root=kroot, projects_root=tmp_path / "p")
        m = next(mv for mv in moves if mv.src.name == name)
        assert m.dest == kroot / "raw" / "_intake" / name  # contained in the sas, not escaped
        assert m.dest.resolve().is_relative_to(kroot.resolve())  # provably inside the zone


def test_working_collision_renamed_not_silently_overwritten(tmp_path: Path) -> None:
    """Audit M1: a pre-existing WORKING dest (different content) must be renamed, never clobbered."""
    root = tmp_path / "raw"
    _write(root / "notes.md", b"NEW CONTENT")
    proots = tmp_path / "p"
    existing = proots / "trading" / "raw" / "notes.md"
    _write(existing, b"OLD CONTENT - must survive")
    plan = plan_triage(root, project=TRADING, primary_domain=QUANT)
    moves = resolve_moves(plan, knowledge_root=tmp_path / "k", projects_root=proots)
    m = next(mv for mv in moves if mv.src.name == "notes.md")
    assert m.action == "collision-rename"
    assert m.dest != existing  # a distinct path -> shutil.move cannot overwrite the old file


def test_working_reingest_preserves_both_versions(tmp_path: Path) -> None:
    """End-to-end: re-running with changed content keeps BOTH (no silent datum loss, D85)."""
    root = tmp_path / "raw"
    kroot, proots = tmp_path / "k", tmp_path / "p"
    _write(root / "notes.md", b"V1")
    execute_plan(
        plan_triage(root, project=TRADING, primary_domain=QUANT),
        knowledge_root=kroot,
        projects_root=proots,
        dry_run=False,
        copy=True,
    )
    _write(root / "notes.md", b"V2 DIFFERENT")
    execute_plan(
        plan_triage(root, project=TRADING, primary_domain=QUANT),
        knowledge_root=kroot,
        projects_root=proots,
        dry_run=False,
        copy=True,
    )
    files = sorted((proots / "trading" / "raw").glob("notes*.md"))
    assert len(files) == 2  # V1 kept, V2 added under a renamed path - neither clobbered


def test_ambiguous_dirs_not_pruned_but_real_venv_still_is(tmp_path: Path) -> None:
    """Audit M2: 'dist'/'env'/'build'/'target' are content-plausible -> NOT pruned whole (a real
    source under them surfaces); a genuine .venv is still pruned."""
    root = tmp_path / "raw"
    _write(root / "dist" / "distribution_of_returns.pdf")  # 'dist' = distribution in finance
    _write(root / "env" / "macro_env_notes.md")
    _write(root / ".venv" / "lib" / "vendored_icon.pdf")  # real venv -> still pruned
    plan = plan_triage(root, project=TRADING, primary_domain=QUANT)
    d = {str(e.relative): e.disposition for e in plan.entries}
    assert d["dist/distribution_of_returns.pdf"] is Disposition.SOURCE  # surfaced, not dropped
    assert d["env/macro_env_notes.md"] is Disposition.WORKING
    rels = {str(e.relative) for e in plan.entries}
    assert not any(".venv" in r for r in rels)  # genuine dependency dir still pruned whole


def test_summary_surfaces_pruned_dir_paths(tmp_path: Path) -> None:
    """Audit M2/F3: pruning a whole subtree must be reviewable (a path), not a silent count."""
    root = tmp_path / "raw"
    _write(root / ".venv" / "x.py")
    _write(root / "real.md")
    plan = plan_triage(root, project=TRADING, primary_domain=QUANT)
    text = plan.summary()
    assert "pruned (review)" in text
    assert ".venv" in text


# ---- intake backlog depth (Q2 autonomy signal) ---------------------------------------
def test_intake_backlog_count_is_zero_without_a_sas(tmp_path: Path) -> None:
    """No knowledge/raw/_intake yet => 0, never a crash on the absent tree (a pure read)."""
    assert intake_backlog_count(tmp_path) == 0


def test_intake_backlog_count_counts_un_homed_files_and_ignores_cruft(tmp_path: Path) -> None:
    """Counts the flat un-homed sources triage parked in the sas; skips dot-files, subdirs, and README."""
    sas = tmp_path / "raw" / "_intake"
    sas.mkdir(parents=True)
    (sas / "an-unmapped-book.pdf").write_text("x", encoding="utf-8")
    (sas / "a-novel-theme.epub").write_text("y", encoding="utf-8")
    (sas / ".gitkeep").write_text("", encoding="utf-8")  # dot-file cruft - not counted
    (sas / "README.md").write_text(
        "# _intake sas\n", encoding="utf-8"
    )  # nav placeholder - not counted
    (sas / "nested").mkdir()  # a subdir is not a file - not counted
    assert intake_backlog_count(tmp_path) == 2
