"""`G1` — the outbound-sites freeze: what it sees, and what it refuses to guess.

 **THE HOLE THIS MECHANISM CLOSES IS WRITTEN IN `CLAUDE.md`** (inv. 5 / D156): *"Outside [...],
the Guard is an API one chooses to call: nothing stops an `import requests` from going out."*
Another project built it while the doctrine was documenting its absence -- G1 write-up from the 2026-09-08
harvest.

 **THE POPULATION IS INJECTED INTO EVERY JUDGING WITNESS**: the judge reads no file, so the
witnesses do not depend on the repo's state -- *a witness that freezes the current state turns
red the day the project moves forward*.
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.production import sites_de_sortie as sds


class TestJugePur:
    def test_un_site_NON_DECLARE_est_nomme(self) -> None:
        v = sds.verdict((sds.Site("a.py", "requests"),), frozenset())
        assert v.apparus == ("a.py::requests",)
        assert not v.tient

    def test_une_DECLARATION_SANS_SITE_est_nommee_aussi(self) -> None:
        """ The double difference: staying silent about disappearances would let the freeze ROT
 unseen, and a stale freeze ends up authorising everything."""
        v = sds.verdict((), frozenset({"mort.py::socket"}))
        assert v.disparus == ("mort.py::socket",)
        assert not v.tient

    def test_le_gel_EXACT_tient(self) -> None:
        """ THE PASSING CASE -- without it, a judge that ALWAYS returned a refusal would pass the
 two witnesses above."""
        v = sds.verdict((sds.Site("a.py", "socket"),), frozenset({"a.py::socket"}))
        assert v.tient and v.compares == 1

    def test_un_ECHANGE_ne_passe_PAS_alors_que_le_COMPTE_est_identique(self) -> None:
        """ THE HEART OF THE MECHANISM: the SET is frozen, never the COUNT. Removing one
 `subprocess` and adding one `requests` leaves 1 = 1 -- a ratchet on the cardinal alone
 would be MUTE here."""
        v = sds.verdict((sds.Site("a.py", "requests"),), frozenset({"a.py::subprocess"}))
        assert v.compares == 1 and len(v.disparus) == 1 and len(v.apparus) == 1
        assert not v.tient, "a swap at a constant count must turn RED"

    def test_le_CARDINAL_compare_est_publie(self) -> None:
        """*An equality over zero pairs is true by construction* — the count is the only thing
        that says whether the comparison actually TOOK PLACE."""
        assert sds.verdict((), frozenset()).compares == 0
        assert "NOT MEASURED" in sds.resume(sds.verdict((), frozenset()))

    def test_zero_site_n_est_JAMAIS_un_vert(self) -> None:
        """ An empty survey is an instrument failure (wrong path, empty tree). The `tient`
 verdict stays true by vacuity -- it is the SUMMARY that must refuse to read that as a
 green."""
        v = sds.verdict((), frozenset())
        assert v.tient is True  # true by vacuity, and that is precisely the trap
        assert "NOT MEASURED" in sds.resume(v)

    def test_le_resume_est_BORNE(self) -> None:
        vus = tuple(sds.Site(f"f{i}.py", "socket") for i in range(9))
        phrase = sds.resume(sds.verdict(vus, frozenset()), noms_max=3)
        assert phrase.count("::") == 3 and "and 6 others" in phrase

    def test_la_borne_de_PRODUCTION_est_gardee_pas_seulement_l_argument(self) -> None:
        """ CLASS REPRODUCED ONE HOUR AFTER CLOSING IT ELSEWHERE, AND FOUND BY SABOTAGE.
 The witness above passes `noms_max=3` explicitly: it proves ITS OWN ARGUMENT, never the
 value production actually uses. Mutating the default to 999 SURVIVED. *Checking one value
 does not protect the site that uses another* -- this is defect #3, which an isolated
 auditor had found that very morning on the neighbouring module."""
        vus = tuple(sds.Site(f"f{i}.py", "socket") for i in range(20))
        phrase = sds.resume(sds.verdict(vus, frozenset()))  # WITHOUT noms_max
        assert phrase.count("::") == 5, "the DEFAULT floor must be 5"
        assert "and 15 others" in phrase


class TestBordAST:
    def test_il_voit_import_et_from_import(self, tmp_path) -> None:
        (tmp_path / "a.py").write_text("import socket\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("from urllib.parse import quote\n", encoding="utf-8")
        cles = {s.cle() for s in sds.recenser(tmp_path)}
        assert cles == {"a.py::socket", "b.py::urllib.parse"}

    def test_il_IGNORE_ce_qui_ne_sort_pas(self, tmp_path) -> None:
        """ THE PASSING CASE for the edge: without it, a surveyor that returned EVERYTHING would
 pass the other witnesses."""
        (tmp_path / "a.py").write_text("import json\nfrom pathlib import Path\n", encoding="utf-8")
        assert sds.recenser(tmp_path) == ()

    def test_un_import_RELATIF_n_est_pas_une_sortie(self, tmp_path) -> None:
        """`from .http import x` targets a LOCAL module named http, never the stdlib."""
        (tmp_path / "a.py").write_text("from .http import client\n", encoding="utf-8")
        assert sds.recenser(tmp_path) == ()

    def test_un_fichier_qui_ne_PARSE_pas_est_saute_et_n_emporte_pas_le_lot(self, tmp_path) -> None:
        """*A per-item guarantee that raises kills the batch.*"""
        (tmp_path / "casse.py").write_text("def (:\n", encoding="utf-8")
        (tmp_path / "sain.py").write_text("import socket\n", encoding="utf-8")
        assert {s.cle() for s in sds.recenser(tmp_path)} == {"sain.py::socket"}

    def test_un_fichier_BINAIRE_est_saute(self, tmp_path) -> None:
        (tmp_path / "bin.py").write_bytes(b"\xff\xfe import socket\n")
        (tmp_path / "sain.py").write_text("import socket\n", encoding="utf-8")
        assert {s.cle() for s in sds.recenser(tmp_path)} == {"sain.py::socket"}


class TestGelReel:
    def test_le_gel_TIENT_sur_le_depot(self) -> None:
        """ The only witness that touches the real repo -- and it asserts NO number: freezing a
 cardinal here would turn red on every legitimately added site. It demands AGREEMENT, and
 that the comparison actually took place."""
        racine = Path(__file__).resolve().parents[2] / "system" / "lib"
        v = sds.verdict(sds.recenser(racine), sds.SITES_GELES)
        assert v.compares > 0, "an empty survey is an instrument failure, never a green"
        assert v.tient, sds.resume(v)

    def test_les_racines_de_sortie_sont_un_PLANCHER_declare(self) -> None:
        """The list does not claim to be exhaustive: an outbound module it ignores is not
        "allowed", it is UNSEEN. This witness pins down the most obvious roots so that a silent
        removal turns red."""
        for essentiel in ("requests", "socket", "subprocess", "urllib", "httpx", "asyncio"):
            assert essentiel in sds.RACINES_DE_SORTIE


class TestCablageDansLeTick:
    """ THE JUDGE CAN BE PERFECT AND UNPLUGGED -- and an unplugged judge looks exactly like a
 working one. Measured on 2026-09-08 on the neighbouring source: cutting its line in `run_tick`
 left 76 witnesses out of 76 GREEN. These witnesses guard the WIRE, not the judge."""

    def test_un_arbre_SANS_system_lib_est_un_SILENCE(self, tmp_path) -> None:
        """ "THIS IS NOT MY TERRITORY" IS NOT "MY INSTRUMENT IS BROKEN". Conflating the two made
 a neighbouring witness turn red within the first minute: the source shouted "not measured"
 on every tree without `system/lib`, hence on every repo that is not Mnemosyne."""
        from mnemosyne.runtime.tick import _sites_de_sortie

        assert _sites_de_sortie(tmp_path) is None

    def test_un_system_lib_VIDE_reste_une_alarme(self, tmp_path) -> None:
        """ THE BOUNDARY: the folder EXISTS and returns NO site at all -- that is an instrument
 failure, and it must stay noisy. Without this witness, the fix above could have been
 widened until it silenced everything."""
        from mnemosyne.runtime.tick import _sites_de_sortie

        (tmp_path / "system" / "lib").mkdir(parents=True)
        phrase = _sites_de_sortie(tmp_path)
        assert phrase is not None and "NOT MEASURED" in phrase

    def test_un_site_NON_DECLARE_traverse_jusqu_au_tick(self, tmp_path) -> None:
        """Is `run_tick`'s wire actually plugged in? Cutting it must turn red HERE."""
        from mnemosyne.runtime.tick import run_tick

        lib = tmp_path / "system" / "lib"
        lib.mkdir(parents=True)
        (lib / "fuite.py").write_text("import requests\n", encoding="utf-8")
        propositions = run_tick(knowledge_root=tmp_path, repo_root=tmp_path)
        assert any("outbound sites" in p.summary for p in propositions), (
            "the G1 source does not reach run_tick — the wiring is cut"
        )

    def test_le_depot_REEL_reste_silencieux(self) -> None:
        """ THE PASSING CASE for the wiring -- without it, a source that ALWAYS spoke up would
 pass the witness above and the tick would publish noise on every single startup."""
        from pathlib import Path as _P

        from mnemosyne.runtime.tick import _sites_de_sortie

        assert _sites_de_sortie(_P(__file__).resolve().parents[2]) is None
