"""BR4 — (host, prefix) egress matching. ADDITIVE: `Config.egress_allowed` (exact-match) is
neither touched nor consulted here — these tests verify only the second recourse this module
adds.

Real-world case: Eurostat lives on `ec.europa.eu`, an apex shared with the whole European
Commission, under specific paths (`/eurostat/...`). The repo had already removed `ec.europa.eu`
from the exact allow-list because the grain was too coarse — these tests prove that the finer
grain (host + prefix) does not reopen the same defect through another path.
"""

from __future__ import annotations

import pytest

from mnemosyne.guard.egress_prefix import PrefixEntry, egress_prefix_allowed

_EUROSTAT = (PrefixEntry(host="ec.europa.eu", prefix="/eurostat/"),)


# ---- THE REAL-WORLD CASE ----------------------------------------------------------------------
def test_EUROSTAT_est_couvert_SANS_ouvrir_tout_l_apex() -> None:
    assert egress_prefix_allowed(
        _EUROSTAT, "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/x"
    )


def test_UN_AUTRE_SERVICE_DU_MEME_APEX_N_EST_PAS_COUVERT() -> None:
    """*Exactly* the defect that removing `ec.europa.eu` from the exact allow-list closed —
    rebuilt here at the finer grain to prove it does not reopen."""
    assert not egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/taxation-customs/other/x")


def test_UN_AUTRE_HOTE_N_EST_JAMAIS_COUVERT() -> None:
    assert not egress_prefix_allowed(_EUROSTAT, "https://evil.example.com/eurostat/x")


# ---- PARTIAL PREFIX: the defect a naive `str.startswith` would have let through ---------------
def test_UN_SEGMENT_PARTIEL_NE_MATCHE_PAS() -> None:
    """`/eurostat-fake/` begins with the same STRING as `/eurostat/`, but it is not the same
    SEGMENT — the distinction that decides whether the comparison is safe."""
    assert not egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat-fake/x")


def test_LE_DOSSIER_EXACT_SANS_RIEN_APRES_EST_COUVERT() -> None:
    assert egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat/")


# ---- `..` TRAVERSAL: resolved BEFORE the verdict, never compared as raw text ------------------
def test_UNE_TRAVERSEE_QUI_SORT_DU_PREFIXE_EST_REFUSEE() -> None:
    assert not egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat/../secret")


def test_UNE_TRAVERSEE_QUI_S_ANNULE_RESTE_COUVERTE() -> None:
    """The REAL destination after resolution is indeed inside the prefix — refusing here would
    punish the shape of the request, not its destination."""
    assert egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat/../eurostat/x")


def test_UNE_TRAVERSEE_QUI_VISE_AU_DESSUS_DE_LA_RACINE_EST_REFUSEE() -> None:
    assert not egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat/../../../etc/passwd")


# ---- PATH ENCODING: decoded BEFORE normalization -----------------------------------------------
def test_UN_POINT_POINT_ENCODE_EST_TRAITE_COMME_LITTERAL() -> None:
    """`%2e%2e` must produce the SAME verdict as a literal `..` — otherwise the encoding becomes
    the bypass surface this module exists to close."""
    assert not egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat/%2e%2e/secret")


def test_UN_CHEMIN_ENCODE_QUI_RESTE_DANS_LE_PREFIXE_EST_COUVERT() -> None:
    assert egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat/api%2Fdata")


def test_UN_DOUBLE_ENCODAGE_NE_FABRIQUE_PAS_UN_FAUX_ACCORD() -> None:
    """`%252e%252e` only decodes ONCE (into `%2e%2e`, a weird literal segment) — never
    recursively down to `..`. This module does a per-segment ALLOW-list: a weird literal segment
    never matches `eurostat`, so the worst a repeated encoding can produce is a refusal, never a
    grant."""
    assert not egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat/%252e%252e/secret")


# ---- QUERY PARAMETERS: never read for the decision ----------------------------------------------
def test_LA_QUERY_STRING_NE_PEUT_PAS_SPOOFER_UN_PREFIXE() -> None:
    assert not egress_prefix_allowed(
        _EUROSTAT, "https://ec.europa.eu/autre-chemin/?fake=/eurostat/"
    )


def test_UNE_QUERY_STRING_LEGITIME_N_EMPECHE_PAS_LE_MATCH() -> None:
    assert egress_prefix_allowed(_EUROSTAT, "https://ec.europa.eu/eurostat/api/data?format=json")


# ---- MULTIPLE ENTRIES AND ABSENCE ---------------------------------------------------------------
def test_PLUSIEURS_ENTREES_INDEPENDANTES() -> None:
    entries = (
        PrefixEntry(host="ec.europa.eu", prefix="/eurostat/"),
        PrefixEntry(host="ec.europa.eu", prefix="/comext/"),
    )
    assert egress_prefix_allowed(entries, "https://ec.europa.eu/comext/data")
    assert not egress_prefix_allowed(entries, "https://ec.europa.eu/autre/data")


def test_AUCUNE_ENTREE_NE_REFUSE_TOUT() -> None:
    assert not egress_prefix_allowed((), "https://ec.europa.eu/eurostat/x")


@pytest.mark.parametrize("url", ["", "not a url", "ftp://[::1", "https:///no-host"])
def test_UNE_URL_ILLISIBLE_REFUSE_PLUTOT_QUE_DE_LEVER(url: str) -> None:
    assert egress_prefix_allowed(_EUROSTAT, url) is False


# ---- WRITING THE PREFIX: with or without slashes, same folder -----------------------------------
@pytest.mark.parametrize("prefix", ["/eurostat/", "eurostat/", "/eurostat", "eurostat"])
def test_LA_BARRE_DE_TETE_OU_DE_QUEUE_NE_CHANGE_PAS_LE_DOSSIER_DESIGNE(prefix: str) -> None:
    entries = (PrefixEntry(host="ec.europa.eu", prefix=prefix),)
    assert egress_prefix_allowed(entries, "https://ec.europa.eu/eurostat/api/x")
    assert not egress_prefix_allowed(entries, "https://ec.europa.eu/eurostat-fake/x")
