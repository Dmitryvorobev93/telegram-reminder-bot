from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from config import Config

class Keyboards:
    @staticmethod
    def main_menu():
        keyboard = [
            ['📝 Создать напоминание', '📋 Мои напоминания'],
            ['🔄 Повторяющиеся', '📊 Статистика'],
            ['ℹ️ Помощь']
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def repeat_options():
        keyboard = []
        for key, value in Config.REPEAT_OPTIONS.items():
            keyboard.append([InlineKeyboardButton(value, callback_data=f"repeat_{key}")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def categories():
        keyboard = []
        row = []
        for i, (key, value) in enumerate(Config.CATEGORIES.items()):
            row.append(InlineKeyboardButton(value, callback_data=f"category_{key}"))
            if (i + 1) % 2 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def reminder_actions(reminder_id):
        keyboard = [
            [
                InlineKeyboardButton("✅ Выполнено", callback_data=f"complete_{reminder_id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{reminder_id}")
            ],
            [
                InlineKeyboardButton("🔔 Уведомить за 15 мин", callback_data=f"notify15_{reminder_id}"),
                InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{reminder_id}")
            ],
            [InlineKeyboardButton("📋 Назад к списку", callback_data="back_to_list")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def edit_options(reminder_id):
        keyboard = [
            [
                InlineKeyboardButton("✏️ Текст", callback_data=f"edit_text_{reminder_id}"),
                InlineKeyboardButton("📅 Время", callback_data=f"edit_time_{reminder_id}")
            ],
            [
                InlineKeyboardButton("🔄 Повтор", callback_data=f"edit_repeat_{reminder_id}"),
                InlineKeyboardButton("📂 Категория", callback_data=f"edit_category_{reminder_id}")
            ],
            [InlineKeyboardButton("📋 Назад", callback_data=f"back_to_reminder_{reminder_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)