from __future__ import annotations

import asyncio
import json
import queue
import sys
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Literal

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from deep_agent_demo.blackboard import (
    AppSettings,
    BlackboardSnapshot,
    GoalDocument,
)


class ChatRequest(BaseModel):
    message: str
    auto_approve_memory: bool = True
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "local-user"


@dataclass(frozen=True, slots=True)
class RuntimeScope:
    user_id: str
    thread_id: str
    run_id: str
    blackboard_root: Path
    memory_root: Path

    @property
    def checkpoint_thread_id(self) -> str:
        return f"{self.user_id}:{self.thread_id}:{self.run_id}"


class RuntimeEvent(BaseModel):
    type: Literal["progress", "blackboard", "hitl", "final"]
    actor: str | None = None
    message: str | None = None
    step: str | None = None
    state: str | None = None
    action: str | None = None
    snapshot: BlackboardSnapshot | None = None
    artifacts: dict[str, str] | None = None
    final_answer: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def progress(cls, *, actor: str, message: str, step: str | None = None) -> "RuntimeEvent":
        return cls(type="progress", actor=actor, message=message, step=step)

    @classmethod
    def blackboard(
        cls,
        *,
        snapshot: BlackboardSnapshot | None = None,
        artifacts: dict[str, str] | None = None,
    ) -> "RuntimeEvent":
        return cls(type="blackboard", snapshot=snapshot, artifacts=artifacts)

    @classmethod
    def hitl(cls, *, action: str, state: str, message: str) -> "RuntimeEvent":
        return cls(type="hitl", action=action, state=state, message=message)

    @classmethod
    def final(cls, *, final_answer: str, snapshot: BlackboardSnapshot) -> "RuntimeEvent":
        return cls(type="final", final_answer=final_answer, snapshot=snapshot)


class OrchestratorOutput(BaseModel):
    final_answer: str
    snapshot: BlackboardSnapshot


@dataclass(slots=True)
class DeepAgentsRuntimeFactory:
    settings: AppSettings
    auto_approve_memory: bool = True
    model: Any = "openai:gpt-4.1"

    def build(self) -> "DeepAgentsRuntime":
        load_demo_environment()
        return DeepAgentsRuntime(
            settings=self.settings,
            auto_approve_memory=self.auto_approve_memory,
            agent_factory=self._build_agent_for_request,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[RuntimeEvent]:
        runtime = self.build()
        async for event in runtime.stream(request):
            yield event

    async def _build_agent_for_request(self, request: ChatRequest) -> Any:
        scope = resolve_runtime_scope(self.settings, request)
        return await self._build_agent(scope)

    async def _build_agent(self, scope: RuntimeScope) -> Any:
        settings = _scope_settings(self.settings, scope)
        mcp_tools = await self._load_mcp_tools()
        return create_deep_agent(
            name="blackboard-orchestrator",
            model=self.model,
            system_prompt=_orchestrator_system_prompt(),
            tools=[_build_promote_memory_tool(settings), *mcp_tools],
            subagents=[
                _build_subagent_config(
                    name="planner",
                    description="Plans blackboard-centered execution steps.",
                    system_prompt=_planner_system_prompt(),
                    skill_dirs=[_skills_root() / "common", _skills_root() / "planner"],
                    tools=mcp_tools,
                    permissions=_role_permissions(settings, can_write_memory=False),
                ),
                _build_subagent_config(
                    name="critic",
                    description="Finds risks and gaps in the plan.",
                    system_prompt=_critic_system_prompt(),
                    skill_dirs=[_skills_root() / "common", _skills_root() / "critic"],
                    tools=mcp_tools,
                    permissions=_role_permissions(settings, can_write_memory=False),
                ),
                _build_subagent_config(
                    name="synthesizer",
                    description="Synthesizes planner and critic output into a final strategy.",
                    system_prompt=_synthesizer_system_prompt(),
                    skill_dirs=[_skills_root() / "common", _skills_root() / "synthesizer"],
                    tools=mcp_tools,
                    permissions=_role_permissions(settings, can_write_memory=False),
                ),
            ],
            skills=[str(_skills_root() / "common")],
            memory=[str(settings.memory_root / "study-notes.md")],
            permissions=_role_permissions(settings, can_write_memory=True),
            backend=_build_backend(settings),
            checkpointer=MemorySaver(),
            interrupt_on={"promote_memory": True},
            response_format=OrchestratorOutput,
        )

    async def _load_mcp_tools(self) -> list[Any]:
        client = MultiServerMCPClient(
            {
                "local-demo": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": ["-m", "deep_agent_demo.mcp_server"],
                }
            }
        )
        return await client.get_tools()


