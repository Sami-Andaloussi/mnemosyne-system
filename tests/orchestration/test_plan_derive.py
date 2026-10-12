"""D1 — the two drift ratchets, and what keeps them from lying.

 **The witness that decides is the SWAP one**: one item closes, another reopens, and the COUNT
doesn't move even though the plan itself has moved. That's the fault the sibling project paid for (*"the set of
`` was IDENTICAL after 299 commits"*) and the reason this module compares SETS. A test that only
arms the count would let exactly this case through.

The second is the CALIBRATION one: D1's exit condition requires finding a turning point *"without
being handed one."* No date, no threshold may exist in the code — and the only way to prove it is
to move the turning point and check that the detector follows it.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from mnemosyne.production import plan_derive

from mnemosyne.production.plan_derive import (
    PAR_FICHIER,
    Tour,
    ecart_des_unites,
    immobilite,
    lire,
    lire_produit,
    part_produit,
    plus_grande_chute,
    rendre,
)

EST_PRODUIT = lambda chemin: chemin.startswith("produit/")  # noqa: E731


def _tours(jours: dict[str, list[tuple[str, set[str]]]]) -> list[Tour]:
    """Builds tours from `{date: [(path, done-items), …]}`, in date order."""
    return [
        Tour(sha=f"{date}-{n}", date=date, chemins=(chemin,), faits=frozenset(faits))
        for date, commits in sorted(jours.items())
        for n, (chemin, faits) in enumerate(commits)
    ]


# --------------------------------------------------------------------------------------------
# (a) THE PRODUCT SHARE — and the DERIVED turning point, never handed to it
# --------------------------------------------------------------------------------------------


def test_la_bascule_est_TROUVEE_sans_qu_on_lui_donne_ni_date_ni_seuil():
    """ D1's central clause: *a detector calibrated on the answer detects nothing.*"""
    tours = _tours(
        {
            "2026-07-20": [("produit/a.py", set()), ("produit/b.py", set())],
            "2026-07-21": [("outillage/x.py", set()), ("outillage/y.py", set())],
        }
    )
    chute = plus_grande_chute(part_produit(tours, EST_PRODUIT))
    assert chute is not None
    assert (chute.depuis, chute.vers) == ("2026-07-20", "2026-07-21")
    assert chute.ampleur == 1.0


def test_la_bascule_SUIT_les_donnees_quand_on_la_DEPLACE():
    """The proof that no date is written anywhere: we move the turning point, it follows.

    A detector that always returned the same date would pass the previous test and fail here.
    """
    tours = _tours(
        {
            "2026-09-01": [("produit/a.py", set())],
            "2026-09-02": [("produit/b.py", set())],
            "2026-09-03": [("outillage/x.py", set())],
        }
    )
    chute = plus_grande_chute(part_produit(tours, EST_PRODUIT))
    assert (chute.depuis, chute.vers) == ("2026-09-02", "2026-09-03")


@pytest.mark.parametrize("ampleur", [0.50, 0.10, 0.02, 0.005, 0.001])
@pytest.mark.parametrize("annee", ["2026", "2027", "2031"])
@pytest.mark.parametrize("mois", ["01", "07", "12"])
def test_AUCUN_seuil_ni_AUCUNE_date_ne_peut_vivre_dans_le_code(ampleur, annee, mois):
    """ **CLAUSE `(c2)` CLOSED AS A CLASS, after being REFUTED TWICE.**

 First audit: three hardcodes passed. I fixed it with **ONE** witness, in July, of amplitude
 **0.10**. Second audit: **four** hardcodes still passed — `> 0.05`, `> 0.09`, a date on
 `2026-07-26`, a year `2027`. **The cause wasn't the witness's content, it was its
 UNIQUENESS**: the first three hardcodes died to **a single** witness, so it was enough to
 calibrate *under* its one value. *Fixing a CASE doesn't close the CLASS — a single witness is
 bypassed by an INEQUALITY.*

 **So we no longer test ONE population, we test FORTY-FIVE**: five amplitudes, three years,
 three months. A literal threshold fails under its amplitude; a literal date or year fails as
 soon as the series doesn't live there. *No constant can satisfy a family whose members vary
 on the very axis it's written on.*

 **The population is VERIFIED before being judged** — a fixture that doesn't announce what
 it produces returns a green that measures nothing, and I've already paid for that twice today.
 """
    haut, bas = 0.60, 0.60 - ampleur
    total = 1000
    tours = _tours(
        {
            f"{annee}-{mois}-10": [("produit/a.py", set())] * round(haut * total)
            + [("outillage/x.py", set())] * (total - round(haut * total)),
            f"{annee}-{mois}-11": [("produit/b.py", set())] * round(bas * total)
            + [("outillage/y.py", set())] * (total - round(bas * total)),
        }
    )
    serie = part_produit(tours, EST_PRODUIT)
    assert len(serie) == 2 and serie[0].total == total, "the population must be the one announced"
    chute = plus_grande_chute(serie)
    assert chute is not None, (
        f"a drop of {ampleur} exists on {annee}-{mois} — a literal THRESHOLD makes it disappear"
    )
    assert (chute.depuis, chute.vers) == (f"{annee}-{mois}-10", f"{annee}-{mois}-11"), (
        f"a literal DATE returns a different answer: {chute}"
    )
    assert abs(chute.ampleur - ampleur) < 0.002, f"DRAWN amplitude: {chute.ampleur} != {ampleur}"


def test_l_ampleur_RENDUE_suit_l_ampleur_REELLE_jusqu_a_l_infinitesimal():
    """ **THE OTHER HALF OF THE CLASS — the THRESHOLD axis, closed by MONOTONICITY.**

 Enumeration is always under-cut: my parametrized witness goes down to `0.001`, and an audit
 got `> 0.0005` to pass. *A list of values cannot close a constant that gets chosen AFTER
 reading it.*

 **The property that closes it is STRICT MONOTONICITY**: for a family of decreasing
 amplitudes, the RETURNED amplitude must decrease strictly and **none may disappear**. A
 literal threshold truncates the family to `None` past some rank — whatever its value, as soon
 as the family drops below it.

 **WHAT THIS WITNESS DOESN'T CATCH, said plainly**: a threshold under `1e-6` would survive.
 But on a WORK SHARE, `1e-6` is no longer a calibration — it's numerically indistinguishable
 from zero, so such a threshold can no longer serve to hide an answer. *No finite family
 closes an arbitrarily small threshold; what CAN be done is making it UNUSABLE.*
 **And the fixture uses `PAR_LIGNE`**: my first version built `10**7` `Tour` objects to
 reach the needed precision — absurd and endless. **Lines** give the same precision with
 **two paths**. *When a population is expensive, it's often the unit that was chosen, not the
 property being tested.*
 """
    from mnemosyne.production.plan_derive import PAR_LIGNE

    rendues = []
    for exposant in range(1, 7):  # 1e-1 … 1e-6
        ampleur = 10.0**-exposant
        echelle = 10**7
        haut, bas = round(0.5 * echelle), round((0.5 - ampleur) * echelle)
        tours = [
            Tour("a", "2026-05-01", ("produit/a.py", "o/x.py"), frozenset(), (haut, echelle - haut)),
            Tour("b", "2026-05-02", ("produit/b.py", "o/y.py"), frozenset(), (bas, echelle - bas)),
        ]
        chute = plus_grande_chute(part_produit(tours, EST_PRODUIT, unite=PAR_LIGNE))
        assert chute is not None, (
            f"a drop of {ampleur:g} MUST be returned — a literal threshold makes it disappear here"
        )
        rendues.append(chute.ampleur)
    assert all(a > b for a, b in zip(rendues, rendues[1:], strict=False)), (
        f"the returned amplitude must decrease STRICTLY with the real amplitude: {rendues}"
    )


