from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import DataNotFoundError
from app.models.flight import AirlineInfo, AirportInfo, FlightInfoQuery, FlightNumberInfo, FlightStatusData, LiveFlightInfo, PlaceAirportMatch, RouteFlightItem, RouteFlightQuery, RouteFlightResponse, parse_date, parse_datetime
from app.services.base import BaseExternalService
from app.services.cache import InMemoryCache


class AviationstackService(BaseExternalService):
    def __init__(self, client: httpx.AsyncClient, settings: Settings, cache: InMemoryCache, logger: logging.Logger) -> None:
        super().__init__(client, settings, logger)
        self.cache = cache

    async def get_flight_status(self, query: FlightInfoQuery) -> FlightStatusData:
        cache_key = self._cache_key("aviationstack", query.model_dump(mode="json"))
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return FlightStatusData.model_validate(cached)

        payload = await self.request_json(
            "GET",
            f"{self.settings.aviationstack_base_url.rstrip('/')}/flights",
            params=self._build_params(query),
        )

        records = payload.get("data")
        if not isinstance(records, list) or not records:
            raise DataNotFoundError("No flights were returned by Aviationstack for the given filters")

        flight_record = self._select_record(records, query)
        if flight_record is None:
            raise DataNotFoundError("No matching flight was found")

        result = self._parse_record(flight_record)
        await self.cache.set(cache_key, result.model_dump(mode="json"))
        return result

    async def find_route_flights(self, query: RouteFlightQuery) -> RouteFlightResponse:
        cache_key = self._cache_key("route-flights", query.model_dump(mode="json"))
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return RouteFlightResponse.model_validate(cached)

        origin_is_iata = self._looks_like_iata(query.origin)
        destination_is_iata = self._looks_like_iata(query.destination)

        if origin_is_iata:
            origin_matches = [PlaceAirportMatch(airport=query.origin.upper(), iata=query.origin.upper())]
        else:
            origin_matches = await self._search_airports(query.origin)

        if destination_is_iata:
            destination_matches = [PlaceAirportMatch(airport=query.destination.upper(), iata=query.destination.upper())]
        else:
            destination_matches = await self._search_airports(query.destination)

        if not origin_matches:
            raise DataNotFoundError(f"No airports were found for origin: {query.origin}")
        if not destination_matches:
            raise DataNotFoundError(f"No airports were found for destination: {query.destination}")

        candidate_origins = origin_matches[:3]
        candidate_destinations = destination_matches[:3]

        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        if len(origin_matches) > len(candidate_origins):
            warnings.append(f"Origin matched multiple airports; using top {len(candidate_origins)} matches")
        if len(destination_matches) > len(candidate_destinations):
            warnings.append(f"Destination matched multiple airports; using top {len(candidate_destinations)} matches")

        for origin in candidate_origins:
            for destination in candidate_destinations:
                if not origin.iata or not destination.iata:
                    continue
                records.extend(await self._fetch_flights_by_airports(origin.iata, destination.iata, query.date))

        deduped = self._deduplicate_records(records)
        if not deduped:
            raise DataNotFoundError("No flights were found for the given route")

        route_flights = [self._parse_route_flight_item(record) for record in deduped[: query.max_results]]
        result = RouteFlightResponse(
            query=query,
            origin_matches=candidate_origins,
            destination_matches=candidate_destinations,
            flights=route_flights,
            warnings=warnings,
        )
        await self.cache.set(cache_key, result.model_dump(mode="json"))
        return result

    @staticmethod
    def _looks_like_iata(value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z]{3}", value.strip()))

    def _build_params(self, query: FlightInfoQuery) -> dict[str, Any]:
        params: dict[str, Any] = {
            "access_key": self.settings.aviationstack_api_key,
            "flight_iata": query.flight_number,
        }
        if query.date is not None:
            params["flight_date"] = query.date.isoformat()
        if query.airline:
            params["airline_name"] = query.airline
        if query.departure_airport:
            params["dep_iata"] = query.departure_airport
        if query.arrival_airport:
            params["arr_iata"] = query.arrival_airport
        return params

    async def _search_airports(self, place: str) -> list[PlaceAirportMatch]:
        payload = await self.request_json(
            "GET",
            f"{self.settings.aviationstack_base_url.rstrip('/')}/airports",
            params={
                "access_key": self.settings.aviationstack_api_key,
                "search": place,
                "limit": 10,
            },
        )

        records = payload.get("data")
        if not isinstance(records, list):
            return []

        matches: list[PlaceAirportMatch] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            matches.append(
                PlaceAirportMatch(
                    airport=record.get("airport_name") or record.get("airport"),
                    iata=record.get("iata_code") or record.get("iata"),
                    city=record.get("city_name") or record.get("city"),
                    country=record.get("country_name") or record.get("country"),
                )
            )
        return [m for m in matches if m.iata]

    async def _fetch_flights_by_airports(self, dep_iata: str, arr_iata: str, flight_date: date | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "access_key": self.settings.aviationstack_api_key,
            "dep_iata": dep_iata,
            "arr_iata": arr_iata,
            "limit": 20,
        }
        if flight_date is not None:
            params["flight_date"] = flight_date.isoformat()

        payload = await self.request_json(
            "GET",
            f"{self.settings.aviationstack_base_url.rstrip('/')}/flights",
            params=params,
        )
        records = payload.get("data")
        if not isinstance(records, list):
            return []
        return [record for record in records if isinstance(record, dict)]

    @staticmethod
    def _deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []

        for record in records:
            flight = record.get("flight") or {}
            departure = record.get("departure") or {}
            arrival = record.get("arrival") or {}
            key = "|".join(
                [
                    str(flight.get("iata") or flight.get("icao") or flight.get("number") or ""),
                    str(departure.get("iata") or ""),
                    str(arrival.get("iata") or ""),
                    str(departure.get("scheduled") or ""),
                ]
            )
            if not key.strip("|"):
                continue
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        return deduped

    def _parse_route_flight_item(self, record: dict[str, Any]) -> RouteFlightItem:
        airline = record.get("airline") or {}
        flight = record.get("flight") or {}
        departure = record.get("departure") or {}
        arrival = record.get("arrival") or {}

        return RouteFlightItem(
            flight_status=record.get("flight_status"),
            flight_iata=flight.get("iata") or flight.get("icao") or flight.get("number"),
            airline_name=airline.get("name"),
            departure_airport=departure.get("airport"),
            departure_iata=departure.get("iata"),
            departure_scheduled=parse_datetime(departure.get("scheduled")),
            arrival_airport=arrival.get("airport"),
            arrival_iata=arrival.get("iata"),
            arrival_scheduled=parse_datetime(arrival.get("scheduled")),
        )

    def _select_record(self, records: list[dict[str, Any]], query: FlightInfoQuery) -> dict[str, Any] | None:
        normalized_number = query.flight_number.lower().strip()
        normalized_airline = query.airline.lower().strip() if query.airline else None
        normalized_departure = query.departure_airport.lower().strip() if query.departure_airport else None
        normalized_arrival = query.arrival_airport.lower().strip() if query.arrival_airport else None

        best_match: dict[str, Any] | None = None
        for record in records:
            flight = record.get("flight") or {}
            airline = record.get("airline") or {}
            departure = record.get("departure") or {}
            arrival = record.get("arrival") or {}

            candidates = [
                str(flight.get("iata") or "").lower(),
                str(flight.get("icao") or "").lower(),
                str(flight.get("number") or "").lower(),
            ]
            if normalized_number not in candidates and not any(normalized_number == candidate for candidate in candidates if candidate):
                continue

            if normalized_airline and normalized_airline not in str(airline.get("name") or "").lower() and normalized_airline not in str(airline.get("iata") or "").lower() and normalized_airline not in str(airline.get("icao") or "").lower():
                continue

            if normalized_departure and normalized_departure not in str(departure.get("airport") or "").lower() and normalized_departure not in str(departure.get("iata") or "").lower() and normalized_departure not in str(departure.get("icao") or "").lower():
                continue

            if normalized_arrival and normalized_arrival not in str(arrival.get("airport") or "").lower() and normalized_arrival not in str(arrival.get("iata") or "").lower() and normalized_arrival not in str(arrival.get("icao") or "").lower():
                continue

            if query.date is not None:
                record_date = parse_date(record.get("flight_date"))
                if record_date != query.date:
                    continue

            best_match = record
            break

        return best_match or (records[0] if len(records) == 1 else None)

    def _parse_record(self, record: dict[str, Any]) -> FlightStatusData:
        airline = record.get("airline") or {}
        flight = record.get("flight") or {}
        departure = record.get("departure") or {}
        arrival = record.get("arrival") or {}
        live = record.get("live") or {}

        return FlightStatusData(
            flight_date=parse_date(record.get("flight_date")),
            flight_status=record.get("flight_status"),
            airline=AirlineInfo(
                name=airline.get("name"),
                iata=airline.get("iata"),
                icao=airline.get("icao"),
            )
            if airline
            else None,
            flight=FlightNumberInfo(
                number=flight.get("number"),
                iata=flight.get("iata"),
                icao=flight.get("icao"),
            )
            if flight
            else None,
            departure=AirportInfo(
                airport=departure.get("airport"),
                iata=departure.get("iata"),
                icao=departure.get("icao"),
                terminal=departure.get("terminal"),
                gate=departure.get("gate"),
                delay=departure.get("delay"),
                scheduled=parse_datetime(departure.get("scheduled")),
                estimated=parse_datetime(departure.get("estimated")),
                actual=parse_datetime(departure.get("actual")),
                estimated_runway=parse_datetime(departure.get("estimated_runway")),
                actual_runway=parse_datetime(departure.get("actual_runway")),
                city=departure.get("city"),
                country=departure.get("country"),
                timezone=departure.get("timezone"),
            )
            if departure
            else None,
            arrival=AirportInfo(
                airport=arrival.get("airport"),
                iata=arrival.get("iata"),
                icao=arrival.get("icao"),
                terminal=arrival.get("terminal"),
                gate=arrival.get("gate"),
                delay=arrival.get("delay"),
                scheduled=parse_datetime(arrival.get("scheduled")),
                estimated=parse_datetime(arrival.get("estimated")),
                actual=parse_datetime(arrival.get("actual")),
                estimated_runway=parse_datetime(arrival.get("estimated_runway")),
                actual_runway=parse_datetime(arrival.get("actual_runway")),
                city=arrival.get("city"),
                country=arrival.get("country"),
                timezone=arrival.get("timezone"),
            )
            if arrival
            else None,
            live=LiveFlightInfo(
                updated=parse_datetime(live.get("updated")),
                latitude=live.get("latitude"),
                longitude=live.get("longitude"),
                altitude=live.get("altitude"),
                direction=live.get("direction"),
                speed_horizontal=live.get("speed_horizontal"),
                speed_vertical=live.get("speed_vertical"),
                is_ground=live.get("is_ground"),
            )
            if live
            else None,
        )

    @staticmethod
    def _cache_key(prefix: str, payload: dict[str, Any]) -> str:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"
