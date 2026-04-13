"""Configuration helpers for the Telegram bot."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramBotSettings:
    token: str
    allowed_chat_id: int


def load_settings() -> TelegramBotSettings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is required.")

    return TelegramBotSettings(token=token, allowed_chat_id=int(chat_id))