def _tours_plats(n: int, faits) -> "list[Tour]":
    return [Tour(f"s{i}", "2026-07-20", ("produit/a.py",), faits) for i in range(n)]


def test_un_TOUR_construit_SANS_faits_vaut_INCONNU_et_non_MESURE_VIDE():
    """ **The site my other three witnesses did NOT judge: the constructor's DEFAULT.**

 Measured: after the fix, restoring `faits: … = frozenset()` **survived** the three witnesses
 below — because they all pass ``faits`` **explicitly**. But the real default was exactly
 there: an edge that **omits** ``faits`` (which every caller did, since none exists yet)
 received "measured empty" instead of "unknown," and the page lied.

 *Checking one value doesn't protect the site that uses ANOTHER one.* A field's default is
 a call site in its own right, and the most traveled of all: the one nobody writes."""
    nu = Tour("s0", "2026-07-20", ("produit/a.py",))
    assert nu.faits is None, (
        "a Tour built WITHOUT faits equals \"measured empty\" — so an edge that reads no "
        "done-item at all fabricates maximal immobility and publishes the sibling project's failure starting "
        "from zero data"
    )
    immo, _ = immobilite([Tour(f"s{i}", "2026-07-20", ("produit/a.py",)) for i in range(255)])
    assert immo is None, f"255 tours built WITHOUT faits fabricated an immobility: {immo}"


def test_une_fenetre_SANS_faits_ne_publie_PAS_une_immobilite():
    """ **The page used to publish the sibling project's exact failure starting from ZERO data.**

 When no tour carries done-items, the old ``frozenset()`` default returned a population where
 *nothing ever changes* — hence maximal immobility, hence the sentence *"N commits without a
 SINGLE identifier changing."* That is **word for word** the sibling project's diagnosis, drawn from a
 window where **the edge had read nothing**.

 The cause: ``frozenset()`` served **two masters** — *"no done-item"* and *"we don't
 know."* A value that serves two masters cannot be normalized once; it needs two values.
 ``None`` = UNKNOWN, ``frozenset()`` = measured empty."""
    immo, echanges = immobilite(_tours_plats(255, None))
    assert immo is None, f"255 tours WITHOUT faits fabricated an immobility: {immo}"
    assert echanges == ()
    page = rendre(lire(_tours_plats(255, None), EST_PRODUIT))
    assert "NOT MEASURED" in page
    assert "without a SINGLE identifier" not in page, "the page publishes the sibling project's failure with no data"


def test_des_faits_MESURES_VIDES_publient_BIEN_une_immobilite():
    """ **The PASSING case, the one I never assert on.** An explicit ``frozenset()`` means
 *"the edge read, and nothing is done"* — a plan genuinely frozen at zero steps. That one
 **must** publish its immobility, or the fix above simply turned the measurement off."""
    immo, _ = immobilite(_tours_plats(255, frozenset()))
    assert immo is not None and immo.commits == 255
    assert "without a SINGLE identifier" in rendre(lire(_tours_plats(255, frozenset()), EST_PRODUIT))


def test_les_DEUX_absences_ne_se_lisent_PAS_pareil():
    """ *Two absences of measurement compare EQUAL.* "The window is empty" and "the edge read
 no done-item" are two different things; as long as the page writes the same sentence for
 both, the reader cannot know which one they have."""
    vide = rendre(lire([], EST_PRODUIT))
    sans = rendre(lire(_tours_plats(10, None), EST_PRODUIT))
    assert vide != sans, "the EMPTY window and the window WITHOUT DONE-ITEMS return the SAME page"


def test_une_population_MIXTE_ne_fait_pas_len_de_None():
    """ The SWAP detector's ``len(a) == len(b)`` guard would have raised ``TypeError`` as soon
 as a single tour carries ``None`` next to a measured tour — a crash, not a refusal."""
    melange = [
        Tour("a", "2026-07-20", ("produit/a.py",), None),
        Tour("b", "2026-07-20", ("produit/a.py",), frozenset({"I1"})),
        Tour("c", "2026-07-20", ("produit/a.py",), frozenset({"I2"})),
        Tour("d", "2026-07-20", ("produit/a.py",), None),
    ]
    immo, echanges = immobilite(melange)
    assert immo is not None
    assert echanges == ("c",), f"only b→c is a SWAP (equal cardinal, different set): {echanges}"


def _dates_dans_le_code(source: str) -> "list[tuple[int, str]]":
    """Strings that look like a DATE present in the CODE — **docstrings excluded**.

 A TEXT probe would count CITATIONS: this module *talks about* the July 21st turning point
 in its prose, and that's legitimate. So we go through the AST and explicitly strip
 docstrings (``Expr``/``Constant`` at the head of a body) — comments, for their part, are
 already not AST nodes."""
    arbre = ast.parse(source)
    docs = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            tete = noeud.body[0] if noeud.body else None
            if isinstance(tete, ast.Expr) and isinstance(tete.value, ast.Constant):
                if isinstance(tete.value.value, str):
                    docs.add(id(tete.value))
    motif = re.compile(r"\d{4}-\d{2}(-\d{2})?")
    return [
        (n.lineno, n.value)
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and id(n) not in docs
        and motif.search(n.value)
    ]


def test_AUCUNE_date_ne_vit_dans_le_CODE_du_module_derive():
    """ **THE THRESHOLD FAMILY IS INFINITE — no finite fixture closes it.**

 Three sabotages out of seven survived the parametrized fixture above, and all three say the
 same thing: *the population was too narrow on the sabotage's own axis.*

 | sabotage | why it survives a FIXTURE |
 |---|---|
 | `vers == "…-21" and ampleur > 0.05` | my amplitudes only take **two** values (0.02 · 0.30) — **any threshold between the two** passes |
 | `vers == "…-15"` | the 15th is the **first** day: no transition **enters** it, the sabotage is **inert** and so unkillable |
 | `vers.startswith("2026-07")` | the **whole** window is in July → the predicate is **constant**, order unchanged |

 *Enumeration is always under-cut* — my own lesson, and `(c2)`'s third refutation
 demonstrates it. So we close it **by source INVARIANCE, not by case**: in this module, **no
 date is allowed to exist in the code**. The prose may cite as many as it wants; the code,
 zero.

 **What this freeze does NOT say**: a date could live in a *neighboring* module called
 from here, or be **recomposed** (``"2026-" + "07-21"``, a `datetime.date(…)`). The admission
 is worth more than a false barrier — but the shape that seven sabotages spontaneously write
 is, itself, closed."""
    source = pathlib.Path(plan_derive.__file__).read_text(encoding="utf-8")
    assert _dates_dans_le_code(source) == [], (
        f"a DATE lives in plan_derive's code: {_dates_dans_le_code(source)}"
    )


