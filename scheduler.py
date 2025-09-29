from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import logging
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

    def restore_pending_reminders(self):
        """Восстановление напоминаний при перезапуске бота"""
        try:
            reminders = self.db.get_pending_reminders()
            for rem_id, user_id, text, reminder_time, repeat_type, notify_before in reminders:
                reminder_time = datetime.strptime(reminder_time, '%Y-%m-%d %H:%M:%S')
                
                # Основное напоминание
                self.add_reminder(user_id, text, reminder_time, rem_id)
                
                # Уведомление за N минут
                if notify_before > 0:
                    notify_time = reminder_time - timedelta(minutes=notify_before)
                    if notify_time > datetime.now():
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
                self.send_reminder,
                trigger,
                id=job_id,
                args=[user_id, reminder_text, reminder_id, is_notification]
            )
            
            logging.info(f"Reminder scheduled for {reminder_time} (notification: {is_notification})")
        except Exception as e:
            logging.error(f"Error scheduling reminder: {e}")

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
                if reminder and reminder[6] == 'once':  # repeat_type
                    self.db.update_reminder_status(reminder_id, 'completed')
                elif reminder and reminder[6] != 'once':
                    # Для повторяющихся - создаем следующее напоминание
                    self.schedule_next_repetition(reminder_id, reminder)
            
            await self.bot.send_message(chat_id=user_id, text=message)
            logging.info(f"Reminder sent to user {user_id} (notification: {is_notification})")
            
        except Exception as e:
            logging.error(f"Failed to send reminder: {e}")

    def schedule_next_repetition(self, reminder_id, reminder):
        """Планирование следующего повторения"""
        try:
            user_id, reminder_text, reminder_time, category, repeat_type, status, notify_before = reminder[1:8]
            next_time = TimeParser.calculate_next_reminder(
                datetime.strptime(reminder_time, '%Y-%m-%d %H:%M:%S'), 
                repeat_type
            )
            
            if next_time:
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