"""
handlers/tools/tools_handler.py — معالج أدوات الأمن السيبراني
"""

import logging
import io

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile,
)

import database as db
import tools as t

logger = logging.getLogger(__name__)
router = Router()


# ══════════════════════════════════════════════════════════════
#  حالات FSM
# ══════════════════════════════════════════════════════════════

class ToolState(StatesGroup):
    waiting_username   = State()
    waiting_website    = State()
    waiting_ip         = State()
    waiting_email      = State()
    waiting_password   = State()
    waiting_pw_length  = State()
    waiting_qr_text    = State()
    waiting_enc_op     = State()
    waiting_enc_text   = State()
    waiting_domain     = State()
    waiting_vpn_ip     = State()
    enc_operation      = State()


# ══════════════════════════════════════════════════════════════
#  لوحات المفاتيح المساعدة
# ══════════════════════════════════════════════════════════════

def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ رجوع للقائمة", callback_data="back:main")]
    ])


def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="tool:cancel")]
    ])


# ══════════════════════════════════════════════════════════════
#  الرجوع والإلغاء
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer("تم الإلغاء")
    from utils.keyboards import build_start_keyboard
    from config import DEFAULT_WELCOME
    import database as _db
    welcome = _db.get_setting("welcome_message", DEFAULT_WELCOME)
    name    = cb.from_user.first_name or "زائر"
    try:
        await cb.message.edit_text(
            welcome.replace("{name}", name),
            reply_markup=build_start_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        try:
            await cb.message.answer(
                welcome.replace("{name}", name),
                reply_markup=build_start_keyboard(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("خطأ في الإلغاء: %s", e)


# ══════════════════════════════════════════════════════════════
#  دالة مساعدة: إرسال رسالة خطأ للمستخدم
# ══════════════════════════════════════════════════════════════

async def _send_error(msg, text: str = "❌ حدث خطأ أثناء التنفيذ، حاول مرة أخرى.") -> None:
    try:
        await msg.edit_text(text, reply_markup=_back_kb())
    except Exception:
        try:
            await msg.answer(text, reply_markup=_back_kb())
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  1. البحث عن اسم المستخدم
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:username_lookup")
async def cb_username_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_username)
    db.log_tool_usage(cb.from_user.id, "username_lookup")
    try:
        await cb.message.edit_text(
            "🔎 <b>البحث عن اسم المستخدم</b>\n"
            f"{'━' * 22}\n\n"
            "أرسل اسم المستخدم للبحث عنه في:\n"
            "Instagram · TikTok · X · Facebook · GitHub\n\n"
            "مثال: <code>elonmusk</code> أو <code>@elonmusk</code>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة البحث: %s", e)


@router.message(ToolState.waiting_username, F.text)
async def handle_username(message: Message, state: FSMContext) -> None:
    await state.clear()
    msg = await message.answer("⏳ جاري البحث عبر المنصات...", parse_mode="HTML")
    try:
        result = await t.lookup_username(message.text)
        await msg.edit_text(result, parse_mode="HTML", reply_markup=_back_kb(), disable_web_page_preview=True)
    except Exception as e:
        logger.error("خطأ في lookup_username: %s", e)
        await _send_error(msg)


# ══════════════════════════════════════════════════════════════
#  2. تحليل الموقع
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:website_analyzer")
async def cb_website_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_website)
    db.log_tool_usage(cb.from_user.id, "website_analyzer")
    try:
        await cb.message.edit_text(
            "🌐 <b>تحليل الموقع</b>\n"
            f"{'━' * 22}\n\n"
            "أرسل رابط أو اسم الموقع:\n\n"
            "مثال: <code>google.com</code> أو <code>https://example.com</code>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة تحليل الموقع: %s", e)


@router.message(ToolState.waiting_website, F.text)
async def handle_website(message: Message, state: FSMContext) -> None:
    await state.clear()
    msg = await message.answer("⏳ جاري تحليل الموقع...")
    try:
        result = await t.analyze_website(message.text.strip())
        await msg.edit_text(result, parse_mode="HTML", reply_markup=_back_kb(), disable_web_page_preview=True)
    except Exception as e:
        logger.error("خطأ في analyze_website: %s", e)
        await _send_error(msg)


# ══════════════════════════════════════════════════════════════
#  3. تحليل IP
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:ip_geolocation")
async def cb_ip_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_ip)
    db.log_tool_usage(cb.from_user.id, "ip_geolocation")
    try:
        await cb.message.edit_text(
            "📍 <b>تحليل IP</b>\n"
            f"{'━' * 22}\n\n"
            "أرسل عنوان IP للتحليل:\n\n"
            "مثال: <code>8.8.8.8</code> أو <code>1.1.1.1</code>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة تحليل IP: %s", e)


