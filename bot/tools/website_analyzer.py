"""
tools/website_analyzer.py — تحليل المواقع الإلكترونية
"""

import asyncio
import ssl
import time
import socket
import aiohttp
import logging

logger = logging.getLogger(__name__)


def _resolve_ip(hostname: str) -> str:
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return "تعذّر التحليل"


async def _check_ssl(hostname: str) -> str:
    try:
        ctx  = ssl.create_default_context()
        loop = asyncio.get_event_loop()

        def _check():
            try:
                conn = ctx.wrap_socket(
                    socket.create_connection((hostname, 443), timeout=5),
                    server_hostname=hostname,
                )
                cert = conn.getpeercert()
                conn.close()
                exp = cert.get("notAfter", "—")
                return f"✅ صالح — ينتهي: {exp}"
            except ssl.SSLError as e:
                return f"❌ خطأ SSL: {str(e)[:40]}"
            except Exception:
                return "⚠️ لا يدعم HTTPS أو تعذّر الفحص"

        return await loop.run_in_executor(None, _check)
    except Exception:
        return "⚠️ تعذّر فحص SSL"


async def _get_ip_info(ip: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ip-api.com/json/{ip}?fields=country,city,isp,org,regionName",
                timeout=aiohttp.ClientTimeout(total=6)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return {}


async def analyze_website(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    from urllib.parse import urlparse
    parsed   = urlparse(url)
    hostname = parsed.netloc or parsed.path.split("/")[0]

    lines = [f"🌐 <b>تحليل الموقع:</b> <code>{hostname}</code>\n{'━' * 22}\n"]

    # IP
    ip = _resolve_ip(hostname)
    lines.append(f"🖥 <b>عنوان IP:</b> <code>{ip}</code>")

    # معلومات IP
    if ip and ip != "تعذّر التحليل":
        info = await _get_ip_info(ip)
        if info:
            lines.append(f"🌍 <b>الدولة:</b> {info.get('country','—')}")
            lines.append(f"🏙 <b>المدينة:</b> {info.get('city','—')}, {info.get('regionName','')}")
            lines.append(f"📡 <b>مزود الخدمة:</b> {info.get('isp','—')}")

    # SSL
    ssl_status = await _check_ssl(hostname)
    lines.append(f"🔒 <b>SSL:</b> {ssl_status}")

    # سرعة الاستجابة
    try:
        start = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=8),
                headers={"User-Agent": "Mozilla/5.0"},
                allow_redirects=True,
            ) as resp:
                elapsed = int((time.time() - start) * 1000)
                status  = resp.status
                server  = resp.headers.get("Server", "—")
                powered = resp.headers.get("X-Powered-By", "—")
                ct      = resp.headers.get("Content-Type", "—")
                lines.append(f"⚡ <b>زمن الاستجابة:</b> {elapsed} ms")
                lines.append(f"📊 <b>كود الحالة:</b> {status}")
                lines.append(f"🛠 <b>خادم الويب:</b> {server}")
                if powered != "—":
                    lines.append(f"⚙️ <b>التقنية:</b> {powered}")
                lines.append(f"📄 <b>نوع المحتوى:</b> {ct[:50]}")
    except asyncio.TimeoutError:
        lines.append("⚡ <b>زمن الاستجابة:</b> ⏱ انتهت المهلة")
    except Exception as e:
        lines.append(f"⚠️ تعذّر الاتصال: {str(e)[:60]}")

    lines.append(f"\n⚠️ <i>هذا الفحص لأغراض تعليمية فقط.</i>")
    return "\n".join(lines)
