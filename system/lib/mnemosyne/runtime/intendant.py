"""The Intendant — the store of what the operator dumps out, and the memory of its threads.

This module is **the foundation of the first of the three agents** (`projects/mnemosyne/ui/AGENTS.md`).
It holds two things, and nothing else: the NOTES the operator dictates, and the THREADS of conversation
that survive closing the window. No model, no brick, no network — that is deliberate, and it is
measured: ``make memory-queue`` takes **~11 s** to start because it loads Docling + bge-m3 + the
reranker *before writing a single line of text*. For a tool the operator wants to open thirty times a
day, that price kills it. Here, recording a thought is a file write.

**Recording NEVER depends on the model.** The operator dictates, the line is written, period. Sorting
(kind / topics / horizon / return situation) arrives *afterwards*, in a ``modif`` line, once a model is
around to propose it. If the model is off, refuses, or goes off the rails, the thought is still safe.
The reverse — sort first, write after — would lose exactly what the operator asks this tool to never
lose.

**Topics are FREE.** I had proposed constraining them to the 22 declared domains in ``domains.toml``,
so that what the operator files becomes searchable by the library without a bridge. He refused, in
these words: *"no, I don't agree. Give me freedom. Don't restrict me."* So there is no validation here,
no closed list. The price is real (two vocabularies that never meet) and it is HIS to pay, not imposed.

**Non-destructive (invariant 2).** The journal is APPEND ONLY. Removing a note, or marking it done,
writes one more line — never a deletion, never a rewrite. Reading replays the journal and returns only
the current state: a removed note **disappears from what the agent reads**, while staying in the
journal, where the agent does not look. That is how "I want it to disappear" is satisfied without
breaking "we never erase".

Code, docstrings and every operator-facing string are English (D33/D117). Two things stay
French ON PURPOSE and are NOT prose: the journal's stored field values (``horizon``/``genre``/
``etat`` and the legacy ``court``/``moyen``/``long``), which are DATA KEYS an append-only journal
already carries, and the deferral regexes :data:`_DIFFERE` / :data:`_PLUS_TARD`, which MATCH what
the operator dictates in French - translating either would change behaviour, not language.
Tested without a brick — it has none.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: The three old horizons — court/moyen/long (short/medium/long-term) — are DEAD by the operator's
#: own verdict, from actual use: *"short term, medium term, long term, that doesn't mean anything to
#: me. I realize that."* What his list holds now are three SECTIONS of a different nature, not three
#: deadlines on the same rule: a general TODO (no date), a DEADLINE (with a due date, sorted by
#: urgency), a ROUTINE (recurring). Closed, because it is the FRAME of the screen — not the vocabulary
#: of what he says, which stays free.
HORIZONS: tuple[str, ...] = ("deadline", "todo", "routine")

#: The old values, still present in the journal from previous sessions (29 notes filed before this
#: day). The journal is APPEND ONLY (inv. 2): they are NEVER rewritten. On READ only, they fall back
#: into "todo" — the only one of the three sections that requires nothing more than a title, exactly
#: what they carried.
_HORIZONS_HERITES: dict[str, str] = {"court": "todo", "moyen": "todo", "long": "todo"}

#: What a note IS. Closed for the same reason: the screen groups by it.
GENRES: tuple[str, ...] = ("tache", "pensee", "regle", "projet")

#: A note's states along the READ path. `retiree` (removed), `faite` (done) and `versee` (poured out)
#: all leave the default view; none ever leaves the journal.
#:
#: `versee` is the state of a DUMP that daughter notes were drawn from. The operator: *"if I send a
#: huge block of text with 500 different topics, that's going to end up as a single task, that makes
#: no sense"*. The whole message stays written (that is the guarantee: nothing depends on the model),
#: but it leaves the view as soon as its daughters exist — otherwise the screen would show both the
#: block AND the tasks drawn from it.
ETATS: tuple[str, ...] = ("vive", "faite", "retiree", "versee")

_VERSION = 1


def racine() -> Path:
    """The store's folder. ``MNEMO_INTENDANT_RACINE`` relocates it — that is what makes this module
    testable without touching the operator's real notes."""
    surcharge = os.environ.get("MNEMO_INTENDANT_RACINE")
    if surcharge:
        return Path(surcharge)
    return Path(__file__).resolve().parents[3] / "state" / "intendant"


def _journal() -> Path:
    return racine() / "notes.jsonl"


def _dossier_fils() -> Path:
    return racine() / "fils"


def _maintenant() -> str:
    """The timestamp, to the MICROSECOND.

    The first version stopped at the second, and a test killed it: two threads touched in the
    same second were tie-broken at random, so ``fil_dernier()`` could reopen the wrong one. That is
    precisely the operator's own case — *"I reopen it two seconds later"*: the one granularity where
    the tool had to be exact was the one where it was wrong. These timestamps serve to SORT as much
    as to display; the precision costs nothing, and the lack of it cost the guarantee."""
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _neuf_id() -> str:
    return uuid.uuid4().hex[:12]


def _ecrire_ligne(objet: dict[str, Any]) -> None:
    """Appends ONE line to the journal. Creates the folder if needed. Never a rewrite."""
    chemin = _journal()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(objet, ensure_ascii=False) + "\n")


def _lignes() -> list[dict[str, Any]]:
    """Every readable line of the journal, in write order.

    An unreadable line is SKIPPED, not fatal: an append-only journal can end on a truncated write
    (a power cut), and losing the 400 healthy lines because of the 401st would be the worst of both
    worlds."""
    chemin = _journal()
    if not chemin.is_file():
        return []
    sorties: list[dict[str, Any]] = []
    for brut in chemin.read_text(encoding="utf-8").splitlines():
        if not brut.strip():
            continue
        try:
            objet = json.loads(brut)
        except json.JSONDecodeError:
            continue
        if isinstance(objet, dict):
            sorties.append(objet)
    return sorties


# ── DEPOSIT ─────────────────────────────────────────────────────────────────────────────────────


