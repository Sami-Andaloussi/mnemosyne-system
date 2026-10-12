"""Pre-ingestion triage (D137 / D85 / Step 3) — sort a raw project folder before capture.

A real project folder the user hands over is ~90 % noise (venvs, market data, caches, binaries)
with the signal SCATTERED: books and papers buried inside sub-projects and even inside venvs,
the user's own code and notes mixed with library code (measured: Example Research + the sibling project ≈ 19 GB /
157 k files, ~450 document files strewn across eight locations, 22 of them matplotlib icons
vendored in a ``.venv``). Ingesting such a tree naïvely would drown the stores. This module is
the FRONT DOOR before the benne (D85): a deterministic walk that gives every file ONE
disposition —

* ``SOURCE``  — a source of truth (book / paper): a document file NOT inside a dependency or
  cache dir. Proposed role **knowledge base** (D137), shelved by DOMAIN and shared across
  projects (the D137 asymmetry: a source of truth is reusable, never bubble-local). The
  endorsement itself stays a human gesture (:meth:`CoreApi.endorse_document`) — triage only
  PROPOSES a role, it never grants one (fail-closed, D59 / D137).
* ``WORKING`` — working material: the user's own code / notes / drafts. Stays WITH the project
  bubble, fail-closed role working material — never automatically a source of truth.
* ``NOISE``   — a dependency (``.venv`` / ``site-packages`` / ``node_modules``), a cache
  (``__pycache__`` …), market data (``.parquet`` / ``.csv`` / ``.zip``), a compiled binary, or
  an unknown blob. Excluded: never ingested, never moved.

Deterministic and brick-free (D126): pure path + extension rules, no model, no network — so the
PLAN is testable with nothing installed and reviewable BEFORE a single file moves. Dependency and
cache dirs are PRUNED at the walk (never descended), so a 100 k-file venv costs nothing and its
vendored documents can never masquerade as sources. Physical execution (moving files into their
gitignored homes) is a SEPARATE, dry-run-by-default step (:func:`execute_plan`).

Code & docstrings English (D117); role / domain / governance tokens stay French where they are
governance vocabulary (D33 / D66).
"""

from __future__ import annotations

import hashlib
import os
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import taxonomy
from ..ports import DEFAULT_ROLE, Bubble, DocRole, Domain

# --- rules (pure data — the whole classifier is these frozensets + _classify) -------------------

#: A directory whose presence makes EVERYTHING under it noise — dependencies, caches, VCS. Matched
#: by exact (lower-cased) name at ANY depth and PRUNED from the walk, so a nested venv (even the one
#: Vpilot ships three levels down) is skipped whole and its vendored ``.pdf`` icons never surface.
#: ONLY UNAMBIGUOUS markers (dotted / tool-specific) — deliberately NOT the human-meaningful words
#: ``build`` / ``dist`` / ``env`` / ``target`` (audit D75 M2): "dist" = distribution, "env" =
#: environment/economy are real content dir names in a finance corpus, and pruning them whole would
#: silently drop a real source (D85). Their contents are instead classified file-by-file (a wheel /
#: ``.so`` still falls to noise by extension, a real ``.pdf`` still SURFACES). A residual dependency
#: dir under such a name simply costs a cheap walk, never a lost datum (fail toward surfacing, D100).
_NOISE_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".venv",
        "venv",
        ".venv-lean",
        ".env",
        "virtualenv",
        "site-packages",
        "node_modules",
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".ipynb_checkpoints",
        ".tox",
        ".eggs",
        ".cache",
        ".gradle",
        ".idea",
        ".vscode",
        ".next",
        ".turbo",
    }
)
#: Directory-name SUFFIXES that mark a dependency artefact dir (e.g. ``numpy-1.26.dist-info``).
_NOISE_DIR_SUFFIXES: tuple[str, ...] = (".dist-info", ".egg-info")

