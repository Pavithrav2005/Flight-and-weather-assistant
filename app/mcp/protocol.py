from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class MCPContext:
    request_id: str
    user_prompt: str


@dataclass(slots=True)
class MCPToolExecutionResult:
    tool_name: str
    payload: Any
    metadata: dict[str, Any] | None = None


class MCPTool(Protocol):
    name: str

    async def execute(self, arguments: dict[str, Any], context: MCPContext) -> MCPToolExecutionResult:
        ...