def _echeance_valide(echeance: str) -> str:
    """The due date as-is if it is a readable ISO date, else "".

    Neither mandatory nor strict about the exact form (the browser's `datetime-local` field and a
    model writing a date do not necessarily use the same precision) — only a filter against text
    that is plainly not a date, so a sort or a count never fails on an unspeakable value."""
    propre = echeance.strip()
    if not propre:
        return ""
    try:
        datetime.fromisoformat(propre.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return propre


def deposer(
    texte: str,
    *,
    mode: str = "",
    fil: str = "",
    genre: str = "",
    sujets: Iterable[str] | None = None,
    horizon: str = "",
    quand: str = "",
    resume: str = "",
    parent: str = "",
    echeance: str = "",
    description: str = "",
) -> dict[str, Any]:
    """Writes ONE thought into the store, immediately. Returns the note as stored.

    ``texte`` is the operator's VERBATIM and is never rewritten — not here, nor by a later sort. The
    Intendant's ``resume`` (summary) lives next to it, it does not replace it: that is the only way
    to always be able to go back to what he said, rather than to what a model understood of it.

    ``echeance`` (due date) only means something for a ROOT in the ``deadline`` section — it is what
    feeds the screen's countdown and urgency sort. ``description`` is free on any task.

    Everything else is optional, because recording must never wait on sorting."""
    propre = texte.strip()
    if not propre:
        raise ValueError("nothing to record")
    note = {
        "id": _neuf_id(),
        "texte": propre,
        "resume": resume.strip(),
        "genre": genre if genre in GENRES else "",
        "sujets": [s.strip() for s in (sujets or []) if s and s.strip()],
        "horizon": horizon if horizon in HORIZONS else "",
        "quand": quand.strip(),
        "mode": mode.strip(),
        "fil": fil.strip(),
        # The dump this note was drawn from, if any. Keeps the link to the entire VERBATIM: an
        # extracted note is a reading, and it must always be possible to trace back to what the
        # operator actually said.
        "parent": parent.strip(),
        "echeance": _echeance_valide(echeance),
        "description": description.strip(),
        "etat": "vive",
        "depose_le": _maintenant(),
    }
    _ecrire_ligne({"v": _VERSION, "ts": note["depose_le"], "geste": "depot", "note": note})
    _ecrire_liste_md()
    return note


def ranger(
    note_id: str,
    *,
    genre: str = "",
    sujets: Iterable[str] | None = None,
    horizon: str = "",
    quand: str = "",
    resume: str = "",
    echeance: str = "",
    description: str = "",
    parent: str = "",
) -> dict[str, Any]:
    """Completes the sorting of a note ALREADY recorded — the second pass, the model's or an
    operator click's (move to a section, set a due date, write a description).

    ``parent`` RE-PARENTS an already-existing note — the gesture that was missing to turn a flat
    list of 28 tasks into themes + sub-tasks without rewriting anything: the operator had tasks filed
    FLAT (the migrated portrait), and the only way to regroup them after the fact was to redo the
    recording. The only guard: a note cannot become ITS OWN mother — the same lightness as
    ``deposer`` (which also does not check that the parent exists), because the guarantee that
    matters lies elsewhere: a sub-task whose mother is not readable becomes a root again
    (`par_horizon`), it never disappears.

    Only overwrites what is supplied AND valid: a model that returns an invented kind leaves the
    field as it was, it does not fill it with anything. Writes a ``modif`` line, never touches the
    original line."""
    champs: dict[str, Any] = {}
    if genre in GENRES:
        champs["genre"] = genre
    if horizon in HORIZONS:
        champs["horizon"] = horizon
    if sujets is not None:
        champs["sujets"] = [s.strip() for s in sujets if s and s.strip()]
    if quand.strip():
        champs["quand"] = quand.strip()
    if resume.strip():
        champs["resume"] = resume.strip()
    if echeance.strip():
        valide = _echeance_valide(echeance)
        if valide:
            champs["echeance"] = valide
    if description.strip():
        champs["description"] = description.strip()
    if parent.strip() and parent.strip() != note_id:
        champs["parent"] = parent.strip()
    if not champs:
        return {}
    _ecrire_ligne(
        {"v": _VERSION, "ts": _maintenant(), "geste": "modif", "id": note_id, "champs": champs}
    )
    _ecrire_liste_md()
    return champs


def marquer(note_id: str, etat: str) -> None:
    """Moves a note to ``faite`` (done) or ``retiree`` (removed) — via ONE MORE line (invariant 2).

    ``retiree`` takes it off the read path. It stays in the journal, where the agent does not look:
    the operator gets "it disappears", Mnémosyne keeps "we never erase"."""
    if etat not in ETATS:
        raise ValueError(f"unknown state: {etat!r} (expected: {', '.join(ETATS)})")
    _ecrire_ligne(
        {"v": _VERSION, "ts": _maintenant(), "geste": "etat", "id": note_id, "etat": etat}
    )
    _ecrire_liste_md()


def reordonner(ids: list[str]) -> None:
    """Fixes the MANUAL order of a group of SIBLING notes — the gesture the operator asked for:
    "being able to sort them however I want by dragging them". ``ids`` is the complete list, in the
    chosen visual order, of the tasks of ONE SINGLE list (a section, or the sub-tasks of one mother)
    — never a mix of two lists, the screen never offers that.

    One ``modif`` line per note (the same family as ``ranger``, never a rewrite — inv. 2): ``ordre``
    carries its position, 0 first. A note never moved has no such field and keeps sorting by
    recording time (``par_horizon`` places it ahead of anything with an explicit order) — manual
    sorting is therefore never all-or-nothing, it only touches what the operator actually dragged."""
    for position, note_id in enumerate(ids):
        propre = str(note_id).strip()
        if not propre:
            continue
        _ecrire_ligne(
            {
                "v": _VERSION,
                "ts": _maintenant(),
                "geste": "modif",
                "id": propre,
                "champs": {"ordre": position},
            }
        )
    _ecrire_liste_md()


# ── THE BACKUP COPY — a .md view, readable WITHOUT the server or the browser ──────────────────────
#
# The operator: *"make sure there's a continuous backup of the metadata [...] so if one day there's
# some screwup with the UI, I can still get to my tasks somewhere [...] the list of the list's current
# state at all times"*. `notes.jsonl` is already the truth (inv. 24: `.md` + git, or here the journal,
# is the arbiter), but reading an append-only JSONL journal requires replaying it — not a gesture you
# can do from a panicking text editor. This copy IS that reading, already done, rewritten on every
# mutation: never the truth (`lire()` stays the sole arbiter), never hand-edited, purely derived — one
# MORE file, never a second place to write to.


def _rendre_liste_md(notes: list[dict[str, Any]] | None = None) -> str:
    """The backup copy's content — what the screen shows, in Markdown rather than HTML."""
    source = lire() if notes is None else notes
    groupes = par_horizon(source)
    connus = {str(n.get("id", "")) for n in source}
    enfants: dict[str, list[dict[str, Any]]] = {}
    for n in source:
        p = str(n.get("parent", ""))
        if p and p in connus:
            enfants.setdefault(p, []).append(n)

    def libelle(n: dict[str, Any]) -> str:
        return str(n.get("resume") or n.get("texte", ""))

    def lignes_pour(n: dict[str, Any], profondeur: int) -> list[str]:
        morceau = libelle(n)
        if n.get("echeance"):
            morceau += f" (due {n['echeance']})"
        sortie = ["  " * profondeur + f"- {morceau}"]
        if n.get("description"):
            sortie.append("  " * (profondeur + 1) + f"> {n['description']}")
        for fille in enfants.get(str(n.get("id", "")), []):
            sortie.extend(lignes_pour(fille, profondeur + 1))
        return sortie

    titres = {"routine": "Routine", "deadline": "Deadlines", "todo": "To-do", "sans": "To sort"}
    blocs = [
        "# The operator's list — backup copy",
        f"> Regenerated automatically on every change, last time on {_maintenant()}. "
        "Read-only: this is not where it gets edited — it is a COPY, never the truth "
        "(which lives in `notes.jsonl`).",
        "",
    ]
    for horizon in ("routine", "deadline", "todo", "sans"):
        racines = groupes.get(horizon, [])
        if not racines:
            continue
        blocs.append(f"## {titres[horizon]}")
        for racine in racines:
            blocs.extend(lignes_pour(racine, 0))
        blocs.append("")
    return "\n".join(blocs).rstrip() + "\n"


def _ecrire_liste_md() -> None:
    """Writes the backup copy, atomically — on a BEST-EFFORT basis: a write failure here must never
    fail the real recording (which, itself, has already succeeded in the journal right before this
    call). A backup copy that could itself break the gesture it is meant to secure would be worse
    than not having one."""
    try:
        chemin = racine() / "liste.md"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(chemin.parent), delete=False, suffix=".tmp"
        )
        try:
            tmp.write(_rendre_liste_md())
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            tmp.close()
        os.replace(tmp.name, chemin)
    except OSError:
        pass


# ── READ ────────────────────────────────────────────────────────────────────────────────────────


def lire(*, tous: bool = False) -> list[dict[str, Any]]:
    """Replays the journal and returns the CURRENT state of the notes, most recent first.

    By default, only ``vive`` (live) notes come out: this is the READ path, the one the agent and
    the screen see. ``tous=True`` also returns the done and removed ones — for an archive view,
    never to feed an agent."""
    etat: dict[str, dict[str, Any]] = {}
    for ligne in _lignes():
        geste = ligne.get("geste")
        if geste == "depot":
            note = ligne.get("note")
            if isinstance(note, dict) and note.get("id"):
                etat[str(note["id"])] = dict(note)
        elif geste == "modif":
            note = etat.get(str(ligne.get("id", "")))
            champs = ligne.get("champs")
            if note is not None and isinstance(champs, dict):
                note.update(champs)
                note["range_le"] = ligne.get("ts", "")
        elif geste == "etat":
            note = etat.get(str(ligne.get("id", "")))
            if note is not None and ligne.get("etat") in ETATS:
                note["etat"] = ligne["etat"]
                note["etat_le"] = ligne.get("ts", "")
    notes = list(etat.values())
    if not tous:
        notes = [n for n in notes if n.get("etat") == "vive"]
    notes.sort(key=lambda n: str(n.get("depose_le", "")), reverse=True)
    return notes


