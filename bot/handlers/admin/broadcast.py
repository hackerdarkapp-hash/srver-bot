"""
handlers/admin/broadcast.py
═══════════════════════════
① الإرسال الجماعي  — الأدمن يرسل رسالة لكل المشتركين
② الرد على رسائل الدعم — الأدمن يرد على رسالة مستخدم
"""

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

import database as db
from config import ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

DELAY = 0.05   # تأخير بين كل رسالة (ثانية) لتجنب الحظر


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ لوحة التحكم", callback_data="ap:panel")]
    ])


def _confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ إرسال الآن", callback_data="bc:confirm"),
            InlineKeyboardButton(text="❌ إلغاء",      callback_data="ap:panel"),
        ]
    ])


# ══════════════════════════════════════════════════════════════
#  FSM — الإرسال الجماعي
# ══════════════════════════════════════════════════════════════

class Broadcast(StatesGroup):
    WAITING = State()   # ينتظر الرسالة من الأدمن


@router.callback_query(F.data == "ap:broadcast")
async def cb_broadcast_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    await state.set_state(Broadcast.WAITING)
    await cb.message.edit_text(
        "📢 <b>الإرسال الجماعي</b>\n\n"
        "أرسل الرسالة التي تريد إيصالها لجميع المشتركين.\n"
        "تدعم: نص · صورة · فيديو · صوت · ملف · استيكر\n\n"
        "<i>⚠️ ستصل لكل المشتركين غير المحظورين</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="ap:panel")]
        ]),
        parse_mode="HTML",
    )


@router.message(Broadcast.WAITING)
async def bc_receive_msg(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.update_data(
        msg_id=message.message_id,
        chat_id=message.chat.id,
    )
    total = len(db.get_all_active_user_ids())
    await message.answer(
        f"👁 <b>معاينة الرسالة ↑</b>\n\n"
        f"سيتم الإرسال إلى <b>{total}</b> مشترك.\n"
        "هل تريد المتابعة؟",
        reply_markup=_confirm_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "bc:confirm")
async def bc_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return

    data = await state.get_data()
    await state.clear()

    src_chat = data.get("chat_id")
    src_msg  = data.get("msg_id")

    if not src_msg:
        await cb.answer("⚠️ لم يتم العثور على الرسالة.", show_alert=True)
        return

    await cb.answer("⏳ جارٍ الإرسال...")
    status_msg = await cb.message.edit_text(
        "📤 <b>جارٍ الإرسال الجماعي...</b>",
        parse_mode="HTML",
    )

    user_ids = db.get_all_active_user_ids()
    sent = blocked = failed = 0

    for uid in user_ids:
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=src_chat,
                message_id=src_msg,
            )
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramBadRequest:
            failed += 1
        except Exception as e:
            logger.warning("broadcast error uid=%s: %s", uid, e)
            failed += 1
        await asyncio.sleep(DELAY)

    from utils.keyboards import admin_panel_keyboard
    await status_msg.edit_text(
        f"✅ <b>اكتمل الإرسال الجماعي</b>\n\n"
        f"📨 أُرسل إلى:    <b>{sent}</b>\n"
        f"🚫 محظورون:   <b>{blocked}</b>\n"
        f"❌ فشل:         <b>{failed}</b>\n"
        f"📊 الإجمالي:    <b>{len(user_ids)}</b>",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  FSM — رد الأدمن على رسائل الدعم
# ══════════════════════════════════════════════════════════════

class SupportReply(StatesGroup):
    WAITING = State()   # ينتظر رد الأدمن


@router.callback_query(F.data.startswith("sreply:"))
async def cb_support_reply_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()

    user_id = int(cb.data.split(":")[1])
    user    = db.get_user(user_id)
    name    = (user.get("first_name") or "المستخدم") if user else "المستخدم"

    await state.set_state(SupportReply.WAITING)
    await state.update_data(target_user_id=user_id)

    await cb.message.reply(
        f"✏️ اكتب ردّك على <b>{name}</b> (<code>{user_id}</code>):\n"
        "<i>أرسل أي نوع رسالة (نص · صورة · ملف · ...)</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="sreply:cancel")]
        ]),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "sreply:cancel")
async def cb_support_reply_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await state.clear()
    await cb.answer("تم الإلغاء")
    await cb.message.edit_reply_markup(reply_markup=None)


@router.message(SupportReply.WAITING)
async def support_reply_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    data    = await state.get_data()
    uid     = data.get("target_user_id")
    await state.clear()

    try:
        await bot.copy_message(
            chat_id=uid,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.reply(
            f"✅ <b>تم إرسال الرد بنجاح</b> إلى <code>{uid}</code>",
            parse_mode="HTML",
        )
    except TelegramForbiddenError:
        await message.reply(
            f"🚫 المستخدم <code>{uid}</code> أوقف البوت ولا يمكن مراسلته.",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.reply(f"❌ فشل الإرسال: {e}")
