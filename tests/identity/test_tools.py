"""(3)-5a - the tool / sandbox execution-governance couture (D114 / D99 / D100).

Biting tests for the couture NÔTRE of "agents & outils": the protected allow-list (deny-by-default),
the governed invoker that closes the tool-call loop (grant -> redeem -> invoke -> re-label the untrusted
return by the max), the exercised local-function stub, and the fail-closed sandbox default. The two
(3)-1 debts this lot closes - the non-local egress CONSUMER (the grant is finally redeemed) and the
bounded `_spent` registry (TTL sliding window) - are proven here and in ``test_invariants`` (inv. 5).
"""

from __future__ import annotations

from pathlib import Path

from pytest import raises

from mnemosyne.guard import DeterministicGuard
from mnemosyne.ingest import DeterministicClassifier
from mnemosyne.ports import (
    Bubble,
    DataEgress,
    Effect,
    Envelope,
    EscalateToHuman,
    GovernanceLabel,
    Grant,
    GuardDenied,
    GuardRequest,
    IsolationTier,
    SandboxSpec,
    Sensitivity,
    ToolBackend,
    ToolEffect,
    ToolManifest,
)
from mnemosyne.tools import (
    ConfigToolCatalog,
    GovernedToolInvoker,
    LocalFunctionTool,
    RefusingSandbox,
)

_BUBBLE = Bubble("agent")


def _label(sensitivity: Sensitivity = Sensitivity.PUBLIC, bubble: str = "agent") -> GovernanceLabel:
    return GovernanceLabel(sensitivity=sensitivity, bubble=Bubble(bubble))


def _manifest(
    name: str,
    *,
    egress: DataEgress = DataEgress.STAYS_LOCAL,
    effect: ToolEffect = ToolEffect.READ_ONLY,
) -> ToolManifest:
    return ToolManifest(
        name=name,
        backend=ToolBackend.LOCAL_FUNCTION,
        io_schema="q:str -> out:str",
        permissions=("read",),
        egress=egress,
        effect=effect,
    )


def _armed_invoker(
    manifest: ToolManifest,
    fn,
    *,
    classifier: DeterministicClassifier | None = None,
    guard: DeterministicGuard | None = None,
) -> GovernedToolInvoker:
    """An invoker whose Guard allow-lists exactly ``manifest`` and whose only plugin runs ``fn``."""
    cls = classifier if classifier is not None else DeterministicClassifier()
    grd = (
        guard
        if guard is not None
        else DeterministicGuard(catalog=ConfigToolCatalog([manifest]), classifier=cls)
    )
    tool = LocalFunctionTool(manifest, fn)
    return GovernedToolInvoker(guard=grd, plugins={manifest.name: tool}, classifier=cls)


# --- ConfigToolCatalog - the protected allow-list, deny-by-default (D114-(5)) ----------------
def test_catalog_deny_by_default_when_file_missing(tmp_path: Path) -> None:
    catalog = ConfigToolCatalog.load(tmp_path / "absent.toml")
    assert catalog.authorized() == ()
    with raises(GuardDenied):
        catalog.get("anything")  # a missing file authorises NOTHING (fail-closed)


def test_catalog_loads_manifest_from_protected_zone(tmp_path: Path) -> None:
    zone = tmp_path / "tools.toml"
    zone.write_text(
        '[[tools]]\nname = "grep"\nbackend = "local_function"\nio_schema = "q -> hits"\n'
        'permissions = ["read"]\negress = "stays_local"\neffect = "read_only"\n',
        encoding="utf-8",
    )
    catalog = ConfigToolCatalog.load(zone)
    manifest = catalog.get("grep")
    assert manifest.backend is ToolBackend.LOCAL_FUNCTION
    assert manifest.egress is DataEgress.STAYS_LOCAL and manifest.effect is ToolEffect.READ_ONLY
    assert catalog.authorized() == (manifest,)


def test_catalog_refuses_duplicate_name(tmp_path: Path) -> None:
    # enforce-collisions-structurally: a second entry must not silently shadow the first.
    zone = tmp_path / "tools.toml"
    entry = (
        '[[tools]]\nname = "dup"\nbackend = "local_function"\nio_schema = "x"\n'
        'permissions = []\negress = "stays_local"\neffect = "read_only"\n'
    )
    zone.write_text(entry + entry, encoding="utf-8")
    with raises(ValueError, match="duplicate tool name"):
        ConfigToolCatalog.load(zone)


