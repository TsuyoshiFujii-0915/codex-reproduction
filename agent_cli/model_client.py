"""Minimal Responses API client using the standard library."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import urllib.error
import urllib.request

from agent_cli.responses_types import ModelResponse, StreamEvent


class ResponsesModelClient:
    """HTTP client for OpenAI-compatible Responses APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: int,
        debug_output_path: Path | None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._debug_output_path = debug_output_path

    def create_response(self, request: dict[str, Any]) -> ModelResponse:
        """Create a response using the configured backend."""
        url: str = f"{self._base_url}/responses"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key != "":
            headers["Authorization"] = f"Bearer {self._api_key}"
        encoded_request: bytes = json.dumps(request).encode("utf-8")
        http_request = urllib.request.Request(url=url, data=encoded_request, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                if request["stream"]:
                    return _parse_streaming_response(
                        response=response,
                        debug_output_path=self._debug_output_path,
                    )
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"request failed: {exc}") from exc
        return ModelResponse(
            output_items=list(payload.get("output", [])),
            response_id=str(payload.get("id", "")),
            raw_response=payload,
            events=[],
        )


def _parse_streaming_response(
    response: Any,
    debug_output_path: Path | None = None,
) -> ModelResponse:
    event_name: str = ""
    data_lines: list[str] = []
    output_items: list[dict[str, Any]] = []
    events: list[StreamEvent] = []
    final_response: dict[str, Any] = {}
    raw_lines: list[str] = []
    try:
        for raw_line in response:
            line: str = _decode_sse_line(raw_line=raw_line)
            raw_lines.append(line)
            if line == "":
                final_response = _finalize_sse_event(
                    event_name=event_name,
                    data_lines=data_lines,
                    output_items=output_items,
                    events=events,
                    final_response=final_response,
                )
                event_name = ""
                data_lines = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = _parse_sse_field_value(line=line)
                continue
            if line.startswith("data:"):
                data_lines.append(_parse_sse_field_value(line=line))
        final_response = _finalize_sse_event(
            event_name=event_name,
            data_lines=data_lines,
            output_items=output_items,
            events=events,
            final_response=final_response,
        )
    finally:
        _write_stream_debug_dump(debug_output_path=debug_output_path, raw_lines=raw_lines)
    if final_response == {}:
        raise RuntimeError("stream ended without response.completed")
    return ModelResponse(
        output_items=output_items if output_items != [] else list(final_response.get("output", [])),
        response_id=str(final_response.get("id", "")),
        raw_response=final_response,
        events=events,
    )


def _decode_sse_line(raw_line: bytes) -> str:
    """Decode a single SSE line and normalize line endings.

    Args:
        raw_line: Raw bytes read from the HTTP response iterator.

    Returns:
        The decoded line without trailing CRLF characters.
    """
    return raw_line.decode("utf-8").rstrip("\r\n")


def _parse_sse_field_value(line: str) -> str:
    """Extract an SSE field value while preserving significant spaces.

    Args:
        line: A normalized SSE line in ``field:value`` form.

    Returns:
        The field value with at most one leading separator space removed.
    """
    _, _, value = line.partition(":")
    if value.startswith(" "):
        return value[1:]
    return value


def _finalize_sse_event(
    event_name: str,
    data_lines: list[str],
    output_items: list[dict[str, Any]],
    events: list[StreamEvent],
    final_response: dict[str, Any],
) -> dict[str, Any]:
    """Commit the current SSE event into the parsed response state.

    Args:
        event_name: The current SSE event name.
        data_lines: The collected ``data:`` payload lines for the event.
        output_items: Parsed response output items collected so far.
        events: Parsed stream events collected so far.
        final_response: The most recent completed response payload.

    Returns:
        The updated final response payload.

    Raises:
        RuntimeError: If the stream emitted an ``error`` event.
    """
    if event_name == "" and data_lines == []:
        return final_response
    data_text: str = "\n".join(data_lines)
    if data_text == "[DONE]":
        return final_response
    data: dict[str, Any] = json.loads(data_text) if data_text != "" else {}
    resolved_event_name: str = event_name or str(data.get("type", ""))
    if resolved_event_name == "":
        return final_response
    if resolved_event_name == "error":
        message: Any = data.get("message", data)
        raise RuntimeError(f"stream error: {message}")
    events.append(StreamEvent(event=resolved_event_name, data=data))
    if resolved_event_name == "response.output_item.done":
        output_items.append(data["item"])
    if resolved_event_name == "response.completed":
        return data["response"]
    return final_response


def _write_stream_debug_dump(debug_output_path: Path | None, raw_lines: list[str]) -> None:
    """Persist raw streaming lines for debugging when requested.

    Args:
        debug_output_path: Destination file path for the raw stream dump.
        raw_lines: Normalized raw lines read from the SSE response.
    """
    if debug_output_path is None:
        return
    debug_output_path.parent.mkdir(parents=True, exist_ok=True)
    debug_output_path.write_text("\n".join(raw_lines) + ("\n" if raw_lines != [] else ""), encoding="utf-8")
