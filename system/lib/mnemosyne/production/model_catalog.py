"""ModelCatalog (C9) — the declared basket of LOCAL models, VERIFIED against the disk.

**What this closes.** Nothing declared which models this machine holds. 12 MLX repos, 103 GiB, and
three separate hard-coded defaults decided for everyone: ``runner_mlx._DEFAULT_MODEL_ID``,
``distill_book._MODEL``, ``caption_mlx._DEFAULT_MODEL``. The measured proof of the defect is written
into this repo's own plan — an agent concluded *"no model installed"* with 103 GiB on disk.

**There is no default any more, and that is the point.** The operator: *"I don't like being boxed
into 'oh, this is the agent I use, not that one.'"* So the silent default is replaced by a REFUSAL
THAT NAMES: :func:`resolve_model_id` refuses when nobody named a model, and prints the basket. *The
default branch is where silence hides* — this module removes the branch.

**The declaration is verified against the disk, BOTH WAYS, on every call.** A hand-kept index rots
in hours; a verified one cannot lie in silence. Declared-and-absent → ``modele_absent``;
present-and-undeclared → ``modele_non_declare``; declared weight drifted from the disk →
``poids_derive``. The measured cost of the full scan is **0.9 ms** (16 repos, snapshot-resolved), so
the door is never slower than the wall it guards — the whole check costs less than a millisecond
against a load that costs gigabytes.

**The basket has a declared SCOPE, and what it excludes is NAMED, never dropped.** Only
``mlx-community/*`` repos are judged: ``BAAI/bge-m3``, ``BAAI/bge-reranker-v2-m3`` and
``docling-project/*`` are retrieval and OCR bricks, not brains. An excluded population is UNJUDGED,
not safe — so :func:`reconcile` returns them separately and ``make modeles`` prints them by name.

**Presence is not a directory name.** A repo directory exists from the first byte of a download.
Presence here means: the revision resolves (``refs/main`` → ``snapshots/<sha>``, or a single
snapshot when no ref) AND every entry of that snapshot resolves to a real file. Measured why:
``Qwen2.5-VL-7B-Instruct-4bit`` carries a leftover ``*.incomplete`` blob from an interrupted
download while its snapshot is whole — so ``.incomplete`` alone is NOT absence, and a checker keyed
on it would have refused a model that loads fine.

Read by the standard-library ``tomllib`` — no dependency (D116). Nothing here writes: adding a line
to the protected zone is the operator's gesture (``POLICY_WRITE``, SE4 / D102); the refusal EMITS
the exact lines to paste, the way ``domain-new`` emits its policy line. Code & docstrings English
(D117); human-facing text is English in this public mirror (the private original keeps it French,
D33).

Decisions: D95 (one big model at a time, 32 GB) · D104 / D103 (MLX runner, sole importer) ·
D70 / D26 (declarative, model-agnostic — adding a model is a CONFIG act) · SE4 / D102 (protected
zone) · D89 / D100 (deny-by-default, structural incapacity).
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final

__all__ = [
    "BASKET_PREFIX",
    "DEFAULT_MODELS_PATH",
    "ENV_TEXT_MODEL",
    "ENV_VISION_MODEL",
    "REFUSAL_LABEL",
    "CatalogRefusal",
    "DiskModel",
    "ModelCard",
    "ModelCatalog",
    "ModelRefused",
    "Reconciliation",
    "basket_report",
    "emit_declaration",
    "hub_root",
    "reconcile",
    "resolve_model_id",
    "scan_hub",
]

#: The protected model zone: ``<repo>/system/config/models.toml`` (sibling of ``skills.toml`` /
#: ``tools.toml``), resolved from this module's home (``…/production/model_catalog.py`` →
#: ``parents[3]`` is ``system``).
DEFAULT_MODELS_PATH: Final[Path] = Path(__file__).resolve().parents[3] / "config" / "models.toml"

#: The declared SCOPE of the basket. Read from the file at load; this is the fallback used when the
#: file is absent, so the two never disagree about what "out of basket" means.
BASKET_PREFIX: Final = "mlx-community/"

#: The env channels through which a caller NAMES its model. Two distinct names on purpose: a text
#: decode and a vision decode are different jobs, and one variable would let ``MODELE=phi-4-4bit``
#: silently become the EYE of the captioner. Neither has a default — unset means REFUSED, never
#: "pick something". Surfaced as ``MODELE=`` / ``MODELE_VISION=`` on the make line.
ENV_TEXT_MODEL: Final = "MNEMO_MODELE"
ENV_VISION_MODEL: Final = "MNEMO_MODELE_VISION"

#: Every refusal this module can name, and what triggered it — declared as a mapping so a refusal
#: added without a sentence raises a ``KeyError`` at the surface instead of printing a token nobody
#: can act on (the same contract ``plan_scaffold.REFUSAL_LABEL`` holds).
REFUSAL_LABEL: Final = {
    "modele_non_nomme": "no model named — the local engine no longer guesses which one to use",
    "modele_hors_panier": "the named model is not declared in the basket",
    "modele_absent": "a model declared in the basket is NOT FOUND on disk",
    "modele_non_declare": "a model is on disk but declared nowhere",
    "poids_derive": "the declared weight no longer matches what the disk carries",
    "revision_ambigue": "several revisions on disk and no readable `refs/main`",
    "fichier_illisible": "a piece of the model does not resolve — interrupted download",
    "panier_absent": "no basket declared — `system/config/models.toml` is missing",
    "panier_vide": "the basket declares no model",
    "identite_dupliquee": "two basket entries carry the same `id`",
    "octets_invalides": "a declared `octets` is not a positive integer",
    "identite_manquante": "a basket entry has no `id`",
    "hors_portee": "a declared `id` does not respect the basket's prefix",
}

#: 32 GB of RAM, 10 cores, ONE big model at a time (D95). Printed per line so "does it fit" is read
#: off the report rather than computed by the reader.
RAM_BYTES: Final = 32 * 1024**3


@dataclass(frozen=True, slots=True)
class CatalogRefusal:
    """One named reason, and what it landed on. The token is the contract; the label is for humans."""

    reason: str
    detail: str

    @property
    def label(self) -> str:
        """The human-readable sentence for this token. Raises on an unknown token rather than
        defaulting — a refusal that degrades to a generic message is a refusal nobody can act on."""
        return REFUSAL_LABEL[self.reason]

    def __str__(self) -> str:
        return f"{self.reason} : {self.label} — {self.detail}"


class ModelRefused(RuntimeError):
    """The named refusal every model seam raises. Carries the refusals AND prints the basket.

    Printing the basket is not decoration: the whole reason a default existed was that nobody knew
    what was installed. A refusal that says "name a model" without saying WHICH ones exist just moves
    the guess one step out."""

    def __init__(self, refusals: Iterable[CatalogRefusal], *, basket: str = "") -> None:
        self.refusals: tuple[CatalogRefusal, ...] = tuple(refusals)
        self.basket = basket
        body = "\n".join(f"  \U000026D4 {r}" for r in self.refusals)
        super().__init__(f"{body}\n\n{basket}" if basket else body)


@dataclass(frozen=True, slots=True)
class ModelCard:
    """One DECLARED model: the id ``mlx_lm.load()`` receives, and the snapshot weight in bytes.

    Deliberately two fields. Every capability field an audit might want here — "fast", "good at
    code", "recommended" — would be a claim nobody measured on this machine, and a future agent
    reads an invented field as a fact. The bench (C15) adds ``[[mesures]]``, WITH its command."""

    id: str
    octets: int

    @property
    def gib(self) -> float:
        return self.octets / 1024**3


@dataclass(frozen=True, slots=True)
class DiskModel:
    """What the disk actually holds for one repo — measured, never declared."""

    id: str
    octets: int
    revision: str | None = None
    #: Snapshot entries whose target does not resolve (interrupted download). Non-empty ⇒ ABSENT.
    unresolved: tuple[str, ...] = ()
    #: Several snapshots and no readable ``refs/main`` — the revision cannot be named, so neither
    #: can the weight. Fail-closed: this is a refusal, not a guess at which revision was meant.
    ambiguous: bool = False

    @property
    def whole(self) -> bool:
        return not self.unresolved and not self.ambiguous and self.octets > 0

    @property
    def gib(self) -> float:
        return self.octets / 1024**3


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """The verdict of declaration ↔ disk, both ways, plus the population deliberately NOT judged."""

    refusals: tuple[CatalogRefusal, ...] = ()
    #: Declared AND whole on disk — the models a caller may actually name.
    usable: tuple[str, ...] = ()
    #: Repos in the cache outside the basket prefix, NAMED so the exclusion stays visible. An
    #: excluded population is unjudged, not safe — a silent filter is how a hole hides.
    out_of_scope: tuple[str, ...] = ()
    milliseconds: float = 0.0
    _cards: Mapping[str, ModelCard] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def ok(self) -> bool:
        return not self.refusals


# ── the disk ─────────────────────────────────────────────────────────────────────────────────────


def hub_root(env: Mapping[str, str] | None = None) -> Path:
    """The Hugging Face hub cache this machine reads, honouring the HF stack's own precedence.

    ``HF_HUB_CACHE`` > ``HF_HOME/hub`` > ``~/.cache/huggingface/hub``. Read from ``env`` rather than
    captured at import: ``local_first.enforce_local_first`` rewrites these before the bricks load,
    and a constant frozen at import would name a directory nobody is using."""
    source = os.environ if env is None else env
    if explicit := source.get("HF_HUB_CACHE"):
        return Path(explicit)
    if home := source.get("HF_HOME"):
        return Path(home) / "hub"
    return Path(source.get("HOME", str(Path.home()))) / ".cache" / "huggingface" / "hub"


def _repo_id(directory_name: str) -> str:
    """``models--mlx-community--phi-4-4bit`` → ``mlx-community/phi-4-4bit`` (the HF cache convention)."""
    return directory_name[len("models--") :].replace("--", "/")


def _snapshot(repo_dir: Path) -> tuple[Path | None, str | None, bool]:
    """Resolve the revision to read: ``(snapshot_dir, revision, ambiguous)``.

    ``refs/main`` first — the revision the cache itself considers current. When it is missing or
    points nowhere, a SINGLE snapshot directory is unambiguous and is used; SEVERAL is ambiguous and
    refuses rather than picking one, because the weight of the wrong revision is a plausible-looking
    lie."""
    try:
        revision = (repo_dir / "refs" / "main").read_text(encoding="utf-8").strip()
    except OSError:
        revision = ""
    if revision and (repo_dir / "snapshots" / revision).is_dir():
        return repo_dir / "snapshots" / revision, revision, False
    try:
        candidates = sorted(d for d in (repo_dir / "snapshots").iterdir() if d.is_dir())
    except OSError:
        return None, None, False
    if len(candidates) == 1:
        return candidates[0], candidates[0].name, False
    return None, revision or None, len(candidates) > 1


def scan_hub(root: Path | None = None) -> Mapping[str, DiskModel]:
    """Every model repo in the cache, with its snapshot weight — measured at 0.9 ms for 16 repos.

    ``os.scandir`` + one ``stat`` per snapshot entry, never a recursive walk of ``blobs/``: the walk
    would re-count superseded revisions, and this must answer "what does THIS revision weigh".
    A missing cache is an EMPTY mapping, never an error — a fresh machine holds no model, and that
    is a state to report, not a crash."""
    hub = hub_root() if root is None else root
    found: dict[str, DiskModel] = {}
    try:
        entries = list(os.scandir(hub))
    except OSError:
        return MappingProxyType({})
    for entry in entries:
        if not entry.name.startswith("models--") or not entry.is_dir():
            continue
        repo = _repo_id(entry.name)
        snapshot, revision, ambiguous = _snapshot(Path(entry.path))
        if snapshot is None:
            found[repo] = DiskModel(repo, 0, revision, (), ambiguous)
            continue
        total = 0
        unresolved: list[str] = []
        try:
            for piece in os.scandir(snapshot):
                try:
                    # follow_symlinks: the snapshot is symlinks into blobs/; a dangling one is an
                    # interrupted download, and stat RAISES rather than quietly reporting the link.
                    total += piece.stat().st_size
                except OSError:
                    unresolved.append(piece.name)
        except OSError:
            unresolved.append("(unreadable snapshot)")
        found[repo] = DiskModel(repo, total, revision, tuple(sorted(unresolved)), False)
    return MappingProxyType(found)


# ── the declaration ──────────────────────────────────────────────────────────────────────────────


class ModelCatalog:
    """The declared basket, read from the protected zone. Read-only, structurally (D100).

    Building it wires nothing and loads nothing: it advertises what the operator declared, and the
    seams ask it before they touch a weight."""

    __slots__ = ("_by_id", "_prefix", "_measured_on", "_source")

    def __init__(
        self,
        cards: Iterable[ModelCard] = (),
        *,
        prefix: str = BASKET_PREFIX,
        measured_on: str = "",
        source: Path | None = None,
    ) -> None:
        by_id: dict[str, ModelCard] = {}
        for card in cards:
            if card.id in by_id:
                raise ModelRefused(
                    [CatalogRefusal("identite_dupliquee", card.id)],
                    basket=f"only one entry per `id` in {source or DEFAULT_MODELS_PATH}",
                )
            by_id[card.id] = card
        self._by_id: Mapping[str, ModelCard] = MappingProxyType(by_id)
        self._prefix = prefix
        self._measured_on = measured_on
        self._source = source if source is not None else DEFAULT_MODELS_PATH

    @classmethod
    def load(cls, path: Path | None = None) -> ModelCatalog:
        """Load ``models.toml``. A MISSING file is an EMPTY basket, not an exception.

        Empty rather than raising for one measured reason: this loader runs inside ``make modeles``,
        the surface whose whole job is to say what is wrong. A raise there prints a traceback where
        a named refusal belongs — so absence becomes the ``panier_absent`` refusal at
        :func:`reconcile`, one layer up, where it is printed with the gesture that repairs it."""
        source = DEFAULT_MODELS_PATH if path is None else path
        if not source.exists():
            return cls((), source=source)
        data = tomllib.loads(source.read_text(encoding="utf-8"))
        basket = data.get("panier", {})
        return cls(
            _parse_cards(data.get("modeles", []), prefix=str(basket.get("prefixe", BASKET_PREFIX))),
            prefix=str(basket.get("prefixe", BASKET_PREFIX)),
            measured_on=str(basket.get("mesure_le", "")),
            source=source,
        )

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def source(self) -> Path:
        return self._source

    @property
    def measured_on(self) -> str:
        return self._measured_on

    def ids(self) -> tuple[str, ...]:
        return tuple(self._by_id)

    def cards(self) -> tuple[ModelCard, ...]:
        return tuple(self._by_id.values())

    def card(self, model_id: str) -> ModelCard | None:
        return self._by_id.get(model_id)


def _parse_cards(rows: object, *, prefix: str) -> tuple[ModelCard, ...]:
    """Parse ``[[modeles]]``, fail-closed on every malformed row.

    A typo in the protected zone must fail LOUDLY, never widen or default (D100). ``octets`` in
    particular: a missing or zero weight would make ``poids_derive`` unable to fire, and a check
    that cannot fire is not a barrier."""
    if not isinstance(rows, list):
        raise ModelRefused([CatalogRefusal("panier_vide", "[[modeles]] is not an array")])
    cards: list[ModelCard] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ModelRefused([CatalogRefusal("identite_manquante", repr(row))])
        model_id = row.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ModelRefused([CatalogRefusal("identite_manquante", repr(row))])
        if not model_id.startswith(prefix):
            raise ModelRefused([CatalogRefusal("hors_portee", f"{model_id} (prefix {prefix!r})")])
        octets = row.get("octets")
        if not isinstance(octets, int) or isinstance(octets, bool) or octets <= 0:
            raise ModelRefused([CatalogRefusal("octets_invalides", f"{model_id} : {octets!r}")])
        cards.append(ModelCard(id=model_id, octets=octets))
    return tuple(cards)


# ── declaration ↔ disk, both ways ────────────────────────────────────────────────────────────────


def reconcile(
    catalog: ModelCatalog | None = None,
    disk: Mapping[str, DiskModel] | None = None,
) -> Reconciliation:
    """Judge the declaration against the disk IN BOTH DIRECTIONS, and time the judgment.

    Both directions, because one alone rots differently: checking only *declared → disk* misses the
    model the operator downloads and nobody declares (the exact state this repo was in — 12
    undeclared models); checking only *disk → declared* misses the model that was deleted or
    half-downloaded while its line stayed. ``poids_derive`` is the third: an id can be right on both
    sides while the weight silently belongs to another revision.

    The elapsed time is CARRIED, not printed once and forgotten: the moment this check costs more
    than the load it guards, nobody uses the door, and the number has to be readable to notice."""
    import time

    started = time.perf_counter()
    cat = ModelCatalog.load() if catalog is None else catalog
    present = scan_hub() if disk is None else disk
    prefix = cat.prefix

    refusals: list[CatalogRefusal] = []
    if not cat.source.exists():
        refusals.append(CatalogRefusal("panier_absent", str(cat.source)))
    elif not cat.ids():
        refusals.append(CatalogRefusal("panier_vide", str(cat.source)))

    usable: list[str] = []
    for card in cat.cards():
        found = present.get(card.id)
        if found is None:
            refusals.append(
                CatalogRefusal("modele_absent", f"{card.id} — declared, nothing on disk")
            )
            continue
        if found.ambiguous:
            refusals.append(CatalogRefusal("revision_ambigue", card.id))
            continue
        if found.unresolved:
            refusals.append(
                CatalogRefusal("fichier_illisible", f"{card.id} : {', '.join(found.unresolved)}")
            )
            continue
        if found.octets != card.octets:
            refusals.append(
                CatalogRefusal(
                    "poids_derive",
                    f"{card.id} : declared {card.octets} bytes, disk has {found.octets}",
                )
            )
            continue
        usable.append(card.id)

    declared = set(cat.ids())
    out_of_scope: list[str] = []
    for repo in sorted(present):
        if not repo.startswith(prefix):
            out_of_scope.append(repo)
            continue
        if repo not in declared:
            refusals.append(
                CatalogRefusal("modele_non_declare", f"{repo} — on disk, absent from the basket")
            )

    return Reconciliation(
        refusals=tuple(refusals),
        usable=tuple(usable),
        out_of_scope=tuple(out_of_scope),
        milliseconds=(time.perf_counter() - started) * 1000,
        _cards=MappingProxyType({c.id: c for c in cat.cards()}),
    )


# ── the seam every model consumer goes through ───────────────────────────────────────────────────


def resolve_model_id(
    model_id: str | None = None,
    *,
    env_var: str = ENV_TEXT_MODEL,
    environ: Mapping[str, str] | None = None,
    catalog: ModelCatalog | None = None,
    disk: Mapping[str, DiskModel] | None = None,
) -> str:
    """The ONE place a local model id is decided. No default: unnamed REFUSES, and prints the basket.

    Order of the checks is load-bearing — *the order of my checks decides what is accused*. "Nobody
    named a model" is checked FIRST, before the declaration↔disk reconciliation, because a caller who
    named nothing must read ``modele_non_nomme`` and the basket, not a drift report about a model
    they never asked for. Then the named id is checked against the basket, then the basket against
    the disk: each refusal can fire alone, so each names its own cause.

    ``env_var`` is a parameter rather than a constant so the vision seam reads its OWN variable
    (:data:`ENV_VISION_MODEL`): one shared variable would let a text model become the captioner's eye
    without a word."""
    source = os.environ if environ is None else environ
    named = (model_id or source.get(env_var, "")).strip()
    cat = ModelCatalog.load() if catalog is None else catalog
    verdict = reconcile(cat, disk)

    if not named:
        raise ModelRefused(
            [
                CatalogRefusal(
                    "modele_non_nomme",
                    f"no argument, no ${env_var} — name it (e.g. `make … {_make_flag(env_var)}=<id>`)",
                )
            ],
            basket=basket_report(cat, verdict),
        )
    if cat.card(named) is None:
        raise ModelRefused(
            [CatalogRefusal("modele_hors_panier", named)],
            basket=basket_report(cat, verdict),
        )
    if named not in verdict.usable:
        raise ModelRefused(
            [r for r in verdict.refusals if named in r.detail] or list(verdict.refusals),
            basket=basket_report(cat, verdict),
        )
    return named


def _make_flag(env_var: str) -> str:
    """``MNEMO_MODELE`` → ``MODELE`` — the name on the make line, so the refusal names a gesture the
    reader can actually type. A refusal that names a problem without naming a gesture is an obstacle."""
    return env_var.removeprefix("MNEMO_")


# ── what a human reads ───────────────────────────────────────────────────────────────────────────


def basket_report(catalog: ModelCatalog, verdict: Reconciliation) -> str:
    """The basket, printed. What is usable, what is refused, and what was deliberately not judged."""
    lines = [f"DECLARED BASKET ({catalog.source}) — {len(catalog.ids())} model(s):"]
    if not catalog.ids():
        lines.append("  (empty)")
    for card in sorted(catalog.cards(), key=lambda c: -c.octets):
        mark = "\U00002705" if card.id in verdict.usable else "\U000026D4"
        share = 100 * card.octets / RAM_BYTES
        lines.append(f"  {mark} {card.id}  {card.gib:.2f} GiB  ({share:.0f}% of 32 GB of RAM)")
    if verdict.refusals:
        lines.append("")
        lines.append(f"{len(verdict.refusals)} REFUSAL(S) between the declaration and the disk:")
        lines += [f"  \U000026D4 {r}" for r in verdict.refusals]
    if verdict.out_of_scope:
        lines.append("")
        lines.append(
            f"OUT OF BASKET, hence NOT JUDGED ({len(verdict.out_of_scope)}) — retrieval / OCR"
            " bricks, not brains:"
        )
        lines += [f"  · {repo}" for repo in verdict.out_of_scope]
    lines.append("")
    lines.append("Name a model — at every call, there is no default (C9):")
    lines.append('  make local-run PROMPT="…" MODELE=<id>')
    lines.append("  make modeles                      # this basket, and what the disk says about it")
    return "\n".join(lines).rstrip() + "\n"


def emit_declaration(
    disk: Mapping[str, DiskModel] | None = None, *, prefix: str = BASKET_PREFIX
) -> str:
    """EMIT the ``[[modeles]]`` block the disk justifies, for the operator to paste into the
    protected zone.

    This module never writes ``models.toml`` — the zone is the operator's (SE4 / D102). Emitting
    from the SAME scan the reconciliation reads means the pasted line cannot disagree with the
    check that will judge it: a copy typed by hand is the thing that rots."""
    present = scan_hub() if disk is None else disk
    rows = sorted(
        (m for repo, m in present.items() if repo.startswith(prefix)),
        key=lambda m: -m.octets,
    )
    out = [f"# emitted from disk — {len(rows)} repo(s) under {prefix!r}"]
    for model in rows:
        if not model.whole:
            out.append(f"# \U000026D4 {model.id} — incomplete on disk, NOT emitted")
            continue
        out += ["", "[[modeles]]", f'id = "{model.id}"', f"octets = {model.octets}"]
    return "\n".join(out) + "\n"
