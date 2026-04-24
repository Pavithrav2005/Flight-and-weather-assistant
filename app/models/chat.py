from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.flight import FlightInfoResponse, RouteFlightResponse
from app.models.weather import WeatherSummary


class ChatIntent(str, Enum):
    flight = "flight"
    temperature = "temperature"
    combined = "combined"
    unknown = "unknown"


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1)


class ToolRunInfo(BaseModel):
    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    duration_ms: int
    status: str
    summary: str | None = None


class ChatResponse(BaseModel):
    intent: ChatIntent
    answer: str
    tool: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    tool_runs: list[ToolRunInfo] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_question: str | None = None

    extracted_flight_numbers: list[str] = Field(default_factory=list)
    extracted_cities: list[str] = Field(default_factory=list)

    extracted_flight_number: str | None = None
    extracted_city: str | None = None

    flight: FlightInfoResponse | None = None
    weather: WeatherSummary | None = None
    flights: list[FlightInfoResponse] = Field(default_factory=list)
    weathers: list[WeatherSummary] = Field(default_factory=list)
    route_results: list[RouteFlightResponse] = Field(default_factory=list)
