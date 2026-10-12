"""The Advisor — the second of three agents (`projects/mnemosyne/ui/AGENTS.md`), its own
bubble, separate from the Steward's.

The operator, what they expect from it: *"someone who knows my whole life"* — a chat that
discusses their situation, their doubts, their trade-offs, and that, when a real choice comes up,
leans on **real decision models** (:mod:`mnemosyne.runtime.decision`) rather than improvising an
opinion.

**Why a SEPARATE bubble, never the Steward's.** The operator, `AGENTS.md`, 2026-08-02: *"agents
should only be able to act WITHIN their own zone [...] even if that means creating a folder for
each of them. I honestly prefer that to something with too much access."* This module therefore
deliberately duplicates `intendant.py`'s storage pattern (append-only journal, persistent threads)
rather than reusing it through a shared root — this is the very cloisonnement that makes it
impossible for a bubble mix-up to make the Advisor write into the Steward's list, or the reverse.

**What it holds, and why it is NOT the same shape as the Steward's.** The Steward holds a STATE
(what remains to be done); the Advisor holds MILESTONES — dated points, with a FREE-FORM status
the operator writes themself (*"not found yet, thinking about X"*), never a score invented by a
model. This is the choice that short-circuits the unresolved condensation problem (C6, `AGENTS.md`
§5): a milestone is a bounded object, like a line in the Steward's journal, rather than a
narrative portrait that grows without shape.

**What it CAN write, and where that right stops.** The operator, this same conversation: *"it
absolutely has to be view-only too, but it should be able to write in exactly one document of its
own, strictly, strictly, strictly."* — the same rule `AGENTS.md` had already set for it (*"NO"* to
a special pass, *"it's the worst possible place"*). Only TWO writes are open to it: its own
milestones (this module), and its own bounded notebook (§ NOTEBOOK, below) — never the Steward's
storage, never the operator's own portrait, never a file outside its own root.

Code & docstrings are French here, same reason as `intendant.py`: this module speaks only about
the operator's own material — in the source repository (D33); this mirror translates it to
English throughout. Tested brick-free.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - resource is POSIX-only (absent on Windows)
    resource = None  # type: ignore[assignment]

#: The states of a note on the READ path — only two, unlike the Steward's
#: (no "done": a milestone that is reached stays in the SET, with a status that says so, it does
#: not leave view — that is exactly what the operator wants to be able to re-read: "ah, they
#: finally found it").
ETATS: tuple[str, ...] = ("vive", "retiree")

_VERSION = 1


def racine() -> Path:
    """The storage folder. ``MNEMO_CONSEILLER_RACINE`` moves it — testable without touching the
    operator's real milestones. Never the same default value as ``intendant.racine()``: two
    sibling folders, not a shared one."""
    surcharge = os.environ.get("MNEMO_CONSEILLER_RACINE")
    if surcharge:
        return Path(surcharge)
    return Path(__file__).resolve().parents[3] / "state" / "conseiller"


def _journal() -> Path:
    return racine() / "jalons.jsonl"


def _dossier_fils() -> Path:
    return racine() / "fils"


def _bac() -> Path:
    """The ONLY folder where `executer_code` is allowed to run (§ SANDBOX)."""
    chemin = racine() / "bac"
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


def _maintenant() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _neuf_id() -> str:
    return uuid.uuid4().hex[:12]


def _ecrire_ligne(objet: dict[str, Any]) -> None:
    """Appends ONE line to the journal. Never a rewrite (invariant 2)."""
    chemin = _journal()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(objet, ensure_ascii=False) + "\n")


def _lignes() -> list[dict[str, Any]]:
    """Every readable line of the journal. An unreadable line is SKIPPED, not fatal — the same
    reasoning as `intendant._lignes`: an append-only journal can end on a truncated write, and
    losing everything over one line would be the worst of both worlds."""
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


def _plier(texte: str) -> str:
    """Lowercase, accent-stripped — so a search for "decide" finds "décidé"."""
    decompose = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def titres_correspondent(a: str, b: str) -> bool:
    """Do two titles match, ignoring accents/case/extra whitespace? Same rule as
    `intendant.titres_correspondent` — duplicated rather than imported, so this module stays
    readable and testable on its own, without depending on `intendant.py`'s internal wiring."""
    return _plier(a).strip().split() == _plier(b).strip().split()


# ── MILESTONES ──────────────────────────────────────────────────────────────────────────────────


