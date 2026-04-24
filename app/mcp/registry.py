from __future__ import annotations

from app.core.exceptions import ValidationAppError
from app.mcp.protocol import MCPTool


class MCPToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}

    def register(self, tool: MCPTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> MCPTool:
        tool = self._tools.get(name)
        if tool is None:
            raise ValidationAppError(f"Unknown MCP tool: {name}")
        return tool

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())
