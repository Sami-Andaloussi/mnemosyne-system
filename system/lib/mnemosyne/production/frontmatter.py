"""Frontmatter schema + validator (P1 identity card, D33 / D121-C2) — additive, not a rewrite.

The P1 identity card (D28) is the one part every distilled fiche fills, normed — "role =
retrieve / filter / sort / compare" (D33). **D33 fixes the CONCEPTUAL content** (which
fields exist, required vs optional, their semantics); **D121-C2's correspondence table is the
AUTHORITY for the canonical English NAMES** (precised D122 — that table wins over D17's
illustrative, complementary plumbing list; D17 is NOT used here as a naming source). This module
is the first CODE encoding of that schema: :data:`FRONTMATTER_FIELDS` names/types/cardinality/
closed-value-sets, and :func:`validate_frontmatter` is a pure, fail-honest check — it never
invents a value and never applies a default; it only reports what a candidate frontmatter dict is
missing or gets wrong (mirrors the ``ok`` / named-reason shape of
:class:`~mnemosyne.production.distillation.SourceQuality`, the sibling input gate).

**Scope (deliberately narrow, additive — invariant 2).** This graves the SCHEMA + VALIDATOR only,
not a rewrite of the writer. Today's actual emitters (``system/skills/distillateur/
distill_book.py::_frontmatter`` and this package's ``_render_frontmatter`` in
:mod:`.distillation`) still emit a handful of fields (``title`` / ``type`` / ``source`` /
``summary`` / ``tags`` / ``distilled_by`` / ``chapters``) — none of it renamed or recabled here.
Recabling the real writer onto the full 16 fields (and migrating the ~237 already-distilled
fiches) is production work + a migration, a separate audited lot. Nothing existing reads or
writes through this module yet — zero behaviour change for the current pipeline.

**Two fields are deliberately left OPEN, not closed enums (D29 / D30 — "floor, not
ceiling").** ``format`` (the FORM axis — book / article / transcript…) and ``content_type`` (the
GENRE axis — theory / method / data / opinion…) are both introduced by D33 with a trailing "…",
the same open-set spirit as :class:`~mnemosyne.production.distillation.DistilledType`. Forcing a
closed set here would silently re-close what D29/D30 explicitly left extensible. ``status`` is
left open for a different reason — see the note below.

**One field reuses an existing single source of truth.** ``sensitivity`` validates against
:class:`~mnemosyne.ports.Sensitivity` (its ``.token`` for each member) rather than a second,
hand-copied ``{"public", "perso", "sensible"}`` literal — D121-C2 pins this exact 3-value closed
set, and the engine already carries it (D66 / D101); duplicating it here would be a second home
that could drift (cf. [[contract-single-source-emit]]).

**Honest gaps left by the source decisions (not invented here).** D33 parenthesises ``statut``
the same way it parenthesises ``langue`` (slash-separated: "raw / distilled / validated"), which
would suggest a closed set symmetric to ``lang``'s. But unlike ``sensitivity`` (spelled out with
backticks in D121-C2's own naming table) and unlike ``lang`` (whose two tokens ``fr``/``en`` are
language-invariant spellings), D121-C2 never pins ENGLISH tokens for ``status``'s three French
pipeline words — and the real code already emits a fourth value outside that list
(``status: source-unusable``, the D85 source-quality gate in :mod:`.distillation`). Absent a
ratified English value set, closing ``status`` here would be a guess, not a reading of the
decisions — so it stays a required non-empty string, untyped beyond that (fail-honest: no
invented enum).

Decisions: D33 (P1 schema, conceptual) · D121-C2 (canonical English field names, precised D122)
· D17 (complementary plumbing list — illustrative only, NOT authoritative for names) · D28
(three-part document) · D29 / D30 (open type axes) · D66 / D101 (sensitivity). Code & docstrings
English (D117); the frontmatter tokens stay French-flavoured where D33 fixed them
(``perso`` / ``sensible``).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ports import Sensitivity

#: The 3-value closed set for ``sensitivity`` (D33 / D66 / D121-C2) — read off the engine's own
#: :class:`~mnemosyne.ports.Sensitivity` enum, never re-typed by hand (single source of truth).
SENSITIVITY_TOKENS: tuple[str, ...] = tuple(s.token for s in Sensitivity)

#: The 2-value closed set for ``lang`` (D33: "langue (fr/en)").
LANG_TOKENS: tuple[str, ...] = ("fr", "en")


@dataclass(frozen=True, slots=True)
class FrontmatterField:
    """One field of the P1 schema (D33 / D121-C2): name, Python type, cardinality, closed set.

    ``multi=True`` marks a multi-valued field (``domain`` / ``tags``, D33) whose value is a
    list/tuple of ``py_type``. ``allowed`` is a CLOSED value set — populated only where D33 /
    D121-C2 actually pin one explicitly (``sensitivity``, ``lang``); left ``None`` everywhere the
    decisions give open-ended examples (a trailing "…") or no enumeration at all, so the
    validator never invents a closed set the governance never decided (fail-honest)."""

    name: str
    py_type: type
    required: bool
    multi: bool = False
    allowed: tuple[str, ...] | None = None
    default: object = None
    concept_fr: str = ""  # the FR concept name D33 uses — traceability back to the decision
    note: str = ""


#: The P1 identity card schema (D33 §obligatoires/optionnels + D121-C2's naming table). Order
#: follows D121-C2's correspondence table: the 11 "obligatoires" of D33, then ``template`` (D33's
#: "additional automatic plumbing field" — grouped with the required fields in D121-C2's own
#: ordering, ahead of its "(optionnels)" marker, hence required here too), then the 4 optional
#: fields = 12 required + 4 optional = 16 fields total.
FRONTMATTER_FIELDS: tuple[FrontmatterField, ...] = (
    FrontmatterField("title", str, required=True, concept_fr="titre", note="document title"),
    FrontmatterField(
        "source",
        str,
        required=True,
        concept_fr="source",
        note='origin: author / book / link / "conversation with…"',
    ),
    FrontmatterField(
        "lang",
        str,
        required=True,
        allowed=LANG_TOKENS,
        concept_fr="langue",
        note="document language (D33: fr/en)",
    ),
    FrontmatterField(
        "domain",
        str,
        required=True,
        multi=True,
        concept_fr="domaine(s)",
        note="the SUBJECT(s) (D35); controlled vocabulary (system/config), multi-valued, flat",
    ),
    FrontmatterField(
        "format",
        str,
        required=True,
        concept_fr="format",
        note="FORM axis (book/article/transcript…); OPEN set (D29/D30) — no closed enum here",
    ),
    FrontmatterField(
        "content_type",
        str,
        required=True,
        concept_fr="contenu",
        note="GENRE axis (theory/method/data/opinion…); OPEN set (D29/D30)",
    ),
    FrontmatterField(
        "sensitivity",
        str,
        required=True,
        allowed=SENSITIVITY_TOKENS,
        concept_fr="sensibilité",
        note="3 closed levels (D33/D66) — reuses ports.Sensitivity, never recopied",
    ),
    FrontmatterField(
        "status",
        str,
        required=True,
        concept_fr="statut",
        note="pipeline stage (raw/distilled/validated, D33); no closed enum here (see module docstring)",
    ),
    FrontmatterField("id", str, required=True, concept_fr="id", note="plumbing, automatic"),
    FrontmatterField(
        "ingested_at",
        str,
        required=True,
        concept_fr="date d'ajout",
        note="plumbing, automatic; timestamp (format not fixed by D33 — non-empty text here)",
    ),
    FrontmatterField(
        "source_path",
        str,
        required=True,
        concept_fr="chemin de l'original conservé",
        note="plumbing, automatic",
    ),
    FrontmatterField(
        "template",
        str,
        required=True,
        concept_fr="template utilisé",
        note="additional automatic plumbing field (D33); reference to the P3 template, idempotent regeneration",
    ),
    FrontmatterField(
        "origin_date",
        str,
        required=False,
        default=None,
        concept_fr="date d'origine",
        note="optional; no default set by D33",
    ),
    FrontmatterField(
        "tags",
        str,
        required=False,
        multi=True,
        default=(),
        concept_fr="tags",
        note="optional, free-form bonus; default = empty list",
    ),
    FrontmatterField(
        "version",
        str,
        required=False,
        default=None,
        concept_fr="version",
        note="optional; no default set by D33",
    ),
    FrontmatterField(
        "read_status",
        str,
        required=False,
        default=None,
        concept_fr="statut de lecture",
        note="optional (to read / read); no default set by D33",
    ),
)

#: Lookup by canonical name (D121-C2) — e.g. ``FIELDS_BY_NAME["sensitivity"].allowed``.
FIELDS_BY_NAME: dict[str, FrontmatterField] = {f.name: f for f in FRONTMATTER_FIELDS}
#: The 12 field names a complete P1 card MUST carry (D33 §obligatoires + the auto ``template``).
REQUIRED_FIELD_NAMES: frozenset[str] = frozenset(f.name for f in FRONTMATTER_FIELDS if f.required)
#: The 4 field names D33 tolerates absent (§optionnels).
OPTIONAL_FIELD_NAMES: frozenset[str] = frozenset(
    f.name for f in FRONTMATTER_FIELDS if not f.required
)


@dataclass(frozen=True, slots=True)
class FieldError:
    """One named validation failure (which field, what kind) — mirrors D108-② normalized errors."""

    field: str
    code: str  # "missing" | "wrong_type" | "empty_value" | "invalid_value"
    message: str


@dataclass(frozen=True, slots=True)
class FrontmatterValidation:
    """Verdict of :func:`validate_frontmatter`.

    Mirrors the ``ok`` / named-reason shape of
    :class:`~mnemosyne.production.distillation.SourceQuality`: ``ok`` is the gate, ``errors``
    names every failing field (empty tuple when ok)."""

    ok: bool
    errors: tuple[FieldError, ...] = ()


def validate_frontmatter(data: dict[str, object]) -> FrontmatterValidation:
    """Validate a candidate P1 frontmatter dict against :data:`FRONTMATTER_FIELDS` (D33/D121-C2).

    Pure and fail-honest: never mutates ``data``, never invents or fills in a default — an ABSENT
    optional field is simply tolerated (no error, D33), while an absent REQUIRED field is a named
    ``"missing"`` error. For each field actually PRESENT in ``data``: the Python type is checked
    (a scalar field must be ``str``; a ``multi`` field must be a ``list``/``tuple`` whose items
    are all ``str``), a REQUIRED field's value may not be blank (empty string) or an empty list,
    and closed-value membership is checked where the schema pins one (``sensitivity``, ``lang``).

    Optional fields, when present, are only type-checked — the decisions never say a present-but-
    blank optional value is wrong, so this does not invent that rule. Keys in ``data`` that are
    not part of the schema are ignored (this checks the D33/D121-C2 contract, not whether a
    real-world fiche — which today still writes different, legacy field names — has extra or
    renamed keys; that gap is the writer-recabling this module deliberately leaves alone)."""
    errors: list[FieldError] = []
    for spec in FRONTMATTER_FIELDS:
        if spec.name not in data:
            if spec.required:
                errors.append(
                    FieldError(spec.name, "missing", f'required field absent: "{spec.name}"')
                )
            continue  # optional absent — tolerated (D33)

        value = data[spec.name]

        if spec.multi:
            if not isinstance(value, (list, tuple)):
                errors.append(
                    FieldError(
                        spec.name,
                        "wrong_type",
                        f'"{spec.name}": expected a list, got {type(value).__name__}',
                    )
                )
                continue
            if spec.required and len(value) == 0:
                errors.append(
                    FieldError(
                        spec.name,
                        "empty_value",
                        f'"{spec.name}": empty list (≥ 1 value required)',
                    )
                )
                continue
            for i, item in enumerate(value):
                if not isinstance(item, spec.py_type):
                    errors.append(
                        FieldError(
                            spec.name,
                            "wrong_type",
                            f'"{spec.name}"[{i}]: expected {spec.py_type.__name__}, got {type(item).__name__}',
                        )
                    )
                elif spec.required and spec.py_type is str and not item.strip():
                    # a REQUIRED multi (e.g. `domain`) may not carry a blank element — a `[""]` is as
                    # empty as `[]`, and a blank domain would mis-tag the fiche (mirrors the scalar rule)
                    errors.append(
                        FieldError(spec.name, "empty_value", f'"{spec.name}"[{i}]: empty string')
                    )
            continue

        if not isinstance(value, spec.py_type):
            errors.append(
                FieldError(
                    spec.name,
                    "wrong_type",
                    f'"{spec.name}": expected {spec.py_type.__name__}, got {type(value).__name__}',
                )
            )
            continue

        if spec.required and spec.py_type is str and not value.strip():
            errors.append(FieldError(spec.name, "empty_value", f'"{spec.name}": empty string'))
            continue

        if spec.allowed is not None and value not in spec.allowed:
            errors.append(
                FieldError(
                    spec.name,
                    "invalid_value",
                    f'"{spec.name}": {value!r} outside the closed set {spec.allowed!r}',
                )
            )

    return FrontmatterValidation(ok=not errors, errors=tuple(errors))
