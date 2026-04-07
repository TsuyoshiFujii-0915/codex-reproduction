"""Agent loop and session controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import subprocess

from agent_cli.agents_loader import load_agents_text
from agent_cli.model_client import ResponsesModelClient
from agent_cli.plan_store import PlanStep, save_plan
from agent_cli.progress_store import save_progress
from agent_cli.prompt_builder import build_request
from agent_cli.renderer import Renderer
from agent_cli.responses_types import ModelResponse, RunResult
from agent_cli.storage.session_store import (
    SessionPaths,
    prepare_session_paths,
    prepare_specific_session_paths,
    save_session_snapshot,
)
from agent_cli.storage.transcript import append_transcript_event
from agent_cli.storage.transcript import read_transcript_events
from agent_cli.token_estimator import estimate_items_tokens
from agent_cli.tools.base import ToolExecutionContext, ToolProtocol, ToolResult
from agent_cli.tools.read_file import ReadFileTool
from agent_cli.tools.shell import ShellTool
from agent_cli.tools.update_plan import UpdatePlanTool
from agent_cli.tools.write_file import WriteFileTool
from agent_cli.policy import CommandPolicy


class InMemoryModelClient:
    """Deterministic in-memory model client for tests."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = responses[:]
        self.requests: list[dict[str, Any]] = []

    def create_response(self, request: dict[str, Any]) -> ModelResponse:
        self.requests.append(request)
        if self._responses == []:
            raise RuntimeError("in-memory model client ran out of queued responses")
        return self._responses.pop(0)


@dataclass(frozen=True)
class SessionState:
    """Persisted session snapshot."""

    session_id: str
    history_items: list[dict[str, Any]]
    plan: list[str]
    assistant_last_message: str | None
    compact_summary: str | None


