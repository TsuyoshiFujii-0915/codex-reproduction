"""Plan update tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_cli.plan_store import PlanStep, save_plan
from agent_cli.tools.base import ToolExecutionContext, ToolResult


class UpdatePlanTool:
    """Update the current task plan stored on disk."""

    def name(self) -> str:
        return "update_plan"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": "update_plan",
            "description": "Update the current task plan shown to the user.",
            "strict": False,
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                },
                "required": ["plan"],
            },
        }

    def execute(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        plan_value: Any = arguments.get("plan")
        explanation_value: Any = arguments.get("explanation", "")
        if not isinstance(plan_value, list) or not all(isinstance(item, str) for item in plan_value):
            raise ValueError("plan must be a list of strings")
        if not isinstance(explanation_value, str):
            raise ValueError("explanation must be a string")
        if context.memory_root is None:
            raise ValueError("memory_root is required for update_plan")
        save_plan(
            plan_path=Path(context.memory_root) / "plan.json",
            current_goal=context.current_goal or "",
            steps=[PlanStep(text=item, status="todo") for item in plan_value],
        )
        return ToolResult(
            ok=True,
            output=explanation_value,
            exit_code=0,
            metadata={"plan_length": len(plan_value)},
        )
