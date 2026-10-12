"""The differential trial — a skill is proven by the DIFFERENCE it makes, never by re-reading it.

`references/testing.md` already carries the right doctrine (a fresh agent, the documented entry
point, a real task) — but only as prose. This module adds the arm the doctrine lacks: **the same
task run WITHOUT the artifact**. "Is this skill good?" is a judgement a model renders badly; "do
these two outputs differ?" is an observation it does not miss.

## What two isolated audits changed here, and what they could not close

Tour 1 (14 real sabotages, 13 survived) found the three claimed barriers were sentences: the
blinding function was called by no code, the blind arm's mandate was emitted by no function, and a
verdict was tied to no trial. Tour 2 (16 real, 15 survived) found the repairs closed each audit's
exact case rather than its class, plus two first-order defects: the trial could not judge an output
longer than twenty lines, and the blinding was recoverable 75% of the time because it was a public
deterministic function of the two texts. This version answers those:

* **the blind arm cannot learn the artifact exists** — :func:`build_without_arm` takes the task and
  nothing else; its signature has no parameter to leak with. The residual surface (its own wording)
  is frozen by digest, and the freeze covers **the emitted text**, not a constant a caller can route
  around;
* **the blinding uses a SECRET, not a public hash** — :func:`blind_labels` needs a random salt the
  operator holds and the judge never receives. A judge who reads this file still cannot invert the
  pairing, which the previous hash-only version could not claim (measured: 75% recovery);
* **a verdict cannot exist without the trial it reports** — recording requires the digests of both
  outputs AND of both emitted mandates. Two hand-typed files no longer pass;
* **both arms get the SAME task and the SAME method instructions** — the only asymmetry left is the
  artifact itself. What remains unclosable is declared in :data:`KNOWN_LIMITS` rather than papered
  over: an artifact that merely imposes a format can still differentiate, and only a judge can see
  that.

## What the FIRST REAL USE found, which no audit of the apparatus could

Both audits attacked the channel they could see in the source: recomputing the pairing. The first
real trial (`distillateur`, 2026-07-28) leaked through the one channel no reader of this file looks
at — **the outputs themselves**. The arm that holds the artifact names it: nine identifying strings
in arm 1's text (`SKILL.md`, `DISTILL_SCHEMA`, its own output path), zero in arm 2's. Worse, the
mandate *ordered* the leak: "l'artefact a un trou : NOTE-LE dans ta sortie" — the sentence that
produced the trial's single most valuable finding is also the one that broke its blinding.

The two answers, one per level, because prose alone was what failed:

* the artifact report is REDIRECTED out of the deliverable (a separate file), so the arm no longer
  has to choose between reporting a gap and staying blind;
* :func:`signature_leaks` MEASURES what remains, and :func:`build_judge_arm` refuses to emit a blind
  mandate over leaky outputs. The leak set is *derived from the two mandates*, never a list of
  representations I thought of. Judging anyway is possible — through
  :func:`build_open_judge_arm`, whose signature cannot even accept a salt — but the verdict then
  carries ``blinding="rompu"``, a field with no default that no caller can omit.

Print-only, offline, brick-free: this module emits mandates and records verdicts; it runs no agent
and calls no model. Code & docstrings English (D117); emitted contracts are French.

NOTE ON THIS MIRROR: the mandate text (the arm and judge templates below) is data, not prose about
the code — it is the actual wire format this instrument emits, digest-frozen by the tests in
`test_skill_trial.py`, and read back verbatim by `runtime/skill_trial_run.py`. It is left in its
original French here rather than translated, since translating it would silently change what those
frozen digests and that sibling module actually match on. Decisions: D75, D100 (incapacity over
trust), D92, contract-single-source-emit.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

__all__ = [
    "BLINDING_STATES",
    "KNOWN_LIMITS",
    "LedgerRead",
    "SkillTrialError",
    "TrialEmission",
    "TrialLedger",
    "TrialOutcome",
    "TrialRecord",
    "blind_labels",
    "build_judge_arm",
    "build_open_judge_arm",
    "build_trial",
    "build_with_arm",
    "build_without_arm",
    "digest_of",
    "naming_leaks",
    "new_salt",
    "signature_leaks",
]

#: A TASK is one instruction, interpolated into both mandates — it stays short and tightly bounded.
_MAX_TASK_CHARS = 2000
_MAX_TASK_LINES = 20

#: An OUTPUT is a real deliverable. Applying the task's bounds to it made the trial refuse anything
#: longer than twenty lines — i.e. every real piece of work, and asymmetrically against the arm that
#: produces more. Bounded only against a runaway paste.
_MAX_OUTPUT_CHARS = 400_000

#: What a caller may write in a task, stated as what is PERMITTED rather than what is banned. The
#: previous version blacklisted `---`, `===` and `# BRAS`; an audit walked through it with `___`,
#: `***`, `-- BRAS --` and the Unicode line separators U+2028 / U+0085, which `^` in MULTILINE does
#: not anchor on. Enumerating the forbidden always misses the next representation.
_STRUCTURAL_PUNCT = frozenset("-=_*#~`|<>[]{}")


class SkillTrialError(Exception):
    """A trial could not be built or recorded — always fail closed, never a degraded trial."""


#: Stated limits of the method itself. NOT bugs to be fixed later: properties no mechanism in this
#: module can remove, kept where a reader meets them instead of in a commit message nobody re-reads.
KNOWN_LIMITS = (
    "Arm 1 must read the artifact; arm 2 cannot. This asymmetry IS the trial, but it also favors "
    "an artifact that brings only a FORMAT: the judge is explicitly tasked with distinguishing "
    "extra work from an extra instruction. No code can do this in its place.",
    "A trial measures ONE task. An artifact can differentiate on one and not on another; a single "
    "verdict neither condemns nor sanctifies anything.",
    "The judge is still a model: it can be wrong. What the apparatus guarantees is that it does "
    "not know WHICH arm it is looking at — not that it judges well.",
    "MEASURED on 2026-07-28, first real use: an arm that follows an artifact NAMES it in its "
    "output, and no salt catches that. The code now measures the literal leak "
    "(signature_leaks) and refuses to emit a BLIND mandate over it; what remains impossible to "
    "mechanize is the STYLE leak — a plan, a tone, a structure learned from the artifact carry "
    "no literal signature. The judge is explicitly tasked with saying so.",
    "PICK A TASK WHERE THE OUTPUT CAN BE WRONG. Verdict of the first real judge, and it is the "
    "single most valuable criticism: « a trial with no possibility of failure does not rank "
    "anything ». On a chapter with no figures, no threshold, no table and no claim under "
    "tension, the plan is dictated by the source and the only free axis left is PRESENTATION — "
    "that is, exactly the axis a template controls. The trial then measures conformity and will "
    "call it quality. Pick a task where one can get it wrong: figures to carry over, two claims "
    "to adjudicate, or a length budget that forces a choice between quoting and reasoning.",
    "The refusal only covers signatures that NAME the artifact (a path and its segments). The "
    "rest of the asymmetry is PRINTED to the operator without refusing, because it contains "
    "chance: measured on the 2nd real trial, 3 residual tokens (`make` from an English quotation "
    "in the book, `quoi`, `savoir`) — refusing on those would have killed a clean trial. The "
    "operator sees this list before declaring the verdict's blinding.",
)

#: How blind a verdict actually was. NOT a quality scale: `rompu` means the judge could tell the
#: arms apart, so its verdict is contaminated by expectation and must be read as such.
BLINDING_STATES = ("aveugle", "rompu")

#: Below this length a token discriminates nothing (`de`, `la`, `md`) and only adds noise to the
#: leak report. Stated here rather than buried: it is the one arbitrary number in the detector.
_MIN_SIGNATURE_CHARS = 3


class TrialOutcome(Enum):
    """What the differential trial concluded. The three cases are NOT a severity scale."""

    DIFFERENTIATES = "differencie"
    INDIFFERENT = "ne_differencie_pas"
    HARMS = "nuit"


def _no_control_chars(text: str, *, field: str) -> None:
    """Refuse anything that hides text from whoever proofreads it — by CATEGORY, not by list.

    Unicode general category Cc (control) and Cf (format) cover carriage returns, zero-width joiners
    and bidi overrides alike; Zl/Zp cover U+2028/U+2029, the line separators that slipped past a
    `\\n`-based check. A partition of the codepoint space, not an enumeration of the ones I thought of."""
    for ch in text:
        if ch in "\n\t":
            continue
        if unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"}:
            raise SkillTrialError(
                f"{field}: contains an invisible or separator character "
                f"(U+{ord(ch):04X}, category {unicodedata.category(ch)}) — refused"
            )


def _bounded_task(text: str, *, field: str) -> str:
    """A task: short, no invisible characters, and no line that could pass for a section header."""
    if not text.strip():
        raise SkillTrialError(f"{field}: empty — refused")
    _no_control_chars(text, field=field)
    if len(text) > _MAX_TASK_CHARS:
        raise SkillTrialError(f"{field}: exceeds {_MAX_TASK_CHARS} characters")
    if len(text.splitlines()) > _MAX_TASK_LINES:
        raise SkillTrialError(f"{field}: exceeds {_MAX_TASK_LINES} lines")
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) >= 2 and set(stripped) <= _STRUCTURAL_PUNCT:
            raise SkillTrialError(
                f"{field}: line {stripped!r} is made of structural punctuation and could "
                "pass for a section header — a forged mandate inside the task hijacks an arm."
            )
        if re.match(r"^[^\w]*\s*BRAS\b", stripped, re.IGNORECASE):
            raise SkillTrialError(f"{field}: line {stripped!r} imitates an arm header")
    return text.strip()


def _bounded_field(text: str, *, field: str) -> str:
    """A short identifying field (skill name, author, evidence, digest)."""
    if not text.strip():
        raise SkillTrialError(f"{field}: empty — refused")
    _no_control_chars(text, field=field)
    if len(text) > _MAX_TASK_CHARS:
        raise SkillTrialError(f"{field}: exceeds {_MAX_TASK_CHARS} characters")
    return text.strip()


def _bounded_output(text: str, *, field: str) -> str:
    """An arm's output: a real deliverable, so no line or shape limit — only a runaway guard.

    The previous version ran outputs through the TASK bounds and refused anything over twenty lines.
    That made the instrument unusable on real work, and worse, asymmetric: the arm that produced
    more was the one refused."""
    if not text.strip():
        raise SkillTrialError(f"{field}: empty — an arm that returned nothing cannot be judged")
    if len(text) > _MAX_OUTPUT_CHARS:
        raise SkillTrialError(f"{field}: exceeds {_MAX_OUTPUT_CHARS} characters")
    return text


def digest_of(text: str) -> str:
    """The content digest of a text — over the WHOLE text, never a prefix."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def new_salt() -> str:
    """A fresh secret for one trial. The operator keeps it; the judge never receives it."""
    return secrets.token_hex(16)


