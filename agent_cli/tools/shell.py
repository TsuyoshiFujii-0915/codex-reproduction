"""Shell execution tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import subprocess

from agent_cli.approval import ensure_approved
from agent_cli.policy import ensure_within_workspace
from agent_cli.tools.base import ToolExecutionContext, ToolResult, truncate_tool_text


class ShellTool:
    """Run shell commands inside the workspace."""

    def name(self) -> str:
        return "shell"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": "shell",
            "description": "Run a shell command in the workspace and return stdout, stderr, exit_code.",
            "strict": False,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "array", "items": {"type": "string"}},
                    "workdir": {"type": "string"},
                    "timeout_ms": {"type": "integer"},
                },
                "required": ["command"],
            },
        }

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        command: list[str] = _require_string_list(value=arguments.get("command"), field_name="command")
        workdir_value: Any = arguments.get("workdir", ".")
        timeout_value: Any = arguments.get("timeout_ms", 30_000)
        if not isinstance(workdir_value, str):
            raise ValueError("workdir must be a string")
        if not isinstance(timeout_value, int):
            raise ValueError("timeout_ms must be an integer")
        self._validate_command(command=command, context=context)
        workdir: Path = ensure_within_workspace(
            workspace_root=context.workspace_root,
            target_path=context.workspace_root / workdir_value,
        )
        completed = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_value / 1000,
            check=False,
        )
        combined_output: str = "\n".join(
            [part for part in [completed.stdout.rstrip("\n"), completed.stderr.rstrip("\n")] if part != ""]
        )
        truncated_output: str = truncate_tool_text(text=combined_output, limit=1200)
        return ToolResult(
            ok=completed.returncode == 0,
            output=truncated_output,
            exit_code=completed.returncode,
            metadata={"workdir": str(workdir), "command": context.command_policy.format_command(command)},
        )

    def _validate_command(self, command: list[str], context: ToolExecutionContext) -> None:
        if context.agent_settings.sandbox_mode == "read-only":
            readonly_commands: set[str] = {"pwd", "ls", "find", "cat", "sed", "grep", "git"}
            if command[0] not in readonly_commands:
                raise ValueError(f"command is not allowed in read-only mode: {command[0]}")
        self._validate_inline_execution(command=command, context=context)
        self._validate_mutating_targets(command=command, context=context)
        if context.agent_settings.approval_mode == "always":
            ensure_approved(
                message=f"approval required for shell command: {context.command_policy.format_command(command)}",
                approval_handler=context.approval_handler,
            )
            return
        if (
            context.agent_settings.approval_mode == "on-request"
            and context.command_policy.requires_approval(command)
        ):
            ensure_approved(
                message=f"approval required for shell command: {context.command_policy.format_command(command)}",
                approval_handler=context.approval_handler,
            )

    def _validate_inline_execution(self, command: list[str], context: ToolExecutionContext) -> None:
        if context.agent_settings.sandbox_mode != "workspace-write":
            return
        inline_interpreters: set[str] = {"python", "python3", "bash", "sh", "zsh", "node", "perl", "ruby"}
        if command[0] not in inline_interpreters:
            return
        for index, argument in enumerate(command[1:], start=1):
            if argument not in {"-c", "-e"}:
                continue
            code_text: str = command[index + 1] if index + 1 < len(command) else ""
            suspicious_patterns: tuple[str, ...] = ("/tmp/", "../", "/etc/", "/var/", "open(", "write_text(", "mkdir(")
            if any(pattern in code_text for pattern in suspicious_patterns):
                raise ValueError("inline interpreter execution is not allowed in workspace-write mode")
            return

    def _validate_mutating_targets(self, command: list[str], context: ToolExecutionContext) -> None:
        mutating_commands: dict[str, slice] = {
            "touch": slice(1, None),
            "mkdir": slice(1, None),
            "rm": slice(1, None),
            "mv": slice(1, None),
            "cp": slice(1, None),
        }
        target_slice: slice | None = mutating_commands.get(command[0])
        if target_slice is None:
            return
        for argument in command[target_slice]:
            if argument.startswith("-"):
                continue
            ensure_within_workspace(
                workspace_root=context.workspace_root,
                target_path=context.workspace_root / argument,
            )


def _require_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return value
