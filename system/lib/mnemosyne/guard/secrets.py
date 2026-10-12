"""Secret broker (D81, invariant 22) - inject at the last instant, never persist.

Least privilege (D89): the Guard *decides* but does not scatter secrets. Keys live
in a vault opened only at the call point - the Guard mints a :class:`~mnemosyne.
ports.guard.Grant` carrying a secret *handle* (a name), never the value; the value
materializes only when :meth:`SecretBroker.redeem` is called against a valid grant,
and is passed straight to the backend. Nothing the Guard records - the ruling, the
grant, the audit event - carries the value, so a ``grep`` of snapshots / JSONL logs
/ tool outputs never reveals a key (invariant 22).

The on-disk snapshot / JSONL facet is shared infrastructure with the replay layer
(invariant 12, LOT 5); LOT 3 fixes the injection point and proves the Guard's own
artifacts stay clean. Code & docstrings English (D117).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType

from ..ports import Effect, GuardDenied
from ..ports.guard import Grant

#: A decryptor: encrypted vault bytes -> the plaintext ``handle -> value`` map. The brick (SOPS + age,
#: (3)-6b) implements it and is injected LAZILY by ``real_runtime``; our loader treats its output as the
#: vault contents and never sees a key any other way (D81 / D103).
SecretDecryptor = Callable[[bytes], Mapping[str, str]]


class SecretBroker:
    """A last-instant secret vault (D81). Holds ``handle -> value`` and hands a value
    out ONLY against a valid ``SECRET_USE`` grant whose target names that handle.

    The broker never logs, never returns its map, and its ``repr`` hides values, so
    a secret cannot leak through the broker itself (invariant 22)."""

    __slots__ = ("_vault",)

    def __init__(self, secrets: Mapping[str, str]) -> None:
        self._vault: Mapping[str, str] = MappingProxyType(dict(secrets))

    def __contains__(self, handle: object) -> bool:
        return handle in self._vault

    def redeem(self, grant: Grant) -> str:
        """Return the secret value for a valid ``SECRET_USE`` grant (the injection
        point). Fail-closed: a non-secret grant or an unknown handle is refused
        (:class:`GuardDenied`) rather than leaking or guessing."""
        request = grant.request
        if request.effect is not Effect.SECRET_USE:
            raise GuardDenied("grant is not a SECRET_USE capability (invariant 22)")
        handle = request.target
        if handle is None or handle not in self._vault:
            raise GuardDenied(f"unknown secret handle {handle!r} (invariant 22)")
        return self._vault[handle]

    def __repr__(self) -> str:  # never expose values, even in a traceback / log
        return f"SecretBroker(handles={sorted(self._vault)!r})"


def load_secret_broker(
    *, vault_path: Path | None = None, decrypt: SecretDecryptor | None = None
) -> SecretBroker:
    """Load the encrypted secret vault into a last-instant :class:`SecretBroker` (D81 / (3)-6, inv. 22).

    The seam between the encrypted-at-rest vault (SOPS + age) and the runtime broker: read the vault
    ciphertext and hand it to the injected ``decrypt`` brick, whose plaintext ``handle -> value`` map
    becomes the broker. **Fail-closed (D100)**: a missing ``vault_path``, no ``decrypt`` wired, an absent
    file, or a decryptor that RAISES yields an EMPTY broker - every ``SECRET_USE`` is then denied, never a
    partial map nor a plaintext fallback. The decryption brick is injected by ``real_runtime`` at (3)-6b;
    the decryption keys live OUT-OF-BAND (a human prerequisite, D121-E4), so this never reads a key from
    beside the vault. The ignition smoke must confirm the vault actually decrypted - a silently-empty
    broker denies fail-closed, it does not announce itself (``[OPERATOR]`` allumage check)."""
    if vault_path is None or decrypt is None or not vault_path.exists():
        return SecretBroker({})
    try:
        # ``dict(...)`` is INSIDE the try (audit (3)-6 M2): a decryptor that returns a non-Mapping (a broken
        # brick) is a decryption failure too - fail-closed to an EMPTY broker, never a crash out of
        # bootstrap and never a partial / plaintext fallback (the promise is total, D100 / inv. 22).
        vault = dict(decrypt(vault_path.read_bytes()))
    except Exception:  # noqa: BLE001 - any decryption failure is fail-closed: an empty vault, never partial
        return SecretBroker({})
    return SecretBroker(vault)
