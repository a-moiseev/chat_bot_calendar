"""Мастер рассылки /broadcast (только для админов)."""

from __future__ import annotations

from aiogram import F, Router
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
from bot.keyboards import parse_buttons
from bot.states import BroadcastForm

router = Router(name="broadcast")
router.message.filter(IsAdmin)

_SKIP = "/skip"


def _payload_from_data(data: dict) -> BroadcastPayload:
    return BroadcastPayload(
        text=data.get("text"),
        media_type=data.get("media_type"),
        file_id=data.get("file_id"),
        buttons=data.get("buttons", []),
    )


def _confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="bcast:send"),
                InlineKeyboardButton(text="✖️ Отмена", callback_data="bcast:cancel"),
            ]
        ]
    )


@router.message(F.text == "/cancel")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer("Рассылка отменена.")


@router.message(F.text == "/broadcast")
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BroadcastForm.waiting_text)
    await message.answer(
        "Создаём рассылку. Пришлите <b>текст</b> сообщения "
        "(форматирование сохранится). /cancel — отмена."
    )


@router.message(BroadcastForm.waiting_text, F.text)
async def got_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.html_text)
    await state.set_state(BroadcastForm.waiting_media)
    await message.answer(
        f"Принято. Прикрепите <b>фото или видео</b> или отправьте {_SKIP}, чтобы без медиа."
    )


@router.message(BroadcastForm.waiting_media, F.photo)
async def got_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(media_type="photo", file_id=message.photo[-1].file_id)
    await _ask_buttons(message, state)


@router.message(BroadcastForm.waiting_media, F.video)
async def got_video(message: Message, state: FSMContext) -> None:
    await state.update_data(media_type="video", file_id=message.video.file_id)
    await _ask_buttons(message, state)


@router.message(BroadcastForm.waiting_media, F.text == _SKIP)
async def skip_media(message: Message, state: FSMContext) -> None:
    await state.update_data(media_type=None, file_id=None)
    await _ask_buttons(message, state)


async def _ask_buttons(message: Message, state: FSMContext) -> None:
    await state.set_state(BroadcastForm.waiting_buttons)
    await message.answer(
        "Кнопки — по одной в строке в формате <code>Текст - https://ссылка</code>.\n"
        f"Или {_SKIP}, чтобы без кнопок."
    )


@router.message(BroadcastForm.waiting_buttons, F.text == _SKIP)
async def skip_buttons(message: Message, state: FSMContext) -> None:
    await state.update_data(buttons=[])
    await _show_preview(message, state)


@router.message(BroadcastForm.waiting_buttons, F.text)
async def got_buttons(message: Message, state: FSMContext) -> None:
    try:
        buttons = parse_buttons(message.text)
    except ValueError as exc:
        await message.answer(f"Не получилось разобрать кнопки: {exc}\nПопробуйте ещё раз или {_SKIP}.")
        return
    await state.update_data(buttons=buttons)
    await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    payload = _payload_from_data(data)
    await message.answer("Так будет выглядеть рассылка:")
    await send_to(message.bot, message.chat.id, payload)
    count = await db.count_subscribers()
    await state.set_state(BroadcastForm.waiting_confirm)
    await message.answer(
        f"Отправить <b>{count}</b> подписчикам?", reply_markup=_confirm_kb()
    )


@router.callback_query(BroadcastForm.waiting_confirm, F.data == "bcast:cancel")
async def confirm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.")
    await callback.answer()


@router.callback_query(BroadcastForm.waiting_confirm, F.data == "bcast:send")
async def confirm_send(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text("Отправляю…")
    await callback.answer()
    payload = _payload_from_data(data)
    sent, failed = await broadcast_to_all(callback.bot, payload)
    await callback.message.answer(f"Готово. Отправлено: {sent}, ошибок: {failed}.")
