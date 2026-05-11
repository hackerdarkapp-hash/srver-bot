"""
tools/email_checker.py — فحص صحة البريد الإلكتروني
"""

import re
import asyncio
import logging
import dns.resolver

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com",
    "tempmail.com", "throwam.com", "yopmail.com", "sharklasers.com",
    "guerrillamailblock.com", "grr.la", "guerrillamail.info", "spam4.me",
    "trashmail.com", "dispostable.com", "fakeinbox.com",
}


async def _get_mx(domain: str) -> list[str]:
    loop = asyncio.get_event_loop()

    def _resolve():
        try:
            records = dns.resolver.resolve(domain, "MX")
            return sorted(
                [(r.preference, str(r.exchange).rstrip(".")) for r in records],
                key=lambda x: x[0]
            )
        except dns.resolver.NXDOMAIN:
            return []
        except dns.resolver.NoAnswer:
            return []
        except Exception:
            return None

    return await loop.run_in_executor(None, _resolve)


async def check_email(email: str) -> str:
    email = email.strip().lower()

    # فحص الصيغة
    if not EMAIL_RE.match(email):
        return (
            f"📧 <b>فحص البريد:</b> <code>{email}</code>\n"
            f"{'━' * 22}\n"
            f"❌ <b>النتيجة:</b> صيغة غير صالحة\n"
            f"⚠️ تأكد من كتابة البريد بشكل صحيح."
        )

    domain = email.split("@")[1]

    # فحص المجالات المؤقتة
    is_disposable = domain in DISPOSABLE_DOMAINS

    # فحص MX Records
    mx_records = await _get_mx(domain)

    lines = [
        f"📧 <b>فحص البريد:</b> <code>{email}</code>",
        f"{'━' * 22}",
        f"✅ <b>الصيغة:</b> صالحة",
        f"🌐 <b>الدومين:</b> <code>{domain}</code>",
        f"🗑 <b>بريد مؤقت:</b> {'⚠️ نعم — غير موثوق' if is_disposable else '✅ لا'}",
    ]

    if mx_records is None:
        lines.append(f"📮 <b>MX Records:</b> ⚠️ تعذّر الفحص")
    elif not mx_records:
        lines.append(f"📮 <b>MX Records:</b> ❌ لا توجد — الدومين لا يقبل البريد")
        lines.append(f"📊 <b>الحكم النهائي:</b> ❌ البريد غير صالح (لا يوجد خادم بريد)")
    else:
        lines.append(f"📮 <b>MX Records:</b> ✅ موجودة ({len(mx_records)} سجل)")
        for pref, mx in mx_records[:3]:
            lines.append(f"  ├ [{pref}] <code>{mx}</code>")
        verdict = "⚠️ ممكن — لكنه مؤقت" if is_disposable else "✅ قابل للتسليم"
        lines.append(f"📊 <b>الحكم النهائي:</b> {verdict}")

    lines.append(f"\n⚠️ <i>الفحص لا يضمن وجود صندوق البريد الفعلي.</i>")
    return "\n".join(lines)
