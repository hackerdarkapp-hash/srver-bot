"""
bot.py — تشغيل عدة بوتات تيليجرام
═══════════════════════════════════════════════════════════════════
• Webhook Mode  : عند وجود RENDER_EXTERNAL_URL (Render / Cloud)
• Polling Mode  : للتشغيل المحلي
• Multi-Bot     : كل بوت له token خاص، dispatcher وقاعدة مشتركة
• Anti-Crash    • Auto-Reconnect  • Heartbeat  • Global Error Handler
"""

import asyncio
import gc
import hashlib
import json
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
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, Update

import database as db
from config import ADMIN_ID, SESSION_SECRET, DEFAULT_FREE_TOOLS, get_all_bot_tokens
from handlers import (
    nav_router, panel_router, start_router,
    usermgmt_router, wizard_router, tools_router,
)
from security import AntiSpamMiddleware, SafeHandlerMiddleware


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

BOT_START_TIME = datetime.now()
_active_bots: dict[str, bool] = {}
_reconnect_counts: dict[str, int] = {}


# ══════════════════════════════════════════════════════════════
#  HTTP Server — Health + Webhook Handler
# ══════════════════════════════════════════════════════════════

# map: webhook_path → (bot, dispatcher)
_webhook_handlers: dict[str, tuple[Bot, Dispatcher]] = {}


async def _health(req: aio_web.Request) -> aio_web.Response:
    uptime = datetime.now() - BOT_START_TIME
    h, rem = divmod(int(uptime.total_seconds()), 3600)
    m = rem // 60
    return aio_web.json_response({
        "status":     "ok",
        "uptime":     f"{h}h {m}m",
        "mode":       "webhook" if _webhook_handlers else "polling",
        "bots_count": len(_active_bots),
        "bots":       {k: v for k, v in _active_bots.items()},
        "time":       datetime.now().isoformat(),
    })


async def _webhook_handle(req: aio_web.Request) -> aio_web.Response:
    path = req.match_info.get("path", "")
    entry = _webhook_handlers.get(path)
    if not entry:
        return aio_web.Response(status=404, text="unknown webhook path")

    bot, dp = entry
    try:
        data = await req.json()
        update = Update(**data)
        asyncio.create_task(dp.feed_update(bot=bot, update=update))
    except Exception as e:
        logger.error("Webhook parse error: %s", e)

    return aio_web.Response(text="ok")


async def start_http_server(port: int) -> aio_web.AppRunner:
    app = aio_web.Application()
    for p in ("/", "/healthz", "/health", "/ping", "/status"):
        app.router.add_get(p, _health)
    app.router.add_post("/webhook/{path}", _webhook_handle)

    runner = aio_web.AppRunner(app)
    await runner.setup()

    candidates = [port, port + 1, 8000, 5000, 3000, 9000]
    for p in candidates:
        try:
            await aio_web.TCPSite(runner, "0.0.0.0", p).start()
            logger.info("🌐 HTTP Server جاهز على المنفذ %d", p)
            return runner
        except OSError:
            logger.warning("⚠️ المنفذ %d مشغول، أجرب التالي...", p)

    logger.warning("⚠️ تعذّر تشغيل HTTP Server")
    return runner


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
        active = sum(1 for v in _active_bots.values() if v)
        logger.info(
            "💓 Heartbeat | uptime=%dh%dm | بوتات نشطة=%d/%d",
            h, rem // 60, active, len(_active_bots),
        )


# ══════════════════════════════════════════════════════════════
#  أوامر البوت
# ══════════════════════════════════════════════════════════════

async def set_commands(bot: Bot, bot_label: str) -> None:
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
        logger.info("[%s] ✅ أوامر البوت ضُبطت", bot_label)
    except Exception as e:
        logger.warning("[%s] تعذّر ضبط الأوامر: %s", bot_label, e)


# ══════════════════════════════════════════════════════════════
#  Global Error Handler
# ══════════════════════════════════════════════════════════════

