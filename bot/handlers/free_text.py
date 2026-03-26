"""Handler for free text input (not commands or menu buttons)."""
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.texts import (
    MENU_RENT,
    MENU_BUY_SELL,
    MENU_ANALYTICS,
    MENU_DOCS_TAXES,
    MENU_ABOUT_SPECIALIST,
    FEEDBACK_THANKS_DOWN_FINAL,
    DISCLAIMER_A,
    DISCLAIMER_D,
)
from bot.state import MenuState, FeedbackState, SpecialistRequest
from bot.llm import generate_reply
from bot.keyboards import get_feedback_keyboard
from bot.config import Config
from bot.context import get_session_context, add_to_conversation_history
from bot.errors import handle_error, APITimeoutError
from bot.utils import (
    is_docs_or_taxes_topic,
    add_disclaimer_if_needed,
    BotResponse,
    send_long,
    add_history,
)

logger = logging.getLogger(__name__)
router = Router()

# Keywords that indicate need for specialist (for adding suggestion after answer)
SPECIALIST_KEYWORDS = [
    "оцен",
    "за сколько",
    "бюджет",
    "что лучше",
    "ипотек",
    "налог",
    "документ",
]


@router.message(
    F.text,
    ~F.text.startswith("/"),  # Exclude commands
    ~F.text.in_([MENU_RENT, MENU_BUY_SELL, MENU_ANALYTICS, MENU_DOCS_TAXES, MENU_ABOUT_SPECIALIST])  # Exclude menu buttons
)
async def handle_free_text(message: Message, state: FSMContext) -> None:
    """Handle free text input: check feedback state, generate LLM reply with disclaimers."""
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"
    text = message.text
    logger.info(f"User {user_id} (@{username}) sent text: {text}")
    
    # Add to history
    add_history(user_id, "U", text)
    
    # Check current state
    current_state = await state.get_state()
    
    # If user is in specialist consultation flow, let specialist.py handle it
    if current_state and current_state.startswith("SpecialistRequest"):
        return
    
    # Check if user is in feedback comment state (v1.1: awaiting_other_comment)
    if current_state == FeedbackState.awaiting_comment or current_state == FeedbackState.awaiting_other_comment:
        # This is handled in feedback.py, but keep for backward compatibility
        # The new flow uses awaiting_other_comment
        return
    
    # Regular question handling - ALWAYS call LLM first (v1.1 principle)
    # Получаем контекст сессии
    context = await get_session_context(state)
    selected_section = context.get("selected_section")
    
    # Добавляем сообщение в историю разговора
    await add_to_conversation_history(state, "U", text)
    
    # Подготавливаем session_data для LLM (для обратной совместимости)
    collected_data = context.get("collected_data", {})
    session_data = {
        "collected_data": collected_data,
        "asked_questions": context.get("asked_questions", []),
        "selected_section": selected_section,
    }
    
    # Также добавляем плоские поля для обратной совместимости
    if collected_data.get("location", {}).get("city"):
        session_data["city"] = collected_data["location"]["city"]
    if collected_data.get("object_type"):
        session_data["property_type"] = collected_data["object_type"]
    if collected_data.get("request_type"):
        session_data["request_type"] = collected_data["request_type"]
    if collected_data.get("budget"):
        session_data["budget"] = collected_data["budget"]
    if collected_data.get("urgency"):
        session_data["urgency"] = collected_data["urgency"]
    
    # Send loading messages
    loading_msg1 = await message.answer("🤖")
    loading_msg2 = await message.answer("<i>Анализирую ваш вопрос и готовлю ответ…</i>", parse_mode="HTML")
    
    # Определяем topic для BotResponse
    if is_docs_or_taxes_topic(text, selected_section):
        topic = 'tax'
    elif selected_section == "market" or selected_section == "analytics":
        topic = 'analytics'
    else:
        topic = 'general'
    
    # Generate LLM reply
    bot_response = None
    try:
        reply_text = await generate_reply(text, selected_section, session_data if session_data else None)
        
        # Создаем BotResponse
        bot_response = BotResponse(
            text=reply_text,
            has_useful_content=True,
            is_system_message=False,
            is_error=False,
            topic=topic
        )
    except Exception as e:
        logger.error(f"Error generating reply: {e}", exc_info=True)
        # Обрабатываем ошибку через централизованный обработчик
        error_context = {"user_id": user_id}
        bot_response = handle_error(e, error_context)
    finally:
        # Delete loading messages
        try:
            await loading_msg1.delete()
            await loading_msg2.delete()
        except Exception as e:
            logger.warning(f"Failed to delete loading messages: {e}")
    
    # Добавляем disclaimer, если нужно
    final_text = add_disclaimer_if_needed(bot_response)
    
    # Check if specialist suggestion is needed (after answer)
    text_lower = text.lower()
    needs_specialist_suggestion = any(keyword in text_lower for keyword in SPECIALIST_KEYWORDS)
    
    if needs_specialist_suggestion and bot_response.has_useful_content:
        specialist_note = "\n\nЕсли хотите, можем подключить специалиста: опишите город/тип объекта/цель и бюджет (или \"не знаю\") — я передам запрос."
        final_text += specialist_note
    
    # Save data for feedback
    await state.update_data(
        last_question_text=text,
        last_answer_text=final_text,
        last_section=selected_section or "не выбран"
    )
    
    # Добавляем в историю разговора
    await add_to_conversation_history(state, "B", final_text)
    
    # Add to legacy history (для обратной совместимости)
    add_history(user_id, "B", final_text)
    
    # Send using send_long
    await send_long(message, final_text, reply_markup=get_feedback_keyboard())
