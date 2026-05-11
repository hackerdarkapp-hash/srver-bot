"""
security/middleware.py — حماية من السبام والإغراق
"""

import time
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

import database as db
from config import RATE_LIMIT_SECONDS, MAX_MSG_PER_MINUTE

logger = logging.getLogger(__name__)

_msg_times: dict[int, list[float]] = defaultdict(list)
_last_msg:  dict[int, float]       = {}


class AntiSpamMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:   TelegramObject,
        data:    dict[str, Any],
    ) -> Any:
        uid = None
        if isinstance(event, (Message, CallbackQuery)):
            uid = event.from_user.id if event.from_user else None

        if uid:
            user = db.get_user(uid)
            if user and user.get("is_blocked"):
                if isinstance(event, Message):
                    await event.answer("🚫 أنت محظور من استخدام البوت.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 أنت محظور.", show_alert=True)
                return

            now  = time.time()
            last = _last_msg.get(uid, 0)
            if now - last < RATE_LIMIT_SECONDS:
                if isinstance(event, CallbackQuery):
                    await event.answer("⏳ انتظر لحظة...", show_alert=False)
                return

            _last_msg[uid] = now
            times = _msg_times[uid]
            times.append(now)
            _msg_times[uid] = [t for t in times if now - t < 60]
            if len(_msg_times[uid]) > MAX_MSG_PER_MINUTE:
                if isinstance(event, Message):
                    await event.answer("⚠️ أرسلت الكثير من الرسائل، انتظر دقيقة.")
                return

        return await handler(event, data)
