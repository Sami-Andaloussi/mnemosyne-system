"""atelier - a LONG-LIVED local worker, so an interface can hold a CONVERSATION.

``make local-run`` dispatches ONE bounded task and exits. That shape is right for a frontier model
delegating a unit of work; it is wrong for a chat, because it pays the cold start on every turn -
12.9 s measured end to end (document parsing 3.6 s, embeddings 1.5 s, reranker 0.7 s, a local 7B
1.7 s, assembly 2.8 s), of which the answer itself is a fraction. Ten turns would cost two minutes
of loading and nothing else.

So this process stays up and keeps the runtime warm. It reads one JSON object per line on stdin and
answers one JSON object per line on stdout::

    {"geste": "etat"}                                   -> {"etat": "pret"|"vide", "modele": ...}
    {"geste": "dire", "modele": "<id>", "texte": "..."} -> {"etat": "reponse", "texte": ...}
    {"geste": "attacher", "fil_id": "<id>", "magasin": "intendant"|"conseiller"}
                                                        -> {"etat": "attache", "tours": n}
    {"geste": "socle", "texte": "..."}                  -> {"etat": "socle_pose", "caracteres": n}
    {"geste": "fil_plus_loin", "fin": n, "combien": n}  -> {"etat": "trouve"|"vide", "fin": n}

It decodes THROUGH THE GUARD, like every other surface (invariant 5). The answer comes from
:meth:`~mnemosyne.api.core_api.CoreApi.run_local`, which mints a single-use ``MODEL_CALL`` grant,
redeems it, and labels the output - exactly the path ``make local-run`` takes. Calling the model
backend directly would have been fifty lines and about ten seconds shorter, and it would have been
a back door inside ``system/lib/mnemosyne/``, which this repo does not have.

WARNING: STDOUT IS THE PROTOCOL, AND THE RUNTIME PRINTS ON IT. ``real_runtime()`` narrates its five
startup steps to stdout by design (a start that says nothing is how thirty silent minutes happened
once). Those lines would land in the middle of the JSON stream. The real stdout is therefore
captured at import and stdout is re-pointed at stderr for everyone else: the caller reads a clean
protocol, and the narration is still there, on the channel where a caller drains logs.

One model at a time: naming a different one rebuilds the runtime, and says how long it took.

A THREAD CAN SURVIVE THE PROCESS. This worker used to persist nothing - no history, no transcript -
so shutting it down lost the conversation. ``attacher`` binds the worker to a thread held by
:mod:`~mnemosyne.runtime.intendant` (or :mod:`~mnemosyne.runtime.conseiller`, via ``magasin``), and
re-attaching rebuilds the thread the model sees. Attach nothing and the old behaviour is unchanged:
a throw-away chat that writes no file.

``dire()`` itself no longer writes to disk. It used to, on EVERY call, which silently corrupted the
history the moment a turn involved a tool call: one real exchange became several fake ones (the
internal "here is the tool result, now confirm" follow-up persisted under the operator's own role,
the raw tool-call JSON persisted as the agent's reply). Measured in real use: one message, one tool
call, FOUR thread entries instead of two. Only the CALLER knows, once its tool loop is done, which
exchange is the real one - so the caller persists it, exactly once, with the operator's actual
message and the model's actual final answer. ``self._fil`` (what the model itself sees) still
accumulates every turn as before; only the disk stopped seeing the internal ones.

The decode path needs the local model backend, the weights and the vector store, so it is NOT run
in CI - but ``attacher``, ``poser_socle`` and the thread trimming are pure and ARE covered by
``tests/platform/test_atelier_fil``.
"""

from __future__ import annotations

import json
import os
import sys
import time

_CANAL = sys.stdout
sys.stdout = sys.stderr

_BULLE = "work"

# Reserves response capacity for protocol overhead around a model-generated answer.
_PART_DU_PLAFOND = 0.8

_FIL_ENTETE = "Here is the start of our conversation. Reply to the LAST message.\n"


def fenetre_declaree(model_id: str) -> tuple[int, str]:
    """Implementation behavior is covered by tests."""
    import json

    from ..production.model_catalog import hub_root

    dossier = hub_root() / ("models--" + model_id.replace("/", "--")) / "snapshots"
    if not dossier.is_dir():
        return 0, ""
    for snapshot in sorted(dossier.glob("*")):
        fichier = snapshot / "config.json"
        if not fichier.is_file():
            continue
        try:
            config = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0, ""
        for chemin, source in (
            (config, "max_position_embeddings"),
            (config.get("text_config") or {}, "text_config.max_position_embeddings"),
        ):
            valeur = chemin.get("max_position_embeddings")
            if isinstance(valeur, int) and valeur > 0:
                return valeur, source
    return 0, ""


