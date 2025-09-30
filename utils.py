import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

# Добавляем импорт Config
from config import Config

class TimeParser:
    @staticmethod
    def parse_time(time_text):
        """Улучшенный парсинг времени с поддержкой повторений"""
        time_text = time_text.lower().strip()
        
        # Получаем текущее время в московском часовом поясе
        # Создаем наивное datetime и добавляем московский часовой пояс
        now_utc = datetime.utcnow()
        # Москва = UTC+3
        moscow_offset = timedelta(hours=3)
        now_moscow = now_utc + moscow_offset
        
        # Базовые форматы (как были)
        if time_text.startswith('через'):
            return TimeParser._parse_relative_time(time_text, now_moscow)
        elif 'завтра' in time_text:
            return TimeParser._parse_tomorrow_time(time_text, now_moscow)
        elif 'сегодня' in time_text and 'в' in time_text:
            return TimeParser._parse_today_time(time_text, now_moscow)
        elif ':' in time_text and len(time_text) <= 5:
            return TimeParser._parse_simple_time(time_text, now_moscow)
        elif '.' in time_text and ' в ' in time_text:
            return TimeParser._parse_full_datetime(time_text)
        else:
            raise ValueError("Неизвестный формат времени")
    
    @staticmethod
    def _parse_relative_time(time_text, now):
        if 'минут' in time_text:
            minutes = int(''.join(filter(str.isdigit, time_text)))
            return now + timedelta(minutes=minutes)
        elif 'час' in time_text:
            hours = int(''.join(filter(str.isdigit, time_text)))
            return now + timedelta(hours=hours)
        elif 'день' in time_text or 'дня' in time_text or 'дней' in time_text:
            days = int(''.join(filter(str.isdigit, time_text)))
            return now + timedelta(days=days)
        elif 'недел' in time_text:
            weeks = int(''.join(filter(str.isdigit, time_text)))
            return now + timedelta(weeks=weeks)
        elif 'месяц' in time_text:
            months = int(''.join(filter(str.isdigit, time_text)))
            return now + relativedelta(months=months)
        else:
            raise ValueError("Не могу распознать временной интервал")
    
    @staticmethod
    def _parse_tomorrow_time(time_text, now):
        time_part = time_text.split('в ')[1]
        hours, minutes = map(int, time_part.split(':'))
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    
    @staticmethod
    def _parse_today_time(time_text, now):
        time_part = time_text.split('в ')[1]
        hours, minutes = map(int, time_part.split(':'))
        return now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    
    @staticmethod
    def _parse_simple_time(time_text, now):
        hours, minutes = map(int, time_text.split(':'))
        reminder_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        if reminder_time < now:
            reminder_time += timedelta(days=1)
        return reminder_time
    
    @staticmethod
    def _parse_full_datetime(time_text):
        date_part, time_part = time_text.split(' в ')
        day, month, year = map(int, date_part.split('.'))
        hours, minutes = map(int, time_part.split(':'))
        # Создаем datetime и добавляем московское смещение
        naive_dt = datetime(year, month, day, hours, minutes)
        moscow_offset = timedelta(hours=3)
        return naive_dt - moscow_offset  # Конвертируем в UTC
    
    @staticmethod
    def calculate_next_reminder(reminder_time, repeat_type):
        """Вычисление следующего напоминания для повторяющихся"""
        if repeat_type == 'daily':
            return reminder_time + timedelta(days=1)
        elif repeat_type == 'weekly':
            return reminder_time + timedelta(weeks=1)
        elif repeat_type == 'monthly':
            return reminder_time + relativedelta(months=1)
        elif repeat_type == 'yearly':
            return reminder_time + relativedelta(years=1)
        return None

class TextFormatter:
    @staticmethod
    def format_reminder_list(reminders):
        if not reminders:
            return "📭 У тебя пока нет активных напоминаний."
        
        text = "📋 Твои напоминания:\n\n"
        for rem_id, text_msg, time, category, repeat_type, status in reminders:
            if status == 'completed':
                status_icon = "✅"
            elif status == 'cancelled':
                status_icon = "❌"
            else:
                status_icon = "⏳"
            
            # Исправляем парсинг времени с микросекундами
            try:
                if '.' in time:
                    # Формат с микросекундами: 2025-09-29 19:55:23.191360
                    time_obj = datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    # Формат без микросекунд: 2025-09-29 19:55:23
                    time_obj = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
                
                # Конвертируем UTC время в московское для отображения
                moscow_offset = timedelta(hours=3)
                moscow_time = time_obj + moscow_offset
                time_str = moscow_time.strftime('%d.%m.%Y %H:%M')
            except ValueError as e:
                logging.error(f"Ошибка форматирования времени {time}: {e}")
                time_str = time  # Используем оригинальную строку при ошибке
            
            category_icon = Config.CATEGORIES.get(category, '📌').split(' ')[0]
            repeat_text = f" ({Config.REPEAT_OPTIONS.get(repeat_type, '')})" if repeat_type != 'once' else ""
            
            text += f"{status_icon} {category_icon} {text_msg}\n"
            text += f"   📅 {time_str}{repeat_text}\n"
            text += f"   ID: {rem_id}\n\n"
        
        return text
    
    @staticmethod
    def format_stats(stats):
        text = "📊 Статистика напоминаний:\n\n"
        text += f"✅ Выполнено: {stats.get('completed', 0)}\n"
        text += f"⏳ Активных: {stats.get('active', 0)}\n"
        text += f"❌ Отменено: {stats.get('cancelled', 0)}\n"
        text += f"📈 Всего создано: {stats.get('total', 0)}\n"
        
        if stats.get('categories'):
            text += "\n📂 По категориям:\n"
            for category, count in stats['categories'].items():
                category_name = Config.CATEGORIES.get(category, 'Другое')
                text += f"  {category_name}: {count}\n"
        
        return text