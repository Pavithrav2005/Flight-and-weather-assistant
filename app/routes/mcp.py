from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/tools")
async def list_mcp_tools(request: Request) -> dict[str, list[str]]:
    registry = request.app.state.mcp_tool_registry
    return {"tools": registry.list_tools()}
