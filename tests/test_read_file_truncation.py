"""Tests for read_file truncation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentSettings
from agent_cli.policy import CommandPolicy
from agent_cli.tools.base import ToolExecutionContext
from agent_cli.tools.read_file import ReadFileTool


class ReadFileTruncationTest(unittest.TestCase):
    """Covers truncation of large file reads."""

    def test_read_file_truncates_large_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir)
            file_path = workspace_root / "large.txt"
            file_path.write_text("\n".join(f"line-{index}" for index in range(200)), encoding="utf-8")
            context = ToolExecutionContext(
                workspace_root=workspace_root,
                agent_settings=AgentSettings(
                    max_turns=4,
                    compact_trigger_tokens=24000,
                    keep_last_turns_after_compact=4,
                    approval_mode="never",
                    sandbox_mode="workspace-write",
                    workspace_root=workspace_root,
                    shell="/bin/bash",
                ),
                command_policy=CommandPolicy(),
            )

            result = ReadFileTool().execute(arguments={"path": "large.txt"}, context=context)

            self.assertIn("truncated", result.output)
            self.assertIn("line-0", result.output)
            self.assertIn("line-199", result.output)


if __name__ == "__main__":
    unittest.main()

