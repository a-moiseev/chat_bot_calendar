"""FSM-состояния мастера рассылки."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class BroadcastForm(StatesGroup):
    waiting_text = State()
    waiting_media = State()
    waiting_buttons = State()
    waiting_when = State()
    waiting_datetime = State()
    waiting_confirm = State()
