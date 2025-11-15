import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from maxapi import Bot
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types import CallbackButton

from .ai_service import AIService 
from .studgram_api import StudGramAPIService
from .university_service import UniversityService
from .calendar_service import CalendarService
from models.user import User, UserRole, UserStatus, CalendarState
from templates.messages import MessageTemplates
from config import users_db, pending_registrations, active_chats

logger = logging.getLogger(__name__)

class BotService:
    """Основной сервис бота"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.university_service = UniversityService()
        self.api_service = StudGramAPIService()
        self.ai_service = AIService()
        self.templates = MessageTemplates()

    async def _check_access(self, user: User) -> bool:
        """Проверяет, есть ли у пользователя доступ к функциям (подтверждена ли заявка)"""
        if not user.system_id:
            logger.info(f"У пользователя {user.user_id} нет system_id")
            return False
        
        if user.application_approved and user.status == UserStatus.APPROVED:
            logger.info(f"Заявка пользователя {user.user_id} уже подтверждена")
            return True

        try:
            logger.info(f"Проверяем статус заявки пользователя {user.user_id} через API")
            is_approved = await self.api_service.get_student_application_status(user.system_id)
            logger.info(f"Статус заявки от API: {is_approved}")
            
            if is_approved is not None:
                user.application_approved = is_approved
                if is_approved:
                    user.status = UserStatus.APPROVED
                    logger.info(f"✅ Заявка пользователя {user.user_id} подтверждена администратором")
                    return True
                else:
                    logger.info(f"⏳ Заявка пользователя {user.user_id} на рассмотрении")
                    return False
        except Exception as e:
            logger.error(f"Ошибка проверки статуса заявки: {e}")
        
        return False

    async def _send_pending_application_message(self, chat_id: int):
        """Отправляет сообщение о неподтвержденной заявке"""
        message = """❌ Доступ ограничен

Эта функция доступна только после подтверждения вашей заявки администрацией учебного заведения.

Используйте команду «Мой статус» для проверки текущего статуса заявки."""
        
        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="📊 Проверить статус", payload="menu_status"))
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=message,
            attachments=[builder.as_markup()]
        )

    async def _handle_student_not_found(self, chat_id: int, user: User):
        """Обрабатывает случай, когда студент не найден в системе"""
        logger.error(f"❌ Студент {user.user_id} не найден в системе StudGram. Запускаем перерегистрацию.")
        
        error_text = """❌ Ошибка: ваш профиль не найден в системе StudGram

Возможные причины:
• Ваши данные были удалены из системы
• Произошла ошибка при регистрации
• Изменилась структура учебного заведения

Для восстановления доступа необходимо пройти регистрацию заново.

Не волнуйтесь! Это займет всего несколько минут."""
        
        if user.user_id in users_db:
            del users_db[user.user_id]
            logger.info(f"✅ Пользователь {user.user_id} удален из users_db")
        
        if user.user_id in active_chats.values():
            for chat_id_key, user_id in list(active_chats.items()):
                if user_id == user.user_id:
                    del active_chats[chat_id_key]
                    logger.info(f"✅ Пользователь {user.user_id} удален из active_chats")
                    break
        
        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="🔄 Начать регистрацию заново", payload="restart_registration"))
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=error_text,
            attachments=[builder.as_markup()]
        )

    async def _force_restart_registration(self, chat_id: int, user_id: int):
        """Принудительно запускает перерегистрацию"""
        logger.info(f"🔄 Принудительная перерегистрация для пользователя {user_id}")
        
        if user_id in users_db:
            del users_db[user_id]
        
        if user_id in pending_registrations:
            del pending_registrations[user_id]
        
        await self.start_registration(chat_id, user_id)

    async def check_application_status(self, user: User) -> bool:
        """Проверяет статус заявки пользователя и обновляет его права доступа"""
        if not user.system_id:
            return False
        
        try:
            is_approved = await self.api_service.get_student_application_status(user.system_id)
            
            if is_approved is not None:
                user.application_approved = is_approved
                if is_approved:
                    user.status = UserStatus.APPROVED
                    logger.info(f"✅ Заявка пользователя {user.user_id} подтверждена администратором")
                else:
                    user.status = UserStatus.PENDING
                    logger.info(f"⏳ Заявка пользователя {user.user_id} на рассмотрении")
                
                return True
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки статуса заявки: {e}")
            return False

    async def send_application_status(self, chat_id: int, user: User):
        """Отправляет текущий статус заявки пользователя"""
        
        status_updated = await self.check_application_status(user)
        
        if user.application_approved:
            status_text = """✅ Ваша заявка подтверждена!

Теперь у вас есть полный доступ ко всем функциям StudGram:
• 📚 Просмотр расписания
• 📝 Отслеживание заданий
• 🤖 Общение с AI-ассистентом
• 🏫 Информация о ВУЗе

Для начала работы выберите нужный раздел в главном меню."""
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🚀 Перейти в меню", payload="menu_back"))
            
        else:
            status_text = """⏳ Ваша заявка на рассмотрении

Администрация учебного заведения проверяет ваши данные. 
Обычно это занимает от 1 до 3 рабочих дней.

Что сейчас доступно:
• Просмотр профиля и статуса заявки
• Основная информация о платформе

Что будет доступно после подтверждения:
• Полное расписание занятий
• Все учебные задания
• AI-ассистент для помощи в учебе
• Информация о ВУЗе и факультете

Пожалуйста, проверяйте статус позже."""
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔄 Обновить статус", payload="menu_status"))
            builder.row(CallbackButton(text="👤 Мой профиль", payload="menu_profile"))
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=status_text,
            attachments=[builder.as_markup()]
        )
    
    async def send_main_menu(self, chat_id: int, user: User):
        """Отправляет главное меню с кнопками в зависимости от статуса заявки"""
        
        if not user.application_approved and user.system_id:
            await self.check_application_status(user)
        
        menu_text = self.templates.get_main_menu(user)
        builder = InlineKeyboardBuilder()
        
        if user.application_approved and user.status == UserStatus.APPROVED:
            buttons = [
                CallbackButton(text="📚 Расписание", payload="menu_schedule"),
                CallbackButton(text="📝 Дисциплины", payload="menu_assignments"),
                CallbackButton(text="🤖 Чат-бот", payload="menu_chatbot"),
                CallbackButton(text="👤 Мой профиль", payload="menu_profile")
            ]
            
            for i in range(0, len(buttons), 2):
                row_buttons = buttons[i:i+2]
                builder.row(*row_buttons)
            
        else:
            builder.row(
                CallbackButton(text="📊 Мой статус", payload="menu_status"),
                CallbackButton(text="👤 Мой профиль", payload="menu_profile")
            )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            attachments=[builder.as_markup()]
        )
    
    async def start_chatbot(self, chat_id: int, user: User):
        """Запускает режим чат-бота"""
        if not await self._check_access(user):
            await self._send_pending_application_message(chat_id)
            return
        
        user.in_chat_mode = True
        
        welcome_text = """🤖 Чат-бот StudGram AI