def blind_labels(with_output: str, without_output: str, salt: str) -> tuple[str, str]:
    """Return ``(label_of_with_arm, label_of_without_arm)`` — "A"/"B" or "B"/"A".

    ``salt`` is REQUIRED and secret. Without it the pairing was a public function of two texts the
    judge holds: an audit recovered the mapping 75% of the time by simply evaluating both
    hypotheses, while the mandate told the judge it was impossible. With a per-trial secret the
    judge can read this file line by line and still learn nothing.

    Deterministic given the salt, so a trial replays exactly — the salt lives beside the mandates."""
    if not salt.strip():
        raise SkillTrialError("blinding requires a salt — without it the pairing is public")
    paired = f"{salt}\x00{digest_of(with_output)}\x00{digest_of(without_output)}"
    return ("A", "B") if hashlib.sha256(paired.encode("utf-8")).digest()[0] % 2 == 0 else ("B", "A")


def _tokens(text: str) -> frozenset[str]:
    """The comparable words of a text — case-folded, paths and dotted names kept whole.

    `SKILL.md`, `system/skills/distillateur` and `NOTE-LE` must survive as single tokens: they are
    exactly the strings that identify an arm."""
    found = re.findall(r"[\w./\\-]+", text)
    return frozenset(t.casefold() for t in found if len(t) >= _MIN_SIGNATURE_CHARS)


