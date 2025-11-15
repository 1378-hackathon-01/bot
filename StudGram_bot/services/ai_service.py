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
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    async def chat_completion(
            self,
            messages: List[Dict[str, Any]],
            model: str = "openai/gpt-4o",  
            **kwargs
    ) -> str:
        """
        Выполнение chat completion запроса
        """
        try:
            
            if not messages or not any(self._has_content(msg) for msg in messages):
                return "Пожалуйста, отправьте текст или изображение для анализа."

            completion = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"Ошибка при обработке запроса: {str(e)}"

    def _has_content(self, message: Dict[str, Any]) -> bool:
        """Проверяет, есть ли в сообщении контент"""
        content = message.get('content')
        if not content:
            return False
        
        if isinstance(content, str):
            return bool(content.strip())
        
        if isinstance(content, list):
            for item in content:
                if item.get('type') == 'text' and item.get('text', '').strip():
                    return True
                if item.get('type') == 'image_url' and item.get('image_url', {}).get('url'):
                    return True
        return False

    async def send_text(self, text: str, model: str = "openai/gpt-4o", **kwargs) -> str:
        """
        Отправка текстового запроса с проверкой пустого ввода
        """
        if not text or not text.strip():
            return "Вы отправили пустое сообщение. Пожалуйста, напишите ваш вопрос или запрос."

        messages = [
            {
                "role": "user",
                "content": text.strip()
            }
        ]
        return await self.chat_completion(messages, model, **kwargs)

    async def send_text_with_image(
            self,
            text: str,
            image_url: str,
            model: str = "openai/gpt-4o",
            **kwargs
    ) -> str:
        """
        Отправка запроса с текстом и изображением
        """
        if not image_url or not image_url.startswith(('http://', 'https://', 'data:')):
            return "Некорректная ссылка на изображение. Пожалуйста, укажите валидный URL."

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text or "Что изображено на картинке?"
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
        
        try:
            return await self.chat_completion(messages, model, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка обработки изображения AI: {e}")
            return "Не удалось обработать изображение. Попробуйте отправить другое изображение или опишите его текстом."


async def handle_user_message(message_text: str, image_url: str = None):
    ai_service = AIService()

    if not message_text.strip() and not image_url:
        return "Пожалуйста, отправьте текст или изображение для анализа."

    if image_url:
        return await ai_service.send_text_with_image(
            text=message_text or "Что изображено на картинке?",
            image_url=image_url
        )

    return await ai_service.send_text(message_text)


if __name__ == "__main__":
    import asyncio

    async def main():
        ai_service = AIService()

        response = await ai_service.send_text("")
        print("Пустой запрос:", response)

        response = await ai_service.send_text("Привет! Как дела?")
        print("Нормальный запрос:", response)

        response = await ai_service.send_text_with_image(
            text="Что изображено на картинке?",
            image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
        )
        print("Запрос с изображением:", response)

    asyncio.run(main())