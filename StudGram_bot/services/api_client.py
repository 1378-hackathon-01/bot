import aiohttp
import asyncio
import logging
from typing import Optional, Dict
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class APIClient:
    """Универсальный клиент для работы с API StudGram"""
    
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "API-Token": token,
            "Content-Type": "application/json"
        }
        self.timeout = aiohttp.ClientTimeout(total=30)
    
    @asynccontextmanager
    async def _create_session(self):
        """Контекстный менеджер для сессии"""
        async with aiohttp.ClientSession(
            headers=self.headers, 
            timeout=self.timeout
        ) as session:
            yield session
    
    async def request(self, method: str, endpoint: str, data: Dict = None) -> Optional[dict]:
        """Универсальный метод для выполнения API запросов с обработкой ошибок"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with self._create_session() as session:
                async with session.request(method, url, json=data) as response:
                    
                    if response.status in (200, 201):
                        return await response.json()
                    elif response.status == 404:
                        logger.warning(f"Ресурс не найден: {url}")
                        return None
                    elif response.status == 401:
                        logger.error("Ошибка авторизации API")
                        return None
                    elif response.status == 400:
                        logger.error(f"Ошибка в запросе: {response.status} для {url}")
                        return None
                    elif response.status == 403:
                        logger.error(f"Недостаточно прав: {response.status} для {url}")
                        return None
                    elif response.status == 405:
                        logger.error(f"Неверный метод: {response.status} для {url}")
                        return None
                    elif response.status == 409:
                        logger.error(f"Конфликт сущностей: {response.status} для {url}")
                        return None
                    elif response.status == 500:
                        logger.error(f"Ошибка сервера StudGram: {response.status} для {url}")
                        return None
                    else:
                        logger.error(f"Неизвестная ошибка API: {response.status} для {url}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error(f"Таймаут подключения к API: {url}")
            return None
        except Exception as e:
            logger.error(f"Ошибка подключения к API: {e}")
            return None