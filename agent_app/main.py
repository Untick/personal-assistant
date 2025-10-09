import asyncio
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения в самом начале
load_dotenv()

# Убедимся, что все модули (особенно agent.py) загружены до старта бота
# Этот импорт инициализирует agent_executor
from agent import agent_executor
from bot import main_bot

def main():
    """Точка входа в приложение."""
    logging.info("Запуск AI-ассистента...")
    try:
        # Запускаем асинхронную функцию `main_bot`
        asyncio.run(main_bot())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Остановка AI-ассистента.")

if __name__ == "__main__":
    main()