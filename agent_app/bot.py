# agent_app/bot.py
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode, ChatAction

# Импортируем наши готовые компоненты
# Важно: импорты должны быть относительными, так как все будет в одном пакете
from agent import agent_executor
from memory import get_user_memory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
router = Router() 

@router.message(Command("start"))
async def start_command(message: types.Message):
    """Обработчик команды /start."""
    await message.answer(f"Привет, {message.from_user.full_name}! Я твой личный AI-помощник. Чем могу помочь?",parse_mode=ParseMode.HTML)

@router.message(Command("help"))
async def help_command(message: types.Message):
    """Обработчик команды /help."""
    help_text = (
        "<b>Я твой личный AI-помощник. Вот что я могу:</b>\n\n"
        "📅 <b>Google Calendar:</b>\n"
        "   - 'Что у меня на сегодня?'\n"
        "   - 'Создай событие: Обед с командой завтра в 13:00'\n\n"
        "✅ <b>Google Tasks:</b>\n"
        "   - 'Какие у меня задачи?'\n"
        "   - 'Добавь задачу: купить молоко'\n\n"
        "🌐 <b>Web Search:</b>\n"
        "   - 'Сделай сводку новостей по AI за сегодня'\n\n"
        "Просто напиши мне свой вопрос."
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@router.message(Command("health"))
async def health_command(message: types.Message, bot: Bot):
    """Обработчик команды /health для проверки статуса."""
    try:
        await bot.get_me()
        status_text = "✅ Telegram Bot: Работает"
    except Exception as e:
        status_text = f"❌ Telegram Bot: Ошибка ({e})"
    await message.answer(f"<b>Статус системы:</b>\n\n{status_text}", parse_mode=ParseMode.HTML)

@router.message(F.text)
async def handle_message(message: types.Message, bot: Bot):
    """Основной обработчик текстовых сообщений."""
    user_id = message.from_user.id
    user_input = message.text
    logging.info(f"Получено сообщение от user_id {user_id}: {user_input}")

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    memory = get_user_memory(user_id)
    try:
        # Мы запускаем блокирующий вызов agent_executor в отдельном потоке,
        # чтобы не "замораживать" основной поток, где работает aiogram.
        # Для этого используем синхронный метод .invoke() внутри to_thread.
        response = await asyncio.to_thread(
            agent_executor.invoke,
            {
                "input": user_input,
                "chat_history": memory.chat_memory.messages,
            },
        )
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        ai_response = response.get('output', "Не удалось обработать ваш запрос.")
    except Exception as e:
        logging.error(f"Ошибка при вызове agent_executor: {e}", exc_info=True)
        ai_response = "К сожалению, произошла внутренняя ошибка. Попробуйте, пожалуйста, позже."

    await message.answer(ai_response)

async def main_bot():
    """Главная функция для запуска бота."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logging.critical("Критическая ошибка: TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
        return

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)
    
    # Удаляем вебхук, если он был установлен, на случай перезапуска
    await bot.delete_webhook(drop_pending_updates=True)
    
    logging.info("Бот запускается в режиме опроса (polling)...")
    await dp.start_polling(bot)