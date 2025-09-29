import sqlite3
import logging
from datetime import datetime

class Database:
    def __init__(self, db_name='reminders.db'):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reminder_text TEXT NOT NULL,
                reminder_time DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_completed BOOLEAN DEFAULT FALSE
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")

    def add_reminder(self, user_id, reminder_text, reminder_time):
        """Добавление напоминания в базу"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reminders (user_id, reminder_text, reminder_time)
            VALUES (?, ?, ?)
        ''', (user_id, reminder_text, reminder_time))
        
        reminder_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return reminder_id

    def get_pending_reminders(self):
        """Получение всех ожидающих напоминаний"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_id, reminder_text, reminder_time 
            FROM reminders 
            WHERE is_completed = FALSE AND reminder_time <= datetime('now', '+1 hour')
            ORDER BY reminder_time
        ''')
        
        reminders = cursor.fetchall()
        conn.close()
        
        return reminders

    def mark_completed(self, reminder_id):
        """Пометить напоминание как выполненное"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE reminders 
            SET is_completed = TRUE 
            WHERE id = ?
        ''', (reminder_id,))
        
        conn.commit()
        conn.close()

    def get_user_reminders(self, user_id):
        """Получить напоминания пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, reminder_text, reminder_time, is_completed
            FROM reminders 
            WHERE user_id = ?
            ORDER BY reminder_time
        ''', (user_id,))
        
        reminders = cursor.fetchall()
        conn.close()
        
        return reminders