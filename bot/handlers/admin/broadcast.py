"""
handlers/admin/broadcast.py
═══════════════════════════
① الإرسال الجماعي  — الأدمن يرسل رسالة لكل المشتركين عبر جميع البوتات
② الرد على رسائل الدعم — الأدمن يرد على رسالة مستخدم
"""

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
  CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

import database as db
from config import ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

DELAY = 0.05


def is_admin(uid: int) -> bool:
  return uid == ADMIN_ID


def _back_kb() -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="◄️ لوحة التحكم", callback_data="ap:panel")]
  ])


def _confirm_kb() -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(inline_keyboard=[
      [
          InlineKeyboardButton(text="✅ إرسال الآن", callback_data="bc:confirm"),
          InlineKeyboardButton(text="❌ إلغاء",      callback_data="ap:panel"),
      ]
  ])


class Broadcast(StatesGroup):
  WAITING = State()


@router.callback_query(F.data == "ap:broadcast")
async def cb_broadcast_start(cb: CallbackQuery, state: FSMContext) -> None:
  if not is_admin(cb.from_user.id):
      await cb.answer("🚫", show_alert=True)
      return
  await cb.answer()
  await state.set_state(Broadcast.WAITING)
  from utils.bot_registry import get_all_bots
  bots_count = len(get_all_bots())
  await cb.message.edit_text(
      f"📢 <b>الإرسال الجماعي</b>

"
      f"أرسل الرسالة التي تريد إيصالها لجميع المشتركين.
"
      "تدعم: نص · صورة · فيديو · صوت · ملف · استيكر

"
      f"<i>⚠️ ستصل لكل المشتركين غير المحظورين عبر <b>{bots_count}</b> بوتات</i>",
      reply_markup=InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="❌ إلغاء", callback_data="ap:panel")]
      ]),
      parse_mode="HTML",
  )


@router.message(Broadcast.WAITING)
async def bc_receive_msg(message: Message, state: FSMContext) -> None:
  if not is_admin(message.from_user.id):
      return
  await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
  total = len(db.get_all_active_user_ids())
  from utils.bot_registry import get_all_bots
  bots_count = len(get_all_bots())
  await message.answer(
      f"👁 <b>معاينة الرسالة ↑</b>

"
      f"سيتم الإرسال إلى <b>{total}</b> مشترك عبر <b>{bots_count}</b> بوت.
"
      "هل تريد المتابعة؟",
      reply_markup=_confirm_kb(),
      parse_mode="HTML",
  )


@router.callback_query(F.data == "bc:confirm")
async def bc_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
  if not is_admin(cb.from_user.id):
      await cb.answer("🚫", show_alert=True)
      return
  data = await state.get_data()
  await state.clear()
  src_chat = data.get("chat_id")
  src_msg  = data.get("msg_id")
  if not src_msg:
      await cb.answer("⚠️ لم يتم العثور على الرسالة.", show_alert=True)
      return
  await cb.answer("⏳ جارٍ الإرسال...")
  status_msg = await cb.message.edit_text(
      "📤 <b>جارٍ الإرسال الجماعي عبر جميع البوتات...</b>",
      parse_mode="HTML",
  )
  from utils.bot_registry import get_all_bots
  all_bots = get_all_bots() or [bot]
  user_ids  = db.get_all_active_user_ids()
  sent      = 0
  failed    = 0
  delivered = set()
  for current_bot in all_bots:
      remaining = [uid for uid in user_ids if uid not in delivered]
      if not remaining:
          break
      for uid in remaining:
          try:
              await current_bot.copy_message(
                  chat_id=uid,
                  from_chat_id=src_chat,
                  message_id=src_msg,
              )
              delivered.add(uid)
              sent += 1
          except TelegramForbiddenError:
              pass
          except TelegramBadRequest:
              delivered.add(uid)
              failed += 1
          except Exception as e:
              logger.warning("broadcast uid=%s bot=...%s: %s", uid, current_bot.token[-6:], e)
          await asyncio.sleep(DELAY)
  blocked = len(user_ids) - len(delivered)
  from utils.keyboards import admin_panel_keyboard
  await status_msg.edit_text(
      f"✅ <b>اكتمل الإرسال الجماعي</b>

"
      f"📤 أُرسل:    <b>{sent}</b>
"
      f"🚫 محجوب:   <b>{blocked}</b>
"
      f"❌ فشل:     <b>{failed}</b>
"
      f"🤖 البوتات: <b>{len(all_bots)}</b>",
      reply_markup=admin_panel_keyboard(),
      parse_mode="HTML",
  )


@router.callback_query(F.data.startswith("reply:"))
async def cb_reply_start(cb: CallbackQuery, state: FSMContext) -> None:
  if not is_admin(cb.from_user.id):
      await cb.answer("🚫", show_alert=True)
      return
  target_uid = int(cb.data.split(":")[1])
  await state.update_data(reply_target=target_uid)
  await cb.answer()
  await cb.message.reply(
      f"✏️ أرسل ردك على المستخدم <code>{target_uid}</code>:",
      reply_markup=_back_kb(),
      parse_mode="HTML",
  )


@router.message(lambda m: True)
async def admin_fwd_reply(message: Message, state: FSMContext, bot: Bot) -> None:
  if not is_admin(message.from_user.id):
      return
  data = await state.get_data()
  target = data.get("reply_target")
  if not target:
      return
  try:
      await bot.copy_message(chat_id=target, from_chat_id=message.chat.id, message_id=message.message_id)
      await message.reply("✅ تم إرسال الرد.", reply_markup=_back_kb())
  except TelegramForbiddenError:
      await message.reply("🚫 المستخدم حجب البوت.", reply_markup=_back_kb())
  except Exception as e:
      logger.warning("reply error: %s", e)
      await message.reply(f"❌ فشل الإرسال: {e}", reply_markup=_back_kb())
  await state.clear()
