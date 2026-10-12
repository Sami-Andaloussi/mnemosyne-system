"""D155 — the end-of-task reflex: does the system NOTICE a lesson, or does it only remind?

The detector replaces a generic "think about capturing" with the operator's own quoted words.
Three ways that could go wrong, and this file holds all three shut:

* it fires on things the operator never said (the host's own sub-agent reports ride in as
  ``type: user``);
* it stays quiet on the turns that matter (the whole point);
* it becomes chatty enough to be tuned out — the failure mode of every nudge ever written.

The fixtures quote the real session of 2026-07-20, because a detector tuned on invented sentences
proves nothing about the sentences it will actually meet.
"""

from __future__ import annotations

import pytest

from mnemosyne.production.review_signals import DO_NOT_CAPTURE, detect, render_review


def _said(text: str, **extra: object) -> dict:
    return {"type": "user", "uuid": "u1", "message": {"role": "user", "content": text}, **extra}


def _kinds(events: list[dict], **kwargs: object) -> set[str]:
    return {signal.kind for signal in detect(events, **kwargs)}


# --- it fires on what actually happened ------------------------------------------------------
def test_the_sentence_that_cost_a_whole_day_is_detected() -> None:
    """Verbatim, 2026-07-20. The adverbs between "tu as" and "derivé" are why the verb stands alone."""
    assert "correction" in _kinds(
        [_said("on va compacter et reprendre dès le debut là tu as vraiment vraiment vraiment derivé")]
    )


def test_an_explicit_order_to_remember_is_the_least_ambiguous_signal() -> None:
    for phrase in ("garde ça", "retiens bien ça", "note ça", "grave ça", "range ça", "souviens-toi"):
        assert "consigne" in _kinds([_said(phrase)]), phrase


def test_the_repos_own_words_are_not_read_as_an_order_to_remember() -> None:
    """The measured over-fire: every marker now demands its object.

    In THIS repo "le Garde" is the reference monitor and "graver" is the verb for writing to
    the project's decisions log — 70 and 161 hits across 1 718 real turns, none of them asking to
    remember anything. A lexicon that fires on what the project is ABOUT is furniture within a week.
    """
    for phrase in (
        "le Garde refuse par defaut",
        "on garde le meme format",
        "il faut graver la decision dans le journal des decisions",
        "c'est pas grave, on continue",
        "range le depot avec make rangement",
    ):
        assert not detect([_said(phrase)]), phrase


def test_a_standing_preference_is_detected_apart_from_a_complaint() -> None:
    assert _kinds([_said("à l'avenir tu me demandes avant de lancer un run")]) == {"preference"}


# --- the calm disagreement: five sentences that were measured SILENT, frozen as witnesses --------
#
# 2026-08-14. On seven real pushbacks of one session the detector fired TWICE; these five are the
# silent ones, verbatim. Each changed a design — which is the whole argument: the corrections that
# cost the most are the ones the operator makes without raising their voice, so a detector
# calibrated on anger misses exactly the expensive half. They are frozen HERE, in the test file,
# because a
# witness that lives in a commit message is a memory, not a gate.
_WITNESSES_2026_08_14 = (
    "Ah non, attention, pas forcement. On s'adapte avec ce qu'on a.",
    "cette regle-la de 'avoir beaucoup de contexte c'est mauvais', pas forcement",
    "Je vois connaitre plus comme un OUTIL qu'un prerequis",
    "est-ce qu'on est bien d'accord que tout ce qu'on vient de capter sera bien applique",
    "faut aussi voir pourquoi ca a pas ete capte par le rituel et le hook",
)


def test_the_five_calm_corrections_that_used_to_pass_unnoticed() -> None:
    """0 of 5 before 2026-08-14. Each one asserted SEPARATELY: a loop over a tuple that stops on
    the first failure would report one hole where there are five, and the count is the point."""
    silent = [phrase for phrase in _WITNESSES_2026_08_14 if "desaccord" not in _kinds([_said(phrase)])]

    assert not silent, f"{len(silent)} witness(es) still unheard: {silent}"


