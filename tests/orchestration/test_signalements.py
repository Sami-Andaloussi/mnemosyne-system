"""Signalements — a PROJECT session files a Mnemosyne defect; a Mnemosyne session drains it.

The channel is the REPO, not a conversation: what matters is that a report survives between two
sessions, that draining never destroys it, and that the count reaches the project's owner through
the existing tick nerve without leaking what the filing project was working on. Brick-free, driven
over ``tmp_path``.

Several cases below are named regression guards for a 2026-07-19 audit: the drain must not rewrite a
body that quotes a ``status:`` line, a long title must not raise, and CRLF must survive.
"""
from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from mnemosyne.production import signalements as sig
from mnemosyne.production.proposer import DETTE_PREFIX, SignalementReview
from mnemosyne.runtime.signalements import main, render_open
from mnemosyne.runtime.tick import render_proposals, run_tick


def _filed(root: Path, title: str = "make search plante") -> Path:
    return sig.file_signalement(title, root=root, today=date(2026, 7, 20))


# ---- filing (the project side — trivial on purpose) ----------------------------------
def test_a_filed_signalement_is_open_and_dated(tmp_path: Path) -> None:
    path = _filed(tmp_path)
    assert path.name == "2026-07-20-make-search-plante.md"  # date-prefixed ⇒ chronological on disk
    assert sig._status_of(path) == sig.OPEN
    assert "stays **local**" in path.read_text(encoding="utf-8")  # it invites frankness, not self-censorship


def test_reports_are_structurally_excluded_from_git_but_the_contract_is_not() -> None:
    """D153: the guard is `.gitignore`, not a warning in prose (D100 / inv. 17 — an incapacity, not
    discipline). Proven against the REAL repo, because that is where the barrier has to hold: a report
    cannot enter history even under `git add -A`, while the contract doc stays versioned so a fresh
    clone still learns what this directory is for."""
    def ignored(rel: str) -> bool:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "check-ignore", "-q", rel], cwd=sig._REPO_ROOT, check=False
        )
        return done.returncode == 0

    assert ignored("docs/signalements/2026-01-01-un-rapport.md")
    assert not ignored("docs/signalements/README.md")


def test_two_reports_same_title_same_day_never_overwrite(tmp_path: Path) -> None:
    """Structural: the file is created with ``O_EXCL``, so even two sessions filing at the same
    instant get distinct reports — the guarantee is the exclusive create, not an ``exists()`` look."""
    first, second = _filed(tmp_path), _filed(tmp_path)
    assert first != second and first.exists() and second.exists()
    assert second.name == "2026-07-20-make-search-plante-02.md"  # zero-padded ⇒ sorts chronologically


def test_slug_folds_accents_and_punctuation(tmp_path: Path) -> None:
    path = sig.file_signalement("L'ingest a planté !", root=tmp_path, today=date(2026, 7, 20))
    assert path.name == "2026-07-20-l-ingest-a-plante.md"  # ASCII-safe filename, title kept inside
    assert "L'ingest a planté !" in path.read_text(encoding="utf-8")


def test_a_pasted_error_message_as_title_does_not_raise(tmp_path: Path) -> None:
    """An agent pasting a whole traceback as the title is the NOMINAL case; an untruncated slug would
    raise ``OSError: File name too long`` (255 bytes on APFS) and lose the report."""
    path = sig.file_signalement("x" * 400, root=tmp_path, today=date(2026, 7, 20))
    assert path.exists() and len(path.name) < 120
    assert sig._status_of(path) == sig.OPEN


def test_a_title_with_quotes_keeps_the_frontmatter_parseable(tmp_path: Path) -> None:
    path = sig.file_signalement('il dit "ok"\net saute', root=tmp_path, today=date(2026, 7, 20))
    assert sig._status_of(path) == sig.OPEN  # the status survives a hostile title
    assert 'titre: "il dit \\"ok\\" et saute"' in path.read_text(encoding="utf-8")


# ---- counting (what the tick surfaces) -----------------------------------------------
def test_count_ignores_the_contract_doc_and_drained_reports(tmp_path: Path) -> None:
    """Only OPEN reports await a session: the README living beside them is not a signalement, and a
    drained one stays on disk (invariant 2) without ever being counted again."""
    (tmp_path / "README.md").write_text("---\nstatus: ouvert\n---\n", encoding="utf-8")
    open_one, drained = _filed(tmp_path, "a casse"), _filed(tmp_path, "b casse")
    sig.mark_handled(drained, today=date(2026, 7, 21))
    assert sig.open_signalements(tmp_path) == (open_one,)
    assert sig.open_signalement_count(tmp_path) == 1
    assert drained.exists()  # drained ≠ deleted


def test_missing_directory_counts_zero_not_an_error(tmp_path: Path) -> None:
    assert sig.open_signalement_count(tmp_path / "never-used") == 0


def test_a_report_without_a_frontmatter_block_is_skipped_not_fatal(tmp_path: Path) -> None:
    """Fail-OPEN like the veille ledger — with the residual named: a report whose BLOCK is destroyed
    goes SILENT (it stops being counted) rather than blocking every tick."""
    (tmp_path / "2026-07-20-broken.md").write_text("no frontmatter at all\n", encoding="utf-8")
    good = _filed(tmp_path)
    assert sig.open_signalements(tmp_path) == (good,)


def test_a_hand_edited_status_still_counts(tmp_path: Path) -> None:
    """``Ouvert`` (capitalised) or a trailing comment is a plausible human edit — it must not drop the
    report silently out of the queue for good."""
    path = tmp_path / "2026-07-20-edited.md"
    path.write_text('---\nstatus: Ouvert  # relance\ntitre: "x"\n---\n\ncorps\n', encoding="utf-8")
    assert sig.open_signalements(tmp_path) == (path,)


