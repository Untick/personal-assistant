from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
import mcp
from typing import List, Union

# Импортируем наши модели и бизнес-логику
from tools import (
    perform_web_search,
    get_google_tasks,
    create_google_task,
    get_google_events,
    create_google_event,
    WebSearchResult,
    GoogleTask,
    GoogleEvent,
    OperationStatus
)

app = FastAPI(
    title="Personal Assistant MCP Server",
    description="Сервер, предоставляющий инструменты для AI-агента.",
    version="1.0.0"
)

# Создаем экземпляр сервера. Имя будет видно клиентам.
mcp = FastMCP("PersonalAssistantTools")

# --- Регистрация инструментов ---
@mcp.tool()
async def tavily_web_search(query: str) -> Union[WebSearchResult, str]:
    """Ищет актуальную информацию в интернете по заданному запросу."""
    return await perform_web_search(query)

@mcp.tool()
async def list_google_tasks(task_list_id: str = '@default') -> Union[List[GoogleTask], str]:
    """Получает список активных задач из Google Tasks."""
    return await get_google_tasks(task_list_id)

@mcp.tool()
async def add_google_task(title: str, task_list_id: str = '@default') -> Union[OperationStatus, str]:
    """Добавляет новую задачу в Google Tasks."""
    return await create_google_task(title, task_list_id)

@mcp.tool()
async def list_google_calendar_events(time_min: str, time_max: str) -> Union[List[GoogleEvent], str]:
    """Получает список событий из Google Calendar. Даты должны быть в формате ISO 8601."""
    return await get_google_events(time_min, time_max)

@mcp.tool()
async def create_google_calendar_event(summary: str, start_time: str, end_time: str, timezone: str = 'Europe/Moscow') -> Union[OperationStatus, str]:
    """Создает новое событие в Google Calendar. Дата и время должны быть в формате ISO 8601."""
    return await create_google_event(summary, start_time, end_time, timezone)

app.mount("/mcp", mcp.streamable_http_app())

# 2. КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Создаем переменную 'mcp', которую ищет Uvicorn,
#    вызывая метод .streamable_http_mcp() на нашем сервере.

@app.get("/")
def health_check():
    return {"status": "ok", "mcp_endpoint": "/mcp"}