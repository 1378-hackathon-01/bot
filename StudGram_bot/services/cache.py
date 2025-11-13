from datetime import datetime, timedelta
from typing import Any, Dict

class Cache:
    """Простой кэш с TTL"""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Any:
        """Получить значение из кэша"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """Установить значение в кэш"""
        self._cache[key] = (value, datetime.now())
    
    def clear(self):
        """Очистить кэш"""
        self._cache.clear()