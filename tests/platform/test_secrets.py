"""(3)-6a - the secrets-at-rest seam (D81 / invariant 22).

Biting tests for :func:`load_secret_broker`, the seam between the encrypted-at-rest vault (SOPS + age,
(3)-6b) and the last-instant :class:`SecretBroker`. The whole point is fail-closed: a missing vault, no
decryptor, or a decryptor that raises yields an EMPTY broker - every ``SECRET_USE`` is then denied,
never a partial map nor a plaintext fallback. A genuine decryptor loads the handles, and the value
still never surfaces in a repr (inv. 22).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pytest import raises

from mnemosyne.guard import DeterministicGuard, SecretBroker, load_secret_broker
from mnemosyne.ports import (
    Bubble,
    Effect,
    GovernanceLabel,
    GuardDenied,
    GuardRequest,
    Sensitivity,
)

_HANDLE = "anthropic_api_key"
# An obviously fake plaintext. Its FORM carries nothing here: neither `Grant` (a frozen record of
# request / label / channel / token) nor `SecretBroker.__repr__` (handle names only) ever holds a
# value, so the "never leaks" assertion below is a plain substring test that bites identically for
# any distinctive string - verified by sabotaging both the repr and `redeem`.
_VALUE = "not-a-real-secret-value"


def _public() -> GovernanceLabel:
    return GovernanceLabel(sensitivity=Sensitivity.PUBLIC, bubble=Bubble("x"))


def _fixed_decryptor(mapping: Mapping[str, str]):
    def decrypt(_ciphertext: bytes) -> Mapping[str, str]:
        return mapping

    return decrypt


def _secret_grant(guard: DeterministicGuard):
    return guard.grant(
        GuardRequest(
            effect=Effect.SECRET_USE, subject=Bubble("x"), inputs=(_public(),), target=_HANDLE
        )
    )


def test_no_decryptor_wired_is_fail_closed_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault.enc"
    vault.write_bytes(b"ciphertext")
    broker = load_secret_broker(vault_path=vault, decrypt=None)  # no brick wired
    assert _HANDLE not in broker
    guard = DeterministicGuard(secrets=broker)
    with raises(GuardDenied):  # SECRET_USE denied - no handle in an empty vault (inv. 22)
        _secret_grant(guard)


def test_missing_vault_file_is_fail_closed_empty(tmp_path: Path) -> None:
    absent = tmp_path / "absent.enc"
    broker = load_secret_broker(vault_path=absent, decrypt=_fixed_decryptor({_HANDLE: _VALUE}))
    assert _HANDLE not in broker  # a decryptor with nothing to decrypt loads nothing


def test_no_vault_path_is_fail_closed_empty() -> None:
    broker = load_secret_broker(vault_path=None, decrypt=_fixed_decryptor({_HANDLE: _VALUE}))
    assert _HANDLE not in broker


def test_decryptor_that_raises_is_fail_closed_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault.enc"
    vault.write_bytes(b"corrupt")

    def _boom(_ciphertext: bytes) -> Mapping[str, str]:
        raise ValueError("bad key / tampered vault")

    broker = load_secret_broker(vault_path=vault, decrypt=_boom)  # must NOT crash bootstrap
    assert _HANDLE not in broker  # a failed decryption is an empty vault, never a partial one


def test_decryptor_returning_non_mapping_is_fail_closed_empty(tmp_path: Path) -> None:
    # audit (3)-6 M2 / D100: a decryptor that returns a NON-Mapping (a broken brick) is a decryption
    # failure too -> EMPTY broker, never a crash out of bootstrap and never a partial/plaintext fallback
    # (the "any failure -> empty broker" promise is total).
    vault = tmp_path / "vault.enc"
    vault.write_bytes(b"ciphertext")

    def _bad_shape(_ciphertext: bytes) -> Mapping[str, str]:
        return 42  # type: ignore[return-value]  # a broken brick returns a non-Mapping

    broker = load_secret_broker(vault_path=vault, decrypt=_bad_shape)  # must NOT crash
    assert _HANDLE not in broker


def test_genuine_decryptor_loads_handles_and_never_leaks_value(tmp_path: Path) -> None:
    vault = tmp_path / "vault.enc"
    vault.write_bytes(b"ciphertext")
    broker = load_secret_broker(vault_path=vault, decrypt=_fixed_decryptor({_HANDLE: _VALUE}))
    assert _HANDLE in broker

    guard = DeterministicGuard(secrets=broker)
    grant = _secret_grant(guard)
    # the value materializes ONLY at the injection point (handed straight to the backend, D81):
    assert guard.inject_secret(grant) == _VALUE
    # ... and a grep of the grant + the broker reveals no key (inv. 22 - repr hides values).
    assert _VALUE not in (repr(grant) + repr(broker))
    assert isinstance(broker, SecretBroker)
