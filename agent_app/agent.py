import os
import asyncio
import logging
from typing import List, Any

from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools.retriever import create_retriever_tool
from langchain.tools import Tool


from langchain_community.llms import Ollama 

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from db import get_vector_db_retriever

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

async def create_mcp_tools(mcp_base_url: str) -> List[Tool]:
    """Создает инструменты LangChain, подключаясь к MCP-серверу."""
    mcp_url = mcp_base_url.rstrip('/') + "/mcp"
    logging.info(f"Подключение к MCP-серверу: {mcp_url}")
    langchain_tools = []
    
    try:
        async with streamablehttp_client(mcp_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                server_tools_response = await session.list_tools()
                server_tools = server_tools_response.tools
        logging.info(f"С MCP-сервера получено {len(server_tools)} инструментов.")

        for tool_spec in server_tools:
            def create_tool_coro(spec):
                async def tool_coro(**kwargs: Any) -> Any:
                    name = spec.name
                    logging.info(f"Вызов MCP-инструмента '{name}' с параметрами: {kwargs}")
                    try:
                        async with streamablehttp_client(mcp_url) as (r, w, _):
                            async with ClientSession(r, w) as s:
                                await s.initialize()
                                result = await s.call_tool(name, arguments=kwargs)
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
    
    # --- ИЗМЕНЕНИЕ: Используем базовый Ollama ---
    llm = Ollama(model="gemma:2b", base_url=OLLAMA_BASE_URL, temperature=0.1)
    
    mcp_tools = asyncio.run(create_mcp_tools(MCP_SERVER_URL))
    
    retriever = get_vector_db_retriever()
    retriever_tool = create_retriever_tool(retriever, "knowledge_base_search", "Поиск информации о проекте.")
    
    all_tools = mcp_tools + [retriever_tool]
    logging.info(f"Всего инструментов загружено: {len(all_tools)}")

    # --- ИЗМЕНЕНИЕ: Используем базовый ReAct промпт, он лучше подходит для не-чатовых моделей ---
    prompt = hub.pull("hwchase17/react")
    agent = create_react_agent(llm, all_tools, prompt)
    
    agent_executor = AgentExecutor(agent=agent, tools=all_tools, verbose=True, handle_parsing_errors=True)
    
    logging.info("Ядро агента (ReAct AgentExecutor) успешно создано.")
    return agent_executor

agent_executor = create_agent_executor()