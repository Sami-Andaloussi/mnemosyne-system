"""Print what the Guard ACTUALLY answers, right now, on the real protected policy zone.

`make murs` shows the refusals that already HAPPENED; this shows the refusals that WOULD happen -
the two are complementary, and the second is what you need before changing a posture. Arc E (E1)
needed it because the plan's own hypothesis about what closes the system turned out to be false:
the sensitivity default ROUTES a model call, it never refuses one (`_rule_model_call` returns ALLOW
and merely names the channel). A comment cannot be trusted for that; only a verdict can.

**The harness is a variable of the measurement.** The Guard is built here from the same inputs as
`runtime/bootstrap.py` - real policy, floor classifier, protected tool catalog, and *the same
vault path and decryptor*. A bare `DeterministicGuard()` answers differently (no catalog => every
TOOL_CALL denied "no wired catalog"), which would publish a posture nobody runs. Two arguments are
deliberately NOT passed, and neither can change a verdict: ``observability`` is read only from
``grant()`` (never reached - see below), and ``walls`` is omitted ON PURPOSE, so that hypothetical
refusals measured here never land in `system/state/walls.jsonl` and get mistaken by `make murs`
for walls something really hit.

An earlier version claimed it built the Guard "exactly" as bootstrap while passing a DIFFERENT
secret broker (the argument-less one). It converged only by accident - no vault exists on this
machine yet - and would have diverged silently the day one lands. An isolated audit caught it.
That is why the vault is now threaded through: an instrument that is right by accident is wrong.

Read-only: it authorizes, it never grants, redeems, writes or egresses. Safe to run any time.
Reproduce a measure with:  PYTHONPATH=system/lib uv run python scripts/posture_garde.py

Decisions: D89 (the one choke point)  -  D159 (`make murs`, the after-the-fact half)  -  arc E.
Code stays in English project-wide (D117); in the private deployment this mirrors, printed
output stays in the operator's own language - translated to English here for this public mirror.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from mnemosyne.config import load_policy
from mnemosyne.guard import DeterministicGuard, load_secret_broker
from mnemosyne.guard.secrets_sops import connect_sops_age
from mnemosyne.ingest import DeterministicClassifier
from mnemosyne.ports.core import Bubble, Domain, GovernanceLabel, Sensitivity
from mnemosyne.ports.guard import Decision, Effect, GuardRequest, HumanTier
from mnemosyne.tools import ConfigToolCatalog

_MARK = {Decision.ALLOW: "PASSE ", Decision.DENY: "REFUS ", Decision.ESCALATE: "HUMAIN"}


def _label(
    sensitivity: Sensitivity = Sensitivity.PUBLIC,
    bubble: str = "perso",
    domains: tuple[str, ...] = (),
) -> GovernanceLabel:
    return GovernanceLabel(
        sensitivity=sensitivity,
        bubble=Bubble(bubble),
        domains=frozenset(Domain(d) for d in domains),
    )


#: The SAME vault bootstrap resolves (`bootstrap.py:540`), reached from this file's own location so
#: the two never drift apart by a moved directory. Absent => an empty broker, fail-closed, identically.
_SECRET_VAULT_PATH: Final = (
    Path(__file__).resolve().parents[1] / "system" / "config" / "secrets.enc.json"
)


def build_guard() -> DeterministicGuard:
    """The RUNTIME's Guard, not a bare one - see the module docstring."""
    return DeterministicGuard(
        policy=load_policy(),
        classifier=DeterministicClassifier(),
        catalog=ConfigToolCatalog.load(),
        secrets=load_secret_broker(vault_path=_SECRET_VAULT_PATH, decrypt=connect_sops_age()),
    )


