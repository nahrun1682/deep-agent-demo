from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEEP_AGENT_DEMO_", extra="ignore")

    workspace_root: Path = Path("/workspace")
    blackboard_root: Path | None = None
    memory_root: Path = Field(default=Path("/memories"))

    @model_validator(mode="after")
    def _derive_paths(self) -> "AppSettings":
        if self.blackboard_root is None:
            self.blackboard_root = self.workspace_root / "blackboard"
        return self
