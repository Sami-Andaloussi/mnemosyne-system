"""ModelRouter (D7) - resolve a task's capability class to the model that serves it.

The concrete D7 *task-class router*: given a :class:`~mnemosyne.ports.RoutingClass`
(the capability a call NEEDS), return the model id to run it on - read from the model-agnostic
config table (:meth:`~mnemosyne.config.Policy.model_for`, D70) with the capable model as the
default. An unmapped class -> ``None`` -> the wired default runner ("frontier suffices for the
majority", D66 / D69); only a class the bench (D69) has mapped to a small local model returns a
concrete id. Adding a model is therefore a CONFIG change, never a code change (D7 / D26 / D98).

**One axis only - the MODEL.** The CHANNEL (local vs canal A) stays the Guard's ``route_model``
decision, keyed on SENSITIVITY (invariant 1, sensible-local) - orthogonal and always dominant:
this router never routes a ``sensible`` call off-machine. It names a model; the Guard names the
channel, and a ``sensible`` input forces LOCAL regardless of which model was chosen. The two
compose; the channel wins.

**The physical swap is a just-in-time seam (D98).** Today one backend is wired (the stub until (3),
then MLX), so every class resolves to the default and the returned id is recorded as the call's
declared ``target`` (:attr:`~mnemosyne.ports.GuardRequest.target` - "destination: model backend")
for provenance, not yet a backend switch. A registry keyed on the returned id materialises when
the bench provides more than one model - with zero change to this router or its callers. Code &
docstrings English (D117)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..ports import RoutingClass

if TYPE_CHECKING:
    from ..config import Policy


class ModelRouter:
    """Resolve a :class:`RoutingClass` to a model id via the model-agnostic config table (D7 / D70).

    Stateless over a frozen :class:`~mnemosyne.config.Policy`: a handle on it cannot mutate a
    mapping (the Policy is read-only, SE4). Injected where a model consumer needs to declare its
    task class (bootstrap wires one from the loaded policy)."""

    __slots__ = ("_policy",)

    def __init__(self, policy: Policy) -> None:
        self._policy = policy

    def route(self, routing_class: RoutingClass) -> str | None:
        """The model id for ``routing_class`` (D7), or ``None`` when the class is unmapped - the
        capable default (``None`` => the wired default runner, so "frontier suffices for the
        majority" holds until the bench, D69, maps it). Never raises on an unmapped class: it falls
        back to the default, fail-safe toward the capable model (D70)."""
        return self._policy.model_for(routing_class)
