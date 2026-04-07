"""Tests for compaction summary contents."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.responses_types import ModelResponse
from agent_cli.session import InMemoryModelClient, SessionController


class CompactionTest(unittest.TestCase):
    """Covers compaction summary formatting."""

    def test_compaction_summary_has_required_sections(self) -> None:
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

            controller = SessionController(config=config, cwd=root, model_client=model_client)
            controller.run_task(user_input="A" * 120)

            summary = (root / ".agent" / "compact_summary.md").read_text(encoding="utf-8")
            self.assertIn("## Goal", summary)
            self.assertIn("## Completed Work", summary)
            self.assertIn("## Changed Files", summary)
            self.assertIn("## Important Observations", summary)
            self.assertIn("## Unresolved Issues", summary)
            self.assertIn("## Next Likely Action", summary)


if __name__ == "__main__":
    unittest.main()