def test_a_body_quoting_a_status_line_is_not_mistaken_for_the_field(tmp_path: Path) -> None:
    """A report ABOUT the fiche frontmatter writer quotes exactly such a line. The status field is
    read from the LEADING block only, so the quoted line can neither be counted nor rewritten."""
    path = tmp_path / "2026-07-20-about-the-writer.md"
    path.write_text(
        '---\nstatus: traite\ntitre: "x"\n---\n\nLe writer produit :\n\nstatus: ouvert\n\nau lieu de rien.\n',
        encoding="utf-8",
    )
    assert sig.open_signalements(tmp_path) == ()  # the drained report stays drained
    sig.mark_handled(path, today=date(2026, 7, 21))
    assert "status: ouvert\n\nau lieu de rien." in path.read_text(encoding="utf-8")  # body untouched


# ---- draining (the Mnemosyne side) ---------------------------------------------------
def test_draining_preserves_the_body_byte_for_byte(tmp_path: Path) -> None:
    path = _filed(tmp_path)
    path.write_text(
        '---\nstatus: ouvert\ndate: "2026-07-20"\ntitre: "x"\n---\n\nCE QUE J AI ECRIT\n', encoding="utf-8"
    )
    sig.mark_handled(path, today=date(2026, 7, 21))
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\nCE QUE J AI ECRIT\n")  # the human's prose is untouched
    assert "status: traite" in text and 'traite_le: "2026-07-21"' in text


def test_draining_preserves_a_crlf_body_verbatim(tmp_path: Path) -> None:
    """"Byte-for-byte" holds for a body written on CRLF too. The guarantee is scoped honestly: the
    BODY is spliced back untouched, while the machine-managed frontmatter block is re-emitted in
    ``\\n`` (its closing ``---`` line belongs to the block, not to the prose)."""
    path = tmp_path / "2026-07-20-crlf.md"
    path.write_bytes(b'---\r\nstatus: ouvert\r\ntitre: "x"\r\n---\r\n\r\nMON CORPS\r\n')
    sig.mark_handled(path, today=date(2026, 7, 21))
    assert path.read_bytes().endswith(b"\r\nMON CORPS\r\n")  # the prose kept its own line endings
    assert b"status: traite" in path.read_bytes()


def test_draining_is_idempotent(tmp_path: Path) -> None:
    """Re-running the drain never re-stamps an already-handled report (no second traite_le line)."""
    path = _filed(tmp_path)
    sig.mark_handled(path, today=date(2026, 7, 21))
    once = path.read_text(encoding="utf-8")
    sig.mark_handled(path, today=date(2026, 7, 22))
    assert path.read_text(encoding="utf-8") == once


def test_a_reopened_report_carries_a_single_drain_stamp(tmp_path: Path) -> None:
    """Re-opening by hand then re-draining must not leave two ``traite_le:`` keys in the frontmatter."""
    path = _filed(tmp_path)
    sig.mark_handled(path, today=date(2026, 7, 21))
    path.write_text(
        path.read_text(encoding="utf-8").replace("status: traite", "status: ouvert"), encoding="utf-8"
    )
    sig.mark_handled(path, today=date(2026, 7, 22))
    assert path.read_text(encoding="utf-8").count("traite_le:") == 1


# ---- the proposer source (how it reaches the project's owner) ------------------------
def test_source_is_silent_when_nothing_is_filed() -> None:
    assert SignalementReview(lambda: 0).scan() == ()  # silence is correct, not a gap


def test_source_reports_a_count_never_the_title() -> None:
    """Invariant 22 / D66: the filing session sits inside ANOTHER project's context, so the proposal
    carries HOW MANY and the remedy — never a title, never a path."""
    (draft,) = SignalementReview(lambda: 2).scan()
    assert "2 field signalements" in draft.summary
    assert "make signalements" in draft.summary


# ---- AGE, and why it exists (measured 2026-09-08) -------------------------------------
# WHAT THESE WITNESSES HOLD, AND WHAT DID NOT EXIST BEFORE: the count ALONE was published
# faithfully at every session start — and 12 reports stayed open for 27 days. A count says the
# SIZE of a queue, never its STASIS. Each witness below was SABOTAGED before being locked in:
# removing the age, removing the prefix, or removing the threshold turns one red, never zero.
def test_age_of_the_oldest_open_report_comes_from_the_name_never_the_mtime(tmp_path: Path) -> None:
    """Age is read from the NAME'S STAMP: a `git checkout`, a copy, or an iCloud sync rewrite the
    mtime without the report having moved by even a day."""
    assert sig.oldest_open_signalement_age_days(tmp_path) is None  # empty queue ⇒ None, never 0
    sig.file_signalement("le vieux", root=tmp_path, today=date(2026, 8, 12))
    sig.file_signalement("le recent", root=tmp_path, today=date(2026, 9, 1))
    assert sig.oldest_open_signalement_age_days(tmp_path, today=date(2026, 9, 8)) == 27


def test_an_unreadable_stamp_is_skipped_never_guessed(tmp_path: Path) -> None:
    """An unreadable date does NOT manufacture an age — in either direction. It is skipped."""
    sig.file_signalement("le vieux", root=tmp_path, today=date(2026, 8, 12))
    (tmp_path / "pas-une-date-du-tout.md").write_text(
        '---\nstatus: ouvert\n---\ncorps\n', encoding="utf-8"
    )
    assert sig.oldest_open_signalement_age_days(tmp_path, today=date(2026, 9, 8)) == 27


def test_a_future_stamp_is_clamped_never_negative(tmp_path: Path) -> None:
    """A clock running ahead would make a queue "younger than empty" — clamped to 0."""
    sig.file_signalement("horloge en avance", root=tmp_path, today=date(2026, 12, 25))
    assert sig.oldest_open_signalement_age_days(tmp_path, today=date(2026, 9, 8)) == 0


def test_the_summary_carries_the_age_because_a_count_hides_stasis() -> None:
    (draft,) = SignalementReview(lambda: 12, lambda: 27).scan()
    assert "27 days" in draft.summary  # THE number that separates a queue from an outage


