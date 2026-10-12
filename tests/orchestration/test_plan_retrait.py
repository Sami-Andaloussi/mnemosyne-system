"""Witnesses for the withdrawal engine (H1) — the D159 pipeline replayed for plan items.

**This module still has NO `make` target** — but it now has a real caller,
`runtime/plan_retrait_run.py` (witnesses: `test_plan_retrait_run.py`). These witnesses prove the
ENGINE in isolation; the `Makefile` hookup stays out of this batch (chat 3). See the docstring of
`plan_retrait.py`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "system" / "lib"))

from mnemosyne.production import plan_retrait  # noqa: E402
from mnemosyne.production.plan_format import read_plan  # noqa: E402
from mnemosyne.production.plan_retrait import (  # noqa: E402
    RetraitDemande,
    RetraitError,
    RetraitLedger,
)


def _ledger(tmp_path: Path) -> RetraitLedger:
    return RetraitLedger(tmp_path / "retraits.jsonl")


def _demande(**kw: object) -> RetraitDemande:
    base = {
        "items": ("Z1", "Z2"),
        "motif": "duplicate of Z9",
        "cout": "aucun",
        "requested_by": "chat-1",
    }
    base.update(kw)
    return RetraitDemande(**base)  # type: ignore[arg-type]


# --- RetraitDemande: validation at construction ----------------------------------------------


def test_une_demande_sans_item_est_refusee() -> None:
    with pytest.raises(RetraitError, match="at least one item"):
        RetraitDemande(items=(), motif="m", cout="aucun", requested_by="x")


def test_une_demande_sans_motif_est_refusee() -> None:
    with pytest.raises(RetraitError, match="motif"):
        RetraitDemande(items=("Z1",), motif="   ", cout="aucun", requested_by="x")


def test_une_demande_sans_cout_est_refusee() -> None:
    with pytest.raises(RetraitError, match="cout"):
        RetraitDemande(items=("Z1",), motif="m", cout=" ", requested_by="x")


def test_un_caractere_de_controle_dans_le_motif_est_refuse() -> None:
    with pytest.raises(RetraitError, match="control character"):
        RetraitDemande(items=("Z1",), motif="m\x1b[2Jecran efface", cout="aucun", requested_by="x")


def test_les_items_sont_DEDUPLIQUES_et_TRIES__l_ordre_d_appel_ne_change_pas_le_contenu() -> None:
    """The id is a hash of the content: two equivalent calls must produce the SAME id, otherwise
    "filing the same thing twice" would create two requests instead of one (not idempotent)."""
    a = RetraitDemande(items=("Z2", "Z1", "Z1"), motif="m", cout="aucun", requested_by="x")
    b = RetraitDemande(items=("Z1", "Z2"), motif="m", cout="aucun", requested_by="x")
    assert a.items == ("Z1", "Z2")
    assert a.content_hash() == b.content_hash()


# --- filing (the request) -----------------------------------------------------------------------


def test_deposer_puis_relire_rend_l_etat_depose(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    etat = ledger.state(id_)
    assert etat is not None
    assert etat.stage == "depose"
    assert etat.items == ("Z1", "Z2")
    assert not etat.examined and not etat.approved and not etat.refused


def test_deposer_deux_fois_le_MEME_contenu_rend_le_MEME_id_sans_dupliquer(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_a = ledger.file(_demande())
    id_b = ledger.file(_demande())
    assert id_a == id_b
    assert len(ledger.all_states()) == 1


# --- the examiner (narrow, never widen) -----------------------------------------------------------


def test_un_verdict_narrow_RETRECIT_reellement_les_items(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande(items=("Z1", "Z2", "Z3")))
    ledger.record_examination(
        id_, verdict="narrow", narrowed_items=("Z1",), notes="Z2/Z3 still useful"
    )
    etat = ledger.state(id_)
    assert etat.items == ("Z1",)
    assert etat.stage == "examine"
    assert etat.examiner_verdict == "narrow"


def test_un_verdict_narrow_qui_AJOUTE_un_item_est_refuse(tmp_path: Path) -> None:
    """D159's structural guarantee, carried here: the examiner can invent NOTHING."""
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande(items=("Z1", "Z2")))
    with pytest.raises(RetraitError, match="WITHDRAW, never add"):
        ledger.record_examination(id_, verdict="narrow", narrowed_items=("Z1", "Z9"))
    # And the request has NOT moved: the refusal arrived BEFORE any write that would mutate it
    # (a `denied` event IS now written -- see below -- but `items` stays intact).
    assert ledger.state(id_).items == ("Z1", "Z2")
    assert ledger.state(id_).stage == "depose"
    # AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): "the exact same class" as the member judged
    # by H1's clause, on D159's CENTRAL attack -- an isolated examiner smuggling in an identifier
    # never on the table under the 'narrow' label. Measured: 5 attempts, 0 bytes. An examiner
    # could hammer this attempt indefinitely, zero footprint.
    assert ledger.state(id_).denied_count == 1, (
        "a 'narrow' verdict that widens left no trace of the attempt"
    )


