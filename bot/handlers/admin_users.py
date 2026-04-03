"""Админка: статистика по новым пользователям (первый /start)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import Config
from bot.handlers.admin import admin_panel_opening_html, is_admin, is_prompt_only_editor
from bot.keyboards import get_admin_panel_kb
from bot.prompt_store import can_edit_prompt
from bot.users_registry import build_export_tsv, get_stats

logger = logging.getLogger(__name__)
router = Router()

_MSK = ZoneInfo("Europe/Moscow")
PAGE_SIZE = 12


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


def _build_page_html(items: list[dict], page: int) -> tuple[str, int, int]:
    """
    HTML одной страницы. Возвращает (текст, страница 0-based, всего страниц).
    """
    total = len(items)
    if total == 0:
        return "<b>📊 Пользователи</b>", 0, 1

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]

    lines = [
        f"<b>📊 Пользователи</b>  <i>{page + 1}/{total_pages}</i>",
        "",
    ]
    for row in chunk:
        uid = row.get("user_id", "")
        un = row.get("username")
        fn = row.get("first_name") or ""
        ln = row.get("last_name") or ""
        name = " ".join(p for p in (fn, ln) if p).strip() or "—"
        at = f"@{escape(un)}" if un else "<i>—</i>"
        when = _format_msk(row.get("first_seen_at"))
        lines.append(
            f"• <code>{uid}</code> {at}\n  {escape(name)} · {escape(when)}"
        )
    return "\n".join(lines), page, total_pages


def _users_kb(page: int, total_pages: int, has_rows: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_rows and total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text="◀", callback_data=f"admin:users:p:{page - 1}")
            )
        nav.append(
            InlineKeyboardButton(
                text=f"· {page + 1}/{total_pages} ·",
                callback_data="admin:users:noop",
            )
        )
        if page < total_pages - 1:
            nav.append(
                InlineKeyboardButton(text="▶", callback_data=f"admin:users:p:{page + 1}")
            )
        rows.append(nav)
    rows.append(
        [InlineKeyboardButton(text="📥 Скачать .txt", callback_data="admin:users:export")]
    )
    rows.append(
        [InlineKeyboardButton(text="« В админ-панель", callback_data="admin:users:back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_users_screen(
    callback: CallbackQuery,
    page: int,
    *,
    edit: bool,
) -> None:
    _, items = get_stats()
    text, page, total_pages = _build_page_html(items, page)
    kb = _users_kb(page, total_pages, bool(items))
    if edit:
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.warning("admin users edit_text: %s", e)
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "admin:users")
async def cb_users_menu(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    un = callback.from_user.username
    if not is_admin(uid, un):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await _show_users_screen(callback, 0, edit=True)


@router.callback_query(F.data == "admin:users:noop")
async def cb_users_noop(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id, callback.from_user.username):
        await callback.answer()
        return
    await callback.answer()


@router.callback_query(F.data.startswith("admin:users:p:"))
async def cb_users_page(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    un = callback.from_user.username
    if not is_admin(uid, un):
        await callback.answer("Нет доступа", show_alert=True)
        return
    suffix = (callback.data or "").removeprefix("admin:users:p:")
    try:
        page = int(suffix)
    except ValueError:
        page = 0
    await callback.answer()
    await _show_users_screen(callback, page, edit=True)


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
        caption="Реестр первых /start (TSV).",
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
        admin_panel_opening_html(uid, un) + "\n\nВыберите действие:",
        reply_markup=get_admin_panel_kb(
            show_prompt=can_edit_prompt(uid, un),
            prompt_only=is_prompt_only_editor(uid, un),
            show_full_admin_tools=True,
        ),
        parse_mode="HTML",
    )
