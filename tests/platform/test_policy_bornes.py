"""A5 · THE D159 CHANNEL LEARNS TO TALK ABOUT BOUNDS — and it can still only WIDEN.

THE BLOCKER MEASURED ON 2026-08-09. `agent_fanout` and `agent_max_turns` were changeable by
NOBODY: not by an agent (protected zone SE4, policy loaded into a frozen object, and no
`/dev/tty` readable from an agent shell — verified), not by the governed channel (it only
accepted `egress` / `domains` / `contract`: NO `bound` kind), and not by the operator in practice
(they do not edit configuration files — a memory lesson measures this at a 5-day wait). An item
"ready, waiting on the operator's gesture" that no gesture can execute is not waiting: it is dead.

AND THE CODE ALREADY CLAIMED THIS CHANNEL, IN BLACK AND WHITE: `core_api` declares
`refine_max_rounds` and `proposer_fanout` as *"a later policy addition (when the config zone is
next opened)."* Three consumers share two bounds today — changing one moves the other two.
"""

from __future__ import annotations

import pytest

from mnemosyne.production.policy_requests import _is_item_subset
from mnemosyne.production.policy_writer import PolicyItem, PolicyWriteError, apply_items

_TEXTE = """[bounds]
agent_fanout = 8          # breadth
agent_max_turns = 16      # depth

[cost]
x = 1
"""


def test_l_INNOCENT_une_borne_se_RELEVE_et_le_commentaire_survit() -> None:
    """The passing path first. And the line's comment must SURVIVE: it carries the bound's
    reason for being (D165), erasing it while raising the bound would lose what justifies it."""
    apres, applied = apply_items(
        _TEXTE, (PolicyItem(kind="bound", bound_name="agent_fanout", bound_value=16),)
    )
    assert applied.bounds_raised == (("agent_fanout", 8, 16),)
    ligne = next(ligne for ligne in apres.splitlines() if ligne.startswith("agent_fanout"))
    assert "16" in ligne and "breadth" in ligne, ligne
    assert "agent_max_turns = 16" in apres, "the neighboring bound does not move"


def test_une_borne_ABSENTE_est_CREEE_dans_la_bonne_section() -> None:
    """`refine_max_rounds` / `proposer_fanout` do not exist yet — the channel must be able to
    bring them into being, or it only serves half of what the code itself claims."""
    apres, applied = apply_items(
        _TEXTE,
        (PolicyItem(kind="bound", bound_name="proposer_fanout", bound_value=12, note="nerf ⑤"),),
    )
    assert applied.bounds_raised == (("proposer_fanout", 0, 12),)
    bornes = apres.split("[cost]")[0]
    assert "proposer_fanout = 12  # nerf ⑤" in bornes, "created INSIDE [bounds], never elsewhere"


def test_une_BAISSE_est_REFUSEE_le_canal_ne_sait_qu_ELARGIR() -> None:
    """THE INCAPABILITY THAT MATTERS MOST HERE. *Making a constraint real is a change of
    nature, not a fix* — this repository paid for that once, by turning a decorative ceiling into
    an active refusal on the operator's work. Tightening a bound stays possible, but never by
    slipping it into a batch of widenings approved with ONE word."""
    with pytest.raises(PolicyWriteError) as capture:
        apply_items(_TEXTE, (PolicyItem(kind="bound", bound_name="agent_fanout", bound_value=4),))
    assert "TIGHTENS" in str(capture.value), capture.value


def test_une_valeur_IDENTIQUE_est_un_NO_OP() -> None:
    apres, applied = apply_items(
        _TEXTE, (PolicyItem(kind="bound", bound_name="agent_fanout", bound_value=8),)
    )
    assert applied.bounds_raised == () and applied.is_noop and apres == _TEXTE


def test_une_borne_a_ZERO_ou_NEGATIVE_est_REFUSEE() -> None:
    """Zero is not a ceiling, it is a shutdown — a different act, with a different gate."""
    for mauvaise in (0, -1):
        with pytest.raises(PolicyWriteError):
            PolicyItem(kind="bound", bound_name="agent_fanout", bound_value=mauvaise)