@router.message(ToolState.waiting_ip, F.text)
async def handle_ip(message: Message, state: FSMContext) -> None:
    await state.clear()
    msg = await message.answer("⏳ جاري تحليل عنوان IP...")
    try:
        result = await t.geolocate_ip(message.text.strip())
        await msg.edit_text(result, parse_mode="HTML", reply_markup=_back_kb(), disable_web_page_preview=True)
    except Exception as e:
        logger.error("خطأ في geolocate_ip: %s", e)
        await _send_error(msg)


# ══════════════════════════════════════════════════════════════
#  4. فحص البريد الإلكتروني
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:email_checker")
async def cb_email_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_email)
    db.log_tool_usage(cb.from_user.id, "email_checker")
    try:
        await cb.message.edit_text(
            "📧 <b>فحص البريد الإلكتروني</b>\n"
            f"{'━' * 22}\n\n"
            "أرسل عنوان البريد الإلكتروني:\n\n"
            "مثال: <code>example@gmail.com</code>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة فحص البريد: %s", e)


@router.message(ToolState.waiting_email, F.text)
async def handle_email(message: Message, state: FSMContext) -> None:
    await state.clear()
    msg = await message.answer("⏳ جاري فحص البريد الإلكتروني...")
    try:
        result = await t.check_email(message.text.strip())
        await msg.edit_text(result, parse_mode="HTML", reply_markup=_back_kb())
    except Exception as e:
        logger.error("خطأ في check_email: %s", e)
        await _send_error(msg)


# ══════════════════════════════════════════════════════════════
#  5. فحص قوة كلمة المرور
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:password_strength")
async def cb_pw_strength_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_password)
    db.log_tool_usage(cb.from_user.id, "password_strength")
    try:
        await cb.message.edit_text(
            "🔐 <b>فحص قوة كلمة المرور</b>\n"
            f"{'━' * 22}\n\n"
            "أرسل كلمة المرور لتحليل قوتها:\n\n"
            "⚠️ <i>لا تُرسل كلمة مرور حساب حقيقي تستخدمه حالياً.</i>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة فحص كلمة المرور: %s", e)


@router.message(ToolState.waiting_password, F.text)
async def handle_pw_strength(message: Message, state: FSMContext) -> None:
    await state.clear()
    try:
        from tools.password_tools import check_password_strength
        result = check_password_strength(message.text)
        await message.answer(result, parse_mode="HTML", reply_markup=_back_kb())
    except Exception as e:
        logger.error("خطأ في check_password_strength: %s", e)
        await message.answer("❌ حدث خطأ في الفحص، حاول مرة أخرى.", reply_markup=_back_kb())


