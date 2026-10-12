"""I6 — `make rendement`: the command that reads two populations out of the transcripts.

The judge is already covered by ``test_rendement.py``. What nothing else arms is the EDGE: how it
builds its populations, and above all **what it does when it finds none at all**.

**The feared defect is not a wrong number, it is a number that STOPS BEING TAKEN.** This command
searches, inside text, for the header the hook prints. The day that phrase moves, the measurement
drops to zero — and a table of zeros reads exactly like "the loop no longer detects anything". The
two barriers held here are therefore: the header is **derived** from the module instead of being
copied, and an empty population **refuses** instead of publishing.
"""

from __future__ import annotations

import json
from pathlib import Path

from mnemosyne.runtime import rendement_run


def _transcript(dossier: Path, nom: str, evenements: list[tuple[str, str]]) -> Path:
    """A transcript with the real shape: (text, timestamp) per line."""
    chemin = dossier / f"{nom}.jsonl"
    chemin.write_text(
        "\n".join(
            json.dumps(
                {
                    "type": "user",
                    "timestamp": stamp,
                    "message": {"content": [{"type": "text", "text": texte}]},
                }
            )
            for texte, stamp in evenements
        )
        + "\n",
        encoding="utf-8",
    )
    return chemin


def _bloc_signal() -> str:
    """The block the hook REALLY prints when it detects — never an imitation written here."""
    from mnemosyne.production.review_signals import Signal, render_review

    return render_review((Signal(kind="correction", quote="ah non", advice="x"),))


RITUEL = "[Mnemosyne · essence ritual] This task wrote to the repo"  # the hook's REAL label


# --- it separates the two populations on the ONLY criterion that distinguishes them -------------
def test_une_fin_de_tache_AVEC_signal_et_une_SANS_sont_separees(tmp_path: Path) -> None:
    _transcript(
        tmp_path,
        "s1",
        [
            (_bloc_signal() + "\n" + RITUEL, "2026-08-15T10:00:00Z"),  # with
            (RITUEL, "2026-08-15T11:00:00Z"),  # without
        ],
    )

    avec, sans = rendement_run.populations(tmp_path)

    assert len(avec) == 1
    assert len(sans) == 1


def test_un_tour_SANS_rituel_n_est_pas_une_fin_de_tache(tmp_path: Path) -> None:
    """The ritual is what MARKS the boundary. An ordinary turn is not one, and counting it would
    inflate the witness with thousands of moments that are not task ends."""
    _transcript(tmp_path, "s1", [("we are talking about the weather", "2026-08-15T10:00:00Z")])

    assert rendement_run.populations(tmp_path) == ([], [])


def test_le_bloc_REJOUE_dans_le_contexte_ne_compte_QU_UNE_FOIS(tmp_path: Path) -> None:
    """The host copies the block into the context of later turns. Measured: 73 occurrences for 55
    distinct instants. Counting occurrences would inflate the population by a factor unrelated to
    the number of task ends — and the published rate along with it."""
    bloc = _bloc_signal() + "\n" + RITUEL
    _transcript(
        tmp_path,
        "s1",
        [(bloc, "2026-08-15T10:00:00Z"), (bloc, "2026-08-15T10:00:00Z")],  # same instant
    )

    avec, _ = rendement_run.populations(tmp_path)

    assert len(avec) == 1