#: Document files = source-of-truth candidates (books, papers). The ONE positive signal for SOURCE.
_DOC_EXTS: frozenset[str] = frozenset(
    {".pdf", ".epub", ".mobi", ".djvu", ".azw", ".azw3", ".fb2", ".cbz", ".cbr"}
)
#: The user's own working material — text they (or an agent working on their behalf) authored. Only OUTSIDE a noise dir.
#: NOTE ``.json`` / ``.yaml`` are NOT here: in these data-heavy corpora they are overwhelmingly bulk
#: data / run outputs, not authored knowledge (measured: 20 491 of the sibling project's ``.json`` are
#: optimisation dumps under one results folder), so they are handled as data below with a small config allowlist.
_WORK_EXTS: frozenset[str] = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".org",
        ".py",
        ".ipynb",
        ".r",
        ".jl",
        ".sql",
        ".sh",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".c",
        ".h",
        ".cpp",
        ".rs",
        ".go",
        ".toml",
        ".cfg",
        ".ini",
        ".tex",
        ".bib",
    }
)
#: Structured-text extensions used for BOTH config AND bulk data. Treated as data (NOISE) by default
#: — a lost config is cheap and regenerable, its consuming code is preserved, and it is never a source
#: of truth; a bulk dump of 20 k of them would junk the project. A canonical config basename is rescued.
_DATA_LIKE_TEXT_EXTS: frozenset[str] = frozenset({".json", ".yaml", ".yml", ".ndjson", ".jsonl"})
#: The few config basenames worth keeping as working material even though their extension is data-like.
_CONFIG_ALLOWLIST: frozenset[str] = frozenset(
    {"package.json", "tsconfig.json", "lean.json", "composer.json", "pyrightconfig.json"}
)
#: Data blobs — market data, dumps, archives. Noise even OUTSIDE a venv (this corpus is 61 k parquet
#: + 420 csv of market data). A meaningful small table is re-fetchable; we do not ingest data.
_DATA_EXTS: frozenset[str] = frozenset(
    {
        ".parquet",
        ".csv",
        ".tsv",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".rar",
        ".dat",
        ".arrow",
        ".feather",
        ".h5",
        ".hdf5",
        ".pkl",
        ".pickle",
        ".npy",
        ".npz",
        ".db",
        ".sqlite",
    }
)
#: Compiled / binary artefacts — always noise.
_BINARY_EXTS: frozenset[str] = frozenset(
    {
        ".pyc",
        ".pyo",
        ".pyi",
        ".so",
        ".dylib",
        ".dll",
        ".o",
        ".a",
        ".lib",
        ".exe",
        ".bin",
        ".whl",
        ".egg",
        ".class",
        ".wasm",
        ".node",
    }
)
#: OS / editor cruft filenames (lower-cased) that are never signal.
_CRUFT_NAMES: frozenset[str] = frozenset({".ds_store", "thumbs.db", ".gitkeep", "desktop.ini"})

#: Coarse domain hints for a source of truth — keywords that USUALLY mean a non-primary domain, to
#: LIMIT (not eliminate) mis-shelving; everything else falls to the primary domain. A keyword can
#: still misfire on a finance title (e.g. "…machine learning…") — it is a PROPOSAL, corrected by a
#: human gesture / D137 Lot 2 auto-proposition, and a mis-file is a wrong folder, never a lost datum.
_DOMAIN_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "computer-science",
        (
            "computer architecture",
            "domain-driven design",
            "operating system",
            "the pragmatic programmer",
            "clean code",
            "clean architecture",
            "designing data-intensive",
            "structure and interpretation",
            "compiler",
            "introduction to algorithms",
        ),
    ),
    (
        "machine-learning",
        (
            "pytorch",
            "scikit-learn",
            "hands-on machine learning",
            "deep learning",
            "learning from data",
        ),
    ),
)


#: The raw-intake airlock dir name: where a SOURCE with no declared taxonomy home is parked, never lost
#: or mis-shelved (D85 / D137). One literal, shared by :func:`_destination` (writes it) and
#: :func:`intake_backlog_count` (reads its depth) — never two copies to drift ([[contract-single-source-emit]]).
_INTAKE_DIRNAME = "_intake"


class Disposition(Enum):
    """What triage decides a file IS — its disposition before any move (Step 3 / D85)."""

    SOURCE = (
        "source"  # a source of truth (book / paper) → the shelf, proposed knowledge base
    )
    WORKING = "working"  # working material (the user's own) → the project bubble
    NOISE = "noise"  # dependency / cache / data / binary / unknown → excluded, never ingested


