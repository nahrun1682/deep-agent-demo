from __future__ import annotations

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

    lines.append("")
    lines.append("## User Request")
    _append_text_block(lines, goal.request)
    _append_bullets(lines, "Success Criteria", goal.success_criteria)
    _append_bullets(lines, "Constraints", goal.constraints)
    _append_bullets(lines, "Context Notes", goal.context_notes)
    return "\n".join(lines)


def render_plan_markdown(plan: PlanDocument | None) -> str:
    lines = ["# Plan"]
    if plan is None:
        lines.append("")
        lines.append("No plan has been recorded yet.")
        return "\n".join(lines)

    lines.append("")
    lines.append("## Overview")
    _append_text_block(lines, plan.overview)
    if plan.steps:
        lines.extend(["", "## Steps"])
        for step in sorted(plan.steps, key=lambda item: item.order):
            lines.append(f"{step.order}. {step.title}")
            _append_text_block(lines, step.detail, indent="   ", indent_first=True)
    _append_bullets(lines, "Assumptions", plan.assumptions)
    _append_bullets(lines, "Dependencies", plan.dependencies)
    return "\n".join(lines)


def render_critique_markdown(critique: CritiqueDocument | None) -> str:
    lines = ["# Critique"]
    if critique is None:
        lines.append("")
        lines.append("No critique has been recorded yet.")
        return "\n".join(lines)

    _append_bullets(lines, "Risks", critique.risks)
    _append_bullets(lines, "Improvements", critique.improvements)
    _append_bullets(lines, "Questions", critique.questions)
    return "\n".join(lines)


def render_synthesis_markdown(synthesis: SynthesisDocument | None) -> str:
    lines = ["# Synthesis"]
    if synthesis is None:
        lines.append("")
        lines.append("No synthesis has been recorded yet.")
        return "\n".join(lines)

    lines.append("")
    lines.append("## Recommended Direction")
    _append_text_block(lines, synthesis.recommended_direction)
    _append_bullets(lines, "Tradeoffs", synthesis.tradeoffs)
    _append_bullets(lines, "Unresolved Items", synthesis.unresolved_items)
    return "\n".join(lines)


def render_trace_markdown(entries: list[TraceEntry]) -> str:
    lines = ["# Trace"]
    if not entries:
        lines.extend(["", "No trace entries recorded yet."])
        return "\n".join(lines)

    for entry in entries:
        lines.extend(["", f"## {entry.actor}"])
        _append_field(lines, "action", entry.action)
        if entry.timestamp is not None:
            _append_field(lines, "timestamp", entry.timestamp.isoformat())
        if entry.target:
            _append_field(lines, "target", entry.target)
        if entry.reason:
            _append_field(lines, "reason", entry.reason)
        if entry.result:
            _append_field(lines, "result", entry.result)
        if entry.next_step:
            _append_field(lines, "next", entry.next_step)
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
            ]
        )
        _append_field(lines, "summary", proposal.summary)
        _append_field(lines, "rationale", proposal.rationale)
        if proposal.persistence_hint:
            _append_field(lines, "persistence hint", proposal.persistence_hint)
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
            ]
        )
        _append_field(lines, "server", record.server)
        _append_field(lines, "tool", record.tool_name)
        _append_field(lines, "reason", record.reason)
        _append_field(lines, "summary", record.summary)
        if record.outcome:
            _append_field(lines, "outcome", record.outcome)
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
        ]
    )
    _append_field(lines, "status", summary.status)
    _append_field(lines, "current focus", summary.current_focus)
    _append_bullets(lines, "Completed", summary.completed)
    _append_bullets(lines, "Next Actions", summary.next_actions)
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
            ]
        )
        _append_field(lines, "summary", decision.summary)
        _append_field(lines, "rationale", decision.rationale)
        _append_field(lines, "outcome", decision.outcome)
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
            ]
        )
        _append_field(lines, "question", question.question)
        _append_field(lines, "severity", question.severity)
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


def _append_text_block(lines: list[str], text: str, *, indent: str = "  ", indent_first: bool = False) -> None:
    normalized_lines = _normalize_lines(text)
    if not normalized_lines:
        lines.append("")
        return
    if indent_first:
        lines.append(f"{indent}{normalized_lines[0]}")
    else:
        lines.append(normalized_lines[0])
    lines.extend(f"{indent}{line}" for line in normalized_lines[1:])


def _append_field(lines: list[str], label: str, value: str) -> None:
    normalized_lines = _normalize_lines(value)
    if not normalized_lines:
        lines.append(f"- {label}:")
        return
    lines.append(f"- {label}: {normalized_lines[0]}")
    lines.extend(f"  {line}" for line in normalized_lines[1:])


def _append_bullets(lines: list[str], heading: str, values: list[str]) -> None:
    if not values:
        return
    lines.extend(["", f"## {heading}"])
    for value in values:
        normalized_lines = _normalize_lines(value)
        if not normalized_lines:
            lines.append("-")
            continue
        lines.append(f"- {normalized_lines[0]}")
        lines.extend(f"  {line}" for line in normalized_lines[1:])


def _normalize_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines()]
