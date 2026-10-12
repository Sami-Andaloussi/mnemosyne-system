"""I4 (b) — the signals of MY OWN TRACE: what the operator's words cannot contain.

**The witnesses are FROZEN BY THEIR SET, never by their count.** Item I4 announces "5
admissions of error and 5 item additions across the 16 commits of this session"; the population
has grown since (23 commits that same evening, three chats committing in parallel). A test that
asserted "5" would be measuring the date on which it was written. This file therefore freezes the
**exact titles** of the five admissions, and the exact title of the repository's own phrase that
must NOT be mistaken for an admission.
"""

from __future__ import annotations

import pytest

from mnemosyne.production.review_signals import (
    Commit,
    detect,
    detect_trace,
    is_task_boundary,
    items_ajoutes,
    render_trace,
)

# The FIVE admissions from the 2026-08-14 session, verbatim (ASCII titles with no accents, repo rule).
AVEUX = (
    "fix(plan): la porte d'entree annoncait un cap qui n'existe plus, et j'avais cree 3 liens morts",
    "fix(plan): l'EXTRACTION n'est pas << fusionner >> -- j'avais pris un exemple pour une specification",
    "fix(prerequis): mon ticket K1 posait 1,2 Go de base VIVANTE dans iCloud",
    "feat(K1): l'index vit sur un VOLUME -- et mon ticket portait deux defauts",
    "fix(I4): j'avais declare la moitie (b) INFERMABLE sur une premisse FAUSSE",
)

# THE REPOSITORY'S OWN VOCABULARY, which is NOT an admission. Two of the eight titles
# containing "FAUX" [FALSE] are talking about the domain, not an error — exactly the trap this
# module already paid for once (patterns cut because they fired on `stop`, `deriv`, `once again`,
# 136 hits).
# The FOUR admissions the first version used to miss — RECALL measured out-of-sample: 0 out of 4.
# The patterns had been written while looking at the very window they were then validated against.
AVEUX_HORS_ECHANTILLON = (
    "fix(A2): l'audit isole a trouve une ligne FAUSSE, trois chiffres faux, une perte SILENCIEUSE",
    "fix(F1): l'audit isole a FALSIFIE ma porte -- 7 affirmations fabriquees, VERT, sortie 0",
    "fix(A5): l'audit isole a falsifie ma clause -- 8 evasions, et 9 sabotages sur 9 SURVIVAIENT",
    "feat(F1): l'USAGE REEL refuse ma porte -- la memoire vit HORS du depot",
)

VOCABULAIRE = (
    "fix(skill-trial): un taux de capture sans son taux de FAUX POSITIFS est un mur",
    "feat(bornes): A4 -- un plafond de SORTIE qui coupe en silence rend une FAUSSE reponse",
    "feat(A2): l'echelle d'obligation -- et le depot compte ZERO cible make de niveau 2",
    "feat(postes): le prompt d'un chat devient COURT, l'instruction devient une DONNEE",
)

# THE CONTROL CORPUS, and it is worth more than the positive witnesses. Six PLAUSIBLE titles
# this repository never wrote: exactly why the first version of the widened patterns scored 0
# false positives on the real corpus — yet it accused 6 out of 6 of these. *A rate measured where
# no counter-examples exist is not a rate.* Supplied by the isolated audit.
CORPUS_TEMOIN = (
    "feat(garde): l'audit a trouve 0 defaut -- la porte tient",
    "feat(plan): ma regle de nommage est posee et documentee",
    "docs: ma mesure de reference est publiee",
    "feat(audit): l'audit isole a corrige la coquille d'un tiers",
    "chore: ma clause de style passe au lint",
    "feat: l'audit a trouve la cause du bug d'un AUTRE chat",
)


@pytest.mark.parametrize("titre", AVEUX)
def test_les_cinq_aveux_geles_sont_TOUS_detectes(titre):
    signaux = detect_trace((Commit("abc1234", titre),))
    assert [s.kind for s in signaux] == ["aveu"], f"missed admission: {titre}"


@pytest.mark.parametrize("titre", AVEUX_HORS_ECHANTILLON)
def test_les_quatre_aveux_HORS_ECHANTILLON_sont_rattrapes(titre):
    """The RECALL, never measured, was 0/4 on the very next window — an audit caught it."""
    assert [s.kind for s in detect_trace((Commit("abc1234", titre),))] == ["aveu"], titre