def _classify(rel: Path) -> tuple[Disposition, str]:
    """Give one relative path its disposition + an honest reason (F3). Pure: name + extension only.

    Order matters: a dependency/cache ancestor wins over ANY extension (so a ``.venv``-vendored PDF
    is noise, not a source), then cruft, then the positive document signal, then data / binary, then
    working material, then a fail-closed default of noise for an unknown blob (never dragged in)."""
    ext = rel.suffix.lower()
    name = rel.name.lower()
    # 1) an ancestor dependency / cache / build dir makes the file noise, whatever its extension.
    for part in rel.parts[:-1]:
        low = part.lower()
        if low in _NOISE_DIR_NAMES or low.endswith(_NOISE_DIR_SUFFIXES):
            return Disposition.NOISE, f"under dependency/cache dir '{part}'"
    # 2) OS / editor cruft.
    if name in _CRUFT_NAMES or name.startswith("._"):
        return Disposition.NOISE, "OS/editor cruft"
    # 3) a document is a source of truth (the one positive signal).
    if ext in _DOC_EXTS:
        return Disposition.SOURCE, f"document '{ext}'"
    # 4) data blob or compiled binary → noise.
    if ext in _DATA_EXTS:
        return Disposition.NOISE, f"data file '{ext}'"
    if ext in _BINARY_EXTS:
        return Disposition.NOISE, f"binary '{ext}'"
    # 5) structured-text: a canonical config is working, else it is a data/config blob → noise.
    if ext in _DATA_LIKE_TEXT_EXTS:
        if name in _CONFIG_ALLOWLIST:
            return Disposition.WORKING, f"config '{name}'"
        return Disposition.NOISE, f"data/config blob '{ext}'"
    # 6) the user's own text → working material.
    if ext in _WORK_EXTS:
        return Disposition.WORKING, f"working material '{ext}'"
    # 7) fail-closed: an unknown blob is NOT ingested (surfaced in the plan for review, never guessed).
    return Disposition.NOISE, f"unknown type '{ext or '(no extension)'}'"


def _propose_domain(name: str, primary: Domain) -> Domain:
    """The proposed shelf domain for a source (D137). Primary by default; a non-primary hint
    re-shelves it. Biased toward the primary domain to LIMIT mis-filing, but not immune: a keyword
    can misfire (a finance title containing "machine learning" → machine-learning). This is a
    PROPOSAL a human corrects (D137 Lot 2), and a mis-file is a wrong folder, never a lost datum."""
    low = name.lower()
    for domain, keywords in _DOMAIN_HINTS:
        if any(k in low for k in keywords):
            return Domain(domain)
    return primary


def intake_backlog_count(knowledge_root: Path) -> int:
    """How many sources sit un-homed in the ``knowledge/raw/_intake`` airlock (the Q2 autonomy signal).

    A META count for the autonomous proposer (:class:`~mnemosyne.production.proposer.IntakeBacklogReview`):
    the DEPTH of the passive basket, never its contents (invariant 22 / D66). Counts regular files
    directly under the airlock — matching :func:`_destination`, which flattens each un-homed source to
    ``raw/_intake/<name>`` — while skipping the fixed placeholders that are NOT parked sources: dot-files
    (``.gitkeep`` / OS cruft) and the airlock's own ``README`` navigation doc (the reorg added one to every
    folder). Without the README skip the nudge would fire on an EMPTY airlock every session (a perpetual false
    signal — the exact noise the proposer must not make). Returns 0 when the airlock does not exist yet; robust
    to a missing tree, never raises on an absent root (a pure read)."""
    sas = knowledge_root / "raw" / _INTAKE_DIRNAME
    if not sas.is_dir():
        return 0
    return sum(
        1
        for p in sas.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.stem.lower() != "readme"
    )


@dataclass(frozen=True, slots=True)
class TriageEntry:
    """One walked file with its disposition (Step 3). ``relative`` is under the scanned root;
    ``domain`` is the proposed shelf domain for a SOURCE (``None`` otherwise); ``reason`` is the
    rule that fired (honest + greppable, F3)."""

    relative: Path
    disposition: Disposition
    reason: str
    size: int
    domain: Domain | None = None

    @property
    def role(self) -> DocRole | None:
        """The PROPOSED role (D137) — a proposal only; endorsement stays a human gesture (D59).
        A SOURCE proposes knowledge base, WORKING is the fail-closed working material,
        NOISE has no role (it is never filed)."""
        if self.disposition is Disposition.SOURCE:
            return DocRole.BASE_DE_CONNAISSANCES
        if self.disposition is Disposition.WORKING:
            return DEFAULT_ROLE
        return None


