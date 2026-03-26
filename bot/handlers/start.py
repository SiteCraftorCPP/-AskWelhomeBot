"""Handler for /start command."""
import os
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.config import Config
from bot.keyboards import get_main_menu_inline
from bot.texts import ONBOARDING_TEXT

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command: send logo (if exists), onboarding text, and main menu."""
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"User {user_id} (@{username}) sent /start")
    
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
    await message.answer(ONBOARDING_TEXT)
    
    # Show main menu (inline)
    await message.answer(
        "Выберите раздел или напишите вопрос.",
        reply_markup=get_main_menu_inline()
    )
