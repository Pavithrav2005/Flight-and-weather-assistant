from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError


class BaseExternalService:
    def __init__(self, client: httpx.AsyncClient, settings: Settings, logger: logging.Logger) -> None:
        self.client = client
        self.settings = settings
        self.logger = logger

    async def request_json(self, method: str, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, self.settings.external_api_retries + 1):
            try:
                response = await self.client.request(method, url, params=params, headers=headers)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    error_headers = {"Retry-After": retry_after} if retry_after else None
                    raise UpstreamServiceError("Upstream rate limit exceeded", status_code=429, code="rate_limited", headers=error_headers)

                if 500 <= response.status_code < 600:
                    raise UpstreamServiceError(f"Upstream service returned HTTP {response.status_code}", status_code=502, code="upstream_unavailable")

                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise UpstreamServiceError("Unexpected upstream payload format", status_code=502, code="invalid_upstream_payload")
                return payload
            except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError, UpstreamServiceError) as exc:
                last_error = exc
                if attempt >= self.settings.external_api_retries or not self._should_retry(exc):
                    raise self._normalize_error(exc) from exc

                delay = min(2 ** (attempt - 1), 5)
                self.logger.warning("external_request_retry", extra={"url": url, "attempt": attempt, "delay_seconds": delay, "error": str(exc)})
                await asyncio.sleep(delay)

        raise self._normalize_error(last_error) if last_error else UpstreamServiceError("Unknown upstream error")

    @staticmethod
    def _should_retry(exc: Exception) -> bool:
        if isinstance(exc, (httpx.TimeoutException, httpx.RequestError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {429, 500, 502, 503, 504}
        if isinstance(exc, UpstreamServiceError):
            return exc.status_code in {429, 502, 503, 504}
        return False

    @staticmethod
    def _normalize_error(exc: Exception | None) -> UpstreamServiceError:
        if isinstance(exc, UpstreamServiceError):
            return exc
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            code = "upstream_http_error"
            if status == 401:
                code = "upstream_unauthorized"
            elif status == 403:
                code = "upstream_forbidden"
            elif status == 404:
                code = "upstream_not_found"
            elif status == 429:
                code = "rate_limited"

            detail = f"Upstream returned HTTP {status}"
            try:
                payload = exc.response.json()
                if isinstance(payload, dict):
                    error_obj = payload.get("error")
                    if isinstance(error_obj, dict):
                        message = error_obj.get("message") or error_obj.get("info")
                        if isinstance(message, str) and message.strip():
                            detail = message.strip()
                    elif isinstance(payload.get("message"), str) and payload["message"].strip():
                        detail = payload["message"].strip()
            except (ValueError, json.JSONDecodeError):
                pass

            return UpstreamServiceError(detail, status_code=status if status < 500 else 502, code=code)
        if isinstance(exc, httpx.TimeoutException):
            return UpstreamServiceError("External API request timed out", status_code=504, code="upstream_timeout")
        if isinstance(exc, httpx.RequestError):
            return UpstreamServiceError(f"External API request failed: {exc}", status_code=502, code="upstream_request_failed")
        return UpstreamServiceError("Unknown upstream error")
