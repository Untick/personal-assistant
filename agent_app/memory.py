import os
import logging
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import RedisChatMessageHistory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Константы ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CONVERSATION_WINDOW_SIZE = 5

def get_user_memory(user_id: int) -> ConversationBufferWindowMemory:
    """
    Создает или загружает историю диалога для конкретного пользователя из Redis
    и возвращает объект памяти LangChain.
    """
    session_id = str(user_id)
    logging.info(f"Инициализация памяти для пользователя {session_id} в Redis по URL: {REDIS_URL}")

    try:
        # Создаем объект, который будет автоматически синхронизировать историю чата с Redis
        chat_history = RedisChatMessageHistory(
            session_id=session_id, 
            url=REDIS_URL
        )

        # Оборачиваем его в стандартный буфер памяти LangChain
        memory = ConversationBufferWindowMemory(
            memory_key="chat_history", # Это имя будет использоваться в промпте
            chat_memory=chat_history,
            k=CONVERSATION_WINDOW_SIZE, # Храним 5 последних пар сообщений
            return_messages=True # Важно для современных агентов
        )
        
        logging.info(f"Память для пользователя {session_id} успешно инициализирована.")
        return memory

    except Exception as e:
        logging.error(f"Не удалось подключиться к Redis для пользователя {session_id}: {e}")
        logging.warning("Возвращается временная, пустая память на один запрос.")
        return ConversationBufferWindowMemory(
            memory_key="chat_history",
            k=CONVERSATION_WINDOW_SIZE,
            return_messages=True
        )

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    # Этот блок кода для тестирования модуля
    print("--- Тестирование модуля memory.py ---")
    
    # 1. Получаем "докерный" URL из .env
    docker_redis_url = os.getenv("REDIS_URL")
    if not docker_redis_url:
        print("Ошибка: Переменная окружения REDIS_URL не найдена в .env файле.")
    else:
        # 2. Адаптируем URL для локального запуска: меняем хост 'redis' на 'localhost'
        local_redis_url = docker_redis_url.replace("redis:6379", "localhost:6379")
        print(f"URL для Docker: {docker_redis_url}")
        print(f"Адаптированный URL для локального теста: {local_redis_url}")

        # 3. Переопределяем глобальную переменную ТОЛЬКО для этого теста
        REDIS_URL = local_redis_url
    
        # Проверяем, что Redis доступен (нужен запущенный Docker-контейнер Redis)
        try:
            import redis
            r = redis.from_url(REDIS_URL)
            r.ping()
            print("Подключение к Redis успешно.")

            test_user_id = 12345
            print(f"Создаем память для тестового пользователя: {test_user_id}")
            
            user_memory = get_user_memory(test_user_id)
            user_memory.clear()
            print("Старая история для тестового пользователя очищена.")

            user_memory.save_context({"input": "Привет!"}, {"output": "Здравствуйте!"})
            user_memory.save_context({"input": "Как дела?"}, {"output": "Все отлично, спасибо!"})
            print("Два сообщения добавлены в память.")

            history = user_memory.load_memory_variables({})
            print("\nЗагруженная история из Redis:")
            print(history)

            assert len(history['chat_history']) == 4
            assert history['chat_history'][0].content == "Привет!"
            
            print("\nТест пройден успешно!")
        
        except Exception as e:
            print(f"\nОшибка во время тестирования: {e}")
            print("Убедитесь, что Docker-контейнер Redis запущен (`docker-compose up -d redis`) и порт 6379 не занят.")
    
    print("--- Тестирование завершено ---")