Я здесь, чтобы помочь вам с учебными вопросами! Можете спросить меня о:
• Расписании занятий
• Домашних заданиях  
• Учебных материалах
• Подготовке к экзаменам
• И любых других учебных вопросах

Просто напишите ваш вопрос, и я постараюсь помочь!

Для выхода из режима чата отправьте /menu"""

        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="🔙 Выйти из чата", payload="menu_back"))
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            attachments=[builder.as_markup()]
        )
    
    async def handle_ai_message(self, chat_id: int, user: User, message: str) -> bool:
        """Обрабатывает сообщение для AI"""
        if not user.in_chat_mode:
            return False
        
        if not await self._check_access(user):
            user.in_chat_mode = False
            await self._send_pending_application_message(chat_id)
            return True
        
        if not message or not message.strip():
            await self.bot.send_message(
                chat_id=chat_id,
                text="🤖 AI-ассистент:\n\nВы отправили пустое сообщение. Пожалуйста, напишите ваш вопрос или запрос."
            )
            return True
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text="⏳ AI-ассистент обрабатывает запрос..."
            )
            
            response = await self.ai_service.send_text(message)
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔙 Выйти из чата", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"🤖 AI-ассистент:\n\n{response}",
                attachments=[builder.as_markup()]
            )
            return True
            
        except Exception as e:
            logger.error(f"Ошибка в AI-чате: {e}")
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔙 Выйти из чата", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при обращении к AI. Попробуйте позже.",
                attachments=[builder.as_markup()]
            )
            return True

    async def handle_ai_message_with_image(self, chat_id: int, user: User, message: str, image_url: str) -> bool:
        """Обрабатывает сообщение для AI с изображением"""
        if not user.in_chat_mode:
            return False
        
        if not await self._check_access(user):
            user.in_chat_mode = False
            await self._send_pending_application_message(chat_id)
            return True
        
        if (not message or not message.strip()) and not image_url:
            await self.bot.send_message(
                chat_id=chat_id,
                text="🤖 AI-ассистент:\n\nПожалуйста, отправьте текст или изображение для анализа."
            )
            return True
        
        try:
            if image_url:
                response = await self.ai_service.send_text_with_image(
                    text=message or "Что изображено на картинке?",
                    image_url=image_url
                )
            else:
                response = await self.ai_service.send_text(message)
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔙 Выйти из чата", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"🤖 AI-ассистент:\n\n{response}",
                attachments=[builder.as_markup()]
            )
            return True
            
        except Exception as e:
            logger.error(f"Ошибка в AI-чате с изображением: {e}")
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔙 Выйти из чата", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при обращении к AI. Попробуйте позже.",
                attachments=[builder.as_markup()]
            )
            return True
   
    async def exit_chat_mode(self, chat_id: int, user: User):
        """Выход из режима чата"""
        user.in_chat_mode = False
        
        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="🤖 Вернуться в чат", payload="menu_chatbot"))
        
        await self.bot.send_message(
            chat_id=chat_id,
            text="✅ Вы вышли из режима чат-бота. Чтобы продолжить общение, нажмите кнопку ниже или выберите 'Чат-бот' в меню.",
            attachments=[builder.as_markup()]
        )
        await self.send_main_menu(chat_id, user)
    
    async def send_schedule_menu(self, chat_id: int, user: User):
        """Отправляет меню выбора расписания"""
        if not await self._check_access(user):
            await self._send_pending_application_message(chat_id)
            return
        
        menu_text = self.templates.get_schedule_menu()
        builder = InlineKeyboardBuilder()
        
        builder.row(
            CallbackButton(text="📅 Сегодня", payload="schedule_today"),
            CallbackButton(text="📅 Завтра", payload="schedule_tomorrow")
        )
        builder.row(
            CallbackButton(text="🗓️ Календарь", payload="menu_calendar"),
            CallbackButton(text="🔙 Назад", payload="menu_back")
        )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            attachments=[builder.as_markup()]
        )
    
    async def send_calendar(self, chat_id: int, user: User, navigation: str = None):
        """Отправляет календарь для выбора даты"""
        if not await self._check_access(user):
            await self._send_pending_application_message(chat_id)
            return
        
        current_month = await self._handle_calendar_navigation(user, navigation)
        
        try:
            calendar_days = CalendarService.get_month_calendar(
                current_month.year, current_month.month
            )
            
            calendar_text = self.templates.get_calendar(calendar_days, current_month)
            
            builder = InlineKeyboardBuilder()
            builder.row(
                CallbackButton(text="⬅️ Предыдущий месяц", payload="calendar_prev"),
                CallbackButton(text="➡️ Следующий месяц", payload="calendar_next")
            )
            builder.row(CallbackButton(text="📅 Сегодня", payload="calendar_today"))
            builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=calendar_text,
                attachments=[builder.as_markup()]
            )
            
            user.calendar_state = CalendarState.SELECTING_DATE
            
        except Exception as e:
            logger.error(f"Ошибка отображения календаря: {e}")
            await self.bot.send_message(
                chat_id=chat_id, 
                text="Календарь временно недоступен. Повторите попытку позже."
            )
    
    async def handle_date_selection(self, chat_id: int, user: User, date_input: str) -> bool:
        """Обрабатывает выбор даты пользователем"""
        selected_date = CalendarService.parse_date(date_input)
        
        if not selected_date:
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например, 15.12.2024)"
            )
            return False
        
        current_month = user.selected_month
        if selected_date.month != current_month.month or selected_date.year != current_month.year:
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Выбранная дата не принадлежит текущему месяцу. Используйте навигацию для перехода к нужному месяцу."
            )
            return False
        
        if not CalendarService.is_study_day(selected_date):
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"❌ {selected_date.strftime('%d.%m.%Y')} - выходной день. Расписания нет."
            )
            return True
        
        await self._show_schedule_for_date(chat_id, user, selected_date)
        return True
    
    async def show_schedule_for_today(self, chat_id: int, user: User):
        """Показывает расписание на сегодня"""
        if not await self._check_access(user):
            await self._send_pending_application_message(chat_id)
            return
        
        today = datetime.now()
        await self._show_schedule_for_date(chat_id, user, today)
    
    async def show_schedule_for_tomorrow(self, chat_id: int, user: User):
        """Показывает расписание на завтра"""
        if not await self._check_access(user):
            await self._send_pending_application_message(chat_id)
            return
        
        tomorrow = datetime.now() + timedelta(days=1)
        await self._show_schedule_for_date(chat_id, user, tomorrow)
    
    async def _show_schedule_for_date(self, chat_id: int, user: User, date: datetime):
        """Показывает расписание на указанную дату"""
        if not await self._check_access(user):
            await self._send_pending_application_message(chat_id)
            return
        
        try:
            schedule = await self.api_service.get_schedule(user.group, date)
            schedule_text = self.templates.get_schedule(schedule, date)
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🗓️ Календарь", payload="menu_calendar"))
            builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=schedule_text,
                attachments=[builder.as_markup()]
            )
            
            user.calendar_state = CalendarState.VIEWING
            
        except Exception as e:
            logger.error(f"Ошибка получения расписания: {e}")
            await self.bot.send_message(
                chat_id=chat_id, 
                text="Расписание временно недоступно. Повторите попытку позже."
            )
    
    async def _handle_calendar_navigation(self, user: User, navigation: str) -> datetime:
        """Обрабатывает навигацию по календарю"""
        current_month = user.selected_month
        
        if navigation == "prev_month":
            if current_month.month == 1:
                current_month = current_month.replace(year=current_month.year-1, month=12)
            else:
                current_month = current_month.replace(month=current_month.month-1)
        
        elif navigation == "next_month":
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year+1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month+1)
        
        elif navigation == "today":
            current_month = datetime.now().replace(day=1)
        
        user.selected_month = current_month
        return current_month
    
    async def send_assignments(self, chat_id: int, user: User):
        """Отправляет список дисциплин с содержимым из API StudGram"""
        if not await self._check_access(user):
            await self._send_pending_application_message(chat_id)
            return
        
        try:
            subjects = await self.api_service.get_student_subjects(user.system_id)
            
            if not subjects:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="📚 На данный момент у вас нет активных дисциплин."
                )
                return
            
            assignments_text = await self._format_subjects_with_content(subjects, user)
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔄 Обновить", payload="menu_assignments"))
            builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=assignments_text,
                attachments=[builder.as_markup()]
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения дисциплин: {e}")
            await self.bot.send_message(
                chat_id=chat_id, 
                text="❌ Не удалось загрузить список дисциплин. Попробуйте позже."
            )
            
    async def _format_subjects_with_content(self, subjects: List[dict], user: User) -> str:
        """Форматирует список дисциплин с содержимым"""
        if not subjects:
            return "📚 На данный момент у вас нет активных дисциплин."
        
        subjects_text = f"📚 **Ваши дисциплины и задания** ({len(subjects)}):\n\n"
        
        for i, subject in enumerate(subjects, 1):
            subjects_text += f"**{i}. {subject.get('title', 'Без названия')}**\n"
            
            if subject.get('abbreviation'):
                subjects_text += f"*Сокр.: {subject['abbreviation']}*\n"
            
            if subject.get('id'):
                subject_content = await self.api_service.get_subject_content(user.system_id, subject['id'])
                if subject_content and subject_content.get('content'):
                    content = subject_content['content']
                    if len(content) > 300:
                        content = content[:300] + "..."
                    subjects_text += f"*Содержание:* {content}\n"
                else:
                    subjects_text += f"*Содержание:* Информация отсутствует\n"
            
            subjects_text += "─" * 20 + "\n\n"
        
        subjects_text += "💡 *Для получения дополнительной информации используйте веб-интерфейс StudGram*\n\n"
        subjects_text += "🔄 *Обновить* - обновить список дисциплин\n"
        subjects_text += "🔙 *Назад* - вернуться в главное меню"
        
        return subjects_text

    async def send_subject_details(self, chat_id: int, user: User, subject_id: str):
        """Отправляет детальную информацию о дисциплине"""
        if not await self._check_access(user):
            await self._send_pending_application_message(chat_id)
            return
        
        try:
            subject_content = await self.api_service.get_subject_content(user.system_id, subject_id)
            
            if not subject_content:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Не удалось загрузить информацию о дисциплине."
                )
                return

            subject_text = self.templates.get_subject_details(subject_content)
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="📚 К списку дисциплин", payload="menu_assignments"))
            builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=subject_text,
                attachments=[builder.as_markup()]
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о дисциплине: {e}")
            await self.bot.send_message(
                chat_id=chat_id, 
                text="❌ Не удалось загрузить информацию о дисциплине. Попробуйте позже."
            )
    
    async def send_profile(self, chat_id: int, user: User):
        """Отправляет профиль пользователя с данными из API StudGram"""
        try:
            if user.system_id and not user.application_approved:
                await self.check_application_status(user)
            
            system_data = None
            faculty_info = None
            institution_info = None
            group_info = None
            
            student_not_found = False
            
            if user.system_id:
                logger.info(f"🔍 Запрашиваем данные из API для system_id: {user.system_id}")
                try:
                    system_data = await self.api_service.get_student_data(user.system_id)
                    if system_data is None:
                        student_not_found = True
                        logger.error(f"❌ Студент {user.system_id} не найден в системе")
                except Exception as e:
                    logger.error(f"Ошибка получения данных студента: {e}")
                    student_not_found = True
                
                if not student_not_found:
                    try:
                        faculty_info = await self.api_service.get_student_faculty(user.system_id)
                        if faculty_info is None:
                            logger.warning(f"⚠️ Факультет студента {user.system_id} не найден")
                    except Exception as e:
                        logger.error(f"Ошибка получения факультета студента: {e}")
                    
                    try:
                        institution_info = await self.get_student_institution_info(user.system_id)
                        if institution_info is None:
                            logger.warning(f"⚠️ Учреждение студента {user.system_id} не найдено")
                    except Exception as e:
                        logger.error(f"Ошибка получения учреждения студента: {e}")
                    
                    try:
                        group_info = await self.api_service.get_student_group(user.system_id)
                        if group_info is None:
                            logger.warning(f"⚠️ Группа студента {user.system_id} не найдена")
                    except Exception as e:
                        logger.error(f"Ошибка получения группы студента: {e}")
            
            if student_not_found:
                await self._handle_student_not_found(chat_id, user)
                return
            
            profile_text = "👤 Ваш профиль (данные из системы StudGram)\n\n"
            
            if system_data and system_data.get('fullName'):
                profile_text += f"📝 ФИО: {system_data['fullName']}\n"
            else:
                profile_text += f"📝 ФИО: {user.full_name}\n"
            
            if institution_info:
                profile_text += f"🎓 Вуз: {institution_info.get('title', 'Не указан')}\n"
                if institution_info.get('abbreviation'):
                    profile_text += f"   Аббревиатура: {institution_info['abbreviation']}\n"
            else:
                profile_text += f"🎓 Вуз:{user.university}\n"
            
            if faculty_info:
                profile_text += f"📚 Факультет: {faculty_info.get('title', 'Не указан')}\n"
                if faculty_info.get('abbreviation'):
                    profile_text += f"   Аббревиатура: {faculty_info['abbreviation']}\n"
            elif hasattr(user, 'faculty') and user.faculty:
                profile_text += f"📚 Факультет: {user.faculty} (локальные данные)\n"
            else:
                profile_text += f"📚 Факультет: Не указан\n"
            
            if group_info:
                profile_text += f"👥 Группа: {group_info.get('title', 'Не указана')}\n"
                if group_info.get('abbreviation'):
                    profile_text += f"   Аббревиатура: {group_info['abbreviation']}\n"
            else:
                profile_text += f"👥 Группа: {user.group} (локальные данные)\n"
            
            role_text = "Студент" if user.role == UserRole.STUDENT else "Модератор"
            
            if user.application_approved:
                status_text = "✅ подтвержден"
            else:
                status_text = "⏳ ожидает подтверждения"
            
            profile_text += f"🎯 Роль: {role_text}\n"
            profile_text += f"📊 Статус: {status_text}\n"
            
            if user.system_id:
                profile_text += f"🔗 ID в системе: {user.system_id}\n"
            
            if system_data:
                if system_data.get('maxId'):
                    profile_text += f"🆔 MAX ID: {system_data['maxId']}\n"
                
                if system_data.get('createdAt'):
                    profile_text += f"📅 Зарегистрирован: {system_data['createdAt']}\n"
            
            application_status = "✅ подтверждена администратором" if user.application_approved else "⏳ на рассмотрении"
            profile_text += f"📋 Статус заявки: {application_status}\n"

            sync_status = await self.check_student_sync_status(user)
            profile_text += f"\n\n{sync_status}"

            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔄 Обновить данные", payload="profile_refresh"))
            builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))

            await self.bot.send_message(
                chat_id=chat_id, 
                text=profile_text,
                attachments=[builder.as_markup()]
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении профиля из API: {e}")
            await self.send_profile_fallback(chat_id, user)
            
    async def send_profile_fallback(self, chat_id: int, user: User):
        """Отправляет профиль с локальными данными (fallback)"""
        try:
            if user.system_id and not user.application_approved:
                await self.check_application_status(user)
            
            if user.system_id:
                try:
                    student_exists = await self.api_service.check_student_exists(user.system_id)
                    if not student_exists:
                        await self._handle_student_not_found(chat_id, user)
                        return
                except Exception as e:
                    logger.error(f"Ошибка проверки существования студента: {e}")
            
            role_text = "Студент" if user.role == UserRole.STUDENT else "Модератор"
            
            if user.application_approved:
                status_text = "✅ подтвержден"
            else:
                status_text = "⏳ ожидает подтверждения"
            
            profile_text = f"""👤 Ваш профиль (локальные данные)

