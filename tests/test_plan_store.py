"""Tests for plan storage."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_cli.plan_store import PlanStep, save_plan


class PlanStoreTest(unittest.TestCase):
    """Covers plan serialization."""

    def test_save_plan_persists_structured_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path: Path = Path(tmp_dir) / "plan.json"
            save_plan(
                plan_path=plan_path,
                current_goal="Fix parser tests",
                steps=[PlanStep(text="Run tests", status="done")],
            )

            data = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(data["current_goal"], "Fix parser tests")
            self.assertEqual(data["steps"][0]["text"], "Run tests")
            self.assertEqual(data["steps"][0]["status"], "done")


if __name__ == "__main__":
    unittest.main()

