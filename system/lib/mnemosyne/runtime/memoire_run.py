"""``make memoire`` (D173) - the index overflow, and the ratchet that measures it.

    make memoire

Emits a secondary index file (the overflow channel the built-in memory index cannot load) and
publishes the ratchet line: bijection over BOTH indexes by set diff, the frozen size of the
primary memory index, and whether the overflow was REALLY emitted. Brick-free, read-only, no
model, no network.

WARNING: Wired into the SessionStart hook, whose ``rc`` is discarded by construction (fail-open). There it
only PRINTS. Run by hand or from a script, this exits non-zero - that is where it bites.
Code is English (D117); the report belongs to the user, so it prints in French.
"""

from __future__ import annotations

from .memoire import rendre

if __name__ == "__main__":
    raise SystemExit(rendre())
