import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from maxapi import Bot
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types import CallbackButton

from models.user import User, UserRole, UserStatus, CalendarState
from services.studgram_api import StudGramAPIService
from services.university_service import UniversityService
from services.calendar_service import CalendarService
from templates.messages import MessageTemplates
from config import users_db, pending_registrations, active_chats, moderators_db

logger = logging.getLogger(__name__)

class BotService:
    """Основной сервис бота"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.university_service = UniversityService()
        self.api_service = StudGramAPIService()
        self.templates = MessageTemplates()
    
    async def send_main_menu(self, chat_id: int, user: User):
        """Отправляет главное меню с кнопками"""
        menu_text = self.templates.get_main_menu(user)
        builder = InlineKeyboardBuilder()
        
        if user.status == UserStatus.APPROVED:
            buttons = [
                CallbackButton(text="📚 Расписание", payload="menu_schedule"),
                CallbackButton(text="📝 Задания", payload="menu_assignments"),
                CallbackButton(text="🏫 О ВУЗе", payload="menu_university_info"),
                CallbackButton(text="👤 Мой профиль", payload="menu_profile")
            ]
            
            for i in range(0, len(buttons), 2):
                row_buttons = buttons[i:i+2]
                builder.row(*row_buttons)
            
            if user.role == UserRole.MODERATOR:
                builder.row(CallbackButton(text="⚙️ Управление группой", payload="menu_management"))
        else:
            builder.row(
                CallbackButton(text="ℹ️ Инфо", payload="menu_info"),
                CallbackButton(text="👤 Мой профиль", payload="menu_profile")
            )
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=menu_text,
            attachments=[builder.as_markup()]
        )
    
    async def send_schedule_menu(self, chat_id: int, user: User):
        """Отправляет меню выбора расписания"""
        if user.status != UserStatus.APPROVED:
            await self._send_not_approved_message(chat_id)
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
        if user.status != UserStatus.APPROVED:
            await self._send_not_approved_message(chat_id)
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
        today = datetime.now()
        await self._show_schedule_for_date(chat_id, user, today)
    
    async def show_schedule_for_tomorrow(self, chat_id: int, user: User):
        """Показывает расписание на завтра"""
        tomorrow = datetime.now() + timedelta(days=1)
        await self._show_schedule_for_date(chat_id, user, tomorrow)
    
    async def _show_schedule_for_date(self, chat_id: int, user: User, date: datetime):
        """Показывает расписание на указанную дату"""
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
        """Отправляет список заданий"""
        if user.status != UserStatus.APPROVED:
            await self._send_not_approved_message(chat_id)
            return
        
        try:
            assignments = await self.api_service.get_assignments(user.group)
            assignments_text = self.templates.get_assignments(assignments)
            
            builder = InlineKeyboardBuilder()
            builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=assignments_text,
                attachments=[builder.as_markup()]
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения заданий: {e}")
            await self.bot.send_message(
                chat_id=chat_id, 
                text="Задания временно недоступны. Повторите попытку позже."
            )
    
    async def send_university_info(self, chat_id: int, user: User):
        """Отправляет информацию о вузе"""
        info_text = self.templates.get_university_info()
        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))

        await self.bot.send_message(
            chat_id=chat_id, 
            text=info_text,
            attachments=[builder.as_markup()]
        )
    
    async def send_profile(self, chat_id: int, user: User):
        """Отправляет профиль пользователя"""
        status_text = "подтвержден" if user.status == UserStatus.APPROVED else "ожидает подтверждения"
        role_text = "Студент" if user.role == UserRole.STUDENT else "Модератор"
        
        profile_text = f"""Ваш профиль:

ФИО: {user.full_name}
Вуз: {user.university}
Группа: {user.group}
Роль: {role_text}
Статус регистрации: {status_text}"""

        if user.system_id:
            profile_text += f"\nID в системе: {user.system_id}"

        if user.status == UserStatus.PENDING:
            moderator_contact = moderators_db.get(user.group, "@group_moderator")
            profile_text += f"\n\nВаш профиль отправлен на подтверждение старосте. Вот его контакты: {moderator_contact}. Вы получите уведомление после проверки."

        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))

        await self.bot.send_message(
            chat_id=chat_id, 
            text=profile_text,
            attachments=[builder.as_markup()]
        )
    
    async def send_group_management_info(self, chat_id: int, user: User):
        """Отправляет информацию об управлении группой"""
        if user.role != UserRole.MODERATOR:
            await self.bot.send_message(chat_id=chat_id, text="❌ Доступ запрещен!")
            return
        
        management_text = f"""Управление группой {user.group}

