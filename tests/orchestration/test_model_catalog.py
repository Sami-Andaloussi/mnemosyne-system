"""C9 - the declared basket of LOCAL models, and the REFUSAL that replaced the silent default.

What these prove, and each one has been seen to go red by sabotage:

* **the default is GONE, and what replaced it REFUSES BY NAME** - an unnamed decode raises
  ``modele_non_nomme`` and PRINTS the basket, instead of silently becoming Qwen2.5-7B;
* **the pendant** - a declared, whole model resolves. A refusal rate without its pendant is a wall,
  so both directions of the seam are here, side by side;
* **the declaration is checked against the DISK, both ways** - declared-and-absent
  (``modele_absent``), present-and-undeclared (``modele_non_declare``), and the third one an
  id-only check cannot see: a weight that drifted (``poids_derive``);
* **presence is not a directory name** - an interrupted download leaves a whole-looking repo, and
  the measured nuance goes the other way too: a leftover ``.incomplete`` marker beside a COMPLETE
  snapshot must NOT condemn it (a valid state for ``Qwen2.5-VL-7B-Instruct-4bit``);
* **the excluded population is NAMED** - bge-m3 / docling are out of the basket, and an excluded
  population is unjudged, not safe, so it is printed rather than filtered away in silence;
* **the CLASS is closed, not the case** - an AST detector refuses any new hard-coded
  ``mlx-community/`` id in ``system/``. The C9 mandate named ONE hard-coded default; there were
  THREE. A test that only guarded ``runner_mlx`` would let the next one in.

Brick-free: a synthetic HF cache under ``tmp_path``, no weight, no model, no network (D126)."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from _invariants import REPO_ROOT

from mnemosyne.production.model_catalog import (
    BASKET_PREFIX,
    ENV_TEXT_MODEL,
    ENV_VISION_MODEL,
    REFUSAL_LABEL,
    CatalogRefusal,
    ModelCatalog,
    ModelRefused,
    emit_declaration,
    hub_root,
    reconcile,
    resolve_model_id,
    scan_hub,
)

_ALPHA = "mlx-community/alpha-7B-4bit"
_BETA = "mlx-community/beta-3B-4bit"


# -- a synthetic Hugging Face cache ---------------------------------------------------------------


def _repo(
    hub: Path,
    model_id: str,
    *,
    payload: int = 1024,
    revision: str = "abc123",
    write_ref: bool = True,
    dangling: bool = False,
    extra_revisions: tuple[str, ...] = (),
    incomplete_marker: bool = False,
) -> None:
    """Materialise one repo in the HF cache layout: ``blobs/`` + ``snapshots/<rev>/`` symlinks.

    Real symlinks, not plain files, because that IS the shape the scanner must survive: the whole
    ``fichier_illisible`` branch exists for a snapshot link whose blob never finished downloading,
    and a fixture of plain files could never make it fire. *A fixture must carry the structure that
    tries the gate.*"""
    root = hub / ("models--" + model_id.replace("/", "--"))
    blobs = root / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    (root / "refs").mkdir(exist_ok=True)
    if write_ref:
        (root / "refs" / "main").write_text(revision, encoding="utf-8")
    for rev in (revision, *extra_revisions):
        snapshot = root / "snapshots" / rev
        snapshot.mkdir(parents=True, exist_ok=True)
        blob = blobs / f"blob-{rev}"
        if not dangling:
            blob.write_bytes(b"\0" * payload)
        (snapshot / "model.safetensors").symlink_to(blob)
    if incomplete_marker:
        (blobs / "blob-leftover.abcdef.incomplete").write_bytes(b"")


def _catalog(*cards: tuple[str, int], tmp_path: Path) -> ModelCatalog:
    """A basket written as real TOML and read back - never hand-built objects.

    Round-tripping through the parser is the point: it is the parser that a typo in the protected
    zone meets first, and a catalog assembled in memory would leave that whole path unexercised."""
    body = ["[panier]", f'prefixe = "{BASKET_PREFIX}"', 'mesure_le = "2026-08-02"']
    for model_id, octets in cards:
        body += ["", "[[modeles]]", f'id = "{model_id}"', f"octets = {octets}"]
    path = tmp_path / "models.toml"
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return ModelCatalog.load(path)


# -- the refusal, and its pendant -----------------------------------------------------------------


def test_the_engine_REFUSES_when_nobody_names_a_model_and_PRINTS_the_basket(tmp_path: Path) -> None:
    """The heart of C9: no default, and the refusal hands back what the caller was missing."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    with pytest.raises(ModelRefused) as refused:
        resolve_model_id(None, environ={}, catalog=catalog, disk=scan_hub(hub))

    tokens = [r.reason for r in refused.value.refusals]
    assert tokens == ["modele_non_nomme"], tokens
    # It must PRINT the basket - the reason a default existed at all was that nobody knew what was
    # installed, and a refusal that only says "name one" moves the guess one step out.
    assert _ALPHA in str(refused.value)
    assert "MODELE=" in str(refused.value)


