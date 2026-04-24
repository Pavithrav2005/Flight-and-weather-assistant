from __future__ import annotations

import asyncio
import hashlib
import json
import logging

from app.core.config import Settings
from app.core.context import request_id_var
from app.models.flight import FlightInfoQuery, FlightInfoResponse
from app.services.aviationstack import AviationstackService
from app.services.cache import InMemoryCache
from app.services.openweather import OpenWeatherService


class FlightInfoService:
    def __init__(self, settings: Settings, cache: InMemoryCache, flight_service: AviationstackService, weather_service: OpenWeatherService, logger: logging.Logger) -> None:
        self.settings = settings
        self.cache = cache
        self.flight_service = flight_service
        self.weather_service = weather_service
        self.logger = logger

    async def get_flight_info(self, query: FlightInfoQuery) -> FlightInfoResponse:
        cache_key = self._cache_key(query)
        cached = await self.cache.get(cache_key)
        request_id = request_id_var.get()
        if cached is not None:
            response = FlightInfoResponse.model_validate(cached)
            return response.model_copy(update={"cached": True, "request_id": request_id})

        flight = await self.flight_service.get_flight_status(query)

        departure_city = flight.departure.city if flight.departure else None
        arrival_city = flight.arrival.city if flight.arrival else None

        departure_weather, arrival_weather = await asyncio.gather(
            self.weather_service.get_weather(departure_city),
            self.weather_service.get_weather(arrival_city),
        )

        warnings: list[str] = []
        if not departure_city:
            warnings.append("Departure city was not available from the flight data")
        if not arrival_city:
            warnings.append("Arrival city was not available from the flight data")

        response = FlightInfoResponse(
            request_id=request_id,
            cached=False,
            flight_number=query.flight_number,
            query_date=query.date,
            flight=flight,
            departure_weather=departure_weather.model_dump(mode="json") if departure_weather else None,
            arrival_weather=arrival_weather.model_dump(mode="json") if arrival_weather else None,
            warnings=warnings,
        )
        await self.cache.set(cache_key, response.model_dump(mode="json"))
        return response

    @staticmethod
    def _cache_key(query: FlightInfoQuery) -> str:
        digest = hashlib.sha256(json.dumps(query.model_dump(mode="json"), sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return f"flight-info:{digest}"