📝 ФИО: {user.full_name}
🎓 Вуз: {user.university}"""
            
            if hasattr(user, 'faculty') and user.faculty:
                profile_text += f"\n📚 Факультет: {user.faculty}"
            
            profile_text += f"""
👥 Группа: {user.group}
🎯 Роль: {role_text}
📊 Статус: {status_text}"""

            if user.system_id:
                profile_text += f"\n🔗 ID в системе: {user.system_id}"

            application_status = "✅ подтверждена администратором" if user.application_approved else "⏳ на рассмотрении"
            profile_text += f"\n📋 Статус заявки: {application_status}"

            if user.status == UserStatus.PENDING and not user.application_approved:
                moderator_contact = moderators_db.get(user.group, "@group_moderator")
                profile_text += f"\n\n⏳ Ваш профиль отправлен на подтверждение модератору."
                profile_text += f"\n📞 Контакты модератора: {moderator_contact}"
                profile_text += f"\n📨 Вы получите уведомление после проверки."

            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔄 Обновить данные", payload="profile_refresh"))
            builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))

            await self.bot.send_message(
                chat_id=chat_id, 
                text=profile_text,
                attachments=[builder.as_markup()]
            )
            
        except Exception as e:
            logger.error(f"Ошибка при отправке профиля (fallback): {e}")
            await self._handle_student_not_found(chat_id, user)

    async def get_student_institution_info(self, student_id: str) -> Optional[dict]:
        """Получить информацию об учебном заведении студента из системы StudGram"""
        try:
            if not student_id:
                return None
            
            result = await self.api_service.client.request("GET", f"students/{student_id}/institution")
            return result
        except Exception as e:
            logger.error(f"Ошибка получения информации об учебном заведении: {e}")
            return None

    async def check_student_sync_status(self, user: User) -> str:
        """Проверить статус синхронизации студента с системой StudGram"""
        try:
            if not user.system_id:
                return "❌ Не синхронизирован с системой StudGram"
            
            student_exists = await self.api_service.check_student_exists(user.system_id)
            if not student_exists:
                return "❌ Студент не найден в системе StudGram\n\n⚠️ Требуется перерегистрация"
            
            faculty_info = None
            institution_info = None
            group_info = None
            
            try:
                faculty_info = await self.api_service.get_student_faculty(user.system_id)
            except Exception as e:
                logger.warning(f"Ошибка получения факультета: {e}")
            
            try:
                institution_info = await self.get_student_institution_info(user.system_id)
            except Exception as e:
                logger.warning(f"Ошибка получения учреждения: {e}")
            
            try:
                group_info = await self.api_service.get_student_group(user.system_id)
            except Exception as e:
                logger.warning(f"Ошибка получения группы: {e}")
            
            sync_status = "✅ Синхронизирован с системой StudGram"
            
            if institution_info:
                sync_status += f"\n🎓 Вуз в системе: {institution_info.get('title', 'Не указан')}"
                if institution_info.get('abbreviation'):
                    sync_status += f" ({institution_info['abbreviation']})"
            else:
                sync_status += "\n🎓 Вуз: Не прикреплен в системе"
            
            if faculty_info:
                sync_status += f"\n📚 Факультет в системе: {faculty_info.get('title', 'Не указан')}"
                if faculty_info.get('abbreviation'):
                    sync_status += f" ({faculty_info['abbreviation']})"
            else:
                sync_status += "\n📚 Факультет: Не прикреплен в системе"
            
            if group_info:
                sync_status += f"\n👥 Группа в системе: {group_info.get('title', 'Не указана')}"
                if group_info.get('abbreviation'):
                    sync_status += f" ({group_info['abbreviation']})"
            else:
                sync_status += "\n👥 Группа: Не прикреплена в системе"
            
            return sync_status
            
        except Exception as e:
            logger.error(f"Ошибка проверки синхронизации: {e}")
            return "⚠️ Ошибка проверки синхронизации\n\n❌ Требуется перерегистрация"
    
    async def start_registration(self, chat_id: int, user_id: int):
        """Начинает процесс регистрации"""
        pending_registrations[user_id] = {
            "step": "full_name",
            "chat_id": chat_id
        }
        active_chats[chat_id] = user_id
        
        await self.bot.send_message(
            chat_id=chat_id,
            text="Добро пожаловать в StudGram! 📚\n\nДля регистрации укажите ваши данные.\n\nВведите ваше ФИО:"
        )

    async def send_university_selection(self, chat_id: int, user_id: int):
        """Отправляет кнопки для выбора ВУЗа с сокращениями"""
        try:
            universities = await self.university_service.get_university_names()
            if not universities:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Не удалось загрузить список учебных заведений. Попробуйте позже."
                )
                return
            
            institutions = await self.university_service.get_universities()
            logger.info(f"Доступные ВУЗы: {institutions}")
            
            builder = InlineKeyboardBuilder()
            
            for i in range(0, len(institutions), 2):
                row_universities = institutions[i:i+2]
                buttons = []
                for uni in row_universities:
                    display_name = uni.get('abbreviation') or uni.get('title', '')[:15] + "..."
                    safe_uni = uni.get('title', '').replace(' ', '_')
                    payload = f"university_{user_id}_{safe_uni}"
                    buttons.append(CallbackButton(text=display_name, payload=payload))
                builder.row(*buttons)
            
            await self.bot.send_message(
                chat_id=chat_id,
                text="🎓 Выберите ваш вуз (показаны сокращения):",
                attachments=[builder.as_markup()]
            )
            logger.info("Кнопки ВУЗов с сокращениями отправлены успешно")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке кнопок ВУЗов: {e}")
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при загрузке списка ВУЗов"
            )
            
    async def send_faculty_selection(self, chat_id: int, user_id: int, university: str):
        """Отправляет кнопки для выбора факультета с сокращениями"""
        try:
            institution = await self.university_service.get_university_by_name(university)
            if not institution:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Не удалось найти информацию о выбранном вузе"
                )
                return
            
            faculties = await self.university_service.get_faculties(institution["id"])
            if not faculties:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Не удалось загрузить список факультетов для выбранного вуза"
                )
                return
            
            logger.info(f"Доступные факультеты для {university}: {faculties}")
            
            builder = InlineKeyboardBuilder()
            
            for i in range(0, len(faculties), 2):
                row_faculties = faculties[i:i+2]
                buttons = []
                for faculty in row_faculties:
                    display_name = faculty.get('abbreviation') or faculty.get('title', '')[:15] + "..."
                    safe_faculty = faculty.get('title', '').replace(' ', '_')
                    payload = f"faculty_{user_id}_{safe_faculty}"
                    buttons.append(CallbackButton(text=display_name, payload=payload))
                builder.row(*buttons)
            
            # Используем сокращение университета для отображения
            uni_display = institution.get('abbreviation') or university
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"🎓 Вуз: {uni_display}\n📚 Выберите ваш факультет (показаны сокращения):",
                attachments=[builder.as_markup()]
            )
            logger.info("Кнопки факультетов с сокращениями отправлены успешно")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке кнопок факультетов: {e}")
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при загрузке списка факультетов"
            )

    async def send_group_selection(self, chat_id: int, user_id: int, university: str, faculty: str = None):
        """Отправляет кнопки для выбора группы через API"""
        try:
            if user_id not in pending_registrations:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Ошибка: данные регистрации не найдены"
                )
                return
            
            reg_data = pending_registrations[user_id]
            institution_id = reg_data.get("institution_id")
            faculty_id = reg_data.get("faculty_id")
            
            if not institution_id or not faculty_id:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Ошибка: не найдены ID института или факультета"
                )
                return
            
            groups = await self.university_service.get_group_names(institution_id, faculty_id)
            
            if not groups:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Не удалось загрузить список групп для выбранного факультета"
                )
                return
            
            builder = InlineKeyboardBuilder()
            
            for i in range(0, len(groups), 2):
                row_groups = groups[i:i+2]
                buttons = []
                for group in row_groups:
                    safe_group = group.replace(' ', '_')
                    payload = f"group_{user_id}_{safe_group}"
                    buttons.append(CallbackButton(text=group, payload=payload))
                builder.row(*buttons)
            
            faculty_text = f" (факультет: {faculty})" if faculty else ""
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"🎓 Вуз: {university}{faculty_text}\n👥 Выберите вашу группу:",
                attachments=[builder.as_markup()]
            )
            logger.info("Кнопки групп отправлены успешно")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке кнопок групп: {e}")
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при загрузке списка групп"
            )

    async def send_confirmation(self, chat_id: int, user_id: int, reg_data: Dict):
        """Отправляет подтверждение введенных данных"""
        from templates.messages import MessageTemplates
        
        confirmation_text = MessageTemplates.get_registration_confirmation(reg_data)
        
        builder = InlineKeyboardBuilder()
        builder.row(
            CallbackButton(text="✅ Да, все верно", payload=f"confirm_yes_{user_id}"),
            CallbackButton(text="❌ Нет, исправить", payload=f"confirm_no_{user_id}")
        )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=confirmation_text,
            attachments=[builder.as_markup()]
        )

    async def handle_callback(self, callback_data: str, chat_id: int) -> bool:
        """Обрабатывает callback от кнопок"""
        logger.info(f"Обработка callback в чате {chat_id}: {callback_data}")
        
        if (callback_data.startswith("menu_") or 
            callback_data.startswith("schedule_") or 
            callback_data in ["calendar_prev", "calendar_next", "calendar_today", "profile_refresh", "restart_registration"]):
            return await self.handle_menu_callback(callback_data, chat_id)
        
        user_id = None
        
        if chat_id in active_chats:
            user_id = active_chats[chat_id]
            logger.info(f"Найден user_id из active_chats: {user_id}")
        
        if not user_id:
            for uid, reg_data in pending_registrations.items():
                if reg_data.get("chat_id") == chat_id:
                    user_id = uid
                    active_chats[chat_id] = user_id
                    logger.info(f"Найден user_id из pending_registrations: {user_id}")
                    break
        
        if not user_id:
            logger.warning(f"User_id не найден для callback: {callback_data}, пробуем как меню-колбэк")
            return await self.handle_menu_callback(callback_data, chat_id)

        if callback_data.startswith("university_"):
            parts = callback_data.split("_", 2)
            if len(parts) >= 3:
                university = parts[2].replace('_', ' ')
                return await self.handle_university_selection(user_id, chat_id, university)
        
        elif callback_data.startswith("faculty_"):
            parts = callback_data.split("_", 2)
            if len(parts) >= 3:
                faculty = parts[2].replace('_', ' ')
                return await self.handle_faculty_selection(user_id, chat_id, faculty)
        
        elif callback_data.startswith("group_"):
            parts = callback_data.split("_", 2)
            if len(parts) >= 3:
                group = parts[2].replace('_', ' ')
                return await self.handle_group_selection(user_id, chat_id, group)
        
        elif callback_data.startswith("confirm_"):
            parts = callback_data.split("_")
            if len(parts) >= 3:
                confirmation = parts[1]  # yes или no
                return await self.handle_confirmation(user_id, chat_id, confirmation)
        
        logger.error(f"Неизвестный callback: {callback_data}")
        return False
    
    async def handle_menu_callback(self, callback_data: str, chat_id: int) -> bool:
        """Обрабатывает callback от меню-кнопок"""
        logger.info(f"Обработка меню-колбэка: {callback_data} для чата {chat_id}")
        
        user_id = None
        if chat_id in active_chats:
            user_id = active_chats[chat_id]
            logger.info(f"Найден user_id в active_chats: {user_id}")
        else:
            for uid, reg_data in pending_registrations.items():
                if reg_data.get("chat_id") == chat_id:
                    user_id = uid
                    active_chats[chat_id] = user_id
                    logger.info(f"Найден user_id в pending_registrations: {user_id}")
                    break
            
            if not user_id and users_db:
                for uid, user_data in users_db.items():
                    user_id = uid
                    active_chats[chat_id] = user_id
                    logger.info(f"Найден user_id в users_db: {user_id}")
                    break
    
        if not user_id:
            logger.error(f"Не удалось найти user_id для чата {chat_id}")
            await self.bot.send_message(chat_id=chat_id, text="❌ Ошибка: не найден пользователь. Попробуйте отправить сообщение 'меню'")
            return False

        if user_id not in users_db and callback_data != "restart_registration":
            logger.error(f"Пользователь {user_id} не найден в users_db. Доступные пользователи: {list(users_db.keys())}")
            await self.bot.send_message(chat_id=chat_id, text="❌ Ошибка: профиль не найден. Пройдите регистрацию заново.")
            return False
        
        user = None
        if user_id in users_db:
            user = users_db[user_id]
            logger.info(f"Найден пользователь: {user.full_name}, статус: {user.status}, application_approved: {user.application_approved}")
        
        menu_actions = {
            "menu_schedule": {
                "handler": lambda: self.send_schedule_menu(chat_id, user),
                "required_access": True
            },
            "menu_assignments": {
                "handler": lambda: self.send_assignments(chat_id, user),
                "required_access": True
            },
            "menu_chatbot": {
                "handler": lambda: self.start_chatbot(chat_id, user),
                "required_access": True
            },
            "menu_profile": {
                "handler": lambda: self.send_profile(chat_id, user),
                "required_access": False
            },
            "menu_status": {
                "handler": lambda: self.send_application_status(chat_id, user),
                "required_access": False
            },
            "subject_": {
                "handler": lambda: self.send_subject_details(chat_id, user, callback_data.replace("subject_", "")),
                "required_access": True
            },
            "profile_refresh": {
                "handler": lambda: self.send_profile(chat_id, user),
                "required_access": False
            },
            "menu_info": {
                "handler": lambda: self.send_university_info(chat_id, user),
                "required_access": True
            },
            "menu_back": {
                "handler": lambda: self.exit_chat_mode(chat_id, user) if user.in_chat_mode else self.send_main_menu(chat_id, user),
                "required_access": False
            },
            "menu_calendar": {
                "handler": lambda: self.send_calendar(chat_id, user),
                "required_access": True
            },
            "calendar_prev": {
                "handler": lambda: self.send_calendar(chat_id, user, "prev_month"),
                "required_access": True
            },
            "calendar_next": {
                "handler": lambda: self.send_calendar(chat_id, user, "next_month"),
                "required_access": True
            },
            "calendar_today": {
                "handler": lambda: self.send_calendar(chat_id, user, "today"),
                "required_access": True
            },
            "schedule_today": {
                "handler": lambda: self.show_schedule_for_today(chat_id, user),
                "required_access": True
            },
            "schedule_tomorrow": {
                "handler": lambda: self.show_schedule_for_tomorrow(chat_id, user),
                "required_access": True
            },
            "restart_registration": {
                "handler": lambda: self._force_restart_registration(chat_id, user_id),
                "required_access": False
            }
        }
        
        action_config = menu_actions.get(callback_data)
        if not action_config:
            logger.error(f"Неизвестный меню-колбэк: {callback_data}")
            return False
        
        if action_config.get("required_access") and callback_data != "restart_registration":
            logger.info(f"Проверяем доступ для действия: {callback_data}")
            has_access = await self._check_access(user)
            logger.info(f"Результат проверки доступа: {has_access}")
            if not has_access:
                await self._send_pending_application_message(chat_id)
                return True
        
        
        try:
            logger.info(f"Выполнение действия: {callback_data}")
            await action_config["handler"]()
            logger.info(f"Действие {callback_data} выполнено успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка при выполнении действия {callback_data}: {e}")
            import traceback
            logger.error(f"Трассировка ошибки: {traceback.format_exc()}")
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при выполнении действия"
            )
            return False
    
    async def handle_university_selection(self, user_id: int, chat_id: int, university: str) -> bool:
        """Обрабатывает выбор университета"""
        if user_id not in pending_registrations:
            logger.error(f"Пользователь {user_id} не найден в pending_registrations")
            return False

        institution = await self.university_service.get_university_by_name(university)
        if not institution:
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Не удалось найти выбранный университет"
            )
            return False
        
        reg_data = pending_registrations[user_id]
        reg_data["university"] = university
        reg_data["institution_id"] = institution["id"]
        reg_data["step"] = "faculty"
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Вы выбрали: {university}"
        )
        
        await self.send_faculty_selection(chat_id, user_id, university)
        return True
    
    async def handle_faculty_selection(self, user_id: int, chat_id: int, faculty: str) -> bool:
        """Обрабатывает выбор факультета"""
        if user_id not in pending_registrations:
            logger.error(f"Пользователь {user_id} не найден в pending_registrations")
            return False
            
        reg_data = pending_registrations[user_id]
        institution_id = reg_data.get("institution_id")
        
        if not institution_id:
            logger.error(f"Не найден institution_id для пользователя {user_id}")
            return False

        faculty_data = await self.university_service.get_faculty_by_name(institution_id, faculty)
        if not faculty_data:
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Не удалось найти выбранный факультет"
            )
            return False
        
        reg_data["faculty"] = faculty
        reg_data["faculty_id"] = faculty_data["id"]
        reg_data["step"] = "group"
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Вы выбрали: {faculty}"
        )
        
        await self.send_group_selection(chat_id, user_id, reg_data["university"], faculty)
        return True

    async def handle_group_selection(self, user_id: int, chat_id: int, group: str) -> bool:
        """Обрабатывает выбор группы"""
        if user_id not in pending_registrations:
            logger.error(f"Пользователь {user_id} не найден в pending_registrations")
            return False
            
        reg_data = pending_registrations[user_id]
        institution_id = reg_data.get("institution_id")
        faculty_id = reg_data.get("faculty_id")
        
        if not institution_id or not faculty_id:
            logger.error(f"Не найдены ID института или факультета для пользователя {user_id}")
            return False

        group_data = await self.university_service.get_group_by_name(institution_id, faculty_id, group)
        if not group_data:
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Не удалось найти выбранную группу"
            )
            return False
        
        reg_data["group"] = group
        reg_data["group_id"] = group_data["id"]
        reg_data["step"] = "confirmation"
        
        await self.send_confirmation(chat_id, user_id, reg_data)
        return True

    async def handle_confirmation(self, user_id: int, chat_id: int, confirmation: str) -> bool:
        """Обрабатывает подтверждение данных"""
        if user_id not in pending_registrations:
            logger.error(f"Пользователь {user_id} не найден в pending_registrations")
            return False
            
        reg_data = pending_registrations[user_id]
        
        if confirmation == "yes":
            await self.complete_registration(user_id, chat_id, reg_data)
            return True
        elif confirmation == "no":
            await self.restart_registration(user_id, chat_id)
            return True
        
        return False

    async def process_callback(self, callback_data: str, user_id: int, chat_id: int) -> bool:
        """Обрабатывает callback для конкретного пользователя"""
        if user_id not in pending_registrations:
            logger.error(f"Пользователь {user_id} не найден в pending_registrations")
            return False
        
        reg_data = pending_registrations[user_id]
        logger.info(f"Текущий шаг регистрации: {reg_data.get('step')}")
        
        if callback_data.startswith("university_"):
            try:
                parts = callback_data.split("_", 2)
                if len(parts) >= 3:
                    university = parts[2].replace('_', ' ')
                    logger.info(f"Выбран ВУЗ: {university}")
                    
                    reg_data["university"] = university
                    reg_data["step"] = "faculty"
                    
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ Вы выбрали: {university}"
                    )
                    
                    await self.send_faculty_selection(chat_id, user_id, university)
                    return True
            except Exception as e:
                logger.error(f"Ошибка обработки university callback: {e}")
                return False
        
        elif callback_data.startswith("faculty_"):
            try:
                parts = callback_data.split("_", 2)
                if len(parts) >= 3:
                    faculty = parts[2].replace('_', ' ')
                    logger.info(f"Выбран факультет: {faculty}")
                    
                    reg_data["faculty"] = faculty
                    reg_data["step"] = "group"
                    
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ Вы выбрали: {faculty}"
                    )
                    
                    await self.send_group_selection(chat_id, user_id, reg_data["university"], faculty)
                    return True
            except Exception as e:
                logger.error(f"Ошибка обработки faculty callback: {e}")
                return False
        
        elif callback_data.startswith("group_"):
            try:
                parts = callback_data.split("_", 2)
                if len(parts) >= 3:
                    group = parts[2].replace('_', ' ')
                    logger.info(f"Выбрана группа: {group}")
                    
                    reg_data["group"] = group
                    reg_data["step"] = "confirmation"
                    
                    await self.send_confirmation(chat_id, user_id, reg_data)
                    return True
            except Exception as e:
                logger.error(f"Ошибка обработки group callback: {e}")
                return False
        
        elif callback_data.startswith("confirm_"):
            try:
                parts = callback_data.split("_")
                if len(parts) >= 3:
                    confirmation = parts[1]  # yes или no
                    logger.info(f"Подтверждение: {confirmation}")
                    
                    if confirmation == "yes":
                        await self.complete_registration(user_id, chat_id, reg_data)
                        return True
                    elif confirmation == "no":
                        await self.restart_registration(user_id, chat_id)
                        return True
            except Exception as e:
                logger.error(f"Ошибка обработки confirm callback: {e}")
                return False
        
        logger.error(f"Неизвестный callback: {callback_data}")
        return False

    async def restart_registration(self, user_id: int, chat_id: int):
        """Начинает регистрацию заново"""
        logger.info(f"Перезапуск регистрации для пользователя {user_id}")
        
        if user_id in pending_registrations:
            del pending_registrations[user_id]
        
        await self.start_registration(chat_id, user_id)
        
        await self.bot.send_message(
            chat_id=chat_id,
            text="🔄 Начинаем регистрацию заново. Введите ваше ФИО:"
        )

    async def complete_registration(self, user_id: int, chat_id: int, reg_data: Dict):
        """Завершает регистрацию пользователя с прикреплением к группе через API"""
        logger.info(f"Завершение регистрации для пользователя {user_id}")
        logger.info(f"Данные регистрации: {reg_data}")
        
        try:
            registration_success = await self.register_user_in_system(
                user_id, 
                reg_data["full_name"], 
                reg_data["university"],
                reg_data.get("faculty"),
                reg_data.get("group")
            )
            
            system_id = await self.api_service.get_student_by_max_id(user_id)
            
            user = User(
                user_id=user_id,
                full_name=reg_data["full_name"],
                university=reg_data["university"],
                group=reg_data["group"],
                status=UserStatus.PENDING,  
                system_id=system_id,
                application_approved=False  
            )
            
            if reg_data.get("faculty"):
                user.faculty = reg_data["faculty"]
            
            
            users_db[user_id] = user
            logger.info(f"Пользователь сохранен в users_db: {user_id}")
            
            if user_id in pending_registrations:
                del pending_registrations[user_id]
            
            faculty_text = f"\n📚 Факультет: {reg_data.get('faculty')}" if reg_data.get('faculty') else ""
            
            status_text = f"""✅ Регистрация завершена!{faculty_text}

