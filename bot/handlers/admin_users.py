"""Админка: статистика по новым пользователям (первый /start)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import Config
from bot.handlers.admin import is_admin, is_prompt_only_editor
from bot.keyboards import get_admin_panel_kb
from bot.prompt_store import can_edit_prompt
from bot.users_registry import build_export_tsv, get_stats

logger = logging.getLogger(__name__)
router = Router()

_MSK = ZoneInfo("Europe/Moscow")
_PREVIEW_LINES = 20


def _format_msk(iso_ts: str | None) -> str:
    if not iso_ts:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_MSK).strftime("%Y-%m-%d %H:%M МСК")
    except (ValueError, OSError):
        return iso_ts[:19] if len(iso_ts) >= 19 else iso_ts


def _preview_text(total: int, items: list[dict]) -> str:
    lines = [
        "<b>📊 Пользователи</b>",
        "",
        f"Всего зафиксировано первых <code>/start</code>: <b>{total}</b>",
        "",
        f"<i>Последние {_PREVIEW_LINES} (новые сверху):</i>",
        "",
    ]
    chunk = items[:_PREVIEW_LINES]
    if not chunk:
        lines.append("<i>Пока никого.</i>")
        return "\n".join(lines)
    for row in chunk:
        uid = row.get("user_id", "")
        un = row.get("username")
        fn = row.get("first_name") or ""
        ln = row.get("last_name") or ""
        name = " ".join(p for p in (fn, ln) if p).strip() or "—"
        at = f"@{escape(un)}" if un else "<i>без username</i>"
        when = _format_msk(row.get("first_seen_at"))
        lines.append(
            f"• <code>{uid}</code> {at} — {escape(name)}\n  {escape(when)}"
        )
    if total > _PREVIEW_LINES:
        lines.append("")
        lines.append(f"<i>… и ещё {total - _PREVIEW_LINES}. Полный список — кнопка ниже.</i>")
    return "\n".join(lines)


def _users_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Скачать полный список (.txt)", callback_data="admin:users:export")],
            [InlineKeyboardButton(text="« В админ-панель", callback_data="admin:users:back")],
        ]
    )


@router.callback_query(F.data == "admin:users")
async def cb_users_menu(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    un = callback.from_user.username
    if not is_admin(uid, un):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    total, items = get_stats()
    text = _preview_text(total, items)
    try:
        await callback.message.edit_text(text, reply_markup=_users_kb(), parse_mode="HTML")
    except Exception as e:
        logger.warning("admin users edit_text: %s", e)
        await callback.message.answer(text, reply_markup=_users_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin:users:export")
async def cb_users_export(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    un = callback.from_user.username
    if not is_admin(uid, un):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer("Готовлю файл…")
    raw = build_export_tsv().encode("utf-8")
    name = f"users_first_start_{Config.BOT_VERSION.replace('.', '_')}.txt"
    await callback.message.answer_document(
        BufferedInputFile(raw, filename=name),
        caption="Реестр первых /start: user_id, UTC-время, username, имя.",
    )


@router.callback_query(F.data == "admin:users:back")
async def cb_users_back(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    un = callback.from_user.username
    if not is_admin(uid, un):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "🔐 Админ-панель\n\nВыберите действие:",
        reply_markup=get_admin_panel_kb(
            show_prompt=can_edit_prompt(uid, un),
            prompt_only=is_prompt_only_editor(uid, un),
            show_users_stats=True,
        ),
    )
