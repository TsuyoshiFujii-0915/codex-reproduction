"""Tests for request construction behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.responses_types import ModelResponse
from agent_cli.session import InMemoryModelClient, SessionController


class RequestBuildingTest(unittest.TestCase):
    """Covers prompt construction edge cases."""

    def test_current_user_prompt_is_not_duplicated_in_request(self) -> None:
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
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "done"}],
                            }
                        ],
                        response_id="resp-1",
                        raw_response={"id": "resp-1"},
                        events=[],
                    )
                ]
            )
            controller = SessionController(config=config, cwd=root, model_client=model_client)

            controller.run_task(user_input="unique prompt")

            serialized_request = str(model_client.requests[0]["input"])
            self.assertEqual(serialized_request.count("unique prompt"), 1)

    def test_request_disables_parallel_tool_calls_and_omits_empty_user_item(self) -> None:
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
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": "done"}],
                            }
                        ],
                        response_id="resp-1",
                        raw_response={"id": "resp-1"},
                        events=[],
                    )
                ]
            )
            controller = SessionController(config=config, cwd=root, model_client=model_client)

            controller.run_task(user_input="prompt")

            request = model_client.requests[0]
            self.assertEqual(request["parallel_tool_calls"], False)
            input_items = request["input"]
            empty_messages = [
                item
                for item in input_items
                if item.get("type") == "message"
                and any(part.get("text") == "" for part in item.get("content", []))
            ]
            self.assertEqual(empty_messages, [])


if __name__ == "__main__":
    unittest.main()
