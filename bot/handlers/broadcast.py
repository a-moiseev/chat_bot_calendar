"""The /broadcast wizard (admins only)."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot import db
from bot.broadcaster import BroadcastPayload, broadcast_to_all, send_to
from bot.filters import IsAdmin
from bot.i18n import t
from bot.keyboards import ButtonParseError, dump_buttons, parse_buttons
from bot.states import BroadcastForm
from bot.timeutils import is_future, parse_send_at

router = Router(name="broadcast")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _origin(callback: CallbackQuery) -> Message:
    """The message a callback came from.

    aiogram types this as Message | InaccessibleMessage | None, but a callback
    on a keyboard the bot just sent always carries a real Message.
    """
    message = callback.message
    if not isinstance(message, Message):
        raise RuntimeError(f"Callback {callback.data!r} has no accessible message")
    return message


def _bot(message: Message) -> Bot:
    if message.bot is None:
        raise RuntimeError("Message is not bound to a Bot instance")
    return message.bot


def _payload_from_data(data: dict) -> BroadcastPayload:
    return BroadcastPayload(
        text=data.get("text"),
        media_type=data.get("media_type"),
        file_id=data.get("file_id"),
        buttons=data.get("buttons", []),
    )


def _skip_kb(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("button.skip"), callback_data=action)]
        ]
    )


def _when_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("button.send_now"), callback_data="bcast:now"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("button.schedule"), callback_data="bcast:schedule"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("button.cancel"), callback_data="bcast:cancel"
                )
            ],
        ]
    )


@router.message(F.text == "/cancel")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer(t("broadcast.cancelled"))


@router.message(F.text == "/broadcast")
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BroadcastForm.waiting_text)
    await message.answer(t("broadcast.ask_text"))


@router.message(BroadcastForm.waiting_text, F.text)
async def got_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.html_text)
    await state.set_state(BroadcastForm.waiting_media)
    await message.answer(
        t("broadcast.ask_media", skip=t("word.skip")),
        reply_markup=_skip_kb("bcast:skip_media"),
    )


@router.message(BroadcastForm.waiting_media, F.photo)
async def got_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo or []
    await state.update_data(media_type="photo", file_id=photo[-1].file_id)
    await _ask_buttons(message, state)


@router.message(BroadcastForm.waiting_media, F.video)
async def got_video(message: Message, state: FSMContext) -> None:
    video = message.video
    if video is None:
        return
    await state.update_data(media_type="video", file_id=video.file_id)
    await _ask_buttons(message, state)


@router.callback_query(BroadcastForm.waiting_media, F.data == "bcast:skip_media")
async def skip_media(callback: CallbackQuery, state: FSMContext) -> None:
    origin = _origin(callback)
    await state.update_data(media_type=None, file_id=None)
    await origin.edit_reply_markup()
    await callback.answer()
    await _ask_buttons(origin, state)


async def _ask_buttons(message: Message, state: FSMContext) -> None:
    await state.set_state(BroadcastForm.waiting_buttons)
    await message.answer(
        t("broadcast.ask_buttons", skip=t("word.skip")),
        reply_markup=_skip_kb("bcast:skip_buttons"),
    )


@router.callback_query(BroadcastForm.waiting_buttons, F.data == "bcast:skip_buttons")
async def skip_buttons(callback: CallbackQuery, state: FSMContext) -> None:
    origin = _origin(callback)
    await state.update_data(buttons=[])
    await origin.edit_reply_markup()
    await callback.answer()
    await _show_preview(origin, state)


@router.message(BroadcastForm.waiting_buttons, F.text)
async def got_buttons(message: Message, state: FSMContext) -> None:
    try:
        buttons = parse_buttons(message.text or "")
    except ButtonParseError as exc:
        await message.answer(
            t(
                "broadcast.buttons_parse_failed",
                reason=t(exc.key, **exc.params),
                skip=t("word.skip"),
            ),
            reply_markup=_skip_kb("bcast:skip_buttons"),
        )
        return
    await state.update_data(buttons=buttons)
    await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    payload = _payload_from_data(data)
    await message.answer(t("broadcast.preview"))
    await send_to(_bot(message), message.chat.id, payload)
    count = await db.count_subscribers()
    await state.set_state(BroadcastForm.waiting_when)
    await message.answer(t("broadcast.ask_when", count=count), reply_markup=_when_kb())


@router.callback_query(BroadcastForm.waiting_when, F.data == "bcast:cancel")
async def when_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _origin(callback).edit_text(t("broadcast.cancelled"))
    await callback.answer()


@router.callback_query(BroadcastForm.waiting_when, F.data == "bcast:now")
async def when_now(callback: CallbackQuery, state: FSMContext) -> None:
    origin = _origin(callback)
    data = await state.get_data()
    await state.clear()
    await origin.edit_text(t("broadcast.sending"))
    await callback.answer()
    payload = _payload_from_data(data)
    sent, failed = await broadcast_to_all(_bot(origin), payload)
    await origin.answer(t("broadcast.sent", sent=sent, failed=failed))


@router.callback_query(BroadcastForm.waiting_when, F.data == "bcast:schedule")
async def when_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastForm.waiting_datetime)
    await _origin(callback).edit_text(t("broadcast.ask_datetime"))
    await callback.answer()


@router.message(BroadcastForm.waiting_datetime, F.text)
async def got_datetime(message: Message, state: FSMContext) -> None:
    try:
        send_at = parse_send_at(message.text or "")
    except ValueError:
        await message.answer(t("broadcast.bad_datetime"))
        return
    if not is_future(send_at):
        await message.answer(t("broadcast.past_datetime"))
        return
    data = await state.get_data()
    await state.clear()
    await db.add_scheduled(
        text=data.get("text"),
        media_type=data.get("media_type"),
        file_id=data.get("file_id"),
        buttons=dump_buttons(data.get("buttons", [])),
        send_at=send_at,
    )
    await message.answer(t("broadcast.scheduled", send_at=send_at))
