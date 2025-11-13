import logging
from datetime import datetime
from typing import List, Optional, Dict
from .api_client import APIClient
from config import API_BASE_URL, API_TOKEN

logger = logging.getLogger(__name__)

class StudGramAPIService:
    """Сервис для работы с API StudGram"""
    
    def __init__(self):
        self.client = APIClient(API_BASE_URL, API_TOKEN)
    
    async def get_institutions(self) -> List[dict]:
        """Получить список учебных заведений"""
        institutions = await self.client.request("GET", "institutions") or []
        
        if institutions:
            logger.info(f"Получено {len(institutions)} учебных заведений")
            for inst in institutions[:3]:
                logger.info(f"  - {inst.get('title')} ({inst.get('abbreviation')})")
        else:
            logger.warning("Не удалось получить список учебных заведений")
        
        return institutions
    
    async def register_student(self, max_id: int, full_name: str = None) -> Optional[str]:
        """Зарегистрировать студента в системе StudGram"""
        data = {"maxId": max_id}
        if full_name:
            data["fullName"] = full_name
            
        result = await self.client.request("POST", "students", data)
        return result.get("id") if result else None
    
    async def get_student_by_max_id(self, max_id: int) -> Optional[str]:
        """Получить ID студента по MAX ID"""
        result = await self.client.request("GET", f"students/max/{max_id}")
        return result.get("id") if result else None
    
    async def update_student(self, student_id: str, **kwargs) -> bool:
        """Обновить данные студента"""
        result = await self.client.request("PATCH", f"students/{student_id}", kwargs)
        return result is not None
    
    async def link_student_to_institution(self, student_id: str, institution_id: str) -> bool:
        """Прикрепить студента к учебному заведению"""
        result = await self.client.request("POST", f"students/{student_id}/institution/{institution_id}")
        return result is not None

    async def get_schedule(self, group: str, date: datetime) -> List[dict]:
        """Получить расписание для группы на дату"""
        return await self._get_demo_schedule(group, date)
    
    async def get_assignments(self, group: str) -> List[dict]:
        """Получить задания для группы"""
        return await self._get_demo_assignments(group)
    
    async def _get_demo_schedule(self, group: str, date: datetime) -> List[dict]:
        """Демо-расписание для тестирования"""
        day_schedules = {
            0: [
                {"subject": "Математика", "teacher": "Иванов И.И.", "time": "09:00-10:30", "room": "101", "online_link": ""},
                {"subject": "Программирование", "teacher": "Петров П.П.", "time": "10:45-12:15", "room": "203", "online_link": "https://meet.google.com/abc-def-ghi"}
            ],
            1: [
                {"subject": "Физика", "teacher": "Сидоров А.В.", "time": "09:00-10:30", "room": "105", "online_link": ""},
                {"subject": "Английский язык", "teacher": "Кузнецова О.Л.", "time": "11:00-12:30", "room": "301", "online_link": ""}
            ],
            2: [
                {"subject": "Программирование", "teacher": "Петров П.П.", "time": "13:00-14:30", "room": "203", "online_link": "https://meet.google.com/xyz-uvw-rst"},
                {"subject": "Базы данных", "teacher": "Николаев С.М.", "time": "15:00-16:30", "room": "205", "online_link": ""}
            ],
            3: [
                {"subject": "Математика", "teacher": "Иванов И.И.", "time": "10:00-11:30", "room": "102", "online_link": ""},
                {"subject": "Физкультура", "teacher": "Алексеев В.П.", "time": "12:00-13:30", "room": "спортзал", "online_link": ""}
            ],
            4: [
                {"subject": "Веб-разработка", "teacher": "Смирнова Т.К.", "time": "09:00-10:30", "room": "210", "online_link": ""},
                {"subject": "Проектная деятельность", "teacher": "Петров П.П.", "time": "11:00-13:00", "room": "203", "online_link": "https://meet.google.com/mno-pqr-stu"}
            ]
        }
        weekday = date.weekday()
        return day_schedules.get(weekday, [])
    
    async def _get_demo_assignments(self, group: str) -> List[dict]:
        """Демо-задания для тестирования"""
        return [
            {
                "id": 1,
                "subject": "Математика", 
                "task": "Решить задачи №1-5 из учебника стр. 45", 
                "deadline": "2024-12-25",
                "attachments": [],
                "description": "Задачи на дифференциальные уравнения"
            },
            {
                "id": 2,
                "subject": "Программирование", 
                "task": "Написать телеграм-бота для учета задач", 
                "deadline": "2024-12-20",
                "attachments": ["https://example.com/task_description.pdf"],
                "description": "Бот должен уметь добавлять, удалять и отображать задачи"
            }
        ]