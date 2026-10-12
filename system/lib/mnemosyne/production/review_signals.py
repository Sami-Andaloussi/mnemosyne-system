"""Learning-signal detector (D155) — the half of Hermes's self-improvement loop worth having.

``NousResearch/hermes-agent`` (MIT © 2025 Nous Research, SHA ``3ef6bbd``) forks a clone of itself
after every turn and asks it "should anything be saved?". The fork is plumbing; the VALUE is the
~100-line prompt it hands that clone (``agent/background_review.py``), which is a taxonomy of what
counts as a learning, an order of preference for where to put it, and — the part nobody else
writes — a list of what must NOT be captured.

Their fork does not transpose: our reviewer is the frontier already in the conversation, and the
transcript is full of the operator's words, so it may not be shipped to a second model by automatism
(invariant 1, and there is no local brain installed on this machine anyway). What DOES transpose is
better than a fork: **detect the signal in code, then name it.** The hook already fires at the right
boundary; until now it injected a generic "remember the ritual". Injecting *"the operator corrected
you at this turn, here are their words"* is a different object — the system finds the learning, and I can
only decide what to do with it, not whether to look.

Two deliberate inversions of their design:

* **Silence is the default.** Hermes tells its clone "a pass that does nothing is a missed learning
 opportunity" — right for a product that must look alive, wrong here, where every capture spends
 the operator's attention on a validation queue (``calibrate-validation-rarity``). No signal ⇒ no block.
* **We detect, we never decide.** A signal is an INVITATION to run ``make remember``; nothing here
 writes to memory. Propose, never impose (D92) is not weakened by making the proposal sharper.

**Honest about what this is, with the counter-example first.** It is regex over French prose, so it
over-fires: on the session of 2026-07-20 it reads ``"ça te va??"`` — the operator checking that a
plan suits me — as a CORRECTION, because doubled question marks are otherwise the best evidence of pushback
available (they are what catches ``"elle a pas deja ete faite??"``, which no other marker sees).
That is accepted because the cost matrix is lopsided: a false positive costs one ignored line, a
false negative costs a lesson already paid for in the operator's patience.

What it DID do on that session, measured over its 17 real turns: silent on turns 0-10 (ordinary
instructions), firing on 11-16 — the entire stretch where the day went off the rails. The shape is
the point, not the hit rate.

**And it was DEAF to a calm correction until 2026-08-14** — measured, 2 of 7, see
:data:`_DISAGREEMENT_RE`, which is the fix and which publishes what the fix costs.

**It STILL misses a correction phrased as a deliberation** — *"je pense qu'il vaudrait mieux…"*.
This admission was deleted along with the deafness it described, which was wrong twice over: the
hole is not closed (that exact sentence is silent for all four kinds, checked), and an admission
removed without its fix reads as a fix. It is left open deliberately, on a measurement rather than
on a shrug: ``il vaut / vaudrait mieux`` covers 23 turns of which 7 are silent, and reading those
seven shows six are the operator weighing two options and handing me the choice. Buying them would
buy noise. **An admission is a free and valid answer; a silently deleted admission is not.**

**And nothing here guards against the operator quoting someone else.** The detector reads their
turn whole, so a report they paste back is read as their words: the probe
``"VOILA CE QUI A ETE RENVOYE :\n- Attention, …"`` fires. Measured on the real corpus, **0 of the
127 new firings** are anchored inside a pasted block (123 of 1 605 turns carry pasted structure,
none of them under an anchor) — but that zero is a property of the operator dictating by voice,
**not a barrier**. If that ever changes, this is where it breaks first.

**The other half — MY OWN trace — is here since 2026-08-14 (I4 clause b).** :func:`detect` reads
the operator's turns and nothing else: a method that worked, a measurement that found something, an
item I added to the plan mid-task because I had just learnt something — none of that is in their words, so no
regex over THEIR turns will ever reach it. :func:`detect_trace` reads the other side, and it reads it
in ``git``: **no transcript moves, no model is called, no network is touched** (invariant 1 is about
shipping a transcript to a SECOND model by automatism — reading my own commits is not that).

**What the trace half does NOT buy, and it must be written.** These signals detect that
SOMETHING HAPPENED, never WHAT. The judgement stays with the agent. *A detector that names the
moment beats a reminder that names the virtue — but it thinks for nobody.*

**The DO-NOT-capture list is ported almost verbatim**, because their reasoning is the best argument
in the repo: a negative claim about a tool *"hardens into refusals the agent cites against itself
for months after the actual problem was fixed"*. That is the exact failure mode already recorded
here as ``no-rigidity-corpus-complements`` — someone else hit it and wrote the guard rail.

**HARDENING (2026-08-16, D75, I4).** Every test above this line is white-box, written by
someone who already knew these four patterns — it proves the code does what its author intended,
never whether an independent reader would tag the same turns the same way. :func:`detect` was
**UNPROVEN** on that measure until a corpus of 54 turns, written by an agent explicitly forbidden
from opening this file and given only the five category names in plain French, was run against it —
frozen verbatim in ``tests/orchestration/test_review_signals.py``. **Real numbers, published even
though they are bad:** 11 of 40 signal-bearing turns caught (27.5 %), 13 of 14 "rien" turns correctly
silent (1 false positive, itself the already-known ``??`` disbelief marker). Most misses are natural
paraphrases just outside the fixed vocabulary — "note bien quelque part que" is not "note ça". This
is worse than any rate this module has published before, because every earlier one was measured
against the same corpus that shaped the regexes — the circularity D75 exists to break.

Decisions: D155 (this) · D92 (propose, never impose) · invariant 1 (a transcript stays local) ·
D117 (code and everything it prints are English). **The DETECTION PATTERNS below stay French, and
that is not an oversight: they are matched against the operator's own turns, which are written in
French.** Translating one would not translate the corpus — it would simply stop matching. Pure
stdlib (D126).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

#: A quoted excerpt is trimmed to this — enough to recognise the moment, never a wall of text.
#:
#: (A ``_MAX_SIGNALS = 4`` cap used to sit here. The audit showed it was **unreachable**: there were
#: three kinds and at most one signal per kind, so the slice never cut anything and the test
#: asserting ``len(...) <= 4`` could not fail. A bound that cannot bind is not a guarantee, it is a
#: comment pretending to be one — removed rather than left to be trusted. There are FOUR kinds
#: since 2026-08-14, which is precisely why the removed cap must not be restored from memory: at
#: four it would start cutting, silently, the kind that sorts last.)
_QUOTE_LEN: Final = 220


@dataclass(frozen=True, slots=True)
class Signal:
    """One detected learning opportunity: what kind, in the operator's own words, and what to do."""

    kind: str
    quote: str
    advice: str


