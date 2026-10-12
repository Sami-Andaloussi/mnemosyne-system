"""SpendLedger (D155 / D86) — the two ceilings that were written down and never read.

``policy.toml`` has carried this since the beginning::

 # The spend counter cuts when a ceiling is hit, feeding the same circuit-breakers…
 [quotas]
 daily_cost_ceiling_eur = 5.0
 frontier_token_ceiling = 200000

Both are LOADED into :class:`~mnemosyne.config.Policy` and **neither is read by any code** (grepped,
2026-07-20). The comment describes a spend counter that does not exist, which is worse than having
no ceiling at all: it reads like a guarantee. This module is that counter, ported in design from
``hermes-agent``'s ``agent/usage_pricing.py`` (MIT © 2025 Nous Research) — specifically its two good
ideas, which are not the arithmetic:

* **Four token classes, not two.** ``input`` / ``output`` / **``cache_read``** / **``cache_write``**.
 Cached reads are an order of magnitude cheaper than fresh input and cache writes cost *more*, so a
 counter that lumps them together is wrong by a large factor — measured on a cache-heavy call:
 folding cache reads into ``input`` **over**-states by ×6, and simply not counting them (the old
 two-way tally) **under**-states by ×0.12. It is the omission that flatters; an earlier draft of
 this docstring named the wrong direction and the audit caught it. Nothing in this repo counted
 them at all (grepped: no ``cache_read`` anywhere).
* **A cost STATUS carried next to the cost.** A number with no provenance invites trust it has not
 earned. Every charge says whether its euro figure is measured, computed, free, or unknown — see
 :class:`CostStatus`.

**What this counts, stated plainly so it is never over-read.** It counts what MNEMOSYNE'S OWN CODE
spends through :class:`~mnemosyne.runtime.runner_anthropic.AnthropicBackend` — the distillation
campaigns, the caption passes, a sibling project production run. It does **not** count the Claude Code session
you are reading this in: that runs on the operator's subscription, outside this process, and no API
here can see it. So "€0.00 today" means "Mnemosyne's code has not spent", never "nothing was spent".

**Two ceilings, because one of them cannot be trusted alone.** Euros bound what we can PRICE; tokens
bound EVERYTHING. A model missing from the price table yields :attr:`CostStatus.UNKNOWN` — its tokens
are still counted, so ``frontier_token_ceiling`` still stops it, but it does not block work by being
unpriceable. That asymmetry is deliberate: a missing price is a bookkeeping gap and must not halt
production, while real overspend must. Both refusals raise the existing
:class:`~mnemosyne.guard.bounds.ResourceBoundError` — the same fail-closed shape as every other bound
(invariant 16 / D78), never a new kind of stop for callers to learn.

** The two configured ceilings are NOT on comparable scales, and the audit measured it.** Under
``frontier_token_ceiling = 200000``, the most expensive composition available (200 k tokens of pure
Opus output) reaches **4.60 €** — strictly below ``daily_cost_ceiling_eur = 5.0``. So today the
**token** ceiling always fires first and the euro ceiling can never trigger at all. Both numbers are
the operator's policy and this module does not silently rewrite either; instead :func:`binding_ceiling`
computes which one actually binds and :func:`render_spend` says so out loud, so "0.92 € out of a
5.00 € ceiling" can never be read as "18% of the budget" when it is in fact 100% of the bound.

**Concurrency, bounded and stated.** :meth:`SpendLedger.check_ceilings` reads, then the call spends,
then :meth:`record` writes. With ``W`` workers in flight (the distillation campaign defaults to 6)
every worker can pass the check before any of them writes, so the overshoot is bounded by
``(W-1) × cost_of_one_call`` — **measured at +1.44 € over a 5 € ceiling with 6 Opus workers**. No lock
fixes this: the window is between the check and the *result*, not between two file operations. It is
named here rather than papered over, and the token ceiling carries the same property.

**Why the prices live in code and are never called ACTUAL.** They are a dated vendor fact, not a
policy the operator sets, and ``policy.toml`` is protected (SE4). More importantly, no API here
returns a price — so a figure computed from :data:`_PRICE_PER_MTOK_USD` is an ESTIMATE and says so,
forever. ``ACTUAL`` exists in :class:`CostStatus` and is deliberately never produced today; the day a
provider returns a real cost, that is the value it gets, and every old line stays honest about being
an estimate. Same for the euro conversion: :data:`_USD_TO_EUR` is a dated constant, which is one more
reason nothing here is ``ACTUAL``.

Decisions: D155 (this) · D86 (cost / quota ceilings) · D78 / invariant 16 (a bound is active when a
breach raises) · D82 (a durable local journal under ``system/state``, gitignored) · D117.
Pure stdlib — no brick (D126).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Final

from ..guard.bounds import ResourceBoundError

#: Repo root from here (``system/lib/mnemosyne/production/spend.py`` → parents[4]).
_REPO_ROOT: Final = Path(__file__).resolve().parents[4]

#: The append-only spend journal. Under ``system/state`` ⇒ gitignored (D82), per-machine.
DEFAULT_SPEND_PATH: Final = _REPO_ROOT / "system" / "state" / "spend.jsonl"

#: USD per million tokens, per model, as ``(input, output, cache_read, cache_write)``.
#:
#: **A dated snapshot (2026-07-20) written from knowledge, not fetched.** That is exactly why nothing
#: priced from it is ever reported as ``ACTUAL``. A model absent here is not guessed at — it becomes
#: ``UNKNOWN`` and leans on the token ceiling instead. Add a row when a new model is wired, and move
#: the whole table to config the day it outgrows this file.
#: OpenAI (GPT-5.6, Responses API) rows added 2026-08-21 — fetched TWICE against
#: developers.openai.com/api/docs/pricing (standard tier) after a first pass against a different
#: page + aggregator corroboration gave a WRONG ``gpt-5.6-sol`` figure ($5.00/$30.00) that this
#: table briefly carried; the pricing page itself, fetched twice independently and consistent both
#: times, is the one trusted here. Still ``ESTIMATED`` at :func:`price`, never ``ACTUAL``. No
#: cache-WRITE column: OpenAI has no such charge, caching is automatic and only cache READS are
#: discounted (~90 % off the input rate for all three tiers).
_PRICE_PER_MTOK_USD: Final[dict[str, tuple[float, float, float, float]]] = {
    "claude-haiku-4-5": (1.00, 5.00, 0.10, 1.25),
    "claude-sonnet-5": (3.00, 15.00, 0.30, 3.75),
    "claude-opus-4-8": (5.00, 25.00, 0.50, 6.25),
    "gpt-5.6-sol": (4.00, 20.00, 0.40, 0.0),
    "gpt-5.6-terra": (2.00, 12.00, 0.20, 0.0),
    "gpt-5.6-luna": (0.20, 1.20, 0.02, 0.0),
    # The operator's actual 3-rung ladder (2026-08-21, verbatim in the runner's _DEFAULT_MODEL comment):
    # start at gpt-5-nano, escalate to gpt-5.6-luna, then gpt-5-mini if quality still isn't enough.
    "gpt-5-nano": (0.05, 0.40, 0.005, 0.0),
    "gpt-5-mini": (0.25, 2.00, 0.025, 0.0),
}

#: Dated FX constant (2026-07-20). One more reason a computed cost is an ESTIMATE, never an ACTUAL.
_USD_TO_EUR: Final = 0.92

#: Vendor decorations that do not change the price: a pinned release date (``…-20251001``) and a
#: cloud-marketplace prefix (``anthropic.…`` on Bedrock). Stripped before the table lookup.
#:
#: Without this the DEFAULT model's own full identifier — ``claude-haiku-4-5-20251001``, the one the
#: docs publish and a ``--model`` flag would paste — priced at **0.00 € for ever**, silently, leaving
#: the euro ceiling permanently blind. A price table keyed on a decorated string is a table that
#: works only for the exact spelling its author happened to type.
_MODEL_DECORATION_RE: Final = re.compile(r"^(?:[a-z]+\.)?(.*?)(?:-\d{8})?(?:-v\d+:\d+)?$")

#: Token classes, in the order they appear in a price row.
_CLASSES: Final = ("input", "output", "cache_read", "cache_write")


class CostStatus(str, Enum):
    """How much a euro figure is worth — carried next to every charge.

    ``ACTUAL`` is reserved for a price a provider itself returned. Nothing produces it today, and
    that is the point: the enum records the difference so a future real price is distinguishable
    from every estimate already on disk.
    """

    ACTUAL = "actual"
    ESTIMATED = "estimated"
    INCLUDED = "included"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CanonicalUsage:
    """One call's token counts, split four ways.

    ``cache_read`` and ``cache_write`` are separate because they are priced differently — roughly a
    tenth and roughly a quarter more than fresh input. Folding them into ``input`` is the standard
    way a token counter quietly misreports a long, cache-heavy run.
    """

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    @property
    def total(self) -> int:
        """Every token that crossed the wire — the figure the token ceiling bounds."""
        return self.input + self.output + self.cache_read + self.cache_write

    def __add__(self, other: CanonicalUsage) -> CanonicalUsage:
        return CanonicalUsage(
            input=self.input + other.input,
            output=self.output + other.output,
            cache_read=self.cache_read + other.cache_read,
            cache_write=self.cache_write + other.cache_write,
        )

    @classmethod
    def from_anthropic(cls, usage: object) -> CanonicalUsage:
        """Read the four counts off an Anthropic usage object, tolerating every absent field.

        A provider that stops sending a field must degrade to zero for THAT field, never explode and
        never lose the others — the ledger's whole value is that it keeps counting.
        """

        def field(*names: str) -> int:
            for name in names:
                value = getattr(usage, name, None)
                if value is not None:
                    try:
                        return int(value)
                    except (TypeError, ValueError):
                        return 0
            return 0

        return cls(
            input=field("input_tokens"),
            output=field("output_tokens"),
            cache_read=field("cache_read_input_tokens", "cache_read_tokens"),
            cache_write=field("cache_creation_input_tokens", "cache_write_tokens"),
        )

    @classmethod
    def from_openai(cls, usage: object) -> CanonicalUsage:
        """Read the four counts off a Responses API usage object, same tolerant-degrade contract as
        :meth:`from_anthropic`. OpenAI has no separate cache-WRITE charge (caching is automatic, only
        cache READS are priced differently) — ``cache_write`` stays 0 for this provider, always, not
        as a missing-field degradation but because the class of charge does not exist here.
        ``input_tokens_details.cached_tokens`` is nested one level deeper than the flat Anthropic
        shape; absent at either level degrades to 0 like every other field."""

        def field(*names: str) -> int:
            for name in names:
                value = getattr(usage, name, None)
                if value is not None:
                    try:
                        return int(value)
                    except (TypeError, ValueError):
                        return 0
            return 0

        details = getattr(usage, "input_tokens_details", None)
        cached = getattr(details, "cached_tokens", None) if details is not None else None
        return cls(
            input=field("input_tokens"),
            output=field("output_tokens"),
            cache_read=int(cached) if isinstance(cached, (int, float)) else 0,
            cache_write=0,
        )


@dataclass(frozen=True, slots=True)
class Charge:
    """One priced call: what ran it, what it used, what it cost, and how sure we are."""

    model: str
    usage: CanonicalUsage
    cost_eur: float
    status: CostStatus
    at: str
    kind: str = "model_call"
    #: False when the append failed. Kept APART from ``status`` (which is about where the PRICE comes
    #: from): conflating "we could not price this" with "we could not write this down" is exactly the
    #: kind of blur an API whose selling point is provenance must not have.
    persisted: bool = True


def price(model: str, usage: CanonicalUsage) -> tuple[float, CostStatus]:
    """Euros for one call, and the confidence in that figure.

    A model absent from :data:`_PRICE_PER_MTOK_USD` returns ``(0.0, UNKNOWN)`` — deliberately NOT a
    guessed rate, and deliberately not an error. Its tokens still count toward the token ceiling, so
    an unpriced model is bounded; it is only unpriced, not unwatched.
    """
    rates = _PRICE_PER_MTOK_USD.get(model) or _PRICE_PER_MTOK_USD.get(normalise_model(model))
    if rates is None:
        return 0.0, CostStatus.UNKNOWN
    counts = (usage.input, usage.output, usage.cache_read, usage.cache_write)
    usd = sum(count * rate for count, rate in zip(counts, rates, strict=True)) / 1_000_000
    return round(usd * _USD_TO_EUR, 6), CostStatus.ESTIMATED


def normalise_model(model: str) -> str:
    """Strip the decorations that do not change a model's price (release date, cloud prefix)."""
    match = _MODEL_DECORATION_RE.match(model.strip().lower())
    return match.group(1) if match else model