@dataclass
class SessionController:
    """Coordinates the stateless agent loop."""

    config: Any
    cwd: Path
    model_client: Any | None = None
    session_id: str | None = None
    renderer: Renderer | None = None

    def __post_init__(self) -> None:
        if self.session_id is None:
            self._paths = prepare_session_paths(
                workspace_root=self.config.agent.workspace_root,
                project_memory_dir=self.config.files.project_memory_dir,
            )
        else:
            self._paths = prepare_specific_session_paths(
                workspace_root=self.config.agent.workspace_root,
                project_memory_dir=self.config.files.project_memory_dir,
                session_id=self.session_id,
            )
        if self.model_client is None:
            self.model_client = ResponsesModelClient(
                base_url=self.config.model.base_url,
                api_key=self.config.model.api_key or os.environ.get(self.config.model.api_key_env, ""),
                timeout_seconds=self.config.model.timeout_seconds,
                debug_output_path=(self._paths.memory_root / "debug" / "latest-stream.log")
                if self.config.debug
                else None,
            )
        if self.renderer is None:
            self.renderer = Renderer(
                show_plan=False,
                show_tool_logs=False,
                show_diff_summary=self.config.ui.show_diff_summary,
            )
        self._history_items: list[dict[str, Any]] = []
        self._tools: dict[str, ToolProtocol] = {
            "read_file": ReadFileTool(),
            "shell": ShellTool(),
            "update_plan": UpdatePlanTool(),
            "write_file": WriteFileTool(),
        }
        self._touched_files: set[str] = set()
        self._assistant_last_message: str | None = None

    @classmethod
    def resume(
        cls,
        config: Any,
        cwd: Path,
        model_client: Any | None = None,
        session_id: str | None = None,
        renderer: Renderer | None = None,
    ) -> "SessionController":
        """Create a controller from a saved session snapshot."""
        memory_root: Path = (config.agent.workspace_root / config.files.project_memory_dir).resolve()
        resolved_session_id: str = session_id or (memory_root / "latest_session.txt").read_text(encoding="utf-8").strip()
        controller = cls(
            config=config,
            cwd=cwd,
            model_client=model_client,
            session_id=resolved_session_id,
            renderer=renderer,
        )
        rebuilt_state: SessionState = _rebuild_session_state(paths=controller._paths)
        controller._history_items = rebuilt_state.history_items[:]
        controller._assistant_last_message = rebuilt_state.assistant_last_message
        return controller

    def run_task(self, user_input: str) -> RunResult:
        """Run one task until a final assistant message is produced."""
        agents_text: str = load_agents_text(
            current_dir=self.cwd,
            workspace_root=self.config.agent.workspace_root,
            home_dir=Path.home(),
            max_bytes=32 * 1024,
        )
        self._history_items.append(_message_item(role="user", text=user_input))
        self._emit_git_status()
        save_progress(
            progress_path=self._paths.progress_path,
            goal=user_input,
            what_was_done="Session started",
            current_state="Running",
            next_likely_action="Call the model",
            risks_and_open_questions="",
        )
        append_transcript_event(self._paths.transcript_path, "request", {"user_input": user_input})
        for _turn_index in range(self.config.agent.max_turns):
            request: dict[str, Any] = build_request(
                base_url=self.config.model.base_url,
                model_name=self.config.model.model,
                stream=self.config.model.stream,
                store=self.config.model.store,
                tools=[tool.schema() for tool in self._tools.values()],
                agent_settings=self.config.agent,
                cwd=self.cwd,
                agents_text=agents_text,
                history_items=self._history_items,
                user_input="",
            )
            self._write_debug_payload(turn_kind="request", turn_index=_turn_index, payload=request)
            response: ModelResponse = self.model_client.create_response(request)
            self._write_debug_payload(turn_kind="response", turn_index=_turn_index, payload=response.raw_response)
            append_transcript_event(self._paths.transcript_path, "response", response.raw_response)
            streamed: bool = self._render_stream_events(events=response.events)
            if self._contains_tool_calls(response.output_items):
                for item in response.output_items:
                    if item.get("type") != "function_call":
                        continue
                    result: ToolResult = self._execute_tool(call_item=item, current_goal=user_input)
                    self._history_items.append(item)
                    self._history_items.append(
                        {"type": "function_call_output", "call_id": item["call_id"], "output": result.output}
                    )
                    append_transcript_event(self._paths.transcript_path, "tool_call", item)
                    append_transcript_event(
                        self._paths.transcript_path,
                        "tool_result",
                        {"call_id": item["call_id"], "output": result.output, "metadata": result.metadata},
                    )
                compaction_event: dict[str, Any] | None = self._maybe_compact(user_input=user_input)
                if compaction_event is not None:
                    append_transcript_event(self._paths.transcript_path, "compaction", compaction_event)
                self._save_snapshot()
                continue
            assistant_text: str = self._extract_assistant_text(response.output_items)
            if assistant_text != "":
                self._history_items.extend(response.output_items)
                self._assistant_last_message = assistant_text
                if not streamed:
                    self.renderer.show_assistant_text(assistant_text)
                self.renderer.show_tool_log(f"touched_files={sorted(self._touched_files)}")
                append_transcript_event(self._paths.transcript_path, "assistant", {"text": assistant_text})
                save_progress(
                    progress_path=self._paths.progress_path,
                    goal=user_input,
                    what_was_done="Task finished",
                    current_state="Completed",
                    next_likely_action="None",
                    risks_and_open_questions="",
                )
                self._save_snapshot()
                return RunResult(
                    final_text=assistant_text,
                    touched_files=sorted(self._touched_files),
                    session_id=self._paths.session_id,
                )
        save_progress(
            progress_path=self._paths.progress_path,
            goal=user_input,
            what_was_done="Max turns reached",
            current_state="Stopped",
            next_likely_action="Resume session",
            risks_and_open_questions="Model did not emit a final assistant message.",
        )
        self._save_snapshot()
        return RunResult(
            final_text="",
            touched_files=sorted(self._touched_files),
            session_id=self._paths.session_id,
        )

    def _execute_tool(self, call_item: dict[str, Any], current_goal: str) -> ToolResult:
        tool_name: str = str(call_item.get("name", ""))
        arguments: dict[str, Any] = json.loads(str(call_item.get("arguments", "{}")))
        context = ToolExecutionContext(
            workspace_root=self.config.agent.workspace_root,
            agent_settings=self.config.agent,
            command_policy=CommandPolicy(),
            memory_root=self._paths.memory_root,
            current_goal=current_goal,
            approval_handler=self._request_approval,
        )
        tool: ToolProtocol = self._tools[tool_name]
        self.renderer.show_tool_log(f"{tool_name} {arguments}")
        try:
            result: ToolResult = tool.execute(arguments=arguments, context=context)
        except Exception as exc:  # noqa: BLE001
            error_type: str = type(exc).__name__
            error_output: str = "\n".join(
                [
                    "Tool execution failed.",
                    f"tool={tool_name}",
                    f"error_type={error_type}",
                    f"message={exc}",
                ]
            )
            self.renderer.show_tool_log(
                f"tool_error {tool_name} {error_type}: {exc}"
            )
            return ToolResult(
                ok=False,
                output=error_output,
                exit_code=None,
                metadata={"tool": tool_name, "error_type": error_type},
            )
        path_value: Any = result.metadata.get("path")
        if isinstance(path_value, str):
            self._touched_files.add(path_value)
        if tool_name == "update_plan":
            explanation: str = str(arguments.get("explanation", ""))
            self.renderer.show_plan_update(explanation)
            save_plan(
                plan_path=self._paths.plan_path,
                current_goal=current_goal,
                steps=[PlanStep(text=step, status="todo") for step in arguments["plan"]],
            )
        return result

    def _contains_tool_calls(self, items: list[dict[str, Any]]) -> bool:
        return any(item.get("type") == "function_call" for item in items)

    def _extract_assistant_text(self, items: list[dict[str, Any]]) -> str:
        for item in items:
            if item.get("type") != "message" or item.get("role") != "assistant":
                continue
            content: Any = item.get("content", [])
            if not isinstance(content, list):
                continue
            texts: list[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])
            return "".join(texts)
        return ""

    def _maybe_compact(self, user_input: str) -> dict[str, Any] | None:
        estimated_tokens: int = estimate_items_tokens(self._history_items)
        if estimated_tokens <= self.config.agent.compact_trigger_tokens:
            return None
        keep_count: int = max(1, self.config.agent.keep_last_turns_after_compact * 2)
        recent_items: list[dict[str, Any]] = self._history_items[-keep_count:]
        completed_plan_steps: list[str] = _load_plan_steps(plan_path=self._paths.plan_path)
        summary_text: str = "\n".join(
            [
                "# Compact Summary",
                "",
                "## Goal",
                user_input,
                "",
                "## Completed Work",
                ", ".join(completed_plan_steps) or "No recorded plan steps.",
                "",
                "## Changed Files",
                ", ".join(sorted(self._touched_files)) or "none",
                "",
                "## Important Observations",
                f"Compacted {len(self._history_items) - len(recent_items)} history items.",
                "",
                "## Unresolved Issues",
                "None recorded.",
                "",
                "## Next Likely Action",
                "Continue from retained recent items.",
            ]
        )
        self._paths.compact_summary_path.write_text(summary_text, encoding="utf-8")
        self._history_items = [_message_item(role="user", text=summary_text)] + recent_items
        return {"summary_text": summary_text, "retained_items": recent_items}

    def _request_approval(self, message: str) -> bool:
        prompt: str = f"{message} [y/N]: "
        try:
            answer: str = input(prompt).strip().lower()
        except EOFError:
            return False
        return answer in {"y", "yes"}

    def _save_snapshot(self) -> None:
        compact_summary: str | None = None
        if self._paths.compact_summary_path.exists():
            compact_summary = self._paths.compact_summary_path.read_text(encoding="utf-8")
        save_session_snapshot(
            paths=self._paths,
            session_state=SessionState(
                session_id=self._paths.session_id,
                history_items=self._history_items[:],
                plan=_load_plan_steps(plan_path=self._paths.plan_path),
                assistant_last_message=self._assistant_last_message,
                compact_summary=compact_summary,
            ),
        )

    def _render_stream_events(self, events: list[Any]) -> bool:
        printed_stream: bool = False
        for event in events:
            if getattr(event, "event", "") != "response.output_text.delta":
                continue
            data: Any = getattr(event, "data", {})
            if not isinstance(data, dict):
                continue
            delta: Any = data.get("delta")
            if not isinstance(delta, str):
                continue
            self.renderer.show_stream_text(delta)
            printed_stream = True
        if printed_stream:
            self.renderer.finish_stream()
        return printed_stream

    def _emit_git_status(self) -> None:
        git_status: str = _read_git_status(cwd=self.cwd)
        if git_status != "":
            self.renderer.show_tool_log(f"git_status\n{git_status}")

    def _write_debug_payload(self, turn_kind: str, turn_index: int, payload: dict[str, Any]) -> None:
        if not self.config.debug:
            return
        debug_dir: Path = self._paths.memory_root / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        target_path: Path = debug_dir / f"{turn_index:03d}-{turn_kind}.json"
        target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _message_item(role: str, text: str) -> dict[str, Any]:
    return {"type": "message", "role": role, "content": [{"type": "input_text", "text": text}]}