def test_catalog_rejects_unknown_token(tmp_path: Path) -> None:
    # an unknown egress token must fail loudly - a typo in the protected zone never widens a right.
    zone = tmp_path / "tools.toml"
    zone.write_text(
        '[[tools]]\nname = "x"\nbackend = "local_function"\nio_schema = "x"\n'
        'permissions = []\negress = "everywhere"\neffect = "read_only"\n',
        encoding="utf-8",
    )
    with raises(ValueError, match="egress"):
        ConfigToolCatalog.load(zone)


def test_real_protected_zone_sanctions_search_memory_and_denies_the_rest() -> None:
    # tools.toml now sanctions EXACTLY the first agent tool - search_memory ((3)-5b, a [OPERATOR] gesture);
    # everything else stays deny-by-default (D114-(5)). (It shipped empty until the agentic live was wired.)
    catalog = ConfigToolCatalog.load()
    assert {m.name for m in catalog.authorized()} == {"search_memory"}
    manifest = catalog.get("search_memory")
    assert manifest.effect is ToolEffect.READ_ONLY and manifest.egress is DataEgress.STAYS_LOCAL
    with raises(GuardDenied):
        catalog.get("anything_else")  # deny-by-default holds for every unlisted tool


# --- RefusingSandbox - the OS-isolation seam, fail-closed (D99 / D126) ----------------------
def test_refusing_sandbox_never_runs_untrusted_code() -> None:
    result = RefusingSandbox().run(
        SandboxSpec(tier=IsolationTier.MICROVM),
        "rm -rf /",  # never executed - the point of the abstaining default
        grant=Grant(
            request=GuardRequest(effect=Effect.TOOL_CALL, subject=_BUBBLE, inputs=()),
            released_label=_label(),
        ),
    )
    assert result.exit_code != 0 and result.output == "" and result.violations
    assert "refused" in result.violations[0]


def test_seatbelt_profile_rejects_injection_and_denies_network_by_default() -> None:
    # audit (3)-5 MINEUR-1: a crafted allow-list path cannot escape its quoted string to inject a
    # profile directive (e.g. re-enable the network) - a profile metacharacter is refused fail-closed.
    from mnemosyne.tools.sandbox_seatbelt import _seatbelt_profile

    with raises(ValueError, match="unsafe sandbox allow-list path"):
        _seatbelt_profile(('/tmp") (allow network*) ;',), ())  # a quote would close the string
    with raises(ValueError):
        _seatbelt_profile(("/ok\n(allow network-outbound)",), ())  # a newline would break the line
    # deny-by-default network: no allow-listed host => the profile denies the network outright (native
    # sandbox-exec posture - (allow default) so the command runs, then the network + out-of-zone writes
    # are the capabilities denied and re-opened only by allow-list).
    profile = _seatbelt_profile(("/Users/x/My Docs",), ())
    assert "(deny network*)" in profile
    assert "(allow default)" in profile and "(deny file-write*)" in profile
    # the allow-listed path is embedded as a WRITE-zone subpath (a space is safe inside the quoted string).
    assert '(allow file-write* (subpath "/Users/x/My Docs"))' in profile
    # an explicitly allow-listed host lifts the network denial (coarse on/off - per-host is the proxy leg).
    assert "(deny network*)" not in _seatbelt_profile((), ("api.example.com",))


def test_seatbelt_canonicalises_symlinked_allow_files_to_realpath(tmp_path) -> None:
    # macOS Seatbelt matches (subpath ...) against the KERNEL-canonical path (/tmp -> /private/tmp, a
    # symlinked scratch dir -> its target), so an UN-resolved symlink in allow_files would silently DENY a
    # legitimate in-zone write. _SeatbeltSandbox.run canonicalises to realpath BEFORE building the profile
    # (keeping _seatbelt_profile pure / string-only). Brick-free: a fake executor captures the profile so
    # no sandbox-exec is spawned - this pins the canonicalisation in CI (the manual negative test missed it
    # by using an already-canonical path).
    import os

    from mnemosyne.tools.sandbox_seatbelt import connect_sandbox_runtime

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_dir)
    resolved = os.path.realpath(link)
    assert resolved != str(link)  # the symlink genuinely resolves elsewhere (canonical differs)

    captured: dict[str, str] = {}

    def fake_executor(profile: str, command: str) -> tuple[int, str]:
        captured["profile"] = profile
        return 0, ""

    sandbox = connect_sandbox_runtime(executor=fake_executor)
    sandbox.run(
        SandboxSpec(tier=IsolationTier.SEATBELT, allow_files=(str(link),)),
        "true",
        grant=Grant(
            request=GuardRequest(effect=Effect.TOOL_CALL, subject=_BUBBLE, inputs=()),
            released_label=_label(),
        ),
    )
    profile = captured["profile"]
    # the write-zone is the REALPATH, never the raw symlink (the bug the manual test missed).
    assert f'(allow file-write* (subpath "{resolved}"))' in profile
    assert f'(subpath "{link}")' not in profile


