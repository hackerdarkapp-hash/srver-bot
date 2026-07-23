"""
handlers/user/start.py — معالج /start (يعمل في المحادثات الخاصة والمجموعات)
"""

import logging
from aiogram import Bot, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

import database as db
from config import DEFAULT_WELCOME
from utils.keyboards import build_start_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user = message.from_user
    chat_type = message.chat.type

    is_new = db.save_user(
        user_id    = user.id,
        username   = user.username,
        first_name = user.first_name,
        last_name  = user.last_name,
        bot_id     = bot.id,
    )
    if is_new:
        logger.info("مستخدم جديد: id=%s @%s chat_type=%s",
                    user.id, user.username, chat_type)

    welcome_tmpl = db.get_setting("welcome_message", DEFAULT_WELCOME)
    name         = user.first_name or "زائر"
    welcome_text = welcome_tmpl.replace("{name}", name)

    await message.answer(
        welcome_text,
        reply_markup=build_start_keyboard(chat_type=chat_type),
        parse_mode="HTML",
    )
