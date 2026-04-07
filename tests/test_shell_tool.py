"""Tests for shell tool behavior."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentSettings
from agent_cli.policy import CommandPolicy
from agent_cli.tools.base import ToolExecutionContext
from agent_cli.tools.shell import ShellTool


class ShellToolTest(unittest.TestCase):
    """Covers shell output truncation."""

    def test_shell_tool_accepts_single_string_command_item(self) -> None:
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
                arguments={"command": ["pwd"]},
                context=context,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.output, os.fspath(Path(tmp_dir)))

    def test_shell_tool_splits_single_shell_like_argument(self) -> None:
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
                arguments={"command": ["python3 -c \"print('ok')\""]},
                context=context,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.output, "ok")

    def test_shell_tool_executes_single_shell_line_with_pipe(self) -> None:
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
                arguments={"command": ["printf 'a\\nb\\n' | head -1"]},
                context=context,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.output, "a")

    def test_shell_tool_executes_multiple_shell_lines(self) -> None:
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
                        "printf 'first\\n'",
                        "printf 'second\\n'",
                    ]
                },
                context=context,
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.output, "first\nsecond")

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
