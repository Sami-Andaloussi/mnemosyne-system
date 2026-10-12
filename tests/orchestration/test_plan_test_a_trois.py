"""A5 -- the anti-overfit clause: no item in THIS plan gets in without having answered for all three forms.

The user's own requirement: *"we can't overfit on the project […] we need to find something that can
adapt to anything."* The three forms measured are CREATION (the project), EXTRACTION (the factory) and
INSTANTIATION (Example Research); *the project supplies the proof, never the specification*.

 **THE SHAPE OF THIS FILE IS DICTATED BY AN AUDIT THAT FALSIFIED THE FIRST VERSION.** An isolated
third party (D75) found EIGHT classes of evasion in it and nine sabotages that ALL SURVIVE. The three
causes, and each is a lesson from this repo:

1. **I had written a SECOND item grammar.** ``^- \\*\\*([A-Z]\\d+)\\*\\*`` + ``glob("*.md")``
 against the repo's real reader (``plan_format``), which accepts the ``*`` bullet, a two-letter or
 hyphenated identifier, multiple spaces, and which descends via ``rglob``. Everything the reader
 counted as an item that my regex could not see was an item the anti-overfit clause never judged --
 **including the SUB-PLAN, which is the official growth path** (``make plan-nouveau``).
 This version CALLS ``plan_format.read_plan``. *A contract has ONE home, or the copies drift* --
 and here the copy had already drifted before living an hour.
2. **My judge accepted the NEGATION of what it required.** `` NOT LOOKED AT YET -- nothing
 specific has been measured`` used to pass, because ``sp[ée]cifique`` was searched as a substring.
 The written condition says *"declares IN SO MANY WORDS that it is specific"*: the code accepted
 the exact opposite. The verdict is now a **closed vocabulary** (```` + the named forms, or the
 ``SPECIFIQUE A`` declaration in capitals), and the prose stays free AFTER it.
3. **No test judged the JUDGE.** The four tests only read the real plan, which was conformant:
 weakening the judge therefore changed nothing, and 9 sabotages out of 9 survived. The
 ``test_juge_*`` and ``test_lecture_*`` tests below work on SYNTHETIC plans, green and red, so
 that breaking a clause turns something red.

 **What this clause STILL does not do**: ``.githooks/pre-commit`` does not run pytest (it only
pulls ``plan_format`` over the staged doors), so it refuses a repo state before ``make test`` /
``make check`` sees it, **not a commit**. Wiring the refusal all the way to the commit needs a clause
in ``plan_format.py`` -- another chat's lot, hence the orchestrator's call (the multi-session
orchestration protocol, hard rule 4).
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

from mnemosyne.production import plan_format

from _invariants import REPO_ROOT

PLAN_DIR = REPO_ROOT / "docs" / "plan"
#: The plan's DOOR. `make plans` adds its items to the arcs' ; ignoring it left
#: an item living in the document without ever being judged (measured: 47 counted, 46 judged).
PORTE = REPO_ROOT / "docs" / "PLAN.md"

#: The field, exactly as it is written in items. Read at the start of an item's body line.
_FIELD = re.compile(r"^\s*\*Test à trois\*\s*:\s*(.*)$")

#: POPULATION RATCHET, and it is a PRECONDITION, not a side test. The plan carried 46 items
#: on 2026-08-14. The audit measured the hole: with a floor at 40, **two whole arcs (F and G,
#: 6 items) could disappear in silence**; and on an empty plan folder, three of the four tests
#: stayed GREEN on zero items. The floor therefore lives INSIDE the reader: any clause that reads
#: the plan raises before judging anything at all. It rises as the plan grows, it only falls through
#: a written gesture -- floors, never ceilings.
PLANCHER_ITEMS = 46

#: THE VERDICT'S CLOSED VOCABULARY -- the QUESTION is forced open, never the ANSWER, but the
#: VERDICT is a closed word. Without it, ` NOT LOOKED AT YET -- nothing specific` used to be
#: accepted: a judge that searches for `specifique` as a substring cannot tell a declaration from
#: its negation.
_VERDICT_OK = re.compile("\U00002705")
_LES_TROIS = re.compile(r"les trois", re.IGNORECASE)
_USINE = re.compile(r"usine", re.IGNORECASE)
_RECHERCHE = re.compile(r"example research", re.IGNORECASE)
#: The specificity declaration, IN CAPITALS and followed by its object. `NON SPECIFIQUE` does not
#: produce it, nor does `ce n'est pas spécifique`: that is what makes it deliberate rather than
#: incidental.
_SPECIFIQUE = re.compile(r"SP[EÉ]CIFIQUE\s+[AÀ]\b")

#: POLARITY, and it cost a second round of audit -- then a MEASUREMENT on the population, which
#: killed my first fix. Requiring `SPECIFIQUE A` in capitals was not enough: `NON SPÉCIFIQUE
#: À Mnémosyne`, `PAS SPÉCIFIQUE À un autre projet`, `RIEN DE SPECIFIQUE A signaler` used to pass. But a
#: GLOBAL refusal of any negation wrongly accuses **7 of the 46 real answers**: A1 says "ne dépend
#: d'AUCUN corpus" [depends on NO corpus], A2 says "le registre ne voyage PAS" [the registry does
#: NOT travel] -- perfectly legitimate explanatory prose.
#: Negation is therefore read **LOCALLY, right before the declaration**: that is the only
#: position where it reverses its meaning.
_NEGATION_AVANT = re.compile("(\U0000274C|\\bNON\\b|\\bPAS\\b|\\bRIEN\\b|\\bAUCUN\\b|\\bJAMAIS\\b)[^.]{0,4}$", re.I)

#: The two markers of work NOT DONE, refused globally. Measured on the 46 real
#: answers: **0 false positives** -- no legitimate answer says « à faire » [to do].
_NON_REPONDU = re.compile(r"\bTODO\b|\b[AÀ]\s+FAIRE\b", re.IGNORECASE)


def reponse_valide(reponse: str) -> bool:
    """A5's *Done when*, literally: **an answer for the factory and Example Research, OR an
 in-so-many-words declaration of specificity.**

 Two forms, and nothing else:

 * ```` **and** (« les trois » | « usine » AND « Example Research ») -- the glyph carries the verdict,
 the words carry the answer. Without the glyph, ``les trois premieres semaines se passent chez
 un autre projet`` used to be enough to validate an item.
 * ``SPECIFIQUE A …`` in capitals -- a declaration, not a mention. ``NON SPECIFIQUE et non
 repondu`` does not produce it.

 There is **no** ``if not reponse.strip()`` guard up front, and that is deliberate: an empty
 answer carries neither a verdict nor a declaration, so the two clauses below already refuse it.
 Sabotaged, this guard SURVIVED -- *a sabotage that survives can signal redundancy rather than a
 hole*, and a clause no test can kill is a false barrier. The empty cases are still tested below:
 they now measure the clause that TRULY refuses them.

 **POLARITY is read LOCALLY**, right before the declaration: ``NON SPÉCIFIQUE À`` negates it,
 while « ne dépend d'AUCUN corpus » two sentences later negates nothing. A global refusal of any
 negation used to wrongly accuse 7 of the 46 real answers.

 **WHAT THIS JUDGE DOES NOT CATCH, AND IT MUST BE SAID RATHER THAN LEFT TO BE ASSUMED**:
 `` fait — les trois formes n'ont PAS ete regardees`` [done — the three forms were NOT looked
 at] **passes**. The verdict is positive and the prose contradicts it. On this population, no
 lexical detector separates this case from A1 (`` les trois — une grammaire ne dépend d'AUCUN
 corpus``): both carry a negation at the same distance from the verdict. This is a **false
 declaration**, not a defect of form, and this barrier judges form. *Admitting that no barrier
 exists is a valid, free answer -- that is what keeps the rule from manufacturing false
 barriers.*"""
    if _NON_REPONDU.search(reponse):
        return False
    if match := _SPECIFIQUE.search(reponse):
        return not _NEGATION_AVANT.search(reponse[: match.start()])
    couvre = _LES_TROIS.search(reponse) or (_USINE.search(reponse) and _RECHERCHE.search(reponse))
    return bool(_VERDICT_OK.search(reponse) and couvre)


#: Opening / closing of a code block in an item's detail.
_FENCE = re.compile(r"^\s*(```|~~~)")


def _reponse_de(item: plan_format.PlanItem) -> str | None:
    """The answer THIS item declares, or ``None``. The item's body is the one the repo's reader
 assigns it (``title`` + ``detail``) -- never "everything up to the next item," which used to
 make the final item swallow the end-of-file prose, headings crossed and all.

 CODE BLOCKS in the detail are skipped: ``plan_format`` keeps them verbatim (that is what a
 view must display), so an item that shows the field's TEMPLATE inside a block used to have that
 example count as its answer -- and since the first match wins, the example blinded the real
 line, or its absence."""
    dans_bloc = False
    for line in (item.title, *item.detail):
        if _FENCE.match(line):
            dans_bloc = not dans_bloc
            continue
        if dans_bloc:
            continue
        if match := _FIELD.match(line):
            # The value stops at the NEXT field, never at the end of the line. Otherwise
            # `*Test à trois* : a faire *Produit* : un document pour les trois formes` is valid
            # -- it is the NEIGHBOR's that redeems the answer. `plan_format.read_item_fields`
            # documents exactly this rule ("a value runs to the NEXT field"), and my clause used to
            # commit the very defect the repo's reader closes: 70 lines in this repo carry
            # two markers or more.
            valeur = match.group(1)
            if suivant := plan_format.FIELD_MARKER_RE.search(valeur):
                valeur = valeur[: suivant.start()]
            return valeur.strip()
    return None


def lire_items(
    plan_dir: Path = PLAN_DIR,
    *,
    porte: Path | None = PORTE,
    plancher: int = PLANCHER_ITEMS,
) -> tuple[tuple[str, str, str | None], ...]:
    """``(source, ident, reponse)`` for every item in the plan, via **the repo's reader**.

 ``rglob``, not ``glob``: a sub-plan (``<arc>/plan/<fichier>.md``) is the normal growth
 shape, and it used to be entirely invisible.

 **The DOOR is read too.** ``make plans`` adds up the items from the door file and those
 from the arcs; my clause used to read only the arcs. The audit's measurement: an item written in
 the door gave **47 items counted by the plan and 46 judged here** -- present in the document,
 judged by nobody, and invisible to the floor.

 **A DUPLICATE identifier is an item that DROPS OUT of judgment.** ``read_plan`` removes it
 from ``items`` and files a ``id_duplique`` problem; never reading ``problems`` used to let that
 item live in the plan with no answer AND without moving the count.

 Raises if the population falls below ``plancher``: without that, a plan that shrinks away
 returns zero missing and every clause passes green while keeping nothing at all."""
    ident_seen: dict[str, str] = {}
    out: list[tuple[str, str, str | None]] = []
    problemes: list[str] = []
    fichiers = [f for f in (porte,) if f is not None and f.is_file()]
    fichiers += sorted(plan_dir.rglob("*.md"))
    for f in fichiers:
        reading = plan_format.read_plan(
            f.read_text(encoding="utf-8"), origin=f.name, ident_seen=ident_seen
        )
        for item in reading.items:
            out.append((f.name, item.ident, _reponse_de(item)))
        problemes += [f"{f.name}: {p.detail}" for p in reading.problems if p.kind == "id_duplique"]
    assert not problemes, (
        "duplicate identifiers — read_plan removes these items from its list, so they would live in "
        "the plan without ever being judged: " + " · ".join(problemes)
    )
    assert len(out) >= plancher, (
        f"{len(out)} items read under {plan_dir} (floor {plancher}) — a plan that shrinks away would "
        "make this barrier read green while it keeps nothing at all"
    )
    return tuple(out)


# ============================ THE REAL PLAN ============================
def test_le_plan_porte_encore_ses_items() -> None:
    """The ratchet. ``lire_items`` raises by itself if the population has shrunk away."""
    assert len(lire_items()) >= PLANCHER_ITEMS


def test_chaque_item_repond_au_test_a_trois() -> None:
    sans = [f"{ident} ({f})" for f, ident, rep in lire_items() if rep is None]
    assert not sans, (
        "items with no *Test à trois* field — the anti-overfit clause does not apply to them: "
        + ", ".join(sans)
    )


def test_chaque_reponse_est_un_verdict_valide() -> None:
    muettes = [
        f"{ident} ({f}) → {rep[:70]}"
        for f, ident, rep in lire_items()
        if rep is not None and not reponse_valide(rep)
    ]
    assert not muettes, (
        "answers that carry neither a \U00002705 naming the three forms nor a "
        "« SPÉCIFIQUE À … » declaration: " + " · ".join(muettes)
    )


# ==================== THE JUDGE, JUDGED ON SYNTHETIC CASES ====================
# Without these cases, weakening the judge turns nobody red: since the real plan is conformant, a
# judge that accepts EVERYTHING finds it conformant too. Nine sabotages survived for exactly that
# reason.


@pytest.mark.parametrize(
    "reponse",
    [
        "\U00002705 les trois",
        "\U00002705 les trois — une grammaire d'item ne dépend d'aucun corpus",
        "usine \U00002705 · Example Research \U00002705 — la composition est locale à un plan",
        "**SPÉCIFIQUE À MNÉMOSYNE**, déclaré en toutes lettres",
        "SPECIFIQUE A ce plan-ci dans son obligation",
    ],
)
def test_juge_accepte_une_vraie_reponse(reponse: str) -> None:
    assert reponse_valide(reponse)


@pytest.mark.parametrize(
    "reponse",
    [
        # The eight forms the isolated audit made pass.
        "\U0000274C PAS ENCORE REGARDÉ — rien de spécifique n'a été mesuré, à faire.",
        "pas encore répondu ; ce n'est PAS spécifique, à faire",
        "\U000026A0\U0000FE0F NON SPÉCIFIQUE et non répondu",
        # The six forms from the SECOND round of audit: the NEGATED declaration, and the positive
        # verdict whose own prose admits nothing was done.
        "NON SPÉCIFIQUE À Mnémosyne : c'est generique, rien n'a ete mesure",
        "PAS SPÉCIFIQUE À un autre projet, et pas encore repondu",
        "RIEN DE SPECIFIQUE A signaler -- a faire",
        "\U0000274C SPÉCIFIQUE À rien",
        "\U00002705 mesure pour un autre projet seulement — les trois formes restent A FAIRE",
        "TODO — à mesurer pour les trois formes",
        "aucune idée pour les trois",
        "les trois premières semaines se passent chez un autre projet",
        "spécifique",
        # And the empty / evasive forms already closed.
        "",
        "   ",
        "?",
        "\U00002705",
        "à faire",
        "les 3",
    ],
)
def test_juge_refuse_une_non_reponse(reponse: str) -> None:
    """ Every one of these lines used to pass. « les trois formes » [the three forms] with no
 verdict, and « NON SPÉCIFIQUE » with the word in capitals, are the two that show a
 substring-matching judge judges nothing."""
    assert not reponse_valide(reponse)


# ==================== READING, MEASURED ON SYNTHETIC PLANS ====================
_PORTE = "# PLAN — epreuve\n\n## Ce que c'est\n\nde la prose.\n\n## Les items\n\n"


def _plan(tmp_path: Path, corps: str) -> Path:
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "arc.md").write_text(_PORTE + corps, encoding="utf-8")
    return plan


@pytest.mark.parametrize(
    "ligne",
    [
        "- **L1** \U00002B1C **item with a hyphen bullet.**",
        "* **L2** \U00002B1C **item with an asterisk bullet.**",
        "- **LL4** \U00002B1C **two-letter identifier.**",
        "-  **L5** \U00002B1C **two spaces after the hyphen.**",
        "- **L6-bis** \U00002B1C **hyphenated identifier.**",
    ],
)
def test_lecture_voit_toutes_les_formes_d_item(tmp_path: Path, ligne: str) -> None:
    """The four forms my home-made regex could not see, and that the repo's reader counts.
    Each one was an item the anti-overfit clause never judged."""
    items = lire_items(_plan(tmp_path, ligne + "\n"), porte=None, plancher=0)
    assert len(items) == 1 and items[0][2] is None


def test_lecture_descend_dans_un_SOUS_PLAN(tmp_path: Path) -> None:
    """``glob`` is not recursive, and the sub-plan is the official growth path
    (``make plan-nouveau``): a whole arc used to be invisible there."""
    plan = _plan(tmp_path, "- **L1** \U00002B1C **surface-level item.**\n  *Test à trois* : \U00002705 les trois\n")
    niche = plan / "10-sous-arc" / "plan"
    niche.mkdir(parents=True)
    (niche / "arc.md").write_text(_PORTE + "- **M1** \U00002B1C **nested item, no answer.**\n", "utf-8")
    idents = {ident: rep for _, ident, rep in lire_items(plan, porte=None, plancher=0)}
    assert idents == {"L1": "\U00002705 les trois", "M1": None}


def test_lecture_n_attribue_pas_la_prose_de_fin_de_fichier_au_dernier_item(tmp_path: Path) -> None:
    """The audit's subtlest evasion, demonstrated on the REAL arc A: the last item's body used to
    run to the end of the file, so a table caption sitting 23 lines further down, under a
    `---` and a heading, redeemed the item."""
    plan = _plan(
        tmp_path,
        "- **L1** \U00002B1C **the file's last item, no answer.**\n"
        "\n---\n\n## A RECAP SECTION\n\n"
        "*Test à trois* : \U00002705 les trois — la forme du tableau ci-dessus.\n",
    )
    assert [rep for _, _, rep in lire_items(plan, porte=None, plancher=0)] == [None]


def test_lecture_ignore_un_champ_ecrit_dans_un_BLOC_DE_CODE(tmp_path: Path) -> None:
    """A field shown as an example inside a template does not answer on the author's behalf."""
    plan = _plan(
        tmp_path,
        "- **L1** \U00002B1C **item showing the template.**\n"
        "\n  ```markdown\n  *Test à trois* : \U00002705 les trois — remplace cette ligne\n  ```\n",
    )
    assert [rep for _, _, rep in lire_items(plan, porte=None, plancher=0)] == [None]


