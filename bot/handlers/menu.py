"""Handlers for /menu command and menu button clicks."""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from bot.keyboards import (
    get_main_menu,
    get_main_menu_inline,
    get_cancel_kb,
    get_rent_submenu,
    get_rent_submenu_inline,
    get_deal_submenu,
    get_buysell_submenu_inline,
    get_about_submenu,
)
from bot.texts import (
    MENU_RENT,
    MENU_BUY_SELL,
    MENU_ANALYTICS,
    MENU_DOCS_TAXES,
    MENU_ABOUT_SPECIALIST,
    RESPONSE_RENT,
    RESPONSE_BUY_SELL,
    RESPONSE_ANALYTICS,
    RESPONSE_DOCS_TAXES,
    RESPONSE_ABOUT,
    MENU_PROMPT,
    SPECIALIST_START,
    ABOUT_TEXT,
)
from bot.state import MenuState, SpecialistRequest

logger = logging.getLogger(__name__)
router = Router()


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """
    Безопасно редактирует текст сообщения, игнорируя ошибку "message is not modified".
    
    Args:
        callback: CallbackQuery объект
        text: Текст сообщения
        reply_markup: Опциональная клавиатура
    """
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            # Это нормальная ситуация при повторном нажатии на кнопку
            logger.debug(f"Message not modified (expected): {callback.data}")
        else:
            # Другие ошибки логируем как warning
            logger.warning(f"Failed to edit message: {e}")


@router.message(F.text == "/menu")
async def cmd_menu(message: Message) -> None:
    """Handle /menu command: show inline menu keyboard."""
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"User {user_id} (@{username}) sent /menu")
    
    await message.answer(
        MENU_PROMPT,
        reply_markup=get_main_menu_inline()
    )


@router.message(F.text.in_([MENU_RENT, MENU_BUY_SELL, MENU_ANALYTICS, MENU_DOCS_TAXES, MENU_ABOUT_SPECIALIST]))
async def handle_menu_button(message: Message, state: FSMContext) -> None:
    """Handle menu button clicks: save section and respond accordingly."""
    user_id = message.from_user.id
    username = message.from_user.username
    button_text = message.text
    logger.info(f"User {user_id} (@{username}) clicked menu button: {button_text}")
    
    # Handle rent - show inline submenu
    if button_text == MENU_RENT:
        await state.set_state(MenuState.selected_section)
        await state.update_data(selected_section="rent")
        await message.answer(RESPONSE_RENT, reply_markup=get_rent_submenu())
        return
    
    # Handle buy/sell - show inline submenu
    if button_text == MENU_BUY_SELL:
        await state.set_state(MenuState.selected_section)
        await state.update_data(selected_section="deal")
        await message.answer(RESPONSE_BUY_SELL, reply_markup=get_deal_submenu())
        return
    
    # Handle analytics
    if button_text == MENU_ANALYTICS:
        await state.set_state(MenuState.selected_section)
        await state.update_data(selected_section="market")
        await message.answer(RESPONSE_ANALYTICS)
        return
    
    # Handle docs/taxes
    if button_text == MENU_DOCS_TAXES:
        await state.set_state(MenuState.selected_section)
        await state.update_data(selected_section="docs_taxes")
        await message.answer(RESPONSE_DOCS_TAXES)
        return
    
    # Handle about/specialist - show inline submenu
    if button_text == MENU_ABOUT_SPECIALIST:
        await state.set_state(MenuState.selected_section)
        await state.update_data(selected_section="about_or_specialist")
        await message.answer("Выберите:", reply_markup=get_about_submenu())
        return


# Callback handlers for inline submenus
@router.callback_query(F.data.in_(["rent:take", "rent:give"]))
async def handle_rent_submenu(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle rent submenu callbacks (take/give)."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected rent submenu: {callback.data}")
    
    request_type = "снять" if callback.data == "rent:take" else "сдать"
    await state.update_data(request_type=request_type)
    
    await callback.answer()
    await callback.message.answer(f"Понял, вы хотите {request_type}. Задайте вопрос по аренде.")


@router.callback_query(F.data.in_(["deal:buy", "deal:sell"]))
async def handle_deal_submenu(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle deal submenu callbacks (buy/sell)."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected deal submenu: {callback.data}")
    
    request_type = "купить" if callback.data == "deal:buy" else "продать"
    await state.update_data(request_type=request_type)
    
    await callback.answer()
    await callback.message.answer(f"Понял, вы хотите {request_type}. Задайте вопрос по покупке/продаже.")


