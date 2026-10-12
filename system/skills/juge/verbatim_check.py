#!/usr/bin/env python3
"""Implementation behavior is covered by tests."""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

_RAW = Path("knowledge/raw")
_DISTILLED = Path("knowledge/distilled")
_MAX_SHOWN = 10  # dropped passages shown in clear (the total count is always stated)
_EXCERPT = 200  # characters shown per dropped passage - enough to find it again in the source

_MARQUE_DE_FICHE = re.compile(r"^distilled_by:", re.MULTILINE)


def mirror_raw(fiche: Path) -> Path | None:
    """The raw the fiche MIRRORS: `knowledge/distilled/x/y.md` -> `knowledge/raw/x/y.md`.

    None as soon as the fiche does not live under `knowledge/distilled/` (an agent drafting in /tmp):
    there is then nothing to derive, and GUESSING a source is precisely how a fiche gets blessed
    against the wrong book - everything would either fall apart, or worse, hold together by accident.
    The caller must then name BOOK= itself.
    """
    try:
        rel = fiche.resolve().relative_to(_DISTILLED.resolve())
    except ValueError:
        return None
    return _RAW / rel


def _refus_de_source(fiche_path: Path, raw_path: Path, raw_text: str) -> str | None:
    """Is the designated source acceptable? Returns the REFUSAL reason, or None if it is acceptable.

    **BOOK= is chosen by THE ONE BEING JUDGED**, and that is the whole problem. Two isolated audits
    showed this in succession, on YYYY-MM-DD:
      1. pointing BOOK at the fiche itself made a fiche with ENTIRELY INVENTED citations come out as
         `4/4  -  rendement 100%  -  PASSE` (yield 100% - PASS);
      2. the guard written to close this case relied on a CONTENT MARKER (``distilled_by:``)
         present in a file the attacker OWNS. A
         ``grep -v '^distilled_by:' fiche.md > faux_livre.md`` - **one line removed** - and a real
         fiche from the shelf came back `963/963  -  rendement 100%  -  PASSE`. Reproduced by hand.

    This is the fault already recorded: "fixing a CASE does not close the CLASS". A content marker
    in a file the producer writes is a BLACKLIST, never a closure.

    **What closes the class: the reference is DERIVED, it is not DESIGNATED.** A fiche living under
    ``knowledge/distilled/`` has only ONE acceptable source - its mirror, computed by :func:`mirror_raw`
    from its own path. ``BOOK=`` can then only confirm it. No content edit gets around a derived
    path, and this is already the rule for the bulk judge: the gate and the wall can no longer say
    two different things about the same fiche.

    WARNING: **Exact scope, do not overstate it.** A fiche that does NOT live under ``knowledge/distilled/``
    (an agent drafting in /tmp) has no mirror: its source stays DESIGNATED there, and only the two
    content checks below filter it - the tautology therefore remains possible there. What this does
    not cost: such a fiche is in no base, and the day it enters one, ``make judge`` re-judges it
    against its real mirror. The output SAYS which of the two situations is being read."""
    if fiche_path.resolve() == raw_path.resolve():
        return (
            "the designated source IS the fiche itself. Every passage would then, trivially, "
            "be a literal excerpt of itself - the verdict would mean nothing."
        )
    if _MARQUE_DE_FICHE.search(raw_text):
        return (
            f"{raw_path} is a DISTILLED FICHE, not a source (it carries `distilled_by:`). "
            "Judging a fiche against a fiche measures nothing. Give the book's `.md`, under "
            "knowledge/raw/."
        )
    attendu = mirror_raw(fiche_path)
    if attendu is not None and raw_path.resolve() != attendu.resolve():
        return (
            f"this fiche lives under {_DISTILLED}/ : it is judged ONLY against its mirror\n"
            f"        {attendu}\n"
            f"        and you designated {raw_path}. A reference CHOSEN by the one being judged "
            "proves nothing - that is how an entirely invented fiche got blessed. Drop "
            "BOOK= : the mirror is DERIVED, it is not named."
        )
    return None


