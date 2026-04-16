from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol

from deep_agent_demo.blackboard import (
    BlackboardSnapshot,
    GoalDocument,
    AppSettings,
    render_blackboard_artifacts,
)
from deep_agent_demo.blackboard.writer import BlackboardWritePlanner
from deep_agent_demo.runtime import ChatRequest, RuntimeEvent


class RuntimeProtocol(Protocol):
    async def stream(self, request: ChatRequest) -> AsyncIterator[RuntimeEvent]: ...


@dataclass(slots=True)
class BlackboardProjector:
    settings: AppSettings
    planner: BlackboardWritePlanner = field(default_factory=BlackboardWritePlanner)

    def project(self, snapshot: BlackboardSnapshot) -> None:
        self.settings.blackboard_root.mkdir(parents=True, exist_ok=True)
        artifacts = render_blackboard_artifacts(snapshot)
        for relative_path, content in artifacts.items():
            path = self.settings.blackboard_root / relative_path
            plan = self.planner.plan(path, content, exists=path.exists())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(plan.content, encoding="utf-8")


class ChatService:
    def __init__(self, settings: AppSettings, runtime: RuntimeProtocol) -> None:
        self._settings = settings
        self._runtime = runtime
        self._projector = BlackboardProjector(settings)

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        current_snapshot = BlackboardSnapshot(
            goal=GoalDocument(
                request=request.message,
                context_notes=[
                    f"auto_approve_memory={request.auto_approve_memory}",
                ],
            )
        )
        self._projector.project(current_snapshot)
        yield _sse_event(
            "progress",
            {
                "actor": "Orchestrator",
                "stage": "goal",
                "message": "Goal initialized",
            },
        )
        yield _sse_event("blackboard", {"snapshot": current_snapshot.model_dump(mode="json")})

        async for event in self._runtime.stream(request):
            if event.snapshot is not None:
                current_snapshot = _merge_snapshot(current_snapshot, event.snapshot)
                self._projector.project(current_snapshot)

            yield _sse_event(event.type, event.model_dump(mode="json"))

        self._projector.project(current_snapshot)


def _merge_snapshot(base: BlackboardSnapshot, update: BlackboardSnapshot) -> BlackboardSnapshot:
    data = base.model_dump(mode="python")
    update_data = update.model_dump(mode="python", exclude_none=True)

    for field in ("goal", "plan", "critique", "synthesis", "state_summary"):
        if field in update_data:
            data[field] = update_data[field]

    for field in ("trace", "memory_proposals", "mcp_usage", "decisions", "open_questions"):
        if field in update_data and update_data[field]:
            data[field] = [*data.get(field, []), *update_data[field]]

    return BlackboardSnapshot.model_validate(data)


def _sse_event(name: str, payload: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