def test_un_item_bound_ne_porte_QUE_ses_deux_champs() -> None:
    with pytest.raises(PolicyWriteError):
        PolicyItem(kind="bound", bound_name="x", bound_value=2, values=("intrus",))
    with pytest.raises(PolicyWriteError):
        PolicyItem(kind="bound", bound_value=2)  # no name


def test_l_EXAMINATEUR_peut_BAISSER_la_demande_jamais_la_MONTER() -> None:
    """THE STRUCTURAL GUARANTEE OF D159, AND ITS SENSE IS COUNTER-INTUITIVE ON A NUMBER. On a
    list, narrowing REMOVES elements; on a bound, narrowing LOWERS the value. An examiner who
    returned 32 where 16 was requested would be WIDENING the request — exactly what the
    incapability forbids, and an audit has already exceeded its mandate once in this repository."""
    demande = (PolicyItem(kind="bound", bound_name="agent_fanout", bound_value=16),)
    assert _is_item_subset(
        (PolicyItem(kind="bound", bound_name="agent_fanout", bound_value=12),), demande
    )
    assert _is_item_subset(demande, demande), "the identical request passes"
    assert not _is_item_subset(
        (PolicyItem(kind="bound", bound_name="agent_fanout", bound_value=32),), demande
    ), "RAISING the value is a widening, not a narrowing"


def test_l_EXAMINATEUR_ne_peut_pas_INVENTER_une_borne_absente_de_la_demande() -> None:
    demande = (PolicyItem(kind="bound", bound_name="agent_fanout", bound_value=16),)
    assert not _is_item_subset(
        (PolicyItem(kind="bound", bound_name="agent_max_turns", bound_value=1),), demande
    )


def test_une_borne_CREEE_atterrit_AVANT_le_preambule_de_la_section_suivante() -> None:
    """MEASURED ON THE REAL FILE, on 2026-09-08: `proposer_fanout` had been written **under
    the banner `# --- Cost / quota ceilings (D86) ---` and stuck to `[quotas]`**.

    TOML still parses it correctly inside `[bounds]` — so **no gate turns red**, `make portes`
    returns 0, all 679 witnesses stay green. But a human reader takes it for a cost ceiling.
    *A file the machine reads correctly and the human reads wrong does not flag itself.*

    The original witness passed because its fixture had **no preamble at all** before the next
    section — degenerate for the very property it claimed to hold. This one has one, and the
    empty separator too: exactly the shape of the real file."""
    from mnemosyne.production.policy_writer import raise_bound

    texte = (
        "[bounds]\n"
        "premiere = 1  # une borne reelle\n"
        "deuxieme = 2  # une autre\n"
        "\n"
        "# --- Un bandeau qui appartient a la section SUIVANTE ---------------------\n"
        "# et sa seconde ligne de preambule.\n"
        "[quotas]\n"
        "plafond = 3.0\n"
    )

    neuf, ancienne = raise_bound(texte, "troisieme", 7, comment="creee par ce temoin")

    assert ancienne == 0  # 0 = the key did not exist, it was CREATED
    lignes = neuf.splitlines()
    i_neuve = next(i for i, l in enumerate(lignes) if l.startswith("troisieme"))
    i_bandeau = next(i for i, l in enumerate(lignes) if l.startswith("# --- Un bandeau"))
    i_deuxieme = next(i for i, l in enumerate(lignes) if l.startswith("deuxieme"))

    assert i_neuve < i_bandeau, "the new bound landed INSIDE the next section's preamble"
    assert i_neuve == i_deuxieme + 1, "it must follow the last real bound, immediately"


def test_une_borne_creee_dans_une_section_VIDE_atterrit_quand_meme() -> None:
    """The counter-test: without it, the guard could demand a pre-existing bound and break the
    "first key of an empty section" case — which the original code handled correctly."""
    from mnemosyne.production.policy_writer import raise_bound

    neuf, ancienne = raise_bound("[bounds]\n\n[quotas]\nx = 1.0\n", "seule", 4)

    assert ancienne == 0
    lignes = neuf.splitlines()
    assert next(i for i, l in enumerate(lignes) if l.startswith("seule")) < next(
        i for i, l in enumerate(lignes) if l.startswith("[quotas]")
    )
