# 1. Используем тот же базовый образ
FROM python:3.11-slim

# 2. Устанавливаем рабочую директорию
WORKDIR /app

# 3. Копируем зависимости
COPY requirements.txt .

# 4. Устанавливаем их
RUN pip install --no-cache-dir -r requirements.txt

# 5. Копируем только код, который относится к MCP-серверу
COPY ./mcp_server /app

# 6. Команда для запуска MCP-сервера с помощью uvicorn
# 0.0.0.0 делает сервер доступным извне контейнера
#CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "main.py"]