def policy_ceilings() -> tuple[float, int]:
    """The two configured ceilings, read from the protected policy (SE4) rather than hard-coded.

    ONE home, because both the enforcement point (the Anthropic backend) and the report (``make
    depense``) need them and a second copy would drift. Every failure — policy absent, unparseable,
    a ceiling written as prose — degrades to ``(0.0, 0)`` = "not configured", which never blocks: a
    broken config must not become an accidental kill switch on the paid path.
    """
    try:
        from ..config import load_policy

        quotas = load_policy().quotas
        return float(quotas.get("daily_cost_ceiling_eur", 0.0)), int(
            quotas.get("frontier_token_ceiling", 0)
        )
    except Exception:  # noqa: BLE001 - a readable, non-blocking degradation beats a raised config
        return 0.0, 0


def binding_ceiling(cost_ceiling_eur: float, token_ceiling: int) -> tuple[str, float]:
    """Which ceiling actually stops a run first, and the euro figure at which it does.

    The audit measured what neither number says on its own: with ``frontier_token_ceiling = 200000``
    the priciest composition available (200 k tokens of pure Opus output) reaches **4.60 €**, under
    ``daily_cost_ceiling_eur = 5.0``. So the euro ceiling can never fire, and a report saying "0.92 €
    out of a 5.00 € ceiling" invites reading 18% where the truth is 100%. Returns ``("tokens"``
    or ``"euros"``, the euros at which the binding one trips) so the report can say which is real.
    """
    if token_ceiling <= 0:
        return ("euros", cost_ceiling_eur) if cost_ceiling_eur > 0 else ("none", 0.0)
    dearest = max(
        (price(model, CanonicalUsage(output=token_ceiling))[0] for model in _PRICE_PER_MTOK_USD),
        default=0.0,
    )
    if cost_ceiling_eur <= 0 or dearest < cost_ceiling_eur:
        return "tokens", round(dearest, 2)
    return "euros", cost_ceiling_eur


