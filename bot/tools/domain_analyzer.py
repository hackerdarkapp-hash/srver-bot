"""
tools/domain_analyzer.py — تحليل الدومين (WHOIS + DNS)
"""

import asyncio
import aiohttp
import logging
import re

logger = logging.getLogger(__name__)

DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def _clean_domain(domain: str) -> str:
    domain = domain.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.split("/")[0]


async def analyze_domain(domain: str) -> str:
    domain = _clean_domain(domain)

    if not DOMAIN_RE.match(domain):
        return "⚠️ اسم دومين غير صالح. مثال: <code>google.com</code>"

    lines = [
        f"🌍 <b>تحليل الدومين:</b> <code>{domain}</code>",
        f"{'━' * 22}",
    ]

    # RDAP (بديل WHOIS مفتوح)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://rdap.org/domain/{domain}",
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # تاريخ التسجيل وانتهاء الصلاحية
                    events = {e.get("eventAction"): e.get("eventDate", "—")
                              for e in data.get("events", [])}
                    reg_date = events.get("registration", "—")[:10]
                    exp_date = events.get("expiration", "—")[:10]
                    upd_date = events.get("last changed", "—")[:10]

                    lines.append(f"📅 <b>تاريخ التسجيل:</b> {reg_date}")
                    lines.append(f"⏰ <b>تاريخ الانتهاء:</b> {exp_date}")
                    lines.append(f"🔄 <b>آخر تحديث:</b>    {upd_date}")

                    # الحالة
                    statuses = data.get("status", [])
                    if statuses:
                        status_ar = {
                            "clientTransferProhibited": "🔒 محمي من النقل",
                            "clientDeleteProhibited": "🔒 محمي من الحذف",
                            "clientUpdateProhibited": "🔒 محمي من التعديل",
                            "active": "✅ نشط",
                        }
                        status_text = " | ".join(
                            status_ar.get(s, s) for s in statuses[:3]
                        )
                        lines.append(f"🛡 <b>الحالة:</b> {status_text}")

                    # المسجّل
                    for entity in data.get("entities", []):
                        roles = entity.get("roles", [])
                        if "registrar" in roles:
                            vcard = entity.get("vcardArray", [None, []])[1]
                            for card in vcard:
                                if card[0] == "fn":
                                    lines.append(f"🏢 <b>جهة التسجيل:</b> {card[3]}")
                                    break
                            break

                    # خوادم الأسماء
                    ns_list = [ns.get("ldhName", "") for ns in data.get("nameservers", [])]
                    if ns_list:
                        lines.append(f"🖥 <b>Name Servers:</b>")
                        for ns in ns_list[:4]:
                            lines.append(f"  ├ <code>{ns}</code>")
                else:
                    lines.append(f"⚠️ تعذّر جلب بيانات WHOIS (كود: {resp.status})")
    except asyncio.TimeoutError:
        lines.append("⏱ انتهت مهلة جلب بيانات WHOIS")
    except Exception as e:
        logger.debug("RDAP error for %s: %s", domain, e)
        lines.append("⚠️ تعذّر جلب بيانات WHOIS")

    lines.append(f"\n⚠️ <i>المعلومات لأغراض تعليمية فقط.</i>")
    return "\n".join(lines)