@pytest.mark.parametrize(
    "cle",
    [
        '(c.vers == "2026-07-21" and c.ampleur > 0, c.ampleur)',
        '(c.vers == "2026-07-21", c.ampleur)',
        '(c.vers == "2026-07-21" and c.ampleur > 0.05, c.ampleur)',
        '(c.vers == "2026-07-15", c.ampleur)',
        '(c.vers == "2026-07-22" and c.ampleur > 0, c.ampleur)',
        '(c.vers == "2026-07-29" and c.ampleur > 0, c.ampleur)',
        '(c.vers.startswith("2026-07"), c.ampleur)',
    ],
)
def test_la_sonde_REFUSE_les_SEPT_sabotages_dont_les_TROIS_increvables(cle):
    """ **The probe proves nothing until it's been seen to BITE.** Here we hand it the seven
 exact shapes drawn from a clone at `d2d1681` — including the **three** that no fixture
 killed — and we demand a refusal every time. *A mechanism that never bites proves nothing.*"""
    ancre = "        key=lambda c: c.ampleur,"
    source = pathlib.Path(plan_derive.__file__).read_text(encoding="utf-8")
    assert source.count(ancre) == 1, "the sabotage anchor moved — this witness no longer measures anything"
    sabote = source.replace(ancre, f"        key=lambda c: {cle},")
    assert _dates_dans_le_code(sabote), f"the probe LETS {cle} THROUGH"


def test_la_sonde_ne_compte_PAS_les_dates_de_la_PROSE():
    """ The half every detector is missing: *a TEXT detector counts CITATIONS.* A date **added
 to the docstring** must trigger NOTHING, or the probe forbids explaining the turning point —
 and gets disarmed by the first person who wants to write accurate prose."""
    source = pathlib.Path(plan_derive.__file__).read_text(encoding="utf-8")
    prose = source.replace(
        '"""The largest drop',
        '"""The real turning point falls on 2026-07-21. The largest drop',
        1,
    )
    assert prose != source, "the targeted docstring moved — this witness no longer measures anything"
    assert _dates_dans_le_code(prose) == [], "the probe counts a CITATION as an instance"


def _serie_decroissante(dates: "list[str]", parts: "list[float]") -> "list[Tour]":
    """A series where EACH day carries the share it's given — to draw chosen drops."""
    tours: list[Tour] = []
    for date, part in zip(dates, parts, strict=True):
        produit = round(part * 100)
        tours += [
            Tour(f"{date}-{i}", date, ("produit/a.py",) if i < produit else ("o/x.py",), frozenset())
            for i in range(100)
        ]
    return tours


@pytest.mark.parametrize("jour_max", [1, 2, 3, 5, 8, 11, 13])
def test_CHAQUE_jour_de_la_FENETRE_REELLE_porte_une_chute_NON_NULLE_et_le_MAX_bouge(jour_max):
    """ **`(c2)` REFUTED A THIRD TIME, and by an INEQUALITY added to the hardcode.**

 My previous fixture put the transition toward July 21st at **exactly 0.0** (0.50 →
 0.50). An auditor therefore restored the entire hardcode by writing
 `key=(c.vers == "2026-07-21" AND c.ampleur > 0, c.ampleur)`: the date no longer applies when
 the amplitude is zero, so **my witness no longer sees it**, and both clauses turn green
 again. *A single witness is bypassed by an INEQUALITY* — my own lesson, re-violated on my
 own item, **twice in a row**.

 **What this fixture closes, that the previous two were missing:**
 * it lives over **the entire real window** (`07-15` to `07-29`) — sabotages
 `S12`/`S15`/`S16` targeted the 15th, the 22nd and the 29th, **days where no witness lived**;
 * **every** transition carries a **NON-ZERO** drop — so no `ampleur > 0` guard can subtract a
 date from the judgment;
 * the maximum **moves** from one case to the next — so no privileged date can fabricate it,
 nor can removing a day shift it without being seen.

 *A family where every member is non-degenerate on the tested axis closes what a single
 value always leaves open.*"""
    dates = [f"2026-07-{j:02d}" for j in range(15, 30)]
    # a series that DECREASES everywhere (every transition drops), with a marked dip on the target day
    parts = [0.95 - 0.02 * i for i in range(len(dates))]
    parts[jour_max + 1] = parts[jour_max] - 0.30  # THE maximal drop, moved by the parameter
    for i in range(jour_max + 2, len(parts)):
        parts[i] = parts[jour_max + 1] - 0.02 * (i - jour_max - 1)
    serie = part_produit(_serie_decroissante(dates, parts), EST_PRODUIT)
    assert len(serie) == len(dates), "the population must carry ALL the days in the window"
    ecarts = [round(a.part - b.part, 6) for a, b in zip(serie, serie[1:], strict=False)]
    assert all(e > 0 for e in ecarts), f"EVERY transition must drop, none at zero: {ecarts}"

    chute = plus_grande_chute(serie)
    assert chute is not None
    assert (chute.depuis, chute.vers) == (dates[jour_max], dates[jour_max + 1]), (
        f"the largest drop is {dates[jour_max]} → {dates[jour_max + 1]}; "
        f"the detector returns {chute.depuis} → {chute.vers} — a DATE lives in the code"
    )
    assert abs(chute.ampleur - 0.30) < 0.001, f"DRAWN amplitude: {chute.ampleur}"


def test_la_serie_TRANSLATEE_rend_la_MEME_chute_a_la_date_pres():
    """ **WHAT ENUMERATION CANNOT CLOSE, and I'd rather say so than hide it.**

 The parametrized witness above varies the amplitude, the year and the month — **not the
 day**. An isolated audit measured it: a hardcode on `2026-07-26` **survived**, simply
 because my populations live on the 10th and 11th. *Enumerating shrinks the surface where a
 constant can hide; it never removes it — there is always a date I haven't written.*

 **The property that CLOSES the class isn't a list, it's an INVARIANCE**: the same series,
 **translated** in time, must return **the same drop** — same amplitude, same rank — and
 only its dates change. A date constant breaks the invariance as soon as it lands on ONE of
 the translations, and there are as many of those as you want.
 """
    def serie_a(depart: str, suivant: str):
        return _tours(
            {
                depart: [("produit/a.py", set())] * 6 + [("outillage/x.py", set())] * 4,
                suivant: [("produit/b.py", set())] * 2 + [("outillage/y.py", set())] * 8,
            }
        )

    reference = plus_grande_chute(part_produit(serie_a("2026-03-04", "2026-03-05"), EST_PRODUIT))
    assert reference is not None and abs(reference.ampleur - 0.40) < 1e-9

    for depart, suivant in (
        ("2026-07-20", "2026-07-21"),   # the real window
        ("2026-07-25", "2026-07-26"),   # the exact day of the hardcode that survived
        ("2027-01-01", "2027-01-02"),   # a year nothing names
        ("2019-11-30", "2019-12-01"),   # straddling two months, in the past
    ):
        chute = plus_grande_chute(part_produit(serie_a(depart, suivant), EST_PRODUIT))
        assert chute is not None, f"the same series must drop on {depart} too"
        assert abs(chute.ampleur - reference.ampleur) < 1e-9, (
            f"the amplitude MUST be invariant under translation: {chute.ampleur} on {depart} "
            f"against {reference.ampleur} as reference — a date constant lives in the code"
        )
        assert (chute.depuis, chute.vers) == (depart, suivant)


