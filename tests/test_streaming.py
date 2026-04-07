"""Tests for streaming rendering behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.renderer import Renderer
from agent_cli.responses_types import ModelResponse, StreamEvent
from agent_cli.session import InMemoryModelClient, SessionController


class _StreamRecordingRenderer(Renderer):
    def __init__(self) -> None:
        super().__init__(show_plan=False, show_tool_logs=False, show_diff_summary=True)
        self.stream_chunks: list[str] = []
        self.final_messages: list[str] = []

    def show_stream_text(self, chunk: str) -> None:
        self.stream_chunks.append(chunk)

    def show_assistant_text(self, message: str) -> None:
        self.final_messages.append(message)


class StreamingTest(unittest.TestCase):
    """Covers streaming event rendering."""

    def test_streaming_events_emit_delta_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root: Path = Path(tmp_dir)
            config = AgentConfig(
                model=ModelSettings(
                    base_url="http://localhost:1234/v1",
                    model="test-model",
                    api_key_env="OPENAI_API_KEY",
                    timeout_seconds=120,
                    stream=True,
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
            renderer = _StreamRecordingRenderer()
            model_client = InMemoryModelClient(
                responses=[
                    ModelResponse(
                        output_items=[
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "done"}],
                            }
                        ],
                        response_id="resp-1",
                        raw_response={"id": "resp-1"},
                        events=[
                            StreamEvent(event="response.output_text.delta", data={"delta": "do"}),
                            StreamEvent(event="response.output_text.delta", data={"delta": "ne"}),
                        ],
                    )
                ]
            )
            controller = SessionController(config=config, cwd=root, model_client=model_client, renderer=renderer)

            controller.run_task(user_input="prompt")

            self.assertEqual(renderer.stream_chunks, ["do", "ne"])


if __name__ == "__main__":
    unittest.main()