Функции управления доступны в веб-интерфейсе:
https://studgram.ru/moderator

<b>Доступные функции:</b>
• Просмотр списка студентов
• Подтверждение / удаление студентов  
• Добавление ссылок на онлайн-занятия
• Редактирование информации о предметах и заданиях"""

        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="🔙 Назад в меню", payload="menu_back"))

        await self.bot.send_message(
            chat_id=chat_id, 
            text=management_text,
            attachments=[builder.as_markup()]
        )
    
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
        """Отправляет кнопки для выбора ВУЗа"""
        try:
            universities = await self.university_service.get_university_names()
            if not universities:
                universities = ["МГУ", "МФТИ", "ВШЭ", "МГТУ", "МИФИ"]
            
            logger.info(f"Доступные ВУЗы: {universities}")
            
            builder = InlineKeyboardBuilder()
            
            for i in range(0, len(universities), 2):
                row_universities = universities[i:i+2]
                buttons = []
                for uni in row_universities:
                    # Безопасный формат: university_{user_id}_{uni_name}
                    safe_uni = uni.replace(' ', '_')
                    payload = f"university_{user_id}_{safe_uni}"
                    buttons.append(CallbackButton(text=uni, payload=payload))
                builder.row(*buttons)
            
            await self.bot.send_message(
                chat_id=chat_id,
                text="🎓 Выберите ваш вуз:",
                attachments=[builder.as_markup()]
            )
            logger.info("Кнопки ВУЗов отправлены успешно")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке кнопок ВУЗов: {e}")
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при загрузке списка ВУЗов"
            )

    async def send_group_selection(self, chat_id: int, user_id: int, university: str):
        """Отправляет кнопки для выбора группы"""
        groups = UniversityService.get_groups(university)
        
        builder = InlineKeyboardBuilder()
        
        for i in range(0, len(groups), 2):
            row_groups = groups[i:i+2]
            buttons = []
            for group in row_groups:
                # Безопасный формат: group_{user_id}_{group_name}
                safe_group = group.replace(' ', '_')
                payload = f"group_{user_id}_{safe_group}"
                buttons.append(CallbackButton(text=group, payload=payload))
            builder.row(*buttons)
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"🎓 Вуз: {university}\n👥 Выберите вашу группу:",
            attachments=[builder.as_markup()]
        )

    async def send_confirmation(self, chat_id: int, user_id: int, reg_data: Dict):
        """Отправляет подтверждение введенных данных"""
        confirmation_text = f"""✅ Проверьте введенные данные:

📝 ФИО: {reg_data['full_name']}
🎓 ВУЗ: {reg_data['university']}
👥 Группа: {reg_data['group']}

