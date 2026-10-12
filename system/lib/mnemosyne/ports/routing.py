"""Model routing taxonomy (D7 / D18 / D26) - the CAPABILITY class a model call declares.

D7 fixes the founding rule: the model-abstraction layer is a ROUTER BY TASK CLASS - a
micro-task runs on a small local model; reasoning / synthesis runs on a capable one (frontier
suffices for the majority, D66). This enum IS that taxonomy: the capability a call NEEDS,
model-agnostic (D26 / D70) - never a named model. The mapping class -> concrete model lives in
config (``system/config``, D70), resolved by the :class:`~mnemosyne.runtime.model_router.ModelRouter`,
and the bench (D69) fills it empirically. The DEFAULT is the capable model: an unmapped class ->
``None`` -> the wired default runner, so "frontier suffices for the majority" holds out of the box
and only an explicitly mechanical task diverts to a small local model once the bench provides one.

Two axes this must NOT be confused with:

* **A skill's shape** (:class:`~mnemosyne.production.skills.TaskClass` = ``ATOMIC`` /
  ``ORCHESTRATION``, D36 / D42) - that says how a skill is BUILT; this says what a model call
  NEEDS. A skill can be ATOMIC yet REASONING (the distillateur), so the two never collapse.
* **The Guard's channel routing** (``route_model``, guard.py) - that picks the CHANNEL (local vs
  canal A) by SENSITIVITY, a security barrier (invariant 1, sensible-local). This picks the MODEL
  by task, a cost / quality choice. They COMPOSE, and the channel always wins: a REASONING call on
  ``sensible`` data runs on a LOCAL capable model, never frontier cloud.

Code & docstrings English (D117); the class *tokens* stay lowercase config keys.
"""

from __future__ import annotations

from enum import Enum


class RoutingClass(Enum):
    """The capability class a model call declares, for the D7 task-class router (D7 / D26).

    Model-agnostic: a class names a NEED, never a model. The concrete model is resolved from the
    config table (D70) by the router, with the capable model as the default (unmapped -> the wired
    default runner). Extend by adding a member here AND a mapping in config - never a hard-coded
    model name in code."""

    MICRO = "micro"  # a mechanical micro-task (classify, extract, triage) -> a small local model
    REASONING = "reasoning"  # synthesis / judgment / generation -> a capable model (the default)
