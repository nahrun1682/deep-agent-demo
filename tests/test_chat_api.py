from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from deep_agent_demo.app import create_app
from deep_agent_demo.blackboard import (
    BlackboardSnapshot,
    CritiqueDocument,
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
from deep_agent_demo.runtime import ChatRequest, RuntimeEvent


class FakeRuntime:
    def __init__(self, snapshot: BlackboardSnapshot) -> None:
        self.snapshot = snapshot
        self.requests: list[ChatRequest] = []

    async def stream(self, request: ChatRequest):
        self.requests.append(request)
        yield RuntimeEvent.progress(
            actor="Orchestrator",
            message="Planner started",
            step="planner",
        )
        yield RuntimeEvent.blackboard(snapshot=self.snapshot)
        yield RuntimeEvent.hitl(
            action="memory_promotion",
            state="pending",
            message="Approve memory write",
        )
        yield RuntimeEvent.hitl(
            action="memory_promotion",
            state="approved",
            message="Auto-approved memory write",
        )
        yield RuntimeEvent.final(
            final_answer="Done",
            snapshot=self.snapshot,
        )


def _sample_snapshot() -> BlackboardSnapshot:
    return BlackboardSnapshot(
        goal=GoalDocument(
            request="Study the blackboard pattern",
            success_criteria=["write all blackboard files", "show progress"],
            constraints=["use Deep Agents"],
        ),
        plan=PlanDocument(
            overview="Break the task into planner, critic, and synthesizer work.",
            steps=[
                PlanStep(order=1, title="planner", detail="build a plan"),
                PlanStep(order=2, title="critic", detail="review the plan"),
            ],
        ),
        critique=CritiqueDocument(
            risks=["model output can drift"],
            improvements=["keep a canonical structured snapshot"],
        ),
        synthesis=SynthesisDocument(
            recommended_direction="Use structured outputs and project them to markdown.",
        ),
        trace=[
            TraceEntry(
                actor="Orchestrator",
                action="initialized",
                target="goal.md",
                reason="record the request",
                result="goal ready",
                next_step="invoke planner",
            )
        ],
        memory_proposals=[
            MemoryProposal(
                source_actor="Synthesizer",
                summary="Keep the blackboard as a projection layer.",
                rationale="It helps the study demo stay coherent.",
            )
        ],
        mcp_usage=[
            McpUsageRecord(
                actor="Critic",
                server="local-demo",
                tool_name="facts",
                reason="check a design assumption",
                summary="confirmed the assumption",
            )
        ],
        state_summary=StateSummary(
            headline="Demo in progress",
            status="running",
            current_focus="wiring",
            completed=["goal captured"],
            next_actions=["run the subagents"],
        ),
        decisions=[
            DecisionEntry(
                actor="Orchestrator",
                summary="Use structured outputs as canonical data.",
                rationale="Markdown is a projection only.",
            )
        ],
        open_questions=[
            OpenQuestion(
                question="Should memory promotion be auto-approved in unattended mode?",
                owner="Orchestrator",
                severity="medium",
            )
        ],
    )


@pytest.mark.asyncio
async def test_chat_endpoint_streams_sse_and_writes_blackboard(tmp_path: Path) -> None:
    app = create_app(
        settings_overrides={
            "workspace_root": tmp_path,
            "blackboard_root": tmp_path / "blackboard",
            "memory_root": tmp_path / "memories",
        },
        runtime=FakeRuntime(_sample_snapshot()),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/chat",
            json={
                "message": "Study the blackboard pattern",
                "auto_approve_memory": True,
            },
        )

    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "event: hitl" in response.text
    assert "event: final" in response.text
    assert response.text.index("Approve memory write") < response.text.index("Auto-approved memory write")

    blackboard_root = tmp_path / "blackboard"
    expected_files = {
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
    }
    assert expected_files.issubset({item.name for item in blackboard_root.iterdir()})
    assert "Study the blackboard pattern" in (blackboard_root / "goal.md").read_text()
    assert "Planner started" in response.text


@pytest.mark.asyncio
async def test_chat_endpoint_resets_existing_blackboard_files(tmp_path: Path) -> None:
    blackboard_root = tmp_path / "blackboard"
    blackboard_root.mkdir(parents=True, exist_ok=True)
    existing_plan = blackboard_root / "plan.md"
    existing_plan.write_text("runtime-owned plan", encoding="utf-8")

    app = create_app(
        settings_overrides={
            "workspace_root": tmp_path,
            "blackboard_root": blackboard_root,
            "memory_root": tmp_path / "memories",
        },
        runtime=FakeRuntime(_sample_snapshot()),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/chat",
            json={
                "message": "Study the blackboard pattern",
                "auto_approve_memory": True,
            },
    )

    assert response.status_code == 200
    assert existing_plan.read_text(encoding="utf-8") != "runtime-owned plan"
    assert "No plan has been recorded yet." in existing_plan.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_health_endpoint_reports_ready() -> None:
    app = create_app(
        settings_overrides={
            "workspace_root": Path("/tmp"),
            "blackboard_root": Path("/tmp/blackboard"),
            "memory_root": Path("/tmp/memories"),
        },
        runtime=FakeRuntime(_sample_snapshot()),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.json() == {"status": "ok"}
