from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class BlackboardWriteMode(StrEnum):
    WRITE = "write"
    EDIT = "edit"


class BlackboardWritePlanner:
    def plan(self, path: str | Path, content: str, *, exists: bool) -> BlackboardWritePlan:
        return BlackboardWritePlan(
            path=Path(path),
            content=content,
            mode=BlackboardWriteMode.EDIT if exists else BlackboardWriteMode.WRITE,
        )


@dataclass(frozen=True, slots=True)
class BlackboardWritePlan:
    path: Path
    content: str
    mode: BlackboardWriteMode
