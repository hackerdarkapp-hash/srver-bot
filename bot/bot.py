"""
bot.py — نظام تشغيل البوت 24/7 على Render
═══════════════════════════════════════════════════
• HTTP Keep-Alive Server   • Self-Ping كل 10 دقائق
• Anti-Crash System        • Auto-Reconnect
• Heartbeat Monitor        • Global Error Handler
"""

import asyncio
import gc
import logging
import os
import sys
import traceback
from datetime import datetime

from aiohttp import web as aio_web, ClientSession, ClientTimeout
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramRetryAfter
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
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

BOT_START_TIME   = datetime.now()
_polling_active  = False
_reconnect_count = 0


# ══════════════════════════════════════════════════════════════
#  HTTP Server — Keep-Alive
# ══════════════════════════════════════════════════════════════

async def _health(req: aio_web.Request) -> aio_web.Response:
    uptime = datetime.now() - BOT_START_TIME
    h, rem = divmod(int(uptime.total_seconds()), 3600)
    m      = rem // 60
    return aio_web.json_response({
        "status":     "ok",
        "uptime":     f"{h}h {m}m",
        "polling":    _polling_active,
        "reconnects": _reconnect_count,
        "time":       datetime.now().isoformat(),
    })


async def start_http_server(port: int) -> None:
    app = aio_web.Application()
    for p in ("/", "/healthz", "/health", "/ping"):
        app.router.add_get(p, _health)
    runner = aio_web.AppRunner(app)
    await runner.setup()

    # جرّب المنفذ المطلوب ثم بدائل إذا كان مشغولاً
    candidates = [port, port + 1, 8000, 5000, 3000, 9000]
    for p in candidates:
        try:
            await aio_web.TCPSite(runner, "0.0.0.0", p).start()
            logger.info("🌐 HTTP Server جاهز على المنفذ %d", p)
            return
        except OSError:
            logger.warning("⚠️ المنفذ %d مشغول، أجرب التالي...", p)

    logger.warning("⚠️ تعذّر تشغيل HTTP Server — البوت سيعمل بدونه (Polling فقط)")


# ══════════════════════════════════════════════════════════════
#  Self-Ping — منع النوم على Render
# ══════════════════════════════════════════════════════════════

async def self_ping_loop(port: int) -> None:
    await asyncio.sleep(30)
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    url = f"{render_url}/healthz" if render_url else f"http://localhost:{port}/healthz"
    logger.info("💓 Self-Ping → %s (كل 10 دق)", url)
    timeout = ClientTimeout(total=15)
    while True:
        await asyncio.sleep(600)
        try:
            async with ClientSession(timeout=timeout) as s:
                async with s.get(url) as r:
                    logger.info("💓 Ping %s", "✅" if r.status == 200 else f"⚠️{r.status}")
        except Exception as e:
            logger.warning("💓 Ping فشل: %s", type(e).__name__)


# ══════════════════════════════════════════════════════════════
#  Heartbeat
# ══════════════════════════════════════════════════════════════

async def heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(1800)
        uptime = datetime.now() - BOT_START_TIME
        h, rem = divmod(int(uptime.total_seconds()), 3600)
        gc.collect()
        logger.info(
            "💓 Heartbeat | uptime=%dh%dm | reconnects=%d | polling=%s",
            h, rem // 60, _reconnect_count, _polling_active,
        )


# ══════════════════════════════════════════════════════════════
#  أوامر البوت
# ══════════════════════════════════════════════════════════════

async def set_commands(bot: Bot) -> None:
    try:
        await bot.set_my_commands(
            [BotCommand(command="start", description="▶️ بدء البوت")],
            scope=BotCommandScopeDefault(),
        )
        if ADMIN_ID:
            await bot.set_my_commands(
                [BotCommand(command="start", description="▶️ بدء البوت"),
                 BotCommand(command="admin", description="🎛 لوحة التحكم")],
                scope=BotCommandScopeChat(chat_id=ADMIN_ID),
            )
    except Exception as e:
        logger.warning("تعذّر ضبط الأوامر: %s", e)


# ══════════════════════════════════════════════════════════════
#  Global Error Handler
# ══════════════════════════════════════════════════════════════

