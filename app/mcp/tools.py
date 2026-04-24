from __future__ import annotations

from datetime import date
from typing import Any

from app.core.exceptions import UpstreamServiceError, ValidationAppError
from app.mcp.protocol import MCPContext, MCPToolExecutionResult
from app.models.flight import FlightInfoQuery, RouteFlightQuery
from app.services.aviationstack import AviationstackService
from app.services.flight_info import FlightInfoService
from app.services.openweather import OpenWeatherService


class FlightInfoTool:
    name = "flight_info"

    def __init__(self, flight_info_service: FlightInfoService) -> None:
        self.flight_info_service = flight_info_service

    async def execute(self, arguments: dict[str, Any], context: MCPContext) -> MCPToolExecutionResult:
        flight_number = str(arguments.get("flight_number") or "").strip()
        if not flight_number:
            raise ValidationAppError("flight_number is required for flight_info tool")

        flight_date = arguments.get("date")
        parsed_date: date | None = None
        if isinstance(flight_date, str) and flight_date.strip():
            try:
                parsed_date = date.fromisoformat(flight_date)
            except ValueError as exc:
                raise ValidationAppError("date must be in YYYY-MM-DD format") from exc

        query = FlightInfoQuery(
            flight_number=flight_number,
            date=parsed_date,
            airline=arguments.get("airline"),
            departure_airport=arguments.get("departure_airport"),
            arrival_airport=arguments.get("arrival_airport"),
        )
        result = await self.flight_info_service.get_flight_info(query)
        return MCPToolExecutionResult(tool_name=self.name, payload=result, metadata={"request_id": context.request_id})


class WeatherLookupTool:
    name = "weather_lookup"

    def __init__(self, weather_service: OpenWeatherService) -> None:
        self.weather_service = weather_service

    async def execute(self, arguments: dict[str, Any], context: MCPContext) -> MCPToolExecutionResult:
        city = str(arguments.get("city") or "").strip()
        if not city:
            raise ValidationAppError("city is required for weather_lookup tool")

        result = await self.weather_service.get_weather(city)
        if result is None:
            raise ValidationAppError(f"Weather data could not be resolved for {city}")

        return MCPToolExecutionResult(tool_name=self.name, payload=result, metadata={"request_id": context.request_id})


class RouteFlightsTool:
    name = "route_flights"

    def __init__(self, aviationstack_service: AviationstackService) -> None:
        self.aviationstack_service = aviationstack_service

    async def execute(self, arguments: dict[str, Any], context: MCPContext) -> MCPToolExecutionResult:
        origin = str(arguments.get("origin") or "").strip()
        destination = str(arguments.get("destination") or "").strip()
        if not origin or not destination:
            raise ValidationAppError("origin and destination are required for route_flights tool")

        route_date = arguments.get("date")
        parsed_date: date | None = None
        if isinstance(route_date, str) and route_date.strip():
            try:
                parsed_date = date.fromisoformat(route_date)
            except ValueError as exc:
                raise ValidationAppError("date must be in YYYY-MM-DD format") from exc

        max_results = arguments.get("max_results", 5)
        if not isinstance(max_results, int):
            raise ValidationAppError("max_results must be an integer")

        query = RouteFlightQuery(
            origin=origin,
            destination=destination,
            date=parsed_date,
            max_results=max_results,
        )
        try:
            result = await self.aviationstack_service.find_route_flights(query)
        except UpstreamServiceError as exc:
            if exc.status_code in {401, 403}:
                raise ValidationAppError(
                    "Route search requires Aviationstack airport lookup access. "
                    "Your current API plan appears to block this endpoint. "
                    "Please upgrade your plan, use a specific flight number, or provide airport codes (for example DEL to LHR)."
                ) from exc
            raise
        return MCPToolExecutionResult(tool_name=self.name, payload=result, metadata={"request_id": context.request_id})
