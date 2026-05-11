"""
tools/vpn_detector.py — كشف VPN / Proxy / Hosting
"""

import re
import aiohttp
import logging

logger = logging.getLogger(__name__)

IP_RE = re.compile(
    r"^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)


async def detect_vpn(ip: str) -> str:
    ip = ip.strip()
    if not IP_RE.match(ip):
        return "⚠️ عنوان IP غير صالح. مثال: <code>8.8.8.8</code>"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ip-api.com/json/{ip}?fields=status,message,country,city,isp,org,"
                f"proxy,hosting,mobile,query",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
    except Exception as e:
        return f"❌ خطأ في الاتصال: {str(e)[:60]}"

    if data.get("status") == "fail":
        return f"❌ فشل التحليل: {data.get('message', 'خطأ غير معروف')}"

    proxy   = data.get("proxy", False)
    hosting = data.get("hosting", False)
    mobile  = data.get("mobile", False)

    # تحديد نوع الاتصال
    if proxy and hosting:
        conn_type  = "⚠️ VPN + Hosting"
        conn_emoji = "🔴"
        risk       = "مرتفع جداً"
    elif proxy:
        conn_type  = "🎭 Proxy / VPN"
        conn_emoji = "🟠"
        risk       = "مرتفع"
    elif hosting:
        conn_type  = "🖥 Hosting / Server"
        conn_emoji = "🟡"
        risk       = "متوسط"
    elif mobile:
        conn_type  = "📱 شبكة جوال"
        conn_emoji = "🟢"
        risk       = "منخفض"
    else:
        conn_type  = "🏠 اتصال منزلي / مباشر"
        conn_emoji = "🟢"
        risk       = "منخفض"

    lines = [
        f"🛡️ <b>كشف VPN / Proxy</b>",
        f"{'━' * 22}",
        f"🔍 <b>IP المُحلَّل:</b> <code>{ip}</code>",
        f"",
        f"{conn_emoji} <b>نوع الاتصال:</b> {conn_type}",
        f"⚠️ <b>مستوى المخاطرة:</b> {risk}",
        f"",
        f"📡 <b>ISP:</b>     {data.get('isp','—')}",
        f"🏢 <b>المنظمة:</b> {data.get('org','—')}",
        f"🌍 <b>الدولة:</b>  {data.get('country','—')}",
        f"🏙 <b>المدينة:</b> {data.get('city','—')}",
        f"",
        f"🔎 <b>تفاصيل الكشف:</b>",
        f"  ├ Proxy:   {'✅ مكتشف' if proxy   else '❌ لم يُكتشف'}",
        f"  ├ Hosting: {'✅ مكتشف' if hosting else '❌ لم يُكتشف'}",
        f"  └ Mobile:  {'✅ نعم'    if mobile  else '❌ لا'}",
        f"",
        f"⚠️ <i>الكشف يعتمد على ip-api.com وقد لا يكون دقيقاً 100%.</i>",
        f"⚠️ <i>هذه الأداة لأغراض تعليمية فقط.</i>",
    ]
    return "\n".join(lines)
