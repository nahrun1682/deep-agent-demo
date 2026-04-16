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
        message="Give a one-sentence summary of the blackboard pattern.",
        auto_approve_memory=True,
        thread_id="real-thread",
        run_id="real-run",
        user_id="local-user",
    )
    app = create_app(runtime_factory=DeepAgentsRuntimeFactory(settings=settings, model="openai:gpt-4.1"))

    async def run() -> str:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chat", json=request.model_dump())
        assert response.status_code == 200
        return response.text

    response_text = asyncio.run(run())
    assert "event: progress" in response_text
    assert "event: final" in response_text
    assert resolve_runtime_scope(app.state.settings, request).blackboard_root.joinpath("goal.md").exists()
