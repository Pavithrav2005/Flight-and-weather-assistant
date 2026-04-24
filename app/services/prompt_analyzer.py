from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError, ValidationAppError
from app.models.chat import ChatIntent
from app.services.base import BaseExternalService


@dataclass(slots=True)
class PromptToolCall:
    tool_name: str
    arguments: dict[str, object]


@dataclass(slots=True)
class PromptAnalysis:
    intent: ChatIntent
    tool_calls: list[PromptToolCall]
    clarification_question: str | None = None
    ambiguity_reason: str | None = None
    flight_numbers: list[str] | None = None
    cities: list[str] | None = None
    origins: list[str] | None = None
    destinations: list[str] | None = None


class PromptAnalyzer(Protocol):
    async def analyze(self, prompt: str) -> PromptAnalysis:
        ...


class NvidiaNIMPromptAnalyzer(BaseExternalService):
    def __init__(self, client: httpx.AsyncClient, settings: Settings, logger: logging.Logger) -> None:
        super().__init__(client, settings, logger)

    async def analyze(self, prompt: str) -> PromptAnalysis:
        try:
            payload = await self._post_chat_completion(prompt)
        except UpstreamServiceError as exc:
            self.logger.warning(
                "nim_fallback_used",
                extra={"reason": exc.code, "detail": exc.detail},
            )
            return self._fallback_analysis(prompt)

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise UpstreamServiceError("NVIDIA NIM returned no choices", status_code=502, code="nim_invalid_response")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise UpstreamServiceError("NVIDIA NIM response was empty", status_code=502, code="nim_invalid_response")

        parsed = self._parse_model_json(content)

        tool_calls = self._parse_tool_calls(parsed.get("tool_calls"))
        # Backward-compatible fallback for older analyzer payload shape.
        if not tool_calls:
            legacy_intent = self._parse_intent(parsed.get("intent"))
            legacy_flight_number = self._normalize_optional_text(parsed.get("flight_number"))
            legacy_city = self._normalize_optional_text(parsed.get("city"))
            if legacy_intent is ChatIntent.flight and legacy_flight_number:
                tool_calls = [PromptToolCall(tool_name="flight_info", arguments={"flight_number": legacy_flight_number})]
            elif legacy_intent is ChatIntent.temperature and legacy_city:
                tool_calls = [PromptToolCall(tool_name="weather_lookup", arguments={"city": legacy_city})]

        return PromptAnalysis(
            intent=self._parse_intent(parsed.get("intent")),
            tool_calls=tool_calls,
            clarification_question=self._normalize_optional_text(parsed.get("clarification_question")),
            ambiguity_reason=self._normalize_optional_text(parsed.get("ambiguity_reason")),
            flight_numbers=self._parse_text_list(parsed.get("flight_numbers")),
            cities=self._parse_text_list(parsed.get("cities")),
            origins=self._parse_text_list(parsed.get("origins")),
            destinations=self._parse_text_list(parsed.get("destinations")),
        )

    async def _post_chat_completion(self, prompt: str) -> dict[str, object]:
        request_payload = {
            "model": self.settings.nvidia_nim_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a routing and extraction assistant for a travel chatbot. "
                        "Return strict JSON only. "
                        "Schema keys: "
                        "intent (flight|temperature|combined|unknown), "
                        "tool_calls (array), clarification_question, ambiguity_reason, flight_numbers, cities, origins, destinations. "
                        "Each tool_calls item has: tool_name (flight_info|weather_lookup|route_flights), arguments (object). "
                        "For flight_info arguments may include: flight_number, date (YYYY-MM-DD), airline, departure_airport, arrival_airport. "
                        "For weather_lookup arguments must include: city. "
                        "For route_flights arguments include: origin, destination, optional date (YYYY-MM-DD), optional max_results. "
                        "route_flights must be used for prompts like flights from X to Y where X or Y may be city/state/country. "
                        "If user asks both flight and weather in one sentence, return two tool calls and intent=combined. "
                        "If entities are ambiguous or missing, set clarification_question with a concise follow-up and keep tool_calls empty."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        last_error: Exception | None = None
        for attempt in range(1, self.settings.external_api_retries + 1):
            try:
                response = await self.client.post(
                    f"{self.settings.nvidia_nim_base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.nvidia_nim_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                    timeout=httpx.Timeout(self.settings.nvidia_nim_timeout_seconds),
                )
                if response.status_code == 429:
                    raise UpstreamServiceError("NVIDIA NIM rate limit exceeded", status_code=429, code="rate_limited")
                if 500 <= response.status_code < 600:
                    raise UpstreamServiceError("NVIDIA NIM service unavailable", status_code=502, code="nim_unavailable")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise UpstreamServiceError("NVIDIA NIM returned invalid payload", status_code=502, code="nim_invalid_response")
                return payload
            except (httpx.TimeoutException, httpx.RequestError, UpstreamServiceError) as exc:
                last_error = exc
                if attempt >= self.settings.external_api_retries:
                    break
            
        if isinstance(last_error, UpstreamServiceError):
            raise last_error
        if isinstance(last_error, httpx.TimeoutException):
            raise UpstreamServiceError("NVIDIA NIM request timed out", status_code=504, code="nim_timeout") from last_error
        if isinstance(last_error, httpx.RequestError):
            raise UpstreamServiceError("NVIDIA NIM request failed", status_code=502, code="nim_request_failed") from last_error
        raise UpstreamServiceError("NVIDIA NIM unknown error", status_code=502, code="nim_unknown_error")

    @staticmethod
    def _parse_model_json(content: str) -> dict[str, object]:
        content = content.strip()
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = content[start : end + 1]
            try:
                parsed = json.loads(snippet)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        raise ValidationAppError("Unable to parse LLM intent response")

    @staticmethod
    def _parse_intent(raw_value: object) -> ChatIntent:
        if not isinstance(raw_value, str):
            return ChatIntent.unknown
        lowered = raw_value.strip().lower()
        if lowered == ChatIntent.flight.value:
            return ChatIntent.flight
        if lowered == ChatIntent.temperature.value:
            return ChatIntent.temperature
        return ChatIntent.unknown

    @staticmethod
    def _normalize_optional_text(raw_value: object) -> str | None:
        if not isinstance(raw_value, str):
            return None
        text = raw_value.strip()
        return text or None

    @classmethod
    def _parse_tool_calls(cls, raw_value: object) -> list[PromptToolCall]:
        if not isinstance(raw_value, list):
            return []

        parsed_calls: list[PromptToolCall] = []
        for item in raw_value:
            if not isinstance(item, dict):
                continue

            tool_name = cls._normalize_optional_text(item.get("tool_name"))
            arguments_raw = item.get("arguments")
            if not tool_name or not isinstance(arguments_raw, dict):
                continue

            parsed_calls.append(PromptToolCall(tool_name=tool_name, arguments=arguments_raw))
        return parsed_calls

    @classmethod
    def _parse_text_list(cls, raw_value: object) -> list[str]:
        if not isinstance(raw_value, list):
            return []

        parsed: list[str] = []
        for item in raw_value:
            normalized = cls._normalize_optional_text(item)
            if normalized:
                parsed.append(normalized)
        return parsed

    @classmethod
    def _fallback_analysis(cls, prompt: str) -> PromptAnalysis:
        text = prompt.strip()
        lowered = text.lower()

        route_match = re.search(
            r"\bfrom\s+(?P<origin>[A-Za-z][A-Za-z\s'.-]{1,50}?)\s+to\s+(?P<destination>[A-Za-z][A-Za-z\s'.-]{1,50})(?:[?.!,]|$)",
            text,
            flags=re.IGNORECASE,
        )
        flight_numbers = [
            item.replace(" ", "").upper()
            for item in re.findall(r"\b([A-Za-z]{2,3}\s?\d{1,4}[A-Za-z]?)\b", text)
        ]
        flight_numbers = list(dict.fromkeys(flight_numbers))

        weather_city = cls._extract_weather_city(text)
        weather_keywords = any(token in lowered for token in ("weather", "temperature", "forecast", "climate"))

        tool_calls: list[PromptToolCall] = []
        origins: list[str] = []
        destinations: list[str] = []
        cities: list[str] = []

        if route_match:
            origin = route_match.group("origin").strip(" .,!?:;")
            destination = route_match.group("destination").strip(" .,!?:;")
            tool_calls.append(PromptToolCall(tool_name="route_flights", arguments={"origin": origin, "destination": destination}))
            origins.append(origin)
            destinations.append(destination)

        for number in flight_numbers:
            tool_calls.append(PromptToolCall(tool_name="flight_info", arguments={"flight_number": number}))

        if weather_city:
            tool_calls.append(PromptToolCall(tool_name="weather_lookup", arguments={"city": weather_city}))
            cities.append(weather_city)
        elif weather_keywords and not route_match and not flight_numbers:
            return PromptAnalysis(
                intent=ChatIntent.unknown,
                tool_calls=[],
                clarification_question="Please specify a city for weather or temperature lookup.",
                ambiguity_reason="missing_city",
                flight_numbers=flight_numbers,
                cities=[],
                origins=origins,
                destinations=destinations,
            )

        if not tool_calls:
            return PromptAnalysis(
                intent=ChatIntent.unknown,
                tool_calls=[],
                clarification_question="Please provide a flight number, or ask for flights from X to Y, or weather in a city.",
                ambiguity_reason="fallback_no_entities",
                flight_numbers=flight_numbers,
                cities=cities,
                origins=origins,
                destinations=destinations,
            )

        has_flight_like = any(call.tool_name in {"flight_info", "route_flights"} for call in tool_calls)
        has_weather = any(call.tool_name == "weather_lookup" for call in tool_calls)
        if has_flight_like and has_weather:
            intent = ChatIntent.combined
        elif has_flight_like:
            intent = ChatIntent.flight
        elif has_weather:
            intent = ChatIntent.temperature
        else:
            intent = ChatIntent.unknown

        return PromptAnalysis(
            intent=intent,
            tool_calls=tool_calls,
            flight_numbers=flight_numbers,
            cities=cities,
            origins=origins,
            destinations=destinations,
        )

    @classmethod
    def _extract_weather_city(cls, text: str) -> str | None:
        match = re.search(
            r"\b(?:weather|temperature|forecast|climate)\b(?:\s+in|\s+at|\s+for)?\s+(?P<city>[A-Za-z][A-Za-z\s'.-]{1,50})(?:[?.!,]|$)",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        city = match.group("city").strip(" .,!?:;")
        return city or None