class Atelier:  # pragma: no cover - needs the local model backend, the weights and the vector store
    """Holds ONE warm runtime and answers turns against it.

    The runtime is built on the FIRST turn, never at start-up: launching the worker must stay free,
    so an interface can spawn it eagerly and only pay when the operator actually says something."""

    def __init__(self) -> None:
        self._modele: str = ""
        self._api: object | None = None
        self._charge_s: float = 0.0
        self._fil: list[tuple[str, str]] = []
        self._fil_id: str = ""
        self._magasin: str = "intendant"
        self._socle: str = ""
        self._tokenizer: object | None = None
        self._fenetre: int = 0
        self._fenetre_source: str = ""
        self._derniers_jetons: int = 0
        self._plafond: int = 0

    def etat(self) -> dict:
        return {
            "etat": "pret" if self._api is not None else "vide",
            "modele": self._modele,
            "charge_secondes": round(self._charge_s, 2),
            "tours": len(self._fil),
            "fenetre": self._fenetre,
            "fenetre_source": self._fenetre_source,
            "jetons": self._derniers_jetons,
            "plafond_caracteres": self._plafond,
            "fil_id": self._fil_id,
            "socle": bool(self._socle),
        }

    def attacher(self, fil_id: str, magasin: str = "intendant") -> dict:
        """Attach a PERSISTED thread - the gesture that makes a conversation survive a shutdown.

        Reads the thread from disk and rebuilds the in-memory list from it, so the model is handed
        everything that was said before, including turns produced by a previous process (or a
        previous model). From here on, each turn is written back as it happens.

        Passing ``""`` detaches: the worker goes back to a throw-away chat that writes nothing.

        ``magasin`` - which bulle's thread store ``fil_id`` lives in (``"intendant"`` or
        ``"conseiller"``, see conseiller.py). Defaults to the Intendant's, unchanged from before this
        parameter existed: a caller that never names it gets EXACTLY the old behaviour, one thread
        store, no regression."""
        from . import conseiller, intendant

        module = {"intendant": intendant, "conseiller": conseiller}.get(magasin, intendant)

        if not fil_id:
            self._fil_id = ""
            self._fil = []
            return {"etat": "detache", "fil_id": "", "tours": 0}
        fil = module.fil_lire(fil_id)
        if fil is None:
            return {"etat": "refus", "genre": "fil_introuvable", "detail": fil_id}
        # Rebuilt PAIRWISE from the stored roles, never from position alone: a thread whose last
        # turn was interrupted mid-answer has an odd number of entries, and pairing by index would
        # silently shift every reply onto the wrong question from there on.
        #
        # agent name: the Conseiller's turns are written with role "conseiller", and requiring
        # "intendant" here would silently pair NOTHING on a re-attached Conseiller thread.
        self._fil = []
        attente: str | None = None
        for tour in fil.get("tours", []):
            role, texte = tour.get("role"), str(tour.get("texte", ""))
            if role == "operator":
                attente = texte
            elif attente is not None:
                self._fil.append((attente, texte))
                attente = None
        self._fil_id = fil_id
        self._magasin = magasin
        return {
            "etat": "attache",
            "fil_id": fil_id,
            "titre": fil.get("titre", ""),
            "tours": len(self._fil),
            "modele_du_fil": fil.get("modele", ""),
        }

    def poser_socle(self, texte: str) -> dict:
        """Set the fixed preamble re-injected at every turn - an agent's identity and its rules.

        It lives here rather than being prepended by the caller for one measured reason: the thread
        is trimmed against the runner's ceiling, and a preamble the trimmer cannot see would be the
        first thing to push a prompt over it. Set here, it is counted."""
        self._socle = texte
        return {"etat": "socle_pose", "caracteres": len(texte)}

    def _compter(self, texte: str) -> int:
        """Implementation behavior is covered by tests."""
        if self._tokenizer is None:
            return 0
        try:
            return len(self._tokenizer.encode(texte))  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - counting must never break a turn
            return 0

    def _invite(self, texte: str) -> tuple[str, int]:
        """The last message, preceded by as much thread as the runner's ceiling allows.

        Walks the thread BACKWARDS from the most recent and stops when the next exchange would not
        fit. Backwards, not forwards, because the recent turns are the ones that make the last
        message intelligible: if something must be dropped, it has to be the oldest.

        Returns the prompt AND how many exchanges actually travelled - the screen must be able to
        say what happened rather than repeat a constant that may not describe this turn.

        WARNING: The preamble (socle) is ALWAYS present, even on the very first turn and even when nothing
        of the thread fits. An agent that loses its identity exactly when its thread gets long would
        change character mid-conversation, and that drift would be invisible from the screen."""
        entete = self._socle or _FIL_ENTETE
        queue = f"\nOperator : {texte}\nToi :"
        if not self._fil:
            return (entete + queue if self._socle else texte), 0
        budget = int(self._plafond * _PART_DU_PLAFOND)
        reste = budget - len(entete) - len(queue)
        morceaux: list[str] = []
        gardes = 0
        for demande, reponse in reversed(self._fil):
            bloc = f"\nOperator : {demande}\nToi : {reponse}"
            if len(bloc) > reste:
                break
            reste -= len(bloc)
            morceaux.append(bloc)
            gardes += 1
        if not morceaux:
            # Even the last exchange does not fit: go out with no thread history rather than drop
            # the preamble - THAT stays, since it is what keeps the agent itself.
            return (entete + queue if self._socle else texte), 0
        return "".join([entete, *reversed(morceaux), queue]), gardes

    def plus_loin(self, fin: int, combien: int = 4) -> dict:
        """A slice of the attached thread OLDER than what a turn already sent - on demand.

        ``_invite`` already decides, on every turn, how many recent exchanges fit the window
        (``fil_garde``); anything older is simply left out. This lets a caller (the tool loop, one
        layer up) walk further BACK from there, a few exchanges at a time, instead of paying for the
        whole thread on every turn regardless of whether it is needed.

        ``fin`` is an ABSOLUTE index into ``self._fil`` (never a count from "now"): the list only
        ever grows by appending, so an index computed once - from ``fil_total - fil_garde`` right
        after a turn - still points at the same historical exchange even after several more turns
        have been appended in between (a tool-result round-trip is itself a new exchange). A
        relative "how many already shown" count would drift with every one of those appends; this
        does not, which is why the caller is handed the NEW boundary (``fin`` in the response) to
        pass back for the next call rather than being asked to track it itself."""
        fin = max(0, min(fin, len(self._fil)))
        debut = max(0, fin - combien)
        if fin <= 0:
            return {"etat": "vide", "fin": 0, "total": len(self._fil)}
        tranche = self._fil[debut:fin]
        return {
            "etat": "trouve",
            "texte": "\n\n".join(f"operator : {q}\nToi : {r}" for q, r in tranche),
            # The NEXT boundary to pass, not a count to add up yourself: the same
            # discipline as `fil_garde`/`fil_total` a bit further up.
            "fin": debut,
            "total": len(self._fil),
        }

    def _charger(self, modele: str) -> dict | None:
        """Build (or rebuild) the runtime for ``modele``. Returns a refusal dict, or None on success."""
        if self._api is not None and self._modele == modele:
            return None

        from ..api import CoreApi
        from ..production.model_catalog import ENV_TEXT_MODEL, ModelRefused
        from .bootstrap import real_runtime

        # The id travels by environment because that is where `resolve_model_id` reads it - the same
        # single door `make local-run MODELE=...` goes through. Passing it another way would create a
        # second path to the same decision, and the two would disagree the day one of them changes.
        #
        # WARNING: The variable is IMPORTED, not typed. My first version wrote `MODELE` - the name on the
        # and the refusal named it itself; recopying that name here would have been a second copy
        # of the same string, free to drift. `ENV_TEXT_MODEL` is the one source.
        os.environ[ENV_TEXT_MODEL] = modele
        # Drop the previous runtime BEFORE building the next: 32 Go of RAM, one big model at a time
        # (D95). Holding both across a switch is how a 19 Go model meets a 16 Go one.
        self._api = None
        self._modele = ""
        depart = time.monotonic()
        try:
            runtime = real_runtime(max_tokens=4096)
            self._api = CoreApi(runtime)
            self._plafond = runtime.runner.max_prompt_chars
        except ModelRefused as refus:
            return {
                "etat": "refus",
                "genre": "modele_refuse",
                "detail": str(refus),
            }
        except Exception as erreur:  # noqa: BLE001 - the worker must NAME a failure, never die silently
            return {
                "etat": "refus",
                "genre": type(erreur).__name__,
                "detail": f"{erreur}",
            }
        self._modele = modele
        self._charge_s = time.monotonic() - depart
        self._fenetre, self._fenetre_source = fenetre_declaree(modele)
        self._derniers_jetons = 0
        try:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(modele)
        except Exception:  # noqa: BLE001 - no counter beats a made-up counter
            self._tokenizer = None
        self._fil = []
        if self._fil_id:
            self.attacher(self._fil_id, self._magasin)
        return None

    def dire(self, modele: str, texte: str) -> dict:
        if not modele:
            return {"etat": "refus", "genre": "modele_non_nomme", "detail": "No model named."}
        if not texte.strip():
            return {"etat": "refus", "genre": "texte_vide", "detail": "Nothing to say."}

        etait_charge = self._api is not None and self._modele == modele
        refus = self._charger(modele)
        if refus is not None:
            return refus

        from ..ports import Bubble, Sensitivity

        invite, fil_garde = self._invite(texte)
        depart = time.monotonic()
        try:
            # `within=sensible` by default, like `make local-run`: decoding is LOCAL either way
            # (invariant 1), the label only frames the output.
            sortie = self._api.run_local(  # type: ignore[union-attr]
                invite, subject=Bubble(_BULLE), within=Sensitivity.SENSIBLE
            )
        except Exception as erreur:  # noqa: BLE001 - a failed turn must not kill the warm runtime
            return {"etat": "refus", "genre": type(erreur).__name__, "detail": f"{erreur}"}

        from . import intendant

        sortie = intendant.nettoyer_reponse(str(sortie))
        self._fil.append((texte, str(sortie)))
        # ...the LLM's message. Computed once, reused further down in the returned dict.
        secondes = round(time.monotonic() - depart, 2)
        # This method used to WRITE HERE, on EVERY call -- and a conversation turn with a tool
        # call chains SEVERAL `dire()` calls (the question, then an internal "Result of X, confirm",
        # potentially several). Each one got written as a SEPARATE exchange, with the agent's role
        # sometimes carrying the tool call's raw JSON instead of its actual reply.
        # ONE tool call produced FOUR turns in the thread instead of two -- its
        # real history already contained messages it had never actually written.
        #
        # `dire()` does NOT know, at the moment it answers, whether THIS text is the final reply or an
        # intermediate link in a tool loop -- only the caller (`_tour_unique` on the
        # serve.py side) knows that, once the loop has ended. Persistence is therefore THAT CALLER's call:
        # one write here, never one per call. `self._fil` (the model's memory) continues to accumulate every
        # exchange normally; only DISK no longer sees anything but what truly belongs there.
        # What ACTUALLY occupied the window on this turn: the prompt sent (thread included) plus the
        # reply produced. Counted on the strings that were actually passed, never on the last message
        # alone - it is the whole thread that fills the window, and that is precisely what a gauge
        # should show growing.
        jetons_invite = self._compter(invite)
        jetons_reponse = self._compter(str(sortie))
        self._derniers_jetons = jetons_invite + jetons_reponse
        return {
            "jetons_invite": jetons_invite,
            "jetons_reponse": jetons_reponse,
            "jetons": self._derniers_jetons,
            "fenetre": self._fenetre,
            "fenetre_source": self._fenetre_source,
            # What ACTUALLY travelled with this turn, and what it was bounded against. The screen can
            # thus say what happened, instead of repeating a constant.
            "fil_garde": fil_garde,
            "fil_total": len(self._fil) - 1,
            # The ATTACHED thread's identifier, not a write confirmation -- persistence itself is now
            # decided by the caller (see above), which sets its OWN `fil_ecrit` on the response it
            # returns, once it knows whether this was the right one.
            "fil_id": self._fil_id,
            "plafond_caracteres": self._plafond,
            "etat": "reponse",
            "modele": modele,
            "texte": str(sortie),
            "secondes": secondes,
            "chargement_secondes": 0.0 if etait_charge else round(self._charge_s, 2),
        }