#: The four kinds, strongest first. Order is the display order of the rendered block.
#:
#: A fifth kind, ``detour`` ("a tool failed then eventually passed"), was built and **removed** by
#: the audit. Two reasons, and the second is the one that matters: the hook only ever saw the
#: FAILURE — nothing anywhere checked that a later call succeeded, so the rendered line asserted a
#: fact the code never established, under a header promising "these are the operator's words" with no
#: words quoted (196 of 1 048 real tasks fired that and nothing else). And it contradicted the
#: :data:`DO_NOT_CAPTURE` list shipped in the same block: *"a TRANSIENT error resolved before the
#: end of the task — if retrying was enough, the lesson is the retry, not the breakage."* A signal
#: whose own rules forbid capturing it is not a signal.
#:
#: ``desaccord`` is the 2026-08-14 addition and it is a SEPARATE kind on purpose, not extra
#: alternatives bolted onto :data:`_CORRECTION_RE`. The two say different things to the reader:
#: a correction means the operator pushed back and I noticed; a calm disagreement means they
#: contradicted me *without raising their voice*, which is precisely the case I did not notice — so the block has to
#: name that, or it teaches nothing the louder label already teaches.
_KIND_ORDER: Final = ("consigne", "correction", "desaccord", "preference")

#: An EXPLICIT order to retain. The least ambiguous signal there is — the operator is telling the
#: system to remember, in so many words.
#:
#: **Every marker demands its object**, and that is the audit's correction, measured: the first
#: version allowed a bare ``\bgarde\b`` (the object group was optional) and a bare ``grave[rs]?\b``.
#: In this repo **"le Garde" is the reference monitor** and **"graver" is the verb for writing to
#: the project's decisions log** — 70 and 161 hits respectively across 1 718 real turns, none of them
#: a request to remember anything. The lexicon must fire on what the operator ASKS, never on what the
#: project is ABOUT.
_INSTRUCTION_RE: Final = re.compile(
    r"(garde[ -](?:ça|ca|moi ça|moi ca)\b"
    r"|grave[ -](?:ça|ca)\b|range[ -](?:ça|ca)\b|note[ -](?:ça|ca)\b"
    r"|retiens[ -](?:ça|ca|bien)\b|souviens[ -]toi\b"
    r"|mémorise|memorise|n'oublie pas (?:ça|ca|de|que)\b)",
    re.IGNORECASE,
)

#: A CORRECTION of the work just done — Hermes's "first-class skill signal". Phrase-level on
#: purpose: a bare "non" opens half of the operator's sentences and would fire on everything.
#:
#: Four markers were **cut by the audit** for firing on the repo's own vocabulary rather than on
#: the operator's displeasure: ``stop`` (the name of the hook file this very module feeds),
#: ``encore une fois`` (136 hits — a discourse marker, "once again, to be clear"), ``relis`` (an
#: ordinary instruction), and a bare ``dériv`` (a downstream project trades **produits dérivés**). What survives
#: either
#: addresses me directly or cannot be said about anything but my work.
_CORRECTION_RE: Final = re.compile(
    r"(pourquoi (?:tu|t'es|est-ce que tu)\b"
    r"|c'est pas (?:ce que|ça que|ce qu'on)\b|ce n'est pas ce que\b"
    r"|j'ai (?:pas|jamais) demandé\b|je t'ai (?:pas )?(?:dit|demandé)\b"
    # "tu as vraiment vraiment vraiment derivé": the adverbs between subject and verb are the whole
    # point of the sentence, so a bounded gap follows the pronoun instead of strict adjacency. The
    # pronoun is now REQUIRED — that is what separates "tu dérives" from "les produits dérivés".
    r"|\b(?:tu|t'as|t'es)\b[^.!?]{0,40}?\bd[ée]riv(?:e|é|es|er)\b"
    r"|par[st] en vrille\b"
    r"|arr[êe]te (?:de|ça|ca|tout|avec)\b"
    r"|recommence\b|reprends? (?:dès le|depuis le|du) début"
    r"|tu (?:as|a) perdu\b|ça sert à rien\b|n'importe quoi\b"
    r"|combien de fois\b|t'as pas (?:lu|compris)\b"
    # Doubled punctuation is disbelief in writing — "elle a pas deja ete faite??" is a challenge,
    # and it was the turn before the one where the operator finally said the day had gone off the
    # rails.
    # Known and accepted false positive: "ça te va??". Measured weight: 10 of 344 firings.
    r"|\?\?|\?!"
    r"|putain(?! de)\b|merde\b)",
    re.IGNORECASE,
)

