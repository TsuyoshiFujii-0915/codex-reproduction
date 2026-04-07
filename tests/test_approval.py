"""Tests for approval and sandbox behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.approval import ApprovalRequiredError
from agent_cli.config import AgentSettings
from agent_cli.policy import CommandPolicy
from agent_cli.tools.base import ToolExecutionContext
from agent_cli.tools.shell import ShellTool
from agent_cli.tools.write_file import WriteFileTool


class ApprovalTest(unittest.TestCase):
    """Covers approval and sandbox enforcement."""

    def test_shell_requires_approval_for_dangerous_command_in_on_request_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            context = ToolExecutionContext(
                workspace_root=Path(tmp_dir),
                agent_settings=AgentSettings(
                    max_turns=4,
                    compact_trigger_tokens=24000,
                    keep_last_turns_after_compact=4,
                    approval_mode="on-request",
                    sandbox_mode="workspace-write",
                    workspace_root=Path(tmp_dir),
                    shell="/bin/bash",
                ),
                command_policy=CommandPolicy(),
            )
            with self.assertRaises(ApprovalRequiredError):
                ShellTool().execute(arguments={"command": ["rm", "-rf", "target"]}, context=context)

    def test_write_file_is_blocked_in_read_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            context = ToolExecutionContext(
                workspace_root=Path(tmp_dir),
                agent_settings=AgentSettings(
                    max_turns=4,
                    compact_trigger_tokens=24000,
                    keep_last_turns_after_compact=4,
                    approval_mode="never",
                    sandbox_mode="read-only",
                    workspace_root=Path(tmp_dir),
                    shell="/bin/bash",
                ),
                command_policy=CommandPolicy(),
            )
            with self.assertRaisesRegex(ValueError, "read-only"):
                WriteFileTool().execute(
                    arguments={"path": "note.txt", "content": "hello", "mode": "overwrite"},
                    context=context,
                )


if __name__ == "__main__":
    unittest.main()

