"""Terminal rendering."""

from __future__ import annotations


class Renderer:
    """Minimal terminal renderer."""

    def __init__(self, show_plan: bool, show_tool_logs: bool, show_diff_summary: bool | None = None) -> None:
        """Initializes the renderer.

        Args:
            show_plan: Whether to print plan updates.
            show_tool_logs: Whether to print tool logs.
            show_diff_summary: Unused compatibility flag.
        """
        self._show_plan = show_plan
        self._show_tool_logs = show_tool_logs
        self._show_diff_summary = show_diff_summary

    def show_plan_update(self, message: str) -> None:
        """Prints a plan update when enabled.

        Args:
            message: Plan text.
        """
        if self._show_plan:
            print(message)

    def show_session_header(
        self,
        base_url: str,
        model: str,
        cwd: str,
        sandbox_mode: str,
        approval_mode: str,
    ) -> None:
        """Print the session header."""
        print(
            f"backend={base_url} model={model} cwd={cwd} "
            f"sandbox={sandbox_mode} approval={approval_mode}"
        )

    def show_tool_log(self, message: str) -> None:
        """Prints a tool log when enabled.

        Args:
            message: Tool log text.
        """
        if self._show_tool_logs:
            print(message)

    def show_assistant_text(self, message: str) -> None:
        """Prints assistant text.

        Args:
            message: Assistant text.
        """
        print(message)

    def show_stream_text(self, chunk: str) -> None:
        """Prints one streaming text chunk."""
        print(chunk, end="", flush=True)

    def finish_stream(self) -> None:
        """Terminates a streamed line."""
        print()
