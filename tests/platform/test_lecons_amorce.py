"""THE PRIMER GETS JUDGED (project 0  -  A1, 2nd half) - the hook that SEARCHES in the agent's place.

WHY THIS FILE EXISTS. `production/lecons.py` made the lessons PULLABLE; nobody pulls them.
The repo has already paid for this exact class of bug: memory's git repo (D173) was used only
once, the day it was born - *a net that is never pulled looks exactly like a net.* These witnesses
judge the trigger, and first what it must NEVER do.

THE FIRST WITNESS IS THE INNOCENT: without it, a primer that stayed silent ALWAYS would
pass every witness for silence that follows - *a gate already red discriminates against no one*.

THE CARDINAL WITNESS IS `test_le_dossier_de_memoire_n_est_JAMAIS_ecrit`. It freezes the
fingerprints AND the set of names: a count alone would let one file in and another out without
turning red, and that is literally how a compaction pass destroyed a link in this folder.

WARNING: THE FIXTURE CARRIES 20 FICHES, NOT 3, AND THAT IS A MEASUREMENT CONDITION. The per-session
ceiling is 12: on a population of 3 fiches it would be UNREACHABLE, and the witness defending it
would pass green without ever arming it. *A degenerate population tests nothing.*
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mnemosyne.production.lecons import IndexDesLecons
from mnemosyne.runtime.lecons_amorce import (
    MIN_TERMES,
    PAR_TIR,
    PLAFOND_SESSION,
    Amorce,
    choisir,
    cle_de_session,
    rendre,
)

_RACINE = Path(__file__).resolve().parents[2]

#: Each fiche carries ONE unique subject (therefore rare, therefore discriminating) + a common word.
#:
#: NOTE: the subject words below and the filler vocabulary in `_prompt()` / `_memoire()` are
#: cross-referenced by literal string across roughly a dozen tests in this file. The FTS5 index
#: they are tested against uses a language-agnostic tokenizer (`unicode61 remove_diacritics 2`,
#: confirmed in system/lib/mnemosyne/production/lecons.py), so translating them would not change
#: the mechanism under test - but given the density of interdependent call sites, they are kept
#: in French (as in test_lecons.py's analogous fixture content) rather than risk an incomplete,
#: partially-translated set.
_SUJETS = [
    "hirondelle",
    "cerfvolant",
    "obsidienne",
    "marguerite",
    "tesselle",
    "bergamote",
    "quartzite",
    "nenuphar",
    "sarabande",
    "vermillon",
    "kaleidoscope",
    "amphore",
    "brigantin",
    "clepsydre",
    "dolomite",
    "estuaire",
    "faisceau",
    "girouette",
    "harmonique",
    "isthme",
]


def _memoire(tmp_path: Path) -> Path:
    dossier = tmp_path / "memory"
    dossier.mkdir(parents=True, exist_ok=True)
    for i, sujet in enumerate(_SUJETS):
        (dossier / f"lecon-{i:02d}.md").write_text(
            f"---\nname: lecon-{i:02d}\ndescription: La lecon numero {i} porte sur {sujet}\n"
            f"metadata:\n  type: feedback\n---\n\nGouvernance et mesure : {sujet} "
            f"comes back every time {sujet} is discussed in the repository.\n",
            encoding="utf-8",
        )
    # NOTE: `MEMORY.md`/`MEMORY-2.md` are not decorative test
    # strings: they must match `INDEX_FILENAMES` in the (out-of-scope) production module
    # system/lib/mnemosyne/production/lecons.py. Renaming them here alone would silently break
    # this test against the real, unrenamed constant, so they are left untouched (same pairing
    # verified in test_lecons.py, and checked mirror-wide, not only within this lot).
    (dossier / "MEMORY.md").write_text("# Memory Index\n- [L0](lecon-00.md)\n", encoding="utf-8")
    (dossier / "MEMORY-2.md").write_text("- [L1](lecon-01.md)\n", encoding="utf-8")
    return dossier


@pytest.fixture()
def index(tmp_path: Path) -> IndexDesLecons:
    idx = IndexDesLecons(_memoire(tmp_path), db_path=tmp_path / "lecons.db")
    idx.refresh()
    yield idx
    idx.close()


def _prompt(*sujets: str) -> str:
    """A BACKGROUND prompt: the targeted subjects + enough full words to clear MIN_TERMES.

    NOTE: the filler words below are kept in French, matching the fiche body text written by
    `_memoire()` above (see its note) - the two must share vocabulary for the search-matching
    behaviour under test to hold.
    """
    return "analyse mesure gouvernance depot plafond " + " ".join(sujets)


def test_l_INNOCENT_un_prompt_de_fond_recoit_des_candidates(index: IndexDesLecons) -> None:
    """The passing path must pass, or no witness for silence below measures anything."""
    trouve = choisir(index, _prompt("hirondelle"), deja=set())
    assert trouve, "a background prompt naming a subject from the corpus must return candidates"
    assert trouve[0].nom == "lecon-00.md", [t.nom for t in trouve]


def test_un_prompt_COURT_est_SILENCIEUX(index: IndexDesLecons) -> None:
    """Short prompts are rejected even when they contain a term represented in the fixture."""
    for court in ("hirondelle", "obsidienne cerfvolant", "gouvernance mesure", "quartzite depot"):
        assert choisir(index, court, deja=set()) == [], court


def test_un_sujet_DEJA_SERVI_ne_creuse_pas_plus_bas(index: IndexDesLecons) -> None:
    """Asking the SAME question again yields silence, never the 4th then the 5th match.

    Continuing past already-seen top matches would spend the bounded budget on progressively weaker
    candidates.
    """
    p = _prompt("obsidienne", "marguerite", "tesselle")
    deja = {t.nom for t in choisir(index, p, deja=set())}
    assert deja, "the innocent case: the first draw must return something"
    assert choisir(index, p, deja=deja) == []


def test_une_fiche_n_est_JAMAIS_offerte_deux_fois(index: IndexDesLecons) -> None:
    deja: set[str] = set()
    vus: list[str] = []
    for sujet in _SUJETS[:4]:
        for t in choisir(index, _prompt(sujet), deja):
            vus.append(t.nom)
            deja.add(t.nom)
    assert len(vus) == len(set(vus)), f"duplicate injected: {vus}"


def test_les_TROIS_BORNES_sont_GELEES_a_leur_valeur_mesuree() -> None:
    """THE VALUES ARE FROZEN, AND THE FREEZE COMES FROM A MEASUREMENT. The behaviour
    witnesses used to read the constants to build their own expectation - which made them BLIND to a
    change in those very constants: a harness moved `MIN_TERMES` from 6 to 2 and `PAR_TIR` from 3 to
    8, and **not one witness turned red**. A witness that derives its expectation from the thing
    under judgment judges nothing.

    These three numbers are not comfort settings: they come out of replaying 1,538 real prompts.
    Changing them is legitimate - but then they must be RE-MEASURED, and this freeze is what forces
    that gesture instead of letting the change slip through in silence.
    """
    assert (MIN_TERMES, PAR_TIR, PLAFOND_SESSION) == (6, 3, 12)


def test_le_plafond_tient_meme_a_une_frontiere_NON_MULTIPLE(index: IndexDesLecons) -> None:
    """WARNING: THE BOUNDARY WAS NEVER ARMED. The cap witness only ever met remainders that were
    multiples of 3 (3+3+3+3 = 12 exactly), so it never OVERLAPPED the boundary: the harness removed
    the `neufs[:budget]` slice and **the witness stayed green**. Here 1 slot remains for
    3 candidates."""
    deja = {f"faux-{i}.md" for i in range(PLAFOND_SESSION - 1)}
    assert len(choisir(index, _prompt(*_SUJETS[:5]), deja)) == 1


def test_un_budget_DEPASSE_rend_le_silence_jamais_une_coupe_negative(index: IndexDesLecons) -> None:
    """If `deja` exceeds the cap - which happens as soon as the cap is LOWERED while sessions are
    already under way - the budget goes negative. Without a guard, `neufs[:-2]` does not return
    nothing: it returns the first elements. This is the `budget <= 0` guard the harness found unarmed."""
    deja = {f"faux-{i}.md" for i in range(PLAFOND_SESSION + 2)}
    assert choisir(index, _prompt(*_SUJETS[:5]), deja) == []


def test_le_PLAFOND_par_session_borne_le_total(index: IndexDesLecons) -> None:
    """The session cap bounds accumulated suggestions even when many prompts match."""
    deja: set[str] = set()
    for sujet in _SUJETS:  # 20 distinct subjects: enough to exceed 12 if nothing bounds it
        for t in choisir(index, _prompt(sujet), deja):
            deja.add(t.nom)
    assert len(deja) == PLAFOND_SESSION, (
        f"{len(deja)} fiches injected for a cap of {PLAFOND_SESSION}"
    )
    assert choisir(index, _prompt("isthme"), deja) == [], "saturated = silent, never an empty draw"


def test_un_tir_ne_depasse_JAMAIS_par_tir(index: IndexDesLecons) -> None:
    assert len(choisir(index, _prompt(*_SUJETS[:8]), deja=set())) <= PAR_TIR


def test_deux_sessions_ont_des_budgets_INDEPENDANTS(tmp_path: Path) -> None:
    """The cap bounds ONE session. If it leaked from one session to the next, the second would be
    born mute - and an agent would conclude "memory carries nothing" over a full corpus."""
    amorce = Amorce(db_path=tmp_path / "amorce.db")
    amorce.note("session-A.jsonl", ["lecon-00.md", "lecon-01.md"])
    assert amorce.deja_vues("session-A.jsonl") == {"lecon-00.md", "lecon-01.md"}
    assert amorce.deja_vues("session-B.jsonl") == set()
    amorce.close()


def test_la_meme_fiche_deux_fois_notee_ne_double_pas(tmp_path: Path) -> None:
    amorce = Amorce(db_path=tmp_path / "amorce.db")
    amorce.note("s.jsonl", ["lecon-00.md"])
    amorce.note("s.jsonl", ["lecon-00.md"])
    assert amorce.deja_vues("s.jsonl") == {"lecon-00.md"}
    amorce.close()


def test_le_rituel_de_DEBUT_n_apparait_qu_au_PREMIER_tir(index: IndexDesLecons) -> None:
    """The ritual text is CONSTANT: repeating it on every draw would be exactly the redundancy this
    project fights. It closes a previously reported regression and must not become noise again."""
    trouve = choisir(index, _prompt("hirondelle"), deja=set())
    premier = rendre(trouve, compte=20, dossier=Path("/m"), premiere=True)
    suivant = rendre(trouve, compte=20, dossier=Path("/m"), premiere=False)
    assert "START ritual" in premier
    assert "START ritual" not in suivant
    assert "make plans" in premier, "the ritual must NAME the state command, not just allude to it"


def test_le_rendu_ne_se_donne_JAMAIS_pour_un_verdict(index: IndexDesLecons) -> None:
    """Lexical retrieval returns candidates rather than claiming relevance."""
    texte = rendre(
        choisir(index, _prompt("hirondelle"), deja=set()),
        compte=20,
        dossier=Path("/m"),
        premiere=True,
    )
    assert "candidate" in texte.lower()
    assert "NOT a verdict of relevance" in texte


def test_cle_de_session_prefere_le_transcript(tmp_path: Path) -> None:
    """`transcript_path` first: it is the field `stop.sh` already relies on, so the only one proven
    present on this host. A missing key yields a CONSTANT, never a random value - a fresh key on
    every prompt would silently disarm both the ceiling AND the no-repeat rule."""
    assert cle_de_session({"transcript_path": "/x/y/abc.jsonl", "session_id": "zzz"}) == "abc.jsonl"
    assert cle_de_session({"session_id": "zzz"}) == "zzz"
    assert cle_de_session({}) == "session-inconnue"
    assert cle_de_session({}) == cle_de_session({}), "stable, never random"


def test_le_dossier_de_memoire_n_est_JAMAIS_ecrit(tmp_path: Path) -> None:
    """THE CARDINAL WITNESS. Deleting or rewriting one of the operator's memories
    is THEIR gesture, never an agent's, and nothing here is allowed to be destructive.

    Both the DIGESTS **and** the SET OF NAMES are frozen: a count alone would let one file come in
    and another go out without turning red.
    """
    dossier = _memoire(tmp_path)
    avant = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dossier.iterdir())}

    idx = IndexDesLecons(dossier, db_path=tmp_path / "lecons.db")
    idx.refresh()
    amorce = Amorce(db_path=tmp_path / "amorce.db")
    deja: set[str] = set()
    for sujet in _SUJETS:
        trouve = choisir(idx, _prompt(sujet), deja)
        amorce.note("s.jsonl", [t.nom for t in trouve])
        deja.update(t.nom for t in trouve)
        rendre(trouve, compte=idx.compte(), dossier=dossier, premiere=False)
    amorce.close()
    idx.close()

    apres = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dossier.iterdir())}
    assert apres == avant, "the primer WROTE into the memory folder"


def test_l_etat_ne_vit_JAMAIS_dans_le_dossier_de_memoire(tmp_path: Path) -> None:
    """The memory folder is a GIT REPOSITORY: a binary `.db` dropped in it would leak out through
    `??` at every `git status`, and would end up committed."""
    from mnemosyne.runtime.lecons_amorce import AMORCE_DB_PATH

    assert AMORCE_DB_PATH.parent.name == "state"
    assert ".claude" not in str(AMORCE_DB_PATH), AMORCE_DB_PATH


@pytest.mark.parametrize(
    "charge",
    ["", "not json", "[]", "null", '{"prompt": null}', '{"autre": 1}', '{"prompt": "   "}'],
)
def test_le_hook_est_FAIL_OPEN_sur_toute_charge_tordue(charge: str) -> None:
    """Fired through a SUBPROCESS, i.e. through the real entry point. This hook runs on every
    operator prompt: a trigger able to break a session is worse than zero lessons recalled. It exits 0
    and prints nothing, whatever it is given."""
    env = {**os.environ, "PYTHONPATH": str(_RACINE / "system" / "lib")}
    r = subprocess.run(
        [sys.executable, "-m", "mnemosyne.runtime.lecons_amorce"],
        input=charge,
        capture_output=True,
        text=True,
        env=env,
        cwd=_RACINE,
        timeout=60,
    )
    assert r.returncode == 0, f"charge={charge!r} rc={r.returncode} err={r.stderr[:400]}"
    assert r.stdout.strip() == "", f"charge={charge!r} a produit : {r.stdout[:200]!r}"


def test_le_hook_reste_FAIL_OPEN_si_la_memoire_est_INTROUVABLE(tmp_path: Path) -> None:
    """A missing memory folder is a NORMAL case (another machine, another repo): silence and 0."""
    env = {
        **os.environ,
        "PYTHONPATH": str(_RACINE / "system" / "lib"),
        "CLAUDE_PROJECT_DIR": str(tmp_path / "repo-that-does-not-exist"),
    }
    r = subprocess.run(
        [sys.executable, "-m", "mnemosyne.runtime.lecons_amorce"],
        input=json.dumps({"prompt": _prompt("hirondelle"), "transcript_path": "/t/s.jsonl"}),
        capture_output=True,
        text=True,
        env=env,
        cwd=_RACINE,
        timeout=60,
    )
    assert r.returncode == 0 and r.stdout.strip() == "", r.stdout[:300]


def test_MIN_TERMES_est_bien_la_borne_annoncee(index: IndexDesLecons) -> None:
    """The threshold is not decorative: at MIN_TERMES-1 content words it stays silent, at MIN_TERMES
    it fires. A witness that does not ARM the gate measures its silence, not its bite."""
    pleins = ["gouvernance", "mesure", "depot", "plafond", "hirondelle", "analyse", "corpus"]
    juste_en_dessous = " ".join(pleins[: MIN_TERMES - 1])
    juste_au_dessus = " ".join(pleins[:MIN_TERMES])
    assert choisir(index, juste_en_dessous, deja=set()) == [], juste_en_dessous
    assert choisir(index, juste_au_dessus, deja=set()) != [], juste_au_dessus