def _echeance_valide(echeance: str) -> str:
    propre = echeance.strip()
    if not propre:
        return ""
    try:
        datetime.fromisoformat(propre.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return propre


def deposer_jalon(titre: str, *, echeance: str = "", statut: str = "") -> dict[str, Any]:
    """Writes ONE milestone, immediately — same guarantee as `intendant.deposer`: it NEVER
    depends on the model, a deposit is a file write.

    ``statut`` is FREE-FORM (the operator: *"not found yet, thinking about X"*), never a closed
    box — no score, no validation on it, exactly the choice `AGENTS.md` documents as the remedy
    to the portrait that grows without shape (C6)."""
    propre = titre.strip()
    if not propre:
        raise ValueError("nothing to deposit")
    jalon = {
        "id": _neuf_id(),
        "titre": propre,
        "echeance": _echeance_valide(echeance),
        "statut": statut.strip(),
        "etat": "vive",
        "depose_le": _maintenant(),
    }
    _ecrire_ligne({"v": _VERSION, "ts": jalon["depose_le"], "geste": "depot", "jalon": jalon})
    return jalon


def ranger_jalon(
    jalon_id: str, *, titre: str = "", echeance: str = "", statut: str = ""
) -> dict[str, Any]:
    """Completes or corrects an ALREADY-deposited milestone — one more ``modif`` line, never a
    rewrite of the original line (invariant 2). Overwrites only what is supplied."""
    champs: dict[str, Any] = {}
    if titre.strip():
        champs["titre"] = titre.strip()
    if echeance.strip():
        valide = _echeance_valide(echeance)
        if valide:
            champs["echeance"] = valide
    if statut.strip():
        champs["statut"] = statut.strip()
    if not champs:
        return {}
    _ecrire_ligne(
        {"v": _VERSION, "ts": _maintenant(), "geste": "modif", "id": jalon_id, "champs": champs}
    )
    return champs


def marquer_jalon(jalon_id: str, etat: str) -> None:
    """Removes (or revives) a milestone — one MORE line, never a deletion."""
    if etat not in ETATS:
        raise ValueError(f"unknown state: {etat!r} (expected: {', '.join(ETATS)})")
    _ecrire_ligne(
        {"v": _VERSION, "ts": _maintenant(), "geste": "etat", "id": jalon_id, "etat": etat}
    )


def lire_jalons(*, tous: bool = False) -> list[dict[str, Any]]:
    """Replays the journal, returns the CURRENT state of the milestones. By default, only
    ``vive`` ones come out."""
    etat: dict[str, dict[str, Any]] = {}
    for ligne in _lignes():
        geste = ligne.get("geste")
        if geste == "depot":
            jalon = ligne.get("jalon")
            if isinstance(jalon, dict) and jalon.get("id"):
                etat[str(jalon["id"])] = dict(jalon)
        elif geste == "modif":
            jalon = etat.get(str(ligne.get("id", "")))
            champs = ligne.get("champs")
            if jalon is not None and isinstance(champs, dict):
                jalon.update(champs)
                jalon["range_le"] = ligne.get("ts", "")
        elif geste == "etat":
            jalon = etat.get(str(ligne.get("id", "")))
            if jalon is not None and ligne.get("etat") in ETATS:
                jalon["etat"] = ligne["etat"]
                jalon["etat_le"] = ligne.get("ts", "")
    jalons = list(etat.values())
    if not tous:
        jalons = [j for j in jalons if j.get("etat") == "vive"]
    return jalons


def trier_par_echeance(jalons: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The panel's display order: by ascending due date first (the ones coming up soonest),
    then milestones WITH NO due date, from most recently deposited to oldest — never a manual
    drag-and-drop order (the operator, § design: "stacked by due date"), hence no ``ordre``
    field here unlike `intendant._trier_manuel`."""
    source = lire_jalons() if jalons is None else jalons
    with_due = sorted((j for j in source if j.get("echeance")), key=lambda j: str(j["echeance"]))
    without_due = sorted(
        (j for j in source if not j.get("echeance")),
        key=lambda j: str(j.get("depose_le", "")),
        reverse=True,
    )
    return [*with_due, *without_due]


def jalons_par_titre(titre: str) -> list[dict[str, Any]]:
    """Every LIVE milestone whose title matches — the resolver behind
    rename/update-status/remove, same principle as `intendant.notes_par_titre`: the model never
    knows an identifier, only what the operator wrote."""
    return [j for j in lire_jalons() if titres_correspondent(j.get("titre", ""), titre)]


def chercher_jalons(question: str, *, limite: int = 20, tous: bool = False) -> list[dict[str, Any]]:
    """Full-text search across title + status, no model and no index — instant.
    Same scoring engine as `intendant.chercher` (title words count double)."""
    jalons = lire_jalons(tous=tous)
    mots = [m for m in re.split(r"\W+", _plier(question)) if len(m) > 2]
    if not mots:
        return trier_par_echeance(jalons)[:limite]
    resultats: list[tuple[int, dict[str, Any]]] = []
    for jalon in jalons:
        fort = _plier(str(jalon.get("titre", "")))
        faible = _plier(str(jalon.get("statut", "")))
        score = sum(2 for m in mots if m in fort) + sum(1 for m in mots if m in faible)
        if score:
            resultats.append((score, jalon))
    resultats.sort(key=lambda paire: -paire[0])
    return [jalon for _, jalon in resultats[:limite]]


def jalons_pertinents(texte: str, *, limite: int = 5, sauf: str = "") -> list[dict[str, Any]]:
    """Among the milestones already deposited, whatever touches on what the operator is saying
    RIGHT NOW — the other half of `chercher_jalons`, except this one arrives on its own through
    the base prompt (same role as `intendant.pertinentes`)."""
    trouves = chercher_jalons(texte, limite=limite + 1)
    return [j for j in trouves if j.get("id") != sauf][:limite]


def jalons_proches(*, limite: int = 5) -> list[dict[str, Any]]:
    """The milestones whose due date is approaching — something a local model will never go
    fetch on its own, so it must arrive through the base prompt on EVERY turn (same reasoning as
    ``en_attente`` for the Steward, but on a different notion: here it is the CALENDAR, not a
    return situation)."""
    return [j for j in trier_par_echeance() if j.get("echeance")][:limite]


# ── THREADS — identical in PRINCIPLE to the Steward's, its OWN root ───────────────────────────────


def _chemin_fil(fil_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", fil_id or ""):
        raise ValueError(f"invalid thread id: {fil_id!r}")
    return _dossier_fils() / f"{fil_id}.json"


def fil_neuf(titre: str = "", modele: str = "") -> dict[str, Any]:
    fil = {
        "v": _VERSION,
        "id": _neuf_id(),
        "titre": titre.strip(),
        "modele": modele.strip(),
        "cree_le": _maintenant(),
        "touche_le": _maintenant(),
        "tours": [],
    }
    fil_ecrire(fil)
    return fil


def fil_lire(fil_id: str) -> dict[str, Any] | None:
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
    """Same guard as on the Steward's side (§ intendant.fil_ajouter): ``aucun_outil=True`` flags
    a turn where the model answered without ever calling a tool, so the screen shows an honest
    signal instead of letting a confident piece of text pass for a real action."""
    fil = fil_lire(fil_id)
    if fil is None:
        return None
    horodate = _maintenant()
    fil.setdefault("tours", []).append({"role": "operator", "texte": demande, "ts": horodate})
    tour: dict[str, Any] = {"role": "conseiller", "texte": reponse, "ts": horodate}
    if secondes is not None:
        tour["secondes"] = secondes
    if aucun_outil:
        tour["aucun_outil"] = True
    fil["tours"].append(tour)
    if not fil.get("titre"):
        fil["titre"] = (demande.strip().split("\n")[0])[:70]
    fil_ecrire(fil)
    return fil


def fils_lister(limite: int = 50) -> list[dict[str, Any]]:
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
                "cree_le": objet.get("cree_le", ""),
                "touche_le": objet.get("touche_le", ""),
                "tours": len(objet.get("tours", [])) // 2,
            }
        )
    resume.sort(key=lambda f: str(f.get("touche_le", "")), reverse=True)
    return resume[:limite]


def fil_dernier() -> dict[str, Any] | None:
    fils = fils_lister(limite=1)
    if not fils:
        return None
    return fil_lire(str(fils[0]["id"]))


# ── WHAT THE SCREEN READS ───────────────────────────────────────────────────────────────────────


def etat() -> dict[str, Any]:
    """Everything the screen needs in ONE read."""
    jalons = trier_par_echeance()
    return {
        "jalons": jalons,
        "total": len(jalons),
        "fils": fils_lister(),
        "outils": [{"nom": n, **d} for n, d in OUTILS.items()],
        "racine": str(racine()),
        "lu_le": _maintenant(),
    }


# ── THE NOTEBOOK — the ONLY free-form write, bounded to one file, nothing else ────────────────────
#
# The operator, word for word: *"it absolutely has to be view-only too, but it should be able to
# write in exactly one document of its own, strictly, strictly, strictly."* One file, append-only
# (the same discipline as the journal), never injected into the base prompt (that would grow
# without bound, exactly C6) — consulted by a TOOL, on request, like the rest of what Mnemosyne
# knows (§ `AGENTS.md`, "WHAT IT WILL GO LOOK UP").

#: What `lire_carnet` returns at most — the MOST RECENT entries count, a scratchpad does not need
#: its full history to serve one conversation turn.
_CARNET_CAP_LECTURE = 8000


def _carnet_chemin() -> Path:
    return racine() / "carnet.md"


def noter_carnet(texte: str) -> str:
    """Appends a timestamped entry to the notebook. Never a rewrite: a wrong note is corrected
    by ONE MORE note, never by an edit — the same invariant as the rest of this module."""
    propre = texte.strip()
    if not propre:
        return ""
    chemin = _carnet_chemin()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    entree = f"\n## {_maintenant()}\n{propre}\n"
    with chemin.open("a", encoding="utf-8") as f:
        f.write(entree)
    return entree.strip()


def lire_carnet() -> str:
    """The notebook, bounded to the last ``_CARNET_CAP_LECTURE`` characters — the most recent
    entries, never a file that would grow the tool's response without limit."""
    chemin = _carnet_chemin()
    if not chemin.is_file():
        return ""
    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError:
        return ""
    return texte[-_CARNET_CAP_LECTURE:]


# ── THE SANDBOX — run a bit of code, for a calculation, never more ────────────────────────────────
#
# The operator: *"it should still have a micro-environment, a kind of little sandbox just for it,
# where the Advisor can [...] write code if it needs to write a bit of code from time to time to
# do small calculations [...] let's give it that freedom too."*
#
# **Honesty about what this ACTUALLY protects.** The real net is the TIMEOUT: a script that
# loops is killed after `_TIMEOUT_CODE_S`, full stop. `RLIMIT_CPU`/`RLIMIT_AS` are an EXTRA
# layer, not a guarantee: macOS does NOT reliably enforce `RLIMIT_AS` (a `malloc` can bypass it),
# and nothing here stops a script from opening an ABSOLUTE path outside `_bac()` — only the
# working directory (`cwd`) is confined. This is a SOFT sandbox, proportioned to "a small
# calculation" written by the operator's own local model on their own machine — not a hard
# security boundary, and this module never claims otherwise.

_TIMEOUT_CODE_S = 8
_MAX_SORTIE_CODE = 4000


def _brider() -> None:  # pragma: no cover - system-dependent, exercised indirectly by the tests
    """Best effort: see the warning above the SANDBOX block."""
    if resource is None:
        return
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (_TIMEOUT_CODE_S, _TIMEOUT_CODE_S))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    except (ValueError, OSError):
        pass


def executer_code(code: str) -> dict[str, Any]:
    """Runs ``code`` as an isolated Python script (``-I``: no site-packages, no inherited
    environment variables), inside `_bac()` — never anywhere else, never with Mnemosyne's own
    code reachable through a relative import."""
    propre = (code or "").strip()
    if not propre:
        return {"ok": False, "erreur": "no code to execute"}
    try:
        termine = subprocess.run(
            [sys.executable, "-I", "-c", propre],
            cwd=str(_bac()),
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_CODE_S,
            preexec_fn=_brider if os.name == "posix" else None,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "erreur": f"exceeded {_TIMEOUT_CODE_S} s — killed"}
    except OSError as exc:
        return {"ok": False, "erreur": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": termine.returncode == 0,
        "code_retour": termine.returncode,
        "stdout": termine.stdout[:_MAX_SORTIE_CODE],
        "stderr": termine.stderr[:_MAX_SORTIE_CODE],
    }


# ── THE TOOLS ───────────────────────────────────────────────────────────────────────────────────
#
# Same discipline as `intendant.OUTILS`: one catalog, two uses (the description injected into the
# model by `socle`, the execution table in `serve.py`) — never two copies that could drift apart.
# Four families: what it inherits (read-only, shared with the Steward), its MILESTONES, its
# DECISION MODELS, its sandbox.

OUTILS: dict[str, dict[str, str]] = {
    # ── inherited (read-only, shared — see serve.py) ──
    "rappel": {
        "args": "q",
        "quoi": "searches their past conversations with the frontier assistant "
        "(instant, no cost)",
    },
    "plans": {
        "args": "",
        "quoi": "the REAL state of their projects, item by item — useful for situating a "
        "decision within what they are working on",
    },
    "memoire": {
        "args": "q",
        "quoi": "searches Mnemosyne's library (slow: several seconds)",
    },
    "signaler": {
        "args": "titre",
        "quoi": "reports a Mnemosyne failure — only if they ask you to",
    },
    "voir_plus_loin": {
        "args": "",
        "quoi": "looks further back in THIS conversation's history, beyond what you already "
        "have in view — never by default, never if they are talking about something else",
    },
    # ── its milestones ──
    "chercher_jalons": {
        "args": "q",
        "quoi": "searches the milestones already set (instant)",
    },
    "poser_jalon": {
        "args": "titre, echeance, statut",
        "quoi": "sets ONE milestone — a dated point to track, never a task to check off (that's "
        "the Steward's job). echeance in ISO format if known (e.g. 2026-09-01), otherwise "
        "empty. statut is FREE-FORM text on where things stand — write it only if they said it, "
        "never by inventing it. \U000026A0\U0000FE0F A milestone NEVER repeats on its own: if the operator asks "
        "for a RECURRING reminder (every week, every Monday...), there is NO tool for that — "
        "tell them so, do NOT set a milestone pretending it will come back.",
    },
    "renommer_jalon": {
        "args": "titre_actuel, nouveau_titre",
        "quoi": "renames an ALREADY-set milestone — titre_actuel must reuse EXACTLY what they "
        "said, never a rephrasing.",
    },
    "statuer_jalon": {
        "args": "titre, statut",
        "quoi": 'updates the FREE-FORM status of an ALREADY-set milestone ("finally found it", '
        '"not yet, thinking about X") — titre must reuse EXACTLY what they said.',
    },
    "supprimer_jalon": {
        "args": "titre",
        "quoi": "removes an ALREADY-set milestone from their list (nothing is erased, it just "
        "leaves what they see) — titre must reuse EXACTLY what they said.",
    },
    # ── its decision models — REAL, hardcoded, never improvised (mnemosyne.runtime.decision) ──
    "decider_matrice": {
        "args": "options (list), criteres (list of {nom, poids}), notes ({option: {critere: note}})",
        "quoi": "weighted decision matrix (multi-criteria analysis) — WHEN they compare options "
        "against several criteria that count differently. Example args: "
        'options=["Offer A","Offer B"], criteres=[{"nom":"salary","poids":3},'
        '{"nom":"fulfillment","poids":5}], notes={"Offer A":{"salary":8,"fulfillment":6},'
        '"Offer B":{"salary":6,"fulfillment":9}}. Scores are out of 10, drawn from what they '
        "tell you — never invent them without them having given their own view on each "
        "criterion.",
    },
    "decider_incertitude": {
        "args": "options (list), scenarios (list of {nom, probabilite optional}), "
        "valeurs ({option: {scenario: valeur}})",
        "quoi": "decision under uncertainty (decision theory: cautious/optimistic/minimal "
        "regret, expectation if the probabilities are known) — WHEN the outcome depends on an "
        "uncertain future (several possible scenarios), not a simple choice between known "
        "options.",
    },
    "cadre_wrap": {
        "args": "",
        "quoi": "walks through the WRAP method (Heath) — WHEN they are hesitating over a "
        "decision that matters and no calculation applies (no numbers to compare). Returns a "
        "FIXED four-step frame, asks its questions one at a time, never invent them yourself.",
    },
    "cadre_premortem": {
        "args": "",
        "quoi": "walks through a premortem (Klein) — WHEN a decision has been made and they "
        "want to check its risks before committing.",
    },
    "cadre_10_10_10": {
        "args": "",
        "quoi": "walks through the 10-10-10 rule (Welch) — WHEN a decision is emotionally "
        "loaded in the moment and they need to step back.",
    },
    "matrice_eisenhower": {
        "args": "items (list of {nom, urgent, important})",
        "quoi": 'sorts a list of things by urgent/important — WHEN the question is "what to '
        'start with," not "which one to choose."',
    },
    # ── its notebook and its sandbox ──
    "noter_carnet": {
        "args": "texte",
        "quoi": "writes a note in ITS OWN personal notebook (the only place where you write "
        "freely, outside of milestones) — to remember a line of reasoning or a fact between two "
        "conversations.",
    },
    "lire_carnet": {
        "args": "",
        "quoi": "re-reads what you yourself noted in your notebook during past conversations.",
    },
    "executer_code": {
        "args": "code",
        "quoi": "runs a small Python script for a calculation you cannot do in your head "
        "(e.g. a compounding calculation, a simple simulation) — never for anything other than "
        "a calculation; the result comes from its own ``print(...)``.",
    },
}


def socle(
    *,
    jalons_proches: list[dict[str, Any]] | None = None,
    connexes: list[dict[str, Any]] | None = None,
    portrait: str = "",
) -> str:
    """The preamble re-injected on EVERY turn — same role and same discipline as
    `intendant.socle`: small, fixed, never negotiated. The difference is the CONTENT: here, the
    central instruction is to lean on a REAL decision model rather than improvising an opinion
    the moment a real choice comes up."""
    lignes = [
        "You are the operator's Advisor. They come to talk to you about their situation, their "
        "doubts, their trade-offs — you are a conversational chat, not a form.",
        "",
        "Rules:",
        "- Respond in French, direct and concrete. No preamble, no flattery.",
        "- You are NOT the Steward: you manage no to-do list. If the operator describes a task "
        "to do, tell them to give it to the Steward instead of pretending to note it down.",
        "- When a REAL decision comes up (a choice between options, an uncertainty, a recurring "
        "doubt), call the matching decision model rather than giving your own opinion off the "
        "top of your head — that is exactly why these tools exist.",
        "- If what they are asking for has NO tool to do it, say so clearly rather than "
        "inventing a workaround (for example setting a milestone that SIMULATES something you "
        "cannot do, like a recurring reminder — a milestone never comes back on its own).",
        "- You do not know everything about them. Go look with a tool rather than guessing.",
        "- If you do not know, say so.",
        "- After setting, renaming, updating the status of or removing a milestone, confirm in "
        "ONE SHORT SENTENCE. NEVER recap the rest of their milestones — they already have them "
        "in front of them — and add no generic closing formula.",
        "",
        "Your tools. To call one, respond ONLY with a JSON line of this form:",
        '{"outil": "<nom>", "args": {"<arg>": "<valeur>"}}',
        "The result will come back to you and you will then respond normally.",
    ]
    for nom, fiche in OUTILS.items():
        lignes.append(f"- {nom}({fiche['args']}) — {fiche['quoi']}")
    if portrait.strip():
        lignes += ["", "What you know about their life:", portrait.strip()]
    if jalons_proches:
        lignes += ["", "Their milestones coming up — bring them up if the subject fits:"]
        for j in jalons_proches[:5]:
            echeance = str(j.get("echeance", ""))[:10]
            statut = f" — {j['statut']}" if j.get("statut") else ""
            lignes.append(f"- [{echeance}] {j.get('titre', '')}{statut}")
    if connexes:
        lignes += [
            "",
            "What they have ALREADY told you on this subject — this is material you already "
            "have in hand, not a lead to explore. If they ask what they had said, ANSWER with "
            "this.",
        ]
        for j in connexes[:5]:
            statut = f" — {j['statut']}" if j.get("statut") else ""
            lignes.append(f"- {j.get('titre', '')}{statut}")
    lignes.append("")
    return "\n".join(lignes)


# ── READING WHAT A SMALL MODEL RETURNS ─────────────────────────────────────────────────────────


def _extraire_json(reponse: str) -> dict[str, Any] | None:
    """The first JSON object in a response, whatever surrounds it — same algorithm as
    `intendant._extraire_json` (counts braces, ignores the ones inside strings), duplicated
    rather than imported for the same reason as `titres_correspondent` above."""
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


def lire_appel(reponse: str) -> tuple[str, dict[str, Any]] | None:
    """A tool call within the response, or None. Refuses a tool outside the catalog — same
    guard as `intendant.lire_appel`, over THIS module's catalog."""
    objet = _extraire_json(reponse)
    if not objet:
        return None
    nom = objet.get("outil")
    if not isinstance(nom, str) or nom not in OUTILS:
        return None
    args = objet.get("args")
    return nom, (args if isinstance(args, dict) else {})
