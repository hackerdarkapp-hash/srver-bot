"""config.py — ثوابت الإعداد المركزية"""
import os
from dotenv import load_dotenv

# تحميل .env تلقائياً عند التشغيل المحلي
# في Render/Cloud يُتجاهل إذا لم يوجد الملف
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=False)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("BOT_TOKEN", "")).strip()


def _read_admin_id() -> int:
    """اقرأ معرّف الأدمن بدون إسقاط البوت إذا كان الإعداد غير صالح."""
    raw_id = os.getenv("ADMIN_TELEGRAM_ID", os.getenv("ADMIN_ID", "")).strip()
    if not raw_id:
        return 0
    try:
        admin_id = int(raw_id)
    except ValueError:
        # قيمة غير رقمية لا يمكن استخدامها مع Telegram API.
        return 0
    return admin_id if admin_id > 0 else 0


ADMIN_ID = _read_admin_id()
SESSION_SECRET = os.getenv("SESSION_SECRET", "tg-bot-secret")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "buttons.db")


# ══════════════════════════════════════════════════════════════
#  إعدادات تعدد البوتات
# ══════════════════════════════════════════════════════════════

def get_all_bot_tokens() -> list[str]:
    """
    يقرأ توكنات جميع البوتات من متغيرات البيئة.

    BOT_TOKEN_1, BOT_TOKEN_2, BOT_TOKEN_3 ...
    أو TELEGRAM_BOT_TOKEN_1, TELEGRAM_BOT_TOKEN_2 ...

    إذا لم توجد متغيرات مرقمة يرجع إلى BOT_TOKEN / TELEGRAM_BOT_TOKEN الموحد.
    جميع البوتات تشترك في نفس قاعدة البيانات والأدمن والإعدادات.
    """
    tokens: list[str] = []

    i = 1
    while True:
        t = os.getenv(f"BOT_TOKEN_{i}", os.getenv(f"TELEGRAM_BOT_TOKEN_{i}", "")).strip()
        if not t:
            break
        tokens.append(t)
        i += 1

    # الرجوع إلى التوكن الموحد إذا لم تُعرَّف متغيرات مرقمة
    if not tokens and BOT_TOKEN:
        tokens.append(BOT_TOKEN)

    return tokens

# حماية من السبام
RATE_LIMIT_SECONDS = 1
MAX_MSG_PER_MINUTE = 25

# رسالة الترحيب الافتراضية
DEFAULT_WELCOME = (
    "👋 <b>أهلاً وسهلاً {name}!</b>\n\n"
    "🆓 <b>الخدمات المجانية</b> — أدوات أمن سيبراني تعليمية للجميع\n"
    "💎 <b>الخدمات المميزة</b>  — تتطلب تفعيل الاشتراك\n\n"
    "اختر الخدمة التي تريدها 👇"
)

# أسماء الأدوات الافتراضية للبذر
DEFAULT_FREE_TOOLS = [
    {"label": "🔎 البحث عن اسم مستخدم",   "tool_id": "username_lookup"},
    {"label": "🌐 تحليل الموقع",            "tool_id": "website_analyzer"},
    {"label": "📍 تحليل IP",                "tool_id": "ip_geolocation"},
    {"label": "📧 فحص البريد الإلكتروني",   "tool_id": "email_checker"},
    {"label": "🔐 فحص قوة كلمة المرور",    "tool_id": "password_strength"},
    {"label": "🔑 توليد كلمة مرور",         "tool_id": "password_gen"},
    {"label": "📷 تحليل QR Code",           "tool_id": "qr_analyzer"},
    {"label": "🧠 أدوات التشفير",           "tool_id": "encryption"},
    {"label": "🌍 تحليل الدومين",           "tool_id": "domain_analyzer"},
    {"label": "🛡️ كشف VPN / Proxy",        "tool_id": "vpn_detector"},
    {"label": "⚖️ معلومات قانونية",         "tool_id": "legal_info"},
    {"label": "📚 التوعية الأمنية",          "tool_id": "security_tips"},
]
