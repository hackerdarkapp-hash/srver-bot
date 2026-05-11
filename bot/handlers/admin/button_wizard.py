"""
handlers/admin/button_wizard.py — معالج إضافة/تعديل الأزرار المخصصة
"""

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

import database as db
from config import ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

RESPONSE_TYPES = [
    ("📝 رسالة نصية", "text"),
    ("🖼 صورة",        "photo"),
    ("🎬 فيديو",       "video"),
    ("📁 ملف",         "file"),
    ("🎵 صوت",         "audio"),
    ("🌐 WebApp",      "webapp"),
    ("❌ بدون رد",    "none"),
]


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")]
    ])


class AddBtn(StatesGroup):
    TYPE       = State()
    PARENT     = State()
    LABEL      = State()
    SECTION    = State()
    RESP_TYPE  = State()
    RESP_VALUE = State()


@router.callback_query(F.data == "ap:add")
async def cb_add_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    await state.set_state(AddBtn.TYPE)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔸 زر خارجي",  callback_data="bw:type:ext"),
            InlineKeyboardButton(text="🔹 زر داخلي",  callback_data="bw:type:int"),
        ],
        [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")],
    ])
    try:
        await cb.message.edit_text(
            "➕ <b>إضافة زر جديد</b>\n\nاختر نوع الزر:",
            reply_markup=kb, parse_mode="HTML",
        )
    except Exception:
        await cb.message.answer(
            "➕ <b>إضافة زر جديد</b>\n\nاختر نوع الزر:",
            reply_markup=kb, parse_mode="HTML",
        )


