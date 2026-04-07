"""Progress markdown persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProgressState:
    """Human-readable progress state."""

    goal: str
    what_was_done: str
    current_state: str
    next_likely_action: str
    risks_and_open_questions: str


def save_progress(
    progress_path: Path,
    goal: str,
    what_was_done: str,
    current_state: str,
    next_likely_action: str,
    risks_and_open_questions: str,
) -> None:
    """Writes the human-readable progress file."""
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        "\n".join(
            [
                "# Progress",
                "",
                "## Goal",
                goal,
                "",
                "## What was done",
                what_was_done,
                "",
                "## Current state",
                current_state,
                "",
                "## Next likely action",
                next_likely_action,
                "",
                "## Risks / open questions",
                risks_and_open_questions,
                "",
            ]
        ),
        encoding="utf-8",
    )