def make_error_handler(bot_label: str):
    async def global_error_handler(event, exception) -> bool:
        tb = traceback.format_exc()[-600:]
        logger.error("[%s] ⚠️ %s: %s", bot_label, type(exception).__name__, str(exception)[:150])
        if ADMIN_ID:
            try:
                bot = getattr(event, "bot", None)
                if bot:
                    await bot.send_message(
                        ADMIN_ID,
                        f"⚠️ <b>[{bot_label}] خطأ</b>\n"
                        f"<code>{type(exception).__name__}</code>\n\n"
                        f"<code>{tb}</code>",
                        parse_mode="HTML",
                    )
            except Exception:
                pass
        return True
    return global_error_handler


# ══════════════════════════════════════════════════════════════
#  Polling مع Auto-Reconnect (للتشغيل المحلي)
# ══════════════════════════════════════════════════════════════

async def polling_loop(bot: Bot, dp: Dispatcher, bot_label: str) -> None:
    _active_bots[bot_label] = False
    _reconnect_counts[bot_label] = 0

    INIT_DELAY = 3
    MAX_DELAY  = 120
    delay      = INIT_DELAY
    offset: int = 0
    first_run   = True

    allowed = [
        "message",
        "edited_message",
        "callback_query",
        "my_chat_member",
        "chat_member",
    ]

    while True:
        _active_bots[bot_label] = False
        try:
            logger.info("[%s] 🔄 بدء Polling (محاولة #%d)...",
                        bot_label, _reconnect_counts[bot_label] + 1)
            await bot.delete_webhook(drop_pending_updates=first_run)
            first_run = False
            _active_bots[bot_label] = True
            delay = INIT_DELAY

            while True:
                updates = await bot.get_updates(
                    offset=offset,
                    timeout=30,
                    allowed_updates=allowed,
                )
                for update in updates:
                    asyncio.create_task(dp.feed_update(bot=bot, update=update))
                    offset = update.update_id + 1

        except TelegramRetryAfter as e:
            _active_bots[bot_label] = False
            wait = e.retry_after + 5
            logger.warning("[%s] ⏳ RetryAfter %ds", bot_label, wait)
            await asyncio.sleep(wait)

        except (TelegramNetworkError, TelegramAPIError) as e:
            _active_bots[bot_label] = False
            _reconnect_counts[bot_label] += 1
            logger.error("[%s] 🌐 %s: %s — إعادة بعد %ds",
                         bot_label, type(e).__name__, str(e)[:80], delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)

        except asyncio.CancelledError:
            _active_bots[bot_label] = False
            logger.info("[%s] 🛑 Polling أُلغي.", bot_label)
            return

        except Exception as e:
            _active_bots[bot_label] = False
            _reconnect_counts[bot_label] += 1
            logger.error(
                "[%s] 💥 خطأ Polling [%s]: %s\n%s\n↩️ إعادة بعد %ds",
                bot_label, type(e).__name__, str(e)[:100],
                traceback.format_exc()[-300:], delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)

        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                _active_bots[bot_label] = False
                logger.info("[%s] 🛑 إيقاف بسبب %s", bot_label, type(e).__name__)
                return
            _active_bots[bot_label] = False
            _reconnect_counts[bot_label] += 1
            logger.critical(
                "[%s] ☠️ BaseException [%s]: %s\n↩️ إعادة بعد %ds",
                bot_label, type(e).__name__, str(e)[:100], delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)


# ══════════════════════════════════════════════════════════════
#  Webhook Setup (لـ Render والخوادم السحابية)
# ══════════════════════════════════════════════════════════════

def _make_webhook_path(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:32]


async def setup_webhook(bot: Bot, dp: Dispatcher, bot_label: str,
                        base_url: str) -> None:
    path = _make_webhook_path(bot.token)
    webhook_url = f"{base_url}/webhook/{path}"
    _webhook_handlers[path] = (bot, dp)
    _active_bots[bot_label] = True

    try:
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=[
                "message",
                "edited_message",
                "callback_query",
                "my_chat_member",
                "chat_member",
            ],
            drop_pending_updates=True,
        )
        logger.info("[%s] 🔗 Webhook ضُبط على: %s", bot_label, webhook_url)
    except Exception as e:
        logger.error("[%s] ❌ فشل ضبط Webhook: %s", bot_label, e)
        _active_bots[bot_label] = False


