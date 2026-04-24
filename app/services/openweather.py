from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import DataNotFoundError
from app.models.weather import WeatherSummary
from app.services.base import BaseExternalService
from app.services.cache import InMemoryCache


class OpenWeatherService(BaseExternalService):
    def __init__(self, client: httpx.AsyncClient, settings: Settings, cache: InMemoryCache, logger: logging.Logger) -> None:
        super().__init__(client, settings, logger)
        self.cache = cache

    async def get_weather(self, city: str | None) -> WeatherSummary | None:
        if not city:
            return None

        cache_key = self._cache_key("openweather", {"city": city.lower().strip()})
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return WeatherSummary.model_validate(cached)

        payload = await self.request_json(
            "GET",
            f"{self.settings.openweather_base_url.rstrip('/')}/weather",
            params={
                "q": city,
                "appid": self.settings.openweather_api_key,
                "units": "metric",
            },
        )

        if payload.get("cod") in {"404", 404}:
            raise DataNotFoundError(f"Weather data was not found for {city}")

        main = payload.get("main") or {}
        weather_items = payload.get("weather") or []
        wind = payload.get("wind") or {}
        sys_info = payload.get("sys") or {}

        result = WeatherSummary(
            city=payload.get("name") or city,
            country=sys_info.get("country"),
            temperature_celsius=main.get("temp"),
            condition=weather_items[0].get("description") if weather_items else None,
            wind_speed_mps=wind.get("speed"),
            humidity=main.get("humidity"),
        )
        await self.cache.set(cache_key, result.model_dump(mode="json"))
        return result

    @staticmethod
    def _cache_key(prefix: str, payload: dict[str, Any]) -> str:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"
