"""THE SHELL GATE GETS JUDGED (workstream 1 · requested by the sibling project, 2026-08-09).

THIS IS THE ONLY GATE IN THIS REPOSITORY THAT BLOCKS A MOVE. All the others print. So the
witnesses must hold BOTH directions with the same force:

* **it bites** on the measured case (a backtick the shell substitutes);
* **it does NOT bite** on the three ways out its own refusal message recommends — a
  quoted-delimiter heredoc, single quotes, `$( … )`. *A gate that wrongly refuses gets
  disabled within the week*: a false refusal here is as serious a defect as the leak itself.

THE FIRST WITNESS IS THE INNOCENT CASE: an ordinary command must trigger nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from mnemosyne.production.garde_shell import (
    backticks_substitues,
    cibles_checkout_restore,
    contient_reset_hard,
    contrat_emis,
    refus,
    refus_ecrasement,
)

_RACINE = Path(__file__).resolve().parents[2]
_HOOK = _RACINE / ".claude" / "hooks" / "pre-tool-use.sh"


def test_une_commande_banale_ne_declenche_rien() -> None:
    assert backticks_substitues("git status --short") == ()
    assert refus(()) == ""


# ── It BITES where the shell substitutes ────────────────────────────────────────────────────


def test_le_cas_mesure_chez_le_sibling_est_attrape() -> None:
    """Reproduces: `python3 -c \"print('BEFORE `x` AFTER')\"` returns « BEFORE  AFTER » — the
    content is eaten AND the command SUCCEEDS. It is the silence that makes this defect serious."""
    morsures = backticks_substitues("""python3 -c "print('BEFORE `docs/x.md` AFTER')" """)
    assert len(morsures) == 2, "a PAIR of backticks makes two substituted characters"


def test_un_backtick_entre_guillemets_doubles_mord() -> None:
    assert len(backticks_substitues('git commit -m "see `make arsenal`"')) == 2


def test_un_backtick_nu_mord() -> None:
    assert len(backticks_substitues("echo `date`")) == 2


def test_un_heredoc_NON_quote_mord() -> None:
    assert len(backticks_substitues("cat <<EOF\nsee `make arsenal`\nEOF\n")) == 2


# ── It does NOT bite on what its own refusal recommends ─────────────────────────────────────────────────


def test_le_heredoc_a_delimiteur_QUOTE_passe() -> None:
    """WAY OUT #1 FROM THE REFUSAL MESSAGE. If the gate refused it, it would be sending people
    into a wall — and the refusal itself would become a lie."""
    assert backticks_substitues("git commit -F - <<'EOF'\nsee `make arsenal`\nEOF\n") == ()


def test_les_apostrophes_simples_passent() -> None:
    assert backticks_substitues("""python3 -c 'print("see `make arsenal`")' """) == ()


def test_dollar_parenthese_n_est_JAMAIS_refuse() -> None:
    """DELIBERATE: it is the modern, legitimate form. Refusing it would produce constant false
    refusals, and we would have traded a silent defect for a dead gate."""
    assert backticks_substitues("x=$(git rev-parse HEAD) && echo $(date)") == ()


def test_un_backtick_echappe_passe() -> None:
    assert backticks_substitues("echo \\`literal\\`") == ()


def test_l_etat_revient_apres_un_heredoc_quote() -> None:
    """The literal body must not "swallow" the rest of the command."""
    commande = "git commit -F - <<'EOF'\nsee `x`\nEOF\ngit commit -m \"and `y`\""
    assert len(backticks_substitues(commande)) == 2


def test_un_heredoc_QUOTE_niche_dans_UN_DOLLAR_PARENTHESE_ENTRE_GUILLEMETS_passe() -> None:
    """THE FALSE REFUSAL MEASURED WHILE BUILDING `I8`: `git commit -m "$(cat <<'EOF' … EOF)"` --
    the pattern CLAUDE.md itself prescribes for this repository -- was getting refused as soon as
    a backtick appeared in the heredoc's body. The gate stayed in `double` state (the one for
    `-m "..."`) and never recognized `<<'EOF'` as a heredoc: it scanned its body character by
    character, in `double`, and found "substituted" backticks there that were not. In real bash,
    `$( … )` opens a COMMAND context independent of what surrounds it, quotes included -- hence the
    context stack."""
    commande = "git commit -m \"$(cat <<'EOF'\nsee `make arsenal`\nEOF\n)\""
    assert backticks_substitues(commande) == ()


def test_un_heredoc_NON_quote_niche_dans_UN_DOLLAR_PARENTHESE_mord_quand_meme() -> None:
    """The fix must not become a loophole: WITHOUT quotes on the delimiter, a heredoc nested
    inside `$( … )` is indeed still SUBSTITUTED, exactly as at the top level."""
    commande = 'git commit -m "$(cat <<EOF\nsee `make arsenal`\nEOF\n)"'
    assert len(backticks_substitues(commande)) == 2


def test_un_sous_shell_dans_UN_DOLLAR_PARENTHESE_ne_referme_pas_le_contexte_trop_tot() -> None:
    """A BARE `( … )` inside a `$( … )` (subshell) must not be confused with the
    `)` that closes the `$( … )` itself.

    SABOTAGED AND VERIFIED: a first draft of this witness (`x=$( (echo "a") && echo \\`b\\` )`,
    a BARE backtick right after the subshell) did NOT discriminate -- removing the depth tracking
    returned `2` in both cases, because a bare backtick bites just as well in `nu` (bare) as in
    `double`. A backtick INSIDE SINGLE QUOTES was needed after the subshell: a premature pop at
    the subshell's `)` falls back into the OUTER context (`double`, which does not treat single
    quotes as literal the same way) and makes it bite wrongly."""
    commande = "echo \"before $( (echo x) ; echo 'lit `z` eral' ) after\""
    assert backticks_substitues(commande) == ()


def test_le_refus_NOMME_les_trois_sorties() -> None:
    """*A refusal message often names the way out.* Without them, a gate learns nothing."""
    texte = refus(backticks_substitues("echo `date`"))
    assert "<<'END'" in texte and "$( … )" in texte and "single quotes" in texte


def test_une_paire_sur_une_ligne_n_affiche_la_ligne_qu_une_fois() -> None:
    """Repeating the same excerpt would make a single defect look like an epidemic."""
    assert refus(backticks_substitues("echo `date`")).count("line 1:") == 1


# ── The hook: it blocks, and is FAIL-OPEN everywhere else ────────────────────────────────────────────


def _hook(charge: object) -> int:
    return subprocess.run(
        [str(_HOOK)], input=json.dumps(charge), capture_output=True, text=True, cwd=_RACINE
    ).returncode


def test_le_hook_bloque_le_cas_mesure() -> None:
    assert _hook({"tool_name": "Bash", "tool_input": {"command": 'echo "`date`"'}}) == 2


def test_le_hook_laisse_passer_le_heredoc_quote() -> None:
    charge = {"tool_name": "Bash", "tool_input": {"command": "cat <<'EOF'\n`x`\nEOF\n"}}
    assert _hook(charge) == 0


def test_le_hook_ignore_un_outil_qui_ne_va_pas_au_shell() -> None:
    """Judging text that will never reach the shell would manufacture refusals over prose.

    THE PAYLOAD CARRIES A `command` FIELD, AND THAT IS THE WHOLE POINT. A first draft passed
    ``{"content": …}``: the "every tool gets judged" sabotage did NOT turn it red, because the
    empty command returned 0 before even reaching the filter. *A witness that does not ARM the
    gate measures its own silence.*"""
    charge = {"tool_name": "Write", "tool_input": {"command": 'echo "`date`"'}}
    assert _hook(charge) == 0


def test_le_hook_est_FAIL_OPEN_sur_une_charge_illisible() -> None:
    """OWNED IN WRITING: a gate that breaks the ability to run commands gets removed within the
    hour. We would rather miss a bite than block an innocent."""
    fait = subprocess.run(
        [str(_HOOK)], input="this is not JSON", capture_output=True, text=True, cwd=_RACINE
    )
    assert fait.returncode == 0


def test_le_MODULE_lui_meme_est_fail_open_pas_seulement_son_enveloppe() -> None:
    """TWO BELTS, AND ONLY ONE WAS PROVEN. The bash script only exits 2 on an rc of 2: so it
    catches EVERYTHING else, including an exception from the module. The "fail-open removed"
    sabotage turned nobody red — the Python belt was never tested, only its suspender was. This
    witness calls the module DIRECTLY, without the wrapper."""
    fait = subprocess.run(
        [sys.executable, "-m", "mnemosyne.runtime.garde_shell_run"],
        input="not JSON at all",
        capture_output=True,
        text=True,
        cwd=_RACINE,
        env={**os.environ, "PYTHONPATH": str(_RACINE / "system" / "lib")},
    )
    assert fait.returncode == 0, fait.stderr


def test_le_hook_est_FAIL_OPEN_sur_un_champ_absent() -> None:
    assert _hook({"tool_name": "Bash"}) == 0
    assert _hook({"tool_name": "Bash", "tool_input": {"command": None}}) == 0


def test_le_hook_est_cable_dans_settings() -> None:
    """*A barrier nothing calls* : the judge can be perfect, if the hook is not declared it
    never runs."""
    reglages = json.loads((_RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entrees = reglages.get("hooks", {}).get("PreToolUse", [])
    commandes = [h["command"] for e in entrees for h in e.get("hooks", [])]
    assert any("pre-tool-use.sh" in c for c in commandes), reglages.get("hooks", {}).keys()
    assert _HOOK.exists() and _HOOK.stat().st_mode & 0o111, "the hook must be executable"


# ── EMISSION to another host: the address, never the copy ──────────────────────────────────────────────


def test_le_contrat_emis_POINTE_et_ne_recopie_PAS_le_juge() -> None:
    """THE HEART OF THE CONTRACT. Copying the judge onto each host would produce as many
    versions as hosts, and they would drift (D163 · one single hearth, EMITTED). The contract
    must therefore carry the module's ADDRESS and never its code."""
    texte = contrat_emis("/tmp/racine-injectee")
    assert "/tmp/racine-injectee/system/lib" in texte
    assert "def backticks_substitues" not in texte, "the judge was COPIED into the contract"
    assert "mnemosyne.runtime.garde_shell_run" in texte


