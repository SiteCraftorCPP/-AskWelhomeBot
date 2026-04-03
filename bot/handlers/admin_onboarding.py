"""Админка: редактирование текста приветствия /start (файл data/onboarding_text.txt)."""
from __future__ import annotations

import io
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers.admin import (
    admin_panel_opening_html,
    is_admin,
    is_prompt_only_editor,
)
from bot.keyboards import get_admin_panel_kb
from bot.onboarding_store import get_onboarding_text, save_onboarding_text
from bot.prompt_store import can_edit_prompt
from bot.utils import send_long

logger = logging.getLogger(__name__)
router = Router()


class OnboardingAdminStates(StatesGroup):
    waiting_text = State()


def _onboarding_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👀 Показать в Telegram", callback_data="admin:onboarding:full")],
            [InlineKeyboardButton(text="📥 Скачать .txt", callback_data="admin:onboarding:download")],
            [InlineKeyboardButton(text="✏️ Заменить (текст или .txt)", callback_data="admin:onboarding:edit")],
            [InlineKeyboardButton(text="« В админ-панель", callback_data="admin:onboarding:back")],
        ]
    )


@router.callback_query(F.data == "admin:onboarding")
async def cb_onboarding_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "👋 Приветствие /start\n\nВыберите действие:",
        reply_markup=_onboarding_kb(),
    )


@router.callback_query(F.data == "admin:onboarding:full")
async def cb_onboarding_full(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer("Отправляю…")
    await send_long(callback.message, f"📄 Текущее приветствие\n\n{get_onboarding_text()}")


@router.callback_query(F.data == "admin:onboarding:download")
async def cb_onboarding_download(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    raw = get_onboarding_text().encode("utf-8")
    await callback.message.answer_document(
        BufferedInputFile(raw, filename="onboarding_start.txt"),
        caption="Текст приветствия /start (UTF-8).",
    )


@router.callback_query(F.data == "admin:onboarding:edit")
async def cb_onboarding_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await state.set_state(OnboardingAdminStates.waiting_text)
    await callback.message.answer(
        "✏️ Пришлите новый текст сообщением или файлом .txt\n\n"
        "Отмена: /cancel",
    )


@router.callback_query(F.data == "admin:onboarding:back")
async def cb_onboarding_back(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    un = callback.from_user.username
    if not is_admin(uid, un):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        admin_panel_opening_html(uid, un) + "\n\nВыберите действие:",
        reply_markup=get_admin_panel_kb(
            show_prompt=can_edit_prompt(uid, un),
            prompt_only=is_prompt_only_editor(uid, un),
            show_full_admin_tools=True,
        ),
        parse_mode="HTML",
    )


@router.message(OnboardingAdminStates.waiting_text, Command("cancel"))
async def onboarding_edit_cancel(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    await state.clear()
    await message.answer("Отменено.")


@router.message(OnboardingAdminStates.waiting_text, F.text)
async def onboarding_edit_text(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пусто. Пришлите текст или /cancel.")
        return
    try:
        save_onboarding_text(text)
    except ValueError as e:
        await message.answer(f"❌ {e}")
        return
    await state.clear()
    await message.answer("✅ Приветствие сохранено. Новый текст покажется при следующем /start.")


@router.message(OnboardingAdminStates.waiting_text, F.document)
async def onboarding_edit_document(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id, message.from_user.username):
        await state.clear()
        return
    doc = message.document
    if not doc:
        return
    if doc.file_size and doc.file_size > 512 * 1024:
        await message.answer("❌ Файл слишком большой (макс. 512 КБ).")
        return
    fn = (doc.file_name or "").lower()
    if fn and not fn.endswith(".txt"):
        await message.answer("❌ Пришлите `.txt` (UTF-8).")
        return
    buf = io.BytesIO()
    try:
        await bot.download(doc, destination=buf)
    except Exception as e:
        logger.error("onboarding download: %s", e, exc_info=True)
        await message.answer("❌ Не удалось скачать файл.")
        return
    raw = buf.getvalue()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        await message.answer("❌ Неверная кодировка. Сохраните как UTF-8.")
        return
    try:
        save_onboarding_text(text)
    except ValueError as e:
        await message.answer(f"❌ {e}")
        return
    await state.clear()
    await message.answer("✅ Приветствие загружено из файла.")
