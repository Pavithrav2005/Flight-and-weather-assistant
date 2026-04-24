from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class InMemoryCache:
    def __init__(self, default_ttl_seconds: int) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._store: dict[str, CacheEntry[object]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> object | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.monotonic():
                self._store.pop(key, None)
                return None
            return entry.value

    async def set(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        async with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=time.monotonic() + ttl)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