def rendement(n_verbatim: int, n_passages: int) -> str:
    """Implementation behavior is covered by tests."""
    return f"{math.floor(n_verbatim / n_passages * 1000) / 10:.1f}%".replace(".0%", "%")


def _excerpt(passage: str) -> str:
    """The passage on one line, cut at `_EXCERPT` - enough to find it again, not enough to flood the screen."""
    flat = " ".join(passage.split())
    return flat if len(flat) <= _EXCERPT else flat[:_EXCERPT] + " [...]"


def _tail(passage: str, keep: int = 120) -> str:
    """The END of the passage - for a TRUNCATED passage, the cut is the only interesting spot.

    `_excerpt` shows the BEGINNING (that is how the passage is recognized); here we want to see
    where it stops dead. First version: `_excerpt(p)[-120:]`, which rendered the MIDDLE of the
    beginning followed by a "[...]" that suggested the text kept going - exactly the opposite of
    what needs to be shown.
    """
    flat = " ".join(passage.split())
    return f"...{flat[-keep:]}" if len(flat) > keep else flat


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verbatim-check",
        description=(
            "Replays the verbatim floor on ONE fiche. Writes nothing. Exit: 0 = pass, "
            "1 = rejected, 2 = refused (usage). Via `make`, EVERY recipe failure becomes 2: read the "
            "VERDICT: line to tell a rejection from a refusal."
        ),
    )
    parser.add_argument("fiche", help="the distilled fiche to check")
    parser.add_argument(
        "--raw", default=None, help="the raw source (derived from the mirror path if omitted)"
    )
    args = parser.parse_args(argv)

    from mnemosyne.production import judge_fiche, verbatim_split

    fiche_path = Path(args.fiche)
    if not fiche_path.is_file():
        print(f"REFUSED : fiche not found -> {fiche_path}", file=sys.stderr)
        return 2

    raw_path = Path(args.raw) if args.raw else mirror_raw(fiche_path)
    if raw_path is None:
        print(
            f"REFUSED : {fiche_path} does not live under {_DISTILLED}/, the raw cannot be derived.\n"
            '        Name it: make verbatim-check FICHE="..." BOOK="knowledge/raw/<dom>/<livre>.md"',
            file=sys.stderr,
        )
        return 2
    if not raw_path.is_file():
        print(
            f"REFUSED : raw not found -> {raw_path}\n"
            "        Without the source, there is nothing to verify against: nothing gets blessed blindly.",
            file=sys.stderr,
        )
        return 2

    fiche_text = fiche_path.read_text(encoding="utf-8", errors="replace")
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")

    refus = _refus_de_source(fiche_path, raw_path, raw_text)
    if refus is not None:
        print(f"REFUSED : {refus}", file=sys.stderr)
        # The SAME line as the nominal case, and it cannot say PASSED. The documented contract is
        # "read the VERDICT: line" - and an isolated audit showed that by moving a guard three
        # lines up, stdout carried `963/963  -  rendement 100%` AND `VERDICT: PASSED` while stderr
        # carried the REFUSED message: a producer following the documented procedure would read
        # PASSED on a refused fiche. The fix is not to put the guard back in place (it will just
        # re-derive there again), it is that ONLY ONE place prints `VERDICT:`, and only after all
        # refusals.
        print("\nVERDICT: REFUSED")
        return 2
    verdict = judge_fiche(fiche_text, raw_text)

    print(f"VERBATIM-CHECK - {fiche_path}")
    # DERIVED vs DESIGNATED: the only thing that distinguishes a verification from a tautology. The
    # reader must not have to reconstruct where the source comes from - the line says it.
    origine = (
        "DERIVED from the mirror" if mirror_raw(fiche_path) is not None else "DESIGNATED by the caller"
    )
    print(f"  source   : {raw_path}  ({len(raw_text.encode('utf-8'))} bytes, {origine})")
    print(f"  verdict  : {verdict.status}")

    dropped: tuple[str, ...] = ()
    claimed: tuple[str, ...] = ()
    n_doublons = 0
    if verdict.n_passages:
        kept, dropped = verbatim_split(fiche_text, raw_text)
        claimed = kept + dropped
        n_doublons = verdict.n_passages - (len(kept) + len(dropped))
        if len(kept) != verdict.n_verbatim or n_doublons < 0:
            print(
                f"REFUSED : the judge counts {verdict.n_verbatim}/{verdict.n_passages}, the gate "
                f"counts {len(kept)}/{len(kept) + len(dropped)} - the two DIVERGE. Nothing gets "
                "blessed: the passage extraction was duplicated somewhere (contract-single-source-emit).",
                file=sys.stderr,
            )
            return 2
        print(
            f"  figures  : {verdict.n_verbatim}/{verdict.n_passages} passages verbatim "
            f"(rendement {rendement(verdict.n_verbatim, verdict.n_passages)})  -  "
            f"{verdict.n_chapters} chapter(s)"
        )
    else:
        print(
            f"  figures  : no passage reached the floor  -  {verdict.n_chapters} chapter(s)"
        )
    print(f"  reason   : {verdict.reason}")

    if n_doublons:
        print(
            f"\n  {n_doublons} passage(s) claimed in DUPLICATE - `keep_verbatim` keeps only the "
            "first occurrence, without a word of complaint. They are neither wrong nor dropped: "
            "they count once instead of twice - so they LOWER the displayed yield without any "
            "passage being dropped. (No shelf figure is engraved here: a total frozen in a "
            "program's output rots - it announced 50 when the formula was already yielding 58.)"
        )

    if verdict.n_truncated:
        from mnemosyne.production import passage_cap, truncated_passages

        # The header used to say `verdict.n_truncated` (computed WITH duplicates) while the list came
        # from `claimed` (already de-duplicated): across 3 real fiches, 69 announced vs 58 shown.
        # A single count, the one we PRINT - the contradiction was the very class the divergence
        # guard claims to refuse.
        coupes = truncated_passages(claimed) if claimed else ()
        print(
            f"\n  {len(coupes)} passage(s) CUT CLEAN at the schema ceiling "
            f"(maxLength={passage_cap()}) - the verbatim floor cannot see them: a literal "
            "prefix stays literal, so they are counted as verbatim and truly are, "
            "but AMPUTATED. Only a re-distillation restores them:"
        )
        for i, passage in enumerate(coupes[:_MAX_SHOWN], start=1):
            print(f"    [{i}] {_tail(passage)}")
        if len(coupes) > _MAX_SHOWN:
            print(f"    ... +{len(coupes) - _MAX_SHOWN} other(s) not shown")

    if dropped:
        from mnemosyne.production.juge import _MIN_VERBATIM_YIELD

        suite = (
            f"the verdict TOLERATES them (the judge accepts up to {1 - _MIN_VERBATIM_YIELD:.0%} "
            "non-verbatim) - but these are NOT the source's own words"
            if verdict.ok
            else "to fix BEFORE the fiche enters the base"
        )
        print(f"\n  {len(dropped)} passage(s) DROPPED by the floor - {suite} :")
        for i, passage in enumerate(dropped[:_MAX_SHOWN], start=1):
            print(f"    [{i}] {_excerpt(passage)}")
        if len(dropped) > _MAX_SHOWN:
            print(f"    ... +{len(dropped) - _MAX_SHOWN} other(s) not shown")
        print(
            "\n  A passage is dropped when it is NOT, word for word, a contiguous excerpt of the "
            "source (or when it quotes a line INSERTED by an enrichment, which is not the author)."
        )

    print(f"\nVERDICT: {'PASSED' if verdict.ok else 'REJECTED'}")
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
