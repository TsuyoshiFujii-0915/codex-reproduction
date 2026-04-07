"""Tests for shell workspace path guarding."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentSettings
from agent_cli.policy import CommandPolicy
from agent_cli.tools.base import ToolExecutionContext
from agent_cli.tools.shell import ShellTool


class ShellWorkspaceGuardTest(unittest.TestCase):
    """Covers shell path restrictions in workspace-write mode."""

    def test_shell_rejects_mutating_command_targeting_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir) / "workspace"
            workspace_root.mkdir()
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

            with self.assertRaisesRegex(ValueError, "workspace"):
                ShellTool().execute(arguments={"command": ["touch", "../escaped.txt"]}, context=context)


if __name__ == "__main__":
    unittest.main()

