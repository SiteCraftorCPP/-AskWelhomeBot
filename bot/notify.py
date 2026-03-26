"""Отправка уведомлений админам: супергруппа с подтемами или личка."""
from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot

from bot.config import Config

logger = logging.getLogger(__name__)


def _admin_dm_targets() -> list[int]:
    ids = [a for a in getattr(Config, "ADMIN_CHAT_IDS", []) if a > 0]
    if not ids and Config.ADMIN_CHAT_ID > 0:
        ids = [Config.ADMIN_CHAT_ID]
    return ids


async def send_notification(
    bot: Bot,
    text: str,
    *,
    topic_id: int = 0,
    parse_mode: str | None = None,
) -> bool:
    """
    Сначала — в NOTIFICATION_CHAT_ID / FEEDBACK_CHAT_ID + message_thread_id (если задано).
    Иначе — в каждый ADMIN_CHAT_ID (личка / как раньше).
    """
    chat_id = Config.NOTIFICATION_CHAT_ID
    kwargs: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    if topic_id and topic_id > 0:
        kwargs["message_thread_id"] = topic_id

    if chat_id:
        try:
            await bot.send_message(**kwargs)
            logger.info("Notification sent to chat_id=%s thread=%s", chat_id, topic_id or None)
            return True
        except Exception as e:
            logger.error("Failed to send to group chat_id=%s: %s", chat_id, e, exc_info=True)

    sent = False
    for aid in _admin_dm_targets():
        try:
            dm_kwargs: dict[str, Any] = {"chat_id": aid, "text": text}
            if parse_mode:
                dm_kwargs["parse_mode"] = parse_mode
            await bot.send_message(**dm_kwargs)
            logger.info("Notification sent to admin DM chat_id=%s", aid)
            sent = True
        except Exception as e:
            logger.error("Failed to send notification to admin %s: %s", aid, e, exc_info=True)
    return sent
