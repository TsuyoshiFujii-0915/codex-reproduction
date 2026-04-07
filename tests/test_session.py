"""Tests for compaction and tool-loop behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.responses_types import ModelResponse
from agent_cli.session import InMemoryModelClient, SessionController


class SessionControllerTest(unittest.TestCase):
    """Covers the agent loop core behavior."""

    def test_session_returns_tool_errors_to_model_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root: Path = Path(tmp_dir)
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
                    keep_last_turns_after_compact=1,
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
                                "name": "read_file",
                                "arguments": "{\"path\": \"missing.txt\"}",
                            }
                        ],
                        response_id="resp-1",
                        raw_response={"id": "resp-1"},
                        events=[],
                    ),
                    ModelResponse(
                        output_items=[
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "recovered"}],
                            }
                        ],
                        response_id="resp-2",
                        raw_response={"id": "resp-2"},
                        events=[],
                    ),
                ]
            )

            controller = SessionController(config=config, model_client=model_client, cwd=root)
            result = controller.run_task(user_input="inspect project")

            self.assertEqual(result.final_text, "recovered")
            second_request_input = model_client.requests[1]["input"]
            tool_outputs = [
                item["output"]
                for item in second_request_input
                if item.get("type") == "function_call_output" and item.get("call_id") == "call-1"
            ]
            self.assertEqual(len(tool_outputs), 1)
            self.assertIn("Tool execution failed", tool_outputs[0])
            self.assertIn("FileNotFoundError", tool_outputs[0])

    def test_session_runs_tool_loop_and_compacts_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root: Path = Path(tmp_dir)
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
                    compact_trigger_tokens=20,
                    keep_last_turns_after_compact=1,
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
                    ),
                    ModelResponse(
                        output_items=[
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "done"}],
                            }
                        ],
                        response_id="resp-2",
                        raw_response={"id": "resp-2"},
                        events=[],
                    ),
                ]
            )

            controller = SessionController(config=config, model_client=model_client, cwd=root)
            result = controller.run_task(user_input="A" * 120)

            self.assertEqual(result.final_text, "done")
            self.assertTrue((root / ".agent" / "compact_summary.md").exists())
            self.assertEqual((root / ".agent" / "plan.json").exists(), True)


if __name__ == "__main__":
    unittest.main()
