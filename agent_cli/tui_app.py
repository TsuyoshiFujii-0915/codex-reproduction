"""Textual-based TUI for the agent CLI."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Input, Label, RichLog, Static

from agent_cli.renderer import Renderer
from agent_cli.responses_types import RunResult
from agent_cli.session import SessionController


@dataclass(frozen=True)
class SessionHeaderData:
    """Static session metadata shown in the TUI."""

    base_url: str
    model: str
    cwd: str
    sandbox_mode: str
    approval_mode: str


class ConversationMessage(Static):
    """One transcript bubble in the conversation view."""

    def __init__(self, role: str, text: str, message_id: str) -> None:
        """Initializes a conversation message.

        Args:
            role: Message role. Expected values are ``assistant`` or ``user``.
            text: Initial message text.
            message_id: Stable DOM id for later updates.
        """
        super().__init__("", id=message_id)
        self.role = role
        self.message_text = text
        self.add_class(f"-{role}")
        self.border_title = role.upper()
        self._refresh()

    def set_text(self, text: str) -> None:
        """Replaces the full message text.

        Args:
            text: New message text.
        """
        self.message_text = text
        self._refresh()

    def append_text(self, text: str) -> None:
        """Appends streaming output to the message.

        Args:
            text: Incremental text chunk.
        """
        self.message_text = f"{self.message_text}{text}"
        self._refresh()

    def _refresh(self) -> None:
        display_text: str = self.message_text if self.message_text != "" else "..."
        self.update(display_text)


class TuiRenderer(Renderer):
    """Renderer that routes session events into the Textual app."""

    def __init__(
        self,
        app: "AgentTuiApp",
        assistant_message_id: str,
        show_plan: bool,
        show_tool_logs: bool,
    ) -> None:
        """Initializes the Textual renderer.

        Args:
            app: Owning Textual application.
            assistant_message_id: Transcript widget id for the active assistant reply.
            show_plan: Whether plan messages should be shown.
            show_tool_logs: Whether tool logs should be shown.
        """
        super().__init__(show_plan=show_plan, show_tool_logs=show_tool_logs, show_diff_summary=True)
        self._app = app
        self._assistant_message_id = assistant_message_id

    def show_plan_update(self, message: str) -> None:
        """Displays a plan update inside the sidebar.

        Args:
            message: Plan text.
        """
        if self._show_plan:
            self._app.call_from_thread(self._app.append_plan_log, message)

    def show_session_header(
        self,
        base_url: str,
        model: str,
        cwd: str,
        sandbox_mode: str,
        approval_mode: str,
    ) -> None:
        """Updates session metadata inside the sidebar."""
        self._app.call_from_thread(
            self._app.update_session_header,
            SessionHeaderData(
                base_url=base_url,
                model=model,
                cwd=cwd,
                sandbox_mode=sandbox_mode,
                approval_mode=approval_mode,
            ),
        )

    def show_tool_log(self, message: str) -> None:
        """Displays a tool log inside the sidebar.

        Args:
            message: Tool log text.
        """
        if self._show_tool_logs:
            self._app.call_from_thread(self._app.append_tool_log, message)

    def show_assistant_text(self, message: str) -> None:
        """Sets the current assistant message text.

        Args:
            message: Final assistant response.
        """
        self._app.call_from_thread(self._app.set_message_text, self._assistant_message_id, message)

    def show_stream_text(self, chunk: str) -> None:
        """Appends a streamed assistant text chunk.

        Args:
            chunk: Incremental output.
        """
        self._app.call_from_thread(self._app.append_message_text, self._assistant_message_id, chunk)

    def finish_stream(self) -> None:
        """Finalizes a streamed response."""
        self._app.call_from_thread(self._app.scroll_transcript_to_end)


class AgentTuiApp(App[None]):
    """Interactive Textual shell for the coding agent."""

    CSS = """
    Screen {
        background: #06111c;
        color: #f4efe4;
    }

    #hero {
        height: 3;
        margin: 1 1 0 1;
        padding: 0 2;
        border: heavy #3e6ea1;
        background: #10243a;
        color: #ffcb6b;
        content-align: center middle;
        text-style: bold;
    }

    #workspace {
        height: 1fr;
        margin: 0 1 0 1;
    }

    #main-column {
        width: 1fr;
        margin-right: 1;
    }

    #sidebar {
        width: 38;
    }

    .panel {
        margin-top: 1;
        padding: 0 1 1 1;
        border: round #34506f;
        background: #0b1828;
    }

    .panel-title {
        height: 1;
        margin: 0 0 1 0;
        color: #ffcb6b;
        text-style: bold;
    }

    #transcript {
        height: 1fr;
        padding-bottom: 1;
    }

    ConversationMessage {
        width: 1fr;
        margin: 1 1 0 1;
        padding: 1 2;
        border: round #284563;
        background: #0f2134;
        color: #f4efe4;
    }

    ConversationMessage.-assistant {
        margin-right: 8;
        border: round #ffb454;
        background: #26190f;
        color: #fff2d6;
    }

    ConversationMessage.-user {
        margin-left: 8;
        border: round #66c7ff;
        background: #112d45;
        color: #e6f7ff;
    }

    #session-card {
        color: #c6dae9;
    }

    RichLog {
        height: 1fr;
        background: #0b1828;
        color: #d4e2ef;
    }

    #input-row {
        height: 3;
        margin: 1;
        padding: 0 1;
        border: round #3e6ea1;
        background: #0e1d30;
        align: center middle;
    }

    #prompt-label {
        width: 10;
        color: #ffcb6b;
        text-style: bold;
    }

    #prompt-input {
        width: 1fr;
        border: none;
        background: transparent;
    }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit"), ("ctrl+l", "clear_logs", "Clear Logs")]

    def __init__(
        self,
        controller: SessionController,
        session_header: SessionHeaderData,
        show_plan: bool,
        show_tool_logs: bool,
    ) -> None:
        """Initializes the TUI application.

        Args:
            controller: Session controller reused across prompts.
            session_header: Session metadata displayed in the sidebar.
            show_plan: Whether the plan panel is enabled.
            show_tool_logs: Whether the tool log panel is enabled.
        """
        super().__init__()
        self._controller = controller
        self._session_header = session_header
        self._show_plan = show_plan
        self._show_tool_logs = show_tool_logs
        self._status = "Idle"
        self._session_id: str | None = None
        self._message_count = 0
        self._busy = False

    def compose(self) -> ComposeResult:
        """Builds the TUI layout."""
        yield Static("AGENT COCKPIT // LIVE TERMINAL", id="hero")
        with Horizontal(id="workspace"):
            with Vertical(id="main-column", classes="panel"):
                yield Label("Transcript", classes="panel-title")
                with VerticalScroll(id="transcript"):
                    yield ConversationMessage(
                        role="assistant",
                        text="Ready. Describe the task and I will run it through the agent loop.",
                        message_id=self._next_message_id(),
                    )
            with Vertical(id="sidebar"):
                with Vertical(classes="panel"):
                    yield Label("Session", classes="panel-title")
                    yield Static(id="session-card")
                if self._show_plan:
                    with Vertical(classes="panel"):
                        yield Label("Plan", classes="panel-title")
                        yield RichLog(id="plan-log", wrap=True, auto_scroll=True, markup=False)
                if self._show_tool_logs:
                    with Vertical(classes="panel"):
                        yield Label("Tools", classes="panel-title")
                        yield RichLog(id="tool-log", wrap=True, auto_scroll=True, markup=False)
        with Horizontal(id="input-row"):
            yield Static("PROMPT", id="prompt-label")
            yield Input(placeholder="Ask the agent to inspect, edit, or explain the project", id="prompt-input")
        yield Footer()

    def on_mount(self) -> None:
        """Initializes focus and session metadata."""
        self.update_session_header(self._session_header)
        self.query_one("#prompt-input", Input).focus()

    @on(Input.Submitted, "#prompt-input")
    async def on_prompt_submitted(self, event: Input.Submitted) -> None:
        """Starts one agent run from the prompt bar.

        Args:
            event: Submitted input event.
        """
        prompt: str = event.value.strip()
        if prompt == "":
            return
        if self._busy:
            return
        event.input.clear()
        event.input.disabled = True
        self._busy = True
        self._status = "Running"
        self.update_session_card()
        assistant_message_id: str = self._next_message_id()
        await self._mount_message(role="user", text=prompt, message_id=self._next_message_id())
        await self._mount_message(role="assistant", text="", message_id=assistant_message_id)
        self._run_prompt(prompt=prompt, assistant_message_id=assistant_message_id)

    def update_session_header(self, session_header: SessionHeaderData) -> None:
        """Updates the static session metadata.

        Args:
            session_header: Metadata to display.
        """
        self._session_header = session_header
        self.update_session_card()

    def update_session_card(self) -> None:
        """Renders the session status panel."""
        session_text: str = "\n".join(
            [
                f"model: {self._session_header.model}",
                f"backend: {self._session_header.base_url}",
                f"cwd: {self._session_header.cwd}",
                f"sandbox: {self._session_header.sandbox_mode}",
                f"approval: {self._session_header.approval_mode}",
                f"status: {self._status}",
                f"session: {self._session_id or 'pending'}",
            ]
        )
        self.query_one("#session-card", Static).update(session_text)

    def append_plan_log(self, message: str) -> None:
        """Appends a plan update to the sidebar.

        Args:
            message: Plan text.
        """
        if not self._show_plan:
            return
        self.query_one("#plan-log", RichLog).write(message)

    def append_tool_log(self, message: str) -> None:
        """Appends a tool update to the sidebar.

        Args:
            message: Tool log text.
        """
        if not self._show_tool_logs:
            return
        self.query_one("#tool-log", RichLog).write(message)

    def set_message_text(self, message_id: str, text: str) -> None:
        """Replaces an existing transcript message text.

        Args:
            message_id: DOM id for the target message widget.
            text: Replacement text.
        """
        self.query_one(f"#{message_id}", ConversationMessage).set_text(text)
        self.scroll_transcript_to_end()

    def append_message_text(self, message_id: str, text: str) -> None:
        """Appends streamed text to an existing transcript message.

        Args:
            message_id: DOM id for the target message widget.
            text: Incremental output.
        """
        self.query_one(f"#{message_id}", ConversationMessage).append_text(text)
        self.scroll_transcript_to_end()

    def scroll_transcript_to_end(self) -> None:
        """Scrolls the transcript to the latest message."""
        self.query_one("#transcript", VerticalScroll).scroll_end(animate=False)

    def action_clear_logs(self) -> None:
        """Clears sidebar logs."""
        if self._show_plan:
            self.query_one("#plan-log", RichLog).clear()
        if self._show_tool_logs:
            self.query_one("#tool-log", RichLog).clear()

    @work(thread=True, exclusive=True)
    def _run_prompt(self, prompt: str, assistant_message_id: str) -> None:
        """Runs one prompt in a worker thread.

        Args:
            prompt: User prompt text.
            assistant_message_id: Transcript message id for the reply.
        """
        renderer = TuiRenderer(
            app=self,
            assistant_message_id=assistant_message_id,
            show_plan=self._show_plan,
            show_tool_logs=self._show_tool_logs,
        )
        self._controller.renderer = renderer
        try:
            result: RunResult = self._controller.run_task(user_input=prompt)
        except Exception as exc:  # noqa: BLE001
            self.call_from_thread(self._handle_prompt_failure, assistant_message_id, str(exc))
            return
        self.call_from_thread(self._handle_prompt_result, result)

    def _handle_prompt_result(self, result: RunResult) -> None:
        """Handles a successful worker completion.

        Args:
            result: Completed run result.
        """
        self._session_id = result.session_id
        self._status = "Idle"
        self._busy = False
        prompt_input: Input = self.query_one("#prompt-input", Input)
        prompt_input.disabled = False
        prompt_input.focus()
        self.update_session_card()

    def _handle_prompt_failure(self, assistant_message_id: str, error_message: str) -> None:
        """Handles a failed worker completion.

        Args:
            assistant_message_id: Transcript message id for the active reply.
            error_message: Error text to display.
        """
        self.set_message_text(assistant_message_id, f"Error: {error_message}")
        self._status = "Error"
        self._busy = False
        prompt_input: Input = self.query_one("#prompt-input", Input)
        prompt_input.disabled = False
        prompt_input.focus()
        self.update_session_card()
        self.append_tool_log(f"tui_error {error_message}")

    async def _mount_message(self, role: str, text: str, message_id: str) -> None:
        """Appends a transcript message widget.

        Args:
            role: Message role.
            text: Initial message text.
            message_id: Stable widget id.
        """
        transcript: VerticalScroll = self.query_one("#transcript", VerticalScroll)
        await transcript.mount(ConversationMessage(role=role, text=text, message_id=message_id))
        self.scroll_transcript_to_end()

    def _next_message_id(self) -> str:
        """Returns the next transcript message id."""
        self._message_count += 1
        return f"message-{self._message_count}"
