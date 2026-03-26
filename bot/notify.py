"""Отправка уведомлений только в супергруппу с подтемами (forum). Личка админам не используется."""
from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot

from bot.config import Config

logger = logging.getLogger(__name__)


async def send_notification(
    bot: Bot,
    text: str,
    *,
    topic_id: int = 0,
    parse_mode: str | None = None,
) -> bool:
    """
    Только NOTIFICATION_CHAT_ID (или FEEDBACK_CHAT_ID в конфиге) + message_thread_id при необходимости.
    В личку админам не шлём.
    """
    chat_id = Config.NOTIFICATION_CHAT_ID
    if not chat_id:
        logger.warning(
            "Уведомление не отправлено: в .env не задан FEEDBACK_CHAT_ID / NOTIFICATION_CHAT_ID"
        )
        return False

    kwargs: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    if topic_id and topic_id > 0:
        kwargs["message_thread_id"] = topic_id

    try:
        await bot.send_message(**kwargs)
        logger.info("Notification sent to chat_id=%s thread=%s", chat_id, topic_id or None)
        return True
    except Exception as e:
        logger.error("Failed to send to chat_id=%s: %s", chat_id, e, exc_info=True)
        return False
