from __future__ import annotations

import asyncio
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from deep_agent_demo.blackboard import (
    AppSettings,
    BlackboardSnapshot,
    DecisionEntry,
    GoalDocument,
    MemoryProposal,
    McpUsageRecord,
    OpenQuestion,
    PlanDocument,
    PlanStep,
    StateSummary,
    SynthesisDocument,
    TraceEntry,
)


class ChatRequest(BaseModel):
    message: str
    auto_approve_memory: bool = True
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "local-user"


class RuntimeEvent(BaseModel):
    type: Literal["progress", "blackboard", "hitl", "final"]
    actor: str | None = None
    message: str | None = None
    step: str | None = None
    state: str | None = None
    action: str | None = None
    snapshot: BlackboardSnapshot | None = None
    final_answer: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def progress(cls, *, actor: str, message: str, step: str | None = None) -> "RuntimeEvent":
        return cls(type="progress", actor=actor, message=message, step=step)

    @classmethod
    def blackboard(cls, *, snapshot: BlackboardSnapshot) -> "RuntimeEvent":
        return cls(type="blackboard", snapshot=snapshot)

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
    model: str = "openai:gpt-4.1"

    def build(self) -> "DeepAgentsRuntime":
        load_demo_environment()
        mcp_tools = asyncio.run(self._load_mcp_tools())
        agent = create_deep_agent(
            name="blackboard-orchestrator",
            model=self.model,
            system_prompt=_orchestrator_system_prompt(),
            tools=[_build_promote_memory_tool(self.settings), *mcp_tools],
            subagents=[
                _build_subagent_config(
                    name="planner",
                    description="Plans blackboard-centered execution steps.",
                    system_prompt=_planner_system_prompt(),
                    skill_dirs=[
                        _skills_root() / "common",
                        _skills_root() / "planner",
                    ],
                    tools=mcp_tools,
                    permissions=_role_permissions(self.settings, can_write_memory=False),
                ),
                _build_subagent_config(
                    name="critic",
                    description="Finds risks and gaps in the plan.",
                    system_prompt=_critic_system_prompt(),
                    skill_dirs=[
                        _skills_root() / "common",
                        _skills_root() / "critic",
                    ],
                    tools=mcp_tools,
                    permissions=_role_permissions(self.settings, can_write_memory=False),
                ),
                _build_subagent_config(
                    name="synthesizer",
                    description="Synthesizes planner and critic output into a final strategy.",
                    system_prompt=_synthesizer_system_prompt(),
                    skill_dirs=[
                        _skills_root() / "common",
                        _skills_root() / "synthesizer",
                    ],
                    tools=mcp_tools,
                    permissions=_role_permissions(self.settings, can_write_memory=False),
                ),
            ],
            skills=[str(_skills_root() / "common")],
            memory=[str(self.settings.memory_root / "study-notes.md")],
            permissions=_role_permissions(self.settings, can_write_memory=True),
            backend=_build_backend(self.settings),
            checkpointer=MemorySaver(),
            interrupt_on={"promote_memory": True},
            response_format=OrchestratorOutput,
        )
        return DeepAgentsRuntime(agent=agent, settings=self.settings, auto_approve_memory=self.auto_approve_memory)

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
    agent: Any
    settings: AppSettings
    auto_approve_memory: bool = True

    async def stream(self, request: ChatRequest) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent.progress(actor="Orchestrator", message="Starting deep agent run", step="start")

        result = await asyncio.to_thread(self._invoke, request)
        while getattr(result, "interrupts", ()):
            interrupt_payload = _interrupt_payload(result.interrupts)
            yield RuntimeEvent.hitl(
                action="promote_memory",
                state="pending",
                message="Memory write needs approval",
            )
            if not request.auto_approve_memory or not self.auto_approve_memory:
                return
            result = await asyncio.to_thread(self._resume, request, interrupt_payload)
            yield RuntimeEvent.hitl(
                action="promote_memory",
                state="approved",
                message="Memory write auto-approved",
            )

        output = _coerce_output(result.value)
        if output.snapshot.goal is not None:
            yield RuntimeEvent.blackboard(snapshot=output.snapshot)
        yield RuntimeEvent.final(final_answer=output.final_answer, snapshot=output.snapshot)

    def _invoke(self, request: ChatRequest):
        return self.agent.invoke(
            {"messages": [{"role": "user", "content": request.message}]},
            config={"configurable": {"thread_id": request.thread_id, "user_id": request.user_id}},
            version="v2",
        )

    def _resume(self, request: ChatRequest, interrupt_payload: dict[str, Any]):
        decisions = [{"type": "approve"} for _ in interrupt_payload["action_requests"]]
        return self.agent.invoke(
            Command(resume={"decisions": decisions}),
            config={"configurable": {"thread_id": request.thread_id, "user_id": request.user_id}},
            version="v2",
        )


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
    def factory(_runtime: Any) -> CompositeBackend:
        return CompositeBackend(
            default=StateBackend(_runtime),
            routes={
                "/blackboard/": FilesystemBackend(root_dir=settings.blackboard_root, virtual_mode=True),
                "/memories/": FilesystemBackend(root_dir=settings.memory_root, virtual_mode=True),
            },
        )

    return factory


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
        target = _memory_target(settings, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "\n".join(
                [
                    "# Memory Entry",
                    "",
                    f"## Summary",
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


def _memory_target(settings: AppSettings, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        candidate = Path(*candidate.parts[1:])
    if candidate.parts and candidate.parts[0] == "memories":
        candidate = Path(*candidate.parts[1:])
    return settings.memory_root / candidate


def _coerce_output(value: Any) -> OrchestratorOutput:
    if isinstance(value, OrchestratorOutput):
        return value
    if isinstance(value, dict):
        return OrchestratorOutput.model_validate(value)
    raise TypeError(f"Unexpected agent output type: {type(value)!r}")


def _interrupt_payload(interrupts: Any) -> dict[str, Any]:
    first = interrupts[0]
    value = getattr(first, "value", first)
    if isinstance(value, dict):
        return value
    return value.model_dump(mode="python")


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