def signature_leaks(
    *, with_mandate: str, without_mandate: str, with_output: str, without_output: str
) -> tuple[str, ...]:
    """Literal strings by which a judge can tell the two arms apart. Empty means no literal leak.

    A signature is a token that (a) appears in exactly ONE of the two mandates and (b) appears in
    that same arm's output and (c) does NOT appear in the other arm's output. All three clauses are
    computed from the four texts — nothing is enumerated here, so a representation I never thought
    of is caught the same as `SKILL.md`. Clause (c) is what keeps ordinary vocabulary out: a common
    word appears in both outputs and cancels.

    What this CANNOT see is style: an arm that learnt a plan or a tone from its artifact leaves no
    literal trace. That is why the judge is asked the question too, and why a `rompu` verdict is
    recorded rather than repaired."""
    only_with = _tokens(with_mandate) - _tokens(without_mandate)
    only_without = _tokens(without_mandate) - _tokens(with_mandate)
    out_with, out_without = _tokens(with_output), _tokens(without_output)
    leaks = ((only_with & out_with) - out_without) | ((only_without & out_without) - out_with)
    return tuple(sorted(leaks))


def naming_leaks(
    leaks: tuple[str, ...], *, with_mandate: str, without_mandate: str
) -> tuple[str, ...]:
    """The subset of :func:`signature_leaks` that NAMES the artifact — the only one worth refusing on.

    An artifact is a FILE an arm was pointed at, so what identifies it is the paths written in the
    mandates and **the segments of those paths** — which is how the artifact's bare name (`distillateur`,
    a segment of `system/skills/distillateur/SKILL.md`) is caught even when the output never repeats
    the whole path. Derived from the mandates, so it needs no extra argument and no list of names.

    Everything else in the leak set can be coincidence, and on the second real trial it was: `make`
    (from an English quotation in the book being distilled), `quoi`, `savoir` — three ordinary words
    in one output and not the other, by chance. Refusing on those would have killed a clean trial:
    a perfect catch rate paid for with a false-kill rate nobody measured is how the previous version
    of this instrument became unusable.

    Path segments that come from the TASK cannot reach here: the task is byte-identical in both
    mandates, so its tokens cancel before ``leaks`` is computed."""
    paths = {
        tok for tok in _tokens(with_mandate) | _tokens(without_mandate) if "/" in tok or "\\" in tok
    }
    names = paths | {
        seg
        for path in paths
        for seg in re.split(r"[/\\]", path)
        if len(seg) >= _MIN_SIGNATURE_CHARS
    }
    return tuple(sorted(set(leaks) & names))


