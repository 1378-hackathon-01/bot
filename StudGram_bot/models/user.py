from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .enums import UserRole, UserStatus, ScheduleView, CalendarState

@dataclass
class User:
    user_id: int
    full_name: str
    university: str
    group: str
    role: UserRole = UserRole.STUDENT
    status: UserStatus = UserStatus.PENDING
    system_id: Optional[str] = None
    faculty: Optional[str] = None
    faculty_id: Optional[str] = None
    registration_date: datetime = None
    current_schedule_date: datetime = None
    schedule_view: ScheduleView = ScheduleView.DAY
    calendar_state: CalendarState = CalendarState.VIEWING
    selected_month: datetime = None
    in_chat_mode: bool = False
    application_approved: bool = False  
    requires_reregistration: bool = False  
    
    def __post_init__(self):
        if self.registration_date is None:
            self.registration_date = datetime.now()
        if self.current_schedule_date is None:
            self.current_schedule_date = datetime.now()
        if self.selected_month is None:
            self.selected_month = datetime.now().replace(day=1)