#: A CALM disagreement — the half of the operator's pushback the detector was deaf to until
#: 2026-08-14.
#:
#: **The measured hole.** Every marker in :data:`_CORRECTION_RE` needs the operator to be ANNOYED
#: (``pourquoi tu``, ``c'est pas ce que``, ``??``, ``putain``, ``arrête de``). They mostly are not. On
#: seven real pushbacks of the 2026-08-14 session, **2 fired**; the five silent ones each changed a
#: design (extraction is not "merging" · context is not an enemy · knowing is a TOOL, not a phase).
#: A detector calibrated on anger measures anger, not disagreement.
#:
#: **Every marker below was counted on the 1 605 real turns of ``system/state/sessions.db`` BEFORE
#: being written here**, and its hits were READ, because that is the method this module already
#: paid for once. What the counting threw out is as much a part of the design as what it kept:
#:
#: * ``mais`` (538 hits) and ``en fait`` (290) — discourse markers, the exact shape of the
#:   ``encore une fois`` that a previous audit cut. That older cut is documented below as
#:   **136 hits**; re-counted today the same phrase gives **77 turns**, because it was measured on
#:   a **1 718-turn** population this database no longer holds (1 605 today). Same for the
#:   ``70``/``161`` cited under :data:`_INSTRUCTION_RE`, which re-count as **98**/**100**. The old
#:   numbers are not wrong, they are *out of scope* — and nothing in the file said so, so I quoted
#:   136 next to my own 538 as if the two were commensurable. An inherited count carries the
#:   population it was taken on, or it is a rumour;
#: * ``attends`` (75) — swamped by *"j'attends la fin du run"*, and five of its hits are the operator
#:   PASTING an agent's report back into the chat, prefixed *"VOILA CE QUI A ETE RENVOYÉ"*;
#: * ``faux`` (37) — this repo's own vocabulary. Every read hit was an audit report about a
#:   *"fait devenu faux"*, i.e. the detector reading the project's subject matter;
#: * ``comment ça`` (18) — one hit is a pasted **YouTube transcript** ("Bonjour. Comment ça va ?");
#: * ``plutôt que`` (28) — half its hits are pasted agent prose, and *"fais X plutôt que Y"* is an
#:   ordinary instruction, not a contradiction;
#: * ``on est d'accord SUR`` — kept ``?``/``que`` only. The ``sur`` branch fired on *"on est bien
#:   d'accord sur ça"* (the operator SEALING a decision) and *"si on est d'accord sur les deux, tu
#:   peux
#:   compacter"* (agreement): 2 of the 4 false accusations in the first read sample came from it;
#: * ``il vaut / vaudrait mieux`` — 23 turns, 7 of them silent for all four kinds, and READ: six of
#:   the seven are the operator weighing two options and handing me the choice (*"vaut mieux le faire
#:   ici,
#:   ou est-ce qu'il vaut mieux recompacter ?"*). A deliberation is not a disagreement. This is the
#:   marker the docstring below still admits missing, and it stays missing ON PURPOSE — see there;
#: * ``je sais pas si`` / ``je suis pas sûr`` — 56 turns, 24 silent (14 distinct), and READ: about
#:   four are real doubts about the work. The rest is politeness padding (*"je sais pas si tu vois
#:   ce que je veux dire"*), and **2 of the 14 are assistant prose the operator pasted back** (*"je
#:   ne suis pas sûr de laquelle. Si tu peux préciser la tâche concernée…"*). First-person doubt is
#:   how they speak, not how they disagree;
#: * ``sauf que`` — **1 hit in the operator's turns against 11 in the assistant's**. The ratio alone
#: settles it.
#:
#: Those last two come from the audit's open question, which proposed three forms. Writing a refusal
#: down costs nothing next time; re-measuring does. The third of the three was kept — see
#: ``le problème c'est que`` in the pattern.
#:
#: **The cost is PUBLISHED, not hidden** — a capture rate without its false-accusation rate is a
#: wall, not a measurement.
#:
#: **AND THE POPULATION IS ALIVE, so every number below carries the shot that produced it.**
#: ``sessions.db`` is rebuilt from the transcripts as sessions run: measured across three hours of
#: the same afternoon it went **1 605 → 1 584 turns while the baseline ROSE, 270 → 279** (sessions
#: re-read, others indexed for the first time). A count from this table without its shot is a
#: rumour by construction, not by carelessness — the same trap as the inherited ``136`` above, one
#: level down.
#:
#: Shot of reference: **2026-08-14, 24 001 messages · 36 sessions · max(ts) 18:00:15Z**, and
#: **excluding this module's own authoring session** (see the contamination note below):
#:
#: * it fires on **414** turns of **1 578** where it used to fire on **277** — **+137**;
#: * those turns hold only **844 distinct texts** (the host re-appends a message when a session
#:   resumes), so on distinct wording the gain is **170 → 243, +73**. Both are printed because
#:   quoting only the larger one would flatter the change;
#:
#: **THE CORPUS NOW CONTAINS THIS DETECTOR'S OWN SPECIFICATION.** The session that wrote these
#: patterns is indexed like any other, and its opening prompt quotes the five frozen witnesses
#: verbatim — so the turn that SPECIFIES the detector fires it, on ``Ah non``. Measured effect here
#: is small (6 turns, 2 of them firing) and the numbers above exclude it, but the shape is the one
#: this repo keeps re-learning: *a text detector counts citations as instances*, and a corpus that
#: records our own work will keep serving us our own words back as evidence.
#: * of **30 new firings read one by one**, **2 carry no pushback at all** (6.7 %): a neutral
#:   qualifier (*"une revue, pas forcément profonde"*) and an explicitly idle question (*"ça veut
#:   pas dire que j'ai envie de le faire"*).
#:
#: That rate is measured on a sample drawn AFTER the last tuning decision and at a different offset
#: from the one the tuning was read on — where the strict rate was 5 of 30. Reporting the tuned
#: sample's own rate would have been measuring the green I had just bought.
#:
#: **Both of those numbers were WRONG when first published, and an isolated audit found both.**
#: They are corrected above and the two mistakes are kept here, because each has a shape worth
#: recognising:
#:
#: * ``173 → 242`` came from measuring the distinct set through ``" ".join(text.split())``, a
#:   normalisation that lives in :func:`_excerpt` and runs AFTER detection — never in
#:   :func:`detect`, which searches the RAW text. Through the judge's own accessor it is
#:   **172 → 241**. One text flipped: a pasted conference transcript where a wrapped ``à\nl'avenir``
#:   became ``à l'avenir``. Measuring a gate through anything but the gate's own reader is how you
#:   publish a number the gate will never produce.
#: * ``3 of 30`` was one too pessimistic. The refused turn, *"tant que t'es sûr que ça marche… on
#:   laisse la commande de côté"*, DID produce a durable lesson: the memory file
#:   ``heavy-runs-wait-for-a-free-machine`` was written 3 min 17 s later, in the same session, and
#:   quotes it three times. A judgement about whether a turn taught anything is checkable against
#:   what was written just after it — and I judged it from the text alone.
_DISAGREEMENT_RE: Final = re.compile(
    # "Non, tu fais que du haiku" — opening the turn, this is a rebuttal and almost nothing else.
    # Anchored at \A rather than at every line start: a hard-wrapped "N\non" would otherwise match.
    r"(\A(?:ah |euh |ben |bah )?(?:non|nan)\b|\bah non\b"
    # The politest contradiction the operator has: "Ah non, attention, pas forcément."
    r"|pas forc[ée]ment\b"
    # "fais attention à X" / "attention, si" — a warning is a correction that arrives early.
    r"|(?:fai[ts]|faut|faire)\s+(?:bien |tr[èe]s |aussi |gaffe )?attention\b"
    r"|\battention\s*[,!]|attention (?:[àa]|au|aux)\b"
    # "est-ce qu'on est bien d'accord QUE …" — the operator checks an assumption when they doubt it.
    r"|on est (?:bien )?d'accord\s*(?:\?|que\b|qu')"
    # "faut aussi voir pourquoi …" — the dimension I left out, named without a single reproach.
    r"|\bfaut (?:aussi|quand m[êe]me|pas oublier)\b"
    # "je comprends pas pourquoi ça bloque" / "pourquoi on lance un run de six heures ?" — the
    # pronoun separates a challenge to the WORK from "pourquoi tu", which _CORRECTION_RE owns.
    #
    # NARROWED by the audit of 2026-08-14, on this module's OWN criterion — fire on what the
    # operator ASKS, never on what the project is ABOUT. The first version was a bare
    # ``pourquoi (?:ça|c'est|on|le|la|il|ce)``, and it fired **35 times in the operator's turns
    # against 150 in the assistant prose they paste back** (ratio 4.3) — dirtier, by that exact test,
    # than three
    # markers this file threw out for being repo vocabulary. Requiring either the first-person doubt
    # or a question mark in the same sentence costs 3 of the 20 turns it caught and takes the
    # assistant-prose count from 150 to **1** (ratio 0.02). Same catch, no contamination.
    # Whole-lexicon effect of the narrowing, on the shot where it was decided (1 605 turns):
    # 397 -> 390 turns, 241 -> 237 distinct. The shot is named because the table moved since.
    r"|je (?:comprends|vois|sais) pas pourquoi\b"
    r"|pourquoi (?:[çc]a|c'est|on|le|la|il|ce)\b[^.!?]{0,120}\?"
    r"|\b(?:t'es|tu es|es-tu)\s+s[ûu]r\b"
    # "Je vois connaître plus comme un OUTIL qu'un prérequis" — a REFRAMING. Zero hits on the 1 605
    # turns, and kept anyway: it costs nothing and it is the exact shape of a design being rewritten
    # under my nose. A marker measured at zero is cheap; a marker never measured is the debt.
    r"|je (?:le |la |les |[çc]a )?vois\b[^.!?]{0,60}?\b(?:plus|plut[ôo]t) (?:comme|que)\b"
    r"|au contraire\b"
    # "le problème, c'est qu'il y avait des choses qu'on faisait avant" — the operator NAMING their
    # objection.
    # Added 2026-08-14 from the audit's open question, and the only one of its three proposals that
    # survived being read: 45 turns, 10 of them silent for all four kinds (6 distinct), and **5 of
    # the 5 distinct ones read are real objections** — to a plan's depth, to a categorical claim, to
    # how I work. Assistant prose: 2. Its two obvious variants were measured before being skipped:
    # ``mon problème c'est que`` and ``le souci c'est que`` are BOTH at zero in this corpus.
    r"|le probl[èe]me,? c'est qu)",
    re.IGNORECASE,
)

