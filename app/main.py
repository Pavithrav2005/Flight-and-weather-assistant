from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.context import request_id_var
from app.core.exceptions import AppError, DataNotFoundError, UpstreamServiceError
from app.core.logging import configure_logging
from app.mcp.executor import MCPToolExecutor
from app.mcp.registry import MCPToolRegistry
from app.mcp.tools import FlightInfoTool, RouteFlightsTool, WeatherLookupTool
from app.routes import api_router
from app.services.chatbot import ChatbotService
from app.services.aviationstack import AviationstackService
from app.services.cache import InMemoryCache
from app.services.flight_info import FlightInfoService
from app.services.openweather import OpenWeatherService
from app.services.prompt_analyzer import NvidiaNIMPromptAnalyzer


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    timeout = httpx.Timeout(settings.external_api_timeout_seconds)
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    client = httpx.AsyncClient(timeout=timeout, limits=limits, headers={"User-Agent": settings.app_name})
    cache = InMemoryCache(default_ttl_seconds=settings.cache_ttl_seconds)

    logger = logging.getLogger("flight")
    flight_service = AviationstackService(client=client, settings=settings, cache=cache, logger=logger)
    weather_service = OpenWeatherService(client=client, settings=settings, cache=cache, logger=logger)
    flight_info_service = FlightInfoService(settings=settings, cache=cache, flight_service=flight_service, weather_service=weather_service, logger=logger)
    mcp_tool_registry = MCPToolRegistry()
    mcp_tool_registry.register(FlightInfoTool(flight_info_service=flight_info_service))
    mcp_tool_registry.register(WeatherLookupTool(weather_service=weather_service))
    mcp_tool_registry.register(RouteFlightsTool(aviationstack_service=flight_service))
    mcp_tool_executor = MCPToolExecutor(registry=mcp_tool_registry)
    prompt_analyzer = NvidiaNIMPromptAnalyzer(client=client, settings=settings, logger=logger)
    chatbot_service = ChatbotService(tool_executor=mcp_tool_executor, prompt_analyzer=prompt_analyzer, logger=logger)

    app.state.settings = settings
    app.state.client = client
    app.state.cache = cache
    app.state.flight_service = flight_service
    app.state.weather_service = weather_service
    app.state.flight_info_service = flight_info_service
    app.state.mcp_tool_registry = mcp_tool_registry
    app.state.mcp_tool_executor = mcp_tool_executor
    app.state.prompt_analyzer = prompt_analyzer
    app.state.chatbot_service = chatbot_service

    try:
        yield
    finally:
        await client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Flight Intelligence API", version="1.0.0", lifespan=lifespan)
    app.include_router(api_router)

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        payload = {
            "error": {
                "code": exc.code,
                "message": exc.detail,
                "request_id": request_id_var.get(),
            }
        }
        return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers or {})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        payload = {
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "request_id": request_id_var.get(),
                "details": exc.errors(),
            }
        }
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(httpx.TimeoutException)
    async def timeout_error_handler(request: Request, exc: httpx.TimeoutException):
        payload = {
            "error": {
                "code": "upstream_timeout",
                "message": "The upstream service timed out",
                "request_id": request_id_var.get(),
            }
        }
        return JSONResponse(status_code=504, content=payload)

    @app.exception_handler(httpx.HTTPStatusError)
    async def http_status_error_handler(request: Request, exc: httpx.HTTPStatusError):
        payload = {
            "error": {
                "code": "upstream_error",
                "message": f"Upstream returned HTTP {exc.response.status_code}",
                "request_id": request_id_var.get(),
            }
        }
        return JSONResponse(status_code=502, content=payload)

    @app.exception_handler(DataNotFoundError)
    async def not_found_error_handler(request: Request, exc: DataNotFoundError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.detail, "request_id": request_id_var.get()}},
        )

    @app.exception_handler(UpstreamServiceError)
    async def upstream_error_handler(request: Request, exc: UpstreamServiceError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.detail, "request_id": request_id_var.get()}},
            headers=exc.headers or {},
        )

    return app


app = create_app()
