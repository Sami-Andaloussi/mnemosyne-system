"""THE OUTBOUND-SITES FREEZE — what the code CAN reach, surveyed by AST and frozen by EQUALITY.

**THE HOLE THIS MODULE CLOSES IS WRITTEN IN `CLAUDE.md`, AND HAS BEEN THERE ALL ALONG.**
Verbatim (inv. 5 / D156): *"Outside (a project's own engine, a personal script), the Guard is an
API one chooses to call: **nothing stops an `import requests` from going out**."* So the doctrine
documented its own blind spot — and **the research project built the barrier while it was being written up as
absent** (`validation/fuite/fuite_gel_residus.py`, `[F9.7]`, population frozen by equality,
18 → 21 → 29 → 37 sites, **bitten at least eleven times**, one of them on *the very instrument
written to measure it*). This is the write-up of that mechanism (harvested on 2026-09-08,
candidate G1).

**THIS IS A MODEL OF CAPABILITY, NEVER OF INTENT.** Whether a module *wants* to reach out is not
judged: what it *can* reach is surveyed. An `import subprocess` that only ever launches a `git log`
counts as a site, and that is intentional — *what is declared is seen; what is guessed is not.*

**THE BIAS IS DELIBERATE AND IT LEANS ONE WAY ONLY**, in the research project's own words: *"a false positive
on the DANGEROUS side costs one line, on the INNOCENT side it costs a HOLE."* So the freeze is
LARGE — `urllib.parse` (which only ever parses a string) is surveyed like the others. Declaring
one more site costs a line; forgetting one costs an invisible exit.

**THE SET IS FROZEN, NEVER THE COUNT.** A count is satisfied by a silent SWAP: removing one
`subprocess` and adding one `requests` would leave 28 = 28. The grain is `fichier::module`, and
the comparison is a DOUBLE difference — what appeared AND what disappeared, because a freeze that
does not see disappearances rots without ever turning red.

**THE POPULATION IS INJECTED, NEVER FETCHED.** :func:`verdict` reads no file — *a judge that
goes and fetches its own population can find it empty and return a green.* The only disk access is
:func:`recenser`, the edge, called by the runtime.

**WHAT THIS MODULE DOES NOT CLOSE, and saying so costs nothing**: it reads STATIC `import`
statements. An `__import__(built_name)`, an `importlib.import_module(variable)` or an `exec`
escape it — the same admitted scope as the research project's own guard. *This barrier protects against ACCIDENT
and drift, never against an adversary.*

Prose is French by design (D117). Decisions: inv. 1 (sensitive-stays-local) · inv. 5 / D156 (the
Guard is an API outside).
"""

from __future__ import annotations

import ast
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path

#: The module roots that grant an outbound CAPABILITY — network, process, or both.
#: **THIS LIST IS A FLOOR, NEVER A CEILING.** It does not claim to be exhaustive: an outbound
#: module it ignores is not "allowed", it is **unseen**. This is why the freeze bears on the SET
#: of sites found and not on this list — adding to it here makes new sites appear, and they stay
#: red until they are declared.
RACINES_DE_SORTIE: frozenset[str] = frozenset(
    {
        # -- generic network -------------------------------------------------------------------
        "aiohttp",
        "asyncio",
        "boto3",
        "ftplib",
        "http",
        "httpcore",
        "httpx",
        "paramiko",
        "pycurl",
        "requests",
        "socket",
        "socketserver",
        "ssl",
        "telnetlib",
        "urllib",
        "urllib3",
        "websocket",
        "websockets",
        "xmlrpc",
        # -- email ------------------------------------------------------------------------------
        "imaplib",
        "poplib",
        "smtplib",
        # -- process and native code -------------------------------------------------------------
        "ctypes",
        "multiprocessing",
        "pexpect",
        "pty",
        "subprocess",
        "webbrowser",
        # -- THE FOUR REAL EXITS OF THIS REPO, THAT v1 DID NOT SEE ----------------------------
        # They are exactly what inv. 5 names FIRST ("external / MODEL"), and `CLAUDE.md` calls
        # them a third-party cloud. An isolated audit measured that the v1 freeze surveyed
        # **zero** of them -- it weighed heavily on `urllib.parse` (6 of 27 entries, which only
        # ever parses a string) and lightly on what actually goes out. See the register.
        "anthropic",
        "openai",
        "qdrant_client",
        # -- remote databases and queues ----------------------------------------------------------
        "grpc",
        "psycopg",
        "psycopg2",
        "pymongo",
        "redis",
        "zmq",
    }
)

