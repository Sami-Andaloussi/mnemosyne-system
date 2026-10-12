"""The Guard fabric (LOT 3) - the deterministic reference monitor and its bounds.

One coherent barrier, not a bag of modules (D89 / D73): the deterministic
:class:`DeterministicGuard` is the root of trust; the agent-juge (:mod:`.juge`) can
only RAISE prudence over it (D91 / D100); the secret broker (:mod:`.secrets`) injects
keys at the last instant and never persists them (D81, invariant 22); the resource
bounds (:mod:`.bounds`) make every growing resource fail-closed at a configured
ceiling (D78, invariant 16). All of it keys on the frozen, read-only policy zone
(:mod:`..config`, SE4).

Two modules sit BEHIND that barrier rather than in it (D154), and the distinction
matters: :mod:`.redact` masks a secret already loose in a string, and :mod:`.fencing`
marks recalled corpus text as data rather than instruction. Both are best-effort
heuristics on attacker-influenced strings - defence in depth that catches the ordinary
accident, never a frontier. Nothing above may be relaxed because they exist.

This realizes the LOT 3 slice of eleven invariants (1, 3-8, 16, 17, 21, 22); the
port contracts it binds to live in :mod:`mnemosyne.ports`. Code & docstrings English
(D117).
"""

from __future__ import annotations

from .bounds import BoundedScheduler, check_bound
from .fencing import fence_recalled, sanitize_recalled
from .heavy_lock import HeavyRunBusy, HeavyRunHolder, HeavyRunLock
from .juge import AgentJuge, FailSafeJuge, combine_monotone
from .monitor import DeterministicGuard
from .redact import redact_sensitive_text
from .secrets import SecretBroker, SecretDecryptor, load_secret_broker
from .walls import WallLedger

__all__ = [
    "DeterministicGuard",
    "AgentJuge",
    "FailSafeJuge",
    "combine_monotone",
    "SecretBroker",
    "SecretDecryptor",
    "load_secret_broker",
    "BoundedScheduler",
    "check_bound",
    # heavy-run lock (Q1 / D95) - one heavy run at a time, made cross-process
    "HeavyRunLock",
    "HeavyRunBusy",
    "HeavyRunHolder",
    # boundary hygiene (D154) - defence in depth BEHIND the barriers above, never instead of them
    "redact_sensitive_text",
    "fence_recalled",
    "sanitize_recalled",
    # D159 - every refusal is deposited (fail-open, not a security boundary)
    "WallLedger",
]
