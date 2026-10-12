"""LOT 7 - the headless CoreApi facade (D119): surfaces + Guard mediation, fail-closed.

The one property that makes the facade worth its weight (D119): **every frontier goes through the
Guard**. The structural proof is :func:`test_facade_cannot_bypass_the_guard` - under a Guard that
refuses everything, no outbound method succeeds; if one did, it would have bypassed the Guard. The
rest exercises each surface (a-g) against a permissive Guard so canal A/B, promotion, kill-switch,
the meta inbox and the 1-click smoke test all show their real behaviour.

Decisions: D119 (surfaces, headless, talk-to-the-Guard)  -  D89 (mediation)  -  D101 (capture)  -
D65 (search)  -  D79 (promotion)  -  D80 (kill-switch)  -  D114 / D102 (tool wiring privileged)  -  D92 /
D100 (propose, never impose)  -  D109 (smoke). Code & docstrings English (D117).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mnemosyne.api import (
    CaptureReceipt,
    CoreApi,
    GovernanceView,
    RecallView,
    SearchView,
    YouTubeCaptureReceipt,
)
from mnemosyne.api.core_api import _YOUTUBE_EGRESS_HOST
from mnemosyne.config import Contract, Policy
from mnemosyne.ingest.router import ContentNature, QueryKind
from mnemosyne.ports import (
    Bubble,
    Channel,
    Decision,
    DocId,
    DocRole,
    Domain,
    Envelope,
    EscalateToHuman,
    Fact,
    FetchedTranscript,
    GovernanceLabel,
    Grant,
    GuardDenied,
    NodeId,
    ResourceBoundError,
    Ruling,
    Sensitivity,
    Source,
    TranscriptCue,
    TranscriptFetcher,
    TriggerKind,
    WorkId,
    WorkItem,
)
from mnemosyne.production import (
    CanalBXLRefused,
    Draft,
    Fiche,
    FicheType,
    PromotionRefused,
    ValidationState,
)
from mnemosyne.runtime import Runtime, bootstrap

_ALLOW_HOST = "api.example.com"


def _permissive_policy() -> Policy:
    """A policy allowing canal A for ``public`` to one allow-listed host (egress test)."""
    return Policy(
        profile="test",
        canal_a_auto=frozenset({Sensitivity.PUBLIC}),
        egress_allowlist=frozenset({_ALLOW_HOST}),
        contracts=(),
        declared_domains=MappingProxyType({Bubble("perso"): frozenset({Domain("journal")})}),
        bounds=MappingProxyType(
            {
                "queue_capacity": 8,
                "concurrency": 1,
                "intake_capacity": 8,
                "intake_source_bytes": 268435456,
            }
        ),
        quotas=MappingProxyType({"monthly_api_eur": 20.0}),
    )


def _api(policy: Policy | None = None) -> CoreApi:
    return CoreApi(bootstrap(policy=policy if policy is not None else _permissive_policy()))


# --- (a) YouTube capture doubles (topic 3 / C3) ------------------------------------------
class _StubFetcher:
    """A brick-free ``TranscriptFetcher`` double: returns a canned transcript and COUNTS fetches - so a
    test can prove the Guard blocked BEFORE the network (calls == 0) or that the fetch ran (calls == 1)."""

    def __init__(self, transcript: FetchedTranscript) -> None:
        self._transcript = transcript
        self.calls = 0

    def fetch(self, ref: str) -> FetchedTranscript:  # noqa: ARG002 - the ref is irrelevant to the stub
        self.calls += 1
        return self._transcript


_YT_TRANSCRIPT = FetchedTranscript(
    video_id="abcdefghijk",
    title="A recorded talk",
    uploader="A channel",
    webpage_url="https://youtu.be/abcdefghijk",
    language="fr",
    auto_generated=False,
    cues=(TranscriptCue(start_s=0.0, text="Hello, this is the spoken content of the video."),),
)
_YT_EMPTY = FetchedTranscript(
    "abcdefghijk", "No subtitles", "A channel", "https://youtu.be/abcdefghijk", "", False, ()
)


def _yt_policy() -> Policy:
    """The permissive policy but with the YouTube host allow-listed (so the egress grant is ALLOWed)."""
    return replace(_permissive_policy(), egress_allowlist=frozenset({_YOUTUBE_EGRESS_HOST}))


def _yt_api(*, fetcher: TranscriptFetcher | None, policy: Policy | None = None) -> CoreApi:
    rt = bootstrap(
        policy=policy if policy is not None else _yt_policy(), transcript_fetcher=fetcher
    )
    return CoreApi(rt)


class _DenyAllGuard:
    """A Guard that refuses every frontier - the adversary that proves mediation is real."""

    def grant(self, request: object) -> Grant:
        raise GuardDenied(f"deny-all: {getattr(request, 'effect', '?')}")

    def authorize(self, request: object) -> Ruling:
        return Ruling(Decision.DENY, "deny-all")

    def route_model(self, inputs: object) -> Channel:
        return Channel.LOCAL

    def redeem(self, grant: object) -> None:
        raise GuardDenied("deny-all: redeem")

    def inject_secret(self, grant: object) -> str:
        raise GuardDenied("deny-all: inject_secret")


def _public_env(text: str = "public note", bubble: str = "perso") -> Envelope[str]:
    label = GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble(bubble))
    return Envelope(payload=text, label=label)


def _sensible_env(text: str = "secret", bubble: str = "perso") -> Envelope[str]:
    label = GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble(bubble))
    return Envelope(payload=text, label=label)


class _FakeExtractor:
    """A fact-extractor double ((3)-3a): proposes one fixed fact, bypassing the model, to prove the
    CoreApi wires extraction -> journal -> graph. The real extractor's Guard + grammar path is
    covered in test_runtime; here we isolate the capture wiring."""

    def extract(self, content: Envelope[str]) -> tuple[Fact, ...]:
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return (Fact(NodeId("operator"), "prefere", NodeId("concis"), valid_from=at),)


class _MultiFactExtractor:
    """A double proposing TWO facts about ONE subject ((3)-3c): the rich factory must fold them into a
    single per-subject fiche (de-duplication by subject, D120), not two fragments."""

    def extract(self, content: Envelope[str]) -> tuple[Fact, ...]:
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return (
            Fact(NodeId("operator"), "lives_in", NodeId("paris"), valid_from=at),
            Fact(NodeId("operator"), "prefere", NodeId("concis"), valid_from=at),
        )


class _RaisingExtractor:
    """A double that RAISES a RAW error ((3)-3c, 3a debt): ANY misbehaving extractor - not only a
    normalized one - must never lose the datum; the content still reaches Moteur B, truth-first, and
    capture never crashes."""

    def extract(self, content: Envelope[str]) -> tuple[Fact, ...]:
        raise RuntimeError("extractor boom (unexpected backend failure)")


class _FakeStructuralExtractor:
    """A deterministic structural pre-pass double ((3)-3): emits one fixed fact for any language, to
    prove capture files structural facts INDEPENDENT of the LLM route/trust (they carry no doubt)."""

    def extract_structural(self, content: str, *, language: str) -> tuple[Fact, ...]:
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return (Fact(NodeId("parse_source"), "defined_as", NodeId("function"), valid_from=at),)


class _OperatorStructuralExtractor:
    """A structural double emitting a fact about 'operator' - the SAME subject as :class:`_FakeExtractor`'s
    LLM fact, to prove the two sources never collide into one fiche (audit MAJEUR 1)."""

    def extract_structural(self, content: str, *, language: str) -> tuple[Fact, ...]:
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return (Fact(NodeId("operator"), "defined_as", NodeId("function"), valid_from=at),)


class _RaisingStructuralExtractor:
    """A structural double that RAISES (audit MAJEUR 2): a broken parser must never lose the datum."""

    def extract_structural(self, content: str, *, language: str) -> tuple[Fact, ...]:
        raise RuntimeError("parser boom (modern-API drift at ignition)")


class _FakeSourceReader:
    """A source-reader double ((3)-4): returns a fixed transcription for any source, to prove the
    CoreApi wires source -> read -> benne (preserved) -> the text pipeline, without an OCR / ASR brick."""

    def read(self, source: Source) -> str:
        return "extracted document text"


class _RaisingSourceReader:
    """A reader that RAISES ((3)-4): a broken OCR / ASR must never lose the datum - the raw source is
    preserved in the benne (D85), the receipt is honest (FAILED), and capture never crashes."""

    def read(self, source: Source) -> str:
        raise RuntimeError("ocr boom (unexpected reader failure)")


class _NonStrSourceReader:
    """A reader that VIOLATES the port by returning a non-str ((3)-4a audit MINEUR 2): a (3)-4b adapter
    drift on an unsupported format must degrade like a raise, never crash capture's classify()."""

    def read(self, source: Source) -> None:
        return None


