"""The UI data contract (arc C3) — one payload, six queues, every project, and what it did NOT read.

Three properties carry the weight here, and each one closes a defect this repo has actually measured:

* **a source that fails must not render as a confident zero** — an interface saying "0 signalements"
  because a directory was unreadable is worse than one saying nothing;
* **no number may summarise a list the payload already carries** — the summary/body drift, measured
  three times, the last time inside a generated report two lines from what it contradicted;
* **the shape must not lose a fact that changes the conclusion** — a refused policy request whose
  stage reads ``applique`` would put "applied" on screen next to a request the operator refused.
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from mnemosyne.ports import Bubble, GovernanceLabel, Sensitivity
from mnemosyne.production.memory import learning_fiche
from mnemosyne.production.plan_format import ARCS_DIRNAME, STATUS_LABEL, PlanItem, PlanReading
from mnemosyne.production.policy_requests import PolicyChangeRequest, PolicyRequestLedger
from mnemosyne.production.policy_writer import PolicyItem
from mnemosyne.production.proposals_ledger import ProposalsLedger
from mnemosyne.production.ui_contract import (
    ABSENTE,
    INDISPONIBLE,
    ITEM_KEYS,
    LUE,
    NAME,
    VERSION,
    Sources,
    _parked_from,
    build_contract,
)

FIXED = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
#: The real repo from this file — the same computation as `test_carte.py` (neither recopied nor re-guessed).
REPO = Path(__file__).resolve().parents[2]

#: ``Mnémosyne`` keeps its accent ON PURPOSE, and it is not decoration: it is the only accented
#: character the healthy payload carries, and it is what
#: ``test_what_render_contract_RETURNS_is_the_JSON_the_interface_parses`` asserts is NOT escaped into
#: ``\\uXXXX``. De-accent it and that witness stops being able to match anything — green, and blind.
#: The number of LINES here is load-bearing too: ``parked["ligne"] == 6`` and
#: ``lignes_prose == 4 / lignes_total == 8`` pin the shape of ``PROJECT_PLAN`` below, so translate a
#: line in place — never reflow one into two.
PLAN = """# PLAN — Mnémosyne

> **Cap** : close arc C.

## Arc C

- **C1** \U00002705 The format
- **D8** \U0001F17F\U0000FE0F The full image run
  9 to 18 h, **non-destructive**, resumable.
- **C3** \U0001F504 The data contract
"""

PROJECT_PLAN = """# PLAN — Acme Research

> **Cap** : close arc 6.

- **A1** \U00002B1C The universal contract
- **A4** \U0001F17F\U0000FE0F The full census run
  9 h, resumable.
  - \U000026A0\U0000FE0F do not chain a preview: it costs the same duration.
