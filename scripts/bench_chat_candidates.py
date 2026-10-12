#!/usr/bin/env python3
"""Bench chat candidates for Mnemosyne System."""

from __future__ import annotations

import gc
import json
import re
import sys
import time
from pathlib import Path

# Candidates cover distinct model families and sizes. The baseline makes benchmark comparisons
# reproducible instead of treating any apparently correct result as equivalent.
CANDIDATS = [
    "mlx-community/Qwen3.6-35B-A3B-4bit",
    "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
    "mlx-community/Mistral-Small-3.2-24B-Instruct-2506-4bit",
    "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
    "mlx-community/Qwen2.5-7B-Instruct-4bit",  # low baseline - the current default
]

SYSTEME = """You are a project-filing assistant. You receive unstructured requests.
Your only job: UNDERSTAND and FILE. You do not discuss, you file.

Existing projects, and there are no others:
- "system"  : the system itself (tools, plans, and documentation)
- "research" : research work
- "analysis" : quantitative analysis
- "personal" : general tasks

Reply ONLY with a JSON object, no text around it, in this form:
{"action": "...", "items": [{"texte": "...", "projet": "..."}]}

"action" is exactly one of: "noter" | "rechercher" | "je_ne_sais_pas"
- "noter"          : the message contains one or more tasks to file
- "rechercher"     : the message asks for a search in a document base
- "je_ne_sais_pas" : the message asks for a fact you cannot know. Do NOT invent ANYTHING.

A "texte" repeats the words provided as-is. Do not rephrase to sound nice."""

# Each task: the operator's message + what CORRECT filing must produce.
TACHES = [
    {
        "nom": "pense-bete-multiple",
        "message": (
            "I need to restart the image processing, check the research plan, "
            "and order supplies"
        ),
        "attendu": {"action": "noter", "n_items": 3, "projets": ["system", "research", "personal"]},
        "mesure": "does it separate THREE distinct things and file them in the three right places",
    },
    {
        "nom": "remarque-decousue",
        "message": (
            "as part of the research project, or in system, we need to make sure "
            "that even inside projects things don't end up living in several "
            "different places, and that we can verify them"
        ),
        "attendu": {"action": "noter", "n_items": 1, "projets": ["system", "research"]},
        "mesure": "does a vague thought become ONE note (not five invented ones), filed sanely",
    },
    {
        "nom": "recherche-corpus",
        "message": "find the notes about a risk criterion in the document base",
        "attendu": {"action": "rechercher"},
        "mesure": "does it distinguish a SEARCH from a note to file",
    },
    {
        "nom": "refus-d-inventer",
        "message": "what is the status of project Q7, is it finished?",
        "attendu": {"action": "je_ne_sais_pas"},
        "mesure": "does it ADMIT it, or fabricate a plausible status (the worst failure)",
    },
]


_RAISONNEMENT = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)


def extraire_json(brut: str) -> dict | None:
    """Extracts the first JSON object from the output. Without an imposed grammar, a model
    rambles around it - the bench measures the filing, not the punctuality of the braces, so
    it is lenient on the wrapping and strict on the content."""
    # A reasoning model (Qwen3.x) emits its think block before the answer: strip it, otherwise
    # Deployment-specific measurement omitted; the behavior is covered by tests.
    brut = _RAISONNEMENT.sub("", brut)
    # An UNCLOSED think block (token budget exhausted): resume after the last opening tag.
    ouvre = max(brut.lower().rfind("<think>"), brut.lower().rfind("<thinking>"))
    if ouvre >= 0:
        brut = brut[ouvre:]
    debut = brut.find("{")
    if debut < 0:
        return None
    profondeur = 0
    for i in range(debut, len(brut)):
        if brut[i] == "{":
            profondeur += 1
        elif brut[i] == "}":
            profondeur -= 1
            if profondeur == 0:
                try:
                    return json.loads(brut[debut : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def juger(rendu: dict | None, attendu: dict) -> dict:
    """Mechanical verdict. Each criterion is a checkable boolean, never a judgment call."""
    if rendu is None:
        return {
            "json_lisible": False,
            "action_juste": False,
            "compte_juste": None,
            "projets_justes": None,
        }

    verdict = {
        "json_lisible": True,
        "action_juste": rendu.get("action") == attendu["action"],
        "compte_juste": None,
        "projets_justes": None,
    }
    if "n_items" in attendu:
        items = rendu.get("items") or []
        verdict["compte_juste"] = len(items) == attendu["n_items"]
        vus = {str(i.get("projet", "")).lower().strip() for i in items if isinstance(i, dict)}
        # Lenient: we only require that the named projects be WITHIN the expected set,
        # not that they cover it - inventing a project is the fault, not omitting one.
        verdict["projets_justes"] = bool(vus) and vus <= set(attendu["projets"])
    return verdict


def main() -> None:
    sortie = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/mesures/banc-chat-candidats.json")
    from mlx_lm import generate, load  # late import: the bench must be able to explain itself without MLX

    resultats = []
    for rang, model_id in enumerate(CANDIDATS, 1):
        print(f"\n[{rang}/{len(CANDIDATS)}] {model_id}", flush=True)
        t0 = time.time()
        try:
            model, tokenizer = load(model_id)
        except Exception as exc:  # a missing weight file must not take down the whole bench
            print(f"    LOAD FAILED : {exc}", flush=True)
            resultats.append({"modele": model_id, "erreur": str(exc)[:300]})
            continue
        charge_s = round(time.time() - t0, 1)
        print(f"    loaded in {charge_s} s", flush=True)

        essais = []
        for tache in TACHES:
            invite = tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": SYSTEME},
                    {"role": "user", "content": tache["message"]},
                ],
                add_generation_prompt=True,
                tokenize=False,
            )
            t1 = time.time()
            brut = generate(model, tokenizer, prompt=invite, max_tokens=1200, verbose=False)
            duree = round(time.time() - t1, 1)
            verdict = juger(extraire_json(brut), tache["attendu"])
            reussi = verdict["action_juste"] and verdict.get("compte_juste") is not False
            print(
                f"    {tache['nom']:22s} {duree:6.1f}s  {'OK ' if reussi else 'FAIL'}  {verdict}",
                flush=True,
            )
            essais.append(
                {
                    "tache": tache["nom"],
                    "mesure": tache["mesure"],
                    "secondes": duree,
                    "verdict": verdict,
                    "brut": brut[:900],
                }
            )

        resultats.append({"modele": model_id, "chargement_s": charge_s, "essais": essais})

        # Deployment-specific measurement omitted; the behavior is covered by tests.
        # Deployment-specific measurement omitted; the behavior is covered by tests.
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(
            json.dumps({"taches": TACHES, "resultats": resultats}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

        # Release each model before evaluating the next candidate.
        del model, tokenizer
        gc.collect()

    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(
        json.dumps({"taches": TACHES, "resultats": resultats}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"\nReport written: {sortie}", flush=True)


if __name__ == "__main__":
    main()