def test_a_calm_disagreement_is_not_filed_as_an_angry_one() -> None:
    """The label is the payload. Folding these into ``correction`` would have cost nothing to build
    and taught nothing: "they pushed back" is what I already notice; "they pushed back WITHOUT
    raising their voice" is the case I demonstrably do not."""
    assert _kinds([_said("Ah non, pas forcement, on s'adapte")]) == {"desaccord"}

    block = render_review(detect([_said("Ah non, pas forcement")]))
    assert "CALM DISAGREEMENT" in block
    assert "CORRECTION of the work" not in block


def test_each_calm_marker_is_pinned_by_a_sentence_of_its_own() -> None:
    """Deleting any ONE marker must turn this file red — and SIX of them used to survive.

    A per-branch ablation of ``_DISAGREEMENT_RE`` first showed four survivors: ``fais attention``,
    ``attention,``/``attention à``, ``faut aussi``, ``t'es sûr``. The five frozen witnesses each
    trip TWO markers, so the tuple proved the SENTENCES were caught, never that each MARKER earns
    its place. A marker no test holds is a marker the next tidy-up deletes for free.

    **Then an isolated audit found two more, and found my ablation lying about them.** Deleting the
    first line of the pattern takes the opening ``(`` with it, so the module stops IMPORTING — my
    harness read that as "the tests caught it". It was the compiler answering, not the tests. Under
    a mutation that keeps the regex valid (each alternative → a literal that never matches), the
    true score was **9 of 10 lines and 10 of 12 alternatives**: ``Non…`` opening a turn and
    ``ah non`` were both unheld — the branch the module cites as its own archetype, worth 13 of the
    127 new turns. Whence the two last phrases below, and whence the rule: a sabotage that fails to
    compile measures the compiler.

    Each sentence is written to trip exactly ONE branch — the only shape in which a survivor becomes
    a failure — and each is modelled on a real turn of ``sessions.db`` (the last two are verbatim).
    They are NOT all lifted from it: an earlier version of this docstring claimed they were, which
    could not be true of the reframing branch, measured at zero hits over the 1 605 turns.
    """
    for phrase in (
        "il faut faire tres attention avec ce fichier",  # fais/faut/faire + attention
        "juste attention, ces phases doivent prendre en compte l'environnement",  # attention,
        "attention aux doublons dans le plan",  # attention à / au / aux
        "faut aussi prendre en compte l'usage des 52 validateurs",  # faut aussi
        "est-ce que t'es sur de pas avoir oublie P1 a P6",  # t'es sûr
        "je le vois plutot comme un outil que comme un prerequis",  # the reframing
        "au contraire, il ne faut pas tomber dans ce piege",  # au contraire
        "Non, tu fais que du haiku, jamais du sonne.",  # verbatim — the opening rebuttal
        "et pas etre categoriquement, ah non s'il est dans ca il n'est pas dans ca",  # verbatim
        "le probleme, c'est qu'on decrivait la V1 de facon bien trop breve",  # the named objection
    ):
        assert "desaccord" in _kinds([_said(phrase)]), phrase


def test_the_calm_kind_never_swallows_the_angry_one() -> None:
    """A turn that is BOTH must render both: the loud sentence is still the strongest evidence."""
    kinds = _kinds([_said("pourquoi tu pars en vrille, ah non, pas forcement")])

    assert kinds == {"correction", "desaccord"}


def test_disbelief_punctuation_is_read_as_pushback() -> None:
    """Verbatim. No other marker sees this turn, and it was the last warning before the blow-up."""
    assert "correction" in _kinds([_said("elle a pas deja ete faite?? on peut pas run sans ???")])


def test_every_signal_carries_the_words_that_caused_it() -> None:
    """A block that asserts a signal with nothing quoted is what the audit deleted.

    The removed ``detour`` kind claimed "a tool failed then eventually passed" while the code only
    ever saw the failure, under a header promising "these are the operator's words" with no words —
    196 of
    1 048 real tasks showed exactly that and nothing else. No kind may reintroduce it.
    """
    signals = detect([_said("pourquoi tu pars en vrille"), _said("garde ça"), _said("à l'avenir demande")])

    assert signals
    assert all(signal.quote.strip() for signal in signals)


