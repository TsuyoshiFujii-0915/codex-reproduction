"""Minimal Responses API client using the standard library."""

from __future__ import annotations

from typing import Any
import json
import urllib.error
import urllib.request

from agent_cli.responses_types import ModelResponse, StreamEvent


class ResponsesModelClient:
    """HTTP client for OpenAI-compatible Responses APIs."""

    def __init__(self, base_url: str, api_key: str, timeout_seconds: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

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
                    return _parse_streaming_response(response=response)
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"request failed: {exc}") from exc
        return ModelResponse(
            output_items=list(payload.get("output", [])),
            response_id=str(payload.get("id", "")),
            raw_response=payload,
            events=[],
        )


def _parse_streaming_response(response: Any) -> ModelResponse:
    event_name: str = ""
    data_lines: list[str] = []
    output_items: list[dict[str, Any]] = []
    events: list[StreamEvent] = []
    final_response: dict[str, Any] = {}
    for raw_line in response:
        line: str = raw_line.decode("utf-8").rstrip("\n")
        if line == "":
            if event_name != "":
                data_text: str = "\n".join(data_lines)
                data: dict[str, Any] = json.loads(data_text) if data_text != "" else {}
                if event_name == "error":
                    message: Any = data.get("message", data)
                    raise RuntimeError(f"stream error: {message}")
                events.append(StreamEvent(event=event_name, data=data))
                if event_name == "response.output_item.done":
                    output_items.append(data["item"])
                if event_name == "response.completed":
                    final_response = data["response"]
                event_name = ""
                data_lines = []
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
    if final_response == {}:
        raise RuntimeError("stream ended without response.completed")
    return ModelResponse(
        output_items=output_items if output_items != [] else list(final_response.get("output", [])),
        response_id=str(final_response.get("id", "")),
        raw_response=final_response,
        events=events,
    )
