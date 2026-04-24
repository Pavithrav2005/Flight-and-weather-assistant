from __future__ import annotations

from pydantic import BaseModel


class WeatherSummary(BaseModel):
    city: str
    temperature_celsius: float | None = None
    condition: str | None = None
    wind_speed_mps: float | None = None
    humidity: int | None = None
    country: str | None = None
