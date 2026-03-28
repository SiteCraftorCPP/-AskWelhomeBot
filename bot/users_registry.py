"""Персистентный реестр пользователей: кто впервые нажал /start и когда (UTC в файле)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bot.config import project_root

logger = logging.getLogger(__name__)

DATA_DIR = project_root / "data"
REGISTRY_PATH = DATA_DIR / "users_registry.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_raw() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        return {"version": 1, "users": {}}
    try:
        raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"version": 1, "users": {}}
        users = raw.get("users")
        if not isinstance(users, dict):
            users = {}
        return {"version": int(raw.get("version", 1)), "users": users}
    except (OSError, json.JSONDecodeError) as e:
        logger.error("users_registry load failed: %s", e)
        return {"version": 1, "users": {}}


def _save_raw(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(REGISTRY_PATH)


def record_first_start(
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> bool:
    """
    Зафиксировать первый /start. Возвращает True, если пользователь новый.
    """
    data = _load_raw()
    users: dict[str, Any] = data["users"]
    key = str(user_id)
    if key in users:
        return False
    users[key] = {
        "first_seen_at": _utc_now_iso(),
        "username": (username or "").strip() or None,
        "first_name": (first_name or "").strip() or None,
        "last_name": (last_name or "").strip() or None,
    }
    _save_raw(data)
    logger.info("New user in registry: %s @%s", user_id, username or "-")
    return True


def get_stats() -> tuple[int, list[dict[str, Any]]]:
    """Число пользователей и записи по убыванию даты первого /start."""
    data = _load_raw()
    users = data.get("users", {})
    items: list[dict[str, Any]] = []
    for uid_str, u in users.items():
        if not isinstance(u, dict):
            continue
        try:
            uid = int(uid_str)
        except ValueError:
            continue
        row = {"user_id": uid, **u}
        items.append(row)
    items.sort(key=lambda x: x.get("first_seen_at") or "", reverse=True)
    return len(items), items


def build_export_tsv() -> str:
    """Полный список для .txt (табуляция, UTF-8)."""
    _, items = get_stats()
    lines = ["user_id\tfirst_seen_utc\tusername\tfirst_name\tlast_name"]
    for row in items:
        lines.append(
            "\t".join(
                [
                    str(row.get("user_id", "")),
                    str(row.get("first_seen_at", "")),
                    str(row.get("username") or ""),
                    str(row.get("first_name") or ""),
                    str(row.get("last_name") or ""),
                ]
            )
        )
    return "\n".join(lines)
