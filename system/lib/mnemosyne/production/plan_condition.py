"""`C1` — THE DEFINITION OF A COMMAND: one single home, ported up from another project, not reinvented.

 **THIS MODULE EXISTS BECAUSE THE DEFINITION LIVED IN THREE COPIES IN ANOTHER PROJECT**, as a copy-pasted
regex. An isolated executor disproved it on 2026-07-30: the span `` `octets.find(phrase.
encode()) != -1` `` was counted as a command — the pattern read `octets.` as a path prefix and
`-1` as a flag, so `find` passed for the `find` binary. **The count published at the time (103)
carried at least one item with no command at all**, and any condition writing `x.find(y) != -1`
crossed the gate for free.

 **THIS VERSION IS A PORT, NOT A REWRITE** — the plan's `C1` item says so: *"the single home …
ported up from another project."* Each fix below carries the fault that motivated it, because a rule copied
without its history gets the same fault corrected all over again once stripped of its context.
*Taking over a form means taking over what was written, not what one would have written.*

 **WHAT THIS DEFINITION DOES NOT JUDGE, and it is written here rather than discovered later**: it
does not say whether the command actually SETTLES anything. `git ls-files` alone is runnable and
does not say ON WHAT; a `grep` with no written threshold returns LINES, not a verdict. Whether it
settles is measured by the REAL trial, never by a pattern — `sans_commande=0` is a FLOOR, never the
goal.

Docstrings and comments English (D117); the regex literals and witness strings below are kept
verbatim, unmodified from the source they port.
"""

from __future__ import annotations

import re

#: The recognized executables — an ENUMERATED LIST, never an "etc.": an open list can't be
#: attacked. A missing binary is a diff line that names it.
EXECUTABLES = (
    "python", "pytest", "make", "git", "grep", "rg", "jq", "ls", "find", "wc", "sh",
    "bash", "shasum", "diff", "sed", "awk", "cat", "head", "tail", "sort", "uniq",
)

#: (1) THE PREFIX IS A PATH OR IT ISN'T: every segment ends with `/`, so `octets.` can no longer
#: pass for a folder. `~/` is handled separately — `~` is not a `[\w.-]+` segment, and forgetting
#: it used to refuse a legitimate venv interpreter (`~/…/.venv/bin/python`).
_PREFIXE = r"(?:~/)?(?:[\w.-]+/)*"

#: (2) AT LEAST ONE ARGUMENT TOKEN. A bare subcommand counts (`make plans`), an executable alone
#: does not. THE SPACE IS NON-NEWLINE (`[ \t]`), and (3) the inline span CONTAINS NO LINE BREAK
#: — the third fix ported from that project: a span FOLDED by markdown across two lines glues itself into
#: a BROKEN command. `[^`]` crosses `\n`, so the previous version counted these folded spans as
#: typable. The definition demands "typable as written": a fold violates that.
_ARGUMENT = r"[ \t]+\S"

#: An INLINE span, with no line break — this is the population the pattern is tested against.
_SPAN_INLINE = re.compile(r"`([^`\n]*)`")

#: (4) THE VERSION NUMBER IS PART OF THE NAME. A `\b` after `python` used to refuse `python3` —
#: two items in that project were counted "still to write" while already carrying a command.
#: (5) AND THE `^` ANCHOR CLOSES THE LEFT BOUNDARY: without it, an executable named MID-SENTENCE —
#: preceded by an ORDINARY word, not a path separator — would read as a command if a token
#: follows. Isolated witness: `voir ls -la` matches WITHOUT the anchor, never with it.
#: **A FALSE COMMENT, INHERITED FROM THAT PROJECT AND COPIED WITHOUT RE-CHECKING IT, long attributed
#: this role to `` `profils-et-obligation.md` ``: measured by an isolated audit, this witness is
#: refused BOTH WITH AND WITHOUT the anchor — it is the absence of a following space (2) that
#: refuses it, not (5). *Taking over a form means taking over what was WRITTEN, not what one would
#: have written* — it still had to be checked that what was written was true.
_VERSION = r"[0-9.]*"

COMMANDE = re.compile(rf"^\s*{_PREFIXE}(?:{'|'.join(EXECUTABLES)}){_VERSION}\b{_ARGUMENT}")

#: The same pattern inside a block closed by triple backticks — a command can live in a block too.
BLOC = re.compile(
    rf"```(?:bash|sh)?\s*\n[^`]*?^\s*{_PREFIXE}(?:{'|'.join(EXECUTABLES)}){_VERSION}\b{_ARGUMENT}",
    re.M | re.S,
)

