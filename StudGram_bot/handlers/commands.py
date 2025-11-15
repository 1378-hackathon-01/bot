import logging
from models.user import User, CalendarState
from services.bot_service import BotService

logger = logging.getLogger(__name__)

class CommandHandler:
    """Обработчик команд бота"""
    
    def __init__(self, bot_service: BotService):
        self.bot_service = bot_service
        self.command_handlers = {
            'расписание': self._handle_schedule,
            'календарь': self._handle_calendar,
            'задания': self._handle_assignments,
            'мой профиль': self._handle_profile,
            'предыдущий месяц': self._handle_calendar_prev,
            'следующий месяц': self._handle_calendar_next,
            'сегодня': self._handle_calendar_today,
            'назад': self._handle_back,
            'меню': self._handle_menu
        }
    
    async def handle_command(self, chat_id: int, user: User, command: str):
        """Обрабатывает команду пользователя"""
        command_lower = command.lower()
        handler = self.command_handlers.get(command_lower)
        
        if handler:
            await handler(chat_id, user)
        else:
            await self._handle_unknown_command(chat_id, user)
    
    async def _handle_schedule(self, chat_id: int, user: User):
        await self.bot_service.send_schedule_menu(chat_id, user)
    
    async def _handle_calendar(self, chat_id: int, user: User):
        await self.bot_service.send_calendar(chat_id, user)
    
    async def _handle_assignments(self, chat_id: int, user: User):
        await self.bot_service.send_assignments(chat_id, user)
    
    async def _handle_info(self, chat_id: int, user: User):
        await self.bot_service.send_university_info(chat_id, user)
    
    async def _handle_profile(self, chat_id: int, user: User):
        await self.bot_service.send_profile(chat_id, user)
    
    async def _handle_calendar_prev(self, chat_id: int, user: User):
        await self.bot_service.send_calendar(chat_id, user, "prev_month")
    
    async def _handle_calendar_next(self, chat_id: int, user: User):
        await self.bot_service.send_calendar(chat_id, user, "next_month")
    
    async def _handle_calendar_today(self, chat_id: int, user: User):
        await self.bot_service.send_calendar(chat_id, user, "today")
    
    async def _handle_back(self, chat_id: int, user: User):
        user.calendar_state = CalendarState.VIEWING
        await self.bot_service.send_main_menu(chat_id, user)
    
    async def _handle_menu(self, chat_id: int, user: User):
        await self.bot_service.send_main_menu(chat_id, user)
    
    async def _handle_unknown_command(self, chat_id: int, user: User):
        await self.bot_service.bot.send_message(chat_id=chat_id, text="❌ Неизвестная команда.")
        await self.bot_service.send_main_menu(chat_id, user)