from enum import Enum

class UserRole(Enum):
    STUDENT = "student"

class UserStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class RegistrationStep(Enum):
    FULL_NAME = "full_name"
    UNIVERSITY = "university"
    FACULTY="faculty"
    GROUP = "group"
    CONFIRMATION = "confirmation"

class ScheduleView(Enum):
    DAY = "day"
    WEEK = "week"

class CalendarState(Enum):
    VIEWING = "viewing"
    SELECTING_DATE = "selecting_date"