# =================================================================================================
# THE INDEPENDENT CONTROL CORPUS — twenty titles WRITTEN BY THE ISOLATED AUDITOR, never by me.
# =================================================================================================
#
# This is the only measurement, across four rounds, that the producer could not manufacture. It
# killed TWO successive tightening passes that each scored "0 false positives" on the 602 real
# titles — a zero that was a property of what this repository has HISTORICALLY written, never a
# property of the rule. It is frozen HERE, verbatim, because a gate's proof living inside a
# conversation disappears at the first compaction, and the next agent would recalibrate on
# nothing.
#
# MEASURED RATES, and both of them count:
#   before the subject + polarity fix: 4 false positives / 10  ·  9 misses / 10
#   after                             : 0 false positives / 10  ·  4 misses / 10
#
# WE NO LONGER WIDEN AGAINST THIS CORPUS. Each further alternative would be tuned against the
# one corpus capable of refuting me, and a control corpus one calibrates against stops being a
# control. The four remaining misses are NAMED rather than closed: "doesn't hold," "the wrong
# end," "my X does not…," and #10, which the auditor themselves declares contentious.
#
# TWO HONESTY CAVEATS FROM THE AUDITOR, frozen along with the titles (none is removed — a corpus
# amputated of its awkward cases no longer measures anything):
#   * ADMISSION #10 is CONTENTIOUS: "the rate published yesterday covered the wrong population"
#     carries no first-person marker at all. A detector that misses it is not necessarily wrong.
#   * INNOCENT #9 leans slightly the other way: "the reader invalidates my status-less items" can
#     read as an admission; the end of the title (0 out of 48) says it is describing a function.
TEMOIN_INNOCENTS = (
    "feat(garde): la porte refuse ma demande de test -- comportement attendu, refus nomme",
    "docs(plan): ma methode de lecture d'un item est decrite en trois lignes",
    "feat(audit): l'audit isole confirme les trois chiffres -- aucun FAUX POSITIF",
    "chore(tests): le corpus temoin compte 8 titres, 0 faux, et il entre dans la suite",
    "feat(E3): le hook NOMME les fichiers, l'agent commit -- la porte n'ecrit rien",
    "fix(lint): ruff casse ma ligne trop longue -- reformatee, aucun changement de sens",
    "feat(F2): ma sous-question part avec son a-lire et sa sortie bornee",
    "obs(banc): l'audit tiers rend son verdict -- rien de FAUX trouve sur les 12 items",
    "feat(plan): le lecteur invalide mes items sans statut -- refus nomme, 0 sur 48",  # contentious
    "chore(rangement): 12 fichiers deplaces, aucun lien mort, portabilite verifiee",
)

#: The four the detector still MISSES, by their (1-based) INDEX in the tuple below.
#: Frozen as an ACKNOWLEDGED GAP, not as a failure: they say exactly where the hole is.
TEMOIN_AVEUX_RATES = (1, 2, 9, 10)

TEMOIN_AVEUX = (
    "fix(A2): le chiffre que j'ai publie hier ne tient pas -- 3 au lieu de 8",
    "corrige(E3): la borne que j'ai posee coupait le mauvais bout de la fenetre",
    "fix(I4): je n'avais pas vu que le detecteur comptait les clotures comme des naissances",
    "mesure(C1): erreur de ma part -- la population mesuree n'etait pas la bonne",
    "fix(plan): oubli dans mon dernier commit -- l'item n'etait pas ferme",
    "revert(F1): ma porte etait trop large, on revient en arriere",
    "fix(hook): le budget que j'avais choisi jetait la fin de la tache",
    "corrige(memoire): j'ai casse un lien en compactant -- restaure et verifie",
    "fix(tests): mon sabotage ne compilait pas, il mesurait le compilateur",
    "mesure(I): le taux publie hier portait sur la mauvaise population",  # contentious
)


@pytest.mark.parametrize("titre", TEMOIN_INNOCENTS)
def test_AUCUN_innocent_du_corpus_INDEPENDANT_n_est_accuse(titre):
    """The hardest witness in the file: 4 out of 10 used to fall, including one CLEAN audit
    verdict."""
    assert detect_trace((Commit("abc1234", titre),)) == (), f"false positive on: {titre}"