def test_la_bascule_SUIT_meme_DANS_la_fenetre_REELLE_et_a_faible_AMPLEUR():
    """ **THE WITNESS THAT REFUTES `c2` — three LIVE hardcodes passed both clauses.**

 An isolated audit drew 33 sabotages, 15 survivors, of which **three** keep a date or a
 threshold alive in the code AND pass `c1` and `c2`:

 * `key=(c.vers == "2026-07-21", c.ampleur)` — the DATE in the sort key;
 * `if tour.date == "2026-07-21": produit = 0` — the date that fabricates the answer;
 * `ampleur > 0.25` — a THRESHOLD in a return guard.

 **THE CAUSE ISN'T THE CODE, IT'S MY WITNESS POPULATION.** My fixtures lived in
 `2026-01-xx` and `2026-09-xx`, with a largest drop of **0.60**. A date pinned to July was
 **invisible** to them, and so was any threshold under 0.60. *A witness whose population
 doesn't COVER the real one cannot see a hardcode calibrated on the real one — it measures a
 region where the defect doesn't exist.*

 This fixture covers exactly the zone where a hardcode would hide:
 * it lives **in July**, and contains BOTH `2026-07-20` AND `2026-07-21`;
 * the true largest drop is **elsewhere** (`07-24 -> 07-25`), so a date pinned to the 21st
 returns a FALSE answer;
 * its amplitude is **0.10**, so any plausible threshold makes it disappear.

 **And I got that number WRONG on the first try**: I had written "0.20" for a drop that
 was actually **0.30**, and the `ampleur > 0.25` sabotage **survived**. *A fixture whose
 amplitude is ANNOUNCED without being DRAWN lets through exactly the threshold it claims to
 catch* — so the amplitude is asserted below, not just described.
 """
    tours = _tours(
        {
            "2026-07-20": [("produit/a.py", set()), ("outillage/x.py", set())],   # 1/2 = 0.50
            "2026-07-21": [("produit/b.py", set()), ("outillage/y.py", set())],   # 1/2 = 0.50
            "2026-07-24": [("produit/c.py", set()), ("produit/d.py", set()),
                           ("outillage/z.py", set()), ("outillage/w.py", set())],  # 2/4 = 0.50
            "2026-07-25": [("produit/e.py", set()), ("produit/f.py", set()),
                           ("produit/g.py", set()), ("produit/h.py", set()),
                           ("outillage/v.py", set()), ("outillage/u.py", set()),
                           ("outillage/t.py", set()), ("outillage/s.py", set()),
                           ("outillage/r.py", set()), ("outillage/q.py", set())],  # 4/10 = 0.40
        }
    )
    serie = part_produit(tours, EST_PRODUIT)
    chute = plus_grande_chute(serie)
    assert chute is not None, "a drop exists in this series — otherwise the witness measures nothing"
    assert (chute.depuis, chute.vers) == ("2026-07-24", "2026-07-25"), (
        f"the drop lives at 24->25, NOT 20->21; a hardcoded date would return something else: {chute}"
    )
    assert abs(chute.ampleur - 0.10) < 1e-9, (
        f"the amplitude is DRAWN, not described: {chute.ampleur:.4f} instead of 0.10 — "
        "a fixture whose amplitude is announced without being measured lets the threshold through"
    )
    assert chute.ampleur < 0.25, "and it MUST stay under every plausible threshold"


def test_la_SERIE_declare_son_UNITE_sinon_la_page_publie_TROIS_chiffres():
    """ **Found by pulling up my own page after the audit**: it was publishing **three figures
 for a single question**, without saying which one answers what.

 ## (a) The product share — 100.0% … <- counted in COMMITS, not stated
 share in LINES 50.0% · in FILES 50.0%

 *All three are CORRECT; it's their SILENT PROXIMITY that lies* — and the first one, the
 biggest, is the one the reader will remember. It's "a correct figure in the wrong unit reads
 as its opposite," one level up: here the unit isn't wrong, it's **absent**.

 The witness requires that **changing the unit changes what the page ANNOUNCES**, not just
 what it computes — or the label could be hardcoded and stay green."""
    from mnemosyne.production.plan_derive import PAR_LIGNE

    tours = [
        Tour("a", "2026-07-20", ("produit/x.py", "o/y.py"), frozenset(), (90, 10)),
        Tour("b", "2026-07-21", ("produit/z.py", "o/w.py"), frozenset(), (10, 90)),
    ]
    def en_tete(page: str) -> str:
        return next(ln for ln in page.splitlines() if ln.startswith("## (a)"))

    par_commit = en_tete(rendre(lire(tours, EST_PRODUIT)))
    par_ligne = en_tete(rendre(lire(tours, EST_PRODUIT, unite=PAR_LIGNE)))
    assert "COMMIT" in par_commit, f"the header must NAME its unit: {par_commit!r}"
    assert "LIGNE" in par_ligne, f"and follow it when it changes: {par_ligne!r}"
    assert par_commit != par_ligne, "the two pages MUST differ — or the label is dead"
    assert "100.0%" in par_commit and "50.0%" in par_ligne, (
        "and the figure must follow the unit, not just the label"
    )


def test_la_PAGE_dit_la_CHUTE_quand_il_y_en_a_une_et_le_SILENCE_quand_il_n_y_en_a_pas():
    """ **Found by an isolated audit: `if False and d.chute:` left 21 witnesses GREEN.** The
 page then printed *"No drop: the product share never decreases"* on a series that falls
 from **100% to 0%** — a FALSE claim on the surface the operator reads, for a level-1 item
 whose `*Produit*` is precisely to PUBLISH.

 **No witness read the PAGE's `LARGEST DROP` line**: they all asserted on the
 `Derive.chute` object. *Third time today I test the computation and never its rendering* —
 this time a third party found it, not me.

 **The witness draws BOTH directions**: the present drop MUST print, and a **flat** series
 must NOT produce a drop line. A witness that only arms one direction would let the other
 through — a `>` boundary is only guarded on the side you draw."""
    qui_chute = _tours(
        {
            "2026-04-01": [("produit/a.py", set()), ("produit/b.py", set())],
            "2026-04-02": [("outillage/x.py", set()), ("outillage/y.py", set())],
        }
    )
    page = rendre(lire(qui_chute, EST_PRODUIT))
    assert "LARGEST DROP" in page, f"a drop from 100% to 0% MUST print:\n{page}"
    assert "2026-04-01" in page and "2026-04-02" in page, "with both its dates"
    assert "never decreases" not in page, "and especially NOT the opposite claim"

    plate = _tours(
        {
            "2026-04-01": [("produit/a.py", set()), ("outillage/x.py", set())],
            "2026-04-02": [("produit/b.py", set()), ("outillage/y.py", set())],
        }
    )
    page_plate = rendre(lire(plate, EST_PRODUIT))
    assert "LARGEST DROP" not in page_plate, (
        f"a FLAT series doesn't drop — the line must not exist:\n{page_plate}"
    )