def test_a_stale_queue_leaves_the_proposals_block_a_fresh_one_does_not() -> None:
    """ THE CORE OF IT: a signal filed among options IS an option. Below the threshold it stays a
 proposal; beyond it, it is a DEBT recorded by a third party, and it leaves the block."""
    seuil = SignalementReview.STASE_JOURS
    (vieux,) = SignalementReview(lambda: 12, lambda: seuil).scan()
    (frais,) = SignalementReview(lambda: 12, lambda: seuil - 1).scan()
    assert vieux.summary.startswith(DETTE_PREFIX)
    assert not frais.summary.startswith(DETTE_PREFIX)
    assert "12 field signalements" in frais.summary  # below the threshold, the signal is published ANYWAY


def test_a_missing_age_degrades_to_the_old_line_and_never_silences_the_signal() -> None:
    """An unavailable age weakens the line; it NEVER makes it disappear."""
    (draft,) = SignalementReview(lambda: 3).scan()
    assert "3 field signalements" in draft.summary
    assert "age not measured" in draft.summary
    assert not draft.summary.startswith(DETTE_PREFIX)


def test_the_debt_is_rendered_above_the_propose_never_impose_block() -> None:
    """The highlighting must survive all the way to the RENDER, not just the draft -- the render
    is what the project's owner reads."""
    from mnemosyne.api.core_api import Proposal

    dette = Proposal(
        id="d", source="s", summary=f"{DETTE_PREFIX}12 en attente, le plus vieux a 27 jours"
    )
    autre = Proposal(id="a", source="s", summary="4 fichiers a ranger")
    rendu = render_proposals((autre, dette))
    assert rendu.index("dette qu'un TIERS") < rendu.index("propose, jamais impose")
    assert DETTE_PREFIX not in rendu  # the prefix is a MARKER, never text for the human
    assert "27 jours" in rendu


# ---- the CLI (the only surface a human or a project session touches) ------------------
def test_cli_lists_nothing_honestly_then_the_filed_report(tmp_path: Path, capsys) -> None:
    assert main([], root=tmp_path) == 0
    assert "No field report pending." in capsys.readouterr().out
    _filed(tmp_path)
    assert main([], root=tmp_path) == 0
    assert "1 field report waiting" in capsys.readouterr().out


def test_cli_files_from_the_environment_not_the_shell(tmp_path: Path, capsys, monkeypatch) -> None:
    """``make signaler`` passes the title through ``MNEMO_TITRE`` so backticks / ``$(...)`` in a title
    are never interpolated into a shell recipe."""
    monkeypatch.setenv("MNEMO_TITRE", "`echo pwned` a casse")
    assert main(["--nouveau"], root=tmp_path) == 0
    assert "Field report opened" in capsys.readouterr().out
    (filed,) = sig.open_signalements(tmp_path)
    assert "echo-pwned-a-casse" in filed.name  # inert text in a filename, never a command


