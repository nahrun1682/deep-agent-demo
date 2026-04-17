from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from deep_agent_demo.blackboard import AppSettings, BlackboardSnapshot, GoalDocument
from deep_agent_demo.runtime import (
    ChatRequest,
    DeepAgentsRuntime,
    DeepAgentsRuntimeFactory,
    OrchestratorOutput,
    candidate_env_files,
    resolve_memory_target,
)


class ToolFriendlyFake(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class _FakeInterrupt:
    value = {
        "action_requests": [{"tool_name": "promote_memory"}],
        "review_configs": [{"action_name": "promote_memory"}],
    }


class _FakeGraphOutput:
    def __init__(self, value, interrupts=()):
        self.value = value
        self.interrupts = interrupts


class _FakeAgent:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def invoke(self, input, config=None, version=None):
        self.calls.append(input)
        if len(self.calls) == 1:
            return _FakeGraphOutput(value=None, interrupts=(_FakeInterrupt(),))
        return _FakeGraphOutput(
            value=OrchestratorOutput(
                final_answer="done",
                snapshot=BlackboardSnapshot(goal=GoalDocument(request="hello")),
            ),
            interrupts=(),
        )


def test_runtime_factory_wires_deep_agents_subagents_memory_mcp_and_hitl(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)

        class FakeAgent:
            pass

        return FakeAgent()

    class FakeMcpClient:
        def __init__(self, servers):
            captured["mcp_servers"] = servers

        async def get_tools(self):
            return ["local_factbook"]

    monkeypatch.setattr("deep_agent_demo.runtime.create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("deep_agent_demo.runtime.MultiServerMCPClient", FakeMcpClient)

    settings = AppSettings(
        workspace_root=Path("/tmp/study-demo"),
        blackboard_root=Path("/tmp/study-demo/blackboard"),
        memory_root=Path("/tmp/study-demo/memories"),
    )
    factory = DeepAgentsRuntimeFactory(settings=settings, auto_approve_memory=True)

    runtime = factory.build()
    assert runtime.agent_factory is not None

    built_agent = asyncio.run(
        runtime.agent_factory(
            ChatRequest(
                message="hello",
                thread_id="thread-a",
                run_id="run-a",
                user_id="user-a",
            )
        )
    )

    assert built_agent is not None
    assert captured["model"] == "openai:gpt-4.1"
    assert len(captured["subagents"]) == 3
    assert [item["name"] for item in captured["subagents"]] == [
        "planner",
        "critic",
        "synthesizer",
    ]
    assert captured["skills"] == [str(Path(__file__).resolve().parents[1] / "skills" / "common")]
    assert captured["interrupt_on"]["promote_memory"] is True
    assert str(captured["backend"].routes["/blackboard/"].__dict__["cwd"]).endswith("user-a/thread-a/run-a")
    assert captured["mcp_servers"] == {
        "local-demo": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "deep_agent_demo.mcp_server"],
        }
    }


def test_promote_memory_target_rejects_path_traversal(tmp_path: Path) -> None:
    settings = AppSettings(
        workspace_root=tmp_path,
        blackboard_root=tmp_path / "blackboard",
        memory_root=tmp_path / "memories",
    )

    assert resolve_memory_target(settings, "/memories/study.md") == tmp_path / "memories" / "study.md"
    assert resolve_memory_target(settings, "/memory/study.md") == tmp_path / "memories" / "study.md"
    assert resolve_memory_target(settings, "memories/nested/note.md") == tmp_path / "memories" / "nested" / "note.md"
    assert resolve_memory_target(settings, "memory/nested/note.md") == tmp_path / "memories" / "nested" / "note.md"

    with pytest.raises(ValueError):
        resolve_memory_target(settings, "../escape.md")

    with pytest.raises(ValueError):
        resolve_memory_target(settings, "/tmp/escape.md")


def test_candidate_env_files_include_repo_and_codex_envs() -> None:
    files = candidate_env_files()

    assert Path.cwd() / ".env" in files
    assert Path.cwd() / ".codex" / ".env" in files


@pytest.mark.asyncio
async def test_runtime_auto_approves_memory_interrupts() -> None:
    runtime = DeepAgentsRuntime(
        agent=_FakeAgent(),
        settings=AppSettings(
            workspace_root=Path("/tmp/study-demo"),
            blackboard_root=Path("/tmp/study-demo/blackboard"),
            memory_root=Path("/tmp/study-demo/memories"),
        ),
        auto_approve_memory=True,
    )

    events = [event async for event in runtime.stream(ChatRequest(message="hello"))]

    assert [event.type for event in events] == ["progress", "hitl", "hitl", "blackboard", "final"]
    assert events[1].state == "pending"
    assert events[2].state == "approved"
    assert runtime.agent.calls[1].__class__.__name__ == "Command"


@pytest.mark.asyncio
async def test_runtime_can_stop_on_memory_interrupt_when_auto_approve_is_disabled() -> None:
    runtime = DeepAgentsRuntime(
        agent=_FakeAgent(),
        settings=AppSettings(
            workspace_root=Path("/tmp/study-demo"),
            blackboard_root=Path("/tmp/study-demo/blackboard"),
            memory_root=Path("/tmp/study-demo/memories"),
        ),
        auto_approve_memory=False,
    )

    events = [
        event
        async for event in runtime.stream(
            ChatRequest(message="hello", auto_approve_memory=False)
        )
    ]

    assert [event.type for event in events] == ["progress", "hitl"]
    assert events[1].state == "pending"
    assert len(runtime.agent.calls) == 1


def test_real_factory_with_fake_model_and_local_mcp_runs_end_to_end(tmp_path: Path) -> None:
    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "promote_memory",
                    "args": {
                        "path": "/memories/blackboard.md",
                        "content": "keep the blackboard observable",
                        "summary": "Blackboard stays as a projection layer",
                    },
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content='{"final_answer":"done","snapshot":{"goal":{"request":"hello"}}}',
        ),
    ]
    model = ToolFriendlyFake(responses=responses)
    settings = AppSettings(
        workspace_root=tmp_path,
        blackboard_root=tmp_path / "blackboard",
        memory_root=tmp_path / "memories",
    )

    runtime = DeepAgentsRuntimeFactory(settings=settings, model=model).build()

    async def run() -> list[str]:
        events = [
            event
            async for event in runtime.stream(ChatRequest(message="hello"))
        ]
        assert events[0].type == "progress"
        assert any(event.type == "hitl" and event.state == "pending" for event in events)
        assert any(event.type == "hitl" and event.state == "approved" for event in events)
        assert events[-1].type == "final"
        assert events[-1].final_answer == "done"
        return [event.type for event in events]

    assert "final" in asyncio.run(run())
