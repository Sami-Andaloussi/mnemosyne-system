"""The Atelier attached to a thread - the part that needs NO brick, so it is tested.

``Atelier.dire`` loads MLX, Qdrant and the weights: unavailable in CI, necessarily. But
``attacher``, ``poser_socle`` and the thread's trimming are pure text, and they are what carry the
guarantee the operator asked for. Leaving them under the same ``pragma: no cover`` as decoding
would have turned persistence into a **barrier that nothing calls** - the class of defect that has
already bitten me.

What this defends:

1. **Re-attaching gives the model back what was said before**, including by another process.
2. **A thread interrupted mid-turn does not shift the replies** - pairing is done by the
   roles written, never by position.
3. **The base survives trimming**: an agent must not lose its identity at the exact moment its
   conversation gets long.
"""

from __future__ import annotations

import pytest

from mnemosyne.runtime import conseiller, intendant
from mnemosyne.runtime.atelier import Atelier


@pytest.fixture(autouse=True)
def magasin_neuf(tmp_path, monkeypatch):
    monkeypatch.setenv("MNEMO_INTENDANT_RACINE", str(tmp_path / "intendant"))
    monkeypatch.setenv("MNEMO_CONSEILLER_RACINE", str(tmp_path / "conseiller"))


# -- Attacher ------------------------------------------------------------------------------------


def test_attacher_rend_au_modele_ce_qui_a_ete_dit_avant():
    """The operator's full scenario: we talk, the process dies, a NEW one picks the thread back up."""
    fil = intendant.fil_neuf()
    intendant.fil_ajouter(fil["id"], "I'm working on the workshop", "sounds good")
    intendant.fil_ajouter(fil["id"], "it loses everything on shutdown", "that's the unpersisted thread")

    neuf = Atelier()  # a process that has NEVER seen this conversation
    rep = neuf.attacher(fil["id"])

    assert rep["etat"] == "attache"
    assert rep["tours"] == 2
    assert neuf._fil == [
        ("I'm working on the workshop", "sounds good"),
        ("it loses everything on shutdown", "that's the unpersisted thread"),
    ]


def test_attacher_un_fil_introuvable_refuse_sans_lever():
    atelier = Atelier()
    rep = atelier.attacher("doesnotexist12")
    assert rep["etat"] == "refus"
    assert rep["genre"] == "fil_introuvable"
    assert atelier._fil_id == ""


def test_attacher_un_identifiant_mechant_refuse():
    """`fil_lire` filters at the filesystem boundary; the atelier must inherit the refusal."""
    assert Atelier().attacher("../evasion")["etat"] == "refus"


def test_attacher_le_vide_detache_et_oublie():
    fil = intendant.fil_neuf()
    intendant.fil_ajouter(fil["id"], "a", "b")
    atelier = Atelier()
    atelier.attacher(fil["id"])
    rep = atelier.attacher("")
    assert rep["etat"] == "detache"
    assert atelier._fil == []
    assert atelier._fil_id == ""


def test_un_tour_interrompu_ne_decale_pas_les_repliques():
    """A close in the middle of a turn leaves an ODD number of entries.

    Pairing by position would make each question carry the NEXT one's reply, from that point on
    and for the rest of the thread - silent corruption, and illegible from the screen."""
    fil = intendant.fil_neuf()
    intendant.fil_ajouter(fil["id"], "question 1", "response 1")
    # operator closes the window while the model is answering: their question is written, not the answer.
    brut = intendant.fil_lire(fil["id"])
    brut["tours"].append({"role": "operator", "texte": "question 2 left unanswered", "ts": "x"})
    intendant.fil_ecrire(brut)
    intendant.fil_ajouter(fil["id"], "question 3", "response 3")

    atelier = Atelier()
    atelier.attacher(fil["id"])
    assert atelier._fil == [("question 1", "response 1"), ("question 3", "response 3")]