def par_horizon(notes: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    """The sections of the operator's list: deadline / todo / routine, plus ``sans`` for the
    unsorted.

    **Only ROOT tasks take a section.** A sub-task lives under its mother, not in a section:
    listing it separately too would make it appear TWICE, and the section's count would stop saying
    "what I have to do here".

    A sub-task whose mother is no longer on the read path (the operator removed it) becomes a root
    again: better to see it as an orphan than to lose it in silence.

    LEGACY values (``court``/``moyen``/``long``, filed before the list became three sections rather
    than three deadlines) fall back to ``todo`` HERE, on read — never rewritten to the journal
    (inv. 2). This is the only normalization in this whole module that does not come from a field
    stored as-is.

    ``sans`` is not a fourth section: it is the queue of what has not been sorted yet. Showing it is
    the only way nothing gets lost in between."""
    source = lire() if notes is None else notes
    connus = {str(n.get("id", "")) for n in source}
    groupes: dict[str, list[dict[str, Any]]] = {h: [] for h in HORIZONS}
    groupes["sans"] = []
    for note in source:
        if str(note.get("parent", "")) in connus and note.get("parent"):
            continue
        cle = _HORIZONS_HERITES.get(note.get("horizon") or "", note.get("horizon") or "sans")
        groupes[cle if cle in groupes else "sans"].append(note)
    return {h: _trier_manuel(taches) for h, taches in groupes.items()}


def _trier_manuel(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Notes touched by `reordonner` sort by their chosen `ordre`, AFTER all the others — which keep
    the recording order already carried by `source` (a stable sort: an identical key does not change
    relative order). A section never dragged-and-dropped therefore sees no difference; a new note,
    on the other hand, always appears first until the operator has sorted it somewhere himself."""
    return sorted(notes, key=lambda n: (1, n["ordre"]) if n.get("ordre") is not None else (0, 0))


# ── SEARCH ──────────────────────────────────────────────────────────────────────────────────────


def _plier(texte: str) -> str:
    """Lowercase, no accents — so a search for "prefere" finds "préféré" (the accented example
    is the demonstration: it must stay accented or it demonstrates nothing).

    The operator dictates by voice: accents fall wherever chance has it in the transcription. A
    search that requires them would find nothing half the time."""
    sans = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in sans if unicodedata.category(c) != "Mn")


def chercher(question: str, *, limite: int = 20, tous: bool = False) -> list[dict[str, Any]]:
    """Searches the store, full text, with no model and no index — instant.

    Score = number of the question's words found, with the words of ``texte`` and ``sujets``
    weighing double compared to ``resume``: what the OPERATOR said must come out first, not what a
    model summarized of it.

    An empty question returns the recent notes rather than nothing: "what had I noted?" is a
    legitimate question, and an empty screen does not answer it."""
    notes = lire(tous=tous)
    mots = [m for m in re.split(r"\W+", _plier(question)) if len(m) > 2]
    if not mots:
        return notes[:limite]
    resultats: list[tuple[int, dict[str, Any]]] = []
    for note in notes:
        fort = _plier(str(note.get("texte", "")) + " " + " ".join(note.get("sujets", [])))
        faible = _plier(str(note.get("resume", "")) + " " + str(note.get("quand", "")))
        score = sum(2 for m in mots if m in fort) + sum(1 for m in mots if m in faible)
        if score:
            resultats.append((score, note))
    resultats.sort(key=lambda paire: (-paire[0], str(paire[1].get("depose_le", ""))), reverse=False)
    return [note for _, note in resultats[:limite]]


def pertinentes(texte: str, *, limite: int = 5, sauf: str = "") -> list[dict[str, Any]]:
    """What the operator has already said that bears on what he is saying RIGHT NOW.

    This is the other half of his request — *"I remember I'd thought of something, but I don't
    remember exactly what it is, go look for it"* — except that here he does not ask: it happens on
    its own, via the base prompt. A recall that has to be requested never fires at the moment it
    would actually be useful.

    ``sauf`` excludes the note that was just written: it matches itself perfectly and would take up
    all the room, feeding the model what it has just already read."""
    trouvees = chercher(texte, limite=limite + 1)
    return [n for n in trouvees if n.get("id") != sauf][:limite]


def rappeler_situation(situation: str, *, limite: int = 10) -> list[dict[str, Any]]:
    """The pending notes whose return SITUATION resembles what the operator is doing right now.

    This is the deferral mechanism, which he described this way: *"not now, [do it] when I do
    that"*, then *"don't forget, now that you're working on that"*. A note with no ``quand``
    (situation) is not concerned: it was not waiting for anything in particular."""
    mots = [m for m in re.split(r"\W+", _plier(situation)) if len(m) > 2]
    if not mots:
        return []
    resultats: list[tuple[int, dict[str, Any]]] = []
    for note in lire():
        cible = _plier(str(note.get("quand", "")))
        if not cible:
            continue
        score = sum(1 for m in mots if m in cible)
        if score:
            resultats.append((score, note))
    resultats.sort(key=lambda paire: -paire[0])
    return [note for _, note in resultats[:limite]]


# ── THE THREADS — instant memory ───────────────────────────────────────────────────────────────
#
# The operator's request, word for word: *"I want to be able to talk with it, I shut down and I
# forgot to say something, I reopen two seconds later, I can pick the conversation back up with it
# directly as if I'd never left."*
#
# The prior workbench kept its thread IN MEMORY ONLY (`Atelier._fil`), and its own docstring said so:
# "Nothing is persisted — no history, no transcript." That is exactly what needed to change, and it
# is the one thing in this v1 whose absence would make everything else pointless.


def _chemin_fil(fil_id: str) -> Path:
    """The file for a thread. Refuses an id that would try to escape the folder.

    An id travels via an HTTP request: letting it carry ``../`` would let a page write anywhere on
    disk. The filter sits here, at the filesystem's edge, not in the caller — a caller that forgets
    to filter is an open door; a barrier placed at the edge cannot be forgotten."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", fil_id or ""):
        raise ValueError(f"invalid thread id: {fil_id!r}")
    return _dossier_fils() / f"{fil_id}.json"


def fil_neuf(titre: str = "", modele: str = "") -> dict[str, Any]:
    """Opens an empty thread and writes it right away, so it exists even with zero turns."""
    fil = {
        "v": _VERSION,
        "id": _neuf_id(),
        "titre": titre.strip(),
        "modele": modele.strip(),
        "mode": "",
        "cree_le": _maintenant(),
        "touche_le": _maintenant(),
        "tours": [],
    }
    fil_ecrire(fil)
    return fil


def fil_lire(fil_id: str) -> dict[str, Any] | None:
    """A thread, or None if it does not exist / is unreadable.

    Unreadable returns None rather than raising: a corrupted thread must cost ONE thread, never the
    whole screen."""
    try:
        chemin = _chemin_fil(fil_id)
    except ValueError:
        return None
    if not chemin.is_file():
        return None
    try:
        objet = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return objet if isinstance(objet, dict) else None


def fil_ecrire(fil: dict[str, Any]) -> None:
    """Writes an ENTIRE thread, atomically.

    Temp file then ``os.replace``: an interrupted write leaves the old thread intact instead of a
    truncated JSON. The operator closes the window in the middle of a turn — that is the NORMAL case
    for this tool, not the accident."""
    fil_id = str(fil.get("id", ""))
    chemin = _chemin_fil(fil_id)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fil["touche_le"] = _maintenant()
    tmp = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(chemin.parent), delete=False, suffix=".tmp"
    )
    try:
        json.dump(fil, tmp, ensure_ascii=False, indent=1)
        tmp.flush()
        os.fsync(tmp.fileno())
    finally:
        tmp.close()
    os.replace(tmp.name, chemin)


def fil_ajouter(
    fil_id: str,
    demande: str,
    reponse: str,
    *,
    secondes: float | None = None,
    aucun_outil: bool = False,
) -> dict[str, Any] | None:
    """Appends ONE exchange to a thread and persists it immediately.

    Immediately, and not on close: an end-of-session persistence does not survive an abrupt close,
    which is precisely the case the operator describes.

    ``secondes`` — the model's GENERATION time for THIS turn (measured by the caller, never
    recomputed here) — lives on the ``intendant`` turn only: the operator's question has no
    generation duration, only the answer does.

    ``aucun_outil`` (no tool) — measured under real conditions (2026-08-11): a model can answer
    "Filed: 'Run to launch' (todo) with 2 sub-task(s)…" — perfectly credible text, in the exact
    shape of a real tool confirmation — WITHOUT having called `poser_tache`. The store, checked,
    held nothing. `aucun_outil=True` (set by the caller, who alone knows whether `executer_outil`
    actually ran this time) flags the turn so the screen can show an honest signal instead of
    letting any confident-sounding text pass for a real action — neither hidden, nor guessed
    after the fact from the text (the same shape serves REAL confirmations too)."""
    fil = fil_lire(fil_id)
    if fil is None:
        return None
    horodate = _maintenant()
    fil.setdefault("tours", []).append({"role": "operator", "texte": demande, "ts": horodate})
    tour_intendant: dict[str, Any] = {"role": "intendant", "texte": reponse, "ts": horodate}
    if secondes is not None:
        tour_intendant["secondes"] = secondes
    if aucun_outil:
        tour_intendant["aucun_outil"] = True
    fil["tours"].append(tour_intendant)
    if not fil.get("titre"):
        # The title is born from the operator's FIRST sentence, never from the model's answer: he
        # is the one who has to recognize his thread in a list, and he recognizes his own words.
        fil["titre"] = (demande.strip().split("\n")[0])[:70]
    fil_ecrire(fil)
    return fil