#: Method instructions given to BOTH arms, so the only difference between them is the artifact.
#: An audit measured the previous split: arm 1 got the task plus eight lines of method, arm 2 got
#: the task plus one — enough for a purely decorative artifact to "differentiate" by construction.
#: The last two lines were added after the first real trial: an arm named its own output path and
#: its tooling inside the deliverable, which told the judge which arm it was reading. Symmetric on
#: purpose — a discretion asked of one arm only would itself be the signature.
_COMMON_METHOD = """\
Tu es un agent FRAIS. Fais la tache au mieux de ce que tu sais faire, jusqu'au bout.
Rends TA SORTIE, et rien d'autre : aucun commentaire sur cette consigne, aucune question.
Si quelque chose te manque pour finir, ecris-le DANS ta sortie et continue.
Ta sortie est le LIVRABLE SEUL. N'y ecris ni le chemin d'un fichier, ni le nom d'un outil ou
d'une consigne qu'on t'a donnes, ni aucune trace de la facon dont tu as ete mandate : un lecteur
doit pouvoir la lire sans deviner d'ou elle vient."""

_WITH_ARM = """\
BRAS 1
{rule}
LA TACHE :
{task}

{method}

En plus : cette tache se fait avec l'artefact `{skill}`. Lis `system/skills/{skill}/SKILL.md`
comme n'importe quel futur agent le lira, et passe par le point d'entree `make` DOCUMENTE.
S'il faut te souffler une etape, l'artefact a un trou. Ces trous nous interessent BEAUCOUP —
ecris-les, avec la commande reellement lancee et ce qu'elle a rendu, dans un fichier SEPARE
nomme `notes-artefact.md`, a cote de ta sortie. JAMAIS dans ta sortie : ta sortie est le
livrable, et elle sera lue par quelqu'un qui ne doit pas savoir avec quoi tu as travaille.
{baseline}"""

