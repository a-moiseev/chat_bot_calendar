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
from bot.keyboards import dump_buttons, parse_buttons
from bot.states import BroadcastForm
from bot.timeutils import is_future, parse_send_at

router = Router(name="broadcast")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


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
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=action)]
        ]
    )


def _when_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📣 Отправить сейчас", callback_data="bcast:now")],
            [InlineKeyboardButton(text="🕒 По расписанию", callback_data="bcast:schedule")],
            [InlineKeyboardButton(text="✖️ Отмена", callback_data="bcast:cancel")],
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
        "Принято. Прикрепите <b>фото или видео</b> — или нажмите «Пропустить».",
        reply_markup=_skip_kb("bcast:skip_media"),
    )


@router.message(BroadcastForm.waiting_media, F.photo)
async def got_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(media_type="photo", file_id=message.photo[-1].file_id)
    await _ask_buttons(message, state)


@router.message(BroadcastForm.waiting_media, F.video)
async def got_video(message: Message, state: FSMContext) -> None:
    await state.update_data(media_type="video", file_id=message.video.file_id)
    await _ask_buttons(message, state)


@router.callback_query(BroadcastForm.waiting_media, F.data == "bcast:skip_media")
async def skip_media(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(media_type=None, file_id=None)
    await callback.message.edit_reply_markup()
    await callback.answer()
    await _ask_buttons(callback.message, state)


async def _ask_buttons(message: Message, state: FSMContext) -> None:
    await state.set_state(BroadcastForm.waiting_buttons)
    await message.answer(
        "Кнопки — по одной в строке в формате <code>Текст - https://ссылка</code>.\n"
        "Или нажмите «Пропустить».",
        reply_markup=_skip_kb("bcast:skip_buttons"),
    )


@router.callback_query(BroadcastForm.waiting_buttons, F.data == "bcast:skip_buttons")
async def skip_buttons(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(buttons=[])
    await callback.message.edit_reply_markup()
    await callback.answer()
    await _show_preview(callback.message, state)


@router.message(BroadcastForm.waiting_buttons, F.text)
async def got_buttons(message: Message, state: FSMContext) -> None:
    try:
        buttons = parse_buttons(message.text)
    except ValueError as exc:
        await message.answer(
            f"Не получилось разобрать кнопки: {exc}\nПопробуйте ещё раз или «Пропустить».",
            reply_markup=_skip_kb("bcast:skip_buttons"),
        )
        return
    await state.update_data(buttons=buttons)
    await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    payload = _payload_from_data(data)
    await message.answer("Так будет выглядеть рассылка:")
    await send_to(message.bot, message.chat.id, payload)
    count = await db.count_subscribers()
    await state.set_state(BroadcastForm.waiting_when)
    await message.answer(
        f"Когда отправить <b>{count}</b> подписчикам?", reply_markup=_when_kb()
    )


@router.callback_query(BroadcastForm.waiting_when, F.data == "bcast:cancel")
async def when_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.")
    await callback.answer()


@router.callback_query(BroadcastForm.waiting_when, F.data == "bcast:now")
async def when_now(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text("Отправляю…")
    await callback.answer()
    payload = _payload_from_data(data)
    sent, failed = await broadcast_to_all(callback.bot, payload)
    await callback.message.answer(f"Готово. Отправлено: {sent}, ошибок: {failed}.")


@router.callback_query(BroadcastForm.waiting_when, F.data == "bcast:schedule")
async def when_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastForm.waiting_datetime)
    await callback.message.edit_text(
        "Пришлите дату и время отправки (мск). Например:\n"
        "<code>24.06.2026 19:00</code>, <code>24.06 19:00</code> (текущий год) "
        "или просто <code>19:00</code> (сегодня)."
    )
    await callback.answer()


@router.message(BroadcastForm.waiting_datetime, F.text)
async def got_datetime(message: Message, state: FSMContext) -> None:
    try:
        send_at = parse_send_at(message.text)
    except ValueError:
        await message.answer(
            "Не понял дату. Формат: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>. Попробуйте ещё раз."
        )
        return
    if not is_future(send_at):
        await message.answer("Это время уже прошло. Укажите будущую дату и время.")
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
    await message.answer(f"Запланировано на <b>{send_at}</b> (мск).")
