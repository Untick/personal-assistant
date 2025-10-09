# 1. Используем официальный легковесный образ Python
FROM python:3.11-slim

# 2. Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# 3. Копируем файл с зависимостями
COPY requirements.txt .

# 4. Устанавливаем зависимости.
# --no-cache-dir чтобы не хранить кэш pip и уменьшить размер образа
# python3-dev и gcc нужны для компиляции некоторых зависимостей
RUN apt-get update && apt-get install -y python3-dev gcc && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y python3-dev gcc && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# 5. Копируем весь код приложения агента в рабочую директорию
COPY ./agent_app /app
# Копируем базу знаний, чтобы агент мог ее найти
COPY ./knowledge_base /app/knowledge_base

# 6. Указываем команду для запуска приложения при старте контейнера
CMD ["python", "main.py"]