#: A standing PREFERENCE about how to work — durable by nature, which is exactly what memory is for.
_PREFERENCE_RE: Final = re.compile(
    r"(à l'avenir\b|a l'avenir\b|la prochaine fois\b|dorénavant\b|desormais\b|désormais\b"
    r"|je préfère\b|je prefere\b|je veux (?:que|pas)\b|j'aimerais que tu\b"
    r"|j'ai pas envie (?:de|que)\b|je (?:n'ai|nai) pas envie\b"
    r"|systématiquement\b|systematiquement\b"
    r"|(?:ne )?(?:fais|refais) (?:jamais|plus)\b|toujours (?:faire|passer|commencer|vérifier)\b)",
    re.IGNORECASE,
)

#: What each kind means for what to do next — printed with the quote so the block is actionable.
_ADVICE: Final = {
    "consigne": "The operator explicitly asked you to retain something. `make remember` — this is "
    "the least debatable case there is.",
    "correction": "A correction of the work under way. What gets retained is NOT the incident: it "
    "is the rule that would have avoided it, written down for next time.",
    "desaccord": "The operator contradicted you WITHOUT raising their voice — the signal that is "
    "easiest to miss, and measured as such (2 detected out of 7 on 2026-08-14). Re-read the "
    "sentence: what the operator is correcting is often a DESIGN, not a gesture. And if it "
    "contradicts nothing, say so and move on.",
    "preference": "A durable working preference — it holds beyond this task.",
}

#: Ported from ``background_review.py``'s "Do NOT capture", whose reasoning we adopt wholesale.
DO_NOT_CAPTURE: Final = (
    "an ENVIRONMENT failure (a missing binary, an uninstalled dependency, unconfigured "
    "credentials) — that gets repaired, not engraved;",
    'a NEGATIVE claim about a tool ("X does not work", "you cannot Y") — it hardens into refusals '
    "the system cites against itself for months after the problem was fixed;",
    "a TRANSIENT error resolved before the end of the task — if retrying was enough, the lesson is "
    "the retry, not the breakage;",
    'the STORY of a single task — "we did X today" is not a reusable rule;',
    "what the repo ALREADY SAYS (a file, a commit, CLAUDE.md) — memory carries what cannot be "
    "reconstructed.",
)


def _text_of(message: Any) -> str:
    """The spoken text of one transcript message — text blocks only, scaffolding stripped."""
    from .sessions import _message_text  # one reader, one home (no second parser to drift)

    return _message_text(message)


def _is_real_user_turn(event: dict[str, Any]) -> bool:
    """True for something the operator actually typed.

    Excludes what merely LOOKS like a user turn: a sub-agent's prompt (``isSidechain``), hook and
    system injections (``isMeta``), a compaction summary, and the tool_result messages the host
    also files under ``type: user`` (they carry no text block, so they fall out on emptiness).
    """
    return (
        event.get("type") == "user"
        and not event.get("isSidechain")
        and not event.get("isMeta")
        and not event.get("isCompactSummary")
    )


def detect(events: Sequence[dict[str, Any]]) -> tuple[Signal, ...]:
    """Find the learning signals in one task's worth of transcript events.

    ``events`` is the slice since the last real user prompt — the boundary the Stop hook computes
    with :func:`is_task_boundary`, so that the hook and this function agree on what a user turn is.

    At most one signal per kind, strongest kind first: four phrasings of the same complaint are one
    complaint, and quoting them all would bury the others. **Every returned signal carries a
    quote** — a block that asserts a signal without showing the words that caused it is what the
    audit removed, and nothing here may reintroduce it.
    """
    found: dict[str, Signal] = {}
    for event in events:
        if not _is_real_user_turn(event):
            continue
        text = _text_of(event.get("message"))
        if not text:
            continue
        for kind, pattern in (
            ("consigne", _INSTRUCTION_RE),
            ("correction", _CORRECTION_RE),
            ("desaccord", _DISAGREEMENT_RE),
            ("preference", _PREFERENCE_RE),
        ):
            if kind in found:
                continue
            match = pattern.search(text)
            if match:
                found[kind] = Signal(kind=kind, quote=_excerpt(text, match.start()), advice=_ADVICE[kind])
    return tuple(found[kind] for kind in _KIND_ORDER if kind in found)


