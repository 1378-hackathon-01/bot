import logging
from services.bot_service import BotService
from config import active_chats, users_db

logger = logging.getLogger(__name__)

async def handle_callback(event, bot_service: BotService):
    """Обрабатывает нажатия на кнопки"""
    user_id = event.from_user.user_id
    chat_id = event.chat.chat_id
    callback_data = event.callback.payload
    
    logger.info(f"Callback в чате {chat_id}: '{callback_data}'")
    
    try:
        handled = await bot_service.handle_callback(callback_data, chat_id)
        
        if not handled:
            logger.error(f"Не удалось обработать callback: {callback_data}")
            await bot_service.bot.send_message(chat_id=chat_id, text="❌ Не удалось обработать действие")
            
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")
        await bot_service.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка при обработке действия. Попробуйте позже."
        )