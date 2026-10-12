"""``make reprise`` — the STARTUP hook: what it ranks, and what it admits.

**THIS FILE IS THIS MODULE'S FIRST WITNESS.** It has run at the start of EVERY session for
weeks and had no test suite at all. The two defects it holds were measured on 2026-09-08, by
pulling it for real:

1. **It was pushing a SANDBOX's state.** The ranking ran on the handoff's ``mtime`` — but a
   COPY refreshes an mtime without producing anything. Measured: 11 bubbles, the REAL project
   ranked **LAST**, behind a `tmpm6umirfm` and three audit clones.
2. **It was serving a FRESH derived state for a STALE command** without saying so. The handoff
   of the only bubble that declares anything was 25 days and 1,922 commits old.
"""

from __future__ import annotations

from mnemosyne.runtime import reprise as r


class TestPhrasePeremption:
    """The PURE JUDGE of freshness — no disk access, no git."""

    def test_a_jour_quand_aucun_commit_depuis_le_bilan(self) -> None:
        assert "up to date" in r.phrase_peremption(0, 0)

    def test_non_mesuree_n_est_PAS_un_silence(self) -> None:
        """"the handoff is fresh" and "I couldn't look" don't read the same."""
        phrase = r.phrase_peremption(None, None)
        assert "NOT MEASURED" in phrase
        # We test the SUBSTANCE, not a substring: the sentence QUOTES "up to date" to say
        # it is NOT that verdict. A bare `"up to date" not in phrase` would turn red on its own
        # explanation — *a TEXT detector counts citations.*
        assert not phrase.startswith("handoff freshness: up to date")
        assert phrase != r.phrase_peremption(0, 0)

    def test_une_seule_moitie_absente_suffit_a_ne_pas_conclure(self) -> None:
        assert "NOT MEASURED" in r.phrase_peremption(12, None)
        assert "NOT MEASURED" in r.phrase_peremption(None, 12)

    def test_le_chiffre_REEL_traverse(self) -> None:
        """The real measured case: the sentence carries BOTH numbers, never a verdict alone."""
        phrase = r.phrase_peremption(25, 1922)
        assert "25 days" in phrase and "1922 commits" in phrase

    def test_le_singulier_est_correct(self) -> None:
        phrase = r.phrase_peremption(1, 1)
        assert "1 day " in phrase and "1 commit " in phrase

    def test_aucun_seuil_n_est_invente(self) -> None:
        """This module PUBLISHES, it doesn't judge: an invented ceiling here would turn a
        measurement into a verdict. A single commit's gap must already carry the warning — so
        the sentence depends on no hidden bound."""
        assert r.phrase_peremption(0, 1).startswith("\U000026A0\U0000FE0F")
        assert r.phrase_peremption(999, 99999).startswith("\U000026A0\U0000FE0F")


class TestClassementParHistoire:
    """THE MEASURED DEFECT: a COPY refreshes an mtime without producing anything."""

    def _bulle(self, racine, nom: str, mtime: float) -> None:
        d = racine / "saas" / nom / "state"
        d.mkdir(parents=True)
        f = d / "FIN-DE-SESSION.md"
        f.write_text("---\nreprise: x.py\n---\n", encoding="utf-8")
        import os

        os.utime(f, (mtime, mtime))

    def test_le_scratch_au_mtime_FRAIS_perd_contre_le_projet_qui_COMMITTE(
        self, tmp_path, monkeypatch
    ) -> None:
        """The exact case from 2026-09-08, reduced: the sandbox has the most recent mtime and
        the real project the oldest one — it's HISTORY that must decide, not the disk."""
        self._bulle(tmp_path, "scratch-tmp", mtime=2_000_000_000)  # the MOST RECENT mtime
        self._bulle(tmp_path, "real-project", mtime=1_000_000_000)  # the OLDEST one
        monkeypatch.setattr(r, "BULLES", tmp_path)
        monkeypatch.setattr(r, "_est_une_bulle", lambda d: True)
        monkeypatch.setattr(
            r, "_dernier_commit", lambda d: 9_000 if d.name == "real-project" else 1_000
        )
        assert [b.name for b in r.bulles()] == ["real-project", "scratch-tmp"]

    def test_une_bulle_SANS_histoire_lisible_ne_gagne_jamais(self, tmp_path, monkeypatch) -> None:
        """``_dernier_commit`` returns 0 when git is silent: the bubble ranks LAST, never first
        — *a bubble nobody can confirm is alive doesn't win the freshness contest.*"""
        self._bulle(tmp_path, "silent", mtime=2_000_000_000)
        self._bulle(tmp_path, "alive", mtime=1_000_000_000)
        monkeypatch.setattr(r, "BULLES", tmp_path)
        monkeypatch.setattr(r, "_est_une_bulle", lambda d: True)
        monkeypatch.setattr(r, "_dernier_commit", lambda d: 0 if d.name == "silent" else 5_000)
        assert [b.name for b in r.bulles()] == ["alive", "silent"]

    def test_le_mtime_departage_a_egalite_d_histoire(self, tmp_path, monkeypatch) -> None:
        """THE PASSING CASE for mtime — without it, a ranking that IGNORED it entirely would
        pass the two witnesses above."""
        self._bulle(tmp_path, "a-recent", mtime=2_000_000_000)
        self._bulle(tmp_path, "b-old", mtime=1_000_000_000)
        monkeypatch.setattr(r, "BULLES", tmp_path)
        monkeypatch.setattr(r, "_est_une_bulle", lambda d: True)
        monkeypatch.setattr(r, "_dernier_commit", lambda d: 7_000)  # strict tie
        assert [b.name for b in r.bulles()] == ["a-recent", "b-old"]

    def test_aucune_bulle_rend_une_liste_vide(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(r, "BULLES", tmp_path / "absent")
        assert r.bulles() == []


class TestBordPeremption:
    """The edge reads git; it must NEVER raise — this batch is the whole startup hook."""

    def test_un_dossier_sans_git_rend_non_mesurable(self, tmp_path) -> None:
        assert r._mesure_peremption(tmp_path) == (None, None)


class TestDernierCommit:
    """The EDGE of the ranking — monkeypatched everywhere else, so WITHOUT A WITNESS without
    this class.

    Found by sabotage: mutating ``_dernier_commit`` killed NO witness, because the ranking
    witnesses inject it. *A function that gets replaced everywhere is never actually proven.*
    """

    def test_un_dossier_SANS_git_rend_zero_donc_perd(self, tmp_path) -> None:
        """0 is the floor that sends the bubble to LAST place — never a high value."""
        assert r._dernier_commit(tmp_path) == 0

    def test_un_vrai_depot_rend_un_horodatage_positif(self, tmp_path) -> None:
        """THE PASSING CASE: without it, a `_dernier_commit` that ALWAYS returned 0 would pass
        the witness above, and the ranking by history would become a ranking by a silent mtime."""
        import subprocess

        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(tmp_path),
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, env=env, check=True)
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, env=env, check=True)
        subprocess.run(["git", "commit", "-qm", "c"], cwd=tmp_path, env=env, check=True)
        assert r._dernier_commit(tmp_path) > 0