def test_le_contrat_emis_NOMME_les_deux_tirs_d_epreuve() -> None:
    """*A printed string is not a proof* : the contract must tell the host how to
    PROVE the gate itself, in BOTH directions — a gate that refuses everything passes the first."""
    texte = contrat_emis("/tmp/x")
    assert "rc=2" in texte and "rc=0" in texte
    assert "BITE" in texte and "LET THROUGH" in texte


def test_le_contrat_emis_ouvre_par_ES_TU_DEJA_COUVERT() -> None:
    """MOVE 0, AND IT WAS PAID FOR. A host installed the gate IN DUPLICATE while already
    covered (its `CLAUDE_PROJECT_DIR` was Mnemosyne's, so my hooks were already running there).
    Its copy was never loaded; its only real effect was to turn its own anti-exfiltration gate
    red and to BLOCK a commit. *Look for what already exists before building* — the contract
    must ask this question BEFORE its installation moves, not after."""
    texte = contrat_emis("/tmp/racine")
    assert "MOVE 0" in texte
    assert 'echo "$CLAUDE_PROJECT_DIR"' in texte
    assert "ALREADY COVERED" in texte
    assert texte.index("MOVE 0") < texte.index("MOVE 1"), (
        "move 0 must come BEFORE move 1"
    )