Ваши данные отправлены на проверку администрации учебного заведения.

Что сейчас происходит:
• Администратор проверяет ваше соответствие группе
• Обычно это занимает 1-3 рабочих дня  
• Вы получите уведомление о результате

Что доступно сейчас:
• 📊 Проверка статуса заявки
• 👤 Просмотр вашего профиля

Используйте команду «Мой статус» для отслеживания прогресса."""
            
            if registration_success:
                if system_id:
                    status_text += f"\n\n🔗 Ваш профиль синхронизирован с системой StudGram"
            else:
                status_text += f"\n\n⚠️ Не удалось полностью синхронизировать с системой StudGram"
                status_text += f"\n📞 Обратитесь к администратору для решения проблемы"
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="📊 Мой статус", payload="menu_status"))
            builder.row(CallbackButton(text="👤 Мой профиль", payload="menu_profile"))
            
            await self.bot.send_message(
                chat_id=chat_id, 
                text=status_text,
                attachments=[builder.as_markup()]
            )
            
            await self.send_main_menu(chat_id, user)
            
        except Exception as e:
            logger.error(f"Ошибка при завершении регистрации: {e}")
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при завершении регистрации. Попробуйте позже."
            )

    async def register_user_in_system(self, user_id: int, full_name: str, university: str, faculty_name: str = None, group_name: str = None) -> bool:
        """Зарегистрировать пользователя в системе StudGram и прикрепить к группе"""
        try:
            logger.info(f"=== НАЧАЛО РЕГИСТРАЦИИ В СИСТЕМЕ ===")
            logger.info(f"User ID: {user_id}, ФИО: {full_name}, Университет: {university}, Факультет: {faculty_name}, Группа: {group_name}")
            
            logger.info("1. Тестируем подключение к API...")
            if not await self.api_service.test_api_connection():
                logger.error("❌ Нет подключения к API StudGram")
                return False
            logger.info("✅ Подключение к API успешно")

            logger.info("2. Получаем/регистрируем студента...")
            existing_id = await self.api_service.get_student_by_max_id(user_id)
            
            if existing_id:
                system_id = existing_id
                logger.info(f"✅ Студент уже существует в системе: {system_id}")
                
                logger.info("Обновляем данные существующего студента...")
                update_success = await self.api_service.update_student(
                    system_id, 
                    fullName=full_name, 
                    maxId=user_id
                )
                if not update_success:
                    logger.error("❌ Не удалось обновить данные студента")
                    return False
                logger.info("✅ Данные студента обновлены")
            else:
                logger.info("Регистрируем нового студента...")
                system_id = await self.api_service.register_student(user_id, full_name)
                if not system_id:
                    logger.error("❌ Не удалось зарегистрировать студента в системе")
                    return False
                logger.info(f"✅ Новый студент зарегистрирован: {system_id}")

            logger.info("3. Ищем ID учебного заведения...")
            institution = await self.university_service.get_university_by_name(university)
            if not institution:
                logger.error(f"❌ Не найден институт для университета: {university}")
                return False
            
            institution_id = institution["id"]
            logger.info(f"✅ Найден институт: {institution['title']} (ID: {institution_id})")

            logger.info("4. Прикрепляем студента к учебному заведению...")
            institution_success = await self.api_service.link_student_to_institution(system_id, institution_id)
            
            if not institution_success:
                logger.error(f"❌ Не удалось прикрепить студента к институту")
                return False
            logger.info("✅ Студент прикреплен к институту")

            faculty_success = True
            faculty_id = None
            if faculty_name:
                logger.info("5. Прикрепляем студента к факультету...")
                faculty = await self.university_service.get_faculty_by_name(institution_id, faculty_name)
                if faculty:
                    faculty_id = faculty["id"]
                    faculty_success = await self.api_service.link_student_to_faculty(system_id, faculty_id)
                    if faculty_success:
                        logger.info(f"✅ Студент прикреплен к факультету: {faculty_name}")
                    else:
                        logger.error(f"❌ Не удалось прикрепить студента к факультету: {faculty_name}")
                else:
                    logger.warning(f"⚠️ Факультет не найден: {faculty_name}")
                    faculty_success = False

            group_success = True
            if group_name and faculty_id:
                logger.info("6. Прикрепляем студента к группе...")
                group = await self.university_service.get_group_by_name(institution_id, faculty_id, group_name)
                if group:
                    group_id = group["id"]
                    group_success = await self.api_service.link_student_to_group(system_id, group_id)
                    if group_success:
                        logger.info(f"✅ Студент прикреплен к группе: {group_name}")
                    else:
                        logger.error(f"❌ Не удалось прикрепить студента к группе: {group_name}")
                else:
                    logger.warning(f"⚠️ Группа не найдена: {group_name}")
                    group_success = False

            if user_id in users_db:
                users_db[user_id].system_id = system_id
            
            logger.info("=== РЕГИСТРАЦИЯ УСПЕШНО ЗАВЕРШЕНА ===")
            return institution_success and faculty_success and group_success
                
        except Exception as e:
            logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА регистрации в системе: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False