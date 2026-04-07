"""Safety policy and workspace guards."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import shlex


@dataclass(frozen=True)
class CommandPolicy:
    """Shell command policy checks."""

    dangerous_tokens: frozenset[str] = frozenset(
        {"rm", "mv", "chmod", "chown", "sudo", "curl", "wget", "ssh", "scp"}
    )

    def requires_approval(self, command: Iterable[str]) -> bool:
        """Return whether the command should require approval."""
        tokens: list[str] = list(command)
        return any(token in self.dangerous_tokens for token in tokens)

    def format_command(self, command: Iterable[str]) -> str:
        """Return a shell-escaped display string."""
        return shlex.join(list(command))


class PolicyGuard:
    """Compatibility wrapper around workspace path checks."""

    def __init__(self, sandbox_mode: str, approval_mode: str, workspace_root: Path) -> None:
        self._sandbox_mode = sandbox_mode
        self._approval_mode = approval_mode
        self._workspace_root = workspace_root.resolve()
        self._command_policy = CommandPolicy()

    def resolve_path(self, target_path: Path) -> Path:
        """Resolve a path according to sandbox policy."""
        candidate: Path = target_path if target_path.is_absolute() else self._workspace_root / target_path
        if self._sandbox_mode == "full-access":
            return candidate.resolve()
        return ensure_within_workspace(workspace_root=self._workspace_root, target_path=candidate)

    def validate_shell_command(self, command: Iterable[str]) -> None:
        """Validate a shell command according to sandbox policy."""
        tokens: list[str] = list(command)
        if tokens == []:
            raise ValueError("shell command cannot be empty")
        if self._sandbox_mode == "read-only" and tokens[0] not in {"pwd", "ls", "find", "cat", "sed", "grep", "git"}:
            raise ValueError(f"command is not allowed in read-only mode: {tokens[0]}")
        if self._approval_mode == "always":
            raise ValueError("command requires approval in always mode")

    def ensure_write_allowed(self, path: Path, content: str) -> Path:
        """Validate and resolve a write target."""
        del content
        if self._sandbox_mode == "read-only":
            raise ValueError("writes are not allowed in read-only mode")
        return self.resolve_path(path)


def ensure_within_workspace(workspace_root: Path, target_path: Path) -> Path:
    """Resolve and validate that a path stays within the workspace."""
    root_resolved: Path = workspace_root.resolve()
    target_resolved: Path = target_path.resolve()
    if root_resolved == target_resolved or root_resolved in target_resolved.parents:
        return target_resolved
    raise ValueError(f"path escapes workspace: {target_resolved}")
