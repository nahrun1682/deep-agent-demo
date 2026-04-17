from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from deep_agent_demo.app import create_app
from deep_agent_demo.blackboard import AppSettings
from deep_agent_demo.runtime import ChatRequest, DeepAgentsRuntimeFactory, resolve_runtime_scope


pytestmark = pytest.mark.skipif(
    os.getenv("DEEP_AGENT_DEMO_RUN_REAL_E2E") != "1" or not os.getenv("OPENAI_API_KEY"),
    reason="Set DEEP_AGENT_DEMO_RUN_REAL_E2E=1 and OPENAI_API_KEY to run the real OpenAI-backed E2E validation.",
)


@pytest.mark.integration
def test_real_openai_backed_runtime_path_with_local_mcp(tmp_path: Path) -> None:
    settings = AppSettings(
        workspace_root=tmp_path,
        blackboard_root=tmp_path / "blackboard",
        memory_root=tmp_path / "memories",
    )
    request = ChatRequest(
        message="黒板パターンを使って OSS 公開計画を立てて",
        auto_approve_memory=True,
        thread_id="real-thread",
        run_id="real-run",
        user_id="local-user",
    )
    app = create_app(runtime_factory=DeepAgentsRuntimeFactory(settings=settings, model="openai:gpt-4.1"))

    async def run() -> list[str]:
        events: list[str] = []
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/chat", json=request.model_dump()) as response:
                assert response.status_code == 200
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        events.append(line.removeprefix("event: "))
                        if line == "event: final":
                            break
        return events

    event_names = asyncio.run(run())
    assert event_names[0] == "progress"
    assert "blackboard" in event_names
    assert event_names[-1] == "final"
    blackboard_root = resolve_runtime_scope(app.state.settings, request).blackboard_root
    assert blackboard_root.joinpath("goal.md").exists()
    assert "No plan has been recorded yet." not in blackboard_root.joinpath("plan.md").read_text(encoding="utf-8")
    assert "No critique has been recorded yet." not in blackboard_root.joinpath("critique.md").read_text(encoding="utf-8")
    assert "No synthesis has been recorded yet." not in blackboard_root.joinpath("synthesis.md").read_text(encoding="utf-8")
    assert "No trace entries recorded yet." not in blackboard_root.joinpath("trace.md").read_text(encoding="utf-8")
