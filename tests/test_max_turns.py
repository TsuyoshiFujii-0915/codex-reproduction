"""Tests for max-turn handling."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.responses_types import ModelResponse
from agent_cli.session import InMemoryModelClient, SessionController


class MaxTurnsTest(unittest.TestCase):
    """Covers graceful stop when max turns are reached."""

    def test_max_turns_returns_partial_result_and_saves_progress(self) -> None:
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
                    max_turns=1,
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
            model_client = InMemoryModelClient(
                responses=[
                    ModelResponse(
                        output_items=[
                            {
                                "type": "function_call",
                                "call_id": "call-1",
                                "name": "update_plan",
                                "arguments": "{\"plan\": [\"Inspect\"], \"explanation\": \"Start\"}",
                            }
                        ],
                        response_id="resp-1",
                        raw_response={"id": "resp-1"},
                        events=[],
                    )
                ]
            )
            controller = SessionController(config=config, cwd=root, model_client=model_client)

            result = controller.run_task(user_input="keep going")

            self.assertEqual(result.final_text, "")
            progress_text = (root / ".agent" / "progress.md").read_text(encoding="utf-8")
            self.assertIn("Max turns reached", progress_text)
            self.assertIn("Resume session", progress_text)


if __name__ == "__main__":
    unittest.main()

