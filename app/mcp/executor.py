from __future__ import annotations

from app.mcp.protocol import MCPContext, MCPToolExecutionResult
from app.mcp.registry import MCPToolRegistry


class MCPToolExecutor:
    def __init__(self, registry: MCPToolRegistry) -> None:
        self.registry = registry

    async def execute(self, tool_name: str, arguments: dict[str, object], context: MCPContext) -> MCPToolExecutionResult:
        tool = self.registry.get(tool_name)
        return await tool.execute(arguments, context)