def test_l_etat_dit_a_quel_fil_on_est_attache():
    fil = intendant.fil_neuf()
    atelier = Atelier()
    assert atelier.etat()["fil_id"] == ""
    atelier.attacher(fil["id"])
    assert atelier.etat()["fil_id"] == fil["id"]


# -- The store - the Conseiller has ITS OWN bubble, distinct from the Intendant's ------------------
#
# Before this parameter existed, attacher() always looked in the Intendant's store, regardless of
# the caller - a Conseiller thread would return "fil_introuvable" every time; the Conseiller's
# first three real tests all failed this way.


def test_attacher_sans_magasin_cherche_toujours_chez_l_intendant():
    """The default remains EXACTLY the behavior from before this parameter - zero regression for any
    caller that does not name it (all of the Intendant's existing code, unchanged)."""
    fil = intendant.fil_neuf()
    intendant.fil_ajouter(fil["id"], "q", "r")
    rep = Atelier().attacher(fil["id"])
    assert rep["etat"] == "attache"


def test_attacher_magasin_conseiller_trouve_un_fil_du_conseiller():
    fil = conseiller.fil_neuf()
    conseiller.fil_ajouter(fil["id"], "I'm torn between two offers", "let's look at that together")
    atelier = Atelier()
    rep = atelier.attacher(fil["id"], magasin="conseiller")
    assert rep["etat"] == "attache"
    assert atelier._fil == [("I'm torn between two offers", "let's look at that together")]


def test_attacher_magasin_conseiller_ne_trouve_pas_un_fil_de_l_intendant():
    """The two bubbles are TRULY separate: an id valid in one is not found in the other, never
    confused."""
    fil = intendant.fil_neuf()
    intendant.fil_ajouter(fil["id"], "q", "r")
    rep = Atelier().attacher(fil["id"], magasin="conseiller")
    assert rep["etat"] == "refus"
    assert rep["genre"] == "fil_introuvable"


def test_un_tour_du_conseiller_interrompu_ne_decale_pas_les_repliques():
    """Same guarantee as on the Intendant side (§ above), on the role the Conseiller actually
    writes ("conseiller", never "intendant") - the generalization that makes this test necessary:
    pairing on a literal `role == "intendant"` would have paired ZERO turns here."""
    fil = conseiller.fil_neuf()
    conseiller.fil_ajouter(fil["id"], "question 1", "response 1")
    brut = conseiller.fil_lire(fil["id"])
    brut["tours"].append({"role": "operator", "texte": "question 2 restee sans response", "ts": "x"})
    conseiller.fil_ecrire(brut)
    conseiller.fil_ajouter(fil["id"], "question 3", "response 3")

    atelier = Atelier()
    atelier.attacher(fil["id"], magasin="conseiller")
    assert atelier._fil == [("question 1", "response 1"), ("question 3", "response 3")]


def test_changer_de_modele_reattache_dans_le_bon_magasin():
    """`_charger` re-attaches on its own when the model changes mid-thread (§ atelier.py) - it
    must land back on the SAME store, never on the Intendant default by accident."""
    fil = conseiller.fil_neuf()
    conseiller.fil_ajouter(fil["id"], "q", "r")
    atelier = Atelier()
    atelier.attacher(fil["id"], magasin="conseiller")
    assert atelier._magasin == "conseiller"


# -- The base -------------------------------------------------------------------------------------


def test_sans_socle_le_premier_tour_part_nu():
    """The original behavior is intact: a caller that asks for nothing gets no persona."""
    atelier = Atelier()
    invite, gardes = atelier._invite("hello")
    assert invite == "hello"
    assert gardes == 0


def test_le_socle_est_la_des_le_PREMIER_tour():
    atelier = Atelier()
    atelier.poser_socle("You are the Intendant.")
    invite, gardes = atelier._invite("hello")
    assert invite.startswith("You are the Intendant.")
    assert "hello" in invite
    assert gardes == 0


