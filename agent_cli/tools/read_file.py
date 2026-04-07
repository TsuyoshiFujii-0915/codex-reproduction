"""Read file tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_cli.policy import ensure_within_workspace
from agent_cli.tools.base import ToolExecutionContext, ToolResult, truncate_tool_text


class ReadFileTool:
    """Read UTF-8 text files from the workspace."""

    def name(self) -> str:
        return "read_file"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": "read_file",
            "description": "Read a UTF-8 text file from the workspace.",
            "strict": False,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        }

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        path_value: Any = arguments.get("path")
        if not isinstance(path_value, str):
            raise ValueError("path must be a string")
        start_line: int = _coerce_line(value=arguments.get("start_line"), field_name="start_line", default_value=1)
        end_line: int = _coerce_line(value=arguments.get("end_line"), field_name="end_line", default_value=0)
        file_path: Path = ensure_within_workspace(
            workspace_root=context.workspace_root,
            target_path=context.workspace_root / path_value,
        )
        lines: list[str] = file_path.read_text(encoding="utf-8").splitlines()
        selected: list[str] = lines[start_line - 1 :] if end_line == 0 else lines[start_line - 1 : end_line]
        output_text: str = truncate_tool_text("\n".join(selected), 1200)
        return ToolResult(
            ok=True,
            output=output_text,
            exit_code=0,
            metadata={"path": str(file_path), "start_line": start_line, "end_line": end_line},
        )


def _coerce_line(value: Any, field_name: str, default_value: int) -> int:
    if value is None:
        return default_value
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return value