async def global_error_handler(event, exception) -> bool:
    tb = traceback.format_exc()[-600:]
    logger.error("⚠️ %s: %s", type(exception).__name__, str(exception)[:150])
    if ADMIN_ID:
        try:
            bot = getattr(event, "bot", None)
            if bot:
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>خطأ</b>\n<code>{type(exception).__name__}</code>\n\n<code>{tb}</code>",
                    parse_mode="HTML",
                )
        except Exception:
            pass
    return True


# ══════════════════════════════════════════════════════════════
#  Polling مع Auto-Reconnect لا نهائي
# ══════════════════════════════════════════════════════════════

async def polling_loop(bot: Bot, dp: Dispatcher) -> None:
    global _polling_active, _reconnect_count

    INIT_DELAY = 3
    MAX_DELAY  = 120
    delay      = INIT_DELAY
    first_run  = True

    while True:
        _polling_active = False
        try:
            logger.info("🔄 بدء Polling (محاولة #%d)...", _reconnect_count + 1)
            await bot.delete_webhook(drop_pending_updates=first_run)
            first_run       = False
            _polling_active = True
            delay           = INIT_DELAY

            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_signals=False,
                polling_timeout=30,
            )

        except TelegramRetryAfter as e:
            _polling_active = False
            wait = e.retry_after + 5
            logger.warning("⏳ RetryAfter %ds", wait)
            await asyncio.sleep(wait)

        except (TelegramNetworkError, TelegramAPIError) as e:
            _polling_active  = False
            _reconnect_count += 1
            logger.error("🌐 %s: %s — إعادة بعد %ds", type(e).__name__, str(e)[:80], delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)

        except asyncio.CancelledError:
            _polling_active = False
            logger.info("🛑 Polling أُلغي.")
            return

        except Exception as e:
            _polling_active  = False
            _reconnect_count += 1
            logger.error(
                "💥 خطأ Polling [%s]: %s\n%s\n↩️ إعادة بعد %ds",
                type(e).__name__, str(e)[:100],
                traceback.format_exc()[-300:], delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)


# ══════════════════════════════════════════════════════════════
#  main() — يُستدعى مرة واحدة، كل الـ retry بداخله
# ══════════════════════════════════════════════════════════════

async def main() -> None:
    if not BOT_TOKEN:
        logger.critical("❌ TELEGRAM_BOT_TOKEN غير موجود!")
        sys.exit(1)

    logger.info("=" * 55)
    logger.info("🚀 بوت الاختراق | %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 55)

    db.init_db()
    db.seed_default_tools(DEFAULT_FREE_TOOLS)
    db.seed_from_file()
    logger.info("✅ قاعدة البيانات جاهزة")

    # ── البوت والـ Dispatcher — مرة واحدة فقط ─────────────────
    session = AiohttpSession(timeout=30)
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AntiSpamMiddleware())
    dp.callback_query.middleware(AntiSpamMiddleware())
    dp.errors.register(global_error_handler)

    # ── الـ Routers — مرة واحدة فقط ───────────────────────────
    dp.include_router(tools_router)
    dp.include_router(panel_router)
    dp.include_router(wizard_router)
    dp.include_router(usermgmt_router)
    dp.include_router(nav_router)
    dp.include_router(start_router)

    await set_commands(bot)

    port = int(os.environ.get("PORT", 8080))
    logger.info("📡 PORT=%d | URL=%s", port,
                os.environ.get("RENDER_EXTERNAL_URL", "local"))

    # ── تشغيل كل المهام معاً ──────────────────────────────────
    try:
        await asyncio.gather(
            start_http_server(port),
            self_ping_loop(port),
            heartbeat_loop(),
            polling_loop(bot, dp),
        )
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass
        logger.info("🏁 البوت أُوقف.")


# ══════════════════════════════════════════════════════════════
#  نقطة الدخول — asyncio.run() مرة واحدة فقط
#  إذا خرجت العملية، Render يُعيد تشغيلها تلقائياً
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 إيقاف يدوي.")
    except Exception as e:
        logger.critical(
            "💥 خطأ فادح: %s\n%s",
            type(e).__name__, traceback.format_exc(),
        )
        # نخرج بـ exit code 1 — Render سيُعيد التشغيل تلقائياً
        sys.exit(1)