@pytest.mark.parametrize("n", [i for i in range(1, 11) if i not in TEMOIN_AVEUX_RATES])
def test_les_aveux_du_corpus_INDEPENDANT_que_le_detecteur_DOIT_voir(n):
    titre = TEMOIN_AVEUX[n - 1]
    assert [s.kind for s in detect_trace((Commit("abc1234", titre),))] == ["aveu"], titre


@pytest.mark.parametrize("n", TEMOIN_AVEUX_RATES)
def test_les_quatre_aveux_RATES_sont_geles_comme_un_DU_et_non_caches(n):
    """A DECLARED gap, frozen by a test that holds it open.

    These four are not seen, and the admission is a free, valid answer. The test fails the day
    one of them gets caught — and that is deliberate: it will force a RE-MEASURE of the false
    positives before banking the gain, instead of silently widening against the one corpus that
    can refute me.
    """
    titre = TEMOIN_AVEUX[n - 1]
    assert detect_trace((Commit("abc1234", titre),)) == (), (
        f"CAUGHT MISS: {titre!r} — re-measure the 10 innocents BEFORE removing this index from "
        "TEMOIN_AVEUX_RATES, or you bank a recall gain without its false-accusation rate."
    )


# =================================================================================================
# THE THIRD CONTROL CORPUS — and it is THIS one that carries the published figure.
# =================================================================================================
#
# Written by the same isolated auditor, AFTER corpus 2 had entered these tests: corpus 2 could
# therefore no longer measure the rule, only my calibration against it. The four-round table, and
# it is the WRITTEN reason to stop:
#
#     round | false positives on the corpus IN HAND | on the first corpus NEVER SEEN
#       2   | 0 / 591 (the real repository)          | 6 / 6
#       3   | 0 / 6   (corpus 1)                      | 4 / 10
#       4   | 0 / 10  (corpus 2)                      | 3 / 10
#
# Each tightening pass drives the metric to ZERO on everything it owns and finds 30-40% false
# accusations on the first corpus it doesn't own. The cause is STRUCTURAL: an admission is a claim
# about the AUTHOR'S INTENT and about the VALENCE of an outcome; a regex on a title has access to
# neither. The limit is DECLARED; no more widening.
#
# AND THE ASYMMETRY EXPLAINS EVERYTHING: the other half of I4(b) — the item detector — is EXACT
# (8/8, 0 false, 0 missed across 120 commits) because it reads a STRUCTURE (a diff), not prose.
# *What is measured on a structure gets closed; what is measured on prose gets bounded and
# declared.*
#
# AUDITOR'S CAVEATS, engraved and not removed: admission 6 is CONTENTIOUS ("this commit fixes what
# the previous one broke" carries no first-person marker at all) · innocent 10 is the most
# debatable of the three false positives · innocent 7 carries an accent ("gelés") where this
# repository writes its titles in ASCII: that is the auditor's own typo, KEPT AS-IS because the
# 3/10 rate was taken against this exact string.
TEMOIN3_INNOCENTS = (
    "feat(banc): le banc mesure ma porte en 12 ms -- aucune regression",
    "docs(audit): le protocole d'audit isole est ecrit -- qui juge, quoi, avec quelle preuve",
    "feat(garde): l'epreuve tue mes cas de test lents -- 40 s gagnees sur la suite",
    "revert(deps): on repasse a la version 2.1 en attendant le correctif amont",
    "feat(mesure): la mesure refute l'hypothese de l'article, pas la mienne",
    "obs(banc): l'usage reel confirme ma porte sur 40 tirs -- zero refus",
    "feat(I5): mon detecteur de doublons entre dans la suite, 3 cas gelés",  # accent: typo KEPT
    "fix(perf): le profil tue mon cache inutile -- 3 Mo de moins en memoire",
    "docs(D176): l'audit tiers a valide les trois chiffres -- rien a corriger",
    "feat(A7): l'epreuve casse mes 12 cas obsoletes -- remplaces par 4 plus durs",  # contentious
)

