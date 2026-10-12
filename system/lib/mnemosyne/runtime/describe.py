"""describe (⑥ / D114-TO2 / D25) — render Mnemosyne's self-model so a fresh agent can discover it.

The CONSUMPTION surface of the self-aware nerve. ``CoreApi.describe_self`` builds a truthful, read-only
:class:`~mnemosyne.production.self_model.SelfModel` (identity + agent surfaces + authorized tools +
active skills); this module RENDERS it as readable markdown and exposes it as a one-command entry, so a
blank agent arriving on Mnemosyne can, at session start, learn "what are you, what can you do?" and use
it (D25) — the in-repo, brick-free incarnation of "Mnemosyne as an MCP" (D114-TO2). A network MCP server
would later WRAP this same read; nothing here needs a brick or the network. Run::

    make describe
    python -m mnemosyne.runtime.describe

It is a PURE READ: it builds the default brick-free :func:`~mnemosyne.runtime.bootstrap.bootstrap`
runtime, crosses no frontier and wires nothing (D100 / D102). Code & docstrings English (D117); the
rendered product name keeps its accent.
"""

from __future__ import annotations

from ..api.core_api import CoreApi
from ..production import SelfModel
from .bootstrap import bootstrap

#: The capability kinds, in reading order MAP → invokables, each with its section title and the honest
#: message shown when the group is empty (deny-by-default under-states, it never invents one, D73).
_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("surface", "Surfaces — the map of what I can do", "no surface advertised"),
    ("tool", "Tools — what I can call directly", "no tool sanctioned yet"),
    ("skill", "Skills — what I know how to do", "no skill active yet"),
)


def render_self_model(model: SelfModel) -> str:
    """Render a :class:`SelfModel` as readable markdown: identity, then capabilities grouped by kind.

    A faithful, lossless projection for a human or a fresh agent — every advertised card is shown with
    its governed posture (``effect`` / ``reach``); an empty group says so honestly (deny-by-default: it
    under-states, it never invents a capability, D73). Rendering wires and runs nothing."""
    lines = ["# Mnémosyne", "", model.identity, ""]
    known = {kind for kind, _, _ in _SECTIONS}
    # every card is rendered under SOME section: a kind the render does not know (a future
    # CapabilitySource, e.g. the promised governance posture) gets a generic heading rather than being
    # SILENTLY dropped — a self-description must never quietly under-state (fail loud, D73 / D100).
    extra = [k for k in dict.fromkeys(c.kind for c in model.capabilities) if k not in known]
    sections = (*_SECTIONS, *((k, k.capitalize(), f"no {k} advertised") for k in extra))
    for kind, title, empty in sections:
        cards = tuple(c for c in model.capabilities if c.kind == kind)
        lines.append(f"## {title}")
        if not cards:
            lines.append(f"_{empty}_")
        else:
            lines.extend(
                f"- **{card.name}** — {card.summary}  `[{card.effect} · {card.reach}]`"
                for card in cards
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    """Build the brick-free runtime, read the self-model, print it. A pure read (D25 / D114-TO2)."""
    print(render_self_model(CoreApi(bootstrap()).describe_self()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
