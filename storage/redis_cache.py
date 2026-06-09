from __future__ import annotations

import json
from typing import Any


_MEMORY_CACHE: dict[str, str] = {}


class RedisCache:
    def __init__(self, url: str = "redis://localhost:6379/0", *, use_memory_fallback: bool = True) -> None:
        self.url = url
        self.use_memory_fallback = use_memory_fallback
        self.client = None
        self.error_message_safe = ""
        try:
            import redis

            self.client = redis.Redis.from_url(url, decode_responses=True)
        except Exception as exc:
            self.error_message_safe = str(exc)

    @property
    def available(self) -> bool:
        return self.client is not None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> dict[str, Any]:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        if self.client is not None:
            self.client.set(key, payload, ex=ttl_seconds)
            return {"status": "written", "backend": "redis", "key": key}
        if self.use_memory_fallback:
            _MEMORY_CACHE[key] = payload
            return {"status": "written", "backend": "memory_fallback", "key": key}
        return {"status": "dependency_missing", "error_message_safe": self.error_message_safe}

    def get_json(self, key: str) -> Any:
        payload = None
        if self.client is not None:
            payload = self.client.get(key)
        elif self.use_memory_fallback:
            payload = _MEMORY_CACHE.get(key)
        if not payload:
            return None
        return json.loads(payload)