def repondre(atelier: Atelier, ligne: str) -> dict:  # pragma: no cover - protocol shell
    """One request line -> one response dict. Pure enough to be read at a glance."""
    try:
        requete = json.loads(ligne)
    except json.JSONDecodeError as exc:
        return {"etat": "refus", "genre": "requete_illisible", "detail": str(exc)}
    geste = requete.get("geste")
    if geste == "etat":
        return atelier.etat()
    if geste == "dire":
        return atelier.dire(str(requete.get("modele", "")), str(requete.get("texte", "")))
    if geste == "attacher":
        return atelier.attacher(
            str(requete.get("fil_id", "")), str(requete.get("magasin", "") or "intendant")
        )
    if geste == "socle":
        return atelier.poser_socle(str(requete.get("texte", "")))
    if geste == "fil_plus_loin":
        return atelier.plus_loin(int(requete.get("fin", 0)), int(requete.get("combien", 4)))
    return {"etat": "refus", "genre": "geste_inconnu", "detail": repr(geste)}


def main() -> int:  # pragma: no cover - CLI side effect
    atelier = Atelier()
    for ligne in sys.stdin:
        if not ligne.strip():
            continue
        _CANAL.write(json.dumps(repondre(atelier, ligne), ensure_ascii=False) + "\n")
        _CANAL.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