# --- it does NOT fire on what the operator did not say ------------------------------------------
def test_the_hosts_own_subagent_report_is_never_read_as_the_operator_speaking() -> None:
    """Measured: 783 of these in 20 transcripts, filed as ``type: user``. Left in, the detector
    fires on the system quoting itself — which is how a nudge becomes furniture."""
    assert not detect(
        [_said("<task-notification><summary>pourquoi tu pars en vrille</summary></task-notification>")]
    )


def test_a_hook_reminder_inside_a_user_message_is_not_a_correction() -> None:
    assert not detect([_said("<system-reminder>arrête et relis CLAUDE.md</system-reminder>")])


def test_a_delegated_subagents_prompt_is_not_the_operator() -> None:
    assert not detect([_said("pourquoi tu pars en vrille", isSidechain=True)])
    assert not detect([_said("pourquoi tu pars en vrille", isMeta=True)])


def test_an_assistant_turn_is_never_mined_for_signals() -> None:
    """Otherwise the system detects a lesson in its own apology and captures a fact about itself."""
    assert not detect(
        [{"type": "assistant", "message": {"role": "assistant", "content": "pourquoi tu pars en vrille"}}]
    )


def test_ordinary_instructions_stay_silent() -> None:
    """Verbatim from the same session — turns 0 to 10, none of which carried a lesson."""
    for phrase in (
        "envoie un audit pour evaluer qu'est ce qui pourrait etre valuable pour mnemosyne",
        "vas-y sur le tier 1",
        "commit",
        "prepare pour le compacte. on /compact. puis on enchaine post ce dernier",
    ):
        assert not detect([_said(phrase)]), phrase


def test_the_markers_the_2026_08_14_count_threw_out_stay_out() -> None:
    """The barrier under the rule "measure on the real population before adding a marker".

    Each phrase below was a CANDIDATE for the calm-disagreement lexicon and was rejected on a count
    over the 1 605 real turns of ``sessions.db``: ``mais`` 538 hits, ``en fait`` 290, ``attends``
    75 (mostly "j'attends la fin du run", five of them the operator pasting an agent report back),
    ``faux``
    37 (this repo's own audit vocabulary), ``comment ça`` 18 (one is a pasted YouTube transcript),
    ``plutôt que`` 28 (half pasted agent prose). Without this test, the next session re-adds them
    from intuition — which is exactly how ``encore une fois`` (136 hits) got in the first time.
    """
    for phrase in (
        "mais du coup on enchaine sur le rangement",
        "en fait je pense qu'on peut lancer le run maintenant",
        "j'attends la fin du run avant de te repondre",
        "le rapport dit que le fait est devenu faux, corrige la fiche",
        "explique-moi comment ca marche stp",
        "utilise un agent local plutot que la frontiere",
    ):
        assert not detect([_said(phrase)]), phrase


def test_agreeing_out_loud_is_not_a_disagreement() -> None:
    """``on est d'accord SUR ça`` was measured and dropped: it fires on the operator SEALING a
    decision and on plain assent. The challenge form they actually use carries a ``?`` or a
    ``que``."""
    assert not detect([_said("on est bien d'accord sur ca, c'est scelle")])
    assert not detect([_said("si on est d'accord sur les deux, tu peux compacter")])

    assert "desaccord" in _kinds([_said("est-ce qu'on est bien d'accord ?")])
    assert "desaccord" in _kinds([_said("on est d'accord qu'on casse pas un document trop long")])


def test_a_question_about_MY_work_fires_where_a_question_about_ME_already_did() -> None:
    """``pourquoi tu`` was the only "pourquoi" the detector knew, and the operator mostly asks
    about the WORK: *"pourquoi on lance un run de six heures ?"*. The pronoun is the first
    distinction."""
    assert "desaccord" in _kinds([_said("pourquoi on lance un run de six heures ?")])
    assert "desaccord" in _kinds([_said("je comprends pas pourquoi ca bloque")])


