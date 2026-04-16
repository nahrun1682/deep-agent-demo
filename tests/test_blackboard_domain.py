from pathlib import Path

import pytest

from deep_agent_demo.blackboard import (
    AppSettings,
    BlackboardSnapshot,
    BlackboardWriteMode,
    BlackboardWritePlanner,
    DecisionEntry,
    GoalDocument,
    MemoryProposal,
    McpUsageRecord,
    OpenQuestion,
    PlanDocument,
    PlanStep,
    CritiqueDocument,
    SynthesisDocument,
    StateSummary,
    TraceEntry,
    render_blackboard_artifacts,
)


def test_render_blackboard_artifacts_from_structured_snapshot() -> None:
    snapshot = BlackboardSnapshot(
        goal=GoalDocument(
            request="Build a blackboard demo",
            success_criteria=[
                "show blackboard files",
                "use structured outputs as canonical data",
            ],
            constraints=["no FastAPI orchestration yet"],
        ),
        plan=PlanDocument(
            overview="Turn the request into a typed study demo.",
            steps=[
                PlanStep(order=1, title="model the domain", detail="add typed models"),
                PlanStep(order=2, title="render markdown", detail="produce observable artifacts"),
            ],
            assumptions=["python 3.11"],
        ),
        critique=CritiqueDocument(
            risks=[
                "markdown projection can drift from structured state",
                "memory and blackboard responsibilities can blur",
            ],
            improvements=["keep a single canonical snapshot"],
        ),
        synthesis=SynthesisDocument(
            recommended_direction="use structured output internally and markdown for observability",
            tradeoffs=["extra redundancy is acceptable for learning"],
        ),
        trace=[
            TraceEntry(
                actor="Orchestrator",
                action="initialized blackboard snapshot",
                target="goal.md",
                reason="start from the user request",
                result="goal recorded",
                next_step="ask planner to propose a plan",
            )
        ],
        memory_proposals=[
            MemoryProposal(
                source_actor="Planner",
                summary="Keep the blackboard model separate from runtime orchestration.",
                rationale="It simplifies later integration.",
            )
        ],
        mcp_usage=[
            McpUsageRecord(
                actor="Critic",
                server="docs",
                tool_name="search",
                reason="verify a design assumption",
                summary="confirmed the assumption",
            )
        ],
        state_summary=StateSummary(
            headline="Demo foundation drafted",
            status="in-progress",
            current_focus="domain modeling",
            next_actions=["wire the markdown renderers"],
        ),
        decisions=[
            DecisionEntry(
                actor="Orchestrator",
                summary="Use structured output as the canonical state.",
                rationale="Blackboard files are projections only.",
            )
        ],
        open_questions=[
            OpenQuestion(
                question="Should future subagents write directly to memory?",
                owner="Orchestrator",
                severity="medium",
            )
        ],
    )

    artifacts = render_blackboard_artifacts(snapshot)

    assert set(artifacts) == {
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
    assert "Build a blackboard demo" in artifacts["goal.md"]
    assert "1. model the domain" in artifacts["plan.md"]
    assert "markdown projection can drift" in artifacts["critique.md"]
    assert "use structured output internally" in artifacts["synthesis.md"]
    assert "Orchestrator" in artifacts["trace.md"]
    assert "Keep the blackboard model separate" in artifacts["memory-proposals.md"]
    assert "docs" in artifacts["mcp-log.md"]
    assert "Demo foundation drafted" in artifacts["state-summary.md"]
    assert "Use structured output as the canonical state." in artifacts["decisions.md"]
    assert "Should future subagents write directly to memory?" in artifacts["open-questions.md"]


def test_blackboard_write_planner_uses_write_then_edit() -> None:
    planner = BlackboardWritePlanner()

    fresh = planner.plan("plan.md", "first version", exists=False)
    update = planner.plan("plan.md", "second version", exists=True)

    assert fresh.mode is BlackboardWriteMode.WRITE
    assert update.mode is BlackboardWriteMode.EDIT
    assert fresh.path == Path("plan.md")
    assert update.path == Path("plan.md")


def test_settings_derives_blackboard_and_memory_roots() -> None:
    settings = AppSettings(workspace_root=Path("/tmp/demo"))

    assert settings.blackboard_root == Path("/tmp/demo/blackboard")
    assert settings.memory_root == Path("/memories")
