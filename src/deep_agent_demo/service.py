from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Protocol

from deep_agent_demo.blackboard import (
    BlackboardSnapshot,
    AppSettings,
    GoalDocument,
    render_blackboard_artifacts,
)
from deep_agent_demo.blackboard.writer import BlackboardWritePlanner
from deep_agent_demo.runtime import ChatRequest, RuntimeEvent, resolve_runtime_scope


class RuntimeProtocol(Protocol):
    async def stream(self, request: ChatRequest) -> AsyncIterator[RuntimeEvent]: ...


@dataclass(slots=True)
class BlackboardProjector:
    planner: BlackboardWritePlanner = field(default_factory=BlackboardWritePlanner)

    def reset_run(self, root: Path, snapshot: BlackboardSnapshot) -> None:
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        artifacts = render_blackboard_artifacts(snapshot)
        for relative_path, content in artifacts.items():
            path = root / relative_path
            plan = self.planner.plan(path, content, exists=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(plan.content, encoding="utf-8")

    def project_snapshot(self, root: Path, snapshot: BlackboardSnapshot) -> None:
        self.write_artifacts(root, _populated_artifacts(snapshot))

    def write_artifacts(self, root: Path, artifacts: dict[str, str]) -> None:
        root.mkdir(parents=True, exist_ok=True)
        for relative_path, content in artifacts.items():
            path = root / relative_path
            exists = path.exists()
            plan = self.planner.plan(path, content, exists=exists)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(plan.content, encoding="utf-8")


class ChatService:
    def __init__(self, settings: AppSettings, runtime: RuntimeProtocol) -> None:
        self._settings = settings
        self._runtime = runtime
        self._projector = BlackboardProjector()

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        scope = resolve_runtime_scope(self._settings, request)
        initial_snapshot = BlackboardSnapshot(
            goal=GoalDocument(
                request=request.message,
                context_notes=[
                    f"auto_approve_memory={request.auto_approve_memory}",
                ],
            )
        )
        self._projector.reset_run(scope.blackboard_root, initial_snapshot)
        yield _sse_event(
            "progress",
            {
                "actor": "Orchestrator",
                "stage": "goal",
                "message": "Goal initialized",
            },
        )
        yield _sse_event("blackboard", {"artifacts": self._read_artifacts(scope.blackboard_root)})

        try:
            async for event in self._runtime.stream(request):
                if event.snapshot is not None:
                    self._projector.project_snapshot(scope.blackboard_root, event.snapshot)
                elif event.artifacts:
                    self._projector.write_artifacts(scope.blackboard_root, event.artifacts)
                yield _sse_event(event.type, event.model_dump(mode="json"))
        except Exception as exc:
            yield _sse_event(
                "error",
                {
                    "message": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

    def _read_artifacts(self, root: Path) -> dict[str, str]:
        artifacts: dict[str, str] = {}
        for relative_path in render_blackboard_artifacts(BlackboardSnapshot()).keys():
            path = root / relative_path
            if path.exists():
                artifacts[relative_path] = path.read_text(encoding="utf-8")
        return artifacts


def _sse_event(name: str, payload: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _populated_artifacts(snapshot: BlackboardSnapshot) -> dict[str, str]:
    rendered = render_blackboard_artifacts(snapshot)
    artifacts: dict[str, str] = {}
    if snapshot.goal is not None:
        artifacts["goal.md"] = rendered["goal.md"]
    if snapshot.plan is not None:
        artifacts["plan.md"] = rendered["plan.md"]
    if snapshot.critique is not None:
        artifacts["critique.md"] = rendered["critique.md"]
    if snapshot.synthesis is not None:
        artifacts["synthesis.md"] = rendered["synthesis.md"]
    if snapshot.trace:
        artifacts["trace.md"] = rendered["trace.md"]
    if snapshot.memory_proposals:
        artifacts["memory-proposals.md"] = rendered["memory-proposals.md"]
    if snapshot.mcp_usage:
        artifacts["mcp-log.md"] = rendered["mcp-log.md"]
    if snapshot.state_summary is not None:
        artifacts["state-summary.md"] = rendered["state-summary.md"]
    if snapshot.decisions:
        artifacts["decisions.md"] = rendered["decisions.md"]
    if snapshot.open_questions:
        artifacts["open-questions.md"] = rendered["open-questions.md"]
    return artifacts
