"""
utils/keyboards.py — مُنشئو لوحات المفاتيح
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import database as db


# ── الصفحة الرئيسية الموحدة ───────────────────────────────────────────────────
#
#  التصميم:
#   [━━━ 🆓 الخدمات المجانية ━━━]   ← رأس غير قابل للضغط
#   [أداة 1]
#   [أداة 2]
#   ...
#   [━━━ 💎 الخدمات المدفوعة ━━━]   ← رأس غير قابل للضغط
#   [خدمة مدفوعة 1]  أو  [— قريباً —]
#
# ─────────────────────────────────────────────────────────────────────────────

def build_start_keyboard() -> InlineKeyboardMarkup:
    """
    لوحة المفاتيح الرئيسية — عمودان متجاوران:
      [🆓 الخدمات المجانية]  [💎 الخدمات المدفوعة]
      [زر مجاني 1]           [زر مدفوع 1]
      [زر مجاني 2]           [زر مدفوع 2]
      ...
    """
    all_roots = db.get_children(None)
    free_btns = [b for b in all_roots if b["section"] == "free"]
    paid_btns = [b for b in all_roots if b["section"] == "paid"]

    rows: list[list[InlineKeyboardButton]] = []

    # ── رأسا القسمين في نفس الصف ──
    rows.append([
        InlineKeyboardButton(text="🆓 الخدمات المجانية", callback_data="__noop__"),
        InlineKeyboardButton(text="💎 الخدمات المدفوعة", callback_data="__noop__"),
    ])

    # ── دمج الأزرار في صفوف متجاورة ──
    max_len = max(len(free_btns), len(paid_btns), 1)
    for i in range(max_len):
        row: list[InlineKeyboardButton] = []

        # عمود المجاني (أيسر)
        if i < len(free_btns):
            row.extend(_btn_row(free_btns[i]))
        else:
            row.append(InlineKeyboardButton(text="ㅤ", callback_data="__noop__"))

        # عمود المدفوع (أيمن)
        if i < len(paid_btns):
            row.extend(_btn_row(paid_btns[i]))
        elif i == 0 and not paid_btns:
            row.append(InlineKeyboardButton(text="— قريباً —", callback_data="__noop__"))
        else:
            row.append(InlineKeyboardButton(text="ㅤ", callback_data="__noop__"))

        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── الأزرار الفرعية (عمق أعمق) ───────────────────────────────────────────────

def build_children_keyboard(
    parent_id: int,
    parent_parent_id,
    section: str = "free",
) -> InlineKeyboardMarkup:
    """
    يعرض الأزرار الداخلية لزر معيّن مع زر رجوع مناسب.
    """
    children = db.get_children(parent_id)
    rows: list[list[InlineKeyboardButton]] = []

    for btn in children:
        rows.append(_btn_row(btn))

    if parent_parent_id is None:
        back_cb = "back:main"
    else:
        back_cb = f"back:{parent_parent_id}"

    rows.append([InlineKeyboardButton(text="◀️ رجوع", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── لوحة تحكم الأدمن ────────────────────────────────────────────────────────

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 الأزرار",          callback_data="ap:list"),
            InlineKeyboardButton(text="➕ إضافة زر",         callback_data="ap:add"),
        ],
        [
            InlineKeyboardButton(text="✏️ تعديل زر",        callback_data="ap:edit"),
            InlineKeyboardButton(text="🗑 حذف زر",           callback_data="ap:del"),
        ],
        [
            InlineKeyboardButton(text="🔃 الترتيب",          callback_data="ap:order"),
            InlineKeyboardButton(text="👁 معاينة",           callback_data="ap:preview"),
        ],
        [
            InlineKeyboardButton(text="👥 المستخدمون",       callback_data="ap:users:0"),
            InlineKeyboardButton(text="📊 الإحصائيات",       callback_data="ap:stats"),
        ],
        [
            InlineKeyboardButton(text="🔧 إحصائيات الأدوات", callback_data="ap:tool_stats"),
            InlineKeyboardButton(text="⚙️ الإعدادات",       callback_data="ap:settings"),
        ],
        [
            InlineKeyboardButton(text="💾 نسخ احتياطي",      callback_data="ap:backup"),
        ],
    ])


# ── دالة مساعدة داخلية ───────────────────────────────────────────────────────

def _btn_row(btn: dict) -> list[InlineKeyboardButton]:
    """بناء صف زر واحد — يدعم tool_id للأدوات المدمجة"""
    tool_id = btn.get("tool_id")
    if tool_id:
        return [InlineKeyboardButton(
            text=btn["label"],
            callback_data=f"tool:{tool_id}",
        )]
    resp = db.get_response(btn["id"])
    if resp and resp["response_type"] == "webapp" and resp.get("url"):
        return [InlineKeyboardButton(
            text=btn["label"],
            web_app=WebAppInfo(url=resp["url"]),
        )]
    return [InlineKeyboardButton(
        text=btn["label"],
        callback_data=f"nav:{btn['id']}",
    )]
