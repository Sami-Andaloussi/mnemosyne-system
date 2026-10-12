"""The Conseiller - REAL, hardcoded, verifiable decision models.

The user, word for word, what he refuses: *« pas juste, oh, des prises de décision, je parle avec un
modèle, et puis le modèle invente un truc de sa tête […] je veux des vrais concepts psychologiques
ou méthodologiques […] qu'on va tester. Donc il faut juste que ça soit hard codé et que ça soit
vraiment quelque chose de réel. »*

So this module contains NO prompt to a model at all: only calculation and fixed structures,
sourced, borrowed from decision theory and published methods - never invented here. Two families:

- **Mathematical** (:func:`matrice_ponderee`, :func:`decision_incertitude`) - a calculation that
  ALWAYS gives the same result for the same numbers. The Conseiller's model FILLS IN the numbers
  from the conversation; it never invents them itself on the way out.
- **Methodological/psychological** (:func:`cadre_wrap`, :func:`cadre_premortem`,
  :func:`cadre_10_10_10`, :func:`matrice_eisenhower`) - published frameworks whose STEPS are
  fixed. A small model that "does WRAP" from memory forgets half of it or invents a fifth
  one; here, the questions are written once, for good.

No function raises on a malformed input (a JSON badly filled in by a local model remains the
norm, not the exception): an option with no name, a negative weight, a missing note are ignored or
counted as zero rather than failing the whole calculation. Tested brick-free - pure, no I/O.
"""

from __future__ import annotations

from typing import Any

# -- A. THE WEIGHTED MATRIX (Weighted Sum Model - the most widely taught model in multi-criteria analysis) --------


