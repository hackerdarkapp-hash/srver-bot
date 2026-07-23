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


def get_primary_bot() -> Bot | None:
    """البوت رقم ١، وهو مصدر لوحة الإدارة والوسائط المضافة منها."""
    return _ALL_BOTS[0] if _ALL_BOTS else None


def is_primary_bot(bot: Bot | None) -> bool:
    """تحقق من أن الحدث وصل عبر البوت الرئيسي."""
    primary = get_primary_bot()
    if primary is None or bot is None:
        return True
    return bot is primary


def clear_registry() -> None:
    _ALL_BOTS.clear()
