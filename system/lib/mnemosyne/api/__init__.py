"""Headless API (D119) - the UI-ready surface of the core, speaking ONLY to the Guard.

The doctrine of D119 is headless-first: the Phase-1 core exposes its capabilities through clean
interfaces, and the UI (Phase 1 bis) is a client on top - never soldered to the core. The single
structural rule this package makes real is **the UI speaks to the Guard, never to the models or
stores directly** (D89): so kill-switch, supervision, costs and cloisonnement are centralized and
infalsifiable. Every frontier crossing an API method performs (egress, tool wiring, model call)
goes through one mediation point - :meth:`~mnemosyne.api.core_api.CoreApi._guarded` - which mints
a Guard capability or fails closed. There is no other path out.

:class:`~mnemosyne.api.core_api.CoreApi` lays the hooks for the seven surfaces D119 fixes -
(a) capture, (b) search, (c) supervision, (d) production, (e) governance, (f) the meta/transverse
inbox, (g) the generic create/extend route - as thin methods that delegate to the subsystems
already built (LOT 3-6). The skeleton poses the API and the hooks at 100 %; the visual rendering
(a local web app, D119) comes at Phase 1 bis (``contenant`` in P1, ``contenu`` at usage - D98).

Decisions: D119 (headless-first, surfaces, web-local)  -  D89 (talk to the Guard)  -  D98 (contenant
/ contenu). Code & docstrings English (D117); ``public`` / ``perso`` / ``sensible`` stay French.
"""

from __future__ import annotations

from .core_api import (
    CaptureReceipt,
    CoreApi,
    GovernanceView,
    Proposal,
    RecallView,
    SearchView,
    YouTubeCaptureReceipt,
)

__all__ = [
    "CoreApi",
    "CaptureReceipt",
    "YouTubeCaptureReceipt",
    "SearchView",
    "RecallView",
    "GovernanceView",
    "Proposal",
]
