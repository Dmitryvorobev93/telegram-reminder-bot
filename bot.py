import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

from config import Config
from database import Database
from scheduler import ReminderScheduler
from keyboards import Keyboards
from utils import TimeParser, TextFormatter

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

# Состояния для ConversationHandler
SET_REMINDER, SET_TIME, SET_CATEGORY, SET_REPEAT, SET_NOTIFICATION = range(5)

class ImprovedReminderBot:
    def __init__(self):
        self.token = Config.BOT_TOKEN
        self.db = Database()
        self.application = Application.builder().token(self.token).build()
        self.scheduler = None
        
        # Регистрация обработчиков
        self.register_handlers()

    def register_handlers(self):
        """Регистрация всех обработчиков команд"""
        # Обработчик для создания напоминаний (должен быть ПЕРВЫМ!)
        reminder_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("remind", self.remind_command),
                MessageHandler(filters.Regex('^(📝 Создать напоминание)$'), self.remind_command)
            ],
            states={
                SET_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_reminder_text)],
                SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_reminder_time)],
                SET_CATEGORY: [CallbackQueryHandler(self.set_reminder_category, pattern='^(category_|cancel)$')],
                SET_REPEAT: [CallbackQueryHandler(self.set_reminder_repeat, pattern='^(repeat_|cancel)$')],
                SET_NOTIFICATION: [CallbackQueryHandler(self.set_reminder_notification, pattern='^(notify_|cancel)$')],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        )
        
        self.application.add_handler(reminder_conv_handler)
        
        # Обработчики кнопок для остальных функций
        self.application.add_handler(CallbackQueryHandler(self.general_button_handler))
        
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("my_reminders", self.my_reminders_command))
        
        # Обработчики сообщений (должен быть ПОСЛЕДНИМ)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.message.from_user
        welcome_text = f"""
Привет, {user.first_name}! 👋

Я улучшенный бот-напоминалка! Теперь я умею:

📝 Создавать напоминания с категориями
🔄 Работать с повторяющимися напоминаниями
🔔 Уведомлять заранее о событиях
📊 Показывать статистику
✏️ Редактировать и удалять напоминания

Используй кнопки ниже или команды:
/remind - создать напоминание
/stats - посмотреть статистику
/help - помощь
        """
        await update.message.reply_text(
            welcome_text, 
            reply_markup=Keyboards.main_menu(),
            parse_mode='Markdown'
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
🤖 *Как пользоваться улучшенным ботом:*

*📝 Создание напоминания:*
1. Нажми "📝 Создать напоминание"
2. Введи текст напоминания
3. Выбери время (или введи текстом)
4. Выбери категорию
5. Настрой повторение (опционально)
6. Настрой уведомление заранее (опционально)

*📋 Управление напоминаниями:*
- Нажми "📋 Мои напоминания" чтобы посмотреть все
- Используй кнопки для управления каждым напоминанием

*🔄 Повторяющиеся напоминания:*
- Ежедневные, еженедельные, ежемесячные
- Автоматически создаются заново

*🔔 Уведомления заранее:*
- Получи уведомление за 15, 30, 60 минут до события

*📊 Статистика:*
- Отслеживай выполненные и активные напоминания
- Статистика по категориям

*Примеры быстрых команд:*
"напомни позвонить маме через 2 часа"
"напомни встречу завтра в 15:00"
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статистику пользователя"""
        user_id = update.message.from_user.id
        stats = self.db.get_user_stats(user_id)
        
        stats_text = TextFormatter.format_stats(stats)
        await update.message.reply_text(stats_text, parse_mode='Markdown')

    async def my_reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать напоминания пользователя"""
        await self.show_reminders_list(update)

    # Conversation Handlers
    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания напоминания"""
        context.user_data.clear()
        await update.message.reply_text(
            "📝 О чем тебе напомнить? Напиши текст напоминания:"
        )
        return SET_REMINDER

    async def set_reminder_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка текста напоминания"""
        context.user_data['reminder_text'] = update.message.text
        await update.message.reply_text(
            "⏰ Когда напомнить? \n\n"
            "Примеры:\n"
            "• через 2 часа\n"
            "• завтра в 15:00\n" 
            "• через 30 минут\n"
            "• 25.12.2024 в 10:00"
        )
        return SET_TIME

    async def set_reminder_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка времени напоминания"""
        time_text = update.message.text
        
        try:
            reminder_time = TimeParser.parse_time(time_text)
            context.user_data['reminder_time'] = reminder_time
            
            await update.message.reply_text(
                "📂 Выбери категорию:",
                reply_markup=Keyboards.categories()
            )
            return SET_CATEGORY
            
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Не могу понять время. Попробуй еще раз!\n"
                f"Ошибка: {str(e)}\n\n"
                f"Пример правильного формата: 'через 2 часа' или 'завтра в 15:00'"
            )
            return SET_TIME

    async def set_reminder_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора категории"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel':
            await query.edit_message_text("Создание напоминания отменено.")
            return ConversationHandler.END
        
        category = query.data.replace('category_', '')
        context.user_data['category'] = category
        
        await query.edit_message_text(
            text=f"📂 Категория: {Config.CATEGORIES.get(category, 'Другое')}\n\n"
                 "🔄 Нужно ли повторять напоминание?",
            reply_markup=Keyboards.repeat_options()
        )
        return SET_REPEAT

    async def set_reminder_repeat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора повторения"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel':
            await query.edit_message_text("Создание напоминания отменено.")
            return ConversationHandler.END
        
        repeat_type = query.data.replace('repeat_', '')
        context.user_data['repeat_type'] = repeat_type
        
        # Для одноразовых - сразу сохраняем
        if repeat_type == 'once':
            return await self.save_reminder(update, context)
        
        # Для повторяющихся - спрашиваем про уведомление
        keyboard = [
            [
                InlineKeyboardButton("За 15 минут", callback_data="notify_15"),
                InlineKeyboardButton("За 30 минут", callback_data="notify_30")
            ],
            [
                InlineKeyboardButton("За 60 минут", callback_data="notify_60"),
                InlineKeyboardButton("Не уведомлять", callback_data="notify_0")
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        
        await query.edit_message_text(
            text=f"🔄 Повтор: {Config.REPEAT_OPTIONS.get(repeat_type, '')}\n\n"
                 "🔔 Уведомить заранее?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SET_NOTIFICATION

    async def set_reminder_notification(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора уведомления"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel':
            await query.edit_message_text("Создание напоминания отменено.")
            return ConversationHandler.END
        
        notify_before = int(query.data.replace('notify_', ''))
        context.user_data['notify_before'] = notify_before
        
        return await self.save_reminder(update, context)

    async def save_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранение напоминания и завершение диалога"""
        query = update.callback_query
        
        user_id = query.from_user.id
        reminder_text = context.user_data['reminder_text']
        reminder_time = context.user_data['reminder_time']
        category = context.user_data.get('category', 'other')
        repeat_type = context.user_data.get('repeat_type', 'once')
        notify_before = context.user_data.get('notify_before', 0)
        
        # Сохраняем в базу
        reminder_id = self.db.add_reminder(
            user_id, reminder_text, reminder_time, category, repeat_type, notify_before
        )
        
        # Добавляем в планировщик
        self.scheduler.add_reminder(user_id, reminder_text, reminder_time, reminder_id)
        
        # Уведомление заранее
        if notify_before > 0:
            notify_time = reminder_time - timedelta(minutes=notify_before)
            if notify_time > datetime.now():
                self.scheduler.add_notification(user_id, reminder_text, notify_time, reminder_id, True)
        
        # Формируем сообщение об успехе
        success_text = (
            f"✅ *Напоминание создано!*\n\n"
            f"*Что:* {reminder_text}\n"
            f"*Когда:* {reminder_time.strftime('%d.%m.%Y в %H:%M')}\n"
            f"*Категория:* {Config.CATEGORIES.get(category, 'Другое')}\n"
            f"*Повтор:* {Config.REPEAT_OPTIONS.get(repeat_type, 'Один раз')}\n"
        )
        
        if notify_before > 0:
            success_text += f"*Уведомление:* за {notify_before} минут\n"
        
        success_text += f"\nID: {reminder_id}"
        
        await query.edit_message_text(
            text=success_text,
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END

    async def general_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на inline кнопки для общих функций"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == 'back_to_list':
                await self.show_user_reminders(query)
            elif data == 'create_new':
                await query.edit_message_text(
                    "Используй кнопку \"📝 Создать напоминание\" в главном меню"
                )
            elif data == 'show_stats':
                user_id = query.from_user.id
                stats = self.db.get_user_stats(user_id)
                stats_text = TextFormatter.format_stats(stats)
                await query.edit_message_text(stats_text, parse_mode='Markdown')
            elif data.startswith('complete_'):
                reminder_id = int(data.replace('complete_', ''))
                await self.complete_reminder(query, reminder_id)
            elif data.startswith('delete_'):
                reminder_id = int(data.replace('delete_', ''))
                await self.delete_reminder(query, reminder_id)
            elif data.startswith('edit_'):
                reminder_id = int(data.replace('edit_', ''))
                await self.show_edit_options(query, reminder_id)
            elif data.startswith('notify15_'):
                reminder_id = int(data.replace('notify15_', ''))
                await self.add_notification(query, reminder_id, 15)
            elif data.startswith('back_to_reminder_'):
                reminder_id = int(data.replace('back_to_reminder_', ''))
                await self.show_reminder_details(query, reminder_id)
            else:
                # Если callback не распознан, пробуем обработать как часть ConversationHandler
                if data.startswith(('category_', 'repeat_', 'notify_')):
                    await query.edit_message_text("❌ Ошибка: диалог прерван. Начни заново.")
                else:
                    await query.edit_message_text("❌ Неизвестная команда")
                
        except Exception as e:
            logging.error(f"Error in button handler: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуй еще раз.")

    async def show_user_reminders(self, query):
        """Показать напоминания пользователя"""
        user_id = query.from_user.id
        reminders = self.db.get_user_reminders(user_id, status='active')
        
        reminders_text = TextFormatter.format_reminder_list(reminders)
        
        keyboard = [
            [InlineKeyboardButton("📝 Создать новое", callback_data="create_new")],
            [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")]
        ]
        
        await query.edit_message_text(
            text=reminders_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def complete_reminder(self, query, reminder_id):
        """Отметить напоминание как выполненное"""
        self.db.update_reminder_status(reminder_id, 'completed')
        self.scheduler.cancel_reminder(reminder_id)
        
        await query.edit_message_text(
            text="✅ Напоминание отмечено как выполненное!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Назад к списку", callback_data="back_to_list")]
            ])
        )

    async def delete_reminder(self, query, reminder_id):
        """Удалить напоминание"""
        self.db.delete_reminder(reminder_id)
        self.scheduler.cancel_reminder(reminder_id)
        
        await query.edit_message_text(
            text="❌ Напоминание удалено!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Назад к списку", callback_data="back_to_list")]
            ])
        )

    async def show_edit_options(self, query, reminder_id):
        """Показать опции редактирования напоминания"""
        reminder = self.db.get_reminder(reminder_id)
        if not reminder:
            await query.edit_message_text("❌ Напоминание не найдено!")
            return
        
        await query.edit_message_text(
            text=f"✏️ Редактирование напоминания:\n\n"
                 f"Текст: {reminder[2]}\n"
                 f"Время: {reminder[3]}\n"
                 f"Что хочешь изменить?",
            reply_markup=Keyboards.edit_options(reminder_id)
        )

    async def show_reminder_details(self, query, reminder_id):
        """Показать детали напоминания"""
        reminder = self.db.get_reminder(reminder_id)
        if not reminder:
            await query.edit_message_text("❌ Напоминание не найдено!")
            return
        
        status_icons = {
            'active': '⏳',
            'completed': '✅', 
            'cancelled': '❌'
        }
        
        text = (
            f"{status_icons.get(reminder[6], '⏳')} *Детали напоминания:*\n\n"
            f"*Текст:* {reminder[2]}\n"
            f"*Время:* {reminder[3]}\n"
            f"*Категория:* {Config.CATEGORIES.get(reminder[4], 'Другое')}\n"
            f"*Повтор:* {Config.REPEAT_OPTIONS.get(reminder[5], 'Один раз')}\n"
            f"*Статус:* {reminder[6]}\n"
            f"*ID:* {reminder_id}"
        )
        
        await query.edit_message_text(
            text=text,
            parse_mode='Markdown',
            reply_markup=Keyboards.reminder_actions(reminder_id)
        )

    async def add_notification(self, query, reminder_id, minutes):
        """Добавить уведомление заранее"""
        reminder = self.db.get_reminder(reminder_id)
        if not reminder:
            await query.edit_message_text("❌ Напоминание не найдено!")
            return
        
        self.db.update_reminder(reminder_id, notify_before=minutes)
        
        # Перепланируем уведомление
        reminder_time = datetime.strptime(reminder[3], '%Y-%m-%d %H:%M:%S')
        notify_time = reminder_time - timedelta(minutes=minutes)
        
        if notify_time > datetime.now():
            self.scheduler.add_notification(reminder[1], reminder[2], notify_time, reminder_id, True)
    
        await query.edit_message_text(
            text=f"🔔 Добавлено уведомление за {minutes} минут!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Назад к напоминанию", callback_data=f"back_to_reminder_{reminder_id}")]
            ])
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений"""
        text = update.message.text
        
        if text == '📋 Мои напоминания':
            await self.show_reminders_list(update)
        elif text == '📊 Статистика':
            await self.stats_command(update, context)
        elif text == 'ℹ️ Помощь':
            await self.help_command(update, context)
        elif text == '📝 Создать напоминание':
            await self.remind_command(update, context)
        elif text == '🔄 Повторяющиеся':
            await update.message.reply_text(
                "🔄 Для создания повторяющихся напоминаний используй кнопку \"📝 Создать напоминание\" "
                "и выбери нужный тип повторения в процессе создания.",
                reply_markup=Keyboards.main_menu()
            )
        elif text.lower().startswith('напомни'):
            await self.quick_reminder(update, text)
        else:
            await update.message.reply_text(
                "Используй кнопки меню или напиши /help для помощи",
                reply_markup=Keyboards.main_menu()
            )

    async def show_reminders_list(self, update: Update):
        """Показать список напоминаний"""
        user_id = update.message.from_user.id
        reminders = self.db.get_user_reminders(user_id, status='active')
        
        if not reminders:
            await update.message.reply_text(
                "📭 У тебя пока нет активных напоминаний.",
                reply_markup=Keyboards.main_menu()
            )
            return
        
        reminders_text = TextFormatter.format_reminder_list(reminders)
        
        # Если текст слишком длинный, разбиваем на части
        if len(reminders_text) > 4000:
            parts = [reminders_text[i:i+4000] for i in range(0, len(reminders_text), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode='Markdown')
        else:
            await update.message.reply_text(reminders_text, parse_mode='Markdown')

    async def quick_reminder(self, update: Update, text: str):
        """Быстрое создание напоминания из текста"""
        try:
            if " через " in text:
                parts = text.split(" через ")
                reminder_text = parts[0].replace("напомни", "").strip()
                time_part = "через " + parts[1]
                
                reminder_time = TimeParser.parse_time(time_part)
                user_id = update.message.from_user.id
                
                reminder_id = self.db.add_reminder(user_id, reminder_text, reminder_time)
                self.scheduler.add_reminder(user_id, reminder_text, reminder_time, reminder_id)
                
                await update.message.reply_text(
                    f"✅ Готово! Напомню: '{reminder_text}' "
                    f"{reminder_time.strftime('%d.%m.%Y в %H:%M')}",
                    reply_markup=Keyboards.main_menu()
                )
            else:
                await update.message.reply_text(
                    "Напиши в формате: 'напомни [текст] через [время]'\n"
                    "Например: 'напомни позвонить маме через 2 часа'",
                    reply_markup=Keyboards.main_menu()
                )
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Не могу понять время. Используй кнопку '📝 Создать напоминание' "
                f"для полного процесса создания.",
                reply_markup=Keyboards.main_menu()
            )

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания напоминания"""
        await update.message.reply_text(
            "Создание напоминания отменено.",
            reply_markup=Keyboards.main_menu()
        )
        return ConversationHandler.END

    def run(self):
        """Запуск бота"""
        # Инициализация планировщика после создания application
        self.scheduler = ReminderScheduler(self.application.bot)
        
        print("Улучшенный бот запущен! Нажми Ctrl+C для остановки")
        self.application.run_polling()

if __name__ == '__main__':
    bot = ImprovedReminderBot()
    bot.run()