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
        
        logger.info(f"🔄 API Request: {method} {url}")
        if data:
            logger.info(f"📤 Request data: {data}")
        
        if data:
            data = {k: v for k, v in data.items() if v is not None}
        
        try:
            async with self._create_session() as session:
                async with session.request(method, url, json=data) as response:
                    
                    response_text = await response.text()
                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    logger.info(f"📥 API Response - Status: {response.status}, Content-Type: {content_type}")
                    
                    if response.status not in (200, 201, 204):
                        logger.error(f"❌ Ошибка API: {response.status} для {url}")
                        logger.error(f"Тело ответа: {response_text}")
                    
                    if response.status in (200, 201, 204):
                        if response.status == 204:  
                            logger.info(f"✅ Успешный ответ без содержимого")
                            return {}
                        
                        if 'application/json' in content_type and response_text.strip():
                            try:
                                json_data = await response.json()
                                logger.info(f"✅ Успешный JSON ответ")
                                return json_data
                            except Exception as json_error:
                                logger.warning(f"⚠️ Ошибка парсинга JSON: {json_error}")
                                return {}
                        else:
                            logger.info(f"✅ Успешный ответ без JSON")
                            return {}
                    
                    elif response.status == 400:
                        logger.error("❌ Ошибка 400: Неверный запрос или нарушение логики")
                        return None
                    elif response.status == 401:
                        logger.error("❌ Ошибка 401: Неверный API-токен")
                        return None
                    elif response.status == 403:
                        logger.error("❌ Ошибка 403: Недостаточно прав")
                        return None
                    elif response.status == 404:
                        logger.warning("⚠️ Ошибка 404: Ресурс не найден")
                        return None
                    elif response.status == 405:
                        logger.error("❌ Ошибка 405: Неверный метод запроса")
                        return None
                    elif response.status == 409:
                        logger.error("❌ Ошибка 409: Конфликт сущностей")
                        return None
                    elif response.status >= 500:
                        logger.error("❌ Ошибка 500: Ошибка сервера StudGram")
                        return None
                    
                    else:
                        logger.warning(f"⚠️ Неизвестный статус ответа: {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error(f"⏰ Таймаут подключения к API: {url}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"🔌 Ошибка подключения к API: {e}")
            return None
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка: {e}")
            return None
        
    async def request_with_debug(self, method: str, endpoint: str, data: Dict = None) -> Optional[dict]:
        """Метод для отладки с подробным логированием"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        logger.info(f"API Request: {method} {url}")
        if data:
            logger.info(f"Request data: {data}")
        
        try:
            async with self._create_session() as session:
                async with session.request(method, url, json=data) as response:
                    response_text = await response.text()
                    content_type = response.headers.get('Content-Type', '')
                    
                    logger.info(f"API Response status: {response.status}")
                    logger.info(f"API Response Content-Type: {content_type}")
                    logger.info(f"API Response body: {response_text}")
                    
                    if response.status in (200, 201, 204):
                        if 'application/json' in content_type and response_text.strip():
                            try:
                                return await response.json()
                            except:
                                return {"raw_response": response_text}
                        else:
                            return {"status": "success", "message": "Empty or non-JSON response"}
                    else:
                        return None
                        
        except Exception as e:
            logger.error(f"API Request error: {e}")
            return None