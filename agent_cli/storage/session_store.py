"""Session storage paths and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any


@dataclass(frozen=True)
class SessionPaths:
    """Canonical paths for one session."""

    memory_root: Path
    transcript_path: Path
    latest_session_path: Path
    plan_path: Path
    progress_path: Path
    compact_summary_path: Path
    session_id: str

    @property
    def project_memory_dir(self) -> Path:
        """Compatibility alias for the memory root."""

        return self.memory_root

    @property
    def sessions_dir(self) -> Path:
        """Return the sessions directory."""

        return self.transcript_path.parent


def prepare_session_paths(workspace_root: Path, project_memory_dir: str) -> SessionPaths:
    """Prepare on-disk storage for a new session."""
    memory_root: Path = (workspace_root / project_memory_dir).resolve()
    session_id: str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    sessions_dir: Path = memory_root / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    latest_session_path: Path = memory_root / "latest_session.txt"
    latest_session_path.write_text(session_id, encoding="utf-8")
    return SessionPaths(
        memory_root=memory_root,
        transcript_path=sessions_dir / f"{session_id}.jsonl",
        latest_session_path=latest_session_path,
        plan_path=memory_root / "plan.json",
        progress_path=memory_root / "progress.md",
        compact_summary_path=memory_root / "compact_summary.md",
        session_id=session_id,
    )


def prepare_specific_session_paths(workspace_root: Path, project_memory_dir: str, session_id: str) -> SessionPaths:
    """Prepare paths for an existing session id."""
    memory_root: Path = (workspace_root / project_memory_dir).resolve()
    sessions_dir: Path = memory_root / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    latest_session_path: Path = memory_root / "latest_session.txt"
    latest_session_path.write_text(session_id, encoding="utf-8")
    return SessionPaths(
        memory_root=memory_root,
        transcript_path=sessions_dir / f"{session_id}.jsonl",
        latest_session_path=latest_session_path,
        plan_path=memory_root / "plan.json",
        progress_path=memory_root / "progress.md",
        compact_summary_path=memory_root / "compact_summary.md",
        session_id=session_id,
    )


def save_session_snapshot(paths: SessionPaths, session_state: Any) -> None:
    """Save a JSON snapshot as an auxiliary cache."""
    paths.sessions_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path: Path = paths.sessions_dir / f"{session_state.session_id}.json"
    snapshot: dict[str, Any] = {
        "session_id": session_state.session_id,
        "history_items": session_state.history_items,
        "plan": session_state.plan,
        "assistant_last_message": session_state.assistant_last_message,
        "compact_summary": session_state.compact_summary,
    }
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    paths.latest_session_path.write_text(session_state.session_id, encoding="utf-8")
