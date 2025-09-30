from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import logging
import asyncio
from database import Database
from utils import TimeParser

class ReminderScheduler:
    def __init__(self, bot):
        self.scheduler = BackgroundScheduler()
        self.db = Database()
        self.bot = bot
        self.start_scheduler()
        self.restore_pending_reminders()

    def start_scheduler(self):
        """Запуск планировщика"""
        self.scheduler.start()
        logging.info("Scheduler started")

    # В методе restore_pending_reminders и других местах, где проверяется время:
def restore_pending_reminders(self):
    """Восстановление напоминаний при перезапуске бота"""
    try:
        reminders = self.db.get_pending_reminders()
        for rem_id, user_id, text, reminder_time, repeat_type, notify_before in reminders:
            # Исправляем парсинг времени
            try:
                if '.' in reminder_time:
                    reminder_time_obj = datetime.strptime(reminder_time, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    reminder_time_obj = datetime.strptime(reminder_time, '%Y-%m-%d %H:%M:%S')
            except ValueError as e:
                logging.error(f"Ошибка парсинга времени {reminder_time}: {e}")
                continue
            
            # Основное напоминание
            self.add_reminder(user_id, text, reminder_time_obj, rem_id)
            
            # Уведомление за N минут
            if notify_before > 0:
                notify_time = reminder_time_obj - timedelta(minutes=notify_before)
                if notify_time > datetime.utcnow():  # Используем UTC
                    self.add_notification(user_id, text, notify_time, rem_id, is_notification=True)
        
        logging.info(f"Restored {len(reminders)} pending reminders")
    except Exception as e:
        logging.error(f"Error restoring reminders: {e}")

    def add_reminder(self, user_id, reminder_text, reminder_time, reminder_id, is_notification=False):
        """Добавление напоминания в планировщик"""
        try:
            trigger = DateTrigger(run_date=reminder_time)
            
            job_id = f"notify_{reminder_id}" if is_notification else str(reminder_id)
            
            self.scheduler.add_job(
                self.send_reminder_wrapper,  # Изменено на обертку
                trigger,
                id=job_id,
                args=[user_id, reminder_text, reminder_id, is_notification]
            )
            
            logging.info(f"Reminder scheduled for {reminder_time} (notification: {is_notification})")
        except Exception as e:
            logging.error(f"Error scheduling reminder: {e}")

    def send_reminder_wrapper(self, user_id, reminder_text, reminder_id, is_notification=False):
        """Обертка для асинхронной отправки напоминания"""
        asyncio.run(self.send_reminder(user_id, reminder_text, reminder_id, is_notification))

    def add_notification(self, user_id, reminder_text, notify_time, reminder_id, is_notification=True):
        """Добавление уведомления заранее"""
        self.add_reminder(user_id, reminder_text, notify_time, reminder_id, is_notification)

    async def send_reminder(self, user_id, reminder_text, reminder_id, is_notification=False):
        """Отправка напоминания пользователю"""
        try:
            if is_notification:
                message = f"🔔 Скоро напоминание: {reminder_text}"
            else:
                message = f"⏰ Напоминание: {reminder_text}"
                
                # Помечаем как выполненное для одноразовых напоминаний
                reminder = self.db.get_reminder(reminder_id)
                if reminder and reminder[5] == 'once':  # repeat_type находится в 5-й позиции
                    self.db.update_reminder_status(reminder_id, 'completed')
                elif reminder and reminder[5] != 'once':
                    # Для повторяющихся - создаем следующее напоминание
                    self.schedule_next_repetition(reminder_id, reminder)
            
            await self.bot.send_message(chat_id=user_id, text=message)
            logging.info(f"Reminder sent to user {user_id} (notification: {is_notification})")
            
        except Exception as e:
            logging.error(f"Failed to send reminder: {e}")

    def schedule_next_repetition(self, reminder_id, reminder):
        """Планирование следующего повторения"""
        try:
            user_id, reminder_text, reminder_time_str, category, repeat_type, status = reminder[1:7]
            
            # Исправляем парсинг времени
            try:
                if '.' in reminder_time_str:
                    reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError as e:
                logging.error(f"Ошибка парсинга времени для повторения: {e}")
                return
            
            next_time = TimeParser.calculate_next_reminder(reminder_time, repeat_type)
            
            if next_time:
                # Получаем notify_before из базы
                full_reminder = self.db.get_reminder(reminder_id)
                notify_before = full_reminder[7] if len(full_reminder) > 7 else 0
                
                # Создаем новое напоминание для следующего повторения
                new_reminder_id = self.db.add_reminder(
                    user_id, reminder_text, next_time, category, repeat_type, notify_before
                )
                
                # Планируем его
                self.add_reminder(user_id, reminder_text, next_time, new_reminder_id)
                
                # Уведомление заранее
                if notify_before > 0:
                    notify_time = next_time - timedelta(minutes=notify_before)
                    self.add_notification(user_id, reminder_text, notify_time, new_reminder_id, True)
                
                logging.info(f"Scheduled next repetition for reminder {new_reminder_id} at {next_time}")
                
        except Exception as e:
            logging.error(f"Error scheduling next repetition: {e}")

    def cancel_reminder(self, reminder_id):
        """Отмена напоминания в планировщике"""
        try:
            # Удаляем основное напоминание
            if self.scheduler.get_job(str(reminder_id)):
                self.scheduler.remove_job(str(reminder_id))
            
            # Удаляем уведомление
            notification_job_id = f"notify_{reminder_id}"
            if self.scheduler.get_job(notification_job_id):
                self.scheduler.remove_job(notification_job_id)
                
            logging.info(f"Cancelled reminder {reminder_id}")
        except Exception as e:
            logging.error(f"Error cancelling reminder: {e}")

    def shutdown(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()