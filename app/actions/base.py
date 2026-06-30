from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionResult:
    success: bool
    action_id: str
    output: dict[str, Any] | None = None
    error: str | None = None


class BaseAction(ABC):
    @abstractmethod
    async def execute(self, params: dict) -> ActionResult: ...