def test_a_bare_pourquoi_stays_out_because_the_repos_own_prose_is_full_of_it() -> None:
    """The audit's measurement, on this module's own criterion: a bare ``pourquoi ça/on/c'est``
    fired **35 times in the operator's turns against 150 in the assistant prose they paste back** —
    dirtier than three markers this file threw out as repo vocabulary. Demanding the first-person doubt or
    a question mark in the same sentence keeps 17 of the 20 turns and drops the assistant count to
    one. Without this test the wider form comes back, since it reads as the more generous choice."""
    assert not detect([_said("le rapport explique pourquoi on garde deux registres separes")])
    assert not detect([_said("voici pourquoi c'est la bonne architecture pour ce module")])


def test_the_repos_own_term_of_art_is_not_a_complaint() -> None:
    """``anti-dérive`` is what this repo calls a prompt drifting from its source. It is a noun here,
    not a reproach — and it appears in the very skills whose work triggers this hook."""
    assert not detect([_said("le skill applique sa regle anti-derive a lui-meme")])


# --- it stays small enough to keep being read -------------------------------------------------
def test_one_turn_yields_at_most_one_signal_per_kind() -> None:
    """Four phrasings of the same complaint are one complaint. Quoting each would bury the rest."""
    events = [_said("arrête ça, pourquoi tu pars en vrille, n'importe quoi, putain")]

    assert len(detect(events)) == 1


def test_the_strongest_kinds_come_first() -> None:
    events = [
        _said("pourquoi tu pars en vrille"),
        _said("à l'avenir demande"),
        _said("garde ça"),
        _said("ah non, pas forcement"),
    ]

    kinds = [signal.kind for signal in detect(events)]

    # explicit order outranks inferred; the calm kind sits under the loud one, never above it
    assert kinds == ["consigne", "correction", "desaccord", "preference"]


def test_the_first_occurrence_is_what_gets_quoted() -> None:
    """A complaint made twice is quoted where it STARTED — the later restatement is the echo, and
    quoting the echo strips the context that explains it."""
    events = [_said("pourquoi tu pars en vrille sur le RAG"), _said("pourquoi tu pars en vrille encore")]

    (signal,) = [s for s in detect(events) if s.kind == "correction"]

    assert "sur le RAG" in signal.quote


def test_a_short_turn_is_quoted_whole_rather_than_windowed_three_times() -> None:
    """Three windows of one sentence read like a bug and hide that it was a single turn.

    The fixture puts the match at the very END of a message that only just fits: that is the only
    place where quoting-whole and windowing disagree, so a shorter fixture would pass either way.
    """
    text = "on avance sur le rangement du depot " * 5 + "et pourquoi tu pars en vrille"
    assert 150 < len(text) <= 220  # inside the quote budget, match near the far edge

    quotes = {signal.quote for signal in detect([_said(text)])}

    assert quotes == {text}


def test_a_long_turn_is_windowed_on_word_boundaries() -> None:
    text = "bla " * 200 + "pourquoi tu pars en vrille" + " bla" * 200
    (signal,) = detect([_said(text)])

    assert "pourquoi tu pars en vrille" in signal.quote
    assert signal.quote.startswith("…") and signal.quote.endswith("…")
    assert " bla bl" not in signal.quote[-8:]  # no half-word at the seam


# --- the rendered block ------------------------------------------------------------------------
def test_no_signal_renders_nothing_at_all() -> None:
    """Silence is the inverted half of Hermes's design and the reason this can stay switched on."""
    assert render_review(()) == ""


def test_the_block_quotes_the_operator_and_carries_the_do_not_capture_rules() -> None:
    block = render_review(detect([_said("pourquoi tu pars en vrille comme ça")]))

    assert "pourquoi tu pars en vrille comme ça" in block
    assert "DO NOT CAPTURE" in block
    assert "hardens into refusals" in block  # the ported reasoning, not just the rule
    assert "make remember" in block  # it says where the lesson goes
    assert "silence is a valid result" in block  # capturing nothing stays legitimate


def test_the_do_not_capture_list_keeps_the_rule_that_matters_most() -> None:
    """A negative claim about a tool is the one that quietly disables the system months later."""
    assert any("NEGATIVE" in rule and "refusals" in rule for rule in DO_NOT_CAPTURE)