def test_le_contrat_emis_previent_de_la_porte_anti_fuite() -> None:
    """The host must know that placing this hook in its TRACKED tree can turn its own gate red:
    it launches a subprocess toward code OUTSIDE its repository."""
    texte = contrat_emis("/tmp/racine")
    assert "anti-exfiltration" in texte
    assert "SESSION tool" in texte


def test_le_contrat_emis_avoue_son_fail_open() -> None:
    """The host must know it would lose the protection SILENTLY if Mnemosyne moved."""
    assert "FAIL-OPEN" in contrat_emis("/tmp/x")


def test_le_hook_EMIS_mord_et_laisse_passer_une_fois_installe_ailleurs(tmp_path: Path) -> None:
    """THE WITNESS THAT COUNTS: we EXTRACT the hook from the contract, install it in a
    foreign folder, and fire it. A contract that reads well but does not execute would be a
    printed string, not a gate."""
    lignes = contrat_emis(str(_RACINE)).splitlines()
    debut = lignes.index("#!/usr/bin/env bash")
    fin = lignes.index("exit 0", debut)
    hook = tmp_path / "pre-tool-use.sh"
    hook.write_text("\n".join(lignes[debut : fin + 1]) + "\n", encoding="utf-8")
    hook.chmod(0o755)

    def tirer(commande: str) -> int:
        charge = json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}})
        return subprocess.run(
            [str(hook)], input=charge, capture_output=True, text=True, cwd=tmp_path
        ).returncode

    assert tirer('echo "`date`"') == 2, "the emitted hook does not bite"
    assert tirer("cat <<'EOF'\n`x`\nEOF\n") == 0, "the emitted hook refuses the way out it recommends"


