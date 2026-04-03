"""Handler for /start command."""
import os
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from bot.config import Config
from bot.keyboards import get_main_menu_inline
from bot.onboarding_store import get_onboarding_text

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command: send logo (if exists), onboarding text, and main menu."""
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"User {user_id} (@{username}) sent /start")

    if Config.ENABLE_ANALYTICS:
        try:
            from bot.users_registry import record_first_start

            record_first_start(
                user_id,
                username,
                message.from_user.first_name,
                message.from_user.last_name,
            )
        except Exception as e:
            logger.warning("users_registry record_first_start: %s", e, exc_info=True)
    
    # Reset state
    await state.clear()
    
    # Send logo if exists
    if os.path.exists(Config.LOGO_PATH):
        try:
            with open(Config.LOGO_PATH, "rb") as photo:
                await message.answer_photo(photo=photo)
        except Exception as e:
            logger.warning(f"Failed to send logo: {e}")
    
    # Send onboarding text
    await message.answer(get_onboarding_text())

    # Send report PDF after greeting (path в Config уже абсолютный от корня проекта)
    if Config.REPORT_PDF_PATH and os.path.isfile(Config.REPORT_PDF_PATH):
        try:
            await message.answer_document(
                FSInputFile(Config.REPORT_PDF_PATH),
                caption="Итоги 2025 — Москва и Санкт-Петербург",
            )
        except Exception as e:
            logger.warning("Failed to send report PDF: %s", e, exc_info=True)
    else:
        logger.warning("Report PDF not found at: %s", Config.REPORT_PDF_PATH)
    
    # Show main menu (inline)
    await message.answer(
        "Выберите раздел или напишите вопрос.",
        reply_markup=get_main_menu_inline()
    )


@router.message(Command("chatinfo"))
async def cmd_chatinfo(message: Message) -> None:
    """Show current chat/topic identifiers for routing notifications."""
    thread_id = getattr(message, "message_thread_id", None)
    is_topic_message = bool(getattr(message, "is_topic_message", False))
    title = getattr(message.chat, "title", None) or "-"
    username = f"@{message.chat.username}" if getattr(message.chat, "username", None) else "-"
    await message.answer(
        "🧭 Chat routing info\n\n"
        f"chat_id: <code>{message.chat.id}</code>\n"
        f"chat_type: <code>{message.chat.type}</code>\n"
        f"chat_title: <code>{title}</code>\n"
        f"chat_username: <code>{username}</code>\n"
        f"is_topic_message: <code>{is_topic_message}</code>\n"
        f"message_thread_id: <code>{thread_id if thread_id is not None else 0}</code>\n\n"
        "Отправь /chatinfo в каждой подтеме и сохрани соответствие topic -> thread_id.",
        parse_mode="HTML",
    )
