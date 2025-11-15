import asyncio
import logging
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, BotStarted, MessageCallback

from config import BOT_TOKEN, users_db, pending_registrations, active_chats
from services.bot_service import BotService
from handlers.commands import CommandHandler
from handlers.callbacks import handle_callback
from models.user import User, CalendarState
from services.university_service import UniversityService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

bot_service = BotService(bot)
command_handler = CommandHandler(bot_service)

@dp.bot_started()
async def on_bot_started(event: BotStarted):
    user_id = event.from_user.user_id
    chat_id = event.chat_id
    
    logger.info(f"Бот запущен для пользователя {user_id} в чате {chat_id}")
    
    active_chats[chat_id] = user_id
    
    if user_id not in users_db:
        await bot_service.start_registration(chat_id, user_id)
    else:
        user = users_db[user_id]
        await bot_service.send_main_menu(chat_id, user)

@dp.message_created()
async def message_handler(event: MessageCreated):
    user_id = event.from_user.user_id
    chat_id = event.chat.chat_id
    text = event.message.body.text if event.message.body and event.message.body.text else ""
    text = text.strip()
    
    logger.info(f"Сообщение от {event.from_user.first_name} ({user_id}): '{text}'")
    
    active_chats[chat_id] = user_id
    
    try:
        if user_id in users_db:
            user = users_db[user_id]
            if user.in_chat_mode and text.lower() not in ['меню', 'назад', '/menu']:
                has_attachments = False
                image_url = None

                if hasattr(event.message, 'attachments') and event.message.attachments:
                    for attachment in event.message.attachments:
                        if hasattr(attachment, 'type') and attachment.type == "image":
                            has_attachments = True
                            image_url = getattr(attachment, 'url', None)
                            break

                if has_attachments and image_url:
                    handled = await bot_service.handle_ai_message_with_image(
                        chat_id, user, text, image_url
                    )
                    if handled:
                        return

                handled = await bot_service.handle_ai_message(chat_id, user, text)
                if handled:
                    return

        if user_id in pending_registrations:
            await _handle_registration(event, user_id, chat_id, text)
            return
        
        if user_id not in users_db:
            await bot_service.start_registration(chat_id, user_id)
            return
        
        user = users_db[user_id]
        
        if user.calendar_state == CalendarState.SELECTING_DATE:
            handled = await bot_service.handle_date_selection(chat_id, user, text)
            if handled:
                return
        
        command_mapping = {
            'расписание': ['расписание'],
            'календарь': ['календарь', 'календарь'],
            'задания': ['задания', 'домашние задания', 'дз'],
            'мой профиль': ['мой профиль', 'профиль', 'мои данные'],
            'предыдущий месяц': ['предыдущий месяц', 'пред месяц'],
            'следующий месяц': ['следующий месяц', 'след месяц'],
            'сегодня': ['сегодня', 'текущий день'],
            'назад': ['назад', 'меню'],
            'меню': ['меню', 'главное меню'],
            'чат': ['чат', 'чат-бот', 'бот', 'ai', 'gpt']
        }
        
        matched_command = None
        for command, synonyms in command_mapping.items():
            if text.lower() in synonyms:
                matched_command = command
                break
        
        if matched_command:
            await command_handler.handle_command(chat_id, user, matched_command)
        else:
            await command_handler.handle_command(chat_id, user, text)
            
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Произошла ошибка. Попробуйте позже."
        )

@dp.message_callback()
async def callback_handler(event: MessageCallback):
    await handle_callback(event, bot_service)

async def _handle_registration(event: MessageCreated, user_id: int, chat_id: int, text: str):
    """Обработка процесса регистрации"""
    logger.info(f"Обработка регистрации для пользователя {user_id}, шаг: {pending_registrations[user_id].get('step')}")
    
    reg_data = pending_registrations[user_id]
    
    if reg_data["step"] == "full_name":
        is_valid, validation_msg = UniversityService.validate_full_name(text)
        if not is_valid:
            await bot.send_message(chat_id=chat_id, text=f"❌ {validation_msg}")
            return
        
        reg_data["full_name"] = text
        reg_data["step"] = "university"
        
        logger.info(f"ФИО сохранено: {text}, переходим к выбору ВУЗа")
        
        await bot_service.send_university_selection(chat_id, user_id)

async def main():
    logger.info("🤖 StudGram Bot запущен и готов к работе!")
    
    from services.studgram_api import StudGramAPIService
    api_service = StudGramAPIService()
    institutions = await api_service.get_institutions()
    if institutions:
        logger.info(f"✅ Подключение к API успешно. Доступно {len(institutions)} учебных заведений")
    else:
        logger.warning("⚠️ Не удалось подключиться к API StudGram")
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")