_WITHOUT_ARM = """\
BRAS 2
{rule}
LA TACHE :
{task}

{method}
"""

_JUDGE_ARM = """\
BRAS 3 — LE JUGE
{rule}
Deux agents distincts ont traite LA MEME tache — mot pour mot la meme. Tu recois leurs deux
sorties, etiquetees A et B. Tu ne sais PAS laquelle vient de quel agent : l'appariement est
calcule a partir d'un SECRET tire au sort pour cette epreuve, que tu n'as pas et que le code ne
contient pas. Inutile de chercher : tu ne peux pas le retrouver.
{task_block}
TON MANDAT :
  1. Les deux sorties different-elles ? Ou, precisement ?
  2. Si oui, laquelle fait mieux LA TACHE — et par quelle preuve CITEE dans la sortie ?
  3. Pas de credit partiel : chaque point est tenu ou ne l'est pas.
  4. La charge de la preuve pese sur l'AFFIRMATION, jamais sur la sortie. Dans le doute, non.
  5. Une sortie qui respecte la FORME sans faire le TRAVAIL est un echec, pas un demi-succes.
  6. PIEGE DE FORME, et c'est le point ou ton jugement est irremplacable : l'un des deux agents a
     peut-etre recu un gabarit (sections, citations, longueur) que l'autre n'avait aucun moyen de
     connaitre. Une sortie mieux RANGEE n'est pas une sortie mieux FAITE. Si la difference que tu
     vois est de forme et non de fond, DIS-LE explicitement — aucun code ne peut le voir a ta place.
  7. Critique l'INSTRUMENT : cette tache separait-elle vraiment les deux, ou n'importe quelle
     sortie plausible passait-elle ? Une epreuve qu'on ne peut pas rater ne mesure rien.

Tu ne conclus PAS sur la valeur d'un artefact — tu n'en connais aucun. Tu rends la DIFFERENCE.

{rule}
SORTIE {label_a}
{rule}
{output_a}

{rule}
SORTIE {label_b}
{rule}
{output_b}
"""

#: THE TASK, GIVEN TO THE JUDGE. Found by a third-party judge on 2026-08-14, on a real trial:
#: the mandate asked it *"which one does THE TASK better"* without ever telling it what the task
#: was. It therefore had to reconstruct the target FROM THE TWO COPIES THEMSELVES -- that is,
#: grade each copy against a rubric derived from those same copies. This is exactly the fault
#: this repo catalogs: *a rubric drawn from what it judges never refuses anything*. The task is
#: the SAME for both arms (that is what they share), so printing it opens no blindness leak.
_TASK_BLOCK = """
LA TACHE QUE LES DEUX ONT RECUE, mot pour mot :
  {task}
"""

#: And when it is MISSING, the mandate ADMITS it to the judge rather than staying silent: a judge
#: who does not know it is grading against a rubric derived from the copies cannot flag that in
#: its verdict.
_TASK_ABSENT = """
\U000026D4 LA TACHE NE T'A PAS ETE FOURNIE. Tu vas donc devoir la reconstruire A PARTIR des deux copies,
   c'est-a-dire les noter contre un bareme derive d'elles-memes. DIS-LE dans ton verdict : c'est
   une limite de l'epreuve, pas de ton jugement.
"""