def fils_lister(limite: int = 50) -> list[dict[str, Any]]:
    """The threads, most recently touched to oldest — without their turns.

    Without the turns, because this list is used to CHOOSE a thread: loading a hundred whole
    conversations to display a hundred titles would cost the very time this v1 exists to save."""
    dossier = _dossier_fils()
    if not dossier.is_dir():
        return []
    resume: list[dict[str, Any]] = []
    for chemin in dossier.glob("*.json"):
        try:
            objet = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(objet, dict):
            continue
        resume.append(
            {
                "id": objet.get("id", chemin.stem),
                "titre": objet.get("titre", ""),
                "modele": objet.get("modele", ""),
                "mode": objet.get("mode", ""),
                "cree_le": objet.get("cree_le", ""),
                "touche_le": objet.get("touche_le", ""),
                "tours": len(objet.get("tours", [])) // 2,
            }
        )
    resume.sort(key=lambda f: str(f.get("touche_le", "")), reverse=True)
    return resume[:limite]


def fil_dernier() -> dict[str, Any] | None:
    """The most recently touched thread — the one reopened when the operator comes back.

    This is the exact translation of "I reopen it two seconds later and pick back up": the screen
    does not have to ask which one, it reopens the one he just left."""
    fils = fils_lister(limite=1)
    if not fils:
        return None
    return fil_lire(str(fils[0]["id"]))


# ── WHAT THE SCREEN READS ──────────────────────────────────────────────────────────────────────


def etat() -> dict[str, Any]:
    """Everything the screen needs in ONE read: the grouped store, the threads, the counts."""
    notes = lire()
    groupes = par_horizon(notes)
    return {
        "notes": notes,
        "par_horizon": {h: groupes[h] for h in (*HORIZONS, "sans")},
        "comptes": {h: len(groupes[h]) for h in (*HORIZONS, "sans")},
        "total": len(notes),
        "fils": fils_lister(),
        "modes": [{"clef": c, **d} for c, d in MODES.items()],
        "outils": [{"nom": n, **d} for n, d in OUTILS.items()],
        "racine": str(racine()),
        "lu_le": _maintenant(),
    }


# ── THE MODES ───────────────────────────────────────────────────────────────────────────────────
#
# The operator's request: *"having like modes for it […] I press the technical mode on the
# Intendant, and now it's more technical and it knows I'm going to talk to it about LLMs, trading or
# workflows"*. A mode does exactly ONE thing: add a sentence to the base prompt saying what the
# conversation is about. It restricts NOTHING — the operator explicitly refused to have what he can
# say bounded (*"give me freedom, don't restrict me"*), so a mode orients, it does not forbid, and
# talking about something else within a mode remains perfectly legal.

MODES: dict[str, dict[str, str]] = {
    "libre": {
        "titre": "Free",
        "amorce": "",
    },
    "technique": {
        "titre": "Technical",
        "amorce": "We are talking technical: language models, code, architecture, workflows, "
        "tooling. Assume that frame by default, without locking yourself into it.",
    },
    "trading": {
        "titre": "Trading",
        "amorce": "We are talking markets: strategies, risk, execution, data, backtests. "
        "Assume that frame by default, without locking yourself into it.",
    },
    "perso": {
        "titre": "Personal",
        "amorce": "We are talking about his personal life: health, rhythm, relationships, "
        "admin, organisation. Be concrete and discreet.",
    },
    "projet": {
        "titre": "Project",
        "amorce": "We are talking about his ongoing projects and how far along they are. When he "
        "asks where something stands, call the `plans` tool rather than guessing.",
    },
}


# ── THE TOOLS ───────────────────────────────────────────────────────────────────────────────────
#
# The four the operator kept (③ rappel · ⑤ search_memory · ⑥ plans · ⑦ signaler), plus search within
# his own store, plus `poser_tache` — the only WRITE in the set. The catalogue lives HERE, in one
# single place, because it serves TWO things that must say the same: the description given to the
# model, and the server's execution table. Two copies would drift apart, and the model would call a
# tool that no longer exists.
#
# `poser_tache` is NOT a return to the automatic splitting removed above. The difference is the one
# that made all the difference, as measured in use: the old mechanism wrote BEFORE every answer, on
# EVERY message, including a question. This one is a tool the model CHOOSES to call — like the other
# five — and only when the operator explicitly describes things to do. The operator's request, word
# for word: *"it needs the engineering to understand, when I give it something big, how to give the
# task a title and sub-tasks"*.

OUTILS: dict[str, dict[str, str]] = {
    "chercher_notes": {
        "args": "q",
        "quoi": "searches what the operator has already dictated to you (instant)",
    },
    "rappel": {
        "args": "q",
        "quoi": "searches his past conversations with the frontier assistant "
        "(instant, no cost)",
    },
    "plans": {
        "args": "",
        "quoi": "the REAL state of his projects, item by item",
    },
    "memoire": {
        "args": "q",
        "quoi": "searches Mnemosyne's library (slow: several seconds)",
    },
    "signaler": {
        "args": "titre",
        "quoi": "reports a Mnemosyne breakdown — only if he asks you to",
    },
    "poser_tache": {
        "args": "titre, sous_taches, section, echeance, description",
        "quoi": "files A NEW task in HIS list — use it ONLY for a task that does NOT EXIST "
        "YET, never on a question or a remark. If he is talking about a task ALREADY in his "
        "list (\"for task X, add...\"), this is NOT the tool: it is `ajouter_sous_tache`. "
        "Group several RELATED things under ONE title with sous_taches (a list of strings) "
        "rather than answering him in prose. If his message describes SEVERAL DISTINCT "
        "groups (subjects with nothing to do with each other), call this tool SEVERAL TIMES, "
        "once per group, never everything in a single call nor in your prose — each call is "
        "executed one by one, and an answer that describes a filing without really having "
        "called the tool for IT writes nothing at all. section = deadline|todo|routine (todo "
        "by default); echeance only if section=deadline, in ISO format (e.g. "
        "2026-08-15T18:00); description (optional) carries the CONTEXT the title alone does "
        "not give — write it ONLY if he gave details beyond the title and the sub-tasks, "
        "never by guessing it",
    },
    "ajouter_sous_tache": {
        "args": "titre_parent, sous_taches",
        "quoi": "adds one or more sub-tasks to a task ALREADY FILED in his list — use it as "
        "soon as he says \"for task X, add...\" or \"add to X...\" about a task that already "
        "exists. titre_parent must repeat EXACTLY what he said (the name as it appears in "
        "his list), never a rewording. sous_taches is a list of strings, one per thing to "
        "add. titre_parent may be a ROOT or a SUB-TASK — in the latter case what you add "
        "becomes a sub-sub-task: depth is never a limit.",
    },
    "deplacer_sous_tache": {
        "args": "titre, nouveau_parent_titre",
        "quoi": "moves a task or sub-task ALREADY FILED so that it becomes a sub-task of "
        "ANOTHER task ALREADY FILED — use it when he says \"that sub-task, put it under X\" "
        "or \"I would rather it were the sub-task of X\". nouveau_parent_titre may itself be "
        "a root or a sub-task (creating a sub-sub-task). titre and nouveau_parent_titre must "
        "both repeat EXACTLY what he said.",
    },
    "voir_plus_loin": {
        "args": "",
        "quoi": "looks further back in THIS conversation's history, beyond what you already "
        "have in front of you — use it ONLY if what he is asking depends on an exchange older "
        "than your current context; never by default, never if he is talking about something "
        "else",
    },
    "renommer_tache": {
        "args": "titre_actuel, nouveau_titre",
        "quoi": "renames a task or sub-task ALREADY FILED in his list — titre_actuel must "
        "repeat EXACTLY what he said (the name as it appears in his list), never a rewording. "
        "Never invent a titre_actuel: if he did not give it to you, ask for it rather than "
        "guessing.",
    },
    "supprimer_tache": {
        "args": "titre",
        "quoi": "removes a task or sub-task ALREADY FILED from his list (nothing is erased, "
        "it just leaves what he sees — exactly the screen's \U00002715 button) — titre must repeat "
        "EXACTLY what he said.",
    },
    "decrire_tache": {
        "args": "titre, description",
        "quoi": "adds or replaces the description of a task or sub-task ALREADY FILED — "
        "titre must repeat EXACTLY what he said.",
    },
}


