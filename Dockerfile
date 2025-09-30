FROM python:3.9-slim

WORKDIR /app

# Создаем директории для данных и бэкапов
RUN mkdir -p /app/data /app/backups

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Меняем путь к базе данных
ENV DB_PATH=/app/data/reminders.db
ENV BACKUP_DIR=/app/backups

CMD ["python", "bot.py"]