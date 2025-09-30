import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_IDS = [890219846]  # Замени на свой ID
    TIMEZONE = 'Europe/Moscow'
    
    # Пути к данным
    DB_PATH = os.getenv('DB_PATH', 'reminders.db')
    BACKUP_DIR = os.getenv('BACKUP_DIR', 'backups')
    
    # Настройки повторений
    REPEAT_OPTIONS = {
        'once': 'Один раз',
        'daily': 'Ежедневно',
        'weekly': 'Еженедельно',
        'monthly': 'Ежемесячно',
        'yearly': 'Ежегодно'
    }
    
    # Категории
    CATEGORIES = {
        'work': '💼 Работа',
        'personal': '👨‍👩‍👧‍👦 Личное',
        'health': '🏥 Здоровье',
        'shopping': '🛒 Покупки',
        'other': '📌 Другое'
    }