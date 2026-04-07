"""Transcript event storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_transcript_event(path: Path, kind: str, data: dict[str, Any]) -> None:
    """Appends one JSONL transcript event.

    Args:
        path: Transcript path.
        kind: Event kind.
        data: Event payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "data": data,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_transcript_events(path: Path) -> list[dict[str, Any]]:
    """Read transcript events from a JSONL file."""
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "":
            continue
        payload: Any = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("transcript event must be an object")
        events.append(payload)
    return events
