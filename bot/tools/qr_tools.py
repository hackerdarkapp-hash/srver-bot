"""
tools/qr_tools.py — توليد QR Code وتحليل النصوص
"""

import io
import re
import logging
import qrcode
from qrcode.image.pure import PyPNGImage

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s]+")


def generate_qr(text: str) -> io.BytesIO:
    """توليد صورة QR من نص"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img    = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def analyze_qr_text(text: str) -> str:
    """تحليل النص المستخرج من QR"""
    text = text.strip()
    if not text:
        return "⚠️ النص فارغ."

    lines = [
        f"📷 <b>تحليل QR Code</b>",
        f"{'━' * 22}",
        f"📝 <b>المحتوى:</b>",
        f"<code>{text[:200]}</code>",
        "",
    ]

    # تحديد النوع
    if text.startswith("http://") or text.startswith("https://"):
        lines.append("🔗 <b>النوع:</b> رابط URL")
        if text.startswith("http://"):
            lines.append("⚠️ <b>تحذير:</b> الرابط غير مشفر (HTTP) — كن حذراً!")
        else:
            lines.append("✅ <b>الأمان:</b> الرابط مشفر (HTTPS)")
        lines.append(f"🌐 <b>الدومين:</b> {text.split('/')[2] if len(text.split('/')) > 2 else '—'}")

    elif text.startswith("WIFI:"):
        lines.append("📶 <b>النوع:</b> بيانات WiFi")
        parts = text[5:].split(";")
        for p in parts:
            if p.startswith("S:"):
                lines.append(f"  📡 الشبكة: <code>{p[2:]}</code>")
            elif p.startswith("P:"):
                lines.append(f"  🔑 كلمة المرور: <code>{p[2:]}</code>")
            elif p.startswith("T:"):
                lines.append(f"  🔒 التشفير: {p[2:]}")

    elif text.startswith("BEGIN:VCARD"):
        lines.append("👤 <b>النوع:</b> بطاقة اتصال (vCard)")

    elif text.startswith("mailto:"):
        lines.append(f"📧 <b>النوع:</b> بريد إلكتروني")
        lines.append(f"  📮 العنوان: <code>{text[7:]}</code>")

    elif text.startswith("tel:"):
        lines.append(f"📞 <b>النوع:</b> رقم هاتف")
        lines.append(f"  ☎️ الرقم: <code>{text[4:]}</code>")

    elif "@" in text and "." in text.split("@")[-1]:
        lines.append("📧 <b>النوع:</b> بريد إلكتروني")

    else:
        lines.append("📄 <b>النوع:</b> نص عادي")

    lines.append(f"\n📏 <b>الطول:</b> {len(text)} حرف")
    return "\n".join(lines)