TEMOIN3_AVEUX = (
    "fix(E4): j'ai confondu la borne et la fenetre -- deux choses differentes",
    "corrige(D3): ce que j'ai ecrit hier sur les invariants est a jeter",
    "fix(A1): mauvaise lecture de ma part sur le champ *Prerequis*",
    "mesure(F1): mon estimation etait a cote -- 40 fois trop optimiste",
    "fix(garde): j'ai oublie le cas du chemin relatif, il passait tout droit",
    "corrige(plan): ce commit repare ce que le precedent a casse",  # contentious
    "fix(I4): ma faute -- le veto s'appliquait avant les regles positives",
    "revert(E3): je reviens sur mon propre correctif, il elargissait trop",
    "fix(hook): bug introduit par moi hier, le rituel se taisait",
    "mesure(C2): je m'etais plante de population, tout est a refaire",
)

#: THE TWO PUBLISHED RATES, by their exact INDICES — this is what the block prints to the agent.
TEMOIN3_FAUX_POSITIFS = (3, 4, 10)
TEMOIN3_AVEUX_VUS = (8, 10)


def test_LES_DEUX_TAUX_PUBLIES_sont_EXACTEMENT_ceux_qu_on_mesure():
    """THE BIDIRECTIONAL BARRIER — it turns red if things get WORSE **and** if they get BETTER.

    Turning red on worse is ordinary. Turning red on better is the point: making these three false
    positives fall would mean calibrating against this corpus, which kills it as a control — and
    that would be the FIFTH iteration of a trap four rounds have documented. The day a tightening
    pass changes these indices, a FRESH corpus is needed before banking anything.

    This is also what ARMS the figure printed in the block: without this test, it could be removed
    or left to go stale without any witness moving. *A count with no command behind it is a
    memory.*
    """
    faux = tuple(i + 1 for i, t in enumerate(TEMOIN3_INNOCENTS) if detect_trace((Commit("a", t),)))
    vus = tuple(i + 1 for i, t in enumerate(TEMOIN3_AVEUX) if detect_trace((Commit("a", t),)))
    assert faux == TEMOIN3_FAUX_POSITIFS, (
        f"false positives {faux} instead of {TEMOIN3_FAUX_POSITIFS} — if this is BETTER, you "
        "calibrated against the control corpus: write a NEW one before banking it, and update "
        "the rate the block prints (production/review_signals.py, the advice for the `aveu` "
        "signal)."
    )
    assert vus == TEMOIN3_AVEUX_VUS, f"admissions seen {vus} instead of {TEMOIN3_AVEUX_VUS}"


def test_le_VERDICT_D_AUDIT_est_arme_alternative_par_alternative():
    """`rendu NON` [`returned NO`] was the fix HIGHLIGHTED by its own commit — and nothing armed
    it.

    This is the line that recovers the admission silently lost by the round-3 tightening pass (two
    counts of 24, both identical, two different sets). An isolated sabotage removed it: 82 tests
    stayed green. *The barrier nothing calls.*
    """
    for titre in (
        "chore(postes): journal chat 2 -- l'audit a rendu NON, tout est corrige",
        "obs(banc): l'audit a rendu NON SOUTENABLE -- 13 survivants sur 14",
        "fix(A2): l'audit isole a trouve une ligne FAUSSE",
    ):
        assert [s.kind for s in detect_trace((Commit("a", titre),))] == ["aveu"], titre
    # and the polarity check keeps THIS clause, without touching the others
    assert detect_trace((Commit("a", "obs: l'audit rend son verdict -- rien de FAUX trouve"),)) == ()
    assert [s.kind for s in detect_trace((Commit("a", "fix: j'avais tort, zero erreur reelle"),))] == [
        "aveu"
    ], "a veto written for one clause must not kill a MEASURED alternative"


def test_le_bloc_IMPRIME_les_deux_taux_et_pas_seulement_le_flatteur():
    """Publishing one's false accusations without publishing one's SILENCES is a wall, in the
    other direction."""
    (signal,) = detect_trace((Commit("abc", "fix(x): j'avais tort"),))
    assert "3 false out of 10" in signal.advice
    assert "8 silences out of 10" in signal.advice


@pytest.mark.parametrize("titre", CORPUS_TEMOIN)
def test_le_CORPUS_TEMOIN_n_est_PAS_accuse(titre):
    """An artifact of mine that is MENTIONED is not an admission; nor is an audit that finds
    ANOTHER's defect.

    What an admission really is: a DESTRUCTIVE verb whose object is mine ("falsified my clause"),
    or an audit verdict that names a falsehood. Not "my rule is in place."
    """
    assert detect_trace((Commit("abc1234", titre),)) == (), f"false positive on: {titre}"