#: (6) A `grep` WITH NO TARGET READS STDIN — it returns nothing and it BLOCKS. Sixth defect found
#: in that project: `` `grep 'motif' --include='*.py'` `` satisfied the clause (a concrete flag) and could
#: never deliver the verdict its condition claimed. "Typable as written" implies that it
#: TERMINATES. A `grep` inside a PIPE (`|`) reads from upstream: legitimate.
_TUYAU = "|"


def _grep_sans_cible(span: str) -> bool:
    """True if the span is a `grep`/`rg` outside a pipe where no argument looks like a target."""
    mots = span.split()
    if not mots or _TUYAU in span:
        return False
    if not any(mots[0].endswith(b) for b in ("grep", "rg")):
        return False
    # the pattern is one argument; we look for an ADDITIONAL target — a token carrying `/` or `.`,
    # excluding flags and excluding `--include=...` (which filters names, it does not say WHERE to
    # search).
    # `.` IS A TARGET, and forgetting it used to refuse `grep -rn x --include='*.py' .` — the
    # most common idiom in a repository of this kind. Found while writing the witness, not while
    # re-reading the code.
    cibles = [
        m for m in mots[1:]
        if not m.startswith("-")
        and (m in (".", "..") or "/" in m
             or m.endswith((".py", ".md", ".yaml", ".json", ".jsonl", ".txt", ".toml")))
    ]
    return not cibles


def est_une_commande(texte: str) -> bool:
    """True if `texte` carries a command in the sense above — as an inline span (no fold) OR a block."""
    return (
        any(COMMANDE.search(s) and not _grep_sans_cible(s) for s in _SPAN_INLINE.findall(texte))
        or bool(BLOC.search(texte))
    )


#: THE WITNESSES THAT MUST PASS — generalized from that project's 11 witnesses (real paths replaced with
#: equivalent forms, the STRUCTURE that broke an earlier version stays identical).
TEMOINS_OUI = (
    "`~/bin/mon_interprete/python fichier.py`",
    "`python -c \"import x\"`",
    "`git ls-files chemin/vers/dossier/`",
    "`grep -c \"^verdict: TIENT\" chemin/vers/verdict.md`",
    "`grep -rn \"motif\" --include='*.py' .`",              # the `.` target is enough
    "`grep -rn 'x' dossier/ | cut -d: -f1`",                 # inside a PIPE: legitimate
    "`pytest -q tests/test_x.py`",
    "`make plans`",                                          # a BARE subcommand: passes
    "`wc -l fichier.py`",
    "`python3 chemin/vers/script.py`",                       # the version number is part of the name
    "```bash\n~/bin/mon_interprete/python script.py\n```",
)

#: THE FOLD WITNESS, isolated because it alone carries the third fix: the text does hold every word
#: of a command, and it is NOT typable — markdown cut it across two lines.
TEMOIN_REPLIE = "`grep -c \"motif_a\\|motif_b\"\n  fichier.py`"

#: THE WITNESSES THAT MUST BE REFUSED. The first is the refutation that motivated this module.
TEMOINS_NON = (
    "`octets.find(phrase.encode()) != -1`",   # the founding false-accept
    "`resultat.diff(autre) == -1`",
    "`UnObjet._champ_interne`",
    "`statut == 'valeur'`",
    "`python`",                               # an executable ALONE settles nothing
    "la condition rend vrai quand les octets EGALENT la valeur",
    "`dossier/manifeste/manifeste.json`",
    "`ls`",
    "`profils-et-obligation.md`",             # refused by (2): no space follows -- NOT the anchor
    "voir ls -la",                            # the REAL witness for the anchor (5): without it, matches
    "`grep 'motif' --include='*.py'`",        # no TARGET: reads stdin, returns nothing, BLOCKS
    "`grep -rn \"motif\" --include='*.py'`",
    TEMOIN_REPLIE,
)


def main() -> int:
    fautes = [f"SHOULD PASS: {t!r}" for t in TEMOINS_OUI if not est_une_commande(t)]
    fautes += [f"SHOULD BE REFUSED: {t!r}" for t in TEMOINS_NON if est_une_commande(t)]
    if fautes:
        print(f"FAIL plan_condition: {len(fautes)} witness(es) misjudged")
        for f in fautes:
            print(f"  {f}")
        return 1
    print(
        f"plan_condition=pass temoins_oui={len(TEMOINS_OUI)} temoins_non={len(TEMOINS_NON)} "
        f"executables={len(EXECUTABLES)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