#: The heading under which the life portrait enters the base. A CONSTANT, not a string copied
#: at the emission site, because the PRIVACY witness that checks for its ABSENCE must read the
#: SAME value. Measured 2026-09-09 on this very mirror: translation changed the emitted heading
#: without touching the two assertions that looked for it, and `assert "<french>" not in
#: socle()` had become TRUE BY CONSTRUCTION -- a privacy leak guard that was INERT, green
#: forever, including if the portrait had actually leaked. Translating one half of a matched
#: pair does not redden anything; making the pair impossible is what fixes the class.
EN_TETE_PORTRAIT = "What you know of his life:"


def socle(
    mode: str = "libre",
    *,
    en_attente: list[dict[str, Any]] | None = None,
    connexes: list[dict[str, Any]] | None = None,
    portrait: str = "",
) -> str:
    """The preamble re-injected on EVERY turn: who it is, what it knows, what is waiting for him.

    This is the fixed layer of the three (base prompt · thread · what it goes and fetches). It is
    small on purpose: everything put here is paid for on every turn, over a context window that, for
    the small models in the lineup, is worth about 16,000 tokens.

    Three things enter here rather than through a tool, and for the same reason: **the operator will
    not think to ask for them.**

    · ``portrait`` — what is known of his life (`ui/ENTRETIEN.md`). Without this a local model
      guesses nothing: it has no way to know he has class until 5pm.
    · ``en_attente`` — what he had set aside FOR THIS MOMENT (the deferral).
    · ``connexes`` — what he has already said about the subject he is talking about now.

    ``mode`` is no longer chosen by the operator: *"free, technical, trading, personal — oh, very
    tedious, extremely tedious even"*. It stays a parameter because the INTENDANT can infer it itself
    from a message, but the screen no longer asks for it and the default is "libre" (free). A button
    that costs a gesture on every sentence costs more than it earns."""
    lignes = [
        "You are the operator's Intendant. You are his memory aid: he dumps out what is on his "
        "mind, you file it, and you hand it back to him when he needs it.",
        "",
        "Rules:",
        "- Reply in English, short and concrete. No preamble, no flattery.",
        "- You do not know everything about him. When the answer depends on what he has already "
        "told you, go and fetch it with a tool rather than guessing.",
        "- If you do not know, say so.",
        "- If what he is asking for has NO tool that can do it, say so clearly rather than "
        "inventing a workaround (for instance filing a task that DESCRIBES the action instead "
        "of performing it — that is never the same thing).",
        "- Everything he writes to you is ALREADY recorded: never ask him whether to keep it.",
        "- \U000026A0\U0000FE0F\U000026A0\U0000FE0F Measured (2026-08-11): if he corrects you about what you have just done (\"you are "
        "being stupid\", \"not X but Y\", \"delete what you just did\", \"no, you misunderstood\"…), "
        "that is an INSTRUCTION ABOUT YOUR LAST GESTURE — never content to file as-is. NEVER file "
        "his correcting sentences themselves as a task or sub-task title (it has already "
        "happened: \"Delete what you just did\" filed literally as a sub-task). Understand what he "
        "wants you to fix and fix it (remove what is wrong with `supprimer_tache`, file or sort "
        "what is missing in the right place) — his reprimand never becomes an entry in his list.",
        "- When he describes SEVERAL things to do that belong together, file them with "
        "`poser_tache` (one title, one sub-task per thing) rather than summarising them in prose. "
        "Never use it on a plain question.",
        "- If he names a task that ALREADY exists in his list and asks to add something to it, "
        "use `ajouter_sous_tache` — never `poser_tache`, which would create a duplicate instead "
        "of completing the task he meant.",
        "- \U000026A0\U0000FE0F Measured (2026-08-11): \"add into Mnemosyne (already there), as a deadline, a "
        "sub-task saying we must look at…\" produced a ROOT task titled \"Add a task in "
        "Mnemosyne\" — the title took up YOUR OWN INSTRUCTION VERB (\"add a task\") instead of the "
        "content it describes. A title that starts with \"Add…\", \"File…\", \"Create…\", \"Add a "
        "task…\" is almost always the sign that you have confused the instruction with what it "
        "asks you to file — the title must be WHAT HE IS TALKING ABOUT, never the order he has "
        "just given you. \"Mnemosyne\" in \"add into Mnemosyne\" names the PARENT (already there → "
        "`ajouter_sous_tache`), not the title to create.",
        "- \U000026A0\U0000FE0F Measured trap (2026-08-11): \"in X (already there), add a sub-task Y; in Y, add the "
        "sub-sub-tasks Z1, Z2, Z3\" requires TWO calls to `ajouter_sous_tache` ONE AFTER THE OTHER "
        "in the SAME turn — never `poser_tache`, even if Y has several children to create at "
        'once. Call 1: `ajouter_sous_tache(titre_parent="X", sous_taches=["Y"])`. Result '
        'received, THEN call 2: `ajouter_sous_tache(titre_parent="Y", sous_taches=["Z1", "Z2", '
        '"Z3"])`. A single call filing Y with Z1/Z2/Z3 as though they were ITS OWN sub-tasks '
        "would put them one level too high.",
        "- If he asks to MOVE a task or sub-task ALREADY FILED under another task ALREADY FILED "
        "(\"put that sub-task under X\", \"I would rather it were the sub-task of X\"), use "
        "`deplacer_sous_tache`. Depth is never a limit: a sub-task can become the sub-task of "
        "another sub-task.",
        "- \U000026A0\U0000FE0F Measured (2026-08-11), the most fragile point in everything you do: acting on a task "
        "ALREADY FILED (ajouter_sous_tache, renommer_tache, deplacer_sous_tache, decrire_tache, "
        "supprimer_tache) requires repeating its EXACT title — not from memory, not approximate. "
        "The operator dictates by voice: \"personal learning\" can come back out distorted "
        "(\"learning personally\"…) and be confused with ANOTHER task with a neighbouring name "
        "(\"Learn to code\"). If you are not 100% certain of the EXACT title as it appears in his "
        "list, call `chercher_notes` FIRST with the keywords he said to find the real title, THEN "
        "act with that precise title — never with your own rewording. Guessing an approximate "
        "title is the most frequent cause of a gesture that fails silently or touches the wrong "
        "task.",
        "- After filing, renaming, describing, removing or completing a task, confirm in ONE "
        "SHORT SENTENCE what was done. NEVER recap the rest of his list — he already has it in "
        "front of him — and add no generic closing formula (\"feel free to...\", \"I am here to "
        "help\"). A long answer after a writing tool is ALWAYS a mistake, never a service.",
        "",
        "Your tools. To call one, reply ONLY with a JSON line of this shape:",
        '{"outil": "<name>", "args": {"<arg>": "<value>"}}',
        "The result will come back to you and you will then answer normally.",
    ]
    for nom, fiche in OUTILS.items():
        # The signature used to read `chercher_notes("q": "…")` — a mix of two notations that
        # resembles neither a real function call nor the JSON requested two lines above. A small
        # model imitates what it sees: show it a bastard shape, and that is what you get back.
        lignes.append(f"- {nom}({fiche['args']}) — {fiche['quoi']}")
    if portrait.strip():
        lignes += ["", EN_TETE_PORTRAIT, portrait.strip()]
    amorce = MODES.get(mode, MODES["libre"])["amorce"]
    if amorce:
        lignes += ["", amorce]
    if en_attente:
        lignes += ["", "\U000026A0\U0000FE0F He had set this aside FOR THIS MOMENT — remind him of it:"]
        for note in en_attente[:5]:
            lignes.append(f"- {note.get('resume') or note.get('texte', '')[:160]}")
    if connexes:
        # This block used to say "only repeat it if it's useful", and the model concluded from
        # that it was never useful: to "was there something I'd said about this?" it would answer
        # "sure, let me go look", even though the answer was already right in front of it. An
        # instruction that leaves a small model to ARBITRATE, it arbitrates badly. Tell it what to
        # do with it instead.
        lignes += [
            "",
            "What he has ALREADY told you on this subject — this is material you have in "
            "hand, not a lead to explore. If he asks what he had said, ANSWER with this: "
            "never offer to go and look it up.",
        ]
        for note in connexes[:5]:
            date = str(note.get("depose_le", ""))[:10]
            lignes.append(f"- [{date}] {note.get('resume') or note.get('texte', '')[:160]}")
    lignes.append("")
    return "\n".join(lignes)