# ══════════════════════════════════════════════════════════════
#  6. توليد كلمة مرور
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:password_gen")
async def cb_pw_gen(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    db.log_tool_usage(cb.from_user.id, "password_gen")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="8 أحرف",  callback_data="pwgen:8"),
            InlineKeyboardButton(text="12 حرف",  callback_data="pwgen:12"),
            InlineKeyboardButton(text="16 حرف",  callback_data="pwgen:16"),
        ],
        [
            InlineKeyboardButton(text="20 حرف",  callback_data="pwgen:20"),
            InlineKeyboardButton(text="24 حرف",  callback_data="pwgen:24"),
            InlineKeyboardButton(text="32 حرف",  callback_data="pwgen:32"),
        ],
        [InlineKeyboardButton(text="◀️ رجوع", callback_data="back:main")],
    ])
    try:
        await cb.message.edit_text(
            "🔑 <b>توليد كلمة مرور قوية</b>\n"
            f"{'━' * 22}\n\n"
            "اختر طول كلمة المرور:",
            reply_markup=kb, parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة توليد كلمة المرور: %s", e)


@router.callback_query(F.data.startswith("pwgen:"))
async def cb_pw_gen_result(cb: CallbackQuery) -> None:
    await cb.answer()
    try:
        length = int(cb.data.split(":")[1])
        from tools.password_tools import password_gen_response
        result = password_gen_response(length)
        await cb.message.edit_text(result, parse_mode="HTML", reply_markup=_back_kb())
    except Exception as e:
        logger.error("خطأ في توليد كلمة المرور: %s", e)
        await cb.answer("❌ حدث خطأ، حاول مرة أخرى.", show_alert=True)


# ══════════════════════════════════════════════════════════════
#  7. تحليل QR Code
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:qr_analyzer")
async def cb_qr_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    db.log_tool_usage(cb.from_user.id, "qr_analyzer")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 توليد QR من نص", callback_data="qr:generate")],
        [InlineKeyboardButton(text="🔍 تحليل نص QR",    callback_data="qr:analyze")],
        [InlineKeyboardButton(text="◀️ رجوع",            callback_data="back:main")],
    ])
    try:
        await cb.message.edit_text(
            "📷 <b>أدوات QR Code</b>\n"
            f"{'━' * 22}\n\n"
            "اختر العملية المطلوبة:",
            reply_markup=kb, parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة QR: %s", e)


@router.callback_query(F.data == "qr:generate")
async def cb_qr_gen_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_qr_text)
    await state.update_data(qr_mode="generate")
    try:
        await cb.message.edit_text(
            "📝 <b>توليد QR Code</b>\n\n"
            "أرسل النص أو الرابط لتحويله إلى QR Code:\n\n"
            "مثال: <code>https://google.com</code>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة توليد QR: %s", e)


@router.callback_query(F.data == "qr:analyze")
async def cb_qr_analyze_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_qr_text)
    await state.update_data(qr_mode="analyze")
    try:
        await cb.message.edit_text(
            "🔍 <b>تحليل محتوى QR Code</b>\n\n"
            "أرسل النص المستخرج من QR Code لتحليله:\n\n"
            "مثال: <code>https://example.com/redirect?id=123</code>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة تحليل QR: %s", e)


@router.message(ToolState.waiting_qr_text, F.text)
async def handle_qr_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    mode = data.get("qr_mode", "analyze")
    await state.clear()

    if mode == "generate":
        msg = await message.answer("⏳ جاري توليد QR Code...")
        try:
            from tools.qr_tools import generate_qr
            qr_buffer = generate_qr(message.text.strip())
            photo = BufferedInputFile(qr_buffer.read(), filename="qrcode.png")
            await msg.delete()
            await message.answer_photo(
                photo,
                caption=f"📷 <b>QR Code للنص:</b>\n<code>{message.text[:100]}</code>",
                parse_mode="HTML",
                reply_markup=_back_kb(),
            )
        except Exception as e:
            logger.error("خطأ في توليد QR: %s", e)
            await _send_error(msg, f"❌ خطأ في توليد QR: {str(e)[:60]}")
    else:
        try:
            result = t.analyze_qr_text(message.text.strip())
            await message.answer(result, parse_mode="HTML", reply_markup=_back_kb())
        except Exception as e:
            logger.error("خطأ في تحليل QR: %s", e)
            await message.answer("❌ حدث خطأ في التحليل، حاول مرة أخرى.", reply_markup=_back_kb())


