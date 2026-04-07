"""Tests for layered AGENTS.md loading."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.agents_loader import load_agents_text


class AgentsLoaderTest(unittest.TestCase):
    """Covers layered AGENTS file loading."""

    def test_load_agents_text_stacks_global_and_project_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            home_dir: Path = Path(tmp_dir) / "home"
            project_dir: Path = Path(tmp_dir) / "project"
            nested_dir: Path = project_dir / "src" / "feature"
            nested_dir.mkdir(parents=True)
            home_dir.mkdir(parents=True)

            (home_dir / ".agent").mkdir()
            (home_dir / ".agent" / "AGENTS.md").write_text("global", encoding="utf-8")
            (project_dir / "AGENTS.md").write_text("root", encoding="utf-8")
            (project_dir / "src" / "AGENTS.override.md").write_text("src", encoding="utf-8")
            (nested_dir / "AGENTS.md").write_text("nested", encoding="utf-8")

            text = load_agents_text(
                current_dir=nested_dir,
                workspace_root=project_dir,
                home_dir=home_dir,
                max_bytes=32 * 1024,
            )

            self.assertEqual(text.split("\n\n"), ["global", "root", "src", "nested"])


if __name__ == "__main__":
    unittest.main()

