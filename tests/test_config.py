"""Tests for configuration loading."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from agent_cli.config import load_config


class ConfigLoadingTest(unittest.TestCase):
    """Covers configuration defaults and overrides."""

    def test_load_config_applies_defaults_and_file_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path: Path = Path(tmp_dir) / "config.toml"
            config_path.write_text(
                textwrap.dedent(
                    """
                    [model]
                    base_url = "http://localhost:1234/v1"
                    model = "openai/gpt-oss-20b"

                    [agent]
                    workspace_root = "workspace"
                    approval_mode = "always"
                    sandbox_mode = "workspace-write"
                    """
                ).strip(),
                encoding="utf-8",
            )

            config = load_config(config_path=config_path, cwd=Path(tmp_dir), overrides={})

            self.assertEqual(config.model.base_url, "http://localhost:1234/v1")
            self.assertEqual(config.model.model, "openai/gpt-oss-20b")
            self.assertEqual(config.agent.approval_mode, "always")
            self.assertEqual(config.agent.workspace_root, (Path(tmp_dir) / "workspace").resolve())
            self.assertFalse(config.model.stream)
            self.assertFalse(config.model.store)

    def test_load_config_requires_model_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path: Path = Path(tmp_dir) / "config.toml"
            config_path.write_text("[model]\nbase_url = 'http://localhost:1234/v1'\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "model"):
                load_config(config_path=config_path, cwd=Path(tmp_dir), overrides={})


if __name__ == "__main__":
    unittest.main()
