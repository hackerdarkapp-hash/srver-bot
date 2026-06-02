"""
security/safe_middleware.py — طبقة حماية شاملة تلتقط أي خطأ في أي handler
لا يمكن لأي استثناء —حتى BaseException— أن يُوقف البوت
"""

import logging
import traceback
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config import ADMIN_ID

logger = logging.getLogger(__name__)


class SafeHandlerMiddleware(BaseMiddleware):
    """
    يلفّ كل handler في try/except.
    إذا رمى Handler أي استثناء يُسجَّل الخطأ ويُبلَّغ الأدمن
    والبوت يستمر دون توقف.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event:   TelegramObject,
        data:    dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            tb = traceback.format_exc()[-800:]
            uid = _get_uid(event)
            logger.error(
                "SafeMiddleware caught: %s | user=%s\n%s",
                type(exc).__name__, uid, tb,
            )
            await _notify_admin(event, exc, tb)
            await _reply_user(event)
        except BaseException as exc:
            # SystemExit, KeyboardInterrupt, GeneratorExit ...
            logger.critical(
                "SafeMiddleware caught BaseException: %s\n%s",
                type(exc).__name__, traceback.format_exc()[-400:],
            )
            # لا نُعيد رميه حتى لا يُوقف البوت


# ── دوال مساعدة ─────────────────────────────────────────────────────────────

def _get_uid(event: TelegramObject) -> str:
    if isinstance(event, (Message, CallbackQuery)):
        u = event.from_user
        return f"{u.id} (@{u.username})" if u else "unknown"
    return "unknown"


async def _reply_user(event: TelegramObject) -> None:
    """يُرسل رسالة خطأ مختصرة للمستخدم."""
    try:
        if isinstance(event, Message):
            await event.answer("❌ حدث خطأ غير متوقع، حاول مرة أخرى.")
        elif isinstance(event, CallbackQuery):
            await event.answer("❌ حدث خطأ، حاول مرة أخرى.", show_alert=False)
    except Exception:
        pass


async def _notify_admin(event: TelegramObject, exc: Exception, tb: str) -> None:
    """يُبلّغ الأدمن بالخطأ عبر التيليجرام."""
    if not ADMIN_ID:
        return
    try:
        bot = None
        if isinstance(event, Message):
            bot = event.bot
            info = f"Message: <code>{event.text[:80] if event.text else '—'}</code>"
        elif isinstance(event, CallbackQuery):
            bot = event.bot
            info = f"Callback: <code>{event.data[:80] if event.data else '—'}</code>"
        else:
            return

        if bot:
            uid = _get_uid(event)
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ <b>خطأ في Handler</b>\n"
                f"👤 المستخدم: <code>{uid}</code>\n"
                f"{info}\n\n"
                f"<b>{type(exc).__name__}:</b> <code>{str(exc)[:200]}</code>\n\n"
                f"<pre>{tb[-600:]}</pre>",
                parse_mode="HTML",
            )
    except Exception:
        pass
