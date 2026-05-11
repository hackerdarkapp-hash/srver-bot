"""
handlers/user/navigation.py — تنقل المستخدم بين الأزرار
"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo,
)

import database as db
from utils.keyboards import build_start_keyboard, build_children_keyboard

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════════════
#  الأزرار غير القابلة للضغط (العناوين والفواصل)
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.in_({"__noop__", "__sep__"}))
async def cb_noop(cb: CallbackQuery) -> None:
    await cb.answer()


# ══════════════════════════════════════════════════════════════
#  دالة مساعدة: عرض/تحديث الصفحة الرئيسية
# ══════════════════════════════════════════════════════════════

async def _show_main(cb: CallbackQuery, state: FSMContext) -> None:
    """عرض الصفحة الرئيسية الموحدة"""
    from config import DEFAULT_WELCOME
    await state.clear()
    welcome_tmpl = db.get_setting("welcome_message", DEFAULT_WELCOME)
    name         = cb.from_user.first_name or "زائر"
    text         = welcome_tmpl.replace("{name}", name)
    kb           = build_start_keyboard()
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.error("خطأ في عرض الصفحة الرئيسية: %s", e)


# ══════════════════════════════════════════════════════════════
#  زر الرجوع للقائمة الرئيسية (من الأدوات)
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.in_({"tool:back_main", "section:free", "section:paid"}))
async def cb_back_main(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await _show_main(cb, state)


# ══════════════════════════════════════════════════════════════
#  زر الرجوع
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("back:"))
async def cb_back(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    target = cb.data.split(":", 1)[1]

    if target in ("main", "0"):
        await _show_main(cb, state)
        return

    await state.clear()
    try:
        parent_id = int(target)
    except ValueError:
        await _show_main(cb, state)
        return

    btn = db.get_button(parent_id)
    if not btn:
        await _show_main(cb, state)
        return

    section  = btn.get("section", "free")
    keyboard = build_children_keyboard(parent_id, btn.get("parent_id"), section)
    try:
        await cb.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        try:
            await cb.message.answer(
                f"📂 <b>{btn['label']}</b>\nاختر من القائمة:",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("خطأ في زر الرجوع: %s", e)


# ══════════════════════════════════════════════════════════════
#  الضغط على زر nav:{id} — الأزرار الديناميكية
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("nav:"))
async def cb_navigate(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    try:
        btn_id = int(cb.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await cb.answer("⚠️ بيانات غير صحيحة.", show_alert=True)
        return

    btn = db.get_button(btn_id)
    if not btn or not btn["is_active"]:
        await cb.answer("⚠️ هذا الزر غير متاح حالياً.", show_alert=True)
        return

    await _execute_button(cb, btn_id, btn)


async def _execute_button(cb: CallbackQuery, btn_id: int, btn: dict) -> None:
    try:
        resp     = db.get_response(btn_id)
        children = db.get_children(btn_id)
        section  = btn.get("section", "free")

        if resp and resp["response_type"] != "none":
            await _send_response(cb.message, resp)

        if children:
            keyboard = build_children_keyboard(btn_id, btn.get("parent_id"), section)
            label    = btn["label"]
            if resp and resp["response_type"] != "none":
                await cb.message.answer(
                    f"📂 <b>{label}</b>\nاختر من القائمة:",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                try:
                    await cb.message.edit_text(
                        f"📂 <b>{label}</b>\nاختر من القائمة:",
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                except Exception:
                    await cb.message.answer(
                        f"📂 <b>{label}</b>\nاختر من القائمة:",
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
        elif not resp or resp["response_type"] == "none":
            await cb.answer("⚠️ لم يُضف مالك البوت رداً لهذا الزر بعد.", show_alert=True)

    except Exception as e:
        logger.error("خطأ في تنفيذ الزر %s: %s", btn_id, e)
        try:
            await cb.answer("⚠️ حدث خطأ، حاول مرة أخرى.", show_alert=True)
        except Exception:
            pass


async def _send_response(message: Message, resp: dict) -> None:
    rtype   = resp["response_type"]
    text    = resp.get("text_content") or ""
    file_id = resp.get("file_id")
    caption = resp.get("caption") or ""
    url     = resp.get("url") or ""
    pm      = resp.get("parse_mode") or "HTML"
    redir   = resp.get("redirect_to")

    try:
        if rtype == "text":
            await message.answer(text, parse_mode=pm)
        elif rtype == "photo":
            src = file_id or url
            if src:
                await message.answer_photo(src, caption=caption or text, parse_mode=pm)
        elif rtype == "video" and file_id:
            await message.answer_video(file_id, caption=caption or text, parse_mode=pm)
        elif rtype == "file" and file_id:
            await message.answer_document(file_id, caption=caption or text, parse_mode=pm)
        elif rtype == "audio" and file_id:
            await message.answer_audio(file_id, caption=caption or text, parse_mode=pm)
        elif rtype == "webapp" and url:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🌐 فتح التطبيق", web_app=WebAppInfo(url=url))
            ]])
            await message.answer(text or "اضغط لفتح التطبيق:", reply_markup=kb, parse_mode=pm)
        elif rtype == "redirect" and redir:
            target = db.get_button(redir)
            if target:
                target_resp = db.get_response(redir)
                if target_resp and target_resp["response_type"] != "none":
                    await _send_response(message, target_resp)
    except Exception as e:
        logger.error("خطأ في إرسال الرد: %s", e)
