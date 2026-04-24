from __future__ import annotations

from datetime import date as date_cls, datetime

from pydantic import BaseModel, Field, field_validator


class FlightInfoQuery(BaseModel):
    flight_number: str = Field(min_length=1)
    date: date_cls | None = None
    airline: str | None = None
    departure_airport: str | None = None
    arrival_airport: str | None = None

    @field_validator("flight_number", "airline", "departure_airport", "arrival_airport", mode="before")
    @classmethod
    def strip_blank_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AirlineInfo(BaseModel):
    name: str | None = None
    iata: str | None = None
    icao: str | None = None


class FlightNumberInfo(BaseModel):
    number: str | None = None
    iata: str | None = None
    icao: str | None = None


class AirportInfo(BaseModel):
    airport: str | None = None
    iata: str | None = None
    icao: str | None = None
    terminal: str | None = None
    gate: str | None = None
    delay: int | None = None
    scheduled: datetime | None = None
    estimated: datetime | None = None
    actual: datetime | None = None
    estimated_runway: datetime | None = None
    actual_runway: datetime | None = None
    city: str | None = None
    country: str | None = None
    timezone: str | None = None


class LiveFlightInfo(BaseModel):
    updated: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    direction: float | None = None
    speed_horizontal: float | None = None
    speed_vertical: float | None = None
    is_ground: bool | None = None


class FlightStatusData(BaseModel):
    flight_date: date_cls | None = None
    flight_status: str | None = None
    airline: AirlineInfo | None = None
    flight: FlightNumberInfo | None = None
    departure: AirportInfo | None = None
    arrival: AirportInfo | None = None
    live: LiveFlightInfo | None = None


class FlightInfoResponse(BaseModel):
    request_id: str
    cached: bool = False
    flight_number: str
    query_date: date_cls | None = None
    flight: FlightStatusData
    departure_weather: dict[str, object] | None = None
    arrival_weather: dict[str, object] | None = None
    warnings: list[str] = Field(default_factory=list)


class PlaceAirportMatch(BaseModel):
    airport: str | None = None
    iata: str | None = None
    city: str | None = None
    country: str | None = None


class RouteFlightQuery(BaseModel):
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    date: date_cls | None = None
    max_results: int = Field(default=5, ge=1, le=20)

    @field_validator("origin", "destination", mode="before")
    @classmethod
    def normalize_place_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RouteFlightItem(BaseModel):
    flight_status: str | None = None
    flight_iata: str | None = None
    airline_name: str | None = None
    departure_airport: str | None = None
    departure_iata: str | None = None
    departure_scheduled: datetime | None = None
    arrival_airport: str | None = None
    arrival_iata: str | None = None
    arrival_scheduled: datetime | None = None


class RouteFlightResponse(BaseModel):
    query: RouteFlightQuery
    origin_matches: list[PlaceAirportMatch] = Field(default_factory=list)
    destination_matches: list[PlaceAirportMatch] = Field(default_factory=list)
    flights: list[RouteFlightItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_date(value: str | None) -> date_cls | None:
    if not value:
        return None
    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        return None
