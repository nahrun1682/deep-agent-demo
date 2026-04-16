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

        async for event in self._runtime.stream(request):
            yield _sse_event(event.type, event.model_dump(mode="json"))

    def _read_artifacts(self, root: Path) -> dict[str, str]:
        artifacts: dict[str, str] = {}
        for relative_path in render_blackboard_artifacts(BlackboardSnapshot()).keys():
            path = root / relative_path
            if path.exists():
                artifacts[relative_path] = path.read_text(encoding="utf-8")
        return artifacts


def _sse_event(name: str, payload: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