def test_lecture_ignore_une_mention_EN_MILIEU_de_ligne(tmp_path: Path) -> None:
    """The field is read at the START of a line: a sentence that quotes it does not answer on the
 item's behalf.

 **Correcting one of the audit's conclusions, with its measurement.** It reported that removing
 the ``^`` from ``_FIELD`` turned nobody red, and concluded from that that the claimed mechanism
 was not actually there. Measured: the anchor is held by **TWO redundant mechanisms** --
 ``re.compile(r"\\s*x").match("y x")`` returns ``None`` (it is the CALL that anchors), and ``^``
 anchors again as soon as you switch to ``search``. **Removing EITHER ONE therefore changes
 nothing**; removing **both** opens the hole, and that double sabotage is what this test kills
 (measured: ``1 failed``). *A single sabotage that survives can measure redundancy, not a
 death.*"""
    plan = _plan(
        tmp_path,
        "- **L1** \U00002B1C **item with no answer.**\n"
        "  *Produit* : un document qui explique le *Test à trois* : \U00002705 les trois formes\n",
    )
    assert [rep for _, _, rep in lire_items(plan, porte=None, plancher=0)] == [None]


def test_juge_exige_les_DEUX_formes_pas_une_seule() -> None:
    """The clause says « usine ET Example Research » [factory AND Example Research]. No fixture carried an answer
    for just ONE form, so swapping AND for OR used to survive: the clause was correct, nothing
    measured it."""
    assert not reponse_valide("\U00002705 mesure pour l'usine seulement")
    assert not reponse_valide("\U00002705 Example Research uniquement")
    assert reponse_valide("\U00002705 usine · Example Research")


