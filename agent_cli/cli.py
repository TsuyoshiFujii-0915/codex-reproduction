"""CLI entrypoint for the minimal agent."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import argparse
import json
import os
import os.path
import sys
import urllib.request

from agent_cli.config import AgentConfig, default_config_text, load_config
from agent_cli.renderer import Renderer
from agent_cli.session import SessionController

_COMMAND_NAMES: frozenset[str] = frozenset({"chat", "resume", "doctor", "config", "tui"})


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    cwd: Path = Path(args.cwd).resolve()
    config_path: Path = Path(args.config).expanduser().resolve()
    if args.command == "config" and args.config_command == "init":
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(default_config_text(), encoding="utf-8")
        print(config_path)
        return 0
    overrides: dict[str, object] = _build_overrides(args=args)
    config: AgentConfig = load_config(config_path=config_path, cwd=cwd, overrides=overrides)
    if args.api_key is not None:
        os.environ[config.model.api_key_env] = args.api_key
    renderer = Renderer(
        show_plan=config.ui.show_plan,
        show_tool_logs=config.ui.show_tool_logs,
        show_diff_summary=config.ui.show_diff_summary,
    )
    if args.command == "doctor":
        return _run_doctor(config=config)
    if args.command == "tui":
        return _run_tui(config=config, cwd=cwd)
    if args.command == "resume":
        renderer.show_session_header(
            base_url=config.model.base_url,
            model=config.model.model,
            cwd=str(cwd),
            sandbox_mode=config.agent.sandbox_mode,
            approval_mode=config.agent.approval_mode,
        )
        controller = SessionController.resume(
            config=config,
            cwd=cwd,
            session_id=args.session_id,
            renderer=renderer,
        )
        prompt: str = args.prompt if args.prompt is not None else input("> ").strip()
        controller.run_task(user_input=prompt)
        return 0
    prompt: str = _resolve_prompt(args=args)
    if prompt == "":
        return _run_chat(config=config, cwd=cwd)
    renderer.show_session_header(
        base_url=config.model.base_url,
        model=config.model.model,
        cwd=str(cwd),
        sandbox_mode=config.agent.sandbox_mode,
        approval_mode=config.agent.approval_mode,
    )
    controller = SessionController(config=config, cwd=cwd, renderer=renderer)
    controller.run_task(user_input=prompt)
    return 0


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    options_parser: argparse.ArgumentParser = _build_options_parser()
    _, remainder = options_parser.parse_known_args(list(argv))
    if remainder and remainder[0] in _COMMAND_NAMES:
        return _build_command_parser().parse_args(list(argv))
    return _build_prompt_parser().parse_args(list(argv))


def _build_common_parser(add_help: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", add_help=add_help)
    _add_common_arguments(parser=parser)
    return parser


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="~/.agent/config.toml")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key")
    parser.add_argument("--api-key-env")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--approval")
    parser.add_argument("--sandbox")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--max-turns", type=int)
    parser.add_argument("--compact-trigger-tokens", type=int)
    parser.add_argument("--debug", action="store_true")


def _build_prompt_parser() -> argparse.ArgumentParser:
    parser = _build_common_parser(add_help=True)
    parser.add_argument("prompt", nargs="?")
    parser.set_defaults(command=None)
    return parser


def _build_options_parser() -> argparse.ArgumentParser:
    return _build_common_parser(add_help=False)


def _build_command_parser() -> argparse.ArgumentParser:
    parser = _build_common_parser(add_help=True)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("chat")
    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("session_id", nargs="?")
    resume_parser.add_argument("prompt", nargs="?")
    subparsers.add_parser("doctor")
    subparsers.add_parser("tui")
    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("init")
    return parser


def _build_overrides(args: argparse.Namespace) -> dict[str, object]:
    overrides: dict[str, object] = {}
    if args.base_url is not None:
        overrides["model.base_url"] = args.base_url
    if args.model is not None:
        overrides["model.model"] = args.model
    if args.api_key is not None:
        overrides["model.api_key"] = args.api_key
    if args.api_key_env is not None:
        overrides["model.api_key_env"] = args.api_key_env
    if args.approval is not None:
        overrides["agent.approval_mode"] = args.approval
    if args.sandbox is not None:
        overrides["agent.sandbox_mode"] = args.sandbox
    if args.max_turns is not None:
        overrides["agent.max_turns"] = args.max_turns
    if args.compact_trigger_tokens is not None:
        overrides["agent.compact_trigger_tokens"] = args.compact_trigger_tokens
    if args.stream and not args.no_stream:
        overrides["model.stream"] = True
    if args.no_stream:
        overrides["model.stream"] = False
    if args.debug:
        overrides["debug"] = True
    return overrides


def _resolve_prompt(args: argparse.Namespace) -> str:
    if args.command is None:
        return args.prompt or ""
    return ""


def _run_chat(config: AgentConfig, cwd: Path) -> int:
    renderer = Renderer(
        show_plan=config.ui.show_plan,
        show_tool_logs=config.ui.show_tool_logs,
        show_diff_summary=config.ui.show_diff_summary,
    )
    renderer.show_session_header(
        base_url=config.model.base_url,
        model=config.model.model,
        cwd=str(cwd),
        sandbox_mode=config.agent.sandbox_mode,
        approval_mode=config.agent.approval_mode,
    )
    controller = SessionController(config=config, cwd=cwd, renderer=renderer)
    while True:
        try:
            prompt: str = input("> ").strip()
        except EOFError:
            return 0
        except KeyboardInterrupt:
            print()
            return 0
        if prompt in {"exit", "quit"}:
            return 0
        controller.run_task(user_input=prompt)


def _run_tui(config: AgentConfig, cwd: Path) -> int:
    from agent_cli.tui_app import AgentTuiApp, SessionHeaderData

    controller = SessionController(config=config, cwd=cwd)
    app = AgentTuiApp(
        controller=controller,
        session_header=SessionHeaderData(
            base_url=config.model.base_url,
            model=config.model.model,
            cwd=str(cwd),
            sandbox_mode=config.agent.sandbox_mode,
            approval_mode=config.agent.approval_mode,
        ),
        show_plan=config.ui.show_plan,
        show_tool_logs=config.ui.show_tool_logs,
    )
    app.run()
    return 0


def _run_doctor(config: AgentConfig) -> int:
    models_url: str = f"{config.model.base_url.rstrip('/')}/models"
    responses_url: str = f"{config.model.base_url.rstrip('/')}/responses"
    workspace_root: Path = config.agent.workspace_root.resolve()
    memory_root: Path = (workspace_root / config.files.project_memory_dir).resolve()
    print(f"base_url={config.model.base_url}")
    print(f"model={config.model.model}")
    print(f"workspace_root={workspace_root}")
    print(f"sandbox_mode={config.agent.sandbox_mode}")
    print(f"approval_mode={config.agent.approval_mode}")
    print(f"project_memory_dir={memory_root}")
    print(f"workspace_exists={workspace_root.exists()}")
    print(f"project_memory_dir_parent_writable={os.access(memory_root.parent, os.W_OK)}")
    try:
        with urllib.request.urlopen(models_url, timeout=config.model.timeout_seconds) as response:
            print(f"models_status={response.status}")
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"models_probe_failed={exc}")
    request_body = json.dumps(
        {
            "model": config.model.model,
            "instructions": "Return short text.",
            "tools": [],
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "ping"}],
                }
            ],
            "stream": False,
            "store": False,
            "parallel_tool_calls": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url=responses_url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.model.timeout_seconds) as response:
            print(f"responses_status={response.status}")
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"doctor failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