@dataclass(frozen=True, slots=True)
class DaySpend:
    """What one day cost, and how much of it is actually known."""

    day: str
    cost_eur: float
    usage: CanonicalUsage
    calls: int
    unpriced_calls: int

    @property
    def is_complete(self) -> bool:
        """False when at least one call could not be priced — the total is then a LOWER bound."""
        return self.unpriced_calls == 0


class SpendLedger:
    """Durable, append-only record of what Mnemosyne's own code spent.

    Pure I/O over one JSONL file (no brick, D126), constructed with an explicit path so the suite
    drives it against a temp tree instead of the real journal.

    **Fail-OPEN on write, unlike its siblings**, and the asymmetry is deliberate. The endorsement and
    human-gesture journals fail CLOSED because a lost line loses a human decision that nothing can
    rebuild. Here a lost line loses one accounting row — while failing closed would abort a paid call
    that already succeeded, spending the money AND losing the work. So a write error is swallowed and
    the call proceeds. The ceiling check below reads the journal, so an unwritable journal degrades to
    "under-counted", which is the honest thing to say about it rather than a pretend guarantee.
    """

    __slots__ = ("_path", "_cache")

    def __init__(self, path: Path | str = DEFAULT_SPEND_PATH) -> None:
        self._path = Path(path)
        self._cache: dict[str, tuple[tuple[int, int], DaySpend]] = {}

    @property
    def path(self) -> Path:
        return self._path

    def record(self, model: str, usage: CanonicalUsage, *, kind: str = "model_call") -> Charge:
        """Price one call and append it. Returns the charge even if the append failed."""
        cost, status = price(model, usage)
        charge = Charge(
            model=model,
            usage=usage,
            cost_eur=cost,
            status=status,
            at=datetime.now(UTC).isoformat(),
            kind=kind,
        )
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(_to_wire(charge), ensure_ascii=False) + "\n")
        except OSError:
            return replace(charge, persisted=False)  # priced correctly, simply never written down
        self._cache.clear()  # our own append moves the stamp; drop the memo rather than trust it
        return charge

    def spent(self, day: str | None = None) -> DaySpend:
        """Total one LOCAL day (default: today). A garbled line is skipped, never fatal.

        **Local, not UTC.** "Daily" means the operator's day. Comparing UTC dates put the boundary at
        02 h 00 Paris — inside a working night — so one civil day could hold two UTC days and spend
        **twice** the ceiling. Timestamps are stored in UTC and converted here.

        **Parsed, not prefix-matched.** The first version compared the start of the ISO string, which
        made ``--jour 2026-07`` silently report a whole month, sorted an entry carrying ``+02:00``
        into the wrong day, and — worse — let a line with **no** ``at`` at all escape every day for
        ever. An undatable entry is now counted against TODAY: an unattributable charge must weigh on
        the ceiling, not vanish from it.

        **Every number is clamped at zero.** A single negative line used to drive the total to
        −999 999 950 € and neutralise BOTH ceilings — falsifying this very docstring's old claim that
        a corrupt journal "can only make the system think it has spent less".
        """
        target = day or datetime.now().astimezone().date().isoformat()
        cached = self._cache.get(target)
        stamp = self._stamp()
        if cached is not None and cached[0] == stamp:
            return cached[1]
        total, usage, calls, unpriced = 0.0, CanonicalUsage(), 0, 0
        for event in self._events():
            if _local_day(event.get("at")) != target:
                continue
            calls += 1
            total += max(0.0, _num(event.get("cost_eur")))
            raw = event.get("usage")
            raw = raw if isinstance(raw, dict) else {}
            usage = usage + CanonicalUsage(
                **{name: max(0, int(_num(raw.get(name)))) for name in _CLASSES}
            )
            if event.get("status") == CostStatus.UNKNOWN.value:
                unpriced += 1
        result = DaySpend(
            day=target, cost_eur=round(total, 6), usage=usage, calls=calls, unpriced_calls=unpriced
        )
        self._cache[target] = (stamp, result)
        return result

    def _stamp(self) -> tuple[int, int]:
        """(size, mtime_ns) of the journal — the memo key.

        ``check_ceilings`` runs before EVERY paid call and re-parses the whole append-only file;
        measured at 21.5 ms for 10,000 lines, i.e. ~3.6 minutes of pure re-reading over a 10,000-call
        campaign. The file cannot change without its size or mtime changing, so an unchanged stamp
        means the previous total still holds — including when another process appended, since that
        moves the stamp too.
        """
        try:
            stat = self._path.stat()
        except OSError:
            return (-1, -1)
        return (stat.st_size, stat.st_mtime_ns)

    def _events(self) -> list[dict[str, Any]]:
        """Every readable line. NOTHING here may raise — this runs in front of a paid call.

        ``utf-8-sig`` drops a BOM that used to swallow the first line whole, and ``errors="replace"``
        survives a byte torn mid-character: an invalid byte anywhere used to make the journal
        permanently unreadable, so every later call died with ``UnicodeDecodeError`` before spending.
        The per-line guard is deliberately broad — the earlier version caught only ``JSONDecodeError``
        while the docstring promised "a garbled line is skipped, never fatal", and a line that was
        valid JSON but wrongly typed (``"cost_eur": "a lot"``) killed the whole run.
        """
        if not self._path.is_file():
            return []
        events: list[dict[str, Any]] = []
        try:
            handle = self._path.open("r", encoding="utf-8-sig", errors="replace")
        except OSError:
            return []
        try:
            with handle:
                for line in handle:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        event = json.loads(stripped)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if isinstance(event, dict):
                        events.append(event)
        except Exception:  # noqa: BLE001 - a read that raises would abort a paid call; never
            return events
        return events

    def check_ceilings(self, *, cost_ceiling_eur: float, token_ceiling: int) -> None:
        """Refuse fail-closed when today's spend has reached either ceiling (invariant 16 / D78).

        Called BEFORE a paid request, so the ceiling stops the next call rather than reporting the
        one that broke it. A ceiling of ``0`` or less is treated as "not configured" and does not
        block — an absent ceiling must not become an accidental kill switch.
        """
        today = self.spent()
        if cost_ceiling_eur > 0 and today.cost_eur >= cost_ceiling_eur:
            raise ResourceBoundError(
                f"daily spend {today.cost_eur:.2f} EUR reached the configured ceiling "
                f"{cost_ceiling_eur:.2f} EUR over {today.calls} call(s) (D86, invariant 16)"
                + ("" if today.is_complete else f" — plus {today.unpriced_calls} unpriced call(s)")
            )
        if token_ceiling > 0 and today.usage.total >= token_ceiling:
            raise ResourceBoundError(
                f"daily frontier tokens {today.usage.total} reached the configured ceiling "
                f"{token_ceiling} (D86, invariant 16) — the net under an unpriced model"
            )


