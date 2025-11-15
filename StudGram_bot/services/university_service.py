import logging
from typing import List, Optional, Tuple
from .studgram_api import StudGramAPIService
from .cache import Cache

logger = logging.getLogger(__name__)

class UniversityService:
    """Сервис для работы с университетами через API"""
    
    def __init__(self):
        self.api = StudGramAPIService()
        self.cache = Cache()
    
    async def get_universities(self) -> List[dict]:
        """Получить список учебных заведений с кэшированием"""
        cache_key = "universities"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        institutions = await self.api.get_institutions()
        self.cache.set(cache_key, institutions)
        return institutions or []
    
    async def get_university_names(self) -> List[str]:
        """Получить список названий университетов"""
        institutions = await self.get_universities()
        return [inst["title"] for inst in institutions] if institutions else []
    
    async def get_university_by_name(self, name: str) -> Optional[dict]:
        """Найти университет по названию"""
        institutions = await self.get_universities()
        if not institutions:
            return None
            
        for inst in institutions:
            if inst["title"] == name or inst["abbreviation"] == name:
                return inst
        return None
    
    async def get_faculties(self, institution_id: str) -> List[dict]:
        """Получить список факультетов учебного заведения"""
        cache_key = f"faculties_{institution_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        faculties = await self.api.get_faculties(institution_id)
        self.cache.set(cache_key, faculties)
        return faculties or []
    
    async def get_faculty_names(self, institution_id: str) -> List[str]:
        """Получить список названий факультетов"""
        faculties = await self.get_faculties(institution_id)
        return [faculty["title"] for faculty in faculties] if faculties else []
    
    async def get_faculty_by_name(self, institution_id: str, faculty_name: str) -> Optional[dict]:
        """Найти факультет по названию"""
        faculties = await self.get_faculties(institution_id)
        if not faculties:
            return None
            
        for faculty in faculties:
            if faculty["title"] == faculty_name or faculty["abbreviation"] == faculty_name:
                return faculty
        return None
    
    async def get_groups(self, institution_id: str, faculty_id: str) -> List[dict]:
        """Получить список групп факультета через API"""
        cache_key = f"groups_{institution_id}_{faculty_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        groups = await self.api.get_groups(institution_id, faculty_id)
        self.cache.set(cache_key, groups)
        return groups or []

    async def get_group_names(self, institution_id: str, faculty_id: str) -> List[str]:
        """Получить список названий групп"""
        groups = await self.get_groups(institution_id, faculty_id)
        return [group["title"] for group in groups] if groups else []

    async def get_group_by_name(self, institution_id: str, faculty_id: str, group_name: str) -> Optional[dict]:
        """Найти группу по названию"""
        groups = await self.get_groups(institution_id, faculty_id)
        if not groups:
            return None
            
        for group in groups:
            if group["title"] == group_name or group["abbreviation"] == group_name:
                return group
        return None

    @staticmethod
    def validate_full_name(full_name: str) -> Tuple[bool, str]:
        """Проверяет валидность ФИО"""
        name_parts = full_name.strip().split()
        if len(name_parts) < 2:
            return False, "Введите полное ФИО (Имя и Фамилия)"
        if len(name_parts) > 3:
            return False, "Слишком много слов в ФИО"
        if any(not part.isalpha() for part in name_parts):
            return False, "ФИО должно содержать только буквы"
        if len(full_name) < 5:
            return False, "ФИО слишком короткое"
        return True, "ФИО корректно"
    
    async def get_student_subjects(self, student_id: str) -> List[dict]:
        """Получить дисциплины студента с кэшированием"""
        cache_key = f"subjects_{student_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        subjects = await self.api.get_student_subjects(student_id)
        self.cache.set(cache_key, subjects)
        return subjects or []