def test_an_empty_or_malformed_transcript_is_survivable() -> None:
    assert not detect([])
    assert not detect([{"type": "user"}, {"type": "user", "message": None}, {}])


# --- what three audit-surviving mutations proved was unpinned ---------------------------------
def test_a_compaction_summary_is_not_mined_as_if_the_operator_had_said_it() -> None:
    """A compact summary restates the conversation in MY words, attributed to a user event."""
    assert not detect([_said("pourquoi tu pars en vrille", isCompactSummary=True)])


def test_the_quote_budget_actually_binds() -> None:
    """A budget nothing tests is a number, not a bound: raising it must change the output."""
    from mnemosyne.production.review_signals import _QUOTE_LEN

    text = "x " * 400 + "pourquoi tu pars en vrille"
    (signal,) = detect([_said(text)])

    assert len(signal.quote) <= _QUOTE_LEN + 2  # + the two ellipses
    assert len(signal.quote) < len(text)


def test_the_quote_never_opens_mid_word_nor_past_its_own_trigger() -> None:
    """The audit's shape: the forward snap could slide the window PAST the phrase it was quoting,
    leaving the block offering as evidence an excerpt without the trigger in it."""
    # A long UNBROKEN run before the trigger: the first space after the window start then falls
    # AFTER the trigger, which is the only shape where an unclamped forward snap slides past it.
    text = "a" * 250 + " " + "b" * 90 + "pourquoi tu pars en vrille sur le RAG" + " et la suite ici"
    (signal,) = detect([_said(text)])

    assert "pourquoi tu pars en vrille" in signal.quote

    # Counter-proof: when a boundary DOES exist before the trigger, the quote still opens on it.
    spaced = "mot " * 90 + "pourquoi tu pars en vrille" + " et la suite de la phrase ici"
    (other,) = detect([_said(spaced)])
    assert other.quote.lstrip("…").startswith("mot ")


def test_each_kind_renders_its_own_label_and_its_own_advice() -> None:
    """The labels ARE the actionable content; replacing them all with "x" used to pass every test."""
    block = render_review(detect([_said("pourquoi tu pars en vrille"), _said("garde ça")]))

    assert "EXPLICIT INSTRUCTION" in block and "CORRECTION" in block
    assert "the least debatable case" in block  # the consigne advice
    assert "the rule that would have avoided it" in block  # the correction advice


def test_the_task_boundary_is_the_same_predicate_the_detector_uses() -> None:
    """The hook and the detector disagreed: a <task-notification> opened a task for one and was
    invisible to the other, so in 433 of 1 048 real tasks the window began after the operator's
    prompt."""
    from mnemosyne.production.review_signals import is_task_boundary

    assert is_task_boundary(_said("fais le rangement"))
    assert not is_task_boundary(_said("<task-notification><summary>fini</summary></task-notification>"))
    assert not is_task_boundary(_said("pourquoi tu pars en vrille", isSidechain=True))
    assert not is_task_boundary({"type": "assistant", "message": {"role": "assistant", "content": "x"}})


