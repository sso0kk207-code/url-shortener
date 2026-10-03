"""Кэш и rate limiter. Если задан REDIS_URL - работают через Redis, иначе in-memory (для разработки и тестов)."""
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

REDIS_URL = os.getenv("REDIS_URL")
_redis = None
if REDIS_URL:
    import redis

    _redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)


class Cache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> str | None:
        if _redis:
            return _redis.get(key)
        item = self._data.get(key)
        if not item:
            return None
        if item[0] < time.time():
            self._data.pop(key, None)
            return None
        return item[1]

    def set(self, key: str, value: str, ttl: int = 300) -> None:
        if _redis:
            _redis.set(key, value, ex=ttl)
        else:
            self._data[key] = (time.time() + ttl, value)

    def delete(self, key: str) -> None:
        if _redis:
            _redis.delete(key)
        else:
            self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()


class RateLimiter:
    """Скользящее окно: не более `limit` запросов за `window` секунд на ключ."""

    def __init__(self, limit: int, window: int = 60) -> None:
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        now = time.time()
        if _redis:
            k = f"rl:{key}:{int(now // self.window)}"
            n = _redis.incr(k)
            if n == 1:
                _redis.expire(k, self.window)
            return n <= self.limit
        q = self._hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


cache = Cache()
create_limiter = RateLimiter(limit=int(os.getenv("RATE_LIMIT_CREATE", "30")))
redirect_limiter = RateLimiter(limit=int(os.getenv("RATE_LIMIT_REDIRECT", "300")))


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def limit_by_ip(limiter_getter):
    def dep(request: Request) -> None:
        if not limiter_getter().hit(client_ip(request)):
            raise HTTPException(429, "Too many requests", headers={"Retry-After": "60"})

    return dep
