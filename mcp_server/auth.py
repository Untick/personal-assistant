import os.path
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Определяем права доступа, которые будет запрашивать наше приложение
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks"
]

CREDENTIALS_FILE = 'mcp_server/credentials.json'
TOKEN_FILE = 'mcp_server/token.json'

def get_google_api_service(service_name: str, version: str):
    """
    Универсальная функция для получения аутентифицированного объекта service Google API.
    Обрабатывает получение, хранение и обновление OAuth 2.0 токенов.
    """
    creds = None
    # 1. Проверка наличия файла token.json с сохраненными данными аутентификации.
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            logging.error(f"Не удалось загрузить учетные данные из {TOKEN_FILE}: {e}")
            creds = None

    # 2. Если учетные данные не найдены или они истекли/недействительны.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Если токен просто истек, но у нас есть refresh_token, обновляем его.
            logging.info("Обновление истекшего токена...")
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.error(f"Ошибка при обновлении токена: {e}")
                creds = None # Сбрасываем creds, чтобы запустить полную аутентификацию
        
        # Если нужно пройти аутентификацию с нуля.
        if not creds:
            logging.info(f"Запуск процесса аутентификации, т.к. токен не найден или недействителен.")
            if not os.path.exists(CREDENTIALS_FILE):
                logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Файл {CREDENTIALS_FILE} не найден. "
                                 "Скачайте его из Google Cloud Console и поместите в папку mcp_server.")
                return None
            
            # Запускаем интерактивный процесс в консоли.
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 4. Сохраняем полученные или обновленные учетные данные в файл.
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        logging.info(f"Учетные данные успешно сохранены в {TOKEN_FILE}")

    try:
        service = build(service_name, version, credentials=creds)
        logging.info(f"Сервис Google API '{service_name} v{version}' успешно инициализирован.")
        return service
    except Exception as e:
        logging.error(f"Не удалось создать сервис Google API '{service_name}': {e}")
        return None

if __name__ == '__main__':
    # Этот блок кода позволяет запустить этот файл напрямую для получения token.json
    print("Запуск процесса первоначальной аутентификации...")
    print("Будет запрошен доступ к Google Calendar и Google Tasks.")
    get_google_api_service('tasks', 'v1')
    print("\nПроцесс аутентификации завершен. Проверьте, что в папке mcp_server создался файл token.json.")
