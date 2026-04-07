"""Tests for shell tool behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentSettings
from agent_cli.policy import CommandPolicy
from agent_cli.tools.base import ToolExecutionContext
from agent_cli.tools.shell import ShellTool


class ShellToolTest(unittest.TestCase):
    """Covers shell output truncation."""

    def test_shell_tool_truncates_large_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tool = ShellTool()
            context = ToolExecutionContext(
                workspace_root=Path(tmp_dir),
                agent_settings=AgentSettings(
                    max_turns=10,
                    compact_trigger_tokens=24000,
                    keep_last_turns_after_compact=4,
                    approval_mode="never",
                    sandbox_mode="workspace-write",
                    workspace_root=Path(tmp_dir),
                    shell="/bin/bash",
                ),
                command_policy=CommandPolicy(),
            )

            result = tool.execute(
                arguments={
                    "command": [
                        "python3",
                        "-c",
                        "for index in range(400): print(f'line-{index}')",
                    ]
                },
                context=context,
            )

            self.assertTrue(result.ok)
            self.assertIn("truncated", result.output)
            self.assertIn("line-0", result.output)
            self.assertIn("line-399", result.output)


if __name__ == "__main__":
    unittest.main()

