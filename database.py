import sqlite3
import logging
import os
import shutil
from datetime import datetime
from config import Config

class Database:
    def __init__(self, db_name=None):
        self.db_name = db_name or Config.DB_PATH
        # Создаем директорию для базы данных если её нет
        os.makedirs(os.path.dirname(self.db_name), exist_ok=True)
        self.init_db()

    def init_db(self):
        """Инициализация улучшенной базы данных"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Основная таблица напоминаний
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reminder_text TEXT NOT NULL,
                reminder_time DATETIME NOT NULL,
                category TEXT DEFAULT 'other',
                repeat_type TEXT DEFAULT 'once',
                status TEXT DEFAULT 'active',
                notify_before INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для статистики
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                total_reminders INTEGER DEFAULT 0,
                completed_reminders INTEGER DEFAULT 0,
                cancelled_reminders INTEGER DEFAULT 0,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для бэкапов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                size_kb INTEGER,
                reminder_count INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info(f"Database initialized successfully at {self.db_name}")

    def create_backup(self):
        """Создание бэкапа базы данных"""
        try:
            # Создаем директорию для бэкапов если её нет
            os.makedirs(Config.BACKUP_DIR, exist_ok=True)
            
            # Генерируем имя файла с timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"reminders_backup_{timestamp}.db"
            backup_path = os.path.join(Config.BACKUP_DIR, backup_filename)
            
            # Копируем базу данных
            shutil.copy2(self.db_name, backup_path)
            
            # Получаем статистику бэкапа
            file_size = os.path.getsize(backup_path) // 1024  # размер в KB
            reminder_count = self.get_total_reminders_count()
            
            # Сохраняем информацию о бэкапе
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO backup_history (filename, size_kb, reminder_count)
                VALUES (?, ?, ?)
            ''', (backup_filename, file_size, reminder_count))
            conn.commit()
            conn.close()
            
            logging.info(f"Backup created: {backup_path} ({file_size} KB, {reminder_count} reminders)")
            return backup_filename, file_size, reminder_count
            
        except Exception as e:
            logging.error(f"Error creating backup: {e}")
            return None

    def get_backup_list(self):
        """Получение списка бэкапов"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT filename, created_at, size_kb, reminder_count 
                FROM backup_history 
                ORDER BY created_at DESC
            ''')
            backups = cursor.fetchall()
            conn.close()
            return backups
        except Exception as e:
            logging.error(f"Error getting backup list: {e}")
            return []

    def restore_from_backup(self, backup_filename):
        """Восстановление из бэкапа"""
        try:
            backup_path = os.path.join(Config.BACKUP_DIR, backup_filename)
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Создаем бэкап текущей базы
            current_backup = self.create_backup()
            
            # Заменяем текущую базу данных бэкапом
            shutil.copy2(backup_path, self.db_name)
            
            logging.info(f"Database restored from backup: {backup_filename}")
            return True
            
        except Exception as e:
            logging.error(f"Error restoring from backup: {e}")
            return False

    def get_total_reminders_count(self):
        """Получение общего количества напоминаний"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM reminders')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logging.error(f"Error getting reminders count: {e}")
            return 0

    # Остальные методы остаются без изменений
    def add_reminder(self, user_id, reminder_text, reminder_time, category='other', repeat_type='once', notify_before=0):
        """Добавление напоминания с дополнительными параметрами"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reminders (user_id, reminder_text, reminder_time, category, repeat_type, notify_before)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, reminder_text, reminder_time, category, repeat_type, notify_before))
        
        reminder_id = cursor.lastrowid
        
        # Обновляем статистику
        cursor.execute('''
            INSERT OR REPLACE INTO user_stats (user_id, total_reminders, last_active)
            VALUES (?, COALESCE((SELECT total_reminders FROM user_stats WHERE user_id = ?), 0) + 1, CURRENT_TIMESTAMP)
        ''', (user_id, user_id))
        
        conn.commit()
        conn.close()
        
        return reminder_id

    def get_reminder(self, reminder_id):
        """Получение конкретного напоминания"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM reminders WHERE id = ?
        ''', (reminder_id,))
        
        reminder = cursor.fetchone()
        conn.close()
        
        return reminder

    def get_user_reminders(self, user_id, status=None):
        """Получить напоминания пользователя с фильтрацией по статусу"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT id, reminder_text, reminder_time, category, repeat_type, status
                FROM reminders 
                WHERE user_id = ? AND status = ?
                ORDER BY reminder_time
            ''', (user_id, status))
        else:
            cursor.execute('''
                SELECT id, reminder_text, reminder_time, category, repeat_type, status
                FROM reminders 
                WHERE user_id = ?
                ORDER BY reminder_time
            ''', (user_id,))
        
        reminders = cursor.fetchall()
        conn.close()
        
        return reminders

    def update_reminder_status(self, reminder_id, status):
        """Обновление статуса напоминания"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE reminders 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, reminder_id))
        
        # Обновляем статистику
        if status == 'completed':
            cursor.execute('''
                UPDATE user_stats 
                SET completed_reminders = completed_reminders + 1
                WHERE user_id = (SELECT user_id FROM reminders WHERE id = ?)
            ''', (reminder_id,))
        elif status == 'cancelled':
            cursor.execute('''
                UPDATE user_stats 
                SET cancelled_reminders = cancelled_reminders + 1
                WHERE user_id = (SELECT user_id FROM reminders WHERE id = ?)
            ''', (reminder_id,))
        
        conn.commit()
        conn.close()

    def delete_reminder(self, reminder_id):
        """Удаление напоминания"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
        conn.commit()
        conn.close()

    def update_reminder(self, reminder_id, **kwargs):
        """Обновление напоминания"""
        if not kwargs:
            return
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [reminder_id]
        
        cursor.execute(f'''
            UPDATE reminders 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', values)
        
        conn.commit()
        conn.close()

    def get_user_stats(self, user_id):
        """Получение статистики пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Основная статистика
        cursor.execute('''
            SELECT total_reminders, completed_reminders, cancelled_reminders
            FROM user_stats 
            WHERE user_id = ?
        ''', (user_id,))
        
        stats = cursor.fetchone()
        
        # Статистика по категориям
        cursor.execute('''
            SELECT category, COUNT(*) 
            FROM reminders 
            WHERE user_id = ? 
            GROUP BY category
        ''', (user_id,))
        
        categories = cursor.fetchall()
        
        conn.close()
        
        if stats:
            return {
                'total': stats[0],
                'completed': stats[1],
                'cancelled': stats[2],
                'active': stats[0] - stats[1] - stats[2],
                'categories': dict(categories)
            }
        return {
            'total': 0, 'completed': 0, 'cancelled': 0, 'active': 0, 'categories': {}
        }

    def get_pending_reminders(self):
        """Получение всех ожидающих напоминаний (для планировщика)"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_id, reminder_text, reminder_time, repeat_type, notify_before
            FROM reminders 
            WHERE status = 'active' AND reminder_time <= datetime('now', '+1 hour')
            ORDER BY reminder_time
        ''')
        
        reminders = cursor.fetchall()
        conn.close()
        
        return reminders