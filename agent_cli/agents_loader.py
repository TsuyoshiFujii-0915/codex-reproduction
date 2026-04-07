"""AGENTS.md layering support."""

from __future__ import annotations

from pathlib import Path


def load_agents_text(current_dir: Path, workspace_root: Path, home_dir: Path, max_bytes: int) -> str:
    """Load layered AGENTS instructions."""
    candidates: list[Path] = []
    global_dir: Path = home_dir / ".agent"
    candidates.extend([global_dir / "AGENTS.md", global_dir / "AGENTS.override.md"])
    traversal_dirs: list[Path] = _directories_from_root(root=workspace_root.resolve(), leaf=current_dir.resolve())
    for directory in traversal_dirs:
        candidates.append(directory / "AGENTS.md")
        candidates.append(directory / "AGENTS.override.md")
    parts: list[str] = []
    total_bytes: int = 0
    for path in candidates:
        if not path.is_file():
            continue
        text: str = path.read_text(encoding="utf-8")
        text_bytes: int = len(text.encode("utf-8"))
        if total_bytes + text_bytes > max_bytes:
            raise ValueError("AGENTS content exceeds max_bytes")
        total_bytes += text_bytes
        parts.append(text)
    return "\n\n".join(parts)


def _directories_from_root(root: Path, leaf: Path) -> list[Path]:
    root_resolved: Path = root.resolve()
    leaf_resolved: Path = leaf.resolve()
    if root_resolved not in [leaf_resolved, *leaf_resolved.parents]:
        raise ValueError("current_dir must be within workspace_root")
    directories: list[Path] = []
    current: Path = leaf_resolved
    while True:
        directories.append(current)
        if current == root_resolved:
            break
        current = current.parent
    directories.reverse()
    return directories
