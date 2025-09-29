import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)
from database import Database
from scheduler import ReminderScheduler

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния для ConversationHandler
SET_REMINDER, SET_TIME = range(2)

class ReminderBot:
    def __init__(self):
        self.token = os.getenv('BOT_TOKEN')
        self.db = Database()
        self.application = Application.builder().token(self.token).build()
        self.scheduler = None
        
        # Регистрация обработчиков
        self.register_handlers()

    def register_handlers(self):
        """Регистрация всех обработчиков команд"""
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("my_reminders", self.my_reminders_command))
        
        # Обработчик для создания напоминаний
        reminder_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("remind", self.remind_command)],
            states={
                SET_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_reminder_text)],
                SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_reminder_time)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        )
        
        self.application.add_handler(reminder_conv_handler)
        
        # Обработчик обычных сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.message.from_user
        welcome_text = f"""
Привет, {user.first_name}! 👋

Я бот-напоминалка! Я помогу тебе не забывать о важных делах.

Доступные команды:
/remind - создать новое напоминание
/my_reminders - посмотреть мои напоминания
/help - помощь

Просто напиши "напомни" и я подскажу, как работать со мной!
        """
        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 *Как пользоваться ботом:*

1. *Создать напоминание:*
   Используй команду /remind
   Или просто напиши "напомни [текст] через [время]"

2. *Примеры:*
   "напомни позвонить маме через 2 часа"
   "напомни встречу завтра в 15:00"
   "напомни принять таблетки через 30 минут"

3. *Посмотреть напоминания:*
   /my_reminders - покажет все твои активные напоминания

*Поддерживаемые форматы времени:*
- Через X минут/часов/дней
- Завтра в HH:MM
- В HH:MM (на сегодня)
- DD.MM.YYYY в HH:MM
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания напоминания"""
        await update.message.reply_text(
            "О чем тебе напомнить? Напиши текст напоминания:"
        )
        return SET_REMINDER

    async def set_reminder_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка текста напоминания"""
        context.user_data['reminder_text'] = update.message.text
        await update.message.reply_text(
            "Отлично! Когда напомнить? \n\n"
            "Примеры:\n"
            "• через 2 часа\n"
            "• завтра в 15:00\n" 
            "• через 30 минут\n"
            "• 25.12.2024 в 10:00"
        )
        return SET_TIME

    async def set_reminder_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка времени напоминания и сохранение"""
        user_id = update.message.from_user.id
        reminder_text = context.user_data['reminder_text']
        time_text = update.message.text
        
        try:
            reminder_time = self.parse_time(time_text)
            reminder_id = self.db.add_reminder(user_id, reminder_text, reminder_time)
            
            # Добавляем в планировщик
            self.scheduler.add_reminder(user_id, reminder_text, reminder_time, reminder_id)
            
            await update.message.reply_text(
                f"✅ Отлично! Напоминание создано:\n"
                f"*Что:* {reminder_text}\n"
                f"*Когда:* {reminder_time.strftime('%d.%m.%Y в %H:%M')}",
                parse_mode='Markdown'
            )
            
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Не могу понять время. Попробуй еще раз!\n"
                f"Ошибка: {str(e)}\n\n"
                f"Пример правильного формата: 'через 2 часа' или 'завтра в 15:00'"
            )
            return SET_TIME
        
        return ConversationHandler.END

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания напоминания"""
        await update.message.reply_text("Создание напоминания отменено.")
        return ConversationHandler.END

    async def my_reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать напоминания пользователя"""
        user_id = update.message.from_user.id
        reminders = self.db.get_user_reminders(user_id)
        
        if not reminders:
            await update.message.reply_text("У тебя пока нет активных напоминаний.")
            return
        
        reminder_text = "📋 Твои напоминания:\n\n"
        for rem_id, text, time, completed in reminders:
            status = "✅ Выполнено" if completed else "⏳ Ожидает"
            time_str = datetime.strptime(time, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
            reminder_text += f"• {text}\n  📅 {time_str} - {status}\n\n"
        
        await update.message.reply_text(reminder_text)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений"""
        text = update.message.text.lower()
        
        if text.startswith('напомни'):
            # Пытаемся разобрать сообщение формата "напомни [текст] через [время]"
            try:
                if " через " in text:
                    parts = text.split(" через ")
                    reminder_text = parts[0].replace("напомни", "").strip()
                    time_part = "через " + parts[1]
                    
                    reminder_time = self.parse_time(time_part)
                    user_id = update.message.from_user.id
                    
                    reminder_id = self.db.add_reminder(user_id, reminder_text, reminder_time)
                    self.scheduler.add_reminder(user_id, reminder_text, reminder_time, reminder_id)
                    
                    await update.message.reply_text(
                        f"✅ Готово! Напомню: '{reminder_text}' "
                        f"{reminder_time.strftime('%d.%m.%Y в %H:%M')}"
                    )
                else:
                    await update.message.reply_text(
                        "Напиши в формате: 'напомни [текст] через [время]'\n"
                        "Например: 'напомни позвонить маме через 2 часа'"
                    )
            except ValueError as e:
                await update.message.reply_text(
                    f"❌ Не могу понять время. Используй команду /remind "
                    f"или напиши 'напомни [что] через [когда]'"
                )
        else:
            await update.message.reply_text(
                "Напиши 'напомни' чтобы создать напоминание или /help для помощи"
            )

    def parse_time(self, time_text):
        """Парсинг текстового времени в datetime"""
        time_text = time_text.lower().strip()
        now = datetime.now()
        
        if time_text.startswith('через'):
            # Формат: "через X минут/часов/дней"
            if 'минут' in time_text:
                minutes = int(''.join(filter(str.isdigit, time_text)))
                return now + timedelta(minutes=minutes)
            elif 'час' in time_text:
                hours = int(''.join(filter(str.isdigit, time_text)))
                return now + timedelta(hours=hours)
            elif 'день' in time_text or 'дня' in time_text or 'дней' in time_text:
                days = int(''.join(filter(str.isdigit, time_text)))
                return now + timedelta(days=days)
        
        elif 'завтра' in time_text:
            # Формат: "завтра в HH:MM"
            time_part = time_text.split('в ')[1]
            hours, minutes = map(int, time_part.split(':'))
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        
        elif ':' in time_text and len(time_text) <= 5:
            # Формат: "HH:MM" на сегодня
            hours, minutes = map(int, time_text.split(':'))
            reminder_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if reminder_time < now:
                reminder_time += timedelta(days=1)
            return reminder_time
        
        elif '.' in time_text:
            # Формат: "DD.MM.YYYY в HH:MM"
            date_part, time_part = time_text.split(' в ')
            day, month, year = map(int, date_part.split('.'))
            hours, minutes = map(int, time_part.split(':'))
            return datetime(year, month, day, hours, minutes)
        
        raise ValueError("Неизвестный формат времени")

    def run(self):
        """Запуск бота"""
        # Инициализация планировщика после создания application
        self.scheduler = ReminderScheduler(self.application.bot)
        
        print("Бот запущен! Нажми Ctrl+C для остановки")
        self.application.run_polling()

if __name__ == '__main__':
    bot = ReminderBot()
    bot.run()