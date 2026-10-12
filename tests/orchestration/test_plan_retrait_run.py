"""Tests of the `item-retirer` CLI (H1) — the CALLER of the `plan_retrait.py` engine.

Measured before writing this module: `who imports plan_retrait -> test_plan_retrait.py, and
NOTHING else` — a module whose only caller is its own test has exactly the appearance of a
finished module. This file proves the REAL caller. The `make item-retirer` wiring is now in place
(chat 3, a single target, `ARGS=`) — verified live: `make item-retirer ARGS="queue"` responds.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "system" / "lib"))

from _invariants import REPO_ROOT  # noqa: E402

from mnemosyne.production import plan_retrait  # noqa: E402
from mnemosyne.production.plan_format import read_plan  # noqa: E402
from mnemosyne.production.plan_retrait import RetraitDemande, RetraitLedger  # noqa: E402
from mnemosyne.runtime import plan_retrait_run  # noqa: E402

_LIB = str(REPO_ROOT / "system" / "lib")


def _run(ledger_path: Path, *args: str) -> int:
    return plan_retrait_run.main(["--ledger", str(ledger_path), *args])


def _plan_minimal(*idents: str) -> str:
    six = "".join(
        f"  *{n}* : {v}\n"
        for n, v in (
            ("Produit", "p"),
            ("Fini quand", "f"),
            ("Dépend de", "AUCUNE"),
            ("Prérequis", "AUCUN"),
            ("À lire", "a"),
            ("Taille", "t"),
        )
    )
    tete = "# PLAN — d\n\n> **Cap** : c\n\n"
    corps = "".join(f"- **{ident}** \U00002B1C item {ident}.\n{six}" for ident in idents)
    return tete + corps


# --- queue ------------------------------------------------------------------------------------


def test_queue_vide_ne_plante_pas(tmp_path: Path, capsys) -> None:
    assert _run(tmp_path / "l.jsonl", "queue") == 0
    assert "No request filed" in capsys.readouterr().out


def test_queue_liste_une_demande_deposee(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    _run(
        ledger_path,
        "demander",
        "--items",
        "Z1",
        "--motif",
        "duplicate",
        "--cout",
        "none",
        "--requested-by",
        "chat-1",
    )
    out = capsys.readouterr().out
    assert "Request filed" in out
    capsys.readouterr()
    assert _run(ledger_path, "queue") == 0
    assert "[depose]" in capsys.readouterr().out


# --- demander -----------------------------------------------------------------------------------


def test_demander_deduplique_et_trie_via_le_moteur(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    rc = _run(
        ledger_path,
        "demander",
        "--items",
        "Z2, Z1, Z1",
        "--motif",
        "duplicate of Z9",
        "--cout",
        "none",
        "--requested-by",
        "chat-1",
    )
    assert rc == 0
    ledger = RetraitLedger(ledger_path)
    (state,) = ledger.all_states()
    assert state.items == ("Z1", "Z2")


def test_demander_sans_motif_est_refusee_proprement(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    rc = _run(
        ledger_path,
        "demander",
        "--items",
        "Z1",
        "--motif",
        "",
        "--cout",
        "none",
        "--requested-by",
        "c1",
    )
    assert rc == 2
    assert "Request refused" in capsys.readouterr().err
    assert RetraitLedger(ledger_path).all_states() == ()


# --- examiner -----------------------------------------------------------------------------------


def test_examiner_sans_verdict_imprime_le_mandat_borne(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1",), motif="duplicate", cout="none", requested_by="c1")
    )
    capsys.readouterr()
    assert _run(ledger_path, "examiner", "--id", id_) == 0
    out = capsys.readouterr().out
    assert "Adversarial examination mandate" in out
    assert "Z1" in out
    assert "verdict" in out


def test_examiner_avec_verdict_narrow_retrecit_les_items(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1", "Z2"), motif="duplicate", cout="none", requested_by="c1")
    )
    verdict_path = tmp_path / "verdict.json"
    verdict_path.write_text(
        json.dumps({"verdict": "narrow", "notes": "Z2 unrelated", "narrowed_items": ["Z1"]}),
        encoding="utf-8",
    )
    assert _run(ledger_path, "examiner", "--id", id_, "--verdict", str(verdict_path)) == 0
    assert ledger.state(id_).items == ("Z1",)


def test_examiner_id_inconnu_est_refuse_proprement(tmp_path: Path, capsys) -> None:
    rc = _run(tmp_path / "l.jsonl", "examiner", "--id", "inconnu")
    assert rc == 2
    assert "Unknown request" in capsys.readouterr().err


# --- approuver / refuser -- monkeypatch of the SAME seam as test_plan_retrait.py ----------------


def test_approuver_sans_oui_en_direct_n_approuve_rien(tmp_path: Path, monkeypatch, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1",), motif="duplicate", cout="none", requested_by="c1")
    )
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", lambda prompt: False)
    assert _run(ledger_path, "approuver", "--id", id_) == 1
    assert ledger.state(id_).stage == "depose"
    # DELEGATED AUDIT OF 2026-08-15 (RE-AUDIT): `render_queue` can lose the entire block of
    # denied attempts without ANY witness turning red -- nothing forced the surface the operator
    # actually reads (`queue`, not the raw JSONL) to show what the engine journals.
    capsys.readouterr()
    assert _run(ledger_path, "queue") == 0
    out = capsys.readouterr().out
    assert "attempt" in out and "refused" in out, (
        f"the denied attempt does not appear in what the operator reads: {out!r}"
    )
    # DELEGATED AUDIT OF 2026-08-15 (RE-AUDIT): `by="terminal (/dev/tty), H1"` was true ONLY
    # on the success path, and still landed in THIS `denied` event -- a terminal attested for a
    # refusal caused by its own absence. Same fault already closed for
    # `_cmd_refuser`/`_cmd_appliquer`, reopened here. Checks the EXACT label, not just its
    # presence -- a regression to the old text must turn this witness red, not just disappear
    # silently.
    assert ledger.state(id_).last_denied_by == "CLI item-retirer, /dev/tty read attempted", (
        "the by= field attributes a RESULT (confirmed terminal) rather than an attempt"
    )


def test_approuver_avec_oui_en_direct_approuve_et_montre_le_contenu_AVANT(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1",), motif="duplicate of Z9", cout="none", requested_by="c1")
    )
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", lambda prompt: True)
    capsys.readouterr()
    assert _run(ledger_path, "approuver", "--id", id_) == 0
    out = capsys.readouterr().out
    # The content (motif included) must appear BEFORE the confirmation, never after the fact.
    assert "duplicate of Z9" in out
    assert ledger.state(id_).stage == "approuve"


def test_refuser_exige_une_raison(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1",), motif="duplicate", cout="none", requested_by="c1")
    )
    assert _run(ledger_path, "refuser", "--id", id_, "--raison", "") == 2
    assert ledger.state(id_).stage == "depose"


def test_refuser_enregistre_la_raison(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1",), motif="duplicate", cout="none", requested_by="c1")
    )
    assert _run(ledger_path, "refuser", "--id", id_, "--raison", "not sure enough") == 0
    assert ledger.state(id_).refused_reason == "not sure enough"
    # DELEGATED AUDIT OF 2026-08-15 (RE-AUDIT): same gap as for `denied`, but on `refused` --
    # `by`/`at` have traveled inside the event from the start, but nothing forced `queue` (what
    # the operator reads) to show them. Checks against the ACTUAL command output, not just the
    # state.
    capsys.readouterr()
    assert _run(ledger_path, "queue") == 0
    out = capsys.readouterr().out
    assert "CLI item-retirer" in out and "not sure enough" in out, (
        f"who/when refused does not appear in what the operator reads: {out!r}"
    )


# --- THE FORGERY SABOTAGE (H1, level 3 -- incapacity) --------------------------------------------
#
# **WHAT THE TASK ASKED FOR, VERBATIM**: "clause H1 requires that a withdrawal without a live
# GO be impossible -- not refused: IMPOSSIBLE -- proven by a sabotage that tries to FORGE the
# approval. A sabotage that fails to forge proves the incapacity; a sabotage that was never
# written proves nothing."
#
# The monkeypatch witnesses above (`read_live_confirmation` replaced by `lambda: True/False`)
# prove that THE CODE reacts correctly to whatever the gate returns to it -- they do NOT prove
# that the gate itself resists a real attempt to forge an entry with no terminal. This is exactly
# the distinction that `tests/orchestration/test_human_gate.py` had to learn (2026-07-28, the
# audit that found `input()` satisfiable via a pipe): "the suite had only ever mocked the ENTIRE
# function, proving everything EXCEPT the function." Here, the ATTACK IS REPLAYED end-to-end
# through the REAL CLI of this module (not `read_live_confirmation` directly) -- even from a
# DETACHED subprocess (`start_new_session=True`, no controlling terminal to inherit), exactly the
# shape of an agent that would try to run `make item-retirer ARGS="approuver ..."` on its own
# behalf.


def _forger_une_approbation_par_pipe(ledger_path: Path, id_: str, mot: bytes) -> int:
    """The forgery attempt: the word is pushed onto stdin, NO controlling terminal exists."""
    code = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {_LIB!r})
        from mnemosyne.runtime.plan_retrait_run import main
        sys.exit(main(["--ledger", {str(ledger_path)!r}, "approuver", "--id", {id_!r}]))
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        input=mot,
        capture_output=True,
        timeout=30,
        start_new_session=True,  # detached: no controlling terminal to inherit
        check=False,
    )
    return proc.returncode


def test_LE_SABOTAGE_DE_FORGE_un_mot_pousse_par_pipe_sans_terminal_N_APPROUVE_RIEN(
    tmp_path: Path,
) -> None:
    """The forgery fails -- through the REAL CLI, a REAL detached subprocess, the REAL gate."""
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1",), motif="duplicate of Z9", cout="none", requested_by="c1")
    )
    for mot in (b"oui\n", b"OUI\n", b"o\n"):
        rc = _forger_une_approbation_par_pipe(ledger_path, id_, mot)
        assert rc != 0, (
            f"the word {mot!r} pushed via pipe made it LOOK like an approval happened (rc={rc})"
        )
        # Re-read FROM DISK, in THIS process -- not the subprocess's own output, which an
        # attacker could forge separately. It is the STATE that must stay intact.
        assert RetraitLedger(ledger_path).state(id_).stage == "depose"


def test_LE_SABOTAGE_DE_FORGE_NE_CORROMPT_RIEN_meme_apres_plusieurs_essais(
    tmp_path: Path,
) -> None:
    """The forgotten second half: the motif AND the cost stay exactly what was filed, never
    altered by the attempt -- a forgery that fails partway must not let anything drift either.

    DELEGATED AUDIT OF 2026-08-15 (RE-AUDIT): this witness used to be called
    ...ne_laisse_AUCUNE_trace..., a title that today asserts the OPPOSITE of the intended
    behavior -- since the fix to the third member of the clause, the forgery leaves EXACTLY 3
    traces (one `denied` event per attempt), and that is the POINT of the fix. Renamed to say
    what remains true (nothing is CORRUPTED); what this title used to wrongly claim (no trace at
    all) is now covered by the assertions below, in the opposite direction.
    """
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(
            items=("Z1", "Z2"), motif="duplicate of Z9", cout="1 hour", requested_by="c1"
        )
    )
    for _ in range(3):
        _forger_une_approbation_par_pipe(ledger_path, id_, b"oui\n")
    etat = RetraitLedger(ledger_path).state(id_)
    assert etat.stage == "depose"
    assert etat.motif == "duplicate of Z9"
    assert etat.cout == "1 hour"
    assert etat.approved_at == ""
    assert etat.approved_content_hash == ""
    # The EXACT grievance from the audit that motivated the fix: hammering the gate should still
    # leave a NULL footprint. Verifies here that the COUNT tracks the hammering (3 attempts, 3
    # events) -- a `denied_count` frozen at 1 by an overwrite instead of an increment would miss
    # it.
    assert etat.denied_count == 3, f"3 forgery attempts, only {etat.denied_count} trace(s)"
    assert etat.last_denied_reason, "the last attempt must remain named"


# --- appliquer ------------------------------------------------------------------------------------


def test_appliquer_sans_confirm_est_un_DRY_RUN_qui_n_ecrit_rien(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    ledger_path = tmp_path / "l.jsonl"
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(_plan_minimal("Z1", "A1"), encoding="utf-8")
    avant = plan_path.read_text(encoding="utf-8")
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1",), motif="duplicate", cout="none", requested_by="c1")
    )
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", lambda prompt: True)
    _run(ledger_path, "approuver", "--id", id_)
    capsys.readouterr()
    assert _run(ledger_path, "appliquer", "--id", id_, "--fichier", str(plan_path)) == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert plan_path.read_text(encoding="utf-8") == avant
    assert ledger.state(id_).stage == "approuve"


def test_appliquer_avec_confirm_ecrit_et_relit_depuis_le_disque(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """**The second, often-forgotten half of clause H1**: the withdrawal writes the MOTIF and
    the COST, verified on a REAL withdrawal (the text that lands on disk), not on a function
    signature."""
    ledger_path = tmp_path / "l.jsonl"
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(_plan_minimal("Z1", "A1"), encoding="utf-8")
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(
            items=("Z1",),
            motif="distinctive duplicate of Z9",
            cout="12 minutes of proofreading",
            requested_by="c1",
        )
    )
    monkeypatch.setattr(plan_retrait, "read_live_confirmation", lambda prompt: True)
    _run(ledger_path, "approuver", "--id", id_)
    assert (
        _run(ledger_path, "appliquer", "--id", id_, "--fichier", str(plan_path), "--confirm") == 0
    )
    assert ledger.state(id_).stage == "applique"
    texte_disque = plan_path.read_text(encoding="utf-8")
    assert "distinctive duplicate of Z9" in texte_disque
    assert "12 minutes of proofreading" in texte_disque
    relu = read_plan(texte_disque)
    z1 = next(i for i in relu.items if i.ident == "Z1")
    assert z1.status == "clos"
    a1 = next(i for i in relu.items if i.ident == "A1")
    assert a1.status == "a_faire"  # the untargeted neighbor stays intact


def test_appliquer_sans_fichier_est_refuse_proprement(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "l.jsonl"
    ledger = RetraitLedger(ledger_path)
    id_ = ledger.file(
        RetraitDemande(items=("Z1",), motif="duplicate", cout="none", requested_by="c1")
    )
    assert _run(ledger_path, "appliquer", "--id", id_, "--fichier", "") == 2
    assert "FICHIER=" in capsys.readouterr().err
