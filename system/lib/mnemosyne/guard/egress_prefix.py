"""BR4 -- (host, path-prefix) egress matching, ADDITIVE to the exact-host allow-list.

Real-world case: Eurostat's API has no dedicated host -- it lives on the European Commission's
shared apex (`ec.europa.eu`), under specific paths. `Config.egress_allowed` (``config.py``) matches a host
EXACTLY: the only way to reach Eurostat today is to allow-list the entire apex -- and the repo
had already reversed that exact grant once (see the comment on ``publicreporting.cftc.gov`` in
``system/config/policy.toml``), because "the note says Eurostat, the value grants the whole
Commission." A refusal caused by missing EXPRESSIVENESS is indistinguishable from a refusal that
is actually meant, and that is worse than either.

**THIS MODULE DOES NOT TOUCH `Config.egress_allowed`, AND DOES NOT GRANT ANYTHING.** The
exact-match allow-list keeps deciding exactly as it does today, for every host already declared.
:func:`egress_prefix_allowed` is a SEPARATE, OPT-IN check a caller may consult *after* the
exact-match has already said no -- never a replacement, never wired into the existing path by
this module itself. **The actual (host, prefix) VALUE to grant — e.g. `ec.europa.eu` +
`/eurostat/` — is a `POLICY_WRITE` under `system/config/policy.toml`, a wall only a human crosses
(D74, D102): this module makes the grant EXPRESSIBLE, it does not make it EXIST.**

**Every class of bypass named in the incident is answered by ONE discipline: parse first,
compare SEGMENTS on the RESOLVED path, never a raw string prefix.**

* *Path encoding* -- ``unquote`` runs before any comparison, so ``%2e%2e`` and ``..`` reach
  the normalizer as the same bytes. **Double-encoding is refused explicitly, not by accident**:
  the first sabotage battery run left a single ``unquote`` pass, so ``%252e%252e`` survived as the
  literal segment ``%2e%2e`` — which happened to match nothing and so happened to be refused, but
  by the SHAPE of the input, never by a rule that says so. A second ``unquote`` pass now checks
  whether anything was left to decode; if it was, the whole match refuses outright. *Deny-by-default
  means refusing a path whose final form cannot be guaranteed, not reasoning about what one
  interpretation of it would resolve to.*
* *`..` traversal* -- ``posixpath.normpath`` resolves the path to its true destination BEFORE the
  prefix check runs. ``/eurostat/../secret`` normalizes to ``/secret``, which does not start with
  the ``eurostat`` segment, and is refused. A traversal that cancels itself out
  (``/eurostat/../eurostat/x`` → ``/eurostat/x``) is correctly allowed, because that genuinely IS
  the destination.
* *Query parameters* -- ``urlsplit`` separates ``.query`` from ``.path`` before anything else
  runs; the match never reads the query string, so nothing there can spoof a prefix.
* *Partial prefix* -- comparison is by path SEGMENT (split on ``/``), never by raw string
  prefix: ``/eurostat-fake/`` does not match a ``/eurostat/`` entry, because the segment
  ``eurostat-fake`` is not the segment ``eurostat``. A naive ``str.startswith`` would have missed
  exactly this case (measured directly in the sabotage battery below).
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True, slots=True)
class PrefixEntry:
    """ONE declared authorization (host, path prefix) -- never `Config`'s exact-match.

    ``prefix`` designates a FOLDER, compared by segment: ``/eurostat/`` covers
    ``/eurostat/api/x`` but never ``/eurostat-fake/``. The leading slash is not required when
    writing it (``eurostat/`` and ``/eurostat/`` designate the same folder); it IS required
    internally after normalization, so segment-splitting stays unambiguous."""

    host: str
    prefix: str


def _segments(chemin: str) -> tuple[str, ...]:
    """The path as non-empty segments -- `/a/b/` and `a/b` designate the SAME sequence."""
    return tuple(seg for seg in chemin.split("/") if seg)


def _est_couvert(prefix: str, chemin_normalise: str) -> bool:
    """Does `chemin_normalise` live INSIDE the folder `prefix` designates -- comparison by
    SEGMENT, never by STRING prefix (`str.startswith` would confuse `/eurostat-fake/` and
    `/eurostat/`, measured and refused by the sabotage battery below)."""
    voulus = _segments(prefix)
    portes = _segments(chemin_normalise)
    return len(portes) >= len(voulus) and portes[: len(voulus)] == voulus


def egress_prefix_allowed(entries: tuple[PrefixEntry, ...], url: str) -> bool:
    """Is `url` covered by a declared `(host, prefix)` entry?

    Parses `url` itself -- NEVER trusts a host/path already split by the caller: a naive
    upstream split would itself be the bypass surface the incident points at. Additive: grants
    nothing that `Config.egress_allowed` would not already grant otherwise; the caller stays
    responsible for trying the exact-match FIRST."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = parsed.hostname
    if not host:
        return False
    # Decode BEFORE normalizing: a `%2e%2e` must produce the SAME verdict as a literal `..`,
    # otherwise the encoding becomes the bypass surface this module exists to close.
    chemin = unquote(parsed.path) or "/"
    # SABOTAGE FOUND: a DOUBLE encoding (`%252e%252e`) only decoded ONCE, leaving a weird
    # literal segment (`%2e%2e`) that matched nothing -- so it was ALREADY refused, but by
    # accident of shape, never by a rule that says so. Now explicitly refuses any residual
    # encoding left after the first pass: *deny-by-default* means refusing a path whose final
    # form cannot be guaranteed, never interpreted with confidence.
    if unquote(chemin) != chemin:
        return False
    chemin_normalise = posixpath.normpath(chemin)
    return any(
        entry.host == host and _est_couvert(entry.prefix, chemin_normalise) for entry in entries
    )
