"""Tests for shell guard against inline interpreter code."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentSettings
from agent_cli.policy import CommandPolicy
from agent_cli.tools.base import ToolExecutionContext
from agent_cli.tools.shell import ShellTool


class ShellInlineCodeGuardTest(unittest.TestCase):
    """Covers blocking inline interpreter execution in workspace-write mode."""

    def test_shell_rejects_python_c_in_workspace_write_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir)
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

            with self.assertRaisesRegex(ValueError, "inline"):
                ShellTool().execute(
                    arguments={"command": ["python3", "-c", "open('/tmp/x', 'w').write('x')"]},
                    context=context,
                )


if __name__ == "__main__":
    unittest.main()