#: Judging with the blinding admitted broken. Its whole point is that it says so, loudly, to the
#: judge AND in the record — an unlabelled contaminated verdict is worse than no verdict.
_OPEN_JUDGE_ARM = """\
BRAS 3 — LE JUGE, A DECOUVERT (aveuglement ROMPU)
{rule}
\U000026A0\U0000FE0F Cette epreuve N'EST PAS aveugle, et tu dois le savoir. Deux agents ont traite LA MEME tache ;
l'un disposait d'un artefact (une procedure ecrite), l'autre non. La sortie 1 vient de l'agent
QUI AVAIT l'artefact, la sortie 2 de celui qui ne l'avait pas.

Pourquoi tu l'apprends : la sortie de l'agent equipe se designe elle-meme. Signatures mesurees
dans les textes ci-dessous : {leaks}
Te cacher ce que le texte dit deja ne t'aveuglerait pas, ca te ferait deviner en silence.

CE QUE CETTE CONNAISSANCE TE COUTE, et c'est ta tache principale : tu sais lequel est cense
gagner. C'est exactement le biais qui fabrique un faux positif. Donc :
  0. AVANT tout jugement, ecris ce que tu aurais conclu en ignorant les etiquettes — en ne
     regardant QUE le fond. Puis juge. Si les deux conclusions different, DIS-LE : c'est la
     mesure la plus utile que cette epreuve puisse encore rendre.

TON MANDAT :
  1. Les deux sorties different-elles ? Ou, precisement ?
  2. Si oui, laquelle fait mieux LA TACHE — et par quelle preuve CITEE dans la sortie ?
  3. Pas de credit partiel : chaque point est tenu ou ne l'est pas.
  4. La charge de la preuve pese sur l'AFFIRMATION, jamais sur la sortie. Dans le doute, non.
  5. Une sortie qui respecte la FORME sans faire le TRAVAIL est un echec, pas un demi-succes.
  6. PIEGE DE FORME : l'agent equipe a peut-etre recu un gabarit (sections, citations, longueur)
     que l'autre n'avait aucun moyen de connaitre. Une sortie mieux RANGEE n'est pas une sortie
     mieux FAITE. Si la difference que tu vois est de forme et non de fond, DIS-LE.
  7. Critique l'INSTRUMENT : cette tache separait-elle vraiment les deux, ou n'importe quelle
     sortie plausible passait-elle ? Une epreuve qu'on ne peut pas rater ne mesure rien.

{rule}
SORTIE 1 — l'agent QUI AVAIT l'artefact
{rule}
{with_output}

{rule}
SORTIE 2 — l'agent SANS artefact
{rule}
{without_output}
"""

_BASELINE_SNAPSHOT = """
(Compare a l'ETAT PRECEDENT : {baseline}. On ne mesure pas « mieux que rien », qu'on sait deja,
mais « mieux que la version d'avant », qui est la seule question posee.)
"""


def build_with_arm(skill: str, task: str, *, baseline: str | None = None) -> str:
    """The mandate for the arm that HAS the artifact."""
    block = (
        ""
        if baseline is None
        else _BASELINE_SNAPSHOT.format(
            baseline=_bounded_task(baseline, field="the comparison reference")
        )
    )
    return _WITH_ARM.format(
        skill=_bounded_field(skill, field="the skill's name"),
        task=_bounded_task(task, field="the task"),
        method=_COMMON_METHOD,
        baseline=block,
        rule="=" * 88,
    )


def build_without_arm(task: str) -> str:
    """The mandate for the arm that does NOT have the artifact.

    **Its signature is the barrier**: no ``skill`` parameter, no ``baseline`` parameter, so neither
    can leak through any wording choice — this function never holds them."""
    return _WITHOUT_ARM.format(
        task=_bounded_task(task, field="the task"), method=_COMMON_METHOD, rule="=" * 88
    )


