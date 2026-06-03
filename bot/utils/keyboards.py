"""utils/keyboards.py — مُنشئو لوحات المفاتيح"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import database as db

DEVELOPER_URL = "https://t.me/OX_U1"


def _developer_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="👨‍💻 المطور", url=DEVELOPER_URL)]


def build_start_keyboard() -> InlineKeyboardMarkup:
    """القائمة الرئيسية — زرّا الأقسام فقط"""
    all_roots = db.get_children(None)
    has_free = any(b["section"] == "free" for b in all_roots)
    has_paid = any(b["section"] == "paid" for b in all_roots)

    rows: list[list[InlineKeyboardButton]] = []

    # زرّا القسمين — قابلان للضغط
    rows.append([
        InlineKeyboardButton(
            text="🆓 الخدمات المجانية",
            callback_data="section:free",
        ),
        InlineKeyboardButton(
            text="💎 الخدمات المدفوعة",
            callback_data="section:paid",
        ),
    ])

    rows.append(_developer_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_section_keyboard(section: str) -> InlineKeyboardMarkup:
    """قائمة خدمات قسم معين (مجانية أو مدفوعة)"""
    all_roots = db.get_children(None)
    btns = [b for b in all_roots if b["section"] == section]

    rows: list[list[InlineKeyboardButton]] = []

    title = "🆓 الخدمات المجانية" if section == "free" else "💎 الخدمات المدفوعة"
    rows.append([InlineKeyboardButton(text=f"── {title} ──", callback_data="__noop__")])

    if btns:
        for btn in btns:
            rows.append(_btn_row(btn))
    else:
        rows.append([InlineKeyboardButton(text="— لا توجد خدمات حالياً —", callback_data="__noop__")])

    rows.append([InlineKeyboardButton(text="◀️ رجوع للقائمة الرئيسية", callback_data="back:main")])
    rows.append(_developer_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_children_keyboard(
    parent_id: int,
    parent_parent_id,
    section: str = "free",
) -> InlineKeyboardMarkup:
    children = db.get_children(parent_id)
    rows: list[list[InlineKeyboardButton]] = []

    for btn in children:
        rows.append(_btn_row(btn))

    if parent_parent_id is None:
        back_cb = f"section:{section}"
    else:
        back_cb = f"back:{parent_parent_id}"

    rows.append([InlineKeyboardButton(text="◀️ رجوع", callback_data=back_cb)])
    rows.append(_developer_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 الأزرار",    callback_data="ap:list"),
            InlineKeyboardButton(text="➕ إضافة زر",      callback_data="ap:add"),
        ],
        [
            InlineKeyboardButton(text="✏️ تعديل زر", callback_data="ap:edit"),
            InlineKeyboardButton(text="🗑 حذف زر",              callback_data="ap:del"),
        ],
        [
            InlineKeyboardButton(text="🔃 الترتيب",   callback_data="ap:order"),
            InlineKeyboardButton(text="👁 معاينة",         callback_data="ap:preview"),
        ],
        [
            InlineKeyboardButton(text="👥 المستخدمون", callback_data="ap:users:0"),
            InlineKeyboardButton(text="📊 الإحصائيات", callback_data="ap:stats"),
        ],
        [
            InlineKeyboardButton(text="🔧 إحصائيات الأدوات", callback_data="ap:tool_stats"),
            InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="ap:settings"),
        ],
        [
            InlineKeyboardButton(text="💾 نسخ احتياطي", callback_data="ap:backup"),
        ],
    ])


def _btn_row(btn: dict) -> list[InlineKeyboardButton]:
    """بناء صف زر واحد — يتعامل مع جميع أنواع الأزرار"""
    tool_id = btn.get("tool_id")
    if tool_id:
        return [InlineKeyboardButton(text=btn["label"], callback_data=f"tool:{tool_id}")]
    resp = db.get_response(btn["id"])
    if resp and resp["response_type"] == "webapp" and resp.get("url"):
        # WebApp buttons تحتاج صف خاص بها
        return [InlineKeyboardButton(text=btn["label"], web_app=WebAppInfo(url=resp["url"]))]
    return [InlineKeyboardButton(text=btn["label"], callback_data=f"nav:{btn['id']}")]
