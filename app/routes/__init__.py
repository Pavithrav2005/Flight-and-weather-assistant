from fastapi import APIRouter

from app.routes.chat import router as chat_router
from app.routes.flight import router as flight_router
from app.routes.health import router as health_router
from app.routes.mcp import router as mcp_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(mcp_router)
api_router.include_router(chat_router)
api_router.include_router(flight_router)
