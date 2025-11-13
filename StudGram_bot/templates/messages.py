from datetime import datetime
from typing import List, Dict
from models.user import User, UserStatus, UserRole
from services.calendar_service import CalendarService

class MessageTemplates:
    """Шаблоны сообщений"""
    
    @staticmethod
    def get_main_menu(user: User) -> str:
        """Главное меню в соответствии с ролью пользователя"""
        if user.status != UserStatus.APPROVED:
            return """Добро пожаловать в StudGram.

Доступные команды:
• Инфо
• Мой профиль"""
        
        base_commands = """• Расписание
• Задания 
• О ВУЗе
• Мой профиль"""
        
        if user.role == UserRole.STUDENT:
            return f"""Главное меню StudGram

Доступные команды:
{base_commands}"""
        else:
            return f"""Главное меню StudGram

Доступные команды:
{base_commands}
• Управление группой"""
    
    @staticmethod
    def get_schedule_menu() -> str:
        """Меню выбора расписания"""
        return "📚 Выберите расписание:"
    
    @staticmethod
    def get_calendar(calendar_days: List[Dict], current_month: datetime) -> str:
        """Форматирование календаря"""
        month_names = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]
        
        month_name = month_names[current_month.month - 1]
        year = current_month.year
        
        calendar_text = f"🗓️ Календарь на {month_name} {year} года:\n\n"
        calendar_text += "Пн Вт Ср Чт Пт Сб Вс\n"
        
        first_day_weekday = current_month.weekday()
        calendar_text += "   " * first_day_weekday
        
        for day_data in calendar_days:
            day = day_data['day']
            is_study = day_data['is_study']
            is_today = day_data['is_today']
            
            if is_today:
                calendar_text += f"[{day:2d}] "
            elif is_study:
                calendar_text += f" {day:2d}  "
            else:
                calendar_text += f"({day:2d}) "
            
            if day_data['weekday'] == 6:
                calendar_text += "\n"
        
        calendar_text += "\n\n📝 Обозначения:"
        calendar_text += "\n• 12  - учебный день"
        calendar_text += "\n• (12) - выходной день" 
        calendar_text += "\n• [12] - сегодняшний день"
        calendar_text += "\n\nВыберите действие:"
        calendar_text += "\n• Введите дату в формате ДД.ММ.ГГГГ (например, 15.12.2024)"
        calendar_text += "\n• 'Предыдущий месяц' - перейти к предыдущему месяцу"
        calendar_text += "\n• 'Следующий месяц' - перейти к следующему месяцу"
        calendar_text += "\n• 'Сегодня' - выбрать сегодняшнюю дату"
        calendar_text += "\n• 'Назад' - вернуться в главное меню"
        
        return calendar_text
    
    @staticmethod
    def get_schedule(schedule: List[dict], date: datetime) -> str:
        """Форматирование расписания"""
        day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_name = day_names[date.weekday()]
        date_str = date.strftime("%d.%m.%Y")
        
        schedule_text = f"📚 Расписание на {date_str} ({day_name}):\n\n"
        
        if not schedule:
            schedule_text += "🎉 Пар нет! Отличный день для отдыха или самообразования."
        else:
            for i, lesson in enumerate(schedule, 1):
                schedule_text += f"{i}. {lesson['subject']}\n"
                schedule_text += f"   👨‍🏫 Преподаватель: {lesson['teacher']}\n"
                schedule_text += f"   ⏰ Время: {lesson['time']}\n"
                schedule_text += f"   🏫 Аудитория: {lesson['room']}\n"
                if lesson.get('online_link'):
                    schedule_text += f"   🔗 Ссылка: {lesson['online_link']}\n"
                schedule_text += "\n"
        
        schedule_text += "\nНавигация:"
        schedule_text += "\n• 'Календарь' - вернуться к выбору даты"
        schedule_text += "\n• 'Назад' - вернуться в главное меню"
        
        return schedule_text
    
    @staticmethod
    def get_assignments(assignments: List[dict]) -> str:
        """Форматирование заданий"""
        if not assignments:
            return "🎉 На данный момент заданий нет!"
        
        assignments_text = "📝 Текущие задания:\n\n"
        for i, assignment in enumerate(assignments, 1):
            assignments_text += f"{i}. {assignment['subject']}\n"
            assignments_text += f"   📋 Задание: {assignment['task']}\n"
            assignments_text += f"   ⏰ Срок сдачи: {assignment['deadline']}\n"
            if assignment.get('attachments'):
                assignments_text += f"   📎 Вложения: {', '.join(assignment['attachments'])}\n"
            assignments_text += "\n"
        
        assignments_text += "Назад - вернуться в главное меню"
        return assignments_text
    
    @staticmethod
    def get_university_info() -> str:
        """Информация о вузе"""
        return """Информация о вузе и платформе

Контакты администрации для обращений:
• Email: <i>admin@studgram.ru</i>
• Телефон: +7 (495) 123-45-67

Ссылки на внутренние порталы:
• Официальный сайт: https://studgram.ru
• Личный кабинет: https://lk.studgram.ru
• Образовательная платформа: https://edu.studgram.ru

Инструкции по использованию StudGram:
• Для доступа ко всем функциям необходимо подтверждение профиля
• Расписание обновляется автоматически
• Уведомления о заданиях приходят за 24 часа до дедлайна
• Уведомления о занятиях приходят за 2 часа до начала"""