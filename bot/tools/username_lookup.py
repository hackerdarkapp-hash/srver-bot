"""
tools/username_lookup.py — البحث عن اسم المستخدم عبر المنصات
"""

import asyncio
import aiohttp
import logging

logger = logging.getLogger(__name__)

PLATFORMS = {
    "GitHub": {
        "url": "https://api.github.com/users/{username}",
        "profile": "https://github.com/{username}",
        "api": True,
    },
    "Instagram": {
        "url": "https://www.instagram.com/{username}/",
        "profile": "https://www.instagram.com/{username}/",
        "api": False,
    },
    "TikTok": {
        "url": "https://www.tiktok.com/@{username}",
        "profile": "https://www.tiktok.com/@{username}",
        "api": False,
    },
    "X (Twitter)": {
        "url": "https://twitter.com/{username}",
        "profile": "https://twitter.com/{username}",
        "api": False,
    },
    "Facebook": {
        "url": "https://www.facebook.com/{username}",
        "profile": "https://www.facebook.com/{username}",
        "api": False,
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def _check_platform(session: aiohttp.ClientSession, name: str, config: dict, username: str) -> dict:
    url     = config["url"].format(username=username)
    profile = config["profile"].format(username=username)
    result  = {"platform": name, "status": "❓ غير معروف", "profile": profile, "details": {}}

    try:
        if config["api"] and name == "GitHub":
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result["status"] = "✅ موجود"
                    result["details"] = {
                        "الاسم":         data.get("name") or "—",
                        "المتابعون":     f"{data.get('followers', 0):,}",
                        "المستودعات":    str(data.get("public_repos", 0)),
                        "Bio":           (data.get("bio") or "—")[:80],
                        "الموقع":        data.get("location") or "—",
                    }
                elif resp.status == 404:
                    result["status"] = "❌ غير موجود"
                else:
                    result["status"] = f"⚠️ خطأ {resp.status}"
        else:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8),
                                   allow_redirects=True) as resp:
                if resp.status == 200:
                    result["status"] = "✅ موجود (احتمالي)"
                elif resp.status == 404:
                    result["status"] = "❌ غير موجود"
                elif resp.status in (301, 302, 303, 307, 308):
                    result["status"] = "⚠️ تحويل — قد يكون موجوداً"
                else:
                    result["status"] = f"⚠️ كود {resp.status}"
    except asyncio.TimeoutError:
        result["status"] = "⏱ انتهت المهلة"
    except Exception as e:
        result["status"] = "⚠️ تعذّر الفحص"
        logger.debug("Username lookup error for %s on %s: %s", username, name, e)

    return result


async def lookup_username(username: str) -> str:
    username = username.lstrip("@").strip()
    if not username or len(username) > 50:
        return "⚠️ اسم المستخدم غير صالح."

    lines = [f"🔎 <b>نتائج البحث عن:</b> <code>@{username}</code>\n{'━' * 22}\n"]

    async with aiohttp.ClientSession() as session:
        tasks   = [_check_platform(session, name, cfg, username) for name, cfg in PLATFORMS.items()]
        results = await asyncio.gather(*tasks)

    for r in results:
        lines.append(f"<b>🔷 {r['platform']}</b>")
        lines.append(f"  ├ الحالة:  {r['status']}")
        lines.append(f"  ├ الرابط:  {r['profile']}")
        if r["details"]:
            for k, v in r["details"].items():
                lines.append(f"  ├ {k}: {v}")
        lines.append("")

    lines.append("⚠️ <i>ملاحظة: النتائج تعليمية وقد لا تكون دقيقة 100% بسبب حماية المنصات.</i>")
    return "\n".join(lines)