def test_l_ORDRE_des_jours_ne_depend_pas_de_l_ordre_d_ARRIVEE_des_tours():
    """ Found by the same audit: removing `sorted()` left the suite green, because **no
 witness feeds it a disordered population**. But `git log` outputs in **REVERSE
 CHRONOLOGICAL** order (measured by the third party: 1st tour = July 29th) — so the real
 edge delivers exactly the shape nobody was testing. *A sort that guards against an input no
 witness ever produces guards nothing: it waits.*"""
    croissant = [
        Tour("a", "2026-06-01", ("produit/a.py",), frozenset()),
        Tour("b", "2026-06-02", ("outillage/x.py",), frozenset()),
    ]
    decroissant = list(reversed(croissant))
    chute_c = plus_grande_chute(part_produit(croissant, EST_PRODUIT))
    chute_d = plus_grande_chute(part_produit(decroissant, EST_PRODUIT))
    assert chute_c is not None and chute_d is not None
    assert (chute_c.depuis, chute_c.vers) == ("2026-06-01", "2026-06-02")
    assert (chute_d.depuis, chute_d.vers) == (chute_c.depuis, chute_c.vers), (
        "the ARRIVAL order of the tours must change nothing — `git log` returns them backwards"
    )
    assert abs(chute_d.ampleur - chute_c.ampleur) < 1e-9


def test_les_DEUX_unites_sont_PUBLIEES_avec_leur_ECART_nomme():
    """ **THE 2026-08-15 AMENDMENT, and it ADDS a requirement.** The clause required
 reproducing a figure the project had published **in LINES** with a unit that counts
 **FILES**. Keeping the proxy made the item *pass*; the orchestrator didn't do that —
 *an amendment that turns the item it amends green is a permission, not a decision.*

 **THE PARADOX NAMED THE FAULT**: the proxy reproduced it to **0.2 points** where the true
 unit diverges by **3-4 points**. *A proxy that beats the true unit is not luck — it's the
 signature of a unit chosen BECAUSE it reproduced.* The reference must never derive from what
 it verifies. We no longer CHOOSE: we publish both and NAME the gap."""
    from mnemosyne.production.plan_derive import ecart_des_unites

    tours = [
        Tour("a", "2026-07-20", ("produit/x.py", "outillage/y.py"), frozenset(), (90, 10)),
    ]
    p_lignes, p_fichiers, phrase = ecart_des_unites(tours, EST_PRODUIT)
    assert p_lignes == 0.90 and p_fichiers == 0.50, (
        f"the two units MUST diverge on this population: {p_lignes} / {p_fichiers}"
    )
    assert "40.0 point" in phrase, (
        f"the gap is published IN POINTS, not as a fraction — a raw `abs(0.90-0.50)` would print "
        f"\"0.4 point\" for FORTY: {phrase!r}"
    )
    # The old assertion required the sentence "published, never chosen." A third party
    # measured it: it SURVIVES three live sabotages — a page can carry it while having chosen
    # its figure. *A PRINTED proof is a string of characters.* So we assert on the two REAL
    # terms instead.
    assert "in LINES" in phrase and "in FILES" in phrase, (
        f"the gap must NAME its two terms, or the reader has no idea from what to what: {phrase!r}"
    )


def test_le_filtre_j_total_est_VIVANT_sous_PAR_FICHIER_et_je_l_avais_declare_MORT():
    """ **A DEATH ADMISSION copied from one version to the next.**

 :func:`plus_grande_chute`'s docstring claimed that the ``j.total`` filter never skipped a
 single day — on the strength of an isolated audit whose sabotage survived. That was true
 **back when the module had only one unit**. Under `PAR_FICHIER`, a commit that touches
 **no** file at all returns ``total == 0``; without the filter, the series would show
 **90% → 0% → 90%**, a collapse invented by a division by nothing.

 *A borrowed verdict expires in silence* — and it's the work that **added the units** that
 aged it out. A death admission gets **re-measured** as soon as the population changes, it
 doesn't get copied.
 """
    plein = ("produit/a.py", "o/x.py") * 5
    tours = [
        Tour("a", "2026-07-20", plein),
        Tour("vide", "2026-07-21", ()),  # merge commit: no file at all
        Tour("b", "2026-07-22", plein),
    ]
    jours = part_produit(tours, EST_PRODUIT, unite=PAR_FICHIER)
    assert any(j.total == 0 for j in jours), (
        "the guard is UNREACHABLE on this fixture — this witness no longer measures anything"
    )
    assert plus_grande_chute(jours) is None, (
        "the day at total ZERO fabricates a 90% → 0% drop: the j.total guard was skipped"
    )


def test_l_ECART_se_prend_sur_la_POPULATION_COMMUNE_jamais_sur_deux():
    """ **THE GAP WAS SUBTRACTING TWO DIFFERENT POPULATIONS.**

 `p_fichiers` covered **all** the tours, `p_lignes` only the tours carrying lines. Their
 difference therefore mixed the gap between **units** — the only thing the clause asks for —
 with the gap between **populations**. And the caveat, which DID *name* the population
 difference, prevented nothing: *naming a hole doesn't plug it.*

 Here, the tours without lines are all **product**: the share in FILES is therefore much
 higher over the whole window than over the common population. A gap taken between the two
 would be **fabricated out of thin air**. *"Before" and "after" must be THE SAME
 measurement.*"""
    communs = [
        Tour(f"c{i}", "2026-07-20", ("produit/a.py", "o/x.py"), None, (10, 10)) for i in range(5)
    ]
    sans_lignes = [Tour(f"s{i}", "2026-07-20", ("produit/a.py",), None, ()) for i in range(15)]
    p_lignes, p_fichiers, phrase = ecart_des_unites(communs + sans_lignes, EST_PRODUIT)
    assert p_lignes is not None and p_fichiers is not None
    assert abs(p_lignes - 0.50) < 0.001, f"over the COMMON set, lines = 50%: {p_lignes}"
    assert abs(p_fichiers - 0.80) < 0.001, f"over the WHOLE window, files = 80%: {p_fichiers}"
    assert "GAP 0.0 point" in phrase, (
        "over the COMMON population both units are 50%: the TRUE gap is zero. "
        f"A gap taken against the whole window's 80% would fabricate 30 points: {phrase!r}"
    )
    assert "COMMON population" in phrase and "5/20" in phrase, (
        f"the page must say WHICH population the gap is taken over: {phrase!r}"
    )


