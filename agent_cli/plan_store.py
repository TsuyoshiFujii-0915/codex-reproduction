"""Plan persistence helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class PlanStep:
    """Single plan step."""

    text: str
    status: str


@dataclass(frozen=True)
class PlanState:
    """Structured plan state."""

    current_goal: str
    steps: list[PlanStep]
    explanation: str
    updated_at: str


PlanRecord = PlanState


def save_plan(
    plan_path: Path | None = None,
    current_goal: str | None = None,
    steps: list[PlanStep] | None = None,
    path: Path | None = None,
    state: PlanState | None = None,
) -> None:
    """Persist a plan record in either supported call shape."""
    target_path: Path
    payload_state: PlanState
    if path is not None and state is not None:
        target_path = path
        payload_state = state
    elif plan_path is not None and current_goal is not None and steps is not None:
        target_path = plan_path
        payload_state = PlanState(
            current_goal=current_goal,
            steps=steps,
            explanation=current_goal,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    else:
        raise ValueError("invalid save_plan arguments")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "current_goal": payload_state.current_goal,
        "steps": [asdict(step) for step in payload_state.steps],
        "explanation": payload_state.explanation,
        "updated_at": payload_state.updated_at,
    }
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_plan(path: Path) -> PlanState:
    """Load a plan record from disk."""
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    raw_steps: object = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise ValueError("plan steps must be a list")
    steps: list[PlanStep] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            raise ValueError("plan step must be an object")
        text: object = raw_step.get("text")
        status: object = raw_step.get("status")
        if not isinstance(text, str) or not isinstance(status, str):
            raise ValueError("plan step fields must be strings")
        steps.append(PlanStep(text=text, status=status))
    return PlanState(
        current_goal=str(payload["current_goal"]),
        steps=steps,
        explanation=str(payload.get("explanation", payload["current_goal"])),
        updated_at=str(payload["updated_at"]),
    )