# --- (a) capture -------------------------------------------------------------------------
def test_capture_classifies_by_max_and_routes() -> None:
    api = _api()
    iban = api.capture("IBAN FR76 3000 6000 0112 3456 7890 189", bubble=Bubble("perso"))
    assert isinstance(iban, CaptureReceipt)
    assert iban.sensitivity is Sensitivity.SENSIBLE  # the PII floor raised it (D101)
    assert iban.engines == ("B",)  # a document => Moteur B (D57)

    clean = api.capture("weather notes", bubble=Bubble("perso"), domain_signal=Sensitivity.PUBLIC)
    assert clean.sensitivity is Sensitivity.PUBLIC


# --- (b) search --------------------------------------------------------------------------
def test_search_admits_low_recall_then_finds_after_capture() -> None:
    api = _api()
    empty = api.search("anything", within=Sensitivity.PERSO, subject=Bubble("perso"))
    assert isinstance(empty, SearchView)
    assert empty.admitted_low_recall  # nothing indexed => "I don't know" (invariant 14)

    text = "my personal note about retrieval"
    receipt = api.capture(text, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    found = api.search(text, within=Sensitivity.PERSO, subject=Bubble("perso"))
    assert not found.admitted_low_recall
    # Hybrid recall finds the captured doc; the score is now an RRF rank score, not a cosine,
    # so assert the doc is present rather than a cosine floor ((3)-2b).
    assert receipt.doc in {doc for doc, _score in found.hits}


def test_search_stays_within_its_partition() -> None:
    api = _api()
    text = "a perso secret about money"
    api.capture(text, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    # the same query in a DIFFERENT partition never sees it (invariant 1 / D54)
    other = api.search(text, within=Sensitivity.PUBLIC, subject=Bubble("perso"))
    assert other.admitted_low_recall


def test_search_does_not_read_across_bubbles_unmediated() -> None:
    api = _api()
    text = "a note owned by bubble A"
    api.capture(text, bubble=Bubble("bubbleA"), domain_signal=Sensitivity.PERSO)
    # a caller in bubbleB searching the same sensitivity partition gets nothing - the Guard
    # withholds the foreign hit (no validated cross-bubble contract, invariant 3 / D54 / D119)
    foreign = api.search(text, within=Sensitivity.PERSO, subject=Bubble("bubbleB"))
    assert foreign.admitted_low_recall and foreign.hits == ()
    # the owning bubble reads its own note fine (intra-bubble, not a frontier, D89)
    own = api.search(text, within=Sensitivity.PERSO, subject=Bubble("bubbleA"))
    assert own.hits


def test_search_enforces_domain_cloisonnement() -> None:
    # A bubble sees ONLY its declared domains (invariant 4 / D72): a hit carrying an UNdeclared
    # domain is withheld by the Guard (DOMAIN_ACCESS), even intra-bubble. Domain closure defaults
    # to fail-open - search filtered by sensitivity + bubble but never mediated the domain grain.
    policy = replace(
        _permissive_policy(),
        declared_domains=MappingProxyType({Bubble("projet"): frozenset({Domain("sante")})}),
    )
    api = _api(policy)
    rt = api._rt  # noqa: SLF001 - structural test of the domain barrier on the read path
    fin = "quarterly balance alpha bravo charlie delta echo foxtrot golf hotel india"
    fin_label = GovernanceLabel(
        sensitivity=Sensitivity.SENSIBLE,
        bubble=Bubble("projet"),
        domains=frozenset({Domain("finances")}),  # NOT declared for projet
    )
    rt.journal.integrate(DocId("fin-1"), Envelope(payload=fin, label=fin_label))
    withheld = api.search(
        fin,
        within=Sensitivity.SENSIBLE,
        subject=Bubble("projet"),
        domains=frozenset({Domain("finances")}),
    )
    assert withheld.hits == () and withheld.admitted_low_recall  # undeclared domain -> withheld
    # a DECLARED domain reads fine (no false positive)
    ok = "checkup lima mike november oscar papa quebec romeo sierra tango uniform"
    ok_label = GovernanceLabel(
        sensitivity=Sensitivity.SENSIBLE,
        bubble=Bubble("projet"),
        domains=frozenset({Domain("sante")}),
    )
    rt.journal.integrate(DocId("sante-1"), Envelope(payload=ok, label=ok_label))
    seen = api.search(
        ok,
        within=Sensitivity.SENSIBLE,
        subject=Bubble("projet"),
        domains=frozenset({Domain("sante")}),
    )
    assert seen.hits  # a declared domain is visible


def test_domain_grain_is_not_widened_by_a_bubble_contract() -> None:
    # The domain grain RESTRICTS within the bubble ceiling: a validated cross-bubble contract
    # (coffre->projet) must NOT open a domain projet never declared (invariant 4 restricts 3, D72).
    policy = replace(
        _permissive_policy(),
        contracts=(Contract(source=Bubble("coffre"), target=Bubble("projet")),),
        declared_domains=MappingProxyType({Bubble("projet"): frozenset({Domain("sante")})}),
    )
    api = _api(policy)
    rt = api._rt  # noqa: SLF001 - structural test of the domain × contract interaction
    fin = "IBAN and balance uniform victor whiskey xray yankee zulu november oscar papa"
    label = GovernanceLabel(
        sensitivity=Sensitivity.SENSIBLE,
        bubble=Bubble("coffre"),
        domains=frozenset({Domain("finances")}),
    )
    rt.journal.integrate(DocId("coffre-fin-1"), Envelope(payload=fin, label=label))
    leaked = api.search(
        fin,
        within=Sensitivity.SENSIBLE,
        subject=Bubble("projet"),
        domains=frozenset({Domain("finances")}),
    )
    assert leaked.hits == () and leaked.admitted_low_recall  # a contract is not a domain widening


def test_capture_extracts_to_moteur_a_when_routed_but_the_stub_abstains() -> None:
    # (3)-3a: a living-nature datum is ROUTED to Moteur A (D57) and the extractor now RUNS on that
    # path (Guard-mediated, grammar-bound, raise-only - D100). With the stub runner it ABSTAINS
    # (no fact), so the graph stays empty and the receipt is HONEST (F3): engines stays ('B',) -
    # Moteur A received nothing - and the reason says the model abstained, NOT the old "not yet
    # assembled" (the seam IS wired now).
    receipt = _api().capture(
        "I prefer short answers",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
    )
    assert receipt.engines == ("B",)  # stub abstained => 0 fact => Moteur A received nothing
    assert "abstained" in receipt.reason  # honest: routed to A, the model abstained ((3)-3a)


def test_capture_files_a_fact_into_moteur_a_when_the_extractor_proposes_one() -> None:
    # (3)-3a end-to-end wiring: a living-nature datum whose extractor PROPOSES a fact reaches Moteur A
    # (the graph). engines credits A (a fact was really written), and the fact is queryable -
    # enveloped with the content's label (raise-only: extraction never declassifies, D100).
    rt = replace(bootstrap(policy=_permissive_policy()), fact_extractor=_FakeExtractor())
    receipt = CoreApi(rt).capture(
        "I prefer short answers",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
    )
    assert set(receipt.engines) == {"A", "B"}  # both engines received the datum ((3)-3a)
    assert "1 LLM fact(s) filed" in receipt.reason
    facts = rt.graph.query(subject=NodeId("operator"))
    assert len(facts) == 1 and facts[0].obj == NodeId("concis")


# --- (b′) recall - the A⊕B read fusion via VALIDATED fiches ((3)-3b / D65 / D100) ----------
def test_capture_proposes_a_validatable_fiche_for_each_extracted_fact() -> None:
    # (3)-3b: an extracted fact ALSO surfaces as a PROPOSED fiche - the answer-facing projection of
    # the raw graph fact (the D100 net). It is inert (PROPOSED), carries the CONTENT's label
    # (raise-only), and its type follows the write nature (behaviour -> preference, D57 / D58).
    rt = replace(bootstrap(policy=_permissive_policy()), fact_extractor=_FakeExtractor())
    api = CoreApi(rt)
    api.capture(
        "I prefer short answers",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
    )
    [fiche] = api.pending_fiches()
    assert fiche.state == ValidationState.PROPOSED  # awaiting the gesture (D59-4)
    assert fiche.ftype == FicheType.PREFERENCE  # behaviour nature -> preference (D57 / D58)
    assert fiche.label.sensitivity is Sensitivity.PERSO  # raise-only: the content's label (D100)
    assert "operator prefere concis" in " ".join(fiche.content)


def test_recall_reinjects_a_fiche_into_moteur_a_only_after_validation() -> None:
    # THE D100 net, end to end: nothing extracted reaches an answer without a VALIDATED fiche. A
    # PROPOSED fiche is absent from the recall frame; only user's explicit gesture (a PERSO fiche is
    # two-speed, D59-5) lets it reinject - bubble-scoped - into the living answer.
    rt = replace(bootstrap(policy=_permissive_policy()), fact_extractor=_FakeExtractor())
    api = CoreApi(rt)
    api.capture(
        "I prefer short answers",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
    )
    [fiche] = api.pending_fiches()
    before = api.recall(
        "short", within=Sensitivity.PERSO, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert isinstance(before, RecallView)
    assert before.frame == () and before.engines == (
        "A",
    )  # A consulted, gate closed => empty frame
    with pytest.raises(EscalateToHuman):  # a PERSO preference is never auto-validated (D59-5)
        api.validate_fiche(fiche.id, human_validated=False)
    api.validate_fiche(fiche.id, human_validated=True)  # the explicit gesture opens the gate
    after = api.recall(
        "short", within=Sensitivity.PERSO, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert len(after.frame) == 1 and "operator prefere concis" in after.frame[0].payload


def test_recall_general_fuses_moteur_a_and_b_side_by_side() -> None:
    # A GENERAL query reads BOTH engines (D65): the validated living fiche (A) and the retrieved
    # document (B) are fused SIDE BY SIDE - A never overwrites B, both bubble-scoped.
    api = _api()
    doc = "my perso note about local retrieval and memory design"
    api.capture(doc, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    seed = Fiche(
        id="pref-1",
        ftype=FicheType.PREFERENCE,
        content=frozenset({"answer concisely"}),
        label=GovernanceLabel(sensitivity=Sensitivity.PERSO, bubble=Bubble("perso")),
    )
    api._memory.propose(seed)  # noqa: SLF001 - seed a fiche without the (3)-3c production source
    api.validate_fiche("pref-1", human_validated=True)
    view = api.recall(doc, within=Sensitivity.PERSO, subject=Bubble("perso"))
    assert set(view.engines) == {"A", "B"}  # general => both (D65)
    assert len(view.frame) == 1 and "answer concisely" in view.frame[0].payload  # Moteur A
    # D137: a freshly captured doc is working material (fail-closed default) - it surfaces as
    # WORKING MATERIAL, never among the citable ``facts``, until user explicitly endorses it.
    assert view.working_material and view.facts == ()
    assert not view.admitted_low_recall


def test_recall_packs_the_matched_passage_not_the_whole_document() -> None:
    # D136: recall packs the RELEVANT passage of a long document, never the whole thing - so an answer
    # generator (behind the fail-closed runner bound) reads a bounded, on-topic slice. The whole doc
    # would overflow a bounded model call; a passage never does.
    api = _api()
    filler = "\n\n".join("neutral filler unrelated to anything here" for _ in range(60))
    marker = "harbor cargo tariff transit intake plan " * 30  # a dense on-topic chunk (~1.2k chars)
    doc = filler + "\n\n" + marker + "\n\n" + filler
    assert len(doc) > 3000  # several chunks - the whole doc would not fit one bounded call
    api.capture(doc, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    view = api.recall(
        "harbor cargo tariff",
        within=Sensitivity.PERSO,
        subject=Bubble("perso"),
        kind=QueryKind.FACTUAL,
    )
    # D137: unendorsed => working material (packing is role-agnostic - the same passage discipline).
    assert view.working_material  # the doc was retrieved (Moteur B)
    packed = view.working_material[0].payload
    assert "harbor" in packed and "cargo" in packed  # the on-topic passage is what got packed
    assert len(packed) <= 1500 + 200  # ≤ one chunk (target + overlap) - bounded, not the whole doc
    assert len(packed) < len(doc)


# --------------------------------------------------------------------------- #
# D137 - the epistemic ROLE axis: source of truth vs working material          #
# --------------------------------------------------------------------------- #
def test_capture_defaults_a_document_to_working_material_fail_closed() -> None:
    # D137: a freshly captured document is working material by default - nothing is a source of
    # truth until user explicitly endorses it. The endorsement gate never fires on its own.
    api = _api()
    receipt = api.capture(
        "a rough alpha-theory draft", bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO
    )
    assert api.document_role(receipt.doc) is DocRole.MATIERE_DE_TRAVAIL


def test_endorse_document_needs_an_explicit_human_gesture() -> None:
    # D137: promoting a document to a citable source (knowledge base) is ALWAYS a human gesture
    # - the documentary twin of validating a perso living fiche (D59-5). No gesture => escalate, and the
    # role stays working material (fail-closed); the gesture => knowledge base.
    api = _api()
    receipt = api.capture(
        "reference material", bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO
    )
    with pytest.raises(EscalateToHuman):
        api.endorse_document(receipt.doc, human_validated=False)
    assert api.document_role(receipt.doc) is DocRole.MATIERE_DE_TRAVAIL  # unchanged, fail-closed
    assert api.endorse_document(receipt.doc, human_validated=True) is DocRole.BASE_DE_CONNAISSANCES


def test_declassify_escalates_without_the_human_gesture() -> None:
    # D107 / D147: declassification (sensible -> public COPY) is the ONE human-gated exception to
    # upward-only labelling, now reachable through the facade (D147, wiring the human gesture). The distinct
    # audit PROPOSES; without user's explicit gesture the content stays sensible (fail-safe) - the audit
    # never auto-authorizes egress. The door is reachable, but no weaker than the D107 mechanism.
    api = _api()
    draft = Envelope(
        payload="a deliverable born of sensible material",
        label=GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble("perso")),
    )
    audit = api.audit_declassify(draft, producer="frontier", verifier="opus")
    with pytest.raises(EscalateToHuman):
        api.declassify(draft, audit=audit, human_validated=False)


def test_declassify_refuses_a_self_audit() -> None:
    # D100-6 (producer != verifier): a self-audited attestation cannot even be produced - the FIRST
    # gate fails closed before any declassification is possible (no self-blessed egress).
    api = _api()
    draft = Envelope(
        payload="x", label=GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble("perso"))
    )
    with pytest.raises(CanalBXLRefused):
        api.audit_declassify(draft, producer="same-identity", verifier="same-identity")


def test_declassify_produces_a_public_copy_leaving_the_original_intact() -> None:
    # The gesture path: a DISTINCT audit + human_validated -> a FRESH public envelope with the SAME
    # payload/bubble (declassification does not redact); the original envelope is never mutated
    # (non-destructive, D44 / D56 - the sensible source stays sensible).
    api = _api()
    draft = Envelope(
        payload="publishable once the distinct audit clears it",
        label=GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble("perso")),
    )
    audit = api.audit_declassify(draft, producer="frontier", verifier="opus")
    public = api.declassify(draft, audit=audit, human_validated=True)
    assert public.label.sensitivity is Sensitivity.PUBLIC  # the copy is public
    assert (
        public.payload == draft.payload
    )  # same content - declassification re-labels, never redacts
    assert public.label.bubble == draft.label.bubble  # same bubble
    assert draft.label.sensitivity is Sensitivity.SENSIBLE  # ORIGINAL untouched (non-destructive)


def test_recall_cites_only_endorsed_documents_as_sources_not_working_material() -> None:
    # D137, the danger user named: a "new alpha theory" query must NOT cite an old unendorsed draft as a
    # source. Unendorsed => WORKING MATERIAL (enumerable, never citable); once ENDORSED the SAME doc
    # moves into the citable ``facts`` bucket - the working/source distinction is structural, not advice.
    api = _api()
    doc = "harbor cargo tariff transit intake plan " * 30
    receipt = api.capture(doc, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    before = api.recall(
        "harbor cargo tariff",
        within=Sensitivity.PERSO,
        subject=Bubble("perso"),
        kind=QueryKind.FACTUAL,
    )
    assert before.working_material and before.facts == ()  # unverified - never a source
    api.endorse_document(receipt.doc, human_validated=True)
    after = api.recall(
        "harbor cargo tariff",
        within=Sensitivity.PERSO,
        subject=Bubble("perso"),
        kind=QueryKind.FACTUAL,
    )
    assert after.facts and after.working_material == ()  # now an endorsed, citable source


def test_retract_document_returns_it_to_working_material_without_a_gesture() -> None:
    # D137: tightening (un-endorsing) is the fail-safe direction - always allowed, no gesture (mirrors
    # monotonic prudence: declassifying UP needs a gesture, tightening DOWN is free).
    api = _api()
    receipt = api.capture("material", bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    api.endorse_document(receipt.doc, human_validated=True)
    assert api.document_role(receipt.doc) is DocRole.BASE_DE_CONNAISSANCES
    assert api.retract_document(receipt.doc) is DocRole.MATIERE_DE_TRAVAIL


def test_a_changed_re_write_de_endorses_a_document_but_an_identical_one_keeps_it() -> None:
    # D137 / D58: a new VERSION of an endorsed source is no longer trusted as authority until
    # re-endorsed (fail-closed, like living memory's update->PROPOSED); an identical re-capture keeps it.
    api = _api()
    receipt = api.capture(
        "v1 endorsed body", bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO
    )
    api.endorse_document(receipt.doc, human_validated=True)
    api.capture(
        "v1 endorsed body", bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO, doc=receipt.doc
    )
    assert (
        api.document_role(receipt.doc) is DocRole.BASE_DE_CONNAISSANCES
    )  # identical => endorsement kept
    api.capture(
        "v2 CHANGED body", bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO, doc=receipt.doc
    )
    assert api.document_role(receipt.doc) is DocRole.MATIERE_DE_TRAVAIL  # changed => de-endorsed


def test_recall_of_an_endorsed_source_still_packs_a_bounded_passage() -> None:
    # D137 × D136: endorsement changes the BUCKET, not the passage discipline - an endorsed long doc is
    # still packed to its matched passage, never returned whole (the fail-closed runner bound holds).
    api = _api()
    filler = "\n\n".join("neutral filler unrelated to anything here" for _ in range(60))
    marker = "harbor cargo tariff transit intake plan " * 30
    doc = filler + "\n\n" + marker + "\n\n" + filler
    receipt = api.capture(doc, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    api.endorse_document(receipt.doc, human_validated=True)
    view = api.recall(
        "harbor cargo tariff",
        within=Sensitivity.PERSO,
        subject=Bubble("perso"),
        kind=QueryKind.FACTUAL,
    )
    assert view.facts and view.working_material == ()
    packed = view.facts[0].payload
    assert "harbor" in packed and "cargo" in packed and len(packed) < len(doc)  # bounded passage


def test_recall_never_cites_an_archived_document_even_when_endorsed() -> None:
    # Audit finding 1 (D137 × D60): an INVALIDATED (archived) document is dropped from recall ENTIRELY -
    # least of all cited as a source once endorsed. Defense in depth: the truth store is the arbiter, so
    # a stale derived-index entry that outlived an archival never surfaces in an answer (fail-closed).
    api = _api()
    doc = "harbor cargo tariff transit intake plan " * 30
    receipt = api.capture(doc, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    api.endorse_document(receipt.doc, human_validated=True)
    before = api.recall(
        "harbor cargo tariff",
        within=Sensitivity.PERSO,
        subject=Bubble("perso"),
        kind=QueryKind.FACTUAL,
    )
    assert before.facts  # endorsed & valid => citable
    api._rt.truth.invalidate(receipt.doc, reason="archived: bad theory")  # noqa: SLF001
    after = api.recall(
        "harbor cargo tariff",
        within=Sensitivity.PERSO,
        subject=Bubble("perso"),
        kind=QueryKind.FACTUAL,
    )
    assert (
        after.facts == () and after.working_material == ()
    )  # archived => never surfaced, either bucket
    assert after.admitted_low_recall  # honest "I don't know", not a stale citation


def test_recall_keeps_a_more_sensitive_fiche_out_of_a_lower_partition() -> None:
    # Partition isolation (invariant 1 / D54): a SENSIBLE living fiche NEVER surfaces in a PERSO
    # recall - the living frame is scoped to the read's own sensitivity partition, fail-closed.
    api = _api()
    secret = Fiche(
        id="s1",
        ftype=FicheType.OPINION,
        content=frozenset({"a sensible opinion"}),
        label=GovernanceLabel(sensitivity=Sensitivity.SENSIBLE, bubble=Bubble("perso")),
    )
    api._memory.propose(secret)  # noqa: SLF001
    api.validate_fiche("s1", human_validated=True)  # validated, but SENSIBLE
    perso = api.recall(
        "opinion", within=Sensitivity.PERSO, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert perso.frame == ()  # no upward leak - the sensible fiche stays in its own partition
    sensible = api.recall(
        "opinion", within=Sensitivity.SENSIBLE, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert len(sensible.frame) == 1  # its OWN partition sees it (no false negative)


def test_validate_fiche_auto_applies_a_benign_public_preference() -> None:
    # Two-speed (D59-5): only a benign PUBLIC preference may validate without an explicit gesture,
    # then reinject; everything else escalates (proven in the D100-net test above).
    api = _api()
    pref = Fiche(
        id="pub-1",
        ftype=FicheType.PREFERENCE,
        content=frozenset({"use metric units"}),
        label=GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("perso")),
    )
    api._memory.propose(pref)  # noqa: SLF001
    validated = api.validate_fiche("pub-1", human_validated=False)  # auto-applies (D59-5)
    assert validated.state == ValidationState.VALIDATED
    view = api.recall(
        "units", within=Sensitivity.PUBLIC, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert len(view.frame) == 1


def test_remember_proposes_an_inert_learning_awaiting_validation() -> None:
    # item 2: `remember` deposits a durable learning INERT into the validation queue (PROPOSED, a
    # LEARNING), reinjecting into no answer until the operator's gesture - propose, never impose (D92 / D100).
    api = _api()
    fiche = api.remember("cite the doc ids you relied on", subject=Bubble("perso"))
    assert fiche.state == ValidationState.PROPOSED and fiche.ftype == FicheType.LEARNING
    [pending] = api.pending_fiches()
    assert pending.id == fiche.id
    with pytest.raises(
        EscalateToHuman
    ):  # a LEARNING never auto-applies - it awaits the gesture (D59-5)
        api.validate_fiche(fiche.id, human_validated=False)


def test_remember_is_idempotent_no_queue_noise() -> None:
    # anti-noise (user's concern): proposing the SAME learning twice collapses to ONE queue entry.
    api = _api()
    api.remember("prefer make targets to ad-hoc scripts", subject=Bubble("perso"))
    api.remember("prefer make targets to ad-hoc scripts", subject=Bubble("perso"))
    assert len(api.pending_fiches()) == 1


def test_remember_refuses_a_document_sized_learning() -> None:
    # a learning is concise + stored whole (no Moteur B backup) - an over-long one is refused, never
    # truncated; capturing a document is `capture`'s job.
    with pytest.raises(ValueError, match="concise"):
        _api().remember("x" * 5000, subject=Bubble("perso"))


def test_recall_admits_low_recall_when_both_engines_are_empty() -> None:
    # Invariant 14 on the fused read: with no validated fiche and no document, recall ADMITS "I
    # don't know" rather than inventing.
    view = _api().recall("anything", within=Sensitivity.PERSO, subject=Bubble("perso"))
    assert view.frame == () and view.facts == () and view.working_material == ()
    assert view.admitted_low_recall


def test_capture_never_declassifies_a_validated_living_fiche() -> None:
    # The MAJEUR the audit caught, end to end (dormant under the stub, live once (3)-3c wires the real
    # extractor): re-capturing the SAME fact at a LOWER sensitivity must NOT declassify or re-open a
    # validated fiche. The store refuses (D100-2 / invariant 17); capture absorbs it and keeps the
    # datum in the graph - the sensible fiche stands, never leaking down to a public recall.
    rt = replace(bootstrap(policy=_permissive_policy()), fact_extractor=_FakeExtractor())
    api = CoreApi(rt)
    api.capture(
        "sensible source",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.SENSIBLE,
        nature=ContentNature.BEHAVIOUR,
    )
    [fiche] = api.pending_fiches()
    api.validate_fiche(fiche.id, human_validated=True)  # validated SENSIBLE
    api.capture(
        "public source",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PUBLIC,
        nature=ContentNature.BEHAVIOUR,
    )  # same fact, lower
    assert api.pending_fiches() == ()  # NOT re-opened to PROPOSED - the gesture is preserved
    sensible = api.recall(
        "short", within=Sensitivity.SENSIBLE, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert len(sensible.frame) == 1  # stands in its own partition
    public = api.recall(
        "short", within=Sensitivity.PUBLIC, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert public.frame == ()  # never declassified down to the public partition


def test_capture_aggregates_facts_per_subject_into_one_fiche() -> None:
    # (3)-3c / D120: the rich factory - TWO facts about `operator` in one capture become ONE per-subject
    # fiche (de-duplication), not two fragments, so the validation queue stays humane at scale.
    rt = replace(bootstrap(policy=_permissive_policy()), fact_extractor=_MultiFactExtractor())
    api = CoreApi(rt)
    api.capture(
        "about operator",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
    )
    [fiche] = api.pending_fiches()  # ONE fiche, not two
    assert len(fiche.content) == 2  # both facts aggregated into the single per-subject fiche


def test_capture_falls_back_to_a_plan_b_note_when_extraction_is_untrusted() -> None:
    # (3)-3c / D58: below the golden-set bar (graph_extraction_trusted=False), capture imposes NO
    # graph - the datum lands in Moteur B and a readable `.md` NOTE surfaces for user to triage.
    rt = replace(
        bootstrap(policy=_permissive_policy(), graph_extraction_trusted=False),
        fact_extractor=_FakeExtractor(),
    )
    api = CoreApi(rt)
    receipt = api.capture(
        "I prefer short answers",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
    )
    assert receipt.engines == ("B",)  # no graph imposed (plan B)
    assert rt.graph.query(subject=NodeId("operator")) == []  # the extractor's fact is NOT filed
    [note] = api.pending_fiches()
    assert note.ftype == FicheType.NOTE and "plan-B" in receipt.reason


def test_capture_keeps_the_datum_when_the_extractor_raises() -> None:
    # (3)-3c (3a debt): an extractor that RAISES must never lose the datum. The failure is caught, the
    # content still lands truth-first in Moteur B (searchable), a plan-B note surfaces - no crash.
    rt = replace(bootstrap(policy=_permissive_policy()), fact_extractor=_RaisingExtractor())
    api = CoreApi(rt)
    receipt = api.capture(
        "some behaviour to remember",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
    )
    assert receipt.engines == ("B",)  # datum saved to Moteur B; the graph stays empty
    assert "FAILED" in receipt.reason  # honest (F3): extraction failed, datum not lost
    found = api.search("behaviour", within=Sensitivity.PERSO, subject=Bubble("perso"))
    assert found.hits  # the content reached Moteur B despite the extractor raising
    [note] = api.pending_fiches()
    assert note.ftype == FicheType.NOTE  # plan-B note for the un-extracted datum


def test_capture_files_deterministic_structural_facts_when_a_language_is_given() -> None:
    # (3)-3 / D125-B9: with a source language, the tree-sitter pre-pass files DETERMINISTIC facts to
    # the graph + FACT fiches - INDEPENDENT of the LLM route/trust (they carry no model doubt). Even
    # in plan-B mode (untrusted LLM) on a DOCUMENT route, the structural facts still land.
    rt = replace(
        bootstrap(policy=_permissive_policy(), graph_extraction_trusted=False),
        structural_extractor=_FakeStructuralExtractor(),
    )
    api = CoreApi(rt)
    receipt = api.capture(
        "def parse_source(): pass",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        language="python",
    )
    assert rt.graph.query(subject=NodeId("parse_source"))  # deterministic fact filed to the graph
    assert "A" in receipt.engines  # Moteur A credited - a fact reached the graph
    [fiche] = [f for f in api.pending_fiches() if f.ftype == FicheType.FACT]
    assert "parse_source defined_as function" in " ".join(fiche.content)


def test_capture_without_a_language_never_runs_the_structural_pre_pass() -> None:
    # the pre-pass fires ONLY on a declared language (code ingestion); generic text capture passes
    # none, so it is inert - no structural fact, no spurious triple from ordinary prose.
    rt = replace(
        bootstrap(policy=_permissive_policy()), structural_extractor=_FakeStructuralExtractor()
    )
    CoreApi(rt).capture(
        "an ordinary prose note", bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO
    )
    assert rt.graph.query(subject=NodeId("parse_source")) == []  # inert without a language


def test_structural_and_llm_facts_about_one_subject_stay_distinct_fiches() -> None:
    # audit MAJEUR 1: a structural fact (code identifier) and an LLM fact naming the SAME subject
    # 'operator' must NOT collide - the LLM leg never silently clobbers the structural fiche (disjoint id
    # namespaces). Two distinct PROPOSED fiches result, and the receipt count is honest (2, not a lie).
    rt = replace(
        bootstrap(policy=_permissive_policy()),
        fact_extractor=_FakeExtractor(),  # LLM emits (operator, prefere, concis)
        structural_extractor=_OperatorStructuralExtractor(),  # structural emits (operator, defined_as, function)
    )
    api = CoreApi(rt)
    receipt = api.capture(
        "I prefer short answers",
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
        language="python",
    )
    contents = {" ".join(sorted(f.content)) for f in api.pending_fiches()}
    assert len(contents) == 2  # two distinct fiches - neither clobbered
    assert "operator defined_as function" in contents  # the structural fiche SURVIVED the LLM leg
    assert "operator prefere concis" in contents  # the LLM fiche is present
    assert (
        "2 fiche(s) awaiting" in receipt.reason
    )  # honest count (F3), not a lying "2" over a queue of 1


def test_capture_survives_a_raising_structural_pre_pass() -> None:
    # audit MAJEUR 2: a structural parser that RAISES must never lose the datum (the 3a debt, on the
    # structural leg too). The failure is caught, the content still reaches Moteur B, capture never crashes.
    rt = replace(
        bootstrap(policy=_permissive_policy()), structural_extractor=_RaisingStructuralExtractor()
    )
    api = CoreApi(rt)
    receipt = api.capture(
        "def f(): pass", bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO, language="python"
    )  # structural raises
    assert receipt.doc  # no crash - capture completed
    found = api.search("def", within=Sensitivity.PERSO, subject=Bubble("perso"))
    assert found.hits  # the datum reached Moteur B despite the parser raising
    assert (
        rt.graph.query(subject=NodeId("f")) == []
    )  # degraded gracefully - no structural fact filed


# --- (a″) source ingestion - binary / voice behind the SourceReader prise ((3)-4 / D125-B5) --------
def test_capture_reads_a_raw_source_and_preserves_it_in_the_benne() -> None:
    # (3)-4: a raw source (document / image / voice) is turned into text by the reader prise, then flows
    # through the SAME classify -> route -> integrate path; the raw Source is PRESERVED in the benne
    # (truth-first for binary, D85), and the receipt is honest about fidelity (F3). A DOCUMENT source
    # routes to Moteur B only - it never auto-injects a living fiche.
    rt = replace(bootstrap(policy=_permissive_policy()), source_reader=_FakeSourceReader())
    api = CoreApi(rt)
    src = Source(ref="scan.pdf", data=b"ignored-by-the-double", mime="application/pdf")
    receipt = api.capture(source=src, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    assert receipt.engines == ("B",)  # a document routes to Moteur B (D57)
    assert api.pending_fiches() == ()  # no living fiche imposed from a document source
    assert "fidelity OK" in receipt.reason and "preserved in benne" in receipt.reason
    assert api.search(
        "document", within=Sensitivity.PERSO, subject=Bubble("perso")
    ).hits  # reached B
    assert api._benne.item(receipt.doc).source is src  # raw preserved for re-extraction (D85)


def test_capture_needs_exactly_one_of_text_or_source() -> None:
    # D55 single door, no silent guess: neither / both is a ValueError.
    api = _api()
    with pytest.raises(ValueError, match="exactly one"):
        api.capture(bubble=Bubble("perso"))
    with pytest.raises(ValueError, match="exactly one"):
        api.capture("text", source=Source("a", b"b", "m"), bubble=Bubble("perso"))


def test_capture_keeps_the_datum_when_the_source_reader_raises() -> None:
    # (3)-4 truth-first for binary: a reader that RAISES (broken OCR) must never lose the datum. The raw
    # source is preserved in the benne, the receipt is honest (FAILED), and capture never crashes.
    rt = replace(bootstrap(policy=_permissive_policy()), source_reader=_RaisingSourceReader())
    api = CoreApi(rt)
    src = Source(ref="corrupt.pdf", data=b"\xff\xfe", mime="application/pdf")
    receipt = api.capture(source=src, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    assert receipt.doc  # no crash - capture completed
    assert "FAILED" in receipt.reason  # honest (F3): extraction failed, datum not lost
    assert api._benne.item(receipt.doc).source is src  # raw preserved for re-extraction (D85)


def test_capture_flags_a_low_fidelity_source_extraction() -> None:
    # (3)-4 / D125-B6: when the reader is not trusted (below the ingestion golden-set bar) the extraction
    # is FLAGGED low-fidelity - the text still ingests (raw preserved), never silently trusted (F3).
    rt = replace(
        bootstrap(policy=_permissive_policy(), source_extraction_trusted=False),
        source_reader=_FakeSourceReader(),
    )
    receipt = CoreApi(rt).capture(
        source=Source("s.pdf", b"x", "application/pdf"),
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
    )
    assert "LOW-FIDELITY" in receipt.reason


def test_capture_flags_a_near_duplicate_source_non_destructively() -> None:
    # D85: a re-scan of the same document is FLAGGED (non-destructive) - never auto-dropped; the human
    # arbitrates. Both copies stay held in the benne.
    rt = replace(bootstrap(policy=_permissive_policy()), source_reader=_FakeSourceReader())
    api = CoreApi(rt)
    api.capture(
        source=Source("a.pdf", b"1", "application/pdf"),
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
    )
    receipt = api.capture(
        source=Source("b.pdf", b"2", "application/pdf"),
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
    )  # same extracted text => near-duplicate
    assert "near-duplicate" in receipt.reason
    assert len(api._benne._items) == 2  # both copies held, neither dropped (D85)


def test_capture_source_intake_is_bounded_fail_closed() -> None:
    # invariant 16 / D78: the benne's raw-intake queue is bounded - a source that would overflow it is
    # refused fail-closed (a big medium cannot swamp the queue), never silently accepted.
    policy = replace(
        _permissive_policy(),
        bounds=MappingProxyType(
            {
                "queue_capacity": 8,
                "concurrency": 1,
                "intake_capacity": 1,
                "intake_source_bytes": 268435456,
            }
        ),
    )
    rt = replace(bootstrap(policy=policy), source_reader=_FakeSourceReader())
    api = CoreApi(rt)
    api.capture(
        source=Source("a.pdf", b"1", "application/pdf"),
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
    )  # fills the queue (capacity 1)
    with pytest.raises(ResourceBoundError):
        api.capture(
            source=Source("b.pdf", b"2", "application/pdf"),
            bubble=Bubble("perso"),
            domain_signal=Sensitivity.PERSO,
        )


def test_capture_runs_the_structural_pre_pass_on_an_extracted_source() -> None:
    # (3)-4 ⊕ (3)-3: a code file ingested as a SOURCE composes with the tree-sitter pre-pass - the reader
    # yields the code text, and the declared language files deterministic structural facts from it.
    rt = replace(
        bootstrap(policy=_permissive_policy()), structural_extractor=_FakeStructuralExtractor()
    )
    api = CoreApi(rt)
    src = Source(ref="mod.py", data=b"def parse_source(): pass", mime="text/x-python")
    api.capture(
        source=src, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO, language="python"
    )
    assert rt.graph.query(
        subject=NodeId("parse_source")
    )  # structural facts from the extracted source


def test_a_source_derived_living_fact_is_under_the_d100_net() -> None:
    # (3)-4 ⊕ D100: a living fact extracted from a SOURCE (not typed text) inherits the SAME net - it is
    # inert until validated. Nothing from a scanned document reaches an answer without the human gesture.
    rt = replace(
        bootstrap(policy=_permissive_policy()),
        source_reader=_FakeSourceReader(),
        fact_extractor=_FakeExtractor(),
    )
    api = CoreApi(rt)
    api.capture(
        source=Source("memo.pdf", b"x", "application/pdf"),
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        nature=ContentNature.BEHAVIOUR,
    )
    assert len(api.pending_fiches()) == 1  # proposed, not applied
    before = api.recall(
        "x", within=Sensitivity.PERSO, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert before.frame == ()  # D100 gate closed until validation - even for a source-derived fact


def test_capture_refuses_to_clobber_a_raw_source_on_doc_id_reuse() -> None:
    # (3)-4a audit MAJEUR 1: reusing an explicit doc= for a DIFFERENT source is refused fail-closed - the
    # benne is non-destructive (D85), so the first raw source is never silently dropped (no lost datum).
    rt = replace(bootstrap(policy=_permissive_policy()), source_reader=_FakeSourceReader())
    api = CoreApi(rt)
    first = Source("a.pdf", b"AAAA", "application/pdf")
    api.capture(
        source=first, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO, doc=DocId("dup")
    )
    with pytest.raises(ValueError):
        api.capture(
            source=Source("b.pdf", b"BBBB", "application/pdf"),
            bubble=Bubble("perso"),
            domain_signal=Sensitivity.PERSO,
            doc=DocId("dup"),
        )
    assert api._benne.item(DocId("dup")).source is first  # the original raw source survives (D85)


def test_capture_source_receipt_does_not_leak_a_foreign_partition_doc() -> None:
    # (3)-4a audit MAJEUR 2: a PERSO capture's receipt never names a SENSIBLE document - dedup is
    # cloisonnement-scoped (invariant 1 / 3), so no cross-partition metadata (DocId / %) leaks (D66).
    rt = replace(bootstrap(policy=_permissive_policy()), source_reader=_FakeSourceReader())
    api = CoreApi(rt)
    api.capture(
        source=Source("s.pdf", b"S", "application/pdf"),
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.SENSIBLE,
        doc=DocId("sensible-doc"),
    )
    receipt = api.capture(
        source=Source("p.pdf", b"P", "application/pdf"),
        bubble=Bubble("perso"),
        domain_signal=Sensitivity.PERSO,
        doc=DocId("perso-doc"),
    )
    assert "sensible-doc" not in receipt.reason  # no cross-partition metadata leak in the receipt


def test_capture_degrades_when_the_source_reader_returns_non_str() -> None:
    # (3)-4a audit MINEUR 2: a reader that RETURNS a non-str (a (3)-4b adapter drift on an odd format) must
    # degrade like a raise - raw preserved, honest FAILED receipt, never a classify() crash.
    rt = replace(bootstrap(policy=_permissive_policy()), source_reader=_NonStrSourceReader())
    api = CoreApi(rt)
    src = Source("weird.bin", b"\x00", "application/octet-stream")
    receipt = api.capture(source=src, bubble=Bubble("perso"), domain_signal=Sensitivity.PERSO)
    assert "FAILED" in receipt.reason  # honest (F3) - degraded, not crashed
    assert api._benne.item(receipt.doc).source is src  # raw preserved for re-extraction (D85)


def test_recall_withholds_a_living_fiche_in_an_undeclared_domain() -> None:
    # Inv.4 / D72 on the LIVING leg, symmetric with Moteur B: a validated fiche carrying a domain the
    # bubble does NOT declare is withheld from the recall frame, exactly as a document hit would be.
    policy = replace(
        _permissive_policy(),
        declared_domains=MappingProxyType({Bubble("projet"): frozenset({Domain("sante")})}),
    )
    api = _api(policy)
    fin = Fiche(
        id="f-fin",
        ftype=FicheType.OPINION,
        content=frozenset({"a finance view"}),
        label=GovernanceLabel(
            sensitivity=Sensitivity.SENSIBLE,
            bubble=Bubble("projet"),
            domains=frozenset({Domain("finances")}),
        ),  # NOT declared for projet
    )
    api._memory.propose(fin)  # noqa: SLF001
    api.validate_fiche("f-fin", human_validated=True)
    withheld = api.recall(
        "finance", within=Sensitivity.SENSIBLE, subject=Bubble("projet"), kind=QueryKind.PERSONAL
    )
    assert withheld.frame == ()  # undeclared domain -> withheld from the living frame (inv.4)
    ok = Fiche(
        id="f-sante",
        ftype=FicheType.OPINION,
        content=frozenset({"a health view"}),
        label=GovernanceLabel(
            sensitivity=Sensitivity.SENSIBLE,
            bubble=Bubble("projet"),
            domains=frozenset({Domain("sante")}),
        ),
    )
    api._memory.propose(ok)  # noqa: SLF001
    api.validate_fiche("f-sante", human_validated=True)
    seen = api.recall(
        "health", within=Sensitivity.SENSIBLE, subject=Bubble("projet"), kind=QueryKind.PERSONAL
    )
    assert len(seen.frame) == 1  # a DECLARED domain is visible (no false negative)


def test_recall_reason_names_only_the_engines_actually_read() -> None:
    # F3: a FACTUAL query reads Moteur B only - the reason must not claim a Moteur A leg it never
    # consulted (engines is already honest; this pins the reason string too).
    view = _api().recall(
        "x", within=Sensitivity.PERSO, subject=Bubble("perso"), kind=QueryKind.FACTUAL
    )
    assert view.engines == ("B",)
    assert "Moteur A" not in view.reason


def test_search_reports_the_real_engine_and_points_at_recall_for_fusion() -> None:
    # Honesty on read: a PERSONAL query routes to Moteur A (D65), but search() is the Moteur B
    # document-retrieval surface - it reports engines==('B',) and points at recall() for the A⊕B
    # living fusion ((3)-3b), no longer claiming a deferred, not-yet-assembled A leg.
    view = _api().search(
        "anything", within=Sensitivity.PERSO, subject=Bubble("perso"), kind=QueryKind.PERSONAL
    )
    assert view.engines == ("B",)  # REAL: search reads only Moteur B (vector)
    assert "recall()" in view.reason  # the A⊕B living fusion lives at recall() now ((3)-3b / D65)


# --- (c) supervision: export (canal A/B), kill-switch, backup ----------------------------
def test_export_public_to_allowlisted_host_is_canal_a() -> None:
    api = _api()
    grant = api.export(_public_env(), to_host=_ALLOW_HOST)
    assert isinstance(grant, Grant)


def test_export_sensible_escalates_to_canal_b() -> None:
    api = _api()
    with pytest.raises(EscalateToHuman):  # non-public never leaves automatically (D66 / D90)
        api.export(_sensible_env(), to_host=_ALLOW_HOST)


def test_export_public_label_but_pii_content_escalates_to_canal_b() -> None:
    # M2 - the Guard re-reads the CONTENT at egress: an IBAN in a PUBLIC-labelled envelope
    # is caught by the deterministic PII floor and forced to canal B, never canal A.
    api = _api()
    with pytest.raises(EscalateToHuman):
        api.export(_public_env("wire transfer IBAN FR7630006000011234567890189"), to_host=_ALLOW_HOST)


def test_export_to_unlisted_host_is_denied() -> None:
    api = _api()
    with pytest.raises(GuardDenied):  # allow-list deny-by-default (invariant 21 / SE5)
        api.export(_public_env(), to_host="evil.example.org")


def test_kill_switch_suspends_and_lists_pending() -> None:
    api = _api()
    rt = api._rt  # noqa: SLF001 - structural test of the supervision surface
    work = WorkItem(
        id=WorkId("w1"),
        trigger=TriggerKind.PERIODIC,
        descriptor="a background pass",
        label=GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("perso")),
    )
    rt.scheduler.submit(work)
    rt.scheduler.dispatch()
    api.kill_switch()  # D80
    assert WorkId("w1") in api.pending_validations()


def test_verify_backup_restores_and_smokes() -> None:
    report = _api().verify_backup()
    assert report.smoke_test_passed  # a backup never restored is not a backup (D110)


def test_calibrate_measures_the_golden_bars() -> None:
    report = _api().calibrate()
    # the stub extractor abstains: groundedness reads ungrounded (fail-closed, D148) and the old
    # informative extraction-F1 reads 0 too; the utf-8 reader recovers the seed -> fidelity clears.
    # The groundedness anchor is what flips graph_extraction_trusted at ignition now (D69 / D148 / (3)-7).
    assert report.groundedness is not None and not report.groundedness.trusted
    assert report.extraction_f1 is not None and report.extraction_f1.f1 == 0.0
    assert report.gate(
        "fidelity"
    ).clears  # utf-8 PlainTextSourceReader recovers the seed faithfully
    assert not report.all_clear  # groundedness untrusted => both trust flags stay False


def test_calibrate_floor_earns_the_recall_floor_from_the_golden_set() -> None:
    # the one-door surface (D55) for the third provisional number ((3)-2a / D69): the stub embedder
    # separates the seed, so the sweep earns a clean floor (F1 1.0) at a positive, sub-1 value. A
    # RECOMMENDATION for recall_floor, adopted by [OPERATOR] gesture at ignition, never auto-applied (D100).
    floor = _api().calibrate_floor()
    assert floor.f1 == 1.0 and 0.0 < floor.floor < 1.0


# --- the structural property: the facade cannot bypass the Guard (D119) ------------------
def test_facade_cannot_bypass_the_guard() -> None:
    rt = bootstrap(policy=_permissive_policy())
    denied = CoreApi(replace(rt, guard=_DenyAllGuard()))
    # even a public, allow-listed export fails when the Guard says no - proof the Guard is
    # actually in the path, not decorative (D119 / D89).
    with pytest.raises(GuardDenied):
        denied.export(_public_env(), to_host=_ALLOW_HOST)
    with pytest.raises(GuardDenied):
        denied.register_tool("some-tool")
    # capture_youtube is outbound too: with a fetcher WIRED, a deny-all Guard STILL refuses, and the network
    # is never touched (the grant precedes the fetch) - proof it is Guard-mediated, not decorative (D89).
    stub = _StubFetcher(_YT_TRANSCRIPT)
    yt_denied = CoreApi(replace(rt, guard=_DenyAllGuard(), transcript_fetcher=stub))
    with pytest.raises(GuardDenied):
        yt_denied.capture_youtube("https://youtu.be/abcdefghijk", bubble=Bubble("perso"))
    assert stub.calls == 0


# --- (d) production ----------------------------------------------------------------------
def test_promote_needs_a_distinct_verifier_and_a_human() -> None:
    api = _api()
    draft = Draft(content=_public_env("a deliverable draft"), producer="alice")
    with pytest.raises(PromotionRefused):  # self-audit refused (D79 / D75)
        api.promote(draft, verifier="alice", human_validated=True)
    with pytest.raises(EscalateToHuman):  # missing human gesture (D79 / D96)
        api.promote(draft, verifier="bob", human_validated=False)
    deliverable = api.promote(draft, verifier="bob", human_validated=True)
    assert deliverable.verifier == "bob" and deliverable.producer == "alice"


# --- (e) governance ----------------------------------------------------------------------
def test_governance_view_reads_the_protected_zone() -> None:
    api = _api()
    view = api.governance()
    assert isinstance(view, GovernanceView)
    assert view.profile == "test"
    assert _ALLOW_HOST in view.egress_allowlist
    assert view.bounds["concurrency"] == 1


def test_register_tool_is_a_privileged_human_act() -> None:
    api = _api()
    with pytest.raises(EscalateToHuman):  # POLICY_WRITE - never agent-auto (D114-(5) / D102)
        api.register_tool("new-mcp-server")


def test_authorize_tool_call_is_deny_by_default_without_a_catalog() -> None:
    # the 8th effect is mediated (D114-(3)): the protected allow-list is wired but EMPTY ((3)-5a - the
    # skeleton ships no tool, contenant not contenu, D98), so an invocation is denied by default; the
    # facade cannot reach a tool behind the Guard's back (D100).
    api = _api()
    with pytest.raises(GuardDenied):
        api.authorize_tool_call("any-tool", subject=Bubble("perso"))


def test_call_tool_is_deny_by_default_through_the_governed_executor() -> None:
    # (3)-5a: call_tool runs the WHOLE governed loop (grant -> redeem -> invoke -> re-label the untrusted
    # return). With the protected allow-list empty, the Guard refuses at the mint step - nothing is
    # redeemed, no plugin runs - so the facade reaches no tool fail-closed (D114-(5) / D100).
    api = _api()
    args = Envelope(
        payload="args", label=GovernanceLabel(sensitivity=Sensitivity.PERSO, bubble=Bubble("perso"))
    )
    with pytest.raises(GuardDenied):
        api.call_tool("any-tool", args, subject=Bubble("perso"))


# --- (f) meta/transverse inbox -----------------------------------------------------------
def test_inbox_proposes_but_never_imposes() -> None:
    api = _api()
    proposal = api.submit_proposal(source="aggregator", summary="create a living doc")
    assert len(api.inbox()) == 1  # waiting for user - no auto-application (D92 / D100)
    reviewed = api.review(proposal.id, accept=True, comment="ok")
    assert reviewed.reviewed and reviewed.accepted
    assert api.inbox() == ()  # reviewed leaves the pending queue


def test_review_unknown_proposal_raises() -> None:
    api = _api()
    with pytest.raises(KeyError):
        api.review("nope", accept=True)


# --- (g) generic create/extend hook ------------------------------------------------------
def test_create_is_a_named_hook_without_side_effect() -> None:
    api = _api()
    out = api.create("project", into=Bubble("perso"))
    assert "hook only" in out  # D119-g: named, Phase 1 bis


# --- smoke test (D109 stage (4)) through the runtime ---------------------------------------
def test_smoke_via_bootstrap_passes_and_flags_prereqs() -> None:
    from mnemosyne.runtime import run_smoke_test

    report = run_smoke_test()
    assert report.passed
    names = [s.name for s in report.steps]
    assert names == [
        "bootstrap",
        "capture",
        "source",
        "index",
        "graph",
        "living",
        "retrieve",
        "recall",
        "answer",
        "tools",
        "agent",
        "render",
    ]
    assert len(report.flags) == 3  # ADP / Kopia key / API ceiling all UNKNOWN by default (E4)


def test_runtime_type_is_frozen_snapshot() -> None:
    # the facade holds a Runtime; a public re-export exists for typing/UIs
    assert isinstance(bootstrap(policy=_permissive_policy()), Runtime)


# --- (a) capture_youtube - outbound, Guard-mediated (topic 3 / C3) ------------------------
def test_capture_youtube_refused_when_host_not_allowlisted() -> None:
    # deny-by-default OUTBOUND (inv. 5/21): the default allow-list has NO YouTube host, so the Guard refuses
    # the grant - and the fetch NEVER runs. THE safety property: the grant is asked BEFORE the network.
    stub = _StubFetcher(_YT_TRANSCRIPT)
    api = _yt_api(
        fetcher=stub, policy=_permissive_policy()
    )  # allow-list = {api.example.com}, not youtube
    with pytest.raises(GuardDenied):
        api.capture_youtube("https://youtu.be/abcdefghijk", bubble=Bubble("perso"))
    assert (
        stub.calls == 0
    )  # blocked before touching the network - order is the safety, not discipline


def test_capture_youtube_memorizes_the_transcript_when_allowlisted() -> None:
    stub = _StubFetcher(_YT_TRANSCRIPT)
    receipt = _yt_api(fetcher=stub).capture_youtube(
        "https://youtu.be/abcdefghijk", bubble=Bubble("perso")
    )
    assert isinstance(receipt, YouTubeCaptureReceipt)
    assert stub.calls == 1
    assert receipt.video_id == "abcdefghijk" and receipt.auto_generated is False
    assert receipt.capture is not None  # a transcript was memorized
    assert "B" in receipt.capture.engines  # routed to Moteur B (a document) and memorized
    # a YouTube transcript is PUBLIC by provenance (D144 / D107) - the 2nd public-source door: capture_youtube
    # sets public_provenance=True, so the label is authoritatively PUBLIC end-to-end, NOT a content verdict and
    # independent of the egress grant (which only ever exposed the url). This locks the door against regression.
    assert receipt.capture.sensitivity is Sensitivity.PUBLIC


def test_capture_youtube_fails_closed_without_a_fetcher() -> None:
    # no yt-dlp brick wired => no fetcher => refused fail-closed (D126), never a silent no-op.
    with pytest.raises(GuardDenied):
        _yt_api(fetcher=None).capture_youtube(
            "https://youtu.be/abcdefghijk", bubble=Bubble("perso")
        )


def test_capture_youtube_rejects_a_non_youtube_url() -> None:
    # fail-loud at the door, before any egress or fetch (D55): a non-YouTube ref raises ValueError.
    stub = _StubFetcher(_YT_TRANSCRIPT)
    with pytest.raises(ValueError):
        _yt_api(fetcher=stub).capture_youtube(
            "https://example.com/watch?v=nope", bubble=Bubble("perso")
        )
    assert stub.calls == 0  # never reached the network


def test_capture_youtube_memorizes_nothing_on_an_empty_transcript() -> None:
    # a video with no usable subtitles: the fetch ran (authorized), but nothing is memorized (honest
    # emptiness, F3 - capture is None), leaving room for a LOCAL ASR fallback later (AV1).
    stub = _StubFetcher(_YT_EMPTY)
    receipt = _yt_api(fetcher=stub).capture_youtube(
        "https://youtu.be/abcdefghijk", bubble=Bubble("perso")
    )
    assert stub.calls == 1
    assert receipt.capture is None and receipt.video_id == "abcdefghijk"
