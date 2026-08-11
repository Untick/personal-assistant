import os
import logging
import requests

logger = logging.getLogger(__name__)


def transcribe_audio(file_path: str) -> str:
    """
    Распознает аудиофайл с помощью Yandex SpeechKit STT API.
    
    Args:
        file_path: Путь к аудиофайлу на диске.
        
    Returns:
        Распознанный текст или пустую строку в случае ошибки.
    """
    yandex_folder_id = os.environ.get("YANDEX_FOLDER_ID")
    yandex_api_key = os.environ.get("YANDEX_API_KEY")
    
    if not yandex_folder_id or not yandex_api_key:
        logger.error("YANDEX_FOLDER_ID или YANDEX_API_KEY не настроены в переменных окружения.")
        return ""
    
    try:
        with open(file_path, "rb") as f:
            audio_data = f.read()
    except FileNotFoundError:
        logger.error(f"Аудиофайл не найден: {file_path}")
        return ""
    except Exception as e:
        logger.error(f"Ошибка при чтении аудиофайла: {e}")
        return ""
    
    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    
    headers = {
        "Authorization": f"Api-Key {yandex_api_key}",
        "Content-Type": "audio/*"
    }
    
    params = {
        "topic": "general",
        "lang": "ru-RU",
        "folderId": yandex_folder_id
    }
    
    try:
        response = requests.post(url, headers=headers, params=params, data=audio_data)
        response.raise_for_status()
        
        result_json = response.json()
        result_text = result_json.get("result", "")
        
        if result_text:
            logger.info(f"STT распознал текст: {result_text}")
        
        return result_text
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP ошибка при запросе к Yandex STT: {e}. Ответ: {response.text if 'response' in locals() else 'N/A'}")
        return ""
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при запросе к Yandex STT: {e}")
        return ""
    except Exception as e:
        logger.error(f"Неизвестная ошибка при распознавании аудио: {e}")
        return ""
