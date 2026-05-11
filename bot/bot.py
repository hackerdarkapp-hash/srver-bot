"""
bot.py — نظام تشغيل البوت للعمل 24/7 على Render
═══════════════════════════════════════════════════
• HTTP Keep-Alive Server   • Self-Ping كل 10 دقائق
• Anti-Crash System        • Auto-Reconnect
• Memory Monitor           • Detailed Logging
• Global Error Handler     • Graceful Shutdown
"""

import asyncio
import gc
import logging
import os
import sys
import time
import traceback
from datetime import datetime

from aiohttp import web as aio_web, ClientSession, ClientTimeout
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

import database as db
from config import ADMIN_ID, BOT_TOKEN, SESSION_SECRET, DEFAULT_FREE_TOOLS
from handlers import (
    nav_router, panel_router, start_router,
    usermgmt_router, wizard_router, tools_router,
)
from security import AntiSpamMiddleware


# ══════════════════════════════════════════════════════════════
#  إعداد السجلات
# ══════════════════════════════════════════════════════════════

os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a"),
    ],
)
# تقليل ضوضاء المكتبات الخارجية
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
#  حالة عامة
# ══════════════════════════════════════════════════════════════

BOT_START_TIME   = datetime.now()
_polling_running = False
_reconnect_count = 0


# ══════════════════════════════════════════════════════════════
#  HTTP Server — Keep-Alive + Health Endpoints
# ══════════════════════════════════════════════════════════════

async def _health(request: aio_web.Request) -> aio_web.Response:
    uptime  = datetime.now() - BOT_START_TIME
    hours   = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    return aio_web.json_response({
        "status":    "ok",
        "bot":       "بوت الاختراق",
        "uptime":    f"{hours}h {minutes}m",
        "polling":   _polling_running,
        "reconnects": _reconnect_count,
        "timestamp": datetime.now().isoformat(),
    })


async def _metrics(request: aio_web.Request) -> aio_web.Response:
    try:
        import tracemalloc
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        mem_info = f"{current/1024/1024:.1f} MB (peak: {peak/1024/1024:.1f} MB)"
    except Exception:
        mem_info = "غير متاح"

    return aio_web.json_response({
        "memory":    mem_info,
        "polling":   _polling_running,
        "reconnects": _reconnect_count,
        "uptime_sec": int((datetime.now() - BOT_START_TIME).total_seconds()),
    })


async def run_web_server(port: int) -> None:
    app = aio_web.Application()
    app.router.add_get("/",        _health)
    app.router.add_get("/healthz", _health)
    app.router.add_get("/health",  _health)
    app.router.add_get("/metrics", _metrics)

    runner = aio_web.AppRunner(app)
    await runner.setup()
    site = aio_web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("🌐 خادم HTTP يعمل على المنفذ %d", port)


# ══════════════════════════════════════════════════════════════
#  Self-Ping — منع النوم على Render (كل 10 دقائق)
# ══════════════════════════════════════════════════════════════

async def self_ping_task(port: int) -> None:
    """يُرسل طلب HTTP لنفسه كل 10 دقائق لمنع Render من إيقاف الخدمة."""
    await asyncio.sleep(60)  # انتظر دقيقة قبل البدء

    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    local_url  = f"http://localhost:{port}/healthz"
    url        = f"{render_url}/healthz" if render_url else local_url

    logger.info("💓 Self-Ping مفعّل → %s", url)

    timeout = ClientTimeout(total=15)
    while True:
        await asyncio.sleep(600)  # كل 10 دقائق
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        logger.info("💓 Self-Ping ✅ (%s)", url)
                    else:
                        logger.warning("💓 Self-Ping ⚠️ status=%d", resp.status)
        except Exception as e:
            logger.warning("💓 Self-Ping فشل: %s", e)


# ══════════════════════════════════════════════════════════════
#  Heartbeat — سجل دوري كل 30 دقيقة
# ══════════════════════════════════════════════════════════════