@dataclass(frozen=True, slots=True)
class TriagePlan:
    """The reviewable result of a walk (Step 3): every kept file's disposition + the pruned
    dependency dirs (recorded, not silently dropped — F3). Physical moves happen only in
    :func:`execute_plan`, so the plan is a pure, inspectable artefact."""

    root: Path
    project: Bubble
    primary_domain: Domain
    entries: tuple[TriageEntry, ...]
    #: The root-relative PATH of each PRUNED dependency/cache dir — the honest record of what the walk
    #: skipped whole, so "excluded" is auditable rather than invisible (F3); surfaced by :meth:`summary`.
    pruned_dirs: tuple[Path, ...] = field(default_factory=tuple)

    def of(self, disposition: Disposition) -> tuple[TriageEntry, ...]:
        """The entries with the given disposition (order preserved)."""
        return tuple(e for e in self.entries if e.disposition is disposition)

    def summary(self) -> str:
        """A compact human summary (counts + bytes per disposition, sources per domain, the unknown
        extensions that fell to noise) — what to eyeball before authorising the moves."""
        by_disp: Counter[Disposition] = Counter()
        bytes_by_disp: Counter[Disposition] = Counter()
        by_domain: Counter[str] = Counter()
        unknown_exts: Counter[str] = Counter()
        for e in self.entries:
            by_disp[e.disposition] += 1
            bytes_by_disp[e.disposition] += e.size
            if e.disposition is Disposition.SOURCE and e.domain is not None:
                by_domain[str(e.domain)] += 1
            if e.disposition is Disposition.NOISE and e.reason.startswith("unknown type"):
                unknown_exts[e.relative.suffix.lower() or "(none)"] += 1

        def gb(n: int) -> str:
            return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB"

        lines = [
            f"Triage of {self.root} → project '{self.project}' (primary domain '{self.primary_domain}')",
            f"  SOURCE  (→ shelf)   : {by_disp[Disposition.SOURCE]:>6} files  {gb(bytes_by_disp[Disposition.SOURCE])}",
            f"  WORKING (→ project) : {by_disp[Disposition.WORKING]:>6} files  {gb(bytes_by_disp[Disposition.WORKING])}",
            f"  NOISE   (excluded)  : {by_disp[Disposition.NOISE]:>6} files  {gb(bytes_by_disp[Disposition.NOISE])}",
            f"  pruned dependency/cache dirs: {len(self.pruned_dirs)}",
        ]
        if self.pruned_dirs:
            # surface the pruned dirs (a sample) — pruning is a WHOLE-subtree exclusion, so it must
            # be reviewable, not a silent count (audit D75 M2 / D85 / F3).
            sample = ", ".join(str(p) for p in self.pruned_dirs[:6])
            more = "" if len(self.pruned_dirs) <= 6 else f", …(+{len(self.pruned_dirs) - 6})"
            lines.append(f"    pruned (review): {sample}{more}")
        if by_domain:
            shelf = ", ".join(f"{d}={n}" for d, n in sorted(by_domain.items(), key=lambda x: -x[1]))
            lines.append(f"  sources by domain: {shelf}")
        if unknown_exts:
            top = ", ".join(f"{e}×{n}" for e, n in unknown_exts.most_common(8))
            lines.append(f"  unknown→noise exts (review): {top}")
        return "\n".join(lines)


def plan_triage(
    root: Path | str,
    *,
    project: Bubble,
    primary_domain: Domain,
    follow_symlinks: bool = False,
) -> TriagePlan:
    """Walk ``root`` and classify every file WITHOUT touching it (Step 3 / D126).

    Dependency and cache dirs are pruned in place (never descended), so the walk is cheap on a
    19 GB / 157 k-file tree and a vendored document can never be taken for a source. Returns a
    :class:`TriagePlan` — pure and reviewable; nothing moves until :func:`execute_plan`."""
    root = Path(root)
    entries: list[TriageEntry] = []
    pruned: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        here = Path(dirpath)
        # prune dependency/cache dirs in place (os.walk honours mutation of `dirnames`).
        keep: list[str] = []
        for d in dirnames:
            low = d.lower()
            if low in _NOISE_DIR_NAMES or low.endswith(_NOISE_DIR_SUFFIXES):
                pruned.append((here / d).relative_to(root))
            else:
                keep.append(d)
        dirnames[:] = keep
        for fn in filenames:
            abs_path = here / fn
            rel = abs_path.relative_to(root)
            disposition, reason = _classify(rel)
            try:
                size = abs_path.stat().st_size
            except OSError:
                size = 0  # a broken symlink / vanished file is size 0, still recorded (F3)
            domain = (
                _propose_domain(fn, primary_domain) if disposition is Disposition.SOURCE else None
            )
            entries.append(TriageEntry(rel, disposition, reason, size, domain))
    return TriagePlan(
        root=root,
        project=project,
        primary_domain=primary_domain,
        entries=tuple(entries),
        pruned_dirs=tuple(pruned),
    )