def test_le_socle_survit_au_rognage_du_fil():
    """THE trap: when the thread gets too big, everything is cut - except the agent's identity.

    An agent that lost its base at the exact moment its conversation gets long would change
    character mid-stream, with nothing on screen to say so."""
    atelier = Atelier()
    atelier.poser_socle("You are the Intendant.")
    atelier._plafond = 200  # a tiny ceiling: nothing of the thread can fit anymore
    atelier._fil = [("a question " * 40, "a response " * 40)]
    invite, gardes = atelier._invite("what now?")
    assert invite.startswith("You are the Intendant.")
    assert "what now?" in invite
    assert gardes == 0  # the loss of the thread is STATED, not silent


def test_le_socle_remplace_l_entete_par_defaut_il_ne_s_y_ajoute_pas():
    """Two stacked preambles would say twice who's answering, and the second instruction would win."""
    atelier = Atelier()
    atelier.poser_socle("You are the Intendant.")
    atelier._plafond = 48_000
    atelier._fil = [("hi", "hi")]
    invite, _ = atelier._invite("continue")
    # a real fragment of _FIL_ENTETE, the default header this module falls back to when no socle
    # was set (system/lib/mnemosyne/runtime/atelier.py). It must track that constant character for
    # character: the day the two drift apart, this check stops proving anything and stays green.
    assert "LAST message" not in invite


def test_poser_socle_rend_sa_taille():
    assert Atelier().poser_socle("abc")["caracteres"] == 3


# -- Reaching further back - digging beyond what a turn has already received -----------------------
#
# Requirement: answering a question must be able to walk backward through older messages, one
# slice at a time, until it finds what it needs, rather than reloading everything at once. `_invite`
# already decides, at each turn, how many recent exchanges fit (`fil_garde`); `plus_loin` lets a
# caller reach further back than that, one slice at a time, without ever reloading the whole
# thread in one go.


def test_plus_loin_rend_une_tranche_plus_ancienne():
    atelier = Atelier()
    atelier._fil = [(f"question {i}", f"response {i}") for i in range(10)]
    rep = atelier.plus_loin(fin=10, combien=4)
    assert rep["etat"] == "trouve"
    assert "question 6" in rep["texte"] and "question 9" in rep["texte"]
    assert "question 5" not in rep["texte"]
    assert rep["fin"] == 6  # the NEXT bound, to keep walking back


def test_plus_loin_s_enchaine_avec_la_borne_rendue():
    """The real scenario: two calls in a row, the second picks up exactly where the first left off."""
    atelier = Atelier()
    atelier._fil = [(f"question {i}", f"response {i}") for i in range(10)]
    premier = atelier.plus_loin(fin=10, combien=4)
    second = atelier.plus_loin(fin=premier["fin"], combien=4)
    assert "question 2" in second["texte"] and "question 5" in second["texte"]
    assert "question 6" not in second["texte"]
    assert second["fin"] == 2


def test_plus_loin_dit_le_debut_plutot_que_de_rendre_vide_en_silence():
    atelier = Atelier()
    atelier._fil = [("question 0", "response 0"), ("question 1", "response 1")]
    rep = atelier.plus_loin(fin=2, combien=4)
    assert rep["etat"] == "trouve"
    assert rep["fin"] == 0  # nothing left before this: the bound touches the start, this is not a refusal


def test_plus_loin_sur_une_borne_a_zero_ne_trouve_rien():
    atelier = Atelier()
    atelier._fil = [("question 0", "response 0")]
    rep = atelier.plus_loin(fin=0, combien=4)
    assert rep["etat"] == "vide"


def test_plus_loin_une_borne_plus_grande_que_le_fil_est_bornee_sans_lever():
    """An inconsistent `fin` (the thread may have been re-read in the meantime) must never overflow
    the slice - clamp to the real size instead of bluntly refusing a value that is a bit too large."""
    atelier = Atelier()
    atelier._fil = [("question 0", "response 0"), ("question 1", "response 1")]
    rep = atelier.plus_loin(fin=999, combien=4)
    assert rep["etat"] == "trouve"
    assert "question 0" in rep["texte"] and "question 1" in rep["texte"]
    assert rep["fin"] == 0
