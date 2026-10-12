"""THE CENSUS OF THE COMMIT GATE'S PASSES (G3 candidate from the research project's harvest).

> *"two freshly wired passes whose removal **left the repository green**, with a
> `36/38` report whose denominator was `len(ran)`"* — the isolated audit that gave birth to
> `pass_census` on the research project.

**What this module freezes, and why here.** `.githooks/pre-commit` is the **only automatic judge
in this repository** — `pre-push` never fires (measured: `git remote -v` → **0 lines**, there is no
remote), and `/usr/bin/grep -cE "pytest|ruff|make test" .githooks/pre-commit` → **0**. This file
carries **5 refusal passes** (5 `sys.exit(1)`, 5 distinct `[pre-commit] …` headers, measured on
2026-09-08) and **nothing surveys them**: `/usr/bin/grep -rl "pass_census|PASS_CENSUS|PASSES_GELEES"
system/lib tests .githooks` → **0 files**. Removing one of these five blocks leaves the repository green.

## The TWO axes, and why one alone is not enough

* **WIRING** — does the pass exist in the judge's AST? A header that only lives in a
  comment or a docstring **is not wiring**: :func:`recenser` only accepts a string if it is
  **the argument of a call**.
* **EXECUTION (reachability)** — is the refusal site **reachable from the module**? This is
  the half a purely syntactic census cannot see, and the repository already carries it in
  memory, verbatim: *"the code that is WRITTEN is not the code that RUNS — a check moved into a
  function nobody calls keeps its rule, its signature and its printed output, so a
  static census must prove the EXECUTION of each site"*. Moving a refusal block into a function
  nobody calls leaves the WIRING axis **green**, and turns the EXECUTION axis **red**.

## THE DENOMINATOR IS THE FREEZE, NEVER WHAT WAS SEEN

This is the exact fault the research project's audit named (`36/38`, denominator `len(ran)`): a pass
that **disappears** shrinks the denominator, and the rate **climbs**. Here :func:`rendre` always
divides by ``len(PASSES_GELEES)`` — the hand-written table below, never the observed
population.

## What this module is NOT

It is not a copy of :mod:`~mnemosyne.production.sites_de_sortie` (G1, already in the repository):
that one freezes **imports** through a purely syntactic question and asks no reachability
question at all. The freeze verdict itself is not rewritten here — it lives in
:mod:`~mnemosyne.production.barriere_gelee` (G5), and this module **hands** it its two sets.

Source prose was originally French (repository convention D117). The judge is **PURE**: no disk
access, no `os.environ` — the hook's text is INJECTED by the boundary
(:mod:`mnemosyne.runtime.passes_run`)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Final

#: The header EVERY pass in the gate writes before refusing. It is the only convention the
#: hook already holds by itself (5 occurrences out of 5, measured), so it is the only key a
#: census can read without inventing a new discipline.
PREFIXE_ENTETE: Final = "[pre-commit]"

#: The marker for the python block INSIDE the shell hook. Anchored on the **heredoc
#: delimiter**, never on a line number or on the first `import`: *a block that is moved or
#: shortened carries a named anchor along with it*, and this hook has already grown from 400 to
#: 666 lines.
_HEREDOC: Final = re.compile(r"<<'PYEOF'\n(?P<corps>.*?)\nPYEOF\b", re.DOTALL)


@dataclass(frozen=True, slots=True)
class PasseDeclaree:
    """A pass the freeze requires: its stable name, and the text it writes when refusing.

    ``marqueur`` is a fragment of the `[pre-commit] …` header, chosen to survive a
    rewording of the full sentence — and **verified present** in the real hook by a witness,
    never assumed."""

    identifiant: str
    marqueur: str


#: **HAND-WRITTEN, NEVER DERIVED FROM WHAT IT CHECKS.** That is the whole property: a table
#: derived from the hook would always read "everything is fine," including the day the hook loses
#: a pass. The five passes of `.githooks/pre-commit`, recorded one by one on 2026-09-08
#: (`/usr/bin/grep -noE '\[pre-commit\][^"\\]*' .githooks/pre-commit` → 5 headers;
#: `/usr/bin/grep -nE 'sys\.exit\(1\)'` → 5 sites):
#:
#: TODO(public-mirror): needs human review -- this table's `marqueur` (and `identifiant`) values
#: are exact substrings of THIS PRIVATE repository's own `.githooks/pre-commit`, kept in French
#: and unchanged here for behavioral fidelity (rule 4). `.githooks/pre-commit` itself is on the
#: "never synced" list (hand-authored independently in this public mirror, per the sync SCOPE), so
#: this whole module -- and the production-value tests in test_recensement_des_passes.py sections
#: 3-4 that read the real hook file and hardcode these same French marker substrings -- describe a
#: private repository fact that will not correspond to the mirror's own, independently-authored
#: `.githooks/pre-commit`. A human should decide whether this module belongs in the public mirror
#: at all, or needs a mirror-specific PASSES table matching the mirror's own hook.
PASSES: Final[tuple[PasseDeclaree, ...]] = (
    PasseDeclaree("index_illisible", "`git ls-files` a echoue"),
    PasseDeclaree("bilan_perime", "table derivee PERIMEE"),
    PasseDeclaree("filiation_incomplete", "promotion incomplete"),
    PasseDeclaree("cycle_de_dependances", "cycle de dependances"),
    PasseDeclaree("plan_illisible", "plan illisible mis en scene"),
)

#: The frozen SET — **never a count**. A swap (one pass removed, another added)
#: would leave an identical, mute count; the set, by contrast, names both moves.
#: DERIVED from :data:`PASSES` (a single hand-written table), never from the hook.
PASSES_GELEES: Final[frozenset[str]] = frozenset(p.identifiant for p in PASSES)


@dataclass(frozen=True, slots=True)
class PasseVue:
    """What the census could establish about a declared pass, on BOTH axes."""

    identifiant: str
    cablee: bool
    atteignable: bool
    #: The name of the function carrying the refusal site, or ``""`` for the module body.
    portee: str = ""

    @property
    def vivante(self) -> bool:
        """A pass is only alive if it is written **and** reachable. Both, never just one."""
        return self.cablee and self.atteignable


@dataclass(frozen=True, slots=True)
class Recensement:
    """The complete census — what was seen, and what could not be.

    ``sites`` is the **cardinal**: the number of refusal sites found in the AST. It is published
    because it is the only thing that says whether the census actually **took place** — *a census
    at zero sites is an instrument failure, never a green* (the same rule as
    :attr:`~mnemosyne.production.sites_de_sortie.Verdict.compares`)."""

    passes: tuple[PasseVue, ...]
    non_declarees: tuple[str, ...]
    sites: int

    @property
    def vivantes(self) -> tuple[str, ...]:
        """The names of the passes that are actually alive — the input to :mod:`.barriere_gelee`.

        UNDECLARED passes enter here too, under their header: without them, the gap
        "the hook has a pass the freeze ignores" would be **structurally invisible**."""
        return tuple(
            sorted([p.identifiant for p in self.passes if p.vivante] + list(self.non_declarees))
        )


def extraire_le_python(source_shell: str) -> str | None:
    """The hook's python body, or ``None`` when the heredoc is not found **exactly once**.

    ``None`` is not "nothing to judge": the boundary turns it into an **instrument failure**
    (`rc 2`). Returning an empty string would parse an empty module, hence zero passes, hence
    five refusals — a false, noisy diagnosis instead of a correct one."""
    trouves = _HEREDOC.findall(source_shell)
    if len(trouves) != 1:
        return None
    return trouves[0]


def _portees(arbre: ast.Module) -> dict[ast.AST, str]:
    """``node -> name of the function containing it`` (``""`` for the module body)."""
    portee: dict[ast.AST, str] = {}

    def _descendre(noeud: ast.AST, nom: str) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            suivant = (
                enfant.name if isinstance(enfant, ast.FunctionDef | ast.AsyncFunctionDef) else nom
            )
            portee[enfant] = suivant
            _descendre(enfant, suivant)

    portee[arbre] = ""
    _descendre(arbre, "")
    return portee


def _appels(noeud: ast.AST) -> set[str]:
    """The names of functions called UNDER ``noeud`` — the grain of reachability."""
    noms: set[str] = set()
    for n in ast.walk(noeud):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            noms.add(n.func.id)
    return noms


def _portees_atteignables(arbre: ast.Module) -> frozenset[str]:
    """The scopes reachable **from the module body**, by transitive closure of calls.

    This is the EXECUTION axis, and it cannot be deduced from ANY text search: a function
    keeping its refusal block intact, but that nobody calls anymore, stays **perfectly
    grep-able**."""
    fonctions = {
        n.name: n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    #: The module body WITHOUT the function bodies: what the interpreter actually executes on
    #: load. A call written inside a dead function animates nothing.
    depuis_le_module: set[str] = set()
    for instruction in arbre.body:
        if isinstance(instruction, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        depuis_le_module |= _appels(instruction)

    atteintes: set[str] = {""}
    a_visiter = [nom for nom in depuis_le_module if nom in fonctions]
    while a_visiter:
        nom = a_visiter.pop()
        if nom in atteintes:
            continue
        atteintes.add(nom)
        a_visiter.extend(n for n in _appels(fonctions[nom]) if n in fonctions)
    return frozenset(atteintes)


def _entetes_ecrites(arbre: ast.Module, portee: dict[ast.AST, str]) -> tuple[tuple[str, str], ...]:
    """``(header, scope)`` for every `[pre-commit] …` that is the **argument of a call**.

    **UNDER A CALL, AND THAT IS HALF OF THE WIRING AXIS.** A docstring and a comment
    quote just as well as written code does; *a text detector counts citations as
    instances*. Here only a string that is actually **passed** to something counts.

    **UNDER the call, not just IN ARGUMENT POSITION — and this is a sabotage fix.**
    The first version only looked at ``n.args`` / ``n.keywords``: a BUILT header
    (``"[pre-commit] " + quoi``, an f-string, a ``"".join(...)``) was not seen, so the pass
    passed for ABSENT while it was refusing perfectly. A saboteur that widened the reading
    SURVIVED the witnesses — it made the module *more correct*, which no witness was saying to do."""
    trouves: list[tuple[str, str]] = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call):
            continue
        for sous_noeud in ast.walk(n):
            if isinstance(sous_noeud, ast.Constant) and isinstance(sous_noeud.value, str):
                if PREFIXE_ENTETE in sous_noeud.value:
                    trouves.append((sous_noeud.value, portee.get(n, "")))
    return tuple(trouves)


def _portees_qui_refusent(arbre: ast.Module, portee: dict[ast.AST, str]) -> frozenset[str]:
    """The scopes from which one can **exit with a non-zero code** — a refusal site, not a message.

    *A check that prints is not a barrier, it is a comment*: the hook itself says so in its
    header, having paid for the mistake. A pass whose header exists but whose
    `sys.exit` has vanished is therefore not wired."""
    portees: set[str] = set()
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call):
            continue
        cible = n.func
        nomme_exit = (isinstance(cible, ast.Attribute) and cible.attr == "exit") or (
            isinstance(cible, ast.Name) and cible.id == "exit"
        )
        if not nomme_exit or not n.args:
            continue
        code = n.args[0]
        if isinstance(code, ast.Constant) and code.value in (0, None):
            continue
        portees.add(portee.get(n, ""))
    return frozenset(portees)


def recenser(python: str, declarees: tuple[PasseDeclaree, ...] = PASSES) -> Recensement:
    """The PURE census — it takes python text, it returns a state. It reads no file.

    ``declarees`` is injectable **for the witnesses**, never for production: it is
    :data:`PASSES` that the boundary passes, and a separate witness judges that value."""
    arbre = ast.parse(python)
    portee = _portees(arbre)
    atteignables = _portees_atteignables(arbre)
    refusantes = _portees_qui_refusent(arbre, portee)
    entetes = _entetes_ecrites(arbre, portee)

    vues: list[PasseVue] = []
    apparies: set[str] = set()
    for declaree in declarees:
        sites = [(texte, ou) for texte, ou in entetes if declaree.marqueur in texte]
        apparies.update(texte for texte, _ in sites)
        # A pass is WIRED if its header is written in a scope that knows how to refuse, and
        # REACHABLE if that scope is joinable from the module. Both questions are about the
        # SAME scope: separating them across two different scopes would declare alive a
        # pass whose header lives here and whose refusal lives there.
        cablee = any(ou in refusantes for _, ou in sites)
        atteignable = any(ou in refusantes and ou in atteignables for _, ou in sites)
        ou_elle_vit = next((ou for _, ou in sites if ou in refusantes), "")
        vues.append(
            PasseVue(
                identifiant=declaree.identifiant,
                cablee=cablee,
                atteignable=atteignable,
                portee=ou_elle_vit,
            )
        )

    non_declarees = tuple(
        sorted(
            {texte.strip() for texte, ou in entetes if texte not in apparies and ou in refusantes}
        )
    )
    return Recensement(
        passes=tuple(vues),
        non_declarees=non_declarees,
        sites=len({ou for _, ou in entetes if ou in refusantes}),
    )


def rendre(r: Recensement, gelees: frozenset[str] = PASSES_GELEES) -> str:
    """The page — and the **denominator is the FREEZE**, never what the census saw.

    This is the exact fault named by the research project's audit (`36/38`, denominator `len(ran)`): dividing
    by what was seen makes the rate **climb** when a pass disappears."""
    if r.sites == 0:
        return (
            "\U000026A0\U0000FE0F PASSES NOT SURVEYED: zero refusal site found in the gate. « no pass "
            "lost » and « I could not read the gate » do not read the same way — an empty census "
            "is an instrument failure, never a green."
        )
    vivantes = [p for p in r.passes if p.vivante]
    lignes = [f"live passes: {len(vivantes)}/{len(gelees)} (denominator = THE FREEZE, not what was seen)"]
    muettes = [p for p in r.passes if not p.cablee]
    endormies = [p for p in r.passes if p.cablee and not p.atteignable]
    if muettes:
        lignes.append(
            "\U000026D4 "
            + f"{len(muettes)} frozen pass(es) ABSENT from the gate: "
            + ", ".join(p.identifiant for p in muettes)
        )
    if endormies:
        lignes.append(
            "\U000026D4 "
            + f"{len(endormies)} pass(es) WRITTEN but UNREACHABLE from the module: "
            + ", ".join(f"{p.identifiant} (in `{p.portee or '<module>'}`)" for p in endormies)
            + " — the code is there, it does not run."
        )
    if r.non_declarees:
        lignes.append(
            f"\U000025B6 {len(r.non_declarees)} pass(es) in the gate OUTSIDE the freeze — published, never "
            "refused: " + " · ".join(r.non_declarees) + ". Add them to `PASSES` "
            "(`system/lib/mnemosyne/production/recensement_des_passes.py`) so a future removal "
            "turns red."
        )
    return "\n".join(lignes)
