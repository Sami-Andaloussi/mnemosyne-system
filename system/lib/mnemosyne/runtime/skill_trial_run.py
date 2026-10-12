"""``skill-eprouver`` / ``skill-juger`` / ``skill-verdict`` / ``skill-epreuves`` — the trial as gestures.

    make skill-eprouver SKILL=distillateur TACHE="distill such-and-such document" OUT=/tmp/epreuve
    make skill-juger EPREUVE=/tmp/epreuve AVEC=/tmp/sortie-avec.md SANS=/tmp/sortie-sans.md
    make skill-verdict EPREUVE=/tmp/epreuve AVEC=... SANS=... VERDICT=nuit PREUVE="..." PAR="..."
    make skill-epreuves

Four seams over :mod:`mnemosyne.production.skill_trial`. The trial DIRECTORY is what ties them
together: ``eprouver`` writes both mandates and the secret salt into it, ``juger`` reads the salt
from it, and ``verdict`` recomputes every digest from it. A verdict about a trial that was never
emitted has no directory to cite.

``skill-epreuves`` exists because an audit noticed that ``TrialLedger.read()`` was called by no
surface at all: a recorded ``nuit`` — the verdict with every incentive to be forgotten — had no path
to a human. A journal nobody reads is a journal that does not exist.

Nothing here runs an agent or calls a model. ``PAR`` has no default and cannot be overridden by the
CLI: an audit showed a one-line change hardcoding an author the caller never gave, with no test to
notice. Code English (D117); the CLI surface is English throughout this public mirror.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..production.skill_trial import (
    BLINDING_STATES,
    KNOWN_LIMITS,
    SkillTrialError,
    TrialLedger,
    TrialOutcome,
    build_judge_arm,
    build_open_judge_arm,
    build_trial,
    digest_of,
    naming_leaks,
    signature_leaks,
)

DEFAULT_TRIALS_PATH = Path(__file__).resolve().parents[3] / "state" / "skill_trials.jsonl"

_WITH_MANDATE = "mandat-bras-1-avec.md"
_WITHOUT_MANDATE = "mandat-bras-2-sans.md"
_SALT = "sel-secret.txt"
#: The TASK, written into the trial directory by `eprouver` and read back by `juger`. Without
#: it, the judge's mandate asked *"which one does LA TACHE better"* without ever telling them what
#: the task was -- measured by a third-party judge, 2026-08-14. ABSENT (a trial emitted before
#: this fix), the mandate ADMITS it to the judge rather than staying silent: an admission gets
#: corrected, a silence reads as a healthy trial.
_TASK = "tache.txt"


def _read_file(path: Path, *, what: str) -> str:
    if not path.exists():
        raise SkillTrialError(f"{what} not found: {path}")
    return path.read_text(encoding="utf-8")


def _trial_dir(path: Path) -> tuple[str, str, str, str | None]:
    """The two mandates, the salt and the TASK of an emitted trial — or a refusal naming what is
    missing. The task is the only one that may be ``None``: trials emitted before it was written
    down still judge, but their mandate says so out loud."""
    tache = path / _TASK
    return (
        _read_file(path / _WITH_MANDATE, what="arm 1's mandate"),
        _read_file(path / _WITHOUT_MANDATE, what="arm 2's mandate"),
        _read_file(path / _SALT, what="the trial's salt").strip(),
        tache.read_text(encoding="utf-8").strip() if tache.is_file() else None,
    )


def render_recorded(
    skill: str, outcome: TrialOutcome, path: Path, blinding: str = "aveugle"
) -> str:
    consequence = {
        TrialOutcome.DIFFERENTIATES: "The artifact earns its place: it does what the bare arm does not.",
        TrialOutcome.INDIFFERENT: (
            "The artifact is DECORATIVE on this task. One trial does not condemn — but two or "
            "three saying the same thing are worth archiving (we archive, we never erase)."
        ),
        TrialOutcome.HARMS: (
            "\U000026A0\U0000FE0F The BARE arm does better. This is the case nobody is looking for: handle it "
            "before adding anything else to the corpus."
        ),
    }[outcome]
    caveat = (
        ""
        if blinding == "aveugle"
        else (
            "\U000026A0\U0000FE0F BLINDING BROKEN: the judge knew which arm carried the artifact. This verdict is "
            "contaminated by expectation and is NOT worth a proof — it reads as a clue.\n"
        )
    )
    return f"[skill-verdict] {skill} → {outcome.value}\n{caveat}{consequence}\nJournal: {path}\n"


def render_trials(read, *, limit: int = 20) -> str:
    """The journal, read back. `nuit` verdicts come FIRST — they are the point of the instrument."""
    if not read.entries and not read.unreadable:
        lines = ["# Mnemosyne · differential trials", "", "No trial recorded."]
        return "\n".join(lines) + "\n"
    lines = [
        "# Mnemosyne · differential trials",
        "",
        f"{len(read.entries)} trial(s) recorded.",
    ]
    if read.unreadable:
        lines.append(
            f"\U000026A0\U0000FE0F {read.unreadable} UNREADABLE line(s) in the journal — a lost entry does not "
            "vanish silently, it gets counted."
        )
    harmful = read.harmful
    if harmful:
        lines += ["", f"\U000026A0\U0000FE0F {len(harmful)} 'nuit' verdict(s) — to be handled as a priority:"]
        for e in harmful:
            lines.append(f"  [{e.get('at', '?')}] {e.get('skill', '?')} — {e.get('evidence', '')}")
    broken = [e for e in read.entries if e.get("blinding") != "aveugle"]
    if broken:
        lines.append(
            f"\U000026A0\U0000FE0F {len(broken)} verdict(s) rendered with BLINDING BROKEN — the judge knew which "
            "arm they were reading; these are clues, not proofs."
        )
    lines.append("")
    lines.append(f"The {min(limit, len(read.entries))} most recent:")
    for e in read.entries[-limit:][::-1]:
        mark = "" if e.get("blinding") == "aveugle" else " [BROKEN]"
        lines.append(
            f"  [{e.get('at', '?')}] {e.get('skill', '?')} → {e.get('outcome', '?')}{mark} "
            f"(by {e.get('by', '?')}) — {e.get('task', '')}"
        )
    return "\n".join(lines).rstrip() + "\n"


def _cmd_eprouver(args: argparse.Namespace) -> int:
    emission = build_trial(args.skill, args.tache, baseline=args.reference)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / _WITH_MANDATE).write_text(emission.with_arm, encoding="utf-8")
    (out / _WITHOUT_MANDATE).write_text(emission.without_arm, encoding="utf-8")
    (out / _SALT).write_text(emission.salt + "\n", encoding="utf-8")
    (out / _TASK).write_text(args.tache + "\n", encoding="utf-8")
    limits = "\n".join(f"  - {limit}" for limit in KNOWN_LIMITS)
    print(
        f"[skill-eprouver] trial emitted in {out}\n"
        f"  arm 1 (WITH)  : {out / _WITH_MANDATE}\n"
        f"  arm 2 (WITHOUT): {out / _WITHOUT_MANDATE}\n"
        f"  secret salt   : {out / _SALT}  ← give it to NONE of the three agents\n\n"
        f"Give each mandate to a FRESH, DISTINCT agent. Collect both outputs, then:\n"
        f"  make skill-juger EPREUVE={out} AVEC=<output-1> SANS=<output-2>\n\n"
        f"WHAT THIS TRIAL CANNOT ESTABLISH:\n{limits}\n"
    )
    return 0


def _report_residual(with_mandate: str, without_mandate: str, avec: str, sans: str) -> None:
    """Print the asymmetric tokens the refusal does NOT act on — chance, or a leak the rule missed.

    Not a refusal, because measured false positives exist (`make` from an English quotation in the
    source book). Printed on stderr rather than filed away, so the operator meets it seconds before
    typing `--aveuglement`: the one gesture where this list changes the answer. A label no consumer
    ever reads costs nothing to ignore, so it gets ignored."""
    leaks = signature_leaks(
        with_mandate=with_mandate,
        without_mandate=without_mandate,
        with_output=avec,
        without_output=sans,
    )
    named = set(naming_leaks(leaks, with_mandate=with_mandate, without_mandate=without_mandate))
    residual = tuple(tok for tok in leaks if tok not in named)
    if residual:
        print(
            f"[skill-juger] {len(residual)} token(s) appear on only one side without naming "
            f"an artifact: {', '.join(residual)}\n"
            "  This is NOT a refusal — on a real trial it was chance. Look at them before "
            "choosing AVEUGLEMENT= on the verdict.",
            file=sys.stderr,
        )


def _cmd_juger(args: argparse.Namespace) -> int:
    with_mandate, without_mandate, salt, tache = _trial_dir(args.epreuve)
    with_output = _read_file(args.avec, what="arm 1's output")
    without_output = _read_file(args.sans, what="arm 2's output")
    _report_residual(with_mandate, without_mandate, with_output, without_output)
    if args.ouvert:
        print(
            build_open_judge_arm(
                with_output,
                without_output,
                with_mandate=with_mandate,
                without_mandate=without_mandate,
            ),
            end="",
        )
        print(
            "[skill-juger] mandate issued IN THE OPEN — the verdict will have to carry "
            "--aveuglement rompu.",
            file=sys.stderr,
        )
        return 0
    print(
        build_judge_arm(
            with_output,
            without_output,
            salt,
            with_mandate=with_mandate,
            without_mandate=without_mandate,
            task=tache,
        ),
        end="",
    )
    return 0


def _cmd_verdict(args: argparse.Namespace) -> int:
    with_mandate, without_mandate, _, _ = _trial_dir(args.epreuve)
    outcome = TrialOutcome(args.verdict)
    TrialLedger(args.journal).record(
        skill=args.skill,
        task=args.tache,
        outcome=outcome,
        evidence=args.preuve,
        with_digest=digest_of(_read_file(args.avec, what="arm 1's output")),
        without_digest=digest_of(_read_file(args.sans, what="arm 2's output")),
        with_mandate_digest=digest_of(with_mandate),
        without_mandate_digest=digest_of(without_mandate),
        blinding=args.aveuglement,
        by=args.par,
    )
    print(render_recorded(args.skill, outcome, args.journal, args.aveuglement), end="")
    return 0


def _cmd_epreuves(args: argparse.Namespace) -> int:
    print(render_trials(TrialLedger(args.journal).read()), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="make skill-eprouver",
        description="The differential trial: a skill proves itself by the DIFFERENCE it makes.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    emit = sub.add_parser("eprouver", help="emit the two mandates + the salt into a folder")
    emit.add_argument("--skill", required=True)
    emit.add_argument("--tache", required=True)
    emit.add_argument("--reference", default=None)
    emit.add_argument("--out", type=Path, required=True)
    emit.set_defaults(func=_cmd_eprouver)

    judge = sub.add_parser(
        "juger", help="emit the judge's mandate, outputs labelled under the salt"
    )
    judge.add_argument("--epreuve", type=Path, required=True)
    judge.add_argument("--avec", type=Path, required=True)
    judge.add_argument("--sans", type=Path, required=True)
    judge.add_argument(
        "--ouvert",
        action="store_true",
        help="judge IN THE OPEN when blinding is impossible — the verdict will carry `rompu`",
    )
    judge.set_defaults(func=_cmd_juger)

    rec = sub.add_parser("verdict", help="record what the trial showed")
    rec.add_argument("--epreuve", type=Path, required=True)
    rec.add_argument("--skill", required=True)
    rec.add_argument("--tache", required=True)
    rec.add_argument("--avec", type=Path, required=True)
    rec.add_argument("--sans", type=Path, required=True)
    rec.add_argument("--verdict", required=True, choices=[o.value for o in TrialOutcome])
    rec.add_argument("--preuve", required=True)
    rec.add_argument(
        "--aveuglement",
        required=True,
        choices=list(BLINDING_STATES),
        help="did the judge know which arm they were reading? no default — a silent verdict reads as `aveugle` (blind)",
    )
    rec.add_argument("--par", required=True, help="who renders this verdict — no default, ever")
    rec.add_argument("--journal", type=Path, default=DEFAULT_TRIALS_PATH)
    rec.set_defaults(func=_cmd_verdict)

    show = sub.add_parser("epreuves", help="read the journal back — `nuit` verdicts come first")
    show.add_argument("--journal", type=Path, default=DEFAULT_TRIALS_PATH)
    show.set_defaults(func=_cmd_epreuves)

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return int(args.func(args))
    except SkillTrialError as exc:
        print(f"[skill-trial] REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - [OPERATOR] surface
    raise SystemExit(main())
