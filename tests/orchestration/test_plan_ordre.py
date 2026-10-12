"""B1 — the ORDER of a plan: declared dependencies, named cycle, waves, reverse index.

Two families. The first pins down the list's grammar — this is where this module already nearly
died twice, once by SCANNING the entire value, once by reading PROSE as identifiers. The second
replays on the sibling project's real corpus, the only non-derived reference.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mnemosyne.production.plan_format import PlanItem, PlanReading, read_plan
from mnemosyne.production.plan_ordre import (
    ORDER_REFUSALS,
    SEUIL_OCTETS,
    DureeEtape,
    dependances,
    duree_par_etape,
    duree_par_vague,
    ecart,
    est_une_reponse_gratuite,
    lire_liste,
    lots,
    ordonner,
    repartition,
    router,
)

REPO = Path(__file__).resolve().parents[2]
HEAD = ("# PLAN — demo", "", "> **Cap** : prouver l'ordre", "")


def plan(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def item(ident: str, depend: str, statut: str = "\U00002B1C") -> tuple[str, ...]:
    return (f"- **{ident}** {statut} un item.", f"  *Dépend de* : {depend}")


# --- the list's GRAMMAR -------------------------------------------------------------------------

#: The REAL values from the corpus, and what the rule must draw from them. Named one by one: a
#: shape that is the ONLY witness of its case must not be able to vanish in a two-line edit.
LISTES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("empty answer", "AUCUNE", ()),
    ("empty answer, masculine", "AUCUN", ()),
    ("a single one", "A1", ("A1",)),
    ("trailing period", "A03-9.", ("A03-9",)),
    ("comma then prose", "A03-6, A03-9. *Mesure qui le motive* : `state/...`", ("A03-6", "A03-9")),
    ("dash then prose", "A03-20 — son second membre exige que l'identité porte SON", ("A03-20",)),
    ("French liaison word", "A1 et A2", ("A1", "A2")),
    ("middle dot", "A1 · A2", ("A1", "A2")),
    ("prose alone", "rien", ()),
    ("prose after an id", "A03-2 pour savoir quels hotes repondent", ("A03-2",)),
)


@pytest.mark.parametrize(("forme", "valeur", "attendu"), LISTES, ids=[f for f, _, _ in LISTES])
def test_la_liste_se_lit_par_une_REGLE_et_la_prose_la_TERMINE(forme, valeur, attendu):
    """ **THIS MODULE ALMOST DIED TWICE OVER THIS LINE, in both directions.**

 First a SCAN of the entire value: `A03-20 — son second membre exige…` claimed every identifier
 cited in the prose tail — **68 links instead of 28** on the real corpus. Then a rule that
 accepted ANY word at all: `A03-2 pour savoir quels hotes repondent` produced SIX dependencies,
 and **14 items from the sibling project produced a refusal made of French prose**.

 The rule is a GRAMMAR: the list is the head of the value, and the first word that is neither a
 known identifier nor identifier-shaped closes it. *A sentence is not a badly written dependency.*
 """
    assert lire_liste(valeur) == attendu, f"« {forme} » misread"


def test_le_temoin_couvre_les_deux_directions_du_defaut_et_ne_peut_pas_se_vider():
    """Freezes the SET of forms, never their count — and the two historical faults are both in it."""
    assert {f for f, _, _ in LISTES} >= {"dash then prose", "prose after an id", "empty answer"}


def test_un_identifiant_REEL_hors_forme_est_lu_quand_la_population_est_donnee():
    """The POPULATION is the authority, never the shape — the sibling project carries a step `PEUPLEMENT` no
    pattern can see, and a legitimate dependency toward it was thrown out with the faulty ones."""
    assert lire_liste("PEUPLEMENT", frozenset({"PEUPLEMENT"})) == ("PEUPLEMENT",)
    assert lire_liste("PEUPLEMENT") == (), "without a population, only the shape speaks — and that is stated"


# --- the GRAPH -----------------------------------------------------------------------------------


def test_une_dependance_qui_ne_nomme_AUCUNE_etape_REFUSE_au_lieu_de_liberer():
    """ The sibling project's most expensive lesson, reused here: `& set(connus)` SILENTLY dropped what it did
 not recognise, so **a badly written dependency became a FREE step** — the worse of the two
 directions. Five sabotages passed green behind that silence."""
    reading = read_plan(plan(*HEAD, *item("A1", "A9"), *item("A2", "AUCUNE")))
    graphe, refus = dependances(reading)

    assert graphe["A1"] == frozenset(), "an unknown must not become a link"
    (probleme,) = refus
    assert probleme.kind == "dependance_inconnue"
    assert "A9" in probleme.detail and "FREE" in probleme.detail


def test_le_cycle_est_NOMME_jamais_leve_et_le_reste_du_plan_reste_ordonne():
    """Raising would have made a plan with a single bad edge produce NO order at all — and a
    surface that shows nothing is indistinguishable from a surface that found nothing."""
    reading = read_plan(
        plan(*HEAD, *item("A1", "A2"), *item("A2", "A1"), *item("A3", "AUCUNE"))
    )
    ordre = ordonner(reading)

    assert ordre.cycle == ("A1", "A2")
    assert ordre.ordonnable is False
    assert ordre.vagues == (("A3",),), "the rest of the plan keeps its order"
    assert [p.kind for p in ordre.problems] == ["cycle_de_dependances"]
    assert "NEVER" in ordre.problems[0].detail


def test_les_vagues_sont_ce_qui_est_faisable_EN_PARALLELE():
    reading = read_plan(
        plan(*HEAD, *item("A1", "AUCUNE"), *item("A2", "AUCUNE"), *item("A3", "A1, A2"))
    )
    assert ordonner(reading).vagues == (("A1", "A2"), ("A3",))


def test_le_deblocage_pose_TOUTES_les_clefs_pour_que_ZERO_ne_soit_pas_ABSENT():
    """*Two absences of measurement compare equal* — a step nobody waits on must return 0,
    not disappear from the index."""
    reading = read_plan(plan(*HEAD, *item("A1", "AUCUNE"), *item("A2", "A1")))
    ordre = ordonner(reading)

    assert ordre.debloque("A1") == 1
    assert ordre.debloque("A2") == 0, "a step nobody waits on returns 0, never nothing"
    with pytest.raises(KeyError):
        ordre.debloque("A9")


def test_chaque_refus_declare_est_PRODUCTIBLE():
    """A kind of refusal that no entry ever triggers is a promise nobody keeps."""
    produits: set[str] = set()
    for texte in (
        plan(*HEAD, *item("A1", "A9")),
        plan(*HEAD, *item("A1", "A1")),
        plan(*HEAD, *item("A1", "une phrase sans aucune liste en tête")),
        plan(*HEAD, *item("A1", "A2"), *item("A2", "A1")),
    ):
        produits |= {p.kind for p in ordonner(read_plan(texte)).problems}

    assert produits == set(ORDER_REFUSALS), (
        f"declared but never produced: {sorted(set(ORDER_REFUSALS) - produits)} · "
        f"produced but never declared: {sorted(produits - set(ORDER_REFUSALS))}"
    )


# --- the REAL CORPUS, and the GAP that IS the result ----------------------------------------------


def _projet_reference() -> tuple[PlanReading, dict]:
    root = REPO / "projects/saas/reference-project"
    items = {}
    for md in sorted(root.rglob("*.md")):
        if "/plan/" not in str(md) and md.name != "PLAN.md":
            continue
        for it in read_plan(md.read_text(encoding="utf-8", errors="replace"), origin=str(md)).items:
            if it.ident:
                items[it.ident] = it
    return (
        PlanReading(
            project="reference-project", cap="x", items=tuple(items.values()),
            problems=(), prose_lines=0, total_lines=0,
        ),
        items,
    )


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/saas/reference-project").is_dir(),
    reason="projects/ is gitignored by design — absent from a fresh clone",
)
def test_rejoue_sur_LE_PROJET_le_graphe_declare_tient_et_ne_porte_AUCUN_cycle():
    """`B1`'s `*Fini quand*` clause, half 1 — on the real corpus, never on a fixture.

 **The "cycle of 15 items" I had reported to the orchestrator does not exist.** It was an
 artefact of my own SCAN: by claiming the identifiers cited in the prose tail, I was fabricating
 edges nobody had declared, and two of them closed into a loop. With the rule: **0 cycles**.
 *A measurement taken with the wrong instrument invents its own result.*
 """
    reading, _ = _projet_reference()
    ordre = ordonner(reading)
    graphe, refus = dependances(reading)

    assert len(graphe) == 168, f"{len(graphe)} items — the population has moved"
    assert ordre.cycle == (), f"unexpected cycle: {ordre.cycle}"
    assert ordre.ordonnable is True
    assert sum(len(v) for v in ordre.vagues) == 168, "a step has disappeared from the waves"

    # **FREEZING THE COUNT WAS PROTECTING THE DEFECT, and that is the trickiest find of the
    # evening.** Frozen at 44, it turned RED on the FIX for the fourth drift — with a message
    # accusing "one more drift". *A barrier set on a quantity that is still wrong defends the very
    # error it is supposed to catch.* The count therefore cannot travel alone: what makes it safe
    # is the clause BELOW, which holds the CLASS — moved BEFORE the count (2026-08-18): an `assert`
    # stops the function at the first failure, so as long as it lived AFTER, it NEVER ran when the
    # corpus moved the count first — exactly what happened this round. The count says "it moved";
    # the class says "and here is which way" — and it must speak FIRST for that to be true in
    # practice, not only in a comment.
    silencieux = [
        item.ident
        for item in reading.items
        if item.ident
        and (item.field("depend_de") or "")
        # FALSE POSITIVE measured on the sibling project (2026-08-18), found by running this clause FIRST for
        # the first time: `A06-21` answers `RIEN` then explains in prose that it "shares its
        # material with `A06-22` and `A06-23`" — two real identifiers, cited for CONTEXT, never
        # declared as a dependency. `dependances()` rightly ignores them (`RIEN` closes the list,
        # `est_une_reponse_gratuite` confirms it); without this line, the free answer itself
        # triggered a false alarm on its own explanatory prose. **The hardest proof** (found by the
        # delegated audit, not by me): reading `A06-21`'s prose as dependencies would fabricate a
        # CYCLE — `A06-22` and `A06-23` EACH declare depending on `A06-21` — which the
        # `assert ordre.cycle == ()` just above already forbids.
        # HONEST RESIDUE, named by the same audit: this line removes the ENTIRE population of
        # `AUCUNE`/`RIEN` answers from the scan, not just `A06-21`. **Verified, not assumed**: on
        # the sibling project today, exactly 2 items follow this pattern ("nothing from this arc" + prose citing
        # another real ident) — `A06-21` (above) and `A06-18` ("nothing from this arc [...] it
        # unblocks RT-DE4 (A06-19)"). An item that wrote `AUCUNE — but see A2 and A3` would also no
        # longer be detected, even if `A2`/`A3` were a real, badly worded dependency — under the
        # production grammar it is already "no dependency" (`AUCUNE` closes the list), so this is
        # not a READING hole, but it is a knowingly accepted, not built, SURVEILLANCE hole: giving
        # it a dedicated mechanism would be construction outside this mandate.
        and not est_une_reponse_gratuite(item.field("depend_de") or "")
        and {
            autre
            for autre in graphe
            if autre != item.ident
            and re.search(re.escape(autre) + r"(?![A-Za-z0-9-])", item.field("depend_de") or "")
        }
        - graphe[item.ident]
        and item.line not in {p.line for p in refus}
    ]
    assert silencieux == [], (
        f"{len(silencieux)} items LOSE a known identifier WITH NO refusal at all: {silencieux[:6]} — "
        "this is the shape of defect four drifts of this line have taken, and it is SILENT"
    )
    # The EXACT count, not a floor. The test used to say `>= 20` where the value WAS 44 (even
    # before the measurement that brought it to 46, then 208 below): **24 links could disappear
    # with no red**, on the very quantity that has already broken THREE times. A floor on the
    # quantity that breaks is a floor looking the other way.
    assert sum(len(d) for d in graphe.values()) == 208, (
        "the number of DECLARED links has moved — the structural check just above (no known link "
        "lost in silence) is GREEN: if you are reading this message, it is very probably legitimate "
        "growth of the sibling project's corpus (chats filling in the format), not a regression — verify, then "
        "raise the figure knowingly. If the check above is RED instead of green, it is the reading "
        "rule that has drifted, not just this figure"
    )


def test_l_ECART_est_le_resultat_et_il_se_publie_LIEN_PAR_LIEN_avec_sa_cause():
    """`B1`'s `*Fini quand*` clause, half 2 — **amended** the day a measurement refuted its
 original version ("returns exactly 234 links").

 Reproducing 234 would have required copying the sibling project's permissive rule — *building `B1` to
 reproduce the defect it exists to replace*. The gap IS the result: it measures how many of
 The sibling project's "dependencies" are not ones, and it is compared by **SETS**, never by counts — two
 counts can coincide while naming different links.

 The three causes are distinguished: cited in the field's prose · outside the field (the other
 reader reads a wider tranche) · declared here only.
 """
    reading = read_plan(
        plan(*HEAD, *item("A1", "A2 — mais A3 explique pourquoi"), *item("A2", "AUCUNE"),
             *item("A3", "AUCUNE"))
    )
    graphe, _ = dependances(reading)
    items = {it.ident: it for it in reading.items}

    autre = {"A1": frozenset({"A2", "A3", "A4"}), "A2": frozenset(), "A3": frozenset()}
    lignes = ecart(graphe, autre, items)

    assert ("A1", "A3", "cite_en_prose") in lignes, "A3 is CITED in the value, never declared"
    assert ("A1", "A4", "hors_champ") in lignes, "A4 does not appear in the field at all"
    assert not [x for x in lignes if x[1] == "A2"], "a link BOTH carry is not a gap"


def test_l_ecart_publie_aussi_ce_que_MOI_SEUL_declare():
    """A one-way gap would be a plea, not a measurement."""
    reading = read_plan(plan(*HEAD, *item("A1", "A2"), *item("A2", "AUCUNE")))
    graphe, _ = dependances(reading)
    items = {it.ident: it for it in reading.items}

    lignes = ecart(graphe, {"A1": frozenset(), "A2": frozenset()}, items)
    assert lignes == (("A1", "A2", "declare_seulement_ici"),)


# --- WHAT A THIRD-PARTY AUDIT FALSIFIED — six mutants survived the first twenty tests --------


def test_la_DECORATION_se_depouille_et_ne_ferme_JAMAIS_la_liste():
    """ **THIRD DRIFT OF THE SAME LINE, and the first one in the TOO NARROW direction.**

 The boundary used to cut at the first `*` or `` ` ``: a list written in bold or code —
 ``**A10-1**, **A10-2**, **A10-3**`` — produced an **EMPTY** head, **zero refusals**, and the
 item went straight into **wave 1**. Measured on the sibling project: **17 declared links lost out of 45**, all
 of them toward a step that EXISTS. That is word for word the class this module puts in capitals
 twice. Twice too wide, once too narrow — *close the CLASS*.
 """
    for valeur, attendu in (
        ("**A10-1**, **A10-2**, **A10-3**", ("A10-1", "A10-2", "A10-3")),
        ("`A03-19` — plus le geste de l'opérateur", ("A03-19",)),
        # **VERBATIM from `A03-19-…md:45`, and the order matters.** The version first frozen here
        # was the same line with its two halves REVERSED — i.e. the production amputated of the
        # token that broke the rule: `(fait)` as a gloss closed the list and `A03-17` fell out.
        # *A fixture pulled from the real thing and then touched up is a fixture that no longer
        # pulls from the real thing.*
        ("`A03-18` (fait) et **`A03-17`**", ("A03-18", "A03-17")),
        ("A11-1 (sans lui rien), A10-12 (le catalogue)", ("A11-1", "A10-12")),
        # **AN EXPECTATION THAT CHANGED, and saying so is the point.** This test used to freeze
        # ``(A2) → A2``: the parenthesis there was DECORATION. The gloss rule makes it a MENTION —
        # ``A1 (voir aussi A2)`` declares ``A1``, never ``A2``. The two cannot coexist: it is the
        # same "two rules for one question" contradiction this module just closed elsewhere. The
        # gloss wins, because it is the doctrine of the whole repository (*a mention is not a
        # declaration*) and because it recovers 15 real links where the other reading serves none
        # on the corpus.
        ("[A1], (A2), \"A3\"", ("A1", "A3")),
    ):
        assert lire_liste(valeur) == attendu, f"« {valeur} » misread"


def test_une_valeur_ECRITE_dont_on_ne_tire_AUCUNE_liste_REFUSE_au_lieu_de_liberer():
    """`arc 05, arc 04 items **A04-9**` is a SENTENCE that contains identifiers.

 Two bad answers: scan it (the original defect, which over-captures) or read it empty **in
 silence** (what the narrow boundary did, and the item left free). The third is the right one:
 we NAME it. *An unreadable dependency never becomes a free step.*
 """
    reading = read_plan(plan(*HEAD, *item("A1", "arc 05, arc 04 items **A04-9**")))
    _graphe, refus = dependances(reading)

    (probleme,) = refus
    assert probleme.kind == "liste_illisible"
    assert "AUCUNE" in probleme.detail, "the refusal must name the way out"
    assert ordonner(reading).vagues == (("A1",),), "it remains orderable, it is not lost"


def test_AUCUNE_ecrit_ne_declenche_AUCUN_refus_car_la_question_seule_est_obligee():
    """M12 · the mutant that survived: nothing proved that the free answer stays free."""
    _graphe, refus = dependances(read_plan(plan(*HEAD, *item("A1", "AUCUNE"), *item("A2", "AUCUN"))))
    assert refus == ()


def test_une_auto_dependance_REFUSE_au_lieu_d_etre_effacee():
    """M10 · it survived **in both directions**: the module erased it via a `!= item.ident` written
    twice, without a word, and the step went free. Unsatisfiable by construction."""
    reading = read_plan(plan(*HEAD, *item("A1", "A1")))
    _graphe, refus = dependances(reading)

    assert [p.kind for p in refus] == ["dependance_sur_soi"]
    assert "ITSELF" in refus[0].detail


def test_la_prose_ferme_vraiment_la_liste_et_un_id_APRES_elle_est_PERDU_volontairement():
    """M1 · the most dangerous mutant: `break` → `continue` passed **the entire suite green**.

    None of the ten values in the starting corpus carried an identifier AFTER a word of prose —
    `break` and `continue` returned the same tuple there. Here is the entry that tells them apart:
    with `continue`, it is **the 2026-08-14 scan resurrected**, the one that fabricated a false cycle.
    """
    assert lire_liste("A03-2 pour savoir A03-9") == ("A03-2",), "the prose did not close the list"


def test_la_POPULATION_est_lue_par_le_site_REEL_et_pas_seulement_en_appel_direct():
    """M3 · `connus` stopped being passed and nothing turned red: the only test called
    `lire_liste` **directly**, never the site that uses it inside `dependances`."""
    reading = read_plan(
        plan(*HEAD, "- **PEUPLEMENT** \U00002B1C hors forme.", *item("A1", "PEUPLEMENT"))
    )
    graphe, refus = dependances(reading)

    assert graphe["A1"] == frozenset({"PEUPLEMENT"}), "the population is no longer the authority"
    assert refus == ()


def test_les_vagues_sont_TRIEES_et_les_separateurs_comptent_vraiment():
    """M13 and M14 · two freezes every fixture made a no-op (already alphabetical)."""
    reading = read_plan(plan(*HEAD, *item("B1", "AUCUNE"), *item("A1", "AUCUNE")))
    assert ordonner(reading).vagues == (("A1", "B1"),), "the wave is no longer sorted"
    assert lire_liste("A1;A2·A3+A4&A5") == ("A1", "A2", "A3", "A4", "A5")


# --- B2 · THE ORDER BECOMES A FUNCTION — the COMPOSED rank, and its REASON ---------------------


def test_le_rang_compose_met_le_plus_DEBLOCANT_en_tete_et_ecrit_POURQUOI():
    """The bare topological sort answers "what is doable?", never "what should we start with?".

 The item's ``*Obligation*`` puts the REASON at **level 2** — *a rank with no written reason
 is an invisible arbitration*. A sort that does not say why it sorted asks to be trusted, and
 that is exactly what a plan must never ask.
 """
    from mnemosyne.production.plan_ordre import file_d_attente

    reading = read_plan(
        plan(
            *HEAD,
            *item("Z1", "AUCUNE"),          # alphabetically last, unblocks 2
            *item("A9", "AUCUNE"),          # alphabetically first, unblocks 0
            *item("B1", "Z1"),
            *item("B2", "Z1"),
        )
    )
    file, ignorees = file_d_attente(reading)

    assert [r.ident for r in file] == ["Z1", "A9"], "the most unblocking must come first"
    assert file[0].debloque == 2
    assert "unblocks 2" in file[0].raison
    assert "unblocks nothing" in file[1].raison
    assert ignorees == ("peremption",), "an unsupplied component must be NAMED"


def test_le_PERISSABLE_passe_devant_le_plus_deblocant_et_le_MECANISME_MORD():
    """ **What waiting costs cannot be recovered; everything else can.**

 And this test exists because the component **does not bite on the real corpus**: the 4
 perishable items the sibling project declares are not startable today, so replaying it on its plan would
 prove nothing about this half. *A mechanism that never bites proves nothing* — the missing
 population is supplied here.
 """
    from mnemosyne.production.plan_ordre import file_d_attente

    reading = read_plan(
        plan(*HEAD, *item("Z1", "AUCUNE"), *item("A9", "AUCUNE"), *item("B1", "Z1"), *item("B2", "Z1"))
    )
    file, ignorees = file_d_attente(
        reading, perissables={"A9": "the vintages of this window cannot be reconstructed"}
    )

    assert [r.ident for r in file] == ["A9", "Z1"], "the perishable one must come before the most unblocking one"
    assert file[0].perissable is True and file[1].perissable is False
    assert file[0].raison.startswith("PERISHABLE — ") and "vintages" in file[0].raison
    assert ignorees == (), "a supplied component must no longer be named as ignored"


def test_deux_tirages_du_meme_plan_rendent_le_MEME_ordre():
    """A rank that moves without the plan moving is a rank nobody can cite."""
    from mnemosyne.production.plan_ordre import file_d_attente

    reading = read_plan(plan(*HEAD, *item("A2", "AUCUNE"), *item("A1", "AUCUNE")))
    assert [r.ident for r in file_d_attente(reading).rangs] == ["A1", "A2"]
    assert file_d_attente(reading) == file_d_attente(reading), "two runs must be EQUAL"


def test_un_item_deja_FAIT_ou_bloque_n_entre_pas_dans_la_file():
    """The queue answers "what to start with", not "what exists"."""
    from mnemosyne.production.plan_ordre import file_d_attente

    reading = read_plan(
        plan(*HEAD, *item("A1", "AUCUNE", "\U00002705"), *item("A2", "A3"), *item("A3", "AUCUNE"))
    )
    file, _ = file_d_attente(reading, faits=frozenset({"A1"}))

    assert [r.ident for r in file] == ["A3"], "A1 is done, A2 waits on A3"


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/saas/reference-project").is_dir(),
    reason="projects/ is gitignored by design",
)
def test_sur_LE_PROJET_la_tete_de_file_CHANGE_face_au_tri_topologique_nu():
    """`B2`'s `*Fini quand*` clause, on the real corpus — and the gap is published item by item.

 Measured (2026-08-18): the bare sort puts `A02-1` first; the composed rank puts `A06-3`, which
 was at rank 23 and unblocks 4. *An order that changes nothing would not have been worth the
 function.*
 **These three names are a SNAPSHOT, not a guarantee** — found by an isolated audit after the
 previous version (`A01-1` / `A10-12` / rank 100) had drifted with no red saying so: the
 docstring carried no assertion, only prose. What stays true over time are the `assert`s below,
 never this illustration.
 """
    from mnemosyne.production.plan_ordre import file_d_attente

    reading, items = _projet_reference()
    faits = frozenset(i for i, it in items.items() if it.status in {"fait", "clos"})
    nu = [i for i in ordonner(reading).vagues[0] if items[i].status == "a_faire"]
    compose, _ignorees = file_d_attente(reading, faits=faits)

    # STRUCTURAL checks first (2026-08-18) — they depend only on the FORM of the ranking, never
    # on the sibling project's size, so they stay true whatever pace the corpus grows at. **FIXED after audit**:
    # `nu[0] != compose[0].ident` was already HERE, before the exact rank — only the THREE that
    # follow (`debloque==max`, `all raison`, `rangs contigus`) lived after it and were moved this
    # round. An `assert` stops the function at the first failure: leaving them after the exact rank
    # made them invisible every time the rank moved — this very round, `nu.index(...) == 99` broke
    # first and nothing said whether THOSE THREE still held.
    assert nu[0] != compose[0].ident, "the head has not changed — the composition adds nothing"
    assert compose[0].debloque == max(r.debloque for r in compose)
    assert all(r.raison for r in compose), "a rank with no written reason is an invisible arbitration"
    assert [r.rang for r in compose] == list(range(1, len(compose) + 1)), "the ranks are off"
    # **THE EXACT COUNT, NOT A FLOOR — and I had written this rule 250 lines above, in THIS same
    # file, before breaking it here.** The test used to say `> 10` for a value of **99**: 88 ranks
    # of slack, the head could climb from rank 100 to rank 12 with no red, on the very quantity this
    # item exists to change. *A rule you write and then break in the same file is not a rule, it is
    # an ornament.*
    assert nu.index(compose[0].ident) == 22, (
        f"the new head was at rank {nu.index(compose[0].ident) + 1} of the bare sort — the four "
        "structural checks just above are GREEN: the composition always changes the head, and for "
        "the right reason. If it is the corpus that moved, raise the figure knowingly; if one of "
        "the four checks above is RED, it is the composition that changed meaning — fix that before "
        "touching this figure"
    )


def test_RIEN_ne_sort_de_la_file_sans_etre_NOMME():
    """ **THE CLASS THIS MODULE PUT IN CAPITALS TWICE, AND THAT I HAD REOPENED.**

 The first version did ``graphe, _refus = dependances(reading)`` — the refusals **thrown away**.
 So an item whose dependency is unreadable entered the queue **FREE**, with a confident reason:
 measured on the sibling project, ``A06-9`` at **rank 13 of 113**. It also threw away non-"a_faire" statuses
 (**7 `in progress` items**, dependencies satisfied, absent without a word) and the **cycle**
 computed by `ordonner`.

 One rule replaces the three patches: **nothing leaves the queue without being named.**
 """
    from mnemosyne.production.plan_ordre import file_d_attente

    reading = read_plan(
        plan(
            *HEAD,
            *item("A1", "une phrase sans liste"),   # refusal `liste_illisible`
            *item("A2", "A9"),                      # refusal `dependance_inconnue`
            *item("A3", "A3"),                      # refusal `dependance_sur_soi`
            *item("A4", "AUCUNE", "\U0001F504"),            # in progress
            *item("A5", "AUCUNE"),                  # the only one that should remain
            *item("A6", "A5"),                      # waits on A5
        )
    )
    file = file_d_attente(reading)
    ecartes = dict(file.ecartes)

    assert [r.ident for r in file.rangs] == ["A5"], [r.ident for r in file.rangs]
    assert "REFUSED" in ecartes["A1"] and "REFUSED" in ecartes["A2"] and "REFUSED" in ecartes["A3"]
    assert "en cours" in ecartes["A4"]
    assert "waiting on A5" in ecartes["A6"]
    assert set(ecartes) | {"A5"} == {f"A{n}" for n in range(1, 7)}, "an item neither ranked nor named"


def test_un_item_FAIT_absent_de_faits_est_NOMME_car_c_est_le_defaut_de_la_signature():
    """ The DEFAULT trap: `faits=frozenset()` makes a `` block its dependents as if it still had
 to be done. The behaviour is defensible; staying silent about it would make it a trap — measured,
 **18 items from the sibling project** are in this case."""
    from mnemosyne.production.plan_ordre import file_d_attente

    reading = read_plan(plan(*HEAD, *item("A1", "AUCUNE", "\U00002705"), *item("A2", "A1")))
    ecartes = dict(file_d_attente(reading).ecartes)

    assert "absent from `faits`" in ecartes["A1"]
    assert "waiting on A1" in ecartes["A2"]
    assert file_d_attente(reading, faits=frozenset({"A1"})).rangs[0].ident == "A2"


def test_la_composante_ignoree_juge_la_SUBSTANCE_et_pas_la_presence_du_dictionnaire():
    """ `ignorees` judged the dict's *truthiness*: a table naming a NONEXISTENT item made it say
 "peremption composed" for a strictly unchanged order. **And the sibling project's REAL table falls exactly
 into this hole** — its 4 items are not startable."""
    from mnemosyne.production.plan_ordre import file_d_attente

    reading = read_plan(plan(*HEAD, *item("A1", "AUCUNE"), *item("A2", "AUCUNE")))

    assert file_d_attente(reading, perissables={"FANTOME": "x"}).ignorees == ("peremption",)
    assert file_d_attente(reading, perissables={}).ignorees == ("peremption",)
    assert file_d_attente(reading, perissables={"A2": "irréversible"}).ignorees == ()


def test_la_raison_ne_dit_JAMAIS_le_plus_deblocant_a_egalite():
    """ Two FALSE reasons measured: "**THE** most unblocking" on **19 tied ranks out of 21**, and
 "unblocks nothing" on an item whose link had been lost. *The `*Obligation*` puts the reason at
 level 2 — a false reason is worse than an absent one: it gets cited.*"""
    from mnemosyne.production.plan_ordre import file_d_attente

    egalite = read_plan(
        plan(*HEAD, *item("A1", "AUCUNE"), *item("A2", "AUCUNE"), *item("B1", "A1"), *item("B2", "A2"))
    )
    for rang in file_d_attente(egalite).rangs[:2]:
        assert "tied with 1 other" in rang.raison, rang.raison
        assert "THE most" not in rang.raison

    unique = read_plan(plan(*HEAD, *item("A1", "AUCUNE"), *item("A2", "AUCUNE"), *item("B1", "A1")))
    assert "THE most unblocking" in file_d_attente(unique).rangs[0].raison


def test_la_file_et_les_ECARTES_forment_une_PARTITION_EXACTE_des_items():
    """ **THE FIGURE I PUBLISHED DID NOT RECONSTRUCT, and that is the defect.**

 I had written *"111 in the queue, 75 discarded"* for a plan of **168 items** — `111 + 75 = 186`.
 The orchestrator tried to redo it and could not. The cause: a `` item received **TWO** gap
 entries ("status done" then "absent from `faits`") for **one single** situation — 75 entries for
 57 items. *A duplicate in a list of reasons is not visible; it is visible in the SUM, and only
 if someone computes it.*

 One reason per item, and **the partition is asserted in the code itself**, not only here: this
 test guarantees the guarantee exists, the code guarantees it holds on every call.

 And when two reasons are true, the queue publishes **the one that can be acted on**: "absent
 from `faits`" tells the caller its argument is incomplete; "the status no longer applies" is
 accurate and makes nothing happen.
 """
    from mnemosyne.production.plan_ordre import file_d_attente

    reading = read_plan(
        plan(
            *HEAD,
            *item("A1", "AUCUNE", "\U00002705"),
            *item("A2", "A1"),
            *item("A3", "AUCUNE", "\U0001F504"),
            *item("A4", "AUCUNE"),
            *item("A5", "une phrase sans liste"),
        )
    )
    file = file_d_attente(reading)
    ranges = {r.ident for r in file.rangs}
    ecartes = dict(file.ecartes)

    assert len(file.rangs) + len(file.ecartes) == 5, "the sum does not reconstruct the population"
    assert ranges.isdisjoint(ecartes), "an item is both ranked and discarded"
    assert ranges | set(ecartes) == {f"A{n}" for n in range(1, 6)}
    assert len(file.ecartes) == len(set(ecartes)), "an item has TWO reasons to be discarded"
    assert "absent from `faits`" in ecartes["A1"], "the actionable reason must outrank the status"


# --- E1 · `lots()` — the wave SPLIT for a fan-out with no write collision -----------------


def _item_produit(ident: str, produit: str, depend: str = "AUCUNE") -> tuple[str, ...]:
    return (
        f"- **{ident}** \U00002B1C un item.",
        f"  *Produit* : `{produit}`",
        f"  *Dépend de* : {depend}",
    )


def test_lots_separe_deux_produits_qui_partagent_un_chemin_et_garde_le_reste_ENSEMBLE():
    """`E1`, `*Fini quand*` — no colliding pair inside a single lot, on an EXACT fixture.

    A1 and A2 cite the same file in their `*Produit*`: they can NEVER share a lot. A3 cites a
    different file: nothing stops it from joining A1. The result is deterministic (identifiers are
    sorted before the greedy assignment), so pinned character for character rather than by a single
    property — a single property would not have caught an over-separating partition (e.g. one lot
    per item, always valid, never useful to anyone).
    """
    reading = read_plan(
        plan(
            *HEAD,
            *_item_produit("A1", "a.py"),
            *_item_produit("A2", "a.py"),
            *_item_produit("A3", "b.py"),
        )
    )
    resultat = lots(reading, ("A1", "A2", "A3"))

    assert resultat.lots == (("A1", "A3"), ("A2",)), resultat.lots
    assert resultat.separees == (("A1", "A2", "a.py"),), resultat.separees


def test_lots_ne_separe_RIEN_quand_aucun_produit_ne_se_recouvre():
    """The most frequent case on the real plan (98% of pairs, measured at this arc's opening): a
    single lot, `separees` empty — never one lot per item when nothing requires it."""
    reading = read_plan(
        plan(*HEAD, *_item_produit("A1", "a.py"), *_item_produit("A2", "b.py"))
    )
    resultat = lots(reading, ("A1", "A2"))

    assert resultat.lots == (("A1", "A2"),)
    assert resultat.separees == ()


def test_lots_separe_le_MEME_fichier_cite_a_DEUX_LIGNES_differentes():
    """ AUDIT DELEGATED ON 2026-08-15 (E1, reservation on a clause HELD) — measured on the sibling project's
 real plan: 15 pairs of items writing the SAME file (two different line anchors, ``x.py:143``
 versus ``x.py:57-60``) stayed in the SAME lot, because product equality was STRING equality, not
 file equality. Closed in `chemins_cites_par_produit`, a single home — this test proves it at the
 level `E1` mandates, not only at the reader's level."""
    reading = read_plan(
        plan(
            *HEAD,
            *_item_produit("A1", "x.py:143"),
            *_item_produit("A2", "x.py:57-60"),
        )
    )
    resultat = lots(reading, ("A1", "A2"))

    assert resultat.lots == (("A1",), ("A2",)), resultat.lots
    assert resultat.separees == (("A1", "A2", "x.py"),), resultat.separees


def test_lots_partitionne_meme_une_vague_PARTIELLE_sans_toucher_au_reste_du_plan():
    """`vague` is SUPPLIED by the caller — a plan item absent from `vague` enters no calculation at
    all, even if it would collide. `lots` answers "how do we partition THESE idents?", never "what
    is the current wave?" (already answered by `file_d_attente`)."""
    reading = read_plan(
        plan(
            *HEAD,
            *_item_produit("A1", "a.py"),
            *_item_produit("A2", "a.py"),
            *_item_produit("A3", "a.py"),
        )
    )
    resultat = lots(reading, ("A1", "A2"))  # A3 also collides, but is not in the wave

    assert resultat.lots == (("A1",), ("A2",))
    assert resultat.separees == (("A1", "A2", "a.py"),)


def test_lots_publie_UNE_ligne_par_CHEMIN_partage_pas_une_chaine_fourre_tout():
    """"a lot without its list of exclusions is a lot nobody can contest" (E1, word for word) — and
    contesting wants precision: two files common to the same pair make TWO lines."""
    reading = read_plan(
        plan(*HEAD, *_item_produit("A1", "a.py` `b.py"), *_item_produit("A2", "a.py` `b.py"))
    )
    resultat = lots(reading, ("A1", "A2"))

    assert resultat.separees == (("A1", "A2", "a.py"), ("A1", "A2", "b.py")), resultat.separees


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/saas/reference-project").is_dir(),
    reason="projects/ is gitignored by design — absent from a fresh clone",
)
def test_lots_sur_LE_PROJET_AUCUNE_paire_A_L_INTERIEUR_D_UN_LOT_ne_collisionne():
    """`E1`, `*Fini quand*`, on the real corpus — verified by RE-DERIVING the collision, never by
 trusting `lots()` on its own verdict (the judge is not its own witness).

 **Measured at this arc's opening: the sibling project's 14 gates are NEVER merged by `scan_plans`** —
 called gate by gate, `lots()` sees 3.3 times fewer collisions than merging (78/564 versus
 199/6105, the same order of magnitude: 3.3% ≈ 2.2%), because an item from arc 04 and an item
 from arc 06 are never compared if they live in two separate calls. This test merges FIRST, as
 `_projet_reference()` already does for `dependances`/`ordonner`.
 """
    from mnemosyne.production.plan_ordre import chemins_cites_par_produit, file_d_attente

    reading, items = _projet_reference()
    faits = frozenset(i for i, it in items.items() if it.status in {"fait", "clos"})
    demarrables = tuple(sorted(r.ident for r in file_d_attente(reading, faits=faits).rangs))
    assert len(demarrables) > 10, "too few startable items for this test to prove anything"

    resultat = lots(reading, demarrables)

    # Reconstructs the collision INDEPENDENTLY of lots(), through the same public accessor as C2
    # (a single home) — and verifies no pair within the same lot has one.
    chemins = {i: frozenset(chemins_cites_par_produit(items[i].field("produit") or "")) for i in demarrables}
    for groupe in resultat.lots:
        for a_idx, a in enumerate(groupe):
            for b in groupe[a_idx + 1 :]:
                assert chemins[a].isdisjoint(chemins[b]), (
                    f"{a} and {b} share {chemins[a] & chemins[b]} and are yet in the same lot"
                )

    assert resultat.separees, "the sibling project's real plan has known collisions — 0 separated is suspect"
    # The partition covers exactly the startable items received, no more, no less.
    assert sorted(i for groupe in resultat.lots for i in groupe) == list(demarrables)


# --- C3 · `router()` — DERIVED routing, no declaration on sight ------------------------------


def _item_route(
    fini_quand: str | None = None, obligation: str | None = None, a_lire: str | None = None,
    detail: tuple[str, ...] = (), ident: str = "X1",
) -> PlanItem:
    fields = tuple(
        (cle, val)
        for cle, val in (("fini_quand", fini_quand), ("obligation", obligation), ("a_lire", a_lire))
        if val is not None
    )
    return PlanItem(
        ident=ident, status="a_faire", title="titre", section="", line=1, detail=detail, fields=fields
    )


def test_router_ABSTIENT_quand_NI_la_regle_NI_la_commande_ne_repondent():
    """C3, `*Fini quand*` — "no declaration on sight": with no proof either way, cognition is
    `None`, never an optimistic default toward `"faible"`."""
    item = _item_route(fini_quand="ça se juge à l'oeil, pas de commande ici")
    r = router(item, REPO)
    assert r.cognition is None, r.cognition
    assert r.case is None


def test_router_UN_NIVEAU_2_EMPORTE_meme_si_fini_quand_EST_une_commande():
    """Question 2 ("does it change a RULE?") comes BEFORE question 1 and OVERRIDES it — a level 2
    or 3 is `"elevee"` no matter what `*Fini quand*` says, because a barrier remains an arbitration
    even when its closing clause is mechanical."""
    item = _item_route(fini_quand="`make test` rend `rc=0`", obligation="**niveau 2** — une barrière")
    r = router(item, REPO)
    assert r.cognition == "elevee", r.cognition


def test_router_UN_FINI_QUAND_COMMANDE_SANS_regle_est_FAIBLE():
    item = _item_route(fini_quand="`pytest -q tests/test_x.py` rend `rc=0`", obligation="**niveau 1**")
    r = router(item, REPO)
    assert r.cognition == "faible", r.cognition


def test_router_le_volume_TOMBE_EN_PLANCHER_sur_la_taille_de_l_item_SANS_a_lire():
    """`*À lire*` answers "what to open IN ADDITION" — absent (the sibling project's case, 0/168), the relay is
    the item's OWN size, never a volume invented out of zero."""
    court = _item_route(fini_quand="x", detail=("bref",))
    long = _item_route(fini_quand="x", detail=("l" * (SEUIL_OCTETS + 100),))
    assert router(court, REPO).volume == "faible"
    assert router(long, REPO).volume == "eleve"


def test_router_le_volume_ne_rend_JAMAIS_None_meme_sans_a_lire_ni_detail():
    """ AUDIT DELEGATED ON 2026-08-15 — the docstring promised `None`, the code never returns it
 (the fallback covers every case where `charge_en_octets` returns one): only `cognition` can
 make `router` abstain, never `volume`. The type now says so (`str`, not `str | None`)."""
    vide = _item_route(fini_quand="x", detail=())
    r = router(vide, REPO)
    assert r.volume in ("faible", "eleve")
    assert r.volume is not None


def test_router_le_volume_COMPTE_DES_OCTETS_UTF8_pas_des_CODE_POINTS():
    """ AUDIT DELEGATED ON 2026-08-15 — the fallback compared Python characters (code points)
 against the same threshold `charge_en_octets` compares real bytes with. Accented text has FEWER
 code points than UTF-8 bytes (each accent = 1 code point, 2 bytes): an item just under the byte
 threshold but made of multi-byte characters could silently pass as `faible` while ASCII text of
 the same length IN BYTES would be `eleve`. DISCRIMINATING fixture: ``SEUIL_OCTETS // 2 + 100``
 accented characters (`é`, 2 bytes each in UTF-8) — UNDER the threshold in CODE POINTS (the old
 behaviour would return `faible`), OVER it in BYTES (the fixed behaviour returns `eleve`): the
 only fixture that truly tells the two units apart, not one that clears the threshold under both
 at once."""
    n = SEUIL_OCTETS // 2 + 100
    accents = _item_route(fini_quand="x", detail=("é" * n,))
    code_points = len("é" * n) + len("titre")  # + len(item.title) as _volume computes it
    octets = len(("é" * n).encode("utf-8")) + len("titre".encode("utf-8"))
    assert code_points < SEUIL_OCTETS, "the fixture must MISS the threshold IN CODE POINTS"
    assert octets >= SEUIL_OCTETS, "the fixture must CLEAR the threshold IN UTF-8 BYTES"
    assert router(accents, REPO).volume == "eleve", (
        "counted in UTF-8 bytes as charge_en_octets does, this text clears the threshold — "
        "counted in code points (the old behaviour), it would stay under it"
    )


def test_router_le_volume_PREFERE_a_lire_QUAND_il_est_present(tmp_path: Path):
    (tmp_path / "petit.py").write_text("o" * 10, encoding="utf-8")
    # *À lire* resolves a tiny file (10 bytes); detail ALONE, without it, would be HIGH — if the
    # result is "faible", that is the proof *À lire* truly took precedence over the fallback.
    item = _item_route(
        fini_quand="x", a_lire="`petit.py`", detail=("d" * (SEUIL_OCTETS * 5),)
    )
    r = router(item, tmp_path)
    assert r.volume == "faible", "the *À lire* load (10 bytes) must outweigh the fallback (detail)"


def test_repartition_est_une_PARTITION_EXACTE_les_quatre_cles_toujours_presentes():
    items = (
        _item_route(ident="X1", fini_quand="x", detail=("bref",)),  # abstention (neither rule nor command)
        _item_route(ident="X2", fini_quand="`make plans` rend `rc=0`", detail=("bref",)),  # sous_agent
        _item_route(
            ident="X3", obligation="niveau 2", fini_quand="x", detail=("l" * (SEUIL_OCTETS + 1),)
        ),  # chat d'arc
    )
    comptes, abstentions = repartition(items, REPO)
    assert set(comptes) == {"sous_agent", "le_parc", "sous_agent_capable", "le_chat_d_arc"}
    assert comptes == {"sous_agent": 1, "le_parc": 0, "sous_agent_capable": 0, "le_chat_d_arc": 1}, comptes
    assert abstentions == ("X1",), abstentions
    assert sum(comptes.values()) + len(abstentions) == len(items)


def test_repartition_NOMME_un_item_SANS_ident_au_lieu_de_le_faire_disparaitre():
    """ AUDIT DELEGATED ON 2026-08-15 — an item with no identifier (the floor `- [ ] text`, D33)
 disappeared from BOTH counts: neither classified nor abstained. `sum(counts) + len(abstentions)
 < len(items)` with no figure saying so — exactly the class this function exists to close.
 Reproduced on 2 items, 1 with no ident; the partition must remain EXACT."""
    items = (
        _item_route(ident="X1", fini_quand="`make plans` rend `rc=0`", detail=("bref",)),
        PlanItem(ident="", status="a_faire", title="plancher sans ID", section="", line=7, detail=()),
    )
    comptes, abstentions = repartition(items, REPO)
    assert sum(comptes.values()) + len(abstentions) == len(items), (comptes, abstentions)
    assert any("line 7" in a for a in abstentions), abstentions


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/saas/reference-project").is_dir(),
    reason="projects/ is gitignored by design — absent from a fresh clone",
)
def test_router_REJOUE_sur_LE_PROJET_publie_les_quatre_cases_ET_les_abstentions():
    """C3, `*Fini quand*` — replayed on the sibling project's 168 items, not a fixture.

 **Found by checking, not by reading the code**: `*Obligation*` (0/168) and `*À lire*` (0/168)
 are declared by NO item from the sibling project — both are inventions of THIS plan. Question 2 can therefore NEVER
 answer `"elevee"` on the sibling project today: both HIGH-cognition cells stay at zero, honestly, until the sibling project
 adopts `*Obligation*` (the same gesture as `*État du terrain*`, pushed to all four seats the same
 day). This is not a defect of the router: it is the exact measurement of what the sibling project can classify
 with the vocabulary it has today.
 """
    reading, items = _projet_reference()
    comptes, abstentions = repartition(reading.items, REPO / "projects/saas/reference-project")

    assert sum(comptes.values()) + len(abstentions) == len(reading.items) == 168
    assert comptes["sous_agent_capable"] == 0, "no item from the sibling project declares *Obligation* >= 2"
    assert comptes["le_chat_d_arc"] == 0, "no item from the sibling project declares *Obligation* >= 2"
    assert comptes["sous_agent"] > 0 and comptes["le_parc"] > 0, (
        "question 1 (command) must decide at least a few items on both volumes"
    )
    assert len(abstentions) > 0, "at least one item must remain unclassified (a suspicious zero otherwise)"


# TODO(public-mirror): this test reads docs/PLAN.md via scan_plans(REPO) at runtime. docs/PLAN.md
# is not part of this public mirror's scope (docs/ is allow-listed to FORMAT_PLAN.md, parentheses/
# README.md and signalements/README.md only — see contract rule 2's own example, which names
# docs/PLAN.md itself as a private document absent from this mirror). Unlike the sibling-project-dependent
# tests above, this one carries no skipif guard, so it will fail in the mirror (StopIteration on
# `next(...)`) until a human decides whether to add a skip, point it at a plan that does ship with
# the mirror, or exclude it.
def test_router_sur_MNEMOSYNE_les_items_a_barriere_LOURDE_atterrissent_chez_le_chat_d_arc():
    """Counter-proof on the plan that DECLARES `*Obligation*`: `H1`/`A1`/`C2` (level 2 or 3, large
    items) must fall into `"le_chat_d_arc"` — the cell the operator explicitly asked to preserve
    (*"the main chat has enormous granularity"*)."""
    from mnemosyne.production.plan_registry import scan_plans

    registry = scan_plans(REPO)
    porte = next(p for p in registry.projects if p.plan_path == REPO / "docs" / "PLAN.md")
    par_ident = {it.ident: it for it in porte.reading.items if it.ident}

    for ident in ("H1", "A1", "C2"):
        assert ident in par_ident, f"{ident} disappeared from the real plan — this test's fixture has moved"
        r = router(par_ident[ident], REPO)
        assert r.cognition == "elevee", f"{ident} declares obligation>=2 and should be 'elevee': {r}"


# --- D6 -- DURATION PER STEP: two absences of measurement must never compare equal -------------


def test_duree_par_etape_NOMME_une_ouverture_absente_JAMAIS_zero():
    resultat = duree_par_etape(("A1",), {"A1": None}, {"A1": "2026-08-01T00:00:00+00:00"})
    assert resultat == (
        DureeEtape("A1", None, "2026-08-01T00:00:00+00:00", None, "opening not datable"),
    )


def test_duree_par_etape_NOMME_une_fermeture_absente_JAMAIS_zero():
    resultat = duree_par_etape(("A1",), {"A1": "2026-08-01T00:00:00+00:00"}, {"A1": None})
    assert resultat == (
        DureeEtape("A1", "2026-08-01T00:00:00+00:00", None, None, "closing not datable"),
    )


def test_duree_par_etape_NOMME_les_DEUX_absences_avec_une_raison_QUI_LES_DISTINGUE():
    """The two reasons from `test_..._ouverture_absente`/`..._fermeture_absente` and this one are
    THREE different strings -- a generic reason ("unknown") would have blurred the three classes D6
    requires to be kept separate."""
    seule_ouverture = duree_par_etape(("A1",), {"A1": None}, {"A1": "2026-08-01T00:00:00+00:00"})
    seule_fermeture = duree_par_etape(("A1",), {"A1": "2026-08-01T00:00:00+00:00"}, {"A1": None})
    aucune = duree_par_etape(("A1",), {"A1": None}, {"A1": None})
    raisons = {seule_ouverture[0].raison_absence, seule_fermeture[0].raison_absence, aucune[0].raison_absence}
    assert len(raisons) == 3, f"the three absence classes must carry THREE reasons: {raisons}"
    assert aucune == (DureeEtape("A1", None, None, None, "neither opening nor closing is datable"),)


def test_duree_par_etape_calcule_des_JOURS_QUAND_les_deux_dates_existent():
    resultat = duree_par_etape(
        ("A1",),
        {"A1": "2026-08-01T00:00:00+00:00"},
        {"A1": "2026-08-03T12:00:00+00:00"},
    )
    assert resultat[0].jours == pytest.approx(2.5)
    assert resultat[0].raison_absence == ""


def test_duree_par_etape_ZERO_JOUR_REEL_ne_se_confond_PAS_avec_une_absence():
    """Same commit opens and closes. The result must carry `jours=0.0`, NEVER `None`: a real zero
 measurement and no measurement at all are two different things, and confusing the two would be
 exactly the error D6's clause forbids.

 **RETRACTION (audit of 2026-08-16)**: this docstring claimed "a real case on the sibling project, measured
 by hand" -- FALSE. What I had measured by hand was an ARTEFACT of the sibling project's root commit (the
 repository was recreated after an object loss): 9 of the 13 items that looked like "zero real
 days" opened AND closed on that same root commit, one item (`F7`) itself carrying "CLOSED on
 2026-07-29" -- NINE DAYS before the visible history begins. Fixed in `plan_duree_run.py`
 (`_est_commit_racine`): a date resolved on the root commit is now NAMED non-datable, never
 published as a real zero. This test itself remains valid on the PURE function (synthetic dates,
 not the sibling project) -- only my characterisation of the real corpus was wrong."""
    resultat = duree_par_etape(
        ("A1",), {"A1": "2026-08-01T00:00:00+00:00"}, {"A1": "2026-08-01T00:00:00+00:00"}
    )
    assert resultat[0].jours == 0.0
    assert resultat[0].raison_absence == ""


def test_duree_par_etape_NOMME_une_fermeture_ANTERIEURE_a_l_ouverture_comme_ANOMALIE():
    """A closing dated BEFORE the opening cannot be a real negative -- it is a defect further up
    the git archaeology (wrong path, wrong item), and naming it stops a negative number from
    silently polluting a per-wave median."""
    resultat = duree_par_etape(
        ("A1",), {"A1": "2026-08-03T00:00:00+00:00"}, {"A1": "2026-08-01T00:00:00+00:00"}
    )
    assert resultat[0].jours is None
    assert "anomaly" in resultat[0].raison_absence


def test_duree_par_vague_rend_None_PAS_zero_quand_AUCUNE_etape_datable():
    etapes = (DureeEtape("A1", None, None, None, "neither opening nor closing is datable"),)
    resultat = duree_par_vague((("A1",),), etapes)
    assert resultat == ((0, None, ("A1",)),)


def test_duree_par_vague_calcule_la_MEDIANE_des_etapes_datables_SEULEMENT():
    etapes = (
        DureeEtape("A1", "o", "f", 1.0, ""),
        DureeEtape("A2", "o", "f", 3.0, ""),
        DureeEtape("A3", None, None, None, "neither opening nor closing is datable"),
    )
    indice, mediane, non_datables = duree_par_vague((("A1", "A2", "A3"),), etapes)[0]
    assert indice == 0
    assert mediane == 2.0
    assert non_datables == ("A3",)


def test_duree_par_vague_saute_un_ident_ENCORE_OUVERT_sans_l_accuser():
    """An item not in `etapes` at all (not yet closed) is neither counted nor named as
    non-datable -- it is not the same class as a closed item whose dates are missing."""
    etapes = (DureeEtape("A1", "o", "f", 1.0, ""),)
    indice, mediane, non_datables = duree_par_vague((("A1", "A2"),), etapes)[0]
    assert mediane == 1.0
    assert non_datables == (), "A2 (still open) must not appear here or anywhere else"


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "projects/saas/reference-project").is_dir(),
    reason="projects/ is gitignored by design — absent from a fresh clone",
)
def test_duree_REJOUE_sur_LE_PROJET_date_ou_NOMME_chacune_des_18_etapes_fermees():
    """D6, `*Fini quand*` — on the sibling project's real history, never a fixture.

 Measured before writing this test (not assumed): the sibling project carries exactly 18 `fait`/`clos` items
 out of 168. Each must come out with a real duration OR a named reason -- never silent, never a
 zero that would mask an absence.

 **AUDIT OF 2026-08-16: 0/18 date, AND THAT IS THE CORRECT RESULT, not a failure.** The sibling project was
 recreated after an object loss ("base: NEW REPOSITORY" -- its own root commit message): the 18
 closed items all open and/or close on that root commit or just after, which makes them GENUINELY
 non-datable -- the visible history does not reach back far enough to know. The pre-audit version
 published 13/18 at `jours=0.0`, confusing this history gap with real lightning-fast work; this
 one honestly names all 18, in TWO distinct classes (see `plan_duree_run._est_commit_racine`).
 """
    from mnemosyne.runtime.plan_duree_run import duree_du_plan

    reading, _ = _projet_reference()
    fermes = tuple(i for i in reading.items if i.status in ("fait", "clos"))
    assert len(fermes) == 18, f"population expected by the clause: 18, measured: {len(fermes)}"

    duree = duree_du_plan(REPO / "projects/saas/reference-project", reading, "PLAN.md")
    assert len(duree) == 18
    assert {e.ident for e in duree} == {i.ident for i in fermes}
    for etape in duree:
        assert (etape.jours is not None) != bool(etape.raison_absence), (
            f"{etape.ident}: exactly ONE of (jours, raison_absence) must be set — "
            f"jours={etape.jours!r} raison={etape.raison_absence!r}"
        )
        assert etape.jours != 0.0 or etape.raison_absence, (
            f"{etape.ident}: jours=0.0 on the sibling project is ALWAYS suspicious (recent root, imported corpus) "
            "— a real zero-day has never been proven on this specific repository, unlike the "
            "dedicated test on the pure function (synthetic dates)"
        )
    raisons = {e.raison_absence for e in duree if e.raison_absence}
    assert raisons == {"opening not datable", "neither opening nor closing is datable"}, (
        f"the two measured absence classes must both remain present: {raisons}"
    )