"""

# TODO(public-mirror): needs human review -- the `docs/PLAN.md` and `docs/plan/arc-*.md` paths used
# throughout this file are not a free choice of this test suite: `Sources.under()` in the
# (out-of-scope) `ui_contract.py` module hardcodes `mnemosyne_plan=root / "docs" / "PLAN.md"`, so
# every fixture and assertion below has to agree with that literal or the contract this file tests
# stops matching what it builds. Left unchanged for that reason; `docs/PLAN.md` is this repository's
# own real plan door, not a document this public mirror ships (`docs/FORMAT_PLAN.md`, which IS
# shipped, documents the same folder convention generically).


#: A learning the SIZE of a real one. The three sitting in the live ledger run 400 to 900 characters;
#: a two-line fixture made "truncate the text instead of carrying it" an equivalent mutation — the
#: sabotage changed nothing because there was nothing to cut, and read exactly like a killed one.
LEARNING = (
    "The operator NEVER writes code: a gesture I ask of them in the shape of a file edit simply "
    "does not happen (measured: the policy block waited 5 days, and STATE.md charged 4 days of a "
    "blockage that did not exist to their gesture). When something does require them, my job is to "
    "build or to demand the TOOLED gesture — dry-run, implications spelled out in plain language, "
    "append-only journal, their share fits in ONE WORD — the way make endorse / remember / "
    "rangement already do."
)


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def in_sandbox(sources: Sources, root: Path) -> Sources:
    """Refuse to write anywhere but ``root`` — checked BEFORE the first byte, not asserted after.

    Paid for on 2026-07-28: a mutation trial redirected ONE field of :class:`Sources` back to the
    real repo, and this fixture cheerfully wrote a ``PLAN.md`` into the operator's own
    ``projects/saas/Acme Research/``. The test went red — the sabotage was correctly killed — but
    the file already existed. A red test is not a barrier: it reports damage that has been done.
    A fixture that trusts its own isolation is one edit away from writing into real work, so the
    isolation is verified here, structurally, for EVERY root at once.
    """
    for field in fields(sources):
        path = getattr(sources, field.name)
        if not path.is_relative_to(root):
            raise AssertionError(
                f"Sources.{field.name} points outside the sandbox ({path}) — "
                "no write may leave tmp_path"
            )
    return sources


def full_repo(root: Path) -> Sources:
    """A tree with something in EVERY queue — the fixture a blind one would let mutations survive."""
    sources = in_sandbox(Sources.under(root), root)
    write(
        sources.proposals_dir / "veille" / "un-livre.md",
        "---\nsource: \"a book\"\nstatus: draft\n---\n\n# Watch — a macro book\n\nbody\n",
    )
    write(
        sources.signalements_dir / "2026-07-28-make-search-plante.md",
        # `status: ouvert` and the `titre:` key are DATA, not prose: `signalements.OPEN` is the
        # literal `"ouvert"` and the queue only picks up a report whose status matches it.
        '---\nstatus: ouvert\ntitre: "make search crashes on an empty corpus"\n---\n\nbody\n',
    )
    write(sources.mnemosyne_plan, PLAN)
    write(sources.projects_root / "saas" / "Acme Research" / "PLAN.md", PROJECT_PLAN)
    (sources.projects_root / "trading" / "example_research").mkdir(parents=True)

    ledger = ProposalsLedger(sources.proposals_ledger)
    label = GovernanceLabel(sensitivity=Sensitivity.PERSO, bubble=Bubble("perso"))
    ledger.record_propose(learning_fiche(LEARNING, label))

    policy = PolicyRequestLedger(sources.policy_ledger)
    policy.file(
        PolicyChangeRequest(
            title="Acme reaches the public statistical sources",
            items=(PolicyItem(kind="egress", values=("api.stlouisfed.org",)),),
            justification="Acme needs to measure series together with their revisions.",
            requested_by="Acme project session",
        )
    )
    return sources


def payload(root: Path) -> dict[str, Any]:
    return build_contract(full_repo(root), now=FIXED)


def queue(data: dict[str, Any], clef: str) -> dict[str, Any]:
    return next(q for q in data["files"] if q["clef"] == clef)


def walk(node: Any, path: str = "$"):
    """Every (path, value) pair in the payload — used by the barriers that must hold EVERYWHERE."""
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}[{index}]")


# --- the universal form --------------------------------------------------------------------------


def test_the_contract_is_json_and_names_itself(tmp_path: Path):
    """A UI checks name + version before parsing; a moved field must fail loudly, not render blank."""
    data = payload(tmp_path)
    assert json.loads(json.dumps(data, ensure_ascii=False)) == data
    assert data["contrat"] == NAME and data["version"] == VERSION
    assert data["genere_le"] == FIXED.isoformat()


def test_EVERY_item_in_EVERY_queue_carries_EVERY_contract_key(tmp_path: Path):
    """The operator's whole reason for imposing a form: one renderer for six queues.

    A queue that omits a key pushes ``item.chemin ?? item.path ?? ''`` into the UI, where a missing
    field renders as nothing at all and nobody can tell it was missing.
    """
    data = payload(tmp_path)
    seen = 0
    for group in data["files"]:
        for entry in group["items"]:
            assert set(ITEM_KEYS) <= set(entry), f"{group['clef']} lacks {set(ITEM_KEYS) - set(entry)}"
            seen += 1
    for project in data["projets"]["items"]:
        for entry in project["items"]:
            assert set(ITEM_KEYS) <= set(entry), f"{project['nom']} lacks {set(ITEM_KEYS) - set(entry)}"
            seen += 1
    assert seen >= 6, "the fixture must exercise several queues, or this proves nothing"


def test_the_six_queues_the_plan_names_are_all_there(tmp_path: Path):
    """``fiches_refusees`` joined on 2026-07-28, and it is not decoration.

    The operator's constraint when they validated arming the verbatim FLOOR: *"when it's refused,
    it has to go somewhere [...] we shouldn't end up with a pile of corpses [...] ideally it should
    get relayed to the UI."* A floor that refuses without a destination manufactures a graveyard —
    so the queue ships in the same breath as the floor, and this frozen list is what forbids
    dropping it.
    """
    assert [q["clef"] for q in payload(tmp_path)["files"]] == [
        "propositions",
        "memoire",
        "policy",
        "signalements",
        "fiches_refusees",
        "runs_parques",
    ]


# --- the three states, and the confident zero that must never happen -------------------------------


def test_an_untouched_repo_says_ABSENTE_everywhere_never_a_confident_zero(tmp_path: Path):
    """Nothing ever deposited is NOT the same as a drained queue, and an interface must show both."""
    data = build_contract(Sources.under(tmp_path), now=FIXED)
    for group in data["files"]:
        if group["clef"] == "runs_parques":
            continue  # aggregates several plans — its own test below
        assert group["etat"] == ABSENTE, group["clef"]
        assert group["pourquoi"], f"{group['clef']} is absent and does not say why"
    assert data["projets"]["etat"] == ABSENTE and data["projets"]["pourquoi"]


def test_a_populated_repo_says_LUE_with_items(tmp_path: Path):
    data = payload(tmp_path)
    for clef in ("propositions", "memoire", "policy", "signalements", "runs_parques"):
        group = queue(data, clef)
        assert group["etat"] == LUE and group["items"], clef


def test_an_UNREADABLE_source_is_INDISPONIBLE_and_the_other_queues_still_read(tmp_path: Path):
    """The property that matters most: one corrupt ledger degrades ITS card, never the whole page.

    And it must not degrade to zero: ``indisponible`` with a named reason, so the interface can say
    "je n'ai pas pu lire" instead of drawing an empty, confident list.
    """
    sources = full_repo(tmp_path)
    lines = sources.policy_ledger.read_text(encoding="utf-8").splitlines()
    sources.policy_ledger.write_text("this is not json\n" + "\n".join(lines), encoding="utf-8")

    data = build_contract(sources, now=FIXED)
    broken = queue(data, "policy")
    assert broken["etat"] == INDISPONIBLE
    assert broken["pourquoi"] and broken["items"] == []
    assert queue(data, "propositions")["items"], "a neighbour queue was lost with it"
    assert queue(data, "memoire")["items"], "a neighbour queue was lost with it"


def test_a_missing_mnemosyne_plan_is_SAID_even_though_the_queue_was_read(tmp_path: Path):
    """``runs_parques`` reads several plans. An empty list means "nothing is parked" — so when the
    one plan most likely to hold a parked run is missing, the payload must say so."""
    sources = full_repo(tmp_path)
    sources.mnemosyne_plan.unlink()
    group = queue(build_contract(sources, now=FIXED), "runs_parques")
    assert group["etat"] == LUE
    assert "not found" in group["pourquoi"]


# --- no number may summarise a list the payload already carries ------------------------------------


def test_NO_field_counts_a_list_that_sits_beside_it(tmp_path: Path):
    """The summary/body drift, closed as a CLASS rather than case by case.

    Every earlier fix here was "make this one total agree with its body". They kept diverging — the
    body is where work happens, the summary is what gets read. So the contract carries no such
    number at all: the UI calls ``.length``. This walks the WHOLE payload, so a future queue that
    adds one is caught the day it is written, not the day it drifts.
    """
    for path, key, value, lengths in _counts_of_siblings(payload(tmp_path)):
        pytest.fail(
            f"{path}.{key} = {value} equals the length of {lengths} beside it — "
            "a count of a sibling list is the summary that always ends up lying"
        )


def _counts_of_siblings(data: Any):
    """Every scalar that equals the length of a NON-EMPTY list in the same dict.

    Empty lists are skipped deliberately: ``0 == len([])`` is a coincidence, not a summary, and a
    barrier that fires on it would be silenced within a week — which is how a control stops working.
    """
    for path, node in walk(data):
        if not isinstance(node, dict):
            continue
        lengths = {key: len(value) for key, value in node.items() if isinstance(value, list) and value}
        for key, value in node.items():
            if isinstance(value, bool) or not isinstance(value, int) or value == 0:
                continue
            if value in lengths.values():
                yield path, key, value, lengths


def test_the_barrier_above_actually_BITES(tmp_path: Path):
    """Prove the walker fires, rather than trust a green test that may simply never look.

    A control that has never been shown failing is a name, not a test — and this one guards a class
    whose whole nature is to look correct until the day it does not.
    """
    data = payload(tmp_path)
    assert list(_counts_of_siblings(data)) == []
    group = queue(data, "propositions")
    group["nombre_de_propositions"] = len(group["items"])
    found = list(_counts_of_siblings(data))
    assert [key for _, key, _, _ in found] == ["nombre_de_propositions"], found


def test_the_prose_residual_travels_so_no_caller_can_show_items_without_what_it_ignored(
    tmp_path: Path,
):
    """The one place numbers ARE allowed: they describe lines that are NOT in the payload."""
    project = payload(tmp_path)["projets"]["items"][0]
    prose = project["prose"]
    assert prose["lignes_total"] > prose["lignes_prose"] > 0
    assert prose["lignes_prose"] == 4 and prose["lignes_total"] == 8  # the 2 blank lines are neither item nor prose
    assert prose["lignes_total"] == len(PROJECT_PLAN.splitlines())
    # `lignes_rattachees` was the exception that broke the rule: it counted the `detail` lines this
    # very payload carries (measured equal, 293 vs 293), i.e. a derived total inside the contract
    # that forbids them. The barrier could not see it — it compares an integer to the `len()` of a
    # SIBLING list, and those lines live in strings, inside a list, inside another node.
    assert "lignes_rattachees" not in prose, prose
    attached_in_payload = sum(len(entry["detail"].splitlines()) for entry in project["items"])
    assert attached_in_payload > 0, "otherwise this test would pass on an empty payload"


# --- the shape must not lose a fact that changes the conclusion -------------------------------------


def test_a_REFUSED_policy_request_carries_its_refusal_even_when_its_stage_says_otherwise(
    tmp_path: Path,
):
    """The real incident: refused by the operator, application cancelled, ``stage`` still reports ``applique``.

    ``make policy-queue`` prints the stage AND a ``refuse:`` line. A projection keeping only the
    stage would put "applied" on screen next to *"approval forged by an agent"*.
    """
    sources = full_repo(tmp_path)
    ledger = PolicyRequestLedger(sources.policy_ledger)
    request_id = ledger.all_states()[0].id
    ledger.refuse(request_id, reason="approval forged by an agent", by="operator")

    entry = queue(build_contract(sources, now=FIXED), "policy")["items"][0]
    assert "approval forged by an agent" in entry["detail"]
    assert entry["geste"] == "", "a closed request must not offer a button that does nothing"


def test_a_pending_policy_request_offers_the_NEXT_gesture_named_with_its_own_id(tmp_path: Path):
    sources = full_repo(tmp_path)
    entry = queue(build_contract(sources, now=FIXED), "policy")["items"][0]
    assert entry["etat"] == "depose"
    assert entry["geste"] == f"make policy-examiner ID={entry['id']}"


def test_every_gesture_names_the_item_it_acts_on(tmp_path: Path):
    """A generic command on a card is a button that acts on the wrong row."""
    data = payload(tmp_path)
    for clef in ("propositions", "signalements", "memoire"):
        for entry in queue(data, clef)["items"]:
            assert entry["geste"], f"{clef} item offers nothing to do"
            assert entry["id"] in entry["geste"] or entry["chemin"] in entry["geste"], entry


# --- what an interface must never render unknowingly ------------------------------------------------


def test_a_captured_learning_travels_WHOLE_and_labelled(tmp_path: Path):
    """Validating is the operator's gesture: a truncated preview would make the UI worse than the terminal.
    So the text travels — and it never travels without saying it is personal."""
    entry = queue(payload(tmp_path), "memoire")["items"][0]
    assert entry["detail"] == LEARNING
    assert entry["titre"] != LEARNING and entry["titre"].endswith("…"), "the card gets a line, not a wall"
    assert entry["sensibilite"] == "perso" and entry["bulle"] == "perso"
    assert entry["geste"] == f"make memory-validate ID={entry['id']}"


def test_a_proposal_travels_as_a_PATH_and_a_TITLE_never_as_a_body(tmp_path: Path):
    """``make proposals`` states the rule: a proposal is mined from the operator's own library and
    cites their sources, so it is read in the file. The UI has the path — it can open it itself."""
    entry = queue(payload(tmp_path), "propositions")["items"][0]
    assert entry["titre"] == "Watch — a macro book"
    assert entry["chemin"].endswith("un-livre.md")
    assert entry["detail"] == "", "the body must not be inlined into a machine surface (inv. 22)"


def test_a_signalement_shows_its_declared_title_not_its_filename(tmp_path: Path):
    entry = queue(payload(tmp_path), "signalements")["items"][0]
    assert entry["titre"] == "make search crashes on an empty corpus"


# --- the projects, and the parked runs that live inside them ----------------------------------------


def test_parked_runs_come_from_mnemosyne_AND_from_project_plans(tmp_path: Path):
    """Scoping to one file is right today and wrong the moment a project parks a run of its own."""
    items = queue(payload(tmp_path), "runs_parques")["items"]
    # A LIST, not a set. The set form passed identically with 2 items and with 12 duplicates — and
    # the ids were bare (`A4`), which collides across plans: keyed on `id`, an interface renders ONE
    # card and a 9-to-18-hour run vanishes. `id` is qualified by its plan, and the comparison can
    # now see a duplicate at all.
    assert [entry["id"] for entry in items] == [
        "docs/PLAN.md#D8",
        "projects/saas/Acme Research/PLAN.md#A4",
    ]
    plans = {entry["chemin"] for entry in items}
    assert plans == {"docs/PLAN.md", "projects/saas/Acme Research/PLAN.md"}
    parked = next(entry for entry in items if entry["id"].endswith("#D8"))
    assert "9 to 18 h" in parked["detail"], "a parked run without its duration is a trap on a card"


def test_every_project_is_named_in_whatever_state_it_is_in(tmp_path: Path):
    sources = full_repo(tmp_path)
    write(sources.projects_root / "trading" / "usine" / "PLAN.md", "# PLAN — usine\n\n- **A1** \U00002B1C x\n")
    projects = build_contract(sources, now=FIXED)["projets"]["items"]
    by_name = {entry["nom"]: entry for entry in projects}
    assert by_name["saas/Acme Research"]["etat"] == "lisible"
    assert by_name["trading/example_research"]["etat"] == "absent"
    assert by_name["trading/usine"]["etat"] == "illisible"
    assert "Cap" in by_name["trading/usine"]["pourquoi"], "an unreadable plan must say what is missing"


def test_a_readable_project_hands_over_its_cap_its_items_and_their_detail(tmp_path: Path):
    project = payload(tmp_path)["projets"]["items"][0]
    assert project["titre"] == "Acme Research" and project["cap"].startswith("close arc 6")
    idents = [entry["id"] for entry in project["items"]]
    assert idents == ["A1", "A4"]
    parked = project["items"][1]
    # The LABEL is aimed through the production constant, not recopied: `STATUS_LABEL` is prose and
    # gets translated, `"pret"` is the token every consumer indexes on. A copied value would close
    # this case; the constant closes the class, and survives the next translation of the label.
    assert parked["etat"] == "pret" and parked["libelle"] == STATUS_LABEL["pret"]
    assert parked["detail"] == (
        "  9 h, resumable.\n  - \U000026A0\U0000FE0F do not chain a preview: it costs the same duration."
    )
    assert parked["section"] == "" and parked["ligne"] == 6


def test_a_refused_plan_line_is_reported_not_dropped(tmp_path: Path):
    sources = full_repo(tmp_path)
    plan = sources.projects_root / "saas" / "Acme Research" / "PLAN.md"
    plan.write_text(PROJECT_PLAN + "- **A9** \U00002753 out of vocabulary\n", encoding="utf-8")
    project = build_contract(sources, now=FIXED)["projets"]["items"][0]
    assert [refus["genre"] for refus in project["refus"]] == ["statut_inconnu"]
    assert project["refus"][0]["ligne"] == 9


def test_mnemosyne_grades_its_OWN_plan_by_the_rule_it_imposes_on_the_projects(tmp_path: Path):
    """The repo's own plan, in the same shape as a project — because a rule its author is exempt
    from stops being a rule, and because a dashboard about "where I stand" cannot omit the cap."""
    own = payload(tmp_path)["mnemosyne"]
    assert own["etat"] == "lisible" and own["titre"] == "Mnémosyne"
    assert own["cap"] == "close arc C."
    assert [entry["id"] for entry in own["items"]] == ["C1", "D8", "C3"]
    assert own["items"][1]["section"] == "Arc C"


def test_a_mnemosyne_plan_without_a_cap_is_ILLISIBLE_and_says_so(tmp_path: Path):
    """The state this whole key exists to surface: measured on the real file, it WAS unreadable —
    no ``**Cap** :`` line — and nothing outside a test could see it."""
    sources = full_repo(tmp_path)
    sources.mnemosyne_plan.write_text(PLAN.replace("> **Cap** : close arc C.\n", ""), encoding="utf-8")
    own = build_contract(sources, now=FIXED)["mnemosyne"]
    assert own["etat"] == "illisible"
    assert "Cap" in own["pourquoi"]
    assert own["items"], "an unreadable plan still hands over what it DID parse"


def test_bubbles_carrying_markdown_at_their_root_are_flagged(tmp_path: Path):
    """The depth rule cannot see a project written one level too high — so it is named separately."""
    sources = full_repo(tmp_path)
    write(sources.projects_root / "saas" / "NOTES.md", "a project written one level too high")
    assert build_contract(sources, now=FIXED)["projets"]["mal_placees"] == ["saas"]


# --- hermeticity: a test that isolates the tree must measure NOTHING from the real repo ---------------


def test_relocating_the_sources_relocates_ALL_of_them(tmp_path: Path):
    """``Sources.under`` exists so no suite can redirect four roots and silently read the fifth from
    the real repo — the hermeticity bug ``tick`` had to fix twice, one source at a time."""
    data = build_contract(Sources.under(tmp_path), now=FIXED)
    for path, node in walk(data):
        if isinstance(node, str) and "/Users/" in node and str(tmp_path) not in node:
            pytest.fail(f"{path} leaked a path outside the isolated tree: {node}")
    assert data["racine"] == str(tmp_path)


def test_what_render_contract_RETURNS_is_the_JSON_the_interface_parses(tmp_path: Path):
    """The half a UI actually consumes. A mutation trial found it covered by nothing: every other
    test drives the payload builder, so a render emitting Python ``repr`` passed all of them.

    Named for what it drives — ``render_contract``, a Python function. It used to be named after "the
    COMMAND", and that misnomer is exactly what let a real defect live: nothing here spawns ``make``,
    so ``make ui-json`` echoing its own recipe onto stdout (no leading ``@``) went unseen through 26
    controls and 20 killed mutations, until the first real redirect produced a file whose first line
    was a shell command. A name is not a test — the command is now pinned by the test below."""
    from mnemosyne.runtime.ui_run import render_contract

    text = render_contract(full_repo(tmp_path))
    assert text.endswith("\n")
    assert "'" not in text.splitlines()[1], "a Python repr would quote its keys with apostrophes"
    reparsed = json.loads(text)
    assert reparsed["contrat"] == NAME
    assert [q["clef"] for q in reparsed["files"]][0] == "propositions"
    # The accent comes from the `Mnémosyne` plan title in `PLAN` — see the note on that fixture: it
    # is the payload's only non-ASCII character, so de-accenting it silently voids this probe.
    assert "é" in text, "the payload must not be escaped into \\uXXXX — a human reads this too"


def test_make_ui_json_REDIRECTED_TO_A_FILE_is_valid_JSON():
    """THE integration surface, driven exactly as the contract documents it: ``make ui-json``.

    This is the only test that spawns the real command over the real tree, and it exists because the
    26 controls above could not see the defect that shipped: ``make`` echoes a recipe line to STDOUT
    unless it starts with ``@``, so ``make ui-json > contrat.json`` wrote a file whose first line was
    ``PYTHONPATH=system/lib uv run python -m ...``. Every Python-level test passed; the first real
    redirect failed on character one. Read-only and brick-free — the command writes no file, always
    exits 0, and renders a failing source as a named state rather than an error."""
    import subprocess

    from _invariants import REPO_ROOT

    done = subprocess.run(
        ["make", "ui-json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.startswith("{"), (
        "stdout must BE the payload and nothing else — first line was: "
        f"{done.stdout.splitlines()[0] if done.stdout else '<empty>'!r}"
    )
    data = json.loads(done.stdout)  # the whole point: a UI does exactly this
    assert (data["contrat"], data["version"]) == (NAME, VERSION)


def test_paths_are_repo_relative_so_a_ui_never_shows_the_machine_layout(tmp_path: Path):
    data = payload(tmp_path)
    for group in data["files"]:
        assert not group["source"].startswith("/"), group["clef"]
        for entry in group["items"]:
            assert not entry["chemin"].startswith("/"), entry


# --- the three-state doctrine, on the paths an isolated audit found it MISSING (arc C7) ------------
# All three defects rendered a card that LOOKED fine. That is why each of these builds a hostile
# tree instead of asserting on a healthy one: the healthy tree is where they all passed.


def _make_unreadable(path: Path) -> bool:
    """chmod 000 and verify it actually took — running as root makes this test vacuous, not passing."""
    path.chmod(0o000)
    try:
        list(path.iterdir()) if path.is_dir() else path.read_bytes()
    except OSError:
        return True
    path.chmod(0o755)
    return False


def test_an_unreadable_signalement_FILE_is_indisponible_never_a_confident_zero(tmp_path: Path):
    """"0 signalement" because a file could not be read looks like good news. It is the opposite.

    The reader underneath is fail-OPEN by design (the tick must survive one bad file), and chained to
    a queue that design produced exactly the lie the contract forbids: `etat: lue`, empty list, no
    reason. ONE unreadable file was enough.
    """
    sources = full_repo(tmp_path)
    victim = next(sources.signalements_dir.rglob("*.md"))
    if not _make_unreadable(victim):
        pytest.skip("cannot make a file unreadable here (root?) — the test would be vacuous")
    try:
        card = queue(build_contract(sources, now=FIXED), "signalements")
        assert card["etat"] == "indisponible", card
        assert card["pourquoi"], "a refusal that does not say why is a wall"
    finally:
        victim.chmod(0o644)


def test_an_unreadable_projects_directory_degrades_ONE_card_not_the_whole_page(tmp_path: Path):
    """`scan_projects` was the one call outside every guard: PermissionError → exit 1, ZERO bytes.

    Every queue degrades card by card; the projects section did not, so one unreadable bubble blanked
    the entire contract — an interface with no page at all rather than one missing panel.
    """
    sources = full_repo(tmp_path)
    bubble = next(directory for directory in sources.projects_root.iterdir() if directory.is_dir())
    if not _make_unreadable(bubble):
        pytest.skip("cannot make a directory unreadable here (root?) — the test would be vacuous")
    try:
        data = build_contract(sources, now=FIXED)  # must not raise
        assert data["projets"]["etat"] == "indisponible", data["projets"]
        assert data["projets"]["pourquoi"]
        assert [q["clef"] for q in data["files"]], "the other cards must survive"
    finally:
        bubble.chmod(0o755)


def test_a_project_plan_that_could_not_be_read_is_NAMED_in_the_parked_runs_queue(tmp_path: Path):
    """The queue titled "Runs ready" declared a clean read while skipping every unread plan.

    The qualification existed — but only for the BENIGN case (Mnémosyne's own plan missing). The
    dangerous case, a PLAN.md that exists and cannot be parsed, passed in silence: a parked run that
    is invisible reads exactly like a project with no parked run.
    """
    sources = full_repo(tmp_path)
    plan = next(sources.projects_root.rglob("PLAN.md"))
    plan.write_text("not a plan: no title, no cap\n", encoding="utf-8")
    card = queue(build_contract(sources, now=FIXED), "runs_parques")
    assert card["etat"] == "lue"  # the queue WAS read, over the plans that could be
    assert "invisible" in card["pourquoi"], card["pourquoi"]
    assert any(part in card["pourquoi"] for part in ("saas", "Acme")), card["pourquoi"]


# --- the queue of REFUSED records: a refusal must land somewhere -----------------------------------


def _rapport(tmp_path: Path, lignes: str) -> Path:
    rapport = tmp_path / "system" / "logs" / "judge_report.md"
    rapport.parent.mkdir(parents=True, exist_ok=True)
    rapport.write_text("# Judge report\n\n" + lignes, encoding="utf-8")
    return rapport


def _file_refus(tmp_path: Path) -> dict:
    data = build_contract(Sources.under(tmp_path), now=FIXED)
    return next(q for q in data["files"] if q["clef"] == "fiches_refusees")


def test_une_fiche_refusee_ATTERRIT_avec_sa_raison_et_son_geste(tmp_path: Path):
    """A refusal is only useful if it is ACTIONABLE: the reason AND the command that fixes it."""
    _rapport(
        tmp_path,
        "- **paraphrased** — `Finance/livre.md` — only 6/9 passages are real verbatim\n"
        "- **thin** — `Methods/autre.md` — under-distilled (stub)\n",
    )
    file = _file_refus(tmp_path)
    assert file["etat"] == "lue"
    assert [i["id"] for i in file["items"]] == ["Finance/livre.md", "Methods/autre.md"]
    premier = file["items"][0]
    assert premier["etat"] == "paraphrased"
    assert "real verbatim" in premier["detail"]
    assert premier["chemin"] == "knowledge/distilled/Finance/livre.md"
    assert premier["geste"] == 'make verbatim-check FICHE="knowledge/distilled/Finance/livre.md"'


def test_AUCUN_rapport_ne_veut_PAS_dire_aucun_refus(tmp_path: Path):
    """The exact silent death the operator dreads: an empty list that reads as "all is well".

    Here the card must say `absente` AND name the reason — "nothing has been judged", never
    "0 refusals".
    """
    file = _file_refus(tmp_path)
    assert file["etat"] == ABSENTE
    assert file["items"] == []
    assert "has never run" in file["pourquoi"]
    assert "NOT 'no refusals'" in file["pourquoi"]


def test_un_rapport_PERIME_le_DIT_au_lieu_de_paraitre_frais(tmp_path: Path):
    """A derivative ages FAR from its source: a stale card that looks fresh is BELIEVED.

    That is one notch worse than no card at all, and it is the fault already recorded about
    derived caches.
    """
    import os
    import time

    _rapport(tmp_path, "- **thin** — `A/b.md` — under-distilled\n")
    fiche = tmp_path / "knowledge" / "distilled" / "A" / "b.md"
    fiche.parent.mkdir(parents=True, exist_ok=True)
    fiche.write_text("touched AFTER the report", encoding="utf-8")
    futur = time.time() + 60
    os.utime(fiche, (futur, futur))

    file = _file_refus(tmp_path)
    assert file["etat"] == "lue"  # it stays READABLE — we don't hide what we have
    assert "STALE" in file["pourquoi"]
    assert "b.md" in file["pourquoi"], "the card must NAME what moved, not just apologise"

    # and the inverse holds: a shelf OLDER than the report does not cry wolf
    passe = time.time() - 600
    os.utime(fiche, (passe, passe))
    assert _file_refus(tmp_path)["pourquoi"] == ""


def test_une_ligne_de_rapport_MALFORMEE_est_ignoree_sans_tuer_la_carte(tmp_path: Path):
    """The report's header and prose lines are not refusals — and do not manufacture any."""
    _rapport(
        tmp_path,
        "249 books — ok=243\n\nP2 template: 7376/8284 descriptions.\n\n"
        "Records to handle:\n\n- **hollow** — `X/y.md` — empty\n- a bullet that is not a refusal\n",
    )
    file = _file_refus(tmp_path)
    assert [i["id"] for i in file["items"]] == ["X/y.md"]


# --- a plan is a FOLDER (D166 / arc C20-3): a door, and one file per arc beside it -----------------
# The defect this section closes is SILENT by construction: reading the door alone renders a
# perfectly credible "Runs ready" card — state `lue`, no alert — with every item living in the
# arcs having vanished. That is exactly the queue that tells the operator "this is all that's left
# for you". So every test below builds a REAL folder-plan, never a single-file plan.

DOOR = """# PLAN — Mnémosyne

> **Cap** : close arc C20.

## The arcs

- Arc C lives in `plan/arc-c.md` ; arc D in `plan/arc-d.md`.
"""

ARC_C = """## Arc C

- **C1** \U00002705 The format
- **D8** \U0001F17F\U0000FE0F The full image run
  9 to 18 h, **non-destructive**, resumable.
"""

ARC_D = """## Arc D

- **E4** \U0001F17F\U0000FE0F The census run
  3 h, resumable.
- **C3** \U0001F504 The data contract
"""


def folder_plan(root: Path) -> Sources:
    """Mnémosyne's own plan as a FOLDER: the door carries the cap, the arcs carry the items.

    The door has NO item at all — that is D166's normal shape, and it is what makes the defect
    lethal: a mono-file reader renders zero parked runs here, without saying a word.
    """
    sources = full_repo(root)
    write(sources.mnemosyne_plan, DOOR)
    write(sources.mnemosyne_plan.parent / ARCS_DIRNAME / "arc-c.md", ARC_C)
    write(sources.mnemosyne_plan.parent / ARCS_DIRNAME / "arc-d.md", ARC_D)
    return sources


def test_a_parked_run_living_in_an_ARC_still_reaches_the_ready_queue(tmp_path: Path):
    """The items of the arcs are the BULK of a folder-plan: the door carries none of them.

 An empty list reads as "nothing awaits you" — the worst possible output for the one queue
 whose title promises the opposite. `chemin` leads to the FILE, not only to the plan: in a
 folder of five arcs, opening the door to find an item that is not in it is a dead end.
 """
    items = queue(build_contract(folder_plan(tmp_path), now=FIXED), "runs_parques")["items"]
    assert [entry["id"] for entry in items] == [
        "docs/PLAN.md#D8",
        "docs/PLAN.md#E4",
        "projects/saas/Acme Research/PLAN.md#A4",
    ]
    parked = next(entry for entry in items if entry["id"].endswith("#D8"))
    assert parked["chemin"] == "docs/plan/arc-c.md"
    assert "9 to 18 h" in parked["detail"], "a parked run without its duration is a trap on a card"


# Line-for-line shapes: `lignes["F1"] == lignes["F2"] == 3` below pins the parked item to the
# THIRD line of each arc file, so a translation may not add or remove a line here.
TWIN_DOOR = """# PLAN — Mnémosyne

> **Cap** : two twin arcs.

- `plan/arc-e.md` and `plan/arc-f.md` each carry a parked run.
"""
TWIN_E = """## Arc E

- **F1** \U0001F17F\U0000FE0F The run of arc E
"""
TWIN_F = """## Arc F

- **F2** \U0001F17F\U0000FE0F The run of arc F
"""


def test_two_arcs_parking_a_run_at_the_SAME_line_keep_two_cards(tmp_path: Path):
    """Line 12 is no longer a place: five arcs each have one.

    The fixture is verified BEFORE the conclusion — the two items really are on the same line,
    otherwise this test would pass on a plan that creates no ambiguity and would prove nothing.
    """
    sources = full_repo(tmp_path)
    write(sources.mnemosyne_plan, TWIN_DOOR)
    write(sources.mnemosyne_plan.parent / ARCS_DIRNAME / "arc-e.md", TWIN_E)
    write(sources.mnemosyne_plan.parent / ARCS_DIRNAME / "arc-f.md", TWIN_F)
    data = build_contract(sources, now=FIXED)

    lignes = {entry["id"]: entry["ligne"] for entry in data["mnemosyne"]["items"]}
    assert lignes["F1"] == lignes["F2"] == 3, f"the fixture creates no ambiguity: {lignes}"

    parques = [e for e in queue(data, "runs_parques")["items"] if e["chemin"].startswith("docs/")]
    assert [entry["chemin"] for entry in parques] == ["docs/plan/arc-e.md", "docs/plan/arc-f.md"]
    assert len({entry["id"] for entry in parques}) == 2, [e["id"] for e in parques]


def test_two_UNIDENTIFIED_parked_items_at_the_SAME_line_keep_two_keys():
    """The exact collision the folder shape manufactures, on the NO-identity branch.

 Synthetic by NECESSITY, and measured before being written: today an item only becomes `pret`
 through the glyph form, which requires a bold token — so every parked item carries a non-empty
 identity (measured across the whole repo: 3 `pret` items, 0 with no identity). The fallback
 branch is therefore unreachable from real bytes, and that is exactly why it is pinned here
 instead: this format's status vocabulary has already grown TWICE from reading what authors
 actually wrote, and the day a parked item with no identity exists, `plan:12` will render ONE
 card for TWO runs — silently, in the very queue that promises "this is all that's left for
 you".

 The key of an IDENTIFIED item stays the PLAN's (`plan#ident`), never the file's: the
 uniqueness scope of an identity stops at the plan folder, and moving an item from one arc to
 another must not manufacture a new card.
 """
    reading = PlanReading(
        project="Mnémosyne",
        cap="deux arcs",
        items=(
            PlanItem("", "pret", "a run of arc C", "", 12, (), f"{ARCS_DIRNAME}/arc-c.md"),
            PlanItem("", "pret", "a run of arc D", "", 12, (), f"{ARCS_DIRNAME}/arc-d.md"),
        ),
        problems=(),
        prose_lines=0,
        total_lines=0,
    )
    items = _parked_from(reading, plan="docs/PLAN.md")
    assert [entry["id"] for entry in items] == [
        "docs/plan/arc-c.md:12",
        "docs/plan/arc-d.md:12",
    ]
    assert [entry["chemin"] for entry in items] == ["docs/plan/arc-c.md", "docs/plan/arc-d.md"]


def test_the_mnemosyne_prose_measure_covers_the_door_AND_its_arcs(tmp_path: Path):
    """`docs/FORMAT_PLAN.md` forbids any hand-written total and designates `mnemosyne.prose`
    (`make ui-json`) as THE living measure — twice over. A living measure that only reads the door
    would publish a false number under a title that says "measured", which is worse than no number
    at all.

    And the merged arcs are NAMED, never counted: "4 arcs" does not say which one is missing.
    """
    own = build_contract(folder_plan(tmp_path), now=FIXED)["mnemosyne"]
    assert own["etat"] == "lisible" and own["cap"] == "close arc C20."
    assert [entry["id"] for entry in own["items"]] == ["C1", "D8", "E4", "C3"]
    assert own["arcs"] == ["docs/plan/arc-c.md", "docs/plan/arc-d.md"]
    prose = own["prose"]
    assert prose["lignes_total"] == len(DOOR.splitlines()) + len(ARC_C.splitlines()) + len(
        ARC_D.splitlines()
    )
    assert prose["lignes_prose"] > 0
    assert own["items"][1]["fichier"] == "docs/plan/arc-c.md", "an item knows where it came from"
    assert own["items"][0]["fichier"] == "docs/plan/arc-c.md"


def test_a_refused_line_inside_an_ARC_names_the_FILE_not_only_a_line(tmp_path: Path):
    """A refusal that cannot be located is barely better than silence.

    "line 6: statut_inconnu" sends the operator into the door, where there is nothing on line 6.
    """
    sources = folder_plan(tmp_path)
    write(
        sources.mnemosyne_plan.parent / ARCS_DIRNAME / "arc-d.md",
        ARC_D + "- **A9** \U00002753 out of vocabulary\n",
    )
    own = build_contract(sources, now=FIXED)["mnemosyne"]
    assert [refus["genre"] for refus in own["refus"]] == ["statut_inconnu"]
    assert own["refus"][0]["ligne"] == 6
    assert own["refus"][0]["fichier"] == "docs/plan/arc-d.md"


def test_an_unreadable_ARC_is_NAMED_instead_of_silently_shrinking_the_queue(tmp_path: Path):
    """An unreadable arc degrades THAT ARC, and it is NAMED — it no longer takes the other twelve
 down with it.

 A named loss beats a silent one: the card stays `lue` — it did read the plans it could — but it
 SAYS which one is missing, otherwise zero parked runs reads as "everything is done".

 **This test used to CARVE THE DEFECT IN AS A REQUIREMENT.** Its first line used to say "an
 unreadable arc takes down the WHOLE plan", and the assertion at the bottom demanded it: no
 ``docs/`` item left at all. Measured against the real surface, a single corrupted arc out of
 twelve rendered **0 items out of 43** — the blast radius grown from one file to thirteen the
 day of the conversion. What stays true and what must keep being true: the loss is NAMED. What
 changes: it is now BOUNDED, and this assertion now says so through a named set — only the
 victim arc disappears from the queue.
 """
    sources = folder_plan(tmp_path)
    victim = sources.mnemosyne_plan.parent / ARCS_DIRNAME / "arc-c.md"
    if not _make_unreadable(victim):
        pytest.skip("cannot make a file unreadable here (root?) — the test would be vacuous")
    try:
        card = queue(build_contract(sources, now=FIXED), "runs_parques")
        assert card["etat"] == LUE
        assert "arc-c.md" in card["pourquoi"], card["pourquoi"]
        survivors = {e["chemin"] for e in card["items"] if e["chemin"].startswith("docs/")}
        assert survivors == {"docs/plan/arc-d.md"}, (
            f"an unreadable arc must degrade ITSELF ALONE: arcs still rendered = {sorted(survivors)}"
        )
    finally:
        victim.chmod(0o644)


# --- the `carte` key (B4): by arc, never truncated, and WHO holds it -------------------------------

ARC_A = """## Arc A

- **A1** \U00002705 First step
- **A2** \U00002705 Second step
"""

ARC_B = """## Arc B

- **B1** \U00002B1C One
- **B2** \U0001F504 Two
- **B3** \U00002B1C Three
"""

DOOR_DEUX_ARCS = """# PLAN — Mnémosyne

> **Cap** : close arc B.

## The arcs

- Arc A lives in `plan/arc-a.md` ; arc B in `plan/arc-b.md`.
"""


def carte_plan(root: Path) -> Sources:
    """A folder-plan with TWO CLEAN arcs — one prefix per file, like the REAL repo (measured
    2026-08-15: eleven arcs, eleven homogeneous prefixes). `folder_plan` (above) mixes prefixes
    ACROSS files for a different clause (naming by file rather than by ident); this one keeps them
    clean to isolate what `carte` must prove without inheriting noise that is not its own."""
    sources = full_repo(root)
    write(sources.mnemosyne_plan, DOOR_DEUX_ARCS)
    write(sources.mnemosyne_plan.parent / ARCS_DIRNAME / "arc-a.md", ARC_A)
    write(sources.mnemosyne_plan.parent / ARCS_DIRNAME / "arc-b.md", ARC_B)
    return sources


def test_la_clef_carte_porte_CHAQUE_arc_de_mnemosyne_avec_sa_forme_ENTIERE(tmp_path: Path):
    """`ArcEtat` as JSON, with no truncation: two declared arcs, two rendered entries — not a
    section bounded like the rest of this contract."""
    data = build_contract(carte_plan(tmp_path), now=FIXED)
    par_etiquette = {arc["etiquette"]: arc for arc in data["carte"]["mnemosyne"]}
    assert set(par_etiquette) == {"A", "B"}, par_etiquette

    a = par_etiquette["A"]
    assert a["fichier"] == "docs/plan/arc-a.md"
    assert (a["total"], a["fait"], a["en_cours"], a["a_faire"]) == (2, 2, 0, 0)
    assert a["etat"] == "fini"
    assert a["attend"] == []
    assert a["qui_le_tient"] == [], "no seat written in this fixture"

    b = par_etiquette["B"]
    assert b["fichier"] == "docs/plan/arc-b.md"
    assert (b["total"], b["fait"], b["en_cours"], b["a_faire"]) == (3, 0, 1, 2)
    assert b["etat"] == "en_cours"


def test_qui_le_tient_lit_les_VRAIS_postes_et_ignore_JOURNAUX_et_L_ORCHESTRATEUR(tmp_path: Path):
    """Measured against the three real seats before writing the parser: `arcs:` is PROSE
    (`A (the obligation) · E (the commit)`), not the idealised shape of the seat-format document. And
    two traps named by hand: a `journal-chat-*.md` can CITE `arcs:` (it happened, inside a lesson
    in the repo) without being a seat; the orchestrator has NONE at all (`role:`, never `arcs:`)."""
    sources = carte_plan(tmp_path)
    write(sources.postes_dir / "chat-1.md", "# SEAT — chat 1\narcs: A — The first arc\n")
    write(
        sources.postes_dir / "chat-2.md",
        "# SEAT — chat 2\narcs: B (the map) · Z (no arc of that name in THIS plan)\n",
    )
    write(sources.postes_dir / "chat-0-orchestrateur.md", "# SEAT — chat 0\nrole: arbitrate\n")
    write(
        sources.postes_dir / "journal-chat-1.md",
        "## a lesson\narcs:      line 4   (a CITATION inside an example, not a seat)\n",
    )

    data = build_contract(sources, now=FIXED)
    par_etiquette = {arc["etiquette"]: arc for arc in data["carte"]["mnemosyne"]}
    assert par_etiquette["A"]["qui_le_tient"] == ["chat-1"]
    assert par_etiquette["B"]["qui_le_tient"] == ["chat-2"]


def test_qui_le_tient_est_TOUJOURS_VIDE_pour_un_PROJET(tmp_path: Path):
    """No `postes/` mechanism exists for a project — an empty list is the TRUE answer, the same
    convention the rest of this contract uses for "the notion does not apply"."""
    sources = carte_plan(tmp_path)
    write(sources.postes_dir / "chat-1.md", "# SEAT — chat 1\narcs: A — The first arc\n")
    data = build_contract(sources, now=FIXED)
    projet = next(p for p in data["carte"]["projets"] if p["nom"] == "saas/Acme Research")
    assert projet["arcs"], "the fixture must carry at least one arc for this witness to be honest"
    assert all(arc["qui_le_tient"] == [] for arc in projet["arcs"]), projet


def test_carte_projets_NOMME_un_projet_ILLISIBLE_au_lieu_de_l_OMETTRE(tmp_path: Path):
    """A project absent from `carte.projets` would read as "does not exist" — `projets.items`
    already shows it with its state; the same entry must never tell two different truths."""
    sources = carte_plan(tmp_path)
    plan = next(sources.projects_root.rglob("PLAN.md"))
    plan.write_text("not a plan: no title, no cap\n", encoding="utf-8")
    data = build_contract(sources, now=FIXED)
    projet = next(p for p in data["carte"]["projets"] if p["nom"] == "saas/Acme Research")
    assert projet["arcs"] == [], "unreadable: the LIST is empty, never the entry itself absent"
    autre_vue = next(p for p in data["projets"]["items"] if p["nom"] == "saas/Acme Research")
    assert autre_vue["etat"] == "illisible", autre_vue


def test_qui_le_tient_dit_INCONNU_plutot_que_de_SE_TAIRE_quand_un_poste_est_ILLISIBLE(tmp_path: Path):
    """ **Requested by the orchestrator BEFORE the coupling existed** (a real seat file,
 21:4x): this parser reads files it does not write (`pas_a_moi` forbids writing, never reading),
 and the day their shape breaks, it MUST say so rather than stay silent — an empty list reads as
 "nobody holds this arc", a silent lie of the very class this contract exists to refuse. An
 unreadable seat therefore renders `["inconnu"]`, never `[]`."""
    sources = carte_plan(tmp_path)
    victime = write(sources.postes_dir / "chat-1.md", "# SEAT — chat 1\narcs: A — The first arc\n")
    if not _make_unreadable(victime):
        pytest.skip("cannot make a file unreadable here (root?) — the test would be vacuous")
    try:
        data = build_contract(sources, now=FIXED)
        par_etiquette = {arc["etiquette"]: arc for arc in data["carte"]["mnemosyne"]}
        assert par_etiquette["A"]["qui_le_tient"] == ["inconnu"], par_etiquette["A"]
    finally:
        victime.chmod(0o644)


def test_qui_le_tient_survit_a_la_PROSE_REELLE_des_VRAIS_postes():
    """ **Requested by the orchestrator, word for word**: "a witness against the REAL seats, not
 an idealised fixture". The real seat-format document prescribes `arcs: <letter(s)> — <title>`; the
 real files do not stick to it — measured on 2026-08-15 before writing the parser:
 a seat may carry `A (the obligation) · E (the commit) · D (the drift) · B (the map,
 handed over)`, and another `F — The enquiry · **B6 (new, opened ON YOUR MEASUREMENT)**` —
 PROSE, with parentheses, middle dots, markdown bold.

 **No exact equality against today's text**: these files are rewritten on EVERY turn by the
 orchestrator and by the other chats — a witness frozen on their current content would break at
 the next commit to a file that is not even mine. What must stay true whatever the prose is: the
 parser never RAISES, every seat carrying an `arcs:` line renders AT LEAST one recognisable
 letter, and nothing leaks from the journals or from the orchestrator (which has no `arcs:`
 line at all)."""
    from mnemosyne.production.ui_contract import _arcs_du_poste, _qui_tient_par_arc

    reels = sorted((REPO / "docs" / "postes").glob("chat-*.md"))
    assert len(reels) >= 3, "this witness's fixture IS the repo: it must carry at least 3 seats"
    for chemin in reels:
        texte = chemin.read_text(encoding="utf-8")
        arcs = _arcs_du_poste(texte)  # must never raise, whatever the real prose is
        if "\narcs:" in f"\n{texte}":
            assert arcs, f"{chemin.name} carries an arcs: line and yet nothing comes out of it"
        assert all(a.isalpha() and a.isupper() for a in arcs), (
            f"{chemin.name} -> {arcs}: a label must be LETTERS, never a fragment of prose"
        )

    tenants, degrade = _qui_tient_par_arc(REPO / "docs" / "postes")
    assert not degrade, "the real seats are readable; a True here would be a defect of THIS repo"
    assert tenants, "at least one real arc must have a named holder"
    for arc, postes in tenants.items():
        assert all(p.startswith("chat-") and "journal" not in p for p in postes), (
            f"arc {arc} attributed to {postes} — a journal or a non-seat file leaked into the count"
        )