@dataclass(slots=True)
class DeepAgentsRuntime:
    settings: AppSettings
    agent: Any | None = None
    agent_factory: Callable[[ChatRequest], Awaitable[Any]] | None = None
    auto_approve_memory: bool = True

    async def stream(self, request: ChatRequest) -> AsyncIterator[RuntimeEvent]:
        agent = self.agent
        if agent is None:
            if self.agent_factory is None:
                raise RuntimeError("DeepAgentsRuntime requires an agent or an agent_factory")
            agent = await self.agent_factory(request)
        scope = resolve_runtime_scope(self.settings, request)
        events: "queue.Queue[RuntimeEvent | Exception | object]" = queue.Queue()
        sentinel = object()
        worker = threading.Thread(
            target=self._run_stream,
            args=(request, scope, agent, events, sentinel),
            daemon=True,
        )
        worker.start()

        while True:
            item = await asyncio.to_thread(events.get)
            if item is sentinel:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    def _run_stream(
        self,
        request: ChatRequest,
        scope: RuntimeScope,
        agent: Any,
        events: "queue.Queue[RuntimeEvent | Exception | object]",
        sentinel: object,
    ) -> None:
        try:
            self._emit_stream_events(request, scope, agent, events)
        except Exception as exc:  # pragma: no cover - surfaced in async consumer
            events.put(exc)
        finally:
            events.put(sentinel)

    def _emit_stream_events(
        self,
        request: ChatRequest,
        scope: RuntimeScope,
        agent: Any,
        events: "queue.Queue[RuntimeEvent | Exception | object]",
    ) -> None:
        events.put(RuntimeEvent.progress(actor="Orchestrator", message="Starting deep agent run", step="start"))
        base_snapshot = _seed_snapshot(request)
        final_snapshot = base_snapshot
        last_ai_content = ""
        interrupt_payload: dict[str, Any] | None = None

        if not hasattr(agent, "stream"):
            self._emit_legacy_events(agent, request, scope, events, base_snapshot)
            return

        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": request.message}]},
            config={"configurable": {"thread_id": _graph_thread_id(request), "user_id": request.user_id}},
            stream_mode=["updates", "messages"],
            subgraphs=True,
            version="v2",
        ):
            if chunk["type"] == "updates":
                updates = chunk["data"]
                if "__interrupt__" in updates:
                    interrupt_payload = _interrupt_payload(updates["__interrupt__"])
                    events.put(
                        RuntimeEvent.hitl(
                            action="promote_memory",
                            state="pending",
                            message="Memory write needs approval",
                        )
                    )
                    break
                events.put(
                    RuntimeEvent.progress(
                        actor=_chunk_actor(chunk["ns"], None),
                        message=_summarize_updates(updates),
                        step=_step_name(updates),
                    )
                )
                events.put(RuntimeEvent.blackboard(artifacts=_read_blackboard_artifacts(scope.blackboard_root)))
                continue

            token, metadata = chunk["data"]
            actor = _chunk_actor(chunk["ns"], metadata)
            if getattr(token, "tool_calls", None):
                tool_names = ", ".join(call.get("name", "tool") for call in token.tool_calls)
                events.put(RuntimeEvent.progress(actor=actor, message=f"Requested tools: {tool_names}", step="tool_calls"))
            elif getattr(token, "type", None) == "tool":
                events.put(
                    RuntimeEvent.progress(
                        actor=actor,
                        message=f"Tool result [{getattr(token, 'name', 'tool')}]: {_truncate(getattr(token, 'content', ''))}",
                        step="tool_result",
                    )
                )
                if getattr(token, "name", "") in {"write_file", "edit_file", "promote_memory"}:
                    events.put(RuntimeEvent.blackboard(artifacts=_read_blackboard_artifacts(scope.blackboard_root)))
            elif getattr(token, "type", None) == "ai" and getattr(token, "content", ""):
                last_ai_content = token.content
                events.put(RuntimeEvent.progress(actor=actor, message=_truncate(token.content), step="message"))

        if interrupt_payload is not None:
            if not request.auto_approve_memory or not self.auto_approve_memory:
                return
            events.put(
                RuntimeEvent.hitl(
                    action="promote_memory",
                    state="approved",
                    message="Memory write auto-approved",
                )
            )
            resume_result = agent.invoke(
                Command(resume={"decisions": [{"type": "approve"} for _ in interrupt_payload["action_requests"]]}),
                config={"configurable": {"thread_id": _graph_thread_id(request), "user_id": request.user_id}},
                version="v2",
            )
            output = _coerce_output(resume_result.value, fallback_snapshot=final_snapshot)
            events.put(RuntimeEvent.blackboard(snapshot=output.snapshot, artifacts=_read_blackboard_artifacts(scope.blackboard_root)))
            events.put(RuntimeEvent.final(final_answer=output.final_answer, snapshot=output.snapshot))
            return

        output = _coerce_output_from_text(last_ai_content, fallback_snapshot=base_snapshot)
        events.put(RuntimeEvent.blackboard(snapshot=output.snapshot, artifacts=_read_blackboard_artifacts(scope.blackboard_root)))
        events.put(RuntimeEvent.final(final_answer=output.final_answer, snapshot=output.snapshot))

    def _emit_legacy_events(
        self,
        agent: Any,
        request: ChatRequest,
        scope: RuntimeScope,
        events: "queue.Queue[RuntimeEvent | Exception | object]",
        base_snapshot: BlackboardSnapshot,
    ) -> None:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": request.message}]},
            config={"configurable": {"thread_id": _graph_thread_id(request), "user_id": request.user_id}},
            version="v2",
        )
        if getattr(result, "interrupts", ()):
            events.put(
                RuntimeEvent.hitl(
                    action="promote_memory",
                    state="pending",
                    message="Memory write needs approval",
                )
            )
            if not request.auto_approve_memory or not self.auto_approve_memory:
                return
            events.put(
                RuntimeEvent.hitl(
                    action="promote_memory",
                    state="approved",
                    message="Memory write auto-approved",
                )
            )
            result = agent.invoke(
                Command(resume={"decisions": [{"type": "approve"} for _ in _interrupt_payload(result.interrupts)["action_requests"]]}),
                config={"configurable": {"thread_id": _graph_thread_id(request), "user_id": request.user_id}},
                version="v2",
            )

        output = _coerce_output(result.value, fallback_snapshot=base_snapshot)
        events.put(RuntimeEvent.blackboard(snapshot=output.snapshot))
        events.put(RuntimeEvent.final(final_answer=output.final_answer, snapshot=output.snapshot))


