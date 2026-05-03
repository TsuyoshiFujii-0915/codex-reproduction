"""Tests for CLI argument support."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_cli.cli import _build_overrides, _parse_args, _run_chat
from agent_cli.config import AgentConfig, AgentSettings, FilesSettings, ModelSettings, UISettings


class CliTest(unittest.TestCase):
    """Covers common CLI flags."""

    def test_run_chat_exits_cleanly_on_keyboard_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
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
                    max_turns=40,
                    compact_trigger_tokens=24000,
                    keep_last_turns_after_compact=4,
                    approval_mode="on-request",
                    sandbox_mode="workspace-write",
                    workspace_root=Path(tmp_dir),
                    shell="/bin/bash",
                ),
                ui=UISettings(show_plan=True, show_tool_logs=True, show_diff_summary=True),
                files=FilesSettings(project_memory_dir=".agent"),
            )

            with patch("builtins.input", side_effect=KeyboardInterrupt):
                exit_code = _run_chat(config=config, cwd=Path(tmp_dir))

        self.assertEqual(exit_code, 0)

    def test_parser_accepts_api_key_and_debug(self) -> None:
        args = _parse_args(["--api-key", "secret", "--debug", "doctor"])

        self.assertEqual(args.api_key, "secret")
        self.assertTrue(args.debug)
        self.assertEqual(args.command, "doctor")

    def test_build_overrides_includes_api_key_and_debug(self) -> None:
        args = _parse_args(["--api-key", "secret", "--debug", "--model", "m"])

        overrides = _build_overrides(args=args)

        self.assertEqual(overrides["model.api_key"], "secret")
        self.assertEqual(overrides["debug"], True)

    def test_parse_args_accepts_config_init(self) -> None:
        args = _parse_args(["config", "init"])

        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_command, "init")

    def test_parse_args_accepts_tui_command(self) -> None:
        args = _parse_args(["tui"])

        self.assertEqual(args.command, "tui")

    def test_parse_args_treats_non_command_as_prompt(self) -> None:
        args = _parse_args(["README を要約して"])

        self.assertIsNone(args.command)
        self.assertEqual(args.prompt, "README を要約して")


if __name__ == "__main__":
    unittest.main()