@pytest.mark.parametrize("titre", VOCABULAIRE)
def test_le_vocabulaire_du_depot_n_est_PAS_un_aveu(titre):
    assert detect_trace((Commit("abc1234", titre),)) == (), f"false positive on: {titre}"


def test_MUET_sur_une_tache_qui_n_a_rien_avoue_ni_rien_ajoute():
    """The explicit clause of I4(b)'s stopping condition: *a detector that always talks says
    nothing.*"""
    commits = (
        Commit("aaa1111", "feat(A2): l'echelle d'obligation"),
        Commit("bbb2222", "chore(rangement): deplace deux fichiers"),
    )
    assert detect_trace(commits) == ()
    assert render_trace(detect_trace(commits)) == ""


# =================================================================================================
# `b2` IN PRODUCTION — the witness the orchestrator demands, on REAL commits
# =================================================================================================
#
# The witnesses above use MANUFACTURED titles. This one freezes four real commits from the
# repository, written by THREE different chats and by the orchestrator, that no pattern had ever
# seen when they were written. This is the only form of proof `b2` can receive: *a detector that
# always talks says nothing*, and silence cannot be proven on data chosen to stay quiet.
#
# MEASURED ON 2026-08-15 across the last 40 commits (`git log -40 --pretty=format:%s`):
#   2 fire · 38 stay SILENT  ->  firing rate 5%
# AND THE COMPLEMENT, FOR HONESTY: among the 38 silent ones, a manual read counts ~9 that ARE
# genuine admissions ("two defects opened by MY OWN fix," "I AM WITHDRAWING my own call," "chat 3
# corrected me"). Production recall is therefore of the same order as the one declared on the
# independent control corpus: ~2 out of 10.
# THIS IS NOT A REASON TO WIDEN — that would be the fifth iteration of the trap documented in
# `_est_un_aveu`'s docstring (0 false positives on every corpus owned, 30-40% on the first corpus
# never seen). *The limit is declared; a fresh measurement that CONFIRMS it is not a reason to
# reopen it.*
COMMITS_MUETS_REELS = (
    ("ef5a6b9", "chore(format): le reformatage de masse, ISOLE dans son propre fragment"),
    ("54587b1", "chore(chat-3): tour 12 -- G1 construit, et la FORME a ete mesuree avant d'etre imposee"),
    ("e34834f", "fix(E3): 127 lignes a chaque fin de tache -- la borne ne touche QUE les fichiers d'autrui"),
    ("2568500", "chore(postes): journal chat 2 -- A2 rendu OUI, et 30 conditions du plan sur 49"),
)


@pytest.mark.parametrize("sha, sujet", COMMITS_MUETS_REELS, ids=[s for s, _ in COMMITS_MUETS_REELS])
def test_b2_le_detecteur_est_MUET_sur_des_commits_REELS_sans_aveu_ni_item(sha, sujet):
    """THE CLAUSE THAT DECIDES, on production data rather than fixtures."""
    assert detect_trace((Commit(sha, sujet),)) == (), f"{sha} should not have triggered anything: {sujet}"
    assert render_trace(detect_trace((Commit(sha, sujet),))) == "", "and the block stays EMPTY"


def test_une_COMMANDE_ouvre_une_tache_meme_sans_rien_dire_de_citable():
    """Measured on the REAL transcript: 6 command invocations, 0 recognized as a boundary.

    A `/loop` arrives as a user turn whose text is ENTIRELY made of `<command-message>` /
    `<command-name>` / `<command-args>`: stripped down, nothing is left, and the predicate used to
    return False. The hook's window would then pull in **79 events** — three turns instead of one
    — so the E3 block and the ritual would fire on turns that were ENTIRELY read-only, and
    `detect_trace`'s window would span several tasks. *This undermined the clause that requires
    SILENCE on a task that did nothing.*

    These are TWO separate questions: "where does the task begin?" and "did the operator say
    something QUOTABLE?" A command answers YES to the first and NO to the second.
    """
    commande = {
        "type": "user",
        "isSidechain": False,
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": "<command-message>loop</command-message>\n"
                    "<command-name>/loop</command-name>\n"
                    "<command-args>Reread the session notes</command-args>",
                }
            ]
        },
    }
    assert is_task_boundary(commande), "a command OPENS a task"
    assert detect(( commande,)) == (), "but it has NO word to quote — detect always ignores it"
    # and the flip side: an empty turn that does NOT carry a command stays outside any boundary
    vide = {"type": "user", "isSidechain": False, "message": {"content": []}}
    assert not is_task_boundary(vide)


