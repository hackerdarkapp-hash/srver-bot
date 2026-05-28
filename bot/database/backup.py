"""database/backup.py — نسخ احتياطي تلقائي على GitHub"""
  import asyncio
  import base64
  import json
  import logging
  import os
  from datetime import datetime

  logger = logging.getLogger(__name__)

  GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
  GITHUB_REPO  = os.getenv("GITHUB_REPO", "hackerdarkapp-hash/srver-bot")
  SEEDS_PATH   = "bot/seeds.json"

  _backup_lock = asyncio.Lock()


  def export_to_json() -> str:
      from database.db import get_all_buttons_flat, get_response
      buttons = get_all_buttons_flat()
      result = []
      for btn in buttons:
          resp = get_response(btn["id"])
          entry = {
              "id":          btn["id"],
              "parent_id":   btn["parent_id"],
              "label":       btn["label"],
              "section":     btn["section"],
              "is_active":   btn["is_active"],
              "position":    btn["position"],
              "description": btn["description"] or "",
              "tool_id":     btn["tool_id"],
          }
          if resp and resp.get("response_type", "none") != "none":
              entry["response"] = {
                  "response_type": resp["response_type"],
                  "text_content":  resp.get("text_content"),
                  "file_id":       resp.get("file_id"),
                  "file_type":     resp.get("file_type"),
                  "url":           resp.get("url"),
                  "caption":       resp.get("caption"),
                  "parse_mode":    resp.get("parse_mode", "HTML"),
              }
          result.append(entry)
      return json.dumps(result, ensure_ascii=False, indent=2)


  async def _push() -> None:
      if not GITHUB_TOKEN:
          logger.warning("GITHUB_TOKEN غير موجود — تخطي النسخ الاحتياطي")
          return
      async with _backup_lock:
          try:
              import aiohttp
              loop = asyncio.get_event_loop()
              content_str = await loop.run_in_executor(None, export_to_json)
              content_b64 = base64.b64encode(content_str.encode()).decode()
              hdrs = {
                  "Authorization": f"token {GITHUB_TOKEN}",
                  "Accept": "application/vnd.github.v3+json",
                  "User-Agent": "srver-bot-backup",
              }
              url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SEEDS_PATH}"
              async with aiohttp.ClientSession() as session:
                  async with session.get(url, headers=hdrs) as r:
                      sha = (await r.json()).get("sha") if r.status == 200 else None
                  payload = {
                      "message": f"backup {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                      "content": content_b64,
                  }
                  if sha:
                      payload["sha"] = sha
                  async with session.put(url, headers=hdrs, json=payload) as r:
                      if r.status in (200, 201):
                          logger.info("تم النسخ الاحتياطي على GitHub (%d زر)", len(json.loads(content_str)))
                      else:
                          logger.error("فشل النسخ الاحتياطي: %d", r.status)
          except Exception as e:
              logger.error("خطأ في النسخ الاحتياطي: %s", e)


  def schedule_backup() -> None:
      """جدولة النسخ الاحتياطي في الخلفية."""
      try:
          loop = asyncio.get_running_loop()
          loop.create_task(_push())
      except RuntimeError:
          pass
  