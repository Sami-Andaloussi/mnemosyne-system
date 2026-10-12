r"""THE SHELL GATE — the backtick the shell SWALLOWS in silence. A PURE judge.

> Another project, 2026-08-09, after doing it **twice in the same evening**: *"The lesson was cited,
> re-read, and not applied."*

## The defect, reproduced in one command

    python3 -c "print('BEFORE `docs/truc.md` AFTER')"
      → (eval): no such file or directory: docs/truc.md
      → BEFORE  AFTER

**The content is eaten AND the command SUCCEEDS.** This is not an error that announces itself,
it is mutilated output that looks normal — three fragments of a commit message lost without a
word. And this repository's style is saturated with backticks (`make arsenal`, `docs/…`): every
commit message is a minefield.

## Why a GATE and not a reminder — this is A2, measured on someone else

That project re-read the rule **on every turn**, in capital letters, in its own mandate. It violated it
twice in one evening. *A lesson with no barrier is a wish.* And by B3's dividing line — **what is
a prompt belongs to the agent, what refuses in code belongs to Mnemosyne** — this gate is on
Mnemosyne's side.

## What it refuses, and above all what it does NOT refuse

It refuses **the backtick**, and **only where the shell SUBSTITUTES it**:

* between **single quotes** → literal for the shell → **let through**;
* inside the body of a **quoted-delimiter heredoc** (``<<'EOF'``) → literal → **let through**
  (this is the way out the refusal message itself recommends: it must stay open);
* **escaped** by a backslash → literal → **let through**.

**`$( … )` is NOT refused, and that is deliberate.** It is the modern, legitimate form of
substitution: refusing it would produce false refusals constantly, and *a gate that wrongly
refuses gets disabled within the week* — we would have traded a silent defect for a dead gate.
The backtick, by contrast, is the **legacy** form: by 2026 it is almost always text someone
meant literally. Whoever really wants to substitute writes `$( … )`, and the refusal message says so.

**Pure** judge: it receives the command as a string and reads nothing. Source prose was
originally French (repository convention D117).

**HARDENING (2026-08-16, D75): PROVEN ON A POPULATION ITS AUTHOR DID NOT HAVE IN FRONT OF
THEM.** Every witness written with this module judged commands composed BY HAND by its own
author. `tests/platform/test_garde_shell.py
::test_eprouve_sur_de_VRAIS_messages_de_commit_de_CE_depot` replays the REAL commit messages of
this repository (uncurated text, multiple sessions, saturated with markdown backticks) wrapped in
the canonical pattern `git commit -F - <<'EOF' … EOF` — zero false refusals on the real sample.
And the second firing (`test_le_MEME_backtick_MORD_quand_le_delimiteur_n_est_PAS_quote`) confirms
that those same messages become dangerous again without the quoting — *a gate that never bites on
anything would pass the first firing just as well as a gate that works*.

## I8 — this file's second judge: `checkout`/`restore`/`reset --hard` on dirty state

> Chat 1, 2026-08-15: *"this exact fault is already documented SEVEN times since 2026-07-28, with
> an explicit 'how to apply' read before acting, and I did it again anyway."* — the 8th time.

`git checkout -- <file>` (and `restore`, and `reset --hard`) restores the working directory WITH
NO warning: the command SUCCEEDS, uncommitted content is LOST. A sabotage loop that restores the
sabotaged target does not distinguish the sabotage from the work sitting next to it — it erases
both. Eight repetitions are the experimental proof that repetition is not a barrier (A2).

**Here the judge is NOT pure**: unlike :func:`backticks_substitues`, knowing whether a target is
"dirty" requires reading the repository's REAL state (`git status --porcelain`), not just the
command's text. The split follows the same spirit: :func:`cibles_checkout_restore` and
:func:`contient_reset_hard` are PURE on the text alone (they return candidates, never a verdict);
it is the boundary (`garde_shell_run`, already this module's only I/O point for the hook's JSON)
that runs `git status` and cross-references the result. *The judge knows nothing of the world, the
boundary brings it to it* — the same dividing line as for the JSON.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

#: A heredoc: ``<<`` or ``<<-``, optional spaces, then the delimiter — **quoted or not**.
#: That is the only thing that decides whether the body is literal, and it is exactly the way
#: out the refusal recommends: it therefore must be recognized, or the gate would refuse its own
#: recommended fix.
_HEREDOC = re.compile(r"<<-?\s*(?:'([^']*)'|\"([^\"]*)\"|([A-Za-z_][A-Za-z0-9_]*))")


@dataclass(frozen=True, slots=True)
class Morsure:
    """A backtick the shell will substitute: its position, and the line where it can be read."""

    position: int
    ligne: int
    extrait: str


def backticks_substitues(commande: str) -> tuple[Morsure, ...]:
    """The backticks the shell WILL SUBSTITUTE. Empty when everything is literal.

    The scan follows quoting state character by character — it is the only way to
    distinguish ``'…`…'`` (literal) from ``"…`…"`` (substituted), and a ``<<'EOF'`` from a
    ``<<EOF``. A regular expression over the whole command would conflate the two, and would
    then refuse the very way out the refusal message recommends.

    **`$( … )` opens a STACK of contexts, and this is a measured fix, not a hypothesis**:
    `git commit -m "$(cat <<'EOF' … EOF)"` -- the pattern CLAUDE.md itself prescribes for THIS
    repository -- placed a QUOTED-delimiter heredoc inside a `$( … )` that was itself between
    double quotes. A single `etat` (state) could not see it: the gate stayed in `"double"` the
    whole way through and mistook the heredoc's literal body for substituted prose -- **it refused
    the very commit its own move 3 recommends**. In real bash, `$( … )` opens a command context
    INDEPENDENT of what surrounds it, quotes included -- hence the stack: every `$(`
    pushes a fresh `nu` (bare) context (its own quotes, its own heredoc), every `)` that
    balances it pops it."""
    morsures: list[Morsure] = []
    i, n = 0, len(commande)
    #: A stack of contexts, each entry `[state, local_paren_depth]`. The top is the active
    #: context; `$( … )` pushes a new one (always `nu`/bare, as at the start of a real command),
    #: a bare `(` in that context increments its depth (a subshell does NOT close the `$( … )`),
    #: and the `)` that brings that depth back to zero pops it -- THAT is the one that closes the
    #: `$( … )`.
    pile: list[list] = [["nu", 0]]
    heredoc_litteral: str | None = None
    heredoc_substitue: str | None = None
    while i < n:
        c = commande[i]
        etat = pile[-1][0]

        # The body of a heredoc: we walk it until its closing line.
        if heredoc_litteral is not None or heredoc_substitue is not None:
            fin = commande.find("\n", i)
            ligne_texte = commande[i : n if fin < 0 else fin]
            delim = heredoc_litteral if heredoc_litteral is not None else heredoc_substitue
            if ligne_texte.strip() == delim:
                heredoc_litteral = heredoc_substitue = None
            elif heredoc_substitue is not None:
                for k, ch in enumerate(ligne_texte):
                    if ch == "`":
                        morsures.append(_morsure(commande, i + k))
            i = n if fin < 0 else fin + 1
            continue

        if etat == "simple":
            if c == "'":
                pile[-1][0] = "nu"
            i += 1
            continue

        if c == "\\" and etat in ("nu", "double"):
            i += 2  # escaped: the next character is literal, backtick included
            continue

        if etat == "double":
            if c == '"':
                pile[-1][0] = "nu"
            elif c == "`":
                morsures.append(_morsure(commande, i))
            elif c == "$" and commande.startswith("$(", i):
                pile.append(
                    ["nu", 0]
                )  # $( … ) remains a command context, even inside quotes
                i += 2
                continue
            i += 1
            continue

        # "nu" (bare) state (at the top of the current stack)
        if c == "'":
            pile[-1][0] = "simple"
        elif c == '"':
            pile[-1][0] = "double"
        elif c == "`":
            morsures.append(_morsure(commande, i))
        elif c == "$" and commande.startswith("$(", i):
            pile.append(["nu", 0])
            i += 2
            continue
        elif c == "(" and len(pile) > 1:
            pile[-1][1] += 1  # a BARE subshell inside a $( … ): does not close it
        elif c == ")" and len(pile) > 1:
            if pile[-1][1] > 0:
                pile[-1][1] -= 1
            else:
                pile.pop()  # this ")" balances the "$(" that opened this context
        elif c == "<" and commande.startswith("<<", i):
            trouve = _HEREDOC.match(commande, i)
            if trouve:
                simple, double, nu = trouve.groups()
                if simple is not None or double is not None:
                    heredoc_litteral = simple if simple is not None else double
                else:
                    heredoc_substitue = nu
                fin_ligne = commande.find("\n", trouve.end())
                i = n if fin_ligne < 0 else fin_ligne + 1
                continue
        i += 1
    return tuple(morsures)


def _morsure(commande: str, position: int) -> Morsure:
    debut = commande.rfind("\n", 0, position) + 1
    fin = commande.find("\n", position)
    ligne_texte = commande[debut : len(commande) if fin < 0 else fin]
    return Morsure(
        position=position,
        ligne=commande.count("\n", 0, position) + 1,
        extrait=ligne_texte.strip()[:120],
    )


#: Splits a compound command into simple commands -- `&&`/`||` before the lone `|`, otherwise
#: `||` would get cut into two `|`.
_SEPARATEURS_SHELL = re.compile(r"&&|\|\||;|\n|\|")


def _segments_shell(commande: str) -> tuple[list[str], ...]:
    """Each simple command from `commande`, already tokenized -- tolerant, NEVER raises:
    unbalanced quotes return an EMPTY segment (unrecognized form -> this segment is ignored,
    fail-open by construction, never an exception that would propagate up to the boundary)."""
    segments: list[list[str]] = []
    for morceau in _SEPARATEURS_SHELL.split(commande):
        try:
            segments.append(shlex.split(morceau))
        except ValueError:
            segments.append([])
    return tuple(segments)


def _sans_prefixe_point_slash(chemin: str) -> str:
    return chemin[2:] if chemin.startswith("./") else chemin


def cibles_checkout_restore(commande: str) -> tuple[str, ...]:
    """The paths a `git checkout -- <path...>` or `git restore <path...>` in `commande` would
    target for restoration -- and therefore OVERWRITE if the path is DIRTY.

    PURE judge on the TEXT alone: it does NOT know which paths are dirty, that is the boundary's
    job (`garde_shell_run`) to cross-reference this result with `git status --porcelain`, exactly
    the way :func:`backticks_substitues` does not care whether the shell that will execute it is
    really bash.

    **Scope deliberately NARROW, and that is written down rather than discovered by surprise**:
    * `git checkout <path>` WITHOUT `--` is NOT recognized -- ambiguous with a branch name, and a
      false bite there would cost more than a missed real one (*we would rather miss a bite than
      block an innocent*). Only the unambiguous `--` form is judged.
    * `git restore --staged <path>` WITHOUT `--worktree` is NOT recognized: it only touches the
      INDEX, never the working directory -- nothing there is lost."""
    cibles: list[str] = []
    for mots in _segments_shell(commande):
        for i, mot in enumerate(mots):
            if mot != "git":
                continue
            reste = mots[i + 1 :]
            if not reste:
                continue
            sous, apres = reste[0], reste[1:]
            if sous == "checkout":
                if "--" in apres:
                    cibles.extend(apres[apres.index("--") + 1 :])
            elif sous == "restore":
                if "--staged" in apres and "--worktree" not in apres:
                    continue
                cibles.extend(a for a in apres if not a.startswith("-"))
    return tuple(dict.fromkeys(_sans_prefixe_point_slash(c) for c in cibles))


def contient_reset_hard(commande: str) -> bool:
    """`True` if `commande` contains a `git reset --hard`.

    It does NOT target a file: it threatens EVERYTHING `git status --porcelain` shows as dirty.
    Same pure scope as :func:`cibles_checkout_restore` -- it is the boundary that brings the list
    of dirty paths, this judge only recognizes the FORM in the text."""
    for mots in _segments_shell(commande):
        for i, mot in enumerate(mots):
            if mot == "git" and mots[i + 1 : i + 2] == ["reset"] and "--hard" in mots[i + 2 :]:
                return True
    return False


def contrat_emis(racine_mnemosyne: str) -> str:
    """The contract to install on an OTHER host — **the address, never a copy** (D163).

    **WHAT IS EMITTED IS A FIVE-LINE POINTER, NOT THE JUDGE.** Copying
    :func:`backticks_substitues` onto every host would produce as many versions as hosts, and
    they would drift — *a master→executor contract = ONE single code hearth, emitted to each
    host*. The emitted hook calls THIS module; if Mnemosyne improves it, the host inherits the
    improvement for free, and if Mnemosyne disappears, the hook **fails open**.

    ``racine_mnemosyne`` is **injected** by the boundary: this module does not know where it is
    installed, and a guessed path would be exactly the defect the gate fights."""
    return f"""\
