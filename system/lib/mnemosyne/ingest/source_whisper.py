"""_WhisperKitBackend — the voice → text reader over a LOCAL WhisperKit server (AV1 / D115 / D114).

"Voice is just another source" (AV1): audio is the SAME :class:`~mnemosyne.ports.source.SourceReader`
port as a document, split only at the MIME aiguillage. WhisperKit (D115 / D121-E4; ``oss_registry.md``)
is NOT a Python import — it is a native Swift binary run as a **LOCAL server with an OpenAI-compatible
audio API** (registry §0 / E4, D104 / D114: a binary back-end behind a prise, never rewritten). So this
adapter is an HTTP CLIENT to the machine's transcription endpoint (``POST /v1/audio/transcriptions``,
multipart audio bytes → JSON ``{"text": ...}``), speaking only ``urllib`` (stdlib — no ``httpx`` in the
deps, ``pyproject.toml``). There is no importable ``whisperkit`` module to encapsulate; the server is
an ``[OPERATOR]`` install/launch gesture, and the CLIENT is what talks to it.

Everything here is ``# pragma: no cover``: it needs the running server, absent in CI, so it is exercised
only by the 1-click smoke at ③ ignition. A drift (URL, field name, multipart shape) is non-catastrophic —
the ③-4a benne net (D85) preserves the raw audio and re-extracts, so a broken read degrades to a
low-fidelity flag, never a lost datum. All LOCAL (D27 / D66). Code & docstrings English (D117).

Decisions: AV1 (voice as a source) · D115 / D121-E4 (WhisperKit) · D114 / D104 (binary behind a prise) ·
D125-B5 (SourceReader) · D126 (import-safe, brick-free suite) · D100-3 (audio untrusted, local) · D85.
"""

from __future__ import annotations

from ..ports import Source, SourceReader

#: Default local WhisperKit endpoint — an OpenAI-compatible audio server on the loopback (LOCAL only,
#: D27 / D66). Host + port are an ``[OPERATOR]`` config at ignition; the path mirrors the OpenAI audio API.
_DEFAULT_BASE_URL = "http://127.0.0.1:50060"
_TRANSCRIBE_PATH = "/v1/audio/transcriptions"
_DEFAULT_MODEL = "whisper-large-v3"
_TIMEOUT_S = 300.0  # a long recording may take minutes to transcribe locally


def connect_whisperkit(  # pragma: no cover - needs the local server (③ ignition)
    *, base_url: str = _DEFAULT_BASE_URL, model: str = _DEFAULT_MODEL
) -> SourceReader:
    """Wire a client to the LOCAL WhisperKit audio server as a :class:`SourceReader` (AV1, ``[OPERATOR]``).

    No brick to import — WhisperKit is a local OpenAI-compatible server (D114 / D115), so this returns a
    client bound to ``base_url``, wired by :func:`~mnemosyne.runtime.bootstrap.real_runtime` for
    ``audio/`` sources. The 1-click smoke confronts it with the real endpoint at ignition; a drift
    degrades to a low-fidelity flag (raw audio preserved, D85), never a lost datum.

    ALLUMAGE NOTE (best-guess API, confronted to the real WhisperKit server at the smoke ``[OPERATOR]``):
    an OpenAI-compatible ``POST {base_url}/v1/audio/transcriptions`` with a ``multipart/form-data`` body
    carrying the audio ``file`` and a ``model`` field, responding ``200`` with JSON ``{"text": "..."}``.
    Confirm at ignition: the exact host/port WhisperKit binds, the endpoint path, the ``model`` id it
    expects, and the response field (``text``). ``urllib`` (stdlib) is the client — no HTTP dep is
    pulled in for one endpoint."""
    return _WhisperKitBackend(base_url=base_url, model=model)


class _WhisperKitBackend:  # pragma: no cover - real HTTP client (③-4b ignition, smoke-tested)
    """HTTP client for the local WhisperKit transcription endpoint (AV1 / D114).

    Posts a source's audio bytes as multipart to ``base_url + /v1/audio/transcriptions`` and returns the
    transcribed text. Speaks only ``urllib`` (stdlib), imported LAZILY so this module is import-safe
    without a running server (D126). Runs LOCAL on untrusted audio (D100-3); a network / server failure
    propagates to the single ③-4a benne net (D85), which preserves the raw audio — this client never
    swallows a failure into a false empty transcription."""

    __slots__ = ("_base_url", "_model")

    def __init__(self, *, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def read(self, source: Source) -> str:
        import json
        import urllib.request  # stdlib client, lazy (no HTTP dep for one endpoint)

        body, content_type = _multipart(
            file_field="file",
            filename=source.ref or "audio",
            file_bytes=source.data,
            fields={"model": self._model},
        )
        request = urllib.request.Request(
            self._base_url + _TRANSCRIBE_PATH,
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload["text"]


def _multipart(
    *, file_field: str, filename: str, file_bytes: bytes, fields: dict[str, str]
) -> tuple[bytes, str]:
    """Encode one file + text fields as ``multipart/form-data`` (stdlib only) → (body, content-type).

    A minimal hand-rolled encoder so no HTTP dependency is added for a single endpoint. The boundary is
    a per-request RANDOM token (RFC 7578, 128 bits): the audio ``file_bytes`` are UNTRUSTED (D100-3), so
    a fixed / guessable delimiter an adversarial payload could contain — forging an extra part — is
    refused by CONSTRUCTION, not by a probabilistic bet (③-4b audit MINEUR-1). Pure stdlib, so it is
    unit-tested without the WhisperKit server (unlike the surrounding ``# pragma: no cover`` client)."""
    import secrets

    boundary = f"----Mnemosyne{secrets.token_hex(16)}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(value.encode("utf-8"))
    lines.append(f"--{boundary}".encode("utf-8"))
    lines.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'.encode(
            "utf-8"
        )
    )
    lines.append(b"Content-Type: application/octet-stream")
    lines.append(b"")
    lines.append(file_bytes)
    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")
    body = b"\r\n".join(lines)
    return body, f"multipart/form-data; boundary={boundary}"