#: **THE SECOND GRAIN: THE ATTRIBUTE CALLED, NOT THE MODULE IMPORTED.**
#: `os` is imported by **46 files** here: declaring it as a root would add 46 noise sites and
#: drown the signal. But `os.system(f"curl ... {secret}")` IS an exit -- it is literally the
#: demonstration by which an isolated audit slipped an SSH key exfiltration past as `rc=0`.
#: So the **call** is frozen, not the import. Measured on 2026-09-08: **zero calls** in
#: `system/lib`, so this freeze starts EMPTY and **any future appearance turns it red**, for zero
#: noise.
APPELS_DE_SORTIE: frozenset[tuple[str, str]] = frozenset(
    {
        ("os", "system"),
        ("os", "popen"),
        ("os", "execl"),
        ("os", "execle"),
        ("os", "execlp"),
        ("os", "execv"),
        ("os", "execve"),
        ("os", "execvp"),
        ("os", "execvpe"),
        ("os", "fork"),
        ("os", "forkpty"),
        ("os", "posix_spawn"),
        ("os", "posix_spawnp"),
        ("os", "spawnl"),
        ("os", "spawnv"),
        ("os", "spawnve"),
        ("os", "startfile"),
        ("shutil", "unpack_archive"),  # extracts a remote archive to an arbitrary path
        ("importlib", "import_module"),  # the admitted escape hatch: an import computed at runtime
    }
)


