"""Local web interface for Mnemosyne System."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"

ROOT = HERE.parents[2]


sys.path.insert(0, str(ROOT / "system" / "lib"))
try:
    from mnemosyne.runtime import intendant as INTENDANT  # noqa: N812
except Exception as _exc:  # noqa: BLE001 - an app that fails to start says nothing
    INTENDANT = None
    INTENDANT_PANNE = f"{type(_exc).__name__}: {_exc}"
else:
    INTENDANT_PANNE = ""


try:
    from mnemosyne.runtime import conseiller as CONSEILLER  # noqa: N812
    from mnemosyne.runtime import decision as DECISION  # noqa: N812
except Exception as _exc:  # noqa: BLE001 - an app that fails to start says nothing
    CONSEILLER = None
    DECISION = None
    CONSEILLER_PANNE = f"{type(_exc).__name__}: {_exc}"
else:
    CONSEILLER_PANNE = ""

CONTRACT_NAME = "mnemosyne-ui"


CONTRACT_VERSION = 2
DEFAULT_PORT = 7373
COMMAND_TIMEOUT_S = 60

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


def read_contract() -> dict:
    """Run `make ui-json` and return the payload, or a named failure.

    Never returns an empty payload to signal trouble. A dashboard showing "0
    signalements" because a command failed looks like good news, which is worse
    than showing nothing -- the same rule the contract applies to its own sources.
    """
    if not (ROOT / "Makefile").is_file():
        return _failure(
            "Could not find Mnemosyne.",
            f"Expected {ROOT} to be the repo root, but there is no Makefile there. "
            "Keep this app at its original depth inside the repository, so it can still find its root.",
        )

    try:
        done = subprocess.run(
            ["make", "ui-json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_S,
        )
    except FileNotFoundError:
        return _failure(
            "The `make` command was not found.",
            "It comes from Apple's developer tools. In a terminal: "
            "xcode-select --install",
        )
    except subprocess.TimeoutExpired:
        return _failure(
            "Mnemosyne did not respond.",
            f"`make ui-json` exceeded {COMMAND_TIMEOUT_S} seconds. "
            "It normally responds within milliseconds.",
        )

    if done.returncode != 0:
        return _failure(
            "Mnemosyne refused to report its state.",
            (done.stderr or done.stdout or "").strip()[:2000]
            or f"`make ui-json` stopped with code {done.returncode}, without saying anything.",
        )

    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        return _failure(
            "Mnemosyne's response is not readable.",
            f"The JSON is invalid ({exc}). First characters received: {done.stdout[:300]!r}",
        )

    got_name = payload.get("contrat")
    got_version = payload.get("version")
    if got_name != CONTRACT_NAME or got_version != CONTRACT_VERSION:
        return _failure(
            "Mnemosyne's contract changed shape.",
            f"This app reads '{CONTRACT_NAME}' version {CONTRACT_VERSION}; "
            f"Mnemosyne returns '{got_name}' version {got_version}. "
            "I would rather stop than display fields that have moved. "
            "Check the contract this app expects against what the backend returns, "
            "then update the app.",
        )

    payload["_lecture"] = {
        "ok": True,
        "contrat": CONTRACT_NAME,
        "version": CONTRACT_VERSION,
    }
    return payload


def read_basket() -> dict:
    """Run `make modeles JSON=1` and return the local-model basket, or a named failure.

    Same discipline as :func:`read_contract`, and for the same reason: the SECOND source this app
    reads must fail the same way as the first. An empty list would be read as "no local
    model", which is exactly the false conclusion the basket was created to kill (an agent once
    graved *"no model installed"* with a configured capacity of weights on the disk).

    It is a SEPARATE call, not a field of the contract: the contract describes plans and queues, and
    bolting an unrelated payload onto it would make one command's failure hide the other's.
    """
    if not (ROOT / "Makefile").is_file():
        return _failure(
            "Could not find Mnemosyne.",
            f"Expected {ROOT} to be the repo root, but there is no Makefile there.",
        )
    try:
        done = subprocess.run(
            ["make", "modeles", "JSON=1"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_S,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return _failure("The model basket did not respond.", str(exc))

    if done.returncode != 0:
        return _failure(
            "Mnemosyne refused to report its model basket.",
            (done.stderr or done.stdout or "").strip()[:2000],
        )
    try:
        payload = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        return _failure(
            "The basket's response is not readable.",
            f"The JSON is invalid ({exc}). First characters received: {done.stdout[:300]!r}",
        )
    payload["_lecture"] = {"ok": True}
    return payload


def _failure(titre: str, detail: str) -> dict:
    return {"_lecture": {"ok": False, "titre": titre, "detail": detail}}


_ATELIER: subprocess.Popen | None = None
_ATELIER_VERROU = threading.Lock()


_ANNULER_DECOUPAGE = threading.Event()


def _atelier() -> subprocess.Popen:
    """UI endpoint behavior; covered by contract tests."""
    global _ATELIER
    if _ATELIER is not None and _ATELIER.poll() is None:
        return _ATELIER
    _ATELIER = subprocess.Popen(
        ["uv", "run", "--extra", "bricks", "python", "-m", "mnemosyne.runtime.atelier"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "system/lib"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
    )
    return _ATELIER


def etat_atelier() -> dict:
    """What the worker currently holds - WITHOUT starting one.

    Asking a dead worker must never spawn a live one: this endpoint is polled by the screen to say
    "no agent loaded", and a probe that creates what it measures would make that sentence false
    the instant it is read."""
    with _ATELIER_VERROU:
        if _ATELIER is None or _ATELIER.poll() is not None:
            return {"vivant": False, "modele": "", "tours": 0}
        try:
            _ATELIER.stdin.write(json.dumps({"geste": "etat"}) + "\n")
            _ATELIER.stdin.flush()
            ligne = _ATELIER.stdout.readline()
        except OSError:
            return {"vivant": False, "modele": "", "tours": 0}
    try:
        dit = json.loads(ligne)
    except json.JSONDecodeError:
        return {"vivant": False, "modele": "", "tours": 0}

    return {**dit, "vivant": dit.get("etat") == "pret"}


def arreter_atelier() -> dict:
    """UI endpoint behavior; covered by contract tests."""
    global _ATELIER

    _ANNULER_DECOUPAGE.set()
    cible = _ATELIER
    vivant = cible is not None and cible.poll() is None
    if cible is not None:
        try:
            cible.stdin.close()
        except OSError:
            pass
        cible.terminate()
    with _ATELIER_VERROU:
        _ANNULER_DECOUPAGE.clear()

        if _ATELIER is cible and cible is not None:
            try:
                cible.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cible.kill()
                cible.wait(timeout=10)
            _ATELIER = None
    return {"etat": "arrete", "il_tournait": vivant}


def _envoyer(requete: dict) -> dict:
    """ONE round trip with the worker. WARNING: DOES NOT ACQUIRE THE LOCK - the caller already holds it.

    Separated from :func:`parler` because one Intendant turn chains SEVERAL of these (lay the
    preamble, attach the thread, speak, render a tool result) and these messages must travel
    without another turn slipping in between: the second would read the first's reply."""
    try:
        worker = _atelier()
        worker.stdin.write(json.dumps(requete, ensure_ascii=False) + "\n")
        worker.stdin.flush()
        ligne = worker.stdout.readline()
    except OSError as exc:
        return {"etat": "refus", "genre": "atelier_injoignable", "detail": str(exc)}
    if not ligne:
        return {
            "etat": "refus",
            "genre": "atelier_muet",
            "detail": "The workshop stopped without answering. Its log is at "
            f"{ROOT / '.journal/serveur.log'}.",
        }
    try:
        return json.loads(ligne)
    except json.JSONDecodeError as exc:
        return {"etat": "refus", "genre": "reponse_illisible", "detail": f"{exc} - {ligne[:300]!r}"}


