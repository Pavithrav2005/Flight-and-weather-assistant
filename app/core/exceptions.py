from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppError(Exception):
    status_code: int
    code: str
    detail: str
    headers: dict[str, str] | None = None
    extra: dict[str, Any] | None = None


class UpstreamServiceError(AppError):
    def __init__(self, detail: str, *, status_code: int = 502, code: str = "upstream_error", headers: dict[str, str] | None = None, extra: dict[str, Any] | None = None) -> None:
        super().__init__(status_code=status_code, code=code, detail=detail, headers=headers, extra=extra)


class DataNotFoundError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=404, code="not_found", detail=detail)


class ValidationAppError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=422, code="validation_error", detail=detail)
