"""
handlers/admin/panel.py — لوحة تحكم الأدمن
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

import database as db
from config import ADMIN_ID, DEFAULT_WELCOME
from utils.keyboards import admin_panel_keyboard, build_start_keyboard

logger = logging.getLogger(__name__)
router = Router()


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def _back_to_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ لوحة التحكم", callback_data="ap:panel")]
    ])


# ══════════════════════════════════════════════════════════════
#  /admin أمر
# ══════════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("🚫 ليس لديك صلاحية الوصول.")
        return
    await message.answer(
        "🎛 <b>لوحة تحكم الأدمن</b>\nاختر من القائمة:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ap:panel")
async def cb_panel(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await state.clear()
    await cb.answer()
    try:
        await cb.message.edit_text(
            "🎛 <b>لوحة تحكم الأدمن</b>\nاختر من القائمة:",
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        await cb.message.answer(
            "🎛 <b>لوحة تحكم الأدمن</b>\nاختر من القائمة:",
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML",
        )


# ══════════════════════════════════════════════════════════════
#  قائمة الأزرار
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ap:list")
async def cb_list(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    btns = db.get_all_buttons_flat()
    if not btns:
        await cb.message.edit_text("📋 لا توجد أزرار بعد.", reply_markup=_back_to_panel())
        return

    lines = ["📋 <b>جميع الأزرار:</b>\n"]
    for b in btns:
        indent = "  └─ " if b["parent_id"] else ""
        status = "✅" if b["is_active"] else "❌"
        sect   = "🆓" if b["section"] == "free" else "💎"
        tool   = f" [أداة:{b['tool_id']}]" if b.get("tool_id") else ""
        lines.append(f"{indent}{status}{sect} <b>#{b['id']}</b> {b['label']}{tool}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."

    await cb.message.edit_text(text, reply_markup=_back_to_panel(), parse_mode="HTML")


# ══════════════════════════════════════════════════════════════
#  تعديل زر
# ══════════════════════════════════════════════════════════════

class EditBtn(StatesGroup):
    CHOOSE       = State()
    FIELD        = State()
    VALUE        = State()
    RESP_TYPE    = State()
    RESP_VALUE   = State()


@router.callback_query(F.data == "ap:edit")
async def cb_edit_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    await state.set_state(EditBtn.CHOOSE)
    btns = db.get_all_buttons_flat()
    rows = []
    for b in btns[:20]:
        rows.append([InlineKeyboardButton(
            text=f"{'  ' if b['parent_id'] else ''}{'✅' if b['is_active'] else '❌'} #{b['id']} {b['label'][:25]}",
            callback_data=f"eb:pick:{b['id']}",
        )])
    rows.append([InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")])
    await cb.message.edit_text(
        "✏️ <b>اختر الزر الذي تريد تعديله:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


@router.callback_query(EditBtn.CHOOSE, F.data.startswith("eb:pick:"))
async def cb_edit_pick(cb: CallbackQuery, state: FSMContext) -> None:
    btn_id = int(cb.data.split(":")[2])
    await state.update_data(edit_btn_id=btn_id)
    await state.set_state(EditBtn.FIELD)
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 الاسم",         callback_data="eb:field:label")],
        [InlineKeyboardButton(text="🔀 القسم",          callback_data="eb:field:section")],
        [InlineKeyboardButton(text="📄 المحتوى",        callback_data="eb:field:content")],
        [InlineKeyboardButton(text="🔛 تفعيل/تعطيل",   callback_data="eb:field:toggle")],
        [InlineKeyboardButton(text="◀️ إلغاء",          callback_data="ap:panel")],
    ])
    await cb.message.edit_text(
        f"✏️ ماذا تريد تعديل في الزر <b>#{btn_id}</b>؟",
        reply_markup=kb, parse_mode="HTML",
    )


_EDIT_RESPONSE_TYPES = [
    ("📝 رسالة نصية", "text"),
    ("🖼 صورة",        "photo"),
    ("🎬 فيديو",       "video"),
    ("📁 ملف",         "file"),
    ("🎵 صوت",         "audio"),
    ("🔗 رابط ويب",    "url_link"),
    ("📨 رابط تلجرام", "tg_link"),
    ("🌐 WebApp",      "webapp"),
    ("❌ بدون رد",    "none"),
]


@router.callback_query(EditBtn.FIELD, F.data.startswith("eb:field:"))
async def cb_edit_field(cb: CallbackQuery, state: FSMContext) -> None:
    field  = cb.data.split(":")[2]
    data   = await state.get_data()
    btn_id = data["edit_btn_id"]
    await cb.answer()

    if field == "toggle":
        new_state = db.toggle_button(btn_id)
        status    = "مُفعَّل ✅" if new_state else "مُعطَّل ❌"
        await state.clear()
        await cb.message.edit_text(
            f"✅ تم تغيير حالة الزر #{btn_id} إلى: {status}",
            reply_markup=_back_to_panel(),
        )
    elif field == "section":
        await state.update_data(edit_field="section")
        await state.set_state(EditBtn.VALUE)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🆓 مجاني",  callback_data="eb:val:free"),
                InlineKeyboardButton(text="💎 مدفوع", callback_data="eb:val:paid"),
            ],
            [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")],
        ])
        await cb.message.edit_text("🔀 اختر القسم الجديد:", reply_markup=kb)
    elif field == "content":
        await state.set_state(EditBtn.RESP_TYPE)
        rows = [[InlineKeyboardButton(text=lbl, callback_data=f"eb:rt:{code}")]
                for lbl, code in _EDIT_RESPONSE_TYPES]
        rows.append([InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")])
        await cb.message.edit_text(
            f"📄 <b>اختر نوع المحتوى الجديد للزر #{btn_id}:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML",
        )
    else:
        await state.update_data(edit_field=field)
        await state.set_state(EditBtn.VALUE)
        await cb.message.edit_text(
            f"✏️ أرسل القيمة الجديدة لحقل <b>{field}</b>:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")]
            ]),
            parse_mode="HTML",
        )


@router.callback_query(EditBtn.RESP_TYPE, F.data.startswith("eb:rt:"))
async def cb_edit_resp_type(cb: CallbackQuery, state: FSMContext) -> None:
    rtype = cb.data.split(":")[2]
    await state.update_data(edit_resp_type=rtype)
    await cb.answer()

    if rtype == "none":
        data   = await state.get_data()
        btn_id = data["edit_btn_id"]
        await state.clear()
        db.set_response(button_id=btn_id, response_type="none")
        await cb.message.edit_text(
            f"✅ تم تعيين الزر #{btn_id} بلا رد.",
            reply_markup=_back_to_panel(),
        )
        return

    await state.set_state(EditBtn.RESP_VALUE)
    hints = {
        "text":     "📝 <b>أرسل النص الجديد:</b>",
        "photo":    "🖼 <b>أرسل الصورة أو رابطها:</b>",
        "video":    "🎬 <b>أرسل الفيديو:</b>",
        "file":     "📁 <b>أرسل الملف:</b>",
        "audio":    "🎵 <b>أرسل ملف الصوت:</b>",
        "url_link": "🔗 <b>أرسل رابط الموقع:</b>\nمثال: <code>https://google.com</code>",
        "tg_link":  "📨 <b>أرسل رابط تلجرام:</b>\nمثال: <code>https://t.me/username</code>",
        "webapp":   "🌐 <b>أرسل رابط الـ WebApp (https://):</b>",
    }
    await cb.message.edit_text(
        hints.get(rtype, "أرسل المحتوى الجديد:"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")]
        ]),
        parse_mode="HTML",
    )


@router.message(EditBtn.RESP_VALUE)
async def handle_edit_resp_value(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data   = await state.get_data()
    btn_id = data["edit_btn_id"]
    rtype  = data.get("edit_resp_type", "text")

    text_content = None
    file_id      = None
    file_type    = None
    url          = None

    if rtype == "text":
        text_content = message.text
    elif rtype in ("photo", "video", "file", "audio"):
        if rtype == "photo" and message.photo:
            file_id   = message.photo[-1].file_id
            file_type = "photo"
        elif rtype == "video" and message.video:
            file_id   = message.video.file_id
            file_type = "video"
        elif rtype == "file" and message.document:
            file_id   = message.document.file_id
            file_type = "file"
        elif rtype == "audio" and message.audio:
            file_id   = message.audio.file_id
            file_type = "audio"
        elif message.text and message.text.startswith("http"):
            url = message.text.strip()
        else:
            await message.answer(f"⚠️ يرجى إرسال {rtype} صحيح.")
            return
    elif rtype in ("url_link", "tg_link"):
        url = (message.text or "").strip()
        if not url.startswith("http"):
            await message.answer("⚠️ الرابط يجب أن يبدأ بـ http:// أو https://")
            return
    elif rtype == "webapp":
        url = (message.text or "").strip()
        if not url.startswith("https://"):
            await message.answer("⚠️ الرابط يجب أن يبدأ بـ https://")
            return

    await state.clear()
    db.set_response(
        button_id=btn_id, response_type=rtype,
        text_content=text_content, file_id=file_id,
        file_type=file_type, url=url,
    )
    await message.answer(
        f"✅ <b>تم تحديث محتوى الزر #{btn_id} بنجاح!</b>",
        reply_markup=admin_panel_keyboard(), parse_mode="HTML",
    )


@router.callback_query(EditBtn.VALUE, F.data.startswith("eb:val:"))
async def cb_edit_val_choice(cb: CallbackQuery, state: FSMContext) -> None:
    value = cb.data.split(":")[2]
    data  = await state.get_data()
    btn_id= data["edit_btn_id"]
    field = data.get("edit_field", "section")
    await state.clear()
    await cb.answer()
    db.update_button(btn_id, **{field: value})
    await cb.message.edit_text(
        f"✅ تم تحديث <b>{field}</b> للزر #{btn_id} إلى: {value}",
        reply_markup=_back_to_panel(), parse_mode="HTML",
    )


@router.message(EditBtn.VALUE, F.text)
async def handle_edit_value(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data   = await state.get_data()
    btn_id = data["edit_btn_id"]
    field  = data.get("edit_field", "label")
    await state.clear()
    db.update_button(btn_id, **{field: message.text.strip()})
    await message.answer(
        f"✅ تم تحديث <b>{field}</b> للزر #{btn_id}",
        reply_markup=admin_panel_keyboard(), parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  حذف زر
# ══════════════════════════════════════════════════════════════

class DelBtn(StatesGroup):
    CONFIRM = State()


@router.callback_query(F.data == "ap:del")
async def cb_del_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    btns = db.get_all_buttons_flat()
    rows = []
    for b in [x for x in btns if not x.get("tool_id")][:20]:
        rows.append([InlineKeyboardButton(
            text=f"{'✅' if b['is_active'] else '❌'} #{b['id']} {b['label'][:25]}",
            callback_data=f"db:pick:{b['id']}",
        )])
    rows.append([InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")])
    await cb.message.edit_text(
        "🗑 <b>اختر الزر الذي تريد حذفه:</b>\n"
        "<i>ملاحظة: الأدوات المدمجة لا تُحذف من هنا.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("db:pick:"))
async def cb_del_confirm(cb: CallbackQuery, state: FSMContext) -> None:
    btn_id = int(cb.data.split(":")[2])
    btn    = db.get_button(btn_id)
    if not btn:
        await cb.answer("⚠️ الزر غير موجود.", show_alert=True)
        return
    await state.update_data(del_btn_id=btn_id)
    await state.set_state(DelBtn.CONFIRM)
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ نعم، احذف", callback_data=f"db:confirm:{btn_id}"),
            InlineKeyboardButton(text="❌ لا",        callback_data="ap:panel"),
        ]
    ])
    await cb.message.edit_text(
        f"⚠️ هل أنت متأكد من حذف الزر:\n<b>#{btn_id} — {btn['label']}</b>?\n"
        "سيتم حذف جميع الأزرار الفرعية أيضاً.",
        reply_markup=kb, parse_mode="HTML",
    )


@router.callback_query(DelBtn.CONFIRM, F.data.startswith("db:confirm:"))
async def cb_del_execute(cb: CallbackQuery, state: FSMContext) -> None:
    btn_id = int(cb.data.split(":")[2])
    await state.clear()
    await cb.answer()
    success = db.delete_button(btn_id)
    msg = "✅ تم الحذف بنجاح." if success else "❌ فشل الحذف."
    await cb.message.edit_text(msg, reply_markup=_back_to_panel())


# ══════════════════════════════════════════════════════════════
#  إعادة الترتيب
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ap:order")
async def cb_order(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    btns = db.get_top_level_buttons()
    rows = []
    for b in btns:
        rows.append([
            InlineKeyboardButton(text="⬆️", callback_data=f"ord:up:{b['id']}"),
            InlineKeyboardButton(text=b["label"][:20], callback_data="__sep__"),
            InlineKeyboardButton(text="⬇️", callback_data=f"ord:dn:{b['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="◀️ لوحة التحكم", callback_data="ap:panel")])
    await cb.message.edit_text(
        "🔃 <b>إعادة ترتيب الأزرار:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("ord:"))
async def cb_reorder(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    _, direction, btn_id_str = cb.data.split(":")
    moved = db.reorder_buttons(int(btn_id_str), direction)
    await cb.answer("✅ تم التحريك" if moved else "⚠️ لا يمكن التحريك")
    if moved:
        btns = db.get_top_level_buttons()
        rows = []
        for b in btns:
            rows.append([
                InlineKeyboardButton(text="⬆️", callback_data=f"ord:up:{b['id']}"),
                InlineKeyboardButton(text=b["label"][:20], callback_data="__sep__"),
                InlineKeyboardButton(text="⬇️", callback_data=f"ord:dn:{b['id']}"),
            ])
        rows.append([InlineKeyboardButton(text="◀️ لوحة التحكم", callback_data="ap:panel")])
        try:
            await cb.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  معاينة واجهة المستخدم
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ap:preview")
async def cb_preview(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    welcome_tmpl = db.get_setting("welcome_message", DEFAULT_WELCOME)
    text = welcome_tmpl.replace("{name}", "زائر")
    kb   = build_start_keyboard()
    try:
        await cb.message.edit_text(
            f"👁 <b>معاينة واجهة المستخدم</b>\n{'━'*20}\n\n" + text,
            reply_markup=kb, parse_mode="HTML",
        )
    except Exception as e:
        await cb.message.answer(str(e))


# ══════════════════════════════════════════════════════════════
#  الإحصائيات
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ap:stats")
async def cb_stats(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()

    total      = db.get_users_count()
    today      = db.get_new_users_today()
    with_phone = db.get_users_with_phone()
    btns       = db.get_all_buttons_flat()
    active     = sum(1 for b in btns if b["is_active"])
    tools_cnt  = sum(1 for b in btns if b.get("tool_id"))

    text = (
        "📊 <b>الإحصائيات</b>\n"
        f"{'━'*22}\n"
        f"👥 <b>المستخدمون</b>\n"
        f"  ├ إجمالي:   <b>{total}</b>\n"
        f"  ├ اليوم:    <b>{today}</b>\n"
        f"  └ لديهم رقم: <b>{with_phone}</b>\n\n"
        f"📋 <b>الأزرار</b>\n"
        f"  ├ إجمالي: <b>{len(btns)}</b>\n"
        f"  ├ نشطة:   <b>{active}</b>\n"
        f"  └ أدوات مدمجة: <b>{tools_cnt}</b>"
    )
    await cb.message.edit_text(text, reply_markup=_back_to_panel(), parse_mode="HTML")


@router.callback_query(F.data == "ap:tool_stats")
async def cb_tool_stats(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    stats = db.get_tool_stats()
    if not stats:
        await cb.message.edit_text("📊 لا توجد إحصائيات بعد.", reply_markup=_back_to_panel())
        return

    tool_names = {
        "username_lookup":  "🔎 البحث عن اسم مستخدم",
        "website_analyzer": "🌐 تحليل الموقع",
        "ip_geolocation":   "📍 تحليل IP",
        "email_checker":    "📧 فحص البريد",
        "password_strength":"🔐 فحص كلمة المرور",
        "password_gen":     "🔑 توليد كلمة مرور",
        "qr_analyzer":      "📷 تحليل QR",
        "encryption":       "🧠 أدوات التشفير",
        "domain_analyzer":  "🌍 تحليل الدومين",
        "vpn_detector":     "🛡️ كشف VPN",
        "legal_info":       "⚖️ معلومات قانونية",
        "security_tips":    "📚 التوعية الأمنية",
    }

    lines = ["🔧 <b>إحصائيات استخدام الأدوات</b>\n" + "━"*22 + "\n"]
    for s in stats:
        name = tool_names.get(s["tool_id"], s["tool_id"])
        lines.append(f"{name}\n  ├ الاستخدامات: <b>{s['usage_count']}</b> · المستخدمون: <b>{s['unique_users']}</b>\n")

    await cb.message.edit_text("\n".join(lines), reply_markup=_back_to_panel(), parse_mode="HTML")


# ══════════════════════════════════════════════════════════════
#  الإعدادات
# ══════════════════════════════════════════════════════════════

class WelcomeEdit(StatesGroup):
    WAITING = State()


def _cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")]
    ])


@router.callback_query(F.data == "ap:settings")
async def cb_settings(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    welcome = db.get_setting("welcome_message", DEFAULT_WELCOME)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ تعديل رسالة الترحيب", callback_data="ap:welcome")],
        [InlineKeyboardButton(text="◀️ لوحة التحكم",         callback_data="ap:panel")],
    ])
    await cb.message.edit_text(
        "⚙️ <b>الإعدادات</b>\n\nرسالة الترحيب الحالية:\n\n"
        f"<i>{welcome[:300]}</i>",
        reply_markup=kb, parse_mode="HTML",
    )


@router.callback_query(F.data == "ap:welcome")
async def cb_welcome_edit(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    await state.set_state(WelcomeEdit.WAITING)
    await cb.message.edit_text(
        "✏️ <b>أرسل رسالة الترحيب الجديدة:</b>\n\n"
        "استخدم <code>{name}</code> لاسم المستخدم\n"
        "يمكنك استخدام HTML: <b>غامق</b> <i>مائل</i>",
        reply_markup=_cancel_kb(), parse_mode="HTML",
    )


@router.message(WelcomeEdit.WAITING, F.text)
async def save_welcome(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    db.set_setting("welcome_message", message.text)
    await message.answer(
        "✅ <b>تم تحديث رسالة الترحيب!</b>",
        reply_markup=admin_panel_keyboard(), parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════
#  نسخ احتياطي
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ap:backup")
async def cb_backup(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer("⏳ جاري إعداد النسخة الاحتياطية...")
    try:
        from config import DB_PATH
        with open(DB_PATH, "rb") as f:
            data = f.read()
        doc = BufferedInputFile(data, filename="bot_backup.db")
        await cb.message.answer_document(
            doc,
            caption="💾 <b>نسخة احتياطية من قاعدة البيانات</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await cb.message.answer(f"❌ فشل إنشاء النسخة: {e}")