def test_MUET_sur_une_tache_SANS_AUCUN_commit():
    assert detect_trace(()) == ()


def test_une_FENETRE_TRONQUEE_parle_MEME_SANS_AUCUN_signal():
    """The only silence that LIES: having seen nothing because not everything was read.

    The truncation used to travel like a sentinel slipped into the population — with no item and
    no admission, it never crossed the judge, and the promise "a budget that NAMES what it drops"
    was false. It is now rendered, and it passes even when nothing else was detected.
    """
    assert render_trace((), 0) == ""
    rendu = render_trace(detect_trace(()), 3)
    assert "WINDOW TRUNCATED" in rendu and "3 commit(s)" in rendu


def test_un_item_ajoute_declenche_la_question_SPECIFIQUE():
    """"Did a lesson emerge?" is easy to dodge; "which one should have been there from the
    start?" is not."""
    signaux = detect_trace((Commit("ccc3333", "feat(plan): un item de plus", ("A6",)),))
    assert [s.kind for s in signaux] == ["item_ajoute"]
    assert "A6" in signaux[0].quote
    assert "should have been there from the start" in signaux[0].advice


def test_les_items_sont_DEDUPLIQUES_entre_commits():
    """The same item touched by three commits is ONE item added, not three."""
    signaux = detect_trace(
        (
            Commit("a", "feat: x", ("A6", "B1")),
            Commit("b", "fix: y", ("A6",)),
        )
    )
    assert signaux[0].quote == "A6, B1"


def test_la_liste_citee_est_BORNEE_et_DIT_ce_qu_elle_a_laisse():
    """The commit that CREATED this plan added 42 of them at once: a wall of names gets skipped
    over."""
    items = tuple(f"X{n}" for n in range(42))
    signaux = detect_trace((Commit("d", "feat(plan): nouveau cap", items),))
    assert "…and 36 others" in signaux[0].quote
    assert "42 item(s)" in signaux[0].advice, "the COUNT stays whole; only the QUOTE is bounded"


def test_une_CLOTURE_d_item_n_est_PAS_un_ajout():
    """THE BLOCKING DEFECT found by the isolated audit, measured across 120 commits.

 Closing an item REWRITES its line (`` becomes ``), so the diff carries it as a removal
 PLUS an addition. By reading only the `+` side, the detector used to mistake every closure for
 a birth: **30 tasks used to cry out, 22 wrongly (73%)**, and the block would assert the generic
 reminder "this task added N items" in their place. After subtracting: **8 cry out, 0 false, 0
 missed**, against a ground truth of 8. *A capture rate with no false-accusation rate is a
 WALL* — the very item that commands this detector writes that sentence itself, and the second
 figure had never been measured.
 """
    assert items_ajoutes(["- **D3** \U00002705 **done**"], ["- **D3** \U00002B1C **to do**"]) == ()
    assert items_ajoutes(["- **A6** \U00002B1C **new**"], ["- **D3** \U00002B1C **to do**"]) == ("A6",)
    assert items_ajoutes(["- **A6** \U00002B1C **new**"]) == ("A6",), "with no negative diff, nothing changes"


def test_le_lecteur_d_items_ne_lit_que_la_forme_d_un_item():
    ajoutees = [
        "- **A6** \U00002B1C **THE METHOD FOR BUILDING A PLAN**",
        "  *Produit* : the method section",
        "- a plain bullet, not an item",
        "## A heading",
        "- **B2** \U00002705 **already done**",
    ]
    assert items_ajoutes(ajoutees) == ("A6", "B2")


def test_les_deux_signaux_coexistent_et_l_item_passe_en_premier():
    """The order follows the cost: what was LEARNED before what was fixed."""
    signaux = detect_trace((Commit("e", AVEUX[4], ("I4",)),))
    assert [s.kind for s in signaux] == ["item_ajoute", "aveu"]
    rendu = render_trace(signaux)
    assert rendu.index("ITEM ADDED") < rendu.index("ADMISSION OF ERROR")
    assert "no model, no network" in rendu
