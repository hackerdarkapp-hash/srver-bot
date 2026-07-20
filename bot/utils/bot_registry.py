"""
    utils/bot_registry.py — سجل مركزي لجميع نسخ البوت
    يُستخدم للإرسال الجماعي عبر جميع البوتات المُشغَّلة
    """

    from aiogram import Bot

    # قائمة جميع نسخ البوت المُشغَّلة
    _ALL_BOTS: list[Bot] = []


    def register_bot(bot: Bot) -> None:
      """تسجيل نسخة بوت جديدة في السجل."""
      if bot not in _ALL_BOTS:
          _ALL_BOTS.append(bot)


    def get_all_bots() -> list[Bot]:
      """إرجاع جميع نسخ البوت المسجلة."""
      return list(_ALL_BOTS)


    def clear_registry() -> None:
      """مسح السجل (يُستخدم عند إعادة التشغيل)."""
      _ALL_BOTS.clear()
    