# =================================================================================================
# THE BLIND ADVERSARIAL CORPUS — 54 turns written by an ISOLATED agent, never by the module's author.
# =================================================================================================
#
# Every other test above is white-box: written by someone who already knew the four regexes, so it
# proves the code does what its author intended — never whether an independent reader would tag the
# same turns the same way. Chat 2 measured this gap directly on `detect()` (I4) and refused to close
# it alone: "an 'independent' corpus that I wrote myself, knowing the code, would not be independent
# — the very fault D75 exists to prevent." This is that corpus, commissioned instead from an
# agent explicitly forbidden from opening this file, `test_trace_signals.py`, or searching for any
# of the four pattern names. It labelled each turn from five plain-French definitions alone
# (consigne / correction / desaccord / preference / rien) — no rate, high or low, was announced in
# its mandate, on the exact lesson this repo already paid for: a stated expectation biases the
# labeller toward the mandator's error.
#
# PUBLISHED RATES, verified below by :func:`test_the_blind_corpus_rates_are_exactly_what_is_measured`
# rather than hand-typed — nothing here is rounded, sampled, or quietly re-balanced after the fact:
#
#   40 signal-bearing turns : **11 caught / 40 (27.5 %)**, 29 MISSED
#   14 "rien" turns         : **13 correct / 14 (92.9 %)**, 1 false positive
#   54 total                : **24 correct / 54 (44.4 %)**
#
# **THIS IS WORSE THAN ANY RATE THIS MODULE HAS EVER PUBLISHED**, and that is the point: every
# earlier number here was measured against the SAME real corpus (``sessions.db``) that shaped the
# regexes — self-labelled by whoever tuned them, the exact circularity D75 exists to break. Most
# misses are natural paraphrases just outside the fixed vocabulary — "note bien quelque part que" is
# not "note ça"; "garde en tête que" is not "garde ça"; "je ne suis pas sûr que" is nowhere in
# :data:`_DISAGREEMENT_RE`. None of that is a bug in this test: it is the gap the mandate asked to find.
#
# **The one false positive is not new** — turn 45, "Sérieux ?? T'as fait tout ça en même pas une
# heure ??", fires on the same disbelief-punctuation marker (``??``) the module's own docstring
# already names and accepts ("ça te va??"). An agent that never saw that admission independently
# rediscovered the same failure shape from the category definitions alone — evidence the corpus is
# measuring something real, not noise.
#
# **NOTHING BELOW IS EVER SILENTLY WIDENED.** The 29 misses and the 1 false positive are frozen by
# index, not hidden: each is a named debt (see :data:`MISSED_INDICES` / :data:`FALSE_POSITIVE_INDICES`),
# and the tests that pin them FAIL the day the detector starts catching one — forcing a re-measure of
# the false-positive rate before the gain is banked, on the same principle ``test_trace_signals.py``
# already established for the module's other half.
BLIND_CORPUS = (
    ('rien', 'Est-ce que tu peux vérifier si le serveur tourne toujours ?'),
    ('consigne', "Souviens-toi que le client s'appelle toujours « Aurore » dans nos échanges, jamais le vrai nom de la boîte."),
    ('desaccord', 'Je ne suis pas sûr que ce soit la bonne approche pour la base, on pourrait regarder une alternative avant de trancher.'),
    ('correction', "Non mais c'est pas du tout ce que je voulais, tu es reparti sur l'ancienne version du plan, recommence."),
    ('preference', "À l'avenir, préviens-moi des implications de chaque option avant de me demander de trancher, pas juste la liste brute."),
    ('rien', "Au fait, c'est quoi la différence entre un commit et un push déjà, je m'en souviens plus."),
    ('consigne', 'Note bien quelque part que le serveur de prod redémarre tout seul tous les dimanches à 3h, sinon on va se faire avoir.'),
    ('desaccord', "Attention à cette histoire de cache, je crois qu'on avait eu un souci similaire il y a quelques mois."),
    ('correction', "Franchement je suis déçu là, ça fait trois fois que je te demande la même chose et t'as encore fait l'erreur."),
    ('preference', "Systématiquement, quand tu touches à un fichier de config, précise-le dans ton résumé, même si c'est mineur."),
    ('rien', 'Nickel, ça marche, merci !'),
    ('consigne', "Garde en tête que j'ai rendez-vous chez le comptable jeudi après-midi, je serai moins disponible."),
    ('desaccord', "Hmm, j'ai un petit doute sur le nom choisi pour ce module, tu es sûr que ça colle bien à ce qu'on fait ?"),
    ('correction', "Ça ne va pas du tout, t'as touché à la config sans me prévenir, remets ça comme c'était."),
    ('preference', "Dorénavant, écris-moi toujours en français, même dans les commentaires quand c'est possible."),
    ('rien', "En fait, pendant que j'y pense, faudrait qu'on regarde la facture Stripe du mois dernier à un moment."),
    ('consigne', "N'oublie pas qu'on avait déjà tenté ce coup du cache Redis en mars, ça avait mal tourné."),
    ('desaccord', "Je nuancerais un peu ce que tu proposes, ça me semble tôt pour migrer tout le système d'un coup."),
    ('correction', "Stop, c'est complètement à côté de la plaque, je voulais un résumé d'une page, pas dix."),
    ('preference', "J'aimerais que désormais tu évites de me donner plusieurs plans à la fois, un seul à chaque fois ça me suffit."),
    ('rien', "Mais du coup, tu penses qu'on aura fini avant vendredi ?"),
    ('consigne', "Tiens, ça vaudrait le coup que tu gardes ça de côté pour plus tard : le budget max sur l'API c'est 200 euros par mois."),
    ('desaccord', "Mouais, pourquoi pas, même si j'aurais peut-être fait autrement à ta place."),
    ('correction', "Alors là non, tu as supprimé le fichier que je t'avais dit de garder, c'est l'inverse de ce qu'il fallait faire."),
    ('preference', "De manière générale, je préfère qu'on committe petit à petit plutôt que d'attendre la fin de journée."),
    ('rien', "Ça n'a pas l'air si compliqué que ça finalement, on peut continuer comme ça."),
    ('consigne', "Retiens bien ce nom, Clémentine, c'est elle qui reprend le dossier facturation a partir de la semaine prochaine."),
    ('desaccord', 'On pourrait aussi regarder ça sous un autre angle, non ? Juste une idée, pas obligé de la suivre.'),
    ('correction', "Bon... c'est pas vraiment ce qu'on avait dit hein, ça commence à bien faire ces approximations."),
    ('preference', "Ça m'aide beaucoup quand tu commences par le résumé avant les détails, essaie de garder ce réflexe à chaque fois."),
    ('rien', "Tu peux lancer les tests s'il te plaît ?"),
    ('consigne', "Tu veux bien te souvenir d'un truc pour la suite : c'est toujours moi qui touche aux clés de prod, jamais toi tout seul."),
    ('desaccord', 'Petit bémol quand même sur la partie tests, je trouve ça un peu léger pour un truc aussi sensible.'),
    ('correction', 'Tu sais quoi, laisse tomber, je vais le refaire moi-même.'),
    ('preference', 'Pour toutes les prochaines fois, donne-moi une estimation de temps avant de démarrer un gros chantier.'),
    ('rien', "Génial, exactement ce qu'il fallait !!"),
    ('consigne', "Mets ça de côté dans un coin : je pars trois semaines fin septembre, faudra un plan d'avance pour cette période-là."),
    ('desaccord', 'Je me demande si on ne devrait pas garder les deux versions en parallèle un moment, plutôt que trancher tout de suite.'),
    ('correction', "C'est raté, ce script casse tout en prod, reviens en arrière tout de suite s'il te plaît."),
    ('preference', "Autant qu'on prenne ce pli tout de suite : chaque fois que tu touches à un truc sensible, un petit message avant, même court."),
    ('rien', "Le mot de passe du wifi du bureau c'est changeme2025, au cas ou t'en as besoin."),
    ('consigne', "Écris-toi quelque part que la clé que je t'ai filée hier c'est celle de test, pas celle de prod."),
    ('desaccord', "C'est peut-être moi qui me trompe, mais j'ai l'impression que cette hypothèse sur les utilisateurs n'a jamais été vérifiée."),
    ('correction', "Non, non et non, on avait dit qu'on gardait l'ancien nom, pourquoi tu l'as changé quand même ?"),
    ('preference', "J'aime bien cette façon de faire, garde-la pour les prochaines fois aussi, les options d'abord et le détail après."),
    ('rien', "Sérieux ?? T'as fait tout ça en même pas une heure ??"),
    ('consigne', "Faut que tu retiennes ce détail : le nom de domaine expire en janvier, on n'a pas encore renouvelé."),
    ('desaccord', "Ça peut marcher tel quel, mais je serais plus prudent avant de l'annoncer comme réglé."),
    ('correction', "J'avoue que là ça m'énerve un peu, le bug que je t'ai signalé hier est encore présent ce matin."),
    ('preference', "En règle générale évite de me réveiller avec des questions le matin, tu peux les garder pour l'après-midi."),
    ('rien', "Le serveur redémarre toujours vers 3h du matin, c'est comme ça depuis le début du projet."),
    ('rien', 'Ah au fait, ma fille a eu son bac hier, elle est trop contente.'),
    ('rien', "Ce n'est pas la peine de relancer les tests tout de suite, on verra ça après le déjeuner."),
    ('rien', 'Tu crois que ça vaut le coup de passer sur un nouvel hébergeur un jour, juste par curiosité ?'),
)