# --- physical execution (side-effecting; dry-run by default) ------------------------------------


@dataclass(frozen=True, slots=True)
class Move:
    """One resolved relocation: ``src`` → ``dest`` for ``entry`` (or a dedup/collision note)."""

    entry: TriageEntry
    src: Path
    dest: Path
    action: str  # "move" | "copy" | "dedup-skip" | "collision-rename"


@dataclass(frozen=True, slots=True)
class ExecReport:
    """The outcome of :func:`execute_plan` — what moved, what was a duplicate, bytes relocated."""

    moves: tuple[Move, ...]
    dry_run: bool

    def count(self, action: str) -> int:
        return sum(1 for m in self.moves if m.action == action)

    def summary(self) -> str:
        mode = "DRY-RUN (nothing moved)" if self.dry_run else "EXECUTED"
        moved = self.count("move") + self.count("copy")
        return (
            f"{mode}: {moved} relocated, {self.count('dedup-skip')} duplicates skipped, "
            f"{self.count('collision-rename')} renamed on collision"
        )


def _sha256(path: Path, *, chunk: int = 1 << 20) -> str:
    """Streaming content hash — the dedup key so the shelf holds ONE copy of a book, not three."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _ensure_within(dest: Path, root: Path) -> Path:
    """Fail-closed containment guard (audit D75 M3 / D100): refuse a destination that escapes ``root``.

    ``Bubble`` / ``Domain`` are unvalidated ``NewType(str)`` (a typo or an agent-built name could carry
    ``..`` or an absolute path); concatenated into a path they could land the personal IP OUTSIDE the
    gitignored zone (a git-trackable spot, or off the repo entirely). We never write there — a malformed
    label RAISES rather than silently escaping the guardrail. Normalises ``..`` via ``resolve()``."""
    if not dest.resolve().is_relative_to(root.resolve()):
        raise ValueError(
            f"triage refuses to write outside {root} (got {dest}) — a bubble/domain name must not "
            "escape its gitignored zone (D100 fail-closed / Step 3 guardrail)"
        )
    return dest


def _destination(
    entry: TriageEntry,
    *,
    knowledge_root: Path,
    projects_root: Path,
    project: Bubble,
    working_subdir: str | None = None,
) -> Path | None:
    """Where an entry belongs. A SOURCE is shelved on its hierarchical taxonomy path
    (``knowledge/raw/<Famille>/<Groupe>/<domain>/<type>/``, via :func:`taxonomy.shelf_rel`) — shared,
    not project-nested (D137 asymmetry); a WORKING file keeps its tree under the project bubble
    (``projects/<project>/[<working_subdir>/]``); NOISE has no destination.

    A SOURCE whose proposed domain is OUTSIDE the taxonomy mapping is not guessed onto a shelf: it lands
    in the ``knowledge/raw/_intake`` airlock, surfaced for a human to place, never lost or mis-shelved (D85 /
    fail toward surfacing). ``working_subdir`` namespaces working material by its SOURCE root (e.g.
    ``example_research``), which REDUCES collisions when several raw folders merge into ONE bubble and keeps each
    sub-project's identity — but two roots sharing a leaf name can still clash, so the residual is caught
    by the collision guard in :func:`resolve_moves` (never a silent overwrite, D85). Sources are NOT
    namespaced — they dedupe on the shared shelf (the whole point of the D137 asymmetry). Every
    destination is confinement-checked (:func:`_ensure_within`) so a malformed label can't escape."""
    if entry.disposition is Disposition.SOURCE:
        assert entry.domain is not None  # SOURCE always carries a proposed domain
        shelf = taxonomy.shelf_rel(
            str(entry.domain)
        )  # <Fam>/<Grp>/<domain>/<type> from taxonomy.toml
        base = knowledge_root / "raw" / (shelf if shelf is not None else Path(_INTAKE_DIRNAME))
        return _ensure_within(base / entry.relative.name, knowledge_root)
    if entry.disposition is Disposition.WORKING:
        base = projects_root / str(project)
        if working_subdir is not None:
            base = base / working_subdir
        return _ensure_within(base / entry.relative, projects_root)
    return None