def test_cli_refuses_an_empty_title(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MNEMO_TITRE", raising=False)
    assert main(["--nouveau"], root=tmp_path) == 2  # a usage line, never an untitled report
    assert sig.open_signalements(tmp_path) == ()


def test_render_open_is_pure_and_lists_paths(tmp_path: Path) -> None:
    assert "No field report pending" in render_open(())
    assert "2026-07-20-make-search-plante.md" in render_open((_filed(tmp_path),))


# ---- D4 -- the braise: the report becomes a PLAN ITEM, never a detour outside the plan -----


def _item(niveau: str = "menace", cout: str = "1 test") -> str:
    return sig.item_de_braise(
        titre="un titre de braise",
        niveau=niveau,
        cout=cout,
        identifiant="BR47",
        chemin_signalement="docs/signalements/2026-08-04-x.md",
    )


def test_une_braise_sans_cout_est_refusee() -> None:
    """*Obligation* level 2 of D4, verbatim in the item: a braise with no declared cost is
    refused -- never an item silently created without its cost."""
    try:
        _item(cout="")
    except ValueError as exc:
        assert "co" in str(exc).lower()  # "coût" -- accent-tolerant, whatever the terminal encoding
    else:
        raise AssertionError("an empty cost must raise, never produce an item")
    try:
        _item(cout="   ")  # blank-only == empty
    except ValueError:
        pass
    else:
        raise AssertionError("a cost made only of spaces must raise too")


def test_un_niveau_hors_vocabulaire_leve_plutot_que_de_deviner() -> None:
    try:
        _item(niveau="critique")  # not in NIVEAUX_BRAISE -- does not exist, is not guessed
    except ValueError as exc:
        assert "critique" in str(exc)
    else:
        raise AssertionError("a level outside {invalide, menace} must raise")


def test_niveau_INVALIDE_declare_le_blocage_niveau_MENACE_ne_bloque_rien() -> None:
    """The distinction the whole item rests on (D4): only `invalide` blocks the arc it was born
    in."""
    bloc_invalide = _item(niveau="invalide")
    bloc_menace = _item(niveau="menace")
    assert "BLOCKS the arc" in bloc_invalide
    assert "blocks NO step" in bloc_menace
    assert "niveau 2" in bloc_invalide  # *Obligation* reflects the level
    assert "niveau 1" in bloc_menace


def test_le_bloc_rendu_declare_les_SIX_champs_obliges_via_le_LECTEUR_REEL() -> None:
    """ The witness that matters: not an assumption about the format, a check AGAINST the real
 reader of `plan_format.py` (chat 1, outside my batch -- never modified, only called for
 reading). An invented field (`*Origine*`, `*Coût*`) would be silently swallowed without being
 attached to anything; ONLY the fields from `KNOWN_FIELDS` must appear here, all SIX MANDATORY
 fields present, no ``missing_fields``."""
    from mnemosyne.production.plan_format import FIELD_NAMES, read_item_fields

    bloc = _item()
    lignes = bloc.split("\n")
    champs = dict(read_item_fields(lignes[0], tuple(lignes[1:])))
    manquants = [nom for token, nom in FIELD_NAMES.items() if token not in champs]
    assert manquants == [], f"mandatory fields missing from the rendered block: {manquants}"
    assert champs["taille"] == "1 test"
    assert "obligation" in champs  # known-but-not-mandatory (EXTRA_FIELD_NAMES), present anyway


def test_item_de_braise_EMET_test_a_trois_la_CLASSE_pas_seulement_les_CAS_repares() -> None:
    """ **Triggered by the orchestrator (2026-08-15, 22:01): the first FIVE real braises had been
 fixed one by one (`*Test à trois*` added by hand to each existing item)** -- that closed the
 CASES, not the CLASS: `item_de_braise` itself never emitted that field, so a sixth braise would
 have turned `test_chaque_item_repond_au_test_a_trois` red exactly like the five before it.
 *`grep 'Test à trois' production/signalements.py` returned `0`, measured before this fix.* This
 witness locks in the GENERATOR, not an item fixed by hand."""
    from mnemosyne.production.plan_format import read_item_fields

    bloc = _item()
    lignes = bloc.split("\n")
    champs = dict(read_item_fields(lignes[0], tuple(lignes[1:])))
    assert "test_a_trois" in champs, (
        "the field must be PRESENT in EVERY generated braise -- never a silence about what the "
        "generator ignores"
    )
    assert champs["test_a_trois"].strip(), "present but EMPTY would be the same defect under another name"


def test_le_bloc_rendu_est_reconnu_comme_un_item_par_le_LECTEUR_DE_PLAN_COMPLET() -> None:
    """One notch above the previous test: not just `read_item_fields` on a fragment, but
    `read_plan` (PURE, over the TEXT) on a whole DOCUMENT -- the item must be a valid GATE, not
    just a list of fields that happens to parse."""
    from mnemosyne.production.plan_format import read_plan

    doc = "# ARC TEST\n\n## 1 · Un arc\n\n" + _item() + "\n"
    reading = read_plan(doc, origin="plan-test.md")
    idents = [item.ident for item in reading.items]
    assert "BR47" in idents
    item = next(i for i in reading.items if i.ident == "BR47")
    assert item.missing_fields == ()


def test_un_identifiant_TROP_LONG_disparait_du_lecteur_reel() -> None:
    """ FOUND BY CHECKING, NOT ASSUMED: my first attempt used identifier
 ``BRAISE-2026-08-04`` (18 characters) -- `read_item_fields` alone read it just fine, but
 `read_plan` (the FULL reader) returned ZERO items. Cause: `plan_format._IDENT_RE` bounds an
 identifier to 12 characters (`[A-Za-z][A-Za-z0-9-]{0,11}`). This witness locks in the proof
 rather than just the lesson: whoever builds the edge that generates real identifiers must stay
 under that bound, and this test turns red if they forget."""
    from mnemosyne.production.plan_format import read_plan

    trop_long = sig.item_de_braise(
        titre="x", niveau="menace", cout="1 test",
        identifiant="BRAISE-2026-08-04", chemin_signalement="docs/signalements/x.md",
    )
    doc = "# ARC TEST\n\n## 1 · Un arc\n\n" + trop_long + "\n"
    reading = read_plan(doc, origin="plan-test.md")
    assert "BRAISE-2026-08-04" not in [item.ident for item in reading.items]  # proof of the trap
    court = _item()  # BR47 -- 4 characters, under the bound
    reading_ok = read_plan("# ARC TEST\n\n## 1 · Un arc\n\n" + court + "\n", origin="plan-test.md")
    assert "BR47" in [item.ident for item in reading_ok.items]  # same format, short identifier


def test_identifiant_libre_part_a_BR1_sur_un_ensemble_vide() -> None:
    assert sig.identifiant_libre(frozenset()) == "BR1"


def test_identifiant_libre_saute_les_identifiants_deja_pris() -> None:
    assert sig.identifiant_libre(frozenset({"BR1", "BR2", "BR4"})) == "BR3"
    assert sig.identifiant_libre(frozenset({"BR1", "BR2", "BR3"})) == "BR4"


def test_identifiant_libre_respecte_un_prefixe_different() -> None:
    assert sig.identifiant_libre(frozenset({"X1"}), prefixe="X") == "X2"
    assert sig.identifiant_libre(frozenset({"BR1"}), prefixe="X") == "X1"  # distinct prefixes, no cross-collision


# ---- inserer_item -- never guess the section, exact reconstruction elsewhere --------------


_PLAN_A_DEUX_ARCS = (
    "# PLAN — un plan de test\n\n"
    "> **Cap** : fermer les deux arcs\n\n"
    "## 1 · Premier arc\n\n"
    "- **A1** \U00002705 **Un item déjà fait.**\n"
    "  *Produit* : x\n\n"
    "## 2 · Second arc\n\n"
    "- **B1** \U00002B1C **Un item du second arc.**\n"
    "  *Produit* : y\n\n"
    "Une note de fin d'arc, écrite par l'opérateur.\n"
)


def test_inserer_refuse_une_section_introuvable() -> None:
    try:
        sig.inserer_item(_PLAN_A_DEUX_ARCS, sous_section="## 9 · N'existe pas", bloc_item=_item())
    except ValueError as exc:
        assert "introuvable" in str(exc)
    else:
        raise AssertionError("a missing section must raise, never create a phantom section")


def test_inserer_ajoute_a_la_FIN_de_la_bonne_section_SEULE() -> None:
    resultat = sig.inserer_item(
        _PLAN_A_DEUX_ARCS, sous_section="## 1 · Premier arc", bloc_item=_item()
    )
    # the second arc, meanwhile, is INTACT -- checked character for character
    assert "## 2 · Second arc\n\n- **B1** \U00002B1C **Un item du second arc.**\n  *Produit* : y\n\n" in resultat
    assert "Une note de fin d'arc, écrite par l'opérateur.\n" in resultat
    # the new item lands UNDER the first arc, not the second
    idx_arc1, idx_nouvel_item, idx_arc2 = (
        resultat.index("## 1 ·"), resultat.index("BR47"), resultat.index("## 2 ·")
    )
    assert idx_arc1 < idx_nouvel_item < idx_arc2


def test_inserer_preserve_TOUT_le_texte_AVANT_la_section_cible_octet_pour_octet() -> None:
    resultat = sig.inserer_item(
        _PLAN_A_DEUX_ARCS, sous_section="## 2 · Second arc", bloc_item=_item()
    )
    avant = _PLAN_A_DEUX_ARCS[: _PLAN_A_DEUX_ARCS.index("## 2 ·")]
    assert resultat.startswith(avant)


def test_inserer_dans_la_DERNIERE_section_va_jusqu_a_la_fin_du_fichier() -> None:
    """No section follows -- the insertion gap must be the end of the text, not a phantom section
    found by mistake. "At the end of the section" means after ALL of its content, the operator's
    note included -- not just after the last declared item."""
    resultat = sig.inserer_item(
        _PLAN_A_DEUX_ARCS, sous_section="## 2 · Second arc", bloc_item=_item()
    )
    assert resultat.endswith(  # the new item does close out the file
        "*Taille* : 1 test\n"
        "  *Test à trois* : to be specified by whoever picks up the item -- depends on the shape "
        "of the fix, not on the diagnosis alone.\n\n"
    )
    note_idx, item_idx = resultat.index("Une note de fin"), resultat.index("BR47")
    assert note_idx < item_idx  # the operator's note stays BEFORE the new item, never moved
    assert resultat.index("BR47") > resultat.index("**B1**")


def test_le_plan_RECONSTRUIT_est_LU_correctement_par_le_lecteur_reel() -> None:
    """The proof that matters: not that the text contains the expected substring, but that
    `read_plan` (chat 1, never modified) recognises the RECONSTRUCTED plan in its ENTIRETY -- the
    old item AND the new one, neither broken by the insertion."""
    from mnemosyne.production.plan_format import read_plan

    resultat = sig.inserer_item(
        _PLAN_A_DEUX_ARCS, sous_section="## 1 · Premier arc", bloc_item=_item()
    )
    reading = read_plan(resultat, origin="plan-test.md")
    idents = [item.ident for item in reading.items]
    assert idents == ["A1", "BR47", "B1"]  # order preserved, nothing lost, nothing duplicated
    nouvel_item = next(i for i in reading.items if i.ident == "BR47")
    assert nouvel_item.missing_fields == ()


# ---- D4 -- the ordering witness: a MENACE braise blocks no step at all --------------------

_PLAN_AVEC_GRAPHE = (
    "# PLAN — un graphe de test\n\n"
    "## 1 · Un arc avec des dépendances réelles\n\n"
    "- **C1** \U00002B1C **Ne dépend de rien -- deux autres items en dépendent.**\n"
    "  *Produit* : x\n"
    "  *Dépend de* : AUCUNE\n\n"
    "- **C2** \U00002B1C **Dépend de C1.**\n"
    "  *Produit* : x\n"
    "  *Dépend de* : C1\n\n"
    "- **C3** \U00002B1C **Dépend de C1 aussi.**\n"
    "  *Produit* : x\n"
    "  *Dépend de* : C1\n\n"
    "- **C4** \U00002B1C **Dépend de C2 et C3 -- personne n'en dépend.**\n"
    "  *Produit* : x\n"
    "  *Dépend de* : C2, C3\n\n"
    "- **C5** \U00002B1C **Indépendant -- ne dépend de rien, personne n'en dépend.**\n"
    "  *Produit* : x\n"
    "  *Dépend de* : AUCUNE\n\n"
)

_PREEXISTANTS = ("C1", "C2", "C3", "C4", "C5")


def _vague_de(ordre, ident: str) -> int:
    return next(i for i, vague in enumerate(ordre.vagues) if ident in vague)


def _classement(attente, ident: str) -> tuple[str, str, int | None]:
    """``(statut, raison, debloque)`` for an ident -- 'libre' or 'ecarte', never both (the
    partition is checked by `file_d_attente` itself, via its own assert)."""
    for r in attente.rangs:
        if r.ident == ident:
            return ("libre", r.raison, r.debloque)
    for i, raison in attente.ecartes:
        if i == ident:
            return ("ecarte", raison, None)
    raise AssertionError(f"{ident} missing from both sides of the partition -- should never happen")


def test_une_braise_MENACE_ne_bloque_aucune_etape_deja_existante() -> None:
    """D4's *Fini quand*, the clause that holds ONLY for `menace` (never `invalide`, see
 `test_niveau_INVALIDE_declare_le_blocage_niveau_MENACE_ne_bloque_rien`): "a `menace` braise
 blocks no step at all -- checked by a witness." The witness calls the REAL scheduler
 (`plan_ordre`, chat 1 -- outside my batch, never modified) on a graph BEFORE and AFTER
 insertion, and proves nothing that already existed moves:

 * same WAVE (the set, never the order within a wave -- `freeze-the-set-not-the-count`);
 * same UNBLOCKING count (`ordre.deblocages`);
 * no CYCLE introduced;
 * same RANKING in the queue (`file_d_attente`) -- free or set aside, and the same reason written.

 This is true BY CONSTRUCTION: `item_de_braise` always writes `*Dépend de* : AUCUNE` (a fixed
 line, never derived from the level) -- so the new item has NO outgoing edge, and since
 `inserer_item` never touches the text of the OTHER items, nothing can cite it back. An isolated
 node added to an acyclic graph changes neither the waves nor the unblocking of anyone else --
 that is the property this witness checks against the REAL scheduler, rather than trusting it to
 reasoning in a comment.

 **What this witness does NOT claim**: the NUMERIC RANK (the position in the queue) can slip
 by one for a pre-existing item tied on unblocking (0) with the braise -- `C5` proves it below.
 `BR47` < `C5` alphabetically, and the tiebreak on a draw IS the alphabet (see `file_d_attente`'s
 docstring). This slip is not a block: `C5` stays FREE, with the same `debloque` and the same
 reason -- only its position number in a list with one more member changed. Claiming otherwise
 would have been a broader guarantee than the clause asks for."""
    from mnemosyne.production import plan_ordre
    from mnemosyne.production.plan_format import read_plan

    avant = read_plan(_PLAN_AVEC_GRAPHE, origin="plan-test.md")
    ordre_avant = plan_ordre.ordonner(avant)
    file_avant = plan_ordre.file_d_attente(avant)
    assert ordre_avant.cycle == ()  # the starting graph is a DAG -- otherwise the witness proves nothing

    resultat = sig.inserer_item(
        _PLAN_AVEC_GRAPHE,
        sous_section="## 1 · Un arc avec des dépendances réelles",
        bloc_item=_item(niveau="menace"),
    )
    apres = read_plan(resultat, origin="plan-test.md")
    assert "BR47" in [i.ident for i in apres.items]  # the insertion did happen
    ordre_apres = plan_ordre.ordonner(apres)
    file_apres = plan_ordre.file_d_attente(apres)

    assert ordre_apres.cycle == ()  # an isolated node can never close a cycle

    deblocages_avant = dict(ordre_avant.deblocages)
    deblocages_apres = dict(ordre_apres.deblocages)
    for ident in _PREEXISTANTS:
        assert _vague_de(ordre_avant, ident) == _vague_de(ordre_apres, ident), (
            f"{ident} changed wave -- a menace braise must shift NOTHING"
        )
        assert deblocages_avant[ident] == deblocages_apres[ident], (
            f"{ident} unblocks a different count after the braise was inserted"
        )
        assert _classement(file_avant, ident) == _classement(file_apres, ident), (
            f"{ident} changed ranking (free/set-aside) or reason"
        )

    # the only thing that moves: C5's NUMERIC RANK, from alphabetical tiebreaking against BR47
    # (both at 0 unblocking) -- proven here rather than assumed, so the exact scope of the
    # guarantee above is checked, not just claimed in prose.
    rang_c5_avant = next(r for r in file_avant.rangs if r.ident == "C5")
    rang_c5_apres = next(r for r in file_apres.rangs if r.ident == "C5")
    assert rang_c5_apres.rang == rang_c5_avant.rang + 1
    assert rang_c5_apres.debloque == rang_c5_avant.debloque
    assert rang_c5_apres.raison == rang_c5_avant.raison


# ---- D4 -- inserer_dans_larc and _sans_lignes_finales, PURE, outside the sole CLI path (defect N4
# of the second D75 audit: these two functions were only exercised indirectly, never as a direct witness) --


def test_inserer_dans_larc_va_a_la_fin_du_texte_sans_aucune_section() -> None:
    """The "no `## ` at all" branch -- never exercised by the CLI witnesses (D75 audit, defect N4)."""
    plan = "# ARC Z · Solo\n\n- **Z1** \U00002B1C **Seul.**\n  *Produit* : x\n"
    resultat = sig.inserer_dans_larc(plan, bloc_item=_item())
    assert resultat.index("**Z1**") < resultat.index("BR47")
    assert resultat.rstrip("\n").endswith(
        "to be specified by whoever picks up the item -- depends on the shape of the fix, not on the "
        "diagnosis alone."
    )


def test_inserer_dans_larc_cible_le_PREMIER_meme_quand_il_porte_un_item() -> None:
    """Reproduces the real shape of the foundation-arc document (not part of this mirror, second
    D75 audit, defect N3): TWO `## ` sections, the FIRST one containing a real item (`A8`).
    `inserer_dans_larc` still targets the FIRST `## ` it meets -- proven here directly, not just
    claimed in the docstring after the fix."""
    from mnemosyne.production.plan_format import read_plan

    plan = (
        "# ARC Z · Deux sections\n\n"
        "- **Z1** \U00002B1C **Avant les deux sections.**\n"
        "  *Produit* : x\n\n"
        "## Une section qui porte un item\n\n"
        "- **Z2** \U00002B1C **Dans la première section, comme A8 dans le vrai corpus.**\n"
        "  *Produit* : y\n\n"
        "## Ce que cet arc ne porte PAS\n\n"
        "Rien.\n"
    )
    resultat = sig.inserer_dans_larc(plan, bloc_item=_item())
    # the new item lands BEFORE the first section -- so before Z2 too, even though Z2 is a "real"
    # item: the function targets a structural POSITION, never a judgment on the content
    assert resultat.index("BR47") < resultat.index("## Une section")
    reading = read_plan(resultat, origin="z.md")
    assert [i.ident for i in reading.items] == ["Z1", "BR47", "Z2"]
    assert reading.problems == ()


def test_sans_lignes_finales_traite_CRLF_comme_une_UNITE() -> None:
    """The fix for the self-found defect (`rstrip("\\n")` left an orphan `\\r`) -- tested directly
    on the function, not just observed by ricochet through the CLI."""
    assert sig._sans_lignes_finales("x\r\n\r\n") == "x"
    assert sig._sans_lignes_finales("x\n\n") == "x"
    assert sig._sans_lignes_finales("x\r\r") == "x"
    assert sig._sans_lignes_finales("x") == "x"


# ---- D4 -- the CLI: extended `make signaler` ALSO deposits the item (D4's Produit, no new command) --


def _plan_dossier(tmp_path: Path, *, arcs: dict[str, str]) -> Path:
    """A minimal FOLDER-plan -- carries `PLAN.md` + one file per arc under `plan/` -- the shape
    `read_plan_tree` REALLY requires (D166): a gate must be named exactly `PLAN.md` or
    `PLAN_COURANT.md`; a lone file with an arbitrary name is found by NEITHER of the two legal
    shapes (single-file or folder) -- exactly what the D75 audit measured."""
    (tmp_path / "plan").mkdir()
    index = ["# PLAN -- demo", "", "> **Cap** : prouver", ""]
    for nom, corps in arcs.items():
        (tmp_path / "plan" / nom).write_text(corps, encoding="utf-8")
        index.append(f"- `plan/{nom}` -- arc")
    (tmp_path / "PLAN.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return tmp_path


#: Same shape as the REAL corpus (this repo's plan arc files, not part of this mirror): a single
#: `#`, flat items, then EXACTLY one `## ` section -- never a container for items, verified by the
#: D75 audit on the 11 real arc files.
_ARC_A = (
    "# ARC A · Premier\n\n"
    "- **A1** \U00002705 **Déjà fait.**\n"
    "  *Produit* : x\n\n"
    "## Ce que cet arc ne porte PAS\n\n"
    "Rien de pertinent ici.\n"
)
_ARC_B = (
    "# ARC B · Second\n\n"
    "- **B1** \U00002B1C **À faire.**\n"
    "  *Produit* : y\n\n"
    "## Ce que cet arc ne porte PAS\n\n"
    "Rien de pertinent ici non plus.\n"
)


def _braise_env(
    monkeypatch, *, niveau: str = "menace", cout: str = "1 test", plan: Path | None = None
) -> None:
    monkeypatch.setenv("MNEMO_TITRE", "un titre de braise CLI")
    monkeypatch.setenv("MNEMO_NIVEAU", niveau)
    monkeypatch.setenv("MNEMO_COUT", cout)
    if plan is not None:
        monkeypatch.setenv("MNEMO_PLAN", str(plan))


def test_cli_niveau_sans_cout_plan_refuse_mais_garde_le_rapport(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """D2 again: NIVEAU triggers the braise path, but guesses NOTHING about the other two fields --
    a single one missing is enough to refuse. The report itself stays filed (invariant 2)."""
    monkeypatch.setenv("MNEMO_TITRE", "x casse")
    monkeypatch.setenv("MNEMO_NIVEAU", "menace")
    monkeypatch.delenv("MNEMO_COUT", raising=False)
    monkeypatch.delenv("MNEMO_PLAN", raising=False)
    assert main(["--nouveau"], root=tmp_path) == 2
    err = capsys.readouterr().err
    assert "but COUT and PLAN missing" in err
    assert len(sig.open_signalements(tmp_path)) == 1


def test_cli_COUT_seul_manquant_refuse(tmp_path: Path, monkeypatch, capsys) -> None:
    """ Second D75 audit (MEDIUM defect #N1): a first shot at this witness used
 ``"COUT" in err`` -- a test that DOES NOT BITE, proven by independent sabotage. pytest's
 `tmp_path` is derived from the function's NAME, which already contains the substring ``COUT``;
 removing the requirement in the code fell through to `Plan not found: {chemin}`, whose path
 contained the folder `test_cli_COUT_seul_manquant_re0/…` -- the same substring, for the WRONG
 reason. Fixed: it now checks the EXACT PHRASE the code produces (anchored by
 ``but``/``missing``, which no path can reproduce by accident), never a bare word that can
 also live inside a test's path."""
    _braise_env(monkeypatch, plan=tmp_path / "peu-importe.md")
    monkeypatch.delenv("MNEMO_COUT", raising=False)
    assert main(["--nouveau"], root=tmp_path) == 2
    assert "but COUT missing" in capsys.readouterr().err


def test_cli_PLAN_seul_manquant_refuse(tmp_path: Path, monkeypatch, capsys) -> None:
    """Same defect, the other half: COUT is present, only PLAN is missing. Same witness fix as
    above (exact phrase, never a bare word against text that can carry a path)."""
    _braise_env(monkeypatch)
    monkeypatch.delenv("MNEMO_PLAN", raising=False)
    assert main(["--nouveau"], root=tmp_path) == 2
    assert "but PLAN missing" in capsys.readouterr().err


def test_cli_plan_introuvable_refuse_et_garde_le_rapport(tmp_path: Path, monkeypatch, capsys) -> None:
    """ Second D75 audit (LOW defect #N2, same class as #N1): ``"introuvable" in err.lower()``
 also passed when the function's entire test (`is_file()`) was sabotaged -- THIS function's own
 name already contains ``introuvable``, and the fallback refusal (`Plan unreadable under
 {racine}`) prints `racine`, which EQUALS `tmp_path`, whose folder name carries the same word.
 Fixed with a `startswith` on the message's exact prefix -- anchored at the START of the output,
 never a substring that could live anywhere in a path printed further along."""
    _braise_env(monkeypatch, plan=tmp_path / "n-existe-pas.md")
    assert main(["--nouveau"], root=tmp_path) == 2
    assert capsys.readouterr().err.startswith("Plan not found: ")
    assert len(sig.open_signalements(tmp_path)) == 1


def test_cli_sans_porte_PLAN_md_refuse_plan_illisible(tmp_path: Path, monkeypatch, capsys) -> None:
    """A lone file, even valid as TEXT, is found by neither of the two legal shapes (D166):
 `read_plan_tree` requires a gate named `PLAN.md`/`PLAN_COURANT.md` somewhere above it. The
 report stays filed regardless (invariant 2).

 **FIXED (3rd D75 audit): the original sentence claimed THIS function's name leaks
 "illisible" into its `tmp_path`, like its two neighboring witnesses -- measured FALSE.** pytest
 truncates the generated folder to 30 characters (`test_cli_sans_porte_PLAN_md_re0`), which
 never reaches "illisible". This particular witness was therefore not vulnerable to the leak
 measured on `COUT` and `introuvable`. The exact-prefix assertion remains the right shape
 anyway, for consistency with its neighbors and for defense in depth -- never a bare word
 against text that can carry a path, whether THIS specific name leaks today or not."""
    orphelin = tmp_path / "orphelin.md"
    orphelin.write_text(_ARC_A, encoding="utf-8")
    _braise_env(monkeypatch, plan=orphelin)
    assert main(["--nouveau"], root=tmp_path) == 2
    assert capsys.readouterr().err.startswith("Plan unreadable under ")
    assert len(sig.open_signalements(tmp_path)) == 1


def test_cli_SEC_par_defaut_affiche_l_item_et_n_ecrit_rien(tmp_path: Path, monkeypatch, capsys) -> None:
    """Same convention as `plan-archiver`/`plan-convertir`: DRY-RUN by default, proven on the REAL
    file (not just the output), APPLY=1 is the only thing that writes. The SECOND arc, never
    targeted, stays intact -- the cross-file read (audit defect 1) must write NOTHING outside the
    target."""
    racine = _plan_dossier(tmp_path, arcs={"a.md": _ARC_A, "b.md": _ARC_B})
    cible = racine / "plan" / "a.md"
    avant = cible.read_text(encoding="utf-8")
    _braise_env(monkeypatch, plan=cible)
    assert main(["--nouveau"], root=tmp_path) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out  # "SEC" alone leaked in from THIS test's own name -- defect #N1 class
    assert "un titre de braise CLI" in out  # the item is shown, not just announced
    assert cible.read_text(encoding="utf-8") == avant
    assert (racine / "plan" / "b.md").read_text(encoding="utf-8") == _ARC_B


def test_cli_APPLY_insere_AVANT_la_section_ce_que_larc_ne_porte_pas(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """HIGH defect #2 of the D75 audit: `inserer_item(sous_section=…)` required a NAMED `## `
    section, yet on the REAL corpus that is the ONLY `## ` section of each arc and it NEVER
    contains an item (`## Ce que cet arc ne porte PAS`). `inserer_dans_larc` targets the arc's
    body, never that section -- proven here by checking the new item lands BEFORE it."""
    from mnemosyne.production.plan_format import read_plan

    racine = _plan_dossier(tmp_path, arcs={"a.md": _ARC_A})
    cible = racine / "plan" / "a.md"
    _braise_env(monkeypatch, plan=cible)
    assert main(["--nouveau", "--apply"], root=tmp_path) == 0
    assert "written into" in capsys.readouterr().out
    texte = cible.read_text(encoding="utf-8")
    assert texte.index("BR1") < texte.index("## Ce que cet arc ne porte PAS")
    reading = read_plan(texte, origin="a.md")
    assert [i.ident for i in reading.items] == ["A1", "BR1"]  # order preserved, nothing lost
    nouvel_item = next(i for i in reading.items if i.ident == "BR1")
    assert nouvel_item.missing_fields == ()


def test_cli_deux_braises_dans_DEUX_ARCS_DIFFERENTS_n_entrent_jamais_en_collision(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """THE HIGH defect #1 of the D75 audit, the one that invalidated *Fini quand* itself: a first
    version only read the TARGET FILE to pick the identifier -- two braises filed into two
    DIFFERENT arcs would then pick the SAME identifier, each only seeing its own file. The FOLDED
    plan (`replier`, the one the rest of the repo actually reads) would silently lose one of them
    as `id_duplique`. Proven here against the REAL `read_plan_tree` + `replier`, never a lone file
    that structurally cannot see the defect."""
    from mnemosyne.production.carte import replier
    from mnemosyne.production.plan_registry import read_plan_tree

    racine = _plan_dossier(tmp_path, arcs={"a.md": _ARC_A, "b.md": _ARC_B})
    _braise_env(monkeypatch, plan=racine / "plan" / "a.md")
    assert main(["--nouveau", "--apply"], root=tmp_path) == 0
    monkeypatch.setenv("MNEMO_TITRE", "une seconde braise")
    monkeypatch.setenv("MNEMO_PLAN", str(racine / "plan" / "b.md"))
    assert main(["--nouveau", "--apply"], root=tmp_path) == 0

    lectures = [p.reading for p in read_plan_tree(racine, "demo") if p.reading is not None]
    reading, collisions = replier(lectures)
    assert collisions == ()  # THE proof that matters: no duplicate identifier on the FOLDED plan
    idents = sorted(i.ident for i in reading.items if i.ident)
    assert idents == ["A1", "B1", "BR1", "BR2"]  # the two braises, two DISTINCT identifiers


def test_cli_lit_et_ecrit_un_plan_CRLF_sans_le_traduire(tmp_path: Path, monkeypatch, capsys) -> None:
    """MEDIUM defect of the D75 audit: ``Path.read_text`` silently normalises line endings ON
    READ -- the write side was already correct (``atomic_write``, ``newline=""``), but the READ
    side had already destroyed the guarantee before anything else ran. Proven on a genuinely CRLF
    arc: the pre-existing text, on both sides of the insertion gap, keeps its original ``\\r\\n``."""
    racine = _plan_dossier(tmp_path, arcs={"a.md": _ARC_A})
    cible = racine / "plan" / "a.md"
    cible.write_bytes(_ARC_A.replace("\n", "\r\n").encode("utf-8"))
    _braise_env(monkeypatch, plan=cible)
    assert main(["--nouveau", "--apply"], root=tmp_path) == 0
    brut = cible.read_bytes()
    assert b"\r\n- **A1**" in brut  # UPSTREAM of the gap: the original CRLF survives
    assert b"\r\n\r\n## Ce que cet arc ne porte PAS" in brut  # DOWNSTREAM: same


# ---- the wiring (and its hermeticity) ------------------------------------------------
def test_tick_surfaces_a_filed_signalement_from_the_injected_tree(tmp_path: Path) -> None:
    """The tick derives the signalement directory from ``repo_root``, so a test that isolates the
    tree isolates this source too — a hardcoded default would count the REAL repo's reports from
    inside tmp_path (exactly the non-hermeticity fixed in `wake()`, 893581b)."""
    assert not any("signalement" in p.summary for p in run_tick(knowledge_root=tmp_path, repo_root=tmp_path))
    _filed(tmp_path / "docs" / "signalements")
    proposals = run_tick(knowledge_root=tmp_path, repo_root=tmp_path)
    # WHAT THIS WITNESS HOLDS IN ADDITION SINCE 2026-09-08: that the AGE genuinely travels
    # through `CoreApi` all the way to the draft. An age wired on the source side but forgotten at
    # composition time would render the "âge non mesuré" line -- green for the count, mute on
    # STASIS, therefore useless.
    ligne = next(p.summary for p in proposals if "signalement" in p.summary)
    assert "1 field signalement awaiting" in ligne
    assert "age not measured" not in ligne  # the age did travel through the composition
    assert "the oldest is " in ligne and " days" in ligne
    assert ligne.startswith(DETTE_PREFIX)  # a 2026-07-20 report is in STASIS, not just in the queue
