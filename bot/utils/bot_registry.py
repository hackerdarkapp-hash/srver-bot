"""
utils/bot_registry.py
سجل مركزي لجميع نسخ Bot المُنشأة عند التشغيل.
يُستخدم للإرسال الجماعي عبر جميع البوتات المُشغَّلة
"""

from aiogram import Bot

_ALL_BOTS: list[Bot] = []


def register_bot(bot: Bot) -> None:
    if bot not in _ALL_BOTS:
        _ALL_BOTS.append(bot)


def get_all_bots() -> list[Bot]:
    return list(_ALL_BOTS)


def clear_registry() -> None:
    _ALL_BOTS.clear()