def build_judge_arm(
    with_output: str,
    without_output: str,
    salt: str,
    *,
    with_mandate: str,
    without_mandate: str,
    task: str | None = None,
) -> str:
    """The judge's mandate, both outputs relabelled A/B by :func:`blind_labels` under the salt.

    The two mandates are REQUIRED keywords with no default: a caller cannot obtain a blind mandate
    without submitting the material :func:`signature_leaks` needs. If any literal signature survives
    in the outputs, this refuses — blindness one can bypass by not asking for it is decoration."""
    with_output = _bounded_output(with_output, field="arm 1's output")
    without_output = _bounded_output(without_output, field="arm 2's output")
    leaks = signature_leaks(
        with_mandate=with_mandate,
        without_mandate=without_mandate,
        with_output=with_output,
        without_output=without_output,
    )
    naming = naming_leaks(leaks, with_mandate=with_mandate, without_mandate=without_mandate)
    if naming:
        shown = ", ".join(naming[:12]) + (" …" if len(naming) > 12 else "")
        raise SkillTrialError(
            f"BLINDING IMPOSSIBLE: {len(naming)} signature(s) NAME the artifact in one arm's "
            f"output — {shown}. A salt does not compensate for an output that names itself. "
            "Either re-run the offending arm with a corrected mandate, or judge IN THE OPEN "
            "(build_open_judge_arm) and the verdict will carry blinding=rompu."
        )
    label_with, label_without = blind_labels(with_output, without_output, salt)
    first, second = (
        ((label_with, with_output), (label_without, without_output))
        if label_with == "A"
        else ((label_without, without_output), (label_with, with_output))
    )
    return _JUDGE_ARM.format(
        task_block=_TASK_BLOCK.format(task=_bounded_task(task, field="the task"))
        if task
        else _TASK_ABSENT,
        rule="=" * 88,
        label_a=first[0],
        output_a=first[1],
        label_b=second[0],
        output_b=second[1],
    )


def build_open_judge_arm(
    with_output: str, without_output: str, *, with_mandate: str, without_mandate: str
) -> str:
    """Judge with the blinding admitted broken — **this signature cannot accept a salt**.

    There is no parameter through which a caller could make this look blind, and no branch where it
    quietly becomes blind: a mandate emitted here always names which arm is which. The alternative
    considered and rejected was redacting the leaks out of the outputs — that is the producer
    editing the evidence he is about to be judged on, and it is a blacklist besides."""
    with_output = _bounded_output(with_output, field="arm 1's output")
    without_output = _bounded_output(without_output, field="arm 2's output")
    leaks = signature_leaks(
        with_mandate=with_mandate,
        without_mandate=without_mandate,
        with_output=with_output,
        without_output=without_output,
    )
    return _OPEN_JUDGE_ARM.format(
        rule="=" * 88,
        leaks=", ".join(leaks) if leaks else "aucune signature LITTERALE — la fuite est de style",
        with_output=with_output,
        without_output=without_output,
    )


@dataclass(frozen=True, slots=True)
class TrialEmission:
    """The two arm mandates plus the salt — kept separate, never one stream."""

    with_arm: str
    without_arm: str
    salt: str

    def __post_init__(self) -> None:
        if not (self.with_arm.strip() and self.without_arm.strip() and self.salt.strip()):
            raise SkillTrialError("incomplete emission — two mandates and a salt are required")

    def mandate_digests(self) -> tuple[str, str]:
        """What a verdict must cite to prove it reports on THIS emission."""
        return digest_of(self.with_arm), digest_of(self.without_arm)


def build_trial(
    skill: str, task: str, *, baseline: str | None = None, salt: str | None = None
) -> TrialEmission:
    """Both arm mandates and the trial's secret. The judge's mandate comes later — it needs outputs."""
    return TrialEmission(
        with_arm=build_with_arm(skill, task, baseline=baseline),
        without_arm=build_without_arm(task),
        salt=salt or new_salt(),
    )


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """One recorded trial, bound to the outputs AND the mandates it reports on."""

    skill: str
    task: str
    outcome: TrialOutcome
    evidence: str
    with_digest: str
    without_digest: str
    with_mandate_digest: str
    without_mandate_digest: str
    blinding: str
    by: str
    at: str

    def as_json(self) -> str:
        return json.dumps(
            {
                "kind": "skill_trial",
                "skill": self.skill,
                "task": self.task,
                "outcome": self.outcome.value,
                "evidence": self.evidence,
                "with_digest": self.with_digest,
                "without_digest": self.without_digest,
                "with_mandate_digest": self.with_mandate_digest,
                "without_mandate_digest": self.without_mandate_digest,
                "blinding": self.blinding,
                "by": self.by,
                "at": self.at,
            },
            ensure_ascii=False,
            sort_keys=True,
        )