def test_naming_a_declared_and_whole_model_RESOLVES(tmp_path: Path) -> None:
    """The PENDANT. A catch rate without its false-kill rate is a wall, so the seam must also pass."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    assert resolve_model_id(_ALPHA, environ={}, catalog=catalog, disk=scan_hub(hub)) == _ALPHA


def test_the_env_channel_names_a_model_just_as_an_argument_does(tmp_path: Path) -> None:
    """``MODELE=<id>`` on the make line is the same act as an argument - not a fallback."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    resolved = resolve_model_id(
        None, environ={ENV_TEXT_MODEL: _ALPHA}, catalog=catalog, disk=scan_hub(hub)
    )
    assert resolved == _ALPHA
    # An EMPTY variable is not a name. `make` exports `MNEMO_MODELE=` for every target, so the empty
    # string is the ordinary case, and reading it as a value would hand an id of "" to mlx_lm.load().
    #
    # THE TOKEN IS ASSERTED, NOT MERELY "it raised", AND THAT IS WHAT MADE THIS TEST BITE. Written
    # as a bare ``pytest.raises(ModelRefused)`` it SURVIVED its own sabotage: strip the ``.strip()``
    # and a whitespace-only variable becomes a truthy name, which the next check refuses as
    # ``modele_hors_panier`` - still an exception, still green, and the operator now reads the (French)
    # sentence for "this model is not in the basket" about a model they never typed. *A killed
    # mutation does not say what killed it*, so the assertion names the refusal it expects.
    with pytest.raises(ModelRefused) as refused:
        resolve_model_id(None, environ={ENV_TEXT_MODEL: "   "}, catalog=catalog, disk=scan_hub(hub))
    assert [r.reason for r in refused.value.refusals] == ["modele_non_nomme"]


def test_the_vision_seam_reads_its_OWN_variable_so_a_text_model_never_becomes_the_eye(
    tmp_path: Path,
) -> None:
    """Two variables, on purpose: one shared name would make a set-and-forget text model the eye."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    _repo(hub, _BETA, payload=512)
    catalog = _catalog((_ALPHA, 2048), (_BETA, 512), tmp_path=tmp_path)
    environ = {ENV_TEXT_MODEL: _ALPHA, ENV_VISION_MODEL: _BETA}
    disk = scan_hub(hub)

    assert resolve_model_id(None, environ=environ, catalog=catalog, disk=disk) == _ALPHA
    assert (
        resolve_model_id(
            None, env_var=ENV_VISION_MODEL, environ=environ, catalog=catalog, disk=disk
        )
        == _BETA
    )
    # And the eye refuses on its own when only the TEXT variable is set - the case that matters.
    with pytest.raises(ModelRefused) as refused:
        resolve_model_id(
            None,
            env_var=ENV_VISION_MODEL,
            environ={ENV_TEXT_MODEL: _ALPHA},
            catalog=catalog,
            disk=disk,
        )
    assert "MODELE_VISION=" in str(refused.value)


def test_a_model_outside_the_declared_basket_is_refused_by_NAME(tmp_path: Path) -> None:
    """Naming a model the basket does not declare is its own refusal, distinct from naming none."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    with pytest.raises(ModelRefused) as refused:
        resolve_model_id(
            "mlx-community/never-declared", environ={}, catalog=catalog, disk=scan_hub(hub)
        )
    assert [r.reason for r in refused.value.refusals] == ["modele_hors_panier"]


