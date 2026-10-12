"""The `plan-emit` seam (anti-drift) — the EMITTED skeleton is PARSED by the READER itself.

This is the only proof that counts here, and it isn't an opinion: the emission doesn't just
DESCRIBE a compliant plan, it renders its actual BYTES. The suite pulls them back out of the
emitted text (`plan_emit.emitted_blocks`, the sole expression of the delimitation) and has them
judged by the SAME chain as `read_plan_tree` and the pre-commit hook -- `read_plan` + `merge_plan`
+ `index_problems` + `is_readable`, with ONE SINGLE `ident_seen` threaded through. If the emitter
and the reader ever diverge by one byte, `test_le_plan_EMIS_ENTIER_est_lisible_index_compris` goes
red.

A contract that teaches the mistake at the exact moment a plan is born is worse than no contract
at all: the plan looks written, the pre-commit gate refuses it, and nobody knows which of the two
is wrong. The lesson is already paid for (D170): the reference used to be DERIVED from what the
tool writes, and it scored twelve out of twelve against the tool and two out of ten against a
human hand. Here the reference is the READER, never the emitter -- and the sabotage at the end of
this file shows the fold actually BITES.

Pure / offline: no model, no brick, no network, nothing is written to disk."""

from __future__ import annotations

import importlib.util

from _invariants import REPO_ROOT

from mnemosyne.production.plan_convert import index_entry
from mnemosyne.production.plan_format import (
    ARCS_DIRNAME,
    PLAN_FILENAME,
    REFUSAL_KINDS,
    ROLE_PLAN,
    SEPARATOR_ASCII_KEY,
    SEPARATOR_KEYS_REFUSED,
    STATUS_BY_GLYPH,
    STATUS_LABEL,
    PlanReading,
    _ASCII_SEPARATORS,
    _TYPOGRAPHIC_SEPARATORS,
    index_problems,
    is_readable,
    merge_plan,
    plan_entries,
    read_plan,
)
from mnemosyne.production.plan_scaffold import (
    DEFAULT_ARC_TITLE,
    METHOD_QUESTIONS,
    PLAN_CONTRACT_TEMPLATE,
    REFUSAL_LABEL,
    arc_ident,
)

_SCRIPT = REPO_ROOT / "system" / "skills" / "planificateur" / "plan_emit.py"
_spec = importlib.util.spec_from_file_location("plan_emit", _SCRIPT)
assert _spec is not None and _spec.loader is not None
plan_emit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plan_emit)

#: A project name that is NOT the default placeholder: the name must travel all the way to the
#: title that gets read back.
PROJET = "Horizon Research"


# --- what the suite pulls back out of the emission ------------------------------------------------


def _blocs() -> dict[str, str]:
    """The emission's blocks, via the EMITTER's own delimitation — never re-implemented here."""
    return plan_emit.emitted_blocks(plan_emit.build_emission(PROJET))


