# chat_bot_calendar

Telegram-бот рассылки на aiogram 3.x. Пользователи подписываются командой `/start`,
администратор рассылает всем одинаковые сообщения (текст, фото/видео, инлайн-кнопки) —
сразу или по расписанию.

## Запуск

```bash
uv venv --python 3.13
uv pip install -r requirements.txt

cp .env.example .env                   # BOT_TOKEN (от @BotFather), ADMIN_IDS
cp welcome.example.html welcome.html   # текст приветствия для /start

.venv/bin/python -m bot.main
```

## Использование

- Подписчик: `/start` — подписка и приветствие.
- Админ (из `ADMIN_IDS`): `/broadcast` — пошаговый мастер (текст → фото/видео → кнопки →
  «сейчас» или «по расписанию»), `/cancel` — отмена.

Формат кнопок — по одной в строке: `Текст - https://ссылка`.
Время отложенной рассылки указывается в московском времени: `ДД.ММ.ГГГГ ЧЧ:ММ`.

## Тесты

```bash
.venv/bin/python -m pytest
```
