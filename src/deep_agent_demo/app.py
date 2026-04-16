from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from deep_agent_demo.blackboard import AppSettings
from deep_agent_demo.runtime import ChatRequest, DeepAgentsRuntimeFactory, load_demo_environment
from deep_agent_demo.service import ChatService


def create_app(
    *,
    settings_overrides: dict[str, object] | None = None,
    runtime: object | None = None,
    runtime_factory: DeepAgentsRuntimeFactory | None = None,
) -> FastAPI:
    load_demo_environment()
    settings = AppSettings(**(settings_overrides or {}))
    settings.blackboard_root.mkdir(parents=True, exist_ok=True)
    settings.memory_root.mkdir(parents=True, exist_ok=True)

    if runtime is None:
        runtime = (runtime_factory or DeepAgentsRuntimeFactory(settings=settings)).build()

    service = ChatService(settings=settings, runtime=runtime)  # type: ignore[arg-type]
    app = FastAPI(title="Deep Agents Blackboard Demo")
    app.state.settings = settings
    app.state.runtime = runtime

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat")
    async def chat(request: ChatRequest) -> StreamingResponse:
        return StreamingResponse(
            service.stream(request),
            media_type="text/event-stream",
        )

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        "deep_agent_demo.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