def _arcs(blocs: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """The emitted arcs, `(member path relative to the door, bytes)`, sorted — a report's order is
    stable."""
    return tuple(
        sorted((key, text) for key, text in blocs.items() if key.startswith(f"{ARCS_DIRNAME}/"))
    )


def _slot(emission: str, nom: str) -> str:
    """What the emitter put INSIDE one slot of the contract, cut out by the TEMPLATE'S OWN EDGES.

    Both anchors come from `PLAN_CONTRACT_TEMPLATE` (the code), never from a string retyped here:
    a boundary copied into the test is a second home for it, and the day the template moves the
    test keeps cutting out a section that no longer exists — green, over nothing."""
    avant, apres = PLAN_CONTRACT_TEMPLATE.split("{" + nom + "}", 1)
    ouvre = [ligne for ligne in avant.splitlines() if ligne.strip()][-1]
    ferme = next(ligne for ligne in apres.splitlines() if ligne.strip())
    debut = emission.index(ouvre) + len(ouvre)
    return emission[debut : emission.index(ferme, debut)]


def _replier(porte: str, arcs: tuple[tuple[str, str], ...]) -> PlanReading:
    """Folds door + arcs EXACTLY as `read_plan_tree` and the pre-commit hook fold a plan.

    ONE single `ident_seen` is threaded through every file (D166 clause 5: an identity's scope is
    the PLAN, not the file), `merge_plan` unions them, and `index_problems` judges the index in
    both directions. A third folding would be a third opinion on what a plan says."""
    vus: dict[str, str] = {}
    porte_lue = read_plan(porte, ident_seen=vus)
    arcs_lus = tuple(
        (membre, read_plan(texte, origin=membre, ident_seen=vus)) for membre, texte in arcs
    )
    chemins, imbriques = plan_entries("", tuple(membre for membre, _ in arcs))
    return merge_plan(
        porte_lue,
        arcs_lus,
        extra=index_problems(porte, chemins + imbriques, folder_form=True),
    )


# --- 1. the door -----------------------------------------------------------------------------------


def test_la_porte_EMISE_est_parsee_par_le_lecteur_lui_meme() -> None:
    """The door's bytes are judged by `read_plan`, not by an idea of what they should be."""
    porte = _blocs()[PLAN_FILENAME]
    lecture = read_plan(porte)

    assert lecture.cap, "a door with no `**Cap** :` is unreadable AS A DOOR — the reader says so"
    assert lecture.readable_as_door
    assert lecture.problems == ()
    assert lecture.project == PROJET, "the name passed to the emission must travel to the title read back"
    assert lecture.items == (), "items live in the arcs — a door that carries any redoes the monolith"


# --- 2. one arc ------------------------------------------------------------------------------------


def test_l_arc_EMIS_porte_au_moins_un_item() -> None:
    """An arc with zero items is not readable AS AN ARC and drags the whole plan down with it."""
    for membre, texte in _arcs(_blocs()):
        lecture = read_plan(texte, origin=membre)
        assert lecture.readable_as_arc, f"{membre} carries no readable item"
        assert lecture.problems == (), f"{membre} : {lecture.problems}"
        assert lecture.cap == "", "an arc has no cap — the door carries it, and only once"


def test_les_arcs_EMIS_ouvrent_chacun_leur_propre_LETTRE() -> None:
    """`A1` then `B1`, never `A1` then `A2`: identities are unique across the WHOLE folder, so
    numbering the arcs would have handed every author a collision on their very SECOND item."""
    arcs = _arcs(_blocs())
    premiers = {membre: read_plan(texte, origin=membre).items[0].ident for membre, texte in arcs}

    assert set(premiers.values()) == {arc_ident(rang) for rang in range(len(arcs))}


# --- 3. THE test: the whole plan, index included ---------------------------------------------------


def test_le_plan_EMIS_ENTIER_est_lisible_index_compris() -> None:
    """ The emitted skeleton cannot drift from the reader — this is the test that goes red if it
 does.

 Door + arcs + index, folded the way the pre-commit hook folds them. Verdict rendered by
 `is_readable`, refusals named by `index_problems`: nothing here is judged by the emitter.

 THIS TEST JUDGES THE UNION, SO IT CANNOT SEE ONE EMPTY ARC — measured, not merely feared: on
 removing the `socle` arc's only item, this test stays GREEN (the other arc still carries `B1`,
 and the PLAN role only asks for ONE item across the whole folder) while
 `test_l_arc_EMIS_porte_au_moins_un_item` goes red. Green by batch is not green by item: the two
 tests are a COUPLE, removing the second reopens the class in silence."""
    blocs = _blocs()
    lecture = _replier(blocs[PLAN_FILENAME], _arcs(blocs))

    assert lecture.problems == (), f"the reader refuses the EMITTED plan: {lecture.problems}"
    assert is_readable(lecture, role=ROLE_PLAN)
    assert lecture.project == PROJET and lecture.cap
    assert lecture.parts == tuple(membre for membre, _ in _arcs(blocs))
    assert lecture.untracked == 0, "every emitted item carries an identity — otherwise nothing tracks it"


def test_les_blocs_EMIS_sont_nommes_par_le_FICHIER_a_ecrire() -> None:
    """A block's key IS the path to write it to: a host shouldn't have to guess where what lands."""
    blocs = _blocs()

    assert PLAN_FILENAME in blocs
    assert set(_arcs(blocs)) and all(
        membre.startswith(f"{ARCS_DIRNAME}/") and membre.endswith(".md") for membre, _ in _arcs(blocs)
    )
    assert plan_emit.ENTRY_KEY in blocs


# --- 4. the index entry ----------------------------------------------------------------------------


def test_l_entree_d_index_EMISE_est_celle_de_l_UNIQUE_foyer() -> None:
    """The emitted line IS `plan_convert.index_entry` — a SECOND expression of this shape goes red.

    D170 was paid for exactly here: the entry's shape used to be DERIVED from what the tool
    writes, twelve out of twelve against the tool and two out of ten against a human hand. A
    second home for it reopens that the same day."""
    blocs = _blocs()
    # The arc named by the standalone line is the one the CODE names first — found by its title
    # (`DEFAULT_ARC_TITLE`, plan_scaffold), never by a rank that sort order decides.
    membre = next(
        membre
        for membre, texte in _arcs(blocs)
        if texte.splitlines()[0] == f"# {DEFAULT_ARC_TITLE}"
    )

    assert blocs[plan_emit.ENTRY_KEY].splitlines() == [index_entry(membre, DEFAULT_ARC_TITLE)]
    assert index_entry(membre, DEFAULT_ARC_TITLE) in blocs[PLAN_FILENAME].splitlines(), (
        "the line shown outside the door and the line INSIDE the door must be the SAME"
    )


# --- 5. statuses and refusals -----------------------------------------------------------------------


def test_les_six_statuts_EMIS_sont_exactement_ceux_du_lecteur() -> None:
    """An EQUALITY, not an inclusion: one status too many is a status the reader will refuse, one
    status short is a state the host will push out of the machine's reach — silently."""
    emis: dict[str, str] = {}
    for ligne in _slot(plan_emit.build_emission(PROJET), "statuses").splitlines():
        if ligne.strip():
            glyphe, _, libelle = ligne.strip().partition("  ")
            emis[glyphe] = libelle.strip()

    assert emis == {glyphe: STATUS_LABEL[token] for glyphe, token in STATUS_BY_GLYPH.items()}


def test_chaque_refus_du_lecteur_ET_de_la_naissance_est_NOMME() -> None:
    """A refusal that goes unnamed is a refusal nobody can act on."""
    lignes = [
        ligne.strip()
        for ligne in _slot(plan_emit.build_emission(PROJET), "refusals").splitlines()
        if ligne.strip()
    ]

    assert set(REFUSAL_KINDS) <= set(lignes), "the reader names eight refusals — each on its own line"
    for token, libelle in REFUSAL_LABEL.items():
        assert any(x.startswith(token) and x.endswith(libelle) for x in lignes), token


# --- 6. separators, admitted AND refused -------------------------------------------------------


def test_chaque_separateur_ADMIS_et_chaque_touche_REFUSEE_est_nomme() -> None:
    """The two halves of D170: the marks a TOOL emits, and the keys a HUMAN presses.

    Emitting the first without the second is the measured defect: a human retyping an index line
    with their own keyboard key DISARMED the freshness check on that line."""
    emission = plan_emit.build_emission(PROJET)
    admis = {jeton for jeton in _slot(emission, "separators").split() if len(jeton) == 1}
    refusees = {
        ligne.strip().split()[0]
        for ligne in _slot(emission, "refused").splitlines()
        if ligne.strip()
    }

    assert admis == set(_TYPOGRAPHIC_SEPARATORS) | set(_ASCII_SEPARATORS)
    assert set(SEPARATOR_ASCII_KEY) <= admis, "every typographic mark the reader knows is named"
    assert refusees == set(SEPARATOR_KEYS_REFUSED)
    assert admis & refusees == set(), "one key cannot be BOTH admitted and refused in one contract"


# --- 7. the SABOTAGE proof — the fold BITES ---------------------------------------------------


def test_le_pliage_du_plan_EMIS_MORD_quand_l_index_est_SABOTE() -> None:
    """ A green test nobody has ever seen red proves nothing.

 ONE character changed in an index entry's path, in memory, nothing written to disk — and the
 SAME `_replier` as test 3 must then return the TWO symmetric refusals: the entry names a
 missing file (`index_sans_fichier`) and the real arc is no longer named (`arc_hors_index`).

 Measured, and it bounds the scope of this check: REMOVING the em dash from the same line
 (`- ``plan/socle.md`` Socle`) triggers NOTHING — with no separator behind it the path stops
 being a DECLARATION, so there is no more freshness check, and the mention alone still satisfies
 completeness. The line stays innocent: that's intentional (a sentence that cites a path
 shouldn't be accused), but it needs to be said rather than left believed covered."""
    blocs = _blocs()
    arcs = _arcs(blocs)
    membre = arcs[0][0]
    base = membre.rsplit("/", 1)[-1]
    sabote = blocs[PLAN_FILENAME].replace(base, f"{base[:1]}X{base[2:]}", 1)

    assert sabote != blocs[PLAN_FILENAME], "the sabotage must actually change the door"

    lecture = _replier(sabote, arcs)
    refuses = {probleme.kind for probleme in lecture.problems}

    assert "index_sans_fichier" in refuses, f"refusals obtained: {sorted(refuses)}"
    assert "arc_hors_index" in refuses, f"refusals obtained: {sorted(refuses)}"
    assert not is_readable(lecture, role=ROLE_PLAN)


# --- 8. the method (A6) — level 1, never validated ------------------------------------------------


def test_les_sept_questions_EMISES_sont_EXACTEMENT_celles_du_tuple() -> None:
    """An EQUALITY, like for the statuses (test 5): the method comes from ONE tuple, never
    retyped.

    Seven acronyms P1..P7, no more, no less -- one acronym too many is a property the
    project-lifecycle design notes sec. 3 does not carry, one acronym short is a property silenced."""
    section = _slot(plan_emit.build_emission(PROJET), "method")

    assert [q.sigle for q in METHOD_QUESTIONS] == [f"P{n}" for n in range(1, 8)]
    for q in METHOD_QUESTIONS:
        assert f"{q.sigle} {q.nom}" in section, f"{q.sigle} {q.nom} missing from the emission"


def test_chaque_propriete_EST_formulee_en_question() -> None:
    """"the QUESTION is mandatory, never the ANSWER" (A6) — checked on the TEXT, not on intent.

    A trailing "?" isn't proof of quality, but it IS mechanical proof that the chosen shape really
    is the one A6 requires, rather than a template that slipped in unnoticed."""
    for q in METHOD_QUESTIONS:
        assert q.question.strip().endswith("?"), f"{q.sigle} is not phrased as a question"


def test_la_sequence_EMISE_respecte_l_ordre_enqueter_axes_items_granulariser() -> None:
    """The sequence A6 requires -- "investigate -> axes -> items -> granularize" -- in that
    PRECISE order, not merely the four words present somewhere in the text."""
    section = _slot(plan_emit.build_emission(PROJET), "method")
    mots = ("INVESTIGATE", "AXES", "ITEMS", "GRANULARISE")

    positions = [section.index(mot) for mot in mots]
    assert positions == sorted(positions), f"observed order: {positions}"


def test_la_methode_est_NIVEAU_1_rien_ne_la_valide() -> None:
    """ "A level-2 thinking method would be exactly the template the operator refuses" (A6).

 STRUCTURAL proof rather than documentary: the reader (`verify_readability`, this module's ONLY
 validator) mentions neither the tuple nor the function that render the method, so no refusal
 can ever depend on it. And the object ACTUALLY written to disk (`ScaffoldPlanning`, consumed by
 `plan_new_run.py`) carries no method field at all: the thinking travels ONLY through this
 emission, never through a file `make plan-nouveau` lays down."""
    import inspect

    from mnemosyne.production.plan_scaffold import ScaffoldPlanning, verify_readability

    source = inspect.getsource(verify_readability)
    assert "method" not in source.lower(), "the reader must NEVER judge the method"
    champs = {nom.lower() for nom in ScaffoldPlanning.__dataclass_fields__}
    assert not any("method" in nom for nom in champs), (
        "the method must live ONLY in the emission, never in what is WRITTEN to disk"
    )


def test_la_methode_EST_emise_meme_sans_nom_de_projet() -> None:
    """`make plan-emit` with no NAME still yields a valid placeholder (CLI test below) -- the
    method is NOT conditioned on the project's name, it is owed to WHOEVER reads the contract."""
    section = _slot(plan_emit.build_emission(), "method")

    assert "P1 COMPLETENESS" in section and "P7 PORTABILITY" in section


def test_A9_les_deux_pieges_MESURES_sont_EMIS_et_TRACES_a_leur_mesure() -> None:
    """A9: the A6 trial (verdict `nuit`) named two precise defects -- they must survive in the
    emission, traced back to their measurement (not a vague reformulation that could drift)."""
    section = _slot(plan_emit.build_emission(PROJET), "method")

    assert "harms" in section, "the warning must trace back to the verdict that produced it"
    assert "no guarantee without a server" in section, "pitfall 1 (the unverified claim) is missing"
    assert "privacy" in section.lower(), (
        "pitfall 2 (the easy-to-forget category) is missing"
    )


def test_A9_les_deux_pieges_sont_des_QUESTIONS_pas_des_regles() -> None:
    """A9's `*Obligation*`: level 1, like A6 -- the pitfalls must require NOTHING."""
    section = _slot(plan_emit.build_emission(PROJET), "method")

    assert "neither is a rule" in section


def test_A9_n_a_PAS_touche_aux_sept_questions_ni_a_la_sequence() -> None:
    """A9's *Product*: fix the TWO named defects, and only them -- A6's seven questions and
    sequence must stay EXACTLY what they were (a regression check, not mere presence).

    The questions are wrapped over several lines by `textwrap.fill` (width 88) -- comparing
    against the raw text would require retyping the wrap point here, a second home for it. So we
    compare the WORDS, in order, whitespace-normalized: the only thing that matters for "the text
    hasn't moved", never which column a line wraps at."""
    section = " ".join(_slot(plan_emit.build_emission(PROJET), "method").split())

    for q in METHOD_QUESTIONS:
        assert f"{q.sigle} {q.nom}" in section
        assert " ".join(q.question.split()) in section, f"{q.sigle} : text changed"
    assert "INVESTIGATE" in section and "GRANULARISE" in section
    positions = [section.index(mot) for mot in ("INVESTIGATE", "AXES", "ITEMS", "GRANULARISE")]
    assert positions == sorted(positions)


# --- the CLI surface ------------------------------------------------------------------------------


def test_l_emission_sans_argument_reste_lisible_et_annonce_son_placeholder() -> None:
    """`make plan-emit` with no NAME must remain a valid contract — and say that the name is left
    to fill in."""
    blocs = plan_emit.emitted_blocks(plan_emit.build_emission())
    lecture = _replier(blocs[PLAN_FILENAME], _arcs(blocs))

    assert is_readable(lecture, role=ROLE_PLAN) and lecture.problems == ()
    assert lecture.project == plan_emit.DEFAULT_PROJECT


def test_la_cible_make_accepte_zero_ou_un_argument() -> None:
    """`$(if $(NOM),"$(NOM)",)` passes ONE argument, or none — both must exit at zero."""
    assert plan_emit.main([]) == 0
    assert plan_emit.main([PROJET]) == 0
    assert plan_emit.main([""]) == 0, "an empty NAME is not a name: it falls back to the placeholder"
