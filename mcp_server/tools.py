import os
import asyncio
import logging
from typing import List, Union

from pydantic import BaseModel, Field
from tavily import TavilyClient

from auth import get_google_api_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Модели данных (Pydantic) для структурированного вывода ---

class WebSearchResult(BaseModel):
    """Структурированный результат веб-поиска."""
    summary: str = Field(description="Краткая выжимка из найденной информации.")

class GoogleTask(BaseModel):
    """Представление задачи из Google Tasks."""
    id: str
    title: str
    status: str
    due: str | None = None

class GoogleEvent(BaseModel):
    """Представление события из Google Calendar."""
    id: str
    summary: str
    start: str
    end: str
    htmlLink: str

class OperationStatus(BaseModel):
    """Стандартный ответ для операций создания/изменения."""
    status: str = Field(description="Результат операции, например 'success' или 'error'.")
    details: str | None = Field(default=None, description="Дополнительные детали или ссылка на созданный объект.")


# --- Функции бизнес-логики ---

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

async def perform_web_search(query: str) -> Union[WebSearchResult, str]:
    """Чистая логика для выполнения поиска в Tavily."""
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: tavily_client.search(query=query, search_depth="basic"))
        content = "\n\n".join([res["content"] for res in response.get("results", [])])
        return WebSearchResult(summary=content if content else "По вашему запросу ничего не найдено.")
    except Exception as e:
        logging.error(f"Ошибка при поиске в Tavily: {e}")
        return f"Ошибка Tavily: {e}"

async def get_google_tasks(task_list_id: str) -> Union[List[GoogleTask], str]:
    """Чистая логика для получения задач из Google Tasks."""
    try:
        service = await asyncio.to_thread(get_google_api_service, 'tasks', 'v1')
        results = await asyncio.to_thread(service.tasks().list(tasklist=task_list_id, showCompleted=False).execute)
        items = results.get('items', [])
        return [GoogleTask(**item) for item in items]
    except Exception as e:
        logging.error(f"Ошибка при получении списка задач: {e}")
        return f"Ошибка Google Tasks: {e}"

async def create_google_task(title: str, task_list_id: str) -> Union[OperationStatus, str]:
    """Чистая логика для создания задачи в Google Tasks."""
    try:
        service = await asyncio.to_thread(get_google_api_service, 'tasks', 'v1')
        task = {'title': title}
        result = await asyncio.to_thread(service.tasks().insert(tasklist=task_list_id, body=task).execute)
        return OperationStatus(status="success", details=f"Задача '{result['title']}' создана.")
    except Exception as e:
        logging.error(f"Ошибка при добавлении задачи: {e}")
        return f"Ошибка Google Tasks: {e}"

async def get_google_events(time_min: str, time_max: str) -> Union[List[GoogleEvent], str]:
    """Чистая логика для получения событий из Google Calendar."""
    try:
        service = await asyncio.to_thread(get_google_api_service, 'calendar', 'v3')
        events_result = await asyncio.to_thread(
            service.events().list(calendarId='primary', timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy='startTime').execute
        )
        items = events_result.get('items', [])
        for item in items:
            item['start'] = item['start'].get('dateTime', item['start'].get('date'))
            item['end'] = item['end'].get('dateTime', item['end'].get('date'))
        return [GoogleEvent(**item) for item in items]
    except Exception as e:
        logging.error(f"Ошибка при получении событий календаря: {e}")
        return f"Ошибка Google Calendar: {e}"

async def create_google_event(summary: str, start_time: str, end_time: str, timezone: str) -> Union[OperationStatus, str]:
    """Чистая логика для создания события в Google Calendar."""
    try:
        service = await asyncio.to_thread(get_google_api_service, 'calendar', 'v3')
        event = {
            'summary': summary,
            'start': {'dateTime': start_time, 'timeZone': timezone},
            'end': {'dateTime': end_time, 'timeZone': timezone},
        }
        created_event = await asyncio.to_thread(service.events().insert(calendarId='primary', body=event).execute)
        return OperationStatus(status="success", details=created_event.get('htmlLink'))
    except Exception as e:
        logging.error(f"Ошибка при создании события: {e}")
        return f"Ошибка Google Calendar: {e}"
