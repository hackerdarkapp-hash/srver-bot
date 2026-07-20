"""
handlers/admin/button_wizard.py — معالج إضافة/تعديل الأزرار المخصصة
"""

import json
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
  CallbackQuery, InlineKeyboardButton,
  InlineKeyboardMarkup, Message,
)

import database as db
from config import ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

RESPONSE_TYPES = [
  ("📝 رسالة نصية", "text"),
  ("🖼 صورة",        "photo"),
  ("🎬 فيديو",       "video"),
  ("📁 ملف",         "file"),
  ("🎵 صوت",         "audio"),
  ("🔗 رابط ويب",    "url_link"),
  ("📨 رابط تلجرام", "tg_link"),
  ("🌐 WebApp",      "webapp"),
  ("❌ بدون رد",    "none"),
]

# أنواع الاستجابة التي تدعم الـ Caption
MEDIA_TYPES = {"photo", "video", "file", "audio"}


def is_admin(uid: int) -> bool:
  return uid == ADMIN_ID


def _cancel_kb() -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")]
  ])


def _skip_kb() -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="⏭ تخطى (بدون شرح)", callback_data="bw:skip_caption")],
      [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")],
  ])


class AddBtn(StatesGroup):
  TYPE        = State()
  PARENT      = State()
  LABEL       = State()
  SECTION     = State()
  RESP_TYPE   = State()
  RESP_VALUE  = State()
  CAPTION     = State()   # ← نص وصف للصورة/الفيديو/الملف/الصوت
  INLINE_BTNS = State()   # أزرار أسفل المحتوى (اختياري)