#: 0-based indices into :data:`BLIND_CORPUS` where a real signal exists and `detect` MISSES it.
#: Frozen as an owed debt, never silently closed — see the class docstring above.
MISSED_INDICES = (2, 6, 8, 11, 13, 16, 17, 18, 21, 22, 23, 27, 28, 29, 31, 32, 33, 34, 36, 37, 38, 39, 41, 42, 44, 46, 47, 48, 49)

#: 0-based index where `detect` wrongly fires on a "rien" turn — the disbelief-``??`` marker this
#: module's own docstring already names and accepts.
FALSE_POSITIVE_INDICES = (45,)


def _corpus_signals() -> list[tuple[int, str, str]]:
    return [(i, e, t) for i, (e, t) in enumerate(BLIND_CORPUS) if e != "rien"]


def _corpus_nothings() -> list[tuple[int, str, str]]:
    return [(i, e, t) for i, (e, t) in enumerate(BLIND_CORPUS) if e == "rien"]


@pytest.mark.parametrize("i", [i for i, _, _ in _corpus_signals() if i not in MISSED_INDICES])
def test_the_blind_corpus_signals_detect_DOES_catch(i: int) -> None:
    label, text = BLIND_CORPUS[i]
    assert label in _kinds([_said(text)]), f"[{i}] {text!r}"


