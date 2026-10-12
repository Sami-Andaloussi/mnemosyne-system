"""Drive a human gate against a REAL controlling terminal - the harness, in ONE place.

This exists because the thing it tests exists: the repo has one live-terminal gate
(:func:`mnemosyne.runtime.human_gate.read_live_confirmation`) and it must be exercised for real, not
monkeypatched. A monkeypatched gate proves everything except the gate - which is how
``io.UnsupportedOperation: File or stream is not seekable`` shipped and blew up the first time a
real human typed at it (a ``"r+"`` text file wraps a character device in ``io.BufferedRandom``,
which assumes a seekable stream; a tty never is).

The harness itself was about to be written a second time, in a second test file, for a second
caller of the same gate. Copies of a gate drift, and so do copies of the harness that guards it.
"""

from __future__ import annotations

import fcntl
import os
import pty
import termios
import time
from collections.abc import Callable
from typing import Any


def ask_over_a_real_pty(
    gate: Callable[..., bool],
    prompt: str,
    typed: bytes,
    *,
    timeout: float = 5.0,
    **kwargs: Any,
) -> bool | None:
    """Call ``gate(prompt, **kwargs)`` in a child whose CONTROLLING TERMINAL is a real pty.

    A forked child, not a thread: ``/dev/tty`` resolves per-process to the controlling terminal, so
    the child must ``setsid`` then claim the pty slave (``TIOCSCTTY``) - exactly what happens when
    user runs the command in his own shell. The parent plays the human.

    The parent types only ONCE THE PROMPT HAS APPEARED. Writing sooner races the child's ``open`` of
    the device and the bytes go nowhere: the gate then blocks until the timeout and the call returns
    ``None`` - which reads exactly like a refusal while being an artefact of the harness. Returns
    ``None`` only on timeout, so a test can tell "refused" from "never answered".
    """
    master, slave = pty.openpty()
    slave_name = os.ttyname(slave)
    pid = os.fork()
    if pid == 0:
        try:
            os.setsid()
            fd = os.open(slave_name, os.O_RDWR)
            os.dup2(fd, 0)
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            fcntl.ioctl(fd, termios.TIOCSCTTY, 0)
            result = gate(prompt, **kwargs)
            os.write(2, f"RESULT={result}\n".encode())
        except BaseException as exc:  # noqa: BLE001 - report the failure to the parent, then exit
            os.write(2, f"CHILD-ERROR={exc!r}\n".encode())
        finally:
            os._exit(0)
        return None  # pragma: no cover - unreachable, os._exit already ran

    os.close(slave)
    try:
        deadline = time.time() + timeout
        buffer = b""
        typed_sent = False
        while b"RESULT=" not in buffer and b"CHILD-ERROR=" not in buffer and time.time() < deadline:
            try:
                buffer += os.read(master, 4096)
            except OSError:
                break
            if not typed_sent and prompt.encode() in buffer:
                os.write(master, typed)
                typed_sent = True
            time.sleep(0.05)
        if b"CHILD-ERROR=" in buffer:
            raise AssertionError(f"the real /dev/tty path raised: {buffer!r}")
        if b"RESULT=True" in buffer:
            return True
        if b"RESULT=False" in buffer:
            return False
        return None  # timed out - the test's assertion shows the raw buffer
    finally:
        os.waitpid(pid, 0)
