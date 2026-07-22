"""Tests for delivering a single broadcast message."""

from unittest.mock import AsyncMock

from bot.broadcaster import BroadcastPayload, send_to

CHAT_ID = 42
LONG_TEXT = "a" * 2000  # over the caption limit (1024), under the text limit


def _bot() -> AsyncMock:
    return AsyncMock()


async def test_text_only_sends_single_message() -> None:
    bot = _bot()
    payload = BroadcastPayload(text="hello", media_type=None, file_id=None, buttons=[])

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

    # Media without a caption; the full text goes as its own message so the
    # 1024-character caption limit never truncates it.
    bot.send_photo.assert_awaited_once()
    assert "caption" not in bot.send_photo.await_args.kwargs
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.args[1] == LONG_TEXT


async def test_buttons_go_on_text_message_not_media() -> None:
    bot = _bot()
    payload = BroadcastPayload(
        text="body",
        media_type="photo",
        file_id="file123",
        buttons=[("Button", "https://example.com")],
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
        buttons=[("Button", "https://example.com")],
    )

    await send_to(bot, CHAT_ID, payload)

    bot.send_video.assert_awaited_once()
    assert bot.send_video.await_args.kwargs["reply_markup"] is not None
    bot.send_message.assert_not_awaited()
