# Title
Add an optional Textual-based TUI command

# Status
accepted

# Context
The project currently exposes a minimal line-oriented CLI through `chat`, one-shot prompts, and maintenance commands.
The renderer writes directly to standard output, and interactive chat input is collected with `input()`.

Adding a richer terminal experience is desirable, but replacing the current `chat` flow would change existing behavior and break users who rely on the simple terminal mode.
The repository does not yet contain any ADRs that define an alternative UI architecture.

# Decision
Introduce a new `agent tui` command built with Textual instead of replacing the existing `chat` command.

Keep the current session loop and model interaction logic in `SessionController`.
Implement the TUI as a separate presentation layer that uses a renderer compatible with the existing session controller.
Use Textual as the only additional UI dependency for this mode.

# Consequences
The existing CLI behavior remains unchanged for one-shot prompts, `chat`, `resume`, `doctor`, and `config`.
The project gains a second interactive UI path, so renderer responsibilities must be explicit enough to support both plain terminal output and a structured screen.
An additional dependency is required and must be installed for the TUI command.