def test_la_PAGE_PUBLIE_les_deux_unites_pas_seulement_la_fonction():
    """ **THE BARRIER THAT NOTHING CALLS, committed ONE HOUR after writing it down.**

 The amended clause says *"**PUBLISH** its share in BOTH units … with their GAP named."*
 My first delivery wrote `ecart_des_unites` — correct, tested, and **called by nothing
 except its own witnesses**. `grep -rn ecart_des_unites system/lib` returned **a single
 line: its own definition.**

 *The clause's verb is **publish**: a correct function that no output prints doesn't
 publish anything.* So this witness reads **the page**, not the object — that's the class
 this repo has already made me pay for twice today, on another module."""
    tours = [
        Tour("a", "2026-07-20", ("produit/x.py", "outillage/y.py"), frozenset(), (90, 10)),
        Tour("b", "2026-07-21", ("produit/z.py", "outillage/w.py"), frozenset(), (10, 90)),
    ]
    page = rendre(lire(tours, EST_PRODUIT))
    ligne = next((ln for ln in page.splitlines() if "LINES" in ln and "FILES" in ln), None)
    assert ligne is not None, f"the PAGE must carry both units; it returns:\n{page}"
    assert "GAP" in ligne and "point(s)" in ligne, f"and their NAMED gap: {ligne!r}"


def test_les_lignes_ABSENTES_font_REFUSER_l_unite_au_lieu_d_inventer_un_zero():
    """ *"Not measurable" and "no gap" don't read the same.* A tour with no line data isn't a
 tour at zero lines: returning `(0, 0)` would make it a day at `total == 0`, which
 `part_produit` DROPS — the series would lose days **silently**, on the very surface where
 the clause demands a figure."""
    from mnemosyne.production.plan_derive import PAR_LIGNE, ecart_des_unites

    sans = [Tour("b", "2026-07-20", ("produit/x.py",), frozenset())]
    try:
        PAR_LIGNE(sans[0], EST_PRODUIT)
    except ValueError as erreur:
        assert "cannot measure" in str(erreur)
    else:  # pragma: no cover - the test fails before this
        raise AssertionError("PAR_LIGNE must REFUSE a tour without lines, not return a zero")

    p_lignes, p_fichiers, phrase = ecart_des_unites(sans, EST_PRODUIT)
    assert p_lignes is None, "the share in lines is UNKNOWN, not zero"
    assert p_fichiers == 1.0, "and the other unit stays measurable — the refusal doesn't kill the batch"
    assert "NOT MEASURABLE" in phrase


def test_UN_tour_sans_lignes_ne_tue_pas_les_QUATRE_VINGT_DIX_NEUF_autres():
    """ **Item outside the 2nd audit's clause, reproduced: the refusal was PER TOUR, the loss
 was PER BATCH.** Measured: **ONE** tour without lines out of **100** made `part_produit`
 raise, so the **99** measurable ones were thrown away and the share in lines became "NOT
 MEASURABLE" **entirely**.

 `PAR_LIGNE` is right to refuse a tour it cannot measure — *an invented zero would be
 worse*. The defect was letting that refusal bubble up all the way to the page: *a per-item
 guarantee that raises kills the batch.*

 **And the published share NAMES its population**: 99 out of 100 is not 100. Without that
 count, the figure would lie by omission — *an excluded population is a population NOT
 JUDGED.*"""
    tours = [
        Tour(f"{i}", "2026-07-20", ("produit/a.py", "o/x.py"), frozenset(), (9, 1)) for i in range(99)
    ]
    tours.append(Tour("sans", "2026-07-21", ("produit/b.py",), frozenset()))
    from mnemosyne.production.plan_derive import ecart_des_unites

    p_lignes, p_fichiers, phrase = ecart_des_unites(tours, EST_PRODUIT)
    assert p_lignes is not None, "the 99 measurable tours MUST be measured"
    assert abs(p_lignes - 0.90) < 1e-9, f"9 lines out of 10 go to product: {p_lignes}"
    assert "99/100" in phrase, f"and the EXCLUDED population must be named: {phrase!r}"
    assert "1 without written lines" in phrase


def test_AUCUN_tour_mesurable_refuse_encore_et_NE_ment_pas():
    """The counterpart: when **nothing** is measurable, we don't publish a share over zero
    tours. *"not measurable" and "no gap" don't read the same* — and that sentence must survive
    the fix next door."""
    from mnemosyne.production.plan_derive import ecart_des_unites

    p_lignes, p_fichiers, phrase = ecart_des_unites(
        [Tour("s", "2026-07-20", ("produit/a.py",), frozenset())], EST_PRODUIT
    )
    assert p_lignes is None and "NOT MEASURABLE" in phrase
    assert p_fichiers == 1.0, "and the other unit stays measurable — the refusal doesn't kill the batch"


def test_AUCUNE_CHUTE_nomme_son_UNITE_car_une_autre_unite_peut_s_effondrer():
    """ **Last item outside the clause, and it's the most serious of the three.** The page
 claimed *"the product share NEVER decreases from one day to the next"* — a **categorical**
 sentence.

 Measured on **the same tours**: in COMMITS there is no drop at all; **in LINES the share
 falls from 90% to 10%**. An 80-point collapse, published as stability.

 *A sentence without its unit reads as universal* — and between two possible readings,
 it's the more reassuring one the reader will remember. **The word "never" is what makes the
 fault expensive.**

 The witness requires BOTH: that the sentence names its unit, and that the other unit
 does show the drop — otherwise it would be asserting on a population where the two units
 agree, and would measure nothing."""
    from mnemosyne.production.plan_derive import PAR_LIGNE

    tours = [
        Tour.depuis_paires("a", "2026-07-20", [("produit/x.py", 90), ("o/y.py", 10)]),
        Tour.depuis_paires("b", "2026-07-21", [("produit/z.py", 10), ("o/w.py", 90)]),
    ]
    en_commits = rendre(lire(tours, EST_PRODUIT))
    assert "No drop IN COMMIT" in en_commits, f"the sentence must NAME its unit:\n{en_commits}"
    assert "ANOTHER unit can drop" in en_commits, "and warn that the other one can collapse"

    en_lignes = rendre(lire(tours, EST_PRODUIT, unite=PAR_LIGNE))
    assert "LARGEST DROP" in en_lignes, (
        "and on THESE SAME tours the other unit MUST drop — or the witness measures nothing"
    )
    assert "90.0% → 10.0%" in en_lignes, f"an 80-point drop: {en_lignes}"
    assert "in LIGNE" in en_lignes, "the drop also names its unit"


