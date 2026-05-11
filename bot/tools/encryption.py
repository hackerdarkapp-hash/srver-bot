"""
tools/encryption.py — أدوات التشفير وفك التشفير
"""

import base64
import hashlib
import urllib.parse
import logging

logger = logging.getLogger(__name__)

OPERATIONS = {
    "b64_enc":  "Base64 Encode",
    "b64_dec":  "Base64 Decode",
    "sha256":   "SHA-256 Hash",
    "md5":      "MD5 Hash",
    "url_enc":  "URL Encode",
    "url_dec":  "URL Decode",
    "sha512":   "SHA-512 Hash",
    "sha1":     "SHA-1 Hash",
}


def encrypt_tool(operation: str, text: str) -> str:
    text = text.strip()
    if not text:
        return "⚠️ النص فارغ."
    if len(text) > 5000:
        return "⚠️ النص طويل جداً (5000 حرف كحد أقصى)."

    op_name = OPERATIONS.get(operation, operation)
    result  = ""
    error   = ""

    try:
        if operation == "b64_enc":
            result = base64.b64encode(text.encode("utf-8")).decode("utf-8")
        elif operation == "b64_dec":
            try:
                result = base64.b64decode(text.encode("utf-8")).decode("utf-8")
            except Exception:
                error = "❌ النص ليس Base64 صالحاً"
        elif operation == "sha256":
            result = hashlib.sha256(text.encode("utf-8")).hexdigest()
        elif operation == "sha512":
            result = hashlib.sha512(text.encode("utf-8")).hexdigest()
        elif operation == "sha1":
            result = hashlib.sha1(text.encode("utf-8")).hexdigest()
        elif operation == "md5":
            result = hashlib.md5(text.encode("utf-8")).hexdigest()
        elif operation == "url_enc":
            result = urllib.parse.quote(text, safe="")
        elif operation == "url_dec":
            result = urllib.parse.unquote(text)
        else:
            error = f"❌ عملية غير معروفة: {operation}"
    except Exception as e:
        error = f"❌ خطأ: {str(e)[:80]}"

    is_hash = operation in ("sha256", "sha512", "sha1", "md5")

    lines = [
        f"🧠 <b>أدوات التشفير</b>",
        f"{'━' * 22}",
        f"🔧 <b>العملية:</b> {op_name}",
        f"📥 <b>المدخل:</b>",
        f"<code>{text[:200]}</code>",
        "",
    ]

    if error:
        lines.append(error)
    else:
        lines.append(f"📤 <b>النتيجة:</b>")
        # تقسيم النتائج الطويلة
        if len(result) > 200:
            chunks = [result[i:i+60] for i in range(0, min(len(result), 300), 60)]
            for chunk in chunks:
                lines.append(f"<code>{chunk}</code>")
        else:
            lines.append(f"<code>{result}</code>")

    if is_hash:
        lines.append(f"\n⚠️ <i>الـ Hash لا يمكن عكسه — هو للتحقق فقط.</i>")
    elif operation in ("b64_enc", "b64_dec"):
        lines.append(f"\n⚠️ <i>Base64 تشفير وليس تأمين — لا تستخدمه لحفظ كلمات المرور.</i>")

    return "\n".join(lines)


def encryption_menu() -> str:
    return (
        "🧠 <b>أدوات التشفير</b>\n"
        f"{'━' * 22}\n\n"
        "اختر العملية التي تريدها:\n\n"
        "🔵 <b>Base64:</b> تشفير/فك تشفير النصوص\n"
        "🔴 <b>Hash:</b> SHA-256, MD5, SHA-512, SHA-1\n"
        "🟢 <b>URL:</b> تشفير/فك تشفير روابط الويب\n\n"
        "اضغط على العملية المطلوبة 👇"
    )