#: **THE FROZEN SET OF OUTBOUND SITES, AS OF 2026-09-08 — 38 sites.**
#: **THIS FIGURE IS HELD BY A WITNESS** (`test_le_COMPTE_ECRIT_dans_la_docstring_dit_vrai`),
#: because it LIED: it said 35 when `len(SITES_GELES)` was actually 38, and nothing checked it —
#: `grep -rn "len(SITES_GELES)" tests/` returned zero. *A figure recopied into prose needs a gate,
#: even right beside the code it describes.* This is the `P6` write-up applied to the `G1`
#: write-up.
#: Each entry is a `fichier::module` that the repo CAN reach. **Adding a site here is the normal
#: gesture** when a legitimate one is introduced; what must never happen is a site appearing
#: WITHOUT anyone noticing.
#:
#: **THE SET IS FROZEN, NEVER THE COUNT**: a count is satisfied by a silent SWAP -- removing one
#: `subprocess` and adding one `requests` would leave 27 = 27.
#:
#: **This freeze deliberately contains INNOCUOUS sites** (`urllib.parse` only ever parses a
#: string, `subprocess` often only ever launches a `git log`). This is the deliberate bias: *a
#: false positive on the dangerous side costs one line, on the innocent side it costs a HOLE.*
#:
#: **AND THE BIAS HAD INVERTED ITSELF WITHOUT ANYONE SEEING IT.** v1 froze 27 sites, of which
#: **6 were `urllib.parse`** and **zero were a model client**: it weighed heavily on the innocuous
#: and lightly on the dangerous. An isolated audit measured this by dropping an SSH key
#: exfiltration into `system/lib` -- the gate returned `rc=0` and the tick stayed silent.
#: *Declaring a bias does not check it; only CONFRONTING the list with the REAL repo does.*
SITES_GELES: frozenset[str] = frozenset(
    {
        "mnemosyne/guard/egress_prefix.py::urllib.parse",
        "mnemosyne/guard/redact.py::urllib.parse",
        "mnemosyne/guard/secrets_sops.py::subprocess",
        "mnemosyne/ingest/caption_anthropic.py::anthropic",
        "mnemosyne/ingest/figure_image.py::urllib.parse",
        "mnemosyne/ingest/source_whisper.py::urllib.request",
        "mnemosyne/ingest/youtube.py::urllib.parse",
        "mnemosyne/production/public_mirror.py::subprocess",
        "mnemosyne/runtime/backup_kopia.py::subprocess",
        "mnemosyne/runtime/conseiller.py::subprocess",
        # 2026-09-08 (lot 2, item P6) — the agreement of recopied figures: `git ls-files` to
        # survey the sites, `git log -1` to date them. Read-only, argument list.
        "mnemosyne/runtime/accord_chiffre_run.py::subprocess",
        # 2026-09-08 (lot 2, item G4) — the test battery that cannot melt down: it RE-RUNS
        # pytest and reads its report. That is its whole reason to exist; with no process exit,
        # it could only take some other report's word for it.
        "mnemosyne/runtime/batterie_run.py::subprocess",
        "mnemosyne/runtime/derive_run.py::subprocess",
        # 2026-09-08 (lot 2, item G8) — the diffusion buffer: `git rev-parse`, `git status`
        # and `git merge-base --is-ancestor` to PROVE that the receiver has the history the
        # rule was measured on. Read-only.
        "mnemosyne/runtime/diffusion_run.py::subprocess",
        "mnemosyne/runtime/documents_run.py::subprocess",
        # 2026-09-08 (lot 2, item P9) — the edge of the "declared closure ↔ glyph flip" barrier:
        # `git diff --cached`, `git show <ref>:<path>` and `git log -1`. Read-only access to the
        # INDEX and the history, no writes, argument list, never `shell=True`.
        "mnemosyne/runtime/fermeture_declaree_run.py::subprocess",
        "mnemosyne/runtime/garde_shell_run.py::subprocess",
        # 2026-09-08 (lot 2, item P5) — the commit watcher: `git rev-parse HEAD` to PROVE that
        # HEAD has moved, and the launch of the guarded command. Argument list, never
        # `shell=True` — a shell would reopen the pipe door this module exists to close.
        "mnemosyne/runtime/guetteur_commit.py::subprocess",
        "mnemosyne/runtime/local_first.py::http.client",
        "mnemosyne/runtime/local_first.py::socket",
        "mnemosyne/runtime/local_first.py::urllib.parse",
        "mnemosyne/runtime/orphelins_run.py::subprocess",
        # 2026-09-08 (lot 2, item G10) — the edge of the handover: `git status --porcelain`, the
        # DURABILITY half of a peer's independent measurement. Read-only, no writes.
        "mnemosyne/runtime/passation_run.py::subprocess",
        # 2026-09-08 (lot 2, item P4) — the edge of the rotation ceiling: `git diff --cached`,
        # `git show :<path>` and `git ls-files`. Read-only access to the INDEX, no writes.
        "mnemosyne/runtime/plafond_rotation_run.py::subprocess",
        "mnemosyne/runtime/plan_archiver_run.py::subprocess",
        "mnemosyne/runtime/plan_duree_run.py::subprocess",
        "mnemosyne/runtime/plan_recul_run.py::subprocess",
        "mnemosyne/runtime/qdrant_run.py::http.client",
        "mnemosyne/runtime/qdrant_run.py::subprocess",
        "mnemosyne/runtime/qdrant_run.py::urllib.parse",
        "mnemosyne/runtime/rendement_run.py::subprocess",
        "mnemosyne/runtime/reprise.py::subprocess",
        "mnemosyne/runtime/routage_journal_run.py::subprocess",
        "mnemosyne/runtime/runner_anthropic.py::anthropic",
        "mnemosyne/runtime/runner_openai.py::openai",
        "mnemosyne/stores/vector_qdrant.py::qdrant_client",
        "mnemosyne/tools/mcp_client.py::asyncio",
        "mnemosyne/tools/sandbox_seatbelt.py::subprocess",
    }
)


@dataclass(frozen=True, slots=True)
class Site:
    """An outbound site: a FILE and the MODULE it imports. Nothing else.

    Deliberately sparse: no line, no context, no code. What does not go in here cannot leak into
    a published export (inv. 22) — and the `fichier::module` grain is the one that survives a
    line moving, where a line number would turn red on every reformat."""

    fichier: str
    module: str

    def cle(self) -> str:
        return f"{self.fichier}::{self.module}"


