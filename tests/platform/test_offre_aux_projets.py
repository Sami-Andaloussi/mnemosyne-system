"""The barrier against drifting toward the crutch - proved against the TWO REAL mistakes.

 The operator, verbatim (2026-08-18): *"what I don't want is for us to start using crutches when
we already have the main tool"*. They found the mistake TWICE IN TWO DAYS, by hand. These tests
exist so the third time is caught by the machine.
"""

from __future__ import annotations

from mnemosyne.production import offre_aux_projets as o

from _invariants import REPO_ROOT


def _docs_reels() -> dict[str, str]:
    return {
        d: (REPO_ROOT / d).read_text(encoding="utf-8") for d in o.DOCUMENTS_LUS_PAR_UN_PROJET
    }


# ---- THE REAL THING: what the repo offers TODAY --------------------------------------------------
def test_le_DEPOT_REEL_adresse_chaque_capacite_offerte_AUJOURD_HUI() -> None:
    """ A capability no document read by a project names does not exist for it (D177).
 This test bit on the very day it was written: `gel-inscrire`, built three hours earlier,
 was named NOWHERE."""
    manques = o.capacites_non_adressees(_docs_reels())
    assert manques == (), o.message_offre(manques, ())


def test_le_DEPOT_REEL_montre_la_forme_ATTEIGNABLE_dans_chaque_document() -> None:
    """ From a project folder, `make <target>` returns `No rule to make target` -- the reader
 thinks the tool is broken and falls back to doing it by hand. This test bit on two
 documents the day it was written: `docs/FORMAT_PLAN.md` (13 targets cited, none reachable)
 and a second internal document outside this mirror's scope."""
    sans = o.documents_sans_forme_atteignable(_docs_reels())
    assert sans == (), o.message_offre((), sans)


def test_les_documents_declares_EXISTENT_tous_sur_le_disque() -> None:
    """A declared population that points at a missing file judges a smaller set than it thinks
    it does -- and the refusal would go green by disappearance."""
    for d in o.DOCUMENTS_LUS_PAR_UN_PROJET:
        assert (REPO_ROOT / d).is_file(), d


# ---- THE TWO REAL MISTAKES, REPLAYED: does the barrier BITE on them? ------------------------------
def test_MORD_sur_la_faute_REELLE_du_2026_08_17_signaler_non_atteignable() -> None:
    """ `docs/signalements/README.md` told a PROJECT session to run `make signaler TITRE=...` --
 the one gesture it could not type. The command was NAMED, never REACHABLE.
 *It was the operator who found it, not a gate.*"""
    avant = {
        "docs/signalements/README.md": (
            "| **Session projet** | it breaks | `make signaler TITRE=\"...\"` -> fill it in |"
        )
    }
    assert o.documents_sans_forme_atteignable(avant) == ("docs/signalements/README.md",)


def test_MORD_sur_la_faute_REELLE_du_2026_08_18_lot_emit_jamais_nomme() -> None:
    """ The project's orchestration documentation said "it WRITES the mandate for every chat"
 and never named `lot-emit` ANYWHERE. The tool existed, the document taught the manual path."""
    avant = {
        "governance.md": (
            "It holds the map, gives orders, arbitrates, issues the mandates.\n"
            "| Who works on what | DECIDES -- it writes the mandate for every chat |\n"
            "See also `make -C ~/mnemosyne carte` for the overview.\n"
        )
    }
    # The reachable form is present (so (b) passes): it is (a) that must bite here.
    assert o.documents_sans_forme_atteignable(avant) == ()
    manques = o.capacites_non_adressees(avant)
    assert "lot-emit" in manques, manques


# ---- THE EDGES: the barrier does not accuse what promises nothing ---------------------------------
def test_un_document_qui_ne_cite_AUCUNE_cible_n_est_PAS_en_faute() -> None:
    """ The boundary that keeps this from being a wall: a text that promises no command sends
 nobody into the wall. *Flagging plain prose would turn every governance document in the repo
 red.*"""
    assert o.documents_sans_forme_atteignable({"d.md": "A doctrine, with no command at all."}) == ()


def test_mnemo_seul_SUFFIT_comme_forme_atteignable() -> None:
    """The `J4` shell function is the other legitimate form -- requiring `make -C` alone would
    refuse a perfectly correct document."""
    assert o.documents_sans_forme_atteignable({"d.md": "`make plans` or `mnemo plans`"}) == ()


def test_une_cible_citee_SOUS_sa_forme_atteignable_compte_comme_NOMMEE() -> None:
    """`make -C ~/mnemosyne lot-emit` does name `lot-emit` -- otherwise (a) would flag red on
    a document that does exactly what is asked of it."""
    docs = {"d.md": "`make -C ~/mnemosyne lot-emit ARC=B`"}
    assert "lot-emit" not in o.capacites_non_adressees(docs, offertes=("lot-emit",))


# ---- THE ARTEFACT THAT LANDS IN THE ADOPTER'S REPO (isolated audit, 2026-08-18) -------------------
# The 4-document population had been CHOSEN TO BE GREEN: `CLAUDE.md` (which carried the
# 2026-08-17 mistake VERBATIM), `docs/parentheses/README.md`, and the SCAFFOLD that Mnemosyne
# writes itself into the adopter's `PLAN.md` were all OUTSIDE it. Worse: `CLAUDE.md` had served as
# the SOURCE for establishing the population, and had never been JUDGED by it.
def test_la_PORTE_EMISE_chez_l_adoptant_montre_la_forme_atteignable() -> None:
    """ The most serious case the audit found: this text is not a document one READS, it is an
 artefact Mnemosyne WRITES into the adopter's repo. It named `make describe`,
 `make plan-emit`, `make plan-nouveau` -- without ever saying that none of them exist from
 THERE. *The mistake committed inside the very thing handed to them.*"""
    from mnemosyne.production import plan_scaffold

    porte = plan_scaffold.door_skeleton(
        project="Z", cap="a cap", entries=(("plan/a.md", "ARC A - a"),)
    )
    assert o.cibles_citees(porte), "the scaffold no longer cites any target: this test no longer judges anything"
    assert o.nomme_la_forme_atteignable(porte), porte


def test_la_population_JUGE_les_documents_qui_ont_servi_a_l_ETABLIR() -> None:
    """ THE AUDIT'S LESSON, frozen: `CLAUDE.md` served as the source for choosing the
 population and was not part of it -- that is exactly where the mistake was sleeping.
 *A population derived from a document exempts that document.*"""
    assert "CLAUDE.md" in o.DOCUMENTS_LUS_PAR_UN_PROJET
