"""connect_sops_age — the SOLE user of the SOPS/age CLI as a :class:`SecretDecryptor` (D81 / D103).

The decryption brick behind the :data:`~mnemosyne.guard.secrets.SecretDecryptor` seam (③-6b): it turns
the encrypted-at-rest vault bytes into the plaintext ``handle → value`` map that
:func:`~mnemosyne.guard.secrets.load_secret_broker` loads into the last-instant broker (D81). The brick
is **SOPS + age** driven via **subprocess** (there is no stable Python import surface for SOPS —
``oss_registry.md``), so this module isolates the CLI call, not a Python module. The whole thing is
brick-free at import (nothing runs at module load) and the actual ``sops`` invocation is
``# pragma: no cover``: it needs the ``sops`` binary + the age key, absent in CI, exercised only at ③
ignition, where the 1-click smoke confronts this brick with the real binary. The pure parser
(:func:`_parse_flat_secrets`) is deterministic, brick-free, UNIT-TESTED — it is where the plaintext is
turned into the flat map, so a mis-parse (a nested/malformed vault) must fail LOUDLY there.

**Governance stays in the seam, not the brick (D100).** This decryptor only PRODUCES the map; the
fail-closed behaviour — a missing vault / absent binary / a decryptor that RAISES yields an EMPTY broker
(every ``SECRET_USE`` then denied) — lives in :func:`~mnemosyne.guard.secrets.load_secret_broker`, which
runs AROUND this callable. So on ANY failure this raises (never a partial map, never a plaintext
fallback): the seam catches the raise and fail-closes to an empty broker. The decryption keys live
OUT-OF-BAND (a human prerequisite, D110 / D121-E4) — this never reads a key from beside the vault; the
``sops`` binary resolves the age identity from the ambient key store the human provisioned.

Decisions: D81 (last-instant secret injection) · D103 (sole importer / isolator) · D126 (brick-free
suite, injected runner) · D100 (fail-closed governance is the seam's, not the brick's) · D110
(keys out-of-band). Code & docstrings English (D117).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping

#: A subprocess runner: given the argv list, run it and return the captured stdout bytes; a non-zero
#: exit MUST raise (fail-closed — the seam turns a raise into an empty broker). Injected in tests / at
#: ignition so the arg-building + parsing translation is exercised WITHOUT the ``sops`` binary (D126).
SopsRunner = Callable[[list[str]], bytes]

#: The SOPS subcommand + flags. ``--decrypt`` on the vault path, ``--output-type json`` so the plaintext
#: is a single machine-parseable object regardless of the vault's on-disk format (json/yaml/env → json).
#: The exact flag spelling is confirmed at ignition (IGNITION NOTE on :func:`connect_sops_age`).
_SOPS_ARGV_HEAD: tuple[str, ...] = ("sops", "--decrypt", "--output-type", "json")


def _sops_argv(
    vault_bytes: bytes,
) -> list[str]:  # pragma: no cover - writes a temp file (③ ignition)
    """Build the ``sops`` argv, spooling the ciphertext to a temp file the binary can read.

    SOPS decrypts a FILE, not stdin bytes, so the vault ciphertext handed by
    :func:`~mnemosyne.guard.secrets.load_secret_broker` is written to a private temp file and its path
    is the final argv element. (Kept ``pragma`` because it touches the filesystem in the real path; the
    arg SHAPE is asserted in tests via the injected runner, which receives the resolved argv.) Confirm
    at ignition: whether ``sops`` can read the vault from stdin (``--input-type`` + ``-``) to avoid the
    temp file entirely, and the ``--output-type json`` flag spelling."""
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkstemp(suffix=".vault")[1])
    tmp.write_bytes(vault_bytes)
    return [*_SOPS_ARGV_HEAD, str(tmp)]


def _parse_flat_secrets(plaintext: bytes) -> Mapping[str, str]:
    """Parse SOPS's decrypted JSON plaintext into a flat ``handle → value`` map (pure, UNIT-TESTED).

    The plaintext (``--output-type json``) is a JSON object of secrets. This flattens it to
    ``handle → str(value)`` so it matches the broker's ``Mapping[str, str]`` contract. **Fails LOUDLY**
    on anything unexpected — plaintext that is not a JSON object, or a value that is itself a nested
    object / list (an ambiguous vault shape) — with a ``ValueError``, because the seam turns that
    raise into a fail-closed EMPTY broker (D100): a silently-dropped or mis-flattened secret is worse
    than no secret. Scalar non-string values (an int/bool) are stringified (a handle is a name → a
    string value); ``None`` is refused (an empty secret is a vault error, not an empty string)."""
    try:
        loaded = json.loads(plaintext)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"SOPS plaintext is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(
            f"SOPS plaintext must be a JSON object of handle→value, got {type(loaded).__name__}"
        )
    flat: dict[str, str] = {}
    for handle, value in loaded.items():
        if isinstance(value, (dict, list)):
            raise ValueError(
                f"secret handle {handle!r} maps to a nested {type(value).__name__}; the vault must be "
                "a flat handle→value map (D81) — flatten it or the broker fail-closes empty (D100)"
            )
        if value is None:
            raise ValueError(
                f"secret handle {handle!r} has a null value (an empty secret is refused)"
            )
        flat[str(handle)] = value if isinstance(value, str) else json.dumps(value)
    return flat


def connect_sops_age(*, runner: SopsRunner | None = None) -> SopsRunner:
    """Wire the SOPS/age CLI as a :class:`SecretDecryptor` (the ``[OPERATOR]`` ignition seam, D81).

    Returns a ``Callable[[bytes], Mapping[str, str]]`` — the exact
    :data:`~mnemosyne.guard.secrets.SecretDecryptor` shape — that decrypts the vault ciphertext via
    ``sops`` and parses the plaintext into a flat map. Injected by ``real_runtime`` into
    :func:`~mnemosyne.guard.secrets.load_secret_broker` at ③-6b. Import-safe with no binary present
    (D126): the ``sops`` process only runs when the returned callable is CALLED, not here. On ANY failure
    (absent binary, non-zero exit, un-parseable plaintext) the callable RAISES — the seam catches it
    and fail-closes to an empty broker (D100), so a decrypt failure never yields a partial or plaintext
    vault. Pass ``runner`` in tests / at ignition to inject the resolved subprocess callable and keep the
    arg-building + parsing exercised without the binary.

    IGNITION NOTE (best-guess CLI, confronted to the real ``sops`` binary at the smoke ``[OPERATOR]``):
    ``sops --decrypt --output-type json <vault>`` prints the decrypted secrets as JSON to stdout, exit 0
    on success and non-zero on failure; the age identity is resolved from the ambient key store (env
    ``SOPS_AGE_KEY_FILE`` / ``~/.config/sops/age/keys.txt``) that the human provisioned OUT-OF-BAND
    (D110) — this adapter never passes a key. Confirm at ignition: (1) the ``--output-type json`` flag
    (so json/yaml/env vaults all decrypt to one parseable object); (2) whether the vault can be fed on
    stdin (``--input-type yaml -``) to skip the temp file in :func:`_sops_argv`; (3) how the age key file
    is located (env var vs default path) so the smoke can verify it is present and OUT-OF-BAND; (4) that
    a wrong / missing key exits non-zero (so the runner raises → the broker fail-closes, not a silent
    empty vault). The default runner shells out with :mod:`subprocess`, capturing stdout and raising on a
    non-zero exit."""
    resolved = runner if runner is not None else _default_sops_runner
    return lambda vault_bytes: _parse_flat_secrets(resolved(_sops_argv(vault_bytes)))


def _default_sops_runner(
    argv: list[str],
) -> bytes:  # pragma: no cover - needs the binary (③ ignition)
    """Run ``argv`` (the ``sops`` decrypt command) and return stdout bytes; raise on a non-zero exit.

    The default :class:`SopsRunner`: a plain :mod:`subprocess` call with ``check=True`` so a decrypt
    failure (missing key, tampered vault) becomes a ``CalledProcessError`` the returned decryptor lets
    propagate — the seam turns that raise into a fail-closed empty broker (D100). Never captures the
    plaintext anywhere but the returned bytes (no logging — a secret must not reach the trail, inv. 22)."""
    import subprocess

    completed = subprocess.run(argv, capture_output=True, check=True)  # noqa: S603 - argv is ours, not shell
    return completed.stdout
