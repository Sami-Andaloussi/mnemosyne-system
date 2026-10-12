"""The ONE live-terminal gate - proved against a REAL pty, and against the attack that killed it.

Why this file exists. On 2026-07-28 an isolated audit ran one command against the gesture that lets
figures leave the machine for a third-party cloud::

    printf 'oui\\n' | python -c "...; print(_confirm_frontier_egress('api.anthropic.com'))"
    -> True

That gate read ``input()``, and ``input()`` reads ``stdin`` - whatever the parent process hands over.
So the canal-B human gesture, the one invariant 1 rests on, was satisfiable by a pipe: exactly the
class of the July incident where an agent typed a word meant for user. The two OTHER human gates in
this repo already read ``/dev/tty`` for precisely this reason; the third one had been written by
hand and had drifted.

The fix was to give all three ONE body. So this file proves two things on the real thing - and a
later audit (``H1``, 2026-08-15) found that the second of them had been misread since it was written:

* an agent with NO controlling terminal CANNOT pass - a piped, session-detached caller gets
  ``False`` (the audit's own attack);
* WARNING -- **a real pty with the right word returns ``True`` - and this does NOT mean "user passes".**
  It means the GATE cannot tell a pty driven by ``os.fork`` + ``TIOCSCTTY`` (:func:`_pty.
  ask_over_a_real_pty`, a fully automated harness, no human anywhere in it) apart from user's own
  shell. **This test file has been demonstrating the ``H1`` exploit since it was written** - every
  green run of what is now :func:`test_anything_holding_a_pty_passes_the_gate` (renamed here, I7 -
  it used to be called ``test_a_real_human_at_a_real_terminal_passes_first_try``) was already proof
  that an unattended program can satisfy the gate, mislabelled by its old name and docstring as
  proof that a human can. The mechanical assertions are correct and stay; the NAME and the
  docstring are corrected here (I7) to say what they actually show: the gate refuses a caller with
  NO terminal, and grants one to ANYTHING holding a pty - never mind who or what is driving it.

The pty half matters beyond politeness: the previous copy of this code used ``open(path, "r+")``,
which wraps a character device in ``io.BufferedRandom`` and raises ``io.UnsupportedOperation`` the
instant a real human touched it. The suite had only ever monkeypatched the whole function - proving
everything except the function. Nothing here monkeypatches the gate - which is exactly why it caught
the seekable bug in 2026-07 and exactly why it had already caught the ``H1`` exploit, unread, since.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

from _invariants import REPO_ROOT
from _pty import ask_over_a_real_pty

from mnemosyne.runtime.human_gate import read_live_confirmation

_LIB = str(REPO_ROOT / "system" / "lib")


def _ask_over_a_pipe(typed: bytes) -> bool | None:
    """The AUDIT'S OWN ATTACK: feed the word on stdin, with no controlling terminal at all."""
    code = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {_LIB!r})
        from mnemosyne.runtime.human_gate import read_live_confirmation
        sys.exit(0 if read_live_confirmation("mot : ") else 3)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        input=typed,
        capture_output=True,
        timeout=30,
        start_new_session=True,  # detach: no controlling terminal to inherit
        check=False,
    )
    return {0: True, 3: False}.get(proc.returncode)


def test_a_piped_word_can_never_satisfy_the_gate() -> None:
    """The attack that killed the figure-egress gesture, replayed against the shared gate."""
    assert _ask_over_a_pipe(b"oui\n") is False


def test_anything_holding_a_pty_passes_the_gate() -> None:
    """What this actually proves (I7, corrected - the old name/docstring claimed "user passes",
    which no assertion here can distinguish from "a pty passes"): a real pty with the right word
    returns ``True``, whether the hand on the other end is user's or ``tests/_pty.py``'s fully
    automated fork-and-type harness - the gate cannot tell them apart. Kept green, not deleted:
    the fact itself is desirable (a barrier that also blocks its own owner is a bug, never throttle
    user) - only the CLAIM that green-here means "not an agent" was false. See ``human_gate.py``'s
    module docstring for what this does and does not buy."""
    assert ask_over_a_real_pty(read_live_confirmation, "Tape OUI : ", b"OUI\n") is True


def test_a_real_typed_refusal_is_a_refusal() -> None:
    assert ask_over_a_real_pty(read_live_confirmation, "Tape OUI : ", b"non merci\n") is False


def test_the_accepted_word_is_the_callers_choice_not_a_hardcoded_one() -> None:
    """``figures_enrich_run`` accepts ``oui/o/yes/y``; sharing a body must not silently narrow that.

    Widening or narrowing what user may type is an ERGONOMIC change, and extracting a shared hearth
    is not the moment to make one - so the accepted set travels with the caller and is proved here.
    """
    assert ask_over_a_real_pty(read_live_confirmation, "mot : ", b"y\n", accepted=("y",)) is True
    assert ask_over_a_real_pty(read_live_confirmation, "mot : ", b"y\n") is False  # not by default
