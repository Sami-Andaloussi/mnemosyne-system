"""Renderer (D108 / D66 / D111) — the governed document-output prise (Typst default brick).

Producing a shareable document is the **MIRROR of ingestion** and a NEW egress surface. Where
ingestion floors an untrusted input UP (D101), output governs what may become a portable artifact and
refuses to let ``sensible`` / PII content become one that LEAVES the machine without clearance. This
port is the swap-able rendering ENGINE only (Typst → PDF/HTML, ``oss_registry.md``); the whole
governance lives in :class:`~mnemosyne.runtime.render.GovernedRenderer`, never in the brick (D100 — the
barrier is our code, not a trusted engine).

The frontier that decides governance is the **destination** (:class:`RenderDestination`): a ``LOCAL``
artifact is interior persistence (D71 — the local-only repo already versions the ``sensible``), so any
label renders; a ``SHAREABLE`` artifact is egress, so it passes the Guard's ``EXTERNAL_OUTPUT`` control
(allow-list + a deterministic content re-read, M2) exactly like any other leak.

:class:`Redactor` is the optional PII-masking prise (③-6b Presidio): it may turn a non-public body into
a public-safe copy, but its word is NOT the barrier — the :class:`GovernedRenderer` RE-CLASSIFIES the
redacted text and emits it as public only if the deterministic floor agrees (D100 — a redactor that
under-cleans cannot lower the verdict).

Decisions: D108 (skill I/O contract, output side) · D66 (sensitivity routing) · D89 (Guard mediates
the output frontier) · D100 (governance is our code, not the engine) · D101 (deterministic floor) · D71
(local persistence of the sensible). Invariants carried: substrate of 21 (egress allow-list), 24.
Code & docstrings English (D117).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class RenderDestination(Enum):
    """Where a rendered artifact is headed — the frontier that decides governance (D66 / D89)."""

    LOCAL = "local"  # a file on the operator's own machine (interior persistence, D71) — any label renders
    SHAREABLE = (
        "shareable"  # destined to LEAVE (send / publish / upload) → egress-governed (inv. 21)
    )


@dataclass(frozen=True, slots=True)
class RenderRequest:
    """A document to render: the source ``body`` in a markup the ``fmt`` renderer accepts (D108-①)."""

    body: str
    fmt: str
    title: str = ""


@dataclass(frozen=True, slots=True)
class RenderResult:
    """A rendered artifact — the bytes produced and the format actually emitted."""

    fmt: str
    artifact: bytes


@runtime_checkable
class Renderer(Protocol):
    """Turns a document source into a rendered artifact (PDF / HTML / …).

    The swap-able engine (Typst default, ③-6b); it performs NO governance — a
    :class:`~mnemosyne.runtime.render.GovernedRenderer` stands in front of it and decides whether the
    content may become this artifact at all (D100)."""

    def render(self, request: RenderRequest) -> RenderResult:
        """Render ``request`` into an artifact. Raises a normalized
        :class:`~mnemosyne.ports.core.MnemosyneError` (never a bare crash, D108-②); a missing engine is
        a fail-closed refusal, never a fabricated artifact (:class:`~mnemosyne.runtime.render.\
RefusingRenderer`)."""
        ...


@runtime_checkable
class Redactor(Protocol):
    """Masks PII spans so a non-public body may become a shareable public copy (③-6b Presidio).

    A pure transform; the BARRIER is not this brick's word but the deterministic RE-CLASSIFICATION of
    its output — the :class:`~mnemosyne.runtime.render.GovernedRenderer` re-floors the redacted text and
    emits it as public only if the floor agrees (D100 — a redactor that under-cleans cannot lower the
    verdict)."""

    def redact(self, content: str) -> str:
        """Return a copy of ``content`` with PII spans masked. Deterministic patterns and the domains
        stay OURS (D101); the accelerating pass is the brick (Presidio, ③-6b)."""
        ...