def test_l_emission_REFUSE_quand_le_juge_serait_introuvable(tmp_path: Path) -> None:
    """Emitting a contract that points to a missing judge would install a gate that fails
    OPEN silently: the host would believe it is protected. We refuse instead of emitting."""
    fait = subprocess.run(
        [sys.executable, "-m", "mnemosyne.runtime.garde_emit_run"],
        capture_output=True,
        text=True,
        cwd=_RACINE,
        env={
            **os.environ,
            "PYTHONPATH": str(_RACINE / "system" / "lib"),
            "CLAUDE_PROJECT_DIR": str(tmp_path),
        },
    )
    assert fait.returncode == 2
    assert "cannot be found" in fait.stderr or "does not contain" in fait.stderr


# ── I8 -- checkout/restore/reset --hard on a DIRTY target (workstream 1, 2026-08-15) ───────────────────
#
# Chat 1 made this EXACT mistake EIGHT times: `git checkout -- <file>` inside a sabotage
# loop erases uncommitted work ALONG WITH the sabotage -- eight repetitions are the experimental
# proof that repetition alone is not a barrier (A2). Here the judge is NOT pure: it needs the
# repository's REAL state (`git status --porcelain`), so the REAL hook's witnesses run inside an
# ISOLATED git repository under tmp_path -- NEVER this shared Mnemosyne repository, where other
# sessions may have uncommitted work while these witnesses run.


def _depot_git_propre(tmp_path: Path) -> Path:
    depot = tmp_path / "depot"
    depot.mkdir()
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@local"],
        ["git", "config", "user.name", "test"],
    ):
        subprocess.run(cmd, cwd=depot, check=True)
    (depot / "foo.py").write_text("A\n", encoding="utf-8")
    (depot / "bar.py").write_text("A\n", encoding="utf-8")
    subprocess.run(["git", "add", "foo.py", "bar.py"], cwd=depot, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=depot, check=True)
    return depot


def _depot_git_sale(tmp_path: Path) -> Path:
    """The same repository, with `foo.py` made DIRTY after its first commit -- an UNSTAGED
    modification, exactly what a `checkout --` / `restore` / `reset --hard` would silently overwrite."""
    depot = _depot_git_propre(tmp_path)
    (depot / "foo.py").write_text("B\n", encoding="utf-8")
    return depot


def _hook_dans(
    dossier: Path, charge: object, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_HOOK)], input=json.dumps(charge), capture_output=True, text=True, cwd=dossier, env=env
    )