def _num(value: Any) -> float:
    """A number from anything, or 0.0 — never an exception in front of a paid call."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _local_day(at: Any) -> str:
    """The LOCAL calendar day of a stored timestamp; today when it cannot be read.

    Fail-closed on purpose: an entry whose date is missing or unparseable is charged to today rather
    than dropped, because a line nobody can date is exactly the shape a forged or truncated entry
    takes, and dropping it would remove it from the ceiling it should be weighing on.
    """
    text = str(at or "").strip()
    if text:
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=UTC)
            return moment.astimezone().date().isoformat()
        except ValueError:
            pass
    return datetime.now().astimezone().date().isoformat()


def _to_wire(charge: Charge) -> dict[str, Any]:
    return {
        "at": charge.at,
        "model": charge.model,
        "kind": charge.kind,
        "cost_eur": charge.cost_eur,
        "status": charge.status.value,
        "usage": {name: getattr(charge.usage, name) for name in _CLASSES},
    }


def render_spend(today: DaySpend, *, cost_ceiling_eur: float, token_ceiling: int) -> str:
    """The human report — honest about what it does NOT see."""
    if not today.calls:
        return (
            f"Mnemosyne spend for {today.day}: no paid calls.\n"
            "\U000026A0\U0000FE0F That does not mean \"nothing spent today\": this counter sees ONLY the calls made "
            "by Mnemosyne's own code. Your Claude Code session runs through your own subscription, "
            "out of reach from here."
        )
    usage = today.usage
    which, at_eur = binding_ceiling(cost_ceiling_eur, token_ceiling)
    bar = f"{today.cost_eur:.2f} € out of a {cost_ceiling_eur:.2f} € ceiling"
    lines = [
        f"Mnemosyne spend for {today.day} (local day) — {bar}",
        f"  {today.calls} call(s) · {usage.total} tokens "
        f"(input {usage.input} · output {usage.output} · "
        f"cache read {usage.cache_read} · cache write {usage.cache_write})",
        f"  token ceiling: {usage.total} / {token_ceiling}",
    ]
    if which == "tokens" and cost_ceiling_eur > 0:
        lines.append(
            f"  \U000026A0\U0000FE0F It is the TOKEN ceiling that actually binds, not the euros: 200,000 tokens "
            f"cap out at ~{at_eur:.2f} € on the priciest model, so the "
            f"{cost_ceiling_eur:.2f} € ceiling can never trigger. Read the tokens line, "
            "not the euros one."
        )
    if not today.is_complete:
        lines.append(
            f"  \U000026A0\U0000FE0F {today.unpriced_calls} call(s) on a model with NO known price — the euro total "
            "is a FLOOR, not the truth. It is the token ceiling that bounds them."
        )
    lines.append(
        "  (estimate: no provider returns us a real cost — prices dated 2026-07-20)"
    )
    lines.append(
        "  Not counted: your Claude Code session (subscription, outside this process) — this total "
        "is what Mnemosyne's CODE spent, never your whole day."
    )
    return "\n".join(lines)