@router.callback_query(F.data == "ap:add")
async def cb_add_start(cb: CallbackQuery, state: FSMContext) -> None:
  if not is_admin(cb.from_user.id):
      await cb.answer("🚫", show_alert=True)
      return
  await cb.answer()
  await state.set_state(AddBtn.TYPE)
  kb = InlineKeyboardMarkup(inline_keyboard=[
      [
          InlineKeyboardButton(text="🔸 زر خارجي",  callback_data="bw:type:ext"),
          InlineKeyboardButton(text="🔹 زر داخلي",  callback_data="bw:type:int"),
      ],
      [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")],
  ])
  try:
      await cb.message.edit_text(
          "➕ <b>إضافة زر جديد</b>\n\nاختر نوع الزر:",
          reply_markup=kb, parse_mode="HTML",
      )
  except Exception:
      await cb.message.answer(
          "➕ <b>إضافة زر جديد</b>\n\nاختر نوع الزر:",
          reply_markup=kb, parse_mode="HTML",
      )


@router.callback_query(AddBtn.TYPE, F.data.startswith("bw:type:"))
async def cb_choose_type(cb: CallbackQuery, state: FSMContext) -> None:
  t = cb.data.split(":")[2]
  await state.update_data(btn_type=t)
  await cb.answer()

  if t == "int":
      top = db.get_top_level_buttons()
      if not top:
          await cb.answer("⚠️ لا توجد أزرار خارجية. أضف زراً خارجياً أولاً.", show_alert=True)
          await state.clear()
          return
      rows = [[InlineKeyboardButton(
          text=f"{'✅' if b['is_active'] else '❌'} {b['label']}",
          callback_data=f"bw:par:{b['id']}",
      )] for b in top]
      rows.append([InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")])
      await state.set_state(AddBtn.PARENT)
      try:
          await cb.message.edit_text(
              "🔹 <b>اختر الزر الخارجي الأب:</b>",
              reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
              parse_mode="HTML",
          )
      except Exception:
          await cb.message.answer(
              "🔹 <b>اختر الزر الخارجي الأب:</b>",
              reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
              parse_mode="HTML",
          )
  else:
      await state.set_state(AddBtn.LABEL)
      await cb.message.edit_text(
          "🔸 <b>أرسل اسم الزر الخارجي:</b>",
          reply_markup=_cancel_kb(), parse_mode="HTML",
      )


@router.callback_query(AddBtn.PARENT, F.data.startswith("bw:par:"))
async def cb_choose_parent(cb: CallbackQuery, state: FSMContext) -> None:
  parent_id = int(cb.data.split(":")[2])
  await state.update_data(parent_id=parent_id)
  await state.set_state(AddBtn.LABEL)
  await cb.answer()
  try:
      await cb.message.edit_text(
          "🔹 <b>أرسل اسم الزر الداخلي:</b>",
          reply_markup=_cancel_kb(), parse_mode="HTML",
      )
  except Exception:
      await cb.message.answer(
          "🔹 <b>أرسل اسم الزر الداخلي:</b>",
          reply_markup=_cancel_kb(), parse_mode="HTML",
      )


@router.message(AddBtn.LABEL)
async def bw_receive_label(message: Message, state: FSMContext) -> None:
  if not is_admin(message.from_user.id):
      return
  label = message.text.strip() if message.text else ""
  if not label:
      await message.answer("⚠️ الاسم لا يمكن أن يكون فارغاً.", reply_markup=_cancel_kb())
      return
  data = await state.get_data()
  await state.update_data(label=label)

  if data.get("btn_type") == "int":
      await _ask_resp_type(message, state)
  else:
      await state.set_state(AddBtn.SECTION)
      await message.answer(
          "📂 <b>اختر قسم الزر:</b>",
          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
              [
                  InlineKeyboardButton(text="🆓 مجاني",  callback_data="bw:sec:free"),
                  InlineKeyboardButton(text="💎 مدفوع",  callback_data="bw:sec:paid"),
              ],
              [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")],
          ]),
          parse_mode="HTML",
      )


@router.callback_query(AddBtn.SECTION, F.data.startswith("bw:sec:"))
async def cb_choose_section(cb: CallbackQuery, state: FSMContext) -> None:
  section = cb.data.split(":")[2]
  await state.update_data(section=section)
  await cb.answer()
  await _ask_resp_type(cb.message, state)


async def _ask_resp_type(msg, state: FSMContext) -> None:
  await state.set_state(AddBtn.RESP_TYPE)
  rows = [
      [InlineKeyboardButton(text=label, callback_data=f"bw:rt:{val}")]
      for label, val in RESPONSE_TYPES
  ]
  rows.append([InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")])
  try:
      await msg.edit_text(
          "📄 <b>اختر نوع الرد عند الضغط على الزر:</b>",
          reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
          parse_mode="HTML",
      )
  except Exception:
      await msg.answer(
          "📄 <b>اختر نوع الرد عند الضغط على الزر:</b>",
          reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
          parse_mode="HTML",
      )


@router.callback_query(AddBtn.RESP_TYPE, F.data.startswith("bw:rt:"))
async def cb_choose_resp_type(cb: CallbackQuery, state: FSMContext) -> None:
  resp_type = cb.data.split(":")[2]
  await state.update_data(resp_type=resp_type)
  await cb.answer()

  if resp_type == "none":
      await _ask_inline_buttons(cb.message, state)
      return

  prompts = {
      "text":      "📝 أرسل نص الرسالة:",
      "photo":     "🖼 أرسل الصورة:",
      "video":     "🎬 أرسل الفيديو:",
      "file":      "📁 أرسل الملف:",
      "audio":     "🎵 أرسل الملف الصوتي:",
      "url_link":  "🔗 أرسل الرابط (https://...):",
      "tg_link":   "📨 أرسل رابط التلجرام (t.me/...):",
      "webapp":    "🌐 أرسل رابط WebApp (https://...):",
  }
  prompt = prompts.get(resp_type, "أرسل المحتوى:")
  await state.set_state(AddBtn.RESP_VALUE)
  try:
      await cb.message.edit_text(prompt, reply_markup=_cancel_kb(), parse_mode="HTML")
  except Exception:
      await cb.message.answer(prompt, reply_markup=_cancel_kb(), parse_mode="HTML")


@router.message(AddBtn.RESP_VALUE)
async def bw_receive_value(message: Message, state: FSMContext) -> None:
  if not is_admin(message.from_user.id):
      return
  data = await state.get_data()
  resp_type = data.get("resp_type", "none")

  if resp_type == "text":
      text = message.text or message.caption or ""
      await state.update_data(text_content=text)

  elif resp_type == "photo":
      if message.photo:
          fid = message.photo[-1].file_id
          await state.update_data(file_id=fid, file_type="photo")
      elif message.text and message.text.startswith("http"):
          await state.update_data(url=message.text.strip(), file_id=None)
      else:
          await message.answer("⚠️ أرسل صورة أو رابط صورة.", reply_markup=_cancel_kb())
          return

  elif resp_type == "video":
      if not message.video:
          await message.answer("⚠️ أرسل فيديو.", reply_markup=_cancel_kb())
          return
      await state.update_data(file_id=message.video.file_id, file_type="video")

  elif resp_type == "file":
      if not message.document:
          await message.answer("⚠️ أرسل ملفاً.", reply_markup=_cancel_kb())
          return
      await state.update_data(file_id=message.document.file_id, file_type="file")

  elif resp_type == "audio":
      if not (message.audio or message.voice):
          await message.answer("⚠️ أرسل ملفاً صوتياً.", reply_markup=_cancel_kb())
          return
      fid = (message.audio or message.voice).file_id
      await state.update_data(file_id=fid, file_type="audio")

  elif resp_type in ("url_link", "tg_link", "webapp"):
      url = message.text.strip() if message.text else ""
      if not url.startswith("http") and resp_type != "tg_link":
          await message.answer("⚠️ الرابط غير صحيح، يجب أن يبدأ بـ https://", reply_markup=_cancel_kb())
          return
      await state.update_data(url=url)

  # إذا كان النوع وسائط، اطلب caption
  if resp_type in MEDIA_TYPES:
      await state.set_state(AddBtn.CAPTION)
      await message.answer(
          "✍️ <b>أضف نصاً تعريفياً (Caption) للمحتوى:</b>\n"
          "<i>يظهر هذا النص أسفل الصورة/الفيديو/الملف كوصف أو شرح للمنتج.</i>\n\n"
          "اكتب النص أو اضغط <b>تخطى</b> إذا لم تحتج لوصف.",
          reply_markup=_skip_kb(),
          parse_mode="HTML",
      )
      return

  await _ask_inline_buttons(message, state)


@router.message(AddBtn.CAPTION)
async def bw_receive_caption(message: Message, state: FSMContext) -> None:
  """استقبال نص الـ Caption للوسائط."""
  if not is_admin(message.from_user.id):
      return
  caption = message.text.strip() if message.text else ""
  await state.update_data(caption=caption)
  await _ask_inline_buttons(message, state)


@router.callback_query(AddBtn.CAPTION, F.data == "bw:skip_caption")
async def bw_skip_caption(cb: CallbackQuery, state: FSMContext) -> None:
  """تخطي إدخال الـ Caption."""
  await cb.answer()
  await state.update_data(caption="")
  await _ask_inline_buttons(cb.message, state)


async def _ask_inline_buttons(msg, state: FSMContext) -> None:
  await state.set_state(AddBtn.INLINE_BTNS)
  try:
      await msg.answer(
          "🔘 <b>هل تريد إضافة أزرار داخلية أسفل الرد؟</b>\n\n"
          "أرسل الأزرار بهذا الشكل (كل سطر = صف):\n"
          "<code>نص الزر | https://example.com</code>\n\n"
          "أو اضغط <b>تخطى</b> إذا لم تريد أزراراً.",
          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
              [InlineKeyboardButton(text="⏭ تخطى (بدون أزرار)", callback_data="bw:no_inline")],
              [InlineKeyboardButton(text="◀️ إلغاء", callback_data="ap:panel")],
          ]),
          parse_mode="HTML",
      )
  except Exception:
      pass


@router.callback_query(AddBtn.INLINE_BTNS, F.data == "bw:no_inline")
async def bw_no_inline(cb: CallbackQuery, state: FSMContext) -> None:
  await cb.answer()
  await state.update_data(inline_buttons=None)
  await _save_button(cb.message, state, edit=True)


@router.message(AddBtn.INLINE_BTNS)
async def bw_receive_inline_buttons(message: Message, state: FSMContext) -> None:
  if not is_admin(message.from_user.id):
      return
  text = message.text or ""
  buttons = []
  for line in text.strip().splitlines():
      line = line.strip()
      if not line or "|" not in line:
          continue
      parts = line.split("|", 1)
      btn_text = parts[0].strip()
      btn_url  = parts[1].strip()
      if btn_text and btn_url:
          buttons.append([{"text": btn_text, "url": btn_url}])

  if not buttons:
      await message.answer("⚠️ تنسيق الأزرار غير صحيح. مثال:\n<code>اضغط هنا | https://example.com</code>",
                           reply_markup=_cancel_kb(), parse_mode="HTML")
      return

  await state.update_data(inline_buttons=json.dumps(buttons, ensure_ascii=False))
  await _save_button(message, state)


async def _save_button(msg, state: FSMContext, edit: bool = False) -> None:
  data      = await state.get_data()
  await state.clear()

  btn_type   = data.get("btn_type", "ext")
  label      = data.get("label", "زر جديد")
  section    = data.get("section", "free")
  parent_id  = data.get("parent_id")
  resp_type  = data.get("resp_type", "none")
  text_cont  = data.get("text_content")
  file_id    = data.get("file_id")
  file_type  = data.get("file_type")
  url        = data.get("url")
  caption    = data.get("caption") or ""

  if btn_type == "int":
      section = "free"

  inline_buttons = data.get("inline_buttons")

  btn_id = db.add_button(label=label, section=section, parent_id=parent_id)
  db.set_response(
      button_id=btn_id, response_type=resp_type,
      text_content=text_cont, file_id=file_id,
      file_type=file_type, url=url,
      caption=caption,
      inline_buttons=inline_buttons,
  )

  from utils.keyboards import admin_panel_keyboard
  icon    = "🔸" if not parent_id else "🔹"
  sect_ar = "مجاني 🆓" if section == "free" else "مدفوع 💎"
  success_text = (
      f"✅ <b>تمت إضافة الزر بنجاح!</b>\n\n"
      f"{icon} الاسم:  <b>{label}</b>\n"
      f"📂 القسم:  {sect_ar}\n"
      f"📄 الرد:   {resp_type}\n"
      f"🆔 المعرّف: #{btn_id}"
  )
  if edit:
      try:
          await msg.edit_text(success_text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
          return
      except Exception:
          pass
  await msg.answer(success_text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