# ══════════════════════════════════════════════════════════════
#  8. أدوات التشفير
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:encryption")
async def cb_enc_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    db.log_tool_usage(cb.from_user.id, "encryption")
    from tools.encryption import encryption_menu
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Base64 🔵 Encode", callback_data="enc:b64_enc"),
            InlineKeyboardButton(text="Base64 🔵 Decode", callback_data="enc:b64_dec"),
        ],
        [
            InlineKeyboardButton(text="SHA-256 🔴", callback_data="enc:sha256"),
            InlineKeyboardButton(text="MD5 🔴",     callback_data="enc:md5"),
        ],
        [
            InlineKeyboardButton(text="SHA-512 🔴", callback_data="enc:sha512"),
            InlineKeyboardButton(text="SHA-1 🔴",   callback_data="enc:sha1"),
        ],
        [
            InlineKeyboardButton(text="URL 🟢 Encode", callback_data="enc:url_enc"),
            InlineKeyboardButton(text="URL 🟢 Decode", callback_data="enc:url_dec"),
        ],
        [InlineKeyboardButton(text="◀️ رجوع", callback_data="back:main")],
    ])
    try:
        await cb.message.edit_text(
            encryption_menu(), reply_markup=kb, parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض قائمة التشفير: %s", e)


@router.callback_query(F.data.startswith("enc:"))
async def cb_enc_choose_op(cb: CallbackQuery, state: FSMContext) -> None:
    operation = cb.data.split(":")[1]
    await state.set_state(ToolState.waiting_enc_text)
    await state.update_data(enc_operation=operation)
    await cb.answer()

    op_hints = {
        "b64_enc":  "أرسل النص لتشفيره بـ Base64",
        "b64_dec":  "أرسل النص المشفر بـ Base64 لفك تشفيره",
        "sha256":   "أرسل النص للحصول على SHA-256 Hash",
        "sha512":   "أرسل النص للحصول على SHA-512 Hash",
        "sha1":     "أرسل النص للحصول على SHA-1 Hash",
        "md5":      "أرسل النص للحصول على MD5 Hash",
        "url_enc":  "أرسل النص لتشفيره كـ URL",
        "url_dec":  "أرسل الـ URL المشفر لفك تشفيره",
    }
    hint = op_hints.get(operation, "أرسل النص:")
    try:
        await cb.message.edit_text(
            f"🧠 <b>{hint}</b>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة التشفير: %s", e)


@router.message(ToolState.waiting_enc_text, F.text)
async def handle_enc_text(message: Message, state: FSMContext) -> None:
    data      = await state.get_data()
    operation = data.get("enc_operation", "sha256")
    await state.clear()
    try:
        result = t.encrypt_tool(operation, message.text)
        await message.answer(result, parse_mode="HTML", reply_markup=_back_kb())
    except Exception as e:
        logger.error("خطأ في التشفير: %s", e)
        await message.answer("❌ حدث خطأ في التشفير، حاول مرة أخرى.", reply_markup=_back_kb())


# ══════════════════════════════════════════════════════════════
#  9. تحليل الدومين
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:domain_analyzer")
async def cb_domain_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_domain)
    db.log_tool_usage(cb.from_user.id, "domain_analyzer")
    try:
        await cb.message.edit_text(
            "🌍 <b>تحليل الدومين</b>\n"
            f"{'━' * 22}\n\n"
            "أرسل اسم الدومين للتحليل:\n\n"
            "مثال: <code>google.com</code> أو <code>github.io</code>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة تحليل الدومين: %s", e)


@router.message(ToolState.waiting_domain, F.text)
async def handle_domain(message: Message, state: FSMContext) -> None:
    await state.clear()
    msg = await message.answer("⏳ جاري تحليل الدومين...")
    try:
        result = await t.analyze_domain(message.text.strip())
        await msg.edit_text(result, parse_mode="HTML", reply_markup=_back_kb(), disable_web_page_preview=True)
    except Exception as e:
        logger.error("خطأ في analyze_domain: %s", e)
        await _send_error(msg)