Все данные верны?"""
        
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
        
        # Сначала обрабатываем меню-колбэки
        if (callback_data.startswith("menu_") or 
            callback_data.startswith("schedule_") or 
            callback_data in ["calendar_prev", "calendar_next", "calendar_today"]):
            return await self.handle_menu_callback(callback_data, chat_id)
        
        # Обрабатываем регистрационные колбэки
        user_id = None
        
        # Университеты: university_{user_id}_{university_name}
        if callback_data.startswith("university_"):
            try:
                parts = callback_data.split("_", 2)  # Разделяем только на 3 части
                if len(parts) >= 3:
                    user_id = int(parts[1])
                    university = parts[2].replace('_', ' ')  # Восстанавливаем пробелы
                    return await self.handle_university_selection(user_id, chat_id, university)
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка извлечения user_id из university callback: {e}")
                return False
        
        # Группы: group_{user_id}_{group_name}
        elif callback_data.startswith("group_"):
            try:
                parts = callback_data.split("_", 2)  # Разделяем только на 3 части
                if len(parts) >= 3:
                    user_id = int(parts[1])
                    group = parts[2].replace('_', ' ')  # Восстанавливаем пробелы
                    return await self.handle_group_selection(user_id, chat_id, group)
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка извлечения user_id из group callback: {e}")
                return False
        
        # Подтверждение: confirm_{yes/no}_{user_id}
        elif callback_data.startswith("confirm_"):
            try:
                parts = callback_data.split("_")
                if len(parts) >= 3:
                    confirmation = parts[1]  # yes или no
                    user_id = int(parts[2])
                    return await self.handle_confirmation(user_id, chat_id, confirmation)
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка извлечения user_id из confirm callback: {e}")
                return False
        
        # Если не удалось определить user_id из callback_data, используем active_chats
        if not user_id:
            if chat_id in active_chats:
                user_id = active_chats[chat_id]
                logger.info(f"Используем user_id из active_chats: {user_id}")
            else:
                logger.error(f"Не удалось определить user_id для callback: {callback_data}")
                await self.bot.send_message(chat_id=chat_id, text="❌ Ошибка: не удалось обработать действие")
                return False
        
        logger.info(f"Обработка для пользователя {user_id}")
        return await self.process_callback(callback_data, user_id, chat_id)
    
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
    
        if user_id not in users_db:
            logger.error(f"Пользователь {user_id} не найден в users_db. Доступные пользователи: {list(users_db.keys())}")
            await self.bot.send_message(chat_id=chat_id, text="❌ Ошибка: профиль не найден. Пройдите регистрацию заново.")
            return False
        
        user = users_db[user_id]
        logger.info(f"Найден пользователь: {user.full_name}, статус: {user.status}")
        
        menu_actions = {
            "menu_schedule": {
                "handler": lambda: self.send_schedule_menu(chat_id, user),
                "required_status": UserStatus.APPROVED
            },
            "menu_assignments": {
                "handler": lambda: self.send_assignments(chat_id, user),
                "required_status": UserStatus.APPROVED
            },
            "menu_university_info": {
                "handler": lambda: self.send_university_info(chat_id, user),
                "required_status": None
            },
            "menu_profile": {
                "handler": lambda: self.send_profile(chat_id, user),
                "required_status": None
            },
            "menu_management": {
                "handler": lambda: self.send_group_management_info(chat_id, user),
                "required_status": UserStatus.APPROVED,
                "required_role": UserRole.MODERATOR
            },
            "menu_info": {
                "handler": lambda: self.send_university_info(chat_id, user),
                "required_status": None
            },
            "menu_back": {
                "handler": lambda: self.send_main_menu(chat_id, user),
                "required_status": None
            },
            "menu_calendar": {
                "handler": lambda: self.send_calendar(chat_id, user),
                "required_status": UserStatus.APPROVED
            },
            "calendar_prev": {
                "handler": lambda: self.send_calendar(chat_id, user, "prev_month"),
                "required_status": UserStatus.APPROVED
            },
            "calendar_next": {
                "handler": lambda: self.send_calendar(chat_id, user, "next_month"),
                "required_status": UserStatus.APPROVED
            },
            "calendar_today": {
                "handler": lambda: self.send_calendar(chat_id, user, "today"),
                "required_status": UserStatus.APPROVED
            },
            "schedule_today": {
                "handler": lambda: self.show_schedule_for_today(chat_id, user),
                "required_status": UserStatus.APPROVED
            },
            "schedule_tomorrow": {
                "handler": lambda: self.show_schedule_for_tomorrow(chat_id, user),
                "required_status": UserStatus.APPROVED
            }
        }
        
        action_config = menu_actions.get(callback_data)
        if not action_config:
            logger.error(f"Неизвестный меню-колбэк: {callback_data}")
            return False
        
        if (action_config["required_status"] and 
            user.status != action_config["required_status"]):
            await self._send_not_approved_message(chat_id)
            return True
        
        if (action_config.get("required_role") and 
            user.role != action_config["required_role"]):
            await self.bot.send_message(chat_id=chat_id, text="❌ Доступ запрещен!")
            return True
        
        try:
            logger.info(f"Выполнение действия: {callback_data}")
            await action_config["handler"]()
            return True
        except Exception as e:
            logger.error(f"Ошибка при выполнении действия {callback_data}: {e}")
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
            
        reg_data = pending_registrations[user_id]
        reg_data["university"] = university
        reg_data["step"] = "group"
        
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Вы выбрали: {university}"
        )
        
        await self.send_group_selection(chat_id, user_id, university)
        return True
    
    async def handle_group_selection(self, user_id: int, chat_id: int, group: str) -> bool:
        """Обрабатывает выбор группы"""
        if user_id not in pending_registrations:
            logger.error(f"Пользователь {user_id} не найден в pending_registrations")
            return False
            
        reg_data = pending_registrations[user_id]
        reg_data["group"] = group
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
        
        # Обработка университетов
        if callback_data.startswith("university_"):
            try:
                parts = callback_data.split("_", 2)
                if len(parts) >= 3:
                    university = parts[2].replace('_', ' ')
                    logger.info(f"Выбран ВУЗ: {university}")
                    
                    reg_data["university"] = university
                    reg_data["step"] = "group"
                    
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ Вы выбрали: {university}"
                    )
                    
                    await self.send_group_selection(chat_id, user_id, university)
                    return True
            except Exception as e:
                logger.error(f"Ошибка обработки university callback: {e}")
                return False
        
        # Обработка групп
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
        
        # Обработка подтверждения
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
        """Завершает регистрацию пользователя"""
        logger.info(f"Завершение регистрации для пользователя {user_id}")
        logger.info(f"Данные регистрации: {reg_data}")
        logger.info(f"Active chats до завершения: {active_chats}")
        
        user = User(
            user_id=user_id,
            full_name=reg_data["full_name"],
            university=reg_data["university"],
            group=reg_data["group"],
            status=UserStatus.PENDING
        )
        
        registration_success = await self.register_user_in_system(user_id, reg_data["full_name"], reg_data["university"])
        
        if not users_db:
            user.role = UserRole.MODERATOR
            user.status = UserStatus.APPROVED
            moderators_db[user.group] = f"@{user.full_name.split()[0].lower()}"
        
        users_db[user_id] = user
        
        if user_id in pending_registrations:
            del pending_registrations[user_id]
        
        logger.info(f"Active chats после завершения: {active_chats}")
        logger.info(f"Users DB: {list(users_db.keys())}")
        
        if user.status == UserStatus.APPROVED:
            status_text = "✅ <b>Регистрация завершена!<b> Добро пожаловать в StudGram!"
            if user.role == UserRole.MODERATOR:
                status_text += f"\n🎯 Вы назначены модератором группы {user.group}"
            if registration_success:
                status_text += "\n🔗 Ваш профиль синхронизирован с системой StudGram"
            else:
                status_text += "\n⚠️ Не удалось синхронизировать с системой StudGram"
                
            await self.bot.send_message(chat_id=chat_id, text=status_text)
            await self.send_main_menu(chat_id, user)
        else:
            status_text = "⏳ Ваш профиль отправлен на подтверждение модератору. Вы получите уведомление после проверки."
            if registration_success:
                status_text += "\n🔗 Ваш профиль синхронизирован с системой StudGram"
                
            await self.bot.send_message(chat_id=chat_id, text=status_text)
            await self.send_main_menu(chat_id, user)

    async def register_user_in_system(self, user_id: int, full_name: str, university: str) -> bool:
        """Зарегистрировать пользователя в системе StudGram"""
        try:
            existing_id = await self.api_service.get_student_by_max_id(user_id)
            
            if existing_id:
                system_id = existing_id
                update_success = await self.api_service.update_student(
                    system_id, 
                    fullName=full_name, 
                    maxId=user_id
                )
                if not update_success:
                    logger.error(f"Не удалось обновить данные студента {user_id}")
                    return False
            else:
                system_id = await self.api_service.register_student(user_id, full_name)
                if not system_id:
                    logger.error(f"Не удалось зарегистрировать студента {user_id} в системе")
                    return False
            
            institution = await self.university_service.get_university_by_name(university)
            if institution:
                success = await self.api_service.link_student_to_institution(system_id, institution["id"])
                if success and user_id in users_db:
                    users_db[user_id].system_id = system_id
                return success
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка регистрации в системе: {e}")
            return False
    
    async def _send_not_approved_message(self, chat_id: int):
        """Сообщение о неподтвержденном профиле"""
        await self.bot.send_message(
            chat_id=chat_id, 
            text="❌ Ваш профиль еще не подтвержден. Доступ к этому разделу будет открыт после проверки."
        )