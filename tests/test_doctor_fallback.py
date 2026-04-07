"""Tests for doctor fallback behavior."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from agent_cli.cli import _run_doctor
from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def read(self) -> bytes:
        return b'{"id":"resp-test","output":[]}'


class DoctorFallbackTest(unittest.TestCase):
    """Covers fallback to /responses when /models is unavailable."""

    def test_doctor_falls_back_to_responses_probe(self) -> None:
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

            def _fake_urlopen(request: object, timeout: int) -> _FakeResponse:
                del timeout
                full_url = getattr(request, "full_url", request)
                if str(full_url).endswith("/models"):
                    raise URLError("models unavailable")
                return _FakeResponse(status=200)

            with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
                with patch("sys.stdout", output):
                    exit_code = _run_doctor(config=config)

            self.assertEqual(exit_code, 0)
            self.assertIn("responses_status=200", output.getvalue())


if __name__ == "__main__":
    unittest.main()