def test_lecture_lit_le_champ_pose_sur_la_LIGNE_DU_BULLET(tmp_path: Path) -> None:
    """``plan_format`` measures that **61 bullets in this repo** carry their field on the bullet's
    own line. Removing ``item.title`` from the reading used to survive every test: the failure mode
    here is FALSE ACCUSATION (an answered item declared mute), not evasion -- and it counts just as
    much."""
    plan = _plan(tmp_path, "- **L1** \U00002B1C *Test à trois* : \U00002705 les trois\n")
    assert [rep for _, _, rep in lire_items(plan, porte=None, plancher=0)] == ["\U00002705 les trois"]


def test_lecture_coupe_la_valeur_au_champ_SUIVANT(tmp_path: Path) -> None:
    """ The value used to run to the end of the line and swallow the neighboring field: it was the
 ``*Produit*`` field's ```` that redeemed the answer. ``read_item_fields`` documents the reverse
 rule (« a value runs to the NEXT field ») -- my clause used to commit the very defect the
 repo's reader closes."""
    plan = _plan(
        tmp_path,
        "- **L1** \U00002B1C **unanswered item.**\n"
        "  *Test à trois* : a mesurer *Produit* : un document \U00002705 pour les trois formes\n",
    )
    (reponse,) = [rep for _, _, rep in lire_items(plan, porte=None, plancher=0)]
    assert reponse == "a mesurer" and not reponse_valide(reponse)