def _load_plan_steps(plan_path: Path) -> list[str]:
    if not plan_path.exists():
        return []
    payload: dict[str, Any] = json.loads(plan_path.read_text(encoding="utf-8"))
    raw_steps: Any = payload.get("steps", [])
    if not isinstance(raw_steps, list):
        return []
    result: list[str] = []
    for raw_step in raw_steps:
        if isinstance(raw_step, dict) and isinstance(raw_step.get("text"), str):
            result.append(raw_step["text"])
    return result


def _read_git_status(cwd: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:  # noqa: BLE001
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _rebuild_session_state(paths: SessionPaths) -> SessionState:
    transcript_events: list[dict[str, Any]] = read_transcript_events(paths.transcript_path)
    history_items: list[dict[str, Any]] = []
    assistant_last_message: str | None = None
    last_compaction_index: int = -1
    last_compaction_event: dict[str, Any] | None = None
    for index, event in enumerate(transcript_events):
        if event.get("kind") == "compaction":
            last_compaction_index = index
            last_compaction_event = event
    if last_compaction_event is not None:
        summary_text: str
        if paths.compact_summary_path.exists():
            summary_text = paths.compact_summary_path.read_text(encoding="utf-8")
        else:
            summary_text = str(last_compaction_event["data"]["summary_text"])
        history_items.append(_message_item(role="user", text=summary_text))
        retained_items: Any = last_compaction_event["data"].get("retained_items", [])
        if isinstance(retained_items, list):
            history_items.extend(item for item in retained_items if isinstance(item, dict))
    for event in transcript_events[last_compaction_index + 1 :]:
        kind: Any = event.get("kind")
        data: Any = event.get("data", {})
        if not isinstance(data, dict):
            continue
        if kind == "request":
            prompt_text: str | None = None
            user_input: Any = data.get("user_input")
            prompt: Any = data.get("prompt")
            if isinstance(user_input, str):
                prompt_text = user_input
            elif isinstance(prompt, str):
                prompt_text = prompt
            if prompt_text is not None:
                history_items.append(_message_item(role="user", text=prompt_text))
            continue
        if kind == "tool_call":
            history_items.append(data)
            continue
        if kind == "tool_result":
            call_id: Any = data.get("call_id")
            output: Any = data.get("output")
            if isinstance(call_id, str) and isinstance(output, str):
                history_items.append({"type": "function_call_output", "call_id": call_id, "output": output})
            continue
        if kind == "assistant":
            text: Any = data.get("text")
            if isinstance(text, str):
                assistant_last_message = text
                history_items.append(
                    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}
                )
    return SessionState(
        session_id=paths.session_id,
        history_items=history_items,
        plan=_load_plan_steps(paths.plan_path),
        assistant_last_message=assistant_last_message,
        compact_summary=paths.compact_summary_path.read_text(encoding="utf-8") if paths.compact_summary_path.exists() else None,
    )
