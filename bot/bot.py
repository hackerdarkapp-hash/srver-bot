"""
bot.py — تشغيل عدة بوتات تيليجرام بنفس الإعدادات والأدمن والقاعدة
═══════════════════════════════════════════════════════════════════
• Multi-Bot:  كل بوت له token خاص، dispatcher وقاعدة بيانات مشتركة
• HTTP Keep-Alive Server   • Self-Ping كل 10 دقائق
• Anti-Crash System        • Auto-Reconnect لكل بوت
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

BOT_START_TIME    = datetime.now()
_active_bots: dict[str, bool] = {}   # token_prefix → polling active
_reconnect_counts: dict[str, int] = {}


# ══════════════════════════════════════════════════════════════
#  HTTP Server — Keep-Alive (مشترك لجميع البوتات)
# ══════════════════════════════════════════════════════════════

async def _health(req: aio_web.Request) -> aio_web.Response:
    uptime = datetime.now() - BOT_START_TIME
    h, rem = divmod(int(uptime.total_seconds()), 3600)
    m      = rem // 60
    return aio_web.json_response({
        "status":     "ok",
        "uptime":     f"{h}h {m}m",
        "bots_count": len(_active_bots),
        "bots":       {k: v for k, v in _active_bots.items()},
        "time":       datetime.now().isoformat(),
    })


async def start_http_server(port: int) -> None:
    app = aio_web.Application()
    for p in ("/", "/healthz", "/health", "/ping", "/status"):
        app.router.add_get(p, _health)
    runner = aio_web.AppRunner(app)
    await runner.setup()

    candidates = [port, port + 1, 8000, 5000, 3000, 9000]
    for p in candidates:
        try:
            await aio_web.TCPSite(runner, "0.0.0.0", p).start()
            logger.info("🌐 HTTP Server جاهز على المنفذ %d", p)
            return
        except OSError:
            logger.warning("⚠️ المنفذ %d مشغول، أجرب التالي...", p)

    logger.warning("⚠️ تعذّر تشغيل HTTP Server")


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
#  Polling مع Auto-Reconnect لكل بوت
# ══════════════════════════════════════════════════════════════

async def polling_loop(bot: Bot, dp: Dispatcher, bot_label: str) -> None:
    """
    Long-polling يدوي لكل بوت على حدة.
    يستخدم bot.get_updates() + dp.feed_update() بدلاً من dp.start_polling()
    لأن dp.start_polling() لا يدعم استدعاءات متعددة متزامنة على نفس الـ Dispatcher.
    """
    _active_bots[bot_label] = False
    _reconnect_counts[bot_label] = 0

    INIT_DELAY = 3
    MAX_DELAY  = 120
    delay      = INIT_DELAY
    offset: int = 0
    first_run   = True
    allowed: list[str] | None = None

    while True:
        _active_bots[bot_label] = False
        try:
            logger.info("[%s] 🔄 بدء Polling (محاولة #%d)...",
                        bot_label, _reconnect_counts[bot_label] + 1)
            await bot.delete_webhook(drop_pending_updates=first_run)
            first_run = False
            # تحديد صريح لجميع أنواع التحديثات — يشمل رسائل المجموعات والقنوات
            allowed = [
                "message",
                "edited_message",
                "callback_query",
                "my_chat_member",
                "chat_member",
            ]
            _active_bots[bot_label] = True
            delay = INIT_DELAY

            # ── حلقة long-polling مستقلة لهذا البوت ──
            while True:
                updates = await bot.get_updates(
                    offset=offset,
                    timeout=30,
                    allowed_updates=allowed,
                )
                for update in updates:
                    # feed_update يضع Bot الصحيح في السياق لكل update
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
#  بناء Dispatcher مشترك
# ══════════════════════════════════════════════════════════════

def build_shared_dispatcher() -> Dispatcher:
    """
    ينشئ Dispatcher واحد مشترك بين جميع البوتات.
    نفس الأوامر، نفس الأدمن، نفس قاعدة البيانات.
    """
    dp = Dispatcher(storage=MemoryStorage())

    # الطبقة الأولى: SafeHandlerMiddleware يلتقط أي خطأ في أي handler
    safe = SafeHandlerMiddleware()
    dp.message.outer_middleware(safe)
    dp.callback_query.outer_middleware(safe)

    # الطبقة الثانية: AntiSpamMiddleware للحماية من السبام
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
#  main() — تشغيل جميع البوتات معاً
# ══════════════════════════════════════════════════════════════

async def main() -> None:
    tokens = get_all_bot_tokens()

    if not tokens:
        logger.critical(
            "❌ لم يُعرَّف أي توكن!\n"
            "   أضف BOT_TOKEN_1 (و BOT_TOKEN_2 ...) أو TELEGRAM_BOT_TOKEN"
        )
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("🚀 Multi-Bot Launcher | %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("🤖 عدد البوتات: %d", len(tokens))
    logger.info("=" * 60)

    # تهيئة قاعدة البيانات (مشتركة بين جميع البوتات)
    db.init_db()
    db.seed_default_tools(DEFAULT_FREE_TOOLS)
    db.seed_from_file()
    logger.info("✅ قاعدة البيانات المشتركة جاهزة")

    # Dispatcher مشترك
    dp = build_shared_dispatcher()

    # تسجيل global error handler مرة واحدة على الـ Dispatcher
    dp.errors.register(make_error_handler("global"))

    # إنشاء بوت لكل توكن
    bots: list[tuple[Bot, str]] = []
    for idx, token in enumerate(tokens, start=1):
        bot_label = f"bot_{idx}"
        session   = AiohttpSession(timeout=30)
        bot       = Bot(
            token=token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        bots.append((bot, bot_label))
        logger.info("✅ [%s] تم إنشاؤه | token=...%s", bot_label, token[-6:])

    # ضبط الأوامر لكل بوت
    for bot, bot_label in bots:
        await set_commands(bot, bot_label)

    port = int(os.environ.get("PORT", 8080))
    logger.info("📡 PORT=%d | URL=%s", port,
                os.environ.get("RENDER_EXTERNAL_URL", "local"))

    # تشغيل كل شيء معاً: HTTP Server + Ping + Heartbeat + polling لكل بوت
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
    """
    يلتقط استثناءات asyncio Tasks التي لم يُعالجها أحد.
    يمنعها من إيقاف البوت ويُسجّلها فقط.
    """
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
