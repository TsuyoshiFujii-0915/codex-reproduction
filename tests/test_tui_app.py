"""Tests for the Textual TUI application."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings
from agent_cli.responses_types import ModelResponse, StreamEvent
from agent_cli.session import InMemoryModelClient, SessionController
from agent_cli.tui_app import AgentTuiApp, ConversationMessage, SessionHeaderData


class TuiAppTest(unittest.IsolatedAsyncioTestCase):
    """Covers the interactive terminal UI."""

    async def test_submit_displays_user_and_assistant_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root: Path = Path(tmp_dir)
            config = _build_config(root=root)
            controller = SessionController(
                config=config,
                cwd=root,
                model_client=InMemoryModelClient(
                    responses=[
                        ModelResponse(
                            output_items=[
                                {
                                    "type": "message",
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": "TUI reply"}],
                                }
                            ],
                            response_id="resp-1",
                            raw_response={"id": "resp-1"},
                            events=[],
                        )
                    ]
                ),
            )
            app = AgentTuiApp(
                controller=controller,
                session_header=_build_session_header(root=root),
                show_plan=True,
                show_tool_logs=True,
            )

            async with app.run_test() as pilot:
                await pilot.click("#prompt-input")
                await pilot.press("H", "i", "enter")
                await pilot.pause()

                messages = list(app.query(ConversationMessage))
                self.assertEqual([message.role for message in messages], ["assistant", "user", "assistant"])
                self.assertEqual(messages[1].message_text, "Hi")
                self.assertEqual(messages[2].message_text, "TUI reply")

    async def test_streaming_response_updates_current_assistant_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root: Path = Path(tmp_dir)
            config = _build_config(root=root, stream=True)
            controller = SessionController(
                config=config,
                cwd=root,
                model_client=InMemoryModelClient(
                    responses=[
                        ModelResponse(
                            output_items=[
                                {
                                    "type": "message",
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": "streamed"}],
                                }
                            ],
                            response_id="resp-1",
                            raw_response={"id": "resp-1"},
                            events=[
                                StreamEvent(event="response.output_text.delta", data={"delta": "stream"}),
                                StreamEvent(event="response.output_text.delta", data={"delta": "ed"}),
                            ],
                        )
                    ]
                ),
            )
            app = AgentTuiApp(
                controller=controller,
                session_header=_build_session_header(root=root),
                show_plan=True,
                show_tool_logs=True,
            )

            async with app.run_test() as pilot:
                await pilot.click("#prompt-input")
                await pilot.press("G", "o", "enter")
                await pilot.pause()

                messages = list(app.query(ConversationMessage))
                self.assertEqual(messages[-1].message_text, "streamed")


def _build_config(root: Path, stream: bool = False) -> AgentConfig:
    return AgentConfig(
        model=ModelSettings(
            base_url="http://localhost:1234/v1",
            model="test-model",
            api_key_env="OPENAI_API_KEY",
            timeout_seconds=120,
            stream=stream,
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


def _build_session_header(root: Path) -> SessionHeaderData:
    return SessionHeaderData(
        base_url="http://localhost:1234/v1",
        model="test-model",
        cwd=str(root),
        sandbox_mode="workspace-write",
        approval_mode="never",
    )


if __name__ == "__main__":
    unittest.main()
