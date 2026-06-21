"""
handlers/user/start.py — معالج /start (يعمل في المحادثات الخاصة والمجموعات)
"""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatType

import database as db
from config import DEFAULT_WELCOME
from utils.keyboards import build_start_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start_private(message: Message) -> None:
    user = message.from_user
    is_new = db.save_user(
        user_id    = user.id,
        username   = user.username,
        first_name = user.first_name,
        last_name  = user.last_name,
    )
    if is_new:
        logger.info("مستخدم جديد: id=%s @%s", user.id, user.username)

    welcome_tmpl = db.get_setting("welcome_message", DEFAULT_WELCOME)
    name         = user.first_name or "زائر"
    welcome_text = welcome_tmpl.replace("{name}", name)

    await message.answer(
        welcome_text,
        reply_markup=build_start_keyboard(),
        parse_mode="HTML",
    )


@router.message(CommandStart(), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def cmd_start_group(message: Message) -> None:
    user = message.from_user
    db.save_user(
        user_id    = user.id,
        username   = user.username,
        first_name = user.first_name,
        last_name  = user.last_name,
    )

    bot_info = await message.bot.get_me()
    bot_username = bot_info.username

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 ابدأ في الخاص",
            url=f"https://t.me/{bot_username}?start=from_group"
        )],
    ])

    name = user.first_name or "زائر"
    await message.reply(
        f"👋 أهلاً <b>{name}</b>!\n\n"
        f"🤖 أنا بوت أدوات الأمن السيبراني.\n"
        f"للوصول إلى جميع الأدوات، افتحني في الخاص 👇",
        reply_markup=kb,
        parse_mode="HTML",
    )
