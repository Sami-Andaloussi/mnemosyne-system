"""_TreeSitterBackend - the SOLE importer of tree-sitter (D103 / invariant 20).

The one module allowed to touch the brick: it loads a language grammar, runs a structural query, and
returns naked ``(capture_name, text)`` primitives to
:class:`~mnemosyne.ingest.structural.TreeSitterStructuralExtractor` - which owns the capture->triple
translation, unit-tested without the brick (D126). Everything here is ``# pragma: no cover``: it runs
only at (3) ignition (``uv sync --extra bricks``), where the 1-click smoke confronts this colle with
the real tree-sitter API (as (3)-2a's ``query_points`` correction showed, the allumage is where a
machine-only glue meets reality). Code & docstrings English (D117).

Decisions: D103 (sole importer)  -  D125-B9 (tree-sitter)  -  D126 (primitive seam)  -  D100.
"""

from __future__ import annotations

from collections.abc import Callable

#: Per-language structural query - names the nodes the pre-pass turns into triples. Extensible with
#: the triple map in :mod:`.structural` (calls / inheritance as the query grows). Python first (the
#: project's own language); other grammars slot in at their ignition.
_QUERIES: dict[str, str] = {
    "python": """
    (function_definition name: (identifier) @function.name)
    (class_definition name: (identifier) @class.name)
    (import_statement (dotted_name (identifier) @import.name))
    (import_from_statement (dotted_name (identifier) @import.name))
    """,
}


class _TreeSitterBackend:  # pragma: no cover - real tree-sitter translation ((3)-3 ignition, smoke-tested)
    """Thin translation over tree-sitter: parse ``content``, run the query, return naked captures.

    Holds the brick's loaders (injected so this class never imports at module scope). An unsupported
    language returns ``[]`` - a capture over a language we have no query for is simply nothing, never
    a raise (a broken parse must not break a capture, D108-(2))."""

    __slots__ = ("_get_language", "_get_parser")

    def __init__(
        self, get_language: Callable[[str], object], get_parser: Callable[[str], object]
    ) -> None:
        self._get_language = get_language
        self._get_parser = get_parser

    def captures(self, content: str, language: str) -> list[tuple[str, str]]:
        import tree_sitter

        query_src = _QUERIES.get(language)
        if query_src is None:
            return []
        parser = self._get_parser(language)
        tree = parser.parse(content.encode("utf-8"))
        # ALLUMAGE NOTE confronted ((3) ignition, tree-sitter 0.26.0 / tree-sitter-language-pack
        # 1.12.2): ``Language.query`` is gone (as anticipated), AND ``get_parser`` itself now
        # returns tree-sitter-language-pack's OWN native Parser/Tree/Node (a distinct binding,
        # not interoperable with ``tree_sitter.Query``/``QueryCursor`` - its ``parse`` wants
        # ``str`` not ``bytes``, ``root_node`` is a method, ``Node`` has no ``.text``). Fixed at
        # the factory (:func:`connect_treesitter`): ``get_parser`` is rebuilt there as a real
        # ``tree_sitter.Parser`` over the pack's (still-compatible) ``Language``. The query/
        # capture shape anticipated by the note holds: ``QueryCursor(query).captures(node)``
        # returns the same ``{capture_name: [nodes]}`` dict as the old ``Query.captures``.
        query = tree_sitter.Query(self._get_language(language), query_src)
        out: list[tuple[str, str]] = []
        for capture_name, nodes in tree_sitter.QueryCursor(query).captures(tree.root_node).items():
            for node in nodes:
                out.append((capture_name, node.text.decode("utf-8")))
        return out


def connect_treesitter():  # pragma: no cover - needs the brick ((3) ignition)
    """Wrap the installed tree-sitter as a :class:`StructuralExtractor` (the ``[OPERATOR]`` allumage seam).

    Imports the brick lazily (``tree_sitter_language_pack``, the MAINTAINED grammar bundle - the
    archived ``tree_sitter_languages`` is avoided), so the module is import-safe without it (D126).
    Wired by :func:`~mnemosyne.runtime.bootstrap.real_runtime`. As with every ``pragma: no cover``
    adapter, the 1-click smoke confronts this colle with the real API at ignition (a modern-API drift
    degrades to zero structural fact - never a lost datum - now that the pre-pass is under the net).

    ``get_parser`` is NOT ``tree_sitter_language_pack.get_parser`` (confronted at ignition: that
    now returns the pack's own native Parser/Tree/Node, incompatible with ``tree_sitter.Query`` /
    ``QueryCursor`` - see the note in :meth:`_TreeSitterBackend.captures`). Instead a real
    ``tree_sitter.Parser`` is built locally over the pack's ``Language`` (still a genuine
    ``tree_sitter.Language`` - confirmed interoperable)."""
    import tree_sitter
    from tree_sitter_language_pack import get_language

    from .structural import TreeSitterStructuralExtractor

    def get_parser(language: str) -> tree_sitter.Parser:
        return tree_sitter.Parser(get_language(language))

    return TreeSitterStructuralExtractor(_TreeSitterBackend(get_language, get_parser))
