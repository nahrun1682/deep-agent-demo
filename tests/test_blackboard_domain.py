from pathlib import Path
import tomllib

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
    render_goal_markdown,
    render_plan_markdown,
)


def test_render_goal_and_plan_markdown_preserve_shape_for_multiline_content() -> None:
    goal = GoalDocument(
        request="Build a blackboard demo\n- keep it readable",
        success_criteria=["show files\nwith stable structure", "use typed models"],
        constraints=["no FastAPI\nno Deep Agents orchestration"],
        context_notes=["markdown-ish content:\n# heading\n- bullet"],
    )
    plan = PlanDocument(
        overview="Turn the request into a typed study demo.\nKeep the output observable.",
        steps=[
            PlanStep(order=2, title="render markdown", detail="produce artifacts\nfor humans"),
            PlanStep(order=1, title="model the domain", detail="add typed models"),
        ],
        assumptions=["python 3.11\nportable local checkout"],
        dependencies=["pytest\nfor the test suite"],
    )

    assert render_goal_markdown(goal).splitlines() == [
        "# Goal",
        "",
        "## User Request",
        "Build a blackboard demo",
        "  - keep it readable",
        "",
        "## Success Criteria",
        "- show files",
        "  with stable structure",
        "- use typed models",
        "",
        "## Constraints",
        "- no FastAPI",
        "  no Deep Agents orchestration",
        "",
        "## Context Notes",
        "- markdown-ish content:",
        "  # heading",
        "  - bullet",
    ]

    assert render_plan_markdown(plan).splitlines() == [
        "# Plan",
        "",
        "## Overview",
        "Turn the request into a typed study demo.",
        "  Keep the output observable.",
        "",
        "## Steps",
        "1. model the domain",
        "   add typed models",
        "2. render markdown",
        "   produce artifacts",
        "   for humans",
        "",
        "## Assumptions",
        "- python 3.11",
        "  portable local checkout",
        "",
        "## Dependencies",
        "- pytest",
        "  for the test suite",
    ]


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

    assert list(artifacts) == [
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
    ]
    assert artifacts["goal.md"].splitlines()[:5] == [
        "# Goal",
        "",
        "## User Request",
        "Build a blackboard demo",
        "",
    ]
    assert artifacts["plan.md"].splitlines()[:8] == [
        "# Plan",
        "",
        "## Overview",
        "Turn the request into a typed study demo.",
        "",
        "## Steps",
        "1. model the domain",
        "   add typed models",
    ]
    assert artifacts["trace.md"].splitlines()[3] == "- action: initialized blackboard snapshot"
    assert artifacts["state-summary.md"].splitlines()[2] == "## Demo foundation drafted"


def test_blackboard_write_planner_uses_write_then_edit() -> None:
    planner = BlackboardWritePlanner()

    fresh = planner.plan("plan.md", "first version", exists=False)
    update = planner.plan("plan.md", "second version", exists=True)

    assert fresh.mode is BlackboardWriteMode.WRITE
    assert update.mode is BlackboardWriteMode.EDIT
    assert fresh.path == Path("plan.md")
    assert update.path == Path("plan.md")


def test_app_settings_defaults_are_portable_and_derivable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    settings = AppSettings()

    assert settings.workspace_root == tmp_path
    assert settings.blackboard_root == tmp_path / "blackboard"
    assert settings.memory_root == tmp_path / "memories"


def test_app_settings_can_still_target_workspace_style_paths() -> None:
    settings = AppSettings(workspace_root=Path("/workspace"), memory_root=Path("/memories"))

    assert settings.blackboard_root == Path("/workspace/blackboard")
    assert settings.memory_root == Path("/memories")


def test_pyproject_uses_dependency_group_for_test_dependencies() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    assert "pytest" not in pyproject["project"]["dependencies"]
    assert "pytest-asyncio" not in pyproject["project"]["dependencies"]
    assert pyproject["dependency-groups"]["test"] == [
        "pytest>=9.0.3",
        "pytest-asyncio>=1.3.0",
    ]