# --- THE barrier: an empty population REFUSES, it does not publish zeros ------------------------
def test_aucune_population_REFUSE_au_lieu_d_imprimer_un_tableau_de_zeros(
    tmp_path, capsys, monkeypatch
) -> None:
    """A null population does NOT mean "the loop no longer detects anything": it means the
    marker being searched for has moved. Both read the same on a table of zeros, and that is how
    a measurement stops being taken without anything turning red.

    The `monkeypatch` is the FIX for a first version of this witness: without it, the folder
    did not exist under the transcript root and the refusal fell for THAT reason instead. It
    passed, while measuring the wrong branch. *A witness that passes for the wrong reason
    certifies a guarantee that does not exist.*
    """
    monkeypatch.setattr(rendement_run, "DEFAULT_TRANSCRIPT_ROOT", tmp_path.parent)
    (tmp_path / "vrai-transcript.jsonl").write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-08-15T10:00:00Z",
                "message": {"content": [{"type": "text", "text": "a turn WITHOUT the ritual"}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    code = rendement_run.main(["--projet", tmp_path.name])
    sortie = capsys.readouterr()

    assert code == 1
    assert "with a signal" not in sortie.out  # NO table published
    assert "This is NOT" in sortie.err  # it says what it does NOT mean


def test_le_refus_NOMME_ce_qu_il_a_cherche(tmp_path, capsys, monkeypatch) -> None:
    """A refusal that does not name the marker lets the reader conclude "it's broken" instead of
    "the phrase moved"."""
    monkeypatch.setattr(rendement_run, "DEFAULT_TRANSCRIPT_ROOT", tmp_path.parent)
    (tmp_path / "nothing.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": "2026-08-15T10:00:00Z",
                    "message": {"content": [{"type": "text", "text": "hello"}]}}) + "\n",
        encoding="utf-8",
    )

    code = rendement_run.main(["--projet", tmp_path.name])
    err = capsys.readouterr().err

    assert code == 1
    assert "marker" in err
    assert "essence ritual" in err  # it NAMES what it was searching for


# --- the header is DERIVED, never copied ---------------------------------------------------------
def test_l_entete_cherche_vient_du_module_pas_d_une_copie() -> None:
    """A constant copied from the hook's output is a SECOND SOURCE that drifts silently. This test
    fails if someone hardcodes it here: it compares against the module's real rendering."""
    from mnemosyne.production.review_signals import Signal, render_review

    entete = rendement_run._entete_du_signal()

    assert entete
    assert entete in render_review((Signal(kind="correction", quote="q", advice="a"),))


def test_le_RITUEL_cherche_est_bien_CELUI_QUE_LE_HOOK_EMET() -> None:
    """The sibling of the test above, and it was MISSING while its twin existed ten lines away.

    `_entete_du_signal()` is DERIVED from the renderer, and its docstring already names the exact
    failure: *"a constant copied from the hook's output is a second source that drifts silently:
    the day the wording changes, this command measures zero and reads as 'the loop detects nothing
    any more'."* The author wrote the diagnosis, built the barrier for ONE of the two needles, and
    left the other hand-written -- which then drifted exactly as predicted: the module searched for
    the pre-translation label while the hook emitted the translated one, `populations()` returned
    `with=0 without=0` on a real transcript, and `main()` took the refusal branch in silence.

    No derivation is available for this needle -- the producer is a SHELL script, not a renderer --
    so the barrier available here is a PAIR WITNESS: both files ship, so they can be compared.
    """
    hook = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "stop.sh"
    # NOT a skip when the file is missing. A witness that goes quiet because its subject vanished
    # is the very defect this module's own docstring warns about: "a measurement that STOPS BEING
    # TAKEN". If the hook is gone, either it stopped shipping or it moved -- both need a human.
    assert hook.is_file(), (
        f"{hook} is missing: `_RITUEL` now searches transcripts produced by nothing this "
        "repository ships. Either the hook stopped shipping, or it moved and this pair is broken."
    )
    emis = hook.read_text(encoding="utf-8")
    assert rendement_run._RITUEL in emis, (
        f"`_RITUEL` = {rendement_run._RITUEL!r} appears NOWHERE in the hook that produces the "
        "transcripts it searches. The command would measure zero and report 'nothing detected'."
    )


def test_un_transcript_illisible_ne_coute_que_lui_meme(tmp_path: Path) -> None:
    """A transcript still being written has a torn last line."""
    _transcript(tmp_path, "sain", [(_bloc_signal() + RITUEL, "2026-08-15T10:00:00Z")])
    (tmp_path / "casse.jsonl").write_text('{"type": "user", "mess', encoding="utf-8")

    avec, _ = rendement_run.populations(tmp_path)

    assert len(avec) == 1  # the healthy one still passes
