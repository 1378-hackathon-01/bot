from typing import List, Dict, Any

from openai import AsyncOpenAI

from config import OPENROUTER_TOKEN


class AIService:
    """Сервис для работы с AI моделями через OpenRouter API"""

    def __init__(
            self,
            api_key: str = OPENROUTER_TOKEN,
            base_url: str = "https://openrouter.ai/api/v1",
    ):
        """
        Инициализация AI сервиса

        Args:
            api_key: API ключ для OpenRouter
            base_url: Базовый URL для API
            site_url: URL вашего сайта (для рейтинга на openrouter.ai)
            site_name: Название вашего сайта (для рейтинга на openrouter.ai)
        """
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    async def chat_completion(
            self,
            messages: List[Dict[str, Any]],
            model: str = "openai/gpt-5",
            **kwargs
    ) -> str:
        """
        Выполнение chat completion запроса

        Args:
            messages: Список сообщений для модели
            model: Название модели
            extra_body: Дополнительные параметры для запроса
            **kwargs: Дополнительные аргументы для API (temperature, max_tokens и т.д.)

        Returns:
            Текстовый ответ от модели
        """
        # noinspection PyTypeChecker
        completion = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )
        return completion.choices[0].message.content

    async def send_text(self, text: str, model: str = "openai/gpt-5", **kwargs) -> str:
        """
        Отправка текстового запроса

        Args:
            text: Текст запроса
            model: Название модели
            **kwargs: Дополнительные аргументы для API

        Returns:
            Текстовый ответ от модели
        """
        messages = [
            {
                "role": "user",
                "content": text
            }
        ]
        return await self.chat_completion(messages, model, **kwargs)

    async def send_text_with_image(
            self,
            text: str,
            image_url: str,
            model: str = "openai/gpt-5",
            **kwargs
    ) -> str:
        """
        Отправка запроса с текстом и изображением

        Args:
            text: Текст запроса
            image_url: URL изображения
            model: Название модели
            **kwargs: Дополнительные аргументы для API

        Returns:
            Текстовый ответ от модели
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ]
        return await self.chat_completion(messages, model, **kwargs)


# Пример использования
if __name__ == "__main__":
    import asyncio


    async def main():
        # Инициализация сервиса с context manager
        ai_service = AIService()

        # Простой текстовый запрос
        response = await ai_service.send_text("Привет! Как дела?")
        print(response)

        # Запрос с изображением
        response = await ai_service.send_text_with_image(
            text="What is in this image?",
            image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
            model="openai/gpt-5"
        )
        print(response)


    asyncio.run(main())
