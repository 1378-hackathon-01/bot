import logging
from typing import List, Optional, Tuple
from .studgram_api import StudGramAPIService
from .cache import Cache

logger = logging.getLogger(__name__)

class UniversityService:
    """Сервис для работы с университетами"""
    
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
    
    @staticmethod
    def get_groups(university: str) -> List[str]:
        """Получить список групп для университета"""
        groups_map = {
            "МГУ": ["БИ-101", "БИ-102", "ФИ-201"],
            "МФТИ": ["ФРКТ-01", "ФОПФ-02"],
            "ВШЭ": ["ПМИ-101", "ФКН-201"],
            "МГТУ": ["РК1-01", "РК2-02"],
            "МИФИ": ["Б10-101", "Б10-102"],
            "Санкт-Петербургский государственный электротехнический университет «ЛЭТИ» имени В. И. Ульянова (Ленина)": ["ИТ-101", "ИТ-102", "ЭВМ-201"],
            "Московский государственный институт международных отношений": ["МО-101", "МО-102", "ПО-201"],
            "Санкт-Петербургский Политехнический Университет Петра Великого": ["ТМ-101", "ТМ-102", "ММ-201"]
        }
        return groups_map.get(university, [f"ГР-{i}" for i in range(1, 4)])
    
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