@router.callback_query(AddBtn.TYPE, F.data.startswith("bw:type:"))
async def cb_choose_type(cb: CallbackQuery, state: FSMContext) -> None:
    t = cb.data.split(":")[2]
    await state.update_data(btn_type=t)
    await cb.answer()

    if t == "int":
        top = db.get_top_level_buttons()
        if not top:
            await cb.answer("⚠️ لا توجد أزرار خارجية. أضف زراً خارجياً أولاً.", show_alert=True)
            await state.clear()
            return
        rows = [[InlineKeyboardButton(
            text=f"{'✅' if b['is_active'] else '❌'} {b['label']}",
            callback_data=f"bw:par:{b['id']}",
        )] for b in top]
        rows.append([InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")])
        await state.set_state(AddBtn.PARENT)
        try:
            await cb.message.edit_text(
                "🔹 <b>اختر الزر الخارجي الأب:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                parse_mode="HTML",
            )
        except Exception:
            await cb.message.answer(
                "🔹 <b>اختر الزر الخارجي الأب:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                parse_mode="HTML",
            )
    else:
        await state.set_state(AddBtn.LABEL)
        await cb.message.edit_text(
            "🔸 <b>أرسل اسم الزر الخارجي:</b>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )


@router.callback_query(AddBtn.PARENT, F.data.startswith("bw:par:"))
async def cb_choose_parent(cb: CallbackQuery, state: FSMContext) -> None:
    parent_id = int(cb.data.split(":")[2])
    await state.update_data(parent_id=parent_id)
    await state.set_state(AddBtn.LABEL)
    await cb.answer()
    try:
        await cb.message.edit_text(
            "🔹 <b>أرسل اسم الزر الداخلي:</b>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception:
        await cb.message.answer(
            "🔹 <b>أرسل اسم الزر الداخلي:</b>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )


@router.message(AddBtn.LABEL, F.text)
async def add_label(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    label = message.text.strip()
    if len(label) > 60:
        await message.answer("⚠️ الاسم طويل جداً (60 حرفاً كحد أقصى).")
        return
    await state.update_data(label=label)
    data = await state.get_data()

    if data.get("btn_type") == "ext":
        await state.set_state(AddBtn.SECTION)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🆓 مجاني",  callback_data="bw:sect:free"),
                InlineKeyboardButton(text="💎 مدفوع", callback_data="bw:sect:paid"),
            ],
            [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")],
        ])
        await message.answer(
            f"✅ <b>الاسم:</b> {label}\n\nاختر قسم الزر:",
            reply_markup=kb, parse_mode="HTML",
        )
    else:
        await _ask_response_type(message, state)


@router.callback_query(AddBtn.SECTION, F.data.startswith("bw:sect:"))
async def cb_choose_section(cb: CallbackQuery, state: FSMContext) -> None:
    section = cb.data.split(":")[2]
    await state.update_data(section=section)
    await cb.answer()
    await _ask_response_type(cb.message, state, edit=True)


async def _ask_response_type(msg, state: FSMContext, edit: bool = False) -> None:
    await state.set_state(AddBtn.RESP_TYPE)
    rows = [[InlineKeyboardButton(text=label, callback_data=f"bw:rt:{code}")] for label, code in RESPONSE_TYPES]
    rows.append([InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")])
    kb   = InlineKeyboardMarkup(inline_keyboard=rows)
    text = "📄 <b>اختر نوع الرد عند الضغط على الزر:</b>"
    if edit:
        try:
            await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(AddBtn.RESP_TYPE, F.data.startswith("bw:rt:"))
async def cb_choose_resp_type(cb: CallbackQuery, state: FSMContext) -> None:
    rtype = cb.data.split(":")[2]
    await state.update_data(resp_type=rtype)
    await cb.answer()

    if rtype == "none":
        await _save_button(cb.message, state, edit=True)
    else:
        await state.set_state(AddBtn.RESP_VALUE)
        hints = {
            "text":   "📝 <b>أرسل النص الذي سيظهر للمستخدم:</b>",
            "photo":  "🖼 <b>أرسل الصورة أو رابطها:</b>",
            "video":  "🎬 <b>أرسل الفيديو:</b>",
            "file":   "📁 <b>أرسل الملف:</b>",
            "audio":  "🎵 <b>أرسل ملف الصوت:</b>",
            "webapp": "🌐 <b>أرسل رابط الـ WebApp (https://):</b>",
        }
        await cb.message.edit_text(
            hints.get(rtype, "أرسل المحتوى:"),
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )


@router.message(AddBtn.RESP_VALUE)
async def add_resp_value(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data  = await state.get_data()
    rtype = data.get("resp_type")

    if rtype == "text":
        await state.update_data(text_content=message.text)
    elif rtype in ("photo", "video", "file", "audio"):
        file_id = None
        if rtype == "photo" and message.photo:
            file_id = message.photo[-1].file_id
        elif rtype == "video" and message.video:
            file_id = message.video.file_id
        elif rtype == "file" and message.document:
            file_id = message.document.file_id
        elif rtype == "audio" and message.audio:
            file_id = message.audio.file_id
        elif message.text and message.text.startswith("http"):
            await state.update_data(url=message.text.strip())
            await _save_button(message, state)
            return
        if not file_id:
            await message.answer(f"⚠️ يرجى إرسال {rtype} صحيح.")
            return
        await state.update_data(file_id=file_id, file_type=rtype)
    elif rtype == "webapp":
        url = (message.text or "").strip()
        if not url.startswith("https://"):
            await message.answer("⚠️ الرابط يجب أن يبدأ بـ https://")
            return
        await state.update_data(url=url)

    await _save_button(message, state)


async def _save_button(msg, state: FSMContext, edit: bool = False) -> None:
    data      = await state.get_data()
    await state.clear()

    btn_type   = data.get("btn_type", "ext")
    label      = data.get("label", "زر جديد")
    section    = data.get("section", "free")
    parent_id  = data.get("parent_id")
    resp_type  = data.get("resp_type", "none")
    text_cont  = data.get("text_content")
    file_id    = data.get("file_id")
    file_type  = data.get("file_type")
    url        = data.get("url")

    if btn_type == "int":
        section = "free"

    btn_id = db.add_button(label=label, section=section, parent_id=parent_id)
    db.set_response(
        button_id=btn_id, response_type=resp_type,
        text_content=text_cont, file_id=file_id,
        file_type=file_type, url=url,
    )

    from utils.keyboards import admin_panel_keyboard
    icon    = "🔸" if not parent_id else "🔹"
    sect_ar = "مجاني 🆓" if section == "free" else "مدفوع 💎"
    success_text = (
        f"✅ <b>تمت إضافة الزر بنجاح!</b>\n\n"
        f"{icon} الاسم:  <b>{label}</b>\n"
        f"📂 القسم:  {sect_ar}\n"
        f"📄 الرد:   {resp_type}\n"
        f"🆔 المعرّف: #{btn_id}"
    )
    if edit:
        try:
            await msg.edit_text(success_text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
            return
        except Exception:
            pass
    await msg.answer(success_text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