# ══════════════════════════════════════════════════════════════
#  بناء Dispatcher مشترك
# ══════════════════════════════════════════════════════════════

def build_shared_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    safe = SafeHandlerMiddleware()
    dp.message.outer_middleware(safe)
    dp.callback_query.outer_middleware(safe)

    spam = AntiSpamMiddleware()
    dp.message.middleware(spam)
    dp.callback_query.middleware(spam)

    dp.include_router(tools_router)
    dp.include_router(panel_router)
    dp.include_router(wizard_router)
    dp.include_router(usermgmt_router)
    dp.include_router(nav_router)
    dp.include_router(start_router)

    return dp


# ══════════════════════════════════════════════════════════════
#  main()
# ══════════════════════════════════════════════════════════════

async def main() -> None:
    tokens = get_all_bot_tokens()

    if not tokens:
        logger.critical(
            "❌ لم يُعرَّف أي توكن!\n"
            "   أضف BOT_TOKEN_1 (و BOT_TOKEN_2 ...) أو TELEGRAM_BOT_TOKEN"
        )
        sys.exit(1)

    render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    mode = "webhook" if render_url else "polling"

    logger.info("=" * 60)
    logger.info("🚀 Multi-Bot Launcher | %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("🤖 عدد البوتات: %d | الوضع: %s", len(tokens), mode)
    logger.info("=" * 60)

    db.init_db()
    db.seed_default_tools(DEFAULT_FREE_TOOLS)
    db.seed_from_file()
    logger.info("✅ قاعدة البيانات المشتركة جاهزة")

    dp = build_shared_dispatcher()
    dp.errors.register(make_error_handler("global"))

    bots: list[tuple[Bot, str]] = []
    for idx, token in enumerate(tokens, start=1):
        bot_label = f"bot_{idx}"
        session = AiohttpSession(timeout=30)
        bot = Bot(
            token=token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        bots.append((bot, bot_label))
        logger.info("✅ [%s] تم إنشاؤه | token=...%s", bot_label, token[-6:])

    for bot, bot_label in bots:
        await set_commands(bot, bot_label)

    port = int(os.environ.get("PORT", 8080))

    if mode == "webhook":
        logger.info("🔗 وضع Webhook | URL=%s", render_url)
        runner = await start_http_server(port)

        for bot, bot_label in bots:
            await setup_webhook(bot, dp, bot_label, render_url)

        try:
            await asyncio.gather(
                self_ping_loop(port),
                heartbeat_loop(),
            )
        finally:
            for bot, bot_label in bots:
                try:
                    await bot.delete_webhook()
                    await bot.session.close()
                    logger.info("[%s] 🔌 Session مغلق", bot_label)
                except Exception:
                    pass
            logger.info("🏁 جميع البوتات أُوقفت.")

    else:
        logger.info("📡 وضع Polling محلي | PORT=%d", port)
        polling_tasks = [polling_loop(bot, dp, lbl) for bot, lbl in bots]

        try:
            await asyncio.gather(
                start_http_server(port),
                self_ping_loop(port),
                heartbeat_loop(),
                *polling_tasks,
            )
        finally:
            for bot, bot_label in bots:
                try:
                    await bot.session.close()
                    logger.info("[%s] 🔌 Session مغلق", bot_label)
                except Exception:
                    pass
            logger.info("🏁 جميع البوتات أُوقفت.")


# ══════════════════════════════════════════════════════════════
#  نقطة الدخول
# ══════════════════════════════════════════════════════════════

def _asyncio_exception_handler(loop: asyncio.AbstractEventLoop, ctx: dict) -> None:
    msg = ctx.get("message", "")
    exc = ctx.get("exception")
    if exc:
        logger.error(
            "⚡ asyncio unhandled: %s — %s\n%s",
            type(exc).__name__, str(exc)[:120],
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-400:],
        )
    else:
        logger.error("⚡ asyncio unhandled: %s", msg)


if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(_asyncio_exception_handler)
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("🛑 إيقاف يدوي.")
    except Exception as e:
        logger.critical(
            "💥 خطأ فادح: %s\n%s",
            type(e).__name__, traceback.format_exc(),
        )
        sys.exit(1)
    finally:
        try:
            loop.close()
        except Exception:
            pass
