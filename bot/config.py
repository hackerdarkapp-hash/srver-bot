"""config.py — ثوابت الإعداد المركزية"""
import os

BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", os.getenv("BOT_TOKEN", ""))
ADMIN_ID       = int(os.getenv("ADMIN_TELEGRAM_ID", os.getenv("ADMIN_ID", "0")))
SESSION_SECRET = os.getenv("SESSION_SECRET", "tg-bot-secret")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "buttons.db")

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
