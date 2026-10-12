"""_TypstRenderer - the SOLE importer of the Typst brick (D108 / D103 / invariant 20).

The default rendering ENGINE behind the :class:`~mnemosyne.ports.renderer.Renderer` prise ((3)-6b): it
compiles a document source string into a portable artifact (PDF / PNG / SVG bytes) via the ``typst``
Python package (Apache-2.0; ``oss_registry.md``). It wraps the brick behind the port so the rest of
Mnémosyne talks only to the port and the suite stays green with the brick NOT installed (D126).
Everything that REACHES THE BRICK is ``# pragma: no cover``: it needs the installed compiler, absent in
CI, so it is exercised only at (3) ignition, where the 1-click smoke confronts this colle with the real
API. The pure ``fmt`` normaliser (:func:`_typst_format`) is the exception - deterministic, brick-free,
UNIT-TESTED.

**The engine performs NO governance (D100).** It renders bytes ONLY. Whether the content may become an
artifact at all - the ``SHAREABLE`` egress re-read (M2), the redactor re-classification - lives in the
:class:`~mnemosyne.runtime.render.GovernedRenderer` couture, which stands in FRONT of this engine and
runs BEFORE it is ever reached. A swapped engine can never widen that barrier; this adapter only obeys.

Decisions: D108 (skill I/O contract, output side)  -  D103 (sole importer)  -  D126 (brick-free suite,
injected real adapter)  -  D100 (governance is our code, not the engine). Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable

from ..ports import RenderRequest, RenderResult

#: The output formats the Typst compiler emits, mapped from the caller's ``fmt`` token. The exact
#: ``typst.compile`` ``format=`` spelling is confirmed at ignition (ALLUMAGE NOTE on :func:`connect_typst`).
_TYPST_FORMATS: tuple[str, ...] = ("pdf", "png", "svg")


def _typst_format(fmt: str) -> str:
    """Normalise a caller ``fmt`` token to a Typst output format (pure, brick-free, UNIT-TESTED).

    Lower-cases and strips a leading dot / whitespace, then maps to one of the compiler's known
    outputs (:data:`_TYPST_FORMATS`); an empty or unspecified token defaults to ``pdf`` (the portable
    default, D108). An UNKNOWN format is refused with a clear ``ValueError`` rather than silently
    emitting the wrong bytes - the caller (and the GovernedRenderer in front) must know the artifact
    kind exactly (D108-(2), never a fabricated artifact). The exact Typst spelling is confirmed at
    ignition; this is the deterministic normalisation the adapter feeds the compiler."""
    token = fmt.strip().lstrip(".").lower()
    if not token:
        return "pdf"
    if token in _TYPST_FORMATS:
        return token
    raise ValueError(
        f"unsupported render format {fmt!r}: Typst emits one of {_TYPST_FORMATS} (D108)"
    )


def connect_typst(  # pragma: no cover - needs the brick ((3) ignition)
    *, executor: Callable[..., object] | None = None
) -> "_TypstRenderer":
    """Wire the installed Typst compiler as a :class:`Renderer` engine (the ``[OPERATOR]`` allumage seam).

    Imports ``typst`` LAZILY so this module is import-safe without it (D126); wired by
    :func:`~mnemosyne.runtime.bootstrap.real_runtime` as the default rendering engine behind the
    :class:`~mnemosyne.runtime.render.GovernedRenderer`. As with every ``pragma: no cover`` adapter, the
    1-click smoke confronts this colle with the real API at ignition; a drift degrades to a fail-closed
    refusal (:class:`~mnemosyne.runtime.render.RefusingRenderer`), never a fabricated artifact.

    ALLUMAGE NOTE (best-guess API, confronted to the real ``typst`` package at the smoke ``[OPERATOR]``):
    the package exposes a module-level ``typst.compile(input, *, format=..., root=...)`` that takes the
    document SOURCE and returns the artifact ``bytes`` (``format`` one of ``"pdf"`` / ``"png"`` /
    ``"svg"``). The source is Typst markup - a ``.typ`` string - not arbitrary HTML/Markdown; the caller
    supplies Typst syntax in ``RenderRequest.body``. Best guess is that ``compile`` accepts the source as
    a ``bytes``/``str`` buffer (or a path); ``_TypstRenderer`` passes the encoded body. Confirm at
    ignition: (1) the compile entrypoint (``typst.compile`` vs a ``typst.Compiler(...)`` object with a
    ``.compile()`` method); (2) whether it accepts an in-memory source string or requires a file path
    (if the latter, spool the body to a temp ``.typ`` like the OCR adapters do, D103); (3) the exact
    ``format=`` token spelling and whether PNG needs a ``ppi=`` DPI argument; (4) that the return is raw
    ``bytes``. Pass ``executor`` in tests / at ignition to inject the resolved compile callable and keep
    the translation (:class:`_TypstRenderer`) exercised without the brick."""
    if executor is None:
        import typst  # lazy, machine-only (D103 sole importer)

        executor = typst.compile  # the compile entrypoint (name confirmed at ignition)
    return _TypstRenderer(executor)


class _TypstRenderer:
    """Thin translation from :class:`~mnemosyne.ports.renderer.Renderer` to the Typst compiler (D103).

    Holds the brick's compile callable (injected so this class never imports at module scope - the
    factory :func:`connect_typst` does the sole lazy import). ``render`` normalises the requested format,
    compiles the source body into artifact bytes, and wraps them in a :class:`RenderResult`. It performs
    NO governance - the :class:`~mnemosyne.runtime.render.GovernedRenderer` already decided the content may
    become this artifact (D100) - and does NOT swallow a compile failure into a fabricated artifact: a
    raise propagates to the couture, which normalises it (D108-(2)).

    The ``render`` method itself is brick-free (it only calls the injected executor and normaliser), so
    it is UNIT-TESTED with an injected fake compiler; the ``connect_typst`` factory is the sole
    ``pragma: no cover`` seam that touches the real ``typst`` import at ignition."""

    __slots__ = ("_compile",)

    def __init__(self, compile_fn: Callable[..., object]) -> None:
        self._compile = compile_fn

    def render(self, request: RenderRequest) -> RenderResult:
        """Compile ``request.body`` (Typst source) into an artifact of the requested format.

        The format is normalised deterministically (:func:`_typst_format`); the source is passed to the
        injected compiler as UTF-8 bytes. The compiler's raw ``bytes`` become the artifact. No governance
        happens here (the GovernedRenderer ran first, D100); a compile error is not swallowed - it
        surfaces to the couture, never a fabricated artifact (D108-(2))."""
        fmt = _typst_format(request.fmt)
        artifact = self._compile(request.body.encode("utf-8"), format=fmt)
        return RenderResult(fmt=fmt, artifact=bytes(artifact))
