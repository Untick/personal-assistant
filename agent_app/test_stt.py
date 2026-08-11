import os
import sys
from dotenv import load_dotenv

# Добавляем корень проекта в путь, чтобы импортировать stt
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Загружаем переменные окружения из .env
load_dotenv()

from agent_app.stt import transcribe_audio

def main():
    if len(sys.argv) < 2:
        print("Использование: python test_stt.py <путь_к_аудиофайлу>")
        print("Пример: python test_stt.py ../voice_message.ogg")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"Ошибка: Файл '{file_path}' не найден.")
        sys.exit(1)

    print(f"Проверка переменных окружения...")
    folder_id = os.getenv("YANDEX_FOLDER_ID")
    api_key = os.getenv("YANDEX_API_KEY")

    if not folder_id or not api_key:
        print("Ошибка: Не найдены переменные YANDEX_FOLDER_ID или YANDEX_API_KEY в .env")
        sys.exit(1)
    
    print(f"Folder ID: {folder_id}")
    print(f"API Key: {api_key[:5]}...{api_key[-5:]} (скрыт)")
    print("-" * 30)
    
    print(f"Отправка файла '{file_path}' в Яндекс SpeechKit...")
    result = transcribe_audio(file_path)

    print("-" * 30)
    if result:
        print("✅ УСПЕХ! Распознанный текст:")
        print(result)
    else:
        print("❌ ОШИБКА: Пустой результат или ошибка при распознавании.")
        print("Проверьте консоль выше на наличие логов ошибок.")

if __name__ == "__main__":
    main()
