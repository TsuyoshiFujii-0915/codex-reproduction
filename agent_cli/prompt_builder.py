"""Prompt builder for stateless Responses API requests."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any


BASE_INSTRUCTIONS = "\n".join(
    [
        "You are a pragmatic CLI coding agent.",
        "Use tools when needed and stop when you have a final assistant message.",
        "Keep history stateless and preserve prior items in order.",
    ]
)


def build_permissions_message(agent_settings: Any) -> dict[str, Any]:
    """Build the permissions developer message."""
    writable_root: Path = Path(agent_settings.workspace_root).resolve()
    text: str = "\n".join(
        [
            "<permissions_instructions>",
            f"sandbox_mode={agent_settings.sandbox_mode}",
            f"approval_mode={agent_settings.approval_mode}",
            "writable_roots:",
            f"- {writable_root}",
            "",
            "Rules:",
            "- Do not write outside writable_roots.",
            "- Ask before destructive operations.",
            "- Ask before network-related shell commands.",
            "- Prefer reading before editing.",
            "</permissions_instructions>",
        ]
    )
    return {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": text}]}


def build_environment_message(agent_settings: Any, cwd: Path) -> dict[str, Any]:
    """Build the environment context user message."""
    text: str = "\n".join(
        [
            "<environment_context>",
            f"cwd={cwd.resolve()}",
            f"shell={agent_settings.shell}",
            f"platform={platform.system().lower()}",
            f"sandbox_mode={agent_settings.sandbox_mode}",
            f"approval_mode={agent_settings.approval_mode}",
            "</environment_context>",
        ]
    )
    return {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}


def build_request(
    model_name: str,
    stream: bool,
    store: bool,
    tools: list[dict[str, Any]],
    agent_settings: Any,
    cwd: Path,
    agents_text: str,
    history_items: list[dict[str, Any]],
    user_input: str,
) -> dict[str, Any]:
    """Build a Responses API request."""
    sorted_tools: list[dict[str, Any]] = sorted(tools, key=lambda item: str(item["name"]))
    input_items: list[dict[str, Any]] = [build_permissions_message(agent_settings)]
    if agents_text != "":
        input_items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": agents_text}]})
    input_items.append(build_environment_message(agent_settings, cwd))
    input_items.extend(history_items)
    if user_input != "":
        input_items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": user_input}]})
    return {
        "model": model_name,
        "instructions": BASE_INSTRUCTIONS,
        "tools": sorted_tools,
        "input": input_items,
        "stream": stream,
        "store": store,
        "parallel_tool_calls": False,
    }
