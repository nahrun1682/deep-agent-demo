from __future__ import annotations

from collections.abc import Mapping

from deep_agent_demo.blackboard.models import (
    BlackboardSnapshot,
    CritiqueDocument,
    DecisionEntry,
    GoalDocument,
    MemoryProposal,
    McpUsageRecord,
    OpenQuestion,
    PlanDocument,
    StateSummary,
    SynthesisDocument,
    TraceEntry,
)


def render_goal_markdown(goal: GoalDocument | None) -> str:
    lines = ["# Goal"]
    if goal is None:
        lines.append("")
        lines.append("No goal has been recorded yet.")
        return "\n".join(lines)

    lines.extend(["", "## User Request", goal.request])
    _extend_bullets(lines, "Success Criteria", goal.success_criteria)
    _extend_bullets(lines, "Constraints", goal.constraints)
    _extend_bullets(lines, "Context Notes", goal.context_notes)
    return "\n".join(lines)


def render_plan_markdown(plan: PlanDocument | None) -> str:
    lines = ["# Plan"]
    if plan is None:
        lines.append("")
        lines.append("No plan has been recorded yet.")
        return "\n".join(lines)

    lines.extend(["", "## Overview", plan.overview])
    if plan.steps:
        lines.extend(["", "## Steps"])
        for step in sorted(plan.steps, key=lambda item: item.order):
            lines.append(f"{step.order}. {step.title}")
            lines.append(f"   {step.detail}")
    _extend_bullets(lines, "Assumptions", plan.assumptions)
    _extend_bullets(lines, "Dependencies", plan.dependencies)
    return "\n".join(lines)


def render_critique_markdown(critique: CritiqueDocument | None) -> str:
    lines = ["# Critique"]
    if critique is None:
        lines.append("")
        lines.append("No critique has been recorded yet.")
        return "\n".join(lines)

    _extend_bullets(lines, "Risks", critique.risks)
    _extend_bullets(lines, "Improvements", critique.improvements)
    _extend_bullets(lines, "Questions", critique.questions)
    return "\n".join(lines)


def render_synthesis_markdown(synthesis: SynthesisDocument | None) -> str:
    lines = ["# Synthesis"]
    if synthesis is None:
        lines.append("")
        lines.append("No synthesis has been recorded yet.")
        return "\n".join(lines)

    lines.extend(["", "## Recommended Direction", synthesis.recommended_direction])
    _extend_bullets(lines, "Tradeoffs", synthesis.tradeoffs)
    _extend_bullets(lines, "Unresolved Items", synthesis.unresolved_items)
    return "\n".join(lines)


def render_trace_markdown(entries: list[TraceEntry]) -> str:
    lines = ["# Trace"]
    if not entries:
        lines.extend(["", "No trace entries recorded yet."])
        return "\n".join(lines)

    for entry in entries:
        lines.extend(["", f"## {entry.actor}", f"- action: {entry.action}"])
        if entry.timestamp is not None:
            lines.append(f"- timestamp: {entry.timestamp.isoformat()}")
        if entry.target:
            lines.append(f"- target: {entry.target}")
        if entry.reason:
            lines.append(f"- reason: {entry.reason}")
        if entry.result:
            lines.append(f"- result: {entry.result}")
        if entry.next_step:
            lines.append(f"- next: {entry.next_step}")
    return "\n".join(lines)


def render_memory_proposals_markdown(proposals: list[MemoryProposal]) -> str:
    lines = ["# Memory Proposals"]
    if not proposals:
        lines.extend(["", "No memory proposals recorded yet."])
        return "\n".join(lines)

    for proposal in proposals:
        lines.extend(
            [
                "",
                f"## {proposal.source_actor}",
                f"- summary: {proposal.summary}",
                f"- rationale: {proposal.rationale}",
            ]
        )
        if proposal.persistence_hint:
            lines.append(f"- persistence hint: {proposal.persistence_hint}")
    return "\n".join(lines)


def render_mcp_log_markdown(records: list[McpUsageRecord]) -> str:
    lines = ["# MCP Log"]
    if not records:
        lines.extend(["", "No MCP usage recorded yet."])
        return "\n".join(lines)

    for record in records:
        lines.extend(
            [
                "",
                f"## {record.actor}",
                f"- server: {record.server}",
                f"- tool: {record.tool_name}",
                f"- reason: {record.reason}",
                f"- summary: {record.summary}",
            ]
        )
        if record.outcome:
            lines.append(f"- outcome: {record.outcome}")
    return "\n".join(lines)


def render_state_summary_markdown(summary: StateSummary | None) -> str:
    lines = ["# State Summary"]
    if summary is None:
        lines.extend(["", "No state summary has been recorded yet."])
        return "\n".join(lines)

    lines.extend(
        [
            "",
            f"## {summary.headline}",
            f"- status: {summary.status}",
            f"- current focus: {summary.current_focus}",
        ]
    )
    _extend_bullets(lines, "Completed", summary.completed)
    _extend_bullets(lines, "Next Actions", summary.next_actions)
    return "\n".join(lines)


def render_decisions_markdown(decisions: list[DecisionEntry]) -> str:
    lines = ["# Decisions"]
    if not decisions:
        lines.extend(["", "No decisions recorded yet."])
        return "\n".join(lines)

    for decision in decisions:
        lines.extend(
            [
                "",
                f"## {decision.actor}",
                f"- summary: {decision.summary}",
                f"- rationale: {decision.rationale}",
                f"- outcome: {decision.outcome}",
            ]
        )
    return "\n".join(lines)


def render_open_questions_markdown(questions: list[OpenQuestion]) -> str:
    lines = ["# Open Questions"]
    if not questions:
        lines.extend(["", "No open questions recorded yet."])
        return "\n".join(lines)

    for question in questions:
        lines.extend(
            [
                "",
                f"## {question.owner}",
                f"- question: {question.question}",
                f"- severity: {question.severity}",
            ]
        )
    return "\n".join(lines)


def render_blackboard_artifacts(snapshot: BlackboardSnapshot) -> dict[str, str]:
    return {
        "goal.md": render_goal_markdown(snapshot.goal),
        "plan.md": render_plan_markdown(snapshot.plan),
        "critique.md": render_critique_markdown(snapshot.critique),
        "synthesis.md": render_synthesis_markdown(snapshot.synthesis),
        "trace.md": render_trace_markdown(snapshot.trace),
        "memory-proposals.md": render_memory_proposals_markdown(snapshot.memory_proposals),
        "mcp-log.md": render_mcp_log_markdown(snapshot.mcp_usage),
        "state-summary.md": render_state_summary_markdown(snapshot.state_summary),
        "decisions.md": render_decisions_markdown(snapshot.decisions),
        "open-questions.md": render_open_questions_markdown(snapshot.open_questions),
    }


def _extend_bullets(lines: list[str], heading: str, values: list[str]) -> None:
    if not values:
        return
    lines.extend(["", f"## {heading}"])
    lines.extend(f"- {value}" for value in values)