#: Every field a well-formed record carries. A line missing one is COUNTED as malformed, not
#: silently dropped: an audit showed a whole class of loss slipping past a counter that only knew
#: about JSON syntax errors.
_RECORD_FIELDS = frozenset(
    {
        "kind",
        "skill",
        "task",
        "outcome",
        "evidence",
        "with_digest",
        "without_digest",
        "with_mandate_digest",
        "without_mandate_digest",
        "blinding",
        "by",
        "at",
    }
)


@dataclass(frozen=True, slots=True)
class LedgerRead:
    """What the journal holds — and what it could NOT read, counted rather than swallowed."""

    entries: tuple[dict[str, object], ...]
    unreadable: int

    @property
    def harmful(self) -> tuple[dict[str, object], ...]:
        """The verdicts that say the artifact HARMS — the ones with an incentive to disappear."""
        return tuple(e for e in self.entries if e.get("outcome") == TrialOutcome.HARMS.value)


class TrialLedger:
    """Append-only journal of differential trials."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def record(
        self,
        *,
        skill: str,
        task: str,
        outcome: TrialOutcome,
        evidence: str,
        with_digest: str,
        without_digest: str,
        with_mandate_digest: str,
        without_mandate_digest: str,
        blinding: str,
        by: str,
    ) -> TrialRecord:
        """Append one verdict. Requires the digests of both OUTPUTS and both MANDATES.

        Two hand-typed files used to be enough; citing the mandates means the verdict can only be
        about a trial that was actually emitted. Equal output digests are refused — identical texts
        hold no difference to judge.

        ``blinding`` has no default on purpose: a contaminated verdict that forgot to say so reads
        exactly like a clean one, and the first real trial produced precisely that situation."""
        if blinding not in BLINDING_STATES:
            raise SkillTrialError(
                f"blinding must be one of {BLINDING_STATES} — got {blinding!r}. "
                "A verdict that does not say whether it was blind reads as if it were."
            )
        digests = {
            "output 1's digest": with_digest,
            "output 2's digest": without_digest,
            "mandate 1's digest": with_mandate_digest,
            "mandate 2's digest": without_mandate_digest,
        }
        cleaned = {name: _bounded_field(value, field=name) for name, value in digests.items()}
        if cleaned["output 1's digest"] == cleaned["output 2's digest"]:
            raise SkillTrialError(
                "the two outputs have the same digest — no difference to judge"
            )
        if cleaned["mandate 1's digest"] == cleaned["mandate 2's digest"]:
            raise SkillTrialError(
                "the two mandates have the same digest — these are not two distinct arms"
            )
        record = TrialRecord(
            skill=_bounded_field(skill, field="the skill's name"),
            task=_bounded_task(task, field="the task"),
            outcome=outcome,
            evidence=_bounded_field(evidence, field="the evidence"),
            with_digest=cleaned["output 1's digest"],
            without_digest=cleaned["output 2's digest"],
            with_mandate_digest=cleaned["mandate 1's digest"],
            without_mandate_digest=cleaned["mandate 2's digest"],
            blinding=blinding,
            by=_bounded_field(by, field="the verdict's author"),
            at=datetime.now(UTC).isoformat(),
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(record.as_json() + "\n")
        return record

    def read(self) -> LedgerRead:
        """Every recorded trial, oldest first, WITH the count of lines that could not be read.

        A line counts as unreadable if it is not JSON **or** if it lacks a field a record must
        carry — the previous counter only knew about syntax errors, so a whole class of loss was
        invisible."""
        if not self._path.exists():
            return LedgerRead(entries=(), unreadable=0)
        entries: list[dict[str, object]] = []
        unreadable = 0
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                unreadable += 1
                continue
            if not isinstance(entry, dict) or not _RECORD_FIELDS <= set(entry):
                unreadable += 1
                continue
            entries.append(entry)
        return LedgerRead(entries=tuple(entries), unreadable=unreadable)
