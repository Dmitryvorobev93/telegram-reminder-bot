from datetime import datetime
from enum import Enum

class RepeatType(Enum):
    ONCE = 'once'
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'

class ReminderStatus(Enum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'