def _faux_git_qui_journalise(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """A FAKE `git` at the front of `PATH` that logs every invocation then DELEGATES to the
    real `git` -- to MEASURE the number of calls, never assume it. Same method as `I8`'s second
    isolated audit, which found that the first draft of these witnesses only asserted `rc == 0` --
    a NAME, not a test, passing identically with 0 OR 10 `git` calls."""
    vrai_git = shutil.which("git")
    assert vrai_git, "git not found -- cannot build the fake delegating git"
    journal = tmp_path / "appels-git.log"
    faux_bin = tmp_path / "faux-bin"
    faux_bin.mkdir()
    faux_git = faux_bin / "git"
    faux_git.write_text(
        f'#!/usr/bin/env bash\necho "$*" >> "$JOURNAL_APPELS"\nexec "{vrai_git}" "$@"\n',
        encoding="utf-8",
    )
    faux_git.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{faux_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "JOURNAL_APPELS": str(journal),
    }
    return env, journal


def _appels_journalises(journal: Path) -> list[str]:
    return journal.read_text(encoding="utf-8").splitlines() if journal.exists() else []


# ── Pure functions: candidates on TEXT alone, no I/O ────────────────────────────────────────────


def test_cibles_checkout_reconnait_le_double_tiret() -> None:
    assert cibles_checkout_restore("git checkout -- foo.py bar.py") == ("foo.py", "bar.py")


def test_cibles_checkout_SANS_double_tiret_n_est_PAS_reconnu() -> None:
    """DELIBERATE: ambiguous with a branch name. A false bite there would cost more than a
    missed real one -- we would rather miss a bite than block an innocent."""
    assert cibles_checkout_restore("git checkout foo.py") == ()
    assert cibles_checkout_restore("git checkout main") == ()


def test_cibles_restore_est_reconnu_sans_double_tiret() -> None:
    """`restore` does not have `checkout`'s ambiguity with a branch name: its argument is
    ALWAYS a path."""
    assert cibles_checkout_restore("git restore foo.py") == ("foo.py",)


def test_cibles_restore_staged_seul_n_est_PAS_reconnu() -> None:
    """`git restore --staged` without `--worktree` only touches the INDEX: nothing is lost in the
    working directory."""
    assert cibles_checkout_restore("git restore --staged foo.py") == ()
    assert cibles_checkout_restore("git restore --staged --worktree foo.py") == ("foo.py",)


def test_cibles_checkout_traverse_une_commande_chainee() -> None:
    assert cibles_checkout_restore("echo sabotage && git checkout -- foo.py") == ("foo.py",)


def test_cibles_checkout_normalise_le_prefixe_point_slash() -> None:
    assert cibles_checkout_restore("git checkout -- ./foo.py") == ("foo.py",)


def test_contient_reset_hard() -> None:
    assert contient_reset_hard("git reset --hard") is True
    assert contient_reset_hard("git reset --hard HEAD~1") is True
    assert contient_reset_hard("git reset --soft HEAD~1") is False
    assert contient_reset_hard("git status") is False


def test_refus_ecrasement_NOMME_le_fichier_et_le_geste_de_sortie() -> None:
    texte = refus_ecrasement(("foo.py",))
    assert "foo.py" in texte and "git stash" in texte


def test_refus_ecrasement_vide_est_une_chaine_vide() -> None:
    assert refus_ecrasement(()) == ""


# ── The two mandatory firings, through the REAL hook -- never just one ────────────────────────────────


def test_le_VRAI_hook_refuse_un_checkout_sur_une_cible_sale(tmp_path: Path) -> None:
    """THE FIRING THAT COUNTS: the fault measured eight times. The message must NAME the dirty
    file and the way out (`git stash`), not just refuse."""
    fait = _hook_dans(
        _depot_git_sale(tmp_path),
        {"tool_name": "Bash", "tool_input": {"command": "git checkout -- foo.py"}},
    )
    assert fait.returncode == 2
    assert "foo.py" in fait.stderr
    assert "git stash" in fait.stderr


def test_le_VRAI_hook_laisse_passer_un_checkout_sur_une_cible_propre(tmp_path: Path) -> None:
    """THE SECOND FIRING, WITHOUT WHICH THE FIRST PROVES NOTHING: a gate that refuses
    EVERYTHING passes the first firing."""
    fait = _hook_dans(
        _depot_git_sale(tmp_path),
        {"tool_name": "Bash", "tool_input": {"command": "git checkout -- bar.py"}},
    )
    assert fait.returncode == 0


def test_le_VRAI_hook_refuse_un_restore_sur_une_cible_sale(tmp_path: Path) -> None:
    fait = _hook_dans(
        _depot_git_sale(tmp_path),
        {"tool_name": "Bash", "tool_input": {"command": "git restore foo.py"}},
    )
    assert fait.returncode == 2
    assert "foo.py" in fait.stderr


def test_le_VRAI_hook_refuse_un_reset_hard_quand_quelque_chose_est_sale(tmp_path: Path) -> None:
    """`reset --hard` does NOT target a file: it threatens EVERYTHING that is dirty."""
    fait = _hook_dans(
        _depot_git_sale(tmp_path),
        {"tool_name": "Bash", "tool_input": {"command": "git reset --hard"}},
    )
    assert fait.returncode == 2
    assert "foo.py" in fait.stderr


def test_le_VRAI_hook_laisse_passer_reset_hard_sur_un_depot_propre(tmp_path: Path) -> None:
    fait = _hook_dans(
        _depot_git_propre(tmp_path),
        {"tool_name": "Bash", "tool_input": {"command": "git reset --hard"}},
    )
    assert fait.returncode == 0


# ── The four forms found by the isolated audit (verdict: NO, fixed in the same fragment) ──────
#
# An early version compared the command's RAW token to `git status --porcelain` by STRING
# EQUALITY. The auditor RAN these four forms in a disposable repository and observed real data
# loss for each one -- the gate was weaker than its written condition.


def _depot_git_avec_sousdir_sale(tmp_path: Path) -> Path:
    """A dirty file at the root (`foo.py`) AND a dirty file INSIDE a subfolder
    (`sousdir/enfant.py`) -- `bar.py` stays clean, for the symmetric witness."""
    depot = _depot_git_propre(tmp_path)
    (depot / "sousdir").mkdir()
    (depot / "sousdir" / "enfant.py").write_text("A\n", encoding="utf-8")
    subprocess.run(["git", "add", "sousdir/enfant.py"], cwd=depot, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "sousdir"], cwd=depot, check=True)
    (depot / "foo.py").write_text("B\n", encoding="utf-8")
    (depot / "sousdir" / "enfant.py").write_text("B\n", encoding="utf-8")
    return depot


