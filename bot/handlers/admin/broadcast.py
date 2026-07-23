"""
handlers/admin/broadcast.py
الإرسال الجماعي عبر جميع البوتات لكل المشتركين
"""

import asyncio
import io
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

import database as db
from config import ADMIN_ID
from utils.keyboards import admin_panel_keyboard

logger = logging.getLogger(__name__)
router = Router()

DELAY = 0.05


def _build_broadcast_payload(message: Message, source_bot: Bot) -> dict | None:
    """حوّل الرسالة إلى حمولة يمكن لأي بوت إرسالها، لا نسخها من بوت آخر."""
    source_bot_id = getattr(source_bot, "id", None)
    if message.text:
        return {"type": "text", "text": message.text}
    if message.photo:
        return {
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": message.caption,
            "source_bot_id": source_bot_id,
        }
    if message.video:
        return {
            "type": "video",
            "file_id": message.video.file_id,
            "caption": message.caption,
            "source_bot_id": source_bot_id,
        }
    if message.animation:
        return {
            "type": "animation",
            "file_id": message.animation.file_id,
            "caption": message.caption,
            "source_bot_id": source_bot_id,
        }
    if message.document:
        return {
            "type": "document",
            "file_id": message.document.file_id,
            "caption": message.caption,
            "source_bot_id": source_bot_id,
        }
    if message.audio:
        return {
            "type": "audio",
            "file_id": message.audio.file_id,
            "caption": message.caption,
            "source_bot_id": source_bot_id,
        }
    if message.voice:
        return {
            "type": "voice",
            "file_id": message.voice.file_id,
            "caption": message.caption,
            "source_bot_id": source_bot_id,
        }
    if message.video_note:
        return {
            "type": "video_note",
            "file_id": message.video_note.file_id,
            "source_bot_id": source_bot_id,
        }
    if message.sticker:
        return {
            "type": "sticker",
            "file_id": message.sticker.file_id,
            "source_bot_id": source_bot_id,
        }
    return None


async def _load_media_bytes(bot: Bot, payload: dict) -> bytes:
    """نزّل الوسيط مرة واحدة من البوت المصدر قبل توزيعه."""
    file_info = await bot.get_file(payload["file_id"])
    buffer = io.BytesIO()
    await bot.download_file(file_info.file_path, destination=buffer)
    return buffer.getvalue()


async def _send_broadcast_payload(bot: Bot, chat_id: int, payload: dict) -> None:
    """أرسل المحتوى باستخدام البوت الذي يستطيع الوصول إلى العضو."""
    kind = payload["type"]
    media = payload.get("media_bytes")
    extension = {
        "photo": "jpg",
        "video": "mp4",
        "animation": "mp4",
        "document": "bin",
        "audio": "mp3",
        "voice": "ogg",
        "video_note": "mp4",
        "sticker": "webp",
    }.get(kind, "bin")
    file_id = (
        BufferedInputFile(media, filename=f"broadcast-media.{extension}")
        if media is not None
        else payload.get("file_id")
    )
    caption = payload.get("caption")

    if kind == "text":
        await bot.send_message(chat_id=chat_id, text=payload["text"])
    elif kind == "photo":
        await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
    elif kind == "video":
        await bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
    elif kind == "animation":
        await bot.send_animation(chat_id=chat_id, animation=file_id, caption=caption)
    elif kind == "document":
        await bot.send_document(chat_id=chat_id, document=file_id, caption=caption)
    elif kind == "audio":
        await bot.send_audio(chat_id=chat_id, audio=file_id, caption=caption)
    elif kind == "voice":
        await bot.send_voice(chat_id=chat_id, voice=file_id, caption=caption)
    elif kind == "video_note":
        await bot.send_video_note(chat_id=chat_id, video_note=file_id)
    elif kind == "sticker":
        await bot.send_sticker(chat_id=chat_id, sticker=file_id)
    else:
        raise ValueError(f"نوع رسالة غير مدعوم: {kind}")


def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ لوحة التحكم", callback_data="ap:panel")]
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


class AdminReply(StatesGroup):
    """حالة مؤقتة تستقبل رسالة الأدمن بعد اختيار مستخدم للرد عليه."""

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
        f"📢 <b>الإرسال الجماعي</b>\n\n"
        f"أرسل الرسالة التي تريد إيصالها لجميع المشتركين.\n"
        "تدعم: نص · صورة · فيديو · صوت · ملف · استيكر\n\n"
        f"<i>⚠️ ستصل لكل المشتركين غير المحظورين عبر <b>{bots_count}</b> بوتات</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="ap:panel")]
        ]),
        parse_mode="HTML",
    )


