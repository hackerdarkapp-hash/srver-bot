"""
tools/ip_geolocation.py — تحديد الموقع الجغرافي لعنوان IP
"""

import re
import aiohttp
import logging

logger = logging.getLogger(__name__)

IP_RE = re.compile(
    r"^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)


async def geolocate_ip(ip: str) -> str:
    ip = ip.strip()
    if not IP_RE.match(ip):
        return "⚠️ عنوان IP غير صالح. مثال: <code>8.8.8.8</code>"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,"
                f"regionName,city,zip,lat,lon,isp,org,as,proxy,hosting",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
    except Exception as e:
        return f"❌ خطأ في الاتصال: {str(e)[:60]}"

    if data.get("status") == "fail":
        return f"❌ فشل التحليل: {data.get('message','خطأ غير معروف')}"

    lat  = data.get("lat", 0)
    lon  = data.get("lon", 0)
    maps = f"https://maps.google.com/?q={lat},{lon}"

    proxy   = "✅ نعم" if data.get("proxy") else "❌ لا"
    hosting = "✅ نعم" if data.get("hosting") else "❌ لا"

    lines = [
        f"📍 <b>تحليل IP:</b> <code>{ip}</code>",
        f"{'━' * 22}",
        f"🌍 <b>الدولة:</b>      {data.get('country','—')} ({data.get('countryCode','—')})",
        f"🏙 <b>المنطقة:</b>     {data.get('regionName','—')}",
        f"🏘 <b>المدينة:</b>     {data.get('city','—')}",
        f"📮 <b>الرمز البريدي:</b> {data.get('zip','—')}",
        f"📡 <b>ISP:</b>         {data.get('isp','—')}",
        f"🏢 <b>المنظمة:</b>     {data.get('org','—')}",
        f"🔢 <b>ASN:</b>         {data.get('as','—')}",
        f"🎭 <b>Proxy:</b>       {proxy}",
        f"🖥 <b>Hosting:</b>     {hosting}",
        f"📍 <b>الإحداثيات:</b>  {lat}, {lon}",
        f"🗺 <b>الموقع التقريبي:</b> <a href='{maps}'>فتح في خرائط Google</a>",
        f"\n⚠️ <i>للأغراض التعليمية فقط.</i>",
    ]
    return "\n".join(lines)
