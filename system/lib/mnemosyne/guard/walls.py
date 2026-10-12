"""Record policy-wall outcomes without silent failure."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ..ports import GuardRequest, Ruling

_REPO_ROOT: Final = Path(__file__).resolve().parents[4]
DEFAULT_WALLS_PATH: Final = _REPO_ROOT / "system" / "state" / "walls.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class WallLedger:
    """Append-only, best-effort log of every non-``ALLOW`` :class:`~mnemosyne.ports.guard.Ruling`.

    Fail-open by design (see module docstring): :meth:`record` swallows any exception rather than
    let a down or full disk change what the Guard decided. This is a visibility tool, not a
    security boundary - reads degrade the same way (a corrupt line is skipped, never fatal)."""

    __slots__ = ("_path",)

    def __init__(self, path: Path | str = DEFAULT_WALLS_PATH) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, request: "GuardRequest", ruling: "Ruling") -> None:
        """Append one refusal. NEVER raises - a failure here must not touch the Guard's verdict."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(
                {
                    "at": _utcnow_iso(),
                    "effect": request.effect.value,
                    "subject": str(request.subject),
                    "target": request.target or "",
                    "descriptor": request.descriptor,
                    "decision": ruling.decision.value,
                    "reason": ruling.reason,
                    "tier": ruling.tier.value if ruling.tier is not None else "",
                },
                ensure_ascii=False,
            )
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        except Exception:  # noqa: BLE001 - best-effort (D111): the Guard's verdict never depends on this
            return

    def read_all(self) -> tuple[dict[str, str], ...]:
        """Every recorded refusal, in append order. Fail-open on read too: a missing file is
        empty, and a corrupt line is skipped rather than raised (this is a report, not a gate)."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return ()
        entries: list[dict[str, str]] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
        return tuple(entries)