def projets() -> str:
    """The operator's project map — what each one IS and what is left to do on it, or "".

    Written once by READING the repos, so he does not have to describe them himself. His words:
    *"instead of me being the one who presents my projects to you, go read them, and at least you
    can hand the local agent something clean as memory."*

    **It does NOT enter the base prompt**: ~7,000 characters that are only useful on turns where he
    talks about a project. It comes out via the `plans` tool, with counters pulled fresh alongside it
    — the map gives meaning and ages, the counters give the state and mean nothing alone."""
    chemin = racine() / "projets.md"
    if not chemin.is_file():
        return ""
    try:
        return chemin.read_text(encoding="utf-8")
    except OSError:
        return ""


#: The portrait sections that enter the base prompt on EVERY turn.
#:
#: The whole portrait weighs ~13,000 characters — around **4,200 tokens**, a quarter of a
#: `phi-4`'s window (16,384). Paying it in full on every turn means paying three times the thread's
#: own price for text whose essence is almost never used by the current turn.
#:
#: The sorting criterion is not "what is important" but **"what changes the answer to ANY
#: question"**:
#:   · 1 Rhythm and 2 Energy — any question of time or load depends on them;
#:   · 7 How to talk to him — changes the SHAPE of every answer, hence every turn;
#:   · 8 Thought patterns and 9 To recall when — this is the Intendant's core.
#: The others (3 Projects, 4 People, 5 Admin, 6 Health) stay in the file and are searched: section 3
#: is in any case better served by the `plans` tool, which reads the REAL state of the repos rather
#: than a description written one day and stale the next.
SECTIONS_SOCLE: tuple[str, ...] = ("1.", "2.", "7.", "8.", "9.")

_TITRE_SECTION = re.compile(r"^## (.+)$", re.M)


def portrait(*, sections: tuple[str, ...] | None = None, tout: bool = False) -> str:
    """What Mnémosyne knows of the operator's life — the product of `ui/ENTRETIEN.md`, or "".

    Lives in a file rather than in code: it gets rewritten over the course of interviews, and a
    portrait frozen into a constant would go stale without anyone noticing. Absent, an empty string
    is returned and the base prompt does not mention it — rather than an invented portrait, which
    would make the agent reason about a life that is not his.

    By default, returns only :data:`SECTIONS_SOCLE`. ``tout=True`` returns the whole file — for a
    search or a display, never for the base prompt. **One single file, two views**: a "short version"
    copy would drift from the original with nothing to signal it."""
    chemin = racine() / "portrait.md"
    if not chemin.is_file():
        return ""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError:
        return ""
    if tout:
        return texte
    voulues = SECTIONS_SOCLE if sections is None else sections
    morceaux: list[str] = []
    bornes = [(m.start(), m.group(1)) for m in _TITRE_SECTION.finditer(texte)]
    for i, (debut, titre) in enumerate(bornes):
        fin = bornes[i + 1][0] if i + 1 < len(bornes) else len(texte)
        if titre.lstrip("# ").startswith(voulues):
            morceaux.append(texte[debut:fin].rstrip())
    # No section recognized? Return the whole file rather than NOTHING: a portrait renamed by hand
    # is better truncated to zero, and the silence would be diagnosed as "there is no portrait" when
    # there is one.
    return "\n\n".join(morceaux) if morceaux else texte


# ── READING WHAT A SMALL MODEL RETURNS ─────────────────────────────────────────────────────────


def _extraire_json(reponse: str) -> dict[str, Any] | None:
    """The first JSON object in an answer, whatever surrounds it.

    A 4-to-13 GB model will readily wrap its JSON in ```json, precede it with a polite sentence, or
    follow it with an explanation. Requiring a bare object would fail perfectly correct answers —
    and the failure would be blamed on the model when it comes from the reader.

    Scans by counting braces (ignoring the ones inside strings), so a nested object is returned
    WHOLE: cutting at the first `}` would return an unreadable fragment."""
    depart = reponse.find("{")
    while depart != -1:
        profondeur, dans_chaine, echappe = 0, False, False
        for i in range(depart, len(reponse)):
            c = reponse[i]
            if echappe:
                echappe = False
                continue
            if c == "\\":
                echappe = True
            elif c == '"':
                dans_chaine = not dans_chaine
            elif not dans_chaine:
                if c == "{":
                    profondeur += 1
                elif c == "}":
                    profondeur -= 1
                    if profondeur == 0:
                        try:
                            objet = json.loads(reponse[depart : i + 1])
                        except json.JSONDecodeError:
                            break
                        if isinstance(objet, dict):
                            return objet
                        break
        depart = reponse.find("{", depart + 1)
    return None


#: The REASONING wrappers some models in the lineup write before their answer. Measured on the
#: 2026-08-04 bench, on real outputs:
#:   · `GLM-Z1-9B` opens a `<think>` … `</think>` — in ENGLISH, even when spoken to in French;
#:   · `gpt-oss-20b` uses the "harmony" format: `<|channel|>analysis<|message|>` … then
#:     `<|start|>assistant<|channel|>final<|message|>` for the real answer.
#: Without this cleanup, the operator would read "analysisWe need to respond in 3 lines, in
#: French…" instead of his answer. This is not a flaw in the models: it is an integration flaw, and
#: it only shows up by looking at what they REALLY return.
_PENSEE = re.compile(r"<think>.*?</think>", re.S)
_BALISE = re.compile(r"<\|[^|>]*\|>")
_MESSAGE = "<|message|>"


def nettoyer_reponse(texte: str) -> str:
    """What the operator must READ, stripped of the model's reasoning envelope.

    Two rules, one per family encountered:

    1. ``<think>`` … ``</think>`` is removed (GLM-Z1).
    2. For the "harmony" format (gpt-oss-20b), keep **what follows the LAST** ``<|message|>``.
       My first version removed the tags one at a time — and left the word ``assistant``
       orphaned in the middle of the text ("assistantHello."), because the role name lives BETWEEN
       two tags and no rule that only looks at tags can see it. By construction of the format, the
       last ``<|message|>`` is the opening of the final channel.

    **If the cleanup leaves nothing, the original text is returned.** A model that had not
    finished reasoning before its output limit wrote ONLY reasoning (measured: `GLM-Z1` on two bench
    tasks). Returning an empty string would turn "it answered badly" into "it answered nothing" — a
    silence is far harder to diagnose than a clumsy answer, and it looks like a system failure when
    it is really the model overrunning."""
    propre = _PENSEE.sub("", texte)
    if _MESSAGE in propre:
        propre = propre.rsplit(_MESSAGE, 1)[1]
    propre = _BALISE.sub("", propre).strip()
    return propre or texte.strip()


def lire_appel(reponse: str) -> tuple[str, dict[str, Any]] | None:
    """A tool call within the answer, or None if the model simply talked.

    Refuses a tool outside the catalogue rather than passing it along: a model that invents
    ``supprimer_tout`` (delete everything) must not see its invention reach an execution table."""
    objet = _extraire_json(reponse)
    if not objet:
        return None
    nom = objet.get("outil")
    if not isinstance(nom, str) or nom not in OUTILS:
        return None
    args = objet.get("args")
    return nom, (args if isinstance(args, dict) else {})


# ── SPLITTING A LARGE MESSAGE INTO TASKS TO HANDLE ONE BY ONE ────────────────────────────────────
#
# The operator's request, word for word: *"I'm going to send big messages where I'm going to ask
# for a lot of things […] I'm not sure the small model is very good at handling 15 tasks at the same
# time"*. This is NOT the splitting removed earlier (that one wrote to the store, on EVERY message).
# This one does not touch the store: it splits the text BEFORE talking, and each piece goes out as a
# normal turn — base prompt, tools included (`poser_tache` among them).
#
# The point that matters, also in his words: *"for task number one, I started talking about it at
# the beginning, but I bring it up again in the middle and at the end […] copy-paste word for word
# what he said"* — a single request can be spread across the whole message, and the splitting must
# GATHER it into one single piece rather than leave it shattered into fragments that, taken alone,
# mean nothing.

