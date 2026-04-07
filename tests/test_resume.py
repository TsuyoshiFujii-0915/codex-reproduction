"""Tests for session resume support."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.responses_types import ModelResponse
from agent_cli.session import InMemoryModelClient, SessionController


class ResumeTest(unittest.TestCase):
    """Covers session persistence and resume."""

    def test_resume_uses_transcript_history_without_snapshot(self) -> None:
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
                    compact_trigger_tokens=10_000,
                    keep_last_turns_after_compact=2,
                    approval_mode="never",
                    sandbox_mode="workspace-write",
                    workspace_root=root,
                    shell="/bin/bash",
                ),
                ui=UISettings(show_plan=True, show_tool_logs=True, show_diff_summary=True),
                files=FilesSettings(project_memory_dir=".agent"),
            )
            first_client = InMemoryModelClient(
                responses=[
                    ModelResponse(
                        output_items=[
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "first"}],
                            }
                        ],
                        response_id="resp-1",
                        raw_response={"id": "resp-1"},
                        events=[],
                    )
                ]
            )
            first_controller = SessionController(config=config, model_client=first_client, cwd=root)
            first_result = first_controller.run_task(user_input="initial prompt")
            snapshot_path = root / ".agent" / "sessions" / f"{first_result.session_id}.json"
            snapshot_path.unlink()

            resumed_client = InMemoryModelClient(
                responses=[
                    ModelResponse(
                        output_items=[
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "second"}],
                            }
                        ],
                        response_id="resp-2",
                        raw_response={"id": "resp-2"},
                        events=[],
                    )
                ]
            )
            resumed_controller = SessionController.resume(
                config=config,
                cwd=root,
                model_client=resumed_client,
                session_id=first_result.session_id,
            )

            resumed_result = resumed_controller.run_task(user_input="follow up")

            self.assertEqual(resumed_result.final_text, "second")
            latest_session = (root / ".agent" / "latest_session.txt").read_text(encoding="utf-8").strip()
            self.assertEqual(latest_session, first_result.session_id)
            resumed_request = resumed_client.requests[0]
            serialized_input = str(resumed_request["input"])
            self.assertIn("initial prompt", serialized_input)
            self.assertIn("first", serialized_input)
            self.assertIn("follow up", serialized_input)

    def test_resume_uses_compact_summary_and_recent_raw_items(self) -> None:
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
            first_client = InMemoryModelClient(
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
                                "content": [{"type": "output_text", "text": "first"}],
                            }
                        ],
                        response_id="resp-2",
                        raw_response={"id": "resp-2"},
                        events=[],
                    ),
                ]
            )
            first_controller = SessionController(config=config, model_client=first_client, cwd=root)
            first_result = first_controller.run_task(user_input="initial prompt")
            snapshot_path = root / ".agent" / "sessions" / f"{first_result.session_id}.json"
            snapshot_path.unlink()

            resumed_client = InMemoryModelClient(
                responses=[
                    ModelResponse(
                        output_items=[
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "second"}],
                            }
                        ],
                        response_id="resp-3",
                        raw_response={"id": "resp-3"},
                        events=[],
                    )
                ]
            )

            resumed_controller = SessionController.resume(
                config=config,
                cwd=root,
                model_client=resumed_client,
                session_id=first_result.session_id,
            )
            resumed_controller.run_task(user_input="follow up")

            serialized_input = str(resumed_client.requests[0]["input"])
            self.assertIn("Compact Summary", serialized_input)
            self.assertIn("first", serialized_input)
            self.assertIn("follow up", serialized_input)


if __name__ == "__main__":
    unittest.main()
