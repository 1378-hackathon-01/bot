from datetime import datetime
from typing import List, Dict, Optional
from calendar import monthrange

class CalendarService:
    """Сервис для работы с календарем учебных дней"""
    
    @staticmethod
    def is_study_day(date: datetime) -> bool:
        """Проверяет, является ли день учебным"""
        weekday = date.weekday()
        return weekday < 5  # Пн-Пт - учебные дни
    
    @staticmethod
    def get_month_calendar(year: int, month: int) -> List[Dict]:
        """Возвращает календарь на месяц с отметками учебных дней"""
        _, num_days = monthrange(year, month)
        calendar = []
        
        for day in range(1, num_days + 1):
            date = datetime(year, month, day)
            is_study = CalendarService.is_study_day(date)
            is_today = date.date() == datetime.now().date()
            
            calendar.append({
                'day': day,
                'date': date,
                'is_study': is_study,
                'is_today': is_today,
                'weekday': date.weekday()
            })
        
        return calendar
    
    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """Парсит дату из строки формата ДД.ММ.ГГГГ"""
        try:
            return datetime.strptime(date_str, '%d.%m.%Y')
        except ValueError:
            return None