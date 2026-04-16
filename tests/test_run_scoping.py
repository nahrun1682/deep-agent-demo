from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from deep_agent_demo.app import create_app
from deep_agent_demo.blackboard import AppSettings, BlackboardSnapshot, GoalDocument, PlanDocument, PlanStep, StateSummary
from deep_agent_demo.runtime import ChatRequest, RuntimeEvent, resolve_runtime_scope


class ScopedWritingRuntime:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.requests: list[ChatRequest] = []

    async def stream(self, request: ChatRequest):
        self.requests.append(request)
        scope = resolve_runtime_scope(self.settings, request)
        scope.blackboard_root.mkdir(parents=True, exist_ok=True)

        plan_path = scope.blackboard_root / "plan.md"
        plan_path.write_text(f"plan for {request.thread_id}:{request.run_id}", encoding="utf-8")

        yield RuntimeEvent.progress(actor="Planner", message="Planning started", step="planner")
        yield RuntimeEvent.blackboard(
            artifacts={"plan.md": plan_path.read_text(encoding="utf-8")}
        )
        yield RuntimeEvent.final(
            final_answer="done",
            snapshot=BlackboardSnapshot(
                goal=GoalDocument(request=request.message),
                plan=PlanDocument(
                    overview="isolated run",
                    steps=[PlanStep(order=1, title="write plan", detail="write scoped files")],
                ),
                state_summary=StateSummary(
                    headline="done",
                    status="complete",
                    current_focus="none",
                ),
            ),
        )


@pytest.mark.asyncio
async def test_chat_uses_distinct_blackboard_roots_for_distinct_runs(tmp_path: Path) -> None:
    settings = AppSettings(
        workspace_root=tmp_path,
        blackboard_root=tmp_path / "blackboard",
        memory_root=tmp_path / "memories",
    )
    runtime = ScopedWritingRuntime(settings)
    app = create_app(
        settings_overrides={
            "workspace_root": tmp_path,
            "blackboard_root": tmp_path / "blackboard",
            "memory_root": tmp_path / "memories",
        },
        runtime=runtime,
    )

    body_1 = {
        "message": "run one",
        "thread_id": "shared-thread",
        "run_id": "run-1",
        "user_id": "local-user",
        "auto_approve_memory": True,
    }
    body_2 = {
        "message": "run two",
        "thread_id": "shared-thread",
        "run_id": "run-2",
        "user_id": "local-user",
        "auto_approve_memory": True,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/chat", json=body_1)
        second = await client.post("/chat", json=body_2)

    assert first.status_code == 200
    assert second.status_code == 200

    scope_1 = resolve_runtime_scope(app.state.settings, ChatRequest(**body_1))
    scope_2 = resolve_runtime_scope(app.state.settings, ChatRequest(**body_2))

    assert scope_1.blackboard_root != scope_2.blackboard_root
    assert (scope_1.blackboard_root / "plan.md").read_text(encoding="utf-8") == "plan for shared-thread:run-1"
    assert (scope_2.blackboard_root / "plan.md").read_text(encoding="utf-8") == "plan for shared-thread:run-2"

