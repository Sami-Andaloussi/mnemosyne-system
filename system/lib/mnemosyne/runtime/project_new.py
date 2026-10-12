"""project-new (Ch.7 / D52 / D54-3) - propose a governed project draft from the CLI.

The PROPOSE surface of the project generator (:class:`~mnemosyne.production.projects.ProjectGenerator`),
exposed as one brick-free command. It turns "I want a project named X, for goal Y, in bubble Z" into the
generator's DENY-BY-DEFAULT draft (D54-3a: no network, ``public`` ceiling, no domains, state PAUSED) and
renders it - including the exact gesture activation would take. Mnémosyne PROPOSES, never imposes (D92 /
D79): this door deliberately does NOT activate (activation needs a human-validated profile, D54-3b) and
does NOT materialize a project tree on disk - a project home is created and a profile enforced only when a
human runs the activation gesture (materialization just-in-time, D37 / D98; nothing consumes a manifest
from disk yet, so persisting one here would be a format inventing its own void). Run::

    make project-new NAME=research GOAL="macro research" BUBBLE=research
    python -m mnemosyne.runtime.project_new --name research --goal "macro research" --bubble research

A PURE READ that wires and writes nothing (D25 / D100). Code & docstrings English (D117); the ``public`` /
``perso`` / ``sensible`` tokens stay French (D33)."""

from __future__ import annotations

from ..ports import Bubble
from ..production import ProjectGenerator, ProjectManifest
from ..production.plan_format import PLAN_FILENAME, plan_skeleton


def render_proposal(manifest: ProjectManifest) -> str:
    """Render a proposed project DRAFT as readable markdown: identity + the deny-by-default profile + the
    explicit activation gesture.

    Honest by construction: it shows the LEAST-privilege profile the generator proposed (D54-3a) and states
    plainly that activation is a separate human gesture (D54-3b), never implying the project is live."""
    s = manifest.security
    net = "yes" if s.internet else "no"
    domains = ", ".join(sorted(s.domains)) if s.domains else "none"
    lines = [
        f"# Project proposal - {manifest.name}",
        "",
        f"- **goal**: {manifest.goal}",
        f"- **state**: {manifest.state}  (a DRAFT - proposed, not activated)",
        "",
        "## Proposed security profile - deny-by-default (D54-3a)",
        f"- **bubble**: {str(s.bubble)}",
        f"- **ceiling**: {s.ceiling.token}   (highest sensitivity this bubble may hold)",
        f"- **internet**: {net}",
        f"- **domains**: {domains}",
        "",
        "## To activate",
        "This is a PROPOSAL. Mnémosyne proposes, never imposes (D92): no project runs until a human "
        "validates its profile (D54-3b). Granting network, a higher ceiling or any domain, and activating, "
        "are deliberate human gestures - not this command.",
        "",
        # The imposed plan format, handed over at the one moment a project is being thought about
        # (arc C1/C2). This command materializes nothing (D54-3b), so the skeleton cannot be WRITTEN
        # here - but the gesture that creates the project home must not have to guess the format, and
        # an agent told to "write a plan in the imposed format" writes a slightly different one every
        # time. Handing the bytes is the difference between a convention and a wish.
        f"## Its plan - `{PLAN_FILENAME}` at the project root, mandatory (arc C1)",
        "Create it with the activation gesture; `make plans` says which projects still lack one. "
        "Full form: `docs/FORMAT_PLAN.md`.",
        "",
        "```markdown",
        plan_skeleton(manifest.name).rstrip(),
        "```",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI side effect
    """Parse NAME/GOAL/BUBBLE, propose a deny-by-default draft, print it. Proposes, never activates."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Propose a governed project draft (Ch.7 / D52 / D54-3)."
    )
    parser.add_argument("--name", required=True, help="the project name")
    parser.add_argument("--goal", required=True, help="what the project is for")
    parser.add_argument("--bubble", required=True, help="the project's cloisonned bubble")
    args = parser.parse_args(argv)

    draft = ProjectGenerator().propose(name=args.name, goal=args.goal, bubble=Bubble(args.bubble))
    print(render_proposal(draft), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
