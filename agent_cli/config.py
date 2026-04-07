"""Configuration loading for the CLI agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib


ApprovalMode = str
SandboxMode = str


@dataclass(frozen=True)
class ModelSettings:
    """Settings for the model backend."""

    base_url: str
    model: str
    api_key_env: str
    timeout_seconds: int
    stream: bool
    store: bool
    api_key: str | None = None


@dataclass(frozen=True)
class AgentSettings:
    """Settings for the agent runtime."""

    max_turns: int
    compact_trigger_tokens: int
    keep_last_turns_after_compact: int
    approval_mode: ApprovalMode
    sandbox_mode: SandboxMode
    workspace_root: Path
    shell: str


@dataclass(frozen=True)
class UISettings:
    """Settings for terminal rendering."""

    show_plan: bool
    show_tool_logs: bool
    show_diff_summary: bool


@dataclass(frozen=True)
class FilesSettings:
    """Settings for on-disk project memory."""

    project_memory_dir: str


@dataclass(frozen=True)
class AgentConfig:
    """Application configuration."""

    model: ModelSettings
    agent: AgentSettings
    ui: UISettings
    files: FilesSettings
    debug: bool = False


def load_config(config_path: Path, cwd: Path, overrides: dict[str, Any]) -> AgentConfig:
    """Load configuration from TOML and CLI overrides."""
    file_data: dict[str, Any] = {}
    if config_path.exists():
        file_data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    merged: dict[str, Any] = _build_default_data()
    _deep_merge(target=merged, update=file_data)
    _apply_overrides(data=merged, overrides=overrides)
    model_data: dict[str, Any] = _require_section(data=merged, section_name="model")
    agent_data: dict[str, Any] = _require_section(data=merged, section_name="agent")
    ui_data: dict[str, Any] = _require_section(data=merged, section_name="ui")
    files_data: dict[str, Any] = _require_section(data=merged, section_name="files")
    model_name: str = _require_string(data=model_data, key="model")
    if model_name.strip() == "":
        raise ValueError("model must be configured")
    workspace_root: Path = (cwd / _require_string(data=agent_data, key="workspace_root")).resolve()
    return AgentConfig(
        model=ModelSettings(
            base_url=_require_string(data=model_data, key="base_url"),
            model=model_name,
            api_key_env=_require_string(data=model_data, key="api_key_env"),
            timeout_seconds=_require_int(data=model_data, key="timeout_seconds"),
            stream=_require_bool(data=model_data, key="stream"),
            store=_require_bool(data=model_data, key="store"),
            api_key=_optional_string(data=model_data, key="api_key"),
        ),
        agent=AgentSettings(
            max_turns=_require_int(data=agent_data, key="max_turns"),
            compact_trigger_tokens=_require_int(data=agent_data, key="compact_trigger_tokens"),
            keep_last_turns_after_compact=_require_int(data=agent_data, key="keep_last_turns_after_compact"),
            approval_mode=_require_string(data=agent_data, key="approval_mode"),
            sandbox_mode=_require_string(data=agent_data, key="sandbox_mode"),
            workspace_root=workspace_root,
            shell=_require_string(data=agent_data, key="shell"),
        ),
        ui=UISettings(
            show_plan=_require_bool(data=ui_data, key="show_plan"),
            show_tool_logs=_require_bool(data=ui_data, key="show_tool_logs"),
            show_diff_summary=_require_bool(data=ui_data, key="show_diff_summary"),
        ),
        files=FilesSettings(project_memory_dir=_require_string(data=files_data, key="project_memory_dir")),
        debug=_require_bool(data=merged, key="debug"),
    )


def default_config_text() -> str:
    """Return the default user configuration template."""
    return "\n".join(
        [
            "[model]",
            'base_url = "http://localhost:1234/v1"',
            'model = ""',
            'api_key_env = "OPENAI_API_KEY"',
            "timeout_seconds = 120",
            "stream = false",
            "store = false",
            "",
            "[agent]",
            "max_turns = 40",
            "compact_trigger_tokens = 24000",
            "keep_last_turns_after_compact = 4",
            'approval_mode = "on-request"',
            'sandbox_mode = "workspace-write"',
            'workspace_root = "."',
            'shell = "/bin/bash"',
            "",
            "[ui]",
            "show_plan = true",
            "show_tool_logs = true",
            "show_diff_summary = true",
            "",
            "[files]",
            'project_memory_dir = ".agent"',
        ]
    )


def _build_default_data() -> dict[str, Any]:
    return {
        "model": {
            "base_url": "http://localhost:1234/v1",
            "model": "",
            "api_key_env": "OPENAI_API_KEY",
            "timeout_seconds": 120,
            "stream": False,
            "store": False,
        },
        "agent": {
            "max_turns": 40,
            "compact_trigger_tokens": 24000,
            "keep_last_turns_after_compact": 4,
            "approval_mode": "on-request",
            "sandbox_mode": "workspace-write",
            "workspace_root": ".",
            "shell": "/bin/bash",
        },
        "ui": {
            "show_plan": True,
            "show_tool_logs": True,
            "show_diff_summary": True,
        },
        "files": {"project_memory_dir": ".agent"},
        "debug": False,
    }


def _deep_merge(target: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            nested_target: dict[str, Any] = target[key]
            _deep_merge(target=nested_target, update=value)
            continue
        target[key] = value


def _apply_overrides(data: dict[str, Any], overrides: dict[str, Any]) -> None:
    for dotted_key, value in overrides.items():
        parts: list[str] = dotted_key.split(".")
        cursor: dict[str, Any] = data
        for part in parts[:-1]:
            nested: dict[str, Any] = cursor.setdefault(part, {})
            cursor = nested
        cursor[parts[-1]] = value


def _require_section(data: dict[str, Any], section_name: str) -> dict[str, Any]:
    section: Any = data.get(section_name)
    if not isinstance(section, dict):
        raise ValueError(f"{section_name} section is required")
    return section


def _require_string(data: dict[str, Any], key: str) -> str:
    value: Any = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _require_int(data: dict[str, Any], key: str) -> int:
    value: Any = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _require_bool(data: dict[str, Any], key: str) -> bool:
    value: Any = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    value: Any = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value
