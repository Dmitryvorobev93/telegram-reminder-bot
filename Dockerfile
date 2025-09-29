FROM python:3.9

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

# Проверяем, что файлы скопировались
RUN echo "=== Checking files ===" && \
    ls -la && \
    echo "=== .env files ===" && \
    ls -la .env* || echo "No .env files found"

CMD ["python", "bot.py"]