def test_seatbelt_refuses_a_higher_tier_request_fail_closed() -> None:
    # D99 / D100: the Seatbelt engine is tier 1 ONLY. A MICROVM (tier-2) request it cannot honour is
    # REFUSED fail-closed (non-zero exit + a violation), never silently DOWNGRADED to run under weaker
    # Seatbelt confinement. A SEATBELT (tier-1) request reaches the executor and runs. Brick-free: a fake
    # executor records whether it was invoked, so no sandbox-exec is spawned.
    from mnemosyne.tools.sandbox_seatbelt import connect_sandbox_runtime

    ran: list[str] = []

    def fake_executor(profile: str, command: str) -> tuple[int, str]:
        ran.append(command)
        return 0, "ran"

    sandbox = connect_sandbox_runtime(executor=fake_executor)
    grant = Grant(
        request=GuardRequest(effect=Effect.TOOL_CALL, subject=_BUBBLE, inputs=()),
        released_label=_label(),
    )

    # tier-2 request -> refused fail-closed, the executor is NEVER reached (no silent downgrade).
    refused = sandbox.run(SandboxSpec(tier=IsolationTier.MICROVM), "echo untrusted", grant=grant)
    assert refused.exit_code != 0 and refused.violations
    assert "tier-2 micro-VM unavailable" in refused.violations[0]
    assert ran == []

    # tier-1 request -> runs (reaches the executor).
    ok = sandbox.run(SandboxSpec(tier=IsolationTier.SEATBELT), "echo ok", grant=grant)
    assert ok.exit_code == 0 and ran == ["echo ok"]


# --- GovernedToolInvoker - the keystone: grant -> redeem -> invoke -> re-label -----------------
def test_invoker_happy_path_returns_relabelled_result() -> None:
    """The return travels FENCED since D154 - every tool return, not just recall.

    A tool result is untrusted data by definition (see the class docstring), and it lands
    verbatim in a model's context, so it is wrapped as material rather than instructions. The
    content itself is unchanged inside the block; only the framing is added.
    """
    invoker = _armed_invoker(_manifest("grep"), lambda call: "just some public output")
    out = invoker.call("grep", Envelope(payload="query", label=_label()), subject=_BUBBLE)
    assert "just some public output" in str(out.payload)
    assert str(out.payload).startswith("<recalled>")
    assert str(out.payload).endswith("</recalled>")
    assert out.label.bubble == _BUBBLE and out.label.sensitivity is Sensitivity.PUBLIC


def test_invoker_redeems_the_grant_the_missing_egress_consumer() -> None:
    # (3)-1 posed a grant sealing the channel but NO non-local consumer to redeem it; the invoker IS it.
    class _SpyGuard:
        def __init__(self, inner: DeterministicGuard) -> None:
            self._inner = inner
            self.redeemed: list[Grant] = []

        def grant(self, request: GuardRequest) -> Grant:
            return self._inner.grant(request)

        def redeem(self, grant: Grant) -> None:
            self.redeemed.append(grant)
            self._inner.redeem(grant)

    spy = _SpyGuard(DeterministicGuard(catalog=ConfigToolCatalog([_manifest("grep")])))
    invoker = GovernedToolInvoker(
        guard=spy,  # type: ignore[arg-type]
        plugins={"grep": LocalFunctionTool(_manifest("grep"), lambda call: "ok")},
    )
    invoker.call("grep", Envelope(payload="q", label=_label()), subject=_BUBBLE)
    assert (
        len(spy.redeemed) == 1
    )  # the single-use grant was CONSUMED - egress enforcement is structural


def test_invoker_deny_by_default_for_unlisted_tool() -> None:
    guard = DeterministicGuard(catalog=ConfigToolCatalog(()))  # empty allow-list
    invoker = GovernedToolInvoker(guard=guard, plugins={})
    with raises(GuardDenied):
        invoker.call("unlisted", Envelope(payload="q", label=_label()), subject=_BUBBLE)


def test_invoker_allowlisted_but_unwired_fails_closed() -> None:
    # the Guard allow-lists it, but no plugin is wired - a refusal, never a guess.
    guard = DeterministicGuard(catalog=ConfigToolCatalog([_manifest("grep")]))
    invoker = GovernedToolInvoker(guard=guard, plugins={})
    with raises(GuardDenied, match="not wired"):
        invoker.call("grep", Envelope(payload="q", label=_label()), subject=_BUBBLE)


