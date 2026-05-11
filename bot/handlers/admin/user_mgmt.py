"""
handlers/admin/user_mgmt.py — إدارة المستخدمين
"""

import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

import database as db
from config import ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()
PER_PAGE = 8


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


@router.callback_query(F.data.startswith("ap:users:"))
async def cb_users(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    page  = int(cb.data.split(":")[2])
    total = db.get_users_count()
    users = db.get_all_users(page=page, per_page=PER_PAGE)

    rows = []
    for u in users:
        name  = u.get("first_name") or "مجهول"
        uname = f"@{u['username']}" if u.get("username") else "—"
        phone = "📞" if u.get("phone") else "  "
        blk   = "🚫" if u.get("is_blocked") else "  "
        rows.append([InlineKeyboardButton(
            text=f"{blk}{phone} {name} {uname}",
            callback_data=f"au:{u['user_id']}:{page}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=f"ap:users:{page-1}"))
    if (page + 1) * PER_PAGE < total:
        nav.append(InlineKeyboardButton(text="التالي ➡️", callback_data=f"ap:users:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ لوحة التحكم", callback_data="ap:panel")])

    pages_total = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    text = (
        f"👥 <b>المستخدمون</b> — الصفحة {page+1}/{pages_total}\n"
        f"الإجمالي: <b>{total}</b> مستخدم\n━━━━━━━━━━━━━━━\n"
        "🚫 محظور · 📞 لديه رقم"
    )
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")


@router.callback_query(F.data.startswith("au:") & ~F.data.startswith("au:blk:"))
async def cb_user_view(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    await cb.answer()
    parts   = cb.data.split(":")
    user_id = int(parts[1])
    page    = int(parts[2]) if len(parts) > 2 else 0
    user    = db.get_user(user_id)
    if not user:
        await cb.answer("⚠️ المستخدم غير موجود.", show_alert=True)
        return

    blk_label = "🟢 رفع الحظر" if user.get("is_blocked") else "🚫 حظر"
    name      = user.get("first_name") or "—"
    username  = f"@{user['username']}" if user.get("username") else "—"
    phone     = user.get("phone") or "—"
    joined    = (user.get("joined_at") or "—")[:16]
    last_seen = (user.get("last_seen") or "—")[:16]
    blocked   = "🚫 نعم" if user.get("is_blocked") else "✅ لا"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=blk_label, callback_data=f"au:blk:{user_id}:{page}")],
        [InlineKeyboardButton(text="◀️ رجوع للقائمة", callback_data=f"ap:users:{page}")],
    ])
    await cb.message.edit_text(
        f"👤 <b>تفاصيل المستخدم</b>\n{'━'*20}\n"
        f"🆔 <b>المعرّف:</b> <code>{user_id}</code>\n"
        f"👤 <b>الاسم:</b> {name}\n"
        f"🔗 <b>اليوزر:</b> {username}\n"
        f"📞 <b>الهاتف:</b> {phone}\n"
        f"📅 <b>انضم:</b> {joined}\n"
        f"🕐 <b>آخر ظهور:</b> {last_seen}\n"
        f"🚫 <b>محظور:</b> {blocked}",
        reply_markup=kb, parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("au:blk:"))
async def cb_toggle_block(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    parts   = cb.data.split(":")
    user_id = int(parts[2])
    page    = int(parts[3]) if len(parts) > 3 else 0

    now_blocked = db.toggle_block(user_id)
    status      = "تم الحظر 🚫" if now_blocked else "تم رفع الحظر ✅"
    await cb.answer(status, show_alert=True)

    user = db.get_user(user_id)
    if not user:
        return

    blk_label = "🟢 رفع الحظر" if user.get("is_blocked") else "🚫 حظر"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=blk_label, callback_data=f"au:blk:{user_id}:{page}")],
        [InlineKeyboardButton(text="◀️ رجوع للقائمة", callback_data=f"ap:users:{page}")],
    ])
    try:
        await cb.message.edit_text(
            f"👤 <b>تفاصيل المستخدم</b>\n{'━'*20}\n"
            f"🆔 <b>المعرّف:</b> <code>{user_id}</code>\n"
            f"👤 <b>الاسم:</b> {user.get('first_name','—')}\n"
            f"🚫 <b>محظور:</b> {'🚫 نعم' if user.get('is_blocked') else '✅ لا'}",
            reply_markup=kb, parse_mode="HTML",
        )
    except Exception:
        pass