# ══════════════════════════════════════════════════════════════
#  10. كشف VPN / Proxy
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:vpn_detector")
async def cb_vpn_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(ToolState.waiting_vpn_ip)
    db.log_tool_usage(cb.from_user.id, "vpn_detector")
    try:
        await cb.message.edit_text(
            "🛡️ <b>كشف VPN / Proxy</b>\n"
            f"{'━' * 22}\n\n"
            "أرسل عنوان IP للفحص:\n\n"
            "مثال: <code>8.8.8.8</code>",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض نافذة كشف VPN: %s", e)


@router.message(ToolState.waiting_vpn_ip, F.text)
async def handle_vpn(message: Message, state: FSMContext) -> None:
    await state.clear()
    msg = await message.answer("⏳ جاري فحص عنوان IP...")
    try:
        result = await t.detect_vpn(message.text.strip())
        await msg.edit_text(result, parse_mode="HTML", reply_markup=_back_kb())
    except Exception as e:
        logger.error("خطأ في detect_vpn: %s", e)
        await _send_error(msg)


# ══════════════════════════════════════════════════════════════
#  11. المعلومات القانونية
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:legal_info")
async def cb_legal_start(cb: CallbackQuery) -> None:
    await cb.answer()
    db.log_tool_usage(cb.from_user.id, "legal_info")
    from tools.legal_info import get_legal_info
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 الإبلاغ عن حسابات",  callback_data="legal:report")],
        [InlineKeyboardButton(text="🔒 حماية حسابك",         callback_data="legal:protect")],
        [InlineKeyboardButton(text="📋 سياسات الخصوصية",     callback_data="legal:privacy")],
        [InlineKeyboardButton(text="🆘 روابط الدعم الرسمي",  callback_data="legal:support")],
        [InlineKeyboardButton(text="◀️ رجوع",                callback_data="back:main")],
    ])
    try:
        await cb.message.edit_text(
            get_legal_info("main"), reply_markup=kb, parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض المعلومات القانونية: %s", e)


@router.callback_query(F.data.startswith("legal:"))
async def cb_legal_topic(cb: CallbackQuery) -> None:
    await cb.answer()
    topic = cb.data.split(":")[1]
    from tools.legal_info import get_legal_info
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ رجوع للمعلومات القانونية", callback_data="tool:legal_info")],
    ])
    try:
        await cb.message.edit_text(
            get_legal_info(topic), reply_markup=kb, parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error("خطأ في عرض موضوع قانوني: %s", e)


# ══════════════════════════════════════════════════════════════
#  12. التوعية الأمنية
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "tool:security_tips")
async def cb_tips_start(cb: CallbackQuery) -> None:
    await cb.answer()
    db.log_tool_usage(cb.from_user.id, "security_tips")
    from tools.security_tips import get_security_tips_menu
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 أمان الحسابات",        callback_data="tips:accounts")],
        [InlineKeyboardButton(text="📱 أمان الهاتف",          callback_data="tips:mobile")],
        [InlineKeyboardButton(text="🌐 أمان الإنترنت",        callback_data="tips:internet")],
        [InlineKeyboardButton(text="🎣 الحماية من Phishing",  callback_data="tips:phishing")],
        [InlineKeyboardButton(text="◀️ رجوع",                 callback_data="back:main")],
    ])
    try:
        await cb.message.edit_text(
            get_security_tips_menu(), reply_markup=kb, parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض قائمة التوعية الأمنية: %s", e)


@router.callback_query(F.data.startswith("tips:"))
async def cb_tips_topic(cb: CallbackQuery) -> None:
    await cb.answer()
    topic = cb.data.split(":")[1]
    from tools.security_tips import get_security_tip
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ رجوع للتوعية الأمنية", callback_data="tool:security_tips")],
    ])
    try:
        await cb.message.edit_text(
            get_security_tip(topic), reply_markup=kb, parse_mode="HTML",
        )
    except Exception as e:
        logger.error("خطأ في عرض موضوع أمني: %s", e)
