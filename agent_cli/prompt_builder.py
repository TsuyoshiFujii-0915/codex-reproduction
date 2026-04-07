"""Prompt builder for stateless Responses API requests."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BASE_INSTRUCTIONS = "\n".join(
    [
        "You are a pragmatic CLI coding agent.",
        "Use tools when needed and stop when you have a final assistant message.",
        "Keep history stateless and preserve prior items in order.",
    ]
)


def build_permissions_text(agent_settings: Any) -> str:
    """Build the permissions instructions text.

    Args:
        agent_settings: Agent runtime settings.

    Returns:
        Permissions instructions text.
    """
    writable_root: Path = Path(agent_settings.workspace_root).resolve()
    return "\n".join(
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


def build_permissions_message(agent_settings: Any) -> dict[str, Any]:
    """Build the permissions developer message.

    Args:
        agent_settings: Agent runtime settings.

    Returns:
        Responses API message item.
    """
    text: str = build_permissions_text(agent_settings=agent_settings)
    return {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": text}]}


def build_environment_message(agent_settings: Any, cwd: Path) -> dict[str, Any]:
    """Build the environment context user message.

    Args:
        agent_settings: Agent runtime settings.
        cwd: Current working directory.

    Returns:
        Responses API message item.
    """
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


def uses_openai_native_request_format(base_url: str) -> bool:
    """Determine whether to use the native OpenAI request shape.

    Args:
        base_url: Configured Responses API base URL.

    Returns:
        ``True`` when the request targets the official OpenAI API host.
    """
    parsed = urlparse(base_url)
    return parsed.hostname == "api.openai.com"


def build_instructions(base_url: str, agent_settings: Any) -> str:
    """Build backend-specific instructions text.

    Args:
        base_url: Configured Responses API base URL.
        agent_settings: Agent runtime settings.

    Returns:
        The instructions string sent to the backend.
    """
    if uses_openai_native_request_format(base_url=base_url):
        return BASE_INSTRUCTIONS
    return "\n\n".join([BASE_INSTRUCTIONS, build_permissions_text(agent_settings=agent_settings)])


def build_request(
    base_url: str,
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
    """Build a Responses API request.

    Args:
        base_url: Configured Responses API base URL.
        model_name: Target model identifier.
        stream: Whether to request SSE streaming.
        store: Whether provider-side storage is enabled.
        tools: Tool schemas available to the model.
        agent_settings: Agent runtime settings.
        cwd: Current working directory.
        agents_text: Loaded AGENTS instructions text.
        history_items: Existing conversation items.
        user_input: Current user prompt for the turn.

    Returns:
        Responses API request payload.
    """
    sorted_tools: list[dict[str, Any]] = sorted(tools, key=lambda item: str(item["name"]))
    input_items: list[dict[str, Any]] = []
    if uses_openai_native_request_format(base_url=base_url):
        input_items.append(build_permissions_message(agent_settings=agent_settings))
    if agents_text != "":
        input_items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": agents_text}]})
    input_items.append(build_environment_message(agent_settings, cwd))
    input_items.extend(history_items)
    if user_input != "":
        input_items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": user_input}]})
    return {
        "model": model_name,
        "instructions": build_instructions(base_url=base_url, agent_settings=agent_settings),
        "tools": sorted_tools,
        "input": input_items,
        "stream": stream,
        "store": store,
        "parallel_tool_calls": False,
    }