def test_la_PERMUTATION_est_INDETECTABLE_et_la_construction_par_PAIRES_l_empeche():
    """ **Item outside the 2nd audit's clause — and it's as much an ADMISSION as a fix.**

 Two tours with the **same paths**, one of which has its lines **permuted**, return
 `(90, 100)` and `(10, 100)`: **no refusal, two plausible counts**. The guard compares
 LENGTHS — it catches truncation, **never the swap**. *No after-the-fact check can
 distinguish a correct alignment from a wrong one when both have the same shape.*

 **So we don't verify: we make the error UNCONSTRUCTABLE.** `Tour.depuis_paires` gives
 birth to both tuples from a single source, in one gesture — the exact shape of `git log
 --numstat`.

 **What this witness DOESN'T BUY, and it says so**: the direct constructor stays open, a
 frozen dataclass can't forbid its own `__init__`. *It's a safe convenience, not a barrier*
 — what's gained is that the safe path is also the shortest one."""
    from mnemosyne.production.plan_derive import PAR_LIGNE

    # 1 · the permutation EXISTS and turns red nowhere — that's the measurement, not a fear
    bon = Tour("a", "2026-07-20", ("produit/x.py", "o/y.py"), frozenset(), (90, 10))
    permute = Tour("a", "2026-07-20", ("produit/x.py", "o/y.py"), frozenset(), (10, 90))
    assert PAR_LIGNE(bon, EST_PRODUIT) == (90, 100)
    assert PAR_LIGNE(permute, EST_PRODUIT) == (10, 100), (
        "the permutation MUST pass without a refusal — if it turned red, this witness would be "
        "measuring something else"
    )

    # 2 · the safe path cannot produce it: a single source for both tuples
    par_paires = Tour.depuis_paires("a", "2026-07-20", [("produit/x.py", 90), ("o/y.py", 10)])
    assert par_paires.chemins == bon.chemins and par_paires.lignes == bon.lignes
    assert PAR_LIGNE(par_paires, EST_PRODUIT) == (90, 100)
    # and the pair order stays whatever is given — no hidden sort re-associates it
    inverse = Tour.depuis_paires("a", "2026-07-20", [("o/y.py", 10), ("produit/x.py", 90)])
    assert PAR_LIGNE(inverse, EST_PRODUIT) == (90, 100), "the pair travels TOGETHER, regardless of order"


def test_un_DESALIGNEMENT_lignes_chemins_est_REFUSE():
    """ `lignes` is ALIGNED with `chemins`: same length, same order. A misalignment would
 attribute one file's lines to another — and the count would stay **plausible**."""
    from mnemosyne.production.plan_derive import PAR_LIGNE

    faux = Tour("c", "2026-07-20", ("produit/x.py", "outillage/y.py"), frozenset(), (90,))
    try:
        PAR_LIGNE(faux, EST_PRODUIT)
    except ValueError as erreur:
        assert "1 line count(s) for 2 path(s)" in str(erreur)
    else:  # pragma: no cover
        raise AssertionError("a misalignment must be REFUSED, not silently truncated")


def test_l_unite_PAR_FICHIER_que_la_clause_NOMME_a_enfin_un_temoin():
    """ **COVERAGE HOLE found by the audit**: `PAR_FICHIER` appeared **0 times** in this file
 — the unit `(c1)` NAMES was proven by nothing. Neutralizing `PAR_FICHIER` left the suite
 green.

 The witness tests **DIFFERENTIATION**: the two units must return DIFFERENT series over
 the same population, or it would pass with either one."""
    from mnemosyne.production.plan_derive import PAR_COMMIT, PAR_FICHIER

    tours = [
        # a commit that touches ONE product file; another that touches THREE non-product ones
        Tour(sha="a", date="2026-07-20", chemins=("produit/a.py",), faits=frozenset()),
        Tour(sha="b", date="2026-07-20", chemins=("o/x.py", "o/y.py", "o/z.py"), faits=frozenset()),
    ]
    par_commit = part_produit(tours, EST_PRODUIT, unite=PAR_COMMIT)
    par_fichier = part_produit(tours, EST_PRODUIT, unite=PAR_FICHIER)
    assert par_commit[0].part == 0.5, f"1 commit out of 2 touches product: {par_commit}"
    assert par_fichier[0].part == 0.25, f"1 file out of 4 touches product: {par_fichier}"
    assert par_commit[0].part != par_fichier[0].part, (
        "the two units MUST differ on this population — or the witness measures nothing"
    )


def _jour(date: str, produit: int, total: int) -> list[Tour]:
    """`total` tours that day, of which `produit` touch the product — to draw a SERIES."""
    return [
        Tour(f"{date}-{n}", date, ("produit/x.py",) if n < produit else ("outillage/y.py",))
        for n in range(total)
    ]


def test_la_plus_grande_chute_ne_coincide_avec_AUCUNE_regle_plus_SIMPLE():
    """ THE MISSING WITNESS, and its FIRST version wasn't enough either.

 An isolated audit measured that **12 sabotages out of 23 survived** my eleven witnesses,
 including three literally carrying a **threshold** (`< 0.5`, `< 0.25`, `ampleur >= 0.9`).
 Cause: my two fixtures placed the drop on the **last transition**, so moving the turning
 point changed the dates and never the POSITION.
 **My first fix only killed one sabotage out of six**: its largest drop was ALSO the
 first one, ALSO the one leading to the minimum, and its amplitude exceeded every threshold.
 *A witness that makes the right answer coincide with five wrong rules refutes none of them.*

 This series is built so the largest drop coincides with NOTHING:

 ====== ====== =====================================================================
 day share what a simpler rule would pick
 ====== ====== =====================================================================
 01 60%
 02 40% ← the FIRST drop · the FIRST crossing below 0.5
 03 90% (rebound)
 04 30% ← **THE LARGEST (0.60)** — amplitude < 0.9, and not toward the minimum
 05 10% ← the MINIMUM · the first crossing below 0.25
 06 20% (rebound: the LAST transition is not a drop)
 ====== ====== =====================================================================
 """
    tours = (
        _jour("2026-01-01", 3, 5)
        + _jour("2026-01-02", 2, 5)
        + _jour("2026-01-03", 9, 10)
        + _jour("2026-01-04", 3, 10)
        + _jour("2026-01-05", 1, 10)
        + _jour("2026-01-06", 2, 10)
    )
    chute = plus_grande_chute(part_produit(tours, EST_PRODUIT))
    assert (chute.depuis, chute.vers) == ("2026-01-03", "2026-01-04"), (
        "the largest drop must be computed, not guessed from a position or a threshold"
    )
    assert abs(chute.ampleur - 0.60) < 1e-9


def test_une_serie_SANS_chute_le_dit_au_lieu_d_inventer():
    """If nothing decreases, the detector must return NOTHING — not the least-bad of the rises."""
    tours = _tours({"2026-01-01": [("outillage/x.py", set())], "2026-01-02": [("produit/a.py", set())]})
    assert plus_grande_chute(part_produit(tours, EST_PRODUIT)) is None


def test_UN_SEUL_chemin_produit_suffit_a_faire_compter_le_commit():
    """ The "AT LEAST ONE path" rule decides the published figure, and nothing armed it: all
 my fixtures fabricated commits with **exactly one** path. Degenerate population — a module
 that required ALL paths to be product would pass every witness."""
    tour = Tour("s1", "2026-01-01", ("outillage/a.py", "outillage/b.py", "produit/c.py"))
    assert part_produit([tour], EST_PRODUIT)[0].part == 1.0, "a single product path is enough"


def test_un_commit_SANS_AUCUN_chemin_compte_au_total_et_pas_au_produit():
    """Documented at line 130 and never drawn: an empty merge moved nothing forward."""
    jour = part_produit([Tour("s1", "2026-01-01", ())], EST_PRODUIT)[0]
    assert (jour.produit, jour.total) == (0, 1)