def _build_subagent_config(
    *,
    name: str,
    description: str,
    system_prompt: str,
    skill_dirs: list[Path],
    tools: list[Any],
    permissions: list[FilesystemPermission],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "system_prompt": system_prompt,
        "skills": [str(path) for path in skill_dirs],
        "tools": tools,
        "permissions": permissions,
        "response_format": BlackboardSnapshot,
    }


def _build_backend(settings: AppSettings):
    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/blackboard/": FilesystemBackend(root_dir=settings.blackboard_root, virtual_mode=True),
            "/memories/": FilesystemBackend(root_dir=settings.memory_root, virtual_mode=True),
        },
    )


def _role_permissions(settings: AppSettings, *, can_write_memory: bool) -> list[FilesystemPermission]:
    permissions = [
        FilesystemPermission(operations=["read", "write"], paths=["/blackboard/"], mode="allow"),
        FilesystemPermission(operations=["read", "write"], paths=[str(settings.blackboard_root)], mode="allow"),
    ]
    if can_write_memory:
        permissions.extend(
            [
                FilesystemPermission(operations=["read", "write"], paths=["/memories/"], mode="allow"),
                FilesystemPermission(operations=["read", "write"], paths=[str(settings.memory_root)], mode="allow"),
            ]
        )
    else:
        permissions.extend(
            [
                FilesystemPermission(operations=["read"], paths=["/memories/"], mode="allow"),
                FilesystemPermission(operations=["read"], paths=[str(settings.memory_root)], mode="allow"),
            ]
        )
    permissions.append(FilesystemPermission(operations=["read", "write"], paths=["/.env", "/**/.env"], mode="deny"))
    return permissions


