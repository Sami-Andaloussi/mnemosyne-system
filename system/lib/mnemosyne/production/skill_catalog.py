"""ConfigSkillCatalog (⑥ / D114-TO2) — the protected skill registry, deny-by-default.

The durable home of the skill lifecycle's terminal truth: which skills the operator has sanctioned ACTIVE
(D37 — ACTIVE is the ONLY state that may run). A sibling of the tool allow-list (``tools.toml``) in
the same protected zone (SE4), it loads ``system/config/skills.toml`` into an immutable
name → :class:`~mnemosyne.production.skills.SkillManifest` map. It is the second real
:class:`~mnemosyne.production.self_model.CapabilitySource` behind ``CoreApi.describe_self`` (⑥): a
fresh LLM asking "what can you do?" hears the active skills as well as the authorized tools.

Read-only is structural (D100 — incapacity, not trust): the catalog is built once from the frozen
file and hands out manifests, never a mutable handle on its map. Nothing here ACTIVATES a skill —
persisting an activation is a privileged human act in the protected zone (``POLICY_WRITE`` / D102),
and it presupposes the distinct-auditor ritual (generate → audit → activate, D37 / D39-6). The catalog
is DESCRIBE-ONLY: it advertises what the operator has sanctioned; it authorises no execution — there is no
skill run-path yet, and a future one must re-enforce the audit gate before running, never trust this
file to run code.

Deny-by-default at every seam: a missing file, an empty file, or a file with no ACTIVE skill all
advertise NOTHING (fail-closed, D89). A DRAFT / AUDITED entry is a legitimate registry record but is
never returned by :meth:`active` — only ACTIVE skills are advertised (D37), so the self-model can
only ever under-state, never over-state. A DUPLICATE name is REFUSED at load (enforce-collisions-
structurally: an "improbable" id clash is cloisonnée by construction, incapacity > probabilistic bet).
An unknown token (sensitivity / task-class / state) RAISES — a typo in the protected zone must fail
loudly, never silently widen (D100). Read by the standard-library ``tomllib`` — no dependency, so the
barrier holds before the toolchain lands (D116). Code & docstrings English (D117).

Decisions: D114-TO2 (Mnemosyne describes its capabilities) · D25 (a blank agent loads a skill) · D37
(generate → audit → activate; ACTIVE alone may run) · D39-6 / D75 (distinct auditor) · D102 / SE4
(protected zone, human-wired) · D73 / D89 (deny-by-default) · D100 (structural incapacity) · D38 (a
skill declares needs, not rights).
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import MappingProxyType

from ..ports import Sensitivity
from .skills import ActivationState, SkillManifest, SkillNeeds, TaskClass

#: The protected skill zone: ``<repo>/system/config/skills.toml`` (sibling of ``tools.toml``),
#: resolved from this module's home (``system/lib/mnemosyne/production/skill_catalog.py`` →
#: ``parents[3]`` is ``system``). A missing file is deny-by-default (an empty registry), never an error.
DEFAULT_SKILLS_PATH: Path = Path(__file__).resolve().parents[3] / "config" / "skills.toml"

#: Token → member/value maps, all fail-closed (an unknown token authorises nothing). Sensitivity maps
#: by NAME (its ``.value`` is an int); task-class and state are stored on the manifest as their own
#: string tokens, so they map to themselves — the map's job is to REFUSE anything off-list (D100).
_SENSITIVITY_BY_TOKEN: Mapping[str, Sensitivity] = MappingProxyType(
    {s.name.lower(): s for s in Sensitivity}
)
_TASK_CLASS_BY_TOKEN: Mapping[str, str] = MappingProxyType(
    {t: t for t in (TaskClass.ATOMIC, TaskClass.ORCHESTRATION)}
)
_STATE_BY_TOKEN: Mapping[str, str] = MappingProxyType(
    {s: s for s in (ActivationState.DRAFT, ActivationState.AUDITED, ActivationState.ACTIVE)}
)


def _one_of[E](raw: object, by_token: Mapping[str, E], *, field: str, name: str) -> E:
    """Parse a token to its member; an unknown token RAISES (never silently widens — a typo in the
    protected zone must fail loudly, not authorise something broader, D100)."""
    if not isinstance(raw, str) or raw not in by_token:
        raise ValueError(
            f"skill {name!r}: {field}={raw!r} is not one of {sorted(by_token)} "
            "(deny-by-default: an unknown token authorises nothing)"
        )
    return by_token[raw]


def _flag(raw: object, *, field: str, name: str) -> bool:
    """A declared boolean need must be a REAL TOML boolean (``true`` / ``false``); anything else RAISES
    (fail-closed like every other field — a mistyped value must not silently widen reach, D100). A
    quoted ``"false"`` is a string, not a boolean, and would otherwise read as truthy."""
    if not isinstance(raw, bool):
        raise ValueError(
            f"skill {name!r}: {field}={raw!r} must be a boolean (true/false) "
            "(deny-by-default: a malformed value authorises nothing)"
        )
    return raw


class ConfigSkillCatalog:
    """The registry of skills the operator has sanctioned (D37), read from the protected zone.

    A structural read-only catalog (duck-typed, like every concrete engine in the fabric — never
    subclassing a Protocol): it exposes :meth:`active` — the skills that may run and be advertised —
    and nothing that could mutate the frozen registry. Building it activates NOTHING (D100 / D102)."""

    __slots__ = ("_by_name",)

    def __init__(self, manifests: Iterable[SkillManifest] = ()) -> None:
        by_name: dict[str, SkillManifest] = {}
        for manifest in manifests:
            if manifest.name in by_name:
                # a duplicate registry entry must not silently shadow the first — refuse fail-closed
                # (enforce-collisions-structurally: incapacity > "it won't happen", proven real in ③).
                raise ValueError(
                    f"duplicate skill name {manifest.name!r} in the registry — refused: a second "
                    "entry cannot shadow the first (deny-by-default)"
                )
            by_name[manifest.name] = manifest
        self._by_name: Mapping[str, SkillManifest] = MappingProxyType(by_name)

    @classmethod
    def load(cls, path: Path | None = None) -> ConfigSkillCatalog:
        """Load the protected skill registry (SE4). Deny-by-default: a MISSING file is an EMPTY
        registry (no skill advertised), never an error — the skeleton ships with none active (D98)."""
        source = path if path is not None else DEFAULT_SKILLS_PATH
        if not source.exists():
            return cls(())
        data = tomllib.loads(source.read_text(encoding="utf-8"))
        return cls(_parse_manifests(data.get("skills", [])))

    def active(self) -> tuple[SkillManifest, ...]:
        """The skills sanctioned ACTIVE — the ONLY state that may run and be advertised (D37).

        A DRAFT / AUDITED registry record is filtered OUT here (deny-by-default): describe_self can
        only ever under-state, never advertise a skill that is not live."""
        return tuple(manifest for manifest in self._by_name.values() if manifest.is_active)


def _parse_manifests(rows: object) -> tuple[SkillManifest, ...]:
    """Parse the ``[[skills]]`` array of the protected zone into manifests, fail-closed on any
    malformed row (a bad manifest advertises nothing — it raises, never degrades to a laxer skill)."""
    if not isinstance(rows, list):
        raise ValueError("skills zone: [[skills]] must be an array of tables (deny-by-default)")
    manifests: list[SkillManifest] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("skills zone: each [[skills]] entry must be a table")
        name = row.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"skills zone: a [[skills]] entry has no valid name (got {name!r})")
        needs = SkillNeeds(
            sensitivity_max=_one_of(
                row.get("sensitivity_max"),
                _SENSITIVITY_BY_TOKEN,
                field="sensitivity_max",
                name=name,
            ),
            task_class=_one_of(
                row.get("task_class"), _TASK_CLASS_BY_TOKEN, field="task_class", name=name
            ),
            network=_flag(row.get("network", False), field="network", name=name),
            domains=frozenset(str(d) for d in row.get("domains", [])),
        )
        manifests.append(
            SkillManifest(
                name=name,
                version=str(row.get("version", "")),
                role=str(row.get("role", "")),
                needs=needs,
                state=_one_of(row.get("state"), _STATE_BY_TOKEN, field="state", name=name),
            )
        )
    return tuple(manifests)
