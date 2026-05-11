"""
bot.py — نقطة الدخول الرئيسية
• Global Error Handling  • Anti-Crash System  • Auto-Reconnect
• Webhook (إنتاج) / Polling (تطوير)
"""

import asyncio
import logging
import os
import sys
import time
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

import database as db
from config import ADMIN_ID, BOT_TOKEN, SESSION_SECRET, DEFAULT_FREE_TOOLS
from handlers import (
    nav_router, panel_router, start_router,
    usermgmt_router, wizard_router, tools_router,
)
from security import AntiSpamMiddleware

# ─── مجلد السجلات ────────────────────────────────────────────────────────────
os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  أوامر البوت
# ══════════════════════════════════════════════════════════════

async def set_commands(bot: Bot) -> None:
    public = [BotCommand(command="start", description="▶️ بدء البوت")]
    admin  = [
        BotCommand(command="start", description="▶️ بدء البوت"),
        BotCommand(command="admin", description="🎛 لوحة التحكم"),
    ]
    await bot.set_my_commands(public, scope=BotCommandScopeDefault())
    if ADMIN_ID:
        try:
            await bot.set_my_commands(admin, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
            logger.info("✅ أوامر المشرف مُضبطة للمستخدم %s", ADMIN_ID)
        except Exception as e:
            logger.warning("تعذّر ضبط أوامر المشرف: %s", e)


# ══════════════════════════════════════════════════════════════
#  Global Error Handler
# ══════════════════════════════════════════════════════════════

async def global_error_handler(event, exception) -> bool:
    logger.error(
        "خطأ غير مُعالَج:\nEvent: %s\nException: %s\n%s",
        type(event).__name__, type(exception).__name__, traceback.format_exc(),
    )
    if ADMIN_ID:
        try:
            bot = event.bot if hasattr(event, "bot") else None
            if bot:
                tb = traceback.format_exc()[-800:]
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>خطأ في البوت</b>\n\n<code>{tb}</code>",
                    parse_mode="HTML",
                )
        except Exception:
            pass
    return True


# ══════════════════════════════════════════════════════════════
#  Webhook
# ══════════════════════════════════════════════════════════════

async def _health(request):
    from aiohttp import web as w
    return w.Response(text="✅ Bot running", status=200)


async def run_webhook(bot: Bot, dp: Dispatcher, port: int) -> None:
    from aiohttp import web as w
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    domains = os.environ.get("REPLIT_DOMAINS", "")
    if domains:
        domain      = domains.split(",")[0].strip()
        webhook_url = f"https://{domain}/webhook"
        await bot.set_webhook(webhook_url, secret_token=SESSION_SECRET)
        logger.info("✅ Webhook: %s", webhook_url)
    else:
        logger.warning("REPLIT_DOMAINS غير موجود — تشغيل الخادم بدون webhook")

    app = w.Application()
    app.router.add_get("/",        _health)
    app.router.add_get("/healthz", _health)
    SimpleRequestHandler(dp, bot, secret_token=SESSION_SECRET).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    runner = w.AppRunner(app)
    await runner.setup()
    await w.TCPSite(runner, "0.0.0.0", port).start()
    logger.info("🌐 خادم Webhook يعمل على المنفذ %d", port)
    await asyncio.sleep(float("inf"))


# ══════════════════════════════════════════════════════════════
#  مهمة Heartbeat — تسجيل دوري كل 30 دقيقة
# ══════════════════════════════════════════════════════════════

async def _heartbeat() -> None:
    while True:
        await asyncio.sleep(1800)
        logger.info("💓 البوت يعمل بشكل طبيعي.")


# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════════

async def main() -> None:
    if not BOT_TOKEN:
        logger.critical("❌ TELEGRAM_BOT_TOKEN غير موجود! أضفه في Secrets")
        sys.exit(1)

    if not ADMIN_ID:
        logger.warning("⚠️ ADMIN_TELEGRAM_ID غير محدد")

    # ── تهيئة قاعدة البيانات ──────────────────────────────────
    db.init_db()
    db.seed_default_tools(DEFAULT_FREE_TOOLS)
    logger.info("✅ الأدوات الافتراضية جاهزة")

    # ── إنشاء جلسة HTTP مع timeout ────────────────────────────
    session = AiohttpSession(timeout=30)
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # ── إعداد Dispatcher ──────────────────────────────────────
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AntiSpamMiddleware())
    dp.callback_query.middleware(AntiSpamMiddleware())
    dp.errors.register(global_error_handler)

    dp.include_router(tools_router)
    dp.include_router(panel_router)
    dp.include_router(wizard_router)
    dp.include_router(usermgmt_router)
    dp.include_router(nav_router)
    dp.include_router(start_router)

    try:
        await set_commands(bot)
    except Exception as e:
        logger.warning("تعذّر ضبط الأوامر: %s", e)

    # ── اختيار وضع التشغيل ────────────────────────────────────
    bot_port = os.environ.get("BOT_PORT") or os.environ.get("PORT")
    if bot_port:
        logger.info("🚀 وضع الإنتاج — Webhook (PORT=%s)", bot_port)
        await run_webhook(bot, dp, int(bot_port))
    else:
        logger.info("🤖 وضع التطوير — Long Polling")
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception as e:
            logger.warning("تعذّر حذف الـ webhook: %s", e)

        # تشغيل heartbeat في الخلفية
        asyncio.create_task(_heartbeat())

        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_signals=False,
                polling_timeout=30,
            )
        finally:
            try:
                await bot.session.close()
            except Exception:
                pass
            logger.info("🛑 البوت توقف.")


# ══════════════════════════════════════════════════════════════
#  Anti-Crash — إعادة تشغيل لا نهائية مع Exponential Backoff
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    INITIAL_DELAY = 3   # ثواني
    MAX_DELAY     = 60  # الحد الأقصى للانتظار
    delay         = INITIAL_DELAY
    attempt       = 0

    while True:
        attempt += 1
        try:
            logger.info("🚀 تشغيل البوت (محاولة #%d)...", attempt)
            asyncio.run(main())
            # إذا انتهى main() بشكل طبيعي (لا يحدث) نوقف
            logger.info("✅ انتهى main() بشكل طبيعي.")
            break

        except KeyboardInterrupt:
            logger.info("🛑 تم إيقاف البوت يدوياً.")
            break

        except Exception as exc:
            logger.error(
                "💥 انهيار غير متوقع (#%d): %s\n%s\n— إعادة المحاولة بعد %ds",
                attempt, type(exc).__name__, traceback.format_exc()[-600:], delay,
            )
            time.sleep(delay)
            # Exponential backoff: تضاعف وقت الانتظار حتى MAX_DELAY
            delay = min(delay * 2, MAX_DELAY)