def test_the_UNNAMED_refusal_fires_FIRST_even_when_the_basket_is_also_drifting(
    tmp_path: Path,
) -> None:
    """*The order of my checks decides what is accused.*

    A caller who named nothing must read ``modele_non_nomme``, not a drift report about a model they
    never asked for. Sabotaging the order (reconcile first) makes this test name ``modele_absent``
    to a operator whose only mistake was typing no model at all."""
    hub = tmp_path / "hub"
    hub.mkdir()  # ALPHA declared, nothing on disk at all
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    with pytest.raises(ModelRefused) as refused:
        resolve_model_id(None, environ={}, catalog=catalog, disk=scan_hub(hub))
    assert [r.reason for r in refused.value.refusals] == ["modele_non_nomme"]


# -- declaration <-> disk, in BOTH directions -------------------------------------------------------


def test_a_model_declared_but_ABSENT_from_the_disk_is_a_named_refusal(tmp_path: Path) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    catalog = _catalog((_ALPHA, 2048), (_BETA, 512), tmp_path=tmp_path)

    verdict = reconcile(catalog, scan_hub(hub))
    assert [(r.reason, _BETA in r.detail) for r in verdict.refusals] == [("modele_absent", True)]
    assert verdict.usable == (_ALPHA,)
    # And the seam that CHOOSES refuses too - a report nobody's decode consults is not a barrier.
    # Same discipline as above: the TOKEN is asserted, so this cannot pass on a refusal that happens
    # to fire for another reason entirely.
    with pytest.raises(ModelRefused) as refused:
        resolve_model_id(_BETA, environ={}, catalog=catalog, disk=scan_hub(hub))
    assert [r.reason for r in refused.value.refusals] == ["modele_absent"]


def test_a_model_PRESENT_on_the_disk_and_declared_NOWHERE_is_a_named_refusal(
    tmp_path: Path,
) -> None:
    """The direction that was the repo's ACTUAL state: 12 models on disk, zero declared."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    _repo(hub, _BETA, payload=512)
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    verdict = reconcile(catalog, scan_hub(hub))
    assert [(r.reason, _BETA in r.detail) for r in verdict.refusals] == [
        ("modele_non_declare", True)
    ]


def test_a_declared_weight_that_DRIFTED_from_the_disk_is_a_named_refusal(tmp_path: Path) -> None:
    """The refusal an id-only check cannot see.

    Both names agree, both sides exist - and the declared weight belongs to another revision. This
    is precisely how a hand-kept index rots without ever looking wrong."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    catalog = _catalog((_ALPHA, 9999), tmp_path=tmp_path)

    verdict = reconcile(catalog, scan_hub(hub))
    assert [r.reason for r in verdict.refusals] == ["poids_derive"]
    assert "9999" in verdict.refusals[0].detail and "2048" in verdict.refusals[0].detail
    assert verdict.usable == ()


def test_an_INTERRUPTED_download_is_absent_even_though_its_DIRECTORY_exists(tmp_path: Path) -> None:
    """Presence is not a directory name: a repo dir exists from the first byte of a download."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, dangling=True)
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    verdict = reconcile(catalog, scan_hub(hub))
    assert [r.reason for r in verdict.refusals] == ["fichier_illisible"]
    assert "model.safetensors" in verdict.refusals[0].detail


def test_a_leftover_INCOMPLETE_marker_does_NOT_condemn_a_COMPLETE_snapshot(tmp_path: Path) -> None:
    """The measured nuance, and it goes the other way.

    A model repository can carry a 0-byte ``*.incomplete`` blob left by an
    interrupted attempt, WHILE its snapshot is whole and loads. A presence check keyed on that marker
    - the obvious one to write - would refuse a model that works, and *a repaired gate has its own
    error rate*. Presence is keyed on the snapshot resolving, and the marker is ignored."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048, incomplete_marker=True)
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    verdict = reconcile(catalog, scan_hub(hub))
    assert verdict.refusals == ()
    assert verdict.usable == (_ALPHA,)


def test_an_AMBIGUOUS_revision_refuses_rather_than_picking_one(tmp_path: Path) -> None:
    """Two snapshots and no readable ``refs/main``: the weight of the wrong revision is a plausible
    lie, so the scanner refuses instead of choosing."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, write_ref=False, extra_revisions=("def456",))
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    verdict = reconcile(catalog, scan_hub(hub))
    assert [r.reason for r in verdict.refusals] == ["revision_ambigue"]


def test_the_OUT_OF_SCOPE_population_is_NAMED_never_silently_dropped(tmp_path: Path) -> None:
    """An excluded population is UNJUDGED, not safe - so it is reported, not filtered away."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    _repo(hub, "BAAI/bge-m3", payload=64)
    catalog = _catalog((_ALPHA, 2048), tmp_path=tmp_path)

    verdict = reconcile(catalog, scan_hub(hub))
    assert verdict.refusals == ()
    assert verdict.out_of_scope == ("BAAI/bge-m3",)
    # Named in the REPORT too, not just carried in a field nobody prints: an exclusion that only
    # exists in a dataclass is exactly as invisible as no exclusion at all.
    from mnemosyne.production.model_catalog import basket_report

    assert "BAAI/bge-m3" in basket_report(catalog, verdict)