def test_un_chemin_ABSOLU_sur_une_cible_sale_est_refuse(tmp_path: Path) -> None:
    depot = _depot_git_avec_sousdir_sale(tmp_path)
    fait = _hook_dans(
        depot,
        {"tool_name": "Bash", "tool_input": {"command": f"git checkout -- {depot / 'foo.py'}"}},
    )
    assert fait.returncode == 2
    assert "foo.py" in fait.stderr


def test_checkout_point_ecrase_TOUT_ce_qui_est_sale(tmp_path: Path) -> None:
    depot = _depot_git_avec_sousdir_sale(tmp_path)
    fait = _hook_dans(depot, {"tool_name": "Bash", "tool_input": {"command": "git checkout -- ."}})
    assert fait.returncode == 2
    assert "foo.py" in fait.stderr
    assert "sousdir" in fait.stderr


def test_un_dossier_sale_en_cible_est_refuse(tmp_path: Path) -> None:
    depot = _depot_git_avec_sousdir_sale(tmp_path)
    fait = _hook_dans(
        depot, {"tool_name": "Bash", "tool_input": {"command": "git checkout -- sousdir"}}
    )
    assert fait.returncode == 2
    assert "sousdir" in fait.stderr


def test_cwd_dans_un_sous_dossier_est_refuse(tmp_path: Path) -> None:
    """The command's token (`enfant.py`) is relative to the hook's CWD, not to the repository's
    root -- they must be resolved in the SAME frame of reference before comparison."""
    depot = _depot_git_avec_sousdir_sale(tmp_path)
    fait = _hook_dans(
        depot / "sousdir",
        {"tool_name": "Bash", "tool_input": {"command": "git checkout -- enfant.py"}},
    )
    assert fait.returncode == 2
    assert "enfant.py" in fait.stderr


def test_ces_quatre_formes_LAISSENT_TOUJOURS_PASSER_une_cible_propre(tmp_path: Path) -> None:
    """Without this symmetric witness, the fix could over-correct into a systematic refusal --
    a gate that refuses everything passes the first firing, never the second."""
    depot = _depot_git_avec_sousdir_sale(tmp_path)
    fait = _hook_dans(
        depot,
        {"tool_name": "Bash", "tool_input": {"command": f"git checkout -- {depot / 'bar.py'}"}},
    )
    assert fait.returncode == 0


# ── FAIL-OPEN everywhere else, like the backtick gate ────────────────────────────────────────────


def test_fail_open_hors_de_tout_depot_git(tmp_path: Path) -> None:
    vide = tmp_path / "pas-un-depot"
    vide.mkdir()
    fait = _hook_dans(
        vide, {"tool_name": "Bash", "tool_input": {"command": "git checkout -- foo.py"}}
    )
    assert fait.returncode == 0


def test_fail_open_forme_non_reconnue_checkout_sans_double_tiret(tmp_path: Path) -> None:
    fait = _hook_dans(
        _depot_git_sale(tmp_path),
        {"tool_name": "Bash", "tool_input": {"command": "git checkout foo.py"}},
    )
    assert fait.returncode == 0


def test_le_hook_ne_declenche_PAS_git_status_sur_une_commande_ordinaire(tmp_path: Path) -> None:
    """POST-AUDIT FIX (D75): the first draft only asserted `rc == 0` -- a NAME, not a
    test. It would have passed identically with 0 OR 10 `git` calls, since `echo hello` never
    touches the dirty file anyway, git call or not. Found by the second isolated audit on fix
    `2c69744`. Rebuilt with a fake `git` that LOGS (see
    `_faux_git_qui_journalise`) -- the cost is now MEASURED, never assumed."""
    env, journal = _faux_git_qui_journalise(tmp_path)
    fait = _hook_dans(
        _depot_git_sale(tmp_path),
        {"tool_name": "Bash", "tool_input": {"command": "echo hello"}},
        env=env,
    )
    assert fait.returncode == 0
    appels = _appels_journalises(journal)
    assert appels == [], f"0 git calls expected on an ordinary command, got: {appels}"


