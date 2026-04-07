"""Tests for workspace path guard."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_cli.policy import ensure_within_workspace


class PolicyTest(unittest.TestCase):
    """Covers workspace path restrictions."""

    def test_ensure_within_workspace_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root: Path = Path(tmp_dir) / "workspace"
            outside_file: Path = Path(tmp_dir) / "outside.txt"
            workspace_root.mkdir()
            outside_file.write_text("x", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "workspace"):
                ensure_within_workspace(workspace_root=workspace_root, target_path=outside_file)

    def test_ensure_within_workspace_allows_nested_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root: Path = Path(tmp_dir) / "workspace"
            nested_file: Path = workspace_root / "dir" / "file.txt"
            nested_file.parent.mkdir(parents=True)
            nested_file.write_text("ok", encoding="utf-8")

            resolved = ensure_within_workspace(workspace_root=workspace_root, target_path=nested_file)

            self.assertEqual(resolved, nested_file.resolve())


if __name__ == "__main__":
    unittest.main()

