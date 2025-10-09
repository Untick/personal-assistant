import os
import asyncio
import logging
import json
from typing import List, Any

from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools.retriever import create_retriever_tool
from langchain.tools import Tool
from langchain_community.llms import Ollama

from mcp import ClientSession, types as mcp_types
from mcp.client.streamable_http import streamablehttp_client

from .db import get_vector_db_retriever

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

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
            # --- ИСПРАВЛЕННАЯ ЛОГИКА СОЗДАНИЯ ИНСТРУМЕНТА ---
            def create_tool_coro(spec: mcp_types.Tool):
                # Функция теперь принимает один позиционный аргумент 'tool_input'
                async def tool_coro(tool_input: str) -> Any:
                    name = spec.name
                    params = {}
                    
                    # Получаем схему аргументов инструмента (ИСПОЛЬЗУЕМ camelCase)
                    input_schema = spec.inputSchema if spec.inputSchema else {}
                    properties = input_schema.get('properties', {})
                    
                    # ReAct агент передает один строковый аргумент.
                    # Если инструмент ожидает ровно один аргумент, используем строку как его значение.
                    if len(properties) == 1 and isinstance(tool_input, str):
                        param_name = list(properties.keys())[0]
                        params = {param_name: tool_input}
                    else:
                        # Если аргументов 0 или >1, модель должна была передать JSON.
                        # Если она этого не сделала (например, передала 'None' как строку),
                        # мы передаем пустые параметры.
                        logging.warning(f"Инструмент '{name}' получил неструктурированный ввод '{tool_input}'. Попытка вызова с пустыми параметрами.")
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

    # --- ИЗМЕНЕНИЕ: Улучшаем промпт ---
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
        max_iterations=5
    )
    
    logging.info("Ядро агента (ReAct AgentExecutor) успешно создано с Llama3.")
    return agent_executor

agent_executor = create_agent_executor()