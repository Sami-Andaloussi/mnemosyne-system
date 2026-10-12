"""pydantic_bridge — the SOLE importer of Pydantic AI (D93 / D103 / invariant 20), wired GUARD-SAFE.

Pydantic AI (D125-B7; ``oss_registry.md``) is the typed multi-agent glue. This module makes a Pydantic
AI :class:`~pydantic_ai.Agent` reach models and tools ONLY through Mnémosyne's governed path — never
through Pydantic AI's own provider clients or its own tool executor (D100, capital):

* :class:`RunnerModel` — a Pydantic AI ``Model`` whose ``request`` bridges to OUR
  :class:`~mnemosyne.runtime.runner.LocalRunner` (behind the Guard, grant-gated, grammar-bound). Every
  agent turn is a governed model call; a call the Guard did not mint a grant for never runs.
* :class:`GovernedToolBridge` — turns an allow-listed tool into a plain callable Pydantic AI registers as
  a function tool; the callable routes to OUR :class:`~mnemosyne.tools.invoke.GovernedToolInvoker`
  (grant → redeem → sandbox → re-label the untrusted return by the max). The agent can call a tool no
  other way.

Everything that touches ``pydantic_ai`` is ``# pragma: no cover``: it needs the installed brick, absent
in CI, so it is exercised only at ③ ignition. The bridges hold OUR objects and never import
``pydantic_ai`` at module scope, so the suite stays green with the brick NOT installed (D126).

**Honest scope (F3).** This is the MINIMAL, safe adapter that proves the wiring: an ``Agent`` whose
model and tools are bridges to our governed path. The FULL agent loop — minting a fresh ``MODEL_CALL``
grant per turn (route → grant → redeem), streaming, retries, the multi-step tool/observe cycle — is
orchestration COUTURE for the orchestrator to finish (it depends on our grant lifecycle, which the
Runner requires). :class:`RunnerModel` therefore takes a ``grant_source`` callback the orchestration
supplies; without it a call fails closed (no grant, no model). See the ③-5b report.

Decisions: D93 (multi-agent engine) · D125-B7 (Pydantic AI glue) · D100 (no Guard bypass) · D103 (sole
importer) · D126 (import-safe). Code & docstrings English (D117).
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..ports import Bubble, Envelope, GovernanceLabel, Grant
from ..runtime.runner import LocalRunner
from ..tools.invoke import GovernedToolInvoker

#: A callback the orchestration supplies to mint a fresh single-use ``MODEL_CALL`` grant for one agent
#: turn (route_model → grant → the Runner redeems it, M1). Kept as a seam because the grant lifecycle is
#: orchestration couture (F3): the bridge never mints its own grant — that would bypass the Guard (D100).
GrantSource = Callable[[GovernanceLabel], Grant]


class RunnerModel:  # pragma: no cover - needs pydantic_ai (③-5b ignition)
    """A Pydantic AI ``Model`` that routes every request through OUR governed Runner (D100).

    Subclasses ``pydantic_ai.models.Model`` (resolved lazily at construction so the module is
    import-safe, D126) and overrides ``request`` to call :class:`~mnemosyne.runtime.runner.LocalRunner`
    behind the Guard — Pydantic AI's own provider client is NEVER used to reach a model. Each request
    mints a fresh ``MODEL_CALL`` grant via ``grant_source`` (the orchestration's grant lifecycle) and the
    Runner redeems it (M1); no grant ⇒ no call (fail-closed). The prompt/response labels travel (inv. 17).

    ALLUMAGE NOTE (best-guess API, confronted to the real Pydantic AI at ignition): a custom ``Model``
    implements ``async def request(self, messages: list[ModelMessage], model_settings, model_request_
    parameters) -> ModelResponse`` and a ``model_name`` / ``system`` property. ``ModelResponse`` carries
    ``parts=[TextPart(content=...)]``. Confirm at ignition: the exact ``Model`` base import path
    (``pydantic_ai.models.Model``), the ``request`` signature (it has changed across versions), and how a
    plain text answer is packed into ``ModelResponse``. Because THIS is where a drift could let Pydantic
    AI fall back to its own client, the ignition MUST verify the override is actually invoked (a smoke
    that asserts the Runner saw the call)."""

    def __init__(
        self,
        runner: LocalRunner,
        *,
        grant_source: GrantSource,
        subject: Bubble,
    ) -> None:
        # resolve the Pydantic AI base lazily and re-home this instance under it, so no pydantic_ai
        # import happens at module scope (D126). This is the SOLE importer of the brick (D103).
        from pydantic_ai.models import Model as _PydanticModel

        self.__class__ = type("RunnerModel", (RunnerModel, _PydanticModel), {})
        # run the base ``Model.__init__`` so its instance state exists: it sets ``_settings`` / ``_profile``,
        # which Pydantic AI reads back through ``model.settings`` / ``model.profile`` (a cached_property)
        # during a run. Re-homing ``__class__`` alone skips it, leaving those attrs unset → AttributeError
        # mid-run. Confirmed against pydantic-ai 2.5.0 at ignition (the ALLUMAGE NOTE above).
        _PydanticModel.__init__(self)
        self._runner = runner
        self._grant_source = grant_source
        self._subject = subject

    @property
    def model_name(self) -> str:
        """Report OUR Runner's model id — the agent runs our local model, not a vendor one (D104)."""
        return self._runner.model_id

    @property
    def system(self) -> str:
        return "mnemosyne-governed"

    async def request(self, messages, model_settings, model_request_parameters):
        """Bridge one agent turn to the governed Runner (D100): mint a grant, run the model behind the
        Guard (which redeems it, M1), and pack the answer — a governed tool call the model asked for, or
        its final text.

        When tools are offered (``model_request_parameters.function_tools``), the prompt describes them
        and the exact ``<tool_call>{...}</tool_call>`` reply format (:func:`_render_agent_prompt`), and a
        tool call the model emits is parsed back into a ``ToolCallPart``. Pydantic AI can execute that ONLY
        through OUR :class:`GovernedToolBridge` → invoker → Guard: an unsanctioned or hallucinated tool
        name is refused (D114-⑤), so the marker routes the model's INTENT and authorises nothing. No tool
        call ⇒ the text is the final answer. A non-public label routes LOCAL/canal-B via the Guard's
        ``route_model`` inside ``grant_source`` — never canal A automatically (inv. 1)."""
        from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

        prompt_text = _render_agent_prompt(messages, model_request_parameters)
        label = GovernanceLabel(sensitivity=_prompt_floor(), bubble=self._subject)
        grant = self._grant_source(
            label
        )  # orchestration mints the MODEL_CALL grant (route → grant)
        out = self._runner.complete(
            Envelope(prompt_text, label), grant=grant
        )  # Runner redeems (M1)
        if getattr(model_request_parameters, "function_tools", None):
            call = _parse_tool_call(out.payload)
            if call is not None:
                name, arguments = call
                return ModelResponse(parts=[ToolCallPart(tool_name=name, args=arguments)])
        return ModelResponse(parts=[TextPart(content=out.payload)])


class GovernedToolBridge:  # pragma: no cover - exercised via a pydantic_ai Agent (③-5b ignition)
    """Turns an allow-listed tool into a plain callable a Pydantic AI ``Agent`` registers (D100).

    Holds OUR :class:`~mnemosyne.tools.invoke.GovernedToolInvoker`. :meth:`as_tool` returns a function
    Pydantic AI registers as a function tool; when the agent calls it, the function routes to the invoker
    (grant → redeem → sandbox → re-label the untrusted return by the max) — the agent reaches a tool NO
    other way (Pydantic AI's own tool executor never touches a real tool, D100). The return is the raw
    re-labelled payload; the invoker already floored its sensitivity (a tool cannot launder ``sensible``
    as ``public``, D101 / D100-3)."""

    __slots__ = ("_invoker", "_subject")

    def __init__(self, invoker: GovernedToolInvoker, *, subject: Bubble) -> None:
        self._invoker = invoker
        self._subject = subject

    def as_tool(self, name: str) -> Callable[[str], object]:
        """A callable for tool ``name`` that runs it through the governed invoker (D114-③ / D100).

        Registered on the ``Agent`` (``tools=[bridge.as_tool("grep"), ...]``). The invoker enforces the
        allow-list, redeems the single-use grant, and re-floors the untrusted return — a life-action or
        non-public egress escalates to a human gesture BEFORE the tool runs (the call raises
        ``EscalateToHuman``, surfaced to the agent loop, never a silent auto-effect)."""

        def _call(argument: str) -> object:
            result = self._invoker.call(
                name,
                Envelope(payload=argument, label=self._public(argument)),
                subject=self._subject,
            )
            return result.payload

        _call.__name__ = name  # Pydantic AI keys the function tool on its name
        _call.__doc__ = (  # surfaced as the tool description the model reads (③-5b agentic loop)
            f"Call the governed '{name}' tool; pass its input as 'argument' (a string, e.g. a query)."
        )
        return _call

    def _public(self, argument: str) -> GovernanceLabel:
        """Label the OUTBOUND argument in the caller's bubble. Its sensitivity is a hint only — the Guard
        re-floors the CONTENT for a LEAVES_EXTERNAL tool (M2), so a mislabeled argument cannot exfiltrate
        (D100). Starts at the fail-safe floor; the Guard raises it from the content."""
        return GovernanceLabel(sensitivity=_prompt_floor(), bubble=self._subject)


def connect_pydantic_agent(  # pragma: no cover - needs pydantic_ai (③-5b ignition)
    *,
    runner: LocalRunner,
    invoker: GovernedToolInvoker,
    grant_source: GrantSource,
    subject: Bubble,
    tool_names: tuple[str, ...] = (),
    instructions: str = "",
):
    """Build a Pydantic AI ``Agent`` wired to the governed path (the ``[OPERATOR]`` allumage seam, D93 / D100).

    The agent's MODEL is a :class:`RunnerModel` (our Runner behind the Guard); its TOOLS are
    :class:`GovernedToolBridge` callables for each allow-listed ``tool_names`` (our invoker). Imports
    ``pydantic_ai`` LAZILY so this module is import-safe without it (D126); this + the bridges are the
    SOLE importers of the brick (D103). Returns the constructed ``Agent``.

    ALLUMAGE NOTE (best-guess API, confronted to the real Pydantic AI at ignition): ``from pydantic_ai
    import Agent``; ``Agent(model=<Model instance>, instructions=..., tools=[fn, ...])``; run with
    ``await agent.run(user_prompt)`` → ``result.output``. Confirm at ignition: the ``Agent`` constructor
    kwargs (``model`` / ``instructions`` / ``tools`` — names have shifted across versions), whether a
    custom ``Model`` instance is accepted directly, and the run/return surface. The FULL loop (grant per
    turn via ``grant_source``, retries, streaming) is orchestration couture to finish (F3, see report)."""
    from pydantic_ai import Agent

    model = RunnerModel(runner, grant_source=grant_source, subject=subject)
    bridge = GovernedToolBridge(invoker, subject=subject)
    tools = [bridge.as_tool(name) for name in tool_names]
    return Agent(model=model, instructions=instructions, tools=tools)


def drive_agent(  # pragma: no cover - needs pydantic_ai (③-5b ignition)
    agent: object, user_prompt: str, *, request_limit: int
) -> str:
    """Run an assembled ``Agent`` to completion under a hard request ceiling; return its text output.

    The SOLE place Pydantic AI's RUN surface is touched (invariant 20 / D103): the orchestration
    (:mod:`.loop`) assembles the agent via :func:`connect_pydantic_agent` and drives it HERE, so the
    per-run turn ceiling (invariant 16 / D78) maps onto Pydantic AI's own ``UsageLimits`` inside the
    adapter — the loop never imports the brick. A HIT ceiling must RAISE (fail-closed), never
    truncate silently (D100).

    ALLUMAGE NOTE (best-guess API, confronted to the real Pydantic AI at ignition): ``from
    pydantic_ai.usage import UsageLimits``; ``agent.run_sync(user_prompt, usage_limits=UsageLimits(
    request_limit=...))`` → ``result.output``. Confirm the limit class + kwarg name and the
    run/return surface (both have shifted across versions), and that exceeding the ceiling RAISES
    rather than returning a partial answer."""
    from pydantic_ai.usage import UsageLimits

    result = agent.run_sync(user_prompt, usage_limits=UsageLimits(request_limit=request_limit))
    return str(result.output)


def _parse_tool_call(text: str) -> tuple[str, object] | None:
    """Parse a ``<tool_call>`` the model emitted into ``(name, arguments)``, else ``None``.

    Lenient by necessity (the local 7B often omits the closing ``</tool_call>`` or trails text, ③-5b
    live): find the ``<tool_call>`` marker, then JSON-decode the FIRST brace-balanced object after it
    (nesting-safe, closing tag optional). Fail-safe: no marker, malformed / truncated JSON, or a missing
    / blank name ⇒ ``None`` (the reply is the final text answer, never a crash). The parsed name + args
    are still governed downstream — this routes the model's INTENT, it authorises nothing (D100)."""
    marker = text.find("<tool_call>")
    if marker == -1:
        return None
    start = text.find("{", marker)
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
    except (json.JSONDecodeError, ValueError):
        return None
    name = obj.get("name") if isinstance(obj, dict) else None
    if not isinstance(name, str) or not name:
        return None
    return name, obj.get("arguments", {})


def _render_agent_prompt(messages: object, params: object) -> str:
    """Render Pydantic AI's turn (tools + instructions + transcript) into ONE prompt for the Runner.

    The MLX backend wraps a bare prompt as a single chat turn with NO tool template (runner_mlx
    ``_chat``), so the tool specs, the call format, the agent instructions and the transcript (user
    turns, prior tool calls, tool observations) are all rendered as text HERE. Defensive: a shape we do
    not recognise is stringified, never dropped (never silently lose the prompt, F2)."""
    sections: list[str] = []
    tools = getattr(params, "function_tools", None) or []
    if tools:
        sections.append(_render_tool_preamble(tools))
    for part in getattr(params, "instruction_parts", None) or []:
        content = getattr(part, "content", None)
        if isinstance(content, str) and content:
            sections.append(f"[Instructions]\n{content}")
    for message in messages if isinstance(messages, (list, tuple)) else [messages]:
        for part in getattr(message, "parts", None) or []:
            rendered = _render_part(part)
            if rendered:
                sections.append(rendered)
    return "\n\n".join(sections)


def _neutralize_tool_markers(text: str) -> str:
    """Break any ``<tool_call>`` an UNTRUSTED observation carries, so a poisoned doc cannot smuggle a
    parseable tool call for the model to echo (audit ③-5b re-audit M-1). Only a marker the model emits
    THIS turn stays parsable — and even then the Guard/catalog refuse an unsanctioned name (D114-⑤)."""
    return text.replace("<tool_call>", "<tool_call·>").replace("</tool_call>", "</tool_call·>")


def _render_part(part: object) -> str:
    """Render one message part by its ``part_kind`` for the flattened agent prompt (defensive)."""
    kind = getattr(part, "part_kind", None)
    if kind == "tool-call":
        return (
            f"[You called tool {getattr(part, 'tool_name', '?')} with {getattr(part, 'args', '')}]"
        )
    if kind == "tool-return":
        content = _neutralize_tool_markers(str(getattr(part, "content", "")))
        return f"[Result from tool {getattr(part, 'tool_name', '?')}]\n{content}"
    if kind == "retry-prompt":
        content = _neutralize_tool_markers(str(getattr(part, "content", "")))
        return f"[Tool call error — fix and retry]\n{content}"
    content = getattr(part, "content", None)
    if isinstance(content, str):
        label = {"system-prompt": "System", "user-prompt": "User"}.get(kind, "")
        return f"[{label}]\n{content}" if label else content
    return str(part)


def _render_tool_preamble(tools: object) -> str:
    """Describe the offered tools + the exact reply format the model must use to call one."""
    lines = ["You have tools to consult the user's memory. Available tools:"]
    for tool in tools:
        name = getattr(tool, "name", "?")
        description = getattr(tool, "description", None) or ""
        schema = getattr(tool, "parameters_json_schema", None)
        lines.append(f"- {name}: {description} (arguments JSON schema: {json.dumps(schema)})")
    lines.append(
        "To call a tool, reply with EXACTLY one line and nothing else:\n"
        '<tool_call>{"name": "<tool>", "arguments": {<args>}}</tool_call>\n'
        "You will then see the tool result. When you have enough, write your final answer as plain "
        "text (do NOT wrap the final answer in <tool_call>)."
    )
    return "\n".join(lines)


def _prompt_floor():
    """The fail-safe starting sensitivity for a bridged prompt/argument: ``sensible`` (D101 default in
    doubt). Kept a call (not a constant) so a future policy hook can lower it for a genuinely-public
    agent; today it stays fail-safe so the Guard routes conservatively (LOCAL / canal-B, inv. 1)."""
    from ..ports import Sensitivity

    return Sensitivity.SENSIBLE
