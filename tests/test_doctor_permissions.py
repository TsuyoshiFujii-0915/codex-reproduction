"""Tests for doctor permission diagnostics."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_cli.cli import _run_doctor
from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class DoctorPermissionsTest(unittest.TestCase):
    """Covers workspace and memory root diagnostics."""

    def test_doctor_reports_workspace_and_memory_root_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config = AgentConfig(
                model=ModelSettings(
                    base_url="http://localhost:1234/v1",
                    model="test-model",
                    api_key_env="OPENAI_API_KEY",
                    timeout_seconds=120,
                    stream=False,
                    store=False,
                ),
                agent=AgentSettings(
                    max_turns=4,
                    compact_trigger_tokens=24000,
                    keep_last_turns_after_compact=4,
                    approval_mode="never",
                    sandbox_mode="workspace-write",
                    workspace_root=root,
                    shell="/bin/bash",
                ),
                ui=UISettings(show_plan=True, show_tool_logs=True, show_diff_summary=True),
                files=FilesSettings(project_memory_dir=".agent"),
            )
            output = io.StringIO()
            with patch("urllib.request.urlopen", return_value=_FakeResponse(status=200)):
                with patch("sys.stdout", output):
                    exit_code = _run_doctor(config=config)

            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("workspace_exists=True", rendered)
            self.assertIn("project_memory_dir_parent_writable=True", rendered)


if __name__ == "__main__":
    unittest.main()
