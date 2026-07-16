"""Тесты отправки одного сообщения рассылки."""

from unittest.mock import AsyncMock

from bot.broadcaster import BroadcastPayload, send_to

CHAT_ID = 42
LONG_TEXT = "a" * 2000  # длиннее лимита подписи (1024), но короче лимита текста


def _bot() -> AsyncMock:
    return AsyncMock()


async def test_text_only_sends_single_message() -> None:
    bot = _bot()
    payload = BroadcastPayload(text="привет", media_type=None, file_id=None, buttons=[])

    await send_to(bot, CHAT_ID, payload)

    bot.send_message.assert_awaited_once()
    bot.send_photo.assert_not_awaited()
    bot.send_video.assert_not_awaited()


async def test_photo_with_long_text_is_split_into_two_messages() -> None:
    bot = _bot()
    payload = BroadcastPayload(
        text=LONG_TEXT, media_type="photo", file_id="file123", buttons=[]
    )

    await send_to(bot, CHAT_ID, payload)

    # Медиа без подписи, полный текст — отдельным сообщением (не режется 1024).
    bot.send_photo.assert_awaited_once()
    assert "caption" not in bot.send_photo.await_args.kwargs
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[1] == LONG_TEXT


async def test_buttons_go_on_text_message_not_media() -> None:
    bot = _bot()
    payload = BroadcastPayload(
        text="текст",
        media_type="photo",
        file_id="file123",
        buttons=[("Кнопка", "https://example.com")],
    )

    await send_to(bot, CHAT_ID, payload)

    assert bot.send_photo.await_args.kwargs["reply_markup"] is None
    assert bot.send_message.await_args.kwargs["reply_markup"] is not None


async def test_media_without_text_keeps_buttons_on_media() -> None:
    bot = _bot()
    payload = BroadcastPayload(
        text=None,
        media_type="video",
        file_id="file123",
        buttons=[("Кнопка", "https://example.com")],
    )

    await send_to(bot, CHAT_ID, payload)

    bot.send_video.assert_awaited_once()
    assert bot.send_video.await_args.kwargs["reply_markup"] is not None
    bot.send_message.assert_not_awaited()