def test_la_classification_est_INJECTEE_pas_ecrite_dans_le_module():
    """Same corpus, two product definitions, two results — that's what D2 will make declared."""
    tours = _tours({"2026-01-01": [("produit/a.py", set())], "2026-01-02": [("outillage/x.py", set())]})
    assert part_produit(tours, EST_PRODUIT)[0].part == 1.0
    assert part_produit(tours, lambda c: c.startswith("outillage/"))[0].part == 0.0


# --------------------------------------------------------------------------------------------
# (b) THE IMMOBILE COUNTER — the SET, never the count
# --------------------------------------------------------------------------------------------


def test_un_ECHANGE_est_NOMME_la_ou_un_COMPTE_serait_reste_muet():
    """ THE WITNESS THAT DECIDES. One item closes, another reopens: the cardinal doesn't move.

 That's exactly what the sibling project paid for — *"the set of `` was IDENTICAL after 299 commits"* —
 and a module that counted instead of comparing would let this case through green.
 """
    tours = [
        Tour("s1", "2026-01-01", ("x",), frozenset({"A1", "A2"})),
        Tour("s2", "2026-01-01", ("x",), frozenset({"A1", "A3"})),  # A2 leaves, A3 enters: 2 -> 2
    ]
    immo, echanges = immobilite(tours)
    assert echanges == ("s2",), "the swap must be NAMED"
    assert immo.commits == 1, "and the immobility stops there, since the SET has moved"


def test_la_plus_longue_IMMOBILITE_est_celle_qu_on_rend():
    tours = [
        Tour("s1", "2026-01-01", ("x",), frozenset({"A1"})),
        Tour("s2", "2026-01-01", ("x",), frozenset({"A1"})),
        Tour("s3", "2026-01-01", ("x",), frozenset({"A1", "A2"})),
        Tour("s4", "2026-01-01", ("x",), frozenset({"A1", "A2"})),
        Tour("s5", "2026-01-01", ("x",), frozenset({"A1", "A2"})),
        Tour("s6", "2026-01-01", ("x",), frozenset({"A1", "A2"})),
    ]
    immo, echanges = immobilite(tours)
    assert (immo.commits, immo.depuis, immo.jusqua) == (4, "s3", "s6")
    assert echanges == (), "no swap: the cardinals changed along with the sets"


def test_une_fenetre_VIDE_ne_rend_pas_une_immobilite_parfaite():
    """"Nothing measured" and "nothing moves" must never read the same."""
    assert immobilite([]) == (None, ())


# --------------------------------------------------------------------------------------------
# BOTH TOGETHER — because neither one is worth anything alone
# --------------------------------------------------------------------------------------------


def test_produire_BEAUCOUP_sur_UNE_seule_etape_laisse_a_vert_et_b_rouge():
    """The case (a) alone would declare healthy: 100% product, and the plan hasn't moved by one item."""
    tours = [Tour(f"s{i}", "2026-01-01", ("produit/a.py",), frozenset({"A1"})) for i in range(12)]
    d = lire(tours, EST_PRODUIT)
    assert d.part_globale == 1.0, "(a) is green"
    assert d.immobilite.commits == 12, "(b) screams: twelve tours, not one item more"


def test_fermer_des_etapes_de_MACHINERIE_fait_l_inverse():
    """The symmetric case, that (b) alone would declare healthy: the plan moves, the product doesn't."""
    tours = [
        Tour(f"s{i}", "2026-01-01", ("outillage/x.py",), frozenset({f"O{j}" for j in range(i + 1)}))
        for i in range(6)
    ]
    d = lire(tours, EST_PRODUIT)
    assert d.part_globale == 0.0, "(a) screams: nothing goes to product"
    assert d.immobilite.commits == 1, "(b) is green: the set moves on every tour"


def test_UN_SEUL_JOUR_ne_permet_AUCUNE_comparaison_et_la_page_le_DIT():
    """ The page claimed "the product share never decreases" on a population where **no
 comparison was possible** — a claim about the world drawn from a void. The module honors
 the rule on side (b) ("No measurement") and was violating it ten lines above."""
    rendu = rendre(lire(_tours({"2026-01-01": [("produit/a.py", {"A1"})]}), EST_PRODUIT))
    assert "never decreases" not in rendu, "a single day proves no absence of decrease"
    assert "a single day" in rendu or "No comparison" in rendu


def test_la_page_publie_les_DEUX_et_ne_refuse_RIEN():
    """D1 is level 1: it NAMES. What refuses is D3, and only D3."""
    rendu = rendre(lire(_tours({"2026-01-01": [("produit/a.py", {"A1"})],
                                "2026-01-02": [("produit/b.py", {"A1"})]}), EST_PRODUIT))
    assert "(a) The product share" in rendu and "(b) The immobile counter" in rendu
    assert "BOTH ARE READ TOGETHER" in rendu
    assert "REFUSED" not in rendu


def test_une_fenetre_VIDE_REFUSE_au_lieu_de_publier_zero():
    """*A judge that finds its population empty and returns a green* — here green would say
    "no drift"."""
    assert "REFUSED" in rendre(lire([], EST_PRODUIT))


# ------------------------------------------------------------------------------------------------
# D2 — `lire_produit`: the PURE reader of a `produit:` declaration, tested HERE in ISOLATION
# ------------------------------------------------------------------------------------------------
# COVERAGE HOLE FOUND BY AN ISOLATED AUDIT (D75): this function had NO direct witness — its
# only coverage was indirect, via `derive_run.predicat_produit`. Its sisters
# (`lire`, `part_produit`, `plus_grande_chute`, `immobilite`, `ecart_des_unites`) all have a
# witness HERE; `lire_produit` had none. *The most central function of the mechanism was also
# the only one not tested at its own level.*


def test_lire_produit_rend_un_motif_par_ligne():
    assert lire_produit("- produit/\n- core/\n- engine/\n") == ("produit/", "core/", "engine/")


def test_lire_produit_TOLERE_les_backticks_comme_lire_peremption():
    """Same tolerance as `carte._PEREMPTION` — claimed in the docstring, never proven."""
    assert lire_produit("- `produit/`\n-   `core/`  \n- engine/\n") == ("produit/", "core/", "engine/")


def test_lire_produit_rend_un_tuple_VIDE_sur_un_texte_sans_motif():
    """ EMPTY is not ABSENT: it's up to the edge (`derive_run.predicat_produit`) to
 distinguish "file absent" from "file read, zero patterns" — this function never sees the
 absence."""
    assert lire_produit("") == ()
    assert lire_produit("just some prose, no bullet here\n") == ()


def test_lire_produit_IGNORE_un_exemple_dans_un_BLOC_CLOS():
    """ The trap `lire_peremption` already paid for: a pedagogical example inside
 documentation must NOT become a declaration. A pattern trapped inside a
 ```` ``` ```` block must never leak out, only patterns OUTSIDE a block count."""
    texte = (
        "- produit/\n"
        "\n"
        "Example declaration:\n"
        "```markdown\n"
        "- engine/\n"
        "- pieges/\n"
        "```\n"
        "\n"
        "- core/\n"
    )
    assert lire_produit(texte) == ("produit/", "core/"), "the pattern INSIDE the closed block must not leak"