def _build_promote_memory_tool(settings: AppSettings):
    @tool("promote_memory")
    def promote_memory(path: str, content: str, summary: str) -> str:
        """Persist a proposed memory entry under the configured memory root."""
        target = resolve_memory_target(settings, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "\n".join(
                [
                    "# Memory Entry",
                    "",
                    "## Summary",
                    summary,
                    "",
                    "## Content",
                    content,
                ]
            ),
            encoding="utf-8",
        )
        return f"Saved memory to {target.relative_to(settings.memory_root)}"

    return promote_memory


def resolve_runtime_scope(settings: AppSettings, request: ChatRequest) -> RuntimeScope:
    user_id = _safe_path_component(request.user_id, field_name="user_id")
    thread_id = _safe_path_component(request.thread_id, field_name="thread_id")
    run_id = _safe_path_component(request.run_id, field_name="run_id")
    return RuntimeScope(
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        blackboard_root=settings.blackboard_root / user_id / thread_id / run_id,
        memory_root=settings.memory_root / user_id,
    )


def _scope_settings(settings: AppSettings, scope: RuntimeScope) -> AppSettings:
    return AppSettings(
        workspace_root=settings.workspace_root,
        blackboard_root=scope.blackboard_root,
        memory_root=scope.memory_root,
    )