# THE MNEMOSYNE SHELL GATE — to install on your side.
#
# \U000026D4\U000026D4 MOVE 0, AND IT COMES BEFORE EVERYTHING: ARE YOU ALREADY COVERED? Run, INSIDE YOUR SESSION:
#     echo "$CLAUDE_PROJECT_DIR"
# If that returns `{racine_mnemosyne}`, **YOU ARE ALREADY COVERED**: the hooks loaded are
# THAT folder's, not your repository's. INSTALL NOTHING. Check it in one shot:
#     printf '%s' '{{"tool_name":"Bash","tool_input":{{"command":"echo x"}}}}' | \\
#       "{racine_mnemosyne}/.claude/hooks/pre-tool-use.sh" ; echo "rc=$?"
#
# \U000026B0\U0000FE0F WHAT THIS MOVE 0 COST WHEN IT WAS MISSING (2026-08-09): a host installed the gate IN
# DUPLICATE while already covered. Its copy was NEVER loaded, and its only real effect was to
# make its OWN anti-exfiltration gate turn RED -- a hook that launches a subprocess toward code
# OUTSIDE its repository is exactly what that gate freezes -- and to BLOCK a commit.
# \U000026A0\U0000FE0F If your repository has a gate of that kind, this file DOES NOT BELONG in your tracked
# tree: it is a SESSION tool, not content. Put it outside the tree, or do not install it at all.
#
# What it does: it REFUSES a Bash command that contains a backtick the shell is going to
# SUBSTITUTE. The measurement that gave rise to it: two occurrences in one evening on another project,
# with the rule re-read IN CAPITAL LETTERS on every turn. The content is eaten AND the command
# SUCCEEDS -- nothing warns you.
#
# What it does NOT refuse, and this matters just as much: single quotes, a QUOTED-delimiter
# heredoc (<<'EOF'), an escaped backtick, and $( ... ). The last one is deliberate: it is the
# modern, legitimate form; refusing it would produce constant false refusals, and a gate that
# wrongly refuses gets disabled within the week.
#
# \U000026D4 THIS FILE IS A POINTER, NOT A COPY. The judge lives in ONE single place:
#   {racine_mnemosyne}/system/lib/mnemosyne/production/garde_shell.py
# Do not copy it to your side: a copy drifts, and you would lose the fixes.
#
# \U000026A0\U0000FE0F FAIL-OPEN EVERYWHERE EXCEPT THE REFUSAL: Mnemosyne absent or moved, python absent,
# unreadable JSON -> the command passes. A gate that breaks the ability to run commands gets
# removed within the hour. You would lose the protection silently: if you want to KNOW it is
# alive, run move 3's check.

