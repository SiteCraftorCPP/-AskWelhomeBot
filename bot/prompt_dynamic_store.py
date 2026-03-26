"""Editable storage for dynamic LLM blocks (agrealty-bot2)."""
from __future__ import annotations

import logging
from pathlib import Path

from bot.config import project_root
from bot.texts import (
    BLOCK_FEEDBACK_V1_3_4,
    BLOCK_PRICING_V1_3_4,
    BLOCK_RISKS_DOCS_V1_3_4,
    BLOCK_SPECIALIST_REQUEST_V1_3_4,
)

logger = logging.getLogger(__name__)

DATA_DIR = project_root / "data"

BLOCK_KEYS = ("feedback", "pricing", "risks_docs", "specialist_request")
DEFAULT_BLOCKS: dict[str, str] = {
    "feedback": BLOCK_FEEDBACK_V1_3_4,
    "pricing": BLOCK_PRICING_V1_3_4,
    "risks_docs": BLOCK_RISKS_DOCS_V1_3_4,
    "specialist_request": BLOCK_SPECIALIST_REQUEST_V1_3_4,
}
BLOCK_FILES: dict[str, Path] = {k: DATA_DIR / f"system_prompt_block_{k}.txt" for k in BLOCK_KEYS}


def get_dynamic_block(key: str) -> str:
    if key not in DEFAULT_BLOCKS:
        raise ValueError(f"Unknown block key: {key}")
    path = BLOCK_FILES[key]
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read block override %s: %s", path, e)
    return DEFAULT_BLOCKS[key]


def save_dynamic_block(key: str, text: str) -> None:
    if key not in DEFAULT_BLOCKS:
        raise ValueError(f"Unknown block key: {key}")
    text = (text or "").strip()
    if not text:
        raise ValueError("Текст блока не может быть пустым.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = BLOCK_FILES[key]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