def test_un_verdict_narrow_sans_item_retreci_est_refuse(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    with pytest.raises(RetraitError, match="at least one narrowed item"):
        ledger.record_examination(id_, verdict="narrow", narrowed_items=())


def test_un_verdict_inconnu_est_refuse(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    with pytest.raises(RetraitError, match="unknown examiner verdict"):
        ledger.record_examination(id_, verdict="maybe")


def test_examiner_une_requete_inconnue_est_refuse(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(RetraitError, match="unknown"):
        ledger.record_examination("aucune", verdict="allow")


# --- the refusal --------------------------------------------------------------------------------


def test_refuser_ferme_la_requete(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    ledger.refuse(id_, reason="not yet, Z1 is used elsewhere", by="terminal (/dev/tty), D159")
    etat = ledger.state(id_)
    assert etat.stage == "refuse"
    assert etat.refused_reason == "not yet, Z1 is used elsewhere"
    # AUDIT DELEGATED ON 2026-08-15: `by`/`at` already travelled in the `refused` event but
    # the fold discarded them -- render_queue, the only surface the operator reads, could
    # therefore never show WHO refused nor WHEN, even though the raw JSONL carried them from the
    # start.
    assert etat.refused_by == "terminal (/dev/tty), D159"
    assert etat.refused_at, "a refusal with no timestamp dates nothing for the operator"


def test_refuser_sans_raison_est_refuse(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    with pytest.raises(RetraitError, match="reason"):
        ledger.refuse(id_, reason="  ", by="x")


def test_refuser_une_requete_DEJA_APPLIQUEE_est_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): nothing guarded this case -- a withdrawal
    ALREADY APPLIED (already written to a real plan) could still be 'refused', producing a
    CONTRADICTORY state: `stage` answers 'applique' (it looks at `applied` first), but
    `render_queue` ALSO printed the refusal line, because it tests `state.refused`
    independently of `stage`. A refusal does not undo a write already made (inv. 2)."""
    fichier = tmp_path / "PLAN.md"
    fichier.write_text(_plan_a_trois_items(), encoding="utf-8")
    ledger = _ledger(tmp_path)
    id_ = ledger.file(RetraitDemande(items=("A1",), motif="m", cout="c", requested_by="chat-1"))
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", _FauxTerminal(True))
    ledger.approuver_en_direct(id_, by="terminal (/dev/tty), D159")
    ledger.appliquer_verifie(id_, chemin=fichier, by="terminal (/dev/tty), D159")
    assert ledger.state(id_).stage == "applique"

    with pytest.raises(RetraitError, match="already applied"):
        ledger.refuse(id_, reason="trop tard", by="x")

    etat = ledger.state(id_)
    assert etat.stage == "applique", "the failed refusal must not have moved the stage"
    assert not etat.refused, "a REFUSED refusal must not journal itself anyway"


# --- THE SABOTAGE `H1` REQUIRES: forging the approval must stay REFUSED AND NAMED --------------
#
# FIXED on 2026-08-15: this heading still claimed IMPOSSIBLE although H1 has been downgraded
# to level 2 since (isolated audit D75: a self-fabricated pty -- os.setsid() + TIOCSCTTY -- forces
# a real approval, with no human gesture at all, by reusing tests/_pty.py which proves the
# LEGITIMATE case. See the corresponding plan item, tracked outside this mirror). A witness whose
# comment claims what the item has abandoned teaches the wrong rule to the next reader.
#
# The witnesses below PROVE that forging by pipe/without-a-tty fails -- they do NOT prove general
# incapacity: the pty vector stays open, flagged, outside this module's perimeter (system-wide,
# human_gate.py, spanning four other callers).


def test_AUCUNE_methode_publique_n_accepte_un_MOT_pour_approuver() -> None:
    """The exact shape of the D160 incident: an agent types the approval word itself, without
    ever touching a terminal, and the journal attributes it to the operator. Closed here
    STRUCTURALLY: only ONE method can produce an 'approved' event, and it takes NO `word=`
    parameter — nothing to forge, because nothing asks for it."""
    ledger = RetraitLedger(Path("/tmp/never-created.jsonl"))
    assert not hasattr(ledger, "approve"), "an 'approve(word=...)' bypass has been reintroduced"
    import inspect

    sig = inspect.signature(ledger.approuver_en_direct)
    assert "word" not in sig.parameters, (
        "approuver_en_direct accepts a word -- the gate is forgeable"
    )


def test_SANS_confirmation_EN_DIRECT_le_retrait_n_est_JAMAIS_approuve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulates the absence of a controlling terminal (an agent, a pipe, CI): `human_gate` returns `False`."""
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", lambda prompt: False)

    resultat = ledger.approuver_en_direct(id_, by="terminal (/dev/tty), D159")

    assert resultat is False
    etat = ledger.state(id_)
    assert etat.stage == "depose", (
        "a refusal/silence from the tty still left a trace of approval"
    )
    assert not etat.approved
    # AUDIT DELEGATED ON 2026-08-15: a `False` with no LIVE confirmation journalled NOTHING
    # -- an attempt to forge the approval (the very sabotage H1 requires be countered) therefore
    # left a NULL footprint, indistinguishable from a plain "nobody ever tried".
    assert etat.denied_count == 1, "the failed LIVE confirmation left no trace"
    assert etat.last_denied_by == "terminal (/dev/tty), D159"
    assert etat.last_denied_reason


def test_AVEC_confirmation_EN_DIRECT_le_retrait_est_approuve_et_le_HASH_lie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    vu: list[str] = []
    monkeypatch.setattr(
        plan_retrait, "read_live_confirmation", lambda prompt: (vu.append(prompt), True)[1]
    )

    resultat = ledger.approuver_en_direct(id_, by="terminal (/dev/tty), D159")

    assert resultat is True
    etat = ledger.state(id_)
    assert etat.stage == "approuve"
    assert etat.approved_content_hash == etat.content_hash()
    # The prompt NAMES what is about to happen (items, motif, cout) -- a vague prompt would
    # authorise whatever the caller decided, which would make a hijacked target invisible.
    assert "Z1" in vu[0] and "Z2" in vu[0] and "duplicate of Z9" in vu[0]


def test_approuver_une_requete_deja_REFUSEE_est_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    ledger.refuse(id_, reason="non", by="terminal (/dev/tty), D159")
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", lambda prompt: True)

    with pytest.raises(RetraitError, match="already refused"):
        ledger.approuver_en_direct(id_, by="terminal (/dev/tty), D159")

    # AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): THIS specific branch -- one line above the
    # one the first fix instrumented, in the SAME method -- stayed at 0 bytes. Measured by the
    # auditor: 5 attempts, 0 bytes. Hammering an already-refused request left the same zero
    # footprint as the one H1's clause judges.
    etat = ledger.state(id_)
    assert etat.denied_count == 1, (
        "approving an already-refused request left no trace of the attempt"
    )


def test_approuver_une_requete_INCONNUE_est_refuse(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(RetraitError, match="unknown"):
        ledger.approuver_en_direct("never-filed", by="x")


# --- replay: fail-closed on a corrupt line, tolerant of a truncated tail -----------------------


def test_une_ligne_interne_corrompue_fait_REFUSER_le_rejeu(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    ledger.refuse(id_, reason="to fill in a 2nd line", by="x")
    ledger.path.write_text(
        ledger.path.read_text(encoding="utf-8")[:20]
        + "\n"
        + ledger.path.read_text(encoding="utf-8").splitlines()[1]
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RetraitError, match="corrupt"):
        ledger.state(id_)


def test_une_queue_TRONQUEE_est_toleree_crash_mid_append(tmp_path: Path) -> None:
    """Write-ahead: a crash while writing the LAST line is not a lost decision, RAM had not
    seen it either (D82) -- the truncated tail is ignored."""
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    with ledger.path.open("a", encoding="utf-8") as handle:
        handle.write('{"v": 1, "kind": "examined", "id": "' + id_ + '", "verdict": "al')  # truncated
    etat = ledger.state(id_)
    assert etat.stage == "depose"


def test_un_genre_d_evenement_inconnu_fait_REFUSER_le_rejeu(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    id_ = ledger.file(_demande())
    with ledger.path.open("a", encoding="utf-8") as handle:
        handle.write('{"v": 1, "kind": "mystere", "id": "' + id_ + '"}\n')
    with pytest.raises(RetraitError, match="unknown event kind"):
        ledger.state(id_)


# --- applying (H1): format-preserving write, verified AFTER the fact (D161) --------------------


def _plan_a_trois_items(cap: str = "c") -> str:
    champs = (
        "  *Produit* : p\n  *Fini quand* : f\n  *Dépend de* : AUCUNE\n"
        "  *Prérequis* : AUCUN\n  *À lire* : a\n  *Taille* : t\n"
    )
    return (
        f"# PLAN — d\n\n> **Cap** : {cap}\n\n"
        f"- **A0** \U00002B1C the item before.\n{champs}"
        f"- **A1** \U00002B1C the item to withdraw.\n{champs}"
        f"- **A2** \U00002B1C the item after.\n{champs}"
    )


def test_applique_retrait_CLOT_l_item_et_garde_ses_voisins_A_L_IDENTIQUE() -> None:
    texte = _plan_a_trois_items()
    before = read_plan(texte)

    after = plan_retrait.applique_retrait(
        texte, ("A1",), motif="doublon", cout="aucun", id_retrait="abc", quand="2026-08-15"
    )

    reading = read_plan(after)
    by_ident = {it.ident: it for it in reading.items}
    assert by_ident["A1"].status == "clos"
    assert by_ident["A1"].field("produit") == "p", "the item's text was touched"
    assert by_ident["A0"].fields == before.items[0].fields
    assert by_ident["A2"].fields == before.items[2].fields


def test_applique_retrait_REFUSE_un_item_absent_du_plan() -> None:
    with pytest.raises(RetraitError, match="absent"):
        plan_retrait.applique_retrait(
            _plan_a_trois_items(), ("Z9",), motif="m", cout="c", id_retrait="x", quand="2026-08-15"
        )


def test_applique_retrait_REFUSE_un_item_DEJA_clos() -> None:
    already = plan_retrait.applique_retrait(
        _plan_a_trois_items(), ("A1",), motif="m", cout="c", id_retrait="x", quand="2026-08-15"
    )
    with pytest.raises(RetraitError, match="already closed"):
        plan_retrait.applique_retrait(
            already, ("A1",), motif="m", cout="c", id_retrait="y", quand="2026-08-15"
        )


def test_applique_retrait_de_PLUSIEURS_items_ne_derange_PERSONNE_d_autre() -> None:
    texte = _plan_a_trois_items()
    after = plan_retrait.applique_retrait(
        texte, ("A0", "A2"), motif="m", cout="c", id_retrait="x", quand="2026-08-15"
    )
    reading = read_plan(after)
    by_ident = {it.ident: it for it in reading.items}
    assert by_ident["A0"].status == "clos"
    assert by_ident["A2"].status == "clos"
    assert by_ident["A1"].status == "a_faire"
    assert by_ident["A1"].field("produit") == "p"


def test_le_COMMENTAIRE_de_retrait_ne_VOLE_aucun_champ_voisin() -> None:
    """A direct counter-proof of this same module's `A1`/`A7` fixes: the comment the apply
    step inserts must stay invisible to the field reader, like any other comment."""
    texte = _plan_a_trois_items()
    after = plan_retrait.applique_retrait(
        texte,
        ("A1",),
        motif="a motif long enough to test with",
        cout="0",
        id_retrait="x",
        quand="2026-08-15",
    )
    item = read_plan(after).items[1]
    assert len(item.declared_fields) == 6, item.declared_fields
    assert item.field("prerequis") == "AUCUN"


def test_un_motif_portant_un_fermeur_LITTERAL_n_injecte_PAS_un_item_fantome() -> None:
    """AUDIT DELEGATED ON 2026-08-15, WITHIN H1's CLAUSE: a motif containing `-->` used to
    close the comment too early, and everything that followed (including an item bullet the
    attacker fabricated INSIDE the motif) became real plan content. Measured by the auditor:
    accepted by the real CLI, a PHANTOM item appeared in the reading. This witness replays the
    exact attack against the engine."""
    texte = _plan_a_trois_items()
    motif_attack = "X --> \n- **PHANTOM** \U00002B1C injected by the attacker.\n  *Produit* : p"
    after = plan_retrait.applique_retrait(
        texte, ("A1",), motif=motif_attack, cout="c", id_retrait="x", quand="2026-08-15"
    )
    reading = read_plan(after)
    assert "PHANTOM" not in [i.ident for i in reading.items], [i.ident for i in reading.items]
    assert reading.problems == (), reading.problems


def test_un_motif_MULTI_LIGNES_reste_UNE_seule_ligne_physique_dans_le_commentaire() -> None:
    """The inserted comment is a single element of the line list — a motif carrying a `\\n`
    (a semantically legitimate value, displayed as-is by `queue`) would turn it back into
    SEVERAL physical lines at `\"\\n\".join` time, breaking the format's single-line assumption.
    Verified: the text's line count only grows by ONE, whatever the number of line breaks in
    the motif."""
    texte = _plan_a_trois_items()
    before_n = len(texte.split("\n"))
    motif_multiline = "premiere raison\ndeuxieme raison\ntroisieme raison"
    after = plan_retrait.applique_retrait(
        texte, ("A1",), motif=motif_multiline, cout="c", id_retrait="x", quand="2026-08-15"
    )
    assert len(after.split("\n")) == before_n + 1
    item = read_plan(after).items[1]
    assert len(item.declared_fields) == 6, item.declared_fields


class _FauxTerminal:
    def __init__(self, accepte: bool) -> None:
        self.accepte = accepte
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> bool:
        self.prompts.append(prompt)
        return self.accepte


def test_appliquer_verifie_ECRIT_puis_RELIT_DEPUIS_LE_DISQUE_avant_de_journaliser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fichier = tmp_path / "PLAN.md"
    fichier.write_text(_plan_a_trois_items(), encoding="utf-8")
    ledger = _ledger(tmp_path)
    id_ = ledger.file(
        RetraitDemande(items=("A1",), motif="doublon", cout="aucun", requested_by="chat-1")
    )
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", _FauxTerminal(True))
    assert ledger.approuver_en_direct(id_, by="terminal (/dev/tty), D159") is True

    ledger.appliquer_verifie(id_, chemin=fichier, by="terminal (/dev/tty), D159")

    assert ledger.state(id_).stage == "applique"
    sur_disque = read_plan(fichier.read_text(encoding="utf-8"))
    assert {it.ident: it.status for it in sur_disque.items}["A1"] == "clos"


def test_appliquer_verifie_REFUSE_si_pas_APPROUVE(tmp_path: Path) -> None:
    fichier = tmp_path / "PLAN.md"
    fichier.write_text(_plan_a_trois_items(), encoding="utf-8")
    ledger = _ledger(tmp_path)
    id_ = ledger.file(RetraitDemande(items=("A1",), motif="m", cout="c", requested_by="chat-1"))

    with pytest.raises(RetraitError, match="only 'approuve' can be applied"):
        ledger.appliquer_verifie(id_, chemin=fichier, by="x")

    assert read_plan(fichier.read_text(encoding="utf-8")).items[1].status == "a_faire", (
        "the file was touched even though the request was not even approved"
    )


def test_appliquer_SANS_approbation_ECRIT_une_trace_de_refus_sur_le_journal(
    tmp_path: Path,
) -> None:
    """AUDIT DELEGATED ON 2026-08-15, WITHIN H1's CLAUSE: "a withdrawal with no GO is refused
    AND NAMED -- and by the trace of what the refusal wrote" held on its first member, was EMPTY
    on the second. Measured: 0 bytes written over 4 attempts. An agent could hammer
    `appliquer --confirm` indefinitely without leaving a footprint."""
    fichier = tmp_path / "PLAN.md"
    fichier.write_text(_plan_a_trois_items(), encoding="utf-8")
    ledger = _ledger(tmp_path)
    id_ = ledger.file(RetraitDemande(items=("A1",), motif="m", cout="c", requested_by="chat-1"))

    with pytest.raises(RetraitError, match="only 'approuve' can be applied"):
        ledger.appliquer_verifie(id_, chemin=fichier, by="CLI item-retirer (test)")

    etat = ledger.state(id_)
    assert etat.denied_count == 1, "the refusal left no trace on the journal"
    assert etat.last_denied_by == "CLI item-retirer (test)"
    assert etat.last_denied_reason, "a refusal trace with no reason explains nothing to the operator"
    assert etat.last_denied_at, "a refusal trace with no timestamp dates nothing"
    # Read back from DISK, not from the in-memory state -- the same discipline as the rest of
    # the module: a trace that exists only in RAM is not a trace.
    relu = RetraitLedger(ledger.path).state(id_)
    assert relu is not None and relu.denied_count == 1


def test_un_by_malforme_N_ATTEINT_JAMAIS_le_disque_meme_sur_le_chemin_refus(
    tmp_path: Path,
) -> None:
    """AUDIT DELEGATED ON 2026-08-15 (RE-AUDIT): the `by` check was moved BEFORE the two new
    write branches -- verifies this order genuinely HOLDS, not merely that it is written. A `by`
    with a control character, on a request ALREADY at the wrong stage (both conditions at once),
    must raise for the WRONG SHAPE, never write the refusal event with that dirty value."""
    fichier = tmp_path / "PLAN.md"
    fichier.write_text(_plan_a_trois_items(), encoding="utf-8")
    ledger = _ledger(tmp_path)
    id_ = ledger.file(RetraitDemande(items=("A1",), motif="m", cout="c", requested_by="chat-1"))

    with pytest.raises(RetraitError, match="control character"):
        ledger.appliquer_verifie(id_, chemin=fichier, by="CLI\x01injecte")

    etat = ledger.state(id_)
    assert etat.denied_count == 0, (
        "a malformed by still wrote a denied event -- the check is no longer BEFORE"
    )


def test_le_refus_d_appliquer_NOMME_l_identifiant_dans_son_message(tmp_path: Path) -> None:
    """AUDIT DELEGATED ON 2026-08-15: the clause requires a refusal REFUSED AND NAMED -- this
    message is the ONLY one of the two halves the operator sees live (the other lives in the
    journal, see the witness just above). Sabotage-verified: removing `{id_!r}` from this exact
    message made no witness turn red before this one."""
    fichier = tmp_path / "PLAN.md"
    fichier.write_text(_plan_a_trois_items(), encoding="utf-8")
    ledger = _ledger(tmp_path)
    id_ = ledger.file(RetraitDemande(items=("A1",), motif="m", cout="c", requested_by="chat-1"))

    with pytest.raises(RetraitError) as exc:
        ledger.appliquer_verifie(id_, chemin=fichier, by="x")

    assert id_ in str(exc.value), (
        f"the refusal message does not name the request concerned: {exc.value}"
    )


def test_appliquer_verifie_REFUSE_et_NE_JOURNALISE_PAS_si_la_relecture_disque_MENT(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**THE SABOTAGE D161 REQUIRES.** Simulates a write that does not land as expected — the
    disk, once RE-READ, does not carry the change. `appliquer_verifie` must refuse and NOT
    journal 'applied', even though the text it had PRODUCED in memory was correct."""
    fichier = tmp_path / "PLAN.md"
    fichier.write_text(_plan_a_trois_items(), encoding="utf-8")
    ledger = _ledger(tmp_path)
    id_ = ledger.file(RetraitDemande(items=("A1",), motif="m", cout="c", requested_by="chat-1"))
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", _FauxTerminal(True))
    ledger.approuver_en_direct(id_, by="terminal (/dev/tty), D159")

    vrai_write_text = Path.write_text

    def write_text_qui_ment(self: Path, contenu: str, **kw: object) -> int:
        if self == fichier:
            return vrai_write_text(self, _plan_a_trois_items(), **kw)  # writes something else
        return vrai_write_text(self, contenu, **kw)

    monkeypatch.setattr(Path, "write_text", write_text_qui_ment)

    with pytest.raises(RetraitError, match="NOT journalled"):
        ledger.appliquer_verifie(id_, chemin=fichier, by="terminal (/dev/tty), D159")

    assert ledger.state(id_).stage == "approuve", (
        "the refusal must leave the state at 'approuve', not 'applique'"
    )


def test_appliquer_verifie_REFUSE_sur_un_HASH_devenu_perime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The approved content must match the current state EXACTLY — an item narrowed AFTER the
    fact (say, two successive examinations) must not let a stale approval apply itself to a set
    of items it never saw."""
    fichier = tmp_path / "PLAN.md"
    fichier.write_text(_plan_a_trois_items(), encoding="utf-8")
    ledger = _ledger(tmp_path)
    id_ = ledger.file(
        RetraitDemande(items=("A0", "A1"), motif="m", cout="c", requested_by="chat-1")
    )
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", _FauxTerminal(True))
    ledger.approuver_en_direct(id_, by="terminal (/dev/tty), D159")
    # an examination AFTER the approval narrows the scope -- the approval itself stayed bound to
    # {A0, A1} and must no longer be able to apply as-is.
    ledger.record_examination(id_, verdict="narrow", narrowed_items=("A1",))

    with pytest.raises(RetraitError, match="no longer matches"):
        ledger.appliquer_verifie(id_, chemin=fichier, by="terminal (/dev/tty), D159")

    etat = ledger.state(id_)
    assert etat.denied_count == 1, "the stale hash must ALSO leave a trace, not merely raise"
    assert "no longer matches" in etat.last_denied_reason


# **HARDENING (2026-08-16), H1 stays CLOSED -- this does not reopen the case.**
#
# This module's ORIGINAL population, written before seeking a second population (per the
# orchestrator's own protocol): EVERY witness above, without exception, builds its own ledger in
# `tmp_path` -- verified with `grep -c tmp_path` on this file AND on `test_plan_retrait_run.py`,
# this module's two sisters. Zero witness, before this one, had ever read the REAL production
# ledger (`system/state/retraits_requests.jsonl`).
#
# Second population: THIS real ledger, never synthetic -- 3 requests filed during the D5 work
# (signal 4) and its own H1 audit that same night, never replayed by THIS module. It differs
# structurally (not merely "it is real"): it is usage produced by CLIs and successive human/agent
# audits, not a sequence of calls hand-built to target one precise branch.
#
# This file is NOT tracked by git (`system/state/*.jsonl`, barrier D82) -- absent on a fresh
# clone. The witness SKIPS, never an `xfail` nor a lying green.
# The ledger is LIVE (append-only, other sessions can write to it) -- no exact value is frozen
# in place. The witness recounts the raw bytes itself, INDEPENDENTLY of `RetraitLedger`, and
# compares the two -- an accessor that derives from its own source file would turn red here even
# if its internal output stayed "consistent with itself".
def test_all_states_HORS_POPULATION_sur_le_ledger_REEL_jamais_vu_par_ce_module() -> None:
    chemin = Path(__file__).resolve().parents[2] / "system" / "state" / "retraits_requests.jsonl"
    if not chemin.is_file():
        pytest.skip(
            "system/state/retraits_requests.jsonl absent on this machine -- "
            "no second population available here, not an absence of measurement taken elsewhere"
        )

    # INDEPENDENT recount, on the raw bytes -- not via RetraitLedger, so the comparison is never
    # an accessor confirming itself.
    kinds_par_id: dict[str, list[str]] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        evenement = json.loads(ligne)
        kinds_par_id.setdefault(evenement["id"], []).append(evenement["kind"])

    assert kinds_par_id, "the real ledger exists but carries no request -- empty population"

    etats = {etat.id: etat for etat in RetraitLedger(chemin).all_states()}
    assert set(etats) == set(kinds_par_id), (
        "RetraitLedger.all_states() must see EXACTLY the raw file's ids, no more, no less"
    )

    for id_, kinds in kinds_par_id.items():
        etat = etats[id_]
        assert etat.denied_count == kinds.count("denied"), (
            f"{id_}: denied_count must equal the RAW count of 'denied' events, "
            "never an approximation"
        )
        assert etat.refused == ("refused" in kinds), (
            f"{id_}: `refused` must reflect the real presence of a 'refused' event"
        )
        # append-only (inv. 2): an id closed by a refusal stays closed, the trace cannot vanish.
        if "refused" in kinds:
            assert etat.stage == "refuse", f"{id_}: a raw 'refused' event must close the state"
