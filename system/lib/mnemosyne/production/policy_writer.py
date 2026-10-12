"""policy_writer (D159) — targeted, format-preserving edits to the protected policy zone.

D102 makes ``system/config/policy.toml`` read-only for every agent (the Guard loads it into a
frozen :class:`~mnemosyne.config.Policy`, D100) — and that incapacity is correct, not the defect.
The defect a project session measured (see the signalement this closes) is that NOTHING could
perform the write on the operator's behalf either: he does not write code, and the file mixes
declarative TOML with long prose comments that document *why* each barrier holds. Hand-editing it
is exactly the kind of "a gesture he cannot perform" that D147 says never happens.

This module is the deterministic TOOL a human gesture drives (:mod:`.policy_requests` records the
gesture; :mod:`~mnemosyne.runtime.policy_run` is the CLI). It is NOT a path for an agent to widen
its own authority: every function here is pure text transformation with no notion of "who is
asking" — the caller (the CLI, gated on a recorded, content-bound approval) is what makes the
write legitimate, exactly as ``make endorse CONFIRM=1`` is legitimate because the operator runs
it, not because the code trusts its own judgement (D100 — structural, not discipline).

**Three shapes, closed set (2026-07-26).** The frozen surface the filing signalement names is
egress hosts, per-bubble domains, and cross-bubble contracts. ``model_routing`` is a fourth
instance of the SAME shape (a table key gains a value) but has zero concrete request today —
adding it speculatively would be lookahead with no known need ([[lookahead-vs-simplicity]]); the
docstring of :func:`apply_items` names it as the obvious next extension so the gap is documented,
not silent.

**Format-preserving by construction, not by luck.** Every transform locates its target with a
bracket-depth-aware, quote-aware scan (never a whole-file reformat, never a dependency on a
TOML-writing library the read path deliberately avoids, D116) and inserts new content adjacent to
the last real entry of its kind — never at the literal next-``[section]`` boundary, which would
land a new line INSIDE the blank-line-plus-comment preamble that visually belongs to the section
that follows (confusing to a human reader, even though TOML itself would not care).

**Fail-closed on the write path.** :func:`apply_to_file` re-parses the result with ``tomllib``
(the same zero-dependency reader the Guard uses, D116) and asserts every value that existed
BEFORE still exists AFTER — a superset check, not just "does it still parse" — before it commits
anything to disk (atomic replace). A bug in the splicing logic that would DROP an existing
egress host, domain, or contract is refused rather than written (invariant 2: the tool may only
ever widen or leave-alone, never silently narrow).

Decisions: D102 / SE4 (protected zone, still read-only for agents) · D147 (a gesture is the
decision, not the keystrokes) · D116 (stdlib-only) · invariant 2 (non-destructive) · invariant 5
(deny-by-default — untouched values are byte-identical, never re-guessed). Code English (D117).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: The three item kinds this writer knows how to apply. Closed set — see the module docstring for
#: why `model_routing` (the fourth named surface) is deliberately absent today.
_KINDS: Final = ("egress", "domains", "contract", "bound")

#: A conservative, injection-safe token: hostnames (`api.stlouisfed.org`) and domain/bubble names
#: (`quant-trading`) alike. Not RFC-exhaustive — that is the EXAMINER's semantic job, not the
#: writer's; this only refuses what would break the TOML or smuggle a control character in.
_TOKEN_RE: Final = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?$")

#: Any line that opens a TOML table — `[section]` or `[[array.of.tables]]` — used to find where a
#: section's body ENDS. Deliberately stricter than a bare `^\[.*$`: this file's own writer never
#: emits a bracket at column 0 that is not a real header, and this regex refuses to treat one as
#: such either (a stray `[` starting a continuation line would not falsely end a section here).
_HEADER_RE: Final = re.compile(r"^\[{1,2}[^\[\]\n]+\]{1,2}[ \t]*(?:#.*)?$", re.MULTILINE)

_BUBBLE_KEY_RE: Final = re.compile(r'^"([^"]+)"[ \t]*=[ \t]*\[', re.MULTILINE)
#: Allows an optional trailing comment (``[[cloisonnement.contracts]]  # note``) — `add_contract`
#: writes exactly that shape when an item carries a ``note`` (D159, post-audit fix: without the
#: ``(?:#[^\n]*)?``, a SECOND contract addition after a noted first one found no header match,
#: fell through to the now-vanished `contracts = []` sentinel, and raised — a self-inflicted
#: verrou mort on the very shape the real request from that project uses).
_CONTRACT_HEADER_RE: Final = re.compile(
    r"^\[\[cloisonnement\.contracts\]\][ \t]*(?:#[^\n]*)?\r?\n", re.MULTILINE
)


class PolicyWriteError(Exception):
    """The file does not have the shape this writer expects — refuse rather than guess.

    Raised BEFORE any write, always: every caller sees this as "nothing happened", never a
    partial edit (the file is read fully, transformed in memory, validated, and only then
    replaced atomically — see :func:`apply_to_file`)."""


@dataclass(frozen=True, slots=True)
class PolicyItem:
    """One atomic widening — the unit :mod:`.policy_requests` bundles into a request and this
    module knows how to apply. Validated at construction (fail fast, never at apply time)."""

    kind: str  # "egress" | "domains" | "contract" | "bound"
    bubble: str = ""  # domains only
    values: tuple[str, ...] = ()  # egress hosts / domain values
    contract_from: str = ""  # contract only
    contract_to: str = ""  # contract only
    bound_name: str = ""  # bound only — the key inside [bounds]
    bound_value: int = 0  # bound only — the NEW ceiling asked for
    note: str = ""  # short human-readable reason, carried into the file as a comment

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise PolicyWriteError(f"unknown item kind {self.kind!r} — expected one of {_KINDS}")
        if any(ord(ch) < 0x20 for ch in self.note):
            # D159, post-audit fix: a bare newline/CR already broke the TOML comment this becomes;
            # a control char generally can too (TOML forbids anything but tab in a comment), and an
            # ESC (0x1B, ANSI) would let a "note" inject terminal escapes into whatever prints it.
            raise PolicyWriteError(
                "a note may not contain a control character — keep it to one plain line of text"
            )
        if self.kind == "egress":
            if self.bubble or self.contract_from or self.contract_to:
                raise PolicyWriteError("an egress item carries only `values`")
            if not self.values:
                raise PolicyWriteError("an egress item needs at least one host")
            for host in self.values:
                _validate_token(host, what="egress host")
        elif self.kind == "domains":
            if self.contract_from or self.contract_to:
                raise PolicyWriteError("a domains item carries only `bubble` and `values`")
            if not self.bubble or not self.values:
                raise PolicyWriteError("a domains item needs a bubble AND at least one value")
            _validate_token(self.bubble, what="bubble")
            for value in self.values:
                _validate_token(value, what="domain value")
        elif self.kind == "bound":
            if self.bubble or self.values or self.contract_from or self.contract_to:
                raise PolicyWriteError("a bound item carries only `bound_name` and `bound_value`")
            if not self.bound_name:
                raise PolicyWriteError("a bound item needs a `bound_name`")
            if self.bound_value <= 0:
                # A bound at zero or below is not a ceiling, it is a shutdown — and this channel
                # WIDENS. Turning something off is a different act, with a different gate.
                raise PolicyWriteError("a bound item needs a POSITIVE `bound_value`")
            _validate_token(self.bound_name, what="bound name")
        elif self.kind == "contract":
            if self.bubble or self.values:
                raise PolicyWriteError("a contract item carries only `contract_from`/`contract_to`")
            if not self.contract_from or not self.contract_to:
                raise PolicyWriteError(
                    "a contract item needs both `contract_from` and `contract_to`"
                )
            _validate_token(self.contract_from, what="contract source bubble")
            _validate_token(self.contract_to, what="contract target bubble")


@dataclass(frozen=True, slots=True)
class Applied:
    """What ACTUALLY changed — the diff a human/agent reviews before and after ``CONFIRM=1``.

    Every field reports only what was NEW (already-present values are silently skipped —
    idempotent re-application), so :attr:`is_noop` is a reliable "nothing to do" signal."""

    egress_added: tuple[str, ...] = ()
    domains_added: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (bubble, new values) pairs
    contracts_added: tuple[tuple[str, str], ...] = ()  # (from, to) pairs
    bounds_raised: tuple[tuple[str, int, int], ...] = ()  # (name, before, after)

    @property
    def is_noop(self) -> bool:
        return (
            not self.egress_added
            and not self.domains_added
            and not self.contracts_added
            and not self.bounds_raised
        )


def _validate_token(value: str, *, what: str) -> str:
    if not _TOKEN_RE.match(value):
        raise PolicyWriteError(f"{what} {value!r} does not look like a safe token — refusing")
    return value


def _toml_str(value: str) -> str:
    """A TOML basic-string literal for `value` (already validated as a safe token, but escape
    defensively regardless — belt AND suspenders on the file the Guard trusts)."""
    if "\n" in value or "\r" in value:
        raise PolicyWriteError(f"value {value!r} contains a newline — refusing to write")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _dedup_preserve_order(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return tuple(out)


# --------------------------------------------------------------------------------------------- #
# Low-level text surgery — bracket-depth-aware, quote-aware, never a whole-file reformat.        #
# --------------------------------------------------------------------------------------------- #
def _matching_bracket(text: str, open_pos: int) -> int:
    """Index of the ``]`` matching the ``[`` at ``open_pos`` (a TOML array), quote- AND
    comment-aware.

    This file's arrays carry trailing French prose comments (e.g. ``# ... d'outils -> ...``) —
    an apostrophe inside a ``#`` comment is NOT a TOML string delimiter, so the scanner must
    stop tracking quotes/brackets for the rest of the line once an UNQUOTED ``#`` is seen, or a
    single stray ``'`` in a comment (as `d'outils` above) puts it in a phantom "inside a string"
    state that swallows the real closing ``]`` and every bracket after it. Raises on a truly
    unterminated array — a malformed file is refused, never guessed at."""
    if text[open_pos] != "[":
        raise PolicyWriteError(f"internal: expected '[' at offset {open_pos}")
    depth = 0
    i = open_pos
    quote: str | None = None
    in_comment = False
    n = len(text)
    while i < n:
        ch = text[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if quote is not None:
            if ch == "\\" and quote == '"':
                i += 2  # skip an escaped character inside a basic string
                continue
            if ch == quote:
                quote = None
        elif ch == "#":
            in_comment = True
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise PolicyWriteError("unterminated array in policy.toml — refusing to guess")


def _section_span(text: str, header: str) -> tuple[int, int]:
    """(body_start, body_end) for the EXACT bare table ``[header]`` — from right after its header
    line to the next top-level header (single OR double bracket) at column 0, or EOF."""
    pattern = re.compile(rf"^\[{re.escape(header)}\][ \t]*(?:#.*)?\r?\n", re.MULTILINE)
    m = pattern.search(text)
    if m is None:
        raise PolicyWriteError(f"section [{header}] not found in policy.toml")
    body_start = m.end()
    nxt = _HEADER_RE.search(text, body_start)
    body_end = nxt.start() if nxt else len(text)
    return body_start, body_end


def _find_array(
    text: str, key: str, start: int, end: int, *, required: bool = True
) -> tuple[int, int] | None:
    """Locate ``key = [ ... ]`` within ``text[start:end]``; return ``(open_pos, close_pos)`` —
    ``close_pos`` points AT the matching ``]``. ``key`` is matched LITERALLY (pass ``'"saas"'``
    with its quotes for a domains bubble key). ``required=False`` returns ``None`` instead of
    raising when the key is absent — the domains path uses this to detect "bubble not yet
    declared" as an expected case rather than a file-shape error."""
    pattern = re.compile(rf"^[ \t]*{re.escape(key)}[ \t]*=[ \t]*\[", re.MULTILINE)
    m = pattern.search(text, start, end)
    if m is None:
        if required:
            raise PolicyWriteError(f"key {key!r} not found as an array in the expected section")
        return None
    open_pos = m.end() - 1
    close_pos = _matching_bracket(text, open_pos)
    return open_pos, close_pos


def _strip_line_comments(text: str) -> str:
    """Blank out every ``# ... end-of-line`` comment, quote-aware — used ONLY to decide whether
    an array's last REAL token is a comma (never to determine bracket depth; that stays in
    :func:`_matching_bracket`, which needs the untouched original text)."""
    out: list[str] = []
    quote: str | None = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if quote is not None:
            out.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            nl = text.find("\n", i)
            if nl == -1:
                break
            out.append("\n")
            i = nl + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _splice_array_items(
    text: str, open_pos: int, close_pos: int, new_items: tuple[str, ...]
) -> str:
    """Insert ready-to-write TOML scalars (each already quoted, e.g. ``'"host"'``) into the array
    spanning ``[open_pos, close_pos]`` (``close_pos`` = index of ``]``), right before the closing
    bracket. Handles the empty-array case (no leading comma) and a pre-existing trailing comma
    (no DOUBLE comma) — the only two shapes that would otherwise produce invalid TOML.

    Comment-aware (D159, post-audit fix): the REAL ``policy.toml`` ends its last domain entry
    with a trailing prose comment on the same line as the final comma (``"runtime",  # veille
    d'outils -> ...``). Checking ``inner.rstrip()`` for a trailing comma missed this — the text
    right before ``close_pos`` is comment prose, not the comma — so it took the "no trailing
    comma" branch and inserted a SECOND, empty-slot comma, producing invalid TOML the very first
    time this ran against the real file. Comments are blanked out (:func:`_strip_line_comments`)
    before the check, so a comment after the last value no longer hides its comma."""
    inner = text[open_pos + 1 : close_pos]
    inner_no_comments = _strip_line_comments(inner).rstrip()
    if inner_no_comments.strip() == "":
        lead = "\n  "
    elif inner_no_comments.endswith(","):
        lead = "\n  "
    else:
        lead = ",\n  "
    body = lead + ",\n  ".join(new_items) + "\n"
    return text[:close_pos] + body + text[close_pos:]


def _parse_string_array(array_literal: str) -> tuple[str, ...]:
    """Parse a TOML array literal (e.g. ``'["a", "b"]'``) via ``tomllib`` — reuse the same
    zero-dependency reader the Guard trusts rather than hand-rolling string-array parsing."""
    parsed = tomllib.loads(f"x = {array_literal}")
    return tuple(parsed["x"])


# --------------------------------------------------------------------------------------------- #
# Per-kind appliers.                                                                             #
# --------------------------------------------------------------------------------------------- #
def add_egress_hosts(
    text: str, hosts: tuple[str, ...], *, comment: str = ""
) -> tuple[str, tuple[str, ...]]:
    """Append hosts not already on ``[egress] allowlist`` (SE5, invariant 21). Idempotent: a host
    already present is silently skipped. ``comment`` (if given) is attached to the LAST newly
    added line, mirroring this file's own convention of a dated, gesture-referencing comment."""
    body_start, body_end = _section_span(text, "egress")
    span = _find_array(text, "allowlist", body_start, body_end)
    assert span is not None  # required=True default — mypy/readability, never actually None here
    open_pos, close_pos = span
    existing = _parse_string_array(text[open_pos : close_pos + 1])
    to_add = tuple(h for h in _dedup_preserve_order(hosts) if h not in existing)
    if not to_add:
        return text, ()
    items = [_toml_str(h) for h in to_add]
    if comment:
        items[-1] = f"{items[-1]}  # {comment}"
    return _splice_array_items(text, open_pos, close_pos, tuple(items)), to_add


def _fin_de_la_derniere_borne(text: str, body_start: int, body_end: int) -> int:
    """Offset right after the LAST ``key = value`` line of the section — the point where a NEW
 bound belongs.

 **WITHOUT IT, A NEWLY-CREATED KEY LANDS IN THE PREAMBLE OF THE NEXT SECTION.** Measured
 on 2026-09-08 against the real file: `proposer_fanout` was written **under the
 ``# --- Cost / quota ceilings (D86) ---`` banner and stuck to ``[quotas]``**. TOML parses it
 fine inside ``[bounds]`` — so **no gate turns red** — but a human reader takes it for a cost
 ceiling. *A file the machine reads correctly and the human reads wrong is worse than an
 error: it does not announce itself.*

 Its two neighbours (`domains`, `contract`) already carried this guard; the `bound` path
 was the only one missing it — and its sole witness used a fixture whose following section
 had **no preamble**, so it passed either way. *A degenerate fixture does not test the
 property it claims to hold.*

 Falls back to ``body_start`` when the section is empty."""
    # `_BOUND_LINE` is ANCHORED and reads a STRIPPED line (that is how `raise_bound` uses
    # it): a `finditer` over the whole text matches NOTHING and silently returns `body_start`.
    # Measured: this guard's witness bit on this exact mistake on the first try.
    fin = body_start
    curseur = body_start
    for ligne in text[body_start:body_end].splitlines(keepends=True):
        if _BOUND_LINE.match(ligne.strip()):
            fin = curseur + len(ligne)
        curseur += len(ligne)
    return fin


def _last_bubble_entry_end(text: str, body_start: int, body_end: int) -> int:
    """Offset right after the LAST ``"bubble" = [...]`` entry's own closing line — the point
    where a NEW bubble line belongs, so it lands adjacent to real content and never inside the
    blank-line-plus-comment preamble that visually belongs to the NEXT section. Falls back to
    ``body_start`` (first entry in an empty section) when no bubble is declared yet."""
    matches = list(_BUBBLE_KEY_RE.finditer(text, body_start, body_end))
    if not matches:
        return body_start
    last = matches[-1]
    open_pos = last.end() - 1
    close_pos = _matching_bracket(text, open_pos)
    line_end = text.find("\n", close_pos)
    return line_end + 1 if line_end != -1 else body_end


def add_domain_values(
    text: str, bubble: str, values: tuple[str, ...], *, comment: str = ""
) -> tuple[str, tuple[str, ...]]:
    """Declare ``bubble`` in ``[domains]`` if absent, or union new values into its existing list
    (D72, invariant 4). Idempotent: a value already declared for this bubble is skipped."""
    body_start, body_end = _section_span(text, "domains")
    key = f'"{bubble}"'
    span = _find_array(text, key, body_start, body_end, required=False)
    to_add = tuple(v for v in _dedup_preserve_order(values))
    if span is None:
        if not to_add:
            return text, ()
        insert_at = _last_bubble_entry_end(text, body_start, body_end)
        line_items = ", ".join(_toml_str(v) for v in to_add)
        line = f"{key} = [{line_items}]"
        if comment:
            line = f"{line}  # {comment}"
        return text[:insert_at] + line + "\n" + text[insert_at:], to_add
    open_pos, close_pos = span
    existing = _parse_string_array(text[open_pos : close_pos + 1])
    to_add = tuple(v for v in to_add if v not in existing)
    if not to_add:
        return text, ()
    items = [_toml_str(v) for v in to_add]
    if comment:
        items[-1] = f"{items[-1]}  # {comment}"
    return _splice_array_items(text, open_pos, close_pos, tuple(items)), to_add


def _existing_contracts(text: str) -> frozenset[tuple[str, str]]:
    """Every ``{from, to}`` pair currently in the file — read via ``tomllib`` on the WHOLE
    document (simpler and more robust than text-scanning for a pure existence check)."""
    parsed = tomllib.loads(text)
    contracts = parsed.get("cloisonnement", {}).get("contracts", [])
    return frozenset((c["from"], c["to"]) for c in contracts)


def add_contract(text: str, source: str, target: str, *, comment: str = "") -> tuple[str, bool]:
    """Append a ``{from=source, to=target}`` contract (D54/D72, invariant 3). Idempotent: this
    exact pair already present ⇒ no-op. First contract EVER replaces the empty ``contracts = []``
    sentinel in place; a later one is appended right after the LAST existing block."""
    if (source, target) in _existing_contracts(text):
        return text, False
    header_comment = f"  # {comment}" if comment else ""
    block = f'[[cloisonnement.contracts]]{header_comment}\nfrom = "{source}"\nto   = "{target}"\n'
    matches = list(_CONTRACT_HEADER_RE.finditer(text))
    if matches:
        last = matches[-1]
        # our own writer's fixed 2-line shape (`from = ...` / `to = ...`) right after the header —
        # advance past exactly those two lines, never to the next SECTION (which would skip past
        # the blank-line-plus-comment preamble belonging to whatever follows, D159).
        pos = last.end()
        for _ in range(2):
            nl = text.find("\n", pos)
            pos = nl + 1 if nl != -1 else len(text)
        return text[:pos] + block + text[pos:], True
    body_start, body_end = _section_span(text, "cloisonnement")
    span = _find_array(text, "contracts", body_start, body_end, required=False)
    if span is None:
        raise PolicyWriteError(
            "no `contracts = []` sentinel under [cloisonnement] and no existing "
            "[[cloisonnement.contracts]] block — refusing to guess where to write"
        )
    open_pos, close_pos = span
    line_start = text.rfind("\n", 0, open_pos) + 1
    line_end_pos = text.find("\n", close_pos)
    line_end = line_end_pos + 1 if line_end_pos != -1 else len(text)
    return text[:line_start] + block + text[line_end:], True


# --------------------------------------------------------------------------------------------- #
# Top-level orchestration + the fail-closed, atomic file write.                                 #
# --------------------------------------------------------------------------------------------- #

_BOUND_LINE = re.compile(r"^(?P<cle>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<valeur>\d+)(?P<reste>.*)$")


def raise_bound(text: str, name: str, value: int, *, comment: str = "") -> tuple[str, int | None]:
    """Raise (or create) ONE ceiling inside ``[bounds]``.

 Returns ``(text, previous)`` where ``previous`` is ``None`` if NOTHING changed (idempotent),
 ``0`` if the bound was just CREATED, and the previous ceiling if it was raised. Three
 distinct cases, three distinct values: a ``None`` that meant both "did nothing" and
 "created" would make the report wrong in one case out of two — *two absences of measurement
 compare equal*.

 THIS CHANNEL ONLY KNOWS HOW TO WIDEN, AND THAT IS AN INCAPACITY, NOT A POLICY. A request
 that would LOWER an existing bound is REFUSED: *turning a decorative ceiling into a real
 constraint is a change of nature, not a fix* — this repo paid for that once, by turning a
 decorative ceiling into an active refusal on the operator's own work. Tightening a bound
 remains possible, but through a separate gesture, in front of the operator's eyes — never by
 slipping into a batch of widenings approved with one word. An identical value is an
 idempotent no-op, as everywhere else here.

 The bound may not EXIST yet: `core_api` already states, in black and white, two pending
 additions (`refine_max_rounds`, `proposer_fanout`, *« when the config zone is next opened »*).
 It is therefore created at the end of the section, never elsewhere — the request's comment
 follows it.
 """
    body_start, body_end = _section_span(text, "bounds")
    corps = text[body_start:body_end]
    lignes = corps.splitlines(keepends=True)
    for i, ligne in enumerate(lignes):
        trouve = _BOUND_LINE.match(ligne.strip())
        if not trouve or trouve.group("cle") != name:
            continue
        ancienne = int(trouve.group("valeur"))
        if value == ancienne:
            return text, None
        if value < ancienne:
            raise PolicyWriteError(
                f"bound {name!r}: {ancienne} -> {value} TIGHTENS the bound. This channel widens, "
                f"it does not narrow — tightening happens through a separate gesture, not inside "
                f"a batch approved with one word."
            )
        indent = ligne[: len(ligne) - len(ligne.lstrip())]
        suffixe = trouve.group("reste").rstrip()
        lignes[i] = f"{indent}{name} = {value}{('  ' + suffixe) if suffixe.strip() else ''}\n"
        return text[:body_start] + "".join(lignes) + text[body_end:], ancienne

    # We insert AFTER the last real bound, never at the end of the body: the end of the body
    # includes the preamble (blank line + comment banner) that visually belongs to the NEXT
    # section. Same guard as `add_domain_values` and `add_contract`.
    ajout = f"{name} = {value}" + (f"  # {comment}" if comment else "")
    insert_at = _fin_de_la_derniere_borne(text, body_start, body_end)
    return text[:insert_at] + f"{ajout}\n" + text[insert_at:], 0


def apply_items(text: str, items: tuple[PolicyItem, ...]) -> tuple[str, Applied]:
    """Apply every item in order; pure (no I/O), so the suite can test it without a filesystem.

    Four kinds today (egress / domains / contract / bound) — ``model_routing`` is the same shape
    (a table gains a key) but has no concrete request yet (module docstring)."""
    egress_added: list[str] = []
    domains_added: list[tuple[str, tuple[str, ...]]] = []
    contracts_added: list[tuple[str, str]] = []
    bounds_raised: list[tuple[str, int, int]] = []
    for item in items:
        if item.kind == "egress":
            text, added = add_egress_hosts(text, item.values, comment=item.note)
            if added:
                egress_added.extend(added)
        elif item.kind == "domains":
            text, added = add_domain_values(text, item.bubble, item.values, comment=item.note)
            if added:
                domains_added.append((item.bubble, added))
        elif item.kind == "contract":
            text, was_added = add_contract(
                text, item.contract_from, item.contract_to, comment=item.note
            )
            if was_added:
                contracts_added.append((item.contract_from, item.contract_to))
        elif item.kind == "bound":
            text, ancienne = raise_bound(text, item.bound_name, item.bound_value, comment=item.note)
            if ancienne is not None:
                bounds_raised.append((item.bound_name, ancienne, item.bound_value))
        else:  # pragma: no cover - PolicyItem.__post_init__ already refuses this
            raise PolicyWriteError(f"unknown item kind {item.kind!r}")
    applied = Applied(
        tuple(egress_added), tuple(domains_added), tuple(contracts_added), tuple(bounds_raised)
    )
    return text, applied


def _assert_no_regression(before: str, after: str) -> None:
    """The safety net: every value present BEFORE must still be present AFTER — a superset check,
    not merely "does it still parse". Raises :class:`PolicyWriteError` (never writes) if a bug in
    the splicing logic would have dropped an existing host / domain value / contract."""
    before_parsed = tomllib.loads(before)
    after_parsed = tomllib.loads(after)

    before_egress = set(before_parsed.get("egress", {}).get("allowlist", []))
    after_egress = set(after_parsed.get("egress", {}).get("allowlist", []))
    if not before_egress <= after_egress:
        raise PolicyWriteError("egress allowlist would LOSE an existing host — refusing to write")

    before_domains = before_parsed.get("domains", {})
    after_domains = after_parsed.get("domains", {})
    for bubble, values in before_domains.items():
        if not set(values) <= set(after_domains.get(bubble, [])):
            raise PolicyWriteError(
                f"domains[{bubble!r}] would LOSE an existing value — refusing to write"
            )

    before_contracts = {
        (c["from"], c["to"]) for c in before_parsed.get("cloisonnement", {}).get("contracts", [])
    }
    after_contracts = {
        (c["from"], c["to"]) for c in after_parsed.get("cloisonnement", {}).get("contracts", [])
    }
    if not before_contracts <= after_contracts:
        raise PolicyWriteError("a cloisonnement contract would be LOST — refusing to write")


def _verify_write_landed(path: Path, applied: Applied) -> None:
    """Re-read ``path`` right after writing it and confirm every value :func:`apply_to_file`
    claims to have added is actually there (D159, fixed after a real signalement: a project
    session measured this exact machinery's ``policy.toml`` widened, then narrowed back to
    nothing four minutes later, while the request ledger kept saying ``applied`` — the write had
    genuinely landed, and something else touched the file afterward with no trace of it).

    "Applied" in the ledger must mean something AT THE MOMENT it is recorded, not merely "we
    asked the filesystem to write this once and hoped." This catches a silent write failure, a
    filesystem quirk, or another process racing this exact write — it cannot catch a race that
    happens AFTER this check returns (no lock is taken; that would be a bigger, separate
    undertaking), but it turns the common case of "the write simply didn't stick" from a silent
    lie into a raised, un-recordable refusal: :meth:`~mnemosyne.production.policy_requests.
    PolicyRequestLedger.record_application` is only ever reached by a caller if this returns
    cleanly."""
    reread = tomllib.loads(path.read_text(encoding="utf-8"))
    actual_egress = set(reread.get("egress", {}).get("allowlist", []))
    missing_egress = set(applied.egress_added) - actual_egress
    if missing_egress:
        raise PolicyWriteError(
            f"wrote {path} but a fresh re-read does not show {sorted(missing_egress)} in "
            "egress.allowlist — refusing to let the caller record 'applied' for a write that "
            "may not have landed"
        )
    actual_domains = reread.get("domains", {})
    for bubble, values in applied.domains_added:
        missing_values = set(values) - set(actual_domains.get(bubble, []))
        if missing_values:
            raise PolicyWriteError(
                f"wrote {path} but a fresh re-read does not show {sorted(missing_values)} in "
                f"domains[{bubble!r}] — refusing to let the caller record 'applied'"
            )
    actual_contracts = {
        (c["from"], c["to"]) for c in reread.get("cloisonnement", {}).get("contracts", [])
    }
    for source, target in applied.contracts_added:
        if (source, target) not in actual_contracts:
            raise PolicyWriteError(
                f"wrote {path} but a fresh re-read does not show the contract {source!r} -> "
                f"{target!r} — refusing to let the caller record 'applied'"
            )


def apply_to_file(path: Path, items: tuple[PolicyItem, ...]) -> Applied:
    """Read, transform, validate, and atomically replace ``path`` — or raise and touch nothing.

    Fail-closed end to end: the original must already parse (a pre-existing corruption is not
    this tool's job to fix), the transformed text must still parse AND be a strict superset of
    the original (:func:`_assert_no_regression`), only then is it written — to a sibling ``.tmp``
    file first, then ``os.replace``d over the target (atomic on POSIX, so a crash mid-write never
    leaves a half-written policy file, invariant 2) — and, once written, a fresh re-read confirms
    it actually landed (:func:`_verify_write_landed`) before the caller may treat this as done."""
    original = path.read_text(encoding="utf-8")
    try:
        tomllib.loads(original)  # sanity: refuse to touch an already-broken file
    except tomllib.TOMLDecodeError as exc:
        raise PolicyWriteError(
            f"{path} is not valid TOML already — refusing to touch it: {exc}"
        ) from exc
    new_text, applied = apply_items(original, items)
    if applied.is_noop:
        return applied
    try:
        tomllib.loads(new_text)  # round-trip: the result must still be valid TOML
    except tomllib.TOMLDecodeError as exc:
        # a bug in a splicer produced invalid TOML — surface it as OUR error (never a raw
        # traceback to the CLI, D159 post-audit fix) and touch nothing on disk either way.
        raise PolicyWriteError(
            f"the transformed text is not valid TOML — refusing to write: {exc}"
        ) from exc
    _assert_no_regression(original, new_text)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    tmp.replace(path)  # atomic on POSIX — no reader ever observes a half-written file
    _verify_write_landed(path, applied)
    return applied
