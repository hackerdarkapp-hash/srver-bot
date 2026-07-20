"""
    handlers/user/navigation.py — تنقل المستخدم بين الأزرار
    """

    import json
    import logging
    from typing import Optional

    from aiogram import F, Router
    from aiogram.fsm.context import FSMContext
    from aiogram.types import (
      CallbackQuery, Message,
      InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo,
    )

    import database as db
    from utils.keyboards import build_start_keyboard, build_children_keyboard

    logger = logging.getLogger(__name__)
    router = Router()


    def _chat_type(cb: CallbackQuery) -> str:
      try:
          return cb.message.chat.type if cb.message else "private"
      except Exception:
          return "private"


    @router.callback_query(F.data.in_({"__noop__", "__sep__"}))
    async def cb_noop(cb: CallbackQuery) -> None:
      await cb.answer()


    async def _show_main(cb: CallbackQuery, state: FSMContext) -> None:
      from config import DEFAULT_WELCOME
      await state.clear()
      welcome_tmpl = db.get_setting("welcome_message", DEFAULT_WELCOME)
      name         = cb.from_user.first_name or "زائر"
      text         = welcome_tmpl.replace("{name}", name)
      chat_type    = _chat_type(cb)
      kb           = build_start_keyboard(chat_type=chat_type)
      try:
          await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
      except Exception:
          try:
              await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
          except Exception as e:
              logger.error("خطأ في عرض الصفحة الرئيسية: %s", e)


    @router.callback_query(F.data.in_({"tool:back_main", "section:free", "section:paid"}))
    async def cb_back_main(cb: CallbackQuery, state: FSMContext) -> None:
      await cb.answer()
      await _show_main(cb, state)


    @router.callback_query(F.data.startswith("back:"))
    async def cb_back(cb: CallbackQuery, state: FSMContext) -> None:
      await cb.answer()
      target = cb.data.split(":", 1)[1]
      if target in ("main", "0"):
          await _show_main(cb, state)
          return
      await state.clear()
      try:
          parent_id = int(target)
      except ValueError:
          await _show_main(cb, state)
          return
      btn = db.get_button(parent_id)
      if not btn:
          await _show_main(cb, state)
          return
      section   = btn.get("section", "free")
      chat_type = _chat_type(cb)
      keyboard  = build_children_keyboard(parent_id, btn.get("parent_id"), section, chat_type)
      try:
          await cb.message.edit_reply_markup(reply_markup=keyboard)
      except Exception:
          try:
              await cb.message.answer(
                  f"📂 <b>{btn['label']}</b>\nاختر من القائمة:",
                  reply_markup=keyboard, parse_mode="HTML",
              )
          except Exception as e:
              logger.error("خطأ في زر الرجوع: %s", e)


    @router.callback_query(F.data.startswith("nav:"))
    async def cb_navigate(cb: CallbackQuery, state: FSMContext) -> None:
      await cb.answer()
      try:
          btn_id = int(cb.data.split(":", 1)[1])
      except (ValueError, IndexError):
          await cb.answer("⚠️ بيانات غير صحيحة.", show_alert=True)
          return
      btn = db.get_button(btn_id)
      if not btn or not btn["is_active"]:
          await cb.answer("⚠️ هذا الزر غير متاح حالياً.", show_alert=True)
          return
      await _execute_button(cb, btn_id, btn)


    def _build_back_keyboard(
      back_data: str,
      extra_kb: Optional[InlineKeyboardMarkup] = None,
    ) -> InlineKeyboardMarkup:
      """يبني لوحة مفاتيح تحتوي على زر الرجوع (وأزرار إضافية إن وُجدت)."""
      back_row = [InlineKeyboardButton(text="◀️ رجوع", callback_data=back_data)]
      rows = list(extra_kb.inline_keyboard) if extra_kb else []
      rows.append(back_row)
      return InlineKeyboardMarkup(inline_keyboard=rows)


    def _parse_inline_buttons(raw: Optional[str]) -> Optional[InlineKeyboardMarkup]:
      if not raw:
          return None
      try:
          buttons = json.loads(raw)
          if not buttons:
              return None
          rows = []
          for row in buttons:
              r = []
              for btn in (row if isinstance(row, list) else [row]):
                  text = btn.get("text", "زر")
                  url  = btn.get("url")
                  cbd  = btn.get("callback_data")
                  if url:
                      r.append(InlineKeyboardButton(text=text, url=url))
                  elif cbd:
                      r.append(InlineKeyboardButton(text=text, callback_data=cbd))
              if r:
                  rows.append(r)
          return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
      except Exception as e:
          logger.warning("خطأ في تحليل الأزرار: %s", e)
          return None


    async def _send_response(
      message: Message,
      resp: dict,
      chat_type: str = "private",
      back_data: Optional[str] = None,
    ) -> None:
      rtype   = resp["response_type"]
      text    = resp.get("text_content") or ""
      file_id = resp.get("file_id")
      caption = resp.get("caption") or ""
      url     = resp.get("url") or ""
      pm      = resp.get("parse_mode") or "HTML"
      kb      = _parse_inline_buttons(resp.get("inline_buttons"))

      # إضافة زر الرجوع أسفل المحتوى
      if back_data:
          kb = _build_back_keyboard(back_data, kb)

      try:
          if rtype == "text":
              await message.answer(text, reply_markup=kb, parse_mode=pm)
          elif rtype == "photo":
              src = file_id or url
              if src:
                  await message.answer_photo(src, caption=caption or text,
                                             reply_markup=kb, parse_mode=pm)
          elif rtype == "video" and file_id:
              await message.answer_video(file_id, caption=caption or text,
                                         reply_markup=kb, parse_mode=pm)
          elif rtype == "file" and file_id:
              await message.answer_document(file_id, caption=caption or text,
                                            reply_markup=kb, parse_mode=pm)
          elif rtype == "audio" and file_id:
              await message.answer_audio(file_id, caption=caption or text,
                                         reply_markup=kb, parse_mode=pm)
          elif rtype in ("url_link", "tg_link"):
              pass
          elif rtype == "webapp" and url:
              if chat_type == "private":
                  webapp_kb = InlineKeyboardMarkup(inline_keyboard=[[
                      InlineKeyboardButton(text="🌐 فتح التطبيق", web_app=WebAppInfo(url=url))
                  ]])
              else:
                  webapp_kb = InlineKeyboardMarkup(inline_keyboard=[[
                      InlineKeyboardButton(text="🌐 فتح التطبيق", url=url)
                  ]])
              await message.answer(text or "اضغط لفتح التطبيق:", reply_markup=webapp_kb, parse_mode=pm)
          elif rtype == "redirect":
              redir = resp.get("redirect_to")
              if redir:
                  target = db.get_button(redir)
                  if target:
                      target_resp = db.get_response(redir)
                      if target_resp and target_resp["response_type"] != "none":
                          await _send_response(message, target_resp, chat_type, back_data=back_data)
      except Exception as e:
          logger.error("خطأ في إرسال الرد: %s", e)


    async def _execute_button(cb: CallbackQuery, btn_id: int, btn: dict) -> None:
      chat_type = _chat_type(cb)
      try:
          resp     = db.get_response(btn_id)
          children = db.get_children(btn_id)
          section  = btn.get("section", "free")

          # حساب بيانات زر الرجوع
          parent_id = btn.get("parent_id")
          back_data = f"back:{parent_id}" if parent_id else "tool:back_main"

          if resp and resp["response_type"] != "none":
              await _send_response(cb.message, resp, chat_type, back_data=back_data)

          if children:
              keyboard = build_children_keyboard(btn_id, btn.get("parent_id"), section, chat_type)
              label    = btn["label"]
              if resp and resp["response_type"] != "none":
                  await cb.message.answer(
                      f"📂 <b>{label}</b>\nاختر من القائمة:",
                      reply_markup=keyboard, parse_mode="HTML",
                  )
              else:
                  try:
                      await cb.message.edit_text(
                          f"📂 <b>{label}</b>\nاختر من القائمة:",
                          reply_markup=keyboard, parse_mode="HTML",
                      )
                  except Exception:
                      await cb.message.answer(
                          f"📂 <b>{label}</b>\nاختر من القائمة:",
                          reply_markup=keyboard, parse_mode="HTML",
                      )
          elif not resp or resp["response_type"] == "none":
              await cb.answer("⚠️ لا يوجد محتوى لهذا الزر.", show_alert=True)

      except Exception as e:
          logger.error("خطأ في تنفيذ الزر btn_id=%s: %s", btn_id, e)
    