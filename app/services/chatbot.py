from __future__ import annotations

import asyncio
import logging
import time

from app.core.exceptions import ValidationAppError
from app.core.context import request_id_var
from app.mcp.protocol import MCPContext
from app.mcp.executor import MCPToolExecutor
from app.models.chat import ChatIntent, ChatResponse, ToolRunInfo
from app.models.flight import FlightInfoResponse, RouteFlightResponse
from app.models.weather import WeatherSummary
from app.services.prompt_analyzer import PromptAnalyzer


class ChatbotService:
    def __init__(self, tool_executor: MCPToolExecutor, prompt_analyzer: PromptAnalyzer, logger: logging.Logger) -> None:
        self.tool_executor = tool_executor
        self.prompt_analyzer = prompt_analyzer
        self.logger = logger

    async def handle_prompt(self, prompt: str) -> ChatResponse:
        parsed = await self.prompt_analyzer.analyze(prompt)
        context = MCPContext(request_id=request_id_var.get(), user_prompt=prompt)

        if parsed.clarification_question:
            return ChatResponse(
                intent=ChatIntent.unknown,
                answer=parsed.clarification_question,
                requires_clarification=True,
                clarification_question=parsed.clarification_question,
                extracted_flight_numbers=parsed.flight_numbers or [],
                extracted_cities=parsed.cities or [],
            )

        if not parsed.tool_calls:
            raise ValidationAppError("I could not determine whether this is a flight or temperature query.")

        execution_tasks = [self._execute_single_tool_call(call.tool_name, call.arguments, context) for call in parsed.tool_calls]
        execution_results = await asyncio.gather(*execution_tasks)

        flights: list[FlightInfoResponse] = []
        weathers: list[WeatherSummary] = []
        route_results: list[RouteFlightResponse] = []
        tool_runs: list[ToolRunInfo] = []

        for tool_name, arguments, payload, duration_ms in execution_results:
            summary = None
            if tool_name == "flight_info":
                flight = FlightInfoResponse.model_validate(payload)
                flights.append(flight)
                status = flight.flight.flight_status or "unknown"
                summary = f"{flight.flight_number}: {status}"
            elif tool_name == "weather_lookup":
                weather = WeatherSummary.model_validate(payload)
                weathers.append(weather)
                if weather.temperature_celsius is not None:
                    summary = f"{weather.city}: {weather.temperature_celsius:.1f}C"
                else:
                    summary = f"{weather.city}: temperature unavailable"
            elif tool_name == "route_flights":
                route_result = RouteFlightResponse.model_validate(payload)
                route_results.append(route_result)
                summary = f"{route_result.query.origin} to {route_result.query.destination}: {len(route_result.flights)} flights"
            else:
                raise ValidationAppError(f"Unsupported tool returned by analyzer: {tool_name}")

            tool_runs.append(
                ToolRunInfo(
                    tool_name=tool_name,
                    arguments=arguments,
                    duration_ms=duration_ms,
                    status="success",
                    summary=summary,
                )
            )

        response_intent = self._resolve_response_intent(flights, weathers, route_results)
        answer = self._build_merged_answer(flights, weathers, route_results)
        tools_used = sorted({run.tool_name for run in tool_runs})

        primary_flight = flights[0] if flights else None
        primary_weather = weathers[0] if weathers else None

        return ChatResponse(
            intent=response_intent,
            tool=tools_used[0] if len(tools_used) == 1 else "multi_tool",
            tools_used=tools_used,
            tool_runs=tool_runs,
            answer=answer,
            extracted_flight_numbers=parsed.flight_numbers or [f.flight_number for f in flights],
            extracted_cities=parsed.cities
            or [w.city for w in weathers]
            or [route.query.origin for route in route_results] + [route.query.destination for route in route_results],
            extracted_flight_number=primary_flight.flight_number if primary_flight else None,
            extracted_city=primary_weather.city if primary_weather else None,
            flight=primary_flight,
            weather=primary_weather,
            flights=flights,
            weathers=weathers,
            route_results=route_results,
        )

    async def _execute_single_tool_call(self, tool_name: str, arguments: dict[str, object], context: MCPContext) -> tuple[str, dict[str, object], object, int]:
        started_at = time.perf_counter()
        execution = await self.tool_executor.execute(tool_name, arguments, context)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        return execution.tool_name, arguments, execution.payload, duration_ms

    @staticmethod
    def _resolve_response_intent(flights: list[FlightInfoResponse], weathers: list[WeatherSummary], route_results: list[RouteFlightResponse]) -> ChatIntent:
        if route_results:
            return ChatIntent.flight
        if flights and weathers:
            return ChatIntent.combined
        if flights:
            return ChatIntent.flight
        if weathers:
            return ChatIntent.temperature
        return ChatIntent.unknown

    def _build_merged_answer(self, flights: list[FlightInfoResponse], weathers: list[WeatherSummary], route_results: list[RouteFlightResponse]) -> str:
        segments: list[str] = []

        for flight in flights:
            segments.append(self._render_flight_segment(flight))

        for weather in weathers:
            segments.append(self._render_weather_segment(weather))

        for route_result in route_results:
            segments.append(self._render_route_segment(route_result))

        if not segments:
            return "No actionable data was produced for your prompt."
        return " ".join(segments)

    def _render_flight_segment(self, flight_result: FlightInfoResponse) -> str:
        status = flight_result.flight.flight_status or "unknown"
        departure_city = flight_result.flight.departure.city if flight_result.flight.departure else None
        arrival_city = flight_result.flight.arrival.city if flight_result.flight.arrival else None
        answer_parts = [f"Flight {flight_result.flight_number} status is {status}."]
        if departure_city and arrival_city:
            answer_parts.append(f"It travels from {departure_city} to {arrival_city}.")
        elif departure_city:
            answer_parts.append(f"Departure city: {departure_city}.")
        elif arrival_city:
            answer_parts.append(f"Arrival city: {arrival_city}.")
        return " ".join(answer_parts)

    @staticmethod
    def _render_weather_segment(weather_result: WeatherSummary) -> str:
        condition = weather_result.condition or "unknown conditions"
        temp = f"{weather_result.temperature_celsius:.1f}C" if weather_result.temperature_celsius is not None else "unknown temperature"
        return f"The temperature in {weather_result.city} is {temp} with {condition}."

    @staticmethod
    def _render_route_segment(route_result: RouteFlightResponse) -> str:
        if not route_result.flights:
            return f"No flights found from {route_result.query.origin} to {route_result.query.destination}."

        top = route_result.flights[: min(3, len(route_result.flights))]
        parts = [f"Found {len(route_result.flights)} flights from {route_result.query.origin} to {route_result.query.destination}."]
        flight_summaries = []
        for item in top:
            flight_code = item.flight_iata or "unknown flight"
            airline = item.airline_name or "unknown airline"
            dep = item.departure_iata or "?"
            arr = item.arrival_iata or "?"
            flight_summaries.append(f"{flight_code} ({airline}) {dep}->{arr}")
        parts.append("Top matches: " + "; ".join(flight_summaries) + ".")
        if route_result.warnings:
            parts.append(" ".join(route_result.warnings))
        return " ".join(parts)
