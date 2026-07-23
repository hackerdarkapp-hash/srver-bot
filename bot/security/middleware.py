"""
security/middleware.py — حماية من السبام والإغراق
مُحصَّن: أي خطأ داخلي لا يُوقف البوت، يُسجَّل ويستمر
"""

import time
import logging
import traceback
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config import ADMIN_ID, RATE_LIMIT_SECONDS, MAX_MSG_PER_MINUTE

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
        try:
            return await self._check(handler, event, data)
        except Exception:
            logger.error(
                "AntiSpamMiddleware خطأ داخلي:\n%s", traceback.format_exc()[-400:],
            )
            # نمرر الحدث للـ handler مباشرةً بدلاً من إيقاف البوت
            try:
                return await handler(event, data)
            except Exception:
                pass

    async def _check(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:   TelegramObject,
        data:    dict[str, Any],
    ) -> Any:
        uid = None
        if isinstance(event, (Message, CallbackQuery)):
            uid = event.from_user.id if event.from_user else None

        if uid:
            # سجّل التفاعل مع كل بوت، وليس /start فقط. هذا يحافظ على
            # جمهور البوتات الجديدة والقديمة في قاعدة البيانات المشتركة.
            try:
                import database as db
                user = event.from_user
                bot = data.get("bot") or getattr(event, "bot", None)
                bot_id = getattr(bot, "id", None)
                db.save_user(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    bot_id=bot_id,
                )
            except Exception as e:
                logger.warning("AntiSpam: تعذّر تسجيل العضو: %s", e)

            # حساب الأدمن يجب أن يبقى قادرًا على إدارة كل البوتات حتى لو
            # سُجّل سابقًا كمحظور أو أرسل أوامر متتابعة عبر عدة بوتات.
            # عدّاد السرعة مشترك بين البوتات، لذلك سيمنع الأدمن عرضيًا
            # إذا لم نستثنه هنا.
            if uid == ADMIN_ID:
                return await handler(event, data)

            # فحص الحظر عبر DB بأمان منفصل
            try:
                user = db.get_user(uid)
                if user and user.get("is_blocked"):
                    if isinstance(event, Message):
                        await event.answer("🚫 أنت محظور من استخدام البوت.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("🚫 أنت محظور.", show_alert=True)
                    return
            except Exception as e:
                logger.warning("AntiSpam: تخطي فحص الحظر (خطأ DB): %s", e)

            now  = time.time()
            last = _last_msg.get(uid, 0)
            if now - last < RATE_LIMIT_SECONDS:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer("⏳ انتظر لحظة...", show_alert=False)
                    except Exception:
                        pass
                return

            _last_msg[uid] = now
            times = _msg_times[uid]
            times.append(now)
            _msg_times[uid] = [t for t in times if now - t < 60]
            if len(_msg_times[uid]) > MAX_MSG_PER_MINUTE:
                if isinstance(event, Message):
                    try:
                        await event.answer("⚠️ أرسلت الكثير من الرسائل، انتظر دقيقة.")
                    except Exception:
                        pass
                return

        return await handler(event, data)