#: How many tasks a split returns at most. Same reasoning as everywhere else in this module: beyond
#: this, it is the model looping, not the operator genuinely having ten distinct things.
_MAX_TACHES_DECOUPAGE = 12


def invite_decoupage(texte: str) -> str:
    """The splitting request: which DISTINCT requests does this message carry, and what does it say
    about each — word for word, wherever it appears in the text."""
    return (
        "The operator has just written you a message that may contain SEVERAL distinct requests "
        "— sometimes he comes back to the same thing in several places in the message.\n\n"
        "Identify each DISTINCT request. For each one, gather EVERYTHING he says about it, "
        "wherever it sits in the message, into ONE SINGLE extract.\n\n"
        "Return ONLY a JSON object of this shape, nothing before, nothing after:\n"
        '{"taches": ["the extract, copy-pasted word for word, of the first request", "..."]}\n\n'
        "Rules:\n"
        "- ONE entry per DISTINCT request, never per sentence: if he comes back three times to "
        "the same thing, that is ONE single entry gathering the three passages.\n"
        "- Each entry is a COPY-PASTE of HIS words. Explain nothing, summarise nothing, reword "
        "nothing.\n"
        "- If there is only ONE request in the whole message, return a single entry with the "
        "entire message.\n\n"
        f'The message:\n"{texte}"'
    )


def lire_decoupage(reponse: str, *, source: str = "") -> list[str]:
    """The tasks drawn from the splitting, in the ORDER he said them.

    ``source`` is the floor: a failed splitting (model off, unreadable JSON, empty list) returns the
    WHOLE message as its only task — never nothing. A splitting that lost the message would be worse
    than no splitting at all."""
    repli = [source] if source.strip() else []
    objet = _extraire_json(reponse) or {}
    bruts = objet.get("taches")
    if not isinstance(bruts, list):
        return repli
    taches: list[str] = []
    for brut in bruts[:_MAX_TACHES_DECOUPAGE]:
        if isinstance(brut, str):
            propre = brut.strip()
        elif isinstance(brut, dict):
            propre = str(brut.get("texte") or "").strip()
        else:
            propre = ""
        if propre:
            taches.append(propre)
    return taches or repli


# ── THE GROUPING — filing SEVERAL tasks at once, without going back through the model once more
# per group ─────────────────────────────────────────────────────────────────────────────────────
#
# Measured on 2026-08-08, in real use: the splitting (above) identifies the distinct groups of a
# large message very well — the operator: "it separates them out well" — but each group would then
# go back out as a COMPLETE conversation turn (`_tour_unique`, base prompt + tool choice), and the
# model could still choose to NARRATE instead of calling the tool. The operator's verdict on this
# slowness: "it's 100% an engineering problem [...] it defines, then it runs some Python code" —
# exactly the idea here: ONE SINGLE call structures the `poser_tache` fields directly for EACH group,
# and the recording runs in code, never by calling the model back per group.
#
# Scope assumed, not hidden: this assumes the message describes things to FILE. A message that
# mixes a real question with tasks would lose the question (`intendant_parler` falls back to the
# classic splitting if `lire_groupement` finds NO group — never a lost text, but a mix of
# question+tasks is not yet handled cleanly).

_MAX_GROUPES = 12


def invite_groupement(texte: str) -> str:
    """The grouping request: structure each distinct task directly into fields ready to file, rather
    than returning text that will still need to be interpreted group by group.

    ``parent_titre`` — added after a first, failed measurement: the first pass (without this
    field) correctly UNDERSTOOD the requested attachments (*"that goes into the task I was just
    talking about"*, *"that's a sub-task of UI Mnémosyne"*) — visible in its OWN `description`
    fields — but still flattened them all into separate roots, for lack of a dedicated place to say
    so. A field in the right place, for a relationship the model had already identified but had
    nowhere to write."""
    return (
        "The operator has just written you a message that may describe SEVERAL tasks to file in "
        "his list — sometimes he comes back to the same task in several places in the message, "
        "and sometimes he says explicitly that one task goes INSIDE another.\n\n"
        "Identify each DISTINCT task he describes. For EACH ONE, return an object with:\n"
        "- titre: the task's short title\n"
        "- sous_taches: the list of concrete things to do for this task (may be empty)\n"
        "- section: deadline, todo or routine (todo if nothing is said)\n"
        "- echeance: an ISO date ONLY if section=deadline and a date is given, otherwise an "
        "empty string\n"
        "- description: context beyond the title, ONLY if he gave some — NEVER invent it\n"
        "- parent_titre: EMPTY, EXCEPT if he says EXPLICITLY that this task goes INSIDE another, "
        "or is a SUB-TASK of another (\"that goes into...\", \"that is a sub-task of...\", \"in the "
        "task I have just been talking about\") — then, the EXACT title of that other task, as "
        "YOU yourself wrote it in another object of this same list, or as it already exists in "
        "his list.\n\n"
        "Return ONLY a JSON object of this shape, nothing before, nothing after:\n"
        '{"groupes": [{"titre": "...", "sous_taches": ["..."], "section": "todo", '
        '"echeance": "", "description": "", "parent_titre": ""}]}\n\n'
        "If the message describes NO task to file (a question, a remark with no action), return "
        '{"groupes": []} — never force a task that does not exist in his words.\n\n'
        f'The message:\n"{texte}"'
    )


def lire_groupement(reponse: str) -> list[dict[str, Any]]:
    """The structured groups drawn from the grouping, bounded and cleaned.

    Unlike `lire_decoupage`, NO fallback to the whole message: a failed grouping (unreadable JSON,
    empty list) returns an EMPTY list, and the caller then falls back to the classic splitting
    (§ above) — never a half-structured recording, never a phantom task made of an empty title."""
    objet = _extraire_json(reponse) or {}
    bruts = objet.get("groupes")
    if not isinstance(bruts, list):
        return []
    groupes: list[dict[str, Any]] = []
    for brut in bruts[:_MAX_GROUPES]:
        if not isinstance(brut, dict):
            continue
        titre = str(brut.get("titre") or "").strip()
        if not titre:
            continue
        crues = brut.get("sous_taches")
        sous_taches = (
            [str(s).strip() for s in crues if str(s).strip()][:12]
            if isinstance(crues, list)
            else []
        )
        section = str(brut.get("section") or "todo").strip()
        if section not in HORIZONS:
            section = "todo"
        parent_titre = str(brut.get("parent_titre") or "").strip()
        groupes.append(
            {
                "titre": titre,
                "sous_taches": sous_taches,
                "section": section,
                "echeance": (
                    str(brut.get("echeance") or "").strip() if section == "deadline" else ""
                ),
                "description": str(brut.get("description") or "").strip(),
                # Never its OWN title: a model that cites itself as its own parent would create a
                # loop that `_deposer_groupes` would have to detect — simpler to refuse it HERE, at
                # the source, before it exists.
                "parent_titre": parent_titre
                if parent_titre and not titres_correspondent(parent_titre, titre)
                else "",
            }
        )
    return groupes


def titres_correspondent(a: str, b: str) -> bool:
    """Do two titles match, ignoring accents/case/extra spaces? "UI Mnémosyne" and "ui mnemosyne"
    are the SAME title for any matching in this module — never two distinct tasks by accident of
    accent, case, or typo."""
    return _plier(a).strip().split() == _plier(b).strip().split()


def racine_par_titre(titre: str) -> dict[str, Any] | None:
    """The EXISTING root whose title matches, or None. The operator, in his own message:
    "to add as a sub-task, ONLY IF THERE ISN'T ALREADY a UI Mnemosyne task" — the very check he
    asked for, and one `poser_tache` never knew how to do (it always creates something new)."""
    for n in lire():
        if not n.get("parent") and titres_correspondent(n["texte"], titre):
            return n
    return None


def notes_par_titre(titre: str) -> list[dict[str, Any]]:
    """All the LIVE notes (root OR sub-task) whose title matches — the resolver behind
    `renommer_tache`/`supprimer_tache`/`decrire_tache`: the model never knows an id, only what the
    operator wrote in his sentence, exactly as the operator himself would.

    Matches against the VERBATIM ``texte`` and the ``resume`` (the label shown on screen when it
    differs) — the operator names a task by what he SEES, not necessarily by what he originally
    dictated.

    Returns a LIST, never a single note chosen at random: the same title sometimes exists in two
    places (a root AND a sub-task, for instance "Work on the RAG" in the operator's real
    store) — the only safe move, when that happens, is to SAY so to the caller rather than guess
    which one he meant."""
    return [
        n
        for n in lire()
        if titres_correspondent(n.get("texte", ""), titre)
        or (n.get("resume") and titres_correspondent(n["resume"], titre))
    ]


