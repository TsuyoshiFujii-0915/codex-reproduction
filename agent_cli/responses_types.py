"""Typed runtime objects for model responses and tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class StreamEvent:
    """One parsed SSE event."""

    event: str
    data: JsonObject


@dataclass(frozen=True)
class ModelResponse:
    """Normalized model response."""

    output_items: list[JsonObject]
    response_id: str
    raw_response: JsonObject
    events: list[StreamEvent]


@dataclass(frozen=True)
class RunResult:
    """High-level result returned by the session controller."""

    final_text: str
    touched_files: list[str]
    session_id: str