def test_invoker_leaves_external_with_nonpublic_escalates_and_never_runs() -> None:
    ran: list[str] = []
    fetch = _manifest("fetch", egress=DataEgress.LEAVES_EXTERNAL)
    invoker = _armed_invoker(fetch, lambda call: ran.append("ran") or "x")
    with raises(
        EscalateToHuman
    ):  # non-public data leaving the machine -> canal-B human gesture (D66)
        invoker.call(
            "fetch", Envelope(payload="secret", label=_label(Sensitivity.PERSO)), subject=_BUBBLE
        )
    assert ran == []  # the tool NEVER executed - escalation happens before invocation


def test_invoker_leaves_external_sensible_content_escalates_m2() -> None:
    # audit (3)-5a MAJEUR-2: a LEAVES_EXTERNAL tool with a PUBLIC label but sensible CONTENT must escalate.
    # The content is re-floored (M2 - the label can lie, the content cannot); the tool never runs, so a
    # `sensible` argument mislabeled `public` cannot auto-exfiltrate.
    ran: list[str] = []
    fetch = _manifest("fetch", egress=DataEgress.LEAVES_EXTERNAL)
    invoker = _armed_invoker(fetch, lambda call: ran.append("ran") or "x")
    with raises(EscalateToHuman):
        invoker.call(
            "fetch",
            Envelope(
                payload="wire to IBAN FR76 3000 1000 6400 0000 0000 123",
                label=_label(Sensitivity.PUBLIC),  # the label LIES; the content is sensible
            ),
            subject=_BUBBLE,
        )
    assert ran == []  # the tool NEVER executed - content-floor escalation before invocation


def test_invoker_life_action_escalates_and_never_runs() -> None:
    ran: list[str] = []
    send = _manifest("send", effect=ToolEffect.LIFE_ACTION)
    invoker = _armed_invoker(send, lambda call: ran.append("ran") or "sent")
    with raises(EscalateToHuman):  # a life-action is never full-auto (D74)
        invoker.call("send", Envelope(payload="hi", label=_label()), subject=_BUBBLE)
    assert ran == []


def test_invoker_untrusted_return_cannot_lie_down_content_floor() -> None:
    # M2 / D100-3: a tool returns PII content but the invoker re-floors from the RAW content - a
    # public input cannot launder a `sensible` return as public.
    pii = "please charge card 4242 4242 4242 4242 today"
    invoker = _armed_invoker(_manifest("grep"), lambda call: pii)
    out = invoker.call(
        "grep", Envelope(payload="q", label=_label(Sensitivity.PUBLIC)), subject=_BUBBLE
    )
    assert out.label.sensitivity is Sensitivity.SENSIBLE


def test_invoker_untrusted_return_raised_by_input_floor() -> None:
    # a benign public return called over a SENSIBLE input is raised to SENSIBLE (taint kept, D54).
    invoker = _armed_invoker(_manifest("grep"), lambda call: "benign")
    out = invoker.call(
        "grep", Envelope(payload="q", label=_label(Sensitivity.SENSIBLE)), subject=_BUBBLE
    )
    assert out.label.sensitivity is Sensitivity.SENSIBLE


def test_invoker_discards_the_tools_own_label() -> None:
    # D100-3: the plugin's returned label is UNTRUSTED - a tool cannot mislabel PII as public.
    class _LiarTool:
        manifest = _manifest("liar")

        def invoke(self, call: Envelope[object], *, grant: Grant) -> Envelope[object]:
            # claims PUBLIC over an IBAN - the invoker must ignore this label and re-floor the content.
            return Envelope(payload="IBAN FR76 3000 1000 6400 0000 0000 123", label=_label())

    guard = DeterministicGuard(catalog=ConfigToolCatalog([_LiarTool.manifest]))
    invoker = GovernedToolInvoker(
        guard=guard, plugins={"liar": _LiarTool()}, classifier=DeterministicClassifier()
    )
    out = invoker.call("liar", Envelope(payload="q", label=_label()), subject=_BUBBLE)
    assert (
        out.label.sensitivity is Sensitivity.SENSIBLE
    )  # the lie is overridden by the content floor


def test_invoker_without_classifier_is_failsafe_sensible() -> None:
    # no classifier wired => an unreadable return floors SENSIBLE (fail-safe, D100), never a silent public.
    invoker = GovernedToolInvoker(
        guard=DeterministicGuard(catalog=ConfigToolCatalog([_manifest("grep")])),
        plugins={"grep": LocalFunctionTool(_manifest("grep"), lambda call: "anything")},
    )
    out = invoker.call("grep", Envelope(payload="q", label=_label()), subject=_BUBBLE)
    assert out.label.sensitivity is Sensitivity.SENSIBLE