@router.message(Broadcast.WAITING)
async def bc_receive_msg(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    payload = _build_broadcast_payload(message, bot)
    if not payload:
        await message.answer("⚠️ نوع الرسالة هذا غير مدعوم للإرسال الجماعي.")
        return
    await state.update_data(payload=payload)
    total = len(db.get_all_active_user_ids())
    from utils.bot_registry import get_all_bots
    bots_count = len(get_all_bots())
    await message.answer(
        f"👁 <b>معاينة الرسالة ↑</b>\n\n"
        f"سيتم الإرسال إلى <b>{total}</b> مشترك عبر <b>{bots_count}</b> بوت.\n"
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
    payload = data.get("payload")
    if not payload:
        await cb.answer("⚠️ لم يتم العثور على الرسالة.", show_alert=True)
        return
    await cb.answer("⏳ جارٍ الإرسال...")
    status_msg = await cb.message.edit_text(
        "📤 <b>جارٍ الإرسال الجماعي عبر جميع البوتات...</b>",
        parse_mode="HTML",
    )
    from utils.bot_registry import get_all_bots
    all_bots = get_all_bots() or [bot]
    bots_by_id = {getattr(current_bot, "id", None): current_bot for current_bot in all_bots}
    source_bot = bots_by_id.get(payload.get("source_bot_id")) or bot
    if payload.get("file_id") and payload.get("media_bytes") is None:
        try:
            payload["media_bytes"] = await _load_media_bytes(source_bot, payload)
        except Exception as e:
            logger.error("تعذر تحميل وسيط الإرسال الجماعي: %s", e)
            await status_msg.edit_text(
                "❌ تعذر تجهيز الملف للإرسال. أعد المحاولة.",
                reply_markup=admin_panel_keyboard(),
                parse_mode="HTML",
            )
            return
    user_bot_map = db.get_active_user_bot_map()
    user_ids  = db.get_all_active_user_ids()
    sent      = 0
    delivered = set()
    for uid in user_ids:
        preferred = [
            bots_by_id[bot_id]
            for bot_id in user_bot_map.get(uid, [])
            if bot_id in bots_by_id
        ]
        fallback = [current_bot for current_bot in all_bots if current_bot not in preferred]
        candidates = preferred + fallback
        for current_bot in candidates:
            try:
                await _send_broadcast_payload(current_bot, uid, payload)
                delivered.add(uid)
                sent += 1
                break
            except TelegramForbiddenError:
                # العضو حظر هذا البوت؛ جرّب البوت الذي تفاعل معه بعده.
                pass
            except TelegramBadRequest:
                # قد يعني أن العضو لم يبدأ هذا البوت؛ جرّب البقية.
                pass
            except Exception as e:
                logger.warning(
                    "broadcast uid=%s bot=...%s: %s",
                    uid, current_bot.token[-6:], e,
                )
            await asyncio.sleep(DELAY)

    failed = len(user_ids) - len(delivered)
    await status_msg.edit_text(
        f"✅ <b>اكتمل الإرسال الجماعي</b>\n\n"
        f"📤 أُرسل:    <b>{sent}</b>\n"
        f"⚠️ لم يصل:   <b>{failed}</b>\n"
        f"🤖 البوتات: <b>{len(all_bots)}</b>",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("reply:") | F.data.startswith("sreply:"))
async def cb_reply_start(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("🚫", show_alert=True)
        return
    target_uid = int(cb.data.split(":")[1])
    await state.update_data(reply_target=target_uid)
    await state.set_state(AdminReply.WAITING)
    await cb.answer()
    await cb.message.reply(
        f"✏️ أرسل ردك على المستخدم <code>{target_uid}</code>:",
        reply_markup=_back_kb(),
        parse_mode="HTML",
    )


# لا يستقبل هذا المعالج إلا رسالة الرد بعد اختيار مستخدم فعليًا.
# استخدام معالج عام للأدمن هنا كان يبتلع /start و /admin وبقية الرسائل.
@router.message(AdminReply.WAITING)
async def admin_fwd_reply(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
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