def matrice_ponderee(
    options: list[Any] | None,
    criteres: list[Any] | None,
    notes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Each option gets a note per criterion, each criterion carries a weight, the score is the
    weighted sum - and nothing else. It is the oldest model in multi-criteria analysis
    (Churchman & Ackoff, 1954), still the most used.

    ``criteres`` - objects ``{"nom": ..., "poids": <number>}``. The weights do NOT need to
    sum to 1: they are normalized here, because the user dictates RELATIVE weights ("salary
    counts double the vibe") rather than a budget calibrated in advance.

    ``notes`` - ``{option: {criterion: note}}``. A missing or unreadable note counts as 0 rather
    than failing the whole calculation for one hole in the grid - an incomplete grid stays
    more useful than no result at all."""
    options_propres = [str(o).strip() for o in (options or []) if str(o).strip()]
    criteres_propres: list[tuple[str, float]] = []
    for c in criteres or []:
        if not isinstance(c, dict):
            continue
        nom = str(c.get("nom", "")).strip()
        try:
            poids = float(c.get("poids", 0))
        except (TypeError, ValueError):
            poids = 0.0
        if nom and poids > 0:
            criteres_propres.append((nom, poids))
    poids_total = sum(p for _, p in criteres_propres)
    if not options_propres or not criteres_propres or poids_total <= 0:
        return {
            "modele": "matrice_ponderee",
            "options": [],
            "gagnant": "",
            "erreur": "options, criteria or weights missing",
        }
    notes = notes or {}
    resultats = []
    for option in options_propres:
        grille = notes.get(option)
        grille = grille if isinstance(grille, dict) else {}
        detail = []
        score = 0.0
        for nom, poids in criteres_propres:
            try:
                note = float(grille.get(nom, 0))
            except (TypeError, ValueError):
                note = 0.0
            part = poids / poids_total
            contribution = note * part
            score += contribution
            detail.append(
                {
                    "critere": nom,
                    "note": note,
                    "poids_relatif": round(part, 4),
                    "contribution": round(contribution, 4),
                }
            )
        resultats.append({"option": option, "score": round(score, 4), "detail": detail})
    resultats.sort(key=lambda r: -r["score"])
    return {
        "modele": "matrice_ponderee",
        "options": resultats,
        "gagnant": resultats[0]["option"] if resultats else "",
    }


# -- B. DECISION UNDER UNCERTAINTY (Wald, Savage, Laplace - classical decision theory) -------


def decision_incertitude(
    options: list[Any] | None,
    scenarios: list[Any] | None,
    valeurs: dict[str, Any] | None,
) -> dict[str, Any]:
    """When the outcome depends on an uncertain future, there is NO single right calculation: the
    choice of criterion IS already a stance (cautious, optimistic, indifferent, or regret-
    minimizing). This model renders all five side by side rather than imposing one - if they
    diverge, the divergence IS the information (a "safe" option and a "high-potential" option
    are not settled by a single number, they are settled by the question being asked).

    ``scenarios`` - objects ``{"nom": ..., "probabilite": <0..1, or absent>}``. The expectation
    (``esperance``) appears only if ALL probabilities are given - an expectation computed on
    half-invented probabilities would be worse than not having one.

    ``valeurs`` - ``{option: {scenario: value}}``. An empty cell counts as 0 (not as
    "missing"): a scenario the user named but did not quantify for this option stays in
    the calculation rather than silently disappearing, which would bias exactly the most
    favorable scenario they forgot to fill in."""
    options_propres = [str(o).strip() for o in (options or []) if str(o).strip()]
    scenarios_propres: list[tuple[str, float | None]] = []
    for s in scenarios or []:
        if not isinstance(s, dict):
            continue
        nom = str(s.get("nom", "")).strip()
        if not nom:
            continue
        prob = s.get("probabilite")
        try:
            prob_f = float(prob) if prob not in (None, "") else None
        except (TypeError, ValueError):
            prob_f = None
        scenarios_propres.append((nom, prob_f))
    if not options_propres or not scenarios_propres:
        return {
            "modele": "decision_incertitude",
            "options": [],
            "erreur": "options or scenarios missing",
        }

    valeurs = valeurs or {}

    def valeur(option: str, scenario: str) -> float:
        grille = valeurs.get(option)
        if not isinstance(grille, dict):
            return 0.0
        try:
            return float(grille.get(scenario, 0))
        except (TypeError, ValueError):
            return 0.0

    noms_scenarios = [n for n, _ in scenarios_propres]
    table = {opt: {sc: valeur(opt, sc) for sc in noms_scenarios} for opt in options_propres}
    meilleur_par_scenario = {
        sc: max(table[opt][sc] for opt in options_propres) for sc in noms_scenarios
    }

    probabilites_completes = all(p is not None for _, p in scenarios_propres)
    total_p = sum(p for _, p in scenarios_propres if p is not None) or 1.0

    resultats = []
    for opt in options_propres:
        vals = [table[opt][sc] for sc in noms_scenarios]
        regret_max = max(meilleur_par_scenario[sc] - table[opt][sc] for sc in noms_scenarios)
        ligne: dict[str, Any] = {
            "option": opt,
            "maximin_pessimiste": round(min(vals), 4),
            "maximax_optimiste": round(max(vals), 4),
            "laplace_equiprobable": round(sum(vals) / len(vals), 4),
            "regret_maximal": round(regret_max, 4),
        }
        if probabilites_completes:
            ev = sum(
                (p / total_p) * table[opt][sc]
                for sc, (_, p) in zip(noms_scenarios, scenarios_propres)
            )
            ligne["esperance"] = round(ev, 4)
        resultats.append(ligne)

    def gagnant(cle: str, *, minimiser: bool = False) -> str:
        f = min if minimiser else max
        return f(resultats, key=lambda r: r[cle])["option"]

    verdicts = {
        "prudent_maximin": gagnant("maximin_pessimiste"),
        "optimiste_maximax": gagnant("maximax_optimiste"),
        "indifference_laplace": gagnant("laplace_equiprobable"),
        "moins_de_regret": gagnant("regret_maximal", minimiser=True),
    }
    if probabilites_completes:
        verdicts["esperance_maximale"] = gagnant("esperance")

    return {
        "modele": "decision_incertitude",
        "options": resultats,
        "verdicts": verdicts,
        "accord": len(set(verdicts.values())) == 1,
    }


# -- C. WRAP (Chip & Dan Heath, *Decisive*, 2013) --------------------------------------------------


def cadre_wrap() -> dict[str, Any]:
    """Four biases that break a decision, four countermeasures, in the order of the book.
    No argument: this framework is fixed, it depends on nothing in the conversation - it is a
    questionnaire to run through, not a calculation."""
    return {
        "cadre": "WRAP",
        "source": "Chip & Dan Heath, Decisive (2013)",
        "etapes": [
            {
                "lettre": "W",
                "titre": "Widen your options",
                "biais_combattu": "narrow framing — seeing only a binary choice « do it or not »",
                "questions": [
                    "If this option did not exist, what would you do?",
                    "What would someone you admire do in your place?",
                    "Can you do THIS option AND another one at the same time, rather than choose?",
                ],
            },
            {
                "lettre": "R",
                "titre": "Reality-test your assumptions",
                "biais_combattu": "confirmation bias — looking for what proves you right",
                "questions": [
                    "What would make you CHANGE your mind if you found it out?",
                    "Can you run a small test before committing big?",
                    "What would someone who thinks the opposite of you see, that you do not?",
                ],
            },
            {
                "lettre": "A",
                "titre": "Attain distance before deciding",
                "biais_combattu": "the emotion of the present moment",
                "questions": [
                    "What would you advise a friend in exactly your situation?",
                    "How will you judge this choice in 10 minutes? In 10 months? In 10 years?",
                    "What is your most important value here, and which option serves it best?",
                ],
            },
            {
                "lettre": "P",
                "titre": "Prepare to be wrong",
                "biais_combattu": "overconfidence in a single prediction",
                "questions": [
                    "If in six months it is a failure, what will have happened? (premortem)",
                    "What signal, if it appears, must make you change course WITHOUT hesitating?",
                    "What is the worst case, and can you live with it?",
                ],
            },
        ],
    }


# -- D. PRE-MORTEM (Gary Klein, Harvard Business Review, 2007) ------------------------------------


def cadre_premortem() -> dict[str, Any]:
    """Instead of "what could go wrong" (a soft question: everyone answers "nothing in
    particular"), this forces you to ADMIT failure as an accomplished fact and to
    explain how it happened. Klein measured that this single reformulation doubles the
    number of risks identified by the same people about the same decision."""
    return {
        "cadre": "Premortem",
        "source": "Gary Klein, Harvard Business Review (2007)",
        "consigne": "Imagine we have reached this decision's deadline, and that it has been a "
        "TOTAL FAILURE. This is not a hypothesis: it is an accomplished fact. Explain what happened.",
        "etapes": [
            {
                "titre": "List",
                "question": "Give AT LEAST 5 plausible reasons for this failure, even the ones that "
                "seem silly or embarrassing — especially those.",
            },
            {
                "titre": "Spot",
                "question": "For each reason, what signal COULD have warned you before it was too "
                "late?",
            },
            {
                "titre": "Act",
                "question": "What can you do NOW, before committing, to reduce each of these "
                "risks?",
            },
        ],
    }


# -- E. THE 10-10-10 RULE (Suzy Welch, 2009) -------------------------------------------------------


def cadre_10_10_10() -> dict[str, Any]:
    """Getting out of the emotion of the moment by projecting to three fixed horizons. The point is
    not the precision of the timeframes (10 minutes, 10 months, 10 years are arbitrary) but the GAP
    between them: a decision that feels good at 10 minutes and bad at 10 years is not the same thing
    as a decision that is uncomfortable now but right over time."""
    return {
        "cadre": "10-10-10",
        "source": "Suzy Welch, 10-10-10 (2009)",
        "questions": [
            {
                "horizon": "10 minutes",
                "question": "How will you feel about this choice in 10 MINUTES?",
            },
            {
                "horizon": "10 months",
                "question": "How will you feel about this choice in 10 MONTHS?",
            },
            {
                "horizon": "10 years",
                "question": "How will you feel about this choice in 10 YEARS?",
            },
        ],
    }


# -- F. THE EISENHOWER MATRIX (popularized by Stephen Covey) --------------------------------------
#
# Different from the two mathematical models: it does not compare options against each other, it
# SORTS items by quadrant - the question is not "which one to choose" but "which one to start
# with". No sum: each item falls into ONE of the four boxes, mechanically, as soon as
# its two booleans are known.

_EISENHOWER_QUADRANTS: dict[tuple[bool, bool], dict[str, str]] = {
    (True, True): {
        "quadrant": "Q1 — Do now",
        "conseil": "a real crisis or deadline: handle it directly, but ask yourself why it "
        "arrived so late.",
    },
    (False, True): {
        "quadrant": "Q2 — Plan",
        "conseil": "the most rewarding quadrant in the long run, and the easiest to neglect — "
        "block out a slot, do not let it slip.",
    },
    (True, False): {
        "quadrant": "Q3 — Delegate or shorten",
        "conseil": "urgent but not important for YOU: delegate it, or handle it as fast as "
        "possible to be rid of it.",
    },
    (False, False): {
        "quadrant": "Q4 — Eliminate or defer",
        "conseil": "neither urgent nor important: the natural candidate to cut if time runs short.",
    },
}


def matrice_eisenhower(items: list[Any] | None) -> dict[str, Any]:
    """Sorts a list of items by urgency/importance. ``items`` - objects
    ``{"nom": ..., "urgent": bool, "important": bool}``; an item with no name is ignored."""
    groupes: dict[str, list[dict[str, Any]]] = {
        v["quadrant"]: [] for v in _EISENHOWER_QUADRANTS.values()
    }
    for item in items or []:
        if not isinstance(item, dict):
            continue
        nom = str(item.get("nom", "")).strip()
        if not nom:
            continue
        cle = _EISENHOWER_QUADRANTS[
            (bool(item.get("urgent", False)), bool(item.get("important", False)))
        ]
        groupes[cle["quadrant"]].append({"nom": nom, "conseil": cle["conseil"]})
    return {
        "modele": "matrice_eisenhower",
        "source": "Dwight Eisenhower / Stephen Covey, The 7 Habits of Highly Effective People",
        "quadrants": groupes,
    }
