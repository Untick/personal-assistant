import os
import asyncio
import logging
import json
import tempfile
from typing import List, Any

from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools.retriever import create_retriever_tool
from langchain.tools import Tool
from langchain_community.llms import Ollama
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from mcp import ClientSession, types as mcp_types
from mcp.client.streamable_http import streamablehttp_client

from .db import get_vector_db_retriever
from .stt import transcribe_audio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def create_mcp_tools(mcp_base_url: str) -> List[Tool]:
    """Создает инструменты LangChain, правильно обрабатывая аргументы для ReAct."""
    mcp_url = mcp_base_url.rstrip('/') + "/mcp"
    logging.info(f"Подключение к MCP-серверу: {mcp_url}")
    langchain_tools = []
    try:
        async with streamablehttp_client(mcp_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                server_tools_response = await session.list_tools()
                server_tools: List[mcp_types.Tool] = server_tools_response.tools
        logging.info(f"С MCP-сервера получено {len(server_tools)} инструментов.")

        for tool_spec in server_tools:
            
            def create_tool_coro(spec: mcp_types.Tool):
                # Функция теперь принимает один позиционный аргумент 'tool_input'
                async def tool_coro(tool_input: str) -> Any:
                    name = spec.name
                    params = {}
                    
                    # Получаем схему аргументов инструмента
                    input_schema = spec.inputSchema if spec.inputSchema else {}
                    properties = input_schema.get('properties', {})
                    
                    # ReAct агент передает один строковый аргумент.
                    # Если инструмент ожидает ровно один аргумент, используем строку как его значение.
                    if len(properties) == 1:
                        param_name = list(properties.keys())[0]
                        params = {param_name: tool_input}
                    else:
                        # Если аргументов 0 или >1, модель должна была передать JSON.
                        # Если она этого не сделала, мы не можем угадать параметры.
                        # В этом случае можно либо передать пустой словарь, либо вернуть ошибку.
                        # Для простоты передадим пустой словарь, но в логах это будет видно.
                        logging.warning(f"Инструмент '{name}' ожидает {len(properties)} аргументов, но получил простую строку. Попытка вызова с пустыми параметрами.")
                        params = {}
                    
                    logging.info(f"Вызов MCP-инструмента '{name}' с параметрами: {params}")
                    try:
                        async with streamablehttp_client(mcp_url) as (r, w, _):
                            async with ClientSession(r, w) as s:
                                await s.initialize()
                                result = await s.call_tool(name, arguments=params)
                                return result.structuredContent
                    except Exception as e:
                        return f"Ошибка при вызове инструмента '{name}': {e}"
                return tool_coro

            langchain_tools.append(Tool(
                name=tool_spec.name,
                func=None,
                coroutine=create_tool_coro(tool_spec),
                description=tool_spec.description,
            ))
        logging.info("Инструменты на основе MCP успешно созданы.")
            
    except Exception as e:
        logging.error(f"Не удалось загрузить инструменты с MCP-сервера: {e}", exc_info=True)
    return langchain_tools


def create_agent_executor():
    """Собирает и возвращает готовый к работе AgentExecutor."""
    logging.info("Создание ядра агента...")
    
    llm = Ollama(model="llama3:8b", base_url=OLLAMA_BASE_URL, temperature=0.1)
    
    mcp_tools = asyncio.run(create_mcp_tools(MCP_SERVER_URL))
    
    retriever = get_vector_db_retriever()
    retriever_tool = create_retriever_tool(retriever, "knowledge_base_search", "Используй этот инструмент, чтобы отвечать на вопросы о целях проекта, его архитектуре и технологиях.")
    
    all_tools = mcp_tools + [retriever_tool]
    logging.info(f"Всего инструментов загружено: {len(all_tools)}")

    # Мы добавляем к стандартному промпту свои инструкции
    prompt = hub.pull("hwchase17/react").partial(
        instructions="Всегда отвечай на русском языке. Будь кратким и вежливым. Если нашел ответ с помощью инструмента, сразу давай 'Final Answer', не пытайся использовать другие инструменты без необходимости."
    )
    
    agent = create_react_agent(llm, all_tools, prompt)
    
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=all_tools, 
        verbose=True, 
        handle_parsing_errors=True,
        max_iterations=5 # Возвращаем стандартное значение, т.к. Llama3 умнее
    )
    
    logging.info("Ядро агента (ReAct AgentExecutor) успешно создано с Llama3.")
    return agent_executor

agent_executor = create_agent_executor()


async def process_message_text(text: str) -> str:
    """Обрабатывает текстовое сообщение через LangChain-агент."""
    try:
        response = agent_executor.invoke({"input": text})
        return response.get("output", "Не удалось получить ответ от агента.")
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения агентом: {e}")
        return "Произошла ошибка при обработке вашего запроса."


async def main_bot():
    """Запускает Telegram-бота."""
    if not TELEGRAM_BOT_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
        return
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer("Привет! Я ваш персональный ассистент. Отправьте мне текстовое сообщение или голосовую заметку.")
    
    @dp.message(lambda msg: msg.voice or msg.audio)
    async def handle_voice_audio(message: types.Message):
        """Обработчик голосовых сообщений и аудиофайлов."""
        voice_or_audio = message.voice or message.audio
        
        if not voice_or_audio:
            return
        
        # Скачиваем файл во временную папку
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        temp_file_path = temp_file.name
        temp_file.close()
        
        try:
            file_id = voice_or_audio.file_id
            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, temp_file_path)
            
            # Распознаем аудио
            recognized_text = transcribe_audio(temp_file_path)
            
            if recognized_text:
                logging.info(f"Распознанный текст из голосового сообщения: {recognized_text}")
                # Передаем распознанный текст в агент
                response_text = await process_message_text(recognized_text)
                await message.answer(response_text)
            else:
                await message.answer("Не удалось распознать голосовое сообщение. Попробуйте отправить текстом или запишите громче.")
        except Exception as e:
            logging.error(f"Ошибка при обработке голосового/аудио сообщения: {e}")
            await message.answer("Не удалось распознать голосовое сообщение. Попробуйте отправить текстом или запишите громче.")
        finally:
            # Удаляем временный файл
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
    
    @dp.message()
    async def handle_text_message(message: types.Message):
        """Обработчик текстовых сообщений."""
        if not message.text:
            return
        
        response_text = await process_message_text(message.text)
        await message.answer(response_text)
    
    logging.info("Запуск бота...")
    await dp.start_polling(bot)