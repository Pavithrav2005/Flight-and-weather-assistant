from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request

from app.models.flight import FlightInfoQuery, FlightInfoResponse
from app.services.flight_info import FlightInfoService

router = APIRouter(tags=["flight"])


def build_query(
    flight_number: str = Query(..., min_length=1, description="Flight number, such as AA100"),
    date: date | None = Query(default=None, description="Optional flight date in YYYY-MM-DD format"),
    airline: str | None = Query(default=None, description="Optional airline filter"),
    departure_airport: str | None = Query(default=None, description="Optional departure airport filter"),
    arrival_airport: str | None = Query(default=None, description="Optional arrival airport filter"),
) -> FlightInfoQuery:
    return FlightInfoQuery(
        flight_number=flight_number,
        date=date,
        airline=airline,
        departure_airport=departure_airport,
        arrival_airport=arrival_airport,
    )


@router.get("/flight-info", response_model=FlightInfoResponse)
async def flight_info(request: Request, query: FlightInfoQuery = Depends(build_query)) -> FlightInfoResponse:
    service: FlightInfoService = request.app.state.flight_info_service
    return await service.get_flight_info(query)