@dataclass(frozen=True, slots=True)
class Verdict:
    """The two differences, and the CARDINAL compared."""

    apparus: tuple[str, ...]
    disparus: tuple[str, ...]
    compares: int

    @property
    def tient(self) -> bool:
        return not self.apparus and not self.disparus


def verdict(vus: Iterable[Site], geles: Collection[str]) -> Verdict:
    """The PURE JUDGE — it reads nothing, it compares two sets.

    **DOUBLE DIFFERENCE, CARDINAL INCLUDED.** ``apparus`` are the sites no declaration covers;
    ``disparus`` are the declarations no site justifies anymore — staying silent about them would
    let the freeze rot unseen, and a stale freeze ends up authorising everything. ``compares`` is
    published **because it is the only thing that says whether the comparison actually TOOK
    PLACE**: *an equality over zero pairs is true by construction.*"""
    cles = {s.cle() for s in vus}
    attendus = set(geles)
    return Verdict(
        apparus=tuple(sorted(cles - attendus)),
        disparus=tuple(sorted(attendus - cles)),
        compares=len(cles),
    )


def resume(v: Verdict, *, noms_max: int = 5) -> str:
    """The sentence that gets published — it NAMES, and it always says how many it judged."""
    if v.compares == 0:
        return (
            "\U000026A0\U0000FE0F OUTBOUND SITES NOT MEASURED: zero site compared. \"no undeclared site\" and "
            "\"I could not look\" do not read the same — an empty survey is an instrument "
            "failure, never a green."
        )
    if v.tient:
        return f"outbound sites: {v.compares} surveyed, all declared."

    def _liste(xs: tuple[str, ...]) -> str:
        montres = list(xs[:noms_max])
        reste = len(xs) - len(montres)
        return " · ".join(montres) + (
            f" (and {reste} other{'s' if reste > 1 else ''})" if reste else ""
        )

    morceaux = []
    if v.apparus:
        morceaux.append(f"{len(v.apparus)} NOT DECLARED site(s): {_liste(v.apparus)}")
    if v.disparus:
        morceaux.append(f"{len(v.disparus)} declaration(s) with NO SITE: {_liste(v.disparus)}")
    return (
        f"\U000026D4 outbound sites ({v.compares} compared) — "
        + " ; ".join(morceaux)
        + ". A DECLARED site is seen; a forgotten one is an invisible exit. Update the freeze "
        "in `sites_de_sortie.SITES_GELES` with the dated reason."
    )


def recenser(racine: Path) -> tuple[Site, ...]:
    """The EDGE — the only disk access. It reads, it does not judge.

    A file that fails to parse or fails to read is **SKIPPED**, never guessed at: *a per-item
    guarantee that raises kills the batch*. And a skipped file is an **unseen** site, not an
    absent one — that is the limit of every static detector, and it is real."""
    sites: list[Site] = []
    for chemin in sorted(racine.rglob("*.py")):
        try:
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            continue
        rel = str(chemin.relative_to(racine)) if chemin.is_relative_to(racine) else str(chemin)
        for noeud in ast.walk(arbre):
            noms: list[str] = []
            if isinstance(noeud, ast.Import):
                noms = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.module and noeud.level == 0:
                noms = [noeud.module]
                # `from os import system`: the module is innocent, the ATTRIBUTE is not.
                base = noeud.module.split(".")[0]
                for alias in noeud.names:
                    if (base, alias.name) in APPELS_DE_SORTIE:
                        sites.append(Site(fichier=rel, module=f"{base}.{alias.name}()"))
            # `os.system` — whether it is CALLED or only BOUND (`f = os.system` exits just the same).
            elif isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name):
                if (noeud.value.id, noeud.attr) in APPELS_DE_SORTIE:
                    sites.append(Site(fichier=rel, module=f"{noeud.value.id}.{noeud.attr}()"))
            for nom in noms:
                if nom.split(".")[0] in RACINES_DE_SORTIE:
                    sites.append(Site(fichier=rel, module=nom))
    return tuple(sorted(set(sites), key=lambda s: s.cle()))
