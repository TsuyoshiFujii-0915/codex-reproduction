"""Base tool types and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from agent_cli.config import AgentSettings
from agent_cli.policy import CommandPolicy


@dataclass(frozen=True)
class ToolExecutionContext:
    """Carries shared context required by tool execution."""

    workspace_root: Path
    agent_settings: AgentSettings
    command_policy: CommandPolicy
    memory_root: Path | None = None
    current_goal: str | None = None
    approval_handler: Callable[[str], bool] | None = None


@dataclass(frozen=True)
class ToolResult:
    """Represents the result of a tool execution."""

    ok: bool
    output: str
    exit_code: int | None
    metadata: dict[str, Any]


class ToolProtocol(Protocol):
    """Protocol implemented by tool classes."""

    def name(self) -> str:
        """Return the tool name."""

    def schema(self) -> dict[str, Any]:
        """Return the JSON schema for the tool."""

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        """Runs a tool with JSON-like arguments."""


def truncate_tool_text(text: str, limit: int) -> str:
    """Truncate oversized tool text while keeping head and tail."""
    lines: list[str] = text.splitlines()
    if len(text) <= limit and len(lines) <= 120:
        return text
    head_lines: list[str] = lines[:6]
    tail_lines: list[str] = lines[-6:]
    omitted_line_count: int = max(len(lines) - len(head_lines) - len(tail_lines), 0)
    summary: list[str] = head_lines
    summary.append(f"... truncated {omitted_line_count} middle lines ...")
    summary.extend(tail_lines)
    return "\n".join(summary)
