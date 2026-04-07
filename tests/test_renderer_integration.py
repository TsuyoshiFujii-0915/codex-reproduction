"""Tests for renderer integration in the session loop."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.renderer import Renderer
from agent_cli.responses_types import ModelResponse
from agent_cli.session import InMemoryModelClient, SessionController


class _RecordingRenderer(Renderer):
    def __init__(self) -> None:
        super().__init__(show_plan=True, show_tool_logs=True, show_diff_summary=True)
        self.plan_messages: list[str] = []
        self.tool_messages: list[str] = []
        self.assistant_messages: list[str] = []

    def show_plan_update(self, message: str) -> None:
        self.plan_messages.append(message)

    def show_tool_log(self, message: str) -> None:
        self.tool_messages.append(message)

    def show_assistant_text(self, message: str) -> None:
        self.assistant_messages.append(message)


class RendererIntegrationTest(unittest.TestCase):
    """Covers renderer calls during a tool loop."""

    def test_session_emits_tool_and_plan_updates(self) -> None:
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
            renderer = _RecordingRenderer()
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

            controller = SessionController(config=config, cwd=root, model_client=model_client, renderer=renderer)
            controller.run_task(user_input="task")

            self.assertTrue(any("update_plan" in message for message in renderer.tool_messages))
            self.assertTrue(any("Start" in message for message in renderer.plan_messages))
            self.assertEqual(renderer.assistant_messages, ["done"])


if __name__ == "__main__":
    unittest.main()
