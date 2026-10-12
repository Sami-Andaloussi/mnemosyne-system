"""Canal B XL (D90 / D102) + mixed-deliverable declassification (D107) — the two guarded gates.

Canal B is the semi-manual file bridge to a frontier brain — the ONLY way `perso` / `sensible`
data leaves, and always by a human gesture (D66 / D90). Canal A (automatic public-only cloud)
and the plain per-item canal-B egress are already the Guard's egress ruling (``_rule_egress``:
public ⇒ allow, non-public ⇒ escalate); this module graves what sits ABOVE that primitive —
the **XL protocol** (a whole worksite forked to the frontier) and the **declassification** of
a mixed deliverable — each with fail-closed gates (D102 / D107):

* **Return point BEFORE the copy (D102).** No confirmed commit/snapshot ⇒ no copy, so a later
  merge can always be rolled back (non-destructive, D56 / D60). Fail-closed.
* **Egress gate — expurgation (D102 / SE3).** Exclusion by WHOLE bubble, deny-by-default;
  `sensible` is NEVER in an XL batch; a DISTINCT verifier attests the copy is clean before it
  leaves (double attestation, producer ≠ verifier — D100-6). At any doubt, it does not go.
* **Return gate — merge (D102 / SE6).** The returned diff is UNTRUSTED data (zero-trust,
  D81), re-audited by a DISTINCT verifier; a privileged-zone merge (code / skills / policy)
  needs a human validation (D75 / D79). Rollback via the return point.

Declassification (D107) is the complementary case: a deliverable born of `sensible` material,
audited by a distinct verifier (local by default), then declassified by an explicit human
gesture into a `public` COPY — the original stays intact (non-destructive). Declassifying is
the single human-gated exception to upward-only labelling (D100-2). Code & docstrings English
(D117); the ``public`` / ``perso`` / ``sensible`` tokens stay French (D33).

Decisions: D90 (canal B doctrine + XL fork→work→merge) · D102 (the two gates + return
point) · D107 (mixed-deliverable declassification) · D81 (return = untrusted) · D100-6
(producer ≠ verifier) · D66 (sensible never leaves in auto). Invariant carried: 19.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from datetime import datetime, timezone

from ..ports import (
    Bubble,
    Envelope,
    ErrorCode,
    EscalateToHuman,
    GovernanceLabel,
    MnemosyneError,
    Provenance,
    Sensitivity,
)
from .verifier import require_distinct


class CanalBXLRefused(MnemosyneError):
    """The XL sortie gate refused a copy (fail-closed, D102).

    Like a Guard denial (``DENIED``): a missing return point, a same-identity attestation, an
    unclean copy, or a `sensible` bubble in the batch — any one refuses the copy. Nothing
    crosses to the frontier on trust (D100)."""

    code = ErrorCode.DENIED


@dataclass(frozen=True, slots=True)
class ReturnPoint:
    """A validated commit / snapshot taken BEFORE an XL copy (D102).

    Only a CONFIRMED point authorizes a copy — the guarantee that a drifting merge can always
    be rolled back to a sane state (D71 git + D82 snapshot, non-destructive D56 / D60)."""

    ref: str  # commit hash / snapshot id
    confirmed: bool = False


@dataclass(frozen=True, slots=True)
class ExpurgationAttestation:
    """A DISTINCT verifier's attestation that the expurgated copy is clean (D102 / SE3).

    Double attestation: a producer builds the copy, a *different* verifier certifies it before
    departure (producer ≠ verifier, D100-6). ``clean`` is False ⇒ it does not go (D100-4)."""

    producer: str
    verifier: str
    clean: bool = False


@dataclass(frozen=True, slots=True)
class WorkCopy:
    """An expurgated XL copy cleared to travel to the frontier (D90 / D102).

    A fresh export, NOT a clone: ``has_git_history`` is False (D90). Carries the bubbles it
    contains and the return point it can be rolled back to."""

    bubbles: frozenset[Bubble]
    return_point: ReturnPoint
    attestation: ExpurgationAttestation
    has_git_history: bool = False


@dataclass(frozen=True, slots=True)
class ReturnedDiff:
    """The frontier's returned change (code / skills / memory) — UNTRUSTED data (D81 / D102).

    ``produced_by`` is the frontier identity; the merge re-audits with a DISTINCT local
    verifier. ``return_ref`` pairs the diff to the worksite it must answer (appariement, D81 /
    D102-SE6-1). ``target_paths`` are the files it claims to modify; the merge DERIVES privilege
    from them LOCALLY (:func:`_is_privileged`) — the untrusted return never classifies its own
    privilege, so there is deliberately no ``privileged`` field here (D100 / D81)."""

    produced_by: str
    payload: str
    return_ref: str
    target_paths: tuple[str, ...] = ()


#: Content lives in exactly two POSITIVELY-shaped places (deny-by-default): the ``knowledge/``
#: document store, and a project's bounded deliverable subtree. EVERYTHING else — code, config,
#: skills, workflows, policy, manifests, the harness, any other project-nested path, any unknown
#: location — is privileged (D102-SE6-3 / D100 / D73). An ALLOW-list is used, never a deny-list,
#: precisely so a forgotten location errs toward privileged (fail-SAFE), never open.
_KNOWLEDGE_ROOT = "knowledge/"
_PROJECT_ROOT = "projects/"
#: Within ``projects/<name>/``, ONLY these subtrees are plain content (deliverables / working
#: docs, D50). A file directly in the project root, or in any other subdir (manifest, skills,
#: workflows, config, policy, the harness), is privileged.
_PROJECT_CONTENT_DIRS: frozenset[str] = frozenset(
    {
        "deliverables",
        "drafts",
        "exports",
        "outputs",
        "workspace",
        "data",
        "notes",
    }
)
#: Content = these extensions ONLY (documents / data / media). Code, config, build, lockfiles,
#: an unknown or absent extension ⇒ privileged (fail-closed) — un-evadable by renaming a dir.
_CONTENT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".md",
        ".markdown",
        ".txt",
        ".rst",
        ".org",
        ".csv",
        ".tsv",
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".html",
    }
)
#: Harness steering docs auto-read as configuration (Claude Code reads CLAUDE.md / AGENTS.md
#: from a working dir upward). Privileged EVERYWHERE — a defense-in-depth secondary check that
#: catches a harness file named INTO a content dir (e.g. ``projects/p/workspace/CLAUDE.md``),
#: bounded atop the positive shape so its scope is narrow, not the primary mechanism.
_HARNESS_BASENAMES: frozenset[str] = frozenset(
    {
        "claude.md",
        "claude.local.md",
        "agents.md",
        "agent.md",
    }
)


def _is_content_path(path: object) -> bool:
    """True ONLY for a path POSITIVELY shaped as plain content (deny-by-default, D102-SE6-3).

    The frontier controls this string (UNTRUSTED, D81) and privileged files nest anywhere, so we
    never deny-list forgettable dirs / names (an enumeration leaks) — we ALLOW-list the two
    content shapes and treat everything else as privileged. Content requires ALL of: a ``str``;
    canonical (relative, no ``..`` / dot-segment / null / home / absolute); a content EXTENSION;
    and a location that is EITHER under ``knowledge/`` OR inside a project's bounded deliverable
    subtree (``projects/<name>/{deliverables,drafts,…}/…``). Anything else — code, a harness /
    workflow / policy dir, a project-root file, an unknown place — is privileged (D100 / D73). A
    forgotten content dir fails SAFE (privileged), never open. Canonicalizing first defeats a
    rephrase (``./system/…``, ``knowledge/../projects/p/CLAUDE.md`` normalize before the checks)."""
    if not isinstance(path, str):
        return False
    p = path.strip()
    if not p or p.startswith("/") or p.startswith("~") or "\x00" in p:
        return False
    norm = posixpath.normpath(p.replace("\\", "/"))
    if norm.startswith("..") or norm.startswith("/"):
        return False
    segments = norm.split("/")
    if any(segment.startswith(".") for segment in segments):  # any dotfile / dotdir
        return False
    basename = segments[-1].lower()
    if posixpath.splitext(basename)[1] not in _CONTENT_EXTENSIONS:
        return False
    if basename in _HARNESS_BASENAMES:  # harness steering doc, privileged even in a content dir
        return False
    if norm.startswith(_KNOWLEDGE_ROOT):
        return True  # the knowledge document store is plain content
    if norm.startswith(_PROJECT_ROOT):
        # projects/<name>/<content-dir>/… ONLY; a project-root file or any other subdir is priv.
        return len(segments) >= 4 and segments[2].lower() in _PROJECT_CONTENT_DIRS
    return False


def _is_privileged(target_paths: tuple[str, ...]) -> bool:
    """Whether a returned diff touches the privileged zone — DERIVED by deny-by-default.

    The untrusted frontier controls ``target_paths`` (D81), so privilege is never inferred by
    blocklisting its strings (a rephrase would evade). Instead a diff is privileged UNLESS
    EVERY path provably canonicalizes into a content zone (:func:`_is_content_path`). An empty
    scope, a non-``str`` entry, or any unrecognized / absolute / escaping / code / skills /
    policy path ⇒ privileged (privileged-until-proven-benign, fail-closed — D100 / D73 /
    D102-SE6-3). It classifies (raising a human gesture at most); it never merges on trust."""
    if not target_paths:
        return True
    return not all(_is_content_path(p) for p in target_paths)


@dataclass(frozen=True, slots=True)
class MergeResult:
    """The outcome of a canal-B XL merge (D102) — always flagged untrusted-in-origin.

    Records the distinct re-audit verifier and whether a human validated a privileged merge,
    so the reintegration is auditable; rollback stays available via ``return_point``."""

    verifier: str
    privileged: bool
    return_point: ReturnPoint
    untrusted_origin: bool = True


class CanalBXL:
    """The canal-B XL protocol (D90 / D102): fork (gated) → frontier work → merge (gated).

    Two fail-closed gates carry invariant 19. :meth:`open_copy` refuses to export without a
    confirmed return point, a distinct clean attestation, and a `sensible`-free batch;
    :meth:`merge` treats the return as untrusted, re-audits with a distinct verifier, and
    escalates a privileged merge to a human."""

    __slots__ = ()

    def open_copy(
        self,
        *,
        batch: tuple[GovernanceLabel, ...],
        return_point: ReturnPoint,
        attestation: ExpurgationAttestation,
    ) -> WorkCopy:
        """The SORTIE gate (invariant 19): export an expurgated copy — or refuse fail-closed.

        Refuses unless (i) the ``batch`` is NON-EMPTY (an empty export attests nothing —
        fail-closed); (ii) the return point is CONFIRMED (no rollback ⇒ no copy, D102);
        (iii) the attestation is by a verifier DISTINCT from the producer AND certifies the
        copy clean (D102 / D100-6); (iv) NO label in the batch is `sensible` (D102 / D66) —
        its per-item human gesture stays reserved. The departing ``bubbles`` are DERIVED from
        the batch labels themselves, so the sensitivity gate and the recorded export are the
        SAME source — not a caller-supplied side channel that could be decoupled (D102-SE3)."""
        if not batch:
            raise CanalBXLRefused(
                "empty XL batch — nothing to expurgate or attest; an XL copy exports its "
                "batch, and the empty case proves nothing (fail-closed, D102)"
            )
        if not return_point.confirmed:
            raise CanalBXLRefused(
                "no confirmed return point (commit / snapshot) — no XL copy without a "
                "validated rollback (D102, fail-closed)"
            )
        require_distinct(
            attestation.producer, attestation.verifier, CanalBXLRefused, what="XL expurgation"
        )
        if not attestation.clean:
            raise CanalBXLRefused(
                "expurgation not attested clean by the distinct verifier — at any doubt the "
                "copy does not leave (D102 / D100-4)"
            )
        if any(label.sensitivity >= Sensitivity.SENSIBLE for label in batch):
            raise CanalBXLRefused(
                "a `sensible` datum is in the XL batch — sensible never leaves in an XL copy "
                "(D102 / D66); use the per-item canal-B human gesture"
            )
        return WorkCopy(
            bubbles=frozenset(label.bubble for label in batch),
            return_point=return_point,
            attestation=attestation,
            has_git_history=False,
        )

    def merge(
        self,
        work_copy: WorkCopy,
        diff: ReturnedDiff,
        *,
        verifier: str,
        human_validated: bool = False,
    ) -> MergeResult:
        """The RETOUR gate (D102): reintegrate the frontier's diff — untrusted, paired, re-audited.

        Three fail-closed checks, in order: (1) **appariement** (D102-SE6-1 / D81) — the diff
        must answer THIS worksite's return point, else it is refused (an unpaired or fabricated
        return never merges); (2) **zero-trust re-audit** by a verifier DISTINCT from the
        frontier that produced the diff (D100-6); (3) **privilege DERIVED locally** from the
        diff's target paths — never read off the untrusted return — so a change to code / skills
        / Guard policy needs an explicit human validation (D102-SE6-3 / D75 / D100), and an
        unknown scope is treated as privileged (fail-closed). Rollback stays available via the
        copy's return point. (Content INTEGRITY beyond pairing — a hash of the returned bytes —
        is a ③ concern; the structural appariement is the barrier fixed here.)"""
        if diff.return_ref != work_copy.return_point.ref:
            raise CanalBXLRefused(
                f"returned diff for {diff.return_ref!r} does not match the worksite return "
                f"point {work_copy.return_point.ref!r} — unpaired, refused (D102-SE6-1 / D81)"
            )
        require_distinct(diff.produced_by, verifier, CanalBXLRefused, what="XL return re-audit")
        privileged = _is_privileged(diff.target_paths)
        if privileged and not human_validated:
            raise EscalateToHuman(
                "merging a privileged change (code / skills / Guard policy) from canal B "
                "needs a human validation (D102-SE6-3 / D75) — no automatic privileged merge"
            )
        return MergeResult(
            verifier=verifier,
            privileged=privileged,
            return_point=work_copy.return_point,
            untrusted_origin=True,
        )


@dataclass(frozen=True, slots=True)
class DeclassificationAudit:
    """A DISTINCT verifier's declassification audit (D107 §2 / D100-6).

    Records who audited (verifier ≠ producer) so :meth:`Declassification.declassify` can weave
    the audit step into the provenance chain (source → audit → declassify, D107 §4)."""

    producer: str
    verifier: str
    note: str


class Declassification:
    """Mixed-deliverable declassification (D107) — sensible intrant, public produit.

    A deliverable born in a `perso` bubble is `sensible` by default (fail-safe); a distinct
    verifier audits for residual sensible traces (local by default), then the operator declassifies by
    an explicit gesture into a `public` COPY — the original stays intact (non-destructive).
    Declassifying is the ONE human-gated exception to upward-only labelling (D100-2), and it
    REQUIRES the distinct audit to have run (its evidence is woven into the copy's provenance)."""

    __slots__ = ()

    def audit_declassify(
        self, content: Envelope[str], *, producer: str, verifier: str
    ) -> DeclassificationAudit:
        """Audit a draft for residual sensible traces — by a DISTINCT verifier (D107 / D100-6).

        Local by default (fail-safe): the still-sensible draft does not leave to be audited.
        Returns the attestation :meth:`declassify` requires; a real cleaned version is contenu
        (D98)."""
        require_distinct(producer, verifier, CanalBXLRefused, what="declassification audit")
        return DeclassificationAudit(
            producer=producer,
            verifier=verifier,
            note=f"audited by {verifier} (≠ {producer}) — local (D107)",
        )

    def declassify(
        self, content: Envelope[str], *, audit: DeclassificationAudit, human_validated: bool
    ) -> Envelope[str]:
        """Produce a `public` COPY under an explicit human gesture — original intact (D107).

        Three gates, fail-closed: the ``audit`` must be DISTINCT (producer ≠ verifier, re-checked
        here for defence in depth — D107 §2 / D100-6, symmetric with the canal-B merge); it must
        have run; and ``human_validated`` must be the explicit gesture (D107 §3) — else the
        content stays `sensible` (the audit never auto-authorizes egress, D100 / D74). The
        declassified copy is a FRESH envelope labelled `public`, provenance chained source →
        audit → declassify → timestamp (D107 §4); the original is not mutated (D44 / D56)."""
        require_distinct(
            audit.producer,
            audit.verifier,
            CanalBXLRefused,
            what="declassification (a self-audited attestation cannot declassify, D107 §2)",
        )
        if not human_validated:
            raise EscalateToHuman(
                "declassification is an explicit human gesture (D107 / D66) — the audit "
                "proposes, the operator declassifies; at any doubt it stays sensible (fail-safe)"
            )
        src = content.label
        audit_step = Provenance(
            origin="declassification-audit",
            produced_by=f"audit(verifier={audit.verifier})",
            at=datetime.now(timezone.utc),
            parents=(src.provenance,) if src.provenance is not None else (),
        )
        public_label = GovernanceLabel(
            sensitivity=Sensitivity.PUBLIC,
            bubble=src.bubble,
            domains=src.domains,
            provenance=Provenance(
                origin="declassification",
                produced_by="human-gesture(D107)",
                at=datetime.now(timezone.utc),
                parents=(audit_step,),
            ),
        )
        return Envelope(payload=content.payload, label=public_label)