@router.callback_query(F.data == "about:info")
async def handle_about_info(callback: CallbackQuery) -> None:
    """Handle 'About company' callback."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected 'About company'")
    
    await callback.answer()
    await callback.message.answer(ABOUT_TEXT)


@router.callback_query(F.data == "about:specialist")
async def handle_about_specialist(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Contact specialist' callback - start SpecialistRequest flow."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected 'Contact specialist'")
    
    await callback.answer()
    
    # Check if city already exists in session data
    data = await state.get_data()
    city = data.get("city")
    
    if city:
        # Skip city question, go to property_type
        await state.set_state(SpecialistRequest.property_type)
        from bot.texts import SPECIALIST_ASK_TYPE
        await callback.message.answer(SPECIALIST_ASK_TYPE, reply_markup=get_cancel_kb())
    else:
        # Start from city
        await state.set_state(SpecialistRequest.city)
        await callback.message.answer(SPECIALIST_START, reply_markup=get_cancel_kb())


# Обработчики для нового inline-меню (v1.2.1)
@router.callback_query(F.data == "menu_main")
async def handle_menu_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Back to main menu' callback."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected 'Back to main menu'")
    
    await callback.answer()
    await safe_edit_text(callback, MENU_PROMPT, reply_markup=get_main_menu_inline())


@router.callback_query(F.data == "menu_rent")
async def handle_menu_rent(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Rent' menu callback."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected 'Rent' menu")
    
    await state.set_state(MenuState.selected_section)
    await state.update_data(selected_section="rent")
    
    await callback.answer()
    await safe_edit_text(callback, RESPONSE_RENT, reply_markup=get_rent_submenu_inline())


@router.callback_query(F.data == "menu_buysell")
async def handle_menu_buysell(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Buy/Sell' menu callback."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected 'Buy/Sell' menu")
    
    await state.set_state(MenuState.selected_section)
    await state.update_data(selected_section="deal")
    
    await callback.answer()
    await safe_edit_text(callback, RESPONSE_BUY_SELL, reply_markup=get_buysell_submenu_inline())


@router.callback_query(F.data == "menu_analytics")
async def handle_menu_analytics(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Analytics' menu callback."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected 'Analytics' menu")
    
    await state.set_state(MenuState.selected_section)
    await state.update_data(selected_section="market")
    
    await callback.answer()
    await safe_edit_text(callback, RESPONSE_ANALYTICS, reply_markup=get_main_menu_inline())


@router.callback_query(F.data == "menu_docs")
async def handle_menu_docs(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Documents/Taxes' menu callback."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected 'Documents/Taxes' menu")
    
    await state.set_state(MenuState.selected_section)
    await state.update_data(selected_section="docs_taxes")
    
    await callback.answer()
    await safe_edit_text(callback, RESPONSE_DOCS_TAXES, reply_markup=get_main_menu_inline())


@router.callback_query(F.data == "menu_other")
async def handle_menu_other(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Other/Ask question' menu callback."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected 'Other' menu")
    
    await state.set_state(MenuState.selected_section)
    await state.update_data(selected_section=None)
    
    await callback.answer()
    await safe_edit_text(callback, "Задайте ваш вопрос, и я постараюсь помочь.", reply_markup=get_main_menu_inline())


@router.callback_query(F.data.in_(["rent_find", "rent_list"]))
async def handle_rent_submenu_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle new rent submenu callbacks (rent_find/rent_list)."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected rent submenu: {callback.data}")
    
    request_type = "снять" if callback.data == "rent_find" else "сдать"
    await state.update_data(request_type=request_type)
    
    await callback.answer()
    await safe_edit_text(
        callback,
        f"Понял, вы хотите {request_type}. Задайте вопрос по аренде.",
        reply_markup=get_rent_submenu_inline()
    )


@router.callback_query(F.data.in_(["buy", "sell"]))
async def handle_buysell_submenu_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle new buy/sell submenu callbacks (buy/sell)."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} selected buy/sell submenu: {callback.data}")
    
    request_type = "купить" if callback.data == "buy" else "продать"
    await state.update_data(request_type=request_type)
    
    await callback.answer()
    await safe_edit_text(
        callback,
        f"Понял, вы хотите {request_type}. Задайте вопрос по покупке/продаже.",
        reply_markup=get_buysell_submenu_inline()
    )

