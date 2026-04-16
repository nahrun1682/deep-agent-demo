from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from deep_agent_demo.blackboard import AppSettings
from deep_agent_demo.runtime import ChatRequest, DeepAgentsRuntimeFactory


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
    runtime = DeepAgentsRuntimeFactory(settings=settings, model="openai:gpt-4.1").build()

    async def run() -> list[str]:
        events = [
            event
            async for event in runtime.stream(
                ChatRequest(message="Give a one-sentence summary of the blackboard pattern.", auto_approve_memory=True)
            )
        ]
        assert events
        assert events[-1].type == "final"
        return [event.type for event in events]

    event_types = asyncio.run(run())
    assert "progress" in event_types
    assert "final" in event_types
    assert (tmp_path / "blackboard" / "goal.md").exists()