# ── MOVE 1: write this file to <your-repo>/.claude/hooks/pre-tool-use.sh, then chmod +x ──────
#!/usr/bin/env bash
charge=$(cat)
sortie=$(printf '%s' "$charge" | env \\
  PYTHONPATH="{racine_mnemosyne}/system/lib" \\
  python3 -m mnemosyne.runtime.garde_shell_run 2>&1)
if [ "$?" -eq 2 ]; then
  printf '%s\\n' "$sortie" >&2
  exit 2
fi
exit 0

# ── MOVE 2: add this to <your-repo>/.claude/settings.json, under "hooks" ────────────────────
  "PreToolUse": [
    {{
      "matcher": "Bash",
      "hooks": [
        {{ "type": "command", "command": "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/pre-tool-use.sh" }}
      ]
    }}
  ]

# ── MOVE 3: PROVE IT, do not just believe it. Two firings, two directions ────────────────────
# It must BITE (expected: rc=2):
#   printf '%s' '{{"tool_name":"Bash","tool_input":{{"command":"echo \\\\"`date`\\\\""}}}}' \\
#     | .claude/hooks/pre-tool-use.sh ; echo "rc=$?"
# It must LET THROUGH your usual workaround, the quoted heredoc (expected: rc=0):
#   python3 -c 'import json;print(json.dumps({{"tool_name":"Bash","tool_input":{{"command":"cat <<\\'"'"'EOF\\'"'"'\\n`x`\\nEOF\\n"}}}}))' \\
#     | .claude/hooks/pre-tool-use.sh ; echo "rc=$?"
# \U000026D4 Either firing alone is not enough: a gate that refuses EVERYTHING passes the first one.
"""


def refus(morsures: tuple[Morsure, ...]) -> str:
    """The refusal message: it NAMES the way out, it does not just forbid.

    *A refusal message often names the way out* — without it, a gate teaches nothing and gets
    routed around by the first workaround that comes along."""
    if not morsures:
        return ""
    # A PAIR of backticks makes two bites on the SAME line: the line is shown once.
    # Repeating the same excerpt would make a single defect look like an epidemic.
    lignes = tuple(dict.fromkeys((m.ligne, m.extrait) for m in morsures))
    ou = "\n".join(f"    line {n}: {texte}" for n, texte in lignes[:5])
    reste = f"\n    … and {len(lignes) - 5} more line(s)" if len(lignes) > 5 else ""
    return (
        f"\U000026D4 REFUSED — {len(morsures)} backtick(s) the shell is going to SUBSTITUTE:\n{ou}{reste}\n\n"
        "The shell will execute whatever sits between the backticks and REPLACE it with its output. "
        "The command will still SUCCEED, with your text mutilated — nothing will warn you.\n"
        "Measured: `python3 -c \"print('BEFORE `path` AFTER')\"` returns « BEFORE  AFTER ».\n\n"
        "Three ways out, in order:\n"
        "  1. a QUOTED-delimiter heredoc — `<<'END' … END` — nothing in it is substituted;\n"
        "  2. single quotes around the text;\n"
        "  3. if you really meant to substitute a command, write `$( … )`.\n"
        "Write the text to a file rather than into the argument when it is long."
    )


def refus_ecrasement(chemins: tuple[str, ...]) -> str:
    """The refusal message for the second judge (I8): it NAMES the dirty files and the way out --
    the same discipline as :func:`refus` for backticks. *A refusal message often names the way
    out*: without it, a gate teaches nothing and gets routed around."""
    if not chemins:
        return ""
    lignes = "\n".join(f"    {c}" for c in chemins[:10])
    reste = f"\n    … and {len(chemins) - 10} more" if len(chemins) > 10 else ""
    return (
        f"\U000026D4 REFUSED — this move would SILENTLY OVERWRITE {len(chemins)} modified, UNCOMMITTED "
        f"file(s):\n{lignes}{reste}\n\n"
        "`git checkout --`, `git restore` and `git reset --hard` restore the working directory "
        "WITH NO warning: the command SUCCEEDS, uncommitted content is LOST.\n"
        "Measured: the same fault, repeated EIGHT times since 2026-07-28 in a sabotage loop "
        "that only meant to undo the sabotage -- never the work sitting next to it.\n\n"
        "Get out via `git stash` (or commit whatever must survive) BEFORE this move, then replay it."
    )
