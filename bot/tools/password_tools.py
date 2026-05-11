"""
tools/password_tools.py — فحص قوة كلمة المرور وتوليدها
"""

import re
import secrets
import string


def check_password_strength(password: str) -> str:
    score   = 0
    tips    = []
    details = []

    length = len(password)
    if length >= 16:
        score += 3
        details.append("✅ الطول ممتاز (16+ حرف)")
    elif length >= 12:
        score += 2
        details.append("✅ الطول جيد (12+ حرف)")
    elif length >= 8:
        score += 1
        details.append("⚠️ الطول مقبول (8+ حرف)")
    else:
        tips.append("• أضف المزيد من الأحرف (8 على الأقل)")
        details.append("❌ الطول قصير جداً")

    has_upper = bool(re.search(r"[A-Z]", password))
    has_lower = bool(re.search(r"[a-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_spec  = bool(re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>?/\\|`~]", password))

    if has_upper and has_lower:
        score += 2
        details.append("✅ يحتوي على أحرف كبيرة وصغيرة")
    else:
        tips.append("• أضف أحرفاً كبيرة وصغيرة معاً")
        details.append("❌ يفتقر لتنوع الأحرف")

    if has_digit:
        score += 1
        details.append("✅ يحتوي على أرقام")
    else:
        tips.append("• أضف أرقاماً (0-9)")
        details.append("❌ لا يحتوي على أرقام")

    if has_spec:
        score += 2
        details.append("✅ يحتوي على رموز خاصة")
    else:
        tips.append("• أضف رموزاً خاصة (!@#$%...)")
        details.append("❌ لا يحتوي على رموز خاصة")

    # فحص الأنماط الشائعة
    common = ["123456", "password", "qwerty", "abc123", "111111", "000000",
              "iloveyou", "admin", "welcome", "monkey"]
    if password.lower() in common:
        score = 0
        tips.append("• كلمة المرور هذه شائعة جداً — غيّرها فوراً!")
        details.append("❌ كلمة مرور شائعة ومعروفة")

    # التقييم
    if score >= 8:
        strength = "💪 قوية جداً"
        bar = "🟩🟩🟩🟩🟩"
    elif score >= 6:
        strength = "✅ قوية"
        bar = "🟩🟩🟩🟩⬜"
    elif score >= 4:
        strength = "⚠️ متوسطة"
        bar = "🟨🟨🟨⬜⬜"
    elif score >= 2:
        strength = "🔴 ضعيفة"
        bar = "🟥🟥⬜⬜⬜"
    else:
        strength = "💀 ضعيفة جداً"
        bar = "🟥⬜⬜⬜⬜"

    lines = [
        f"🔐 <b>فحص كلمة المرور</b>",
        f"{'━' * 22}",
        f"📊 <b>القوة:</b> {strength}",
        f"📈 <b>التقييم:</b> {bar} ({score}/8)",
        f"📏 <b>الطول:</b> {length} حرف",
        "",
        "<b>التفاصيل:</b>",
    ]
    lines.extend(f"  {d}" for d in details)

    if tips:
        lines.append("")
        lines.append("<b>💡 اقتراحات التحسين:</b>")
        lines.extend(tips)

    lines.append(f"\n⚠️ <i>لا تشارك كلمات مرورك مع أحد.</i>")
    return "\n".join(lines)


def generate_password(length: int = 16, use_symbols: bool = True,
                       use_digits: bool = True, use_upper: bool = True) -> str:
    if length < 4:
        length = 4
    if length > 64:
        length = 64

    chars = string.ascii_lowercase
    required = [secrets.choice(string.ascii_lowercase)]

    if use_upper:
        chars += string.ascii_uppercase
        required.append(secrets.choice(string.ascii_uppercase))
    if use_digits:
        chars += string.digits
        required.append(secrets.choice(string.digits))
    if use_symbols:
        syms = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        chars += syms
        required.append(secrets.choice(syms))

    remaining = length - len(required)
    password  = required + [secrets.choice(chars) for _ in range(remaining)]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def password_gen_response(length: int = 16) -> str:
    pw1 = generate_password(length, True, True, True)
    pw2 = generate_password(length, True, True, True)
    pw3 = generate_password(length, False, True, True)

    return (
        f"🔑 <b>كلمات مرور مولّدة ({length} حرف)</b>\n"
        f"{'━' * 22}\n\n"
        f"🔐 <b>مع رموز (الأقوى):</b>\n"
        f"<code>{pw1}</code>\n\n"
        f"🔑 <b>بديلة مع رموز:</b>\n"
        f"<code>{pw2}</code>\n\n"
        f"🔢 <b>بدون رموز (أسهل حفظاً):</b>\n"
        f"<code>{pw3}</code>\n\n"
        f"💡 <i>انقر على كلمة المرور لنسخها تلقائياً.</i>\n"
        f"⚠️ <i>لا تشارك هذه الكلمات مع أحد واحفظها بأمان.</i>"
    )
