"""A CLOSURE NO ONE CAN VERIFY IS NOT A CLOSURE (harvest candidate P1).

> *"`closed` **without `by`** REFUSED; `open_accepted` **without `cost`** REFUSED; bijection
> defect <-> closure"* - `validation/closure_check.py`, from another project.

## THE POPULATION, MEASURED HERE BEFORE WRITING A SINGLE LINE (2026-09-08)

```
ls reports/*.md | grep -v README | wc -l          ->  34
grep -h '^status:' ...        -> 12 ouvert · 22 traite       ->  34/34 classified
grep -lE '^(par|by|traite_par|clos_par):' reports/*.md   ->   0
grep -l  '^traite_le:'        reports/*.md         ->  15   (out of 22 traite)
grep -lE '^(cout|cost|prix):' reports/*.md         ->   0
```

**22 closures, ZERO author.** Seven of them do not even have a date. No one can ask anyone
*"what did you actually do, exactly?"*.

## WHAT IS REFUSED, WHAT IS ONLY PUBLISHED - and why this is not timidity

Refusing all 22 at once **on the day this judge is born** would block the entire repo, and *a
wall installed already full gets bypassed the same day* (`--no-verify`) - that is the doctrine
already written in :mod:`~mnemosyne.production.obligation` (*"we do not punish what already
exists"*). Hence a **RATCHET over the SET**, exactly like
:data:`~mnemosyne.production.derives.PORTES_QUI_DECLARENT`:

* a closure **outside** :data:`HERITAGE_SANS_AUTEUR` and without an author => **REFUSAL**;
* a closure **inside** the heritage set => published, never refused;
* a heritage entry that has **gained** an author (or has disappeared) => **REFUSAL** too: *a
  loosened ratchet no longer ratchets*. It refuses in **both directions**, like `make memoire`.

## WHAT THIS MODULE REFUSES TO BUILD, with its measurement

`open_accepted` **has no object here**: this repo's vocabulary carries exactly two statuses
(`signalements.OPEN = "ouvert"`, `signalements.HANDLED = "traite"`), and
``/usr/bin/grep -rc "status: accepte" reports/`` -> **0**. An *accepted* defect - the
one whose price is wanted - **does not exist** as a state here: `ouvert` means "not yet handled",
not "accepted as-is". Placing a "without cost" refusal on the 12 open ones would charge a price
to defects nobody has accepted. *Creating the `accepte` status is a vocabulary decision for the
user to make, not a side effect of a judge.* The day it exists,
:attr:`Verdict.acceptes_sans_cout` is ready and only needs a population.

## The bijection, and the third bucket

A status outside the vocabulary **does not disappear**: it is NAMED (:attr:`Verdict.inconnus`).
That is the fault `signalements.drain` states in plain words - *"already drained, or a status we
do not recognise"*: two opposite causes in a single silent branch. Measured today: **0 unknown
status out of 34**, so this clause bites on nothing - written here so no one reads its silence as
a guarantee.

Pure **judge**: the population is INJECTED by the edge (:mod:`mnemosyne.runtime.cloture_run`).
Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

#: The only two vocabulary statuses, IMPORTED from their home rather than retyped - a third
#: vocabulary home is exactly what `signalements.py` says it does not want to open.
from .signalements import HANDLED, OPEN

#: The status of a defect ACCEPTED AS-IS, with its price. **IT DOES NOT EXIST YET** (measured:
#: 0 occurrences). Named here so the `acceptes_sans_cout` clause stays readable, never to
#: pretend it bites.
ACCEPTE: Final = "accepte"

STATUTS_CONNUS: Final[frozenset[str]] = frozenset({OPEN, HANDLED, ACCEPTE})


@dataclass(frozen=True, slots=True)
class Defaut:
    """A report, reduced to what closure needs. Deliberately thin (inv. 22).

    ``auteur`` and ``cout`` are strings already cleaned by the edge: ``""`` means "the field is
    absent, empty, or could not be read" - three things the edge does not distinguish and must
    not pretend to distinguish."""

    identifiant: str
    statut: str
    auteur: str = ""
    cout: str = ""


#: **THE RATCHET, WRITTEN BY HAND, AND IT IS A MEASUREMENT - NOT A CHOICE.** The 22 closures
#: without an author as of 2026-09-08, recorded one by one (`for f in reports/*.md`;
#: `status: traite` ∧ no `par:` field). The SET, never the count: *a swap would leave 22 = 22,
#: silent*.
#: **The expected gesture**: as these reports gain a `par:`, REMOVE them from here - and the
#: judge refuses until that is done, so the gain is banked instead of quietly lost again.
HERITAGE_SANS_AUTEUR: Final[frozenset[str]] = frozenset(
    {
        "2026-07-20-endorse-document-n-a-aucune-surface-make-ou-cli",
        "2026-07-20-le-garde-est-une-api-pas-une-incapacite-pour-du-code-hors-system",
        "2026-07-20-le-tick-ignore-knowledge-proposals-8-propositions-inertes-jamais-remontees",
        "2026-07-21-enforce-grammar-crashe-sur-un-type-union-json-schema-au-lieu-de-refuser",
        "2026-07-21-real-runtime-bloque-indefiniment-sur-un-appel-reseau-hf-alors-que-tout-est-en-ca",
        "2026-07-26-policy-write-applique-puis-silencieusement-annule-le-journal-dit-applied-policy",
        "2026-07-26-policy-write-est-un-verrou-mort-personne-ne-peut-elargir-une-autorisation-donc-l",
        "2026-07-29-le-lecteur-de-plans-accepte-un-cap-blanc-cap-rend-cap-donc-la-porte-est-declaree",
        "2026-07-29-plan-nouveau-insere-la-ligne-d-index-en-pleine-prose-pas-dans-la-liste-des-arcs",
        "2026-07-29-ui-json-tableaux-de-synthese-perd-son-fichier-sur-un-plan-dossier-d166-non-appli",
        "2026-08-02-le-garde-ne-sait-autoriser-qu-un-hote-exact-eurostat-vit-sur-un-apex-donc-inatte",
        "2026-08-02-le-hook-stop-impose-le-rituel-de-fin-rien-n-impose-celui-de-debut",
        "2026-08-04-plan-scaffold-grave-la-garantie-le-code-verifie-l-index-dans-les-deux-sens-dans",
        "2026-08-14-detecter-une-lecon-ne-verifie-jamais-qu-elle-a-ete-deposee-l-alarme-s-ignore-san",
        "2026-08-14-les-lecons-que-l-agent-trouve-lui-meme-hors-d-un-titre-de-commit-sont-invisibles",
        "2026-08-15-sonde-classe-fermee-ne-pas-traiter",
        "2026-08-15-sonde-classe-ou-cas-ne-pas-traiter",
        "2026-08-15-sonde-orchestrateur-2-ne-pas-traiter",
        "2026-08-15-sonde-orchestrateur-ne-pas-traiter",
        "2026-08-16-test-audit-chat-1-jamais-applique",
        "2026-08-17-make-carte-voit-67-items-11-arcs-sur-sibling-research-contre-168-items-14-arcs-cot",
        "2026-09-02-fuite-gel-py-stale-depuis-2026-08-07-bloque-tout-commit-via-test-m5-f9-7-vs-f9-8",
    }
)


@dataclass(frozen=True, slots=True)
class Verdict:
    """Everything is NAMED, nothing is counted without the list behind it staying readable."""

    #: `traite` without an author, OUTSIDE the heritage set - the refusal with an object today.
    clos_sans_auteur: tuple[str, ...]
    #: Heritage entries that have GAINED an author (or disappeared): the ratchet must move down.
    heritage_perime: tuple[str, ...]
    #: `accepte` without a price. NULL population today: the status does not exist yet.
    acceptes_sans_cout: tuple[str, ...]
    #: A status outside the vocabulary - NAMED, never silently lost.
    inconnus: tuple[tuple[str, str], ...]
    #: Closures duly attributed.
    attribues: tuple[str, ...]
    #: Closures covered by the ratchet - published, never refused.
    heritees: tuple[str, ...]
    #: The CARDINAL: how many defects were actually judged.
    juges: int

    @property
    def non_mesure(self) -> bool:
        """*A comparison over zero pairs is true by construction.* Zero defects judged is
        never a green: it is an instrument failure (missing folder, filter too narrow)."""
        return self.juges == 0

    @property
    def refuse(self) -> bool:
        return bool(
            self.clos_sans_auteur
            or self.heritage_perime
            or self.acceptes_sans_cout
            or self.inconnus
        )


def verdict(
    defauts: Iterable[Defaut], *, heritage: frozenset[str] = HERITAGE_SANS_AUTEUR
) -> Verdict:
    """The PURE judge - it reads no file, it classifies an injected population.

    **THE BIJECTION IS THE BARRIER**: every defect falls into EXACTLY one bucket, and the total
    across buckets is published (:attr:`Verdict.juges`). A silent "other" bucket would be exactly
    the failure this module exists to close off."""
    clos_sans_auteur: list[str] = []
    acceptes_sans_cout: list[str] = []
    inconnus: list[tuple[str, str]] = []
    attribues: list[str] = []
    heritees: list[str] = []
    vus: set[str] = set()

    for d in defauts:
        vus.add(d.identifiant)
        if d.statut == HANDLED:
            if d.auteur.strip():
                attribues.append(d.identifiant)
            elif d.identifiant in heritage:
                heritees.append(d.identifiant)
            else:
                clos_sans_auteur.append(d.identifiant)
        elif d.statut == ACCEPTE:
            if not d.cout.strip():
                acceptes_sans_cout.append(d.identifiant)
        elif d.statut != OPEN:
            inconnus.append((d.identifiant, d.statut))

    # THE RATCHET REFUSES IN BOTH DIRECTIONS. A heritage entry that gained an author, or that
    # disappeared from the population, must COME OUT of the freeze: otherwise the gain is quietly
    # lost again with no red to say so, and the ratchet ends up covering closures it never measured.
    encore_heritees = frozenset(heritees)
    heritage_perime = tuple(sorted(heritage - encore_heritees))

    return Verdict(
        clos_sans_auteur=tuple(sorted(clos_sans_auteur)),
        heritage_perime=heritage_perime,
        acceptes_sans_cout=tuple(sorted(acceptes_sans_cout)),
        inconnus=tuple(sorted(inconnus)),
        attribues=tuple(sorted(attribues)),
        heritees=tuple(sorted(heritees)),
        juges=len(vus),
    )


def message(v: Verdict) -> str:
    """The page. It **always** says how many it judged, and it NAMES every cause.

    **ALL causes present are rendered, never just the first one**: a register with two faults
    that names only one sends you to fix it, come back, and hit a second red."""
    if v.non_mesure:
        return (
            "\U000026A0\U0000FE0F CLOTURES NON MESUREES : zero defaut juge. « aucune cloture sans auteur » et « je "
            "n'ai trouve aucun rapport » ne se lisent pas pareil - une population vide est une "
            "panne d'instrument, jamais un vert."
        )
    lignes = [
        f"clotures attribuees : {len(v.attribues)}/{len(v.attribues) + len(v.heritees)} "
        f"(sur {v.juges} defaut(s) juge(s) ; {len(v.heritees)} couverte(s) par le cliquet)"
    ]
    if v.clos_sans_auteur:
        lignes.append(
            f"\U000026D4 {len(v.clos_sans_auteur)} cloture(s) SANS AUTEUR hors du cliquet : "
            + ", ".join(v.clos_sans_auteur)
            + ". Une cloture que personne ne peut verifier n'est pas une cloture : ajoute "
            "`par: <qui>` dans le frontmatter, ou inscris le rapport dans `HERITAGE_SANS_AUTEUR` "
            "(`system/lib/mnemosyne/production/cloture.py`) en disant pourquoi."
        )
    if v.heritage_perime:
        lignes.append(
            f"\U000026D4 {len(v.heritage_perime)} entree(s) du cliquet ne sont plus des clotures sans "
            "auteur : " + ", ".join(v.heritage_perime) + ". RETIRE-LES de "
            "`HERITAGE_SANS_AUTEUR` pour encaisser le gain - un cliquet desserre ne cliquette plus."
        )
    if v.acceptes_sans_cout:
        lignes.append(
            f"\U000026D4 {len(v.acceptes_sans_cout)} defaut(s) ACCEPTE(S) sans leur prix : "
            + ", ".join(v.acceptes_sans_cout)
            + ". Un defaut accepte sans son cout est un defaut oublie avec bonne conscience : "
            "ajoute `cout: <ce que ca coute de vivre avec>`."
        )
    if v.inconnus:
        lignes.append(
            f"\U000026D4 {len(v.inconnus)} statut(s) HORS VOCABULAIRE : "
            + ", ".join(f"{i} (`{s}`)" for i, s in v.inconnus)
            + f". Les seuls statuts connus sont {', '.join(sorted(STATUTS_CONNUS))} - un statut "
            "inconnu ne disparait plus en silence, il est nomme ici."
        )
    return "\n".join(lignes)
