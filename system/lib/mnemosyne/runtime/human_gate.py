"""The ONE live-terminal gate: a word read from ``/dev/tty``, the controlling terminal.

Why this module exists rather than a third copy. The gate was written twice - ``declassify_run`` and
``policy_run`` - and the duplication has *already* cost: a real bug (``io.UnsupportedOperation: File
or stream is not seekable``, from wrapping a character device in ``io.BufferedRandom``) was found in
one copy and had to be carried by hand to the other. A third copy was about to be written for the
figure-egress gesture. A contract with several homes drifts; this one has one.

The property, and it is structural, not a rule: the word is read from the **controlling terminal**,
never from ``stdin``. A piped caller (``printf 'oui\\n' | ...``), a headless runner, a plain agent
subprocess with no terminal at all - none of them have one, so ``open("/dev/tty")`` fails and the
answer is ``False``, fail-closed.

**Raw file descriptors on purpose.** ``open(path, "r+")`` wraps the fd in ``io.BufferedRandom``,
which assumes a seekable stream; a tty never is, so the wrapper raises the moment it is used - on
every platform. That bug survived for weeks because the suite only ever monkeypatched the whole
function, proving everything except the function itself. ``os.open`` + raw ``os.read``/``os.write``
never construct the wrapper. It is exercised here against a REAL pty pair.

STOP -- **WHAT THIS GATE DOES NOT PROVE (item I7, 2026-08-15) - READ BEFORE TRUSTING ITS RETURN VALUE.**
An isolated audit of ``H1`` found a REAL exploit, against a real ``pty`` pair, not a theoretical one:
a **program** can allocate a pseudo-terminal, make it the controlling terminal of a child process, and
type the accepted word into it. ``open("/dev/tty")`` succeeds, the read behaves exactly as it would
for a person, and this function returns ``True`` - with no human anywhere in the loop. *A pty is a
real device from the kernel's point of view; nothing here can tell it apart from a physical one.*

**What the fail-closed property upstream still buys, precisely** : a caller with NO controlling
terminal at all - a plain subprocess, a CI runner, a pipe - is still refused, unconditionally. That
half of the original claim holds. **What it does NOT buy**: a caller that goes to the trouble of
opening a pty is treated exactly like a person at a keyboard. *An agent cannot pass through a closed
door - but this door was never proven to reject an agent that builds its own room on the other side
of it.*

**The consequence for the level of anything built on this gate, stated once, for every caller to
read here rather than re-derive**: this is a **BARRIER (niveau 2)** - it refuses an unattended,
terminal-less caller, which is a real and useful refusal - **never an INCAPACITY (niveau 3)**. Niveau
3 means *cannot be done without a human*; a pty shows it CAN be done without one, given the effort of
building the pty. **Any docstring, log line, or `*Obligation*` field that calls this gate
"unforgeable" or "niveau 3" is asserting something this module cannot back.**
*This item does not attempt to close the gap* - a stronger check (a challenge only a human could
answer, session/process ancestry checks, ...) is a real engineering cost, and the user decides whether it
is worth paying. The avowal above is the whole deliverable: it costs nothing and it is true today.

Decisions: D74 (a life decision is never full-auto)  -  D159/D160 (the incident that first hardened
this gesture)  -  D100 (incapacity, never trust)  -  I7 (2026-08-15, the avowal above).
"""

from __future__ import annotations

import os
from collections.abc import Sequence

#: The default accepted word. Compared case-insensitively, after stripping surrounding whitespace.
DEFAULT_ACCEPTED: tuple[str, ...] = ("oui",)

#: I7 (2026-08-15) - the REAL obligation level of anything gated ONLY by this function, to cite
#: instead of re-asserting "niveau 3" / "unforgeable" at each of the (currently six) call sites.
#: A pty satisfies this gate, so it is a BARRIER an unattended caller cannot pass without building
#: one - not an INCAPACITY nothing could satisfy. See the module docstring for the measured exploit.
NIVEAU_REEL = "2 (BARRIER) -- never 3 (INCAPACITY): a pty satisfies it, measured on H1, 2026-08-15"


def read_live_confirmation(prompt: str, *, accepted: Sequence[str] = DEFAULT_ACCEPTED) -> bool:
    """Ask on the controlling terminal and return whether the typed word is in ``accepted``.

    ``prompt`` should NAME what is about to happen - the file written, the host data leaves for. A
    gesture whose prompt is vague authorises whatever the caller decided, which is how a diverted
    target stays invisible.

    No controlling terminal => ``False``. That branch is the whole barrier, so it never raises and
    never falls back to ``stdin``: the failure mode of a human gate must be REFUSAL.
    """
    try:
        fd = os.open("/dev/tty", os.O_RDWR)  # the real terminal, not stdin
    except OSError:
        return False  # agent / CI / piped caller -> the gesture cannot be made here (fail-closed)
    try:
        os.write(fd, prompt.encode())
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1)
            if not chunk or chunk == b"\n":
                break
            chunks.append(chunk)
        typed = b"".join(chunks).decode("utf-8", errors="replace").strip().lower()
        return typed in {word.lower() for word in accepted}
    finally:
        os.close(fd)