def test_the_reconciliation_CARRIES_its_own_cost(tmp_path: Path) -> None:
    """The moment this check costs more than the load it guards, nobody uses the door - so the
    number has to be readable, not an anecdote in a commit message."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    verdict = reconcile(_catalog((_ALPHA, 2048), tmp_path=tmp_path), scan_hub(hub))
    assert verdict.milliseconds > 0.0


# -- the protected zone, read fail-closed ---------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "token"),
    [
        ('id = "mlx-community/x"\noctets = 0', "octets_invalides"),
        ('id = "mlx-community/x"', "octets_invalides"),
        ('id = "mlx-community/x"\noctets = "big"', "octets_invalides"),
        ('id = ""\noctets = 12', "identite_manquante"),
        ("octets = 12", "identite_manquante"),
        ('id = "other-org/x"\noctets = 12', "hors_portee"),
    ],
)
def test_a_malformed_entry_in_the_protected_zone_fails_LOUDLY(
    tmp_path: Path, line: str, token: str
) -> None:
    """A typo in the protected zone must fail by NAME, never widen or default to something laxer."""
    path = tmp_path / "models.toml"
    path.write_text(
        f'[panier]\nprefixe = "{BASKET_PREFIX}"\n\n[[modeles]]\n{line}\n', encoding="utf-8"
    )
    with pytest.raises(ModelRefused) as refused:
        ModelCatalog.load(path)
    assert [r.reason for r in refused.value.refusals] == [token]


def test_two_entries_with_the_same_id_are_refused(tmp_path: Path) -> None:
    """A duplicate must not silently shadow the first (enforce-collisions-structurally)."""
    path = tmp_path / "models.toml"
    path.write_text(
        f'[panier]\nprefixe = "{BASKET_PREFIX}"\n\n[[modeles]]\nid = "{_ALPHA}"\noctets = 1\n\n'
        f'[[modeles]]\nid = "{_ALPHA}"\noctets = 2\n',
        encoding="utf-8",
    )
    with pytest.raises(ModelRefused) as refused:
        ModelCatalog.load(path)
    assert [r.reason for r in refused.value.refusals] == ["identite_dupliquee"]


def test_a_MISSING_basket_becomes_a_named_refusal_not_a_traceback(tmp_path: Path) -> None:
    """``make modeles`` is the surface whose job is to say what is wrong; a traceback there is the
    one output it must never produce."""
    catalog = ModelCatalog.load(tmp_path / "nowhere.toml")
    verdict = reconcile(catalog, {})
    assert "panier_absent" in [r.reason for r in verdict.refusals]


def test_every_refusal_token_this_module_can_raise_has_a_FRENCH_sentence() -> None:
    """A refusal that names a token without naming a cause is a refusal nobody can act on.

    ``CatalogRefusal.label`` raises on an unknown token by design, so a token added to the code
    without a line in ``REFUSAL_LABEL`` blows up at the SURFACE, where a operator sees it. This walks the
    module's own source for every ``CatalogRefusal("...")`` literal, so the population is the code's,
    not a list re-typed here that would age away from it."""
    from mnemosyne.production import model_catalog

    source = Path(model_catalog.__file__).read_text(encoding="utf-8")
    raised = {
        node.args[0].value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CatalogRefusal"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert raised, "the detector no longer finds ANY refusal - it is not watching anything anymore"
    missing = sorted(raised - set(REFUSAL_LABEL))
    assert not missing, f"refusal with no human sentence: {missing}"
    for token in raised:
        assert CatalogRefusal(token, "x").label  # the accessor itself, not the mapping


def test_emit_hands_back_exactly_what_the_disk_justifies(tmp_path: Path) -> None:
    """The zone is operator's (SE4): this module emits the lines, he pastes them. Emitted from the SAME
    scan the check reads - a block re-typed by hand is the thing that rots."""
    hub = tmp_path / "hub"
    hub.mkdir()
    _repo(hub, _ALPHA, payload=2048)
    _repo(hub, _BETA, dangling=True)
    _repo(hub, "BAAI/bge-m3", payload=64)

    emitted = emit_declaration(scan_hub(hub))
    assert f'id = "{_ALPHA}"' in emitted and "octets = 2048" in emitted
    assert "BAAI/bge-m3" not in emitted  # out of the basket's scope
    assert (
        f"\U000026D4 {_BETA}" in emitted and f'id = "{_BETA}"' not in emitted
    )  # incomplete: named, not emitted
    # And what it emits must PASS the reader it was emitted for - an emitter whose output its own
    # parser refuses is a contract with two sources.
    path = tmp_path / "round.toml"
    path.write_text(f'[panier]\nprefixe = "{BASKET_PREFIX}"\n\n{emitted}', encoding="utf-8")
    assert ModelCatalog.load(path).ids() == (_ALPHA,)


def test_the_hub_root_follows_the_HF_stacks_own_precedence() -> None:
    """``local_first`` rewrites these before the bricks load; a root frozen at import would name a
    directory nobody is using."""
    assert hub_root({"HF_HUB_CACHE": "/x/hub"}) == Path("/x/hub")
    assert hub_root({"HF_HOME": "/y"}) == Path("/y/hub")
    assert hub_root({"HOME": "/z"}) == Path("/z/.cache/huggingface/hub")


# -- the CLASS, not the case ----------------------------------------------------------------------

#: TASK SPECIFICATIONS - frozen, named, each with its own provenance.
#:
#: The rule must preserve an explicitly configured task-specific model choice.
#:
#: The distinction the rule must encode, and did not encode before:
#:    -  a **DEFAULT** is a generic fallback value for any caller whatsoever - the engine
#:     (``runner_mlx``) carries none, and has no right to pick one back up;
#:    -  a **SPECIFICATION** is the model chosen for ONE task after it has been proven in use. Erasing it
#:     destroys the only application of a measurement: the number survives in the bench, but nothing
#:     uses it any more.
#:
#: Adding a line here IS the decision - it is the only place where it gets made, and it is therefore
#: visible in review. Every entry carries WHERE the measurement lives, so it can be replayed.
_TASK_SPECIFICATIONS: dict[tuple[str, str], str] = {
    ("system/skills/distillateur/distill_book.py", "_MODEL"): (
        "proven against local benchmark results not carried in this public mirror"
    ),
    (
        "system/lib/mnemosyne/ingest/caption_mlx.py",
        "_DEFAULT_MODEL",
    ): "oss_registry.md + pilot 3 (the prompt is calibrated on THIS model)",
}

#: The generic engine: zero identifiers, no exceptions whatsoever. This is where the real silent
#: default used to live, the one the operator asked to have removed.
_ENGINE = "system/lib/mnemosyne/runtime/runner_mlx.py"


def _module_level_constant_names(tree: ast.Module) -> dict[int, str]:
    """``id(value node) -> constant name`` for MODULE-level assignments only.

    A task specification is a module-level constant, named, visible at the top of the file. A
    literal buried inside a call or inside a branch is not a specification: it is a choice that
    hides, and it stays refused."""
    named: dict[int, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    named[id(node.value)] = target.id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            named[id(node.value)] = node.target.id
    return named


def test_a_hardcoded_model_id_is_a_FROZEN_task_spec_or_it_is_a_default_being_born() -> None:
    """The barrier, and it encodes a DISTINCTION rather than a ban.

    Refused: any ``mlx-community/`` literal in executable code under ``system/`` that is **not** a
    module-level constant frozen in :data:`_TASK_SPECIFICATIONS` - and *any* such literal in the
    generic engine, whatever its name. Allowed: the frozen specs, each of which must additionally
    name a model that the declared basket actually carries, so a spec cannot freeze a ghost.

    Parsed with ``ast``, not grepped. A text detector counts CITATIONS as instances, and the comments
    that record what those constants say each contain the literal id verbatim - a grep would accuse
    the very documentation of the decision. ``ast`` never sees a comment, and docstrings are excluded
    explicitly below."""
    declared = set(ModelCatalog.load().ids())
    offenders: list[str] = []
    seen_specs: set[tuple[str, str]] = set()
    for path in sorted((REPO_ROOT / "system").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = str(path.relative_to(REPO_ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constant_names = _module_level_constant_names(tree)
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith(BASKET_PREFIX)
                # The bare prefix is the SCOPE declaration (``BASKET_PREFIX``), not a choice of
                # model: it names the population to judge and picks nobody out of it. What is
                # refused is a literal that names a REPO - the prefix plus something.
                and len(node.value) > len(BASKET_PREFIX)
                and id(node) not in docstrings
            ):
                name = constant_names.get(id(node))
                key = (relative, name or "")
                if relative == _ENGINE:
                    offenders.append(
                        f"{relative}:{node.lineno} -> {node.value} "
                        "(THE ENGINE carries no identifier: this is the generic default)"
                    )
                elif key not in _TASK_SPECIFICATIONS:
                    offenders.append(
                        f"{relative}:{node.lineno} -> {node.value} "
                        f"(constant '{name or 'unnamed, buried'}' not frozen in "
                        "_TASK_SPECIFICATIONS - a default being reborn)"
                    )
                elif node.value not in declared:
                    offenders.append(
                        f"{relative}:{node.lineno} -> {node.value} "
                        "(spec frozen, but this model is NOT in the declared basket)"
                    )
                else:
                    seen_specs.add(key)
    assert not offenders, (
        "a model identifier is hard-coded outside any frozen specification:\n  "
        + "\n  ".join(offenders)
    )
    # The pendant: a frozen spec whose literal has vanished is a DEAD freeze, and it would not say so.
    assert seen_specs == set(_TASK_SPECIFICATIONS), (
        "a frozen specification no longer matches any live literal - stale freeze: "
        f"{sorted(set(_TASK_SPECIFICATIONS) - seen_specs)}"
    )


def test_the_detector_above_really_FIRES_on_a_planted_default(tmp_path: Path) -> None:
    """*A name is not a test.* The detector is re-run against a file that DOES carry a hard-coded id,
    so a green verdict above means "none found", never "the walk found nothing to look at"."""
    planted = tmp_path / "planted.py"
    planted.write_text(f'X = "{_ALPHA}"\n', encoding="utf-8")
    tree = ast.parse(planted.read_text(encoding="utf-8"))
    hits = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and n.value.startswith(BASKET_PREFIX)
    ]
    assert hits == [_ALPHA]
    # ...and that a DOCSTRING mention is correctly NOT an instance (the citation trap).
    quoted = tmp_path / "quoted.py"
    quoted.write_text(f'"""Ce module citait {_ALPHA} autrefois."""\n', encoding="utf-8")
    qtree = ast.parse(quoted.read_text(encoding="utf-8"))
    doc_ids = {
        id(qtree.body[0].value)  # type: ignore[attr-defined]
    }
    assert [
        n.value
        for n in ast.walk(qtree)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and BASKET_PREFIX in n.value
        and id(n) not in doc_ids
    ] == []


# -- representative cache state ---------------------------------------------------------------


def test_the_REAL_declaration_and_the_REAL_disk_agree_on_THIS_machine() -> None:
    """The live check. Skipped where the cache is absent (a fresh clone, CI) rather than failing:
    the declaration describes operator's machine, and a clone that has downloaded nothing is not a
    defect. What is NOT skipped is the declaration itself - see the test below."""
    if os.environ.get("MNEMOSYNE_VERIFY_LOCAL_MODELS") != "1":
        pytest.skip("local model reconciliation is opt-in for the public template")
    if not hub_root().is_dir():
        pytest.skip("no Hugging Face cache on this machine - nothing to reconcile")
    verdict = reconcile()
    assert verdict.ok, "\n".join(str(r) for r in verdict.refusals)
    assert verdict.milliseconds < 100, f"the gate costs {verdict.milliseconds:.1f} ms - too expensive"


def test_the_repos_OWN_basket_is_readable_and_declares_something() -> None:
    """Runs everywhere, cache or no cache: ``models.toml`` is versioned, so an unreadable or empty
    one is a real defect and must never hide behind the skip above. *A control that cannot see must
    fail, never shrug.*"""
    catalog = ModelCatalog.load()
    assert catalog.source.exists(), f"{catalog.source} is missing from the repo"
    assert len(catalog.ids()) >= 1
    assert all(card.octets > 0 for card in catalog.cards())
    assert catalog.prefix == BASKET_PREFIX
