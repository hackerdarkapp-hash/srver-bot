"""
handlers/user/support.py
═════════════════════════
المستخدم يرسل رسالة دعم → تُحوَّل للأدمن مع زر "رد"
"""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

from config import ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()


class SupportMsg(StatesGroup):
    WAITING = State()   # ينتظر رسالة المستخدم


def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="support:cancel")]
    ])


# ── زر "تواصل معنا" ──────────────────────────────────────────

@router.callback_query(F.data == "support:start")
async def cb_support_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(SupportMsg.WAITING)
    await cb.message.answer(
        "💬 <b>تواصل معنا</b>\n\n"
        "أرسل رسالتك أو استفسارك وسيصلك رد من فريق الدعم.\n"
        "<i>تدعم: نص · صورة · فيديو · ملف · صوتية</i>",
        reply_markup=_cancel_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "support:cancel")
async def cb_support_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer("تم الإلغاء ✅")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── استقبال رسالة المستخدم وإحالتها للأدمن ─────────────────

@router.message(SupportMsg.WAITING)
async def support_receive(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()

    user    = message.from_user
    name    = user.full_name or "مجهول"
    uname   = f"@{user.username}" if user.username else "—"
    uid     = user.id

    header = (
        f"📩 <b>رسالة دعم جديدة</b>\n"
        f"{'━' * 22}\n"
        f"👤 <b>الاسم:</b> {name}\n"
        f"🔗 <b>المعرّف:</b> @{user.username or ''} (<code>{uid}</code>)\n"
        f"{'━' * 22}"
    )

    reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ رد على المستخدم", callback_data=f"sreply:{uid}")]
    ])

    try:
        # أرسل رأس المعلومات
        await bot.send_message(ADMIN_ID, header, parse_mode="HTML")
        # أرسل الرسالة الأصلية (نسخة بدون "مُعاد توجيهه من")
        await bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=reply_kb,
        )
    except Exception as e:
        logger.error("support forward error: %s", e)

    await message.answer(
        "✅ <b>وصلت رسالتك!</b>\n"
        "سيتواصل معك فريق الدعم في أقرب وقت.",
        parse_mode="HTML",
    )