def test_le_faux_git_MORD_bien_quand_une_forme_destructrice_est_reconnue(tmp_path: Path) -> None:
    """POSITIVE control for the previous witness: without it, a harness that silently ignored
    the modified `PATH` would pass the "0 calls" witness for a reason that has nothing to do with
    the short-circuit it claims to verify -- *a control that never prints anything is not a
    barrier*."""
    env, journal = _faux_git_qui_journalise(tmp_path)
    fait = _hook_dans(
        _depot_git_sale(tmp_path),
        {"tool_name": "Bash", "tool_input": {"command": "git checkout -- foo.py"}},
        env=env,
    )
    assert fait.returncode == 2
    appels = _appels_journalises(journal)
    assert len(appels) == 2, appels
    assert appels[0].startswith("rev-parse"), appels
    assert appels[1].startswith("status"), appels


# ---- PROVEN OUTSIDE THE POPULATION (hardening, 2026-08-16) ----------------------------------------
def test_eprouve_sur_de_VRAIS_messages_de_commit_de_CE_depot() -> None:
    """HARDENING (D75): every witness above, sabotages included, judges commands WRITTEN BY
    HAND by the module's author — a population the author had entirely in front of them while
    writing `backticks_substitues`. This witness proves it on a population the author did NOT
    have: this repository's REAL commit messages, uncurated text, written across several sessions
    over several days, saturated with markdown backticks (`` `module.py` ``,
    `` `make target` ``) — exactly the style the module's docstring cites as motivating the
    gate.

    The pattern tested is the one this very test file ALREADY ESTABLISHES as canonical
    (`test_l_etat_revient_apres_un_heredoc_quote`, line 88): `git commit -F - <<'EOF' … EOF` --
    a QUOTED delimiter, so the body is literal to the shell regardless of its content. On
    THIS real population, no REAL message should ever make the gate bite: a false refusal here
    would block an honest commit over an ordinary markdown backtick.
    """
    sortie = subprocess.run(
        ["git", "-C", str(_RACINE), "log", "--format=%H%x01%B%x02", "-n", "500"],
        capture_output=True,
        text=True,
        check=True,
    )
    messages = [
        bloc.split("\x01", 1)[1]
        for bloc in sortie.stdout.split("\x02")
        if "\x01" in bloc and bloc.split("\x01", 1)[1].strip()
    ]
    avec_backtick = [m for m in messages if "`" in m]
    assert len(avec_backtick) > 20, (
        f"only {len(avec_backtick)} real messages with a backtick found out of "
        f"{len(messages)} -- population too small to prove anything"
    )
    faux_refus = []
    for message in avec_backtick:
        commande = f"git commit -F - -- x.py <<'EOF'\n{message}\nEOF"
        if backticks_substitues(commande):
            faux_refus.append(message.splitlines()[0][:80])
    assert not faux_refus, f"{len(faux_refus)} FALSE REFUSALS on real messages: {faux_refus[:5]}"


def test_le_MEME_backtick_MORD_quand_le_delimiteur_n_est_PAS_quote() -> None:
    """The second firing, on the SAME real population: without quoting on the delimiter, these
    same authentic messages must become dangerous again. *A gate that never bites on anything
    would pass the previous witness just as well as a gate that works* — both directions, always."""
    sortie = subprocess.run(
        ["git", "-C", str(_RACINE), "log", "--format=%H%x01%B%x02", "-n", "60"],
        capture_output=True,
        text=True,
        check=True,
    )
    messages = [
        bloc.split("\x01", 1)[1]
        for bloc in sortie.stdout.split("\x02")
        if "\x01" in bloc and bloc.split("\x01", 1)[1].strip()
    ]
    avec_backtick = [m for m in messages if "`" in m and "EOF" not in m]
    assert avec_backtick, "no real message with a backtick in this shorter sample"
    for message in avec_backtick[:10]:
        commande = f"git commit -F - -- x.py <<EOF\n{message}\nEOF"
        assert backticks_substitues(commande), f"false LET-THROUGH on: {message[:80]}"