async def heartbeat_task() -> None:
    while True:
        await asyncio.sleep(1800)
        uptime = datetime.now() - BOT_START_TIME
        hours  = int(uptime.total_seconds() // 3600)
        mins   = int((uptime.total_seconds() % 3600) // 60)
        try:
            import tracemalloc
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            cur, _ = tracemalloc.get_traced_memory()
            mem = f"{cur/1024/1024:.1f}MB"
        except Exception:
            mem = "N/A"
        gc.collect()
        logger.info(
            "💓 Heartbeat | uptime=%dh%dm | mem=%s | reconnects=%d | polling=%s",
            hours, mins, mem, _reconnect_count, _polling_running,
        )


# ══════════════════════════════════════════════════════════════
#  أوامر البوت
# ══════════════════════════════════════════════════════════════

async def set_commands(bot: Bot) -> None:
    public = [BotCommand(command="start", description="▶️ بدء البوت")]
    admin  = [
        BotCommand(command="start", description="▶️ بدء البوت"),
        BotCommand(command="admin", description="🎛 لوحة التحكم"),
    ]
    try:
        await bot.set_my_commands(public, scope=BotCommandScopeDefault())
        if ADMIN_ID:
            await bot.set_my_commands(admin, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
            logger.info("✅ أوامر المشرف مُضبطة للمستخدم %s", ADMIN_ID)
    except Exception as e:
        logger.warning("تعذّر ضبط الأوامر: %s", e)


# ══════════════════════════════════════════════════════════════
#  Global Error Handler
# ══════════════════════════════════════════════════════════════

async def global_error_handler(event, exception) -> bool:
    tb_text = traceback.format_exc()
    logger.error(
        "⚠️ خطأ غير مُعالَج | Event=%s | Exception=%s\n%s",
        type(event).__name__, type(exception).__name__, tb_text[-800:],
    )
    if ADMIN_ID:
        try:
            bot = event.bot if hasattr(event, "bot") else None
            if bot:
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>خطأ في البوت</b>\n\n"
                    f"<b>النوع:</b> <code>{type(exception).__name__}</code>\n\n"
                    f"<code>{tb_text[-600:]}</code>",
                    parse_mode="HTML",
                )
        except Exception:
            pass
    return True


# ══════════════════════════════════════════════════════════════
#  Polling مع Auto-Reconnect
# ══════════════════════════════════════════════════════════════

async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    global _polling_running, _reconnect_count

    INITIAL_DELAY = 3
    MAX_DELAY     = 120
    delay         = INITIAL_DELAY

    while True:
        _polling_running = False
        try:
            logger.info("🔄 بدء Polling (محاولة #%d)...", _reconnect_count + 1)
            await bot.delete_webhook(drop_pending_updates=(_reconnect_count == 0))
            _polling_running = True
            delay = INITIAL_DELAY  # إعادة تعيين التأخير عند النجاح

            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_signals=False,
                polling_timeout=30,
            )

        except TelegramRetryAfter as e:
            _polling_running = False
            wait = e.retry_after + 5
            logger.warning("⏳ Telegram طلب الانتظار %ds (RetryAfter)", wait)
            await asyncio.sleep(wait)

        except TelegramNetworkError as e:
            _polling_running = False
            _reconnect_count += 1
            logger.error("🌐 خطأ شبكة Telegram: %s — إعادة المحاولة بعد %ds", e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)

        except TelegramAPIError as e:
            _polling_running = False
            _reconnect_count += 1
            logger.error("📡 خطأ Telegram API: %s — إعادة المحاولة بعد %ds", e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)

        except asyncio.CancelledError:
            logger.info("🛑 Polling أُوقف.")
            _polling_running = False
            return

        except Exception as e:
            _polling_running = False
            _reconnect_count += 1
            logger.error(
                "💥 خطأ غير متوقع في Polling: %s\n%s\n— إعادة بعد %ds",
                type(e).__name__, traceback.format_exc()[-600:], delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)


# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════════

async def main() -> None:
    if not BOT_TOKEN:
        logger.critical("❌ TELEGRAM_BOT_TOKEN غير موجود! أضفه في Environment Variables")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("🚀 تشغيل بوت الاختراق | %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # ── قاعدة البيانات ────────────────────────────────────────
    db.init_db()
    db.seed_default_tools(DEFAULT_FREE_TOOLS)
    logger.info("✅ قاعدة البيانات جاهزة")

    # ── جلسة HTTP مع Timeout ──────────────────────────────────
    session = AiohttpSession(timeout=30)
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # ── Dispatcher ────────────────────────────────────────────
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

    await set_commands(bot)

    # ── اختيار المنفذ ─────────────────────────────────────────
    port = int(os.environ.get("PORT", 8080))
    logger.info("📡 المنفذ: %d", port)
    logger.info("🌍 Render URL: %s", os.environ.get("RENDER_EXTERNAL_URL", "غير محدد"))

    # ── تشغيل كل المهام معاً ──────────────────────────────────
    try:
        await asyncio.gather(
            run_web_server(port),
            self_ping_task(port),
            heartbeat_task(),
            run_polling(bot, dp),
        )
    except asyncio.CancelledError:
        logger.info("🛑 إيقاف المهام...")
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass
        logger.info("🛑 البوت أُوقف.")


# ══════════════════════════════════════════════════════════════
#  Anti-Crash — إعادة تشغيل لا نهائية
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    INITIAL_DELAY = 5
    MAX_DELAY     = 60
    delay         = INITIAL_DELAY
    attempt       = 0

    import tracemalloc
    tracemalloc.start()

    while True:
        attempt += 1
        try:
            logger.info("▶️  محاولة تشغيل رقم #%d", attempt)
            asyncio.run(main())
            logger.info("✅ main() انتهى بشكل طبيعي.")
            break

        except KeyboardInterrupt:
            logger.info("🛑 إيقاف يدوي.")
            break

        except Exception as exc:
            logger.error(
                "💥 انهيار كامل (#%d) | %s\n%s\n↩️  إعادة المحاولة بعد %ds",
                attempt, type(exc).__name__,
                traceback.format_exc()[-800:], delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)