#: The scaffolding a slash-command invocation carries (`/loop`, `/compact`, a project command…).
#: The host files it as an ordinary user turn whose text is ENTIRELY made of these tags.
_COMMAND_RE: Final = re.compile(r"<command-(?:message|name|args)>")


def _carries_a_command(message: Any) -> bool:
    """True when this user turn is a slash-command invocation rather than typed prose."""
    content = (message or {}).get("content")
    if isinstance(content, str):
        blocks = [content]
    elif isinstance(content, list):
        blocks = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    else:
        return False
    return any(_COMMAND_RE.search(b or "") for b in blocks)


def is_task_boundary(event: dict[str, Any]) -> bool:
    """True for the events that OPEN a task — the one definition the hook and :func:`detect` share.

    The audit found the two disagreeing: the hook accepted any ``type: "user"`` event carrying a
    non-tool_result block, so a ``<task-notification>`` (the host's own report that a sub-agent
    finished) counted as "the operator spoke" and became the task boundary. In **433 of 1 048** real
    tasks the window therefore started AFTER the operator's actual prompt, putting the correction it
    contained out of scope — the detector was reading a window that began at the host talking to
    itself.

    So the boundary is now "a turn :func:`detect` would look at, that still has text once the host's
    scaffolding is stripped". Same predicate, one home.

    **AND A COMMAND OPENS A TASK WITHOUT SAYING ANYTHING QUOTABLE — measured 2026-08-15.** A
    `/loop` arrives as an ordinary user turn whose text is ENTIRELY made of
    `<command-message>` / `<command-name>` / `<command-args>`: stripped, **nothing** remains, and
    this predicate therefore returned **False**. On the real transcript: **6 invocations, 0
    recognised**, and the hook's window reached **79 events** back — three turns instead of one.

    **THESE ARE TWO QUESTIONS, AND CONFLATING THEM WAS THE DEFECT**: *"where does the task
    start?"* and *"did the operator say anything QUOTABLE?"*. A command answers YES to the first and
    NO to the second. :func:`detect` keeps ignoring it (it has no word to quote, its `if not text:
    continue` handles that); the boundary, however, accepts it. **One single home, two explicit
    clauses** — rather than two predicates that drift apart.

    What this fixed downstream: the E3 block and the ritual used to fire on turns that were
    ENTIRELY read-only, and :func:`detect_trace`'s window spanned several tasks — which undermined
    the clause that requires SILENCE on a task that did nothing.
    """
    if not _is_real_user_turn(event):
        return False
    message = event.get("message")
    return bool(_text_of(message)) or _carries_a_command(message)


