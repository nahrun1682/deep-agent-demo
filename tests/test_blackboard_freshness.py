from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from deep_agent_demo.app import create_app
from deep_agent_demo.blackboard import (
    BlackboardSnapshot,
    GoalDocument,
    PlanDocument,
    PlanStep,
    StateSummary,
)
from deep_agent_demo.runtime import ChatRequest, RuntimeEvent


class WritingRuntime:
    def __init__(self, blackboard_root: Path) -> None:
        self.blackboard_root = blackboard_root

    async def stream(self, request: ChatRequest):
        plan_path = self.blackboard_root / "plan.md"
        plan_path.write_text("runtime plan", encoding="utf-8")
        trace_path = self.blackboard_root / "trace.md"
        trace_path.write_text("runtime trace", encoding="utf-8")

        yield RuntimeEvent.progress(actor="Planner", message="Planning started", step="planner")
        yield RuntimeEvent.blackboard(
            artifacts={
                "plan.md": plan_path.read_text(encoding="utf-8"),
                "trace.md": trace_path.read_text(encoding="utf-8"),
            }
        )
        yield RuntimeEvent.final(
            final_answer="done",
            snapshot=BlackboardSnapshot(
                goal=GoalDocument(request=request.message),
                plan=PlanDocument(overview="runtime plan", steps=[PlanStep(order=1, title="run", detail="write files")]),
                state_summary=StateSummary(
                    headline="done",
                    status="complete",
                    current_focus="none",
                ),
            ),
        )


@pytest.mark.asyncio
async def test_chat_refreshes_blackboard_and_emits_current_artifacts(tmp_path: Path) -> None:
    blackboard_root = tmp_path / "blackboard"
    blackboard_root.mkdir(parents=True, exist_ok=True)
    (blackboard_root / "goal.md").write_text("stale goal", encoding="utf-8")
    (blackboard_root / "plan.md").write_text("stale plan", encoding="utf-8")
    (blackboard_root / "trace.md").write_text("stale trace", encoding="utf-8")

    app = create_app(
        settings_overrides={
            "workspace_root": tmp_path,
            "blackboard_root": blackboard_root,
            "memory_root": tmp_path / "memories",
        },
        runtime=WritingRuntime(blackboard_root),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json={"message": "fresh run", "auto_approve_memory": True},
        )

    assert response.status_code == 200
    assert "stale plan" not in response.text
    assert "runtime plan" in response.text
    assert "runtime trace" in response.text
    assert (blackboard_root / "plan.md").read_text(encoding="utf-8") == "runtime plan"
    assert (blackboard_root / "trace.md").read_text(encoding="utf-8") == "runtime trace"
    assert (blackboard_root / "goal.md").read_text(encoding="utf-8") != "stale goal"

