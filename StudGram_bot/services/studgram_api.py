import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict
from services.api_client import APIClient
from config import API_BASE_URL, API_TOKEN, users_db, active_chats
import asyncio

logger = logging.getLogger(__name__)

class StudGramAPIService:
    """Сервис для работы с API StudGram"""
    
    def __init__(self):
        self.client = APIClient(API_BASE_URL, API_TOKEN)
    
    async def test_api_connection(self) -> bool:
        """Тестирует подключение к API"""
        try:
            logger.info("🔌 Тестируем подключение к API StudGram...")
            institutions = await self.get_institutions()
            
            if institutions is not None:
                logger.info(f"✅ Подключение к API успешно. Получено {len(institutions)} учебных заведений")
                return True
            else:
                logger.error("❌ Не удалось получить данные от API")
                return False
                
        except Exception as e:
            logger.error(f"💥 Ошибка подключения к API: {e}")
            return False
    
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
    
    async def get_faculties(self, institution_id: str) -> List[dict]:
        """Получить список факультетов учебного заведения"""
        if not await self.validate_uuid(institution_id):
            logger.error(f"❌ Неверный формат ID института: {institution_id}")
            return []
            
        faculties = await self.client.request("GET", f"institutions/{institution_id}/faculties") or []
        
        if faculties:
            logger.info(f"Получено {len(faculties)} факультетов для учреждения {institution_id}")
            for faculty in faculties[:3]:
                logger.info(f"  - {faculty.get('title')} ({faculty.get('abbreviation')})")
        else:
            logger.warning(f"Не удалось получить факультеты для учреждения {institution_id}")
        
        return faculties
    
    async def get_groups(self, institution_id: str, faculty_id: str) -> List[dict]:
        """Получить список групп факультета"""
        try:
            logger.info(f"🔍 Получение групп для факультета {faculty_id} института {institution_id}")
            
            if not await self.validate_uuid(institution_id):
                logger.error(f"❌ Неверный формат ID института: {institution_id}")
                return []
                
            if not await self.validate_uuid(faculty_id):
                logger.error(f"❌ Неверный формат ID факультета: {faculty_id}")
                return []
            
            groups = await self.client.request("GET", f"institutions/{institution_id}/faculties/{faculty_id}/groups") or []
            
            if groups:
                logger.info(f"✅ Получено {len(groups)} групп для факультета {faculty_id}")
                for group in groups[:3]:
                    logger.info(f"  - {group.get('title')} ({group.get('abbreviation')})")
            else:
                logger.warning(f"⚠️ Не удалось получить группы для факультета {faculty_id}")
            
            return groups
        except Exception as e:
            logger.error(f"💥 Ошибка получения групп: {e}")
            return []

    async def get_student_by_max_id(self, max_id: int) -> Optional[str]:
        """Получить ID студента по MAX ID"""
        logger.info(f"🔍 Поиск студента по MAX ID: {max_id}")
        result = await self.client.request("GET", f"students/max/{max_id}")
        if result and "id" in result:
            logger.info(f"✅ Студент найден: {result['id']}")
            return result["id"]
        else:
            logger.info("❌ Студент не найден по MAX ID")
            return None

    async def register_student(self, max_id: int, full_name: str = None) -> Optional[str]:
        """Зарегистрировать студента в системе StudGram"""
        try:
            logger.info(f"📝 Регистрация студента: MAX ID={max_id}, ФИО={full_name}")

            existing_student = await self.get_student_by_max_id(max_id)
            if existing_student:
                logger.info(f"✅ Студент с MAX ID {max_id} уже существует: {existing_student}")
                return existing_student
            
            data = {"maxId": max_id}
            if full_name:
                data["fullName"] = full_name
                
            logger.info(f"📤 Отправка данных: {data}")
            result = await self.client.request("POST", "students", data)
            
            if result and "id" in result:
                logger.info(f"✅ Студент зарегистрирован: {result['id']}")
                return result["id"]
            else:
                logger.error("❌ Не удалось зарегистрировать студента")
                if result:
                    logger.error(f"Ответ API: {result}")
                return None
                
        except Exception as e:
            logger.error(f"💥 Ошибка регистрации студента: {e}")
            return None

    async def get_student_data(self, student_id: str) -> Optional[dict]:
        """Получить полные данные студента с обработкой 404"""
        logger.info(f"🔍 Получение данных студента: {student_id}")
        result = await self.client.request("GET", f"students/{student_id}")
        
        if result is None:
            logger.warning(f"⚠️ Студент {student_id} не найден в системе")

            await self._start_reregistration(student_id)
            return None
            
        if result:
            logger.info(f"✅ Данные студента получены")
            return result
        else:
            logger.error("❌ Не удалось получить данные студента")
            return None

    async def update_student(self, student_id: str, **kwargs) -> bool:
        """Обновить данные студента"""
        logger.info(f"✏️ Обновление студента {student_id}: {kwargs}")
        result = await self.client.request("PATCH", f"students/{student_id}", kwargs)
        success = result is not None
        if success:
            logger.info("✅ Данные студента обновлены")
        else:
            logger.error("❌ Не удалось обновить данные студента")
        return success
    
    async def link_student_to_institution(self, student_id: str, institution_id: str) -> bool:
        """Прикрепить студента к учебному заведению"""
        try:
            logger.info(f"🏫 Прикрепление студента {student_id} к учреждению {institution_id}")

            logger.info("Проверяем существование студента...")
            student_exists = await self.check_student_exists(student_id)
            if not student_exists:
                logger.error("❌ Студент не найден в системе")
                return False
            logger.info("✅ Студент существует")

            logger.info("Проверяем существование учебного заведения...")
            institution_exists = await self.check_institution_exists(institution_id)
            if not institution_exists:
                logger.error("❌ Учебное заведение не найдено")
                return False
            logger.info("✅ Учебное заведение существует")

            logger.info("Открепляем от текущего учреждения...")
            await self.client.request("DELETE", f"students/{student_id}/institution")

            logger.info("Прикрепляем к новому учреждению...")
            result = await self.client.request(
                "POST", 
                f"students/{student_id}/institution/{institution_id}"
            )
            
            if result is not None:
                logger.info("✅ Студент успешно прикреплен к учреждению")
                return True
            else:
                logger.error("❌ Не удалось прикрепить студента к учреждению")
                return False
                
        except Exception as e:
            logger.error(f"💥 Ошибка при прикреплении студента к учреждению: {e}")
            return False

    async def link_student_to_faculty(self, student_id: str, faculty_id: str) -> bool:
        """Прикрепить студента к факультету"""
        try:
            logger.info(f"📚 ПРИКРЕПЛЕНИЕ К ФАКУЛЬТЕТУ: студент={student_id}, факультет={faculty_id}")

            logger.info("1. Проверяем существование студента...")
            if not await self.check_student_exists(student_id):
                logger.error("❌ Студент не найден в системе")
                return False
            logger.info("✅ Студент существует")

            logger.info("2. Проверяем прикрепление к институту...")
            institution = await self.get_student_institution(student_id)
            if not institution:
                logger.error("❌ Студент не прикреплен к институту! Сначала прикрепите к институту.")
                return False
            logger.info(f"✅ Студент прикреплен к институту: {institution.get('title')}")

            logger.info("3. Проверяем существование факультета...")
            if not await self.check_faculty_exists(faculty_id):
                logger.error(f"❌ Факультет с ID {faculty_id} не найден")
                return False
            logger.info("✅ Факультет существует")

            logger.info("4. Открепляем от текущего факультета...")
            current_faculty = await self.get_student_faculty(student_id)
            if current_faculty:
                logger.info(f"📋 Текущий факультет: {current_faculty.get('title')}")

                if current_faculty.get('id') == faculty_id:
                    logger.info("✅ Студент уже прикреплен к этому факультету")
                    return True

                delete_url = f"students/{student_id}/faculty"
                logger.info(f"   DELETE запрос: {delete_url}")
                
                delete_result = await self.client.request("DELETE", delete_url)
                if delete_result is not None:
                    logger.info("✅ Успешно откреплен от факультета")
                    await asyncio.sleep(1)
                else:
                    logger.warning("⚠️ Не удалось открепить от факультета")
            else:
                logger.info("📋 Студент не прикреплен к факультету")

            logger.info("5. Прикрепляем к новому факультету...")
            attach_url = f"students/{student_id}/faculty/{faculty_id}"
            logger.info(f"   POST запрос: {attach_url}")
            
            result = await self.client.request("POST", attach_url)
            
            logger.info(f"📋 Ответ API: {result}")

            if result is not None and isinstance(result, dict) and "id" in result:
                logger.info("✅ СТУДЕНТ УСПЕШНО ПРИКРЕПЛЕН К ФАКУЛЬТЕТУ!")
                logger.info(f"🎉 Факультет: {result.get('title')} ({result.get('abbreviation')})")
                return True
            else:
                logger.error(f"❌ НЕ УДАЛОСЬ ПРИКРЕПИТЬ СТУДЕНТА К ФАКУЛЬТЕТУ")
                logger.error(f"   Ответ: {result}")
                return False
                
        except Exception as e:
            logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА при прикреплении к факультету: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def link_student_to_group(self, student_id: str, group_id: str) -> bool:
        """Прикрепить студента к группе"""
        try:
            logger.info(f"👥 ПРИКРЕПЛЕНИЕ К ГРУППЕ: студент={student_id}, группа={group_id}")
            
            logger.info("1. Проверяем существование студента...")
            if not await self.check_student_exists(student_id):
                logger.error("❌ Студент не найден в системе")
                return False
            logger.info("✅ Студент существует")

            logger.info("2. Проверяем прикрепление к факультету...")
            faculty = await self.get_student_faculty(student_id)
            if not faculty:
                logger.error("❌ Студент не прикреплен к факультету! Сначала прикрепите к факультету.")
                return False
            logger.info(f"✅ Студент прикреплен к факультету: {faculty.get('title')}")

            logger.info("3. Проверяем существование группы...")
            if not await self.check_group_exists(group_id):
                logger.error(f"❌ Группа с ID {group_id} не найдена")
                return False
            logger.info("✅ Группа существует")

            logger.info("4. Открепляем от текущей группы...")
            current_group = await self.get_student_group(student_id)
            if current_group:
                logger.info(f"📋 Текущая группа: {current_group.get('title')}")

                if current_group.get('id') == group_id:
                    logger.info("✅ Студент уже прикреплен к этой группе")
                    return True

                delete_url = f"students/{student_id}/group"
                logger.info(f"   DELETE запрос: {delete_url}")
                
                delete_result = await self.client.request("DELETE", delete_url)
                if delete_result is not None:
                    logger.info("✅ Успешно откреплен от группы")
                    await asyncio.sleep(1)
                else:
                    logger.warning("⚠️ Не удалось открепить от группы")
            else:
                logger.info("📋 Студент не прикреплен к группе")

            logger.info("5. Прикрепляем к новой группе...")
            attach_url = f"students/{student_id}/group/{group_id}"
            logger.info(f"   POST запрос: {attach_url}")
            
            result = await self.client.request("POST", attach_url)
            
            logger.info(f"📋 Ответ API: {result}")

            if result is not None and isinstance(result, dict) and "id" in result:
                logger.info("✅ СТУДЕНТ УСПЕШНО ПРИКРЕПЛЕН К ГРУППЕ!")
                logger.info(f"🎉 Группа: {result.get('title')} ({result.get('abbreviation')})")
                return True
            else:
                logger.error(f"❌ НЕ УДАЛОСЬ ПРИКРЕПИТЬ СТУДЕНТА К ГРУППЕ")
                logger.error(f"   Ответ: {result}")
                return False
                
        except Exception as e:
            logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА при прикреплении к группе: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def get_student_faculty(self, student_id: str) -> Optional[dict]:
        """Получить информацию о факультете студента с обработкой 404 ошибки"""
        try:
            logger.info(f"🔍 Получение факультета студента {student_id}")
            result = await self.client.request("GET", f"students/{student_id}/faculty")

            if result is None:
                logger.warning(f"⚠️ Факультет студента {student_id} не найден")

                await self._start_reregistration(student_id)
                return None
            
            if "id" in result:
                logger.info(f"✅ Факультет студента: {result.get('title')} ({result.get('abbreviation')})")
                return result
            else:
                logger.info("❌ Некорректный ответ при получении факультета")
                return None
                
        except Exception as e:
            logger.error(f"💥 Ошибка получения факультета студента: {e}")
            return None

    async def get_student_group(self, student_id: str) -> Optional[dict]:
        """Получить информацию о группе студента с обработкой 404 ошибки"""
        try:
            logger.info(f"🔍 Получение группы студента {student_id}")
            result = await self.client.request("GET", f"students/{student_id}/group")

            if result is None:
                logger.warning(f"⚠️ Группа студента {student_id} не найдена")

                await self._start_reregistration(student_id)
                return None
            
            if "id" in result:
                logger.info(f"✅ Группа студента: {result.get('title')} ({result.get('abbreviation')})")
                return result
            else:
                logger.info("❌ Некорректный ответ при получении группы")
                return None
                
        except Exception as e:
            logger.error(f"💥 Ошибка получения группы студента: {e}")
            return None

    async def get_student_institution(self, student_id: str) -> Optional[dict]:
        """Получить информацию об учебном заведении студента с обработкой 404"""
        try:
            logger.info(f"🔍 Получение учебного заведения студента {student_id}")
            result = await self.client.request("GET", f"students/{student_id}/institution")

            if result is None:
                logger.warning(f"⚠️ Учебное заведение студента {student_id} не найдено")

                await self._start_reregistration(student_id)
                return None
            
            if "id" in result:
                logger.info(f"✅ Учебное заведение студента: {result.get('title')} ({result.get('abbreviation')})")
                return result
            else:
                logger.info("❌ Некорректный ответ при получении учебного заведения")
                return None
                
        except Exception as e:
            logger.error(f"💥 Ошибка получения учебного заведения студента: {e}")
            return None

    async def _start_reregistration(self, student_id: str):
        """Запускает процесс перерегистрации для студента"""
        try:
            logger.info(f"🚀 Запуск перерегистрации для студента {student_id}")

            user = None
            user_id_found = None
            
            for user_id, user_obj in users_db.items():
                if hasattr(user_obj, 'system_id') and user_obj.system_id == student_id:
                    user = user_obj
                    user_id_found = user_id
                    break
            
            if user and user_id_found:
                chat_id = None
                for chat_id_key, user_id_val in active_chats.items():
                    if user_id_val == user_id_found:
                        chat_id = chat_id_key
                        break
                
                if chat_id:
                    logger.info(f"✅ Найден chat_id {chat_id} для перерегистрации")
                    from services.bot_service import BotService
                    import inspect
                    if any(param.name == 'bot' for param in inspect.signature(BotService.__init__).parameters.values()):
                        bot_service = BotService(None)
                    else:
                        bot_service = BotService()
                    await bot_service._handle_student_not_found(chat_id, user)
                else:
                    logger.warning(f"Не найден chat_id для пользователя {user_id_found}")
            else:
                logger.warning(f"Не найден пользователь с system_id {student_id}")
                    
        except Exception as e:
            logger.error(f"Ошибка запуска перерегистрации: {e}")

    async def check_student_exists(self, student_id: str) -> bool:
        """Проверяет существование студента"""
        result = await self.client.request("GET", f"students/{student_id}")
        return result is not None

    async def check_institution_exists(self, institution_id: str) -> bool:
        """Проверяет существование учебного заведения"""
        institutions = await self.get_institutions()
        return any(inst["id"] == institution_id for inst in institutions)
    
    async def validate_uuid(self, uuid_string: str) -> bool:
        """Проверяет валидность UUID"""
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            logger.error(f"❌ Неверный формат UUID: {uuid_string}")
            return False

    async def get_faculty_directly(self, faculty_id: str) -> Optional[dict]:
        """Получить факультет напрямую по ID"""
        try:
            logger.info(f"🔍 Прямой запрос факультета по ID: {faculty_id}")
            result = await self.client.request("GET", f"faculties/{faculty_id}")
            
            if result is None:
                logger.warning(f"❌ Факультет с ID {faculty_id} не найден")
                return None
                
            if "id" in result:
                logger.info(f"✅ Факультет найден: {result.get('title')} ({result.get('abbreviation')})")
                return result
            else:
                logger.warning(f"❌ Некорректный ответ для факультета {faculty_id}")
                return None
        except Exception as e:
            logger.error(f"Ошибка прямого запроса факультета: {e}")
            return None

    async def get_group_directly(self, group_id: str) -> Optional[dict]:
        """Получить группу напрямую по ID"""
        try:
            logger.info(f"🔍 Прямой запрос группы по ID: {group_id}")
            result = await self.client.request("GET", f"groups/{group_id}")
            
            if result is None:
                logger.warning(f"❌ Группа с ID {group_id} не найдена")
                return None
                
            if "id" in result:
                logger.info(f"✅ Группа найдена: {result.get('title')} ({result.get('abbreviation')})")
                return result
            else:
                logger.warning(f"❌ Некорректный ответ для группы {group_id}")
                return None
        except Exception as e:
            logger.error(f"Ошибка прямого запроса группы: {e}")
            return None

    async def check_faculty_exists(self, faculty_id: str) -> bool:
        """Проверяет существование факультета"""
        try:
            logger.info(f"🔍 Проверка существования факультета {faculty_id}")
            
            faculty = await self.get_faculty_directly(faculty_id)
            if faculty:
                logger.info(f"✅ Факультет найден напрямую: {faculty.get('title')}")
                return True
                
            institutions = await self.get_institutions()
            if not institutions:
                logger.error("❌ Не удалось получить список институтов")
                return False
                
            for institution in institutions:
                faculties = await self.get_faculties(institution["id"])
                for faculty in faculties:
                    if faculty["id"] == faculty_id:
                        logger.info(f"✅ Факультет найден: {faculty.get('title')} в {institution.get('title')}")
                        return True
            
            logger.error(f"❌ Факультет с ID {faculty_id} не найден ни в одном институте")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки существования факультета: {e}")
            return False

    async def check_group_exists(self, group_id: str) -> bool:
        """Проверяет существование группы"""
        try:
            logger.info(f"🔍 Проверка существования группы {group_id}")
            
            group = await self.get_group_directly(group_id)
            if group:
                logger.info(f"✅ Группа найдена напрямую: {group.get('title')}")
                return True
                
            institutions = await self.get_institutions()
            if not institutions:
                logger.error("❌ Не удалось получить список институтов")
                return False
                
            for institution in institutions:
                faculties = await self.get_faculties(institution["id"])
                for faculty in faculties:
                    groups = await self.get_groups(institution["id"], faculty["id"])
                    for group in groups:
                        if group["id"] == group_id:
                            logger.info(f"✅ Группа найдена: {group.get('title')} в {faculty.get('title')}")
                            return True
            
            logger.error(f"❌ Группа с ID {group_id} не найдена ни в одном факультете")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки существования группы: {e}")
            return False
        
    async def debug_student_status(self, student_id: str):
        """Отладочная информация о статусе студента"""
        try:
            logger.info(f"🔍 ОТЛАДКА: Проверка статуса студента {student_id}")
            
            student_data = await self.get_student_data(student_id)
            logger.info(f"📋 Данные студента: {student_data}")
            
            institution = await self.get_student_institution(student_id)
            logger.info(f"🎓 Прикреплен к институту: {institution}")
            
            faculty = await self.get_student_faculty(student_id)
            logger.info(f"📚 Прикреплен к факультету: {faculty}")

            group = await self.get_student_group(student_id)
            logger.info(f"👥 Прикреплен к группе: {group}")
            
            return {
                'student': student_data,
                'institution': institution,
                'faculty': faculty,
                'group': group
            }
        except Exception as e:
            logger.error(f"💥 Ошибка отладки статуса студента: {e}")
            return None

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
        
    async def get_student_application_status(self, student_id: str) -> Optional[bool]:
        """Получить статус заявки студента (подтверждена ли администратором)"""
        try:
            logger.info(f"🔍 Проверка статуса заявки студента: {student_id}")
            result = await self.client.request("GET", f"students/{student_id}/status")
            
            if result and "approved" in result:
                is_approved = result["approved"]
                logger.info(f"✅ Статус заявки студента {student_id}: {'ОДОБРЕНА' if is_approved else 'НА РАССМОТРЕНИИ'}")
                return is_approved
            else:
                logger.warning(f"⚠️ Не удалось получить статус заявки для студента {student_id}")
                return None
                
        except Exception as e:
            logger.error(f"💥 Ошибка при проверке статуса заявки: {e}")
            return None
        
    async def get_student_subjects(self, student_id: str) -> List[dict]:
        """Получить список дисциплин студента с содержимым"""
        try:
            logger.info(f"🔍 Получение дисциплин студента: {student_id}")
            subjects = await self.client.request("GET", f"students/{student_id}/subjects")
            
            if subjects is None:
                logger.warning(f"⚠️ Дисциплины студента {student_id} не найдены")
                return []
            
            if isinstance(subjects, list):
                logger.info(f"✅ Получено {len(subjects)} дисциплин")
                
                enriched_subjects = []
                for subject in subjects:
                    if subject.get('id'):
                        content_data = await self.get_subject_content(student_id, subject['id'])
                        if content_data and content_data.get('content'):
                            subject['content'] = content_data['content']
                        if content_data:
                            subject.update({k: v for k, v in content_data.items() if k != 'id'})
                    
                    enriched_subjects.append(subject)
                
                return enriched_subjects
            else:
                logger.warning(f"❌ Некорректный формат ответа для дисциплин: {subjects}")
                return []
                
        except Exception as e:
            logger.error(f"💥 Ошибка получения дисциплин студента: {e}")
            return []
    
    async def get_subject_content(self, student_id: str, subject_id: str) -> Optional[dict]:
        """Получить содержимое дисциплины"""
        try:
            logger.info(f"🔍 Получение содержимого дисциплины: студент={student_id}, дисциплина={subject_id}")
            result = await self.client.request("GET", f"students/{student_id}/subjects/{subject_id}")
            
            if result is None:
                logger.warning(f"⚠️ Содержимое дисциплины {subject_id} не найдено")
                return None
            
            if isinstance(result, dict):
                logger.info(f"✅ Содержимое дисциплины получено")
                return result
            else:
                logger.warning(f"❌ Некорректный формат ответа для содержимого дисциплины: {result}")
                return None
                
        except Exception as e:
            logger.error(f"💥 Ошибка получения содержимого дисциплины: {e}")
            return None