"""utils/keyboards.py — مُنشئو لوحات المفاتيح"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import database as db

DEVELOPER_URL = "https://t.me/OX_U1"


def _developer_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="👨‍💻 المطور", url=DEVELOPER_URL)]


def build_start_keyboard() -> InlineKeyboardMarkup:
    all_roots = db.get_children(None)
    free_btns = [b for b in all_roots if b["section"] == "free"]
    paid_btns = [b for b in all_roots if b["section"] == "paid"]

    rows: list[list[InlineKeyboardButton]] = []

    rows.append([
        InlineKeyboardButton(text="🆓 الخدمات المجانية", callback_data="__noop__"),
        InlineKeyboardButton(text="💎 الخدمات المدفوعة", callback_data="__noop__"),
    ])

    max_len = max(len(free_btns), len(paid_btns), 1)
    for i in range(max_len):
        row: list[InlineKeyboardButton] = []

        if i < len(free_btns):
            row.extend(_btn_row(free_btns[i]))
        else:
            row.append(InlineKeyboardButton(text="　", callback_data="__noop__"))

        if i < len(paid_btns):
            row.extend(_btn_row(paid_btns[i]))
        elif i == 0 and not paid_btns:
            row.append(InlineKeyboardButton(text="— قريباً —", callback_data="__noop__"))
        else:
            row.append(InlineKeyboardButton(text="　", callback_data="__noop__"))

        rows.append(row)

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
        back_cb = "back:main"
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
    tool_id = btn.get("tool_id")
    if tool_id:
        return [InlineKeyboardButton(text=btn["label"], callback_data=f"tool:{tool_id}")]
    resp = db.get_response(btn["id"])
    if resp and resp["response_type"] == "webapp" and resp.get("url"):
        return [InlineKeyboardButton(text=btn["label"], web_app=WebAppInfo(url=resp["url"]))]
    return [InlineKeyboardButton(text=btn["label"], callback_data=f"nav:{btn['id']}")]