def test_lecture_juge_aussi_les_items_de_la_PORTE(tmp_path: Path) -> None:
    """``make plans`` adds up the door and the arcs; reading only the arcs used to let an item live
    in the document with no judge -- and invisible to the floor (the audit's measurement: 47 counted,
    46 judged)."""
    plan = _plan(tmp_path, "- **L1** \U00002B1C **arc item.**\n  *Test à trois* : \U00002705 les trois\n")
    porte = tmp_path / "PLAN.md"
    porte.write_text(_PORTE + "- **Z9** \U00002B1C **item written in the DOOR, no answer.**\n", "utf-8")
    idents = {ident: rep for _, ident, rep in lire_items(plan, porte=porte, plancher=0)}
    assert idents == {"Z9": None, "L1": "\U00002705 les trois"}


def test_lecture_REFUSE_un_identifiant_duplique(tmp_path: Path) -> None:
    """``read_plan`` removes the duplicate item from ``items`` and files a problem. Never reading
    ``problems`` used to let that item live in the plan **with no answer AND without moving the
    count** -- so invisible to the floor too. *An item removed from judgment is not a conformant
    item.*"""
    plan = _plan(tmp_path, "- **L1** \U00002B1C **premier.**\n  *Test à trois* : \U00002705 les trois\n")
    (plan / "b.md").write_text(_PORTE + "- **L1** \U00002B1C **le meme identifiant, ailleurs.**\n", "utf-8")
    with pytest.raises(AssertionError, match="duplicate"):
        lire_items(plan, porte=None, plancher=0)