def parler(requete: dict) -> dict:
    """One chat turn: hand it to the worker, give back what it said, or a NAMED refusal.

    No timeout on the read, deliberately. Loading a configured-capacity model is minutes of legitimate silence,
    and a timeout short enough to be useful on a warm turn would kill every cold one - the interface
    shows the elapsed time instead, which is the honest version of "it is working"."""
    with _ATELIER_VERROU:
        return _envoyer(requete)


_SEUIL_DECOUPAGE = 200


_MAX_OUTILS = 8


_COUPE_OUTIL = 6_000


_MAX_SOUS_TACHES_OUTIL = 12


def _outil_shell(cible: list[str], timeout: int = 90) -> str:
    """Runs a `make` target and returns its output. Never a shell: the arguments come from a
    MODEL, and a string interpreted by a shell would be an injection wide open to the sky."""
    try:
        done = subprocess.run(cible, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return "(the `make` command was not found)"
    except subprocess.TimeoutExpired:
        return f"(no response within {timeout} s)"
    return (done.stdout or done.stderr or "").strip() or "(nothing)"


def _texte_plans() -> str:
    """UI endpoint behavior; covered by contract tests."""
    carte = INTENDANT.projets()
    contrat = read_contract()
    if not contrat.get("_lecture", {}).get("ok"):
        return carte or "(project state is unreadable)"

    lignes = []
    for projet in (contrat.get("projets") or {}).get("items") or []:
        if not isinstance(projet, dict):
            continue
        items = [i for i in (projet.get("items") or []) if isinstance(i, dict)]
        if not items:
            lignes.append(f"- {projet.get('nom', '?')} : unreadable plan ({projet.get('etat')})")
            continue
        reste = [i for i in items if i.get("etat") not in ("fait", "clos")]
        lignes.append(
            f"- {projet.get('nom', '?')} : {len(reste)} item(s) remaining out of {len(items)}"
        )
        for i in reste[:3]:
            lignes.append(f"     -  {i.get('titre', '')[:90]}")
    compteurs = "\n".join(lignes) or "(no readable plan)"
    if not carte:
        return compteurs
    return f"{carte}\n\n--- where the plans stand, right now ---\n{compteurs}"


def executer_outil(nom: str, args: dict, etat_fil: dict | None = None) -> str:
    """UI endpoint behavior; covered by contract tests."""
    try:
        return _executer_outil(nom, args, etat_fil or {})
    except Exception as exc:  # noqa: BLE001 - a tool must never take the conversation down with it
        return f"(tool '{nom}' failed: {type(exc).__name__} - {exc})"


def _executer_outil(nom: str, args: dict, etat_fil: dict) -> str:
    """Executes ONE tool from the catalogue and renders its result as text.

    The table is here and the catalogue is in the module: the module tells the model what
    exists, this table says how it runs. A tool absent from here returns a NAMED refusal rather
    than an empty string - an empty string reads as "nothing found", which is a conclusion, not
    a failure."""
    q = str(args.get("q", "")).strip()
    if nom == "chercher_notes":
        trouvees = INTENDANT.chercher(q, limite=8)
        if not trouvees:
            return "Nothing filed on that."
        return "\n".join(
            f"- [{n.get('depose_le', '')[:10]}] {n.get('texte', '')[:300]}" for n in trouvees
        )
    if nom == "rappel":
        return _outil_shell(["make", "rappel", f"Q={q}", "TOPK=5"])[:_COUPE_OUTIL]
    if nom == "memoire":
        return _outil_shell(["make", "search", f"Q={q}", "TOPK=5"], timeout=180)[:_COUPE_OUTIL]
    if nom == "plans":
        return _texte_plans()
    if nom == "signaler":
        titre = str(args.get("titre", "")).strip()
        if not titre:
            return "(a title is required to report something)"
        return _outil_shell(["make", "signaler", f"TITRE={titre}"])[:2000]
    if nom == "poser_tache":
        return _outil_poser_tache(args)
    if nom == "voir_plus_loin":
        return _outil_voir_plus_loin(etat_fil)
    if nom == "renommer_tache":
        return _outil_renommer_tache(args)
    if nom == "supprimer_tache":
        return _outil_supprimer_tache(args)
    if nom == "decrire_tache":
        return _outil_decrire_tache(args)
    if nom == "ajouter_sous_tache":
        return _outil_ajouter_sous_tache(args)
    if nom == "deplacer_sous_tache":
        return _outil_deplacer_sous_tache(args)
    return f"(tool '{nom}' does not exist)"


def _outil_voir_plus_loin(etat_fil: dict) -> str:
    """`voir_plus_loin` - an older slice of the thread, beyond what this turn has already received.

    This is NOT direct access to `Atelier._fil` from this file: the worker lives in ANOTHER
    process (see atelier, held by `_ATELIER`), so the only door is the stdin/stdout protocol, the
    same one `dire`/`attacher` use. `etat_fil['fin']` is set by `_tour_unique` right after the first
    `dire` call (at `fil_total - fil_garde`, the exact spot where the prompt stopped climbing back)
    and RETURNED by every following call: an absolute index into a list that only ever grows stays
    correct turn after turn, whereas a relative count would drift with every new exchange added
    in between."""
    rep = _envoyer({"geste": "fil_plus_loin", "fin": etat_fil.get("fin", 0), "combien": 4})
    if rep.get("etat") != "trouve":
        return "(nothing older - this is the very start of this conversation.)"
    etat_fil["fin"] = rep.get("fin", 0)
    reste = etat_fil["fin"]
    fin_mot = (
        f"({reste} older exchange(s) still available, if you need to go further back.)"
        if reste
        else "(this is now the very start of the conversation.)"
    )
    return f"{rep.get('texte', '')}\n\n{fin_mot}"


def _outil_poser_tache(args: dict) -> str:
    """UI endpoint behavior; covered by contract tests."""
    titre = str(args.get("titre", "")).strip()
    if not titre:
        return "(a title is required to create a task)"
    section = str(args.get("section", "") or "todo").strip()
    if section not in INTENDANT.HORIZONS:
        section = "todo"
    echeance = str(args.get("echeance", "") or "").strip() if section == "deadline" else ""

    description = str(args.get("description", "") or "").strip()
    brutes = args.get("sous_taches")
    sous_taches = (
        [str(s).strip() for s in brutes if str(s).strip()][:_MAX_SOUS_TACHES_OUTIL]
        if isinstance(brutes, list)
        else []
    )
    parent = INTENDANT.deposer(
        titre, genre="tache", horizon=section, echeance=echeance, description=description
    )
    for s in sous_taches:
        INTENDANT.deposer(s, genre="tache", parent=parent["id"])
    if sous_taches:
        return (
            f"Added: '{titre}' ({section}) with {len(sous_taches)} subtask(s) - "
            + ", ".join(sous_taches)
        )
    return f"Added: '{titre}' ({section})."


def _resoudre_titre(titre: str) -> tuple[dict | None, str]:
    """UI endpoint behavior; covered by contract tests."""
    propre = titre.strip()
    if not propre:
        return None, "(a title is required to identify the task)"
    trouvees = INTENDANT.notes_par_titre(propre)
    if not trouvees:
        return None, f"(no task called '{propre}' in the list)"
    if len(trouvees) > 1:
        lieux = ", ".join("root" if not n.get("parent") else "subtask" for n in trouvees)
        return None, (
            f"({len(trouvees)} tasks are named '{propre}' ({lieux}) - "
            "ask them to specify which one before acting)"
        )
    return trouvees[0], ""


def _outil_renommer_tache(args: dict) -> str:
    """UI endpoint behavior; covered by contract tests."""
    note, erreur = _resoudre_titre(str(args.get("titre_actuel", "")))
    if erreur:
        return erreur
    new_title = str(args.get("nouveau_titre", "")).strip()
    if not new_title:
        return "(a new title is required)"
    before = note.get("resume") or note.get("texte", "")
    INTENDANT.ranger(note["id"], resume=new_title)
    return f"Renamed: '{before}' -> '{new_title}'."


def _outil_supprimer_tache(args: dict) -> str:
    """Removes (never erases, invariant 2) - same gesture and same cascade as the [no] button on
    the screen (`_descendance`): removing a mother without her children would bubble them back up
    to root level, which is the opposite of what 'delete this task' is meant to do."""
    note, erreur = _resoudre_titre(str(args.get("titre", "")))
    if erreur:
        return erreur
    cibles = [*_descendance(note["id"]), note["id"]]
    for note_id in cibles:
        INTENDANT.marquer(note_id, "retiree")
    libelle = note.get("resume") or note.get("texte", "")
    extra = f" (and {len(cibles) - 1} subtask(s))" if len(cibles) > 1 else ""
    return f"Removed: '{libelle}'{extra}."


def _outil_decrire_tache(args: dict) -> str:
    note, erreur = _resoudre_titre(str(args.get("titre", "")))
    if erreur:
        return erreur
    description = str(args.get("description", "")).strip()
    if not description:
        return "(a description is required)"
    INTENDANT.ranger(note["id"], description=description)
    libelle = note.get("resume") or note.get("texte", "")
    return f"Description added to '{libelle}'."


def _outil_ajouter_sous_tache(args: dict) -> str:
    """UI endpoint behavior; covered by contract tests."""
    parent, erreur = _resoudre_titre(str(args.get("titre_parent", "")))
    if erreur:
        return erreur
    brutes = args.get("sous_taches")
    sous_taches = (
        [str(s).strip() for s in brutes if str(s).strip()][:_MAX_SOUS_TACHES_OUTIL]
        if isinstance(brutes, list)
        else []
    )
    if not sous_taches:
        return "(at least one subtask is required to add)"
    for s in sous_taches:
        INTENDANT.deposer(s, genre="tache", parent=parent["id"])
    libelle = parent.get("resume") or parent.get("texte", "")
    return f"Added to '{libelle}': " + ", ".join(sous_taches)


def _outil_deplacer_sous_tache(args: dict) -> str:
    """UI endpoint behavior; covered by contract tests."""
    note, erreur = _resoudre_titre(str(args.get("titre", "")))
    if erreur:
        return erreur
    nouveau_parent, erreur = _resoudre_titre(str(args.get("nouveau_parent_titre", "")))
    if erreur:
        return erreur
    if nouveau_parent["id"] == note["id"]:
        return "(a task cannot become its own subtask)"
    if nouveau_parent["id"] in _descendance(note["id"]):
        cible = nouveau_parent.get("resume") or nouveau_parent.get("texte", "")
        libelle = note.get("resume") or note.get("texte", "")
        return (
            f"(impossible: '{cible}' is already a subtask of '{libelle}' - "
            "putting them under each other the other way round would create a loop)"
        )
    INTENDANT.ranger(note["id"], parent=nouveau_parent["id"])
    libelle = note.get("resume") or note.get("texte", "")
    cible = nouveau_parent.get("resume") or nouveau_parent.get("texte", "")
    return f"'{libelle}' is now a subtask of '{cible}'."


def executer_outil_conseiller(nom: str, args: dict, etat_fil: dict | None = None) -> str:
    """Same envelope as `executer_outil`: a tool that breaks returns a sentence, never an
    exception that propagates up into the conversation."""
    try:
        return _executer_outil_conseiller(nom, args, etat_fil or {})
    except Exception as exc:  # noqa: BLE001 - a tool must never take the conversation down with it
        return f"(tool '{nom}' failed: {type(exc).__name__} - {exc})"


def _resoudre_titre_jalon(titre: str) -> tuple[dict | None, str]:
    """Same role as `_resoudre_titre` on the Intendant's side, for the Conseiller's store."""
    propre = titre.strip()
    if not propre:
        return None, "(a title is required to identify the milestone)"
    trouves = CONSEILLER.jalons_par_titre(propre)
    if not trouves:
        return None, f"(no milestone called '{propre}' in the list)"
    if len(trouves) > 1:
        return None, (
            f"({len(trouves)} milestones are named '{propre}' - ask them to specify which one "
            "before acting)"
        )
    return trouves[0], ""


def _outil_poser_jalon(args: dict) -> str:
    titre = str(args.get("titre", "")).strip()
    if not titre:
        return "(a title is required to create a milestone)"
    echeance = str(args.get("echeance", "") or "").strip()
    statut = str(args.get("statut", "") or "").strip()
    jalon = CONSEILLER.deposer_jalon(titre, echeance=echeance, statut=statut)
    extra = f" (due {jalon['echeance']})" if jalon["echeance"] else ""
    return f"Added: '{titre}'{extra}."


def _outil_renommer_jalon(args: dict) -> str:
    jalon, erreur = _resoudre_titre_jalon(str(args.get("titre_actuel", "")))
    if erreur:
        return erreur
    nouveau = str(args.get("nouveau_titre", "")).strip()
    if not nouveau:
        return "(a new title is required)"
    CONSEILLER.ranger_jalon(jalon["id"], titre=nouveau)
    return f"Renamed: '{jalon['titre']}' -> '{nouveau}'."


def _outil_statuer_jalon(args: dict) -> str:
    jalon, erreur = _resoudre_titre_jalon(str(args.get("titre", "")))
    if erreur:
        return erreur
    statut = str(args.get("statut", "")).strip()
    if not statut:
        return "(a status is required)"
    CONSEILLER.ranger_jalon(jalon["id"], statut=statut)
    return f"Status updated for '{jalon['titre']}': {statut}"


def _outil_supprimer_jalon(args: dict) -> str:
    jalon, erreur = _resoudre_titre_jalon(str(args.get("titre", "")))
    if erreur:
        return erreur
    CONSEILLER.marquer_jalon(jalon["id"], "retiree")
    return f"Removed: '{jalon['titre']}'."


def _formater_matrice_ponderee(resultat: dict) -> str:
    if resultat.get("erreur"):
        return f"(missing what is needed to compute: {resultat['erreur']})"
    lignes = [f"Weighted matrix - winner: {resultat['gagnant']}"]
    for o in resultat["options"]:
        lignes.append(f"- {o['option']} : score {o['score']}")
        for d in o["detail"]:
            lignes.append(
                f"     -  {d['critere']} (weight {round(d['poids_relatif'] * 100)}%) : "
                f"score {d['note']} -> {d['contribution']}"
            )
    return "\n".join(lignes)


def _formater_decision_incertitude(resultat: dict) -> str:
    if resultat.get("erreur"):
        return f"(missing what is needed to compute: {resultat['erreur']})"
    lignes = ["Decision under uncertainty:"]
    for o in resultat["options"]:
        morceau = (
            f"- {o['option']} : conservative={o['maximin_pessimiste']}, "
            f"optimistic={o['maximax_optimiste']}, indifference={o['laplace_equiprobable']}, "
            f"max regret={o['regret_maximal']}"
        )
        if "esperance" in o:
            morceau += f", expectation={o['esperance']}"
        lignes.append(morceau)
    lignes.append("Verdicts by criterion:")
    for cle, gagnant in resultat["verdicts"].items():
        lignes.append(f"- {cle} : {gagnant}")
    lignes.append(
        "The criteria AGREE."
        if resultat["accord"]
        else "The criteria DISAGREE - tell the user, that disagreement is itself useful information."
    )
    return "\n".join(lignes)


def _formater_cadre(resultat: dict) -> str:
    lignes = [f"Framework: {resultat['cadre']} ({resultat['source']})"]
    if resultat.get("consigne"):
        lignes.append(resultat["consigne"])
    for etape in resultat.get("etapes", []):
        lignes.append(f"\n{etape.get('titre') or etape.get('lettre', '')} :")
        questions = etape.get("questions")
        if questions is None:
            questions = [etape.get("question", "")]
        for q in questions:
            if q:
                lignes.append(f"- {q}")
    for q in resultat.get("questions", []):
        lignes.append(f"- [{q['horizon']}] {q['question']}")
    return "\n".join(lignes)


def _formater_eisenhower(resultat: dict) -> str:
    if not any(resultat["quadrants"].values()):
        return "(give at least one item with a name, urgent, and important)"
    lignes = ["Eisenhower matrix:"]
    for quadrant, items in resultat["quadrants"].items():
        if not items:
            continue
        lignes.append(f"{quadrant} :")
        for i in items:
            lignes.append(f"- {i['nom']}")
    return "\n".join(lignes)


def _executer_outil_conseiller(nom: str, args: dict, etat_fil: dict) -> str:
    q = str(args.get("q", "")).strip()
    if nom == "chercher_jalons":
        trouves = CONSEILLER.chercher_jalons(q, limite=8)
        if not trouves:
            return "Nothing filed on that."
        return "\n".join(
            f"- [{(j.get('echeance', '') or 'no date')[:10]}] {j.get('titre', '')}"
            + (f" - {j['statut']}" if j.get("statut") else "")
            for j in trouves
        )
    if nom == "rappel":
        return _outil_shell(["make", "rappel", f"Q={q}", "TOPK=5"])[:_COUPE_OUTIL]
    if nom == "memoire":
        return _outil_shell(["make", "search", f"Q={q}", "TOPK=5"], timeout=180)[:_COUPE_OUTIL]
    if nom == "plans":
        return _texte_plans()
    if nom == "signaler":
        titre = str(args.get("titre", "")).strip()
        if not titre:
            return "(a title is required to report something)"
        return _outil_shell(["make", "signaler", f"TITRE={titre}"])[:2000]
    if nom == "voir_plus_loin":
        return _outil_voir_plus_loin(etat_fil)
    if nom == "poser_jalon":
        return _outil_poser_jalon(args)
    if nom == "renommer_jalon":
        return _outil_renommer_jalon(args)
    if nom == "statuer_jalon":
        return _outil_statuer_jalon(args)
    if nom == "supprimer_jalon":
        return _outil_supprimer_jalon(args)
    if nom == "decider_matrice":
        resultat = DECISION.matrice_ponderee(
            args.get("options"), args.get("criteres"), args.get("notes")
        )
        return _formater_matrice_ponderee(resultat)
    if nom == "decider_incertitude":
        resultat = DECISION.decision_incertitude(
            args.get("options"), args.get("scenarios"), args.get("valeurs")
        )
        return _formater_decision_incertitude(resultat)
    if nom == "cadre_wrap":
        return _formater_cadre(DECISION.cadre_wrap())
    if nom == "cadre_premortem":
        return _formater_cadre(DECISION.cadre_premortem())
    if nom == "cadre_10_10_10":
        return _formater_cadre(DECISION.cadre_10_10_10())
    if nom == "matrice_eisenhower":
        return _formater_eisenhower(DECISION.matrice_eisenhower(args.get("items")))
    if nom == "noter_carnet":
        texte = str(args.get("texte", "")).strip()
        if not texte:
            return "(nothing to note)"
        CONSEILLER.noter_carnet(texte)
        return "Noted."
    if nom == "lire_carnet":
        return CONSEILLER.lire_carnet() or "(notebook empty)"
    if nom == "executer_code":
        resultat = CONSEILLER.executer_code(str(args.get("code", "")))
        if not resultat.get("ok"):
            return f"(failed: {resultat.get('erreur') or resultat.get('stderr', '')[:500]})"
        sortie = resultat.get("stdout", "").strip()
        return (
            sortie
            or "(ran without error, but nothing was displayed - remember to print(...) the result)"
        )
    return f"(tool '{nom}' does not exist)"


def _ressemble_a_un_appel_rate(texte: str) -> bool:
    """UI endpoint behavior; covered by contract tests."""
    nu = texte.strip()
    if nu.startswith("```"):
        nu = nu.split("\n", 1)[1] if "\n" in nu else ""
        nu = nu.strip()
    return nu.startswith("{") and '"outil"' in nu


def _tour_unique_conseiller(
    fil_id: str, modele: str, texte: str
) -> tuple[dict, list[dict], list, list]:
    """The Conseiller-side counterpart to `_tour_unique` - same structure, over ITS OWN preamble and
    ITS OWN tools. No mode (the Conseiller never had one), no splitting or grouping (see
    `conseiller_parler`; a deliberate choice to keep this first pass simple)."""
    proches = CONSEILLER.jalons_proches(limite=5)
    connexes = CONSEILLER.jalons_pertinents(texte, limite=5)
    pose = _envoyer(
        {
            "geste": "socle",
            "texte": CONSEILLER.socle(
                jalons_proches=proches, connexes=connexes, portrait=INTENDANT.portrait()
            ),
        }
    )
    if pose.get("etat") == "refus":
        return pose, [], proches, connexes

    depart = time.monotonic()
    reponse = _envoyer({"geste": "dire", "modele": modele, "texte": texte})
    appels: list[dict] = []
    dernier_appel: tuple[str, dict] | None = None
    etat_fil = {"fin": max(0, int(reponse.get("fil_total", 0)) - int(reponse.get("fil_garde", 0)))}
    for _ in range(_MAX_OUTILS):
        if reponse.get("etat") != "reponse":
            break
        appel = CONSEILLER.lire_appel(str(reponse.get("texte", "")))
        if appel is None:
            if _ressemble_a_un_appel_rate(str(reponse.get("texte", ""))):
                reponse = _envoyer(
                    {
                        "geste": "dire",
                        "modele": modele,
                        "texte": "Your previous tool call was malformed JSON "
                        "(probably a missing or extra closing brace). Respond "
                        "ONLY with the same call, in valid JSON this time - nothing before, "
                        "nothing after.",
                    }
                )
                appel = CONSEILLER.lire_appel(str(reponse.get("texte", "")))
            if appel is None:
                break
        nom, args = appel

        if (nom, args) == dernier_appel:
            reponse = {
                "etat": "reponse",
                "texte": f"I cannot execute this action: {appels[-1]['resultat']}"
                if appels
                else "I cannot execute this action.",
            }
            break
        dernier_appel = (nom, args)
        resultat = executer_outil_conseiller(nom, args, etat_fil)
        appels.append({"outil": nom, "args": args, "resultat": resultat[:1200]})
        if nom == "voir_plus_loin":
            suite = (
                "If that is enough, answer the user now, without calling the tool again. "
                "Otherwise, call `voir_plus_loin` again to keep climbing back."
            )
        else:
            suite = (
                "Confirm in ONE SHORT sentence what was just done. NEVER repeat "
                "the rest of their milestones (they already have them in view) and add no "
                "generic closing formula. Without calling the tool again."
            )
        reponse = _envoyer(
            {
                "geste": "dire",
                "modele": modele,
                "texte": f"Result of {nom}:\n{resultat}\n\n{suite}",
            }
        )

    secondes = round(time.monotonic() - depart, 2)
    fil_ecrit = False
    if reponse.get("etat") == "reponse":
        fil_ecrit = (
            CONSEILLER.fil_ajouter(fil_id, texte, str(reponse.get("texte", "")), secondes=secondes)
            is not None
        )
    reponse["fil_ecrit"] = fil_ecrit
    reponse["secondes"] = secondes
    return reponse, appels, proches, connexes


def conseiller_parler(fil_id: str, modele: str, texte: str) -> dict:
    """UI endpoint behavior; covered by contract tests."""
    if CONSEILLER is None:
        return {"etat": "refus", "genre": "conseiller_absent", "detail": CONSEILLER_PANNE}
    if not texte.strip():
        return {"etat": "refus", "genre": "rien_a_dire", "detail": "empty message"}
    if not fil_id:
        fil_id = str(CONSEILLER.fil_neuf(modele=modele).get("id", ""))

    with _ATELIER_VERROU:
        attache = _envoyer({"geste": "attacher", "fil_id": fil_id, "magasin": "conseiller"})
        if attache.get("etat") == "refus":
            return attache

        reponse, appels, proches, connexes = _tour_unique_conseiller(fil_id, modele, texte)
    reponse["outils_appeles"] = appels
    reponse["fil_id"] = fil_id
    reponse["jalons_proches"] = [{"id": j["id"], "titre": j.get("titre", "")} for j in proches]
    reponse["connexes"] = [{"id": j["id"], "titre": j.get("titre", "")} for j in connexes]
    return reponse


def ajouter_jalon(texte: str, echeance: str = "", statut: str = "") -> dict:
    """UI endpoint behavior; covered by contract tests."""
    propre = texte.strip()
    if not propre:
        return {"etat": "refus", "genre": "rien_a_poser", "detail": "an empty milestone does not exist"}
    jalon = CONSEILLER.deposer_jalon(propre, echeance=echeance, statut=statut)
    return {"etat": "ok", "jalon": jalon, **CONSEILLER.etat()}


def conseiller_geste(requete: dict) -> dict:
    """The single entry point for the Conseiller's store - same envelope as `intendant_geste`."""
    if CONSEILLER is None:
        return {"etat": "refus", "genre": "conseiller_absent", "detail": CONSEILLER_PANNE}
    geste = str(requete.get("geste", ""))
    try:
        return _conseiller_geste(geste, requete)
    except ValueError as exc:
        return {"etat": "refus", "genre": "argument_invalide", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 - a named refusal beats a dead connection
        import traceback

        return {
            "etat": "refus",
            "genre": f"panne_{type(exc).__name__}",
            "detail": f"{exc}\n\n{traceback.format_exc()[-1500:]}",
        }


def _conseiller_geste(geste: str, requete: dict) -> dict:
    """The bare routing. Its failures are caught by the caller, never here."""
    if geste == "etat":
        return {"etat": "ok", **CONSEILLER.etat()}
    if geste == "jalon":
        return ajouter_jalon(
            str(requete.get("texte", "")),
            str(requete.get("echeance", "")),
            str(requete.get("statut", "")),
        )
    if geste == "marquer":
        nouvel = str(requete.get("nouvel_etat", ""))
        CONSEILLER.marquer_jalon(str(requete.get("id", "")), nouvel)
        return {"etat": "ok", **CONSEILLER.etat()}
    if geste == "ranger":
        CONSEILLER.ranger_jalon(
            str(requete.get("id", "")),
            titre=str(requete.get("titre", "")),
            echeance=str(requete.get("echeance", "")),
            statut=str(requete.get("statut", "")),
        )
        return {"etat": "ok", **CONSEILLER.etat()}
    if geste == "chercher":
        return {"etat": "ok", "jalons": CONSEILLER.chercher_jalons(str(requete.get("q", "")))}
    if geste == "fil_neuf":
        return {"etat": "ok", "fil": CONSEILLER.fil_neuf(modele=str(requete.get("modele", "")))}
    if geste == "fil":
        demande = str(requete.get("id", ""))
        fil = CONSEILLER.fil_lire(demande) if demande else CONSEILLER.fil_dernier()
        return {"etat": "ok", "fil": fil}
    if geste == "parler":
        return conseiller_parler(
            str(requete.get("fil_id", "")),
            str(requete.get("modele", "")),
            str(requete.get("texte", "")),
        )
    return {"etat": "refus", "genre": "geste_inconnu", "detail": repr(geste)}


def _deposer_groupes(groupes: list[dict]) -> str:
    """UI endpoint behavior; covered by contract tests."""
    dernier_id_par_titre: dict[str, str] = {}

    def _resoudre_ou_creer(
        titre: str, *, section: str = "todo", echeance: str = "", description: str = ""
    ) -> tuple[str, str]:
        for titre_connu, rid in dernier_id_par_titre.items():
            if INTENDANT.titres_correspondent(titre_connu, titre):
                return rid, "already there (this message)"
        existante = INTENDANT.racine_par_titre(titre)
        if existante:
            dernier_id_par_titre[titre] = existante["id"]
            return existante["id"], "already there"
        racine = INTENDANT.deposer(
            titre, genre="tache", horizon=section, echeance=echeance, description=description
        )
        dernier_id_par_titre[titre] = racine["id"]
        return racine["id"], f"new, {section}"

    lignes: list[str] = []

    for g in groupes:
        if g["parent_titre"]:
            continue
        racine_id, marque = _resoudre_ou_creer(
            g["titre"], section=g["section"], echeance=g["echeance"], description=g["description"]
        )
        for s in g["sous_taches"]:
            INTENDANT.deposer(s, genre="tache", parent=racine_id)
        lignes.append(
            f"- '{g['titre']}' ({marque}) : "
            + (
                f"+{len(g['sous_taches'])} subtask(s) - {', '.join(g['sous_taches'])}"
                if g["sous_taches"]
                else "nothing to add"
            )
        )

    for g in groupes:
        if not g["parent_titre"]:
            continue
        parent_id, parent_marque = _resoudre_ou_creer(g["parent_titre"])
        for s in [g["titre"], *g["sous_taches"]]:
            INTENDANT.deposer(s, genre="tache", parent=parent_id)
        lignes.append(
            f"- '{g['titre']}' -> subtask of '{g['parent_titre']}' ({parent_marque})"
        )

    return "\n".join(lignes) if lignes else "(nothing to create)"


def _tour_unique(
    fil_id: str, modele: str, mode: str, texte: str
) -> tuple[dict, list[dict], list, list]:
    """ONE conversation turn - preamble, speak, tools included. The core shared by a simple
    message AND by EACH task of a split message: the two must behave identically, otherwise
    splitting would change the quality of the reply rather than only its pacing.

    Called with `_ATELIER_VERROU` already held, and the thread already attached - attaching does
    not depend on the task, only the preamble does (reminders and related items are computed on
    THIS text)."""
    en_attente = INTENDANT.rappeler_situation(texte, limite=5)
    connexes = INTENDANT.pertinentes(texte, limite=5)
    pose = _envoyer(
        {
            "geste": "socle",
            "texte": INTENDANT.socle(
                mode, en_attente=en_attente, connexes=connexes, portrait=INTENDANT.portrait()
            ),
        }
    )
    if pose.get("etat") == "refus":
        return pose, [], en_attente, connexes

    depart = time.monotonic()
    reponse = _envoyer({"geste": "dire", "modele": modele, "texte": texte})
    appels: list[dict] = []
    dernier_appel: tuple[str, dict] | None = None

    etat_fil = {"fin": max(0, int(reponse.get("fil_total", 0)) - int(reponse.get("fil_garde", 0)))}
    for _ in range(_MAX_OUTILS):
        if reponse.get("etat") != "reponse":
            break
        appel = INTENDANT.lire_appel(str(reponse.get("texte", "")))
        if appel is None:
            break
        nom, args = appel

        if (nom, args) == dernier_appel:
            reponse = {
                "etat": "reponse",
                "texte": f"I cannot execute this action: {appels[-1]['resultat']}"
                if appels
                else "I cannot execute this action.",
            }
            break
        dernier_appel = (nom, args)
        resultat = executer_outil(nom, args, etat_fil)
        appels.append({"outil": nom, "args": args, "resultat": resultat[:1200]})

        if nom == "voir_plus_loin":
            suite = (
                "If that is enough, answer the user now, without calling the tool again. "
                "Otherwise, call `voir_plus_loin` again to keep climbing back."
            )
        elif nom == "poser_tache":
            suite = (
                "If they described OTHER distinct groups of tasks besides this one in the same "
                "message, call `poser_tache` ONE MORE TIME for the next group "
                "(never the one already created). Otherwise, confirm in ONE SHORT sentence what "
                "was created - never a reminder of the rest of their list, never a "
                "generic closing formula. Without calling the tool again."
            )
        else:
            suite = (
                "Confirm in ONE SHORT sentence what was just done. NEVER repeat "
                "the rest of their list (they already have it in view) and add no "
                "generic closing formula. Without calling the tool again."
            )
        reponse = _envoyer(
            {
                "geste": "dire",
                "modele": modele,
                "texte": f"Result of {nom}:\n{resultat}\n\n{suite}",
            }
        )

    secondes = round(time.monotonic() - depart, 2)
    fil_ecrit = False
    if reponse.get("etat") == "reponse":
        fil_ecrit = (
            INTENDANT.fil_ajouter(fil_id, texte, str(reponse.get("texte", "")), secondes=secondes)
            is not None
        )
    reponse["fil_ecrit"] = fil_ecrit
    reponse["secondes"] = secondes
    return reponse, appels, en_attente, connexes


def intendant_parler(fil_id: str, modele: str, texte: str, mode: str = "libre") -> dict:
    """UI endpoint behavior; covered by contract tests."""
    if INTENDANT is None:
        return {"etat": "refus", "genre": "intendant_absent", "detail": INTENDANT_PANNE}
    if not texte.strip():
        return {"etat": "refus", "genre": "rien_a_dire", "detail": "empty message"}

    if not fil_id:
        fil_id = str(INTENDANT.fil_neuf(modele=modele).get("id", ""))

    with _ATELIER_VERROU:
        groupes: list[dict] = []
        depart_groupement = 0.0
        if len(texte) >= _SEUIL_DECOUPAGE:
            _envoyer({"geste": "socle", "texte": ""})
            _envoyer({"geste": "attacher", "fil_id": ""})
            depart_groupement = time.monotonic()
            rep_groupement = _envoyer(
                {"geste": "dire", "modele": modele, "texte": INTENDANT.invite_groupement(texte)}
            )
            if rep_groupement.get("etat") == "reponse":
                groupes = INTENDANT.lire_groupement(str(rep_groupement.get("texte", "")))

        if groupes:
            resume = _deposer_groupes(groupes)
            secondes = round(time.monotonic() - depart_groupement, 2)
            INTENDANT.fil_ajouter(fil_id, texte, resume, secondes=secondes)
            return {
                "etat": "reponse",
                "texte": resume,
                "modele": modele,
                "fil_id": fil_id,
                "outils_appeles": [
                    {
                        "outil": "poser_taches_groupees",
                        "args": {"groupes": len(groupes)},
                        "resultat": resume,
                    }
                ],
                "decoupe": len(groupes),
                "rappels": [],
                "connexes": [],
            }

        if len(texte) < _SEUIL_DECOUPAGE:
            taches = [texte]
        else:
            _envoyer({"geste": "socle", "texte": ""})
            _envoyer({"geste": "attacher", "fil_id": ""})
            rep_decoupage = _envoyer(
                {"geste": "dire", "modele": modele, "texte": INTENDANT.invite_decoupage(texte)}
            )
            taches = (
                INTENDANT.lire_decoupage(str(rep_decoupage.get("texte", "")), source=texte)
                if rep_decoupage.get("etat") == "reponse"
                else [texte]
            )

        attache = _envoyer({"geste": "attacher", "fil_id": fil_id})
        if attache.get("etat") == "refus":
            return attache

        reponse: dict = {}
        appels_total: list[dict] = []
        rappels_vus: dict[str, dict] = {}
        connexes_vus: dict[str, dict] = {}
        for tache_texte in taches:
            if _ANNULER_DECOUPAGE.is_set():
                break
            reponse, appels, en_attente, connexes = _tour_unique(fil_id, modele, mode, tache_texte)
            appels_total.extend(appels)
            for n in en_attente:
                rappels_vus[str(n["id"])] = n
            for n in connexes:
                connexes_vus[str(n["id"])] = n
            if reponse.get("etat") == "refus":
                break

    if not reponse:
        reponse = {
            "etat": "refus",
            "genre": "decoupage_annule",
            "detail": "stopped before the first task",
        }
    reponse["outils_appeles"] = appels_total
    reponse["fil_id"] = fil_id

    reponse["decoupe"] = len(taches)
    reponse["rappels"] = [
        {"id": n["id"], "texte": n.get("resume") or n.get("texte", "")[:200]}
        for n in rappels_vus.values()
    ]
    reponse["connexes"] = [
        {"id": n["id"], "texte": n.get("resume") or n.get("texte", "")[:200]}
        for n in connexes_vus.values()
    ]
    return reponse


def ajouter_tache(texte: str, horizon: str, parent: str, echeance: str = "") -> dict:
    """UI endpoint behavior; covered by contract tests."""
    propre = texte.strip()
    if not propre:
        return {"etat": "refus", "genre": "rien_a_poser", "detail": "an empty task does not exist"}
    note = INTENDANT.deposer(
        propre,
        genre="tache",
        horizon="" if parent else (horizon or "todo"),
        parent=parent,
        echeance=echeance if not parent and horizon == "deadline" else "",
    )
    return {"etat": "ok", "note": note, **INTENDANT.etat()}


def _descendance(note_id: str) -> list[str]:
    """UI endpoint behavior; covered by contract tests."""
    vivantes = INTENDANT.lire()
    enfants: dict[str, list[str]] = {}
    for n in vivantes:
        if n.get("parent"):
            enfants.setdefault(str(n["parent"]), []).append(str(n["id"]))
    trouves: list[str] = []
    file = list(enfants.get(note_id, []))
    while file:
        courant = file.pop()
        if courant in trouves:
            continue
        trouves.append(courant)
        file.extend(enfants.get(courant, []))
    return trouves


def intendant_geste(requete: dict) -> dict:
    """UI endpoint behavior; covered by contract tests."""
    if INTENDANT is None:
        return {"etat": "refus", "genre": "intendant_absent", "detail": INTENDANT_PANNE}
    geste = str(requete.get("geste", ""))
    try:
        return _intendant_geste(geste, requete)
    except ValueError as exc:
        return {"etat": "refus", "genre": "argument_invalide", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 - a named refusal beats a dead connection
        import traceback

        return {
            "etat": "refus",
            "genre": f"panne_{type(exc).__name__}",
            "detail": f"{exc}\n\n{traceback.format_exc()[-1500:]}",
        }


def _intendant_geste(geste: str, requete: dict) -> dict:
    """The bare routing. Its failures are caught by the caller, never here."""
    if geste == "etat":
        return {"etat": "ok", **INTENDANT.etat()}
    if geste == "tache":
        return ajouter_tache(
            str(requete.get("texte", "")),
            str(requete.get("horizon", "")),
            str(requete.get("parent", "")),
            str(requete.get("echeance", "")),
        )
    if geste == "marquer":
        nouvel = str(requete.get("nouvel_etat", ""))
        demandes = requete.get("ids")
        if isinstance(demandes, list) and demandes:
            cibles = [str(i) for i in demandes if str(i)]
        else:
            cible = str(requete.get("id", ""))
            cibles = [*_descendance(cible), cible]
        for note_id in cibles:
            INTENDANT.marquer(note_id, nouvel)
        return {"etat": "ok", "touches": cibles, **INTENDANT.etat()}
    if geste == "deplacer":
        horizon = str(requete.get("horizon", ""))
        if horizon not in INTENDANT.HORIZONS:
            return {"etat": "refus", "genre": "horizon_inconnu", "detail": repr(horizon)}
        INTENDANT.ranger(
            str(requete.get("id", "")),
            horizon=horizon,
            echeance=str(requete.get("echeance", "")),
        )
        return {"etat": "ok", **INTENDANT.etat()}
    if geste == "reordonner":
        demandes = requete.get("ids")
        if not isinstance(demandes, list) or not demandes:
            return {"etat": "refus", "genre": "argument_invalide", "detail": "missing ids"}
        INTENDANT.reordonner([str(i) for i in demandes if str(i)])
        return {"etat": "ok", **INTENDANT.etat()}
    if geste == "ranger":
        INTENDANT.ranger(
            str(requete.get("id", "")),
            genre=str(requete.get("genre", "")),
            horizon=str(requete.get("horizon", "")),
            quand=str(requete.get("quand", "")),
            resume=str(requete.get("resume", "")),
            sujets=requete.get("sujets") or None,
            echeance=str(requete.get("echeance", "")),
            description=str(requete.get("description", "")),
            parent=str(requete.get("parent", "")),
        )
        return {"etat": "ok", **INTENDANT.etat()}
    if geste == "chercher":
        return {"etat": "ok", "notes": INTENDANT.chercher(str(requete.get("q", "")))}
    if geste == "fil_neuf":
        return {"etat": "ok", "fil": INTENDANT.fil_neuf(modele=str(requete.get("modele", "")))}
    if geste == "fil":
        demande = str(requete.get("id", ""))
        fil = INTENDANT.fil_lire(demande) if demande else INTENDANT.fil_dernier()
        return {"etat": "ok", "fil": fil}
    if geste == "parler":
        return intendant_parler(
            str(requete.get("fil_id", "")),
            str(requete.get("modele", "")),
            str(requete.get("texte", "")),
            str(requete.get("mode", "libre")),
        )
    return {"etat": "refus", "genre": "geste_inconnu", "detail": repr(geste)}


class Handler(BaseHTTPRequestHandler):
    server_version = "MnemosyneUI"

    def do_GET(self) -> None:  # noqa: N802 (name imposed by BaseHTTPRequestHandler)
        route = self.path.split("?", 1)[0]

        if route == "/api/contrat":
            self._send_json(read_contract())
            return

        if route == "/api/modeles":
            self._send_json(read_basket())
            return

        if route == "/api/atelier":
            self._send_json(etat_atelier())
            return

        if route == "/api/intendant":
            self._send_json(intendant_geste({"geste": "etat"}))
            return

        if route == "/api/conseiller":
            self._send_json(conseiller_geste({"geste": "etat"}))
            return

        name = "index.html" if route == "/" else route.lstrip("/")
        target = (WEB / name).resolve()

        if not target.is_file() or WEB not in target.parents:
            self._send_bytes(404, "text/plain; charset=utf-8", b"not found")
            return

        self._send_bytes(
            200,
            MIME.get(target.suffix, "application/octet-stream"),
            target.read_bytes(),
        )

    def do_POST(self) -> None:  # noqa: N802 (name imposed by BaseHTTPRequestHandler)
        route = self.path.split("?", 1)[0]

        if route == "/api/arreter":
            self._send_json(arreter_atelier())
            return

        if route not in ("/api/dire", "/api/intendant", "/api/conseiller"):
            self._send_bytes(404, "text/plain; charset=utf-8", b"not found")
            return
        try:
            taille = int(self.headers.get("Content-Length") or 0)
            requete = json.loads(self.rfile.read(taille) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json({"etat": "refus", "genre": "requete_illisible", "detail": str(exc)})
            return

        if route == "/api/intendant":
            self._send_json(intendant_geste(requete))
            return

        if route == "/api/conseiller":
            self._send_json(conseiller_geste(requete))
            return

        self._send_json(
            parler(
                {
                    "geste": "dire",
                    "modele": str(requete.get("modele", "")),
                    "texte": str(requete.get("texte", "")),
                }
            )
        )

    def _send_json(self, payload: dict) -> None:
        self._send_bytes(
            200, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8")
        )

    def _send_bytes(self, status: int, mime: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))

        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        """Stay quiet: the terminal shows the address, not a request log."""


def pick_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit(f"No free port between {start} and {start + 19}.")


def main() -> None:
    if not WEB.is_dir():
        raise SystemExit(f"The {WEB} folder is missing: the app is incomplete.")

    port = pick_port(DEFAULT_PORT)
    url = f"http://127.0.0.1:{port}/"

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)

    print("\n  Mnemosyne - dashboard")
    print(f"  {url}")
    print("\n  Ctrl-C to stop.\n")

    if "--sans-navigateur" not in sys.argv:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("  Stopped.\n")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
