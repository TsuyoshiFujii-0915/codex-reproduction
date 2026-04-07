"""Write file tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_cli.approval import ensure_approved
from agent_cli.policy import ensure_within_workspace
from agent_cli.tools.base import ToolExecutionContext, ToolResult


class WriteFileTool:
    """Write UTF-8 text files inside the workspace."""

    def name(self) -> str:
        return "write_file"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": "write_file",
            "description": "Write a UTF-8 text file within the workspace.",
            "strict": False,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["overwrite", "append"]},
                },
                "required": ["path", "content"],
            },
        }

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        path_value: Any = arguments.get("path")
        content_value: Any = arguments.get("content")
        mode_value: Any = arguments.get("mode", "overwrite")
        if not isinstance(path_value, str):
            raise ValueError("path must be a string")
        if not isinstance(content_value, str):
            raise ValueError("content must be a string")
        if mode_value not in {"overwrite", "append"}:
            raise ValueError("mode must be overwrite or append")
        if context.agent_settings.sandbox_mode == "read-only":
            raise ValueError("writes are not allowed in read-only mode")
        if "\x00" in content_value:
            raise ValueError("binary file writes are not supported")
        if context.agent_settings.approval_mode == "always":
            ensure_approved(
                message=f"approval required for file write: {path_value}",
                approval_handler=context.approval_handler,
            )
        if (
            context.agent_settings.approval_mode == "on-request"
            and mode_value == "overwrite"
            and len(content_value.splitlines()) > 1000
        ):
            ensure_approved(
                message=f"approval required for large file write: {path_value}",
                approval_handler=context.approval_handler,
            )
        file_path: Path = ensure_within_workspace(
            workspace_root=context.workspace_root,
            target_path=context.workspace_root / path_value,
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if mode_value == "overwrite":
            file_path.write_text(content_value, encoding="utf-8")
        else:
            with file_path.open("a", encoding="utf-8") as handle:
                handle.write(content_value)
        return ToolResult(
            ok=True,
            output=f"wrote {len(content_value)} bytes",
            exit_code=0,
            metadata={"path": str(file_path), "mode": mode_value},
        )