def _excerpt(text: str, around: int) -> str:
    """The words surrounding the match, flattened — enough to recognise the moment.

    A short message is quoted WHOLE: windowing it produced three near-identical excerpts of the same
    sentence, each starting mid-word, which reads like a bug and hides that the three signals came
    from one turn. Only a long message is windowed, and then on word boundaries.
    """
    flat = " ".join(text.split())
    if len(flat) <= _QUOTE_LEN:
        return flat
    anchor = max(0, min(around, len(flat) - 1))
    start = max(0, anchor - _QUOTE_LEN // 3)
    end = min(len(flat), start + _QUOTE_LEN)
    if start:
        # Snap forward to the next word start so the quote never opens mid-word — but NEVER past the
        # anchor. The audit found the unclamped version sliding the window beyond the very phrase it
        # was quoting: the block then offered as evidence an excerpt that did not contain the
        # trigger. A quote that has lost its reason to exist is worse than a rough word boundary.
        space = flat.find(" ", start)
        if 0 <= space < min(anchor, end):
            start = space + 1
    if end < len(flat):  # and snap back to the previous word end, never before the anchor
        space = flat.rfind(" ", start, end)
        if space > anchor:
            end = space
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


def render_review(signals: Sequence[Signal]) -> str:
    """The block the Stop hook injects. Empty string when there is nothing to say.

    Prints the operator's own words back, because a generic "think about capturing" is exactly what
    was already there and exactly what gets skipped.
    """
    if not signals:
        return ""
    lines = [
        "[Mnemosyne · end-of-task review] Learning signals were DETECTED in this task — not a "
        "generic reminder, these are the operator's own words:",
        "",
    ]
    for signal in signals:
        lines.append(f"  • {_KIND_LABEL[signal.kind]}")
        if signal.quote:
            lines.append(f'      "{signal.quote}"')
        lines.append(f"      → {signal.advice}")
        lines.append("")
    lines.append("DO NOT CAPTURE:")
    lines.extend(f"  – {rule}" for rule in DO_NOT_CAPTURE)
    lines.append("")
    lines.append(
        "Where it goes: a durable fact about the operator or their way of working → `make remember "
        'LEARNING="…"` (inert, they validate it). A rule about HOW to run this class of task → '
        "the skill that governs it, or the decisions log if it is structural."
    )
    lines.append(
        "If after reading none of that is durable, say so in one line and finish — "
        "silence is a valid result, not a failure."
    )
    return "\n".join(lines)


#: Human labels for the block — what the operator reads over my shoulder.
_KIND_LABEL: Final = {
    "consigne": "EXPLICIT INSTRUCTION to retain",
    "correction": "CORRECTION of the work under way",
    "desaccord": "CALM DISAGREEMENT — the operator contradicted you politely",
    "preference": "WORKING PREFERENCE expressed",
}


# =================================================================================================
# I4 (b) — THE OTHER HALF: signals in MY OWN TRACE, not in the operator's words
# =================================================================================================
#
# Measured on the 2026-08-14 session that produced item I4, and this is why the half exists: of its
# commits, FIVE admit an error in their own TITLE and FIVE add an item to the plan MID-TASK. An item
# added while executing is the signature of a lesson found — nobody plans an item they already knew
# they needed. All of it reads in `git`: no model, no network, no transcript moving.
#
# THE GENERIC QUESTION IS THE DEFECT BEING FIXED, not the silence. The Stop hook already fired at
# the right boundary; what it asked was *"did a durable learning emerge?"* — a question one can
# answer "no" to without looking. *"This task added 3 items to the plan: which one should have been
# there from the start?"* cannot be eluded, because it names what happened.


@dataclass(frozen=True, slots=True)
class Commit:
    """One commit of THIS task, as the EDGE read it — this module never speaks to git.

    ``plan_items_added`` is the list of item identifiers the commit's diff ADDS to a plan file. The
    edge extracts the added lines; :func:`items_ajoutes` names them.
    """

    sha: str
    subject: str
    plan_items_added: tuple[str, ...] = ()


#: An avowal in a commit TITLE. **Every alternative below was counted on the real corpus before it
#: was written**, with ``git log --pretty=format:%s`` — the method this module already carries.
#:
#: * ``j'avais`` — **4 hits**, all four genuine avowals;
#: * ``mon ticket`` — **2**, both genuine;
#: * ``est/était FAUX`` · ``prémisse FAUSSE`` — the restricted form (see the cut below);
#: * an audit VERDICT that names a falsity — ``l'audit … FAUX / FAUSSE``;
#: * a DESTRUCTIVE verb whose object is MINE — but it lives in :data:`_DESTRUCTIVE_RE`, **not here**:
#:   it only counts under the evaluator guard, and a guarded rule with an unguarded twin is not
#:   guarded. Measured the moment the guard was written: the twin still sat in this constant, so
#:   *"le profil tue mon cache inutile"* (a real French commit title) passed through the front door
#:   while the guard watched the back one. *Two expressions of a single rule drift — and the one
#:   that drifts is the one nobody is looking at.*
#:
#: **THE LAST TWO WERE NARROWED BY A SECOND AUDIT, AND THE FIRST DRAFT WAS THE OLD TRAP AGAIN.**
#: They read ``l'audit … a (trouvé|falsifié|corrigé)`` and ``ma (porte|clause|…)`` — i.e. *any
#: mention of my artefact* and *any audit result*. They scored 0 false positives on the corpus only
#: because **this repo has never written those sentences yet**: handed a CONTROL corpus of six
#: plausible titles, they accused **6 out of 6** — *« l'audit a trouvé 0 défaut »*, *« ma règle de
#: nommage est posée »*, *« l'audit a corrigé la coquille d'un tiers »*. A rate measured only where
#: the counter-examples do not exist is not a rate. The verb must now be DESTRUCTIVE and its object
#: MINE, which is what an avowal actually is.
#:
#: **Three numbers, one command** (``git log --pretty=format:%s``, 600 titles):
#: **24 caught · 24 genuine avowals, read one by one · 0 false on the 8-title control corpus**,
#: and **9 of 9** frozen witnesses still fire.
#:
#: **THE LAST TWO WERE ADDED BY AN AUDIT THAT MEASURED THE RECALL I NEVER MEASURED.** The first
#: version scored **0 out of 4** on the very next window outside its own sample: four commits whose
#: titles read *« l'audit isolé a falsifié ma porte »*, *« … a trouvé une line FAUSSE »* were all
#: silent. Three of its six hits were the frozen witnesses themselves — the patterns had been
#: written while looking at the window they were then validated on. *A capture rate measured on the
#: sample that produced the patterns is not a capture rate.*
#:
#: **A BARE ``FAUX`` WAS CUT, and it is the exact trap this module was already built to avoid.**
#: It scores 8/565, and two of those eight are the repo's own VOCABULARY, not an avowal: *« un taux
#: de capture sans son taux de FAUX POSITIFS est un mur »* and *« un plafond de SORTIE qui coupe en
#: silence rend une FAUSSE réponse »*. Hence the explicit ``FAUX POSITIF`` / ``FAUX NÉGATIF``
#: exclusion below: the pattern must fire on what I ADMIT, never on what the project is ABOUT.
_MEASURED_ADMISSION_RE: Final = re.compile(
    r"""j'avais\b
      | \bmon\ ticket\b
      | \b(?:est|était|etait|sont|étaient|etaient)\ FAU(?:X|SSE)\b
      | \bpr[ée]misse\ (?:FAUSSE|fausse)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

#: An audit VERDICT that names a falsity — the only clause :data:`_NEGATIVE_POLARITY_RE` keeps,
#: because it is the only one where the negation changes the meaning (*« rien de FAUX trouve »*).
#: ``rendu NON`` is what RECOVERS the admission that the tour-3 tightening had silently lost.
_AUDIT_VERDICT_RE: Final = re.compile(
    r"l'audit\b[^\n]{0,40}?\b(?:FAUSSE|FAUX|fausse|rendu\ NON|a\ tue)\b",
    re.IGNORECASE | re.VERBOSE,
)

#: **THE SUBJECT, which the verb list could not carry EITHER.** *« l'USAGE RÉEL refuse ma
#: porte »* is an admission; *« la porte refuse ma demande de test »* is a feature working as
#: designed. Same shape, opposite meanings — the difference is **who is acting**. A destructive verb
#: therefore only counts when an EVALUATOR is named in the title (an audit, real usage, a
#: measurement, a bench, a trial). Three of the four false positives on the independent control
#: corpus were exactly that: a linter, a reader, a gate, doing their job on something of mine.
_EVALUATOR_RE: Final = re.compile(
    r"\b(?:audits?|usage\s+r[ée]el|mesures?|bancs?|tiers|[ée]preuves?|contre-preuve|r[ée]alit[ée]|essai)\b",
    re.IGNORECASE,
)

#: The destructive verb WITH its object being mine — the half that requires :data:`_EVALUATOR_RE`.
_DESTRUCTIVE_RE: Final = re.compile(
    r"\b(?:falsifi|r[ée]fut|invalid|contredi|demoli|refuse|refusent|tue|tuent|casse|cassent)\w*"
    r"\s+(?:\d+\s+)?(?:de\s+)?m(?:a|on|es)\b",
    re.IGNORECASE,
)

#: Forms of admission WITHOUT a possessive or a destructive verb, added after the independent
#: control corpus (they add **no** hit to the real corpus: the set of 26 is identical before/after —
#: *freeze the SET, never the count*).
_DIRECT_ADMISSION_RE: Final = re.compile(
    r"""erreur\ de\ ma\ part
      | je\ n'(?:ai|avais)\ pas\ vu
      | \bj'ai\ cass[ée]
      | ^revert\(
      | \boubli\b[^\n]{0,24}?\bmon\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

#: **POLARITY, which the verb list could not carry.** An audit that renders a CLEAN verdict uses
#: exactly the same words as an audit that condemns: *« rien de FAUX trouve »*, *« l'audit a trouve
#: 0 defaut »*. The third judgment showed this by changing the corpus just once — I had changed the
#: list of VERBS, the failure mode was still intact. This veto closes the negation CLASS, not the two
#: titles that revealed it.
_NEGATIVE_POLARITY_RE: Final = re.compile(
    r"\b(?:rien\ de|aucune?|sans|0|z[ée]ro)\b[^\n]{0,24}?\b(?:FAUX|FAUSSE|fausse|d[ée]faut|erreur)",
    re.IGNORECASE | re.VERBOSE,
)

#: **UNPROVEN ON THE CORPUS — declared separately ON PURPOSE, and the list GREW after an audit.**
#: Every alternative here scores **0 hits** on the real titles: ordinary French for an avowal that
#: this repo has simply never used yet. They cannot fire on its vocabulary, and the cost matrix is
#: lopsided (a false positive costs one ignored line; a false negative costs a lesson already paid
#: for) — so they are kept. But zero hits means zero evidence.
#:
#: **SEVEN OF THEM WERE LIVING IN THE *MEASURED* CONSTANT**, smuggled in by a parenthesis that
#: said ``mon ticket`` *« (and the same possessive over what I produce) »* while only ``mon ticket``
#: had been counted. ``j'étais`` · ``je m'étais`` · ``mon item`` · ``mon chiffre`` · ``mon compte``
#: · ``mon audit`` · ``mon correctif`` all score 0. (``mon hypothèse`` was in that list and scored
#: **1**, not 0 — the second audit caught the wrong label; it left, and the destructive-verb rule
#: above covers its one real hit, *« l'essai REFUTE mon hypothese »*.) *A MEASURED label must not shelter its
#: unmeasured neighbour* — the exact rule this file writes, broken inside this file, found by the
#: isolated audit. They live here now, and nobody may cite the measurement as covering them.
_UNPROVEN_ADMISSION_RE: Final = re.compile(
    r"""\b(?:à|a)\ tort\b
      | \bje\ (?:croyais|pensais|déclarais|declarais)\b
      | \bj'(?:étais|etais)\b | \bje\ m'(?:étais|etais)\b
      | \bmon\ (?:item|chiffre|compte|audit|correctif)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

#: (A ``_FAUX_METIER_RE`` guard — stripping ``FAUX POSITIF`` / ``FAUX NÉGATIF`` before matching —
#: used to sit here. The audit measured it: **it changes 0 verdicts out of 572**, because the two
#: vocabulary hits it claimed to protect against are already excluded by the CUT of the bare
#: ``FAUX``, and **no test armed it**. A mechanism that never bites proves nothing, and a comment
#: crediting it with a protection it does not provide is worse than its absence. Removed.)

#: A plan ITEM line, in the coarse shape the plans of this repo use: ``- **A2** **titre**``.
#:
#: **A DELIBERATE APPROXIMATION, and the honest reason.** The real grammar of an item belongs to
#: ``plan_format.py`` and to nobody else — but it is a 1 400-line parser whose private constants are
#: being EXTENDED right now (item A1 adds six declared fields). Coupling this detector to its
#: internals today would break it on someone else's commit. The consequence of a mismatch here is
#: bounded and benign: a QUESTION asked once too often, or once too rarely, at the end of a task.
#: Nothing refuses, nothing is written. *Judge the cost of the coupling before paying it.*
_ADDED_ITEM_RE: Final = re.compile(r"^\s*[-*]\s+\*\*([A-Za-z][A-Za-z0-9-]{0,11})\*\*")


def _idents(lines: Sequence[str]) -> list[str]:
    """The item identifiers carried by these lines, deduplicated, in order of appearance."""
    found: list[str] = []
    for line in lines:
        match = _ADDED_ITEM_RE.match(line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found


def items_ajoutes(
    added_lines: Sequence[str], removed_lines: Sequence[str] = ()
) -> tuple[str, ...]:
    """The items a diff really ADDED to a plan file — those added and NOT also removed.

 **THE SECOND ARGUMENT IS THE WHOLE CORRECTNESS OF THIS FUNCTION, and it was missing.**
 Closing an item REWRITES its line (``- **D3** …`` becomes ``- **D3** …``), so the diff
 carries it as one removal PLUS one addition. Reading only the ``+`` side made every closure
 look like a birth — and the block then asserted, in place of the generic reminder, *"this task
 added N items to the plan"*.

 Measured over 120 commits, truth being the ident set of the file AFTER minus BEFORE (same
 grammar on both sides, so the grammar is not the variable):

 * before — **30 commits cry, 22 of them wrongly (73 %)**;
 * after — **8 cry, 0 false, 0 missed**, against a truth of exactly **8**.

 *A capture rate without its false-accusation rate is a WALL* — the item asking for this detector
 writes that sentence itself, and the second number had simply never been taken.
 """
    removed = set(_idents(removed_lines))
    return tuple(ident for ident in _idents(added_lines) if ident not in removed)


#: How many item identifiers the block QUOTES. Not a cap on the COUNT — the count is always stated
#: in full, and what is dropped is NAMED ("…and N others"). Measured reason: the commit that CREATED
#: this plan added **42** items in one go, and a 42-name wall reads as noise, which is how a block
#: teaches people to skip it. *A silent truncation reads as "I covered everything"; this one says
#: what it left out.*
_ITEMS_QUOTED: Final = 6


def _bounded_list(items: Sequence[str]) -> str:
    """The quoted item list — bounded, and SAYING what it dropped."""
    if len(items) <= _ITEMS_QUOTED:
        return ", ".join(items)
    return ", ".join(items[:_ITEMS_QUOTED]) + f", …and {len(items) - _ITEMS_QUOTED} others"


def _est_un_aveu(subject: str) -> bool:
    """True when a commit title LOOKS LIKE an admission of an error of mine.

    **LOOKS LIKE, and the word is chosen.** This is a regex over French prose: it cannot know
    who the SUBJECT of the verb is, and it barely knows POLARITY. *« l'USAGE REEL refuse ma porte »*
    is an avowal; *« la porte refuse ma demande de test »* is a feature working as designed — the
    two are the same shape.

    **THE WIDENING STOPS HERE, AND THE REASON IS A TABLE, NOT A FEELING.** Four rounds of isolated
    audit, each handing this detector a corpus it had never seen:

    ======  ====================================  =============================
    round   false positives on the corpus IN HAND  on the first corpus NEVER SEEN
    ======  ====================================  =============================
    2       0 / 591 (the real repo)               **6 / 6**
    3       0 / 6   (control corpus 1)             **4 / 10**
    4       0 / 10  (control corpus 2)             **3 / 10**
    ======  ====================================  =============================

    Every tightening drives the metric to ZERO on everything it owns and recovers 30-40 % of false
    accusations on the first corpus it does not. The cause is STRUCTURAL, not lexical: an avowal is
    a claim about the AUTHOR'S INTENT and about the VALENCE of a result, and a regex over a title
    has access to neither. The two vetoes below are the proof — they encode *who acts* and *was it
    bad* as lexical proxies, and each was refuted in one sitting.

    **THE TWO PUBLISHED RATES, on the freshest corpus never used to calibrate (control corpus 3,
    frozen in ``tests/orchestration/test_trace_signals.py``): 3 false positives out of 10, and 8
    SILENCES out of 10.** Publishing the first without the second would be the same wall in the
    other direction. On this repo's real titles it reads 27 caught over 624
    (``git log --pretty=format:%s``, 2026-08-14) — a property of what this repo has HAPPENED to
    write, never a property of the rule, and a number to RE-MEASURE rather than to trust.

    **AND THE ASYMMETRY IS THE LESSON WORTH KEEPING.** The other half of I4(b),
    :func:`items_ajoutes`, is EXACT — 8/8, 0 false, 0 missed over 120 commits — because it reads a
    **STRUCTURE** (a diff), not prose. *What is measured on a structure gets CLOSED; what is
    measured on prose gets bounded and declared.*

    That is why the rendered block INVITES a look and never asserts the avowal (see
    :func:`detect_trace`). *A text detector counts citations as instances* — the way to survive that
    is to say so, not to add a tenth alternative.
    """
    # EACH VETO IS CARRIED BY THE CLAUSE IT CORRECTS, never placed at the head of the gate. Placed
    # at the head, they applied to EVERYTHING: `j'avais tort, zero erreur reelle` was killed by the
    # polarity veto, and `j'avais tort -- ruff casse ma line au passage` by the subject one — two
    # MEASURED alternatives (4 and 2 real hits) cancelled by a veto written for a third one.
    # Measured: 0 real titles out of 616 suffered from it, so it was LATENT — and a latent defect in
    # a gate is a defect. *The ORDER of checks decides what gets judged.*
    if _MEASURED_ADMISSION_RE.search(subject) or _DIRECT_ADMISSION_RE.search(subject):
        return True
    if _UNPROVEN_ADMISSION_RE.search(subject):
        return True
    if _AUDIT_VERDICT_RE.search(subject) and not _NEGATIVE_POLARITY_RE.search(subject):
        return True
    return bool(_DESTRUCTIVE_RE.search(subject) and _EVALUATOR_RE.search(subject))


def detect_trace(commits: Sequence[Commit]) -> tuple[Signal, ...]:
    """The learning signals carried by MY commits — the half the operator's words cannot contain.

    Returns the same :class:`Signal` shape as :func:`detect`, so the hook renders one object and not
    two. **Silence is the default here too**: a task that avowed nothing and added no item returns
    an empty tuple, and the hook falls back to the ordinary ritual.
    """
    admissions = tuple(c for c in commits if _est_un_aveu(c.subject))
    items = tuple(dict.fromkeys(ident for c in commits for ident in c.plan_items_added))
    signals: list[Signal] = []
    if items:
        signals.append(
            Signal(
                kind="item_ajoute",
                quote=_bounded_list(items),
                advice=(
                    f"this task added {len(items)} item(s) to the plan WHILE EXECUTING IT — WHICH "
                    "one should have been there from the start, and what did you not know when you "
                    "wrote the plan? That is the lesson. (A plan that is BORN in this task teaches "
                    "nothing: say so in one line and move on.)"
                ),
            )
        )
    if admissions:
        signals.append(
            Signal(
                kind="aveu",
                quote=" · ".join(f"{c.sha[:7]} {c.subject}" for c in admissions),
                advice=(
                    f"{len(admissions)} title(s) of this task LOOK LIKE an admission of error — LOOK AT "
                    "THEM, this detector is a regex over French prose and it is wrong IN BOTH "
                    "DIRECTIONS (independent control corpus: 3 false out of 10, and 8 silences out "
                    "of 10 — it misses more than it invents). If it is one: is the lesson engraved, "
                    'and does it NAME the code that makes the fault impossible? A lesson with no '
                    'barrier is a wish, and the admission "no barrier exists" is a valid and free '
                    "answer."
                ),
            )
        )
    return tuple(signals)


def render_trace(signals: Sequence[Signal], truncated: int = 0) -> str:
    """The block the Stop hook injects for the trace half. Empty string when there is nothing.

    ``truncated`` IS RENDERED, AND IT IS A REPAIR. The edge bounds how many commits it reads; the
    first version pushed a sentinel Commit into the population to say so — **and a sentinel carries
    neither item nor avowal, so it never traversed :func:`detect_trace` and the words never
    appeared**. The commit message promising *"an aggregate budget that NAMES what it leaves out"*
    was therefore false, against the very rule this module writes for :func:`_bounded_list`. A cut
    window now speaks **even with no signal at all** — silence after a truncation is the one silence
    that lies.
    """
    if not signals and not truncated:
        return ""
    lines = [
        "[Mnemosyne · end-of-task review — YOUR OWN TRACE] These signals do not come from the "
        "operator's words: they come from what YOU did (read in `git`, no model, no network):",
        "",
    ]
    for signal in signals:
        lines.append(f"  • {_KIND_LABEL[signal.kind]}")
        if signal.quote:
            lines.append(f"      {signal.quote}")
        lines.append(f"      → {signal.advice}")
        lines.append("")
    if truncated:
        lines.append(
            f"\U000026D4 WINDOW TRUNCATED: {truncated} commit(s) of this task were NOT read (aggregate "
            'bound). What sits in them has not been judged — that is not "nothing to report".'
        )
        lines.append("")
    lines.append(
        "\U000026A0\U0000FE0F These signals say that SOMETHING HAPPENED, NEVER what: the judgement stays with you. "
        "If after reading nothing is durable, say so in one line and finish."
    )
    return "\n".join(lines)


#: The trace kinds join the same label table — one home for what the reader sees.
_KIND_LABEL["item_ajoute"] = "ITEM ADDED TO THE PLAN DURING THE TASK"
_KIND_LABEL["aveu"] = "ADMISSION OF ERROR in a commit title"