def test_lecture_leve_quand_la_population_passe_sous_le_plancher(tmp_path: Path) -> None:
    """A precondition, not a neighboring test: any clause that reads the plan raises along with it."""
    plan = _plan(tmp_path, "- **L1** \U00002B1C **a single item.**\n")
    with pytest.raises(AssertionError, match="floor"):
        lire_items(plan, porte=None, plancher=2)


def test_lecture_leve_sur_un_dossier_de_plan_VIDE(tmp_path: Path) -> None:
    """On a plan folder that has vanished, ``rglob`` returns empty without raising: three clauses
    out of four used to pass GREEN on zero items."""
    vide = tmp_path / "plan"
    vide.mkdir()
    with pytest.raises(AssertionError, match="floor"):
        lire_items(vide, porte=None)


def test_un_plan_synthetique_entierement_conforme_passe(tmp_path: Path) -> None:
    """The PASSING case, asserted rather than assumed: without it, a reader that returned `None`
    everywhere would turn the real plan red without anyone knowing whether it is the plan or the
    reader."""
    corps = textwrap.dedent(
        """\
        - **L1** \U00002B1C **premier item.**
          *Test à trois* : \U00002705 les trois — rien de particulier
        - **L2** \U00002B1C **second item.**
          *Test à trois* : **SPÉCIFIQUE À** cette porte d'entrée, déclaré en toutes lettres
        """
    )
    items = lire_items(_plan(tmp_path, corps), porte=None, plancher=0)
    assert [ident for _, ident, _ in items] == ["L1", "L2"]
    assert all(rep is not None and reponse_valide(rep) for _, _, rep in items)