def cases() -> tuple[tuple[str, GuardRequest], ...]:
    """One request per frontier the system really crosses, plus its refusing twin.

    A posture is only legible in PAIRS: "the corpus is readable" says nothing until the same
    request with an undeclared domain is shown to be refused.

    **And the pairs must run on EVERY axis the conclusion touches.** The first version paired only
    on the HOST axis and left every egress label at ``public`` - so it printed "the sensitivity
    default never refuses", which is false: on ``EXTERNAL_OUTPUT`` a ``perso`` / ``sensible`` flow
    ESCALATES even to an allow-listed host (`monitor.py:_egress_is_non_public`). An isolated audit
    found it by writing the one missing line. A sample paired on the axis you are NOT trying to
    disprove flatters whatever you set out to show."""
    pub, perso, sens = Sensitivity.PUBLIC, Sensitivity.PERSO, Sensitivity.SENSIBLE
    return (
        (
            "read the corpus from research - DECLARED domain (macro)",
            GuardRequest(Effect.DOMAIN_ACCESS, Bubble("research"), (_label(domains=("macro",)),)),
        ),
        (
            "read the corpus from research - UNDECLARED domain (crypto)",
            GuardRequest(Effect.DOMAIN_ACCESS, Bubble("research"), (_label(domains=("crypto",)),)),
        ),
        (
            "cross knowledge -> research - declared contract",
            GuardRequest(Effect.CROSS_BUBBLE, Bubble("research"), (_label(bubble="knowledge"),)),
        ),
        (
            "cross perso -> research - no contract",
            GuardRequest(Effect.CROSS_BUBBLE, Bubble("research"), (_label(bubble="perso"),)),
        ),
        (
            "call a model on PUBLIC content",
            GuardRequest(Effect.MODEL_CALL, Bubble("perso"), (_label(pub),)),
        ),
        (
            "call a model on PERSO content",
            GuardRequest(Effect.MODEL_CALL, Bubble("perso"), (_label(perso),)),
        ),
        (
            "call a model on SENSIBLE content",
            GuardRequest(Effect.MODEL_CALL, Bubble("perso"), (_label(sens),)),
        ),
        (
            "send output to an allow-listed host (www.sec.gov), public content",
            GuardRequest(
                Effect.EXTERNAL_OUTPUT,
                Bubble("perso"),
                (_label(),),
                target="www.sec.gov",
                payload="public figures",
            ),
        ),
        (
            "send output to a NON-listed host (api.anthropic.com)",
            GuardRequest(
                Effect.EXTERNAL_OUTPUT,
                Bubble("perso"),
                (_label(),),
                target="api.anthropic.com",
                payload="public figures",
            ),
        ),
        # -- the SENSITIVITY axis on the SAME allow-listed host: the wall the 1st version never saw --
        (
            "send output to an allow-listed host - PERSO content",
            GuardRequest(
                Effect.EXTERNAL_OUTPUT,
                Bubble("perso"),
                (_label(perso),),
                target="www.sec.gov",
                payload="personal notes",
            ),
        ),
        (
            "send output to an allow-listed host - SENSIBLE content",
            GuardRequest(
                Effect.EXTERNAL_OUTPUT,
                Bubble("perso"),
                (_label(sens),),
                target="www.sec.gov",
                payload="personal notes",
            ),
        ),
        (
            # NOT "(per OPERATION)", as this line first read: the FIELD travels on every request, but
            # the CEREMONY does not - the one live path that hits this wall (image captions) takes
            # operator's word ONCE per run and then carries it across N figures (D164).
            "  ... the SAME, with the operator's canal-B gesture (given ONCE per run)",
            GuardRequest(
                Effect.EXTERNAL_OUTPUT,
                Bubble("perso"),
                (_label(sens),),
                target="www.sec.gov",
                payload="personal notes",
                human_gesture=HumanTier.FLAG_ROUTINE,
            ),
        ),
        (
            "call a model with NO input at all",
            GuardRequest(Effect.MODEL_CALL, Bubble("perso"), ()),
        ),
        (
            "read the corpus without naming ANY domain",
            GuardRequest(Effect.DOMAIN_ACCESS, Bubble("research"), (_label(),)),
        ),
        (
            "call the wired tool (search_memory)",
            GuardRequest(Effect.TOOL_CALL, Bubble("perso"), (_label(),), target="search_memory"),
        ),
        (
            "call an unwired tool (send_email)",
            GuardRequest(Effect.TOOL_CALL, Bubble("perso"), (_label(),), target="send_email"),
        ),
        (
            "MONEY / MESSAGE / PUBLISH / DELETE (life_action)",
            GuardRequest(
                Effect.LIFE_ACTION, Bubble("perso"), (_label(),), descriptor="pay a bill"
            ),
        ),
        (
            "write to the policy zone (policy_write)",
            GuardRequest(Effect.POLICY_WRITE, Bubble("perso"), (_label(),)),
        ),
        (
            "use a secret",
            GuardRequest(
                Effect.SECRET_USE, Bubble("perso"), (_label(),), target="ANTHROPIC_API_KEY"
            ),
        ),
    )


def render(guard: DeterministicGuard) -> str:
    """The printed posture. A raised bound (an explicit safety ceiling in the policy, distinct from
    an allow/deny ruling) is NOT a verdict - it is shown as such rather than swallowed into a fake
    DENY, which would understate what the caller experiences."""
    lines = [
        "# Mnemosyne  -  Guard posture (what PASSES and what HITS A WALL, right now)",
        "",
        "Read-only, against the real policy. The counterpart to `make murs` (which shows what has ALREADY hit a wall).",
        "",
    ]
    for what, request in cases():
        try:
            ruling = guard.authorize(request)
            lines.append(f"{_MARK[ruling.decision]} | {what:<56} | {ruling.reason}")
        except Exception as exc:  # noqa: BLE001 - a bound BREACH is an outcome to show, not to hide
            lines.append(f"{'BORNE ':<6} | {what:<56} | {type(exc).__name__}: {exc}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    print(render(build_guard()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