#: How many notes are drawn at most from a single message. The operator dictates at length; a block
#: of text can legitimately carry ten. Beyond that, it is the model looping, not the operator
#: genuinely having that much to say — and twelve bogus notes would drown out the real ones.
_MAX_EXTRAITS = 10


def invite_extraction(texte: str) -> str:
    """The SPLITTING request: how many distinct things are in this message, and which ones.

    This replaces sorting into ONE note. The operator: *"if I send a huge block of text with 500
    different topics, that's going to end up as a single task, that makes no sense"*. And: *"the
    tasks, HE's the one who has to file them, he's the one who has to word them a bit more
    cleanly"* — so a **clean, actionable phrasing** is requested, not a plain copy.

    Each item's ``texte`` field stays an EXTRACT of his own words, never a rewording: the summary
    goes into ``resume``. That is what always makes it possible to go back to what he said."""
    return (
        "The operator has just dictated a message to you, in bulk. Cut it into DISTINCT "
        "THINGS.\n\n"
        "Return ONLY a JSON object of this shape, nothing before, nothing after:\n"
        '{"items": [\n'
        '  {"texte": "the extract of HIS words that carries this thing",\n'
        '   "resume": "a short, clear, actionable phrasing — YOU are the one who writes it",\n'
        '   "genre": "tache|pensee|regle|projet",\n'
        '   "sujets": ["...", "..."],\n'
        '   "horizon": "todo|deadline|routine",\n'
        '   "quand": "the situation that must bring this back up, or null"}\n'
        "]}\n\n"
        "Rules:\n"
        "- ONE entry per distinct thing. If he talks about five subjects, return five entries.\n"
        "- If he says only one thing, return a single entry. Do not cut artificially.\n"
        '- If he says nothing worth keeping (a question, a greeting), return {"items": []}.\n'
        '- "texte": HIS words, copied. "resume": yours, clean.\n'
        '- "horizon": todo (no date) · deadline (with a due date) · routine (recurring).\n'
        '- "quand": only if he said it had to come back up at a precise moment of his '
        "work. Otherwise null.\n\n"
        f'The message:\n"{texte}"'
    )


def lire_extraction(reponse: str, *, source: str = "") -> list[dict[str, Any]]:
    """The notes drawn from a message, or an EMPTY list.

    An empty list means two very different things — "there was nothing worth keeping" and "the
    model returned nothing usable" — and the caller must treat them the same way: **lose nothing**.
    That is why the parent dump is only marked ``versee`` if daughter notes genuinely exist.

    ``source`` acts as a floor: the deferred situation is re-read from the original sentence when
    the model missed it for this particular extract."""
    objet = _extraire_json(reponse) or {}
    bruts = objet.get("items")
    if not isinstance(bruts, list):
        return []
    notes: list[dict[str, Any]] = []
    for brut in bruts[:_MAX_EXTRAITS]:
        if not isinstance(brut, dict):
            continue
        texte = str(brut.get("texte") or "").strip()
        resume = str(brut.get("resume") or "").strip()
        # An item with no usable text at all is noise: an empty note is not manufactured for it.
        if not texte and not resume:
            continue
        garde = lire_rangement(json.dumps(brut, ensure_ascii=False), texte=texte or source)
        notes.append({"texte": texte or resume, **garde})
    return notes


def invite_rangement(texte: str) -> str:
    """The SORTING request — a single shot, outside the conversation.

    Deliberately separated from the thread: asking a small model to chat AND to return structured
    JSON in the same turn loses both. Here it has exactly one thing to do."""
    return (
        "Sort this thought of the operator's. Return ONLY a JSON object, nothing before, "
        "nothing after:\n"
        '{"genre": "tache|pensee|regle|projet", "sujets": ["...", "..."], '
        '"horizon": "todo|deadline|routine", '
        '"quand": "the situation that must bring this back up, or null", '
        '"resume": "a short sentence"}\n\n'
        "The subjects are FREE words, yours, the ones that describe it best — no imposed "
        "list.\n"
        '"horizon": todo (no date) · deadline (with a due date) · routine (recurring).\n'
        '"quand": fill it in ONLY if he said it had to come back up at a precise moment '
        "of his work. Otherwise null.\n\n"
        f'What the operator has just said:\n"{texte}"'
    )


#: The markers of a DEFERRAL in the operator's sentence, and how to extract the situation from it.
#:
#: Why this exists, and it is the lesson of the 2026-08-04 bench: when the code computed the time
#: slots itself instead of letting the model do the arithmetic, the success rate went from **2/5
#: valid** to **5/5 valid, and faster**. The corollary holds here too: spotting "not now, it's when
#: I'm on X" is PATTERN work, not judgment. A 5 GB model gets it wrong about half the time (measured:
#: an empty `quand` on a sentence that carried it explicitly); a regular expression never misses it.
#:
#: The model keeps what it does better: rewording the situation cleanly. The code only serves as a
#: FLOOR — it never replaces a `quand` the model already managed to produce.
_DIFFERE = re.compile(
    r"\b(?:c'est\s+)?(quand\s+(?:je|on|ce|tu)\b[^.;!?\n]{3,90}"
    r"|une\s+fois\s+que\b[^.;!?\n]{3,90}"
    r"|des\s+que\b[^.;!?\n]{3,90}"
    r"|dès\s+que\b[^.;!?\n]{3,90}"
    r"|apres\s+que\b[^.;!?\n]{3,90}"
    r"|après\s+que\b[^.;!?\n]{3,90})",
    re.IGNORECASE,
)
#: What says "not right now" without naming a moment. Alone, it does not give a situation — but it
#: confirms there is one to look for.
_PLUS_TARD = re.compile(r"pas\s+(?:pour\s+)?maintenant|plus\s+tard|pas\s+tout\s+de\s+suite", re.I)


def situation_differee(texte: str) -> str:
    """The return situation READ DIRECTLY IN THE SENTENCE, or "" — with no model at all.

    Returns the clause exactly as the operator said it: these are his own words, which will have to
    match later, when he describes the same situation differently. A rewording would lose exactly
    the vocabulary by which he will recognize it."""
    trouve = _DIFFERE.search(texte)
    if not trouve:
        return ""
    clause = trouve.group(1).strip(" ,;")
    # "not now" with no moment named is not an actionable deferral: it says there is one, not which
    # one. Better no `quand` at all than a `quand` that would surface the note on everything.
    return clause if len(clause.split()) >= 3 else ""


def lire_rangement(reponse: str, *, texte: str = "") -> dict[str, Any]:
    """What is kept from the sorting the model returned. Keeps ONLY what is valid.

    An invented kind or horizon is left aside, not stored: the store stays clean even when the model
    goes off the rails, and ``ranger`` also refuses on its own side — two barriers, because this one
    can be bypassed by another caller."""
    objet = _extraire_json(reponse) or {}
    retenu: dict[str, Any] = {}
    genre = objet.get("genre")
    if isinstance(genre, str) and genre in GENRES:
        retenu["genre"] = genre
    horizon = objet.get("horizon")
    if isinstance(horizon, str) and horizon in HORIZONS:
        retenu["horizon"] = horizon
    sujets = objet.get("sujets")
    if isinstance(sujets, list):
        propres = [str(s).strip() for s in sujets if str(s).strip()]
        if propres:
            retenu["sujets"] = propres[:8]
    for champ in ("quand", "resume"):
        valeur = objet.get(champ)
        # `null` arrives either as a real None or as the string "null" — a model often returns the
        # second form, and taking it for a real value would surface every note on the slightest
        # situation.
        if isinstance(valeur, str) and valeur.strip() and valeur.strip().lower() != "null":
            retenu[champ] = valeur.strip()
    # The FLOOR: if the model missed the deferral but the sentence carries it, the code sets it. It
    # never REPLACES a `quand` the model returned — a floor raises, it never overwrites.
    if "quand" not in retenu and texte:
        depuis_la_phrase = situation_differee(texte)
        if depuis_la_phrase:
            retenu["quand"] = depuis_la_phrase
    return retenu
