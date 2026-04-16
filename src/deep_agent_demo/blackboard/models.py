from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GoalDocument(BaseModel):
    request: str
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    context_notes: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    order: int
    title: str
    detail: str


class PlanDocument(BaseModel):
    overview: str
    steps: list[PlanStep] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class CritiqueDocument(BaseModel):
    risks: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class SynthesisDocument(BaseModel):
    recommended_direction: str
    tradeoffs: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)


class TraceEntry(BaseModel):
    timestamp: datetime | None = None
    actor: str
    action: str
    target: str | None = None
    reason: str | None = None
    result: str | None = None
    next_step: str | None = None


class MemoryProposal(BaseModel):
    source_actor: str
    summary: str
    rationale: str
    persistence_hint: str | None = None


class McpUsageRecord(BaseModel):
    actor: str
    server: str
    tool_name: str
    reason: str
    summary: str
    outcome: str | None = None


class DecisionEntry(BaseModel):
    actor: str
    summary: str
    rationale: str
    outcome: Literal["accepted", "rejected", "deferred"] = "accepted"


class OpenQuestion(BaseModel):
    question: str
    owner: str
    severity: Literal["low", "medium", "high"] = "medium"


class StateSummary(BaseModel):
    headline: str
    status: str
    current_focus: str
    completed: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class BlackboardSnapshot(BaseModel):
    goal: GoalDocument | None = None
    plan: PlanDocument | None = None
    critique: CritiqueDocument | None = None
    synthesis: SynthesisDocument | None = None
    trace: list[TraceEntry] = Field(default_factory=list)
    memory_proposals: list[MemoryProposal] = Field(default_factory=list)
    mcp_usage: list[McpUsageRecord] = Field(default_factory=list)
    state_summary: StateSummary | None = None
    decisions: list[DecisionEntry] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
