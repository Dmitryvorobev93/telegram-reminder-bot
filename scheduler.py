from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
import logging
from database import Database

class ReminderScheduler:
    def __init__(self, bot):
        self.scheduler = BackgroundScheduler()
        self.db = Database()
        self.bot = bot
        self.start_scheduler()

    def start_scheduler(self):
        """Запуск планировщика"""
        self.scheduler.start()
        logging.info("Scheduler started")

    def add_reminder(self, user_id, reminder_text, reminder_time, reminder_id):
        """Добавление напоминания в планировщик"""
        trigger = DateTrigger(run_date=reminder_time)
        
        self.scheduler.add_job(
            self.send_reminder,
            trigger,
            id=str(reminder_id),
            args=[user_id, reminder_text, reminder_id]
        )
        
        logging.info(f"Reminder scheduled for {reminder_time}")

    async def send_reminder(self, user_id, reminder_text, reminder_id):
        """Отправка напоминания пользователю"""
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=f"🔔 Напоминание: {reminder_text}"
            )
            self.db.mark_completed(reminder_id)
            logging.info(f"Reminder sent to user {user_id}")
        except Exception as e:
            logging.error(f"Failed to send reminder: {e}")

    def shutdown(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()