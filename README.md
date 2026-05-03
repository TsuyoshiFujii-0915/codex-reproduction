# agent-cli

Minimal Codex-style coding agent CLI in Python.

## Requirements

- Python 3.11+
- `uv`

## Setup

```bash
uv sync
```

## Initialize config

```bash
uv run agent config init
```

This creates `~/.agent/config.toml`.

Set at least:

```toml
[model]
base_url = "http://localhost:1234/v1"
model = "openai/gpt-oss-20b"
api_key_env = "OPENAI_API_KEY"
stream = false
```

`stream` defaults to `false`. Enable streaming explicitly with `--stream` when needed.

## Run

One-shot:

```bash
uv run agent "README を要約して"
```

Interactive chat:

```bash
uv run agent chat
```

Interactive TUI:

```bash
uv run agent tui
```

Health check:

```bash
uv run agent doctor
```

## Test

```bash
uv run python -m unittest discover -v
```