def resolve_memory_target(settings: AppSettings, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        parts = candidate.parts
        if len(parts) < 2 or parts[1] != "memories":
            raise ValueError("promote_memory path must start with /memories/")
        candidate = Path(*parts[2:])
    elif candidate.parts and candidate.parts[0] == "memories":
        candidate = Path(*candidate.parts[1:])

    if not candidate.parts:
        raise ValueError("promote_memory path must include a file name")

    root = settings.memory_root.resolve()
    target = (settings.memory_root / candidate).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("promote_memory path escapes the configured memory root") from exc
    return target


def _coerce_output(value: Any, *, fallback_snapshot: BlackboardSnapshot) -> OrchestratorOutput:
    if isinstance(value, OrchestratorOutput):
        return value
    if isinstance(value, dict):
        if "final_answer" in value and "snapshot" in value:
            return OrchestratorOutput.model_validate(value)
        state_output = _output_from_state_dict(value, fallback_snapshot=fallback_snapshot)
        if state_output is not None:
            return state_output
        return OrchestratorOutput.model_validate(value)
    if value is None:
        return OrchestratorOutput(final_answer="completed", snapshot=fallback_snapshot)
    if hasattr(value, "model_dump"):
        return OrchestratorOutput.model_validate(value.model_dump())
    raise TypeError(f"Unexpected agent output type: {type(value)!r}")


def _output_from_state_dict(value: dict[str, Any], *, fallback_snapshot: BlackboardSnapshot) -> OrchestratorOutput | None:
    messages = value.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        if not content:
            continue
        if isinstance(content, list):
            content = "".join(part if isinstance(part, str) else str(part) for part in content)
        return _coerce_output_from_text(str(content), fallback_snapshot=fallback_snapshot)
    return None


def _coerce_output_from_text(text: str, *, fallback_snapshot: BlackboardSnapshot) -> OrchestratorOutput:
    if not text.strip():
        return OrchestratorOutput(final_answer="completed", snapshot=fallback_snapshot)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return OrchestratorOutput(final_answer=text.strip(), snapshot=fallback_snapshot)
    return _coerce_output(data, fallback_snapshot=fallback_snapshot)


def _interrupt_payload(interrupts: Any) -> dict[str, Any]:
    first = interrupts[0]
    value = getattr(first, "value", first)
    if isinstance(value, dict):
        return value
    return value.model_dump(mode="python")


def _seed_snapshot(request: ChatRequest) -> BlackboardSnapshot:
    return BlackboardSnapshot(goal=GoalDocument(request=request.message, context_notes=[f"auto_approve_memory={request.auto_approve_memory}"]))


def _skills_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills"


def load_demo_environment() -> None:
    for candidate in candidate_env_files():
        if candidate.exists():
            load_dotenv(candidate, override=False)


def candidate_env_files() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    return [
        Path.cwd() / ".env",
        Path.cwd() / ".codex" / ".env",
        root / ".env",
        root / ".codex" / ".env",
    ]


def _chunk_actor(namespace: tuple[str, ...], metadata: dict[str, Any] | None) -> str:
    if metadata and metadata.get("lc_agent_name"):
        return str(metadata["lc_agent_name"])
    if not namespace:
        return "Orchestrator"
    return namespace[-1]


def _summarize_updates(updates: dict[str, Any]) -> str:
    return ", ".join(updates.keys()) if updates else "agent step"


def _step_name(updates: dict[str, Any]) -> str | None:
    if not updates:
        return None
    return next(iter(updates.keys()))


def _truncate(text: str, limit: int = 160) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "…"


def _safe_path_component(value: str, *, field_name: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{field_name} must be a single safe path component")
    if Path(value).is_absolute():
        raise ValueError(f"{field_name} must be relative")
    return value


def _graph_thread_id(request: ChatRequest) -> str:
    return ":".join(
        [
            _safe_path_component(request.user_id, field_name="user_id"),
            _safe_path_component(request.thread_id, field_name="thread_id"),
            _safe_path_component(request.run_id, field_name="run_id"),
        ]
    )


def _read_blackboard_artifacts(root: Path) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for relative_path in (
        "goal.md",
        "plan.md",
        "critique.md",
        "synthesis.md",
        "trace.md",
        "memory-proposals.md",
        "mcp-log.md",
        "state-summary.md",
        "decisions.md",
        "open-questions.md",
    ):
        path = root / relative_path
        if path.exists():
            artifacts[relative_path] = path.read_text(encoding="utf-8")
    return artifacts


def _orchestrator_system_prompt() -> str:
    return (
        "You are the orchestrator for a study demo about the blackboard pattern.\n"
        "Use the Planner, Critic, and Synthesizer subagents in that order.\n"
        "Keep the blackboard markdown files updated as you go.\n"
        "Use MCP tools when external facts help.\n"
        "When memory should persist, call promote_memory and let the controller auto-approve it when configured.\n"
        "Return a final structured answer with the merged blackboard snapshot."
    )


def _planner_system_prompt() -> str:
    return (
        "You are Planner.\n"
        "Read the goal and current blackboard state.\n"
        "Produce a concrete plan, trace entries, and memory proposals.\n"
        "Write or update plan.md and collaborate through the blackboard."
    )


def _critic_system_prompt() -> str:
    return (
        "You are Critic.\n"
        "Read the goal and plan.\n"
        "Find gaps, risks, and failure modes.\n"
        "Update critique.md and add trace entries, memory proposals, and open questions."
    )


def _synthesizer_system_prompt() -> str:
    return (
        "You are Synthesizer.\n"
        "Read the plan and critique.\n"
        "Reconcile the arguments into a final strategy.\n"
        "Update synthesis.md and provide decisions, trace entries, and memory proposals."
    )