@pytest.mark.parametrize("i", MISSED_INDICES)
def test_the_blind_corpus_MISSES_are_frozen_as_an_owed_debt(i: int) -> None:
    """A named hole, held open by a test. The day one of these starts firing, THIS test fails —
    forcing a re-measure of the false-positive rate before the gain is banked in silence, exactly
    what ``test_trace_signals.py`` already does for the module's other half."""
    label, text = BLIND_CORPUS[i]
    assert label not in _kinds([_said(text)]), (
        f"CAUGHT UP [{i}] {text!r} — re-measure the false-positive rate on the whole corpus before "
        "removing this index from MISSED_INDICES, or the gain is banked without its cost."
    )


@pytest.mark.parametrize("i", [i for i, _, _ in _corpus_nothings() if i not in FALSE_POSITIVE_INDICES])
def test_the_blind_corpus_riens_are_NOT_accused(i: int) -> None:
    label, text = BLIND_CORPUS[i]
    assert _kinds([_said(text)]) == set(), f"[{i}] {text!r}"


@pytest.mark.parametrize("i", FALSE_POSITIVE_INDICES)
def test_the_blind_corpus_known_false_positive_is_frozen(i: int) -> None:
    """Same shape as the missed signals, mirrored: a known wrong answer, held open rather than
    hidden, so a fix has to be deliberate and re-measured, never an accidental side effect."""
    label, text = BLIND_CORPUS[i]
    kinds = _kinds([_said(text)])
    assert kinds == {"correction"}, f"[{i}] {text!r} — now {kinds}"


def test_the_blind_corpus_rates_are_exactly_what_is_measured() -> None:
    """The published rates in the class docstring above are DERIVED here, not hand-typed — the exact
    trap this repo has paid for before: a number quoted next to a measurement it did not come from."""
    signals = _corpus_signals()
    nothings = _corpus_nothings()
    missed = {i for i, label, text in signals if label not in _kinds([_said(text)])}
    false_positives = {i for i, label, text in nothings if _kinds([_said(text)])}
    assert missed == set(MISSED_INDICES)
    assert false_positives == set(FALSE_POSITIVE_INDICES)
    assert len(signals) == 40 and len(nothings) == 14 and len(BLIND_CORPUS) == 54