def resolve_moves(
    plan: TriagePlan,
    *,
    knowledge_root: Path,
    projects_root: Path,
    seen_hashes: dict[str, Path] | None = None,
    working_subdir: str | None = None,
) -> tuple[Move, ...]:
    """Resolve the plan's SOURCE/WORKING entries into concrete moves, deduping sources by content.

    A source whose bytes are already shelved (same sha256) becomes a ``dedup-skip`` (no second copy);
    a name clash with DIFFERENT bytes becomes a ``collision-rename`` (short hash suffix). NOISE is
    dropped. Working material is namespaced under ``working_subdir`` (default: the source root's name)
    to REDUCE collisions; a residual clash (two roots, same leaf name, or a re-run) is caught by the
    SAME collision guard — never a silent ``shutil.move`` overwrite (audit D75 M1 / D85). Pure
    resolution — no file is touched here (so it is unit-testable). The ``seen`` map records the
    ACTUAL on-disk dest (post-rename), so a later duplicate dedups onto the real file."""
    seen: dict[str, Path] = {} if seen_hashes is None else seen_hashes
    subdir = plan.root.name if working_subdir is None else working_subdir
    taken: set[Path] = (
        set()
    )  # dests already claimed in THIS resolution (catches within-run clashes)
    moves: list[Move] = []
    for entry in plan.entries:
        if entry.disposition is Disposition.NOISE:
            continue
        src = plan.root / entry.relative
        dest = _destination(
            entry,
            knowledge_root=knowledge_root,
            projects_root=projects_root,
            project=plan.project,
            working_subdir=subdir,
        )
        if dest is None:
            continue
        if entry.disposition is Disposition.SOURCE:
            digest = _sha256(src)
            if digest in seen:
                moves.append(Move(entry, src, seen[digest], "dedup-skip"))
                continue
            if dest.exists() or dest in taken:
                dest = dest.with_name(f"{dest.stem}.{digest[:8]}{dest.suffix}")
                moves.append(Move(entry, src, dest, "collision-rename"))
            else:
                moves.append(Move(entry, src, dest, "move"))
            seen[digest] = dest
            taken.add(dest)
        else:  # WORKING — same anti-overwrite guard; a clash is renamed, never silently clobbered.
            if dest.exists() or dest in taken:
                digest = _sha256(src)
                dest = dest.with_name(f"{dest.stem}.{digest[:8]}{dest.suffix}")
                moves.append(Move(entry, src, dest, "collision-rename"))
            else:
                moves.append(Move(entry, src, dest, "move"))
            taken.add(dest)
    return moves


def execute_plan(
    plan: TriagePlan,
    *,
    knowledge_root: Path,
    projects_root: Path,
    dry_run: bool = True,
    copy: bool = False,
    seen_hashes: dict[str, Path] | None = None,
    working_subdir: str | None = None,
) -> ExecReport:
    """Relocate the plan's signal into its gitignored homes (Step 3). DRY-RUN BY DEFAULT.

    Sources are shelved (deduped) under ``knowledge_root/raw/<Famille>/<Groupe>/<domain>/<type>/``
    (an off-taxonomy domain → the ``_intake`` airlock), working material under
    ``projects_root/<project>/<source-root>/``, noise is left untouched. With ``dry_run`` (default)
    nothing is written — the returned :class:`ExecReport` is exactly what WOULD happen, to eyeball
    first. Set ``copy=True`` to duplicate instead of move (leaves the raw corpus intact)."""
    moves = resolve_moves(
        plan,
        knowledge_root=knowledge_root,
        projects_root=projects_root,
        seen_hashes=seen_hashes,
        working_subdir=working_subdir,
    )
    if not dry_run:
        import shutil

        for m in moves:
            if m.action == "dedup-skip":
                continue
            m.dest.parent.mkdir(parents=True, exist_ok=True)
            if copy:
                shutil.copy2(m.src, m.dest)
            else:
                shutil.move(str(m.src), str(m.dest))
    return ExecReport(moves=tuple(moves), dry_run=dry_run)


def plan_many(
    roots: Iterable[tuple[Path | str, Bubble, Domain]],
) -> Sequence[TriagePlan]:
    """Plan several raw folders at once (Example Research + the sibling project share the 'trading' bubble +
    'finance' primary domain). A thin convenience over :func:`plan_triage`."""
    return [
        plan_triage(root, project=project, primary_domain=domain) for root, project, domain in roots
    ]
